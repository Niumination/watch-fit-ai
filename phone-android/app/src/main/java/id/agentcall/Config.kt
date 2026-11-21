package id.agentcall

import android.content.Context
import java.util.UUID

object Config {
    /** Ganti ke domainmu. WebSocket wajib wss:// (TLS). */
    const val gatewayUrl: String = "wss://voice.domainmu.com/ws"

    /** Dipakai kalau user belum memilih agent. */
    const val defaultAgent: String = "echo"

    /** ID perangkat stabil, dipakai untuk auth & kuota. */
    fun deviceId(ctx: Context): String {
        val sp = ctx.getSharedPreferences("agentcall", Context.MODE_PRIVATE)
        var id = sp.getString("device_id", null)
        if (id == null) {
            id = "and-" + UUID.randomUUID().toString().take(8)
            sp.edit().putString("device_id", id).apply()
        }
        return id
    }
}
