"""Agent uji: menggemakan apa yang didengar + durasi. Dipakai Fase 1 dan selftest."""
from __future__ import annotations

from typing import AsyncIterator

from .base import AgentAdapter


class EchoAgent(AgentAdapter):
    name = "echo"

    async def stream(self, text: str) -> AsyncIterator[str]:
        yield f"Saya mendengar: {text}. "
        yield "Kalau ini terdengar jelas di jam, jalur audio sudah benar. "
        yield "Sekarang ganti agent ke opencode untuk jawaban sungguhan."
