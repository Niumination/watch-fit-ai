"""Registry agent: satu sumber kebenaran untuk 'agent apa saja yang ada'.

Konfigurasi di config/agents.json (bisa dioverride lewat env AGENTS_CONFIG).
Menambah agent baru = tambah entri JSON; tidak perlu menyentuh main.py.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from .adapters.base import AgentAdapter
from .adapters.echo import EchoAgent
from .adapters.gemini import GeminiAdapter
from .adapters.http_generic import HttpAgentAdapter
from .adapters.opencode import OpencodeAdapter

log = logging.getLogger("gateway.registry")

_DEFAULT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "agents.json")


@dataclass
class AgentSpec:
    id: str
    label: str
    type: str
    aliases: list[str]
    hint: str = ""
    env: dict | None = None


def load_specs(path: str | None = None) -> tuple[str, list[AgentSpec]]:
    path = path or os.environ.get("AGENTS_CONFIG") or _DEFAULT_PATH
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    specs = [
        AgentSpec(
            id=a["id"],
            label=a.get("label", a["id"]),
            type=a.get("type", "http"),
            aliases=[x.lower() for x in a.get("aliases", [])],
            hint=a.get("hint", ""),
            env=a,
        )
        for a in raw["agents"]
    ]
    return raw.get("default", specs[0].id), specs


def default_agent(path: str | None = None) -> str:
    env_default = os.environ.get("DEFAULT_AGENT")
    if env_default:
        return env_default
    try:
        return load_specs(path)[0]
    except Exception:
        return "echo"


def find(specs: list[AgentSpec], name: str) -> AgentSpec | None:
    name = (name or "").strip().lower()
    for s in specs:
        if s.id.lower() == name or s.label.lower() == name:
            return s
    for s in specs:
        if name in s.aliases:
            return s
    return None


def build(agent_id: str, path: str | None = None) -> AgentAdapter:
    """Bangun adapter dari registry; kalau env kurang, jatuh ke echo + log jelas."""
    try:
        _, specs = load_specs(path)
    except Exception as e:                       # config rusak / tidak ada
        log.warning("gagal memuat registry (%s); pakai echo", e)
        return EchoAgent()

    spec = find(specs, agent_id) or find(specs, default_agent(path)) or specs[0]
    env = spec.env or {}

    try:
        if spec.type == "echo":
            return EchoAgent()
        if spec.type == "opencode":
            base = os.environ[env["base_url_env"]]
            return OpencodeAdapter(
                base_url=base,
                password=os.environ.get(env.get("password_env", ""), ""),
                model=os.environ.get(env.get("model_env", ""), ""),
            )
        if spec.type == "http":
            url = os.environ[env["url_env"]]
            return HttpAgentAdapter(
                name=spec.id,
                endpoint=url,
                token=os.environ.get(env.get("token_env", ""), ""),
                openai=bool(env.get("openai_compat", False)),
            )
        if spec.type in ("gemini", "gemini_live"):
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                log.warning("GEMINI_API_KEY belum diset; fallback ke echo")
                return EchoAgent()
            return GeminiAdapter(api_key=api_key, model=os.environ.get("GEMINI_MODEL"))
    except KeyError as e:
        log.warning("env %s belum diset untuk agent '%s'; fallback ke echo", e, spec.id)
        return EchoAgent()

    log.warning("tipe agent tidak dikenal: %s; pakai echo", spec.type)
    return EchoAgent()
