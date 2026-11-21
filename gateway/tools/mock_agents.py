"""Server "agent palsu" untuk menguji adapter tanpa VPS & tanpa agent sungguhan.

Meniru:
  - opencode  : POST /session, POST /session/{id}/message (JSON per baris, kumulatif)
  - generik   : POST /ask  -> {"answer": "..."}
  - openai    : POST /v1/chat/completions (SSE)  -> untuk HttpAgentAdapter(openai=True)

Semua endpoint memeriksa Basic/Bearer auth supaya adapter yang salah kirim header langsung ketahuan.
Jalankan:  uvicorn tools.mock_agents:app --port 9099
"""
from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="mock agents")

EXPECTED_BASIC = ("opencode", "rahasia")
EXPECTED_BEARER = "tok123"
SESSIONS: dict[str, list[str]] = {}


def _check_basic(auth: str | None) -> None:
    if not auth or not auth.startswith("Basic "):
        raise HTTPException(401, "basic auth required")
    import base64
    user, _, pw = base64.b64decode(auth[6:]).decode().partition(":")
    if (user, pw) != EXPECTED_BASIC:
        raise HTTPException(401, "bad credentials")


@app.post("/session")
async def create_session(authorization: str | None = Header(default=None)):
    _check_basic(authorization)
    sid = f"ses_{len(SESSIONS) + 1}"
    SESSIONS[sid] = []
    return {"id": sid}


@app.post("/session/{sid}/message")
async def send_message(sid: str, request: Request,
                       authorization: str | None = Header(default=None)):
    _check_basic(authorization)
    if sid not in SESSIONS:
        raise HTTPException(404, "no session")
    body = await request.json()
    prompt = "".join(p.get("text", "") for p in body.get("parts", []))
    SESSIONS[sid].append(prompt)

    answer = ("Halo, ini opencode palsu. Saya menerima permintaan: "
              + prompt[:160].replace("\n", " "))

    async def gen():
        # opencode mengalirkan objek JSON kumulatif per baris
        acc = ""
        for word in answer.split(" "):
            acc = (acc + " " + word).strip()
            yield (json.dumps({"info": {"role": "assistant"},
                               "parts": [{"type": "text", "text": acc}]}, ensure_ascii=False) + "\n")
            await asyncio.sleep(0.005)

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.post("/ask")
async def ask(request: Request, authorization: str | None = Header(default=None)):
    if authorization != f"Bearer {EXPECTED_BEARER}":
        raise HTTPException(401, "bearer required")
    body = await request.json()
    return {"answer": f"deepseek-harness palsu mendengar: {body.get('text', '')[:160]}"}


@app.post("/v1/chat/completions")
async def chat(request: Request, authorization: str | None = Header(default=None)):
    if not (authorization or "").startswith("Bearer "):
        raise HTTPException(401, "bearer required")
    body = await request.json()
    text = body["messages"][-1]["content"]

    async def gen():
        for piece in ["OpenAI-compat ", "palsu: ", text[:80]]:
            chunk = {"choices": [{"delta": {"content": piece}}]}
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.005)
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/healthz")
async def healthz():
    return JSONResponse({"ok": True, "sessions": len(SESSIONS)})
