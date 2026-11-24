# watchfit5-agent

Bicara dua arah dengan AI agent-mu (saat ini **OMB / OpenMausBot**) langsung dari **HUAWEI WATCH FIT 5**, lewat HP Android + gateway VPS.

```
mic HP ──rekam 8 dtk──▶ gateway VPS (voice.abstract.biz.id)
                          ├─ ASR Groq → agent OMB (relay-bridge) → TTS piper
                          └─ WAV ~450 KB
WAV ──Wear Engine P2P──▶ jam ──@system.audio──▶ speaker jam
```

## Mulai dari mana

| File | Untuk apa |
|---|---|
| **[`docs/01-riset-dan-arsitektur.md`](docs/01-riset-dan-arsitektur.md)** | **Baca ini dulu.** Riset lengkap + **kondisi aktual per 24 Nov 2026** di bagian atas: rantai berjalan, status uji, batas platform |
| [`docs/02-arsitektur.svg`](docs/02-arsitektur.svg) | Diagram satu halaman (berbasis rancangan HFP lama) |
| **[`docs/03-panduan-fase0.md`](docs/03-panduan-fase0.md)** | Hasil uji perangkat 23–24 Nov 2026 (tabel PASS/FAIL) + panduan Fase 0 |
| [`docs/05-opencode-integration.md`](docs/05-opencode-integration.md) | Kenapa adapter `opencode` rusak di OpenCode v2 (`/api/*`, Basic auth, `POST /session` 405) |
| [`docs/06-jalur-c-hap.md`](docs/06-jalur-c-hap.md) | Langkah build HAP pemutar WAV di jam + batas `@system.audio` (control list) |
| [`docs/DEPLOY-ZB-VELA.md`](docs/DEPLOY-ZB-VELA.md) | Deploy gateway di VPS zb-vela + Cloudflare Tunnel |
| [`gateway/`](gateway/) | Gateway VPS (FastAPI): WS + VAD + ASR + router + adapter agent + TTS piper |
| [`phone-android/`](phone-android/) | App Android "AgentCall" + spike (S1–S7) + tombol Jalur A (kirim WAV ke jam) |
| [`watch-lite/`](watch-lite/) | App lite-JS untuk jam (terima file WAV, putar `@system.audio`) |

## Tiga temuan yang menentukan desain

1. **FIT 5 tidak bisa merekam audio dan tidak punya streaming/WebSocket.** Ia lite wearable
   (HML+JS+CSS, JerryScript ES5.1): tanpa API mic, tanpa WebSocket, tanpa Wi-Fi.
   Yang bisa dilakukannya: tampilkan UI/remote, terima file via P2P Wear Engine,
   dan (dengan syarat *control list*) putar file audio. Rekaman selalu dari mic HP.
2. **Jalur HFP (jam sebagai headset HP) gugur di Infinix X6873.** Rencana awal memakai SCO
   HP → jam; OS menolak (toggle Phone calls terkunci, `availableCommunicationDevices` kosong,
   retry 3× gagal). HFP jam → HP masih OK. Jadi audio jalan lewat **rekaman mic HP**, bukan mic jam.
3. **Otak AI dipilih yang sudah ada di ekosistem.** Rencana awal memakai `opencode`;
   diganti **OMB (OpenMausBot)** via relay-bridge di VPS zb-vela, karena OpenCode v2
   tak kompatibel dengan rantai ini dan saldonya habis. Adapter `opencode` tetap ada
   di repo tapi statusnya RUSAK (lihat `docs/05-opencode-integration.md`).

## Status tahap (per 24 Nov 2026)

| Tahap | Status | Bukti singkat |
|---|---|---|
| Fase 0 — validasi perangkat | SELESAI | HFP jam→HP PASS; HP→jam GUGUR; sideload BELUM |
| Jalur B — HFP HP → jam | GUGUR | X6873 menolak SCO (bukan bug app) |
| Jalur A — mic HP → gateway → WAV | PASS | `askOnce: POST .../ask-audio -> 200`; WAV 450324 byte, 14,07 s, 16 kHz mono |
| ASR Groq | PASS | header `X-Transcript-In` terisi |
| Agent OMB (default) | PASS | `X-Transcript-Out` = jawaban utuh Bahasa Indonesia |
| TTS piper | PASS | WAV ~450 KB, bukan nada |
| Latensi end-to-end (dari Mac) | ±11,5 dtk | ukur total request `/ask-audio` |
| Pemutaran WAV di speaker jam | MENUNGGU build HAP | kode siap (commit `9168ede`), belum diuji di perangkat |
| `@system.audio` lolos control list musik | **UNCHECKED** | pendaftaran bundle tidak terdokumentasi publik |
| Adapter `opencode` | RUSAK | OpenCode v2: API `/api/*`, Basic auth, `POST /session` → 405 |

## Perintah uji cepat

```bash
# 1) gateway hidup?
curl -s -o /dev/null -w "%{http_code}\n" https://voice.abstract.biz.id/health   # 200

# 2) selftest gateway (tanpa HP & tanpa API key)
cd gateway && ./tools/run_selftest.sh

# 3) spike Android: build & jalankan S1–S7
cd phone-android && ./gradlew :app:installDebug

# 4) log Jalur A di HP
adb logcat | grep -iE "askOnce|ask-audio|sendFileToWatch"
```

## Catatan kejujuran teknis

Beberapa hal **belum bisa dipastikan dari dokumentasi publik** dan harus diukur di perangkatmu
sendiri — sudah ditandai di dokumen:

- Apakah FIT 5 (rilis 2026) menerima sideload app lite, dan pada **API level** berapa
  (GT3 maksimal API 6, GT5 menolak dengan Error 40).
- Apakah `@system.audio` boleh dipakai bundle `id.agentcall.watch` (**control list** layanan
  musik Huawei). Kalau belum terdaftar, `audio.play()` langsung `onerror`. **UNCHECKED**.
- Apakah `sendFileToWatch` (callback `FileSendCallback` + `onResult`) cocok dengan versi SDK
  Wear Engine yang terpasang — **belum pernah diuji di perangkat**.
- Adapter `opencode` sengaja **tidak dihapus** meski rusak; perbaiki kontraknya dulu bila
  ingin dipakai (lihat `docs/05`).

Rencana B untuk tiap poin sudah ada di dokumen (register risiko §7 di `docs/01`).
