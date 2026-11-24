package id.agentcall

import android.content.Context
import java.util.UUID

object Config {
    /** Ganti ke domainmu. WebSocket wajib wss:// (TLS). */
    const val gatewayUrl: String = "wss://voice.abstract.biz.id/ws"

    /** Dipakai kalau user belum memilih agent. */
    const val defaultAgent: String = "echo"

    /** ID perangkat stabil, dipakai untuk auth & kuota.
     *
     * Stabil lintas install: turunan dari ANDROID_ID (bukan UUID acak), supaya
     * reinstall APK debug tidak membuat device jadi "tidak dikenal" di gateway.
     */
    fun deviceId(ctx: Context): String {
        val sp = ctx.getSharedPreferences("agentcall", Context.MODE_PRIVATE)
        var id = sp.getString("device_id", null)
        if (id == null) {
            val aid = try {
                android.provider.Settings.Secure.getString(
                    ctx.contentResolver, android.provider.Settings.Secure.ANDROID_ID)
            } catch (e: Exception) {
                null
            }
            id = if (!aid.isNullOrBlank()) {
                "and-" + aid.take(8)
            } else {
                "and-" + UUID.randomUUID().toString().take(8)
            }
            sp.edit().putString("device_id", id).apply()
        }
        return id
    }
}
