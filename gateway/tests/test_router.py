import pytest

from app import registry, router


@pytest.fixture(scope="module")
def specs():
    return registry.load_specs()[1]


@pytest.mark.parametrize("phrase,expected", [
    ("pindah ke opencode", "opencode"),
    ("ganti agent ke openmausbot", "openmausbot"),
    ("pakai deepseek dong", "deepseek-harness"),
    ("switch to gemini", "gemini"),
    ("gunakan echo", "echo"),
])
def test_switch_commands(specs, phrase, expected):
    r = router.route(phrase, specs, current="echo")
    assert r.switch_to is not None, f"tidak terdeteksi: {phrase}"
    assert r.switch_to.id == expected


def test_switch_keeps_question_after_agent_name(specs):
    r = router.route("opencode, tolong cek status deploy", specs, current="echo")
    assert r.switch_to is not None and r.switch_to.id == "opencode"
    assert "cek status deploy" in r.rest


def test_plain_question_is_not_a_switch(specs):
    r = router.route("berapa kapasitas baterai jam ini", specs, current="echo")
    assert r.switch_to is None and r.meta is False
    assert r.rest == "berapa kapasitas baterai jam ini"


def test_meta_question(specs):
    assert router.route("agent apa ini", specs, current="opencode").meta is True


def test_unknown_agent_falls_through(specs):
    r = router.route("pindah ke claude", specs, current="echo")
    assert r.switch_to is None       # claude belum ada di registry
