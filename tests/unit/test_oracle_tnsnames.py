import tempfile
from pathlib import Path

from conftest import ExitJson, module_path, load_module_from_path


class FakeAnsibleModule:
    params = {}

    def __init__(self, **_kwargs):
        self.params = dict(self.__class__.params)
        self.check_mode = self.params.get("check_mode", True)
        self.tmpdir = tempfile.gettempdir()
        self.warnings = []

    def warn(self, msg):
        self.warnings.append(msg)

    def backup_local(self, filename):
        return filename + ".bak"

    def exit_json(self, **kwargs):
        raise ExitJson(kwargs)

    def fail_json(self, **kwargs):
        raise RuntimeError(kwargs)


class FakeParam:
    def __init__(self, name, value):
        self.name = name
        self._value = value

    def valuesstr(self):
        return self._value


class FakeDotOraFile:
    def __init__(self, _filename):
        self.changed = True
        self.warn = []
        self.params = [FakeParam("TEST_ALIAS", "(DESCRIPTION=...)")]

    def upsertalias(self, _alias, _value):
        return None

    def setparamvalue(self, _alias, _name, _value):
        return None

    def upsertaliasatribute(self, _alias, _path, _value):
        return None

    def deleteparampath(self, _alias, _path):
        return None

    def deleteparam(self, _alias, _name):
        return None

    def removealias(self, _alias):
        return None

    def __str__(self):
        return "NEW_CONTENT"


def test_check_mode_does_not_write_changes(monkeypatch):
    mod = load_module_from_path(module_path("plugins", "modules", "oracle_tnsnames.py"), "oracle_tns_test")
    called = {"write": False}

    with tempfile.NamedTemporaryFile("w", delete=False) as tf:
        tf.write("OLD_CONTENT")
        target = tf.name

    FakeAnsibleModule.params = {
        "path": target,
        "follow": True,
        "backup": True,
        "state": "present",
        "alias": "TEST_ALIAS",
        "whole_value": "X",
        "attribute_path": None,
        "attribute_name": None,
        "attribute_value": None,
        "check_mode": True,
    }

    def fake_write_changes(_module, _content, _dest):
        called["write"] = True

    monkeypatch.setattr(mod, "AnsibleModule", FakeAnsibleModule)
    monkeypatch.setattr(mod, "DotOraFile", FakeDotOraFile, raising=False)
    monkeypatch.setattr(mod, "write_changes", fake_write_changes)

    try:
        mod.main()
    except ExitJson as exc:
        payload = exc.args[0]
        assert payload["changed"] is True
    else:
        raise AssertionError("module should exit_json")
    finally:
        Path(target).unlink(missing_ok=True)

    assert called["write"] is False


def test_normal_mode_writes_changes(monkeypatch):
    mod = load_module_from_path(module_path("plugins", "modules", "oracle_tnsnames.py"), "oracle_tns_test_write")
    called = {"write": False}

    with tempfile.NamedTemporaryFile("w", delete=False) as tf:
        tf.write("OLD_CONTENT")
        target = tf.name

    FakeAnsibleModule.params = {
        "path": target,
        "follow": True,
        "backup": False,
        "state": "present",
        "alias": "TEST_ALIAS",
        "whole_value": "X",
        "attribute_path": None,
        "attribute_name": None,
        "attribute_value": None,
        "check_mode": False,
    }

    def fake_write_changes(_module, _content, _dest):
        called["write"] = True

    monkeypatch.setattr(mod, "AnsibleModule", FakeAnsibleModule)
    monkeypatch.setattr(mod, "DotOraFile", FakeDotOraFile, raising=False)
    monkeypatch.setattr(mod, "write_changes", fake_write_changes)

    try:
        mod.main()
    except ExitJson:
        pass
    else:
        raise AssertionError("module should exit_json")
    finally:
        Path(target).unlink(missing_ok=True)

    assert called["write"] is True


def test_write_changes_helper_writes_file(tmp_path):
    mod = load_module_from_path(module_path("plugins", "modules", "oracle_tnsnames.py"), "oracle_tns_test_helper")

    class TmpModule:
        tmpdir = str(tmp_path)

        def atomic_move(self, src, dst, unsafe_writes=True):
            if isinstance(dst, bytes):
                dst = dst.decode("utf-8")
            if isinstance(dst, str) and dst.startswith("b'") and dst.endswith("'"):
                dst = dst[2:-1]
            if isinstance(src, bytes):
                src = src.decode("utf-8")
            Path(dst).write_bytes(Path(src).read_bytes())
            Path(src).unlink(missing_ok=True)

    target = tmp_path / "tns.ora"
    target.write_text("OLD", encoding="utf-8")
    mod.write_changes(TmpModule(), "NEW", str(target))
    assert target.read_text(encoding="utf-8") == "NEW"


def test_absent_state_follow_symlink_and_missing_alias(monkeypatch, tmp_path):
    mod = load_module_from_path(module_path("plugins", "modules", "oracle_tnsnames.py"), "oracle_tns_test_absent")
    real_file = tmp_path / "real.ora"
    link_file = tmp_path / "link.ora"
    real_file.write_text("OLD_CONTENT", encoding="utf-8")
    link_file.symlink_to(real_file)

    class EmptyParamDotOra(FakeDotOraFile):
        def __init__(self, _filename):
            self.changed = True
            self.warn = []
            self.params = []

    FakeAnsibleModule.params = {
        "path": str(link_file),
        "follow": True,
        "backup": False,
        "state": "absent",
        "alias": "TEST_ALIAS",
        "whole_value": None,
        "attribute_path": None,
        "attribute_name": None,
        "attribute_value": None,
        "check_mode": True,
    }

    monkeypatch.setattr(mod, "AnsibleModule", FakeAnsibleModule)
    monkeypatch.setattr(mod, "DotOraFile", EmptyParamDotOra, raising=False)
    monkeypatch.setattr(mod, "write_changes", lambda *_args, **_kwargs: None)

    try:
        mod.main()
    except ExitJson as exc:
        payload = exc.args[0]
        assert payload["msg"] == "TEST_ALIAS="
    else:
        raise AssertionError("module should exit_json")
