/*
 * App lite FIT 5 — remote control untuk app Android "AgentCall".
 *
 * PENTING (lihat docs/01-riset-dan-arsitektur.md §1.3):
 *   - Jam TIDAK punya API mic/audio/WebSocket. Semua suara lewat HFP ke HP.
 *   - App ini hanya: kirim perintah + tampilkan state/transkrip + getar.
 *   - Runtime JerryScript ES5.1: JANGAN pakai let/const, arrow function,
 *     template literal, Promise, class.
 */
import { P2pClient, Message, Builder } from '../../common/wearengine';
import vibrator from '@system.vibrator';
import brightness from '@system.brightness';

// Fingerprint sertifikat app Android (SHA-256), dari AppGallery Connect / keytool.
// Ganti dengan milikmu — kalau kosong, P2P tidak akan tersambung.
var PHONE_CERT_FINGERPRINT = 'GANTI_DENGAN_FINGERPRINT_APP_ANDROID';

var AGENTS = ['opencode', 'deepseek-harness', 'openmausbot', 'gemini'];

export default {
  data: {
    state: 'Siap',
    agentLabel: 'opencode',
    agentIndex: 0,
    talkLabel: 'Bicara',
    transcript: '',
    connected: false,
    listening: false,
    level: 0
  },

  onInit: function () {
    this.agentLabel = AGENTS[this.agentIndex];
    this.setupP2p();
    brightness.setKeepScreenOn({ keepScreenOn: true });
  },

  setupP2p: function () {
    var self = this;
    this.client = new P2pClient();
    // Samakan dengan package name + fingerprint app Android (lihat README).
    this.client.setPeerPkgName('id.agentcall');
    this.client.setPeerFingerPrint(PHONE_CERT_FINGERPRINT);

    this.receiver = {
      onSuccess: function () { self.connected = true; self.state = 'Siap'; },
      onFailure: function () { self.connected = false; self.state = 'HP tidak terbuka'; },
      onReceiveMessage: function (data) {
        self.connected = true;
        var msg = typeof data === 'string' ? data : String(data);
        try { msg = JSON.parse(msg); } catch (e) { /* teks biasa */ }

        if (msg && msg.t === 'state') {
          self.setState(msg.v);
        } else if (msg && msg.t === 'final') {
          self.transcript = msg.text;
          vibrator.vibrate({ mode: 'short' });
          self.setState('listening');
        } else if (msg && msg.t === 'level') {
          self.level = Math.min(100, Math.round(msg.value / 300));
        } else if (typeof msg === 'string') {
          self.transcript = msg;
        }
      }
    };
    this.client.registerReceiver(this.receiver);
  },

  setState: function (v) {
    if (v === 'listening') { this.state = 'Mendengar…'; this.listening = true; }
    else if (v === 'thinking') { this.state = 'Berpikir…'; this.listening = false; }
    else if (v === 'speaking') { this.state = 'Bicara…'; this.listening = false; }
    else { this.state = String(v); }
  },

  onTalk: function () {
    // Perintah kecil (<= 1 KB) supaya aman untuk P2P Wear Engine.
    this.send({ cmd: 'talk', agent: this.agentLabel });
    this.talkLabel = 'Bicara';
    vibrator.vibrate({ mode: 'long' });
  },

  onPrev: function () {
    this.agentIndex = (this.agentIndex + 1) % AGENTS.length;
    this.agentLabel = AGENTS[this.agentIndex];
    this.send({ cmd: 'agent', agent: this.agentLabel });
  },

  onEnd: function () {
    this.send({ cmd: 'end' });
    this.state = 'Siap';
    this.transcript = '';
  },

  send: function (obj) {
    if (!this.client) { return; }
    var payload = JSON.stringify(obj);
    this.client.send(
      new Builder().setPayload(payload).build(),
      function (result) { console.info('send result: ' + result); }
    );
  },

  onDestroy: function () {
    if (this.client) { this.client.unregisterReceiver(); }
  }
};
