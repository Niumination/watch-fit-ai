# Integrasi voice-gateway -> OpenCode (status & temuan)

Diperbarui: 24 Nov 2026

## Tujuan

Jam tangan bertanya lewat mic HP -> gateway VPS -> **OpenCode** (otak AI) ->
jawaban lisan Bahasa Indonesia -> diputar di speaker jam.

## Status

| Bagian | Status |
|--------|--------|
| Rekam mic HP + kirim audio ke gateway | PASS (terbukti ujung-ke-ujung) |
| ASR Groq | PASS (`X-Transcript-In` terisi) |
| TTS piper (suara Indonesia) | PASS (WAV ~63 KB, bukan nada) |
| Agent default `opencode` | **RUSAK — adapter memakai API lama** |
| Pemutaran WAV di speaker jam | BELUM (butuh HAP + signing Huawei) |

## Temuan: adapter `app/adapters/opencode.py` tidak cocok dengan OpenCode modern

Diverifikasi pada OpenCode v2.2.3 (Mac) sebagai pengganti observasi:

- `POST /session` -> **HTTP 405 Method Not Allowed**. Route terbentuk tapi method ditolak.
- `GET /api/session` -> HTTP 401 dengan header `www-authenticate: Basic realm="Secure Area"`.
  Jadi server HTTP menuntut **HTTP Basic**, bukan token Bearer.
- Seluruh jalur API berada di bawah prefix **`/api/`**, bukan root.
- Adapter saat ini:
  - memakai `POST /session` (salah jalur + salah method),
  - memakai basic auth `opencode:<password>` (benar skema, perlu verifikasi kredensial),
  - mengasumsikan stream SSE di `POST /session/{id}/message`.

Kesimpulan: integrasi opencode **belum layak produksi**. Perlu penelusuran jalur
persis (`docs/cek-opencode.sh`) langsung di VPS, karena versi di sana 2.1.4
(berbeda dari 2.2.3 yang bisa diuji di sini).

## Masalah kedua: jangkauan container

OpenCode di VPS bind `127.0.0.1:49374`. Dari dalam container Docker,
`127.0.0.1` = container itu sendiri, jadi `OPENCODE_URL=http://127.0.0.1:*`
pasti gagal. Pilihan perbaikan:

- **A (minimal):** bind OpenCode ke `--hostname 0.0.0.0`, lalu
  `OPENCODE_URL=http://172.17.0.1:49374`. Risiko: port terbuka ke jaringan Docker;
  tapi auth Basic tetap ada.
- **B (lebih bersih):** `network_mode: host` pada service gateway + `OPENCODE_URL=http://127.0.0.1:49374`.
  Konsekuensi: `expose`/`networks` gateway ikut berubah; Caddy tetap perlu publik.
- **C (paling aman):** OpenCode dijalankan sebagai service terpisah di VPS dengan
  bind khusus internal + unit systemd, dan gateway merujuk lewat `host.docker.internal`.

Rekomendasi: **B** bila gateway hanya butuh OpenCode lokal; **A** bila mau perubahan sesedikit mungkin.

## Cara reproduksi / diagnosa

Di VPS:

```bash
bash docs/cek-opencode.sh   # dari ~/zb/voice-gateway (path script disesuaikan)
```

Skrip memeriksa: proses, jalur API, auth Basic, IP bridge Docker, jangkauan dari
dalam container, dan upaya pembuatan sesi.

## Langkah berikutnya (urut)

1. Jalankan `cek-opencode.sh` di VPS, kirim keluarannya.
2. Berdasarkan status code nyata, perbaiki `adapters/opencode.py`
   (prefix `/api`, method yang benar, auth).
3. Uji ulang `POST /ask-audio` dari HP sampai transkrip jawaban AI sungguhan.
