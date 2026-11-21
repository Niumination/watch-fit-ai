"""Mengubah output agent (markdown/kode/panjang) menjadi kalimat yang enak didengar.

Ini bagian yang membuat "bicara dengan agent coding" terasa wajar:
agent boleh menulis 500 baris, yang dibacakan tetap 2-4 kalimat + tawaran detail.
"""
from __future__ import annotations

import os
import re

MAX_SENTENCES = int(os.environ.get("VOICE_MAX_SENTENCES", "4"))

_CLEAN = [
    (re.compile(r"```.*?```", re.S), " (ada blok kode, lihat di HP) "),
    (re.compile(r"`([^`]+)`"), r"\1"),
    (re.compile(r"!?\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"^[#>*\-+]+\s*", re.M), ""),
    (re.compile(r"\*\*|__|\*|_"), ""),
    (re.compile(r"https?://\S+"), " tautan "),
    (re.compile(r"\s+"), " "),
]


def for_speech(text: str) -> str:
    for rx, rep in _CLEAN:
        text = rx.sub(rep, text)
    return text.strip()


def take_sentence(parts: list[str]) -> str | None:
    """Ambil satu kalimat lengkap dari buffer streaming (untuk TTS per kalimat)."""
    buf = for_speech("".join(parts))
    if len(buf) < 12:
        return None
    m = re.search(r"([.!?])\s", buf)
    if not m:
        return None
    return buf[: m.end()].strip()


def flush(parts: list[str]) -> str:
    buf = for_speech("".join(parts))
    if not buf:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", buf)
    return " ".join(sentences[:MAX_SENTENCES]).strip()
