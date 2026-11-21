"""Speech-to-text.

Backend yang didukung (pilih lewat env ASR_BACKEND):
  stub           : mode uji tanpa model (mengembalikan STUB_ASR_TEXT)
  groq           : cloud tercepat (~120-180 ms), whisper-large-v3-turbo (butuh GROQ_API_KEY)
  openai         : cloud standar, whisper-1 (butuh OPENAI_API_KEY)
  gemini         : multimodal gemini-2.5-flash (butuh GEMINI_API_KEY)
  faster-whisper : self-host lokal di VPS (gratis, butuh CPU/GPU)
"""
from __future__ import annotations

import base64
import io
import logging
import os
import wave

import httpx

log = logging.getLogger("gateway.asr")

_whisper = None


def _pcm_to_wav(pcm: bytes, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


async def transcribe(pcm: bytes, sample_rate: int = 16_000, lang: str = "id") -> str:
    backend = os.environ.get("ASR_BACKEND", "stub").lower()

    if backend == "stub":
        secs = len(pcm) / 2 / max(1, sample_rate)
        return os.environ.get("STUB_ASR_TEXT", "tes satu dua tiga") + f" ({secs:.1f} detik audio)"

    if backend == "groq":
        return await _groq(pcm, sample_rate, lang)

    if backend == "openai":
        return await _openai(pcm, sample_rate, lang)

    if backend == "gemini":
        return await _gemini(pcm, sample_rate, lang)

    return _faster_whisper(pcm, sample_rate, lang)


async def _groq(pcm: bytes, rate: int, lang: str) -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        log.warning("GROQ_API_KEY belum diset")
        return ""
    wav = _pcm_to_wav(pcm, rate)
    url = os.environ.get("GROQ_ASR_URL", "https://api.groq.com/openai/v1/audio/transcriptions")
    model = os.environ.get("GROQ_ASR_MODEL", "whisper-large-v3-turbo")

    files = {"file": ("audio.wav", wav, "audio/wav")}
    data = {"model": model, "language": lang, "response_format": "json"}
    headers = {"Authorization": f"Bearer {key}"}

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, files=files, data=data, headers=headers)
        r.raise_for_status()
        return r.json().get("text", "").strip()


async def _openai(pcm: bytes, rate: int, lang: str) -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        log.warning("OPENAI_API_KEY belum diset")
        return ""
    wav = _pcm_to_wav(pcm, rate)
    url = os.environ.get("OPENAI_ASR_URL", "https://api.openai.com/v1/audio/transcriptions")
    model = os.environ.get("OPENAI_ASR_MODEL", "whisper-1")

    files = {"file": ("audio.wav", wav, "audio/wav")}
    data = {"model": model, "language": lang, "response_format": "json"}
    headers = {"Authorization": f"Bearer {key}"}

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, files=files, data=data, headers=headers)
        r.raise_for_status()
        return r.json().get("text", "").strip()


async def _gemini(pcm: bytes, rate: int, lang: str) -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        log.warning("GEMINI_API_KEY belum diset")
        return ""
    model = os.environ.get("GEMINI_ASR_MODEL", "gemini-2.5-flash")
    b64 = base64.b64encode(_pcm_to_wav(pcm, rate)).decode()
    body = {
        "contents": [{
            "parts": [
                {"text": f"Transkripsikan ucapan ini (bahasa {lang}) apa adanya, tanpa komentar atau penjelasan."},
                {"inline_data": {"mime_type": "audio/wav", "data": b64}},
            ]
        }]
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, json=body)
        r.raise_for_status()
        candidates = r.json().get("candidates", [])
        if not candidates:
            return ""
        return candidates[0]["content"]["parts"][0]["text"].strip()


def _faster_whisper(pcm: bytes, rate: int, lang: str) -> str:
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        _whisper = WhisperModel(
            os.environ.get("WHISPER_MODEL", "small"),
            device=os.environ.get("WHISPER_DEVICE", "cpu"),
            compute_type="int8",
        )
    import numpy as np
    audio = np.frombuffer(pcm, dtype=np.int16).astype("float32") / 32768.0
    segments, _ = _whisper.transcribe(audio, language=lang, vad_filter=True, beam_size=1)
    return "".join(s.text for s in segments).strip()
