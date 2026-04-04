from conftest import module_path, load_module_from_path


class DummyModule:
    def __init__(self):
        self.warnings = []

    def warn(self, msg):
        self.warnings.append(msg)

    def fail_json(self, **kwargs):
        raise RuntimeError(kwargs)


def test_oracle_homes_does_not_warn_when_oracle_home_missing(monkeypatch):
    mod = load_module_from_path(module_path("plugins", "module_utils", "oracle_homes.py"), "oracle_homes_test")
    monkeypatch.setattr(mod.os.path, "isdir", lambda _v: False)
    homes = mod.OracleHomes(DummyModule())

    homes.add_home(None)
    homes.add_sid("DB1", ORACLE_HOME=None)

    assert homes.module.warnings == []


def test_oracle_homes_warns_for_invalid_oracle_home(monkeypatch):
    mod = load_module_from_path(module_path("plugins", "module_utils", "oracle_homes.py"), "oracle_homes_test_warn")
    monkeypatch.setattr(mod.os.path, "isdir", lambda _v: False)
    homes = mod.OracleHomes(DummyModule())

    homes.add_home("/invalid/home")
    assert any("does not have valid directory" in w for w in homes.module.warnings)
