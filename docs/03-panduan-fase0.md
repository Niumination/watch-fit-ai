# Panduan Fase 0 — satu hari untuk memastikan skema ini benar di perangkatmu

Tujuan: **sebelum** menulis kode produksi, buktikan 6 hal di bawah. Hasilnya menentukan
jalur mana yang kamu pakai (A / B / C) dan berapa ekspektasi kualitas audionya.

Waktu: ±3–4 jam (banyak menunggu pairing & update). Alat: HP Android + FIT 5 + kabel USB + laptop.

---

## Tes 1 — Jam benar-benar jadi "headset", bukan cuma perangkat Health (15 menit)

1. Huawei Health → Devices → pastikan ter-pair. Lalu buka **Settings → Bluetooth** di HP:
   cari entri jam yang **bukan** hanya "Huawei Health" — biasanya ada dua entri, salah satunya
   berperan sebagai **headset/hands-free**. Kalau hanya ada satu dan tidak ada opsi audio:
   di Health, buka profil perangkat → cari **"Bluetooth calling"** dan aktifkan.
2. Uji tanpa app apa pun: **telepon** ke nomor apa saja (atau WhatsApp call ke diri sendiri),
   lalu pilih output audio → pilih jam. Bicara & dengar.
3. Cek dari adb:

```bash
adb shell dumpsys bluetooth_manager | grep -iE "hfp|headset|sco|msbc|codec"
```

**Kriteria lulus:** ada perangkat HFP terhubung; suara panggilan keluar-masuk lewat jam.

**Kalau gagal:** berhenti di sini. Tanpa HFP, seluruh skema B/C tidak mungkin; pakai Jalur A
(nomor telepon) yang tidak bergantung pada custom HFP — tapi itu pun butuh jam sebagai
headset untuk panggilan. Jadi ini blocker mutlak.

---

## Tes 2 — Apakah jam menampilkan layar panggilan dari app pihak ketiga? (15 menit)

Ini membuktikan mekanisme `self-managed ConnectionService` (dasar Jalur B).

1. Build & install app spike:

```bash
cd phone-android
./gradlew :app:installDebug      # atau buka di Android Studio → Run
```

2. Buka app **AgentCall** → izinkan semua permission.
3. Tekan **"S1–S6"** (Jalankan semua langkah) → baca log di layar.
4. Aktifkan akun panggilan: tombol **"Buka pengaturan akun panggilan"** → pilih
   **"AI Agent (AgentCall)"** → **Enable / Allow**.
5. Tekan **"Buka panggilan self-managed (S4)"**.

**Kriteria lulus:** jam bergetar/berbunyi dan menampilkan **layar panggilan** dengan tombol
jawab/tutup; menekan tombol di jam mengakhiri panggilan.

**Kalau gagal:** beberapa ROM mematikan "self-managed calls" untuk app non-store. Catat pesan
error, lalu pakai rencana B (kontrol dari HP: notifikasi + QS tile). Audio tetap bisa ke jam
selama SCO bisa dibuka (Tes 3).

---

## Tes 3 — Route SCO: apakah audio benar-benar pindah ke jam? (30 menit)

1. Di app spike, tekan **S5** (route) lalu **S6** (frasa uji).
2. Dengarkan: frasa harus keluar dari **speaker jam**, bukan speaker HP.
3. Lalu tekan **S7** (rekam 5 s). Saat merekam, **tutup mic jam dengan jari** di detik ke-2–4.
4. Pemutaran ulang otomatis setelah rekaman.

**Kriteria lulus (dua-duanya):**
- frasa uji terdengar di jam, **dan**
- saat mic jam ditutup dengan jari, level `peak` **turun drastis** (misal 3000 → 300).

**Kalau frasa terdengar tapi peak tidak turun** → audio capture masih dari mic HP.
Penyebab umum, berurutan:
1. `AudioRecord` dibuat sebelum SCO tersambung → tunda 150–300 ms (sudah ada di `WatchAudioRoute`).
2. Sumber rekaman bukan `VOICE_COMMUNICATION`.
3. Permission `BLUETOOTH_CONNECT` belum granted (API 31+) → diam-diam gagal route.
4. Ada panggilan telepon aktif (SCO dipakai sistem).

---

## Tes 4 — Wideband atau narrowband? (10 menit)

```bash
# saat sesi/SCO aktif:
adb shell dumpsys audio | grep -iE "sco|sample|communication device"
adb shell dumpsys bluetooth_manager | grep -iE "msbc|wbs|wideband|codec"
```

| Hasil | Arti | Dampak |
|---|---|---|
| 16000 Hz / `mSBC` | **wideband** | STT akurat, suara enak |
| 8000 Hz / `CVSD` | **narrowband** | seperti telepon; STT masih bisa, tapi tambah prompt domain & kosakata |

Catat angka yang muncul. Ini masuk tabel hasil dan menentukan setelan `rate` di klien.

---

## Tes 5 — Gateway di VPS (45 menit)

```bash
# di VPS (Singapore/Jakarta lebih baik untukmu — cek dulu ping-nya)
git clone <repo-mu> && cd gateway
cp .env.example .env
# .env: GATEWAY_SECRET=$(openssl rand -hex 32), ASR_BACKEND=stub, TTS_BACKEND=tone, DEFAULT_AGENT=echo
docker compose up -d --build
curl -s localhost:8080/healthz

# buktikan rantai berjalan sebelum menyentuh HP:
GATEWAY_SECRET=<secret> python tools/selftest.py
```

**Kriteria lulus:** 5 baris `[PASS]` (audio biner diterima, state speaking, transkrip final,
latensi, token palsu ditolak). Ini sudah diverifikasi di workspace ini — output asli:
`turn done in 49 ms`, token palsu → `403`.

Setelah itu arahkan `Config.gatewayUrl` di app Android ke `wss://voice.domainmu.com/ws`,
isi `device_secret`, lalu tekan S4 dan bicara. Target: **mendengar suara kembali di jam**.

```bash
# ukur ping (dari HP via termux, atau dari laptop sebagai perkiraan)
ping -c 20 voice.domainmu.com
```

---

## Tes 6 — Bisakah sideload app lite ke FIT 5? (60–90 menit, paling tidak pasti)

```text
DevEco Studio 3.1 + SDK API 5/6 → build hap lite (watch-lite/) → signing debug
→ copy ke /sdcard/haps/ → DevEco Assistant → Install
```

Catat **pesan error persisnya** (bukan "gagal"): `40 Invalid configuration file format`,
`47 Invalid value entered for app.apiVersion`, `10 Internal error`, atau sukses.

| Hasil | Arti | Tindakan |
|---|---|---|
| Sukses | jalur C terbuka | lanjut bangun UI jam |
| `Error 40/47` | API level tidak cocok | turunkan `apiVersion` (6→5→4), pakai DevEco 3.1, ulangi |
| `Error 10` | fitur JS di luar dukungan | audit ES5, buang import modern |
| Di luar itu / mentok | jalur C ditutup untuk sementara | pakai rencana B (notifikasi + QS tile) |

---

## Tabel hasil (isi dan simpan)

| # | Tes | Hasil | Angka/detail |
|---|---|---|---|
| 1 | HFP headset terdeteksi | ☐ PASS ☐ FAIL | codec: ____ , nama device: ____ |
| 2 | Layar panggilan muncul dari app | ☐ PASS ☐ FAIL | error: ____ |
| 3 | Speaker jam (S6) | ☐ PASS ☐ FAIL | — |
| 3b | Mic jam (S7, tutup jari) | ☐ PASS ☐ FAIL | peak turun: ____ → ____ |
| 4 | Sample rate SCO | ☐ 16k ☐ 8k | bukti dumpsys: ____ |
| 5 | Gateway selftest | ☐ PASS ☐ FAIL | latensi audio pertama: ____ ms · ping VPS: ____ ms |
| 6 | Sideload app lite | ☐ PASS ☐ FAIL | pesan error: ____ |

## Pohon keputusan

```
Tes 1 gagal ─────────────────────────► berhenti; perbaiki pairing "Bluetooth calling" dulu
Tes 1 lulus
 ├─ Tes 3 gagal (mic/speaker bukan dari jam) ──► debug SCO (4 penyebab di atas), jangan lanjut
 ├─ Tes 3 lulus
 │   ├─ Tes 2 gagal ──────► Jalur B versi "kontrol dari HP" (tanpa call UI di jam)
 │   ├─ Tes 2 lulus ──────► Jalur B penuh ⭐
 │   └─ Tes 6 lulus ──────► naik ke Jalur C (tombol di jam)
 └─ Tes 4 narrowband ────► set rate=8000, aktifkan penyesuaian prompt ASR + kosakata domain
```

## Yang perlu kamu kirim balik ke saya

Supaya iterasi berikutnya tepat sasaran, kirim:
1. Tabel hasil di atas (terisi).
2. Output `adb shell dumpsys bluetooth_manager | grep -iE "hfp|msbc"` (Tes 1/4).
3. Log app spike (copy dari layar) untuk S2/S5/S7.
4. Pesan error sideload (Tes 6), kalau ada.

Dari data itu saya bisa: mengunci setelan `rate` & AEC, memilih TTS/ASR yang tepat untuk
latensi jaringanmu, dan menyiapkan adapter agent yang kamu pakai sehari-hari.

## Hasil — 24 Nov 2026 (jalur AI sungguhan via OMB)

| Tahap | Status | Bukti |
|-------|--------|-------|
| Rekam mic HP + kirim ke gateway | PASS | logcat `askOnce: POST .../ask-audio -> 200` |
| Auth device (ANDROID_ID) | PASS | `and-78ed6a33`, stabil lintas reinstall |
| ASR Groq | PASS | `x-transcript-in: Jamur apa yang bisa dimakan?` |
| **Agent OMB (OpenMausBot, bot ZB)** | **PASS** | `x-transcript-out` = jawaban jamur edible, kalimat utuh |
| TTS piper Indonesia | PASS | WAV 14.07 s / 16 kHz mono / 450 KB |
| Latensi end-to-end | ±11.5 dtk | ukur dari Mac ke endpoint publik |

Jawaban yang diterima (bukan klaim pelaksana — diuji ulang dari Mac):
> Beberapa jamur yang aman dimakan antara lain jamur merang, jamur kancing,
> jamur shiitake, dan jamur champignon. Hindari mengumpulkan jamur liar
> sendiri karena banyak jenis beracun yang mirip dengan yang edible.

Catatan operasional: adapter `omb.py` menembak relay-bridge lewat
`http://172.18.0.1:8801` (listener tambahan, webhook humanoid
`wh_knBDiZz4DGRydSZi`). Konsekuensi yang sudah disadari: pertanyaan jam masuk
ke bot ZbmausHumanoid-Vercel dan bisa muncul juga di situs humanoid.

## Hasil Jalur A — 24 Nov 2026 (mic HP -> gateway -> WAV)

| Tahap | Status | Bukti |
|-------|--------|-------|
| Rekam mic HP 8 dtk (MediaRecorder AAC 16k) | PASS | tombol "Jalur A" di app, izin RECORD_AUDIO granted |
| Kirim WAV/MP4 ke `https://voice.abstract.biz.id/ask-audio` | PASS | logcat `askOnce: POST ... -> 200` |
| Auth device | PASS | `device_id` stabil dari ANDROID_ID (`and-78ed6a33`), terdaftar di VPS |
| ASR Groq | PASS | `X-Transcript-In: Terima kasih telah menonton!` |
| Agent echo | PASS | transkrip jawaban terisi |
| TTS | DEGRADASI (aman) | piper tak terpasang + edge_tts 403 -> nada pengganti 880 Hz; request tetap 200, bukan 500 |
| WAV balik ke HP | PASS | 11.244 byte RIFF 16 kHz mono |
| Putar di speaker jam via P2P | BELUM | butuh HAP liteWearable (`@system.audio`) + signing |

Kesimpulan: pipa audio HP->gateway terbukti. Dua item terbuka: TTS sungguhan
(model piper atau kunci OpenAI/Gemini) dan HAP pemutar di jam.

## Hasil aktual — 23 Nov 2026 (Infinix X6873 + Watch Fit 5 HarmonyOS 6.1.0.125)

| # | Tes | Hasil | Bukti |
|---|-----|-------|-------|
| 1 | HFP headset | **PASS bersyarat** | Jam→HP & panggilan masuk: dua arah via HFP OK (angkat dari jam, tanpa sentuh HP). HP→jam: SCO ditolak OS (toggle Phone calls terkunci, `availableCommunicationDevices` tanpa SCO, retry 3x gagal). |
| 2 | Layar panggilan app pihak ketiga | **FAIL (perangkat)** | `placeCall()` → Telecom ERROR; `route.open()` false → `setDisconnected(ERROR)`. Bukan bug app (5 fix CI hijau). |
| 3 | Route SCO | **FAIL (perangkat)** | `SCO_STATE_INACTIVE`; satu jejak SCO ke C5:5F 1 detik lalu putus (jam tolak SCO yatim). |
| 4 | Codec | **UNCHECKED** | SCO tak pernah stabil; flag `hfpCodecAptxVoice` aktif = wideband didukung. |
| 5 | Gateway VPS | **PASS** | `voice.abstract.biz.id/health` 200, selftest 5/5, token+WS handshake OK. |
| 6 | Sideload HAP | **BELUM** | Jalur C berikutnya. |

**Kesimpulan:** Jalur B gugur di Infinix X6873 (HFP searah jam→HP saja).
Audio fisik dua arah sehat. Lanjut Jalur C (HAP file-transfer via Wear Engine P2P).
