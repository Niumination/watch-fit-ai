# Jalur C — langkah 3: HP kirim WAV, jam putar

Diperbarui: 24 Nov 2026

## Rantai yang dimaksud

```
HP: tekan "Jalur A" → rekam mic 8 dtk → POST /ask-audio
   ← WAV jawaban (~450 KB)
HP: WearEngineHelper.sendFileToWatch(wav, "jawab.wav")  [FileSendCallback]
   → P2P Wear Engine →
Jam: registerReceiver → data.isFileType / data.name = internal://app/jawab.wav
   → <audio id="answer"> play → speaker jam
```

## Yang sudah diubah di repo

| File | Perubahan |
|---|---|
| `phone-android/.../WearEngineHelper.kt` | `sendFileToWatch` kini memasang `FileSendCallback` sungguhan (dulu proxy no-op), mencatat OK/GAGAL/progress, dan ada parameter `onResult`. |
| `phone-android/.../MainActivity.kt` | Tombol Jalur A menampilkan "Kirim ke jam: OK / GAGAL". |
| `watch-lite/.../pages/index/index.js` | Deteksi file masuk (`isFileType`/`data.name`), `playAnswer(path)` dengan handler `onplay/onended/onerror`; daftar agent jadi `omb, opencode, gemini`. |
| `watch-lite/.../pages/index/index.hml` | Elemen `<audio id="answer" src="{{audioSrc}}">`. |
| `watch-lite/.../config.json` | Tambah `ohos.permission.MODIFY_AUDIO_SETTINGS`. |

Kontrak P2P diverifikasi dari contoh resmi Huawei
(`HMS-Core/hms-wear-engine-demo`, lite wearable):
receiver menerima `data.name = "internal://app/<file>"` untuk file, dan
`data.isFileType` menandai tipe.

## Yang WAJIB kamu lakukan (tidak bisa dari sini)

### 1. Build HAP pemutar

Prasyarat:
- **DevEco Studio 3.1** dengan SDK API 5/6 (legacy). DevEco 5.x/6.x menghasilkan
  HAP yang ditolak jam (`Error 40`).
- **Akun developer Huawei** + **debug certificate**, jam didaftarkan UDID-nya.
- **DevEco Assistant** di HP (dari AppGallery) untuk sideload.

Langkah:
1. DevEco Studio → New Project → **Lite Wearable** (Empty Feature Ability, JS).
2. Salin isi `watch-lite/src/main/` ke `entry/src/main/`.
3. Salin `watch-lite/build-profile.json5` ke root proyek.
4. Isi fingerprint app Android di dua tempat:
   - `watch-lite/src/main/js/default/pages/index/index.js` → `PHONE_CERT_FINGERPRINT`
   - `watch-lite/src/main/js/default/config.json` → `metaData.customizeData[].value`
     (`id.agentcall:<fingerprint>`).
   Fingerprint = SHA-256 sertifikat app Android
   (`keytool -list -v -keystore ... | grep SHA256`, ambil heksadesimal tanpa titik dua).
5. Build → `entry/build/default/outputs/default/entry-default-unsigned.hap`.

### 2. Pasang

- Debug-signed: buka DevEco Assistant di HP, pindai/pilih HAP,
  atau push lalu install dari `/sdcard/haps`.
- Catatan debug: HAP debug hanya berlaku terbatas; untuk pemakaian harian
  perlu rilis bertanda tangan penuh.

### 3. Uji berurutan (jangan loncat)

| # | Uji | Cara | Harapan |
|---|-----|------|---------|
| 1 | Jam & HP tersambung | Buka app AgentCall di HP, lalu app jam | Status jam "Siap", hint "Buka app AgentCall" hilang |
| 2 | Kirim perintah | Tekan "Bicara" di jam | HP mulai rekam |
| 3 | **Terima file** | Tekan Jalur A di HP | HP tampil "Kirim ke jam: OK"; jam berubah "Menerima jawaban…" |
| 4 | **Putar audio** | — | Jam bersuara membacakan jawaban |

Kalau langkah 3 OK tapi 4 tidak bersuara, lihat §Batasan.

## Batasan yang sudah diketahui (jujur)

Huawei mensyaratkan agar **bundle app dimasukkan ke "control list" layanan musik**
di wearable sebelum `@system.audio` boleh dipakai. Gejala kalau belum masuk:
`audio.play()` langsung memicu `onerror` (laporan nyata di WATCH FIT 4 Pro:
`onerror` dua kali, `getPlayState()` gagal kode 200). Cara mengajukan bundle name
untuk control list **belum terdokumentasi publik** — pertanyaan yang sama di forum
pengembang Huawei belum ada jawaban. Jadi:

- **UNCHECKED**: apakah `id.agentcall.watch` lolos control list di Fit 5.
- Kalau `onerror` muncul, itu batas platform, bukan bug kode. Dua jalur lanjut:
  1. tanya Huawei (AppGallery Connect / dukungan pengembang) cara mendaftar
     bundle ke music service control list;
  2. **jalur alternatif** — putar WAV lewat speaker HP. Kualitas sama, latensi
     lebih pendek, tapi bukan suara dari jam.

## Batasan lain

- `sendFileToWatch` **belum pernah diuji di perangkat** — helper ini refleksi penuh,
  jadi nama method (`getFileClient`, `sendFile`, callback) belum terbukti cocok
  dengan versi SDK Wear Engine yang terpasang. Kalau logcat menunjukkan
  `sendFileToWatch skipped: ...`, baca pesan `ClassNotFound`/`NoSuchMethod` itu
  dan kirim ke repo — itu petunjuk tepat untuk memperbaiki adapter.
- Ukuran file ~450 KB. Wear Engine P2P punya batas; bila gagal di ukuran ini,
  kompresi ke AMR/WAV mono 8 kHz bisa dicoba.
