"""Unit tests for simple Oracle modules: ping, directory, role, awr, parameter, profile."""
from datetime import timedelta

import pytest

from conftest import ExitJson, FailJson, load_module_from_path, module_path
from helpers import BASE_CONN_PARAMS, BaseFakeConn, BaseFakeModule, SequencedFakeConn, awr_result


# ===========================================================================
# oracle_ping
# ===========================================================================

def _load_ping():
    return load_module_from_path(module_path("plugins", "modules", "oracle_ping.py"), "oracle_ping_test")


class _PingFakeModule(BaseFakeModule):
    params = {**BASE_CONN_PARAMS}


class _PingFakeConn(BaseFakeConn):
    def __init__(self, module):
        super().__init__(module)
        self.data = [{"instance_name": "ORCL", "status": "OPEN", "host_name": "db1"}]

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        return self.data[0] if self.data else {}


def test_ping_successful_connection(monkeypatch):
    mod = _load_ping()
    monkeypatch.setattr(mod, "AnsibleModule", _PingFakeModule)
    monkeypatch.setattr(mod, "oracleConnection", _PingFakeConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is False
    assert "Connection successful" in payload["msg"]


def test_ping_with_pdb_container(monkeypatch):
    mod = _load_ping()

    class PdbFakeModule(BaseFakeModule):
        params = {**BASE_CONN_PARAMS, "session_container": "MYPDB"}

    monkeypatch.setattr(mod, "AnsibleModule", PdbFakeModule)
    monkeypatch.setattr(mod, "oracleConnection", _PingFakeConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert "Connection successful" in exc.value.args[0]["msg"]


# ===========================================================================
# oracle_directory
# ===========================================================================

def _load_directory():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_directory.py"), "oracle_directory_test"
    )


class _DirFakeModule(BaseFakeModule):
    params = {
        **BASE_CONN_PARAMS,
        "directory_name": "TEST_DIR",
        "directory_path": "/oracle/test",
        "state": "present",
    }


class _DirFakeConn(BaseFakeConn):
    """Returns configurable directory row."""

    def __init__(self, module, existing_path=None):
        super().__init__(module)
        self._existing_path = existing_path

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        if self._existing_path is None:
            return {} if fetchone else []
        return {"directory_name": "TEST_DIR", "directory_path": self._existing_path}


def test_directory_present_creates_new(monkeypatch):
    mod = _load_directory()
    monkeypatch.setattr(mod, "AnsibleModule", _DirFakeModule)

    class _Conn(_DirFakeConn):
        def __init__(self, m):
            super().__init__(m, existing_path=None)

    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("create directory" in d.lower() for d in payload["ddls"])


def test_directory_present_same_path_no_change(monkeypatch):
    mod = _load_directory()
    monkeypatch.setattr(mod, "AnsibleModule", _DirFakeModule)

    class _Conn(_DirFakeConn):
        def __init__(self, m):
            super().__init__(m, existing_path="/oracle/test")

    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_directory_present_different_path_updates(monkeypatch):
    mod = _load_directory()
    monkeypatch.setattr(mod, "AnsibleModule", _DirFakeModule)

    class _Conn(_DirFakeConn):
        def __init__(self, m):
            super().__init__(m, existing_path="/old/path")

    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("create or replace directory" in d.lower() for d in payload["ddls"])


def test_directory_absent_existing_drops(monkeypatch):
    mod = _load_directory()

    class AbsentModule(BaseFakeModule):
        params = {
            **BASE_CONN_PARAMS,
            "directory_name": "TEST_DIR",
            "directory_path": "/oracle/test",
            "state": "absent",
        }

    monkeypatch.setattr(mod, "AnsibleModule", AbsentModule)

    class _Conn(_DirFakeConn):
        def __init__(self, m):
            super().__init__(m, existing_path="/oracle/test")

    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("drop directory" in d.lower() for d in payload["ddls"])


def test_directory_absent_missing_no_change(monkeypatch):
    mod = _load_directory()

    class AbsentModule(BaseFakeModule):
        params = {
            **BASE_CONN_PARAMS,
            "directory_name": "MISSING_DIR",
            "directory_path": None,
            "state": "absent",
        }

    monkeypatch.setattr(mod, "AnsibleModule", AbsentModule)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _DirFakeConn(m, existing_path=None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


# ===========================================================================
# oracle_role
# ===========================================================================

def _load_role():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_role.py"), "oracle_role_test"
    )


class _RoleFakeConn(BaseFakeConn):
    def __init__(self, module, existing_auth=None):
        super().__init__(module)
        self._existing_auth = existing_auth

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        if self._existing_auth is None:
            return {} if fetchone else []
        return {"role": "MYROLE", "authentication_type": self._existing_auth}


def _role_params(state="present", auth="none", auth_conf=None):
    return {
        **BASE_CONN_PARAMS,
        "role": "MYROLE",
        "state": state,
        "auth": auth,
        "auth_conf": auth_conf,
    }


def test_role_present_creates_new(monkeypatch):
    mod = _load_role()

    class Mod(BaseFakeModule):
        params = _role_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _RoleFakeConn(m, existing_auth=None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("create role" in d.lower() for d in payload["ddls"])


def test_role_present_same_auth_no_change(monkeypatch):
    mod = _load_role()

    class Mod(BaseFakeModule):
        params = _role_params(auth="none")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _RoleFakeConn(m, existing_auth="NONE"), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_role_present_different_auth_modifies(monkeypatch):
    mod = _load_role()

    class Mod(BaseFakeModule):
        params = _role_params(auth="external")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _RoleFakeConn(m, existing_auth="NONE"), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("alter role" in d.lower() for d in payload["ddls"])


def test_role_absent_drops_existing(monkeypatch):
    mod = _load_role()

    class Mod(BaseFakeModule):
        params = _role_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _RoleFakeConn(m, existing_auth="NONE"), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("drop role" in d.lower() for d in payload["ddls"])


def test_role_absent_missing_no_change(monkeypatch):
    mod = _load_role()

    class Mod(BaseFakeModule):
        params = _role_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _RoleFakeConn(m, existing_auth=None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_role_create_with_password(monkeypatch):
    mod = _load_role()

    class Mod(BaseFakeModule):
        params = _role_params(auth="password", auth_conf="secret123")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _RoleFakeConn(m, existing_auth=None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("identified by" in d.lower() for d in payload["ddls"])


def test_role_create_global(monkeypatch):
    mod = _load_role()

    class Mod(BaseFakeModule):
        params = _role_params(auth="global")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _RoleFakeConn(m, existing_auth=None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_role_create_external(monkeypatch):
    mod = _load_role()

    class Mod(BaseFakeModule):
        params = _role_params(auth="external")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _RoleFakeConn(m, existing_auth=None), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


# ===========================================================================
# oracle_awr
# ===========================================================================

def _load_awr():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_awr.py"), "oracle_awr_test"
    )


class _AwrFakeConn(BaseFakeConn):
    """AWR fake conn: returns timedelta data for snap_interval/retention queries."""

    def __init__(self, module, interval_min=60, retention_days=8, second_call=None):
        super().__init__(module)
        self._interval_min = interval_min
        self._retention_days = retention_days
        self._second_call = second_call  # response after DDL
        self._call_count = 0

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        self._call_count += 1
        # query_existing tries adb sql first, then 19c if empty
        # We always return data from the first call, simulating a non-ADB 19c DB
        if self._call_count % 2 == 1:
            # 1st call (adb sql) - return empty to trigger 19c branch
            return {}
        # 2nd call (19c sql) - or post-DDL call
        if self._second_call and self._call_count > 2:
            return self._second_call
        return awr_result(self._interval_min, self._retention_days)


def _awr_params(interval=None, retention=None):
    return {
        **BASE_CONN_PARAMS,
        "snapshot_interval_min": interval,
        "snapshot_retention_days": retention,
    }


def test_awr_no_change_when_already_correct(monkeypatch):
    mod = _load_awr()

    class Mod(BaseFakeModule):
        params = _awr_params(interval=60, retention=8)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _AwrFakeConn(m, 60, 8), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is False
    assert payload["snap_interval"] == 60
    assert payload["retention"] == 8


def test_awr_updates_interval_when_different(monkeypatch):
    mod = _load_awr()

    class Mod(BaseFakeModule):
        params = _awr_params(interval=30, retention=8)

    updated = awr_result(30, 8)

    class _Conn(_AwrFakeConn):
        def __init__(self, m):
            super().__init__(m, 60, 8, second_call=updated)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _Conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True


def test_awr_invalid_interval_fails(monkeypatch):
    mod = _load_awr()

    class Mod(BaseFakeModule):
        params = _awr_params(interval=5)  # < 10, invalid

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _AwrFakeConn(m), raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "interval" in exc.value.args[0]["msg"].lower()


def test_awr_invalid_large_interval_fails(monkeypatch):
    mod = _load_awr()

    class Mod(BaseFakeModule):
        params = _awr_params(interval=2000)  # > 1000, invalid

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _AwrFakeConn(m), raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "interval" in exc.value.args[0]["msg"].lower()


def test_awr_none_params_no_change(monkeypatch):
    """When both interval and retention are None, nothing should change."""
    mod = _load_awr()

    class Mod(BaseFakeModule):
        params = _awr_params()  # both None

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _AwrFakeConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_awr_old_database_fails(monkeypatch):
    mod = _load_awr()

    class Mod(BaseFakeModule):
        params = _awr_params(interval=60)

    class _OldConn(_AwrFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.version = "10.1.0"  # 10gR1, lexicographically < "10.2"

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _OldConn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "10gR2" in exc.value.args[0]["msg"]


# ===========================================================================
# oracle_parameter
# ===========================================================================

def _load_parameter():
    import re as _re
    mod = load_module_from_path(
        module_path("plugins", "modules", "oracle_parameter.py"), "oracle_parameter_test"
    )
    # oracle_parameter.py uses `re` via `from ansible.module_utils.basic import *`
    # which is not available in the test stub - inject it explicitly.
    mod.re = _re
    return mod


def _param_conn_factory(current_value, display_value, spfile_value=None, is_underscore=False):
    """Return a FakeConn class configured with parameter data."""

    # Build p dict (from v$parameter or x$ksppi)
    if is_underscore:
        p_dict = {
            "name": "_test_param",
            "current_value": current_value,
            "default_value": None,
            "isdefault": "FALSE",
            "display_value": display_value,
        }
    else:
        p_dict = {
            "name": "open_cursors",
            "current_value": current_value,
            "ismodified": "FALSE",
            "isdefault": "FALSE",
            "default_value": None,
            "display_value": display_value,
        }
    s_dict = {"name": p_dict["name"], "spfile_value": spfile_value}

    class _Conn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [p_dict.copy(), s_dict.copy()]

    return _Conn


def _param_params(name="open_cursors", value="300", state="present", scope="both"):
    return {
        **BASE_CONN_PARAMS,
        "parameter_name": name,
        "value": value,
        "comment": None,
        "state": state,
        "scope": scope,
        "sid": "*",
    }


def test_parameter_sets_new_value(monkeypatch):
    mod = _load_parameter()

    class Mod(BaseFakeModule):
        params = _param_params(value="500")

    ConnCls = _param_conn_factory(current_value="300", display_value="300", spfile_value="300")
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("alter system set" in d.lower() for d in payload["ddls"])


def test_parameter_already_set_no_change(monkeypatch):
    mod = _load_parameter()

    class Mod(BaseFakeModule):
        params = _param_params(value="300")

    # display_value == value == spfile_value → no change
    ConnCls = _param_conn_factory(current_value="300", display_value="300", spfile_value="300")
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_parameter_reset_with_spfile_value(monkeypatch):
    mod = _load_parameter()

    class Mod(BaseFakeModule):
        params = _param_params(state="reset", scope="spfile")

    # spfile_value is set → should reset
    ConnCls = _param_conn_factory(current_value="300", display_value="300", spfile_value="300")
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("alter system reset" in d.lower() for d in payload["ddls"])


def test_parameter_reset_nothing_to_do(monkeypatch):
    mod = _load_parameter()

    class Mod(BaseFakeModule):
        params = _param_params(state="reset", scope="memory", value=None)

    # spfile_value=None + default==current → nothing to do
    ConnCls = _param_conn_factory(current_value="300", display_value="300", spfile_value=None)

    class PatchedConn(ConnCls):
        def __init__(self, m):
            super().__init__(m)
            # Override with default_value == current_value
            self.responses = [
                {"name": "open_cursors", "current_value": "300", "ismodified": "FALSE",
                 "isdefault": "TRUE", "default_value": "300", "display_value": "300"},
                {"name": "open_cursors", "spfile_value": None},
            ]

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", PatchedConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_parameter_underscore_requires_sysdba(monkeypatch):
    mod = _load_parameter()

    class Mod(BaseFakeModule):
        params = {
            **_param_params(name="_allow_level_without_connect_by", value="TRUE"),
            "mode": "normal",
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: BaseFakeConn(m), raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "sysdba" in exc.value.args[0]["msg"].lower()


def test_parameter_boolean_value(monkeypatch):
    """Boolean values like TRUE/FALSE should not get single-quoted."""
    mod = _load_parameter()

    class Mod(BaseFakeModule):
        params = _param_params(name="blank_trimming", value="TRUE")

    ConnCls = _param_conn_factory(current_value="FALSE", display_value="FALSE", spfile_value="FALSE")
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", ConnCls, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    # Boolean value should appear without quotes
    assert any("=TRUE" in d for d in payload["ddls"])


# ===========================================================================
# oracle_profile
# ===========================================================================

def _load_profile():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_profile.py"), "oracle_profile_test"
    )


class _ProfileFakeConn(BaseFakeConn):
    """execute_select returns tuples (as oracle_profile uses execute_select not execute_select_to_dict)."""

    def __init__(self, module, existing_attrs=None):
        super().__init__(module)
        # existing_attrs: list of (resource_name, limit) tuples or None
        self._existing_attrs = existing_attrs

    def execute_select(self, sql, params=None, fetchone=False):
        if self._existing_attrs is None:
            return set()
        return set(self._existing_attrs)

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        # Also used inside create_profile/ensure_profile_state to re-read profile
        if self._existing_attrs is None:
            return [] if not fetchone else {}
        return [{"resource_name": r, "limit": l} for (r, l) in self._existing_attrs]


def _profile_params(state="present", attrs=None, attribute_name=None, attribute_value=None):
    p = {
        **BASE_CONN_PARAMS,
        "profile": "TEST_PROFILE",
        "state": state,
        "attributes": attrs or {},
        "attribute_name": attribute_name or [],
        "attribute_value": attribute_value or [],
    }
    return p


def test_profile_creates_new(monkeypatch):
    mod = _load_profile()

    class Mod(BaseFakeModule):
        params = _profile_params(attrs={"PASSWORD_REUSE_MAX": "10"})

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection", lambda m: _ProfileFakeConn(m, existing_attrs=None), raising=False
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("create profile" in d.lower() for d in payload["ddls"])


def test_profile_modify_existing(monkeypatch):
    mod = _load_profile()

    class Mod(BaseFakeModule):
        params = _profile_params(attrs={"PASSWORD_REUSE_MAX": "20"})

    existing = [("PASSWORD_REUSE_MAX", "10"), ("SESSIONS_PER_USER", "UNLIMITED")]
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection", lambda m: _ProfileFakeConn(m, existing_attrs=existing), raising=False
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("alter profile" in d.lower() for d in payload["ddls"])


def test_profile_no_change_when_already_correct(monkeypatch):
    mod = _load_profile()

    class Mod(BaseFakeModule):
        params = _profile_params(attrs={"PASSWORD_REUSE_MAX": "10"})

    existing = [("PASSWORD_REUSE_MAX", "10")]
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection", lambda m: _ProfileFakeConn(m, existing_attrs=existing), raising=False
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_profile_drops_existing(monkeypatch):
    mod = _load_profile()

    class Mod(BaseFakeModule):
        params = _profile_params(state="absent")

    existing = [("PASSWORD_REUSE_MAX", "10")]
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection", lambda m: _ProfileFakeConn(m, existing_attrs=existing), raising=False
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True
    assert any("drop profile" in d.lower() for d in payload["ddls"])


def test_profile_absent_when_missing_no_change(monkeypatch):
    mod = _load_profile()

    class Mod(BaseFakeModule):
        params = _profile_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection", lambda m: _ProfileFakeConn(m, existing_attrs=None), raising=False
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_profile_mismatched_attribute_lists_fails(monkeypatch):
    mod = _load_profile()

    class Mod(BaseFakeModule):
        params = _profile_params(
            attribute_name=["PASSWORD_REUSE_MAX", "SESSIONS_PER_USER"],
            attribute_value=["10"],  # mismatched length
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection", lambda m: _ProfileFakeConn(m, existing_attrs=None), raising=False
    )

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "same length" in exc.value.args[0]["msg"].lower()
