package id.agentcall

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import android.util.Log
import java.io.File
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody

/**
 * Jalur A: mic HP -> gateway /ask-audio -> file jawaban -> P2P ke jam.
 *
 * Dipicu dari app jam ({cmd:ask}) atau tombol di HP. Merekam N detik dari
 * mic HP (bukan SCO — HFP mati di perangkat ini), mengirim WAV ke gateway,
 * menerima WAV jawaban, meneruskannya ke jam via Wear Engine file transfer.
 */
object WatchVoiceRelay {

    private const val TAG = "WatchVoiceRelay"

    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    /**
     * Rekam [secs] detik dari mic HP ke WAV 16 kHz mono, kirim ke gateway,
     * kembalikan Pair(wavJawaban, transkripMasuk).
     */
    suspend fun askOnce(
        ctx: Context,
        secs: Int = 8,
        agent: String = Config.defaultAgent,
    ): Pair<ByteArray, String> = withContext(Dispatchers.IO) {
        val wavIn = recordMic(ctx, secs)
        val device = Config.deviceId(ctx)
        val secret = TokenStore.getDeviceSecret(ctx)
        if (secret.isBlank()) throw IllegalStateException("device secret kosong — isi di TokenStore dulu")

        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("device", device)
            .addFormDataPart("token", secret)
            .addFormDataPart("agent", agent)
            .addFormDataPart(
                "audio", out.name,
                wavIn.asRequestBody("audio/mp4".toMediaType()))
            .build()
        val req = Request.Builder()
            .url(Config.gatewayUrl.replaceFirst("wss://", "https://").replaceFirst("/ws", "/ask-audio"))
            .post(body)
            .build()
        val resp = http.newCall(req).execute()
        Log.i(TAG, "askOnce: POST ${req.url} -> ${resp.code}")
        resp.use {
            if (!it.isSuccessful) throw IllegalStateException("gateway ${it.code}: ${it.body?.string()?.take(200)}")
            val out = it.body?.bytes() ?: byteArrayOf()
            val transcriptIn = it.header("X-Transcript-In").orEmpty()
            val transcriptOut = it.header("X-Transcript-Out").orEmpty()
            WatchBridge.pushTranscript(ctx, transcriptOut.ifBlank { "(jawaban suara tanpa teks)" })
            Log.i(TAG, "askOnce ok: in='${transcriptIn.take(80)}' wav=${out.size}B")
            out to transcriptIn
        }
    }

    private suspend fun recordMic(ctx: Context, secs: Int): File = withContext(Dispatchers.IO) {
        val out = File(ctx.cacheDir, "tanya_${System.currentTimeMillis()}.wav")
        val rec = if (Build.VERSION.SDK_INT >= 31) {
            MediaRecorder(ctx)
        } else {
            @Suppress("DEPRECATION") MediaRecorder()
        }
        rec.apply {
            setAudioSource(MediaRecorder.AudioSource.MIC)
            setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            setAudioSamplingRate(16_000)
            setAudioChannels(1)
            setOutputFile(out.absolutePath)
            prepare()
            start()
        }
        try {
            kotlinx.coroutines.delay(secs * 1000L)
        } finally {
            runCatching { rec.stop() }
            runCatching { rec.release() }
        }
        out
    }
}
