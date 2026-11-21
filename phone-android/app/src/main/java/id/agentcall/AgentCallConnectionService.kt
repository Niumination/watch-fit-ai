package id.agentcall

import android.os.Bundle
import android.telecom.Connection
import android.telecom.ConnectionRequest
import android.telecom.ConnectionService
import android.telecom.DisconnectCause
import android.telecom.PhoneAccountHandle
import android.telecom.TelecomManager

/**
 * Self-managed ConnectionService: membuat sesi AI terlihat sebagai "panggilan VoIP"
 * oleh OS, sehingga jam (via HFP) menampilkan layar panggilan native dan tombol
 * jawab/tutup benar-benar berfungsi — perilaku yang sama seperti panggilan WhatsApp.
 *
 * Konsekuensi penting:
 *  - butuh permission MANAGE_OWN_CALLS
 *  - PhoneAccount harus didaftarkan lebih dulu (lihat AgentCallApp.registerPhoneAccount)
 *  - audio TIDAK otomatis kita dapatkan; tetap kita route manual di WatchAudioRoute
 */
class AgentCallConnectionService : ConnectionService() {

    override fun onCreateOutgoingConnection(
        handle: PhoneAccountHandle,
        request: ConnectionRequest,
    ): Connection {
        val conn = AgentCallConnection(incoming = false)
        conn.connectionProperties = Connection.PROPERTY_SELF_MANAGED
        conn.setAddress(request.address, TelecomManager.PRESENTATION_ALLOWED)
        conn.setInitializing()
        conn.setDialing()
        VoiceSessionManager.start(conn, request.extras)
        return conn
    }

    override fun onCreateIncomingConnection(
        handle: PhoneAccountHandle,
        request: ConnectionRequest,
    ): Connection {
        val conn = AgentCallConnection(incoming = true)
        conn.connectionProperties = Connection.PROPERTY_SELF_MANAGED
        conn.setAddress(request.address, TelecomManager.PRESENTATION_ALLOWED)
        conn.setRinging()          // -> jam berdering
        return conn
    }

    override fun onCreateIncomingConnectionFailed(
        handle: PhoneAccountHandle,
        request: ConnectionRequest,
    ) {
        // Agent tidak tersedia / sesi ditolak: jangan biarkan jam berdering selamanya.
    }
}

class AgentCallConnection(private val incoming: Boolean) : Connection() {

    override fun onAnswer() {
        setActive()
        VoiceSessionManager.answer()
    }

    override fun onAnswer(videoState: Int) = onAnswer()

    override fun onReject() {
        VoiceSessionManager.hangUp()
        setDisconnected(DisconnectCause(DisconnectCause.REJECTED))
        destroy()
    }

    override fun onDisconnect() {
        VoiceSessionManager.hangUp()
        setDisconnected(DisconnectCause(DisconnectCause.LOCAL))
        destroy()
    }

    override fun onAbort() = onDisconnect()

    override fun onHold() = setOnHold()

    override fun onUnhold() = setActive()

    /** Tombol "Mute" pada layar panggilan jam. */
    override fun onCallAudioStateChanged(state: CallAudioState) {
        super.onCallAudioStateChanged(state)
        VoiceSessionManager.setMuted(state.isMuted)
    }

    fun extras(): Bundle = Bundle()
}
