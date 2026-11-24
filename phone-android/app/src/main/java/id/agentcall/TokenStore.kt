package id.agentcall

import android.content.Context
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

/**
 * Token sesi pendek (15 menit) dari gateway: GET /rtc/token?device=..&token=<device_secret>
 *
 * Untuk SPIKE, device_secret boleh disimpan di SharedPreferences (isi manual).
 * Produksi: simpan di EncryptedSharedPreferences / Keystore, dan sediakan refresh.
 */
object TokenStore {

    private fun prefs(ctx: Context) = ctx.getSharedPreferences("agentcall", Context.MODE_PRIVATE)

    fun setDeviceSecret(ctx: Context, secret: String) =
        prefs(ctx).edit().putString("device_secret", secret).apply()

    fun getDeviceSecret(ctx: Context): String =
        prefs(ctx).getString("device_secret", "") ?: ""

    @Volatile private var cached: String? = null
    @Volatile private var expiresAt: Long = 0

    fun accessToken(ctx: Context): String {
        val now = System.currentTimeMillis() / 1000
        if (cached != null && now < expiresAt - 60) return cached!!

        val secret = prefs(ctx).getString("device_secret", "") ?: ""
        val device = Config.deviceId(ctx)
        val base = Config.gatewayUrl
            .replace("wss://", "https://")
            .replace("/ws", "")
        val url = URL("$base/rtc/token?device=$device&token=$secret")
        val conn = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 8000
            readTimeout = 8000
        }
        return try {
            conn.inputStream.bufferedReader().use { it.readText() }.let { body ->
                val o = JSONObject(body)
                cached = o.getString("token")
                expiresAt = now + o.optInt("ttl", 900)
                cached!!
            }
        } catch (e: Exception) {
            // Jangan crash: biarkan koneksi gagal dan tampilkan di log.
            ""
        } finally {
            conn.disconnect()
        }
    }

    fun clear() { cached = null; expiresAt = 0 }
}
