"""Adapter untuk Gemini (Google AI Studio) via SSE streaming API.

Endpoint:
  POST https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={GEMINI_API_KEY}
"""
from __future__ import annotations

import json
import logging
import os
from typing import AsyncIterator

import httpx

from .base import AgentAdapter

log = logging.getLogger("gateway.adapter.gemini")


class GeminiAdapter(AgentAdapter):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "gemini"

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=20.0)
        return self._client

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        if not self.api_key:
            yield "GEMINI_API_KEY belum diset di server gateway."
            return

        client = await self._ensure_client()
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent"
            f"?alt=sse&key={self.api_key}"
        )
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Kamu adalah AI assistant yang diakses lewat smartwatch (Huawei Watch Fit 5). "
                                "Jawab secara ringkas, jelas, lisan, dalam bahasa yang sama dengan pengguna (prioritas Indonesia), "
                                "maksimal 2-3 kalimat, tanpa markdown atau formatting kode.\n\n"
                                f"Pengguna: {prompt}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.6,
                "maxOutputTokens": 200,
            },
        }

        try:
            async with client.stream("POST", url, json=body) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    log.warning("Gemini error %d: %s", resp.status_code, err_body.decode(errors="ignore")[:200])
                    yield f"Maaf, Gemini mengembalikan kode kesalahan {resp.status_code}."
                    return

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if not data_str:
                        continue
                    try:
                        chunk = json.loads(data_str)
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for p in parts:
                                text_piece = p.get("text", "")
                                if text_piece:
                                    yield text_piece
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            log.warning("Gagal streaming dari Gemini: %s", e)
            yield "Terjadi kendala saat menghubungi Gemini."

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
