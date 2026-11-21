from app import registry


def test_config_loads_all_agents():
    default, specs = registry.load_specs()
    ids = {s.id for s in specs}
    assert {"opencode", "deepseek-harness", "openmausbot", "gemini", "echo"} <= ids
    assert default in ids


def test_alias_resolution():
    _, specs = registry.load_specs()
    assert registry.find(specs, "deepseek").id == "deepseek-harness"
    assert registry.find(specs, "mausbot").id == "openmausbot"
    assert registry.find(specs, "tidak-ada") is None


def test_missing_env_falls_back_to_echo(monkeypatch):
    monkeypatch.delenv("OPENCODE_URL", raising=False)
    a = registry.build("opencode")
    assert a.name == "echo"          # sesi tetap hidup, bukan crash


def test_unknown_type_falls_back_to_echo():
    a = registry.build("gemini")     # tipe gemini_live belum diimplementasikan
    assert a.name == "echo"
