#!/usr/bin/env bash
# Diagnosa koneksi voice-gateway -> OpenCode di VPS.
# Jalan di VPS zb-vela:  bash /tmp/cek-opencode.sh
set -uo pipefail

OC="${OPENCODE_URL:-http://127.0.0.1:49374}"
echo "== 1. Proses OpenCode =="
ps -eo pid,etime,cmd | grep "[o]pencode serve" | head -3

echo; echo "== 2. Root server ($OC) =="
curl -s -o /dev/null -w "GET /            -> %{http_code} %{content_type}\n" "$OC/"
curl -s -o /dev/null -w "GET /api/session -> %{http_code} %{content_type}\n" "$OC/api/session"
curl -s -o /dev/null -w "POST /session    -> %{http_code}\n" -X POST -H 'content-type: application/json' -d '{}' "$OC/session"

echo; echo "== 3. Auth Basic (username opencode, password dari .env) =="
PW="$(grep -m1 '^OPENCODE_SERVER_PASSWORD=' ~/zb/voice-gateway/gateway/.env 2>/dev/null | cut -d= -f2-)"
if [ -z "$PW" ]; then PW="${OPENCODE_SERVER_PASSWORD:-}"; fi
if [ -n "$PW" ]; then
  curl -s -u "opencode:$PW" -o /dev/null -w "basic /api/session   -> %{http_code}\n" "$OC/api/session"
else
  echo "(OPENCODE_SERVER_PASSWORD tidak ada di .env)"
fi

echo; echo "== 4. IP bridge Docker (agar container bisa jangkau host) =="
ip -4 addr show docker0 2>/dev/null | grep -oE 'inet [0-9.]+' || echo "(docker0 tidak ada)"

echo; echo "== 5. Dari dalam container gateway =="
CID=$(docker ps --format '{{.Names}}' | grep -m1 gateway)
echo "container: $CID"
if [ -n "${CID:-}" ]; then
  docker exec "$CID" sh -c "getent hosts host.docker.internal || echo 'no host.docker.internal'" 2>&1 | head -2
  docker exec "$CID" python3 -c "
import httpx
for u in ['$OC','http://host.docker.internal:49374','http://172.17.0.1:49374']:
    try:
        r = httpx.get(u + '/api/session', timeout=4.0)
        print(u, '->', r.status_code)
    except Exception as e:
        print(u, '-> GAGAL:', type(e).__name__)
" 2>&1 | tail -5
fi

echo; echo "== 6. Buat sesi lewat /api (bila auth lolos) =="
curl -s -u "opencode:${PW:-x}" -X POST -H 'content-type: application/json' \
     -d '{}' -w "\nstatus:%{http_code}\n" "$OC/api/session" 2>&1 | head -c 400
echo
