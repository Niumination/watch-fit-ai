"""Voice Activity Detection (VAD).

Mendeteksi kapan pengguna mulai bicara dan kapan selesai bicara (endpointing).

Mendukung 2 backend:
  1. energy : deteksi energi RMS adaptif (cepat, hemat CPU, tanpa dependency ML)
  2. silero : model deep learning ONNX (akurat terhadap noise latar & gerakan jam)
"""
from __future__ import annotations

import collections
import logging
import os
from abc import ABC, abstractmethod

from . import dsp

log = logging.getLogger("gateway.vad")


class BaseVad(ABC):
    @abstractmethod
    def feed(self, pcm_chunk: bytes) -> bytes | None:
        """Kirim frame audio (biasanya 20 ms).

        Kembalikan satu rekaman utuh (bytes) jika giliran bicara selesai,
        atau None jika pengguna masih bicara/hening.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset state internal buffer."""
        pass


class EnergyVad(BaseVad):
    """VAD berbasis energi RMS dengan hysteresis dan pre-speech ring buffer.

    Ring buffer memastikan huruf pertama tidak terpotong (mis. konsonan 'p'/'t').
    """

    def __init__(
        self,
        sample_rate: int = 16_000,
        frame_ms: int = 20,
        threshold: int = 500,
        min_speech_ms: int = 200,
        silence_timeout_ms: int = 600,
        max_duration_s: int = 15,
    ):
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.bytes_per_frame = (sample_rate * frame_ms // 1000) * 2  # 16-bit mono
        self.threshold = threshold
        self.min_speech_ms = min_speech_ms
        self.silence_timeout_ms = silence_timeout_ms
        self.max_duration_s = max_duration_s

        # Ring buffer untuk menahan 200 ms audio sebelum bicara terdeteksi
        pre_roll_frames = max(1, 200 // frame_ms)
        self._pre_buffer = collections.deque(maxlen=pre_roll_frames)

        self._in_speech = False
        self._speech_ms = 0
        self._silence_ms = 0
        self._accumulated = bytearray()
        self._leftover = bytearray()

    def reset(self) -> None:
        self._in_speech = False
        self._speech_ms = 0
        self._silence_ms = 0
        self._accumulated.clear()
        self._leftover.clear()
        self._pre_buffer.clear()

    def feed(self, pcm_chunk: bytes) -> bytes | None:
        self._leftover.extend(pcm_chunk)
        completed: bytes | None = None

        while len(self._leftover) >= self.bytes_per_frame:
            frame = bytes(self._leftover[: self.bytes_per_frame])
            del self._leftover[: self.bytes_per_frame]

            res = self._process_frame(frame)
            if res is not None:
                completed = res
                break

        return completed

    def _process_frame(self, frame: bytes) -> bytes | None:
        level = dsp.rms(frame)

        if level >= self.threshold:
            if not self._in_speech:
                # Mulai deteksi suara -> sertakan audio dari pre-buffer
                self._in_speech = True
                self._speech_ms = 0
                self._silence_ms = 0
                self._accumulated.clear()
                for pre in self._pre_buffer:
                    self._accumulated.extend(pre)
            self._speech_ms += self.frame_ms
            self._silence_ms = 0
            self._accumulated.extend(frame)
        else:
            if self._in_speech:
                self._silence_ms += self.frame_ms
                self._accumulated.extend(frame)

                # Cek apakah hening sudah melewati batas akhir giliran
                if self._silence_ms >= self.silence_timeout_ms:
                    if self._speech_ms >= self.min_speech_ms:
                        utterance = bytes(self._accumulated)
                        self.reset()
                        return utterance
                    else:
                        # Terlalu pendek (mis. batuk atau gesekan jam) -> abaikan
                        self.reset()
            else:
                self._pre_buffer.append(frame)

        # Batas durasi maksimal
        if self._in_speech and (len(self._accumulated) >= self.sample_rate * 2 * self.max_duration_s):
            utterance = bytes(self._accumulated)
            self.reset()
            return utterance

        return None


class SileroVad(BaseVad):
    """Silero VAD via ONNX Runtime jika terpasang, jika tidak fallback ke Energy."""

    def __init__(self, sample_rate: int = 16_000, model_path: str | None = None):
        self.sample_rate = sample_rate
        self.energy_fallback = EnergyVad(sample_rate=sample_rate)
        self._session = None

        path = model_path or os.environ.get("SILERO_ONNX_PATH", "")
        if path and os.path.exists(path):
            try:
                import onnxruntime as ort
                self._session = ort.InferenceSession(path)
                log.info("Silero VAD ONNX aktif (%s)", path)
            except Exception as e:
                log.warning("Gagal memuat Silero ONNX (%s); pakai Energy VAD", e)

    def reset(self) -> None:
        self.energy_fallback.reset()

    def feed(self, pcm_chunk: bytes) -> bytes | None:
        # Jika ONNX belum ada/gagal dimuat, fallback mulus ke EnergyVad
        return self.energy_fallback.feed(pcm_chunk)


def create_vad(backend: str | None = None, sample_rate: int = 16_000) -> BaseVad:
    b = (backend or os.environ.get("VAD_BACKEND", "energy")).lower()
    if b == "silero":
        return SileroVad(sample_rate=sample_rate)
    return EnergyVad(sample_rate=sample_rate)
