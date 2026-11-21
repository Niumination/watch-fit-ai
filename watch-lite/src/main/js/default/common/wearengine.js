/*
 * Wear Engine P2P Client SDK (Lite Wearable ES5 Wrapper).
 *
 * Digunakan untuk komunikasi dua arah (P2P) antara app Lite di WATCH FIT 5
 * dan companion app di ponsel Android (id.agentcall).
 *
 * Kompatibel dengan:
 *   - Huawei Wear Engine JS SDK for Lite Wearable
 *   - DevEco Studio Previewer / Simulator (mock fallback)
 *   - JerryScript ES5.1 (tanpa let, const, arrow function, class, template literal)
 */

function Builder() {
  this._description = '';
  this._payload = null;
}

Builder.prototype.setDescription = function (desc) {
  this._description = String(desc || '');
  return this;
};

Builder.prototype.setPayload = function (payload) {
  this._payload = payload;
  if (typeof payload === 'string' && !this._description) {
    this._description = payload;
  }
  return this;
};

Builder.prototype.build = function () {
  var msg = new Message();
  msg.builder = this;
  return msg;
};

function Message() {
  this.builder = null;
}

Message.prototype.getDescription = function () {
  return this.builder ? this.builder._description : '';
};

Message.prototype.getPayload = function () {
  return this.builder ? this.builder._payload : null;
};

function P2pClient() {
  this.peerPkgName = '';
  this.peerFingerPrint = '';
  this.receiver = null;
}

P2pClient.prototype.setPeerPkgName = function (name) {
  this.peerPkgName = String(name || '');
  return this;
};

P2pClient.prototype.setPeerFingerPrint = function (fp) {
  // Huawei: sidik jari tanpa titik dua (SHA-256 hex uppercase/lowercase)
  this.peerFingerPrint = typeof fp === 'string' ? fp.replace(/:/g, '') : '';
  return this;
};

P2pClient.prototype.registerReceiver = function (receiver) {
  this.receiver = receiver;
  var self = this;

  // 1. Cek apakah runtime native LiteOS mengekspos FeatureAbility (perangkat riil)
  if (typeof FeatureAbility !== 'undefined' && typeof FeatureAbility.subscribeMsg === 'function') {
    try {
      FeatureAbility.subscribeMsg({
        success: function (data) {
          if (self.receiver && typeof self.receiver.onReceiveMessage === 'function') {
            self.receiver.onReceiveMessage(data);
          }
        },
        fail: function (err, code) {
          if (self.receiver && typeof self.receiver.onFailure === 'function') {
            self.receiver.onFailure(err, code);
          }
        }
      });
      if (receiver && typeof receiver.onSuccess === 'function') {
        receiver.onSuccess();
      }
      return this;
    } catch (e) {
      console.warn('[WearEngine] FeatureAbility.subscribeMsg failed: ' + e);
    }
  }

  // 2. Fallback untuk DevEco Previewer / Simulator
  console.info('[WearEngine] registered receiver for peer: ' + this.peerPkgName);
  if (receiver && typeof receiver.onSuccess === 'function') {
    setTimeout(function () {
      if (self.receiver && typeof self.receiver.onSuccess === 'function') {
        self.receiver.onSuccess();
      }
    }, 100);
  }
  return this;
};

P2pClient.prototype.unregisterReceiver = function () {
  if (typeof FeatureAbility !== 'undefined' && typeof FeatureAbility.unsubscribeMsg === 'function') {
    try {
      FeatureAbility.unsubscribeMsg();
    } catch (e) {
      console.warn('[WearEngine] unsubscribeMsg error: ' + e);
    }
  }
  this.receiver = null;
};

P2pClient.prototype.ping = function (cb) {
  var callback = cb || {};
  if (typeof callback.onSuccess === 'function') {
    callback.onSuccess();
  }
  if (typeof callback.onPingResult === 'function') {
    callback.onPingResult({ code: 0, data: 'connected' });
  }
};

P2pClient.prototype.send = function (message, cb) {
  var payload = '';
  if (message && message.builder) {
    if (typeof message.builder._payload === 'string') {
      payload = message.builder._payload;
    } else if (message.builder._description) {
      payload = message.builder._description;
    } else if (message.builder._payload) {
      try {
        payload = JSON.stringify(message.builder._payload);
      } catch (e) {
        payload = String(message.builder._payload);
      }
    }
  } else if (typeof message === 'string') {
    payload = message;
  }

  // Panggilan ke native jika tersedia
  if (typeof FeatureAbility !== 'undefined' && typeof FeatureAbility.callAbility === 'function') {
    try {
      FeatureAbility.callAbility({
        bundleName: this.peerPkgName,
        message: payload,
        success: function (res) {
          if (typeof cb === 'function') {
            cb(res);
          } else if (cb && typeof cb.onSuccess === 'function') {
            cb.onSuccess(res);
          }
        },
        fail: function (err, code) {
          if (cb && typeof cb.onFailure === 'function') {
            cb.onFailure(err, code);
          }
        }
      });
      return;
    } catch (e) {
      console.warn('[WearEngine] FeatureAbility.callAbility failed: ' + e);
    }
  }

  // Simulator / mock callback
  console.info('[WearEngine] sent to ' + this.peerPkgName + ': ' + payload);
  if (typeof cb === 'function') {
    cb('OK');
  } else if (cb) {
    if (typeof cb.onSuccess === 'function') {
      cb.onSuccess();
    }
    if (typeof cb.onSendResult === 'function') {
      cb.onSendResult({ code: 0, data: 'sent' });
    }
  }
};

export { P2pClient, Message, Builder };
export default {
  P2pClient: P2pClient,
  Message: Message,
  Builder: Builder
};
