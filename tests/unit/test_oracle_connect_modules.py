"""Unit tests for modules using oracle_connect() + raw cursor API.

Covers: oracle_asmdg, oracle_asmvol, oracle_stats_prefs, oracle_redo.

These modules use oracle_connect(module) which returns a raw oracledb
connection.  We monkeypatch `mod.oracle_connect` to return a
SequencedFakeOracleConn that returns preset fetchall() results in order.
"""
import pytest

from conftest import ExitJson, FailJson, load_module_from_path
from helpers import (
    BASE_CONN_PARAMS,
    BaseFakeModule,
    FakeOracleConn,
    FakeOracleDb,
    SequencedFakeOracleConn,
    _FakeCursor,
    _FakeVar,
)


def _load(name):
    return load_module_from_path(f"plugins/modules/{name}.py", name)


# ===========================================================================
# oracle_asmdg
# ===========================================================================

def _asmdg_params(**overrides):
    base = {
        "name": "DATA",
        "disks": ["/dev/sdb1"],
        "redundancy": "external",
        "attribute_name": [],
        "attribute_value": [],
        "state": "present",
        "user": None,
        "password": None,
        "hostname": "localhost",
        "port": 1521,
        "service_name": "+ASM",
        "oracle_home": None,
    }
    base.update(overrides)
    return base


class _AsmdgFakeModule(BaseFakeModule):
    params = {}

    def run_command(self, cmd, **_kw):
        return (0, "", "")


def _asmdg_mod(params, fetchall_seq):
    """Create a fake module instance with sequenced fetchall results."""
    conn = SequencedFakeOracleConn(fetchall_seq)

    class Mod(_AsmdgFakeModule):
        _params = params

        def __init__(self, **kw):
            super().__init__(**kw)
            self.params = dict(self.__class__._params)
            self._conn = conn

    return Mod, conn


def test_asmdg_absent_missing(monkeypatch):
    """state=absent, diskgroup not found → already absent."""
    mod = _load("oracle_asmdg")
    Mod, conn = _asmdg_mod(_asmdg_params(state="absent"), [
        [("NO",)],  # RAC check → NO
        [(0,)],     # check_diskgroup_exists → count=0 → not found
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_asmdg_absent_existing_drops(monkeypatch):
    """state=absent, diskgroup exists → drops it."""
    mod = _load("oracle_asmdg")
    Mod, conn = _asmdg_mod(_asmdg_params(state="absent"), [
        [("NO",)],  # RAC check
        [(1,)],     # check_diskgroup_exists → found
        # remove_diskgroup uses execute_sql (no fetchall) - just execute
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_asmdg_present_creates(monkeypatch):
    """state=present, diskgroup not found → creates it."""
    mod = _load("oracle_asmdg")
    Mod, conn = _asmdg_mod(_asmdg_params(), [
        [("NO",)],  # RAC check
        [(0,)],     # check_diskgroup_exists → not found
        # create_diskgroup uses execute_sql (no fetchall)
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_asmdg_present_existing_status(monkeypatch):
    """state=status → returns disk configuration info."""
    mod = _load("oracle_asmdg")
    Mod, conn = _asmdg_mod(_asmdg_params(state="status"), [
        [("NO",)],                              # RAC check
        [(1,)],                                 # check_diskgroup_exists → found
        [("/dev/sdb1", "DATA_0000")],           # get_current_disks
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_asmdg_gi_managed_needs_oracle_home(monkeypatch):
    """RAC=YES requires oracle_home → fail_json without it."""
    mod = _load("oracle_asmdg")
    import os
    orig = os.environ.pop("ORACLE_HOME", None)
    try:
        Mod, conn = _asmdg_mod(_asmdg_params(), [
            [("YES",)],  # RAC check → YES (needs oracle_home)
        ])
        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
        monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

        with pytest.raises(FailJson):
            mod.main()
    finally:
        if orig is not None:
            os.environ["ORACLE_HOME"] = orig


def test_asmdg_rac_with_oracle_home_param(monkeypatch):
    """RAC=YES with oracle_home param → sets ORACLE_HOME env var, then creates DG."""
    import os
    mod = _load("oracle_asmdg")
    Mod, conn = _asmdg_mod(_asmdg_params(oracle_home="/u01/grid"), [
        [("YES",)],   # RAC check → YES
        [(0,)],       # check_diskgroup_exists → not found
        # create_diskgroup: execute_sql (no fetchall needed)
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_asmdg_rac_oracle_home_from_env(monkeypatch):
    """RAC=YES, oracle_home not in params but ORACLE_HOME in env → uses env value."""
    import os
    mod = _load("oracle_asmdg")
    orig = os.environ.get("ORACLE_HOME")
    os.environ["ORACLE_HOME"] = "/u01/grid/from/env"
    try:
        Mod, conn = _asmdg_mod(_asmdg_params(), [
            [("YES",)],   # RAC check → YES
            [(0,)],       # check_diskgroup_exists → not found
        ])
        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
        monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

        with pytest.raises(ExitJson) as exc:
            mod.main()
        assert exc.value.args[0]["changed"] is True
    finally:
        if orig is not None:
            os.environ["ORACLE_HOME"] = orig
        else:
            os.environ.pop("ORACLE_HOME", None)


def test_asmdg_present_existing_no_change(monkeypatch):
    """state=present, diskgroup exists, disks already match → no change."""
    mod = _load("oracle_asmdg")
    Mod, conn = _asmdg_mod(_asmdg_params(disks=["/dev/sdb1"]), [
        [("NO",)],              # RAC check
        [(1,)],                 # check_diskgroup_exists → found
        [("/dev/sdb1", "DATA_0000")],  # get_current_disks → same disk
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_asmdg_present_existing_add_disk(monkeypatch):
    """state=present, diskgroup exists, new disk added → changed=True."""
    mod = _load("oracle_asmdg")
    Mod, conn = _asmdg_mod(_asmdg_params(disks=["/dev/sdb1", "/dev/sdc1"]), [
        [("NO",)],                      # RAC check
        [(1,)],                         # check_diskgroup_exists → found
        [("/dev/sdb1", "DATA_0000")],   # get_current_disks → only one disk currently
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_asmdg_present_existing_remove_disk(monkeypatch):
    """state=present, diskgroup exists, old disk removed from list → changed=True."""
    mod = _load("oracle_asmdg")
    # Wanted: only /dev/sdb1; Current: /dev/sdb1 + /dev/sdc1 → remove sdc1
    Mod, conn = _asmdg_mod(_asmdg_params(disks=["/dev/sdb1"]), [
        [("NO",)],                                      # RAC check
        [(1,)],                                         # check_diskgroup_exists → found
        [("/dev/sdb1", "DATA_0000"), ("/dev/sdc1", "DATA_0001")],  # get_current_disks
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_asmdg_oracledb_missing_fails(monkeypatch):
    """oracledb not installed → fail_json immediately."""
    mod = _load("oracle_asmdg")
    Mod, conn = _asmdg_mod(_asmdg_params(), [])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb_exists", False, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "oracledb" in exc.value.args[0]["msg"].lower()


def test_asmdg_absent_existing_remove_fails(monkeypatch):
    """state=absent, diskgroup exists but remove_diskgroup returns False → exit_json changed=False."""
    mod = _load("oracle_asmdg")

    class _FailCursor:
        """Cursor that raises DatabaseError on execute for drop SQL."""
        def __init__(self, conn):
            self._conn = conn

        def execute(self, sql, params=None):
            self._conn.ddls.append(sql)
            if "drop diskgroup" in sql.lower():
                err = type("E", (), {"message": "ORA-15039: diskgroup not dropped"})()
                raise FakeOracleDb.DatabaseError(err)

        def fetchall(self):
            return self._conn._fetchall_seq.pop(0) if self._conn._fetchall_seq else []

        def fetchone(self):
            return self._conn._fetchone_row

        @property
        def rowcount(self):
            return 1 if self._conn._fetchone_row is not None else 0

    class _FailConn(SequencedFakeOracleConn):
        def cursor(self):
            return _FailCursor(self)

    fail_conn = _FailConn([
        [("NO",)],   # RAC check
        [(1,)],      # check_diskgroup_exists → found
    ])

    class Mod(_AsmdgFakeModule):
        _params = _asmdg_params(state="absent")

        def __init__(self, **kw):
            super().__init__(**kw)
            self.params = dict(self.__class__._params)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: fail_conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_asmdg_status_not_found(monkeypatch):
    """state=status, diskgroup not found → exit_json changed=False."""
    mod = _load("oracle_asmdg")
    Mod, conn = _asmdg_mod(_asmdg_params(state="status"), [
        [("NO",)],   # RAC check
        [(0,)],      # check_diskgroup_exists → count=0 → not found
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_asmdg_present_create_with_attributes(monkeypatch):
    """state=present, DG not found, attribute_name/value set → create with attributes."""
    mod = _load("oracle_asmdg")
    Mod, conn = _asmdg_mod(
        _asmdg_params(attribute_name=["compatible.asm"], attribute_value=["12.2"]),
        [
            [("NO",)],   # RAC check
            [(0,)],      # check_diskgroup_exists → not found
            # create_diskgroup: add_attr=True path (execute_sql, no fetchall)
        ]
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    # Verify the CREATE DISKGROUP SQL contains ATTRIBUTE clause
    create_sqls = [s for s in conn.ddls if "create diskgroup" in s.lower()]
    assert create_sqls
    assert "attribute" in create_sqls[0].lower()


def test_asmdg_execute_sql_get_error(monkeypatch):
    """execute_sql_get raises DatabaseError → fail_json."""
    import os
    mod = _load("oracle_asmdg")

    class _ErrorCursor:
        def __init__(self, conn):
            self._conn = conn

        def execute(self, sql, params=None):
            err = type("E", (), {"message": "ORA-00942: table or view does not exist"})()
            raise FakeOracleDb.DatabaseError(err)

        def fetchall(self):
            return []

        @property
        def rowcount(self):
            return 0

    class _ErrorConn(FakeOracleConn):
        def cursor(self):
            return _ErrorCursor(self)

    class Mod(_AsmdgFakeModule):
        _params = _asmdg_params()

        def __init__(self, **kw):
            super().__init__(**kw)
            self.params = dict(self.__class__._params)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: _ErrorConn(), raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_asmdg_present_rac_create_with_srvctl(monkeypatch):
    """RAC=YES + create new DG → srvctl start diskgroup called."""
    import os
    mod = _load("oracle_asmdg")

    # Track run_command calls
    run_cmds = []

    class _RacMod(_AsmdgFakeModule):
        _params = _asmdg_params(oracle_home="/u01/grid")

        def __init__(self, **kw):
            super().__init__(**kw)
            self.params = dict(self.__class__._params)
            self._conn = None

        def run_command(self, cmd, **_kw):
            run_cmds.append(cmd)
            return (0, "", "")

    Mod = _RacMod

    conn = SequencedFakeOracleConn([
        [("YES",)],  # RAC check → YES
        [(0,)],      # check_diskgroup_exists → not found
        # create_diskgroup → execute_sql (no fetchall)
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    # srvctl start diskgroup should be called for RAC
    assert any("srvctl" in str(c) for c in run_cmds)


def test_asmdg_absent_rac_remove(monkeypatch):
    """RAC=YES + remove existing DG → srvctl stop diskgroup called."""
    mod = _load("oracle_asmdg")
    run_cmds = []

    class _RacMod(_AsmdgFakeModule):
        _params = _asmdg_params(state="absent", oracle_home="/u01/grid")

        def __init__(self, **kw):
            super().__init__(**kw)
            self.params = dict(self.__class__._params)

        def run_command(self, cmd, **_kw):
            run_cmds.append(cmd)
            return (0, "", "")

    Mod = _RacMod

    conn = SequencedFakeOracleConn([
        [("YES",)],  # RAC check → YES
        [(1,)],      # check_diskgroup_exists → found
        # remove_diskgroup in rac mode calls srvctl stop, then mount+drop
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("srvctl" in str(c) for c in run_cmds)


def test_asmdg_absent_rac_stop_fails(monkeypatch):
    """RAC=YES + remove DG + srvctl stop fails → exit_json changed=False (lines 192-193, 424)."""
    mod = _load("oracle_asmdg")

    class _FailStopMod(_AsmdgFakeModule):
        _params = _asmdg_params(state="absent", oracle_home="/u01/grid")

        def __init__(self, **kw):
            super().__init__(**kw)
            self.params = dict(self.__class__._params)

        def run_command(self, cmd, **_kw):
            return (1, "", "CRS-5000: Cannot stop resource")

    Mod = _FailStopMod

    conn = SequencedFakeOracleConn([
        [("YES",)],  # RAC check → YES
        [(1,)],      # check_diskgroup_exists → found
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_asmdg_present_rac_create_crs5702(monkeypatch):
    """RAC=YES + create DG + srvctl start returns CRS-5702 → success (line 166-167)."""
    mod = _load("oracle_asmdg")

    class _Crs5702Mod(_AsmdgFakeModule):
        _params = _asmdg_params(oracle_home="/u01/grid")

        def __init__(self, **kw):
            super().__init__(**kw)
            self.params = dict(self.__class__._params)

        def run_command(self, cmd, **_kw):
            return (1, "CRS-5702: Resource 'ora.data.dg' is already running on 'node1'", "")

    Mod = _Crs5702Mod

    conn = SequencedFakeOracleConn([
        [("YES",)],  # RAC check → YES
        [(0,)],      # check_diskgroup_exists → not found → create
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_asmdg_present_rac_create_srvctl_fails(monkeypatch):
    """RAC=YES + create DG + srvctl start fails (no CRS-5702) → fail_json (lines 168-170)."""
    mod = _load("oracle_asmdg")

    class _SrvctlFailMod(_AsmdgFakeModule):
        _params = _asmdg_params(oracle_home="/u01/grid")

        def __init__(self, **kw):
            super().__init__(**kw)
            self.params = dict(self.__class__._params)

        def run_command(self, cmd, **_kw):
            return (1, "PRCR-1004: Cannot start resource", "error detail")

    Mod = _SrvctlFailMod

    conn = SequencedFakeOracleConn([
        [("YES",)],  # RAC check → YES
        [(0,)],      # check_diskgroup_exists → not found → create
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(FailJson):
        mod.main()


# ===========================================================================
# oracle_asmvol
# ===========================================================================

def _asmvol_params(**overrides):
    base = {
        "name": "ACFSVOL",
        "diskgroup": "DATA",
        "size": "10G",
        "column": None,
        "width": None,
        "redundancy": None,
        "state": "present",
        "user": None,
        "password": None,
        "hostname": "localhost",
        "port": 1521,
        "service_name": "+ASM",
        "oracle_home": None,
    }
    base.update(overrides)
    return base


def _asmvol_mod(params, fetchall_seq):
    conn = SequencedFakeOracleConn(fetchall_seq)

    class Mod(BaseFakeModule):
        _params = params

        def __init__(self, **kw):
            super().__init__(**kw)
            self.params = dict(self.__class__._params)

    return Mod, conn


def test_asmvol_absent_missing(monkeypatch):
    """state=absent, volume not found → already absent."""
    mod = _load("oracle_asmvol")
    Mod, conn = _asmvol_mod(_asmvol_params(state="absent"), [
        [(0,)],  # check_vol_exists → count=0 → not found
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_asmvol_absent_existing_drops(monkeypatch):
    """state=absent, volume exists → drops it."""
    mod = _load("oracle_asmvol")
    Mod, conn = _asmvol_mod(_asmvol_params(state="absent"), [
        [(1,)],  # check_vol_exists → found
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_asmvol_present_creates(monkeypatch):
    """state=present, volume not found → creates it."""
    mod = _load("oracle_asmvol")
    Mod, conn = _asmvol_mod(_asmvol_params(), [
        [(0,)],  # check_vol_exists → not found
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_asmvol_present_already_exists(monkeypatch):
    """state=present, volume exists → already exists, no change."""
    mod = _load("oracle_asmvol")
    Mod, conn = _asmvol_mod(_asmvol_params(), [
        [(1,)],  # check_vol_exists → found
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_asmvol_present_no_size_fails(monkeypatch):
    """state=present, no size provided → fail_json."""
    mod = _load("oracle_asmvol")
    Mod, conn = _asmvol_mod(_asmvol_params(size=None), [
        [(0,)],  # check_vol_exists → not found
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_asmvol_oracledb_not_installed_fails(monkeypatch):
    """oracledb not installed → fail_json with message about oracledb."""
    mod = _load("oracle_asmvol")
    monkeypatch.setattr(mod, "oracledb_exists", False, raising=False)
    Mod, conn = _asmvol_mod(_asmvol_params(), [])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "oracledb" in exc.value.args[0]["msg"]


def test_asmvol_execute_sql_get_db_error(monkeypatch):
    """execute_sql_get: cursor.execute raises DatabaseError → fail_json."""
    mod = _load("oracle_asmvol")
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    class _ErrObj:
        message = "ORA-00001: unique constraint violated"

    class _ThrowingCursor:
        def execute(self, sql, params=None):
            raise Exception(_ErrObj())
        def fetchall(self):
            return []

    class Mod(BaseFakeModule):
        params = _asmvol_params()

    with pytest.raises(FailJson):
        mod.execute_sql_get(Mod(), [], _ThrowingCursor(), "SELECT 1 FROM DUAL")


def test_asmvol_execute_sql_db_error(monkeypatch):
    """execute_sql: cursor.execute raises DatabaseError → fail_json."""
    mod = _load("oracle_asmvol")
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    class _ErrObj:
        message = "ORA-01031: insufficient privileges"

    class _ThrowingCursor:
        def execute(self, sql, params=None):
            raise Exception(_ErrObj())

    class Mod(BaseFakeModule):
        params = _asmvol_params()

    with pytest.raises(FailJson):
        mod.execute_sql(Mod(), [], _ThrowingCursor(), "ALTER DISKGROUP DATA ADD VOLUME v1 SIZE 10G")


# ===========================================================================
# oracle_stats_prefs
# ===========================================================================

class _StatsPrefsCursor(_FakeCursor):
    """Cursor that sets output var values on execute()."""

    def __init__(self, conn, changed_val=0, msg_val="Not changed"):
        super().__init__(conn)
        self._changed_val = changed_val
        self._msg_val = msg_val
        self._created_vars = []

    def var(self, typ):
        v = _FakeVar()
        self._created_vars.append(v)
        return v

    def execute(self, sql, params=None):
        super().execute(sql, params)
        # Set output vars: [0]=changed (NUMBER), [1]=msg (STRING)
        if len(self._created_vars) >= 2:
            self._created_vars[0]._value = self._changed_val
            self._created_vars[1]._value = self._msg_val


class _StatsPrefsFakeConn(FakeOracleConn):
    def __init__(self, changed_val=0, msg_val="Not changed"):
        super().__init__()
        self.version = "19.0.0"
        self._changed_val = changed_val
        self._msg_val = msg_val

    def cursor(self):
        return _StatsPrefsCursor(self, self._changed_val, self._msg_val)


def _sp_params(**overrides):
    base = {
        "hostname": "localhost",
        "port": 1521,
        "service_name": "svc",
        "user": "u",
        "password": "p",
        "mode": "normal",
        "preference_name": "AUTOSTATS_TARGET",
        "preference_value": "AUTO",
        "state": "present",
    }
    base.update(overrides)
    return base


def test_stats_prefs_no_change(monkeypatch):
    """state=present, preference already set → changed=False."""
    mod = _load("oracle_stats_prefs")
    conn = _StatsPrefsFakeConn(changed_val=0, msg_val="Not changed")

    class Mod(BaseFakeModule):
        params = _sp_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_stats_prefs_change(monkeypatch):
    """state=present, preference differs → changed=True."""
    mod = _load("oracle_stats_prefs")
    conn = _StatsPrefsFakeConn(changed_val=1, msg_val="Old value MANUAL changed to AUTO")

    class Mod(BaseFakeModule):
        params = _sp_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_stats_prefs_absent_resets(monkeypatch):
    """state=absent → reset to default → changed=True."""
    mod = _load("oracle_stats_prefs")
    conn = _StatsPrefsFakeConn(changed_val=1, msg_val="Value reset to default MANUAL")

    class Mod(BaseFakeModule):
        params = _sp_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_stats_prefs_check_mode(monkeypatch):
    """check_mode=True → exits early with changed=False."""
    mod = _load("oracle_stats_prefs")
    conn = _StatsPrefsFakeConn(changed_val=1, msg_val="would change")

    class Mod(BaseFakeModule):
        params = _sp_params()
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_stats_prefs_old_db_fails(monkeypatch):
    """DB version < 10.2 → fail_json."""
    mod = _load("oracle_stats_prefs")
    conn = _StatsPrefsFakeConn()
    conn.version = "10.1.0"  # < "10.2" in lexicographic order → triggers version check

    class Mod(BaseFakeModule):
        params = _sp_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(FailJson):
        mod.main()


# ===========================================================================
# oracle_redo
# ===========================================================================

class _RedoCursor(_FakeCursor):
    """Cursor that sets output vars on execute() for redo PL/SQL block."""

    def __init__(self, conn, size_changed=0, group_changed=0,
                 size_msg="No size change", group_msg="No group change"):
        super().__init__(conn)
        self._size_changed = size_changed
        self._group_changed = group_changed
        self._size_msg = size_msg
        self._group_msg = group_msg
        self._created_vars = []

    def var(self, typ):
        v = _FakeVar()
        self._created_vars.append(v)
        return v

    def execute(self, sql, params=None):
        super().execute(sql, params)
        # Vars order: size_changed, group_changed, size_msg, group_msg
        values = [self._size_changed, self._group_changed,
                  self._size_msg, self._group_msg]
        for i, val in enumerate(values):
            if i < len(self._created_vars):
                self._created_vars[i]._value = val


class _RedoFakeConn(FakeOracleConn):
    def __init__(self, size_changed=0, group_changed=0,
                 size_msg="", group_msg=""):
        super().__init__()
        self.version = "19.0.0"
        self._size_changed = size_changed
        self._group_changed = group_changed
        self._size_msg = size_msg
        self._group_msg = group_msg

    def cursor(self):
        return _RedoCursor(self, self._size_changed, self._group_changed,
                           self._size_msg, self._group_msg)


def _redo_params(**overrides):
    base = {
        "hostname": "localhost",
        "port": 1521,
        "service_name": "svc",
        "user": "u",
        "password": "p",
        "mode": "normal",
        "size": "200M",
        "groups": 3,
        "log_type": "redo",
    }
    base.update(overrides)
    return base


def test_redo_no_change(monkeypatch):
    """No size or group changes needed → changed=False."""
    mod = _load("oracle_redo")
    conn = _RedoFakeConn(size_changed=0, group_changed=0)

    class Mod(BaseFakeModule):
        params = _redo_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_redo_size_change(monkeypatch):
    """Size change needed → changed=True."""
    mod = _load("oracle_redo")
    conn = _RedoFakeConn(size_changed=1, group_changed=0,
                         size_msg="Redo log resized")

    class Mod(BaseFakeModule):
        params = _redo_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_redo_group_change(monkeypatch):
    """Group count change needed → changed=True."""
    mod = _load("oracle_redo")
    conn = _RedoFakeConn(size_changed=0, group_changed=1,
                         group_msg="Groups added")

    class Mod(BaseFakeModule):
        params = _redo_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_redo_invalid_size_fails(monkeypatch):
    """size without M/G/T suffix → fail_json."""
    mod = _load("oracle_redo")
    conn = _RedoFakeConn()

    class Mod(BaseFakeModule):
        params = _redo_params(size="200")  # no M/G/T suffix

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_redo_standby_type(monkeypatch):
    """log_type=standby → executes standby SQL block."""
    mod = _load("oracle_redo")
    conn = _RedoFakeConn(size_changed=0, group_changed=0)

    class Mod(BaseFakeModule):
        params = _redo_params(log_type="standby")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracle_connect", lambda m: conn, raising=False)
    monkeypatch.setattr(mod, "oracledb", FakeOracleDb, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
