"""Unit tests for oracle_db module.

Targets missing coverage lines to bring oracle_db.py from ~42% to ≥80%.
Uses the same helpers as test_tool_modules.py (_db_params, _make_db_mod,
_NoGiNoDb, _NoGiRunningDb, _GiNoDb) but redefines them locally to keep
this file self-contained.
"""
import os
import pytest

from conftest import ExitJson, FailJson, load_module_from_path
from helpers import BaseFakeModule, BaseFakeConn, FakeOracleHomes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load():
    return load_module_from_path("plugins/modules/oracle_db.py", "oracle_db")


def _db_params(**overrides):
    base = {
        "oracle_home": "/fake/oracle",
        "db_name": "TESTDB",
        "db_unique_name": None,
        "domain": None,
        "state": "present",
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
    _resp = list(responses or [])

    class Mod(BaseFakeModule):
        def run_command(self, cmd, **kw):
            return _resp.pop(0) if _resp else (0, "", "")

    Mod.params = params
    return Mod


class _NoGiNoDb(FakeOracleHomes):
    def __init__(self):
        super().__init__()
        self.oracle_gi_managed = False
        self.oracle_crs = False
        self.facts_item = {}


class _NoGiRunningDb(FakeOracleHomes):
    def __init__(self):
        super().__init__()
        self.oracle_gi_managed = False
        self.oracle_crs = False
        self.facts_item = {
            "TESTDB": {
                "running": True,
                "crsname": None,
                "ORACLE_HOME": "/fake/oracle",
                "israc": False,
            }
        }


class _NoGiRunningDbDifferentHome(FakeOracleHomes):
    def __init__(self):
        super().__init__()
        self.oracle_gi_managed = False
        self.oracle_crs = False
        self.facts_item = {
            "TESTDB": {
                "running": True,
                "crsname": None,
                "ORACLE_HOME": "/other/oracle",
                "israc": False,
            }
        }


class _GiNoDb(FakeOracleHomes):
    def __init__(self):
        super().__init__()
        self.oracle_gi_managed = True
        self.oracle_crs = False
        self.facts_item = {}


class _GiRunningDb(FakeOracleHomes):
    def __init__(self):
        super().__init__()
        self.oracle_gi_managed = True
        self.oracle_crs = True
        self.facts_item = {
            "TESTDB": {
                "running": True,
                "crsname": "TESTDB",
                "ORACLE_HOME": "/fake/oracle",
                "israc": False,
            }
        }


class _FakeConnForEnsure(BaseFakeConn):
    """FakeConn that serves the three sequential execute_* calls in ensure_db_state."""

    def __init__(self, module, *, log_mode="NOARCHIVELOG", force_logging="NO",
                 flashback_on="NO", supplemental_logging="NO",
                 def_tbs_type="BIGFILE", def_tbs="USERS", def_temp_tbs="TEMP",
                 timezone="+00:00", israc=False):
        super().__init__(module)
        self._call_count = 0
        self._log_mode = log_mode
        self._force_logging = force_logging
        self._flashback_on = flashback_on
        self._suppl = supplemental_logging
        self._def_tbs_type = def_tbs_type
        self._def_tbs = def_tbs
        self._def_temp_tbs = def_temp_tbs
        self._tz = timezone
        self._israc = israc

    def execute_select(self, sql, params=None, fetchone=False):
        # database_properties query → list of (name, value) tuples
        return [
            ("DEFAULT_TBS_TYPE", self._def_tbs_type),
            ("DEFAULT_PERMANENT_TABLESPACE", self._def_tbs),
            ("DEFAULT_TEMP_TABLESPACE", self._def_temp_tbs),
            ("DBTIMEZONE", self._tz),
        ]

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        self._call_count += 1
        if self._call_count == 1:
            # israc_sql
            return {"parallel": "YES" if self._israc else "NO",
                    "instance_name": "TESTDB", "host_name": "host1"}
        else:
            # log_sql
            return {
                "supplemental_logging": self._suppl,
                "log_mode": self._log_mode,
                "force_logging": self._force_logging,
                "flashback_on": self._flashback_on,
            }


# ---------------------------------------------------------------------------
# check_db_exists tests (covers lines 268, 284, 290-297, 302-306)
# ---------------------------------------------------------------------------

def test_check_db_exists_gi_db_unique_name(monkeypatch):
    """check_db_exists: GI, db_unique_name set → uses db_unique_name (line 268), rc!=0 db_name in stdout → False."""
    mod = _load()
    orig = os.environ.pop("ORACLE_SID", None)
    try:
        Mod = _make_db_mod(_db_params(db_unique_name="TESTDB_UQ"), responses=[
            (1, "TESTDB not found", ""),  # srvctl config database → rc!=0, db_name in stdout → False
        ])
        m = Mod()
        ohomes = _GiNoDb()
        result = mod.check_db_exists(m, ohomes)
        assert result is False
    finally:
        if orig is not None:
            os.environ["ORACLE_SID"] = orig


def test_check_db_exists_gi_rc0_database_name_in_stdout(monkeypatch):
    """check_db_exists: GI, rc=0 with 'Database name: TESTDB' in stdout → True (line 290-292)."""
    mod = _load()
    orig = os.environ.pop("ORACLE_SID", None)
    try:
        Mod = _make_db_mod(_db_params(), responses=[
            (0, "Database name: TESTDB\nOracle home: /fake/oracle\n", ""),
        ])
        m = Mod()
        ohomes = _GiNoDb()
        result = mod.check_db_exists(m, ohomes)
        assert result is True
    finally:
        if orig is not None:
            os.environ["ORACLE_SID"] = orig


def test_check_db_exists_gi_rc0_other_stdout(monkeypatch):
    """check_db_exists: GI, rc=0 stdout doesn't contain 'Database name: TESTDB' → True (lines 293-297)."""
    mod = _load()
    orig = os.environ.pop("ORACLE_SID", None)
    try:
        Mod = _make_db_mod(_db_params(), responses=[
            (0, "Some other output\n", ""),
        ])
        m = Mod()
        ohomes = _GiNoDb()
        result = mod.check_db_exists(m, ohomes)
        assert result is True
    finally:
        if orig is not None:
            os.environ["ORACLE_SID"] = orig


def test_check_db_exists_gi_rc1_no_prcd1229(monkeypatch):
    """check_db_exists: GI, rc!=0 without PRCD-1229, stdout doesn't contain db_name → False (line 289)."""
    mod = _load()
    orig = os.environ.pop("ORACLE_SID", None)
    try:
        Mod = _make_db_mod(_db_params(), responses=[
            (1, "some other error", ""),  # srvctl config database → rc!=0, not PRCD-1229, db_name not in stdout → False
        ])
        m = Mod()
        ohomes = _GiNoDb()
        result = mod.check_db_exists(m, ohomes)
        assert result is False
    finally:
        if orig is not None:
            os.environ["ORACLE_SID"] = orig


# ---------------------------------------------------------------------------
# ensure_db_state tests (covers lines 558-723)
# ---------------------------------------------------------------------------

def _ensure_sid(monkeypatch):
    """Ensure ORACLE_SID=TESTDB for ensure_db_state tests and clear it after."""
    monkeypatch.setenv("ORACLE_SID", "TESTDB")


def test_ensure_db_state_no_changes_needed(monkeypatch):
    """ensure_db_state: DB already in desired state → exit changed=False."""
    _ensure_sid(monkeypatch)
    mod = _load()
    Mod = _make_db_mod(_db_params(
        state="present", archivelog=False, force_logging=False,
        flashback=False, supplemental_logging=False,
        default_tablespace_type="bigfile",
    ))
    m = Mod()
    ohomes = _NoGiRunningDb()

    monkeypatch.setattr(mod, "oracleConnection", _FakeConnForEnsure, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.ensure_db_state(m, ohomes, newdb=False)
    assert exc.value.args[0]["changed"] is False


def test_ensure_db_state_newdb_no_changes(monkeypatch):
    """ensure_db_state: newdb=True, DB already in desired state → exit changed=True."""
    _ensure_sid(monkeypatch)
    mod = _load()
    Mod = _make_db_mod(_db_params(
        state="present", archivelog=False, force_logging=False,
        flashback=False, supplemental_logging=False,
        default_tablespace_type="bigfile",
    ))
    m = Mod()
    ohomes = _NoGiRunningDb()

    monkeypatch.setattr(mod, "oracleConnection", _FakeConnForEnsure, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.ensure_db_state(m, ohomes, newdb=True)
    assert exc.value.args[0]["changed"] is True


def test_ensure_db_state_force_logging_needed(monkeypatch):
    """ensure_db_state: force_logging differs → norestart change applied."""
    _ensure_sid(monkeypatch)
    mod = _load()
    Mod = _make_db_mod(_db_params(
        state="present", force_logging=True,  # want YES
        archivelog=False, flashback=False, supplemental_logging=False,
        default_tablespace_type="bigfile",
    ))
    m = Mod()
    ohomes = _NoGiRunningDb()

    # DB reports force_logging=NO → mismatch → change_db_sql will have alter database force logging
    conn = _FakeConnForEnsure(m, force_logging="NO")
    monkeypatch.setattr(mod, "oracleConnection", lambda module: conn, raising=False)

    def _fake_apply_norestart(module, change_db_sql):
        return change_db_sql

    monkeypatch.setattr(mod, "apply_norestart_changes", _fake_apply_norestart, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.ensure_db_state(m, ohomes, newdb=False)
    assert exc.value.args[0]["changed"] is True


def test_ensure_db_state_archivelog_needed(monkeypatch):
    """ensure_db_state: archivelog differs → restart change applied."""
    _ensure_sid(monkeypatch)
    mod = _load()
    Mod = _make_db_mod(_db_params(
        state="present", archivelog=True,  # want ARCHIVELOG
        force_logging=False, flashback=False, supplemental_logging=False,
        default_tablespace_type="bigfile",
    ))
    m = Mod()
    ohomes = _NoGiRunningDb()

    # DB reports NOARCHIVELOG → mismatch → change_restart_sql
    conn = _FakeConnForEnsure(m, log_mode="NOARCHIVELOG")
    monkeypatch.setattr(mod, "oracleConnection", lambda module: conn, raising=False)

    def _fake_apply_restart(module, ohomes, instance_name, change_restart_sql):
        return change_restart_sql

    monkeypatch.setattr(mod, "apply_restart_changes", _fake_apply_restart, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.ensure_db_state(m, ohomes, newdb=False)
    assert exc.value.args[0]["changed"] is True


def test_ensure_db_state_flashback_archivelog_off_path(monkeypatch):
    """ensure_db_state: both flashback and archivelog to be disabled → covers special ordering (line 694)."""
    _ensure_sid(monkeypatch)
    mod = _load()
    Mod = _make_db_mod(_db_params(
        state="present", archivelog=False, flashback=False,  # want both OFF
        force_logging=False, supplemental_logging=False,
        default_tablespace_type="bigfile",
    ))
    m = Mod()
    ohomes = _NoGiRunningDb()

    # DB currently has ARCHIVELOG + flashback=YES → triggers the special ordering branch
    conn = _FakeConnForEnsure(m, log_mode="ARCHIVELOG", flashback_on="YES")
    monkeypatch.setattr(mod, "oracleConnection", lambda module: conn, raising=False)

    def _fake_apply_norestart(module, change_db_sql):
        return change_db_sql

    def _fake_apply_restart(module, ohomes, instance_name, change_restart_sql):
        return change_restart_sql

    monkeypatch.setattr(mod, "apply_norestart_changes", _fake_apply_norestart, raising=False)
    monkeypatch.setattr(mod, "apply_restart_changes", _fake_apply_restart, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.ensure_db_state(m, ohomes, newdb=False)
    assert exc.value.args[0]["changed"] is True


def test_ensure_db_state_tablespace_changes(monkeypatch):
    """ensure_db_state: default_tablespace and default_temp_tablespace differ → norestart SQL."""
    _ensure_sid(monkeypatch)
    mod = _load()
    Mod = _make_db_mod(_db_params(
        state="present",
        default_tablespace="MYDATA",
        default_temp_tablespace="MYTEMP",
        default_tablespace_type="bigfile",
        archivelog=False, force_logging=False, flashback=False, supplemental_logging=False,
    ))
    m = Mod()
    ohomes = _NoGiRunningDb()

    conn = _FakeConnForEnsure(m, def_tbs="USERS", def_temp_tbs="TEMP")  # differs from params
    monkeypatch.setattr(mod, "oracleConnection", lambda module: conn, raising=False)

    def _fake_apply_norestart(module, change_db_sql):
        return change_db_sql

    monkeypatch.setattr(mod, "apply_norestart_changes", _fake_apply_norestart, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.ensure_db_state(m, ohomes, newdb=False)
    assert exc.value.args[0]["changed"] is True


def test_ensure_db_state_timezone_change(monkeypatch):
    """ensure_db_state: timezone differs → timezone change SQL added."""
    _ensure_sid(monkeypatch)
    mod = _load()
    Mod = _make_db_mod(_db_params(
        state="present", timezone="America/New_York",
        default_tablespace_type="bigfile",
        archivelog=False, force_logging=False, flashback=False, supplemental_logging=False,
    ))
    m = Mod()
    ohomes = _NoGiRunningDb()

    conn = _FakeConnForEnsure(m, timezone="+00:00")  # differs from America/New_York
    monkeypatch.setattr(mod, "oracleConnection", lambda module: conn, raising=False)

    def _fake_apply_norestart(module, change_db_sql):
        return change_db_sql

    monkeypatch.setattr(mod, "apply_norestart_changes", _fake_apply_norestart, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.ensure_db_state(m, ohomes, newdb=False)
    assert exc.value.args[0]["changed"] is True


# ---------------------------------------------------------------------------
# apply_norestart_changes tests (covers lines 739-743)
# ---------------------------------------------------------------------------

def test_apply_norestart_changes(monkeypatch):
    """apply_norestart_changes: executes DDLs via oracleConnection."""
    mod = _load()
    Mod = _make_db_mod(_db_params())
    m = Mod()

    executed = []

    class _FakeConn(BaseFakeConn):
        def execute_ddl(self, sql, params=None, no_change=False, ignore_errors=None, ddls_entry=None):
            executed.append(ddls_entry if ddls_entry is not None else sql)

    monkeypatch.setattr(mod, "oracleConnection", _FakeConn, raising=False)
    result = mod.apply_norestart_changes(m, ["alter database force logging", "alter database flashback on"])
    assert "alter database force logging" in result or len(executed) == 2


# ---------------------------------------------------------------------------
# stop_db tests (covers lines 747-776)
# ---------------------------------------------------------------------------

def test_stop_db_gi_success(monkeypatch):
    """stop_db: GI-managed, srvctl stop succeeds → no exception."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        Mod = _make_db_mod(_db_params(), responses=[
            (0, "", ""),  # srvctl stop database → success
        ])
        m = Mod()
        ohomes = _GiRunningDb()
        mod.stop_db(m, ohomes)  # Should not raise
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_stop_db_gi_failure(monkeypatch):
    """stop_db: GI-managed, srvctl stop fails → fail_json."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        Mod = _make_db_mod(_db_params(), responses=[
            (1, "PRCD-1234 stop failed", ""),
        ])
        m = Mod()
        ohomes = _GiRunningDb()
        with pytest.raises(FailJson):
            mod.stop_db(m, ohomes)
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_stop_db_gi_prcd_in_stdout_fails(monkeypatch):
    """stop_db: rc=0 but stdout starts with PRCD- → fail_json."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        Mod = _make_db_mod(_db_params(), responses=[
            (0, "PRCD-9999 something wrong", ""),
        ])
        m = Mod()
        ohomes = _GiRunningDb()
        with pytest.raises(FailJson):
            mod.stop_db(m, ohomes)
    finally:
        os.environ.pop("ORACLE_SID", None)


# ---------------------------------------------------------------------------
# start_db tests (covers lines 779-810)
# ---------------------------------------------------------------------------

def test_start_db_gi_success(monkeypatch):
    """start_db: GI-managed, srvctl start succeeds → no exception."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        Mod = _make_db_mod(_db_params(), responses=[
            (0, "", ""),  # srvctl start database → success
        ])
        m = Mod()
        ohomes = _GiRunningDb()
        mod.start_db(m, ohomes)  # Should not raise
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_start_db_gi_failure(monkeypatch):
    """start_db: GI-managed, srvctl start fails → fail_json."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        Mod = _make_db_mod(_db_params(), responses=[
            (1, "Error starting", ""),
        ])
        m = Mod()
        ohomes = _GiRunningDb()
        with pytest.raises(FailJson):
            mod.start_db(m, ohomes)
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_start_db_gi_prcd_in_stdout_fails(monkeypatch):
    """start_db: rc=0 but stdout starts with PRCD → fail_json."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        Mod = _make_db_mod(_db_params(), responses=[
            (0, "PRCD-9999 something", ""),
        ])
        m = Mod()
        ohomes = _GiRunningDb()
        with pytest.raises(FailJson):
            mod.start_db(m, ohomes)
    finally:
        os.environ.pop("ORACLE_SID", None)


# ---------------------------------------------------------------------------
# start_instance tests (covers lines 813-857)
# ---------------------------------------------------------------------------

def test_start_instance_gi_success(monkeypatch):
    """start_instance: GI-managed, israc=False → srvctl start database."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        Mod = _make_db_mod(_db_params(), responses=[
            (0, "", ""),  # srvctl start database → success
        ])
        m = Mod()
        ohomes = _GiRunningDb()
        mod.start_instance(m, ohomes, "mount", "TESTDB")
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_start_instance_gi_israc_success(monkeypatch):
    """start_instance: GI-managed, israc=True → srvctl start instance."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        class _GiRacRunningDb(_GiRunningDb):
            def __init__(self):
                super().__init__()
                self.facts_item["TESTDB"]["israc"] = True

        Mod = _make_db_mod(_db_params(), responses=[
            (0, "", ""),  # srvctl start instance → success
        ])
        m = Mod()
        ohomes = _GiRacRunningDb()
        mod.start_instance(m, ohomes, "mount", "TESTDB")
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_start_instance_gi_failure(monkeypatch):
    """start_instance: GI, srvctl fails → fail_json."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        Mod = _make_db_mod(_db_params(), responses=[
            (1, "Error starting instance", ""),
        ])
        m = Mod()
        ohomes = _GiRunningDb()
        with pytest.raises(FailJson):
            mod.start_instance(m, ohomes, "mount", "TESTDB")
    finally:
        os.environ.pop("ORACLE_SID", None)


# ---------------------------------------------------------------------------
# main() additional coverage tests
# ---------------------------------------------------------------------------

def _make_main_mod(state, responses=None, extra_params=None):
    params = _db_params(state=state)
    if extra_params:
        params.update(extra_params)
    return _make_db_mod(params, responses=responses)


class _FakeOracleHomesForMain(FakeOracleHomes):
    """Base for main() tests."""
    def __init__(self):
        super().__init__()
        self.oracle_gi_managed = False
        self.oracle_crs = False
        self.facts_item = {}

    def list_crs_instances(self): pass
    def list_processes(self): pass
    def parse_oratab(self): pass


class _FakeOracleHomesRunningForMain(_FakeOracleHomesForMain):
    def __init__(self):
        super().__init__()
        self.facts_item = {
            "TESTDB": {"running": True, "crsname": None, "ORACLE_HOME": "/fake/oracle", "israc": False}
        }


def test_main_oracle_home_from_env(monkeypatch):
    """main(): oracle_home not in params but in ORACLE_HOME env → uses it (lines 926-927)."""
    mod = _load()
    orig = os.environ.get("ORACLE_HOME")
    os.environ["ORACLE_HOME"] = "/env/oracle"
    try:
        Mod = _make_main_mod("absent", extra_params={"oracle_home": None})
        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesForMain, raising=False)

        with pytest.raises(ExitJson) as exc:
            mod.main()
        assert exc.value.args[0]["changed"] is False
    finally:
        if orig is not None:
            os.environ["ORACLE_HOME"] = orig
        else:
            os.environ.pop("ORACLE_HOME", None)


def test_main_domain_sets_service_name(monkeypatch):
    """main(): domain set → service_name gets domain suffix (lines 947-948)."""
    mod = _load()
    Mod = _make_main_mod("absent", extra_params={"domain": "example.com"})
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesForMain, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert "doesn't exist" in exc.value.args[0]["msg"]


def test_main_started_calls_start_db(monkeypatch):
    """main(): state=started, DB stopped → calls start_db → exit changed=True (lines 962-963)."""
    mod = _load()

    started = []

    def _fake_start_db(module, ohomes):
        started.append(True)

    class _FakeOracleHomesStoppedForMain(_FakeOracleHomesForMain):
        def __init__(self):
            super().__init__()
            self.facts_item = {
                "TESTDB": {"running": False, "crsname": None, "ORACLE_HOME": "/fake/oracle", "israc": False}
            }

    Mod = _make_main_mod("started")
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesStoppedForMain, raising=False)
    monkeypatch.setattr(mod, "start_db", _fake_start_db, raising=False)
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        with pytest.raises(ExitJson) as exc:
            mod.main()
        assert exc.value.args[0]["changed"] is True
        assert started
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_main_stopped_calls_stop_db(monkeypatch):
    """main(): state=stopped, DB running → calls stop_db → exit changed=True (lines 973-975)."""
    mod = _load()

    stopped = []

    def _fake_stop_db(module, ohomes):
        stopped.append(True)

    Mod = _make_main_mod("stopped")
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesRunningForMain, raising=False)
    monkeypatch.setattr(mod, "stop_db", _fake_stop_db, raising=False)
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        with pytest.raises(ExitJson) as exc:
            mod.main()
        assert exc.value.args[0]["changed"] is True
        assert stopped
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_main_restarted_calls_stop_then_start(monkeypatch):
    """main(): state=restarted, DB running → stop then start → exit changed=True (lines 977-986)."""
    mod = _load()

    ops = []

    def _fake_stop_db(module, ohomes):
        ops.append("stop")

    def _fake_start_db(module, ohomes):
        ops.append("start")

    Mod = _make_main_mod("restarted")
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesRunningForMain, raising=False)
    monkeypatch.setattr(mod, "stop_db", _fake_stop_db, raising=False)
    monkeypatch.setattr(mod, "start_db", _fake_start_db, raising=False)
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        with pytest.raises(ExitJson) as exc:
            mod.main()
        assert exc.value.args[0]["changed"] is True
        assert ops == ["stop", "start"]
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_main_restarted_not_running_skips_stop(monkeypatch):
    """main(): state=restarted, DB stopped → no stop, just start → exit changed=True."""
    mod = _load()

    ops = []

    def _fake_stop_db(module, ohomes):
        ops.append("stop")

    def _fake_start_db(module, ohomes):
        ops.append("start")

    class _FakeOracleHomesStoppedForMain(_FakeOracleHomesForMain):
        def __init__(self):
            super().__init__()
            self.facts_item = {
                "TESTDB": {"running": False, "crsname": None, "ORACLE_HOME": "/fake/oracle", "israc": False}
            }

    Mod = _make_main_mod("restarted")
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesStoppedForMain, raising=False)
    monkeypatch.setattr(mod, "stop_db", _fake_stop_db, raising=False)
    monkeypatch.setattr(mod, "start_db", _fake_start_db, raising=False)
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        with pytest.raises(ExitJson) as exc:
            mod.main()
        assert exc.value.args[0]["changed"] is True
        assert ops == ["start"]  # stop skipped, only start
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_main_present_create_with_warning(monkeypatch):
    """main(): state=present, DB not found, create_db returns WARNING → module.warn called (lines 991-992)."""
    mod = _load()

    warned = []

    def _fake_create_db(module, ohomes):
        return "WARNING: something happened STDOUT: done STDERR: COMMAND: dbca"

    def _fake_ensure_db_state(module, ohomes, newdb):
        module.exit_json(msg="done", changed=newdb)

    class _FakeOracleHomesRefreshable(_FakeOracleHomesForMain):
        def list_crs_instances(self): pass
        def list_processes(self): pass
        def parse_oratab(self): pass

    Mod = _make_main_mod("present")
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesRefreshable, raising=False)
    monkeypatch.setattr(mod, "create_db", _fake_create_db, raising=False)
    monkeypatch.setattr(mod, "ensure_db_state", _fake_ensure_db_state, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


# ---------------------------------------------------------------------------
# create_db additional branch tests (lines 342-347, 353)
# ---------------------------------------------------------------------------

def test_create_db_initparams_skip_memory(monkeypatch):
    """create_db: initparams contains sga_target → skip_memory=True (lines 342-344)."""
    mod = _load()
    Mod = _make_db_mod(_db_params(
        state="present",
        initparams={"sga_target": "1G"},
    ), responses=[
        (0, "SQL*Plus: Release 19.0.0.0.0 - Production", ""),  # get_version
        (0, "Database creation successful", ""),               # dbca
    ])
    m = Mod()
    ohomes = _NoGiNoDb()
    result = mod.create_db(m, ohomes)
    assert "STDOUT" in result or "successful" in result


def test_create_db_initparams_memory_target_skip(monkeypatch):
    """create_db: initparams contains memory_target → skip_memory=True (lines 345-347)."""
    mod = _load()
    Mod = _make_db_mod(_db_params(
        state="present",
        initparams={"memory_target": "2G"},
    ), responses=[
        (0, "SQL*Plus: Release 19.0.0.0.0 - Production", ""),
        (0, "Database creation successful", ""),
    ])
    m = Mod()
    ohomes = _NoGiNoDb()
    result = mod.create_db(m, ohomes)
    assert "STDOUT" in result or "successful" in result


def test_create_db_crs_override_dbconfig_type(monkeypatch):
    """create_db: CRS environment, no dbconfig_type → RAC override (line 353)."""
    mod = _load()
    Mod = _make_db_mod(_db_params(
        state="present",
        dbconfig_type=None,
    ), responses=[
        (0, "SQL*Plus: Release 19.0.0.0.0 - Production", ""),
        (0, "Database creation successful", ""),
    ])
    m = Mod()

    class _CrsNoDb(FakeOracleHomes):
        def __init__(self):
            super().__init__()
            self.oracle_gi_managed = True
            self.oracle_crs = True
            self.facts_item = {}

    ohomes = _CrsNoDb()
    result = mod.create_db(m, ohomes)
    assert "STDOUT" in result or "successful" in result
    # RAC dbconfig was set
    assert m.params.get("dbconfig_type") == "RAC"


# ---------------------------------------------------------------------------
# Additional ensure_db_state coverage (lines 648-649, 655-656, 662-663, 687)
# ---------------------------------------------------------------------------

def test_ensure_db_state_flashback_true_diff(monkeypatch):
    """ensure_db_state: flashback=True, DB has NO → change_db_sql (lines 648-649, 683-684)."""
    _ensure_sid(monkeypatch)
    mod = _load()
    Mod = _make_db_mod(_db_params(
        state="present", flashback=True,  # want YES
        archivelog=False, force_logging=False, supplemental_logging=False,
        default_tablespace_type="bigfile",
    ))
    m = Mod()
    ohomes = _NoGiRunningDb()

    conn = _FakeConnForEnsure(m, flashback_on="NO")  # DB has NO → mismatch
    monkeypatch.setattr(mod, "oracleConnection", lambda module: conn, raising=False)

    def _fake_apply_norestart(module, change_db_sql):
        return change_db_sql

    monkeypatch.setattr(mod, "apply_norestart_changes", _fake_apply_norestart, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.ensure_db_state(m, ohomes, newdb=False)
    assert exc.value.args[0]["changed"] is True


def test_ensure_db_state_supplemental_logging_true_diff(monkeypatch):
    """ensure_db_state: supplemental_logging=True, DB has NO → change_db_sql (lines 655-656, 686-687)."""
    _ensure_sid(monkeypatch)
    mod = _load()
    Mod = _make_db_mod(_db_params(
        state="present", supplemental_logging=True,  # want YES
        archivelog=False, force_logging=False, flashback=False,
        default_tablespace_type="bigfile",
    ))
    m = Mod()
    ohomes = _NoGiRunningDb()

    conn = _FakeConnForEnsure(m, supplemental_logging="NO")  # DB has NO → mismatch
    monkeypatch.setattr(mod, "oracleConnection", lambda module: conn, raising=False)

    def _fake_apply_norestart(module, change_db_sql):
        return change_db_sql

    monkeypatch.setattr(mod, "apply_norestart_changes", _fake_apply_norestart, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.ensure_db_state(m, ohomes, newdb=False)
    assert exc.value.args[0]["changed"] is True


def test_ensure_db_state_tablespace_type_diff(monkeypatch):
    """ensure_db_state: def_tbs_type differs → tablespace type SQL (lines 662-663)."""
    _ensure_sid(monkeypatch)
    mod = _load()
    Mod = _make_db_mod(_db_params(
        state="present", default_tablespace_type="smallfile",  # want SMALLFILE
        archivelog=False, force_logging=False, flashback=False, supplemental_logging=False,
    ))
    m = Mod()
    ohomes = _NoGiRunningDb()

    conn = _FakeConnForEnsure(m, def_tbs_type="BIGFILE")  # DB has BIGFILE → mismatch
    monkeypatch.setattr(mod, "oracleConnection", lambda module: conn, raising=False)

    def _fake_apply_norestart(module, change_db_sql):
        return change_db_sql

    monkeypatch.setattr(mod, "apply_norestart_changes", _fake_apply_norestart, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.ensure_db_state(m, ohomes, newdb=False)
    assert exc.value.args[0]["changed"] is True


# ---------------------------------------------------------------------------
# apply_restart_changes test (covers lines 727-736)
# ---------------------------------------------------------------------------

def test_apply_restart_changes(monkeypatch):
    """apply_restart_changes: stop → start in mount → apply DDLs → stop → start."""
    _ensure_sid(monkeypatch)
    mod = _load()
    Mod = _make_db_mod(_db_params())
    m = Mod()
    ohomes = _NoGiRunningDb()

    ops = []

    def _fake_stop_db(module, ohomes):
        ops.append("stop")

    def _fake_start_instance(module, ohomes, open_mode, instance_name):
        ops.append(("start_instance", open_mode))

    def _fake_start_db(module, ohomes):
        ops.append("start_db")

    class _FakeConnWithDdls(BaseFakeConn):
        pass

    monkeypatch.setattr(mod, "stop_db", _fake_stop_db, raising=False)
    monkeypatch.setattr(mod, "start_instance", _fake_start_instance, raising=False)
    monkeypatch.setattr(mod, "start_db", _fake_start_db, raising=False)
    monkeypatch.setattr(mod, "oracleConnection", _FakeConnWithDdls, raising=False)

    result = mod.apply_restart_changes(m, ohomes, "TESTDB", ["alter database archivelog"])
    assert "stop" in ops
    assert any(o[0] == "start_instance" for o in ops if isinstance(o, tuple))


# ---------------------------------------------------------------------------
# stop_db / start_db: crsname None + db_unique_name path (lines 754, 756, 788, 790)
# ---------------------------------------------------------------------------

def test_stop_db_gi_crsname_none_with_db_unique_name(monkeypatch):
    """stop_db: GI, crsname=None + db_unique_name set → uses db_unique_name (line 754)."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        class _GiRunningDbNoCrsname(_GiRunningDb):
            def __init__(self):
                super().__init__()
                self.facts_item["TESTDB"]["crsname"] = None  # no crsname

        Mod = _make_db_mod(_db_params(db_unique_name="TESTDB_UQ"), responses=[
            (0, "", ""),  # srvctl stop
        ])
        m = Mod()
        ohomes = _GiRunningDbNoCrsname()
        mod.stop_db(m, ohomes)
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_stop_db_gi_crsname_none_no_db_unique_name(monkeypatch):
    """stop_db: GI, crsname=None + no db_unique_name → uses db_name (line 756)."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        class _GiRunningDbNoCrsname(_GiRunningDb):
            def __init__(self):
                super().__init__()
                self.facts_item["TESTDB"]["crsname"] = None

        Mod = _make_db_mod(_db_params(db_unique_name=None), responses=[
            (0, "", ""),  # srvctl stop
        ])
        m = Mod()
        ohomes = _GiRunningDbNoCrsname()
        mod.stop_db(m, ohomes)
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_start_db_gi_crsname_none_with_db_unique_name(monkeypatch):
    """start_db: GI, crsname=None + db_unique_name set → uses db_unique_name (line 788)."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        class _GiRunningDbNoCrsname(_GiRunningDb):
            def __init__(self):
                super().__init__()
                self.facts_item["TESTDB"]["crsname"] = None

        Mod = _make_db_mod(_db_params(db_unique_name="TESTDB_UQ"), responses=[
            (0, "", ""),  # srvctl start
        ])
        m = Mod()
        ohomes = _GiRunningDbNoCrsname()
        mod.start_db(m, ohomes)
    finally:
        os.environ.pop("ORACLE_SID", None)


def test_start_db_gi_crsname_none_no_db_unique_name(monkeypatch):
    """start_db: GI, crsname=None + no db_unique_name → uses db_name (line 790)."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    try:
        class _GiRunningDbNoCrsname(_GiRunningDb):
            def __init__(self):
                super().__init__()
                self.facts_item["TESTDB"]["crsname"] = None

        Mod = _make_db_mod(_db_params(db_unique_name=None), responses=[
            (0, "", ""),  # srvctl start
        ])
        m = Mod()
        ohomes = _GiRunningDbNoCrsname()
        mod.start_db(m, ohomes)
    finally:
        os.environ.pop("ORACLE_SID", None)


# ---------------------------------------------------------------------------
# main() additional paths
# ---------------------------------------------------------------------------

def test_main_db_unique_name_sets_service_name(monkeypatch):
    """main(): db_unique_name set → service_name uses it (line 943)."""
    mod = _load()
    Mod = _make_main_mod("absent", extra_params={"db_unique_name": "TESTDB_UQ"})
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesForMain, raising=False)
    os.environ.pop("ORACLE_SID", None)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
