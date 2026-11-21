"""Helper DSP kecil tanpa ketergantungan berat.

Kenapa ada file ini: modul stdlib `audioop` sudah dihapus di Python 3.13+, sementara
runtime lain masih punya. Kita coba `audioop` dulu (cepat, C), lalu jatuh ke implementasi
murni Python supaya container/venv versi apa pun tetap jalan.
"""
from __future__ import annotations

import array
import math
import sys

try:                                     # pragma: no cover
    import audioop as _ao
except Exception:                        # pragma: no cover
    _ao = None


def rms(pcm: bytes, width: int = 2) -> int:
    """Root-mean-square sampel PCM16 -> dipakai VAD energi."""
    if _ao is not None:
        return _ao.rms(pcm, width)
    if not pcm:
        return 0
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    if not len(a):
        return 0
    return int(math.sqrt(sum(s * s for s in a) / len(a)))


def ratecv(pcm: bytes, width: int, channels: int, in_rate: int, out_rate: int) -> bytes:
    """Resample PCM16 linear (cukup untuk voice 8k<->16k<->24k)."""
    if _ao is not None and in_rate != out_rate:
        return _ao.ratecv(pcm, width, channels, in_rate, out_rate, None)[0]
    if in_rate == out_rate or not pcm:
        return pcm
    src = array.array("h")
    src.frombytes(pcm[: len(pcm) // 2 * 2])
    if sys.byteorder == "big":
        src.byteswap()
    n_out = int(len(src) * out_rate / in_rate)
    out = array.array("h", [0]) * 0
    ratio = in_rate / out_rate
    for i in range(n_out):
        pos = i * ratio
        i0 = int(pos)
        i1 = min(i0 + 1, len(src) - 1)
        frac = pos - i0
        out.append(int(src[i0] * (1 - frac) + src[i1] * frac))
    if sys.byteorder == "big":
        out.byteswap()
    return out.tobytes()
