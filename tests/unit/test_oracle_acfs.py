"""Unit tests for oracle_acfs module.

oracle_acfs.py manages ACFS filesystems and requires an ASM database
connection for most paths. We test the pure run_command helpers and the
main() early-exit path when oracledb is missing.
"""
import pytest

from conftest import ExitJson, FailJson, load_module_from_path
from helpers import BaseFakeModule


def _load():
    return load_module_from_path("plugins/modules/oracle_acfs.py", "oracle_acfs")


def _acfs_params(**overrides):
    base = {
        "volume_name": "MYVOL",
        "diskgroup": "DATA",
        "mountpoint": "/acfs/mnt",
        "mountowner": "oracle",
        "mountgroup": "dba",
        "mountperm": "755",
        "mountusers": "oracle",
        "state": "present",
        "user": "sys",
        "password": "secret",
        "hostname": "localhost",
        "port": 1521,
        "service_name": "+ASM",
        "oracle_home": "/fake/grid",
    }
    base.update(overrides)
    return base


def _make_mod(params, responses=None):
    _resp = list(responses or [])

    class Mod(BaseFakeModule):
        def run_command(self, cmd, **kw):
            return _resp.pop(0) if _resp else (0, "", "")

    Mod.params = params
    return Mod


# ---------------------------------------------------------------------------
# _format_filesystem tests (lines 196-207)
# ---------------------------------------------------------------------------

def test_format_filesystem_success(monkeypatch):
    """_format_filesystem: mkfs succeeds → True."""
    mod = _load()
    m = _make_mod(_acfs_params(), [(0, "", "")])()
    result = mod._format_filesystem(m, [], "/dev/asm/MYVOL")
    assert result is True


def test_format_filesystem_already_formatted(monkeypatch):
    """_format_filesystem: ACFS-01010 in stderr → already formatted → True (line 201-202)."""
    mod = _load()
    m = _make_mod(_acfs_params(), [(1, "", "ACFS-01010 device already formatted")])()
    result = mod._format_filesystem(m, [], "/dev/asm/MYVOL")
    assert result is True


def test_format_filesystem_other_error(monkeypatch):
    """_format_filesystem: other error → fail_json (lines 203-205)."""
    mod = _load()
    m = _make_mod(_acfs_params(), [(1, "error output", "other error")])()
    with pytest.raises(FailJson):
        mod._format_filesystem(m, [], "/dev/asm/MYVOL")


# ---------------------------------------------------------------------------
# _start_filesystem tests (lines 162-175)
# ---------------------------------------------------------------------------

def test_start_filesystem_success(monkeypatch):
    """_start_filesystem: srvctl start filesystem succeeds → True."""
    mod = _load()
    m = _make_mod(_acfs_params(), [(0, "", "")])()
    result = mod._start_filesystem(None, m, [], "/fake/grid", "MYVOL", "DATA", "/acfs/mnt")
    assert result is True


def test_start_filesystem_already_running(monkeypatch):
    """_start_filesystem: CRS-5702 in stdout → already running → exit_json (lines 167-169)."""
    mod = _load()
    m = _make_mod(_acfs_params(), [(1, "CRS-5702 filesystem already mounted", "")])()
    with pytest.raises(ExitJson) as exc:
        mod._start_filesystem(None, m, [], "/fake/grid", "MYVOL", "DATA", "/acfs/mnt")
    assert exc.value.args[0]["changed"] is False


def test_start_filesystem_other_error(monkeypatch):
    """_start_filesystem: other error → fail_json (lines 171-173)."""
    mod = _load()
    m = _make_mod(_acfs_params(), [(1, "some other error", "")])()
    with pytest.raises(FailJson):
        mod._start_filesystem(None, m, [], "/fake/grid", "MYVOL", "DATA", "/acfs/mnt")


# ---------------------------------------------------------------------------
# _check_filesystem_exist tests (lines 146-158)
# ---------------------------------------------------------------------------

def test_check_filesystem_exist_true(monkeypatch):
    """_check_filesystem_exist: rc=0 → True (lines 157-158)."""
    mod = _load()
    m = _make_mod(_acfs_params(), [(0, "filesystem is running", "")])()
    result = mod._check_filesystem_exist(None, m, [], "/fake/grid", [("/dev/asm/MYVOL",)])
    assert result is True


def test_check_filesystem_exist_prca1070(monkeypatch):
    """_check_filesystem_exist: PRCA-1070 → not found → False (lines 150-152)."""
    mod = _load()
    m = _make_mod(_acfs_params(), [(1, "PRCA-1070 filesystem not found", "")])()
    result = mod._check_filesystem_exist(None, m, [], "/fake/grid", [("/dev/asm/MYVOL",)])
    assert result is False


# ---------------------------------------------------------------------------
# check_volume_exists tests (lines 87-101)
# ---------------------------------------------------------------------------

def test_check_volume_exists_true(monkeypatch):
    """check_volume_exists: execute_sql_get returns count > 0 → True (lines 95-99)."""
    mod = _load()

    def _fake_esget(module, msg, cursor, sql):
        return [(1,)]

    monkeypatch.setattr(mod, "execute_sql_get", _fake_esget, raising=False)
    m = _make_mod(_acfs_params())()
    result = mod.check_volume_exists(None, m, [], "MYVOL", "DATA")
    assert result is True


def test_check_volume_exists_false(monkeypatch):
    """check_volume_exists: count = 0 → False (line 100-101)."""
    mod = _load()

    def _fake_esget(module, msg, cursor, sql):
        return [(0,)]

    monkeypatch.setattr(mod, "execute_sql_get", _fake_esget, raising=False)
    m = _make_mod(_acfs_params())()
    result = mod.check_volume_exists(None, m, [], "MYVOL", "DATA")
    assert result is False


# ---------------------------------------------------------------------------
# add_filesystem tests (lines 103-133)
# ---------------------------------------------------------------------------

def test_add_filesystem_already_exists(monkeypatch):
    """add_filesystem: filesystem already exists → return True (lines 130-133)."""
    mod = _load()

    def _fake_esget(module, msg, cursor, sql):
        return [("/dev/asm/MYVOL",)]

    def _fake_check(cursor, module, msg, oracle_home, _device_name):
        return True  # filesystem already mounted

    monkeypatch.setattr(mod, "execute_sql_get", _fake_esget, raising=False)
    monkeypatch.setattr(mod, "_check_filesystem_exist", _fake_check, raising=False)
    m = _make_mod(_acfs_params())()
    result = mod.add_filesystem(
        None, m, [], "/fake/grid", "MYVOL", "DATA", "/acfs/mnt",
        "oracle", "dba", "755", "oracle"
    )
    assert result is True


def test_add_filesystem_new_success(monkeypatch):
    """add_filesystem: not mounted, format ok, srvctl add ok → True (lines 106-129)."""
    mod = _load()

    def _fake_esget(module, msg, cursor, sql):
        return [("/dev/asm/MYVOL",)]

    def _fake_check(cursor, module, msg, oracle_home, _device_name):
        return False

    def _fake_format(module, msg, _device_name):
        return True

    monkeypatch.setattr(mod, "execute_sql_get", _fake_esget, raising=False)
    monkeypatch.setattr(mod, "_check_filesystem_exist", _fake_check, raising=False)
    monkeypatch.setattr(mod, "_format_filesystem", _fake_format, raising=False)
    m = _make_mod(_acfs_params(), [(0, "", "")])()
    result = mod.add_filesystem(
        None, m, [], "/fake/grid", "MYVOL", "DATA", "/acfs/mnt",
        "oracle", "dba", "755", "oracle"
    )
    assert result is True


def test_add_filesystem_srvctl_fails(monkeypatch):
    """add_filesystem: srvctl add fails → fail_json (lines 125-127)."""
    mod = _load()

    def _fake_esget(module, msg, cursor, sql):
        return [("/dev/asm/MYVOL",)]

    def _fake_check(cursor, module, msg, oracle_home, _device_name):
        return False

    def _fake_format(module, msg, _device_name):
        return True

    monkeypatch.setattr(mod, "execute_sql_get", _fake_esget, raising=False)
    monkeypatch.setattr(mod, "_check_filesystem_exist", _fake_check, raising=False)
    monkeypatch.setattr(mod, "_format_filesystem", _fake_format, raising=False)
    m = _make_mod(_acfs_params(), [(1, "error", "srvctl error")])()
    with pytest.raises(FailJson):
        mod.add_filesystem(
            None, m, [], "/fake/grid", "MYVOL", "DATA", "/acfs/mnt",
            "oracle", "dba", "755", "oracle"
        )


# ---------------------------------------------------------------------------
# ensure_filesystem tests (lines 135-144)
# ---------------------------------------------------------------------------

def test_ensure_filesystem_present(monkeypatch):
    """ensure_filesystem: state=present, _start_filesystem returns True → exit changed=True."""
    mod = _load()
    monkeypatch.setattr(mod, "state", "present", raising=False)

    started = []

    def _fake_start(cursor, module, msg, oracle_home, volume_name, diskgroup, mountpoint):
        started.append(True)
        return True

    monkeypatch.setattr(mod, "_start_filesystem", _fake_start, raising=False)
    m = _make_mod(_acfs_params())()

    with pytest.raises(ExitJson) as exc:
        mod.ensure_filesystem(
            None, m, [], "/fake/grid", "MYVOL", "DATA", "/acfs/mnt",
            "oracle", "dba", "755", "oracle"
        )
    assert exc.value.args[0]["changed"] is True
    assert started


def test_ensure_filesystem_absent(monkeypatch):
    """ensure_filesystem: state=absent, _stop_filesystem returns True → exit changed=True."""
    mod = _load()
    monkeypatch.setattr(mod, "state", "absent", raising=False)

    stopped = []

    def _fake_stop(cursor, module, msg, oracle_home, volume_name, diskgroup, mountpoint):
        stopped.append(True)
        return True

    monkeypatch.setattr(mod, "_stop_filesystem", _fake_stop, raising=False)
    m = _make_mod(_acfs_params())()

    with pytest.raises(ExitJson) as exc:
        mod.ensure_filesystem(
            None, m, [], "/fake/grid", "MYVOL", "DATA", "/acfs/mnt",
            "oracle", "dba", "755", "oracle"
        )
    assert exc.value.args[0]["changed"] is True
    assert stopped


# ---------------------------------------------------------------------------
# execute_sql_get / execute_sql tests (lines 211-235)
# ---------------------------------------------------------------------------

def test_execute_sql_get_success(monkeypatch):
    """execute_sql_get: cursor.execute + fetchall succeeds → returns result (lines 214-223)."""
    mod = _load()

    class FakeCursor:
        def execute(self, sql):
            pass

        def fetchall(self):
            return [("SOMEVALUE",)]

    m = _make_mod(_acfs_params())()
    result = mod.execute_sql_get(m, [], FakeCursor(), "select 1 from dual")
    assert result == [("SOMEVALUE",)]


def test_execute_sql_success(monkeypatch):
    """execute_sql: cursor.execute succeeds → True (lines 228-235)."""
    mod = _load()

    class FakeCursor:
        def execute(self, sql):
            pass

    m = _make_mod(_acfs_params())()
    result = mod.execute_sql(m, [], FakeCursor(), "begin null; end;")
    assert result is True


# ---------------------------------------------------------------------------
# execute_sql_get / execute_sql DatabaseError paths (lines 217-221, 230-234)
# ---------------------------------------------------------------------------

def _make_fake_oracledb():
    """Create a fake oracledb module with DatabaseError class."""
    class _FakeDbError:
        message = "fake DB error"

    FakeDbExc = type("DatabaseError", (Exception,), {})

    class FakeOradb:
        DatabaseError = FakeDbExc
        _fake_error_obj = _FakeDbError()

    return FakeOradb


def test_execute_sql_get_database_error(monkeypatch):
    """execute_sql_get: cursor raises DatabaseError → fail_json (lines 217-221)."""
    mod = _load()
    FakeOradb = _make_fake_oracledb()
    monkeypatch.setattr(mod, "oracledb", FakeOradb, raising=False)

    class FakeCursor:
        def execute(self, sql):
            raise FakeOradb.DatabaseError(FakeOradb._fake_error_obj)

        def fetchall(self):
            return []

    m = _make_mod(_acfs_params())()
    with pytest.raises(FailJson):
        mod.execute_sql_get(m, [], FakeCursor(), "select 1 from dual")


def test_execute_sql_database_error(monkeypatch):
    """execute_sql: cursor raises DatabaseError → fail_json (lines 230-234)."""
    mod = _load()
    FakeOradb = _make_fake_oracledb()
    monkeypatch.setattr(mod, "oracledb", FakeOradb, raising=False)

    class FakeCursor:
        def execute(self, sql):
            raise FakeOradb.DatabaseError(FakeOradb._fake_error_obj)

    m = _make_mod(_acfs_params())()
    with pytest.raises(FailJson):
        mod.execute_sql(m, [], FakeCursor(), "begin null; end;")


# ---------------------------------------------------------------------------
# main() early exit: oracledb_exists=False (lines 285-287)
# ---------------------------------------------------------------------------

def test_main_no_oracledb_fails(monkeypatch):
    """main(): oracledb_exists=False → fail_json with install hint."""
    mod = _load()
    monkeypatch.setattr(mod, "oracledb_exists", False, raising=False)

    class Mod(BaseFakeModule):
        params = _acfs_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "oracledb" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# main() present/absent states with mocked helpers (lines 289-315)
# ---------------------------------------------------------------------------

def test_main_present_with_mocked_helpers(monkeypatch):
    """main(): state=present, oracledb ok, oracle_connect works → ensure_filesystem called."""
    mod = _load()
    monkeypatch.setattr(mod, "oracledb_exists", True, raising=False)

    class FakeConn:
        def cursor(self):
            return None

    def _fake_connect(module):
        return FakeConn()

    def _fake_check_vol(cursor, module, msg, name, diskgroup):
        return True

    def _fake_add_fs(cursor, module, msg, oracle_home, volume_name, diskgroup,
                     mountpoint, mountowner, mountgroup, mountperm, mountusers):
        return True

    ensure_called = []

    def _fake_ensure_fs(cursor, module, msg, oracle_home, volume_name, diskgroup,
                        mountpoint, mountowner, mountgroup, mountperm, mountusers):
        ensure_called.append(True)
        module.exit_json(msg="filesystem ensured", changed=True)

    monkeypatch.setattr(mod, "oracle_connect", _fake_connect, raising=False)
    monkeypatch.setattr(mod, "check_volume_exists", _fake_check_vol, raising=False)
    monkeypatch.setattr(mod, "add_filesystem", _fake_add_fs, raising=False)
    monkeypatch.setattr(mod, "ensure_filesystem", _fake_ensure_fs, raising=False)

    class Mod(BaseFakeModule):
        params = _acfs_params(state="present")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert ensure_called


def test_main_present_volume_not_found(monkeypatch):
    """main(): state=present, volume not found → nothing done (lines 292-302 skipped)."""
    mod = _load()
    monkeypatch.setattr(mod, "oracledb_exists", True, raising=False)

    class FakeConn:
        def cursor(self):
            return None

    def _fake_connect(module):
        return FakeConn()

    def _fake_check_vol(cursor, module, msg, name, diskgroup):
        return False  # volume not found, nothing to do

    monkeypatch.setattr(mod, "oracle_connect", _fake_connect, raising=False)
    monkeypatch.setattr(mod, "check_volume_exists", _fake_check_vol, raising=False)

    # After the if block, falls through to fail_json("Unhandled exit")
    class Mod(BaseFakeModule):
        params = _acfs_params(state="present")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "Unhandled exit" in exc.value.args[0]["msg"]
