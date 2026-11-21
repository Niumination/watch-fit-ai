"""E2E lewat WebSocket sungguhan (TestClient) — tanpa HP, tanpa API key."""
import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient
from app.main import app


def token(device="test-dev", ttl=900, secret="test"):
    exp = int(time.time()) + ttl
    msg = f"{device}.{exp}".encode()
    sig = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:32]
    return f"{device}.{exp}.{sig}"


def speech(n=320 * 30, amp=10_000):
    return b"".join(amp.to_bytes(2, "little", signed=True) for _ in range(n))


def test_rejects_bad_token():
    c = TestClient(app)
    try:
        with c.websocket_connect("/ws?token=bogus.1.xx") as ws:
            ws.receive()          # server menutup -> exception / close frame
    except Exception:
        return                    # perilaku yang diharapkan
    raise AssertionError("koneksi dengan token palsu seharusnya ditolak")


def test_full_turn_returns_audio_and_final_text():
    c = TestClient(app)
    tok = token()
    with c.websocket_connect(f"/ws?token={tok}") as ws:
        ws.send_text(json.dumps({"t": "hello", "agent": "echo", "rate": 16000,
                                 "device": "test-dev"}))
        ws.send_bytes(speech())                      # 600 ms bicara
        ws.send_bytes(b"\x00\x00" * 320 * 40)        # 800 ms hening -> endpoint

        audio = 0
        final = None
        states = []
        for _ in range(400):
            msg = ws.receive()
            if msg["type"] != "websocket.send":
                break
            if msg.get("bytes"):
                audio += len(msg["bytes"])
            elif msg.get("text"):
                ev = json.loads(msg["text"])
                if ev.get("t") == "state":
                    states.append(ev["v"])
                elif ev.get("t") == "final":
                    final = ev["text"]
                    break
        assert audio > 0, "tidak ada audio kembali"
        assert "speaking" in states
        assert final, "tidak ada transkrip final"


def test_switch_agent_command_emits_agent_event(monkeypatch):
    monkeypatch.setenv("STUB_ASR_TEXT", "pindah ke opencode")
    c = TestClient(app)
    tok = token("test-dev2")
    with c.websocket_connect(f"/ws?token={tok}") as ws:
        ws.send_text(json.dumps({"t": "hello", "agent": "echo", "rate": 16000,
                                 "device": "test-dev2"}))
        # STUB ASR mengembalikan teks dari env; lihat STUB_ASR_TEXT di bawah
        ws.send_bytes(speech())
        ws.send_bytes(b"\x00\x00" * 320 * 40)

        agent_event = None
        for _ in range(400):
            msg = ws.receive()
            if msg["type"] != "websocket.send":
                break
            if msg.get("text"):
                ev = json.loads(msg["text"])
                if ev.get("t") == "agent":
                    agent_event = ev
                    break
                if ev.get("t") == "final":
                    break          # jangan pernah menunggu tanpa batas
        assert agent_event is not None, "router tidak mengirim event agent"
        assert agent_event["id"] == "opencode"
