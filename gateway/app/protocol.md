# Protokol wire HP ⇄ Gateway (v1)

Tujuan: sesedikit mungkin event, supaya mudah juga diimplementasikan di klien lain (web, iOS).

## Transport
`wss://voice.domainmu.com/ws?token=<session_token>` — HTTP/1.1 upgrade.
Header opsional: `Authorization: Bearer <session_token>`.

## HP → Gateway

| Frame | Isi |
|---|---|
| **binary** | PCM16 **little-endian**, mono, `rate` Hz (8000 atau 16000), frame 20 ms (320 / 640 byte) |
| text | `{"t":"hello","agent":"opencode","rate":16000,"device":"pixel-8"}` |
| text | `{"t":"mute","on":true}` |
| text | `{"t":"interrupt"}` — user menekan tombol saat AI bicara (barge-in eksplisit) |
| text | `{"t":"end"}` — tutup sesi |

## Gateway → HP

| Frame | Isi |
|---|---|
| **binary** | PCM16 LE mono, `rate` Hz — langsung putar ke `AudioTrack` (USAGE_VOICE_COMMUNICATION) |
| text | `{"t":"state","v":"listening\|thinking\|speaking"}` — dipakai untuk UI/getar di jam |
| text | `{"t":"partial","text":"..."}` — transkrip sementara user |
| text | `{"t":"final","text":"..."}` — jawaban teks lengkap (ditampilkan di jam, disimpan) |
| text | `{"t":"error","msg":"..."}` |

## Aturan yang disepakati

1. **Satu sesi = satu panggilan.** Tutup kapan pun tanpa negosiasi (`{"t":"end"}` lalu close 1000).
2. **Barge-in**: gateway berhenti mengirim binary dalam ≤ 100 ms setelah mendeteksi suara user
   atau menerima `interrupt`. HP tidak perlu memberi tahu selain frame audio.
3. **Rate** ditentukan HP (hasil SCO). Gateway wajib me-resample TTS ke rate itu.
4. Semua teks UTF-8. Tidak ada audio terenkripsi tambahan — TLS sudah cukup.
5. Versi protokol dinaikkan kalau ada field wajib baru; klien lama harus tetap jalan.
