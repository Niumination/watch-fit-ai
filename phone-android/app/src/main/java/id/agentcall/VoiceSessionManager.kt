package id.agentcall

import android.content.Context
import android.os.Bundle
import android.util.Log
import okhttp3.*
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.TimeUnit

/**
 * Menyatukan: Telecom connection <-> AudioRouter(SCO) <-> WebSocket ke gateway.
 *
 * Kontrak wire (lihat gateway/app/protocol.md):
 *   HP -> GW : binary frame = PCM16LE mono @ rate (8k/16k) — 20 ms per frame
 *              text frame   = {"t":"hello","agent":"opencode","rate":16000,"device":"..."}
 *                              {"t":"end"}  {"t":"mute","on":true}
 *   GW -> HP : binary frame = PCM16LE mono @ rate — diputar ke speaker jam
 *              text frame   = {"t":"partial","text":"..."}   (transkrip sementara)
 *                              {"t":"final","text":"..."}     (untuk ditampilkan/diteruskan ke jam)
 *                              {"t":"state","v":"thinking|speaking|listening"}
 *                              {"t":"error","msg":"..."}
 */
object VoiceSessionManager {

    private const val TAG = "AgentCall"
    private lateinit var appCtx: Context
    private var ws: WebSocket? = null
    private var route: WatchAudioRoute? = null
    private var io: AudioIo? = null
    private var conn: AgentCallConnection? = null
    private var muted = false

    private val http: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .pingInterval(15, TimeUnit.SECONDS)
            .build()
    }

    fun init(ctx: Context) { appCtx = ctx.applicationContext }

    fun start(connection: AgentCallConnection, extras: Bundle?) {
        conn = connection
        val agent = extras?.getString("agent") ?: Config.defaultAgent
        val gateway = extras?.getString("gateway") ?: Config.gatewayUrl   // wss://voice.domainmu.com/ws

        route = WatchAudioRoute(appCtx)
        if (!route!!.open()) {
            Log.e(TAG, "SCO tidak tersedia — jam tidak ter-pair sebagai Bluetooth calling")
            connection.setDisconnected(android.telecom.DisconnectCause(android.telecom.DisconnectCause.ERROR))
            return
        }

        val rate = route!!.sampleRate
        io = AudioIo(
            route!!,
            onFrame = { buf, n -> if (!muted) ws?.send(buf.toLittleEndian(n)) },
            onLevel = { level -> // kirim VAD ringan/local level untuk indikator UI bila perlu
                if (level > 3000) ws?.send("""{"t":"voice","level":$level}""")
            }
        )

        ws = http.newWebSocket(
            Request.Builder()
                .url(gateway)
                .header("Authorization", "Bearer ${TokenStore.accessToken(appCtx)}")
                .build(),
            object : WebSocketListener() {
                override fun onOpen(w: WebSocket, response: Response) {
                    w.send("""{"t":"hello","agent":"$agent","rate":$rate,"device":"${Config.deviceId(appCtx)}"}""")
                    io?.startOutput()
                    io?.startInput()
                    conn?.setActive()
                }

                override fun onMessage(w: WebSocket, text: String) = onControl(text)

                override fun onMessage(w: WebSocket, bytes: ByteString) {
                    val shorts = shortsFrom(bytes.toByteArray())
                    io?.write(shorts, shorts.size)
                }

                override fun onFailure(w: WebSocket, t: Throwable, r: Response?) {
                    Log.e(TAG, "WS failure: ${t.message}", t)
                    hangUp()
                }
            }
        )
    }

    fun answer() { /* audio sudah jalan saat onOpen; hook untuk mode incoming */ }

    fun setMuted(m: Boolean) { muted = m; ws?.send("""{"t":"mute","on":$m}""") }

    fun hangUp() {
        runCatching { ws?.send("""{"t":"end"}"""); ws?.close(1000, "bye") }
        io?.stop(); route?.close()
        ws = null; io = null; route = null
    }

    private fun onControl(text: String) {
        val o = runCatching { JSONObject(text) }.getOrNull() ?: return
        when (o.optString("t")) {
            "final" -> WatchBridge.pushTranscript(appCtx, o.optString("text"))
            "state" -> WatchBridge.pushState(appCtx, o.optString("v"))
            "error" -> Log.w(TAG, "gateway: ${o.optString("msg")}")
        }
    }

    private fun ShortArray.toLittleEndian(n: Int): ByteString {
        val bb = ByteBuffer.allocate(n * 2).order(ByteOrder.LITTLE_ENDIAN)
        for (i in 0 until n) bb.putShort(this[i])
        return bb.array().toByteString()
    }

    private fun shortsFrom(b: ByteArray): ShortArray {
        val bb = ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN)
        val out = ShortArray(b.size / 2)
        for (i in out.indices) out[i] = bb.short
        return out
    }
}

/** Tempat mendaftarkan PhoneAccount self-managed, dipanggil sekali di Application.onCreate. */
object AgentCallApp {
    fun registerPhoneAccount(ctx: Context) {
        // Lihat README: gunakan TelecomManager.registerPhoneAccount() dengan
        // PhoneAccount.builder(handle, "AI Agent")
        //   .setCapabilities(CAPABILITY_SELF_MANAGED)
        //   .setSupportedUriSchemes(listOf("tel"))
        //   .build()
        // lalu bungkus dalam Intent ACTION_CHANGE_PHONE_ACCOUNTS agar user mengaktifkannya.
    }
}
