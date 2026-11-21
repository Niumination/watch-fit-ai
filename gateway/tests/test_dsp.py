import struct

from app import dsp


def pcm(samples):
    return b"".join(struct.pack("<h", s) for s in samples)


def test_rms_silence_is_zero():
    assert dsp.rms(pcm([0] * 100)) == 0


def test_rms_matches_amplitude():
    rms = dsp.rms(pcm([10_000, -10_000] * 50))
    assert 9_000 < rms <= 10_000


def test_ratecv_halves_length_when_downsampling():
    src = pcm([1000] * 1600)              # 1600 sampel @16k = 0,1 s
    out = dsp.ratecv(src, 2, 1, 16_000, 8_000)
    assert abs(len(out) // 2 - 800) < 8   # ~800 sampel @8k
