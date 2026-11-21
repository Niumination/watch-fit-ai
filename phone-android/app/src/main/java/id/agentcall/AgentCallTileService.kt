package id.agentcall

import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import android.telecom.TelecomManager
import android.util.Log
import androidx.annotation.RequiresApi

/**
 * Quick Settings Tile untuk memicu panggilan AI agent langsung dari pulldown notifikasi HP.
 *
 * Sangat praktis untuk "Jalur B":
 * 1. Tarik status bar / Quick Settings di HP.
 * 2. Ketuk ikon "AI Agent".
 * 3. HP memanggil self-managed call -> jam WATCH FIT 5 bergetar & memunculkan tombol jawab.
 * 4. Tekan tombol hijau di jam -> langsung bicara dari pergelangan tangan!
 */
@RequiresApi(Build.VERSION_CODES.N)
class AgentCallTileService : TileService() {

    private val tag = "AgentCallTile"

    override fun onClick() {
        super.onClick()
        val telecom = getSystemService(TelecomManager::class.java) ?: return
        val handle = phoneAccountHandle(this)

        val extras = Bundle().apply {
            putParcelable(TelecomManager.EXTRA_PHONE_ACCOUNT_HANDLE, handle)
            putString("agent", Config.defaultAgent)
            putString("gateway", Config.gatewayUrl)
        }

        runCatching {
            telecom.placeCall(Uri.fromParts("tel", "agent", null), extras)
            Log.i(tag, "Quick Settings tile triggered placeCall()")
        }.onFailure {
            Log.e(tag, "Gagal memicu panggilan dari tile: ${it.message}")
        }
    }

    override fun onStartListening() {
        super.onStartListening()
        qsTile?.apply {
            state = Tile.STATE_INACTIVE
            label = "AI Agent"
            contentDescription = "Panggil AI Agent ke jam"
            updateTile()
        }
    }
}
