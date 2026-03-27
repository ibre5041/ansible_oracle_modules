from conftest import ExitJson, module_path, load_module_from_path


class FakeAnsibleModule:
    params = {}

    def __init__(self, **_kwargs):
        self.params = dict(self.__class__.params)

    def exit_json(self, **kwargs):
        raise ExitJson(kwargs)

    def fail_json(self, **kwargs):
        raise RuntimeError(kwargs)


class FakeConn:
    last = None

    def __init__(self, _module):
        self.changed = False
        self.ddls = []
        self.data = [{"dummy": 1}]
        self.container = None
        FakeConn.last = self

    def set_container(self, pdb_name):
        self.container = pdb_name

    def execute_select_to_dict(self, _sql):
        return self.data

    def execute_ddl(self, statement):
        self.ddls.append(statement)
        self.changed = statement.startswith("insert")

    def execute_statement(self, statement):
        self.ddls.append(statement)
        self.changed = True
        return []


def _load():
    return load_module_from_path(module_path("plugins", "modules", "oracle_sql.py"), "oracle_sql_test")


def test_select_is_not_changed(monkeypatch):
    mod = _load()
    FakeAnsibleModule.params = {
        "user": "u",
        "password": "p",
        "mode": "normal",
        "hostname": "db.example",
        "port": 1521,
        "service_name": "svc",
        "dsn": None,
        "oracle_home": None,
        "pdb_name": None,
        "sql": "select * from dual",
        "script": None,
    }
    monkeypatch.setattr(mod, "AnsibleModule", FakeAnsibleModule)
    monkeypatch.setattr(mod, "oracleConnection", FakeConn, raising=False)

    try:
        mod.main()
    except ExitJson as exc:
        payload = exc.args[0]
        assert payload["changed"] is False
    else:
        raise AssertionError("module should exit_json")


def test_local_pdb_routing_uses_alter_session(monkeypatch):
    mod = _load()
    FakeAnsibleModule.params = {
        "user": "u",
        "password": "p",
        "mode": "normal",
        "hostname": "localhost",
        "port": 1521,
        "service_name": "cdb1",
        "dsn": None,
        "oracle_home": None,
        "pdb_name": "APPPDB1",
        "sql": "insert into t values (1)",
        "script": None,
    }
    monkeypatch.setattr(mod, "AnsibleModule", FakeAnsibleModule)
    monkeypatch.setattr(mod, "oracleConnection", FakeConn, raising=False)

    try:
        mod.main()
    except ExitJson as exc:
        payload = exc.args[0]
        assert payload["changed"] is True
        assert FakeConn.last.container == "APPPDB1"
    else:
        raise AssertionError("module should exit_json")


def test_script_inline_branch_sets_changed(monkeypatch):
    mod = _load()
    FakeAnsibleModule.params = {
        "user": "u",
        "password": "p",
        "mode": "normal",
        "hostname": "db.example",
        "port": 1521,
        "service_name": "svc",
        "dsn": None,
        "oracle_home": None,
        "pdb_name": None,
        "sql": None,
        "script": "insert into t values (1);",
    }
    monkeypatch.setattr(mod, "AnsibleModule", FakeAnsibleModule)
    monkeypatch.setattr(mod, "oracleConnection", FakeConn, raising=False)

    try:
        mod.main()
    except ExitJson as exc:
        payload = exc.args[0]
        assert payload["changed"] is True
        assert payload["output_lines"] == []
    else:
        raise AssertionError("module should exit_json")


def test_script_file_branch(monkeypatch, tmp_path):
    mod = _load()
    script_file = tmp_path / "test.sql"
    script_file.write_text("insert into t values (1);", encoding="utf-8")
    FakeAnsibleModule.params = {
        "user": "u",
        "password": "p",
        "mode": "normal",
        "hostname": "db.example",
        "port": 1521,
        "service_name": "svc",
        "dsn": None,
        "oracle_home": None,
        "pdb_name": None,
        "sql": None,
        "script": "@%s" % script_file,
    }
    monkeypatch.setattr(mod, "AnsibleModule", FakeAnsibleModule)
    monkeypatch.setattr(mod, "oracleConnection", FakeConn, raising=False)

    try:
        mod.main()
    except ExitJson as exc:
        payload = exc.args[0]
        assert payload["changed"] is True
    else:
        raise AssertionError("module should exit_json")


def test_script_file_ioerror(monkeypatch):
    mod = _load()
    FakeAnsibleModule.params = {
        "user": "u",
        "password": "p",
        "mode": "normal",
        "hostname": "db.example",
        "port": 1521,
        "service_name": "svc",
        "dsn": None,
        "oracle_home": None,
        "pdb_name": None,
        "sql": None,
        "script": "@/path/does/not/exist.sql",
    }
    monkeypatch.setattr(mod, "AnsibleModule", FakeAnsibleModule)
    monkeypatch.setattr(mod, "oracleConnection", FakeConn, raising=False)

    try:
        mod.main()
    except RuntimeError as exc:
        payload = exc.args[0]
        assert payload["changed"] is False
    else:
        raise AssertionError("module should fail_json")
