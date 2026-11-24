/*
 * App lite FIT 5 — remote control untuk app Android "AgentCall".
 *
 * PENTING (lihat docs/01-riset-dan-arsitektur.md §1.3):
 *   - Jam TIDAK punya API mic/WebSocket. Semua suara lewat P2P Wear Engine.
 *   - App ini: kirim perintah + tampilkan state/transkrip + getar +
 *     TERIMA file jawaban (WAV) dari HP lalu putar di speaker jam.
 *   - Runtime JerryScript ES5.1: JANGAN pakai let/const, arrow function,
 *     template literal, Promise, class.
 */
import { P2pClient, Message, Builder } from '../../common/wearengine';
import vibrator from '@system.vibrator';
import brightness from '@system.brightness';

// Fingerprint sertifikat app Android (SHA-256), dari AppGallery Connect / keytool.
// Ganti dengan milikmu — kalau kosong, P2P tidak akan tersambung.
var PHONE_CERT_FINGERPRINT = 'GANTI_DENGAN_FINGERPRINT_APP_ANDROID';

var AGENTS = ['omb', 'opencode', 'gemini'];

export default {
  data: {
    state: 'Siap',
    agentLabel: 'omb',
    agentIndex: 0,
    talkLabel: 'Bicara',
    transcript: '',
    connected: false,
    listening: false,
    level: 0,
    audioSrc: ''
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

        // File jawaban dari HP: Wear Engine menandai isFileType.
        // data.name = jalur internal, mis. "internal://app/jawab.wav"
        var isFile = (data && typeof data === 'object' && data.isFileType) ||
                     (data && typeof data === 'object' && data.name);
        if (isFile) {
          var path = (typeof data === 'object' && data.name) ? data.name : String(data);
          self.setState('Menerima jawaban…');
          self.playAnswer(path);
        }
      }
    };
    this.client.registerReceiver(this.receiver);
  },

  // Putar WAV jawaban di speaker jam.
  // Catatan Huawei: layanan musik di wearable harus memasukkan bundle app ke
  // "control list" sebelum @system.audio boleh dipakai. Kalau onerror muncul,
  // itu penyebabnya — lihat docs/06-jalur-c-hap.md §Batasan.
  playAnswer: function (path) {
    var self = this;
    try {
      var el = this.$element('$answer');
      this.audioSrc = path;
      // Penanganan error lewat event (try/catch tak menangkap onerror async).
      el.onplay = function () { self.setState('Bicara…'); };
      el.onended = function () { self.setState('Siap'); };
      el.onerror = function (e) {
        console.error('[AgentCall] audio onerror: ' + JSON.stringify(e));
        self.setState('Audio ditolak jam');
      };
      el.stop();
      el.src = path;
      el.play();
      self.setState('Memutar jawaban…');
    } catch (e) {
      console.error('[AgentCall] audio gagal: ' + e);
      this.setState('Audio ditolak: ' + path);
    }
  },

  stopAnswer: function () {
    try { this.$element('$answer').stop(); } catch (e) { /* abaikan */ }
    this.setState('Siap');
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
