# watchfit5-agent

Bicara dua arah dengan AI agent-mu (opencode / deepseek-harness / openmausbot / Gemini)
langsung dari **HUAWEI WATCH FIT 5**.

```
WATCH FIT 5 ──HFP (mic+speaker+layar panggilan)── HP ANDROID ──WSS── VPS GATEWAY ──HTTP── agent
```

## Mulai dari mana

| File | Untuk apa |
|---|---|
| **[`docs/01-riset-dan-arsitektur.md`](docs/01-riset-dan-arsitektur.md)** | **Baca ini dulu.** Riset lengkap: fakta perangkat, 4 jalur arsitektur, alur sesi, latensi, biaya, risiko, rencana 4 fase, checklist uji |
| [`docs/02-arsitektur.svg`](docs/02-arsitektur.svg) | Diagram satu halaman |
| **[`docs/03-panduan-fase0.md`](docs/03-panduan-fase0.md)** | **Panduan hari pertama**: 6 tes di perangkatmu + tabel hasil + pohon keputusan |
| [`gateway/`](gateway/) | Gateway VPS (FastAPI): WS + VAD + ASR + router + adapter agent + TTS + Caddy TLS |
| [`phone-android/`](phone-android/) | App Android "AgentCall" + **spike Phase 0** (S1–S7, PASS/FAIL di layar) |
| [`watch-lite/`](watch-lite/) | App lite-JS untuk jam (tombol Talk, pilih agent, transkrip) — opsional, ada risiko install |

## Tiga temuan yang menentukan desain

1. **FIT 5 tidak bisa menjalankan app yang merekam/memutar audio.** Ia lite wearable
   (HML+JS+CSS, JerryScript ES5.1): tanpa API mic, tanpa audio streaming, tanpa Wi-Fi,
   tanpa WebSocket. App di jam hanya bisa jadi remote + display.
2. **Tapi FIT 5 punya mic + speaker + Bluetooth calling** → ia bisa jadi **headset HFP**.
   Dengan *self-managed `ConnectionService`* di HP, sesi AI tampil sebagai **panggilan**
   di jam, lengkap dengan tombol jawab/tutup — persis seperti panggilan WhatsApp.
3. **App Gemini tidak punya API untuk dikendalikan.** "Pakai Gemini" = pakai
   **Gemini Live API** langsung dari gateway (~$0,023/menit, ±4× lebih murah per menit dari `gpt-realtime-2.1`).

## Urutan eksekusi yang disarankan

```
Fase 0 (1 hari)   Uji perangkat: HFP terdeteksi? jam tampilkan call UI? sideload lite app bisa?
Fase 1 (1–2 mgg)  App Android + gateway echo/TTS  → "bicara dari jam, didengar dari jam"
Fase 2 (1–2 mgg)  VAD + ASR + adapter agent       → "agent menjawab lewat suara"
Fase 3 (1–2 mgg)  App lite di jam                 → "dimulai dari pergelangan"
Fase 4            Multi-agent, barge-in penuh, memori, Health Kit
```

Sebelum menulis kode, jalankan **Fase 0** — hasilnya bisa mengubah prioritas
(lihat tabel risiko R1: instalasi lite app berpeluang gagal karena batas API level).

## Perintah uji cepat

```bash
# 1) jam terlihat sebagai headset HFP?
adb shell dumpsys bluetooth_manager | grep -iE "hfp|headset|msbc"

# 2) gateway: uji end-to-end tanpa HP & tanpa API key (5x PASS)
cd gateway && ./tools/run_selftest.sh

# 3) spike Android: build & jalankan S1–S7
cd phone-android && ./gradlew :app:installDebug
```

## Catatan kejujuran teknis

Beberapa hal **belum bisa dipastikan dari dokumentasi publik** dan harus diukur di perangkatmu
sendiri — sudah ditandai di dokumen:

- Apakah FIT 5 (rilis 2026) menerima sideload app lite, dan pada **API level** berapa
  (GT3 maksimal API 6, GT5 menolak dengan Error 40).
- Apakah SCO-nya **wideband (mSBC/16 kHz)** atau narrowband (CVSD/8 kHz).
- Perilaku echo/AEC jam saat barge-in (rencana: mulai semi-duplex, lalu AEC3 di gateway).

Rencana B untuk tiap poin sudah ada di dokumen (register risiko §7).
