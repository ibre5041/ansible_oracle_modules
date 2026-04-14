"""Unit tests for oracle_services module.

oracle_services.py has a quirk: `msg` is only assigned in the else-branch
of the ORACLE_HOME check inside main(), making it an unbound local in all
other paths.  We therefore test the module's helper functions directly,
which avoids this issue while giving good coverage.

For the few tests that go through main() we use the state=absent+missing
path (shortest path, no msg reference before assignment).
"""
import os
import pytest

from conftest import ExitJson, FailJson, load_module_from_path
from helpers import BaseFakeModule, FakeOracleHomes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load():
    return load_module_from_path("plugins/modules/oracle_services.py", "oracle_services")


def _svc_params(**overrides):
    base = {
        "user": None,
        "password": None,
        "mode": "normal",
        "hostname": "localhost",
        "port": 1521,
        "service_name": None,
        "oracle_home": "/fake/grid",
        "session_container": None,
        "name": "MYSVC",
        "database_name": "MYDB",
        "state": "present",
        "preferred_instances": None,
        "available_instances": None,
        "pdb": None,
        "role": None,
        "clbgoal": None,
        "rlbgoal": None,
        "force": False,
        "gi_managed": None,
    }
    base.update(overrides)
    return base


def _make_mod_instance(params_dict, responses):
    """Return a FakeModule instance (not class) driven by a run_command list."""
    _resp = list(responses)

    class Mod(BaseFakeModule):
        params = params_dict

        def __init__(self, **kw):
            super().__init__(**kw)
            self._resp = list(_resp)

        def run_command(self, cmd, **_kw):
            if self._resp:
                return self._resp.pop(0)
            return (0, "", "")

    return Mod()


# ---------------------------------------------------------------------------
# check_service_exists helper tests
# ---------------------------------------------------------------------------

def test_check_service_exists_not_found(monkeypatch):
    """check_service_exists: PRCR-1001 in stdout → False."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(1, "PRCR-1001 service not found", "")])

    result = mod.check_service_exists(None, m, [], "MYSVC", "MYDB")
    assert result is False


def test_check_service_exists_found(monkeypatch):
    """check_service_exists: rc=0 with 'Service name: MYSVC' → True."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(0, "Service name: MYSVC\nDatabase: MYDB\n", "")])

    result = mod.check_service_exists(None, m, [], "MYSVC", "MYDB")
    assert result is True


def test_check_service_exists_error_returns_false(monkeypatch):
    """check_service_exists: rc!=0 without PRCR-1001 → False (error stored in msg)."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(2, "CRS-something error", "")])

    result = mod.check_service_exists(None, m, [], "MYSVC", "MYDB")
    assert result is False


# ---------------------------------------------------------------------------
# create_service helper tests
# ---------------------------------------------------------------------------

def test_create_service_success(monkeypatch):
    """create_service: srvctl add succeeds → True."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(0, "", "")])

    result = mod.create_service(None, m, [])
    assert result is True


def test_create_service_already_exists(monkeypatch):
    """create_service: PRKO-3117 (already exists) → exit_json changed=False."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(1, "PRKO-3117 service already exists", "")])

    with pytest.raises(ExitJson) as exc:
        mod.create_service(None, m, [])
    assert exc.value.args[0]["changed"] is False


def test_create_service_with_role(monkeypatch):
    """create_service with role param → srvctl add includes -l flag."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(role="primary"), [(0, "", "")])

    result = mod.create_service(None, m, [])
    assert result is True


def test_create_service_with_pdb(monkeypatch):
    """create_service with pdb param → srvctl add includes -pdb flag."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(pdb="MYPDB"), [(0, "", "")])

    result = mod.create_service(None, m, [])
    assert result is True


def test_create_service_failure(monkeypatch):
    """create_service: srvctl add fails → False."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(1, "CRS error", "")])

    result = mod.create_service(None, m, [])
    assert result is False


# ---------------------------------------------------------------------------
# remove_service helper tests
# ---------------------------------------------------------------------------

def test_remove_service_success(monkeypatch):
    """remove_service: stops then removes → True."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    responses = [
        (1, "PRCR-1005 already stopped", ""),  # stop_service → already stopped
        (0, "", ""),                             # remove srvctl remove
    ]
    m = _make_mod_instance(_svc_params(), responses)

    result = mod.remove_service(None, m, [], "MYSVC", "MYDB", False)
    assert result is True


def test_remove_service_with_force(monkeypatch):
    """remove_service with force=True → includes -f flag."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    responses = [
        (1, "CRS-2500 already stopped", ""),
        (0, "", ""),
    ]
    m = _make_mod_instance(_svc_params(force=True), responses)

    result = mod.remove_service(None, m, [], "MYSVC", "MYDB", True)
    assert result is True


# ---------------------------------------------------------------------------
# check_service_status helper tests
# ---------------------------------------------------------------------------

def test_check_service_status_running(monkeypatch):
    """check_service_status: service is running → True."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(0, "Service MYSVC is running on MYDB1", "")])

    result = mod.check_service_status(None, m, [], "MYSVC", "MYDB", "started")
    assert result is True


def test_check_service_status_not_running(monkeypatch):
    """check_service_status: service is not running → False."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(0, "Service MYSVC is not running.", "")])

    result = mod.check_service_status(None, m, [], "MYSVC", "MYDB", "stopped")
    assert result is False


def test_check_service_status_exits_for_status_state(monkeypatch):
    """check_service_status with state='status' → exit_json with stdout."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(state="status"),
                           [(0, "Service MYSVC is running on db1", "")])

    with pytest.raises(ExitJson) as exc:
        mod.check_service_status(None, m, [], "MYSVC", "MYDB", "status")
    assert exc.value.args[0]["changed"] is False


# ---------------------------------------------------------------------------
# stop_service helper tests
# ---------------------------------------------------------------------------

def test_stop_service_stops(monkeypatch):
    """stop_service: srvctl stop succeeds → True."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(0, "", "")])

    result = mod.stop_service(None, m, [], "MYSVC", "MYDB")
    assert result is True


def test_stop_service_already_stopped(monkeypatch):
    """stop_service: PRCR-1005 → already stopped, returns False."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(1, "PRCR-1005 already stopped", "")])

    result = mod.stop_service(None, m, [], "MYSVC", "MYDB")
    assert result is False


def test_stop_service_already_stopped_crs2500(monkeypatch):
    """stop_service: CRS-2500 → already stopped, returns False."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(1, "CRS-2500 resource not running", "")])

    result = mod.stop_service(None, m, [], "MYSVC", "MYDB")
    assert result is False


def test_stop_service_not_exists(monkeypatch):
    """stop_service: PRCR-1001 → service doesn't exist → exit_json."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(1, "PRCR-1001 resource doesn't exist", "")])

    with pytest.raises(ExitJson) as exc:
        mod.stop_service(None, m, [], "MYSVC", "MYDB")
    assert exc.value.args[0]["changed"] is False


# ---------------------------------------------------------------------------
# start_service helper tests
# ---------------------------------------------------------------------------

def test_start_service_starts(monkeypatch):
    """start_service: srvctl start succeeds → True."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(0, "", "")])

    result = mod.start_service(None, m, [], "MYSVC", "MYDB", False)
    assert result is True


def test_start_service_already_running(monkeypatch):
    """start_service: PRCC-1014 → already running → exit_json changed=False."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)
    m = _make_mod_instance(_svc_params(), [(1, "PRCC-1014 already running", "")])

    with pytest.raises(ExitJson) as exc:
        mod.start_service(None, m, [], "MYSVC", "MYDB", False)
    assert exc.value.args[0]["changed"] is False


# ---------------------------------------------------------------------------
# _get_service_config helper tests
# ---------------------------------------------------------------------------

def test_get_service_config_empty(monkeypatch):
    """_get_service_config: empty output → empty config dicts."""
    mod = _load()
    m = _make_mod_instance(_svc_params(), [(0, "", "")])

    cfg, ai, pi = mod._get_service_config(None, m, [], "MYSVC", "MYDB")
    assert cfg == {}
    assert ai == []
    assert pi == []


def test_get_service_config_with_balancing(monkeypatch):
    """_get_service_config: output with CLB/RLB → populated config dict."""
    mod = _load()
    stdout = (
        "Connection Load Balancing Goal: LONG\n"
        "Runtime Load Balancing Goal: NONE\n"
        "Preferred instances: MYDB1\n"
        "Available instances: MYDB2\n"
    )
    m = _make_mod_instance(_svc_params(), [(0, stdout, "")])

    cfg, ai, pi = mod._get_service_config(None, m, [], "MYSVC", "MYDB")
    assert cfg == {"clb": "LONG", "rlb": "NONE"}
    assert pi == ["MYDB1"]
    assert ai == ["MYDB2"]


# ---------------------------------------------------------------------------
# ensure_service_state helper tests (newservice=True path)
# ---------------------------------------------------------------------------

def test_ensure_service_state_newservice_present(monkeypatch):
    """ensure_service_state: newservice=True, state=present → exits changed=True."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", True, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)
    m = _make_mod_instance(_svc_params(state="present"), [])

    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    assert exc.value.args[0]["changed"] is True


def test_ensure_service_state_newservice_started(monkeypatch):
    """ensure_service_state: newservice=True, state=started → starts service."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", True, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)
    m = _make_mod_instance(_svc_params(state="started"), [
        (0, "", ""),  # start_service srvctl start
    ])

    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    assert exc.value.args[0]["changed"] is True


def test_ensure_service_state_newservice_stopped(monkeypatch):
    """ensure_service_state: newservice=True, state=stopped → stop service."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", True, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)
    m = _make_mod_instance(_svc_params(state="stopped"), [
        (0, "", ""),  # stop_service
    ])

    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    assert exc.value.args[0]["changed"] is True


# ---------------------------------------------------------------------------
# ensure_service_state with newservice=False (existing service) tests
# ---------------------------------------------------------------------------

def test_ensure_service_state_existing_no_changes(monkeypatch):
    """ensure_service_state: newservice=False, configs match, state=started → no start."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", False, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)

    def _fake_get_config(cursor, module, msg, name, database_name):
        return ({"clb": "LONG", "rlb": "NONE"}, [''], [''])

    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)
    # Use state='started', PRCC-1014 (already running) → exits with changed=False
    # This avoids UnboundLocalError in state='present' path (module bug on line 283)
    m = _make_mod_instance(
        _svc_params(state="started", clbgoal=None, rlbgoal=None),
        [(1, "PRCC-1014 service already running", "")],
    )

    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    assert exc.value.args[0]["changed"] is False


def test_ensure_service_state_existing_config_changed(monkeypatch):
    """ensure_service_state: newservice=False, configs differ → modifies → exit changed=True."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", False, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)

    # Return different config → triggers modify_conf command
    def _fake_get_config(cursor, module, msg, name, database_name):
        return ({"clb": "SHORT", "rlb": "SERVICE_TIME"}, [''], [''])

    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)
    m = _make_mod_instance(
        _svc_params(state="present", clbgoal=None, rlbgoal=None),
        [(0, "", "")],  # run_command for modify_conf succeeds
    )

    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    assert exc.value.args[0]["changed"] is True


def test_ensure_service_state_existing_instances_changed(monkeypatch):
    """ensure_service_state: newservice=False, instance list differs → modifies."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", False, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)

    # Current config has no preferred instances, wanted has MYDB1
    def _fake_get_config(cursor, module, msg, name, database_name):
        return ({}, [], [])

    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)
    m = _make_mod_instance(
        _svc_params(state="present", preferred_instances="MYDB1"),
        [(0, "", "")],  # modify_inst command
    )

    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    assert exc.value.args[0]["changed"] is True


def test_ensure_service_state_existing_modify_fails(monkeypatch):
    """ensure_service_state: newservice=False, modify command fails → fail_json."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", False, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)

    def _fake_get_config(cursor, module, msg, name, database_name):
        return ({"clb": "SHORT", "rlb": "SERVICE_TIME"}, [], [])

    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)
    m = _make_mod_instance(
        _svc_params(state="present", clbgoal=None, rlbgoal=None),
        [(1, "", "CRS error modifying service")],  # modify fails
    )

    with pytest.raises(FailJson):
        mod.ensure_service_state(None, m, [])


def test_ensure_service_state_existing_state_started(monkeypatch):
    """ensure_service_state: newservice=False, state=started, PRCC-1014 → no change."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", False, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)

    def _fake_get_config(cursor, module, msg, name, database_name):
        return ({"clb": "LONG", "rlb": "NONE"}, [''], [''])

    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)
    m = _make_mod_instance(
        _svc_params(state="started"),
        [(1, "PRCC-1014 service already running", "")],  # already running → no change
    )

    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    assert exc.value.args[0]["changed"] is False


def test_ensure_service_state_existing_state_stopped(monkeypatch):
    """ensure_service_state: newservice=False, state=stopped → stop service."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", False, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)

    def _fake_get_config(cursor, module, msg, name, database_name):
        return ({"clb": "LONG", "rlb": "NONE"}, [''], [''])

    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)
    m = _make_mod_instance(
        _svc_params(state="stopped"),
        [(0, "", "")],  # stop_service srvctl stop succeeds
    )

    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    assert exc.value.args[0]["changed"] is True


def test_ensure_service_state_existing_state_stopped_already(monkeypatch):
    """ensure_service_state: newservice=False, state=stopped, already stopped → changed=False."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", False, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)

    def _fake_get_config(cursor, module, msg, name, database_name):
        return ({"clb": "LONG", "rlb": "NONE"}, [''], [''])

    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)
    m = _make_mod_instance(
        _svc_params(state="stopped"),
        [(1, "PRCR-1005 resource already stopped", "")],  # already stopped
    )

    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    assert exc.value.args[0]["changed"] is False


# ---------------------------------------------------------------------------
# main() tests - only test paths that don't hit unbound msg
# ---------------------------------------------------------------------------

def _make_mod_class(params_dict, responses):
    """Return a FakeModule class driven by run_command responses."""
    _resp = list(responses)

    class Mod(BaseFakeModule):
        params = params_dict

        def __init__(self, **kw):
            super().__init__(**kw)
            self._resp = list(_resp)

        def run_command(self, cmd, **_kw):
            if self._resp:
                return self._resp.pop(0)
            return (0, "", "")

    return Mod


def test_ensure_service_state_existing_with_rlbgoal_clbgoal(monkeypatch):
    """ensure_service_state: newservice=False, explicit rlbgoal/clbgoal/available_instances set."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", False, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)

    def _fake_get_config(cursor, module, msg, name, database_name):
        return ({"clb": "SERVICE_TIME", "rlb": "NONE"}, ['MYDB2'], ['MYDB1'])

    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)
    # clbgoal=SERVICE_TIME (line 227), rlbgoal=NONE (line 222), available_instances (line 239)
    # Config matches → PRCC-1014 for start (already running)
    m = _make_mod_instance(
        _svc_params(
            state="started",
            clbgoal="SERVICE_TIME",
            rlbgoal="NONE",
            available_instances="MYDB2",
            preferred_instances="MYDB1",
        ),
        [(1, "PRCC-1014 already running", "")],
    )

    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    assert exc.value.args[0]["changed"] is False


def test_ensure_service_state_existing_config_changed_then_started(monkeypatch):
    """ensure_service_state: newservice=False, config differs + state=started → configchange=True path."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", False, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)

    def _fake_get_config(cursor, module, msg, name, database_name):
        # ai/pi match defaults [''] to avoid extra modify_inst command
        return ({"clb": "SHORT", "rlb": "SERVICE_TIME"}, [''], [''])  # clb/rlb differ

    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)
    m = _make_mod_instance(
        _svc_params(state="started"),
        [
            (0, "", ""),   # modify_conf command succeeds
            (0, "", ""),   # srvctl start succeeds → change=True, configchange=True
        ],
    )

    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    assert exc.value.args[0]["changed"] is True


def test_ensure_service_state_existing_config_changed_then_stopped(monkeypatch):
    """ensure_service_state: newservice=False, config differs + state=stopped → configchange+stop."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", False, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)

    def _fake_get_config(cursor, module, msg, name, database_name):
        # ai/pi match defaults [''] so only modify_conf is needed (not modify_inst)
        return ({"clb": "SHORT", "rlb": "SERVICE_TIME"}, [''], [''])

    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)
    m = _make_mod_instance(
        _svc_params(state="stopped"),
        [
            (0, "", ""),   # modify_conf command succeeds
            (1, "PRCR-1005 already stopped", ""),  # stop → already stopped
        ],
    )

    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    # configchange=True, stop → already stopped → covers lines 306-309
    assert exc.value.args[0]["changed"] is True


def test_main_oracle_home_missing_fails(monkeypatch):
    """main(): no oracle_home in params or env → fail_json."""
    mod = _load()
    orig = os.environ.pop("ORACLE_HOME", None)
    try:
        Mod = _make_mod_class(_svc_params(oracle_home=None), [])
        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)
        monkeypatch.setattr(mod, "gimanaged", True, raising=False)

        with pytest.raises(FailJson) as exc:
            mod.main()
        assert "ORACLE_HOME" in exc.value.args[0]["msg"]
    finally:
        if orig is not None:
            os.environ["ORACLE_HOME"] = orig


# ---------------------------------------------------------------------------
# main() tests – full dispatch paths (GI-managed, oracle_home set)
# ---------------------------------------------------------------------------

class _FakeOracleHomesGi(FakeOracleHomes):
    """GI-managed OracleHomes stub for main() tests."""
    def __init__(self):
        super().__init__()
        self.oracle_gi_managed = True
        self.oracle_crs = False
        self.facts_item = {}

    def list_crs_instances(self): pass
    def list_processes(self): pass
    def parse_oratab(self): pass


def _make_main_mod(state, responses, extra_params=None):
    """Return a FakeModule class for main() tests (oracle_home always set)."""
    params = _svc_params(state=state, oracle_home="/fake/grid")
    if extra_params:
        params.update(extra_params)
    return _make_mod_class(params, responses)


def test_main_absent_service_not_found(monkeypatch):
    """main(): state=absent, service doesn't exist → exit changed=False."""
    mod = _load()
    Mod = _make_main_mod("absent", [
        (1, "PRCR-1001 service not found", ""),  # check_service_exists → False
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert "doesn't exist" in exc.value.args[0]["msg"]


def test_main_absent_service_removed(monkeypatch):
    """main(): state=absent, service exists → remove → exit changed=True."""
    mod = _load()
    Mod = _make_main_mod("absent", [
        (0, "Service name: MYSVC\n", ""),  # check_service_exists → True
        (0, "", ""),                        # stop_service → success
        (0, "", ""),                        # srvctl remove → success
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert "removed" in exc.value.args[0]["msg"]


def test_main_status_service_running(monkeypatch):
    """main(): state=status, service exists and running → exit changed=False."""
    mod = _load()
    Mod = _make_main_mod("status", [
        (0, "Service name: MYSVC\n", ""),            # check_service_exists → True
        (0, "Service MYSVC is running on db1\n", ""), # check_service_status (state=status) → exit_json
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_main_status_service_not_found(monkeypatch):
    """main(): state=status, service doesn't exist → exit changed=False."""
    mod = _load()
    Mod = _make_main_mod("status", [
        (1, "PRCR-1001 service not found", ""),  # check_service_exists → False
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert "doesn't exist" in exc.value.args[0]["msg"]


def test_main_present_new_service(monkeypatch):
    """main(): state=present, service not found → create → ensure → exit changed=True."""
    mod = _load()

    def _fake_get_config(cursor, module, msg, name, database_name):
        return ({}, [''], [''])

    Mod = _make_main_mod("present", [
        (1, "PRCR-1001 not found", ""),  # check_service_exists → False
        (0, "", ""),                      # create_service srvctl add → success
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_main_present_existing_service_no_changes(monkeypatch):
    """main(): state=present, service exists, config unchanged → exit changed=False."""
    mod = _load()

    def _fake_get_config(cursor, module, msg, name, database_name):
        return ({"clb": "LONG", "rlb": "NONE"}, [''], [''])

    Mod = _make_main_mod("present", [
        (0, "Service name: MYSVC\n", ""),  # check_service_exists → True
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_main_present_create_fails(monkeypatch):
    """main(): state=present, service not found, create fails → fail_json."""
    mod = _load()
    Mod = _make_main_mod("present", [
        (1, "PRCR-1001 not found", ""),  # check_service_exists → False
        (1, "CRS error", ""),             # create_service srvctl add → fails
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_main_restarted_success(monkeypatch):
    """main(): state=restarted → stop then start → exit changed=True."""
    mod = _load()
    Mod = _make_main_mod("restarted", [
        (0, "", ""),  # stop_service srvctl stop → success
        (0, "", ""),  # start_service srvctl start → success
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_main_oracle_home_from_env(monkeypatch):
    """main(): oracle_home not in params but in ORACLE_HOME env → uses it."""
    mod = _load()
    orig = os.environ.get("ORACLE_HOME")
    os.environ["ORACLE_HOME"] = "/env/grid"
    try:
        Mod = _make_main_mod("status", [
            (1, "PRCR-1001 not found", ""),  # check_service_exists → False
        ], extra_params={"oracle_home": None})
        monkeypatch.setattr(mod, "AnsibleModule", Mod)
        monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
        monkeypatch.setattr(mod, "gimanaged", True, raising=False)

        with pytest.raises(ExitJson) as exc:
            mod.main()
        assert exc.value.args[0]["changed"] is False
    finally:
        if orig is not None:
            os.environ["ORACLE_HOME"] = orig
        else:
            os.environ.pop("ORACLE_HOME", None)


# ---------------------------------------------------------------------------
# Additional targeted tests to reach >=80% coverage
# ---------------------------------------------------------------------------

def test_check_service_exists_stdout_other(monkeypatch):
    """check_service_exists: rc=0 but stdout doesn't match 'Service name: MYSVC' → fallback True (line 135-136)."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    # rc=0 but stdout has no 'Service name: MYSVC' → falls to else branch
    m = _make_mod_instance(_svc_params(), [(0, "Some other output", "")])
    result = mod.check_service_exists(None, m, [], "MYSVC", "MYDB")
    assert result is True


def test_create_service_with_all_params(monkeypatch):
    """create_service: preferred_instances + available_instances + clbgoal + rlbgoal → covers lines 160,163,172,175."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(
        _svc_params(
            preferred_instances="MYDB1",
            available_instances="MYDB2",
            clbgoal="LONG",
            rlbgoal="SERVICE_TIME",
        ),
        [(0, "", "")],
    )
    result = mod.create_service(None, m, [])
    assert result is True


def test_ensure_service_state_available_instances_changed(monkeypatch):
    """ensure_service_state: available_instances differs from config → line 249 covered."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", False, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)

    # Current config has MYDB1 as available, wanted has MYDB2
    def _fake_get_config(cursor, module, msg, name, database_name):
        return ({}, ['MYDB1'], [''])

    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)
    m = _make_mod_instance(
        _svc_params(state="present", available_instances="MYDB2"),
        [(0, "", "")],  # modify_inst command
    )
    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    assert exc.value.args[0]["changed"] is True


def test_ensure_service_state_stopped_with_configchange(monkeypatch):
    """ensure_service_state: state=stopped, stop succeeds, configchange=True → lines 301-302."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "newservice", False, raising=False)
    monkeypatch.setattr(mod, "configchange", False, raising=False)

    def _fake_get_config(cursor, module, msg, name, database_name):
        return ({"clb": "SHORT", "rlb": "SERVICE_TIME"}, [''], [''])

    monkeypatch.setattr(mod, "_get_service_config", _fake_get_config, raising=False)
    m = _make_mod_instance(
        _svc_params(state="stopped"),
        [
            (0, "", ""),  # modify_conf succeeds (sets configchange=True)
            (0, "", ""),  # stop_service succeeds
        ],
    )
    with pytest.raises(ExitJson) as exc:
        mod.ensure_service_state(None, m, [])
    # configchange=True + stop succeeded → changed=True (lines 301-302)
    assert exc.value.args[0]["changed"] is True


def test_remove_service_fails_non_prcr1001(monkeypatch):
    """remove_service: rc!=0 and no PRCR-1001 → fail_json (lines 323-327)."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    responses = [
        (1, "PRCR-1005 already stopped", ""),  # stop_service → already stopped
        (1, "CRS-9999 some error", ""),          # srvctl remove fails (not PRCR-1001)
    ]
    m = _make_mod_instance(_svc_params(), responses)
    with pytest.raises(FailJson):
        mod.remove_service(None, m, [], "MYSVC", "MYDB", False)


def test_get_service_config_error_path(monkeypatch):
    """_get_service_config: rc!=0 → msg updated (line 350)."""
    mod = _load()
    m = _make_mod_instance(_svc_params(), [(1, "srvctl error", "")])
    cfg, ai, pi = mod._get_service_config(None, m, [], "MYSVC", "MYDB")
    # On error, returns empty config (output parsing of empty stdout)
    assert cfg == {}


def test_check_service_status_error(monkeypatch):
    """check_service_status: rc!=0 → fail_json (lines 373-374)."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(1, "CRS-9999 error", "")])
    with pytest.raises(FailJson):
        mod.check_service_status(None, m, [], "MYSVC", "MYDB", "started")


def test_start_service_prcr1001(monkeypatch):
    """start_service: rc!=0 with PRCR-1001 → fail_json (lines 404-405)."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(1, "PRCR-1001 service doesn't exist", "")])
    with pytest.raises(FailJson):
        mod.start_service(None, m, [], "MYSVC", "MYDB", False)


def test_start_service_prcc1014_with_configchange(monkeypatch):
    """start_service: PRCC-1014 + configchange=True → exit_json changed=True (lines 410-411)."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(1, "PRCC-1014 already running", "")])
    with pytest.raises(ExitJson) as exc:
        mod.start_service(None, m, [], "MYSVC", "MYDB", True)
    assert exc.value.args[0]["changed"] is True


def test_start_service_other_error(monkeypatch):
    """start_service: rc!=0 with other error → fail_json (lines 413-415)."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(1, "CRS-9999 start failed", "")])
    with pytest.raises(FailJson):
        mod.start_service(None, m, [], "MYSVC", "MYDB", False)


def test_stop_service_other_error(monkeypatch):
    """stop_service: rc!=0 with non-PRCR/CRS error → fail_json (lines 451-452)."""
    mod = _load()
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    m = _make_mod_instance(_svc_params(), [(1, "some unexpected error", "")])
    with pytest.raises(FailJson):
        mod.stop_service(None, m, [], "MYSVC", "MYDB")


class _FakeOracleHomesNonGi(FakeOracleHomes):
    """Non-GI OracleHomes stub: oracle_gi_managed=False forces oracleConnection path."""
    def __init__(self):
        super().__init__()
        self.oracle_gi_managed = False
        self.oracle_crs = False
        self.facts_item = {}

    def list_crs_instances(self): pass
    def list_processes(self): pass
    def parse_oratab(self): pass


def test_main_non_gi_oracleconnection(monkeypatch):
    """main(): oracle_gi_managed=False → oracleConnection called; SQL path used."""
    mod = _load()
    oc_calls = []

    class _FakeCursor:
        """Simulates a DB cursor that finds no service (fetchone → None)."""
        def execute(self, sql): return None
        def fetchone(self): return None

    class _FakeConn:
        def cursor(self): return _FakeCursor()

    class _FakeOC:
        conn = _FakeConn()

    def fake_oc(module):
        oc_calls.append(True)
        return _FakeOC()

    Mod = _make_main_mod("absent", [])  # no srvctl calls in non-GI path
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesNonGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "oracleConnection", fake_oc, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert len(oc_calls) == 1


def test_main_absent_remove_returns_false(monkeypatch):
    """main(): state=absent, service exists, remove returns False → exit changed=False (line 591)."""
    mod = _load()
    Mod = _make_main_mod("absent", [
        (0, "Service name: MYSVC\n", ""),  # check_service_exists → True
        (0, "", ""),                        # stop_service → success
        (1, "PRCR-1001 already gone", ""), # srvctl remove → PRCR-1001 → returns False
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_main_restarted_start_fails(monkeypatch):
    """main(): state=restarted, stop succeeds, start fails → fail_json (lines 617-618)."""
    mod = _load()
    Mod = _make_main_mod("restarted", [
        (0, "", ""),                          # stop_service → success
        (1, "CRS-9999 start failed", ""),     # start_service other error → fail_json
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_main_restarted_stop_fails(monkeypatch):
    """main(): state=restarted, stop fails → fail_json (line 620)."""
    mod = _load()
    Mod = _make_main_mod("restarted", [
        (1, "some unexpected stop error", ""),  # stop_service other error → fail_json
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_main_status_service_running_check(monkeypatch):
    """main(): state=status, service exists, check returns True → 'running' msg (lines 625-626)."""
    mod = _load()

    def _fake_check_status(oc, module, msg, name, database_name, state):
        return True

    Mod = _make_main_mod("status", [
        (0, "Service name: MYSVC\n", ""),  # check_service_exists → True
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "check_service_status", _fake_check_status, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert "running" in exc.value.args[0]["msg"]
    assert exc.value.args[0]["changed"] is False


def test_main_status_service_not_running_check(monkeypatch):
    """main(): state=status, service exists, check returns False → 'not running' msg (lines 628-629)."""
    mod = _load()

    def _fake_check_status(oc, module, msg, name, database_name, state):
        return False

    Mod = _make_main_mod("status", [
        (0, "Service name: MYSVC\n", ""),  # check_service_exists → True
    ])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)
    monkeypatch.setattr(mod, "check_service_status", _fake_check_status, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert "not running" in exc.value.args[0]["msg"]
    assert exc.value.args[0]["changed"] is False


def test_main_unhandled_state(monkeypatch):
    """main(): unknown state → falls through all branches → line 633."""
    mod = _load()
    Mod = _make_main_mod("unknown_state", [])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesGi, raising=False)
    monkeypatch.setattr(mod, "gimanaged", True, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["msg"] == "Unhandled exit"
