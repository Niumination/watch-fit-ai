# Deploy Gateway watch-fit-ai di zb-vela

Diperbarui: 25 Nov 2026 (status produksi per 24 Nov 2026)

Gateway berjalan di VPS zb-vela dan dipublikasikan lewat Cloudflare Tunnel
`zb-vela`. Dokumen ini menggambarkan kondisi **nyata** di VPS, termasuk patch
lokal yang sengaja tidak di-commit upstream.

## 1. Status produksi (terverifikasi 24 Nov 2026)

| Item | Nilai |
|---|---|
| Folder VPS | `~/zb/voice-gateway` |
| Container | `gateway-gateway-1` (service `gateway`) |
| URL publik | `https://voice.abstract.biz.id` |
| Health | `GET /health` -> 200 `{"ok":true}`; `GET /healthz` -> 200 |
| Agent default | **`omb`** (`gateway/app/adapters/omb.py`), `DEFAULT_AGENT=omb` |
| ASR | `groq` (`ASR_BACKEND=groq`) |
| TTS | `piper` self-host (`TTS_BACKEND=piper`), `/models/id_ID-news.onnx` (62.950.044 byte) |
| Image | `python:3.11-slim` (pin, lihat §6) |
| OpenCode VPS | **tidak dipakai lagi** — lihat `docs/05-opencode-integration.md` |
| CI android-apk | run 45443080943 SUCCESS |

Kode: catatan 24 Nov 2026 menyebut `c0685fb`; verifikasi ulang dengan
`git log --oneline -1` di VPS. Pastikan `gateway/app/adapters/omb.py` ada di working
tree (`test -f gateway/app/adapters/omb.py`) — OMB baru masuk pada commit `43cf487`.

## 2. Topologi port (yang sebenarnya)

| Lapisan | Alamat | Catatan |
|---|---|---|
| Container gateway | `:8080` | upstream: `expose: ["8080"]`, network internal `agentnet` |
| Host VPS | `127.0.0.1:8091` -> `8080` | **patch lokal** di `gateway/docker-compose.yml` |
| Publik | Cloudflare Tunnel `zb-vela` -> `http://127.0.0.1:8091` | TLS di tunnel |
| `caddy` | tidak dijalankan | port 443/80 milik sistem |

Alasan patch port lokal **sengaja tidak di-commit**:
- Caddy/proxy menghubungi service lewat network internal
  (`Caddyfile`: `reverse_proxy gateway:8080`), jadi upstream cukup `expose`.
- `docker compose` me-MERGE `ports` milik deployer; meng-commit `ports` dapat
  menimpa atau bertabrakan dengan setelan host lain.
- Mapping host `127.0.0.1:8091:8080` hanya dibutuhkan konsumen host (tunnel).

Patch lokal di VPS (blok `gateway` pada `gateway/docker-compose.yml`):

```yaml
    ports: ["127.0.0.1:8091:8080"]
```

**Jangan `git add`/commit baris ini.** Kalau hilang setelah pull, tambahkan lagi.

## 3. `.env` produksi (VPS)

Nilai nyata, disamarkan dengan placeholder:

```
DOMAIN=voice.abstract.biz.id
GATEWAY_SECRET=<64-hex>
DEFAULT_AGENT=omb
ASR_BACKEND=groq
GROQ_API_KEY=<kunci-groq>
TTS_BACKEND=piper
PIPER_MODEL=/models/id_ID-news.onnx
OMB_BRIDGE_URL=http://172.18.0.1:8801
OMB_WEBHOOK_ID=<wh_...>
OMB_WEBHOOK_TOKEN=<rahasia>
DEVICE_TOKENS=<device_id:secret,device_id2:secret2,...>
```

Catatan:
- Otak produksi = **OMB** (OpenMausBot lewat relay-bridge). `OPENCODE_*` dibiarkan kosong.
- `OMB_BRIDGE_URL` memakai IP bridge Docker host (`172.18.0.1`), bukan `127.0.0.1`:
  di dalam container `127.0.0.1` = container itu sendiri.
- `DEVICE_TOKENS` dibaca saat import (`app/auth.py`), format `id:secret` pisah koma.
- Tambah device: edit baris `DEVICE_TOKENS` yang sudah ada. Jangan
  `grep -q ... || echo >> .env` — guard cocok dengan key lama dan tidak menambah apa pun.

### Device terdaftar (id saja, bukan rahasia)

`device_id` HP diturunkan dari `ANDROID_ID`: `"and-" + 8 hex`. Terdaftar di VPS:
`and-5ddb4c9f`, `and-78ed6a33`, `and-zbvela-4277`.

## 4. Model TTS piper

```bash
cd ~/zb/voice-gateway/gateway
./tools/fetch-piper-model.sh models
```

Catatan VPS: unduhan pernah gagal karena folder tujuan root-owned; diselesaikan
dengan unduhan manual `sudo -n`. Verifikasi hasil:

```bash
ls -l models/id_ID-news.onnx     # 62.950.044 byte
```

`gateway/models/` gitignored; compose me-mount `./models` read-only ke `/models`.

## 5. Jalankan / restart

```bash
cd ~/zb/voice-gateway/gateway
docker compose up -d --force-recreate gateway   # --force-recreate wajib bila .env berubah
docker logs --tail 50 gateway-gateway-1          # "Application startup complete"
./tools/run_selftest.sh                          # 5/5 PASS
```

Service `caddy` jangan dijalankan.

## 6. Catatan teknis runtime

- Image di-pin `python:3.11-slim`: `piper-phonemize` hanya punya wheel `cp39`-`cp312`;
  di Python 3.12+ build gambar gagal (gejala: deploy pecah, bukan import error).
- `audioop` (stdlib <=3.12) diganti helper `_to_mono_s16` / `_resample_linear`
  di `app/main.py` supaya aman di Python 3.13+.
- `edge-tts` dimatikan: Microsoft menolak handshake (403). Jangan dijadikan fallback.
- Semua tahap eksternal di `/ask-audio` (ASR, agent, TTS) punya try/except sendiri;
  satu dependensi mati tidak boleh menghasilkan HTTP 500.

## 7. Verifikasi

Dasar (tanpa kredensial):

```bash
curl -s https://voice.abstract.biz.id/health                                            # {"ok":true}
curl -s -o /dev/null -w "%{http_code}\n" https://voice.abstract.biz.id/healthz           # 200
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://voice.abstract.biz.id/ask-audio # 422
```

Penafsiran status: `422` = endpoint hidup tapi body kosong; `404` = kode lama;
`401` = auth/device; `500` = bug setelah auth lolos.

Uji audio sungguhan (pakai device + token nyata; nilai tidak dicetak di dokumen):

```bash
curl -s -D /tmp/hdr.txt -o /tmp/jawab.wav -X POST https://voice.abstract.biz.id/ask-audio \
  -F device=<device_id> -F token=<device_secret> -F agent=omb -F audio=@/tmp/uji.wav
grep -i '^X-Transcript-Out:' /tmp/hdr.txt
ffprobe -v error -show_entries format=duration -of csv=p=0 /tmp/jawab.wav
```

Hasil terverifikasi: balasan `audio/wav`, 450.324 byte, transkrip jawaban nyata.
Status 200 saja tidak membuktikan otak dijawab — cek `X-Transcript-Out`, karena
jalur degradasi juga mengembalikan 200 + audio.

## 8. Update kode tanpa menghapus patch lokal

`.env` dan `gateway/models/` gitignored, jadi `git pull` tidak menyentuhnya. Yang
dilindungi: patch `ports` di `gateway/docker-compose.yml` dan file lokal lainnya.

```bash
cd ~/zb/voice-gateway
git status --porcelain                                     # lihat patch lokal
git diff > /tmp/zbvela-local.patch                         # simpan perubahan terlacak
cp gateway/docker-compose.yml /tmp/zbvela-compose.yml.bak  # cadangan utuh

git stash push -u -m "zbvela-$(date +%F-%H%M)"             # simpan semua patch lokal
git pull origin main
git stash pop                                              # kembalikan patch

grep -n '127.0.0.1:8091' gateway/docker-compose.yml         # harus ada
# bila hilang: cp /tmp/zbvela-compose.yml.bak gateway/docker-compose.yml

docker compose build gateway
docker compose up -d --force-recreate gateway
sleep 5
docker logs --tail 20 gateway-gateway-1
./tools/run_selftest.sh                                    # 5/5 PASS
```

Aturan:
- Jangan `git checkout -- <file>` / `git reset --hard` sebelum diff disimpan.
- Bila `stash pop` konflik: selesaikan, lalu pastikan `ports` masih ada.
- Jangan commit patch port upstream.

## 9. Sambungkan HP Android

`phone-android/app/src/main/java/id/agentcall/Config.kt`:

```kotlin
const val gatewayUrl: String = "wss://voice.abstract.biz.id/ws"
```

Bangun APK lewat CI (`.github/workflows/android-apk.yml`, artifact `agentcall-debug`),
pasang, lalu isi device secret. `device_id` di app = `"and-" + 8 hex` dari
`ANDROID_ID`, stabil walau APK di-reinstall.
