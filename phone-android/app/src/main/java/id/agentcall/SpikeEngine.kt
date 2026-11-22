package id.agentcall

import android.Manifest
import android.app.Activity
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothHeadset
import android.bluetooth.BluetoothProfile
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.net.Uri
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.telecom.PhoneAccount
import android.telecom.TelecomManager
import androidx.core.content.ContextCompat
import java.util.Locale
import kotlin.math.abs
import kotlin.math.max

/**
 * Logika spike. Semua hasil ditulis ke log UI supaya bisa dicopy ke
 * docs/03-panduan-fase0.md (tabel hasil).
 */
class SpikeEngine(
    private val act: Activity,
    private val log: (String) -> Unit,
) {
    private val am = act.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val telecom = act.getSystemService(Context.TELECOM_SERVICE) as TelecomManager
    private var route: WatchAudioRoute? = null
    private var tts: TextToSpeech? = null

    // ---------------------------------------------------------------- S1
    fun checkPermissions() {
        val need = mutableListOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.MODIFY_AUDIO_SETTINGS,
            Manifest.permission.MANAGE_OWN_CALLS,
        )
        if (android.os.Build.VERSION.SDK_INT >= 31) need += Manifest.permission.BLUETOOTH_CONNECT
        val missing = need.filter {
            ContextCompat.checkSelfPermission(act, it) != PackageManager.PERMISSION_GRANTED
        }
        result("S1", missing.isEmpty(), "izin kurang: $missing")
    }

    // ---------------------------------------------------------------- S2
    fun checkHeadset() {
        val adapter = BluetoothAdapter.getDefaultAdapter()
        if (adapter == null || !adapter.isEnabled) {
            result("S2", false, "Bluetooth mati / tidak ada adapter")
            return
        }
        adapter.getProfileProxy(act, object : BluetoothProfile.ServiceListener {
            override fun onServiceConnected(profile: Int, proxy: BluetoothProfile) {
                if (profile != BluetoothProfile.HEADSET) return
                val hs = proxy as BluetoothHeadset
                val devices = hs.connectedDevices
                val names = devices.joinToString { "${it.name} [${it.address}]" }
                val scoOk = runCatching { hs.isAudioConnected(devices.firstOrNull()) }.getOrDefault(false)
                result(
                    "S2", devices.isNotEmpty(),
                    "headset HFP: $names · audioConnected=$scoOk"
                )
                if (devices.isEmpty()) {
                    log("   ⚠ Pastikan jam ter-pair sebagai \"Bluetooth calling\" di Huawei Health,")
                    log("     dan muncul di Settings > Bluetooth sebagai headset (bukan cuma BLE).")
                }
                adapter.closeProfileProxy(profile, proxy)
            }

            override fun onServiceDisconnected(profile: Int) {}
        }, BluetoothProfile.HEADSET)
    }

    // ---------------------------------------------------------------- S3
    fun registerPhoneAccount() {
        val handle = phoneAccountHandle(act)
        val account = PhoneAccount.builder(handle, "AI Agent (AgentCall)")
            .setCapabilities(PhoneAccount.CAPABILITY_SELF_MANAGED)
            .setSupportedUriSchemes(listOf("tel"))
            .setShortDescription("Sesi suara dengan AI agent")
            .build()
        runCatching { telecom.registerPhoneAccount(account) }
            .onSuccess { log("S3 · PhoneAccount didaftarkan. Aktifkan di pengaturan akun panggilan.") }
            .onFailure { log("S3 · FAIL registerPhoneAccount: ${it.message}") }
        val enabled = runCatching { telecom.getPhoneAccount(handle)?.isEnabled }.getOrNull() == true
        result("S3", enabled, "terdaftar, enabled=$enabled (kalau false: buka pengaturan akun panggilan)")
    }

    // ---------------------------------------------------------------- S4
    fun placeSelfManagedCall() {
        val extras = Bundle().apply {
            putParcelable(TelecomManager.EXTRA_PHONE_ACCOUNT_HANDLE, phoneAccountHandle(act))
            putString("agent", "echo")
            putString("gateway", Config.gatewayUrl)
        }
        runCatching {
            telecom.placeCall(Uri.fromParts("tel", "agent", null), extras)
        }.onSuccess {
            log("S4 · placeCall() dipanggil — LIHAT JAM: harus muncul layar panggilan.")
            log("     Kalau tidak muncul: PhoneAccount belum diaktifkan user (Settings > Calls).")
        }.onFailure {
            result("S4", false, "placeCall gagal: ${it.message}")
        }
    }

    // ---------------------------------------------------------------- S5
    fun checkRoute() {
        route = WatchAudioRoute(act)
        val ok = route!!.open()
        result("S5", ok, "SCO open=$ok · sampleRate=${route!!.sampleRate} " +
                "(16000 = wideband/mSBC, 8000 = narrowband/CVSD) · mode=${am.mode}")
        if (!ok) {
            log("   ⚠ setCommunicationDevice(TYPE_BLUETOOTH_SCO) gagal:")
            log("     - jam tidak terhubung HFP, atau")
            log("     - sedang ada panggilan telepon aktif (SCO dipakai sistem).")
        }
    }

    // ---------------------------------------------------------------- S6
    fun speakTestPhrase() {
        val phrase = "Halo, ini tes dari AgentCall. Kalau kamu mendengar suara ini di jam, " +
                "jalur speaker sudah benar."
        tts = TextToSpeech(act) { status ->
            if (status != TextToSpeech.SUCCESS) {
                result("S6", false, "TTS init gagal")
                return@TextToSpeech
            }
            tts?.language = Locale("id", "ID")
            tts?.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            val params = Bundle().apply {
                // stream voice call supaya ikut jalur SCO, bukan speaker HP
                putInt(TextToSpeech.Engine.KEY_PARAM_STREAM, AudioManager.STREAM_VOICE_CALL)
            }
            log("S6 · memutar frasa uji… (dengarkan di jam)")
            tts?.speak(phrase, TextToSpeech.QUEUE_FLUSH, params, "spike-s6")
        }
    }

    // ---------------------------------------------------------------- S7
    fun recordFromWatch(ms: Int) {
        Thread(Runnable {
            val rate = route?.sampleRate ?: 16_000
            val frame = rate / 10                                  // 100 ms
            val minBuf = AudioRecord.getMinBufferSize(
                rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
            )
            val rec = AudioRecord(
                MediaRecorder.AudioSource.VOICE_COMMUNICATION,     // WAJIB, bukan MIC
                rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
                max(minBuf, frame * 4)
            )
            if (rec.state != AudioRecord.STATE_INITIALIZED) {
                result("S7", false, "AudioRecord tidak bisa init (rate=$rate)")
                return@Runnable
            }
            val total = ShortArray(rate * ms / 1000)
            var offset = 0
            var peakAll = 0
            log("S7 · merekam ${ms / 1000} s pada ${rate} Hz — TUTUP MIC JAM DENGAN JARI di tengah rekaman")
            rec.startRecording()
            while (offset < total.size) {
                val n = rec.read(total, offset, minOf(frame, total.size - offset))
                if (n <= 0) break
                var p = 0
                for (i in offset until offset + n) p = max(p, abs(total[i].toInt()))
                peakAll = max(peakAll, p)
                offset += n
            }
            rec.stop(); rec.release()

            val audible = peakAll > 500
            result("S7", audible, "peak=$peakAll (butuh >500) — kalau anda menutup mic jam " +
                    "dan peak TIDAK turun, berarti audio masih dari mic HP")

            // putar ulang lewat jalur SCO supaya terdengar di jam
            val track = AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .setAudioFormat(
                    AudioFormat.Builder()
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setSampleRate(rate)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .build()
                )
                .setTransferMode(AudioTrack.MODE_STREAM)
                .build()
            track.play()
            track.write(total, 0, offset)
            track.stop(); track.release()
            log("S7 · pemutaran ulang selesai (seharusnya terdengar di jam).")
        }).start()
    }

    // ---------------------------------------------------------------- all
    fun runAll() {
        log("===== SPIKE DIMULAI =====")
        checkPermissions()
        checkHeadset()
        registerPhoneAccount()
        checkRoute()
        speakTestPhrase()
        log("→ Setelah ini: tekan tombol S4 (panggilan) lalu S7 (rekam & putar).")
        log("→ Salin log ini ke tabel hasil di docs/03-panduan-fase0.md")
    }

    private fun result(id: String, pass: Boolean, detail: String) {
        log("[$id] ${if (pass) "PASS" else "FAIL"} — $detail")
    }

    fun release() {
        route?.close()
        tts?.shutdown()
        tts = null
    }
}
