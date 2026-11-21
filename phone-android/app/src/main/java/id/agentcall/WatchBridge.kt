package id.agentcall

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import android.util.Log

/**
 * Jembatan ke jam untuk teks/status.
 *
 * Dua lapis:
 *  1) SELALU: notifikasi (muncul di jam sebagai notifikasi; berguna sebagai fallback)
 *  2) OPSIONAL: Wear Engine P2P ke app lite (butuh HMS Core + app lite terpasang)
 *
 * Catatan: audio TIDAK lewat sini — audio lewat HFP/SCO di VoiceSessionManager.
 */
object WatchBridge {
    private const val TAG = "WatchBridge"
    private const val CH = "agentcall"
    private const val ID = 1001

    private fun nm(ctx: Context) = ctx.getSystemService(NotificationManager::class.java)

    private fun channel(ctx: Context) {
        if (Build.VERSION.SDK_INT >= 26) {
            nm(ctx).createNotificationChannel(
                NotificationChannel(CH, "AgentCall", NotificationManager.IMPORTANCE_LOW)
            )
        }
    }

    fun pushTranscript(ctx: Context, text: String) {
        channel(ctx)
        val n = android.app.Notification.Builder(ctx, CH)
            .setContentTitle("Agent")
            .setContentText(text.take(120))
            .setStyle(android.app.Notification.BigTextStyle().bigText(text))
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(false)
            .build()
        nm(ctx).notify(ID, n)
        Log.i(TAG, "transcript: $text")
        // Jalur C (app lite di jam): kirim transkrip ke UI jam via P2P
        WearEngineHelper.sendToWatch(ctx, """{"t":"final","text":${org.json.JSONObject.quote(text)}}""")
    }

    fun pushState(ctx: Context, state: String) {
        Log.i(TAG, "state: $state")
        // Jalur C (app lite di jam): update status lingkaran animasi / VU meter
        WearEngineHelper.sendToWatch(ctx, """{"t":"state","v":"$state"}""")
    }
}
