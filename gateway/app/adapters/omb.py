"""
Adapter OpenMausBot (OMB) lewat relay-bridge.

Kontrak (terverifikasi 24 Nov 2026 di VPS zb-vela):
    POST {base}/hooks/{endpoint_id}
    Header: authorization: Bearer <token>
    Body:   {"message": "<teks>", "state": "idle"}
    Balas:  200 -> {"reply": "<jawaban>", "runId": ..., "threadId": ...}
            202 -> masih berjalan (timeout)
            4xx -> {"error": ...}

Field jawaban = "reply" (bukan answer/text).
Env: OMB_BRIDGE_URL, OMB_WEBHOOK_ID, OMB_WEBHOOK_TOKEN.
"""
from __future__ import annotations

import os
from typing import AsyncIterator

import httpx

from .base import AgentAdapter


class OmbAgent(AgentAdapter):
    name = "omb"

    def __init__(self, base_url: str, webhook_id: str, token: str, timeout: float = 90.0):
        self.webhook_id = webhook_id
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "content-type": "application/json",
                **({"authorization": f"Bearer {token}"} if token else {}),
            },
            timeout=httpx.Timeout(timeout, connect=5.0),
        )

    async def stream(self, text: str) -> AsyncIterator[str]:
        # Instruksi lisan: model coding cenderung menulis markdown panjang.
        prompt = (
            "Jawab dalam bahasa Indonesia, maksimal 3 kalimat, tanpa markdown, "
            "tanpa blok kode. Ini dibacakan lewat speaker jam tangan.\n\n"
            f"Permintaan: {text}"
        )
        r = await self._client.post(
            f"/hooks/{self.webhook_id}",
            json={"message": prompt, "state": "idle"},
        )
        if r.status_code == 202:
            yield "Jawaban sedang disusun. Coba tanya lagi sesaat."
            return
        r.raise_for_status()
        data = r.json()
        reply = (data.get("reply") or "").strip()
        if not reply:
            raise RuntimeError(f"OMB balas tanpa 'reply': {str(data)[:200]}")
        yield reply

    async def aclose(self) -> None:
        await self._client.aclose()


def build_from_env() -> OmbAgent | None:
    """Bangun adapter dari env; None bila env belum lengkap."""
    base = os.environ.get("OMB_BRIDGE_URL", "")
    wid = os.environ.get("OMB_WEBHOOK_ID", "")
    token = os.environ.get("OMB_WEBHOOK_TOKEN", "")
    if not (base and wid and token):
        return None
    return OmbAgent(base, wid, token)
