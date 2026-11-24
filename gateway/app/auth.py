"""Auth minimal: token perangkat + token sesi pendek.

Produksi: ganti dengan JWT (HS256/EdDSA) bertanda tangan, refresh token, dan kuota per device.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

SECRET = os.environ.get("GATEWAY_SECRET", "dev-secret-change-me")
DEVICES: dict[str, str] = {}  # device_id -> sha256(token)


def _h(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()


def register_device(device_id: str, token: str) -> None:
    DEVICES[device_id] = _h(token)


def _init_from_env() -> None:
    """Isi DEVICES dari DEVICE_TOKENS='id:secret,id2:secret2' (produksi file-based)."""
    for pair in os.environ.get("DEVICE_TOKENS", "").split(","):
        if ":" in pair:
            did, tok = pair.split(":", 1)
            if did.strip() and tok.strip():
                register_device(did.strip(), tok.strip())


_init_from_env()


def verify_device(device_id: str, token: str) -> bool:
    known = DEVICES.get(device_id)
    return bool(known) and hmac.compare_digest(known, _h(token))


def issue_session_token(device_id: str, ttl: int = 900) -> str:
    exp = int(time.time()) + ttl
    msg = f"{device_id}.{exp}".encode()
    sig = hmac.new(SECRET.encode(), msg, hashlib.sha256).hexdigest()[:32]
    return f"{device_id}.{exp}.{sig}"


def device_from_token(tok: str) -> str | None:
    if not tok or tok.count(".") != 2:
        return None
    device_id, exp, sig = tok.split(".")
    msg = f"{device_id}.{exp}".encode()
    want = hmac.new(SECRET.encode(), msg, hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(want, sig) or int(exp) < time.time():
        return None
    return device_id


def device_from_header(ws) -> str | None:
    hdr = ws.headers.get("authorization", "")
    if hdr.lower().startswith("bearer "):
        return device_from_token(hdr[7:])
    return None
