#!/usr/bin/env bash
# Menjalankan gateway dalam mode uji (tanpa API key) lalu menjalankan selftest.
set -euo pipefail
cd "$(dirname "$0")/.."

export ASR_BACKEND=${ASR_BACKEND:-stub}
export TTS_BACKEND=${TTS_BACKEND:-tone}
export DEFAULT_AGENT=${DEFAULT_AGENT:-echo}
export GATEWAY_SECRET=${GATEWAY_SECRET:-test}

python3 -m uvicorn app.main:app --port 8080 --host 127.0.0.1 >/tmp/gateway-selftest.log 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  if curl -sf localhost:8080/healthz >/dev/null 2>&1; then break; fi
  sleep 0.5
done

GATEWAY_SECRET="$GATEWAY_SECRET" python3 tools/selftest.py
echo
echo "log gateway: /tmp/gateway-selftest.log"
