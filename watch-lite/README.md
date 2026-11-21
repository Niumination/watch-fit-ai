# App lite untuk WATCH FIT 5 (opsional, Jalur C)

Fungsi app ini **hanya**: tombol "Bicara", pilih agent, tampilkan status + transkrip, getar.
**Bukan** tempat audio — jam tidak punya API mic/speaker untuk app pihak ketiga.
Suara selalu lewat HFP ke HP (lihat `docs/01-riset-dan-arsitektur.md §1.3–1.4`).

## Prasyarat (semua wajib)

| # | Hal | Catatan |
|---|---|---|
| 1 | Akun developer Huawei + **debug certificate** | gratis; perangkat harus didaftarkan UDID-nya |
| 2 | **DevEco Studio 3.1** + **SDK API 5/6 (legacy)** | DevEco 5.x/6.x membuat hap yang **ditolak** jam (`Error 40`) — laporan nyata pada GT3/GT5 |
| 3 | **DevEco Assistant** di HP Android | sumber: AppGallery; pasang hap dari `/sdcard/haps` |
| 4 | Huawei Health, jam sudah ter-pair | Health yang memegang koneksi BLE |
| 5 | **Wear Engine JS SDK for lite wearable** | taruh sebagai `src/main/js/default/common/wearengine.js` |

## Langkah build & install

```text
1. DevEco Studio → New Project → Lite Wearable (Empty Feature Ability, JS)
2. Salin halaman ini ke: entry/src/main/js/default/pages/index/
3. Salin config.json      ke: entry/src/main/js/default/config.json
   (apiVersion.compatible = 5, target = 6 — turunkan ke 4/5 kalau jam menolak)
4. File → Project Structure → Signing Configs → pakai .p12 + .cer + .p7b debug-mu
5. Build → Build Hap(s) → hasil: entry-signed.hap  (harus < 10 MB)
6. Copy ke HP: /sdcard/haps/
7. DevEco Assistant → Apps → pilih hap → Install
8. Ikon app muncul di daftar aplikasi jam
```

Kalau install gagal, pesan error-nya yang menentukan langkah berikutnya:

| Error | Arti | Tindakan |
|---|---|---|
| `40 Invalid configuration file format` | API level tidak cocok | turunkan `apiVersion` (6→5→4) & pakai DevEco 3.1 |
| `47 Invalid value entered for app.apiVersion` | versi API di luar dukungan jam | sama seperti di atas |
| `10 Internal error` | fitur JS di luar kemampuan lite | hapus fitur/babel modern; ES5 murni |
| tidak muncul di DevEco Assistant | jam tidak terhubung Health | buka Huawei Health, pastikan ter-pair |

## Menyambung ke HP (Wear Engine P2P)

1. Di app Android, `p2pClient.setPeerPkgName("id.agentcall.watch")` + fingerprint sertifikat **app jam**.
2. Di app jam, `setPeerPkgName("id.agentcall")` + `PHONE_CERT_FINGERPRINT` (SHA-256 sertifikat app Android).
3. Kontrak pesan (JSON, ≤1 KB — kalau lebih besar, pakai file transfer):

| Arah | Pesan |
|---|---|
| jam → HP | `{"cmd":"talk","agent":"opencode"}` |
| jam → HP | `{"cmd":"agent","agent":"deepseek-harness"}` |
| jam → HP | `{"cmd":"end"}` |
| HP → jam | `{"t":"state","v":"listening\|thinking\|speaking"}` |
| HP → jam | `{"t":"final","text":"jawaban ringkas"}` |
| HP → jam | `{"t":"level","value":1234}` |

## Batasan runtime yang harus dihormati

- **ES5 murni**: tanpa `let/const`, arrow function, template literal, `Promise`, `class`.
- **Tanpa back-stack**: `router.replace` saja; tombol "kembali" harus kamu sediakan sendiri.
- **Halaman bisa mati kapan saja** → render ulang state di `onInit` (jangan simpan state penting di memori saja; pakai `@system.storage`).
- **≤ 48 KB per halaman**, `.hap` ≤ 10 MB, aset gambar `.jpg` 480×408.
- **Tanpa background**: app berhenti saat layar mati → jangan andalkan app ini untuk menahan sesi; sesi dipimpin HP.

## Kalau gagal (rencana B, tanpa app jam)

Pakai HP sebagai remote: notifikasi dengan aksi **Bicara / Ganti agent / Tutup**, plus
**Quick Settings tile** dan **home-screen widget**. Pengalaman turun sedikit (harus menyentuh
HP untuk memulai), tetapi audio tetap dari jam — dan jam tetap menampilkan layar panggilan
karena sesi berjalan sebagai panggilan Telecom.
