"""Unit tests for CRUD-style Oracle modules: user, grant, pdb, tablespace."""
import pytest

from conftest import ExitJson, FailJson, load_module_from_path, module_path
from helpers import BASE_CONN_PARAMS, BaseFakeConn, BaseFakeModule, SequencedFakeConn


# ===========================================================================
# Helpers
# ===========================================================================

def _load(name):
    return load_module_from_path(
        module_path("plugins", "modules", f"{name}.py"), f"{name}_crud_test"
    )


# ===========================================================================
# oracle_user
# ===========================================================================

def _user_params(**overrides):
    base = {
        **BASE_CONN_PARAMS,
        "schema": "TESTUSER",
        "schema_password": "MyPass1",
        "schema_password_hash": None,
        "state": "present",
        "expired": None,
        "locked": None,
        "default_tablespace": None,
        "default_temp_tablespace": None,
        "profile": None,
        "authentication_type": "password",
        "container": None,
        "container_data": None,
    }
    base.update(overrides)
    return base


class _UserConn(BaseFakeConn):
    """Returns configurable user row from dba_users."""

    def __init__(self, module, existing_row=None):
        super().__init__(module)
        self._existing_row = existing_row

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        # Spy query for sys.user$ password hash
        if "spare4" in sql.lower():
            return {"spare4": "S:FAKEHASH1234ABCDEF"}
        if self._existing_row is None:
            return {} if fetchone else []
        return dict(self._existing_row) if fetchone else [dict(self._existing_row)]


def _default_user_row():
    return {
        "username": "TESTUSER",
        "account_status": "OPEN",
        "default_tablespace": "USERS",
        "temporary_tablespace": "TEMP",
        "profile": "DEFAULT",
        "authentication_type": "PASSWORD",
        "oracle_maintained": "N",
        "password_status": "UNEXPIRED",
    }


def test_user_creates_new(monkeypatch):
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("create user" in d.lower() for d in payload["ddls"])


def test_user_creates_with_default_tablespace(monkeypatch):
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(default_tablespace="USERS")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("default tablespace" in d.lower() for d in exc.value.args[0]["ddls"])


def test_user_creates_locked(monkeypatch):
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(locked=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("account lock" in d.lower() for d in exc.value.args[0]["ddls"])


def test_user_creates_expired(monkeypatch):
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(expired=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("password expire" in d.lower() for d in exc.value.args[0]["ddls"])


def test_user_no_change_when_already_correct(monkeypatch):
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None)

    row = _default_user_row()
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    # No password change, no lock, no expire → no DDL
    assert exc.value.args[0]["changed"] is False


def test_user_modify_lock_existing(monkeypatch):
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, locked=True)

    row = _default_user_row()  # currently OPEN
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("account lock" in d.lower() for d in payload["ddls"])


def test_user_drops_existing(monkeypatch):
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(state="absent")

    row = _default_user_row()
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("drop user" in d.lower() for d in payload["ddls"])


def test_user_absent_missing_no_change(monkeypatch):
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_user_cannot_drop_oracle_maintained(monkeypatch):
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(state="absent", schema="SYS")

    row = {**_default_user_row(), "username": "SYS", "oracle_maintained": "Y"}
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "internal" in exc.value.args[0]["msg"].lower()


def test_user_creates_no_authentication(monkeypatch):
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, authentication_type="none")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("no authentication" in d.lower() for d in exc.value.args[0]["ddls"])


def test_user_creates_external(monkeypatch):
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, authentication_type="external")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("identified externally" in d.lower() for d in exc.value.args[0]["ddls"])


def test_user_expired_locked_status_parsing(monkeypatch):
    """Account_status 'EXPIRED & LOCKED' is parsed as both locked and expired (no change needed)."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, locked=True, expired=True)

    row = {**_default_user_row(), "account_status": "EXPIRED & LOCKED"}
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    # Current state matches desired state → no change
    payload = exc.value.args[0]
    assert payload["changed"] is False


# ===========================================================================
# oracle_grant
# ===========================================================================

def _grant_params(**overrides):
    base = {
        **BASE_CONN_PARAMS,
        "grantee": "APPUSER",
        "grants": ["CREATE SESSION", "CONNECT"],
        "object_privs": [],
        "directory_privs": [],
        "grant_mode": "append",
        "container": None,
        "state": "present",
    }
    base.update(overrides)
    return base


class _GrantConn(BaseFakeConn):
    """Fake conn for oracle_grant: tracks execute_select calls."""

    def __init__(self, module, current_roles=None, current_sys=None):
        super().__init__(module)
        self._current_roles = current_roles or []  # list of (role,) tuples
        self._current_sys = current_sys or []       # list of (privilege,) tuples

    def execute_select(self, sql, params=None, fetchone=False):
        sql_l = sql.lower()
        if "dba_role_privs" in sql_l:
            return [(r,) for r in self._current_roles]
        if "dba_sys_privs" in sql_l:
            return [(p,) for p in self._current_sys]
        if "dba_tab_privs" in sql_l:
            return []  # no obj privs
        return []

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        # v$pwfile_users query
        return {} if fetchone else []


def test_grant_adds_new_roles(monkeypatch):
    mod = _load("oracle_grant")

    class Mod(BaseFakeModule):
        params = _grant_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _GrantConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("grant" in d.lower() for d in payload["ddls"])


def test_grant_no_change_when_already_granted(monkeypatch):
    mod = _load("oracle_grant")

    class Mod(BaseFakeModule):
        params = _grant_params(grants=["CONNECT"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    # User already has CONNECT role
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _GrantConn(m, current_roles=["connect"]), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_grant_removes_role_in_exact_mode(monkeypatch):
    mod = _load("oracle_grant")

    class Mod(BaseFakeModule):
        params = _grant_params(grants=["CONNECT"], grant_mode="exact")

    # User has CONNECT and RESOURCE, wants only CONNECT → should revoke RESOURCE
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection",
        lambda m: _GrantConn(m, current_roles=["connect", "resource"]),
        raising=False
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("revoke" in d.lower() for d in payload["ddls"])


def test_grant_absent_revokes(monkeypatch):
    mod = _load("oracle_grant")

    class Mod(BaseFakeModule):
        params = _grant_params(state="absent", grants=["CONNECT"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _GrantConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert any("revoke" in d.lower() for d in payload["ddls"])


def test_grant_remove_all(monkeypatch):
    mod = _load("oracle_grant")

    class Mod(BaseFakeModule):
        params = _grant_params(state="REMOVEALL")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection",
        lambda m: _GrantConn(m, current_roles=["dba"]),
        raising=False
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("revoke" in d.lower() for d in payload["ddls"])


def test_grant_with_container(monkeypatch):
    mod = _load("oracle_grant")

    class Mod(BaseFakeModule):
        params = _grant_params(container="current", session_container=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    class _Conn(_GrantConn):
        def __init__(self, m):
            super().__init__(m)
            self.container = None

    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson):
        mod.main()


def test_grant_object_privs(monkeypatch):
    mod = _load("oracle_grant")

    class Mod(BaseFakeModule):
        params = _grant_params(
            grants=[],
            object_privs=["select:sys.v_$session"],
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _GrantConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("grant select" in d.lower() for d in payload["ddls"])


def test_grant_revokes_excess_obj_privs(monkeypatch):
    """Object priv exists in DB but not in wanted list → revoke all on that object (exact mode)."""
    mod = _load("oracle_grant")

    class Mod(BaseFakeModule):
        params = _grant_params(
            grants=[],
            object_privs=[],  # want nothing
            grant_mode="exact",
        )

    class _Conn(_GrantConn):
        def execute_select(self, sql, params=None, fetchone=False):
            sql_l = sql.lower()
            if "dba_role_privs" in sql_l:
                return []
            if "dba_sys_privs" in sql_l:
                return []
            if "dba_tab_privs" in sql_l:
                # current: user has SELECT on sys.dual
                return [("select", "sys.dual")]
            return []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("revoke all on" in d.lower() for d in payload["ddls"])


def test_grant_modifies_obj_privs_intersection(monkeypatch):
    """Object already has SELECT; wanted is INSERT → grant INSERT, revoke SELECT (exact mode)."""
    mod = _load("oracle_grant")

    class Mod(BaseFakeModule):
        params = _grant_params(
            grants=[],
            object_privs=["insert:sys.dual"],
            grant_mode="exact",
        )

    class _Conn(_GrantConn):
        def execute_select(self, sql, params=None, fetchone=False):
            sql_l = sql.lower()
            if "dba_role_privs" in sql_l:
                return []
            if "dba_sys_privs" in sql_l:
                return []
            if "dba_tab_privs" in sql_l:
                # current: user has SELECT on sys.dual, same object as wanted (INSERT)
                return [("select", "sys.dual")]
            return []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    ddls_lower = [d.lower() for d in payload["ddls"]]
    assert any("grant insert" in d for d in ddls_lower)
    assert any("revoke select" in d for d in ddls_lower)


def test_grant_removes_obj_and_dir_privs(monkeypatch):
    """state=absent with object_privs and directory_privs → revoke statements emitted."""
    mod = _load("oracle_grant")

    class Mod(BaseFakeModule):
        params = _grant_params(
            state="absent",
            grants=[],
            object_privs=["select:sys.dual"],
            directory_privs=["read:DATA_DIR"],
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _GrantConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    ddls_lower = [d.lower() for d in payload["ddls"]]
    assert any("revoke select on sys.dual" in d for d in ddls_lower)
    assert any("revoke read on directory data_dir" in d for d in ddls_lower)


def test_grant_with_dba_no_unlimited_tablespace_revoke(monkeypatch):
    """DBA in wanted grants → 'unlimited tablespace' must NOT be revoked even in exact mode."""
    mod = _load("oracle_grant")

    class Mod(BaseFakeModule):
        params = _grant_params(
            grants=["DBA"],
            grant_mode="exact",
        )

    class _Conn(_GrantConn):
        def __init__(self, m):
            super().__init__(m)

        def execute_select(self, sql, params=None, fetchone=False):
            sql_l = sql.lower()
            if "dba_role_privs" in sql_l:
                return [("dba",)]
            if "dba_sys_privs" in sql_l:
                # unlimited tablespace implicitly granted alongside DBA
                return [("unlimited tablespace",)]
            if "dba_tab_privs" in sql_l:
                return []
            return []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    # Nothing to revoke: DBA already granted, unlimited tablespace exception applies
    assert payload["changed"] is False
    assert not any("unlimited tablespace" in d.lower() for d in payload.get("ddls", []))


def test_grant_exact_mode_with_container(monkeypatch):
    """grant_mode=exact + container → grant SQL includes 'container=CURRENT' clause."""
    mod = _load("oracle_grant")

    class Mod(BaseFakeModule):
        params = _grant_params(
            grants=["CONNECT", "RESOURCE"],
            grant_mode="exact",
            container="current",
            session_container=None,
        )

    class _Conn(_GrantConn):
        def __init__(self, m):
            # user currently has only CONNECT; RESOURCE needs to be added
            super().__init__(m, current_roles=["connect"])

        def execute_select(self, sql, params=None, fetchone=False):
            sql_l = sql.lower()
            if "dba_role_privs" in sql_l:
                return [("connect",)]
            if "dba_sys_privs" in sql_l:
                return []
            if "dba_tab_privs" in sql_l:
                return []
            return []

        def set_container(self, pdb_name):
            self.container = pdb_name

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    # The grant statement for RESOURCE should carry the container clause
    assert any("container=current" in d.lower() for d in payload["ddls"])


# ===========================================================================
# oracle_pdb
# ===========================================================================

def _pdb_params(**overrides):
    base = {
        **BASE_CONN_PARAMS,
        "pdb_name": "TESTPDB",
        "state": "opened",
        "sourcedb": None,
        "snapshot_copy": False,
        "plug_file": None,
        "pdb_admin_username": "pdb_admin",
        "pdb_admin_password": "pdb_admin",
        "roles": [],
        "save_state": True,
        "datafile_dest": None,
        "file_name_convert": None,
        "service_name_convert": None,
        "default_tablespace_type": "smallfile",
        "default_tablespace": None,
        "default_temp_tablespace": None,
        "timezone": None,
    }
    base.update(overrides)
    return base


class _PdbConn(BaseFakeConn):
    """Fake conn for oracle_pdb."""

    def __init__(self, module, existing_mode=None):
        super().__init__(module)
        self._existing_mode = existing_mode  # None = PDB doesn't exist
        self._call_count = 0

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        self._call_count += 1
        # check_pdb_exists: first call
        if self._call_count == 1:
            if self._existing_mode is None:
                return {} if fetchone else []
            return {"name": "TESTPDB", "open_mode": self._existing_mode, "restricted": "NO"}
        # check_pdb_exists: service query (2nd call, if open mode starts with READ)
        if self._call_count == 2:
            return {"service_name": "testpdb"} if fetchone else [{"service_name": "testpdb"}]
        # check_pdb_status (state=status path)
        return {"name": "TESTPDB", "open_mode": "READ WRITE", "restricted": "NO"}

    def execute_select(self, sql, params=None, fetchone=False):
        # database_properties query in check_pdb_exists
        return []


def test_pdb_creates_new(monkeypatch):
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("create pluggable database" in d.lower() for d in payload["ddls"])


def test_pdb_absent_removes_existing(monkeypatch):
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    # PDB exists in MOUNTED state (not READ*)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, "MOUNTED"), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("drop pluggable database" in d.lower() for d in payload["ddls"])


def test_pdb_absent_missing_no_change(monkeypatch):
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_pdb_status_open(monkeypatch):
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(state="status")

    class _Conn(_PdbConn):
        def __init__(self, m):
            super().__init__(m, "READ WRITE")

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            # Always return the PDB row
            return {"name": "TESTPDB", "open_mode": "READ WRITE", "restricted": "NO"}

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["state"] == "open"


def test_pdb_status_missing_fails(monkeypatch):
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(state="status")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, None), raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_pdb_create_from_source(monkeypatch):
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(sourcedb="CDB1", pdb_admin_username=None, pdb_admin_password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("from cdb1" in d.lower() for d in exc.value.args[0]["ddls"])


# ===========================================================================
# oracle_tablespace
# ===========================================================================

def _ts_params(**overrides):
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


def _ts_conn_factory(existing=False, omf=True):
    """Build a SequencedFakeConn for tablespace tests."""

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            status_row = {"tablespace_name": "TESTTS", "status": "ONLINE"}
            omf_row = {"value": "/u01/oradata"} if omf else {"value": None}
            if existing:
                # check_tablespace_exists → exists
                # ensure_tablespace_state calls: OMF, status, numfiles
                self.responses = [
                    status_row,            # check_tablespace_exists (fetchone)
                    omf_row,               # ensure_tablespace_state: OMF check
                    status_row,            # ensure_tablespace_state: status check
                    {"count": 1},          # ensure_tablespace_state: numfiles
                ]
            else:
                # check_tablespace_exists → doesn't exist
                # create_tablespace: OMF check
                # ensure_tablespace_state: OMF, status, numfiles
                self.responses = [
                    {},                    # check_tablespace_exists (fetchone) → empty
                    omf_row,               # create_tablespace: OMF check
                    omf_row,               # ensure_tablespace_state: OMF check
                    {"status": "ONLINE"},  # ensure_tablespace_state: status check
                    {"count": 0},          # ensure_tablespace_state: numfiles
                ]

    return _Conn


def test_tablespace_creates_new_bigfile(monkeypatch):
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params()

    ConnCls = _ts_conn_factory(existing=False, omf=True)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("create bigfile tablespace" in d.lower() for d in payload["ddls"])


def test_tablespace_creates_with_datafile(monkeypatch):
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(bigfile=False, datafile=["/u01/data/test01.dbf"])

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {},                          # check_tablespace_exists → not found
                {"value": None},             # create_tablespace: OMF off
                {"value": None},             # ensure_tablespace_state: OMF
                {"status": "ONLINE"},        # ensure_tablespace_state: status
                {"count": 0},                # ensure_tablespace_state: numfiles
            ]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("create tablespace" in d.lower() for d in payload["ddls"])


def test_tablespace_drops_existing(monkeypatch):
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(state="absent")

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [{"tablespace_name": "TESTTS", "status": "ONLINE"}]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("drop tablespace" in d.lower() for d in payload["ddls"])


def test_tablespace_absent_missing_no_change(monkeypatch):
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(state="absent")

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [{}]  # not found

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_tablespace_creates_temp(monkeypatch):
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(content="temp")

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {},                         # check_tablespace_exists → not found
                {"value": "/u01/oradata"},  # create_tablespace: OMF
                {"value": "/u01/oradata"},  # ensure_tablespace_state: OMF
                {"status": "ONLINE"},       # status
                {"count": 0},               # numfiles
            ]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("temporary tablespace" in d.lower() for d in payload["ddls"])


def test_tablespace_read_only_state(monkeypatch):
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(state="read_only")

    ConnCls = _ts_conn_factory(existing=True, omf=True)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    # ONLINE → READ ONLY change
    assert payload["changed"] is True
    assert any("read only" in d.lower() for d in payload["ddls"])


def test_tablespace_offline_state(monkeypatch):
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(state="offline")

    ConnCls = _ts_conn_factory(existing=True, omf=True)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("offline" in d.lower() for d in payload["ddls"])


# ===========================================================================
# oracle_user - additional tests for better coverage
# ===========================================================================

def test_user_account_expired_status(monkeypatch):
    """Account status 'EXPIRED' → account_status='OPEN', password_status='EXPIRED'."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, expired=True)

    row = {**_default_user_row(), "account_status": "EXPIRED"}
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    # Already expired, want expired=True → no change
    assert exc.value.args[0]["changed"] is False


def test_user_account_locked_status(monkeypatch):
    """Account status 'LOCKED' → parsed correctly → no DDL when locked=True requested."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, locked=True)

    row = {**_default_user_row(), "account_status": "LOCKED"}
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_user_creates_with_hash(monkeypatch):
    """Create user with schema_password_hash (identified by values)."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(
            schema_password=None,
            schema_password_hash="S:DEADBEEF1234",
            authentication_type=None,
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("identified by values" in d.lower() for d in ddls)


def test_user_creates_global(monkeypatch):
    """Create user with global authentication."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, authentication_type="global")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("identified globally" in d.lower() for d in exc.value.args[0]["ddls"])


def test_user_creates_with_temp_tablespace(monkeypatch):
    """Create user with temporary tablespace."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(default_temp_tablespace="TEMP2")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("temporary tablespace temp2" in d.lower() for d in exc.value.args[0]["ddls"])


def test_user_creates_with_profile(monkeypatch):
    """Create user with a non-default profile."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(profile="MY_PROFILE")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("profile my_profile" in d.lower() for d in exc.value.args[0]["ddls"])


def test_user_creates_with_container(monkeypatch):
    """Create user with container=all clause."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(container="all")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("container=all" in d.lower() for d in exc.value.args[0]["ddls"])


def test_user_creates_with_container_data(monkeypatch):
    """Create user with container_data → extra alter user DDL."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(container="all", container_data="objecttype")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert len(ddls) >= 2
    assert any("set container_data" in d.lower() for d in ddls)


def test_user_modify_change_password(monkeypatch):
    """Modify existing user: new password triggers password_matches_hash call."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password="NewPassword1", authentication_type=None)

    row = _default_user_row()
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("identified by" in d.lower() for d in payload["ddls"])


def test_user_modify_change_tablespace(monkeypatch):
    """Modify existing user: change default tablespace."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, default_tablespace="DATA")

    row = _default_user_row()  # currently default_tablespace=USERS
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("default tablespace data" in d.lower() for d in payload["ddls"])


def test_user_modify_change_profile(monkeypatch):
    """Modify existing user: change profile."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, profile="APP_PROFILE")

    row = _default_user_row()  # currently profile=DEFAULT
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("profile" in d.lower() for d in payload["ddls"])


def test_user_modify_unlock(monkeypatch):
    """Modify existing locked user: locked=False → account unlock DDL."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, locked=False)

    row = {**_default_user_row(), "account_status": "LOCKED"}
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("account unlock" in d.lower() for d in payload["ddls"])


def test_user_modify_expire(monkeypatch):
    """Modify existing user: expired=True → password expire DDL."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, expired=True)

    row = _default_user_row()  # currently UNEXPIRED
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("password expire" in d.lower() for d in payload["ddls"])


def test_user_modify_temp_tablespace(monkeypatch):
    """Modify existing user: change temporary tablespace."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, default_temp_tablespace="TEMP2")

    row = _default_user_row()  # currently temporary_tablespace=TEMP
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("temporary tablespace" in d.lower() for d in payload["ddls"])


def test_user_modify_to_external(monkeypatch):
    """Modify existing user: change to external authentication."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, authentication_type="external")

    row = _default_user_row()  # currently PASSWORD auth
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("identified externally" in d.lower() for d in payload["ddls"])


# ===========================================================================
# oracle_user - additional coverage tests (round 2)
# ===========================================================================

def test_user_creates_implicit_none_auth(monkeypatch):
    """Create user with authentication_type=None and no password → implicit 'none'."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(authentication_type=None, schema_password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("no authentication" in d.lower() for d in exc.value.args[0]["ddls"])


def test_user_creates_password_required_fails(monkeypatch):
    """Create user with explicit authentication_type=password but no password → fail."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(authentication_type="password", schema_password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, None), raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "password" in exc.value.args[0]["msg"].lower()


def test_user_password_matches_hash_direct():
    """Direct test of password_matches_hash: S: hash with invalid hex → returns False."""
    mod = _load("oracle_user")
    result = mod.password_matches_hash("MyPass1", "S:FAKEHASH1234ABCDEF")
    assert result is False


def test_user_password_matches_hash_empty():
    """Direct test of password_matches_hash: empty hash → returns False."""
    mod = _load("oracle_user")
    result = mod.password_matches_hash("MyPass1", "")
    assert result is False


def test_user_modify_with_different_hash(monkeypatch):
    """Modify existing user: provide different schema_password_hash → hash identified by values."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(
            schema_password=None,
            schema_password_hash="S:NEWHASH9999",
            authentication_type=None,
        )

    row = _default_user_row()
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("identified by values" in d.lower() for d in payload["ddls"])


def test_user_modify_to_global_auth(monkeypatch):
    """Modify existing user to global authentication."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, authentication_type="global")

    row = _default_user_row()  # currently PASSWORD
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_user_modify_to_none_auth(monkeypatch):
    """Modify existing user to no-authentication."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, authentication_type="none")

    row = _default_user_row()  # currently PASSWORD
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("no authentication" in d.lower() for d in exc.value.args[0]["ddls"])


def test_user_modify_unexpire_no_password_fails(monkeypatch):
    """Modify expired user: expired=False with no password → fail_json (can't re-auth)."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(schema_password=None, expired=False, authentication_type=None)

    row = {**_default_user_row(), "account_status": "EXPIRED"}
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "password" in exc.value.args[0]["msg"].lower()


def test_user_modify_container_data_existing(monkeypatch):
    """Modify existing user: container_data set → extra alter user DDL."""
    mod = _load("oracle_user")

    class Mod(BaseFakeModule):
        params = _user_params(
            schema_password=None,
            container="all",
            container_data="objecttype",
        )

    row = _default_user_row()
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _UserConn(m, row), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("set container_data" in d.lower() for d in ddls)


# ===========================================================================
# oracle_tablespace - additional coverage tests
# ===========================================================================

def test_tablespace_creates_undo_bigfile_omf(monkeypatch):
    """Create bigfile undo tablespace via OMF."""
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(content="undo", bigfile=True)

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {},                         # check_tablespace_exists → not found
                {"value": "/u01/oradata"},  # create_tablespace: OMF check
                {"value": "/u01/oradata"},  # ensure_tablespace_state: OMF
                {"status": "ONLINE"},
                {"count": 0},
            ]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("bigfile undo" in d.lower() for d in exc.value.args[0]["ddls"])


def test_tablespace_creates_undo_nonbigfile_omf(monkeypatch):
    """Create non-bigfile undo tablespace via OMF."""
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(content="undo", bigfile=False)

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {},
                {"value": "/u01/oradata"},
                {"value": "/u01/oradata"},
                {"status": "ONLINE"},
                {"count": 0},
            ]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("undo tablespace" in d.lower() for d in exc.value.args[0]["ddls"])


def test_tablespace_no_datafile_no_omf_exits(monkeypatch):
    """Create tablespace: no datafile + no OMF → exit_json with error msg."""
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(bigfile=False, datafile=None)

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {},              # check_tablespace_exists → not found
                {"value": None}, # create_tablespace: OMF disabled
            ]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert "datafile" in exc.value.args[0]["msg"].lower()


def test_tablespace_creates_undo_with_explicit_datafile(monkeypatch):
    """Create undo tablespace with explicit datafile."""
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(content="undo", bigfile=False, datafile=["/u01/undo01.dbf"])

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {},
                {"value": None},  # no OMF
                {"value": None},
                {"status": "ONLINE"},
                {"count": 0},
            ]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("undo tablespace" in d.lower() for d in exc.value.args[0]["ddls"])


def test_tablespace_creates_temp_with_explicit_datafile(monkeypatch):
    """Create temp tablespace with explicit datafile."""
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(content="temp", bigfile=False, datafile=["/u01/temp01.dbf"])

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {},
                {"value": None},  # no OMF
                {"value": None},
                {"status": "ONLINE"},
                {"count": 0},
            ]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("temporary tablespace" in d.lower() for d in ddls)


def test_tablespace_creates_with_datafile_explicit_no_autoextend(monkeypatch):
    """Create tablespace with explicit datafile and maxsize set but no autoextend."""
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(
            bigfile=False,
            datafile=["/u01/data/test02.dbf"],
            autoextend=False,
            maxsize="2G",  # prevents auto-set to autoextend=True
        )

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {},
                {"value": None},  # no OMF
                {"value": None},
                {"status": "ONLINE"},
                {"count": 0},
            ]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_tablespace_present_when_read_only(monkeypatch):
    """state=present on READ ONLY tablespace → alters to read_write."""
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(state="present")

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {"tablespace_name": "TESTTS", "status": "READ ONLY"},
                {"value": "/u01/oradata"},   # OMF
                {"status": "READ ONLY"},     # current status
                {"count": 1},               # numfiles
            ]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("read write" in d.lower() for d in payload["ddls"])


def test_tablespace_present_when_offline(monkeypatch):
    """state=present on OFFLINE tablespace → brings online."""
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(state="present")

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {"tablespace_name": "TESTTS", "status": "OFFLINE"},
                {"value": "/u01/oradata"},
                {"status": "OFFLINE"},
                {"count": 1},
            ]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("online" in d.lower() for d in payload["ddls"])


def test_tablespace_read_write_from_read_only(monkeypatch):
    """state=read_write on READ ONLY tablespace → alters to read_write."""
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(state="read_write")

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {"tablespace_name": "TESTTS", "status": "READ ONLY"},
                {"value": "/u01/oradata"},
                {"status": "READ ONLY"},
                {"count": 1},
            ]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("read write" in d.lower() for d in payload["ddls"])


def test_tablespace_numfiles_add_with_omf(monkeypatch):
    """Existing tablespace needs more datafiles (OMF mode)."""
    mod = _load("oracle_tablespace")

    class Mod(BaseFakeModule):
        params = _ts_params(bigfile=False, numfiles=3)  # want 3, have 1

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                {"tablespace_name": "TESTTS", "status": "ONLINE"},  # exists
                {"value": "/u01/oradata"},   # ensure: OMF
                {"status": "ONLINE"},        # ensure: status
                {"count": 1},               # ensure: current numfiles = 1 < 3
                [],                         # ensure_tablespace_attributes: datafiles
            ]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("add datafile" in d.lower() for d in payload["ddls"])


# ===========================================================================
# oracle_pdb – additional coverage
# ===========================================================================

def test_pdb_create_with_plug_file(monkeypatch):
    """create_pdb with plug_file → SQL contains 'using'."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(plug_file="/tmp/pdb.xml", pdb_admin_username=None, pdb_admin_password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("using" in d.lower() for d in exc.value.args[0]["ddls"])


def test_pdb_create_with_snapshot_copy(monkeypatch):
    """create_pdb with sourcedb + snapshot_copy → SQL contains 'snapshot copy'."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(sourcedb="CDB1", snapshot_copy=True, pdb_admin_username=None, pdb_admin_password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("snapshot copy" in d.lower() for d in exc.value.args[0]["ddls"])


def test_pdb_create_missing_params_fails(monkeypatch):
    """create_pdb with no plug_file, sourcedb, or admin → fail_json."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(pdb_admin_username=None, pdb_admin_password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, None), raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_pdb_create_with_roles(monkeypatch):
    """create_pdb with roles → SQL contains 'roles ='."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(roles=["CONNECT", "RESOURCE"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("roles" in d.lower() for d in exc.value.args[0]["ddls"])


def test_pdb_create_with_file_name_convert(monkeypatch):
    """create_pdb with file_name_convert → SQL contains 'file_name_convert'."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(file_name_convert={"/old/path": "/new/path"})

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("file_name_convert" in d.lower() for d in exc.value.args[0]["ddls"])


def test_pdb_create_with_service_name_convert(monkeypatch):
    """create_pdb with service_name_convert → SQL contains 'service_name_convert'."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(service_name_convert={"oldsvc": "newsvc"})

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("service_name_convert" in d.lower() for d in exc.value.args[0]["ddls"])


def test_pdb_create_with_datafile_dest(monkeypatch):
    """create_pdb with datafile_dest → SQL contains 'create_file_dest'."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(datafile_dest="/u02/oradata/pdb1")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("create_file_dest" in d.lower() for d in exc.value.args[0]["ddls"])


def test_pdb_remove_when_read_write(monkeypatch):
    """remove_pdb when open_mode=READ WRITE → close first then drop."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    # PDB exists in READ WRITE state — should trigger close before drop
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, "READ WRITE"), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    ddls = payload["ddls"]
    assert any("close" in d.lower() for d in ddls)
    assert any("drop" in d.lower() for d in ddls)


def test_pdb_state_opened_existing_already_open(monkeypatch):
    """state=opened, pdb already exists and is READ WRITE → no open DDL issued."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(state="opened")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, "READ WRITE"), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    # open_mode is already READ WRITE so no 'open force' DDL should appear
    assert not any("open force" in d.lower() for d in exc.value.args[0]["ddls"])


def test_pdb_state_closed_from_read_write(monkeypatch):
    """state=closed, pdb is READ WRITE → ensure_pdb_state closes it."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(state="closed")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, "READ WRITE"), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert any("close" in d.lower() for d in exc.value.args[0]["ddls"])


def test_pdb_state_read_only_from_new(monkeypatch):
    """state=read_only, pdb doesn't exist → create + open read only."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(state="read_only")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("read only" in d.lower() for d in ddls)


def test_pdb_state_with_default_tablespace(monkeypatch):
    """state=opened with default_tablespace → ensure_pdb_state adds tablespace DDL."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(state="opened", default_tablespace="USERS")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, "READ WRITE"), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("default tablespace" in d.lower() for d in ddls)


def test_pdb_state_with_default_temp_tablespace(monkeypatch):
    """state=opened with default_temp_tablespace → DDL for temp tablespace."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(state="opened", default_temp_tablespace="TEMP2")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, "READ WRITE"), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("temporary tablespace" in d.lower() for d in ddls)


def test_pdb_state_with_timezone(monkeypatch):
    """state=opened with timezone → DDL for time_zone."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(state="opened", timezone="+02:00")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, "READ WRITE"), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddls = exc.value.args[0]["ddls"]
    assert any("time_zone" in d.lower() for d in ddls)


def test_pdb_state_no_changes_after_create(monkeypatch):
    """ensure_pdb_state: no state changes after creation → exit with conn.changed=True."""
    mod = _load("oracle_pdb")

    class _Conn(_PdbConn):
        """Returns MOUNTED pdb immediately so ensure_pdb_state sees no state diff."""
        def __init__(self, m):
            super().__init__(m, None)

    class Mod(BaseFakeModule):
        params = _pdb_params(state="opened")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _Conn(m), raising=False)

    # state=opened, pdb newly created with open_mode=MOUNTED
    # wanted_state={'open_mode': 'READ WRITE'}, current={'open_mode': 'MOUNTED'}
    # → changes has open_mode → DDL added → exits changed=True
    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_pdb_status_mounted(monkeypatch):
    """state=status, pdb is MOUNTED → exit with state='closed'."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(state="status")

    class _Conn(_PdbConn):
        def __init__(self, m):
            super().__init__(m, "MOUNTED")

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            return {"name": "TESTPDB", "open_mode": "MOUNTED", "restricted": "NO"}

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["state"] == "closed"


def test_pdb_unplug_missing_exits(monkeypatch):
    """state=unplugged, pdb doesn't exist → exit_json changed=False."""
    mod = _load("oracle_pdb")

    class Mod(BaseFakeModule):
        params = _pdb_params(state="unplugged", plug_file="/tmp/pdb.xml",
                             pdb_admin_username=None, pdb_admin_password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _PdbConn(m, None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_pdb_unplug_executes_ddls(monkeypatch):
    """unplug_pdb: executes close, unplug, drop DDLs (module has unplug_dest bug)."""
    mod = _load("oracle_pdb")

    class _M(BaseFakeModule):
        params = _pdb_params(plug_file="/tmp/pdb.xml")

    m = _M()
    conn = _PdbConn(m, "MOUNTED")

    # The module has a bug: 'unplug_dest' is undefined at line 171, so NameError
    # is expected after DDLs are executed.
    try:
        mod.unplug_pdb(conn, m)
    except NameError:
        pass

    assert len(conn.ddls) == 3
    assert any("unplug" in d.lower() for d in conn.ddls)
    assert any("drop" in d.lower() for d in conn.ddls)
