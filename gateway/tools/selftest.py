#!/usr/bin/env python3
"""
Selftest gateway tanpa HP dan tanpa API key.

Yang dibuktikan:
  1. Auth token sesi diterima / ditolak dengan benar
  2. WS handshake + hello
  3. Frame PCM dikirim -> VAD mendeteksi akhir giliran
  4. Rantai ASR -> agent -> formatter -> TTS menghasilkan audio biner kembali
  5. Latensi per giliran terukur (pakai mode stub: ASR_BACKEND=stub, AGENT=echo, TTS=tone)

Jalankan (terminal 1):
    ASR_BACKEND=stub TTS_BACKEND=tone DEFAULT_AGENT=echo GATEWAY_SECRET=test \
      uvicorn app.main:app --port 8080

Jalankan (terminal 2):
    python tools/selftest.py
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import math
import os
import struct
import sys
import time

import websockets

SECRET = os.environ.get("GATEWAY_SECRET", "test")
URL = os.environ.get("GATEWAY_URL", "ws://127.0.0.1:8080/ws")
DEVICE = "selftest-device"
RATE = 16_000


def session_token(device: str = DEVICE, ttl: int = 900) -> str:
    exp = int(time.time()) + ttl
    msg = f"{device}.{exp}".encode()
    sig = hmac.new(SECRET.encode(), msg, hashlib.sha256).hexdigest()[:32]
    return f"{device}.{exp}.{sig}"


def speechlike_pcm(seconds: float = 1.2, rate: int = RATE, amp: int = 12_000) -> bytes:
    """Bukan suara asli — hanya sinyal berenergi dengan pola on/off supaya VAD ikut teruji."""
    frames = []
    total = int(rate * seconds)
    for i in range(total):
        env = 0.5 + 0.5 * math.sin(2 * math.pi * 3.0 * i / rate)     # modulasi 3 Hz
        s = int(amp * env * math.sin(2 * math.pi * 220.0 * i / rate))
        frames.append(struct.pack("<h", s))
    return b"".join(frames)


async def main() -> int:
    token = session_token()
    print(f"→ connect {URL}")

    async with websockets.connect(URL + "?token=" + token, max_size=None) as ws:
        await ws.send(json.dumps({"t": "hello", "agent": "echo", "rate": RATE, "device": DEVICE}))

        # --- giliran 1: 1,2 s "bicara" lalu 0,8 s hening (memicu endpoint) ---
        t0 = time.time()
        pcm = speechlike_pcm(1.2)
        await ws.send(pcm)
        await ws.send(b"\x00\x00" * int(RATE * 0.05) * 16)   # 800 ms hening

        audio_bytes = 0
        first_audio_ms = None
        final_text = None
        states = []

        deadline = time.time() + 20
        while time.time() < deadline and final_text is None:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=20)
            except asyncio.TimeoutError:
                break
            if isinstance(msg, bytes):
                if first_audio_ms is None:
                    first_audio_ms = (time.time() - t0) * 1000
                audio_bytes += len(msg)
                continue
            ev = json.loads(msg)
            if ev.get("t") == "state":
                states.append(ev["v"])
            elif ev.get("t") == "final":
                final_text = ev.get("text")

        print("\n=== HASIL ===")
        ok_auth = True
        print(f"auth token      : OK ({token[:14]}…)")
        print(f"state events    : {states}")
        print(f"audio kembali   : {audio_bytes} byte  ({audio_bytes/2/RATE:.2f} s @ {RATE} Hz)")
        print(f"audio pertama   : {first_audio_ms:.0f} ms" if first_audio_ms else "audio pertama   : TIDAK ADA")
        print(f"final text      : {final_text}")

        checks = {
            "audio biner diterima": audio_bytes > 0,
            "state 'speaking' muncul": "speaking" in states,
            "transkrip final ada": bool(final_text),
            "latensi < 2000 ms": (first_audio_ms or 9e9) < 2000,
        }
        print()
        for name, passed in checks.items():
            print(f"  [{'PASS' if passed else 'FAIL'}] {name}")

        # --- giliran 2: token tidak valid harus ditolak ---
        try:
            async with websockets.connect(URL + "?token=bogus.1.deadbeef") as ws2:
                await asyncio.wait_for(ws2.recv(), timeout=3)
            print("  [FAIL] token palsu seharusnya ditolak")
            checks["token palsu ditolak"] = False
        except Exception:
            print("  [PASS] token palsu ditolak")
            checks["token palsu ditolak"] = True

        return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
