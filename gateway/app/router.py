"""Router perintah suara -> ganti agent.

Kenapa rule-based dulu (bukan LLM): perintah "pindah ke opencode" harus instan (<5 ms),
deterministik, dan gratis. LLM hanya dipakai kalau kamu memang mau routing semantik
(lihat classify_llm, opsional).

Contoh yang dikenali (ID + EN):
  "pindah ke opencode"        -> switch opencode
  "pakai deepseek dong"       -> switch deepseek-harness
  "ganti agent ke openmausbot"-> switch openmausbot
  "switch to gemini"          -> switch gemini
  "agent apa ini?"            -> meta (tidak mengganti agent)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .registry import AgentSpec, find

_SWITCH = re.compile(
    r"^(?:tolong\s+)?(?:pindah|ganti|pakai|gunakan|sambung(?:kan)?|switch|use|change)"
    r"(?:\s+(?:agent|agen|ke|to|dengan|dgn))*\s+(?P<name>[a-z0-9\s\-]{2,30})$",
    re.I,
)
_META = re.compile(r"(agent|agen)\s+(apa|siapa)|sedang\s+(pakai|menggunakan)", re.I)
# ASR sering menambahkan ekor seperti "(1.8 detik audio)", "…", atau tanda baca.
_NOISE = re.compile(r"\([^)]*\)|\[[^\]]*\]")


@dataclass
class Route:
    switch_to: AgentSpec | None = None
    rest: str = ""
    meta: bool = False


def _norm(text: str) -> str:
    t = _NOISE.sub(" ", text.lower())
    return " ".join(t.split()).strip(" .,!?…\"' ")


def _match_switch(t: str):
    """Cocokkan utuh dulu; kalau gagal, coba 5 kata pertama (toleran ekor ASR)."""
    m = _SWITCH.match(t)
    if m:
        return m
    head = " ".join(t.split()[:5])
    return _SWITCH.match(head)


def route(text: str, specs: list[AgentSpec], current: str) -> Route:
    t = _norm(text)

    if _META.search(t):
        return Route(meta=True)

    m = _match_switch(t)
    if m:
        name = m.group("name").strip()
        spec = find(specs, name)
        if spec:
            return Route(switch_to=spec)
        # coba cocokkan sebagian: "deepseek" sudah ada di alias, ini untuk "agent kode"
        for s in specs:
            if any(a and a in name for a in s.aliases):
                return Route(switch_to=s)

    # Kalau user menyebut nama agent di awal kalimat tapi tetap ingin bertanya:
    # "opencode, tolong cek status deploy"
    for s in specs:
        for a in [s.id, s.label] + s.aliases:
            if a and t.startswith(a):
                rest = text.strip()[len(a):].lstrip(" ,:.-")
                return Route(switch_to=s if s.id != current else None, rest=rest)

    return Route(rest=text)


async def classify_llm(text: str, specs: list[AgentSpec]) -> AgentSpec | None:
    """Opsional: klasifikasi niat dengan LLM. Biaya ~0 (teks pendek), latensi 200-400 ms.

    Aktifkan dengan ROUTER=llm + GEMINI_API_KEY di env. Default: rule-based saja.
    """
    import httpx
    import os
    import json

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    catalog = "\n".join(f"- {s.id}: {s.hint}" for s in specs)
    prompt = (
        "Pilih agent yang paling cocok untuk permintaan user. Balas HANYA id agent, "
        f"atau 'none' kalau tidak perlu ganti.\n\nAgent:\n{catalog}\n\nPermintaan: {text}"
    )
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"{os.environ.get('ROUTER_MODEL', 'gemini-2.5-flash')}:generateContent?key={key}")
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
        r.raise_for_status()
        out = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
    if out.startswith("none"):
        return None
    return find(specs, out.split()[0])
