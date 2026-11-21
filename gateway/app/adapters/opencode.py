"""
Adapter opencode (https://docs.opencode.ai/docs/server/).

API yang dipakai: POST /session  ->  POST /session/:id/message (atau prompt_async + GET /event).
Auth: HTTP basic, user "opencode", password dari OPENCODE_SERVER_PASSWORD.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx
from .base import AgentAdapter


class OpencodeAdapter(AgentAdapter):
    name = "opencode"

    def __init__(self, base_url: str, password: str = "", model: str = ""):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=("opencode", password) if password else None,
            timeout=httpx.Timeout(120.0, connect=10.0),
            headers={"content-type": "application/json"},
        )
        self._session_id: str | None = None
        self._history: list[str] = []

    async def _ensure_session(self) -> str:
        if self._session_id is None:
            r = await self._client.post("/session", json={})
            r.raise_for_status()
            self._session_id = r.json()["id"]
        return self._session_id

    async def stream(self, text: str) -> AsyncIterator[str]:
        sid = await self._ensure_session()

        # Instruksi lisan: agent coding cenderung menulis markdown panjang.
        # Kita minta jawaban lisan singkat, versi panjang tetap dikirim lewat /event.
        prompt = (
            "Jawab dalam bahasa Indonesia, maksimal 3 kalimat, tanpa markdown, "
            "tanpa blok kode. Ini dibacakan lewat speaker jam tangan.\n\n"
            f"Permintaan: {text}"
        )
        body = {"parts": [{"type": "text", "text": prompt}]}
        if self.model:
            body["model"] = self.model

        async with self._client.stream("POST", f"/session/{sid}/message", json=body) as r:
            r.raise_for_status()
            buf = ""
            async for raw in r.aiter_lines():
                if not raw.strip():
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                for part in obj.get("parts", []):
                    if part.get("type") == "text":
                        delta = part.get("text", "")
                        if delta.startswith(buf):
                            delta = delta[len(buf):]
                        buf += delta
                        if delta:
                            yield delta

    async def aclose(self) -> None:
        await self._client.aclose()
