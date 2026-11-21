# Bicara dengan AI Agent dari HUAWEI WATCH FIT 5
## Riset mendalam + skema arsitektur (v1.0 — 21 Nov 2026)

> Sasaran: dari jam tangan FIT 5 kamu menekan satu tombol / menerima "panggilan", lalu **berbicara dua arah** dengan agent milikmu sendiri — entah itu `opencode`, `deepseek-harness`, `openmausbot` di VPS, atau model Gemini/Claude.

---

## 0. Ringkasan eksekutif (baca 2 menit)

**Kesimpulan riset yang paling menentukan:** HUAWEI WATCH FIT 5 **tidak bisa** menjalankan aplikasi yang merekam/memutar suara streaming. FIT 5 adalah **lite wearable** (HarmonyOS Lite / LiteOS), framework-nya HML+JS+CSS di atas JerryScript ES5.1, tanpa API mikrofon, tanpa API audio streaming, tanpa internet langsung yang andal. ([Huawei: Wearable Device Types](https://forums.developer.huawei.com/forumPortal/en/topic/0201200820081036043), [pengalaman developer FIT4](https://forums.developer.huawei.com/forumPortal/en/topic/0201190810572199108))

**Tapi FIT 5 punya satu hal yang jauh lebih berharga: mikrofon + speaker + Bluetooth calling.** Artinya jam ini bisa berfungsi sebagai **headset HFP** bagi HP Android. Jadi jalur audio yang benar bukan "aplikasi AI di dalam jam", melainkan:

> **Jam = mikrofon + speaker + tombol jawab. HP = otak audio. VPS = otak AI.**

Skema yang saya rekomendasikan (Jalur B di bawah) dan sudah terbukti polanya di proyek lain (WhatsApp call muncul di jam; ada proyek `agentx` yang mengerjakan pola yang sama persis — [issue #1636](https://github.com/anis-marrouchi/agentx/issues/1636)):

```
WATCH FIT 5  ──HFP (mic+speaker, call UI native)──  HP ANDROID  ──WSS──  VPS GATEWAY  ──HTTP/SSE──  agent kamu
   (headset)                                    (app "AgentCall":           (Pipecat/FastAPI:       opencode /
                                                 Telecom + SCO + WS)        VAD, STT, TTS,          deepseek-harness /
                                                                            router, adapter)        openmausbot / Gemini
```

**Empat jalur yang layak, urut dari paling cepat jadi:**

| Jalur | Cara kerja | Waktu jadi | Kualitas audio | Biaya | Verdict |
|---|---|---|---|---|---|
| **A. Nomor telepon AI** | Beli nomor (Twilio/Telnyx) → SIP → LiveKit/Pipecat/OpenAI SIP. Simpan sebagai kontak "AI", **telepon dari jam** | 1–2 hari | 8 kHz narrowband (PSTN) | ~$0,03–0,10/menit | **MVP tercepat, nol koding di jam.** Bagus untuk validasi ide |
| **B. App Android + HFP** ⭐ | App di HP mendaftarkan *self-managed call* (Telecom) → audio di-route ke jam via SCO → streaming WSS ke gateway VPS | 2–4 minggu | sampai 16 kHz (wideband, jika mSBC) | ~$0,02–0,10/menit (AI saja) | **Rekomendasi utama.** Kontrol penuh, tanpa biaya telepon |
| **C. B + app lite di jam** | Tambah app lite (JS) di jam: tombol "Talk", pilih agent, transkrip, getar — komunikasi lewat Wear Engine P2P, audio tetap via HFP | +1–2 minggu | sama dengan B | sama dengan B | **Pengalaman terbaik**, tapi ada risiko API level & sideload |
| **D. Hack Gemini app** | Panggil app Gemini via `ACTION_ASSIST` / jadikan app-mu asisten default | — | — | — | **Tidak direkomendasikan.** Tidak ada API resmi, tidak bisa dikontrol, audio tidak dijamin ke jam |

**Soal "Gemini":** app Gemini di Android **tidak menyediakan API** untuk dikendalikan aplikasi lain (hanya bisa jadi *default assistant* untuk input pengguna, bukan untuk dipanggil program). Jadi "pakai Gemini" yang realistis = **pakai Gemini Live API** (`gemini-3.8-live`) langsung dari gateway VPS — suara & kepribadiannya sama, dan bisa dipanggil dari jam. ([Gemini Live API, Okt 2026](https://getstream.io/blog/speech-apis/))

---

## 1. Fakta perangkat: apa yang FIT 5 bisa dan tidak bisa

### 1.1 Spesifikasi yang relevan untuk proyek ini

| Aspek | Nilai | Implikasi |
|---|---|---|
| OS | HarmonyOS wearable platform (lite wearable) | Bukan Android/Wear OS; app harus lite-JS |
| Layar | AMOLED 1,82" 480×408 | UI app lite maksimal sederhana; 48 KB per halaman |
| Mic + Speaker | Ada, untuk **Bluetooth calling** | Ini jalur audio utama kita |
| Bluetooth | 6.0 (BR+BLE) | HFP untuk audio, BLE untuk Huawei Health |
| Wi-Fi | **Tidak ada** | Jam tidak bisa internet sendiri; lewat HP |
| Storage | ±4 GB | Cukup, tapi .hap dibatasi 10 MB |
| Baterai | 471 mAh, ~7–10 hari | Panggilan HFP menguras jauh lebih cepat dari standby |
| Kompatibilitas | Android 9+ / iOS 13+ | Android = jalur yang kita pakai (iOS tidak bisa install app jam) |

Sumber: [Huawei Levant — WATCH FIT 5](https://consumer.huawei.com/levant/wearables/watch-fit5/), [spesifikasi teknis](https://gadgetsandwearables.com/technical-specs/huawei-watch-fit-5/), [ringkasan ID](https://grandcellular.com/produk/huawei-watch-fit-5/).

### 1.2 Platform developer: dua dunia yang tidak kompatibel

Huawei punya **dua platform wearable yang sama sekali berbeda**, dan ini sumber 90% kebingungan developer:

| | **Smart Wearable** | **Lite Wearable** ← FIT 5 di sini |
|---|---|---|
| Contoh | Watch 4, Watch 5, Ultimate | **Watch FIT 1–5**, GT 2–6, Band, Watch D |
| Bahasa | ArkTS / ArkUI (Stage) | HML + JS + CSS (FA), **JerryScript ES5.1** |
| Toolchain | DevEco Studio 5.x, `hdc` via Wi-Fi | DevEco Studio legacy (3.1) + SDK API 5/6/9 |
| Deploy | Debug Wi-Fi langsung | Build `.hap` → copy ke `/sdcard/haps` → **DevEco Assistant** di HP |
| Batas | — | 48 KB/halaman, .hap ≤10 MB, tanpa back-stack router, tanpa audio/mic |
| Sumber | [Wearable Device Types](https://forums.developer.huawei.com/forumPortal/en/topic/0201200820081036043) | [HA-Huawei: GT physically rejects ArkTS HAP](https://github.com/gentslava/Home-Assistant-HarmonyOS-Next) |

Konsekuensi keras: **jangan menulis app ArkTS untuk FIT 5.** Watch GT/FIT "physically rejects third-party ArkTS Stage HAPs ('Failed to decompress')". Satu-satunya app yang bisa jalan adalah lite-JS.

### 1.3 Apa yang lite-JS **tidak** bisa (dan ini yang membunuh ide "app AI di jam")

- ❌ **Tidak ada API mikrofon / rekam suara / audio streaming.** API yang ada hanya `@system.sensor`, `@system.vibrator`, `@system.brightness`, `@system.file`, `@system.storage`, `@system.router`, `@system.notification`, `@system.prompt`, `@system.package`, `@system.fetch`, `@system.geolocation`. Tidak ada `audio`/`record` untuk menangkap suara. Panduan komunitas menyebut eksplisit: "many system features are not available or limited on LiteWearable… like playing videos and audio" ([guide](https://github.com/megaacheyounes/harmonyos-dev-guide)).
- ❌ **Tidak ada Wi-Fi.** `@system.fetch` di FIT 4 bergantung pada "BT proxy" yang **dimatikan di region Eropa** dan dilaporkan gagal ke server sendiri. Jadi jangan mengandalkan HTTP langsung dari jam. ([laporan developer FIT 4](https://forums.developer.huawei.com/forumPortal/en/topic/0201190810572199108))
- ❌ Tidak ada background execution. App mati saat layar mati / pindah page.
- ❌ Tidak ada WebSocket / streaming.

**Kesimpulan:** app di jam hanya bisa jadi **remote control + display** (kirim perintah, tampilkan transkrip, getar). Suara **wajib** lewat jalur HFP ke HP.

### 1.4 Jalur audio yang tersedia: HFP

Karena FIT 5 punya "Bluetooth calling", ia memakai profil **HFP (Hands-Free Profile)** — jam berperan sebagai headset, HP sebagai audio gateway. Ini artinya:

- Android bisa mengaktifkan **SCO** (Synchronous Connection Oriented) link dan membuka `AudioRecord`/`AudioTrack` di jalur SCO.
- Yang didengar/direkam adalah **speaker & mic jam**, tanpa perlu satu baris kode di jam.
- Bonus: dengan **self-managed `ConnectionService`**, sesi ini terlihat oleh OS sebagai *panggilan VoIP*. Jam akan menampilkan **layar panggilan native** (tombol jawab/tutup) persis seperti panggilan WhatsApp — dan tombol jawab di jam benar-benar berfungsi.

Itu adalah mekanisme inti seluruh proyek ini, dan sudah dibuktikan berpola sama: lihat spike `agentx` `#1638` yang menyiapkan "self-managed Telecom call (outgoing, or incoming to answer on the watch), route to the watch's hands-free link: Telecom's Bluetooth route first, then `setCommunicationDevice`".

---

## 2. Peta opsi arsitektur secara rinci

### Jalur A — "Nomor telepon AI" (zero-code di jam, MVP 1–2 hari)

```
WATCH FIT 5 ──dial/kontak (HFP call)── HP (dialer bawaan) ──PSTN/SIP── Twilio/Telnyx
                                                              └── LiveKit SIP / Pipecat / OpenAI Realtime SIP ── agent
```

**Cara:**
1. Beli nomor telepon di Twilio/Telnyx (atau pakai SIP trunk yang sudah ada).
2. Hubungkan nomor itu ke salah satu: **OpenAI Realtime SIP** (paling cepat, `sip:` langsung ke Realtime API), **LiveKit SIP** (open-source SIP bridge built-in), atau **Pipecat** via serializer teleponi. LiveKit punya SIP native; Pipecat butuh provider WebSocket seperti Twilio Media Streams. ([perbandingan](https://meetrix.io/blogs/livekit-agents-vs-pipecat/))
3. Di HP, simpan nomor sebagai kontak bernama "AI Agent". Karena FIT 5 mendukung "dial contacts", kamu **menelepon agent-mu dari jam**.
4. Jawaban AI kembali sebagai suara di speaker jam; mic jam dipakai otomatis.

**Kelebihan:** nol risiko platform, nol koding di jam, UI panggilan 100% native, jawab/tutup dari jam, jalan di HP apa pun.
**Kekurangan:** audio **narrowband 8 kHz** (G.711) — cukup untuk STT tapi terdengar "telepon"; ada biaya per menit nomor + PSTN (~$0,01–0,02/menit di luar biaya AI); latensi tambahan 300–500 ms dari jalur teleponi; agent tidak bisa dipilih dari jam (harus beda nomor per agent).
**Pakai untuk:** membuktikan alur & mengukur preferensi bicara vs baca, sebelum investasi app.

### Jalur B — App Android "AgentCall" (rekomendasi utama)

Komponen di HP:

| Modul | Fungsi teknis |
|---|---|
| `PhoneAccount` + self-managed `ConnectionService` | Mendaftarkan app sebagai penyedia panggilan. Sesi AI tampil sebagai panggilan; bisa dibuat **incoming** sehingga jam berdering dan dijawab dari jam (`MANAGE_OWN_CALLS`) |
| `AudioRouter` | `MODE_IN_COMMUNICATION`, `setCommunicationDevice(TYPE_BLUETOOTH_SCO)` (API 31+; `startBluetoothSco()` untuk lama), tunggu `SCO_AUDIO_STATE_CONNECTED` |
| `AudioIo` | `AudioRecord(VOICE_COMMUNICATION, 16 kHz mono PCM16)` + `AudioTrack(USAGE_VOICE_COMMUNICATION)`; encoder Opus opsional |
| `WsTransport` | WebSocket WSS ke `wss://voice.domainmu.com/ws` — kirim PCM/Opus, terima PCM/Opus, event JSON (partial transcript, status, end) |
| `CallService` | Foreground service (`microphone|phoneCall`), wake lock, notifikasi, auto-timeout saat hening |
| `AgentPicker` | Pilih agent (opencode / deepseek-harness / openmausbot / Gemini) — dari notifikasi, QS tile, atau jam (lihat Jalur C) |

**Kenapa SCO dan bukan A2DP?** A2DP satu arah (output saja) dan latensinya besar. Untuk dua arah dan latensi rendah, HFP/SCO satu-satunya jalan. Catatan teknis: stream output **harus** `STREAM_VOICE_CALL`/`USAGE_VOICE_COMMUNICATION`, mono; sumber rekaman **harus** `VOICE_COMMUNICATION`, kalau tidak, Android akan merekam dari mic HP, bukan mic jam (perilaku ini konsisten sejak Android 5.0). ([referensi](https://stackoverflow.com/questions/33757491/android-recording-audio-from-bluetooth-headset-sometimes-records-from-the-mic))

**Detail penting yang sering bikin gagal:**
- Jam harus di-pair sebagai **"Bluetooth calling"** di Huawei Health + muncul di daftar Bluetooth HP sebagai headset. Pairing Health-only (BLE) saja tidak cukup untuk HFP.
- `BLUETOOTH_CONNECT` (API 31+) wajib diminta runtime, selain `RECORD_AUDIO`, `MODIFY_AUDIO_SETTINGS`.
- Beri jeda 100–300 ms setelah SCO tersambung sebelum `AudioRecord.startRecording()`.
- Android 11+ membatasi mic saat layar mati / app tidak foreground → wajib foreground service bertipe `microphone`, dimulai saat app masih terlihat.
- Panggilan telepon asli selalu menang atas SCO: kalau ada telepon masuk, sesi AI harus menutup SCO dan membuka ulang setelahnya.

### Jalur C — Tambah app lite di jam (pengalaman "dari jam")

App lite-JS kecil (target: 1 halaman, <48 KB) dengan:

- 3 tombol besar: **Talk**, pilih Agent (list), **Mute/End**.
- Status: "Menyambung…", "Mendengar…", "Berpikir…", "Bicara…".
- Transkrip jawaban (teks pendek) + getar saat jawaban siap.
- Kirim perintah ke HP via **Wear Engine P2P**: `{"cmd":"start","agent":"opencode"}` (pesan ≤1 KB; pakai file transfer untuk payload besar).

Batasan yang harus dihormati: ES5 saja (tanpa `let`, arrow function, template literal), tanpa back-stack, download SDK Wear Engine lite wearable (JS) dan set `peerPkgName` + `peerFingerPrint`, halaman bisa di-kill kapan saja → selalu render ulang state di `onShow`/`onInit`.

**Status Wear Engine & HP non-Huawei:** Wear Engine **mendukung HP non-Huawei** asalkan **HMS Core** terpasang dan Huawei Health diizinkan berjalan di background. Seri **WATCH FIT 1 dan seterusnya** tercantum sebagai perangkat yang didukung. ([Service Introduction](https://developer.huawei.com/consumer/en/doc/connectivity-Guides/service-introduction-0000000000018585), [FAQ](https://developer.huawei.com/consumer/en/doc/connectivity-guides/faq-0000001050818031))

**Risiko Jalur C — jujur di depan:** instalasi app lite via DevEco Assistant sangat sensitif terhadap **API level**. Laporan nyata: GT3 maksimal API 6; GT5 menolak dengan *Error 40 "Invalid configuration file format"* saat dibangun dengan SDK baru; FIT 3 berhasil setelah turun ke DevEco 3.1 + SDK API 6. ([Error 40](https://forums.developer.huawei.com/forumPortal/en/topic/0201202047517553128), [FIT 3 berhasil](https://www.reddit.com/r/Huawei/comments/1ulqnag/unable_to_install_custom_hello_world_app_on/)). Untuk FIT 5 (rilis 2026) belum ada laporan publik → **harus diuji sendiri**, sediakan rencana fallback: kalau gagal, pakai notifikasi bertombol + QS tile di HP saja.

### Jalur D — Mengapa "panggil app Gemini" bukan solusi

- App Gemini tidak mengeskpos API/broadcast untuk dikendalikan app lain. Satu-satunya titik integrasi resmi adalah peran **default digital assistant** (`VoiceInteractionService`) — itu artinya *app-mu* yang jadi asisten, bukan memerintah Gemini.
- `ACTION_ASSIST` bisa memunculkan Gemini, tapi: (a) kamu tidak bisa mengalirkan audio ke/dari sesi itu, (b) input mic diambil app Gemini sendiri di HP, bukan dari jam, (c) tidak ada cara mengakhiri/mengontrol dari jam.
- Solusi nyata: **Gemini Live API** langsung dari gateway-mu. Bahasa Indonesia didukung; harga audio input $3/1M token (≈$0,005/menit) dan output $12/1M (≈$0,018/menit) — **≈$0,023/menit** blended, ±4× lebih murah per menit dibanding `gpt-realtime-2.1`. ([pricing, Sep 2026](https://www.multimodelchat.com/blog/gemini-3-8-live-pricing))

---

## 3. Arsitektur yang direkomendasikan (Jalur B + C)

Lihat diagram: [`02-arsitektur.svg`](02-arsitektur.svg)

### 3.1 Pembagian tanggung jawab

**WATCH FIT 5** — headset + UI panggilan native + (opsional) app lite remote control.

**HP ANDROID (app AgentCall)** — jembatan audio & sesi:
- mengubah sesi AI menjadi "panggilan" (Telecom) supaya jam menampilkan UI & tombol jawab;
- memegang SCO link, capture 16 kHz, playout;
- menyimpan token sesi, memilih agent, mengelola reconnect, mengakhiri sesi;
- **tidak** melakukan STT/LLM/TTS lokal (kecuali mode offline opsional).

**VPS GATEWAY (`wss://voice.domainmu.com`)** — seluruh kecerdasan suara:
- `Transport`: WebSocket biner (PCM16/Opus) + JSON control; alternatif WebRTC kalau nanti butuh.
- `VAD & Turn`: Silero VAD + endpointing (Smart Turn) → menentukan kapan user selesai bicara; menangani **barge-in**.
- `ASR`: streaming (Gemini/Deepgram/Whisper-streaming).
- `Router`: klasifikasi intent → agent mana (`opencode` / `deepseek-harness` / `openmausbot` / `gemini-live`).
- `Adapters`: satu kelas per agent, kontrak seragam (`start`, `send(text)`, `stream()`, `cancel()`).
- `Voice Formatter`: ringkas output panjang (markdown/kode dari agent coding) jadi 2–4 kalimat untuk dibacakan, plus versi teks penuh untuk dikirim ke jam/HP.
- `TTS`: Gemini TTS / OpenAI TTS / ElevenLabs / Piper (self-host).
- `Session & Auth`: token perangkat, kuota, timeout, log audit.

**AGENT DI VPS** — dibiarkan apa adanya. Gateway hanya butuh satu dari: HTTP JSON, SSE stream, atau MCP.

### 3.2 Kenapa dua mode AI (S2S vs cascade)

| | **Mode 1 — Speech-to-Speech** (Gemini Live / gpt-realtime) | **Mode 2 — Cascade** (STT→teks→agent→TTS) |
|---|---|---|
| Latensi | 300–500 ms, terasa seperti telepon | 800–1500 ms |
| Barge-in | Native | Harus dirakit (VAD + cancel TTS) |
| Cocok untuk | obrolan, tanya-jawab cepat, kontrol | **agent coding/tugas panjang** (opencode dkk.) |
| Kontrol output | terbatas | penuh (bisa ringkas, bisa pilih kalimat mana dibaca) |

**Rekomendasi: hibrida.** S2S sebagai "lapisan percakapan" (siapa pun yang bicara terasa natural + barge-in), dan saat user meminta tugas ke agent VPS, lapisan itu **memanggil tool** `delegate_to_agent(name, instruction)` lalu mengumumkan hasil secara asinkron ("Selesai. Ada 3 temuan, mau saya bacakan?").

### 3.3 Alur sesi (happy path)

```
1. User (jam)  → tekan "Talk" (app lite) ATAU panggil dari HP/QS tile
2. HP          → Telecom: start self-managed call; AudioRouter → SCO ke jam
3. HP          → WSS connect + auth(token) → gateway buka sesi (VAD, ASR, agent default)
4. Jam mic     → HP AudioRecord 16k → gateway → VAD mendeteksi akhir ucapan
5. Gateway     → ASR transcript → Router → agent adapter
6. Agent       → stream token/markdown → VoiceFormatter → TTS (kalimat per kalimat)
7. HP          → AudioTrack → SCO → speaker jam   (jam menampilkan layar panggilan)
8. Barge-in    → user bicara saat AI bicara → VAD → hentikan TTS (<200 ms) → kembali ke 4
9. Transkrip   → dikirim sebagai event JSON ke HP → (opsional) diteruskan ke app lite via P2P
10. Tutup      → tombol merah di jam / timeout hening 60 s → end call, tutup SCO & WSS
```

### 3.4 Anggaran latensi (target: <1,2 s end-to-end)

| Tahap | Target | Catatan |
|---|---|---|
| SCO setup (sekali per sesi) | 300–800 ms | jangan dihitung per giliran; buka sekali di awal |
| Capture + buffer | 20–60 ms | frame 20 ms |
| HP → VPS (Aceh → Singapura/Jakarta) | 30–70 ms | **taruh VPS di SG/JKT**, bukan EU/US (bisa 180–260 ms) |
| VAD endpoint | 200–500 ms | kompromi: cepat = sering motong |
| ASR streaming final | 100–300 ms | |
| Agent TTFT | 300–900 ms | opencode bisa lebih lama; mulai TTS dari kalimat pertama |
| TTS TTFB | 150–400 ms | streaming per kalimat |
| Playout buffer | 60–120 ms | |

**Implikasi praktis:** VPS Indonesia/Singapura + streaming TTS per kalimat + mulai bicara sebelum jawaban agent selesai = terasa responsif meski agent-nya lambat.

---

## 4. Menyambung ke agent yang sudah kamu punya

Semua agent dibungkus satu kontrak. Contoh konkret untuk **opencode**: `opencode serve` mengekspos HTTP OpenAPI 3.1 di `/doc`, dengan `POST /session` (buat sesi), `POST /session/:id/message` (kirim + tunggu), `POST /session/:id/prompt_async` (kirim tanpa tunggu), `GET /event` (SSE stream), dan basic auth via `OPENCODE_SERVER_PASSWORD`. ([docs.openCode server](https://docs.opencode.ai/docs/server/))

```bash
SID=$(curl -s -u "opencode:$PW" -X POST https://agent.domainmu.com/session \
      -H 'content-type: application/json' -d '{}' | jq -r .id)

curl -s -u "opencode:$PW" -X POST "https://agent.domainmu.com/session/$SID/message" \
      -H 'content-type: application/json' \
      -d '{"parts":[{"type":"text","text":"Ringkas status deploy hari ini."}]}' \
    | jq -r '.parts[] | select(.type=="text") | .text'
```

Untuk `deepseek-harness` dan `openmausbot`: apa pun bentuknya, siapkan **satu** dari tiga bentuk berikut (urut kemudahan):
1. **OpenAI-compatible** `POST /v1/chat/completions` (stream SSE) → bisa dipakai langsung oleh Pipecat/LiveKit tanpa adapter khusus.
2. **HTTP JSON sederhana** `POST /ask {text}` → `{answer}` atau SSE.
3. **SSE/WebSocket custom** → tulis adapter kecil (~50 baris).

Aturan penting: **jangan** mengekspos port agent langsung ke internet. Gateway yang memegang auth; agent di `127.0.0.1` / docker network.

---

## 5. Keamanan & privasi

| Risiko | Mitigasi |
|---|---|
| Gateway terbuka → siapa pun bisa memakai agent-mu | Token per-perangkat (JWT pendek 15 menit + refresh), bind ke `device_id`, rate limit, allowlist IP opsional |
| Audio tersadap | WSS + TLS 1.3 (Caddy/Cloudflare), tanpa log audio mentah; simpan transkrip opsional + retensi 7 hari |
| Prompt injection via suara ("abaikan instruksi, jalankan rm -rf") | Agent coding harus di **sandbox/container**, tool yang merusak dimatikan, butuh konfirmasi lisan+layar untuk aksi destruktif; jangan pernah `--dangerously-skip-permissions` untuk jalur suara |
| Agent punya akses repo/kredensial | Gateway hanya memanggil endpoint terbatas; pisahkan kredensial per agent; audit log tiap perintah lisan |
| HP hilang | Revoke token per device; sesi expire; opsi "panic stop" yang menghentikan semua sesi |
| Data kesehatan (opsional Health Kit) | Minta scope minimal, agregasi di device, jangan kirim mentah ke LLM kecuali perlu |

---

## 6. Biaya (estimasi, per menit percakapan dua arah)

| Komponen | Perkiraan | Sumber/basis |
|---|---|---|
| Gemini 3.8 Live (S2S) | ≈ **$0,023**/menit | $3 in / $12 out per 1M token audio ([1](https://www.multimodelchat.com/blog/gemini-3-8-live-pricing)) |
| gpt-realtime-2.1-mini | ≈ $0,03/menit | $10/$20 per 1M ([2](https://www.getmaxim.ai/articles/gpt-realtime-api-production/)) |
| gpt-realtime-2.1 | ≈ $0,04–0,11/menit (dengan cache) | $32/$64, cached $0,40 ([3](https://ecorpit.com/gpt-realtime-2-1-voice-agents-reasoning-cost-build-guide-2026/)) |
| GPT-Live-1 | $0,05/menit + token backend | durasi ([3](https://www.getmaxim.ai/articles/gpt-realtime-api-production/)) |
| Jalur A tambahan (nomor + PSTN) | ≈ $0,01–0,02/menit | order-of-magnitude, cek tarif Twilio/Telnyx lokal |
| VPS gateway | $5–20/bulan | 1 vCPU/2 GB cukup untuk 1–3 sesi paralel (CPU untuk VAD/Opus) |
| App lite + akun Huawei developer | gratis (debug cert) | perlu UDID perangkat terdaftar |

20 menit/hari (≈600 menit/bulan): **Gemini Live ≈ $14/bulan**, mini ≈ $18, realtime-2.1 penuh ≈ $25–65, GPT-Live-1 ≈ $30 + token. Jauh lebih murah dari langganan apa pun per menit pemakaian.

---

## 7. Risiko & mitigasi (register)

| # | Risiko | Peluang | Dampak | Mitigasi / rencana B |
|---|---|---|---|---|
| R1 | FIT 5 menolak install app lite (Error 40/47 API mismatch) | **Tinggi** | Sedang | Uji di hari pertama; siapkan versi API 5/6 (DevEco 3.1 + SDK lama). Fallback: tanpa app jam, kontrol dari HP + notifikasi bertombol |
| R2 | SCO menyambung tapi mic tetap dari HP | Sedang | Tinggi | Pastikan `VOICE_COMMUNICATION` + `setCommunicationDevice` + jeda; cek `dumpsys audio`; uji di 2 HP berbeda |
| R3 | Audio 8 kHz (narrowband), akurasi STT turun | Sedang | Sedang | Cek mSBC/wideband via `dumpsys bluetooth_manager`; kalau narrowband, perkecil kosakata domain, tambah prompt ASR, atau naikkan volume bicara dekat jam |
| R4 | Echo saat barge-in (mic menangkap speaker jam) | **Tinggi** | Sedang | Mulai mode semi-duplex (mic di-gate saat TTS), lalu tambah AEC (webrtc-audio-processing) di HP/gateway; AEC3 di gateway lebih mudah dikontrol |
| R5 | Panggilan/telepon asli memotong SCO | Sedang | Rendah | Listener state Telecom; auto-pause sesi & resume |
| R6 | Baterai jam terkuras | Pasti (wajar) | Rendah | Timeout hening otomatis, batas durasi, indikator baterai di UI, hindari sesi "selalu terbuka" |
| R7 | Huawei Health dibunuh OS (HP non-Huawei) | Sedang | Tinggi (Wear Engine mati) | Allow background + autostart; audio HFP tetap jalan walau Wear Engine mati (Jalur B aman, hanya remote di Jalur C yang terganggu) |
| R8 | Latensi agent coding tinggi (menit) | Pasti | Sedang | Desain async: "sedang dikerjakan, saya kabari"; notifikasi + getar saat selesai; jangan menahan panggilan |
| R9 | Biaya membengkak | Rendah | Sedang | Kuota per hari, batas durasi sesi, matikan S2S saat idle |

---

## 8. Rencana implementasi bertahap

### Fase 0 — Validasi 1 hari (tanpa koding)
- Pair FIT 5 sebagai Bluetooth calling; uji: rekam voice memo di jam, dengarkan di HP; cek `adb shell dumpsys bluetooth_manager | grep -i hfp` dan `adb shell dumpsys audio | grep -i sco` (lihat apakah `mSBC` dan sample rate 8k/16k).
- Uji "panggilan WhatsApp" → apakah jam menampilkan layar panggilan + tombol jawab? (Ini bukti Jalur B mungkin.)
- Uji `fetch`/sideload: buka DevEco Assistant, coba install hap "hello world" lite → catat pesan error (bukti R1).

### Fase 1 — "Bisa bicara" (1–2 minggu)
- App Android: `ConnectionService` + `AudioRouter` + WS ke gateway echo bot ("halo" → dipantulkan via TTS).
- Gateway: FastAPI + WS + TTS saja. **Target metrik:** latensi TTS-dipantulkan < 800 ms, mic dari jam terkonfirmasi.
- Gate lulus: bicara dari jam, mendengar balasan dari jam, tombol merah berfungsi.

### Fase 2 — "Bisa berpikir" (1–2 minggu)
- Tambah VAD + ASR + router + adapter `opencode` (mulai dari agent yang paling kamu pakai).
- Tambah `VoiceFormatter` (ringkas output panjang), barge-in, timeout.
- **Gate:** "Tanya status repo ke opencode dari jam dan dapat ringkasan lisan < 5 s."

### Fase 3 — "Dari jam, bukan dari HP" (1–2 minggu)
- App lite: tombol Talk, pilih agent, status, transkrip; Wear Engine P2P ke app Android.
- Fallback UI di HP tetap ada (notifikasi + QS tile + home widget).

### Fase 4 — Poles
- Multi-agent routing lisan ("panggil deepseek"), memori sesi, mode hands-free (wake-word? tidak tersedia di jam — pakai long-press tombol di jam / ketuk dua kali), integrasi Health Kit (konteks: HR/stres) opsional.

---

## 9. Checklist verifikasi teknis (perintah & cara cek)

```bash
# 1) Apakah jam terlihat sebagai HFP headset?
adb shell dumpsys bluetooth_manager | grep -iE "hfp|headset|sco|mSBC"

# 2) Apa yang terjadi saat SCO aktif (jalankan saat sesi berjalan)
adb shell dumpsys audio | grep -iE "sco|communication device|sample rate"

# 3) Pastikan app memakai route yang benar
adb logcat -s WatchSpike AgentCall AudioRouter

# 4) Cek apakah mic benar dari jam (peak level) — lihat kode AudioIo.peakLevel()
#    Bandingkan: tutup mic jam dengan jari → level harus turun drastis

# 5) Cek API level app lite (saat build)
#    build-profile.json5 → "compileSdkVersion"/"compatibleSdkVersion" = 5 atau 6
#    Install via DevEco Assistant; kalau "Error 40/47" → turunkan API & pakai DevEco 3.1
```

**Metrik keberhasilan yang harus kamu catat:** latensi end-to-end (ms), WER STT untuk bahasa Indonesia + istilah teknis, durasi baterai per 10 menit sesi, tingkat barge-in salah (false trigger), dan pesan error instalasi lite app.

---

## 10. Kalau ternyata FIT 5 kurang

Jujur: FIT 5 adalah jam kebugaran yang *kebetulan* punya mic+speaker. Untuk "asisten suara di pergelangan" kelas produk, ada dua alternatif arsitektural:

1. **Jam Wear OS** (Galaxy Watch / Pixel Watch): app native Kotlin + `AudioRecord` langsung di jam, tanpa HP, kualitas wideband, wake word. Kelemahan: bukan ekosistem Huawei Health.
2. **Pendant/ESP32 terpisah** (mis. pola Xiaozhi): mic+speaker+Wi-Fi sendiri, tombol fisik, latensi sangat rendah. Kelemahan: perangkat tambahan.
3. **Tetap FIT 5** tapi terima bahwa "call experience" adalah bentuk interaksinya — yang sebenarnya **cocok**: satu tombol, angkat, bicara, tutup. Tidak perlu menatap layar.

Rencana di dokumen ini mengasumsikan kamu tetap memakai FIT 5, dan tetap memberikan pengalaman "telepon ke AI" yang utuh.

---

## 11. Referensi utama

1. Huawei Developers — [Wearable Device Types](https://forums.developer.huawei.com/forumPortal/en/topic/0201200820081036043) (lite vs smart wearable)
2. Huawei Developers — [Wear Engine: Service Introduction](https://developer.huawei.com/consumer/en/doc/connectivity-Guides/service-introduction-0000000000018585) (dukungan WATCH FIT 1+, P2P messaging)
3. Huawei Developers — [Wear Engine: Getting Started / FAQ](https://developer.huawei.com/consumer/en/doc/connectivity-guides/faq-0000001050818031) (HMS Core di HP non-Huawei)
4. Huawei Developers — [How to test the App on Lite Wearable Watches](https://forums.developer.huawei.com/forumPortal/en/topic/0203196494245382012) (DevEco Assistant, `/sdcard/haps`)
5. Huawei Developers — [Error 40 installing Lite Wearable hap](https://forums.developer.huawei.com/forumPortal/en/topic/0201202047517553128) (batas API level)
6. Huawei Developers — [Http request to fetch data on Lite wearables](https://forums.developer.huawei.com/forumPortal/en/topic/0201190810572199108) (fetch tidak andal)
7. [Home Assistant for Huawei Wearables](https://github.com/gentslava/Home-Assistant-HarmonyOS-Next) (bukti: GT/FIT hanya lite-JS; Wear Engine P2P dari Android)
8. [agentx #1636](https://github.com/anis-marrouchi/agentx/issues/1636) + [PR #1638](https://github.com/anis-marrouchi/agentx/pull/1638) (self-managed Telecom call → SCO ke jam; spike yang terbukti polanya)
9. [opencode Server docs](https://docs.opencode.ai/docs/server/) (HTTP OpenAPI untuk agent)
10. [S2S 2026: OpenAI Realtime vs Gemini Live](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/speech-to-speech-realtime-api-gemini-live-seamless) dan [Gemini 3.8 Live pricing](https://www.multimodelchat.com/blog/gemini-3-8-live-pricing)
11. [LiveKit vs Pipecat](https://meetrix.io/blogs/livekit-agents-vs-pipecat/) (SIP native vs transport-agnostic)
12. [Huawei WATCH FIT 5 — spesifikasi resmi](https://consumer.huawei.com/levant/wearables/watch-fit5/)
