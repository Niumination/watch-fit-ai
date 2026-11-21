#!/usr/bin/env python3
"""
"HP palsu" untuk uji Fase 1 dari laptop: pakai mic & speaker laptop untuk berbicara
dengan agent lewat gateway — sebelum app Android-nya selesai.

Berguna untuk mengukur latensi jaringanmu dan memvalidasi prompt agent tanpa
berurusan dengan SCO/HFP.

Butuh: pip install sounddevice numpy
Pakai:
    python tools/laptop_client.py --url wss://voice.domainmu.com/ws --agent echo
    python tools/laptop_client.py --url ws://127.0.0.1:8080/ws --agent echo --loop
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import queue
import sys
import time

try:
    import numpy as np
    import sounddevice as sd
except ImportError:
    sys.exit("Butuh: pip install sounddevice numpy")

RATE = 16_000
FRAME = RATE // 50          # 320 sampel = 20 ms


def session_token(device: str, secret: str, ttl: int = 900) -> str:
    exp = int(time.time()) + ttl
    msg = f"{device}.{exp}".encode()
    sig = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:32]
    return f"{device}.{exp}.{sig}"


async def run(args) -> None:
    import websockets

    token = session_token(args.device, args.secret)
    url = f"{args.url}?token={token}"
    out_q: queue.Queue[bytes] = queue.Queue()
    mic_q: queue.Queue[bytes] = queue.Queue()

    def mic_cb(indata, frames, t, status):
        mic_q.put(bytes(indata))

    play = sd.RawOutputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=FRAME)
    play.start()

    async with websockets.connect(url, max_size=None) as ws:
        await ws.send(json.dumps({"t": "hello", "agent": args.agent, "rate": RATE,
                                  "device": args.device}))
        print(f"terhubung · agent={args.agent} · Ctrl+C untuk berhenti")

        async def pump_mic():
            with sd.RawInputStream(samplerate=RATE, channels=1, dtype="int16",
                                   blocksize=FRAME, callback=mic_cb):
                while True:
                    await ws.send(await asyncio.get_event_loop().run_in_executor(None, mic_q.get))

        async def pump_speaker():
            t_first = None
            while True:
                msg = await ws.recv()
                if isinstance(msg, bytes):
                    if t_first is None:
                        t_first = time.time()
                    play.write(msg)
                else:
                    ev = json.loads(msg)
                    if ev.get("t") == "state":
                        print(f"  [{ev['v']}]", flush=True)
                        if ev["v"] == "listening":
                            t_first = None
                    elif ev.get("t") == "final":
                        print(f"  → {ev['text']}\n")

        tasks = [asyncio.create_task(pump_mic()), asyncio.create_task(pump_speaker())]
        try:
            await asyncio.gather(*tasks)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            for t in tasks:
                t.cancel()
            await ws.send(json.dumps({"t": "end"}))
    play.stop()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8080/ws")
    ap.add_argument("--agent", default="echo")
    ap.add_argument("--device", default="laptop-client")
    ap.add_argument("--secret", default=os.environ.get("GATEWAY_SECRET", "test"))
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
