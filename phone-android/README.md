# App Android "AgentCall" — jembatan audio jam ⇄ gateway

Tujuan app ini: menjadikan sesi AI sebagai **panggilan** sehingga jam menampilkan layar panggilan
native, dan mengalirkan audio jam (SCO) ke gateway VPS.

## Yang harus dibaca dulu
`docs/01-riset-dan-arsitektur.md` bagian 3 & 7. Tiga hal yang paling sering bikin gagal:

1. **Pairing**: jam harus ter-pair sebagai *Bluetooth calling* di Huawei Health **dan** muncul
   di daftar Bluetooth HP sebagai headset. Cek: `adb shell dumpsys bluetooth_manager | grep -i hfp`
2. **Route**: `MODE_IN_COMMUNICATION` + `VOICE_COMMUNICATION` (bukan `MIC`) + `setCommunicationDevice(TYPE_BLUETOOTH_SCO)`.
3. **Foreground service**: mulai saat app masih terlihat, tipe `microphone|phoneCall`, plus wake lock.
   Android 11+ akan memberi mic kosong kalau app tidak benar foreground.

## Struktur

```
app/src/main/java/id/agentcall/
├── WatchAudioRoute.kt          SCO routing + AudioRecord/AudioTrack (VOICE_COMMUNICATION)
├── AgentCallConnectionService.kt  Telecom self-managed call -> layar panggilan di jam
└── VoiceSessionManager.kt      WS transport + orkestrasi sesi
```

## AndroidManifest (potongan penting)

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
<uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS"/>
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT"/>     <!-- API 31+ runtime -->
<uses-permission android:name="android.permission.MANAGE_OWN_CALLS"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_MICROPHONE"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_PHONE_CALL"/>
<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
<uses-permission android:name="android.permission.WAKE_LOCK"/>
<uses-permission android:name="android.permission.INTERNET"/>

<application ...>
  <service
      android:name=".AgentCallConnectionService"
      android:permission="android.permission.BIND_TELECOM_CONNECTION_SERVICE"
      android:exported="true">
    <intent-filter>
      <action android:name="android.telecom.ConnectionService"/>
    </intent-filter>
  </service>

  <service
      android:name=".CallForegroundService"
      android:foregroundServiceType="microphone|phoneCall"
      android:exported="false"/>
</application>
```

## Gradle (dependencies)

```kotlin
implementation("com.squareup.okhttp3:okhttp:4.12.0")
implementation("androidx.core:core-ktx:1.13.1")
// opsional, untuk kompresi bandwidth:
implementation("io.github.livekit:webrtc-audio-processing:0.0.1") // atau bangun libwebrtc-audio-processing sendiri
```

## Alur start sesi

```kotlin
// 1) User menekan tombol/QS tile/notifikasi (bukan dari service di background)
val extras = Bundle().apply {
    putString("agent", "opencode")
    putString("gateway", "wss://voice.domainmu.com/ws")
}
val uri = Uri.fromParts("tel", "agent", null)
telecomManager.placeCall(uri, extras)   // -> onCreateOutgoingConnection -> jam menampilkan call
```

Untuk mode di mana **jam yang berdering** (mis. agent melaporkan tugas selesai dan ingin
menyampaikan hasil): pakai `telecomManager.addNewIncomingCall(handle, extras)` dengan
`PROPERTY_SELF_MANAGED` (butuh izin `MANAGE_OWN_CALLS` + cek `isIncomingCallPermitted` pada API 28+).

## Metrik yang harus kamu ukur di HP ini

| Metrik | Cara | Target |
|---|---|---|
| Mic benar dari jam | tutup mic jam dengan jari → `onLevel` harus turun drastis | turun >80% |
| Sample rate SCO | `adb shell dumpsys audio \| grep -i sco` | 16000 (mSBC) ideal |
| Waktu SCO siap | log waktu `open()` → frame pertama | < 800 ms |
| Latensi TTS dipantulkan | log kirim frame ↔ frame pertama masuk | < 800 ms |
| Dropout | hitung frame hilang per menit | < 1% |
