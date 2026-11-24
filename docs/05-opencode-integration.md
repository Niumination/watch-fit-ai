# Integrasi voice-gateway -> OpenCode (ARSIP + pelajaran)

**Status: TIDAK DIPAKAI LAGI sejak 24 Nov 2026 — agent default = `omb`.**

Agent produksi sekarang OMB (`gateway/app/adapters/omb.py`, commit `43cf487`;
env `OMB_BRIDGE_URL` / `OMB_WEBHOOK_ID` / `OMB_WEBHOOK_TOKEN`). OpenCode v2.1.4 di
VPS zb-vela masih berjalan di `127.0.0.1:49374` (host-local), tetapi **tidak dipakai
gateway dan tidak dipakai lagi**. Adapter `app/adapters/opencode.py` rusak terhadap
API OpenCode modern; jangan dipakai untuk produksi.

Diperbarui: 25 Nov 2026

> Dokumen ini arsip + pelajaran. Isinya sengaja dipertahankan sebagai catatan teknis
> mengapa adapter opencode tidak cocok. Track integrasi opencode **ditutup**.

## Tujuan (dulu)

Jam tangan bertanya lewat mic HP -> gateway VPS -> **OpenCode** (otak AI) ->
jawaban lisan Bahasa Indonesia -> diputar di speaker jam.

## Status (usang — agent default sudah pindah ke OMB)

| Bagian | Status |
|--------|--------|
| Rekam mic HP + kirim audio ke gateway | PASS (terbukti ujung-ke-ujung) |
| ASR Groq | PASS (`X-Transcript-In` terisi) |
| TTS piper (suara Indonesia) | PASS (WAV, bukan nada) |
| Agent default `opencode` | **RUSAK — adapter memakai API lama; TIDAK DIPAKAI LAGI** |
| Agent default `omb` | AKTIF sejak 24 Nov 2026 (commit 43cf487) |
| Pemutaran WAV di speaker jam | BELUM (butuh HAP + signing Huawei) |

## Pengganti: OMB (OpenMausBot via relay-bridge)

- Env: `OMB_BRIDGE_URL=http://172.18.0.1:8801` (IP bridge Docker host, bukan
  `127.0.0.1`), `OMB_WEBHOOK_ID`, `OMB_WEBHOOK_TOKEN`.
- Kontrak: `POST {base}/hooks/{webhook_id}` dengan header
  `authorization: Bearer <token>` dan body `{"message": "...", "state": "idle"}`;
  balasan 200 berfield **`reply`** (bukan `answer`/`text`).
- Di dalam container, `127.0.0.1` = container itu sendiri, jadi URL bridge harus
  memakai IP host Docker. Ini pelajaran serupa dengan masalah jangkauan di bawah.

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

Kesimpulan: integrasi opencode **belum layak produksi**, dan akhirnya **tidak
dilanjutkan** — otak diganti OMB. Perlu penelusuran jalur persis
(`docs/cek-opencode.sh`) langsung di VPS, karena versi di sana 2.1.4 (berbeda dari
2.2.3 yang bisa diuji di sini).

## Masalah kedua: jangkauan container

OpenCode di VPS bind `127.0.0.1:49374`. Dari dalam container Docker,
`127.0.0.1` = container itu sendiri, jadi `OPENCODE_URL=http://127.0.0.1:*`
pasti gagal. Pilihan perbaikan (arsip, tidak dipakai lagi):

- **A (minimal):** bind OpenCode ke `--hostname 0.0.0.0`, lalu
  `OPENCODE_URL=http://172.17.0.1:49374`. Risiko: port terbuka ke jaringan Docker;
  tapi auth Basic tetap ada.
- **B (lebih bersih):** `network_mode: host` pada service gateway + `OPENCODE_URL=http://127.0.0.1:49374`.
  Konsekuensi: `expose`/`networks` gateway ikut berubah; Caddy tetap perlu publik.
- **C (paling aman):** OpenCode dijalankan sebagai service terpisah di VPS dengan
  bind khusus internal + unit systemd, dan gateway merujuk lewat `host.docker.internal`.

Rekomendasi dulu: **B** bila gateway hanya butuh OpenCode lokal; **A** bila mau
perubahan sesedikit mungkin. Kini tidak relevan karena OpenCode ditinggalkan.

## Cara reproduksi / diagnosa (arsip)

Di VPS:

```bash
bash docs/cek-opencode.sh   # dari ~/zb/voice-gateway (path script disesuaikan)
```

Skrip memeriksa: proses, jalur API, auth Basic, IP bridge Docker, jangkauan dari
dalam container, dan upaya pembuatan sesi.

## Langkah berikutnya (DITUTUP)

Track opencode ditutup pada 24 Nov 2026: agent default pindah ke OMB. Tidak ada
langkah perbaikan adapter opencode. Pelajaran yang dipakai setelahnya:

1. Probe versi API dulu di node yang men-hosting agent (`docs/cek-opencode.sh`),
   jangan mengadaptasi dari ingatan atau versi mesin lain.
2. Anggap `405` = jalur ada tapi method/prefix salah; `401` + `www-authenticate:
   Basic` = skema Basic. Dua probe ini mencegah menulis ulang adapter berdasarkan
   rute yang ditebak.
3. Jangkauan container ke layanan host adalah fault terpisah dari auth — cek dari
   dalam container sebelum menyalahkan kredensial.
