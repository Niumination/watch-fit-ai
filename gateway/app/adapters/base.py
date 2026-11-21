"""Kontrak seragam untuk semua agent. Tambah agent baru = tambah satu kelas."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator


class AgentAdapter(ABC):
    name: str = "agent"

    @abstractmethod
    def stream(self, text: str) -> AsyncIterator[str]:
        """Kirim satu giliran user, hasilkan potongan teks jawaban (streaming)."""

    async def aclose(self) -> None:
        """Bersihkan sesi/HTTP client."""
