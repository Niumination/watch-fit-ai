"""Text-to-speech -> stream PCM16 mono.

Urutan backend (pilih lewat env TTS_BACKEND):
  piper  : self-host, offline, latensi paling rendah  (rekomendasi produksi)
  edge   : gratis, kualitas bagus, butuh internet
  gemini : suara paling natural, ~$9-12/1M token audio
  null   : hening (untuk uji jalur audio saja)
"""
from __future__ import annotations

import asyncio
import io
import os
import shutil
import wave
from typing import AsyncIterator

from . import dsp

_BACKEND = os.environ.get("TTS_BACKEND", "piper")
_PIPER_VOICE = os.environ.get("PIPER_VOICE", "id_ID-...")  # unduh voice .onnx Indonesia
_CHUNK = 4096


async def stream_pcm16(text: str, sample_rate: int = 16_000) -> AsyncIterator[bytes]:
    wav = await _synth_wav(text)
    async for chunk in _wav_to_pcm(wav, sample_rate):
        yield chunk


async def _synth_wav(text: str) -> bytes:
    if _BACKEND == "null":
        return _silence_wav(0.3)
    if _BACKEND == "tone":
        # nada 440 Hz sepanjang ~panjang teks: cukup untuk membuktikan audio kembali ke HP
        return _tone_wav(min(3.0, 0.4 + len(text) / 40.0))
    if _BACKEND == "piper" and shutil.which("piper"):
        return await _piper(text)
    if _BACKEND in ("edge", "piper"):
        return await _edge(text)
    if _BACKEND == "gemini":
        return await _gemini(text)
    return _silence_wav(0.3)


async def _piper(text: str) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        "piper", "--model", os.environ["PIPER_MODEL"], "--output_file", "-",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate(text.encode())
    return out


async def _edge(text: str) -> bytes:
    import edge_tts
    voice = os.environ.get("EDGE_VOICE", "id-ID-ArdiNeural")
    buf = bytearray()
    comm = edge_tts.Communicate(text, voice)
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            buf.extend(chunk["data"])
    return bytes(buf)  # mp3 -> di produksi decode ke PCM (ffmpeg/av)


async def _gemini(text: str) -> bytes:
    import base64
    import httpx
    key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
    body = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {"responseModalities": ["AUDIO"]},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    async with httpx.AsyncClient(timeout=60) as c:
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
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(frames)
    return buf.getvalue()


def _silence_wav(sec: float, rate: int = 24_000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * sec))
    return buf.getvalue()


async def _wav_to_pcm(wav: bytes, target_rate: int) -> AsyncIterator[bytes]:
    with wave.open(io.BytesIO(wav), "rb") as w:
        sr = w.getframerate()
        frames = w.readframes(w.getnframes())
    if sr != target_rate:
        frames = dsp.ratecv(frames, 2, 1, sr, target_rate)
    for i in range(0, len(frames), _CHUNK):
        yield frames[i:i + _CHUNK]
        await asyncio.sleep(0)     # jangan blok event loop -> barge-in tetap responsif
