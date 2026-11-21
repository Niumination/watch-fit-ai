# Gateway VPS — "otak suara" untuk jam

Tugasnya: menerima audio dari HP, mengerti ucapan, memilih agent, membaca jawabannya.

```
WS PCM ─▶ VAD ─▶ ASR ─▶ Router ─▶ Agent adapter ─▶ Voice Formatter ─▶ TTS ─▶ WS PCM
```

## Uji dulu, tanpa API key (sudah diverifikasi di workspace ini)

```bash
./tools/run_selftest.sh
```

Output nyata:

```
=== HASIL ===
state events    : ['listening', 'thinking', 'speaking', ...]
audio kembali   : 204800 byte  (6.40 s @ 16000 Hz)
final text      : Saya mendengar: tes satu dua tiga (1.8 detik audio). …
  [PASS] audio biner diterima
  [PASS] state 'speaking' muncul
  [PASS] transkrip final ada
  [PASS] latensi < 2000 ms
  [PASS] token palsu ditolak
```

Itu membuktikan rantai **WS → VAD (per frame 20 ms) → giliran → agent → TTS → audio biner**
dan auth berjalan, tanpa perlu HP, tanpa perlu model AI.

## Jalan cepat (uji jalur audio dulu, tanpa AI)

```bash
cp .env.example .env
# set TTS_BACKEND=null dulu supaya bisa menguji: apakah suara user sampai ke gateway?
docker compose up -d --build
curl -s localhost:8080/healthz        # {"ok":true}
docker compose logs -f gateway        # setiap giliran: "ASR(...ms): <transkrip>"
```

Maka setiap giliran bicara akan tercatat di log: `ASR(...ms): <transkrip>` — itu bukti
rantai **mic jam → SCO → HP → WSS → gateway** bekerja sebelum kamu menyentuh AI.

## Jalan lengkap

```bash
# 1) ASR lokal (gratis, CPU): whisper small int8, ~0,5-1x realtime di 2 vCPU
#    atau ASR_BACKEND=gemini kalau mau akurasi lebih tinggi
# 2) TTS: piper (offline, latensi <150 ms) / edge / gemini
# 3) agent: set OPENCODE_URL dst. ke container agent di network yang sama
docker compose up -d --build
```

## Suite test (30 tes, < 1 detik)

```bash
pip install -r requirements-dev.txt
pytest -q          # 30 passed
```

Yang diuji — bukan cuma unit test, tapi termasuk **adapter melawan server palsu sungguhan**
(`tools/mock_agents.py` meniru opencode/HTTP/OpenAI-compatible, termasuk cek Basic & Bearer auth)
dan **E2E lewat WebSocket** (token valid/ditolak, satu giliran penuh sampai audio biner kembali).

| File | Cakupan |
|---|---|
| `tests/test_dsp.py` | rms & resample (fallback tanpa `audioop`) |
| `tests/test_formatter.py` | markdown → kalimat, batas 4 kalimat |
| `tests/test_vad.py` | endpoint 600 ms, mute, ukuran frame per rate |
| `tests/test_router.py` | "pindah ke opencode", ekor ASR, pertanyaan biasa tidak salah-route |
| `tests/test_registry.py` | alias, env kurang → fallback echo (bukan crash) |
| `tests/test_adapters_mock.py` | opencode (auth 401 benar), HTTP generik, OpenAI-compatible SSE |
| `tests/test_ws_e2e.py` | token palsu ditolak, giliran penuh, event `agent` saat ganti agent |

## Routing agent lewat suara

Perintah dikenali **rule-based (<5 ms, gratis, deterministik)** sebelum dikirim ke agent:

| Ucapan | Efek |
|---|---|
| "pindah ke opencode" / "pakai deepseek dong" / "switch to gemini" | ganti agent, jawab "Baik, sekarang memakai …" |
| "opencode, cek status deploy" | ganti agent **dan** langsung kirim pertanyaannya |
| "agent apa ini?" | menyebut agent aktif, tanpa ganti |
| selain itu | diteruskan ke agent aktif |

Tambah agent baru = **edit `config/agents.json`** (tidak perlu menyentuh `main.py`):

```json
{ "id": "agent-baru", "label": "agent baru", "type": "http",
  "aliases": ["baru", "agentbaru"], "url_env": "AGENT_BARU_URL",
  "token_env": "AGENT_BARU_TOKEN", "hint": "untuk routing semantik" }
```

## Struktur

| File | Isi |
|---|---|
| `app/main.py` | WS endpoint, VAD energi, orkestrasi satu giliran |
| `app/adapters/opencode.py` | Adapter `opencode serve` (`POST /session/:id/message`, basic auth) |
| `app/adapters/http_generic.py` | Generik: `{text}`→`{answer}` atau OpenAI-compatible `/v1/chat/completions` |
| `app/formatter.py` | Markdown/kode → kalimat yang enak dibaca; batasi 4 kalimat |
| `app/asr.py` | faster-whisper (default) atau Gemini |
| `app/tts.py` | piper / edge / gemini / null |
| `app/auth.py` | Token perangkat + token sesi HMAC 15 menit |
| `app/protocol.md` | **Kontrak wire HP ⇄ gateway** — baca ini sebelum menulis klien lain |
| `app/dsp.py` | `rms` + `ratecv` dengan fallback murni Python (karena `audioop` dihapus di Python 3.13) |
| `app/adapters/echo.py` | Agent uji untuk Fase 1 & selftest |
| `app/registry.py` + `config/agents.json` | Daftar agent & pabrik adapter (satu sumber kebenaran) |
| `app/router.py` | Perintah suara → ganti agent (rule-based, opsional LLM) |
| `tools/mock_agents.py` | Server agent palsu untuk menguji adapter tanpa VPS |
| `tools/selftest.py` | Selftest end-to-end tanpa HP & tanpa API key |
| `tools/laptop_client.py` | "HP palsu": bicara ke gateway pakai mic/speaker laptop (`pip install sounddevice numpy`) |
| `Caddyfile` | TLS otomatis + proxy WebSocket |

## Tambah agent baru (2 menit)

1. Kalau agent-mu bicara HTTP/OpenAI-compatible: **cukup** tambah entri di `config/agents.json`.
2. Kalau protokolnya aneh: subclass `AgentAdapter`, implement `stream(text)`, daftarkan
   `type`-nya di `app/registry.py::build`.
3. Uji: `pytest -q tests/test_adapters_mock.py` (atau tambah test sendiri dengan mock server).

## Naik kelas ke produksi

Kode di sini sengaja "datar" agar mudah dipindahkan ke framework yang menangani
hal-hal sulit (turn detection semantik, barge-in yang benar, resampling, jitter buffer):

- **Pipecat** (BSD-2, Python) — transport-agnostic, kontrol penuh per stage,
  bagus untuk teleponi/custom transport. ([perbandingan](https://meetrix.io/blogs/livekit-agents-vs-pipecat/))
- **LiveKit Agents** (Apache-2.0) — kalau nanti butuh SIP/PSTN native, banyak sesi paralel,
  dan turn detector bawaan.
- Untuk **speech-to-speech**, ganti `asr+agent+tts` dengan satu koneksi
  Gemini Live / OpenAI Realtime, lalu pakai *function call* `delegate_to_agent`
  agar agent VPS-mu tetap bisa dipanggil sebagai tool.

## Yang wajib dijaga

- Port agent **tidak** boleh terbuka ke internet — hanya `agentnet` internal.
- Log audio mentah **jangan** disimpan; simpan transkrip dengan retensi terbatas.
- Kuota harian per device + batas durasi sesi (cegah tagihan tak terduga).
- Sandbox untuk agent coding: jalur suara tidak boleh bisa menjalankan aksi destruktif
  tanpa konfirmasi.
