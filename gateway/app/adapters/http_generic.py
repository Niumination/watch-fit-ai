"""
Adapter generik untuk agent yang mengekspos HTTP sederhana.

Dua bentuk didukung otomatis:
  1. OpenAI-compatible: POST {endpoint}/v1/chat/completions  (stream SSE)  -> set openai=True
  2. Sederhana         : POST {endpoint}  {"text": "..."}  -> {"answer": "..."} atau teks polos
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx
from .base import AgentAdapter


class HttpAgentAdapter(AgentAdapter):
    def __init__(self, name: str, endpoint: str, token: str = "", openai: bool = False):
        self.name = name
        self.endpoint = endpoint.rstrip("/")
        self.openai = openai
        headers = {"content-type": "application/json"}
        if token:
            headers["authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(180.0), headers=headers)

    async def stream(self, text: str) -> AsyncIterator[str]:
        if self.openai:
            async for d in self._openai_stream(text):
                yield d
        else:
            r = await self._client.post(self.endpoint, json={"text": text})
            r.raise_for_status()
            try:
                yield r.json().get("answer", "")
            except json.JSONDecodeError:
                yield r.text

    async def _openai_stream(self, text: str) -> AsyncIterator[str]:
        body = {
            "model": "default",
            "stream": True,
            "messages": [
                {"role": "system", "content": "Jawab singkat, tanpa markdown, maksimal 3 kalimat."},
                {"role": "user", "content": text},
            ],
        }
        async with self._client.stream("POST", f"{self.endpoint}/v1/chat/completions", json=body) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                if payload == "[DONE]":
                    return
                try:
                    delta = json.loads(payload)["choices"][0]["delta"].get("content")
                except Exception:
                    continue
                if delta:
                    yield delta

    async def aclose(self) -> None:
        await self._client.aclose()
