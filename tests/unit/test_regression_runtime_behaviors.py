from conftest import module_path, load_module_from_path


class _FailJson(Exception):
    pass


def test_oracle_services_stop_service_does_not_swallow_real_errors():
    mod = load_module_from_path(module_path("plugins", "modules", "oracle_services.py"), "oracle_services_runtime")

    class FakeModule:
        params = {"oracle_home": "/u01/app/oracle/product/19.0.0/dbhome_1"}

        def run_command(self, _cmd):
            return (1, "unexpected failure", "")

        def fail_json(self, **kwargs):
            raise _FailJson(kwargs)

        def exit_json(self, **kwargs):
            raise AssertionError(kwargs)

    mod.gimanaged = True
    try:
        mod.stop_service(None, FakeModule(), "", "SVC1", "DB1")
    except _FailJson as exc:
        assert "failed" in exc.args[0]["msg"].lower()
    else:
        raise AssertionError("stop_service should fail on unexpected rc!=0")


def test_sqldba_run_sql_p_uses_module_in_pdb_scope():
    mod = load_module_from_path(module_path("plugins", "modules", "oracle_sqldba.py"), "oracle_sqldba_runtime")
    calls = []
    marker = object()

    def _fake_run_sql(module, sql, username=None, password=None, pdb=None):
        calls.append((module, sql, username, password, pdb))
        return "ok"

    mod.run_sql = _fake_run_sql
    out = mod.run_sql_p(marker, "select 1 from dual", "u", "p", "pdbs", ["PDB1", "PDB2"])
    assert out == "okok"
    assert calls[0][0] is marker
    assert calls[0][4] == "PDB1"
    assert calls[1][4] == "PDB2"


def test_oracle_homes_query_db_status_returns_unknown_when_unparseable(monkeypatch):
    mod = load_module_from_path(module_path("plugins", "module_utils", "oracle_homes.py"), "oracle_homes_runtime")

    class DummyModule:
        def warn(self, _msg):
            return None

        def fail_json(self, **kwargs):
            raise RuntimeError(kwargs)

    class _PW:
        pw_name = "oracle"
        pw_dir = "/tmp"
        pw_uid = 1000
        pw_gid = 1000

    class _Proc:
        returncode = 0

        def communicate(self, **_kwargs):
            return (b"NO EXPECTED HEADERS\n", b"")

    monkeypatch.setattr(mod.pwd, "getpwnam", lambda _u: _PW())
    monkeypatch.setattr(mod.os, "getuid", lambda: 1000)
    monkeypatch.setattr(mod.os, "getgrouplist", lambda _u, _g: [1000])
    monkeypatch.setattr(mod.subprocess, "Popen", lambda *args, **kwargs: _Proc())

    homes = mod.OracleHomes(DummyModule())
    status = homes.query_db_status("oracle", "/tmp", "ORCLCDB")
    assert status == ["UNKNOWN"]


def test_oracle_facts_userenv_is_not_nested_under_sid():
    content = module_path("plugins", "modules", "oracle_facts.py").read_text(encoding="utf-8", errors="ignore")
    assert "db.update({sid: {'userenv': userenv}})" not in content


def test_oracle_user_does_not_pass_module_to_execute_ddl():
    content = module_path("plugins", "modules", "oracle_user.py").read_text(encoding="utf-8", errors="ignore")
    assert "conn.execute_ddl(module, alter_sql)" not in content
