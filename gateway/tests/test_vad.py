import struct

from app.main import Session


def frame(amp: int, n: int = 320) -> bytes:
    return b"".join(struct.pack("<h", amp) for _ in range(n))


class FakeWs:
    async def send_text(self, *a): pass
    async def send_bytes(self, *a): pass


def new_session(rate=16_000):
    return Session(ws=FakeWs(), device="test", rate=rate)


def test_no_utterance_for_pure_silence():
    s = new_session()
    assert s.feed(frame(0) * 50) is None


def test_utterance_emitted_after_600ms_silence():
    s = new_session()
    assert s.feed(frame(10_000) * 30) is None      # 600 ms bicara
    assert s.feed(frame(0) * 10) is None           # 200 ms hening
    utt = s.feed(frame(0) * 30)                    # +600 ms -> akhir giliran
    assert utt is not None and len(utt) > 0


def test_muted_session_ignores_audio():
    s = new_session()
    s.muted = True
    assert s.feed(frame(10_000) * 60) is None


def test_frame_size_follows_rate():
    assert new_session(16_000).frame_bytes == 640
    assert new_session(8_000).frame_bytes == 320


def test_energy_vad_pre_buffer():
    from app.vad import EnergyVad
    v = EnergyVad(sample_rate=16_000, frame_ms=20, threshold=500, silence_timeout_ms=600)
    for _ in range(5):
        assert v.feed(frame(0)) is None
    for _ in range(15):
        assert v.feed(frame(8_000)) is None
    res = None
    for _ in range(35):
        r = v.feed(frame(0))
        if r is not None:
            res = r
            break
    assert res is not None, "VAD harus menghasilkan rekaman utuh"
    assert len(res) > 300 * 32


def test_create_vad_factory():
    from app.vad import create_vad, EnergyVad, SileroVad
    assert isinstance(create_vad("energy"), EnergyVad)
    assert isinstance(create_vad("silero"), SileroVad)
