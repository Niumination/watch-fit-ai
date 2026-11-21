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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse

from .adapters.base import AgentAdapter
from .adapters.echo import EchoAgent
from . import auth, tts, asr, formatter, dsp, registry, router

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
    pcm: bytearray = field(default_factory=bytearray)
    silence_ms: int = 0
    started_at: float = field(default_factory=time.time)
    turn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # --- VAD sederhana berbasis energi; produksi: Silero VAD (ONNX, ~1 ms/frame) ---
    @property
    def frame_bytes(self) -> int:
        """20 ms PCM16 mono pada rate sesi (640 byte @16k, 320 byte @8k)."""
        return max(2, self.rate // 50) * 2

    def feed(self, chunk: bytes) -> bytes | None:
        """Proses per frame 20 ms — penting: satu pesan WS bisa berisi banyak frame."""
        if self.muted or not chunk:
            return None
        fb = self.frame_bytes
        utterance = None
        for i in range(0, len(chunk) - fb + 1, fb):
            frame = chunk[i:i + fb]
            if dsp.rms(frame, 2) > 500:
                self.pcm.extend(frame)
                self.silence_ms = 0
            elif self.pcm:
                self.pcm.extend(frame)
                self.silence_ms += 20
                if self.silence_ms >= 600:      # 600 ms hening = akhir giliran
                    utterance = bytes(self.pcm)
                    self.pcm.clear()
                    self.silence_ms = 0
                    break
        return utterance


@app.get("/healthz")
async def healthz():
    return {"ok": True}


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
