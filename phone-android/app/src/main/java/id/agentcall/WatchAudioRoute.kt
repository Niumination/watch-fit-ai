package id.agentcall

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.os.Build
import kotlin.math.abs

/**
 * Satu-satunya tugas kelas ini: membuat jalur audio HP <-> jam benar.
 *
 * Aturan yang tidak boleh dilanggar (kalau dilanggar, Android merekam dari mic HP,
 * bukan mic jam):
 *   - AudioManager.mode = MODE_IN_COMMUNICATION
 *   - routing lewat setCommunicationDevice(TYPE_BLUETOOTH_SCO)  [API 31+]
 *     atau startBluetoothSco() + setBluetoothScoOn(true)          [< API 31]
 *   - AudioRecord dengan sumber VOICE_COMMUNICATION
 *   - AudioTrack dengan USAGE_VOICE_COMMUNICATION / STREAM_VOICE_CALL, mono
 */
class WatchAudioRoute(private val ctx: Context) {

    private val am = ctx.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    var sampleRate: Int = 16_000
        private set

    fun open(): Boolean {
        am.mode = AudioManager.MODE_IN_COMMUNICATION

        repeat(3) { attempt ->
            if (tryOpenOnce()) {
                // HFP wideband (mSBC) -> 16 kHz; narrowband (CVSD) -> tetap 8 kHz yang valid.
                sampleRate = if (isWidebandSco()) 16_000 else 8_000
                // Beri waktu radio untuk sinkron sebelum capture dibuka.
                Thread.sleep(150)
                return true
            }
            Log.w(TAG, "SCO attempt ${attempt + 1} gagal — retry 1 dtk (jam butuh call context)")
            Thread.sleep(1000)
        }
        return false
    }

    private fun tryOpenOnce(): Boolean {
        if (Build.VERSION.SDK_INT >= 31) {
            val sco = am.availableCommunicationDevices.firstOrNull {
                it.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
            } ?: return false                      // jam tidak ter-pair sebagai "Bluetooth calling"
            val ok = am.setCommunicationDevice(sco)
            if (!ok) return false
        } else {
            @Suppress("DEPRECATION")
            am.startBluetoothSco()
            @Suppress("DEPRECATION")
            am.isBluetoothScoOn = true
            // tunggu ACTION_SCO_AUDIO_STATE_UPDATED == CONNECTED di production;
            // di sini kita beri jeda konservatif supaya AudioRecord tidak membuka mic HP.
            Thread.sleep(300)
            return true
        }

        // HFP wideband (mSBC) -> 16 kHz; narrowband (CVSD) -> tetap 8 kHz yang valid.
        return true
    }

    fun close() {
        if (Build.VERSION.SDK_INT >= 31) {
            am.clearCommunicationDevice()
        } else {
            @Suppress("DEPRECATION")
            runCatching { am.stopBluetoothSco() }
            @Suppress("DEPRECATION")
            am.isBluetoothScoOn = false
        }
        am.mode = AudioManager.MODE_NORMAL
    }

    /**
     * Tidak ada API resmi untuk membaca lebar pita SCO, jadi kita pakai heuristik:
     * kalau komunikasi device melaporkan sample rate >= 16000 kita anggap wideband.
     * Verifikasi manual: `adb shell dumpsys bluetooth_manager | grep -i msbc`
     */
    @SuppressLint("NewApi")
    private fun isWidebandSco(): Boolean {
        if (Build.VERSION.SDK_INT < 31) return false
        val dev = am.communicationDevice ?: return false
        return dev.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO && dev.sampleRates.any { it >= 16_000 }
    }
}

/**
 * Capture + playout. Dijalankan di dua thread terpisah; frame 20 ms.
 * onFrame(PCM16 mono) dipakai untuk streaming ke gateway.
 */
class AudioIo(
    private val route: WatchAudioRoute,
    private val onFrame: (ShortArray, Int) -> Unit,
    private val onLevel: (Int) -> Unit = {},
) {
    private val rate = route.sampleRate
    private val frame = rate / 50                     // 20 ms
    @Volatile private var running = false
    private var rec: AudioRecord? = null
    private var track: AudioTrack? = null

    fun startInput() {
        val minBuf = AudioRecord.getMinBufferSize(
            rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
        )
        rec = AudioRecord(
            MediaRecorder.AudioSource.VOICE_COMMUNICATION,   // <- wajib, jangan MIC
            rate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            maxOf(minBuf, frame * 2 * 4)
        )
        running = true
        rec?.startRecording()
        Thread({
            val buf = ShortArray(frame)
            while (running) {
                val n = rec?.read(buf, 0, frame) ?: -1
                if (n > 0) {
                    onLevel(peak(buf, n))
                    onFrame(buf, n)
                }
            }
        }, "AgentCall-mic").start()
    }

    fun startOutput() {
        val minBuf = AudioTrack.getMinBufferSize(
            rate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT
        )
        track = AudioTrack.Builder()
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
            .setBufferSizeInBytes(maxOf(minBuf, frame * 2 * 6))
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
            .also { it.play() }
    }

    fun write(pcm: ShortArray, len: Int) {
        track?.write(pcm, 0, len)
    }

    /** 0 = hening. Dipakai untuk VAD lokal / indikator "Mendengar…" di jam. */
    private fun peak(b: ShortArray, n: Int): Int {
        var p = 0
        for (i in 0 until n) { val v = abs(b[i].toInt()); if (v > p) p = v }
        return p
    }

    fun stop() {
        running = false
        runCatching { rec?.stop(); rec?.release() }
        runCatching { track?.stop(); track?.release() }
        rec = null; track = null
    }
}
