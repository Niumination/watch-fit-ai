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
        // TODO (Jalur C): WearEngineHelper.sendMessageToWatch("""{"t":"final","text":"..."}""")
    }

    fun pushState(ctx: Context, state: String) {
        Log.i(TAG, "state: $state")
        // TODO (Jalur C): kirim {"t":"state","v":"..."} via Wear Engine P2P
    }
}
