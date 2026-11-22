# Deploy Gateway watch-fit-ai di zb-vela (manual via Hermes VPS)

Target: `wss://voice.abstract.biz.id/ws` (ganti hostname bila mau).
Prinsip: gateway di port lokal 8091 → Cloudflare Tunnel `zb-vela` → hostname publik.
Tanpa buka 443/80, tanpa ganggu service lain.

## 0. Persiapan di laptop (sekali saja)

```bash
openssl rand -hex 32   # simpan → GATEWAY_SECRET
```

Pilih backend suara (tanpa kartu kredit → groq gratis):
- Daftar https://console.groq.com → API key → `GROQ_API_KEY`
- Atau pakai Gemini: https://aistudio.google.com → `GEMINI_API_KEY`

## 1. Di VPS zb-vela (via Hermes agent di sana)

```bash
cd ~/zb
git clone https://github.com/Niumination/watch-fit-ai.git voice-gateway
cd voice-gateway/gateway
cp .env.example .env
nano .env
```

Isi `.env` (wajib):

```
DOMAIN=voice.abstract.biz.id
GATEWAY_SECRET=<64-hex dari laptop>
DEFAULT_AGENT=opencode
ASR_BACKEND=groq
GROQ_API_KEY=<kunci groq>
TTS_BACKEND=piper
```

Kosongkan yang tak dipakai. `OPENCODE_URL` biarkan default bila opencode jalan di VPS yang sama;
bila agent di Mac, isi `http://100.120.57.37:4096` (Tailscale Mac).

## 2. Jalankan gateway (tanpa Caddy — Tunnel yang TLS)

```bash
cd ~/zb/voice-gateway/gateway
docker compose up -d gateway
docker logs -f voice-gateway-gateway-1  # Ctrl-C setelah "Uvicorn running"
./tools/run_selftest.sh   # harus 5/5 PASS
```

Catatan: service `caddy` di compose JANGAN dijalankan (port 443/80 milik sistem).
Hanya `gateway` (port 8080 internal docker).

## 3. Pasang hostname ke Cloudflare Tunnel `zb-vela`

Tambahkan ingress (via dashboard Cloudflare → Zero Trust → Tunnels → zb-vela,
atau `composio execute CLOUDFLARE_UPDATE_TUNNEL_CONFIGURATION`):

```
voice.abstract.biz.id → http://127.0.0.1:8080
```

Catatan: port 8080 adalah expose docker gateway di host. Bila bentrok,
ubah di `docker-compose.yml` tambah `ports: ["127.0.0.1:8091:8080"]`
lalu origin `http://127.0.0.1:8091`.

Verifikasi dari VPS:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://voice.abstract.biz.id/health
# harus 200
```

Lalu dari laptop (tanpa VPN apa pun):

```bash
curl -s https://voice.abstract.biz.id/health
```

## 4. Sambungkan HP Android

Di `phone-android/app/src/main/java/id/agentcall/Config.kt`:

```kotlin
gatewayUrl = "wss://voice.abstract.biz.id/ws"
```

Rebuild APK (via CI Actions, lihat `.github/workflows/android.yml`),
install, isi token: token dibuat di VPS dengan `GATEWAY_SECRET` yang sama
(lihat `gateway/tools/` bila ada skrip token, atau minta ke Orkestrator).

## 5. Operasional

```bash
docker ps --filter name=voice-gateway   # harus Up
docker logs --tail 50 voice-gateway-gateway-1
docker compose down && docker compose up -d gateway   # restart
```

Jangan commit `.env` ke git. Jangan expose port agent (opencode/4096) ke internet.

## Port yang dipakai

| Komponen | Port host | Publik via |
|---|---|---|
| gateway | 127.0.0.1:8091 (atau 8080) | voice.abstract.biz.id |
| opencode (bila lokal VPS) | 127.0.0.1:4096 | TIDAK publik |
| caddy | — (tidak dijalankan) | — |
