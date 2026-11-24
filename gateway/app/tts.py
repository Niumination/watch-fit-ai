"""Text-to-speech -> stream PCM16 mono.

Urutan backend (pilih lewat env TTS_BACKEND):
  piper  : self-host, offline, latensi paling rendah  (rekomendasi VPS)
  openai : cloud cepat (~300-500 ms), suara natural (butuh OPENAI_API_KEY)
  gemini : suara natural, multimodal
  edge   : gratis, kualitas bagus (butuh internet & edge-tts)
  tone   : nada 440 Hz (untuk uji koneksi & audio loopback tanpa API key)
  null   : hening
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import shutil
import wave
from typing import AsyncIterator

import httpx

from . import dsp

log = logging.getLogger("gateway.tts")

_CHUNK = 4096


async def stream_pcm16(text: str, sample_rate: int = 16_000) -> AsyncIterator[bytes]:
    wav = await _synth_wav(text)
    async for chunk in _wav_to_pcm(wav, sample_rate):
        yield chunk


async def _synth_wav(text: str) -> bytes:
    backend = os.environ.get("TTS_BACKEND", "tone").lower()

    if backend == "null":
        return _silence_wav(0.3)
    if backend == "tone":
        # nada 440 Hz sepanjang ~panjang teks: cukup untuk membuktikan audio kembali ke HP
        return _tone_wav(min(3.0, 0.4 + len(text) / 40.0))
    if backend == "openai":
        return await _openai(text)
    if backend == "piper" and os.path.exists(os.environ.get("PIPER_MODEL", "/models/id_ID-news.onnx")):
        return await _piper(text)
    if backend == "edge":
        return await _edge(text)
    if backend == "gemini":
        return await _gemini(text)
    return _silence_wav(0.3)


async def _openai(text: str) -> bytes:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        log.warning("OPENAI_API_KEY belum diset; fallback ke nada")
        return _tone_wav(0.5)
    url = os.environ.get("OPENAI_TTS_URL", "https://api.openai.com/v1/audio/speech")
    voice = os.environ.get("OPENAI_TTS_VOICE", "alloy")
    model = os.environ.get("OPENAI_TTS_MODEL", "tts-1")
    body = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "wav",
    }
    headers = {"Authorization": f"Bearer {key}"}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, json=body, headers=headers)
        r.raise_for_status()
        return r.content


async def _piper(text: str) -> bytes:
    """Piper self-host (in-proses, tanpa binary eksternal).

    Model: models/id_ID-news.onnx (unduh dengan tools/fetch-piper-model.sh).
    """
    import io
    import wave as _wave
    model = os.environ.get("PIPER_MODEL", "/models/id_ID-news.onnx")
    if not os.path.exists(model):
        log.warning("model piper tidak ada di %s; jalankan tools/fetch-piper-model.sh", model)
        return _tone_wav(0.5)

    def _gen() -> bytes:
        from piper import PiperVoice
        voice = PiperVoice.load(model)
        buf = io.BytesIO()
        with _wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(voice.config.sample_rate)
            voice.synthesize(text, w)
        return buf.getvalue()

    return await asyncio.to_thread(_gen)


async def _edge(text: str) -> bytes:
    try:
        import edge_tts
    except ImportError:
        log.warning("edge_tts belum terpasang; fallback ke nada")
        return _tone_wav(0.5)

    voice = os.environ.get("EDGE_VOICE", "id-ID-ArdiNeural")
    buf = bytearray()
    comm = edge_tts.Communicate(text, voice)
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            buf.extend(chunk["data"])

    # edge_tts menghasilkan mp3; bila ffmpeg tersedia kita decode ke WAV
    if shutil.which("ffmpeg"):
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", "pipe:0", "-f", "wav", "-ar", "24000", "-ac", "1", "pipe:1",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        wav_out, _ = await proc.communicate(bytes(buf))
        return wav_out
    return bytes(buf)


async def _gemini(text: str) -> bytes:
    import base64
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        log.warning("GEMINI_API_KEY belum diset")
        return _tone_wav(0.5)
    model = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
    body = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {"responseModalities": ["AUDIO"]},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, json=body)
        r.raise_for_status()
        data = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    return base64.b64decode(data)


def _tone_wav(sec: float, freq: float = 440.0, rate: int = 24_000) -> bytes:
    import math
    import struct
    n = int(rate * sec)
    frames = b"".join(
        struct.pack("<h", int(9000 * math.sin(2 * math.pi * freq * i / rate))) for i in range(n)
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return buf.getvalue()


def _silence_wav(sec: float, rate: int = 24_000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * sec))
    return buf.getvalue()


async def _wav_to_pcm(wav: bytes, target_rate: int) -> AsyncIterator[bytes]:
    try:
        with wave.open(io.BytesIO(wav), "rb") as w:
            sr = w.getframerate()
            frames = w.readframes(w.getnframes())
    except Exception as e:
        log.warning("Gagal parse WAV (%s); stream nada darurat", e)
        wav = _tone_wav(0.4, rate=target_rate)
        with wave.open(io.BytesIO(wav), "rb") as w:
            sr = w.getframerate()
            frames = w.readframes(w.getnframes())

    if sr != target_rate:
        frames = dsp.ratecv(frames, 2, 1, sr, target_rate)
    for i in range(0, len(frames), _CHUNK):
        yield frames[i:i + _CHUNK]
        await asyncio.sleep(0)     # jangan blok event loop -> barge-in tetap responsif
