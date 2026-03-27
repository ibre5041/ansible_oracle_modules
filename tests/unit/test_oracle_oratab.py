from conftest import ExitJson, module_path, load_module_from_path


class FakeAnsibleModule:
    params = {}
    last = None

    def __init__(self, **_kwargs):
        self.params = dict(self.__class__.params)
        self.warnings = []
        self.__class__.last = self

    def warn(self, msg):
        self.warnings.append(msg)

    def exit_json(self, **kwargs):
        raise ExitJson(kwargs)

    def fail_json(self, **kwargs):
        raise RuntimeError(kwargs)


class FakeOracleHomes:
    def __init__(self, _module):
        self.facts_item = {
            "+ASM": {"ORACLE_HOME": "/nonexistent", "ORACLE_SID": "+ASM", "running": False},
        }
        self.homes = {}

    def list_crs_instances(self):
        return None

    def list_processes(self):
        return None

    def parse_oratab(self):
        return None

    def query_db_status(self, **_kwargs):
        return ["ASM", "STARTED"]


def test_oratab_running_only_does_not_warn_for_asm_false_down(monkeypatch):
    mod = load_module_from_path(module_path("plugins", "modules", "oracle_oratab.py"), "oracle_oratab_test")
    FakeAnsibleModule.params = {
        "asm_only": False,
        "running_only": True,
        "open_only": False,
        "writable_only": False,
        "homes": None,
        "facts_item": {},
    }
    monkeypatch.setattr(mod, "AnsibleModule", FakeAnsibleModule)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    try:
        mod.main()
    except ExitJson as exc:
        payload = exc.args[0]
        assert payload["oracle_list"] == {}
        assert FakeAnsibleModule.last.warnings == []
    else:
        raise AssertionError("module should exit_json")
