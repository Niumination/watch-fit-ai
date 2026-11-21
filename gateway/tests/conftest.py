"""Env uji diset SEBELUM import app.main (modul membaca env saat import)."""
import os

os.environ.setdefault("GATEWAY_SECRET", "test")
os.environ.setdefault("ASR_BACKEND", "stub")
os.environ.setdefault("TTS_BACKEND", "tone")
os.environ.setdefault("DEFAULT_AGENT", "echo")
os.environ.pop("OPENCODE_URL", None)      # paksa registry jatuh ke echo untuk tes default

import pytest  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import socket  # noqa: E402
import uvicorn  # noqa: E402


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def mock_agents_url():
    """Jalankan tools/mock_agents.py di port acak, kembalikan base URL."""
    from tools.mock_agents import app as mock_app

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(mock_app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()

    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)

    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    th.join(timeout=5)
