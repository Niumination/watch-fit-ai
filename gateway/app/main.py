"""
Voice Gateway — jembatan audio HP (jam) <-> AI agent.

Peran:
  WS biner (PCM16)  ->  VAD  ->  ASR  ->  Router  ->  Agent adapter  ->  VoiceFormatter  ->  TTS  ->  WS biner

Produksi: ganti bagian VAD/ASR/TTS dengan Pipecat (BSD-2) atau LiveKit Agents (Apache-2.0) —
struktur di file ini sengaja datar supaya mudah dipindahkan ke pipeline mereka.
Jalankan:  uvicorn app.main:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, UploadFile, File, Form
from fastapi.responses import JSONResponse, Response

from .adapters.base import AgentAdapter
from .adapters.echo import EchoAgent
from . import auth, tts, asr, formatter, dsp, registry, router, vad

log = logging.getLogger("gateway")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AgentCall Voice Gateway", version="1.0")


def build_agent(name: str, session_id: str) -> AgentAdapter:
    """Adapter dibuat dari config/agents.json (lihat app/registry.py)."""
    return registry.build(name)


@dataclass
class Session:
    ws: WebSocket
    device: str
    rate: int = 16_000
    agent_name: str = field(default_factory=lambda: registry.default_agent())
    agent: AgentAdapter | None = None
    speaking: bool = False            # TTS sedang diputar -> untuk gating barge-in
    muted: bool = False
    started_at: float = field(default_factory=time.time)
    turn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    vad_engine: vad.BaseVad = field(default_factory=lambda: vad.create_vad(sample_rate=16_000))

    def __post_init__(self):
        if self.rate != 16_000:
            self.vad_engine = vad.create_vad(sample_rate=self.rate)

    @property
    def frame_bytes(self) -> int:
        """20 ms PCM16 mono pada rate sesi (640 byte @16k, 320 byte @8k)."""
        return max(2, self.rate // 50) * 2

    def feed(self, chunk: bytes) -> bytes | None:
        """Proses per frame 20 ms — penting: satu pesan WS bisa berisi banyak frame."""
        if self.muted or not chunk:
            return None
        return self.vad_engine.feed(chunk)


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/health")
async def health():
    """Alias /healthz (dipakai Cloudflare/monitor yang menembak /health)."""
    return {"ok": True}


@app.post("/ask-audio")
async def ask_audio(
    audio: UploadFile = File(...),
    device: str = Form(...),
    token: str = Form(...),
    agent: str = Form(""),
):
    """Jalur A: HP kirim WAV rekaman mic HP -> kembali WAV jawaban + teks.

    Auth sama seperti WS (device + token). Ukuran maks ~2 MB (~60 dtk @16k mono).
    """
    if not auth.verify_device(device, token):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    raw = await audio.read()
    if len(raw) > 2_000_000:
        return JSONResponse({"error": "file terlalu besar (maks 2 MB)"}, status_code=413)
    pcm, rate = _wav_to_pcm16(raw)
    if not pcm:
        return JSONResponse({"error": "format audio tak dikenal (kirim WAV/3GP/MP4)"}, status_code=415)

    try:
        text = await asr.transcribe(pcm, sample_rate=rate)
    except Exception as exc:
        logging.getLogger("gateway.main").warning("ASR gagal (%s)", exc)
        text = ""
    if not text.strip():
        text = "(tidak terdengar — coba lagi lebih dekat ke mic HP)"

    agent_name = agent or registry.default_agent()
    try:
        ag = build_agent(agent_name, session_id=f"{device}-{int(time.time())}")
    except Exception as exc:
        # Agent default mati (mis. OPENCODE_URL tak ada) — jangan 500 ke HP;
        # balas dengan echo supaya jalur audio tetap terbukti.
        logging.getLogger("gateway.main").warning(
            "agent '%s' gagal dibangun (%s); pakai echo", agent_name, exc)
        from .registry import EchoAgent
        ag = EchoAgent()
    spoken: list[str] = []
    try:
        async for chunk in ag.stream(text):
            spoken.append(chunk)
    except Exception as exc:
        logging.getLogger("gateway.main").warning("agent stream gagal (%s)", exc)
    finally:
        try:
            await ag.aclose()
        except Exception:
            pass
    full = formatter.for_speech(" ".join(spoken).strip()) or "Maaf, agent tidak menjawab."
    wav = await _pcm_text_to_wav(full)
    return Response(
        content=wav,
        media_type="audio/wav",
        headers={"X-Transcript-In": text[:500], "X-Transcript-Out": full[:900]},
    )


def _to_mono_s16(raw: bytes, sampwidth: int, channels: int) -> bytes:
    """Konversi PCM sembarang (1/2/4 byte, mono/stereo) -> s16le mono murni stdlib.

    audioop dihapus di Python 3.13+, jadi konversi dibuat manual.
    """
    import array
    if sampwidth == 2:
        a = array.array("h")
        a.frombytes(raw[: len(raw) - (len(raw) % 2)])
        if a.itemsize != 2:
            a.byteswap()
        if channels >= 2 and len(a) >= 2:
            mono = array.array("h")
            for i in range(0, len(a) - 1, 2):
                mono.append((a[i] + a[i + 1]) // 2)
            return mono.tobytes()
        return a.tobytes()
    if sampwidth == 1:
        a = array.array("B")
        a.frombytes(raw)
        out = array.array("h", ((b - 128) * 256 for b in a))
        return out.tobytes()
    if sampwidth == 4:
        a = array.array("i")
        a.frombytes(raw[: len(raw) - (len(raw) % 4)])
        if a.itemsize != 4:
            a.byteswap()
        out = array.array("h", (max(-32768, min(32767, v >> 16)) for v in a))
        return out.tobytes()
    return raw


def _resample_linear(raw: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Resampling linear sederhana (cukup untuk ASR; bukan kualitas hi-fi)."""
    import array
    a = array.array("h")
    a.frombytes(raw[: len(raw) - (len(raw) % 2)])
    if a.itemsize != 2:
        a.byteswap()
    n_in = len(a)
    if n_in < 2 or src_rate == dst_rate:
        return a.tobytes()
    n_out = max(1, int(n_in * dst_rate / src_rate))
    step = (n_in - 1) / (n_out - 1)
    out = array.array("h")
    for j in range(n_out):
        pos = j * step
        i = int(pos)
        frac = pos - i
        lo = a[i]
        hi = a[min(i + 1, n_in - 1)]
        out.append(int(lo + (hi - lo) * frac))
    return out.tobytes()


def _wav_to_pcm16(raw: bytes) -> tuple[bytes, int]:
    """Decode WAV/3GP/MP4 via ffmpeg bila ada, else WAV PCM langsung."""
    import io
    import shutil
    import subprocess
    import wave
    if raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
        try:
            with wave.open(io.BytesIO(raw), "rb") as w:
                rate = w.getframerate()
                n = w.getnchannels()
                samp = w.getsampwidth()
                frames = w.readframes(w.getnframes())
                frames = _to_mono_s16(frames, samp, n)
                if rate != 16_000:
                    frames = _resample_linear(frames, rate, 16_000)
                    rate = 16_000
                return frames, rate
        except Exception:
            pass
    if shutil.which("ffmpeg") is None:
        return b"", 0
    try:
        p = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
             "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1"],
            input=raw, capture_output=True, timeout=30)
        if p.returncode != 0 or not p.stdout:
            return b"", 0
        return p.stdout, 16_000
    except Exception:
        return b"", 0


def _tone_beep() -> bytes:
    """Nada 880 Hz 300 ms + hentian, sebagai bukti audio terkirim bila TTS mati."""
    import math
    n = int(16_000 * 0.3)
    frames = bytearray()
    for i in range(n):
        v = int(9000 * math.sin(2 * math.pi * 880 * i / 16_000))
        frames += v.to_bytes(2, "little", signed=True)
    return bytes(frames) + b"\x00" * int(16_000 * 0.1)


async def _pcm_text_to_wav(text: str) -> bytes:
    """TTS sesuai backend aktif -> WAV 16k mono (format jam-friendly)."""
    import io
    import wave
    chunks: list[bytes] = []
    try:
        async for pcm in tts.stream_pcm16(text, sample_rate=16_000):
            if pcm:
                chunks.append(pcm)
    except Exception as exc:
        # Backend TTS mati (piper tak terpasang / edge 403 / kunci habis) —
        # jangan bikin whole request 500; kirim nada pengganti + transkrip tetap ada.
        logging.getLogger("gateway.main").warning("TTS gagal (%s); pakai nada pengganti", exc)
    pcm = b"".join(chunks) or _tone_beep()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16_000)
        w.writeframes(pcm)
    return buf.getvalue()


@app.get("/rtc/token")
async def rtc_token(device: str = Query(...), token: str = Query(...)):
    """Token sesi pendek (15 menit). Di produksi pakai JWT bertanda tangan + refresh."""
    if not auth.verify_device(device, token):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return {"token": auth.issue_session_token(device), "ttl": 900}


@app.websocket("/ws")
async def ws_voice(ws: WebSocket, token: str = Query(default="")):
    device = auth.device_from_token(token) or auth.device_from_header(ws)
    if device is None:
        await ws.close(code=4401)
        return
    await ws.accept()

    s = Session(ws=ws, device=device)
    s.agent = build_agent(s.agent_name, session_id=f"{device}-{int(time.time())}")
    log.info("session open device=%s agent=%s", device, s.agent_name)

    async def send_state(v: str):
        await ws.send_text(json.dumps({"t": "state", "v": v}))

    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break

            if (data := msg.get("bytes")) is not None:
                utt = s.feed(data)
                if utt:
                    asyncio.create_task(handle_turn(s, utt, send_state))
                continue

            ctrl = json.loads(msg["text"])
            kind = ctrl.get("t")

            if kind == "hello":
                s.rate = int(ctrl.get("rate", 16_000))
                s.vad_engine = vad.create_vad(sample_rate=s.rate)
                s.agent_name = ctrl.get("agent") or registry.default_agent()
                s.agent = build_agent(s.agent_name, session_id=f"{device}-{int(time.time())}")
                await send_state("listening")
            elif kind == "mute":
                s.muted = bool(ctrl.get("on"))
            elif kind == "end":
                break
            elif kind == "interrupt":         # barge-in eksplisit dari HP (mis. tombol di jam)
                s.speaking = False
    except WebSocketDisconnect:
        pass
    finally:
        if s.agent:
            await s.agent.aclose()
        log.info("session close device=%s dur=%.0fs", device, time.time() - s.started_at)


async def handle_turn(s: Session, pcm: bytes, send_state):
    """Satu giliran percakapan. Target: suara pertama keluar < 1,2 s."""
    # BARGE-IN: user mulai bicara -> hentikan TTS yang sedang jalan seketika.
    s.speaking = False
    async with s.turn_lock:
        await _handle_turn(s, pcm, send_state)


async def _handle_turn(s: Session, pcm: bytes, send_state):
    t0 = time.time()
    await send_state("thinking")

    # 1) ASR (streaming di produksi; di sini batch per giliran)
    text = await asr.transcribe(pcm, sample_rate=s.rate)
    if not text.strip():
        await send_state("listening")
        return
    await s.ws.send_text(json.dumps({"t": "partial", "text": text}))
    log.info("ASR(%.0fms): %s", (time.time() - t0) * 1000, text)

    # 1b) Router: "pindah ke deepseek", "pakai opencode", dst.
    try:
        _, specs = registry.load_specs()
    except Exception:
        specs = []
    decision = router.route(text, specs, current=s.agent_name)

    if decision.meta:
        await speak(s, f"Sedang memakai agent {s.agent_name}.", send_state)
        await s.ws.send_text(json.dumps({"t": "final",
                                         "text": f"agent aktif: {s.agent_name}"}))
        await send_state("listening")
        return

    if decision.switch_to is not None:
        old = s.agent
        s.agent_name = decision.switch_to.id
        s.agent = build_agent(s.agent_name, session_id=f"{s.device}-{int(time.time())}")
        if old:
            await old.aclose()
        await s.ws.send_text(json.dumps({"t": "agent", "id": s.agent_name,
                                         "label": decision.switch_to.label}))
        log.info("router: ganti agent -> %s", s.agent_name)
        text = decision.rest or f"Baik, sekarang memakai {decision.switch_to.label}."
        if not decision.rest:
            await speak(s, text, send_state)
            await s.ws.send_text(json.dumps({"t": "final", "text": text}))
            await send_state("listening")
            return

    # 2) Agent — kirim, lalu bacakan per kalimat selama masih streaming
    spoken: list[str] = []
    async for chunk in s.agent.stream(text):
        spoken.append(chunk)
        sentence = formatter.take_sentence(spoken)
        if sentence:
            await speak(s, sentence, send_state)

    # 3) Sisa + versi teks penuh untuk ditampilkan di jam
    rest = formatter.flush(spoken)
    if rest:
        await speak(s, rest, send_state)

    full = " ".join(spoken).strip()
    await s.ws.send_text(json.dumps({"t": "final", "text": full[:900]}))
    await send_state("listening")
    log.info("turn done in %.0f ms", (time.time() - t0) * 1000)


async def speak(s: Session, text: str, send_state):
    text = formatter.for_speech(text)
    if not text:
        return
    s.speaking = True
    await send_state("speaking")
    async for pcm in tts.stream_pcm16(text, sample_rate=s.rate):
        if not s.speaking:                 # barge-in: hentikan seketika
            break
        await s.ws.send_bytes(pcm)
    s.speaking = False
