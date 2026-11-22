package id.agentcall

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import android.telecom.PhoneAccountHandle
import android.telecom.TelecomManager
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.core.content.ContextCompat

/**
 * SPIKE Phase 0 — "apakah jam bisa dipakai sebagai mic+speaker untuk sesi AI?"
 *
 * Tujuh langkah, masing-masing menghasilkan PASS/FAIL yang bisa dicatat:
 *   S1  izin runtime lengkap
 *   S2  jam terdeteksi sebagai headset (HFP) via BluetoothAdapter
 *   S3  PhoneAccount self-managed terdaftar & aktif
 *   S4  panggilan self-managed bisa dibuka (jam harus menampilkan layar panggilan)
 *   S5  audio route ke SCO berhasil (setCommunicationDevice / startBluetoothSco)
 *   S6  frasa uji terdengar di speaker jam
 *   S7  rekaman 5 detik berasal dari MIC JAM (bukan mic HP) + bisa diputar ulang
 *
 * Cara menilai S7: tutup mic jam dengan jari saat merekam. Kalau level tidak turun
 * drastis, audio masih diambil dari mic HP → routing SCO salah.
 */
class MainActivity : Activity() {

    private lateinit var out: TextView
    private lateinit var engine: SpikeEngine

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 48, 32, 32)
        }
        val title = TextView(this).apply {
            text = "AgentCall — Spike (Phase 0)"
            textSize = 20f
        }
        val run = Button(this).apply {
            text = "Jalankan semua langkah"
            setOnClickListener { engine.runAll() }
        }
        val s7 = Button(this).apply {
            text = "S7: rekam 5 s dari jam → putar ulang"
            setOnClickListener { engine.recordFromWatch(5000) }
        }
        val call = Button(this).apply {
            text = "Buka panggilan self-managed (S4)"
            setOnClickListener { engine.placeSelfManagedCall() }
        }
        val settings = Button(this).apply {
            text = "Buka pengaturan akun panggilan"
            setOnClickListener {
                startActivity(Intent(TelecomManager.ACTION_CHANGE_PHONE_ACCOUNTS))
            }
        }
        out = TextView(this).apply {
            textSize = 13f
            setPadding(0, 24, 0, 0)
            setTextIsSelectable(true)          // supaya log bisa di-copy
        }

        listOf(title, run, call, s7, settings, out).forEach {
            root.addView(it, LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { bottomMargin = 12 })
        }
        setContentView(ScrollView(this).apply { addView(root) })

        engine = SpikeEngine(this) { line -> runOnUiThread { out.append(line + "\n") } }

        requestPerms()
        engine.registerPhoneAccount()
    }

    private fun requestPerms() {
        val perms = mutableListOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.MODIFY_AUDIO_SETTINGS,
            Manifest.permission.MANAGE_OWN_CALLS,
        )
        if (android.os.Build.VERSION.SDK_INT >= 31) {
            perms += Manifest.permission.BLUETOOTH_CONNECT
        }
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            perms += Manifest.permission.POST_NOTIFICATIONS
        }
        val missing = perms.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) requestPermissions(missing.toTypedArray(), 7)
    }
}

/** Dipakai Telecom untuk mengenali penyedia panggilan kita. */
fun phoneAccountHandle(app: android.content.Context): PhoneAccountHandle =
    PhoneAccountHandle(
        android.content.ComponentName(app, AgentCallConnectionService::class.java),
        "id.agentcall"
    )

/** Tampilkan pengaturan notifikasi akses (beberapa ROM butuh ini agar Health tidak dibunuh). */
fun openNotificationAccess(app: android.content.Context) {
    app.startActivity(
        Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    )
}
