package id.agentcall

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.PowerManager

/**
 * Foreground service bertipe microphone|phoneCall.
 *
 * WAJIB: di Android 11+ mic akan kosong kalau app tidak benar-benar foreground.
 * Service ini juga memegang wake lock supaya sesi tidak terputus saat layar mati.
 */
class CallForegroundService : Service() {

    private var wake: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val ch = "agentcall-call"
        if (Build.VERSION.SDK_INT >= 26) {
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
                .createNotificationChannel(
                    NotificationChannel(ch, "Sesi AI", NotificationManager.IMPORTANCE_LOW)
                )
        }
        val n: Notification = android.app.Notification.Builder(this, ch)
            .setContentTitle("Sesi AI aktif")
            .setContentText("Bicara dari jam…")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .build()

        if (Build.VERSION.SDK_INT >= 29) {
            // API 34+: tipe wajib dideklarasikan saat startForeground
            startForeground(NOTIF_ID, n, android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
                    or android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_PHONE_CALL)
        } else {
            startForeground(NOTIF_ID, n)
        }

        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wake = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "AgentCall:session").apply {
            setReferenceCounted(false)
            acquire(30 * 60 * 1000L)
        }

        VoiceSessionManager.init(applicationContext)
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        wake?.let { if (it.isHeld) it.release() }
        super.onDestroy()
    }

    companion object {
        private const val NOTIF_ID = 42
        fun start(ctx: Context) {
            val i = Intent(ctx, CallForegroundService::class.java)
            if (Build.VERSION.SDK_INT >= 26) ctx.startForegroundService(i) else ctx.startService(i)
        }
    }
}
