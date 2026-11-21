"""Speech-to-text. Dua backend: faster-whisper (self-host, gratis) atau Gemini (akurat, murah)."""
from __future__ import annotations

import base64
import io
import os
import wave

import httpx

_BACKEND = os.environ.get("ASR_BACKEND", "faster-whisper")
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
    if _BACKEND == "stub":
        # Mode uji: tidak ada model, tapi rantai VAD -> giliran -> agent tetap teruji.
        import os
        secs = len(pcm) / 2 / max(1, sample_rate)
        return os.environ.get("STUB_ASR_TEXT", "tes satu dua tiga") + f" ({secs:.1f} detik audio)"
    if _BACKEND == "gemini":
        return await _gemini(pcm, sample_rate, lang)
    return _faster_whisper(pcm, sample_rate, lang)


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


async def _gemini(pcm: bytes, rate: int, lang: str) -> str:
    key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_ASR_MODEL", "gemini-2.5-flash")
    b64 = base64.b64encode(_pcm_to_wav(pcm, rate)).decode()
    body = {
        "contents": [{
            "parts": [
                {"text": f"Transkripsikan ucapan ini (bahasa {lang}) apa adanya, tanpa komentar."},
                {"inline_data": {"mime_type": "audio/wav", "data": b64}},
            ]
        }]
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(url, json=body)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
