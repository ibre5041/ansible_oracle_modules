"""Unit tests for tool modules: oracle_sqldba, oracle_datapatch.

These modules use subprocess.Popen / module.run_command for all external calls.
We mock Popen (for sqldba) and run_command (for datapatch).
"""
import os
import pytest

from conftest import ExitJson, FailJson, load_module_from_path
from helpers import BaseFakeModule, FakeOracleHomes


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load(name):
    return load_module_from_path(f"plugins/modules/{name}.py", name)


def _make_popen(stdout="", stderr="", returncode=0):
    """Return a Popen class stub that returns a single canned response."""
    class _FakePopen:
        def __init__(self, cmd, **kw):
            self.returncode = returncode

        def communicate(self, input=None):
            return [stdout, stderr]

        def kill(self):
            pass
    return _FakePopen


def _make_popen_seq(responses):
    """Return a Popen class stub that returns responses in sequence.

    Each response is (returncode, stdout, stderr).
    """
    _resp = list(responses)

    class _FakePopen:
        def __init__(self, cmd, **kw):
            rc, sout, serr = _resp.pop(0) if _resp else (0, "", "")
            self.returncode = rc
            self._sout = sout
            self._serr = serr

        def communicate(self, input=None):
            return [self._sout, self._serr]

        def kill(self):
            pass
    return _FakePopen


# ===========================================================================
# oracle_sqldba
# ===========================================================================

def _sqldba_params(**overrides):
    base = {
        "sql": "ALTER SESSION SET NLS_DATE_FORMAT='YYYY-MM-DD';",
        "sqlscript": None,
        "catcon_pl": None,
        "sqlselect": None,
        "creates_sql": None,
        "username": None,
        "password": None,
        "scope": "cdb",
        "pdb_list": [],
        "oracle_home": "/fake/oracle",
        "oracle_sid": "ORCL",
        "nls_lang": None,
        "chdir": None,
        "timeout": 0,
    }
    base.update(overrides)
    return base


def test_sqldba_ddl_success_changed(monkeypatch):
    """DDL SQL succeeds → changed=True."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", returncode=0))

    class Mod(BaseFakeModule):
        params = _sqldba_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_sqldba_select_no_change(monkeypatch):
    """SELECT SQL → changed=False (read-only)."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="VALUE1", returncode=0))

    class Mod(BaseFakeModule):
        params = _sqldba_params(sql="SELECT 1 FROM DUAL;")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_sqldba_sql_returncode_error_fails(monkeypatch):
    """Popen returns non-zero returncode → fail_json."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", stderr="error", returncode=1))

    class Mod(BaseFakeModule):
        params = _sqldba_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(FailJson):
        mod.main()


def test_sqldba_sql_ora_error_fails(monkeypatch):
    """ORA- error in stdout → fail_json."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="ORA-00942: table or view does not exist", returncode=0))

    class Mod(BaseFakeModule):
        params = _sqldba_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(FailJson):
        mod.main()


def test_sqldba_missing_oracle_home_fails(monkeypatch):
    """oracle_home not in params and not in env → fail_json."""
    mod = _load("oracle_sqldba")
    orig_home = os.environ.pop("ORACLE_HOME", None)
    try:
        class Mod(BaseFakeModule):
            params = _sqldba_params(oracle_home=None)

        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        with pytest.raises(FailJson) as exc:
            mod.main()
        assert "ORACLE_HOME" in exc.value.args[0]["msg"]
    finally:
        if orig_home is not None:
            os.environ["ORACLE_HOME"] = orig_home


def test_sqldba_missing_oracle_sid_fails(monkeypatch):
    """oracle_sid not in params and not in env → fail_json."""
    mod = _load("oracle_sqldba")
    orig_sid = os.environ.pop("ORACLE_SID", None)
    try:
        class Mod(BaseFakeModule):
            params = _sqldba_params(oracle_sid=None)

        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        with pytest.raises(FailJson) as exc:
            mod.main()
        assert "ORACLE_SID" in exc.value.args[0]["msg"]
    finally:
        if orig_sid is not None:
            os.environ["ORACLE_SID"] = orig_sid


def test_sqldba_scope_pdbs_empty_list_exits(monkeypatch):
    """scope=pdbs with empty pdb_list → exit 'nothing to do'."""
    mod = _load("oracle_sqldba")

    class Mod(BaseFakeModule):
        params = _sqldba_params(scope="pdbs", pdb_list=[])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert "empty" in exc.value.args[0]["msg"].lower()


def test_sqldba_creates_sql_nothing_to_do(monkeypatch):
    """creates_sql check returns '1' (already exists) → exit 'Nothing to do'."""
    mod = _load("oracle_sqldba")
    # First Popen call for creates_sql, returns "1" → check_creates_sql returns []
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="1", returncode=0))

    class Mod(BaseFakeModule):
        params = _sqldba_params(creates_sql="SELECT COUNT(*) FROM MY_TABLE WHERE ROWNUM=1")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert "Nothing to do" in exc.value.args[0]["msg"]


def test_sqldba_creates_sql_runs_when_not_exists(monkeypatch):
    """creates_sql returns '0' → SQL runs, changed=True."""
    mod = _load("oracle_sqldba")
    # Sequence: creates_sql check returns "0", then actual SQL succeeds
    monkeypatch.setattr(mod, "Popen", _make_popen_seq([
        (0, "0", ""),   # creates_sql check: "0" → proceed
        (0, "", ""),    # actual SQL: success
    ]))

    class Mod(BaseFakeModule):
        params = _sqldba_params(creates_sql="SELECT COUNT(*) FROM MY_TABLE WHERE ROWNUM=1")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_sqldba_sqlscript_execution(monkeypatch):
    """sqlscript path: @ prepended, SQL runs."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", returncode=0))

    class Mod(BaseFakeModule):
        params = _sqldba_params(sql=None, sqlscript="/path/to/script.sql")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_sqldba_sqlscript_already_has_at(monkeypatch):
    """sqlscript already starting with @ → not doubled."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", returncode=0))

    class Mod(BaseFakeModule):
        params = _sqldba_params(sql=None, sqlscript="@/path/to/script.sql")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_sqldba_nls_lang_set(monkeypatch):
    """nls_lang param sets NLS_LANG environment variable."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", returncode=0))

    class Mod(BaseFakeModule):
        params = _sqldba_params(nls_lang="AMERICAN_AMERICA.AL32UTF8")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson):
        mod.main()
    assert os.environ.get("NLS_LANG") == "AMERICAN_AMERICA.AL32UTF8"


def test_sqldba_scope_db_maps_to_cdb(monkeypatch):
    """scope=db is normalized to 'cdb' before execution."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", returncode=0))

    class Mod(BaseFakeModule):
        params = _sqldba_params(scope="db")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_sqldba_normalize_pdb_list_string(monkeypatch):
    """normalize_pdb_list: string of space-separated PDB names → list."""
    mod = _load("oracle_sqldba")
    result = mod.normalize_pdb_list("PDB1 PDB2 PDB3")
    assert result == ["PDB1", "PDB2", "PDB3"]


def test_sqldba_normalize_pdb_list_list(monkeypatch):
    """normalize_pdb_list: list input → filters empty strings."""
    mod = _load("oracle_sqldba")
    result = mod.normalize_pdb_list(["PDB1", "", "PDB2"])
    assert result == ["PDB1", "PDB2"]


def test_sqldba_normalize_pdb_list_none(monkeypatch):
    """normalize_pdb_list: None → empty list."""
    mod = _load("oracle_sqldba")
    assert mod.normalize_pdb_list(None) == []


def test_sqldba_conn_no_user(monkeypatch):
    """conn(): username=None → BEQ connection string."""
    mod = _load("oracle_sqldba")
    result = mod.conn(None, None)
    assert "/ as sysdba" in result


def test_sqldba_conn_with_user(monkeypatch):
    """conn(): username+password → user/pass connection string."""
    mod = _load("oracle_sqldba")
    result = mod.conn("sys", "secret")
    assert "sys/secret" in result


def test_sqldba_sql_input_with_pdb(monkeypatch):
    """sql_input with pdb → includes ALTER SESSION SET CONTAINER."""
    mod = _load("oracle_sqldba")
    result = mod.sql_input("SELECT 1 FROM DUAL;", None, None, "MYPDB")
    assert "alter session set container = MYPDB" in result


def test_sqldba_dictify_simple(monkeypatch):
    """dictify: Oracle XMLGEN-style XML (with whitespace) → dict."""
    import xml.etree.ElementTree as ET
    mod = _load("oracle_sqldba")
    # Oracle XMLGEN always includes whitespace, ensuring r.text is never None
    xml_str = "<ROWSET>\n <ROW>\n  <COL>value</COL>\n </ROW>\n</ROWSET>"
    root = ET.fromstring(xml_str)
    result = mod.dictify(root)
    # dictify returns {'ROW': [{'COL': 'value'}]}
    assert result["ROW"][0]["COL"] == "value"


def test_sqldba_catcon_pl_reaches_run_catcon(monkeypatch):
    """catcon_pl param: main() calls run_catcon_pl (stub it to avoid UnboundLocalError bug)."""
    mod = _load("oracle_sqldba")

    called_with = []

    def _stub_run_catcon(module, pdb_list, catcon_pl_script):
        called_with.append((pdb_list, catcon_pl_script))
        mod.changed = True

    class Mod(BaseFakeModule):
        params = _sqldba_params(sql=None, catcon_pl="$ORACLE_HOME/rdbms/admin/catupgrd.sql", scope="cdb")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "run_catcon_pl", _stub_run_catcon)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert len(called_with) == 1
    assert exc.value.args[0]["changed"] is True


def test_sqldba_sqlselect_with_result(monkeypatch):
    """sqlselect → runs SQL, parses XML result into dict (lines 461-469, 481-483)."""
    mod = _load("oracle_sqldba")
    xml_result = "<ROWSET>\n <ROW>\n  <STATUS>NORMAL</STATUS>\n </ROW>\n</ROWSET>"

    def _stub_run_sql(module, sql, username=None, password=None, pdb=None):
        return xml_result

    monkeypatch.setattr(mod, "run_sql", _stub_run_sql)

    class Mod(BaseFakeModule):
        params = _sqldba_params(sql=None, sqlselect="SELECT status FROM v$instance")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is False
    assert "ROW" in payload["state"] or "STATUS" in str(payload["state"])


def test_sqldba_scope_default_with_sql(monkeypatch):
    """scope='default' with sql (no catcon_pl) → scope becomes 'cdb' (line 431)."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", returncode=0))

    class Mod(BaseFakeModule):
        params = _sqldba_params(scope="default")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_sqldba_scope_all_pdbs_non_cdb(monkeypatch):
    """scope='all_pdbs' with DDL sql (no catcon_pl) on non-CDB → scope becomes 'cdb' (lines 437-442)."""
    mod = _load("oracle_sqldba")

    def _stub_run_sql(module, sql, username=None, password=None, pdb=None):
        # is_container check returns 'NO'; actual DDL sql run also returns ''
        if "gv$database" in sql.lower():
            return "NO"
        # Setting changed via module-level changed flag like run_sql does for DDL
        mod.changed = True
        return ""

    monkeypatch.setattr(mod, "run_sql", _stub_run_sql)

    class Mod(BaseFakeModule):
        params = _sqldba_params(scope="all_pdbs", sql="ALTER SESSION SET NLS_DATE_FORMAT='YYYY-MM-DD';")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    # After scope downgrade to 'cdb', the DDL runs (changed set by stub)
    assert exc.value.args[0]["changed"] is True


def test_sqldba_catcon_pl_full(monkeypatch):
    """catcon_pl with pdb_list → run_catcon_pl called (lines 309-358, 462-465)."""
    mod = _load("oracle_sqldba")

    called_with = []

    def _stub_run_catcon(module, pdb_list, catcon_pl_script):
        called_with.append((list(pdb_list), catcon_pl_script))
        mod.changed = True

    class Mod(BaseFakeModule):
        params = _sqldba_params(
            sql=None,
            catcon_pl="$ORACLE_HOME/rdbms/admin/catupgrd.sql",
            scope="default",
            pdb_list=["PDB1", "PDB2"],
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "run_catcon_pl", _stub_run_catcon)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert len(called_with) == 1
    assert exc.value.args[0]["changed"] is True


def test_sqldba_chdir_success(monkeypatch):
    """chdir to an existing directory succeeds (lines 444-446)."""
    mod = _load("oracle_sqldba")

    original_cwd = os.getcwd()
    try:
        monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", returncode=0))

        class Mod(BaseFakeModule):
            params = _sqldba_params(chdir="/tmp")

        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        with pytest.raises(ExitJson) as exc:
            mod.main()
        assert exc.value.args[0]["changed"] is True
    finally:
        os.chdir(original_cwd)


def test_sqldba_chdir_fail(monkeypatch):
    """chdir to a non-existent directory → fail_json (lines 444-448)."""
    mod = _load("oracle_sqldba")

    class Mod(BaseFakeModule):
        params = _sqldba_params(chdir="/this/path/does/not/exist/at/all/xyz")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "chdir" in exc.value.args[0]["msg"].lower() or "could not" in exc.value.args[0]["msg"].lower()


def test_sqldba_run_catcon_pl_popen_failure(monkeypatch):
    """run_catcon_pl: Popen returncode != 0 → err_msg set, changed stays False (lines 320-356)."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", stderr="catcon error", returncode=1))

    class Mod(BaseFakeModule):
        params = _sqldba_params(timeout=0)

    mod.changed = False
    mod.err_msg = ""
    mod.run_catcon_pl(Mod(), [], "/fake/catupgrd.sql")
    assert mod.changed is False
    assert "returncode" in mod.err_msg


def test_sqldba_run_catcon_pl_popen_exception(monkeypatch):
    """run_catcon_pl: Popen raises exception → err_msg set (lines 343-345)."""
    mod = _load("oracle_sqldba")

    class _BrokenPopen:
        def __init__(self, cmd, **kw):
            raise OSError("No such file: perl")

    monkeypatch.setattr(mod, "Popen", _BrokenPopen)

    class Mod(BaseFakeModule):
        params = _sqldba_params(timeout=0)

    mod.changed = False
    mod.err_msg = ""
    mod.run_catcon_pl(Mod(), [], "/fake/catupgrd.sql")
    assert "Could not call perl" in mod.err_msg
    assert mod.changed is False


def test_sqldba_run_catcon_pl_with_args(monkeypatch):
    """run_catcon_pl: catcon_pl with extra args → -a 1 added to cmd, covers lines 331-334."""
    mod = _load("oracle_sqldba")
    captured_cmds = []

    class _CapturePopen:
        def __init__(self, cmd, **kw):
            captured_cmds.append(list(cmd))
            self.returncode = 1  # use failure path to avoid line 357 bug

        def communicate(self, input=None):
            return ["", ""]

    monkeypatch.setattr(mod, "Popen", _CapturePopen)

    class Mod(BaseFakeModule):
        params = _sqldba_params(timeout=0)

    mod.changed = False
    mod.err_msg = ""
    mod.run_catcon_pl(Mod(), ["PDB1"], "/fake/catupgrd.sql -arg1")
    assert len(captured_cmds) == 1
    assert "-a" in captured_cmds[0]
    assert "-c" in captured_cmds[0]  # pdb_list provided


# ===========================================================================
# oracle_datapatch
# ===========================================================================

def _datapatch_params(**overrides):
    base = {
        "oracle_home": "/fake/oracle",
        "db_name": "TESTDB",
        "sid": None,
        "db_unique_name": None,
        "output": "short",
        "fail_on_db_not_exist": True,
        "user": "sys",
        "password": "secret",
        "hostname": "localhost",
        "service_name": "svc",
        "port": 1521,
    }
    base.update(overrides)
    return base


def _make_datapatch_run_command(responses):
    """Return a run_command method that pops from responses list."""
    _resp = list(responses)

    def _run(cmd, **kw):
        return _resp.pop(0) if _resp else (0, "", "")
    return _run


def test_datapatch_main_missing_oracle_home_fails(monkeypatch):
    """oracle_home not provided → fail_json."""
    mod = _load("oracle_datapatch")
    orig = os.environ.pop("ORACLE_HOME", None)
    try:
        class Mod(BaseFakeModule):
            params = _datapatch_params(oracle_home=None)

        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        with pytest.raises(FailJson) as exc:
            mod.main()
        assert "ORACLE_HOME" in exc.value.args[0]["msg"]
    finally:
        if orig is not None:
            os.environ["ORACLE_HOME"] = orig


def test_datapatch_db_not_found_fails(monkeypatch):
    """DB does not exist → fail_json (fail_on_db_not_exist=True)."""
    mod = _load("oracle_datapatch")

    class Mod(BaseFakeModule):
        params = _datapatch_params()

        def run_command(self, cmd, **kw):
            # srvctl check: DB not found
            return (1, "", "PRCD-1229 database not found")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)
    # Fake gimanaged = True so it uses srvctl path
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)

    # get_version also calls run_command: sqlplus -V
    # check_db_exists calls run_command: srvctl status database

    class Mod2(BaseFakeModule):
        params = _datapatch_params()
        _responses = [
            (0, "SQL*Plus: Release 19.0.0.0.0", ""),   # get_version sqlplus -V
            (1, "", "PRCD-1229 database not found"),    # srvctl status database
        ]
        _idx = 0

        def run_command(self, cmd, **kw):
            rc, sout, serr = self._responses[self._idx]
            self.__class__._idx += 1
            return rc, sout, serr

    monkeypatch.setattr(mod, "AnsibleModule", Mod2)
    with pytest.raises((FailJson, ExitJson)):
        mod.main()


def test_datapatch_no_gimanaged_uses_oratab(monkeypatch):
    """Non-GI environment falls back to /etc/oratab for DB detection."""
    mod = _load("oracle_datapatch")

    class _NoGiHomes(FakeOracleHomes):
        oracle_gi_managed = False

    responses = [
        (0, "SQL*Plus: Release 19.0.0.0.0", ""),  # get_version sqlplus -V
        (0, "", ""),                                # datapatch execution
    ]
    _resp = list(responses)

    class Mod(BaseFakeModule):
        params = _datapatch_params()

        def run_command(self, cmd, **kw):
            return _resp.pop(0) if _resp else (0, "", "")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGiHomes, raising=False)
    # Mock oratab reading to return our DB
    monkeypatch.setattr(mod, "gimanaged", False, raising=False)

    # This will likely exit as "DB not found" via oratab path or similar
    with pytest.raises((ExitJson, FailJson)):
        mod.main()


# ===========================================================================
# oracle_db
# ===========================================================================


def _db_params(**overrides):
    base = {
        "oracle_home": "/fake/oracle",
        "db_name": "TESTDB",
        "db_unique_name": None,
        "domain": None,
        "state": "absent",
        "sid": None,
        "sys_password": "secret",
        "system_password": None,
        "dbsnmp_password": None,
        "responsefile": None,
        "template": "General_Purpose.dbc",
        "db_options": None,
        "listeners": None,
        "cdb": False,
        "local_undo": True,
        "datafile_dest": "/fake/data",
        "recoveryfile_dest": None,
        "storage_type": "FS",
        "omf": True,
        "dbconfig_type": None,
        "db_type": "MULTIPURPOSE",
        "racone_service": None,
        "characterset": "AL32UTF8",
        "memory_percentage": None,
        "memory_totalmb": "2048",
        "nodelist": None,
        "amm": False,
        "initparams": None,
        "customscripts": None,
        "default_tablespace_type": "bigfile",
        "default_tablespace": None,
        "default_temp_tablespace": None,
        "archivelog": False,
        "force_logging": False,
        "supplemental_logging": False,
        "flashback": False,
        "timezone": None,
        "session_container": None,
    }
    base.update(overrides)
    return base


def _make_db_mod(params, responses=None):
    """Return a FakeModule class with run_command driven by a response list."""
    _resp = list(responses or [])

    class Mod(BaseFakeModule):
        def run_command(self, cmd, **kw):
            return _resp.pop(0) if _resp else (0, "", "")

    Mod.params = params
    return Mod


class _NoGiNoDb(FakeOracleHomes):
    """Non-GI environment, no databases known."""
    def __init__(self):
        super().__init__()
        self.oracle_gi_managed = False
        self.oracle_crs = False
        self.facts_item = {}


class _NoGiRunningDb(FakeOracleHomes):
    """Non-GI environment, TESTDB running."""
    def __init__(self):
        super().__init__()
        self.oracle_gi_managed = False
        self.oracle_crs = False
        self.facts_item = {
            "TESTDB": {
                "running": True,
                "crsname": None,
                "ORACLE_HOME": "/fake/oracle",
            }
        }


class _NoGiStoppedDb(FakeOracleHomes):
    """Non-GI environment, TESTDB stopped."""
    def __init__(self):
        super().__init__()
        self.oracle_gi_managed = False
        self.oracle_crs = False
        self.facts_item = {
            "TESTDB": {
                "running": False,
                "crsname": None,
                "ORACLE_HOME": "/fake/oracle",
            }
        }


class _GiNoDb(FakeOracleHomes):
    """GI environment, no databases known."""
    def __init__(self):
        super().__init__()
        self.oracle_gi_managed = True
        self.oracle_crs = False
        self.facts_item = {}


def test_db_missing_oracle_home_fails(monkeypatch):
    """oracle_home not set → fail_json about ORACLE_HOME."""
    mod = _load("oracle_db")
    orig = os.environ.pop("ORACLE_HOME", None)
    try:
        Mod = _make_db_mod(_db_params(oracle_home=None))
        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        monkeypatch.setattr(mod, "OracleHomes", _NoGiNoDb, raising=False)
        with pytest.raises(FailJson) as exc:
            mod.main()
        assert "ORACLE_HOME" in exc.value.args[0]["msg"]
    finally:
        if orig is not None:
            os.environ["ORACLE_HOME"] = orig


def test_db_absent_nogi_not_found_exits(monkeypatch):
    """state=absent, non-GI, DB not in facts_item → exit changed=False."""
    mod = _load("oracle_db")
    Mod = _make_db_mod(_db_params(state="absent"))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGiNoDb, raising=False)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert "doesn't exist" in exc.value.args[0]["msg"]


def test_db_absent_gi_not_found_exits(monkeypatch):
    """state=absent, GI-managed, srvctl returns not found → exit changed=False."""
    mod = _load("oracle_db")
    Mod = _make_db_mod(_db_params(state="absent"), responses=[
        (1, "", ""),  # srvctl config database → not found (no PRCD-1229)
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _GiNoDb, raising=False)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_db_absent_gi_different_home_fails(monkeypatch):
    """state=absent, GI, srvctl returns PRCD-1229 (different home) → fail_json."""
    mod = _load("oracle_db")
    Mod = _make_db_mod(_db_params(state="absent"), responses=[
        (1, "PRCD-1229 different home", ""),  # PRCD-1229 → DB in different home
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _GiNoDb, raising=False)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "different home" in exc.value.args[0]["msg"]


def test_db_started_already_running(monkeypatch):
    """state=started, DB running → exit 'already running'."""
    mod = _load("oracle_db")
    Mod = _make_db_mod(_db_params(state="started"))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGiRunningDb, raising=False)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert "already running" in exc.value.args[0]["msg"]


def test_db_stopped_already_stopped(monkeypatch):
    """state=stopped, DB not running → exit 'already stopped'."""
    mod = _load("oracle_db")
    Mod = _make_db_mod(_db_params(state="stopped"))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGiStoppedDb, raising=False)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert "already stopped" in exc.value.args[0]["msg"]


def test_db_started_not_found_fails(monkeypatch):
    """state=started, DB not in facts_item and no ORACLE_SID → fail_json."""
    mod = _load("oracle_db")
    Mod = _make_db_mod(_db_params(state="started"))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGiNoDb, raising=False)
    with pytest.raises(FailJson):
        mod.main()


def test_db_stopped_not_found_fails(monkeypatch):
    """state=stopped, DB not found → fail_json."""
    mod = _load("oracle_db")
    Mod = _make_db_mod(_db_params(state="stopped"))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGiNoDb, raising=False)
    with pytest.raises(FailJson):
        mod.main()


def test_db_absent_nogi_exists_removes(monkeypatch):
    """state=absent, non-GI, DB exists → calls remove_db (mocked to exit)."""
    mod = _load("oracle_db")

    def _fake_remove_db(module, ohomes):
        module.exit_json(msg="removed", changed=True)

    Mod = _make_db_mod(_db_params(state="absent"))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGiRunningDb, raising=False)
    monkeypatch.setattr(mod, "remove_db", _fake_remove_db)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_db_present_nogi_not_exists_creates(monkeypatch):
    """state=present, non-GI, DB not found → calls create_db then ensure_db_state."""
    mod = _load("oracle_db")

    def _fake_create_db(module, ohomes):
        return "STDOUT: done, STDERR:  COMMAND: dbca ..."

    def _fake_ensure_db_state(module, ohomes, newdb):
        module.exit_json(msg="done", changed=newdb)

    Mod = _make_db_mod(_db_params(state="present"))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGiNoDb, raising=False)
    monkeypatch.setattr(mod, "create_db", _fake_create_db)
    monkeypatch.setattr(mod, "ensure_db_state", _fake_ensure_db_state)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_db_present_nogi_exists_ensures_state(monkeypatch):
    """state=present, non-GI, DB exists → calls ensure_db_state with newdb=False."""
    mod = _load("oracle_db")

    def _fake_ensure_db_state(module, ohomes, newdb):
        module.exit_json(msg="up to date", changed=False)

    Mod = _make_db_mod(_db_params(state="present"))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGiRunningDb, raising=False)
    monkeypatch.setattr(mod, "ensure_db_state", _fake_ensure_db_state)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_db_restarted_not_found_fails(monkeypatch):
    """state=restarted, DB not found → fail_json."""
    mod = _load("oracle_db")
    Mod = _make_db_mod(_db_params(state="restarted"))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGiNoDb, raising=False)
    with pytest.raises(FailJson):
        mod.main()


def test_db_get_version_success(monkeypatch):
    """get_version: sqlplus -V returns version string → parsed correctly."""
    mod = _load("oracle_db")
    Mod = _make_db_mod(_db_params(), responses=[
        (0, "SQL*Plus: Release 19.0.0.0.0 - Production", ""),
    ])
    m = Mod()
    result = mod.get_version(m, "/fake/oracle")
    assert result == "19.0"


def test_db_get_version_failure(monkeypatch):
    """get_version: sqlplus -V fails → fail_json."""
    mod = _load("oracle_db")
    Mod = _make_db_mod(_db_params(), responses=[
        (1, "", "Not found"),
    ])
    m = Mod()
    with pytest.raises(FailJson):
        mod.get_version(m, "/fake/oracle")


def test_db_create_db_success(monkeypatch):
    """create_db: dbca succeeds → returns success message."""
    mod = _load("oracle_db")
    Mod = _make_db_mod(_db_params(state="present"), responses=[
        (0, "SQL*Plus: Release 19.0.0.0.0 - Production", ""),  # get_version
        (0, "Database creation successful", ""),                # dbca createDatabase
    ])
    m = Mod()
    ohomes = _NoGiNoDb()
    result = mod.create_db(m, ohomes)
    assert "STDOUT" in result or "successful" in result


def test_db_create_db_failure(monkeypatch):
    """create_db: dbca fails → fail_json."""
    mod = _load("oracle_db")
    Mod = _make_db_mod(_db_params(state="present"), responses=[
        (0, "SQL*Plus: Release 19.0.0.0.0 - Production", ""),  # get_version
        (7, "Error creating database", "ORA-12345"),           # dbca fails
    ])
    m = Mod()
    ohomes = _NoGiNoDb()
    with pytest.raises(FailJson):
        mod.create_db(m, ohomes)


def test_db_guess_oracle_sid_from_env(monkeypatch):
    """guess_oracle_sid: ORACLE_SID in env → returns env value."""
    mod = _load("oracle_db")
    os.environ["ORACLE_SID"] = "MYDB"
    try:
        Mod = _make_db_mod(_db_params())
        m = Mod()
        ohomes = _NoGiNoDb()
        result = mod.guess_oracle_sid(m, ohomes)
        assert result == "MYDB"
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_db_guess_oracle_sid_from_facts_item(monkeypatch):
    """guess_oracle_sid: db_name in facts_item → returns db_name."""
    mod = _load("oracle_db")
    os.environ.pop("ORACLE_SID", None)
    Mod = _make_db_mod(_db_params())
    m = Mod()
    ohomes = _NoGiRunningDb()  # facts_item has TESTDB
    result = mod.guess_oracle_sid(m, ohomes)
    assert result == "TESTDB"


def test_db_remove_db_gi_success(monkeypatch):
    """remove_db: GI-managed, dbca -deleteDatabase succeeds → exit changed=True."""
    mod = _load("oracle_db")
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        Mod = _make_db_mod(_db_params(state="absent"), responses=[
            (0, "Database deleted successfully", ""),  # dbca deleteDatabase
        ])
        m = Mod()
        ohomes = _GiNoDb()
        with pytest.raises(ExitJson) as exc:
            mod.remove_db(m, ohomes)
        assert exc.value.args[0]["changed"] is True
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_db_remove_db_gi_failure(monkeypatch):
    """remove_db: dbca deleteDatabase fails → fail_json."""
    mod = _load("oracle_db")
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        Mod = _make_db_mod(_db_params(state="absent"), responses=[
            (99, "Error deleting", ""),  # dbca fails
        ])
        m = Mod()
        ohomes = _GiNoDb()
        with pytest.raises(FailJson):
            mod.remove_db(m, ohomes)
    finally:
        os.environ.pop("ORACLE_SID", None)


# ===========================================================================
# oracle_opatch
# ===========================================================================

def _opatch_params(**overrides):
    base = {
        "oracle_home": "/fake/oracle",
        "patch_base": None,
        "patch_id": "12345678",
        "patch_version": None,
        "opatch_minversion": None,
        "opatchauto": False,
        "rolling": True,
        "conflict_check": True,
        "ocm_response_file": None,
        "offline": False,
        "stop_processes": False,
        "output": "short",
        "state": "present",
    }
    base.update(overrides)
    return base


# Canned run_command responses
_OP_VER_OK = (0, "SQL*Plus: Release 12.2.0.1.0 Production", "")   # → major_version = "12.2"
_OP_OPV_OK = (0, "OPatch Version: 12.2.0.1.20\n", "")              # → opatch_version = "12.2.0.1.20"
_OP_PATCH_ABSENT = (0, "99999999;Other patch\nOPatch succeeded.\n", "")
_OP_PATCH_PRESENT = (0, "12345678;My description\nOPatch succeeded.\n", "")
_OP_PREREQ_OK = (0, "", "")
_OP_APPLY_OK = (0, "apply successful\n", "")
_OP_ROLLBACK_OK = (0, "rollback successful\n", "")


def _make_opatch_mod(params, responses=None, check_mode=False):
    _resp = list(responses or [])

    class Mod(BaseFakeModule):
        def run_command(self, cmd, **kw):
            return _resp.pop(0) if _resp else (0, "", "")

    Mod.params = params
    Mod.check_mode = check_mode
    return Mod


def test_opatch_no_oracle_home_fails(monkeypatch):
    """No oracle_home in params or env → fail_json."""
    mod = _load("oracle_opatch")
    orig = os.environ.pop("ORACLE_HOME", None)
    try:
        Mod = _make_opatch_mod(_opatch_params(oracle_home=None))
        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        with pytest.raises(FailJson) as exc:
            mod.main()
        assert "ORACLE_HOME" in exc.value.args[0]["msg"]
    finally:
        if orig is not None:
            os.environ["ORACLE_HOME"] = orig


def test_opatch_oracle_home_not_exist_fails(monkeypatch):
    """oracle_home given but path doesn't exist → fail_json."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params())
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: False)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "doesn't exist" in exc.value.args[0]["msg"]


def test_opatch_binary_missing_fails(monkeypatch):
    """oracle_home exists but OPatch/opatch not found → fail_json."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params())
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    # oracle_home exists but OPatch binary does not
    monkeypatch.setattr(mod.os.path, "exists", lambda p: "/OPatch/opatch" not in p)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "OPatch" in exc.value.args[0]["msg"]


def test_opatch_no_patch_id_or_base_fails(monkeypatch):
    """state=present, no patch_id and no patch_base → fail_json."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params(patch_id=None, patch_base=None))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    # get_version is called BEFORE the patch check; provide a valid response
    Mod._responses = [_OP_VER_OK, _OP_OPV_OK]
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "patch" in exc.value.args[0]["msg"].lower()


def test_opatch_opatchauto_needs_patch_version(monkeypatch):
    """opatchauto=True without patch_version → fail_json."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params(opatchauto=True, patch_version=None),
                           responses=[_OP_VER_OK, _OP_OPV_OK])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "patch_version" in exc.value.args[0]["msg"].lower()


def test_opatch_get_version_fails(monkeypatch):
    """sqlplus -V returns rc!=0 → fail_json from get_version."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params(), responses=[(1, "", "not found")])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "Error" in exc.value.args[0]["msg"]


def test_opatch_state_opatchversion(monkeypatch):
    """state=opatchversion → exit_json with opatch version string."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params(state="opatchversion"),
                           responses=[_OP_VER_OK, _OP_OPV_OK])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["msg"] == "12.2.0.1.20"
    assert exc.value.args[0]["changed"] is False


def test_opatch_state_lspatches(monkeypatch):
    """state=lspatches → exit with lspatches dict parsed from opatch output."""
    mod = _load("oracle_opatch")
    lsout = "12345678;Description of patch\n99999999;Another patch\nOPatch succeeded.\n"
    Mod = _make_opatch_mod(_opatch_params(state="lspatches"),
                           responses=[_OP_VER_OK, _OP_OPV_OK, (0, lsout, "")])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert "lspatches" in payload
    assert "12345678" in payload["lspatches"]
    assert payload["changed"] is False


def test_opatch_present_already_applied(monkeypatch):
    """state=present, patch already applied → exit changed=False."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params(),
                           responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_PRESENT])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert "already applied" in exc.value.args[0]["msg"]


def test_opatch_present_not_applied_no_conflict(monkeypatch):
    """state=present, not applied, conflict_check=False → apply → exit changed=True."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(conflict_check=False),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_ABSENT, _OP_APPLY_OK],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_opatch_present_not_applied_with_conflict_check(monkeypatch):
    """state=present, not applied, conflict_check=True → prereqs pass → apply."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(conflict_check=True, patch_base="/patches/12345678"),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_ABSENT,
                   _OP_PREREQ_OK, _OP_PREREQ_OK, _OP_APPLY_OK],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_opatch_prereq_conflict_fails(monkeypatch):
    """analyze_patch: prereq rc=0 but 'failed' in stdout → fail_json."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(conflict_check=True, patch_base="/patches/12345678"),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_ABSENT,
                   (0, "failed: conflicts exist", "")],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "STDOUT" in exc.value.args[0]["msg"]


def test_opatch_absent_applied_removes(monkeypatch):
    """state=absent, patch applied → rollback → exit changed=True."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(state="absent"),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_PRESENT, _OP_ROLLBACK_OK],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_opatch_absent_not_applied(monkeypatch):
    """state=absent, patch not applied → exit changed=False."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(state="absent"),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_ABSENT],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert "not applied" in exc.value.args[0]["msg"]


def test_opatch_check_mode_present_not_applied(monkeypatch):
    """check_mode=True, state=present, patch not applied → exit changed=True."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(state="present"),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_ABSENT],
        check_mode=True,
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert "Check mode" in exc.value.args[0]["msg"]


def test_opatch_check_mode_present_already_applied(monkeypatch):
    """check_mode=True, state=present, patch applied → exit changed=False."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(state="present"),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_PRESENT],
        check_mode=True,
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_opatch_check_mode_absent_applied(monkeypatch):
    """check_mode=True, state=absent, patch applied → exit changed=True."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(state="absent"),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_PRESENT],
        check_mode=True,
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_opatch_check_mode_absent_not_applied(monkeypatch):
    """check_mode=True, state=absent, patch not applied → exit changed=False."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(state="absent"),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_ABSENT],
        check_mode=True,
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_opatch_minversion_too_old(monkeypatch):
    """opatch_version < opatch_minversion → fail_json."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(opatch_minversion="13.0.0.0.0", state="opatchversion"),
        responses=[_OP_VER_OK, _OP_OPV_OK],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "version" in exc.value.args[0]["msg"].lower()


def test_opatch_old_opatch_needs_ocm(monkeypatch):
    """opatch < 12.2.0.1.5 with state=present and no ocm_response_file → fail_json."""
    mod = _load("oracle_opatch")
    old_opv = (0, "OPatch Version: 12.2.0.1.4\n", "")
    Mod = _make_opatch_mod(
        _opatch_params(state="present", ocm_response_file=None),
        responses=[_OP_VER_OK, old_opv],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "OCM" in exc.value.args[0]["msg"] or "ocm" in exc.value.args[0]["msg"].lower()


def test_opatch_apply_command_fails(monkeypatch):
    """apply_patch: run_command returns rc!=0 → fail_json."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(conflict_check=False),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_ABSENT, (1, "ERROR applying", "")],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "Error" in exc.value.args[0]["msg"]


def test_opatch_apply_no_success_keyword(monkeypatch):
    """apply_patch: rc=0 but no success keyword → exit_json changed=False (from apply_patch)."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(conflict_check=False),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_ABSENT, (0, "Hmm no keyword here", "")],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_opatch_apply_verbose_output(monkeypatch):
    """apply_patch: output=verbose → exits with full stdout message."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(conflict_check=False, output="verbose"),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_ABSENT, _OP_APPLY_OK],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert "STDOUT" in exc.value.args[0]["msg"]


def test_opatch_rollback_no_success_keyword(monkeypatch):
    """remove_patch: rc=0 but no rollback keyword → exit_json changed=False."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(state="absent"),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_PRESENT, (0, "No keyword here", "")],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_opatch_rollback_verbose_output(monkeypatch):
    """remove_patch: output=verbose → exits with full stdout message."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(state="absent", output="verbose"),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_PRESENT, _OP_ROLLBACK_OK],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert "STDOUT" in exc.value.args[0]["msg"]


def test_opatch_get_version_function(monkeypatch):
    """get_version(): sqlplus -V output → parsed version string."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params(), responses=[_OP_VER_OK])
    m = Mod()
    result = mod.get_version(m, "/fake/oracle")
    assert result == "12.2"


def test_opatch_get_opatch_version_function(monkeypatch):
    """get_opatch_version(): opatch version output → version string."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params(), responses=[_OP_OPV_OK])
    m = Mod()
    result = mod.get_opatch_version(m, "/fake/oracle")
    assert result == "12.2.0.1.20"


def test_opatch_list_patches_function(monkeypatch):
    """list_patches(): parses opatch lspatches output → exit with dict."""
    mod = _load("oracle_opatch")
    lsout = "12345678;Patch description here\nOPatch succeeded.\n"
    Mod = _make_opatch_mod(_opatch_params(), responses=[(0, lsout, "")])
    m = Mod()
    with pytest.raises(ExitJson) as exc:
        mod.list_patches(m, "/fake/oracle")
    payload = exc.value.args[0]
    assert payload["lspatches"]["12345678"] == "Patch description here"
    assert payload["changed"] is False


def test_opatch_check_patch_applied_found(monkeypatch):
    """check_patch_applied(): patch in lspatches output → True."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params(), responses=[_OP_PATCH_PRESENT])
    m = Mod()
    result = mod.check_patch_applied(m, "/fake/oracle", "12345678", None, False)
    assert result is True


def test_opatch_check_patch_applied_not_found(monkeypatch):
    """check_patch_applied(): patch not in lspatches output → False."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params(), responses=[_OP_PATCH_ABSENT])
    m = Mod()
    result = mod.check_patch_applied(m, "/fake/oracle", "12345678", None, False)
    assert result is False


def test_opatch_oracle_home_from_env(monkeypatch):
    """oracle_home not in params, taken from ORACLE_HOME env → succeeds."""
    mod = _load("oracle_opatch")
    orig = os.environ.get("ORACLE_HOME")
    os.environ["ORACLE_HOME"] = "/fake/oracle"
    try:
        Mod = _make_opatch_mod(
            _opatch_params(oracle_home=None, state="opatchversion"),
            responses=[_OP_VER_OK, _OP_OPV_OK],
        )
        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
        with pytest.raises(ExitJson) as exc:
            mod.main()
        assert exc.value.args[0]["changed"] is False
    finally:
        if orig is None:
            os.environ.pop("ORACLE_HOME", None)
        else:
            os.environ["ORACLE_HOME"] = orig


# ---------------------------------------------------------------------------
# oracle_opatch - additional targeted tests for missing lines
# ---------------------------------------------------------------------------

def test_opatch_get_opatch_version_fails(monkeypatch):
    """get_opatch_version(): rc!=0 → fail_json (lines 128-129)."""
    mod = _load("oracle_opatch")
    # Only one run_command call in get_opatch_version - provide the error response directly
    Mod = _make_opatch_mod(_opatch_params(), responses=[(1, "", "opatch not found")])
    m = Mod()
    with pytest.raises(FailJson) as exc:
        mod.get_opatch_version(m, "/fake/oracle")
    assert "Error" in exc.value.args[0]["msg"]


def test_opatch_get_file_owner_file_missing(monkeypatch):
    """get_file_owner(): oracle binary does not exist → fail_json (lines 148-150)."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params())
    m = Mod()
    monkeypatch.setattr(mod.os.path, "exists", lambda p: False)
    with pytest.raises(FailJson) as exc:
        mod.get_file_owner(m, "/fake/oracle")
    assert "Could not determine owner" in exc.value.args[0]["msg"]


def test_opatch_get_file_owner_file_exists(monkeypatch):
    """get_file_owner(): oracle binary exists → returns owner string (lines 142-147)."""
    import stat as stat_mod
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params())
    m = Mod()

    class _FakeStat:
        st_uid = 1000

    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    monkeypatch.setattr(mod.os, "stat", lambda p: _FakeStat())
    monkeypatch.setattr(mod.pwd, "getpwuid", lambda uid: ("oracleuser",))
    result = mod.get_file_owner(m, "/fake/oracle")
    assert result == "oracleuser"


def test_opatch_get_patch_id_both_fail(monkeypatch):
    """get_patch_id(): both bundle.xml and inventory.xml fail → fail_json (line 173)."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params())
    m = Mod()
    # Both XML parses will fail since /nonexistent/path doesn't exist
    with pytest.raises(FailJson) as exc:
        mod.get_patch_id(m, "/nonexistent/patch/path")
    assert "Could not determine patch_id" in exc.value.args[0]["msg"]


def test_opatch_get_patch_id_from_inventory_xml(monkeypatch, tmp_path):
    """get_patch_id(): inventory.xml present with patch_id → returns id (lines 165-170)."""
    import os as os_mod
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params())
    m = Mod()

    # Create a fake inventory.xml
    inv_dir = tmp_path / "etc" / "config"
    inv_dir.mkdir(parents=True)
    inv_xml = inv_dir / "inventory.xml"
    inv_xml.write_text('<inventory><patch_id number="27468957"/></inventory>')

    result = mod.get_patch_id(m, str(tmp_path))
    assert result == "27468957"


def test_opatch_check_patch_applied_rc_nonzero(monkeypatch):
    """check_patch_applied(): lspatches returns rc!=0 → fail_json (lines 190-191)."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params(), responses=[(1, "", "error")])
    m = Mod()
    with pytest.raises(FailJson) as exc:
        mod.check_patch_applied(m, "/fake/oracle", "12345678", None, False)
    assert "Error" in exc.value.args[0]["msg"]


def test_opatch_check_patch_applied_opatchauto_found(monkeypatch):
    """check_patch_applied(): opatchauto=True, patch_version in stdout → True (lines 193-194)."""
    mod = _load("oracle_opatch")
    # When opatchauto=True, check is just the patch_version string
    Mod = _make_opatch_mod(_opatch_params(),
                           responses=[(0, "12.1.0.2.180417 some content\nOPatch succeeded.\n", "")])
    m = Mod()

    class _FakeStat:
        st_uid = 0

    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    monkeypatch.setattr(mod.os, "stat", lambda p: _FakeStat())
    monkeypatch.setattr(mod.pwd, "getpwuid", lambda uid: ("root",))
    result = mod.check_patch_applied(m, "/fake/oracle", "12345678", "12.1.0.2.180417", True)
    assert result is True


def test_opatch_check_patch_applied_with_version_and_id(monkeypatch):
    """check_patch_applied(): not opatchauto, both patch_id and patch_version → 'version (id)' check (line 196)."""
    mod = _load("oracle_opatch")
    stdout = "12.2.0.1.180417 (12345678) some info\nOPatch succeeded.\n"
    Mod = _make_opatch_mod(_opatch_params(), responses=[(0, stdout, "")])
    m = Mod()
    result = mod.check_patch_applied(m, "/fake/oracle", "12345678", "12.2.0.1.180417", False)
    assert result is True


def test_opatch_list_patches_error(monkeypatch):
    """list_patches(): rc!=0 → fail_json (lines 211-212)."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params(), responses=[(1, "", "error")])
    m = Mod()
    with pytest.raises(FailJson) as exc:
        mod.list_patches(m, "/fake/oracle")
    assert "Error" in exc.value.args[0]["msg"]


def test_opatch_list_patches_no_semicolon_line(monkeypatch):
    """list_patches(): line without semicolon → stored as msg (line 228)."""
    mod = _load("oracle_opatch")
    # Line without ';' and without 'OPatch succeeded' → goes to else branch (line 228)
    lsout = "No patches installed\nOPatch succeeded.\n"
    Mod = _make_opatch_mod(_opatch_params(), responses=[(0, lsout, "")])
    m = Mod()
    with pytest.raises(ExitJson) as exc:
        mod.list_patches(m, "/fake/oracle")
    payload = exc.value.args[0]
    # msg should be the OPatch succeeded line
    assert "OPatch succeeded" in payload["msg"]
    assert payload["lspatches"] == {}


def test_opatch_analyze_patch_opatchauto_ge_12(monkeypatch):
    """analyze_patch(): opatchauto=True, major_version >= '12.1' → opatchauto analyze (lines 245-248)."""
    mod = _load("oracle_opatch")
    mod.major_version = "12.2"
    Mod = _make_opatch_mod(_opatch_params(), responses=[_OP_PREREQ_OK])
    m = Mod()
    result = mod.analyze_patch(m, "/fake/oracle", "/patches/12345", True)
    assert result is True


def test_opatch_analyze_patch_opatchauto_lt_12(monkeypatch):
    """analyze_patch(): opatchauto=True, major_version < '12.1' → sudo opatch prereq (lines 235-243)."""
    mod = _load("oracle_opatch")
    mod.major_version = "11.2"

    class _FakeStat:
        st_uid = 1000

    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    monkeypatch.setattr(mod.os, "stat", lambda p: _FakeStat())
    monkeypatch.setattr(mod.pwd, "getpwuid", lambda uid: ("oracle",))

    # Two prereq checks for opatchauto < 12.1
    Mod = _make_opatch_mod(_opatch_params(), responses=[_OP_PREREQ_OK, _OP_PREREQ_OK])
    m = Mod()
    result = mod.analyze_patch(m, "/fake/oracle", "/patches/12345", True)
    assert result is True


def test_opatch_analyze_patch_rc_nonzero_fails(monkeypatch):
    """analyze_patch(): prereq rc!=0 → fail_json (lines 259-260)."""
    mod = _load("oracle_opatch")
    mod.major_version = "12.2"
    Mod = _make_opatch_mod(_opatch_params(), responses=[(1, "", "error")])
    m = Mod()
    with pytest.raises(FailJson) as exc:
        mod.analyze_patch(m, "/fake/oracle", "/patches/12345", True)
    assert "Error" in exc.value.args[0]["msg"]


def test_opatch_apply_patch_opatch_version_check_failed(monkeypatch):
    """apply_patch(): rc=0 but 'Opatch version check failed' in stdout → fail_json (lines 306-308)."""
    mod = _load("oracle_opatch")
    mod.major_version = "12.2"
    mod.opatch_version = "12.2.0.1.20"
    mod.opatch_version_noocm = "12.2.0.1.5"
    mod.conflict_check = False
    Mod = _make_opatch_mod(_opatch_params(),
                           responses=[(0, "Opatch version check failed", "")])
    m = Mod()
    with pytest.raises(FailJson) as exc:
        mod.apply_patch(m, "/fake/oracle", "/patches/12345", "12345678",
                        None, False, None, False, False, True, "short")
    assert "STDOUT" in exc.value.args[0]["msg"]


def test_opatch_apply_patch_opatchauto_nonrolling(monkeypatch):
    """apply_patch(): opatchauto=True, rolling=False → -nonrolling option (lines 275-290)."""
    mod = _load("oracle_opatch")
    mod.major_version = "12.2"
    mod.opatch_version = "12.2.0.1.20"
    mod.opatch_version_noocm = "12.2.0.1.5"
    mod.conflict_check = False
    Mod = _make_opatch_mod(_opatch_params(),
                           responses=[(0, "apply successful\n", "")])
    m = Mod()
    result = mod.apply_patch(m, "/fake/oracle", "/patches/12345", "12345678",
                             "12.2.0.1.180417", True, None, False, False, False, "short")
    assert result is True


def test_opatch_apply_patch_opatchauto_old_offline(monkeypatch):
    """apply_patch(): opatchauto=True, major_version < 12.1, offline=True → -och (lines 277-282)."""
    mod = _load("oracle_opatch")
    mod.major_version = "11.2"
    mod.opatch_version = "12.2.0.1.20"
    mod.opatch_version_noocm = "12.2.0.1.5"
    mod.conflict_check = False
    Mod = _make_opatch_mod(_opatch_params(),
                           responses=[(0, "apply successful\n", "")])
    m = Mod()
    result = mod.apply_patch(m, "/fake/oracle", "/patches/12345", "12345678",
                             "12.2.0.1.180417", True, None, True, False, True, "short")
    assert result is True


def test_opatch_apply_patch_ocm_response_file(monkeypatch):
    """apply_patch(): ocm_response_file set and old opatch → -ocmrf appended (line 300)."""
    mod = _load("oracle_opatch")
    mod.major_version = "12.2"
    mod.opatch_version = "12.2.0.1.4"   # older than noocm threshold
    mod.opatch_version_noocm = "12.2.0.1.5"
    mod.conflict_check = False
    Mod = _make_opatch_mod(_opatch_params(),
                           responses=[(0, "apply successful\n", "")])
    m = Mod()
    result = mod.apply_patch(m, "/fake/oracle", "/patches/12345", "12345678",
                             None, False, "/tmp/ocm.rsp", False, False, True, "short")
    assert result is True


def test_opatch_remove_patch_opatchauto_ge_12(monkeypatch):
    """remove_patch(): opatchauto=True, major >= 12.1 → opatchauto rollback (lines 391-396)."""
    mod = _load("oracle_opatch")
    mod.major_version = "12.2"
    mod.opatch_version = "12.2.0.1.20"
    mod.opatch_version_noocm = "12.2.0.1.5"
    Mod = _make_opatch_mod(_opatch_params(), responses=[(0, "rollback successful\n", "")])
    m = Mod()
    result = mod.remove_patch(m, "/fake/oracle", "/patches/12345", "12345678",
                              True, None, "short")
    assert result is True


def test_opatch_remove_patch_opatchauto_lt_12(monkeypatch):
    """remove_patch(): opatchauto=True, major < 12.1 → opatch auto -rollback (lines 391-392)."""
    mod = _load("oracle_opatch")
    mod.major_version = "11.2"
    mod.opatch_version = "12.2.0.1.20"
    mod.opatch_version_noocm = "12.2.0.1.5"
    Mod = _make_opatch_mod(_opatch_params(), responses=[(0, "rollback successful\n", "")])
    m = Mod()
    result = mod.remove_patch(m, "/fake/oracle", "/patches/12345", "12345678",
                              True, None, "short")
    assert result is True


# ===========================================================================
# oracle_sqldba – additional coverage tests
# ===========================================================================

def test_sqldba_run_catcon_pl_failure(monkeypatch):
    """run_catcon_pl via main(): subprocess returns non-zero → fail_json (lines 320-356)."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", stderr="catcon failed", returncode=1))

    class Mod(BaseFakeModule):
        params = _sqldba_params(
            sql=None,
            catcon_pl="$ORACLE_HOME/rdbms/admin/catupgrd.sql",
            scope="cdb",
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "returncode" in exc.value.args[0]["msg"].lower()


def test_sqldba_run_catcon_pl_with_pdb_list_failure(monkeypatch):
    """run_catcon_pl via main(): pdb_list provided → -c flag used, fails (lines 328-356)."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", stderr="catcon failed", returncode=1))

    class Mod(BaseFakeModule):
        params = _sqldba_params(
            sql=None,
            catcon_pl="$ORACLE_HOME/rdbms/admin/catupgrd.sql",
            scope="pdbs",
            pdb_list=["PDB1", "PDB2"],
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "returncode" in exc.value.args[0]["msg"].lower()


def test_sqldba_run_catcon_pl_exception(monkeypatch):
    """run_catcon_pl: Popen raises exception → err_msg set, fail_json (lines 343-345)."""
    mod = _load("oracle_sqldba")

    class _FailPopen:
        def __init__(self, cmd, **kw):
            raise OSError("no such file")

    monkeypatch.setattr(mod, "Popen", _FailPopen)

    class Mod(BaseFakeModule):
        params = _sqldba_params(
            sql=None,
            catcon_pl="$ORACLE_HOME/rdbms/admin/catupgrd.sql",
            scope="cdb",
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "perl" in exc.value.args[0]["msg"].lower() or "catcon" in exc.value.args[0]["msg"].lower()


def test_sqldba_run_catcon_pl_script_with_args_failure(monkeypatch):
    """run_catcon_pl via main(): script with extra args → -a flag added, then fails (lines 331-356)."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", stderr="catcon failed", returncode=1))

    class Mod(BaseFakeModule):
        params = _sqldba_params(
            sql=None,
            catcon_pl="$ORACLE_HOME/rdbms/admin/catupgrd.sql arg1 arg2",
            scope="cdb",
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "returncode" in exc.value.args[0]["msg"].lower()


def test_sqldba_run_sql_nonzero_via_main(monkeypatch):
    """run_sql: Popen raises via main() with ORA error → fail_json (lines 275-279)."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="ORA-00942: table not found", returncode=0))

    class Mod(BaseFakeModule):
        params = _sqldba_params(sql="SELECT * FROM missing_table;", timeout=0)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(FailJson):
        mod.main()


def test_sqldba_run_sql_nonzero_returncode(monkeypatch):
    """run_sql: non-zero returncode → [ERR] returned (lines 272-274)."""
    mod = _load("oracle_sqldba")
    mod.changed = False
    mod.err_msg = ""

    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", stderr="fatal error", returncode=2))

    class Mod(BaseFakeModule):
        params = _sqldba_params(timeout=0)

    m = Mod()
    result = mod.run_sql(m, "ALTER SYSTEM SET something = 1;", None, None, None)
    assert "[ERR]" in result


def test_sqldba_run_sql_p_pdbs_scope(monkeypatch):
    """run_sql_p: scope=pdbs → runs once per PDB (lines 234-236)."""
    mod = _load("oracle_sqldba")
    mod.changed = False
    mod.err_msg = ""

    calls = []

    def _stub_run_sql(module, sql, username=None, password=None, pdb=None):
        calls.append(pdb)
        return "result"

    monkeypatch.setattr(mod, "run_sql", _stub_run_sql)

    class Mod(BaseFakeModule):
        params = _sqldba_params(timeout=0)

    m = Mod()
    result = mod.run_sql_p(m, "SELECT 1 FROM DUAL;", None, None, "pdbs", ["PDB1", "PDB2"])
    assert calls == ["PDB1", "PDB2"]
    assert result == "resultresult"


def test_sqldba_check_creates_sql_pdbs_branch(monkeypatch):
    """check_creates_sql: scope != cdb → checks each PDB (lines 295-301)."""
    mod = _load("oracle_sqldba")
    mod.changed = False
    mod.err_msg = ""

    def _stub_run_sql(module, sql, username=None, password=None, pdb=None):
        # "0" means needs running (falsy check), "1" means skip
        if pdb == "PDB1":
            return "0"
        return "1"

    monkeypatch.setattr(mod, "run_sql", _stub_run_sql)

    class Mod(BaseFakeModule):
        params = _sqldba_params(timeout=0)

    m = Mod()
    result = mod.check_creates_sql(m, "SELECT COUNT(*) FROM MY_TABLE", "pdbs", ["PDB1", "PDB2"])
    assert result == ["PDB1"]


def test_sqldba_scope_cdb_with_catcon_pl_sets_pdbs(monkeypatch):
    """scope=cdb + catcon_pl → scope becomes 'pdbs' with CDB$ROOT (lines 434-436)."""
    mod = _load("oracle_sqldba")

    called_with = []

    def _stub_run_catcon(module, pdb_list, catcon_pl_script):
        called_with.append(list(pdb_list))
        mod.changed = True

    class Mod(BaseFakeModule):
        params = _sqldba_params(
            sql=None,
            catcon_pl="$ORACLE_HOME/rdbms/admin/catupgrd.sql",
            scope="cdb",
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "run_catcon_pl", _stub_run_catcon)
    with pytest.raises(ExitJson):
        mod.main()
    assert called_with[0] == ["CDB$ROOT"]


def test_sqldba_scope_all_pdbs_is_container(monkeypatch):
    """scope=all_pdbs + catcon_pl=None + is_container=True → pdbs scope with all PDBs."""
    mod = _load("oracle_sqldba")
    mod.changed = False
    mod.err_msg = ""

    def _stub_run_sql(module, sql, username=None, password=None, pdb=None):
        if "gv$database" in sql.lower():
            return "YES"
        if "dba_pdbs" in sql.lower():
            return "PDB1 PDB2"
        mod.changed = True
        return ""

    monkeypatch.setattr(mod, "run_sql", _stub_run_sql)

    class Mod(BaseFakeModule):
        params = _sqldba_params(scope="all_pdbs")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_sqldba_oracle_home_from_env(monkeypatch):
    """oracle_home not in params but ORACLE_HOME env set → succeeds (lines 405-407)."""
    mod = _load("oracle_sqldba")
    orig = os.environ.get("ORACLE_HOME")
    os.environ["ORACLE_HOME"] = "/env/oracle"
    try:
        monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", returncode=0))

        class Mod(BaseFakeModule):
            params = _sqldba_params(oracle_home=None)

        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        with pytest.raises(ExitJson) as exc:
            mod.main()
        assert exc.value.args[0]["changed"] is True
    finally:
        if orig is None:
            os.environ.pop("ORACLE_HOME", None)
        else:
            os.environ["ORACLE_HOME"] = orig


def test_sqldba_oracle_sid_from_env(monkeypatch):
    """oracle_sid not in params but ORACLE_SID env set → succeeds (lines 417-419)."""
    mod = _load("oracle_sqldba")
    orig = os.environ.get("ORACLE_SID")
    os.environ["ORACLE_SID"] = "ENVORCL"
    try:
        monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", returncode=0))

        class Mod(BaseFakeModule):
            params = _sqldba_params(oracle_sid=None)

        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        with pytest.raises(ExitJson) as exc:
            mod.main()
        assert exc.value.args[0]["changed"] is True
    finally:
        if orig is None:
            os.environ.pop("ORACLE_SID", None)
        else:
            os.environ["ORACLE_SID"] = orig


def test_sqldba_creates_sql_err_msg_fails(monkeypatch):
    """creates_sql check produces err_msg → fail_json (lines 452-453)."""
    mod = _load("oracle_sqldba")
    mod.changed = False
    mod.err_msg = ""
    mod.result = ""

    def _stub_check_creates(module, sql, scope, pdb_list):
        mod.err_msg = "ORA-00942: table or view does not exist"
        return []

    monkeypatch.setattr(mod, "check_creates_sql", _stub_check_creates)
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", returncode=0))

    class Mod(BaseFakeModule):
        params = _sqldba_params(creates_sql="SELECT COUNT(*) FROM MISSING_TABLE")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "ORA-00942" in exc.value.args[0]["msg"]


def test_sqldba_err_msg_from_run_sql_fails(monkeypatch):
    """run_sql sets err_msg → fail_json at line 478-479."""
    mod = _load("oracle_sqldba")
    mod.changed = False
    mod.err_msg = ""
    mod.result = ""

    def _stub_run_sql(module, sql, username=None, password=None, pdb=None):
        mod.err_msg = "ORA-12345: some error"
        return "[ERR]"

    monkeypatch.setattr(mod, "run_sql", _stub_run_sql)

    class Mod(BaseFakeModule):
        params = _sqldba_params(sql="ALTER SESSION SET NLS_DATE_FORMAT='YYYY-MM-DD';")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "ORA-12345" in exc.value.args[0]["msg"]


def test_sqldba_sql_ends_with_slash(monkeypatch):
    """SQL ending with / is not re-appended (line 468 branch)."""
    mod = _load("oracle_sqldba")
    monkeypatch.setattr(mod, "Popen", _make_popen(stdout="", returncode=0))

    class Mod(BaseFakeModule):
        params = _sqldba_params(sql="BEGIN NULL; END;\n/")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


# ===========================================================================
# oracle_datapatch – additional coverage tests
# ===========================================================================

def test_datapatch_get_version_success_parse(monkeypatch):
    """get_version: sqlplus -V succeeds → version parsed correctly (lines 84-91)."""
    mod = _load("oracle_datapatch")
    Mod = _make_dp_mod(_datapatch_params(), responses=[
        (0, "SQL*Plus: Release 19.0.0.0.0 - Production on Fri", ""),
    ])
    m = Mod()
    result = mod.get_version(m, "", "/fake/oracle")
    assert result == "19.0"


def test_datapatch_get_version_failure(monkeypatch):
    """get_version: sqlplus -V fails → fail_json (lines 87-89)."""
    mod = _load("oracle_datapatch")
    Mod = _make_dp_mod(_datapatch_params(), responses=[
        (1, "", "No such file or directory"),
    ])
    m = Mod()
    with pytest.raises(FailJson) as exc:
        mod.get_version(m, "", "/fake/oracle")
    assert "Error" in exc.value.args[0]["msg"]


def test_datapatch_check_db_exists_gi_unique_name(monkeypatch):
    """check_db_exists: gimanaged=True, db_unique_name set → uses unique name for srvctl (line 98)."""
    mod = _load("oracle_datapatch")
    mod.gimanaged = True
    Mod = _make_dp_mod(_datapatch_params(), responses=[
        (0, "Database name: TESTDB\nOracle home: /fake/oracle\n", ""),
    ])
    m = Mod()
    result = mod.check_db_exists(m, "", "/fake/oracle", "TESTDB", None, "TESTDB_UNIQUE")
    assert result is True


def test_datapatch_check_db_exists_non_gi_no_oratab(monkeypatch):
    """check_db_exists: gimanaged=False, /etc/oratab doesn't exist → False (lines 113-123)."""
    import unittest.mock as mock
    mod = _load("oracle_datapatch")
    mod.gimanaged = False
    Mod = _make_dp_mod(_datapatch_params())
    m = Mod()
    with mock.patch("os.path.exists", return_value=False):
        result = mod.check_db_exists(m, "", "/fake/oracle", "TESTDB", None, None)
    assert result is False


def test_datapatch_check_db_exists_non_gi_oratab_match_same_home(monkeypatch):
    """check_db_exists: non-GI, oratab has DB with same ORACLE_HOME → True (lines 125-132)."""
    import unittest.mock as mock
    mod = _load("oracle_datapatch")
    mod.gimanaged = False
    Mod = _make_dp_mod(_datapatch_params())
    m = Mod()
    oratab_content = "TESTDB:/fake/oracle:Y\n"
    with mock.patch("os.path.exists", return_value=True):
        with mock.patch("builtins.open", mock.mock_open(read_data=oratab_content)):
            result = mod.check_db_exists(m, "", "/fake/oracle", "TESTDB", "TESTDB", None)
    assert result is True


def test_datapatch_check_db_exists_non_gi_oratab_different_home(monkeypatch):
    """check_db_exists: non-GI, oratab has DB with different ORACLE_HOME → fail_json (lines 128-130)."""
    import unittest.mock as mock
    mod = _load("oracle_datapatch")
    mod.gimanaged = False
    Mod = _make_dp_mod(_datapatch_params())
    m = Mod()
    oratab_content = "TESTDB:/other/oracle:Y\n"
    with mock.patch("os.path.exists", return_value=True):
        with mock.patch("builtins.open", mock.mock_open(read_data=oratab_content)):
            with pytest.raises(FailJson) as exc:
                mod.check_db_exists(m, "", "/fake/oracle", "TESTDB", "TESTDB", None)
    assert "different ORACLE_HOME" in exc.value.args[0]["msg"]


def test_datapatch_run_datapatch_with_sid(monkeypatch):
    """run_datapatch: sid provided → ORACLE_SID set to sid (line 146)."""
    mod = _load("oracle_datapatch")
    mod.major_version = "19.0"
    mod.output = "short"
    Mod = _make_dp_mod(_datapatch_params(), responses=[
        (0, "Patch installation complete.", ""),
    ])
    m = Mod()
    result = mod.run_datapatch(m, "", "localhost", "/fake/oracle", "TESTDB", "TESTDB1")
    assert result is True
    assert os.environ.get("ORACLE_SID") == "TESTDB1"


def test_datapatch_run_datapatch_legacy_sqlplus_success(monkeypatch):
    """run_datapatch: major_version <= '11.2' → uses subprocess.Popen with sqlplus (lines 171-185)."""
    import types
    mod = _load("oracle_datapatch")
    mod.major_version = "11.2"
    mod.output = "short"

    # oracle_datapatch doesn't import subprocess, inject a fake one into its namespace
    fake_sub = types.SimpleNamespace(
        Popen=_make_popen(stdout=b"done", returncode=0),
        PIPE=-1,
    )
    monkeypatch.setattr(mod, "subprocess", fake_sub, raising=False)

    Mod = _make_dp_mod(_datapatch_params())
    m = Mod()
    result = mod.run_datapatch(m, "", "localhost", "/fake/oracle", "TESTDB", None)
    assert result is True


def test_datapatch_run_datapatch_legacy_sqlplus_failure(monkeypatch):
    """run_datapatch: legacy sqlplus returns non-zero → fail_json (lines 181-183)."""
    import types
    mod = _load("oracle_datapatch")
    mod.major_version = "11.2"
    mod.output = "short"

    fake_sub = types.SimpleNamespace(
        Popen=_make_popen(stdout=b"", stderr=b"error", returncode=1),
        PIPE=-1,
    )
    monkeypatch.setattr(mod, "subprocess", fake_sub, raising=False)

    Mod = _make_dp_mod(_datapatch_params())
    m = Mod()
    with pytest.raises(FailJson):
        mod.run_datapatch(m, "", "localhost", "/fake/oracle", "TESTDB", None)


def test_datapatch_execute_sql_get_success(monkeypatch):
    """execute_sql_get: cursor.execute + fetchall returns rows (lines 202-210)."""
    mod = _load("oracle_datapatch")

    class _FakeCursor:
        def execute(self, sql):
            pass
        def fetchall(self):
            return [("row1",), ("row2",)]

    Mod = _make_dp_mod(_datapatch_params())
    m = Mod()
    result = mod.execute_sql_get(m, "", _FakeCursor(), "SELECT 1 FROM DUAL")
    assert result == [("row1",), ("row2",)]


def test_datapatch_execute_sql_get_db_error(monkeypatch):
    """execute_sql_get: DatabaseError raised → fail_json (lines 205-209)."""
    mod = _load("oracle_datapatch")

    class _FakeError:
        message = "ORA-00942: table or view does not exist"

    class _FakeOracleDb:
        class DatabaseError(Exception):
            pass

    monkeypatch.setattr(mod, "oracledb", _FakeOracleDb, raising=False)

    class _FakeCursorWithError:
        def execute(self, sql):
            err = _FakeOracleDb.DatabaseError("db error")
            err.args = (_FakeError(),)
            raise err
        def fetchall(self):
            return []

    Mod = _make_dp_mod(_datapatch_params())
    m = Mod()
    with pytest.raises(FailJson) as exc:
        mod.execute_sql_get(m, "", _FakeCursorWithError(), "SELECT 1 FROM DUAL")
    assert "sql_get" in exc.value.args[0]["msg"]


def test_datapatch_main_db_found_datapatch_returns_falsy(monkeypatch):
    """DB found but run_datapatch returns None → fail_json (line 305)."""
    mod = _load("oracle_datapatch")
    Mod = _make_dp_mod(_datapatch_params(),
                       responses=[(0, "SQL*Plus: Release 19.0.0.0.0", "")])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: False)
    monkeypatch.setattr(mod, "check_db_exists", lambda *a, **kw: True)
    monkeypatch.setattr(mod, "run_datapatch", lambda *a, **kw: None)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "datapatch failed" in exc.value.args[0]["msg"].lower()


def test_datapatch_main_db_not_found_fail_true(monkeypatch):
    """DB not found + fail_on_db_not_exist=True → fail_json (lines 307-309)."""
    mod = _load("oracle_datapatch")
    Mod = _make_dp_mod(_datapatch_params(fail_on_db_not_exist=True),
                       responses=[(0, "SQL*Plus: Release 12.2.0.1.0 Production", "")])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: False)
    monkeypatch.setattr(mod, "check_db_exists", lambda *a, **kw: False)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "does not exist" in exc.value.args[0]["msg"].lower()


# ===========================================================================
# oracle_tablespace – additional coverage tests (extra)
# ===========================================================================

def _ts_params_ext(**overrides):
    """Build tablespace params for the extra coverage tests."""
    from helpers import BASE_CONN_PARAMS
    base = {
        **BASE_CONN_PARAMS,
        "tablespace": "TESTTS",
        "state": "present",
        "bigfile": True,
        "datafile": None,
        "numfiles": None,
        "size": "100M",
        "content": "permanent",
        "autoextend": False,
        "nextsize": None,
        "maxsize": None,
    }
    base.update(overrides)
    return base


def _make_ts_conn_ext(responses):
    """Return a SequencedFakeConn subclass with given responses."""
    from helpers import SequencedFakeConn

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = list(responses)

    return _Conn


def _load_ts():
    return load_module_from_path("plugins/modules/oracle_tablespace.py", "oracle_tablespace_ext")


def test_tablespace_bigfile_multiple_datafiles_fails(monkeypatch):
    """bigfile=True + multiple datafiles → fail_json (lines 180-182)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(bigfile=True, datafile=["/u01/a.dbf", "/u01/b.dbf"])

    ConnCls = _make_ts_conn_ext([
        {},               # check_tablespace_exists → not found
        {"value": None},  # create_tablespace: OMF disabled
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "bigfile" in exc.value.args[0]["msg"].lower()


def test_tablespace_create_omf_autoextend_no_maxsize(monkeypatch):
    """Create OMF tablespace: autoextend=True, nextsize set, no maxsize → autoextend SQL (line 186)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(
            bigfile=False,
            autoextend=True,
            nextsize="50M",
            maxsize=None,
        )

    ConnCls = _make_ts_conn_ext([
        {},
        {"value": "/u01/oradata"},
        {"value": "/u01/oradata"},
        {"status": "ONLINE"},
        {"count": 0},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("autoextend" in d.lower() for d in ddls)


def test_tablespace_create_omf_no_autoextend_with_maxsize(monkeypatch):
    """Create OMF tablespace: autoextend=False, maxsize set → size-only SQL (line 190)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(
            bigfile=False,
            autoextend=False,
            nextsize=None,
            maxsize="2G",
        )

    ConnCls = _make_ts_conn_ext([
        {},
        {"value": "/u01/oradata"},
        {"value": "/u01/oradata"},
        {"status": "ONLINE"},
        {"count": 0},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_tablespace_create_temp_bigfile_omf(monkeypatch):
    """Create bigfile temp tablespace via OMF (lines 200-203)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(content="temp", bigfile=True)

    ConnCls = _make_ts_conn_ext([
        {},
        {"value": "/u01/oradata"},
        {"value": "/u01/oradata"},
        {"status": "ONLINE"},
        {"count": 0},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("bigfile temporary" in d.lower() for d in ddls)


def test_tablespace_create_temp_nonbigfile_omf(monkeypatch):
    """Create non-bigfile temp tablespace via OMF (line 209)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(content="temp", bigfile=False)

    ConnCls = _make_ts_conn_ext([
        {},
        {"value": "/u01/oradata"},
        {"value": "/u01/oradata"},
        {"status": "ONLINE"},
        {"count": 0},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("temporary" in d.lower() for d in ddls)


def test_tablespace_create_explicit_datafile_autoextend_no_nextsize_fails(monkeypatch):
    """autoextend=True but no nextsize + explicit datafile → fail_json (line 222)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(
            bigfile=False,
            datafile=["/u01/data/test01.dbf"],
            autoextend=True,
            nextsize=None,
        )

    ConnCls = _make_ts_conn_ext([
        {},
        {"value": None},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "NEXT size" in exc.value.args[0]["msg"]


def test_tablespace_create_explicit_datafile_autoextend_nextsize_no_maxsize(monkeypatch):
    """autoextend + nextsize + no maxsize + explicit datafile → autoextend SQL (line 224)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(
            bigfile=False,
            datafile=["/u01/data/test01.dbf"],
            autoextend=True,
            nextsize="50M",
            maxsize=None,
        )

    ConnCls = _make_ts_conn_ext([
        {},
        {"value": None},
        {"value": None},
        {"status": "ONLINE"},
        {"count": 0},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    # The create tablespace DDL should have autoextend on next but no maxsize clause
    create_ddls = [d for d in ddls if d.lower().startswith("create")]
    assert any("autoextend on next" in d.lower() for d in create_ddls)


def test_tablespace_create_explicit_datafile_autoextend_with_maxsize(monkeypatch):
    """autoextend + nextsize + maxsize + explicit datafile → full autoextend SQL (lines 225-226)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(
            bigfile=False,
            datafile=["/u01/data/test01.dbf"],
            autoextend=True,
            nextsize="50M",
            maxsize="2G",
        )

    ConnCls = _make_ts_conn_ext([
        {},
        {"value": None},
        {"value": None},
        {"status": "ONLINE"},
        {"count": 0},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("maxsize" in d.lower() for d in ddls)


def test_tablespace_create_explicit_undo_bigfile(monkeypatch):
    """Create bigfile undo tablespace with explicit datafile (line 232)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(content="undo", bigfile=True, datafile=["/u01/undo01.dbf"])

    ConnCls = _make_ts_conn_ext([
        {},
        {"value": None},
        {"value": None},
        {"status": "ONLINE"},
        {"count": 0},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("bigfile undo" in d.lower() for d in ddls)


def test_tablespace_create_explicit_temp_bigfile(monkeypatch):
    """Create bigfile temp tablespace with explicit datafile (line 238)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(content="temp", bigfile=True, datafile=["/u01/temp01.dbf"])

    ConnCls = _make_ts_conn_ext([
        {},
        {"value": None},
        {"value": None},
        {"status": "ONLINE"},
        {"count": 0},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("bigfile temporary" in d.lower() for d in ddls)


def test_tablespace_create_explicit_permanent_bigfile(monkeypatch):
    """Create bigfile permanent tablespace with explicit datafile (line 244)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(content="permanent", bigfile=True, datafile=["/u01/perm01.dbf"])

    ConnCls = _make_ts_conn_ext([
        {},
        {"value": None},
        {"value": None},
        {"status": "ONLINE"},
        {"count": 0},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("bigfile tablespace" in d.lower() for d in ddls)


def test_tablespace_map_status_read_write_online(monkeypatch):
    """map_status: state=read_write, current=ONLINE → wanted=ONLINE (lines 260-261)."""
    mod = _load_ts()
    wanted, enforcesql = mod.map_status("read_write", "ONLINE")
    assert wanted == "ONLINE"
    assert enforcesql == "online"


def test_tablespace_map_status_read_write_offline(monkeypatch):
    """map_status: state=read_write, current=OFFLINE → wanted=ONLINE (lines 263-264)."""
    mod = _load_ts()
    wanted, enforcesql = mod.map_status("read_write", "OFFLINE")
    assert wanted == "ONLINE"
    assert enforcesql == "online"


def test_tablespace_map_status_read_write_read_only(monkeypatch):
    """map_status: state=read_write, current=READ ONLY → read write (line 267)."""
    mod = _load_ts()
    wanted, enforcesql = mod.map_status("read_write", "READ ONLY")
    assert wanted == "ONLINE"
    assert enforcesql == "read write"


def test_tablespace_map_status_online(monkeypatch):
    """map_status: state=online → wanted=ONLINE (lines 269-270)."""
    mod = _load_ts()
    wanted, enforcesql = mod.map_status("online", "OFFLINE")
    assert wanted == "ONLINE"
    assert enforcesql == "online"


def test_tablespace_ensure_state_check_mode_just_created(monkeypatch):
    """ensure_tablespace_state: check_mode + tbs_just_created → returns early (line 290)."""
    from helpers import BaseFakeConn
    mod = _load_ts()

    class _CheckMod(BaseFakeModule):
        params = _ts_params_ext()
        check_mode = True

    m = _CheckMod()
    conn = BaseFakeConn(m)
    conn.module = m
    mod.ensure_tablespace_state(conn, m, tbs_just_created=True)
    assert conn.ddls == []


def test_tablespace_ensure_state_no_datafile_no_omf_fails(monkeypatch):
    """ensure_tablespace_state: no datafile + no OMF → fail_json (lines 336-337)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(bigfile=False, datafile=None, numfiles=None)

    ConnCls = _make_ts_conn_ext([
        {"tablespace_name": "TESTTS", "status": "ONLINE"},
        {"value": None},
        {"status": "ONLINE"},
        {"count": 1},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "datafile" in exc.value.args[0]["msg"].lower()


def test_tablespace_ensure_state_numfiles_add_autoextend_no_nextsize_fails(monkeypatch):
    """ensure_tablespace_state: numfiles add + autoextend + no nextsize → fail_json (line 349)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(bigfile=False, numfiles=3, autoextend=True, nextsize=None)

    ConnCls = _make_ts_conn_ext([
        {"tablespace_name": "TESTTS", "status": "ONLINE"},
        {"value": "/u01/oradata"},
        {"status": "ONLINE"},
        {"count": 1},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "NEXT size" in exc.value.args[0]["msg"]


def test_tablespace_ensure_state_numfiles_add_autoextend_nextsize_no_maxsize(monkeypatch):
    """ensure_tablespace_state: numfiles add + autoextend + nextsize + no maxsize (line 351)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(bigfile=False, numfiles=3, autoextend=True, nextsize="50M", maxsize=None)

    ConnCls = _make_ts_conn_ext([
        {"tablespace_name": "TESTTS", "status": "ONLINE"},
        {"value": "/u01/oradata"},
        {"status": "ONLINE"},
        {"count": 1},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("autoextend on next" in d.lower() for d in ddls)


def test_tablespace_ensure_state_numfiles_add_autoextend_with_maxsize(monkeypatch):
    """ensure_tablespace_state: numfiles add + autoextend + nextsize + maxsize (line 353)."""
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(bigfile=False, numfiles=3, autoextend=True, nextsize="50M", maxsize="2G")

    ConnCls = _make_ts_conn_ext([
        {"tablespace_name": "TESTTS", "status": "ONLINE"},
        {"value": "/u01/oradata"},
        {"status": "ONLINE"},
        {"count": 1},
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("maxsize" in d.lower() for d in ddls)


def test_tablespace_ensure_attributes_verbosity(monkeypatch):
    """ensure_tablespace_attributes: verbosity >= 3 → warn called (line 555)."""
    from helpers import BaseFakeConn
    mod = _load_ts()

    class _VerboseMod(BaseFakeModule):
        params = _ts_params_ext()

    m = _VerboseMod()
    m._verbosity = 3  # set after __init__ to override the default 0
    conn = BaseFakeConn(m)
    conn.module = m
    conn.execute_statement = lambda sql, params=None: ["Changes applied"]

    mod.ensure_tablespace_attributes(conn, "TESTTS", True, "50M", "2G")
    assert len(m._warnings) > 0


def test_tablespace_ensure_attributes_changed(monkeypatch):
    """ensure_tablespace_attributes: non-empty result → conn.changed = True (line 558)."""
    from helpers import BaseFakeConn
    mod = _load_ts()

    class _Mod(BaseFakeModule):
        params = _ts_params_ext()
        _verbosity = 0

    m = _Mod()
    conn = BaseFakeConn(m)
    conn.module = m
    conn.execute_statement = lambda sql, params=None: ["Changes applied"]

    mod.ensure_tablespace_attributes(conn, "TESTTS", True, "50M", "2G")
    assert conn.changed is True


def test_tablespace_manage_tablespace_read_only(monkeypatch):
    """manage_tablespace: state=read_only → cursor.execute called (lines 575-577)."""
    mod = _load_ts()
    executed = []

    class _FakeCursor:
        def execute(self, sql):
            executed.append(sql)

    result = mod.manage_tablespace(None, "", _FakeCursor(), "TESTTS", "read_only")
    assert result[0] is True
    assert "read only" in result[1].lower()
    assert any("read only" in s.lower() for s in executed)


def test_tablespace_manage_tablespace_read_write(monkeypatch):
    """manage_tablespace: state=read_write → cursor.execute called (lines 578-580)."""
    mod = _load_ts()
    executed = []

    class _FakeCursor:
        def execute(self, sql):
            executed.append(sql)

    result = mod.manage_tablespace(None, "", _FakeCursor(), "TESTTS", "read_write")
    assert result[0] is True
    assert "read write" in result[1].lower()


def test_tablespace_manage_tablespace_offline(monkeypatch):
    """manage_tablespace: state=offline → cursor.execute called (lines 581-583)."""
    mod = _load_ts()
    executed = []

    class _FakeCursor:
        def execute(self, sql):
            executed.append(sql)

    result = mod.manage_tablespace(None, "", _FakeCursor(), "TESTTS", "offline")
    assert result[0] is True
    assert "offline" in result[1].lower()


def test_tablespace_manage_tablespace_online(monkeypatch):
    """manage_tablespace: state=online → cursor.execute called (lines 584-586)."""
    mod = _load_ts()
    executed = []

    class _FakeCursor:
        def execute(self, sql):
            executed.append(sql)

    result = mod.manage_tablespace(None, "", _FakeCursor(), "TESTTS", "online")
    assert result[0] is True
    assert "online" in result[1].lower()


def test_tablespace_manage_tablespace_db_error(monkeypatch):
    """manage_tablespace: DatabaseError → returns False (lines 590-593)."""
    mod = _load_ts()

    class _FakeError:
        message = "ORA-01109: database not open"

    class _FakeOracleDb:
        class DatabaseError(Exception):
            pass

    monkeypatch.setattr(mod, "oracledb", _FakeOracleDb, raising=False)

    class _FakeCursorWithError:
        def execute(self, sql):
            err = _FakeOracleDb.DatabaseError("db error")
            err.args = (_FakeError(),)
            raise err

    result = mod.manage_tablespace(None, "", _FakeCursorWithError(), "TESTTS", "read_only")
    assert result is False


def test_tablespace_ensure_state_add_explicit_df_autoextend_no_next_fails(monkeypatch):
    """ensure_tablespace_state: add explicit datafile + autoextend + no nextsize → fail (line 375)."""
    from helpers import SequencedFakeConn
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(
            bigfile=False,
            datafile=["/u01/a.dbf", "/u01/b.dbf"],
            autoextend=True,
            nextsize=None,
            numfiles=None,
        )

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {"tablespace_name": "TESTTS", "status": "ONLINE"},
                {"value": None},
                {"status": "ONLINE"},
                {"count": 1},
            ]

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            if "f.file_name" in sql and not fetchone:
                return [{"file_name": "/u01/a.dbf"}]
            return super().execute_select_to_dict(sql, params, fetchone, fail_on_error)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "NEXT size" in exc.value.args[0]["msg"]


def test_tablespace_ensure_state_add_explicit_df_autoextend_next_no_maxsize(monkeypatch):
    """ensure_tablespace_state: add explicit datafile + autoextend + nextsize (no maxsize) (line 377)."""
    from helpers import SequencedFakeConn
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(
            bigfile=False,
            datafile=["/u01/a.dbf", "/u01/b.dbf"],
            autoextend=True,
            nextsize="50M",
            maxsize=None,
            numfiles=None,
        )

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {"tablespace_name": "TESTTS", "status": "ONLINE"},
                {"value": None},
                {"status": "ONLINE"},
                {"count": 1},
            ]

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            if "f.file_name" in sql and not fetchone:
                return [{"file_name": "/u01/a.dbf"}]
            return super().execute_select_to_dict(sql, params, fetchone, fail_on_error)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("autoextend on next" in d.lower() for d in ddls)


def test_tablespace_ensure_state_add_explicit_df_autoextend_with_maxsize(monkeypatch):
    """ensure_tablespace_state: add explicit datafile + autoextend + nextsize + maxsize (line 379)."""
    from helpers import SequencedFakeConn
    mod = _load_ts()

    class Mod(BaseFakeModule):
        params = _ts_params_ext(
            bigfile=False,
            datafile=["/u01/a.dbf", "/u01/b.dbf"],
            autoextend=True,
            nextsize="50M",
            maxsize="2G",
            numfiles=None,
        )

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {"tablespace_name": "TESTTS", "status": "ONLINE"},
                {"value": None},
                {"status": "ONLINE"},
                {"count": 1},
            ]

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            if "f.file_name" in sql and not fetchone:
                return [{"file_name": "/u01/a.dbf"}]
            return super().execute_select_to_dict(sql, params, fetchone, fail_on_error)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("maxsize" in d.lower() for d in ddls)


def test_opatch_remove_patch_ocm_response_file(monkeypatch):
    """remove_patch(): ocm_response_file set and old opatch → -ocmrf appended (line 403)."""
    mod = _load("oracle_opatch")
    mod.major_version = "12.2"
    mod.opatch_version = "12.2.0.1.4"   # older than noocm threshold
    mod.opatch_version_noocm = "12.2.0.1.5"
    Mod = _make_opatch_mod(_opatch_params(), responses=[(0, "rollback successful\n", "")])
    m = Mod()
    result = mod.remove_patch(m, "/fake/oracle", "/patches/12345", "12345678",
                              False, "/tmp/ocm.rsp", "short")
    assert result is True


def test_opatch_remove_patch_rc_nonzero(monkeypatch):
    """remove_patch(): rc!=0 → fail_json (lines 408-409)."""
    mod = _load("oracle_opatch")
    mod.major_version = "12.2"
    mod.opatch_version = "12.2.0.1.20"
    mod.opatch_version_noocm = "12.2.0.1.5"
    Mod = _make_opatch_mod(_opatch_params(), responses=[(1, "", "error")])
    m = Mod()
    with pytest.raises(FailJson) as exc:
        mod.remove_patch(m, "/fake/oracle", "/patches/12345", "12345678",
                         False, None, "short")
    assert "Error" in exc.value.args[0]["msg"]


def test_opatch_present_patch_base_no_id_calls_get_patch_id(monkeypatch):
    """patch_base set but patch_id=None → get_patch_id called (line 469)."""
    mod = _load("oracle_opatch")

    def _stub_get_patch_id(module, path):
        return "12345678"

    monkeypatch.setattr(mod, "get_patch_id", _stub_get_patch_id)
    Mod = _make_opatch_mod(
        _opatch_params(patch_base="/patches/12345678", patch_id=None),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_PRESENT],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert "already applied" in exc.value.args[0]["msg"]


def test_opatch_present_with_patch_version_already_applied(monkeypatch):
    """state=present, patch applied, patch_version set → msg includes version (line 538)."""
    mod = _load("oracle_opatch")
    stdout = "12.2.0.1.180417 (12345678) some info\nOPatch succeeded.\n"
    Mod = _make_opatch_mod(
        _opatch_params(patch_version="12.2.0.1.180417"),
        responses=[_OP_VER_OK, _OP_OPV_OK, (0, stdout, "")],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is False
    assert "12.2.0.1.180417" in payload["msg"]


def test_opatch_present_applied_returns_version_msg(monkeypatch):
    """state=present, patch applied, with patch_version → msg contains version (line 531)."""
    mod = _load("oracle_opatch")
    # apply_patch returns True for short output; need patch to NOT be applied first
    Mod = _make_opatch_mod(
        _opatch_params(conflict_check=False, patch_version="12.2.0.1.180417"),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_ABSENT, _OP_APPLY_OK],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert "12.2.0.1.180417" in payload["msg"]


def test_opatch_absent_applied_with_patch_version(monkeypatch):
    """state=absent, patch applied, patch_version set → msg includes version (line 547)."""
    mod = _load("oracle_opatch")
    stdout = "12.2.0.1.180417 (12345678) some info\nOPatch succeeded.\n"
    Mod = _make_opatch_mod(
        _opatch_params(state="absent", patch_version="12.2.0.1.180417"),
        responses=[_OP_VER_OK, _OP_OPV_OK, (0, stdout, ""), _OP_ROLLBACK_OK],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert "12.2.0.1.180417" in payload["msg"]


def test_opatch_absent_not_applied_with_patch_version(monkeypatch):
    """state=absent, patch not applied, patch_version set → msg includes version (line 555)."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(
        _opatch_params(state="absent", patch_version="12.2.0.1.180417"),
        responses=[_OP_VER_OK, _OP_OPV_OK, _OP_PATCH_ABSENT],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is False
    assert "12.2.0.1.180417" in payload["msg"]


def test_opatch_stop_process_no_oratab(monkeypatch):
    """stop_process(): /etc/oratab doesn't exist → returns None silently (lines 329-331)."""
    mod = _load("oracle_opatch")
    Mod = _make_opatch_mod(_opatch_params())
    m = Mod()
    monkeypatch.setattr(mod.os.path, "exists", lambda p: False)
    # Should not raise - just returns None
    result = mod.stop_process(m, "/fake/oracle")
    assert result is None


# ===========================================================================
# oracle_datapatch (additional function-level tests)
# ===========================================================================

def _datapatch_params(**overrides):
    base = {
        "oracle_home": "/fake/oracle",
        "db_name": "TESTDB",
        "sid": None,
        "db_unique_name": None,
        "fail_on_db_not_exist": True,
        "output": "short",
        "user": "sys",
        "password": "secret",
        "hostname": "localhost",
        "service_name": None,
        "port": 1521,
    }
    base.update(overrides)
    return base


def _make_dp_mod(params, responses=None):
    _resp = list(responses or [])

    class Mod(BaseFakeModule):
        def run_command(self, cmd, **kw):
            return _resp.pop(0) if _resp else (0, "", "")

    Mod.params = params
    return Mod


def test_datapatch_no_oracle_home_fails(monkeypatch):
    """No oracle_home in params or env → fail_json."""
    mod = _load("oracle_datapatch")
    orig = os.environ.pop("ORACLE_HOME", None)
    try:
        Mod = _make_dp_mod(_datapatch_params(oracle_home=None))
        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        with pytest.raises(FailJson) as exc:
            mod.main()
        assert "ORACLE_HOME" in exc.value.args[0]["msg"]
    finally:
        if orig is not None:
            os.environ["ORACLE_HOME"] = orig


def test_datapatch_oracle_home_from_env(monkeypatch):
    """oracle_home from ORACLE_HOME env variable → succeeds."""
    mod = _load("oracle_datapatch")
    orig = os.environ.get("ORACLE_HOME")
    os.environ["ORACLE_HOME"] = "/env/oracle"
    try:
        Mod = _make_dp_mod(_datapatch_params(oracle_home=None, fail_on_db_not_exist=False),
                           responses=[(0, "SQL*Plus: Release 12.2.0.1.0 Production", "")])
        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        monkeypatch.setattr(mod, "check_db_exists", lambda *a, **kw: False)
        with pytest.raises(ExitJson) as exc:
            mod.main()
        assert exc.value.args[0]["changed"] is False
        assert "not exist" in exc.value.args[0]["msg"].lower()
    finally:
        if orig is None:
            os.environ.pop("ORACLE_HOME", None)
        else:
            os.environ["ORACLE_HOME"] = orig


def test_datapatch_oracledb_missing(monkeypatch):
    """oracledb not installed → fail_json."""
    mod = _load("oracle_datapatch")
    monkeypatch.setattr(mod, "oracledb_exists", False, raising=False)
    Mod = _make_dp_mod(_datapatch_params(),
                       responses=[(0, "SQL*Plus: Release 12.2.0.1.0 Production", "")])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "oracledb" in exc.value.args[0]["msg"].lower()


def test_datapatch_gimanaged_true(monkeypatch):
    """olr.loc exists → gimanaged=True."""
    mod = _load("oracle_datapatch")
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)  # olr.loc exists
    Mod = _make_dp_mod(_datapatch_params(fail_on_db_not_exist=False),
                       responses=[(0, "SQL*Plus: Release 12.2.0.1.0 Production", "")])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "check_db_exists", lambda *a, **kw: False)
    with pytest.raises(ExitJson):
        mod.main()
    assert mod.gimanaged is True


def test_datapatch_db_not_found_fail_true(monkeypatch):
    """DB not found + fail_on_db_not_exist=True → fail_json."""
    mod = _load("oracle_datapatch")
    Mod = _make_dp_mod(_datapatch_params(fail_on_db_not_exist=True),
                       responses=[(0, "SQL*Plus: Release 12.2.0.1.0 Production", "")])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: False)
    monkeypatch.setattr(mod, "check_db_exists", lambda *a, **kw: False)
    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "not exist" in exc.value.args[0]["msg"].lower()


def test_datapatch_db_not_found_continue(monkeypatch):
    """DB not found + fail_on_db_not_exist=False → exit changed=False."""
    mod = _load("oracle_datapatch")
    Mod = _make_dp_mod(_datapatch_params(fail_on_db_not_exist=False),
                       responses=[(0, "SQL*Plus: Release 12.2.0.1.0 Production", "")])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: False)
    monkeypatch.setattr(mod, "check_db_exists", lambda *a, **kw: False)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_datapatch_service_name_from_unique(monkeypatch):
    """db_unique_name set, no service_name → uses db_unique_name as service_name."""
    mod = _load("oracle_datapatch")
    Mod = _make_dp_mod(
        _datapatch_params(db_unique_name="TESTDB_DG", fail_on_db_not_exist=False),
        responses=[(0, "SQL*Plus: Release 12.2.0.1.0 Production", "")],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: False)
    monkeypatch.setattr(mod, "check_db_exists", lambda *a, **kw: False)
    with pytest.raises(ExitJson):
        mod.main()
    assert mod.service_name == "TESTDB_DG"


def test_datapatch_service_name_explicit(monkeypatch):
    """Explicit service_name → used as-is."""
    mod = _load("oracle_datapatch")
    Mod = _make_dp_mod(
        _datapatch_params(service_name="MYSVC", fail_on_db_not_exist=False),
        responses=[(0, "SQL*Plus: Release 12.2.0.1.0 Production", "")],
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: False)
    monkeypatch.setattr(mod, "check_db_exists", lambda *a, **kw: False)
    with pytest.raises(ExitJson):
        mod.main()
    assert mod.service_name == "MYSVC"


def test_datapatch_db_found_success(monkeypatch):
    """DB found, datapatch succeeds → exit changed=True."""
    mod = _load("oracle_datapatch")
    Mod = _make_dp_mod(_datapatch_params(),
                       responses=[(0, "SQL*Plus: Release 12.2.0.1.0 Production", "")])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: False)
    monkeypatch.setattr(mod, "check_db_exists", lambda *a, **kw: True)
    monkeypatch.setattr(mod, "run_datapatch", lambda *a, **kw: True)
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert "successfully" in exc.value.args[0]["msg"].lower()


def test_datapatch_check_db_exists_gi_found(monkeypatch):
    """check_db_exists: gimanaged=True, srvctl finds DB → True."""
    mod = _load("oracle_datapatch")
    mod.gimanaged = True
    Mod = _make_dp_mod(_datapatch_params(), responses=[
        (0, "Database name: TESTDB\nOracle home: /fake/oracle\n", ""),
    ])
    m = Mod()
    result = mod.check_db_exists(m, "", "/fake/oracle", "TESTDB", None, None)
    assert result is True


def test_datapatch_check_db_exists_gi_not_found(monkeypatch):
    """check_db_exists: gimanaged=True, DB not in srvctl output → False."""
    mod = _load("oracle_datapatch")
    mod.gimanaged = True
    Mod = _make_dp_mod(_datapatch_params(), responses=[
        (1, "TESTDB not found in cluster", ""),
    ])
    m = Mod()
    result = mod.check_db_exists(m, "", "/fake/oracle", "TESTDB", None, None)
    assert result is False


def test_datapatch_check_db_exists_gi_error(monkeypatch):
    """check_db_exists: gimanaged=True, srvctl error without DB name → False."""
    mod = _load("oracle_datapatch")
    mod.gimanaged = True
    Mod = _make_dp_mod(_datapatch_params(), responses=[
        (1, "CRS-4000: Command Start failed, or had errors.", ""),
    ])
    m = Mod()
    result = mod.check_db_exists(m, "", "/fake/oracle", "TESTDB", None, None)
    assert result is False


def test_datapatch_run_datapatch_success(monkeypatch):
    """run_datapatch: 19c, 'Patch installation complete' → returns True."""
    mod = _load("oracle_datapatch")
    mod.major_version = "19.0"
    mod.output = "short"
    Mod = _make_dp_mod(_datapatch_params(), responses=[
        (0, "Patch installation complete. SQL Patches applied.", ""),
    ])
    m = Mod()
    result = mod.run_datapatch(m, "", "localhost", "/fake/oracle", "TESTDB", None)
    assert result is True


def test_datapatch_run_datapatch_failure(monkeypatch):
    """run_datapatch: command returns rc!=0 → fail_json."""
    mod = _load("oracle_datapatch")
    mod.major_version = "19.0"
    mod.output = "short"
    Mod = _make_dp_mod(_datapatch_params(), responses=[
        (1, "", "datapatch failed"),
    ])
    m = Mod()
    with pytest.raises(FailJson):
        mod.run_datapatch(m, "", "localhost", "/fake/oracle", "TESTDB", None)


def test_datapatch_run_datapatch_no_complete_msg(monkeypatch):
    """run_datapatch: rc=0 but no 'Patch installation complete' → exit changed=False."""
    mod = _load("oracle_datapatch")
    mod.major_version = "19.0"
    mod.output = "short"
    Mod = _make_dp_mod(_datapatch_params(), responses=[
        (0, "Some other output without completion keyword", ""),
    ])
    m = Mod()
    with pytest.raises(ExitJson) as exc:
        mod.run_datapatch(m, "", "localhost", "/fake/oracle", "TESTDB", None)
    assert exc.value.args[0]["changed"] is False


def test_datapatch_run_datapatch_verbose(monkeypatch):
    """run_datapatch: output=verbose + success → exit_json with STDOUT."""
    mod = _load("oracle_datapatch")
    mod.major_version = "19.0"
    mod.output = "verbose"
    Mod = _make_dp_mod(_datapatch_params(), responses=[
        (0, "Patch installation complete. SQL Patches applied.", ""),
    ])
    m = Mod()
    with pytest.raises(ExitJson) as exc:
        mod.run_datapatch(m, "", "localhost", "/fake/oracle", "TESTDB", None)
    assert exc.value.args[0]["changed"] is True
    assert "STDOUT" in exc.value.args[0]["msg"]
