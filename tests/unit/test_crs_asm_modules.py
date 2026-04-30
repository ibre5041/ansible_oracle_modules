"""Unit tests for CRS/ASM modules (oracle_crs_asm, oracle_crs_db,
oracle_crs_listener, oracle_crs_service).

These modules use OracleHomes + module.run_command for all external calls.
We mock OracleHomes and override run_command via a response list.
"""
import pytest

from conftest import ExitJson, FailJson, load_module_from_path
from helpers import BASE_CONN_PARAMS, BaseFakeModule, FakeOracleHomes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(name):
    return load_module_from_path(f"plugins/modules/{name}.py", name)


def _make_mod(params_dict, responses, check_mode=False):
    """Return a FakeModule class with run_command driven by a response list.

    responses : list of (rc, stdout, stderr) tuples returned in order.
                After exhaustion, returns (0, "", "").
    """
    _responses = list(responses)

    class Mod(BaseFakeModule):
        params = params_dict
        _cls_check_mode = check_mode

        def __init__(self, **kw):
            super().__init__(**kw)
            self.check_mode = self.__class__._cls_check_mode
            self._resp = list(_responses)

        def run_command(self, cmd, **_kw):
            if self._resp:
                return self._resp.pop(0)
            return (0, "", "")

    return Mod


# crsctl stat res output for a resource of a given type / name
def _crsctl_output(res_type, res_name, extra_attrs=None):
    """Build a fake `crsctl stat res -p` output string."""
    attrs = {"NAME": "ora.{}.{}".format(res_name.lower(), res_type),
             "TYPE": "ora.{}.type".format(res_type),
             "ORACLE_HOME": "/u01/app/grid/19.0.0"}
    if extra_attrs:
        attrs.update(extra_attrs)
    body = "\n".join("{}={}".format(k, v) for k, v in attrs.items())
    return body + "\n\n"  # blank line terminates resource


# ===========================================================================
# oracle_crs_asm
# ===========================================================================

def _asm_params(**overrides):
    base = {
        "name": "asm",
        "state": "present",
        "enabled": True,
        "listener": None,
        "spfile": None,
        "pwfile": None,
        "diskstring": None,
        "force": False,
    }
    base.update(overrides)
    return base


def test_crs_asm_absent_missing_exits(monkeypatch):
    """state=absent, ASM not registered → already absent (no change)."""
    mod = _load("oracle_crs_asm")
    # run_command: crsctl stat res → empty (not found)
    Mod = _make_mod(_asm_params(state="absent"), [(0, "", "")])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_crs_asm_absent_existing_removes(monkeypatch):
    """state=absent, ASM registered → removes it (check_mode)."""
    mod = _load("oracle_crs_asm")
    asm_out = _crsctl_output("asm", "asm")
    responses = [
        (0, asm_out, ""),                        # crsctl stat res → found
        (0, "ASM is running on myhost.", ""),    # srvctl status asm (ensure_asm_state always checks)
    ]
    Mod = _make_mod(_asm_params(state="absent"), responses, check_mode=True)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_crs_asm_present_new_with_status(monkeypatch):
    """state=present, ASM not registered → add asm; status returns running."""
    mod = _load("oracle_crs_asm")
    responses = [
        (0, "", ""),                              # crsctl stat res → not found
        (0, "", ""),                              # srvctl add asm (run_change_command, not check_mode)
        (0, "ASM is running on myhost.", ""),     # srvctl status asm (ensure_asm_state)
    ]
    Mod = _make_mod(_asm_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_crs_asm_present_already_running(monkeypatch):
    """state=present, ASM registered and running → no changes."""
    mod = _load("oracle_crs_asm")
    asm_out = _crsctl_output("asm", "asm")
    responses = [
        (0, asm_out, ""),                        # crsctl stat res → found
        (0, "ASM is running on myhost.", ""),    # srvctl status asm
    ]
    Mod = _make_mod(_asm_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_crs_asm_gi_not_detected_fails(monkeypatch):
    """oracle_gi_managed=False → fail_json."""
    mod = _load("oracle_crs_asm")

    class _NoGi(FakeOracleHomes):
        oracle_gi_managed = False

    Mod = _make_mod(_asm_params(), [])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGi, raising=False)

    with pytest.raises(FailJson):
        mod.main()


# ===========================================================================
# oracle_crs_db
# ===========================================================================

def _crsdb_params(**overrides):
    base = {
        "name": "MYDB",
        "state": "present",
        "enabled": True,
        "force": False,
        "oraclehome": "/u01/oracle",
        "domain": None,
        "spfile": None,
        "pwfile": None,
        "role": None,
        "startoption": None,
        "stopoption": None,
        "dbname": None,
        "instance": None,
        "policy": None,
        "diskgroup": None,
    }
    base.update(overrides)
    return base


def test_crs_db_absent_missing(monkeypatch):
    """state=absent, DB not registered → already absent."""
    mod = _load("oracle_crs_db")
    Mod = _make_mod(_crsdb_params(state="absent"), [(0, "", "")])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_crs_db_present_new_check_mode(monkeypatch):
    """state=present, DB not registered → would add (check_mode)."""
    mod = _load("oracle_crs_db")
    responses = [
        (0, "", ""),              # crsctl stat res → not found
        (0, "Database is not running.", ""),  # srvctl status database
    ]
    Mod = _make_mod(_crsdb_params(), responses, check_mode=True)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_crs_db_absent_existing_check_mode(monkeypatch):
    """state=absent, DB registered → would remove (check_mode)."""
    mod = _load("oracle_crs_db")
    db_out = _crsctl_output("database", "mydb", {"ORACLE_HOME": "/u01/oracle"})
    responses = [
        (0, db_out, ""),          # crsctl stat res → found
        (0, "Database is running.", ""),  # srvctl status database
    ]
    Mod = _make_mod(_crsdb_params(state="absent"), responses, check_mode=True)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_crs_db_present_existing_no_change(monkeypatch):
    """state=present, DB registered with matching config → no change."""
    mod = _load("oracle_crs_db")
    db_out = _crsctl_output("database", "mydb", {"ORACLE_HOME": "/u01/oracle"})
    responses = [
        (0, db_out, ""),          # crsctl stat res → found
        (0, "Database is running.", ""),  # srvctl status database
    ]
    Mod = _make_mod(_crsdb_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_crs_db_gi_not_detected_fails(monkeypatch):
    """oracle_gi_managed=False → fail_json."""
    mod = _load("oracle_crs_db")

    class _NoGi(FakeOracleHomes):
        oracle_gi_managed = False

    Mod = _make_mod(_crsdb_params(), [])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGi, raising=False)

    with pytest.raises(FailJson):
        mod.main()


# ===========================================================================
# oracle_crs_listener
# ===========================================================================

def _listener_params(**overrides):
    base = {
        "name": "LISTENER",
        "state": "present",
        "enabled": True,
        "force": True,
        "oraclehome": "%CRS_HOME%",
        "skip": False,
        "endpoints": None,
    }
    base.update(overrides)
    return base


def test_crs_listener_absent_missing(monkeypatch):
    """state=absent, listener not registered → already absent."""
    mod = _load("oracle_crs_listener")
    Mod = _make_mod(_listener_params(state="absent"), [(0, "", "")])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_crs_listener_present_new_check_mode(monkeypatch):
    """state=present, listener not registered → add (check_mode)."""
    mod = _load("oracle_crs_listener")
    responses = [
        (0, "", ""),              # crsctl stat res → not found
    ]
    Mod = _make_mod(_listener_params(), responses, check_mode=True)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_crs_listener_present_existing_no_change(monkeypatch):
    """state=present, listener exists → no change (check_mode)."""
    mod = _load("oracle_crs_listener")
    # ORACLE_HOME must match params['oraclehome'] exactly to avoid modify being triggered
    lsnr_out = _crsctl_output("listener", "listener", {"ORACLE_HOME": "%CRS_HOME%"})
    responses = [
        (0, lsnr_out, ""),            # crsctl stat res → found
        (0, "Listener is running.", ""),  # srvctl status listener
    ]
    Mod = _make_mod(_listener_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_crs_listener_absent_existing_check_mode(monkeypatch):
    """state=absent, listener exists → remove (check_mode)."""
    mod = _load("oracle_crs_listener")
    lsnr_out = _crsctl_output("listener", "listener")
    responses = [
        (0, lsnr_out, ""),
    ]
    Mod = _make_mod(_listener_params(state="absent"), responses, check_mode=True)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


# ===========================================================================
# oracle_crs_service
# ===========================================================================

def _crs_svc_params(**overrides):
    base = {
        "name": "MYSVC",
        "db": "MYDB",
        "state": "present",
        "enabled": True,
        "force": False,
        "pdb": None,
        "role": None,
        "policy": None,
        "failovertype": None,
        "failovermethod": None,
        "failoverretry": None,
        "failoverdelay": None,
        "failover_restore": None,
        "edition": None,
        "maxlag": None,
        "clbgoal": None,
        "rlbgoal": None,
        "notification": None,
        "sql_translation_profile": None,
        "commit_outcome": None,
        "retention": None,
        "replay_init_time": None,
        "session_state": None,
        "tablefamilyid": None,
        "drain_timeout": None,
        "stopoption": None,
        "global": None,
        # RAC placement params (should only be passed to srvctl on RAC)
        "preferred": None,
        "available": None,
        "serverpool": None,
        "cardinality": None,
    }
    base.update(overrides)
    return base


def test_crs_service_absent_missing(monkeypatch):
    """state=absent, service not registered → already absent."""
    mod = _load("oracle_crs_service")
    Mod = _make_mod(_crs_svc_params(state="absent"), [(0, "", "")])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_crs_service_present_new_check_mode(monkeypatch):
    """state=present, service not registered → add (check_mode)."""
    mod = _load("oracle_crs_service")
    responses = [
        (0, "", ""),              # crsctl stat res → not found
    ]
    Mod = _make_mod(_crs_svc_params(), responses, check_mode=True)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_crs_service_gi_not_detected_fails(monkeypatch):
    """oracle_gi_managed=False → fail_json."""
    mod = _load("oracle_crs_service")

    class _NoGi(FakeOracleHomes):
        oracle_gi_managed = False

    Mod = _make_mod(_crs_svc_params(), [])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGi, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def _svc_crsctl_output(db, svc, extra_attrs=None):
    """Build a fake `crsctl stat res -p` output for a service resource."""
    attrs = {
        "NAME": "ora.{}.{}.svc".format(db.lower(), svc.lower()),
        "TYPE": "ora.service.type",
        "ORACLE_HOME": "/u01/app/grid/19.0.0",
        "ENABLED": "1",
    }
    if extra_attrs:
        attrs.update(extra_attrs)
    body = "\n".join("{}={}".format(k, v) for k, v in attrs.items())
    return body + "\n\n"


def test_crs_service_present_existing_no_change(monkeypatch):
    """state=present, service exists with matching config → no change."""
    mod = _load("oracle_crs_service")
    svc_out = _svc_crsctl_output("MYDB", "MYSVC")
    responses = [
        (0, svc_out, ""),                                # crsctl stat res → found
        (0, "Service MYSVC is running on MYDB.", ""),    # srvctl status service
    ]
    Mod = _make_mod(_crs_svc_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_crs_service_present_existing_modifies(monkeypatch):
    """state=present, service exists but has different attribute → srvctl modify called."""
    mod = _load("oracle_crs_service")
    # Service exists but clbgoal is currently LONG; we want SHORT → modify triggered
    svc_out = _svc_crsctl_output("MYDB", "MYSVC", {"CLB_GOAL": "LONG"})
    responses = [
        (0, svc_out, ""),                                # crsctl stat res → found
        (0, "", ""),                                     # srvctl modify service
        (0, "Service MYSVC is running on MYDB.", ""),    # srvctl status service
    ]
    Mod = _make_mod(_crs_svc_params(clbgoal="SHORT"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("modify" in c for c in exc.value.args[0]["commands"])


def test_crs_service_absent_existing_removes(monkeypatch):
    """state=absent, service exists → remove (check_mode)."""
    mod = _load("oracle_crs_service")
    svc_out = _svc_crsctl_output("MYDB", "MYSVC")
    responses = [
        (0, svc_out, ""),    # crsctl stat res → found
    ]
    Mod = _make_mod(_crs_svc_params(state="absent"), responses, check_mode=True)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("remove" in c for c in exc.value.args[0]["commands"])


def test_crs_service_state_started_running(monkeypatch):
    """state=started, service already running → no start command issued."""
    mod = _load("oracle_crs_service")
    svc_out = _svc_crsctl_output("MYDB", "MYSVC")
    responses = [
        (0, svc_out, ""),                                # crsctl stat res → found
        (0, "Service MYSVC is running on MYDB.", ""),    # srvctl status service
    ]
    Mod = _make_mod(_crs_svc_params(state="started"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert not any("start" in c for c in result["commands"])


def test_crs_service_state_started_not_running(monkeypatch):
    """state=started, service not running → start command issued."""
    mod = _load("oracle_crs_service")
    svc_out = _svc_crsctl_output("MYDB", "MYSVC")
    responses = [
        (0, svc_out, ""),                                        # crsctl stat res → found
        (0, "Service MYSVC is not running on MYDB.", ""),        # srvctl status service
        (0, "", ""),                                             # srvctl start service
    ]
    Mod = _make_mod(_crs_svc_params(state="started"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("start" in c for c in result["commands"])


def test_crs_service_state_stopped_running(monkeypatch):
    """state=stopped, service running → stop command issued."""
    mod = _load("oracle_crs_service")
    svc_out = _svc_crsctl_output("MYDB", "MYSVC")
    responses = [
        (0, svc_out, ""),                                # crsctl stat res → found
        (0, "Service MYSVC is running on MYDB.", ""),    # srvctl status service
        (0, "", ""),                                     # srvctl stop service
    ]
    Mod = _make_mod(_crs_svc_params(state="stopped"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("stop" in c for c in result["commands"])


def test_crs_service_state_restarted(monkeypatch):
    """state=restarted, service running → stop then start commands issued."""
    mod = _load("oracle_crs_service")
    svc_out = _svc_crsctl_output("MYDB", "MYSVC")
    responses = [
        (0, svc_out, ""),                                # crsctl stat res → found
        (0, "Service MYSVC is running on MYDB.", ""),    # srvctl status service
        (0, "", ""),                                     # srvctl stop service
        (0, "", ""),                                     # srvctl start service
    ]
    Mod = _make_mod(_crs_svc_params(state="restarted"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    commands = result["commands"]
    assert any("stop" in c for c in commands)
    assert any("start" in c for c in commands)


def test_crs_service_rac_params_excluded_on_has(monkeypatch):
    """On HAS (oracle_crs=False), RAC placement params must NOT appear in srvctl command.

    Reproduces GitHub issue #39: srvctl add/modify service on HAS rejects
    -preferred, -available, -cardinality, -serverpool with PRKO-2002.
    """
    mod = _load("oracle_crs_service")

    class _HasHomes(FakeOracleHomes):
        def __init__(self):
            super().__init__()
            self.oracle_crs = False      # HAS / Oracle Restart single-node
            self.oracle_restart = True

    # New service (not found in crsctl output) with user-supplied preferred param
    responses = [
        (0, "", ""),    # crsctl stat res → service not found
        # check_mode=True: srvctl add not executed; ensure_db_state skipped for new add
    ]
    Mod = _make_mod(
        _crs_svc_params(preferred="TESTDB", available="TESTDB2", cardinality="UNIFORM", serverpool="pool1"),
        responses,
        check_mode=True,
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _HasHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    for cmd in result["commands"]:
        assert "-preferred" not in cmd, f"HAS: unexpected -preferred in: {cmd}"
        assert "-available" not in cmd, f"HAS: unexpected -available in: {cmd}"
        assert "-cardinality" not in cmd, f"HAS: unexpected -cardinality in: {cmd}"
        assert "-serverpool" not in cmd, f"HAS: unexpected -serverpool in: {cmd}"


def test_crs_service_rac_params_included_on_rac(monkeypatch):
    """On RAC (oracle_crs=True), RAC placement params MUST appear in srvctl add command."""
    mod = _load("oracle_crs_service")

    class _RacHomes(FakeOracleHomes):
        def __init__(self):
            super().__init__()
            self.oracle_crs = True       # full RAC cluster
            self.oracle_restart = False

    # New service (not found) with preferred specified — should end up in the command
    responses = [
        (0, "", ""),    # crsctl stat res → service not found
    ]
    Mod = _make_mod(
        _crs_svc_params(preferred="TESTDB"),
        responses,
        check_mode=True,
    )
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _RacHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("-preferred" in cmd for cmd in result["commands"]), (
        "RAC: expected -preferred in srvctl command, got: " + str(result["commands"])
    )


# ===========================================================================
# oracle_crs_asm – additional coverage tests
# ===========================================================================

def test_crs_asm_run_change_command_failure(monkeypatch):
    """run_change_command: non-zero rc → fail_json (lines 96-102)."""
    mod = _load("oracle_crs_asm")
    responses = [
        (0, "", ""),           # crsctl stat res → not found
        (1, "out", "err"),     # srvctl add asm → failure
    ]
    Mod = _make_mod(_asm_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_crs_asm_run_change_command_stderr_only(monkeypatch):
    """run_change_command: rc=0 but stderr set → fail_json (lines 95-102)."""
    mod = _load("oracle_crs_asm")
    responses = [
        (0, "", ""),           # crsctl stat res → not found
        (0, "", "some error"), # srvctl add asm → stderr only
    ]
    Mod = _make_mod(_asm_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_crs_asm_get_change_static():
    """get_change static method: found and not-found cases (lines 107-110)."""
    mod = _load("oracle_crs_asm")
    change_set = [("spfile", "/u01/spfile.ora"), ("pwfile", "/u01/pw.ora")]
    assert mod.oracle_crs_asm.get_change(change_set, "spfile") == "/u01/spfile.ora"
    assert mod.oracle_crs_asm.get_change(change_set, "missing") is None


def test_crs_asm_get_crs_config_rc_error(monkeypatch):
    """get_crs_config: crsctl returns rc != 0 → fail_json (lines 129-132)."""
    mod = _load("oracle_crs_asm")
    responses = [
        (1, "", "crsctl error"),   # crsctl stat res → failure
    ]
    Mod = _make_mod(_asm_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_crs_asm_get_crs_config_name_without_ora_prefix(monkeypatch):
    """get_crs_config: NAME not starting with 'ora.' uses alternate branch (line 146)."""
    mod = _load("oracle_crs_asm")
    # Build output where NAME does NOT start with 'ora.'
    raw_out = "NAME=asm.asm\nTYPE=ora.asm.type\nORACLE_HOME=/u01/grid\n\n"
    responses = [
        (0, raw_out, ""),                          # crsctl stat res → custom name
        (0, "ASM is running on myhost.", ""),      # srvctl status asm
    ]
    Mod = _make_mod(_asm_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_crs_asm_configure_with_listener_param(monkeypatch):
    """configure_asm: listener param is set → included in wanted_set (line 161)."""
    mod = _load("oracle_crs_asm")
    # ASM not registered → add; also spfile differs so modify gets the listener change
    responses = [
        (0, "", ""),                          # crsctl stat res → not found
        (0, "", ""),                          # srvctl add asm (with params)
        (0, "ASM is running on myhost.", ""), # srvctl status asm
    ]
    Mod = _make_mod(_asm_params(listener="LISTENER"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_crs_asm_configure_with_spfile_change(monkeypatch):
    """configure_asm existing ASM: spfile differs → srvctl modify called (lines 188-190)."""
    mod = _load("oracle_crs_asm")
    asm_out = _crsctl_output("asm", "asm", {"SPFILE": "/old/spfile.ora"})
    responses = [
        (0, asm_out, ""),                          # crsctl stat res → found with old spfile
        (0, "", ""),                               # srvctl modify asm -spfile /new/spfile.ora
        (0, "ASM is running on myhost.", ""),      # srvctl status asm
    ]
    Mod = _make_mod(_asm_params(spfile="/new/spfile.ora"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("modify" in c for c in exc.value.args[0]["commands"])


def test_crs_asm_ensure_state_enable(monkeypatch):
    """ensure_asm_state: ENABLED=0 but enabled=True → srvctl enable asm (lines 202-203)."""
    mod = _load("oracle_crs_asm")
    asm_out = _crsctl_output("asm", "asm", {"ENABLED": "0"})
    responses = [
        (0, asm_out, ""),                          # crsctl stat res → found, disabled
        (0, "", ""),                               # srvctl enable asm
        (0, "ASM is running on myhost.", ""),      # srvctl status asm
    ]
    Mod = _make_mod(_asm_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("enable" in c for c in exc.value.args[0]["commands"])


def test_crs_asm_ensure_state_disable(monkeypatch):
    """ensure_asm_state: ENABLED=1 but enabled=False → srvctl disable asm (lines 206-207)."""
    mod = _load("oracle_crs_asm")
    asm_out = _crsctl_output("asm", "asm", {"ENABLED": "1"})
    responses = [
        (0, asm_out, ""),                          # crsctl stat res → found, enabled
        (0, "", ""),                               # srvctl disable asm
        (0, "ASM is running on myhost.", ""),      # srvctl status asm
    ]
    Mod = _make_mod(_asm_params(enabled=False), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("disable" in c for c in exc.value.args[0]["commands"])


def test_crs_asm_ensure_state_running_unknown_fails(monkeypatch):
    """ensure_asm_state: status output has no running/not-running line → fail_json (lines 218-221)."""
    mod = _load("oracle_crs_asm")
    asm_out = _crsctl_output("asm", "asm")
    responses = [
        (0, asm_out, ""),              # crsctl stat res → found
        (0, "Unknown status.", ""),    # srvctl status asm → no parseable output
    ]
    Mod = _make_mod(_asm_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_crs_asm_state_stopped_running(monkeypatch):
    """ensure_asm_state: state=stopped, ASM running → srvctl stop asm (lines 225-228)."""
    mod = _load("oracle_crs_asm")
    asm_out = _crsctl_output("asm", "asm")
    responses = [
        (0, asm_out, ""),                      # crsctl stat res → found
        (0, "ASM is running on myhost.", ""),  # srvctl status asm → running
        (0, "", ""),                           # srvctl stop asm
    ]
    Mod = _make_mod(_asm_params(state="stopped"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("stop" in c for c in exc.value.args[0]["commands"])


def test_crs_asm_state_stopped_force(monkeypatch):
    """ensure_asm_state: state=stopped with force=True → -force appended (lines 226-228)."""
    mod = _load("oracle_crs_asm")
    asm_out = _crsctl_output("asm", "asm")
    responses = [
        (0, asm_out, ""),                      # crsctl stat res → found
        (0, "ASM is running on myhost.", ""),  # srvctl status asm → running
        (0, "", ""),                           # srvctl stop asm -force
    ]
    Mod = _make_mod(_asm_params(state="stopped", force=True), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("-force" in c for c in exc.value.args[0]["commands"])


def test_crs_asm_state_started_not_running(monkeypatch):
    """ensure_asm_state: state=started, ASM not running → srvctl start asm (lines 231-232)."""
    mod = _load("oracle_crs_asm")
    asm_out = _crsctl_output("asm", "asm")
    responses = [
        (0, asm_out, ""),                          # crsctl stat res → found
        (0, "ASM is not running on myhost.", ""),  # srvctl status asm → not running
        (0, "", ""),                               # srvctl start asm
    ]
    Mod = _make_mod(_asm_params(state="started"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("start" in c for c in exc.value.args[0]["commands"])


def test_crs_asm_state_restarted_running(monkeypatch):
    """ensure_asm_state: state=restarted, running → stop then start (lines 234-241)."""
    mod = _load("oracle_crs_asm")
    asm_out = _crsctl_output("asm", "asm")
    responses = [
        (0, asm_out, ""),                      # crsctl stat res → found
        (0, "ASM is running on myhost.", ""),  # srvctl status asm → running
        (0, "", ""),                           # srvctl stop asm
        (0, "", ""),                           # srvctl start asm
    ]
    Mod = _make_mod(_asm_params(state="restarted"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("stop" in c for c in result["commands"])
    assert any("start" in c for c in result["commands"])


def test_crs_asm_state_restarted_not_running(monkeypatch):
    """ensure_asm_state: state=restarted, not running → only start (lines 234-241)."""
    mod = _load("oracle_crs_asm")
    asm_out = _crsctl_output("asm", "asm")
    responses = [
        (0, asm_out, ""),                          # crsctl stat res → found
        (0, "ASM is not running on myhost.", ""),  # srvctl status asm → not running
        (0, "", ""),                               # srvctl start asm
    ]
    Mod = _make_mod(_asm_params(state="restarted"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("start" in c for c in result["commands"])
    assert not any("stop" in c for c in result["commands"])


def test_crs_asm_state_restarted_force(monkeypatch):
    """ensure_asm_state: state=restarted with force=True, running → stop -force then start."""
    mod = _load("oracle_crs_asm")
    asm_out = _crsctl_output("asm", "asm")
    responses = [
        (0, asm_out, ""),                      # crsctl stat res → found
        (0, "ASM is running on myhost.", ""),  # srvctl status asm → running
        (0, "", ""),                           # srvctl stop asm -force
        (0, "", ""),                           # srvctl start asm
    ]
    Mod = _make_mod(_asm_params(state="restarted", force=True), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("-force" in c for c in result["commands"])
    assert any("start" in c for c in result["commands"])


# ===========================================================================
# oracle_crs_db – additional coverage tests
# ===========================================================================

def test_crs_db_get_change_static():
    """get_change static method: found and not-found cases (lines 139-142)."""
    mod = _load("oracle_crs_db")
    change_set = [("oraclehome", "/u01/oracle"), ("domain", "example.com")]
    assert mod.oracle_crs_db.get_change(change_set, "oraclehome") == "/u01/oracle"
    assert mod.oracle_crs_db.get_change(change_set, "missing") is None


def test_crs_db_get_crs_config_rc_error(monkeypatch):
    """get_crs_config: crsctl returns error → fail_json (lines 161-164)."""
    mod = _load("oracle_crs_db")
    responses = [
        (1, "", "crsctl error"),   # crsctl stat res → failure
    ]
    Mod = _make_mod(_crsdb_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_crs_db_get_crs_config_name_without_ora_prefix(monkeypatch):
    """get_crs_config: NAME not starting with 'ora.' uses alternate branch (line 178)."""
    mod = _load("oracle_crs_db")
    raw_out = "NAME=mydb.db\nTYPE=ora.database.type\nORACLE_HOME=/u01/oracle\n\n"
    responses = [
        (0, raw_out, ""),                          # crsctl stat res
        (0, "Database is running.", ""),           # srvctl status database
    ]
    Mod = _make_mod(_crsdb_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_crs_db_absent_existing_force(monkeypatch):
    """configure_db: state=absent, existing, force=True → -force appended (line 220)."""
    mod = _load("oracle_crs_db")
    db_out = _crsctl_output("database", "mydb", {"ORACLE_HOME": "/u01/oracle"})
    responses = [
        (0, db_out, ""),   # crsctl stat res → found
    ]
    Mod = _make_mod(_crsdb_params(state="absent", force=True), responses, check_mode=True)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("-force" in c for c in exc.value.args[0]["commands"])


def test_crs_db_rac_add_instances(monkeypatch):
    """configure_db: oracle_crs=True, new DB → olsnodes called, instances added (lines 239-246)."""
    mod = _load("oracle_crs_db")

    class _RacHomes(FakeOracleHomes):
        def __init__(self):
            super().__init__()
            self.oracle_crs = True  # RAC mode

    responses = [
        (0, "", ""),                              # crsctl stat res → not found
        (0, "", ""),                              # srvctl add database
        (0, "node1\nnode2", ""),                  # olsnodes
        (0, "", ""),                              # srvctl add instance node1
        (0, "", ""),                              # srvctl add instance node2
        (0, "Database is not running.", ""),      # srvctl status database
    ]
    Mod = _make_mod(_crsdb_params(dbname="MYDB"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _RacHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("instance" in c for c in result["commands"])


def test_crs_db_rac_olsnodes_failure(monkeypatch):
    """configure_db: oracle_crs=True, olsnodes fails → fail_json (lines 240-241)."""
    mod = _load("oracle_crs_db")

    class _RacHomes(FakeOracleHomes):
        def __init__(self):
            super().__init__()
            self.oracle_crs = True

    responses = [
        (0, "", ""),              # crsctl stat res → not found
        (0, "", ""),              # srvctl add database
        (1, "", "olsnodes err"),  # olsnodes fails
    ]
    Mod = _make_mod(_crsdb_params(dbname="MYDB"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _RacHomes, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_crs_db_ensure_state_enable(monkeypatch):
    """ensure_db_state: ENABLED=0 but enabled=True → srvctl enable database (lines 256-257)."""
    mod = _load("oracle_crs_db")
    db_out = _crsctl_output("database", "mydb", {"ORACLE_HOME": "/u01/oracle", "ENABLED": "0"})
    responses = [
        (0, db_out, ""),                      # crsctl stat res → found, disabled
        (0, "", ""),                          # srvctl enable database
        (0, "Database is running.", ""),      # srvctl status database
    ]
    Mod = _make_mod(_crsdb_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("enable" in c for c in exc.value.args[0]["commands"])


def test_crs_db_ensure_state_disable(monkeypatch):
    """ensure_db_state: ENABLED=1 but enabled=False → srvctl disable database (lines 260-261)."""
    mod = _load("oracle_crs_db")
    db_out = _crsctl_output("database", "mydb", {"ORACLE_HOME": "/u01/oracle", "ENABLED": "1"})
    responses = [
        (0, db_out, ""),                      # crsctl stat res → found, enabled
        (0, "", ""),                          # srvctl disable database
        (0, "Database is running.", ""),      # srvctl status database
    ]
    Mod = _make_mod(_crsdb_params(enabled=False), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("disable" in c for c in exc.value.args[0]["commands"])


def test_crs_db_state_stopped_running(monkeypatch):
    """ensure_db_state: state=stopped, DB running → srvctl stop database (lines 279-280)."""
    mod = _load("oracle_crs_db")
    db_out = _crsctl_output("database", "mydb", {"ORACLE_HOME": "/u01/oracle"})
    responses = [
        (0, db_out, ""),                      # crsctl stat res → found
        (0, "Database is running.", ""),      # srvctl status database → running
        (0, "", ""),                          # srvctl stop database
    ]
    Mod = _make_mod(_crsdb_params(state="stopped"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("stop" in c for c in exc.value.args[0]["commands"])


def test_crs_db_state_started_not_running(monkeypatch):
    """ensure_db_state: state=started, DB not running → srvctl start database (lines 283-284)."""
    mod = _load("oracle_crs_db")
    db_out = _crsctl_output("database", "mydb", {"ORACLE_HOME": "/u01/oracle"})
    responses = [
        (0, db_out, ""),                          # crsctl stat res → found
        (0, "Database is not running.", ""),      # srvctl status database → not running
        (0, "", ""),                              # srvctl start database
    ]
    Mod = _make_mod(_crsdb_params(state="started"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("start" in c for c in exc.value.args[0]["commands"])


def test_crs_db_state_restarted_running(monkeypatch):
    """ensure_db_state: state=restarted, running → stop then start (lines 287-291)."""
    mod = _load("oracle_crs_db")
    db_out = _crsctl_output("database", "mydb", {"ORACLE_HOME": "/u01/oracle"})
    responses = [
        (0, db_out, ""),                      # crsctl stat res → found
        (0, "Database is running.", ""),      # srvctl status database → running
        (0, "", ""),                          # srvctl stop database
        (0, "", ""),                          # srvctl start database
    ]
    Mod = _make_mod(_crsdb_params(state="restarted"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("stop" in c for c in result["commands"])
    assert any("start" in c for c in result["commands"])


def test_crs_db_state_restarted_not_running(monkeypatch):
    """ensure_db_state: state=restarted, not running → only start (lines 287-291)."""
    mod = _load("oracle_crs_db")
    db_out = _crsctl_output("database", "mydb", {"ORACLE_HOME": "/u01/oracle"})
    responses = [
        (0, db_out, ""),                          # crsctl stat res → found
        (0, "Database is not running.", ""),      # srvctl status database → not running
        (0, "", ""),                              # srvctl start database
    ]
    Mod = _make_mod(_crsdb_params(state="restarted"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("start" in c for c in result["commands"])
    assert not any("stop" in c for c in result["commands"])


# ===========================================================================
# oracle_crs_listener – additional coverage tests
# ===========================================================================

def test_crs_listener_run_change_command_failure(monkeypatch):
    """run_change_command: non-zero rc → fail_json with warnings (lines 93-104)."""
    mod = _load("oracle_crs_listener")
    responses = [
        (0, "", ""),             # crsctl stat res → not found
        (1, "out", "err"),       # srvctl add listener → failure
    ]
    Mod = _make_mod(_listener_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_crs_listener_run_change_command_stderr_only(monkeypatch):
    """run_change_command: rc=0 but stderr set → fail_json (lines 94-104)."""
    mod = _load("oracle_crs_listener")
    responses = [
        (0, "", ""),              # crsctl stat res → not found
        (0, "", "some error"),    # srvctl add listener → stderr only
    ]
    Mod = _make_mod(_listener_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_crs_listener_get_change_static():
    """get_change static method: found and not-found cases (lines 109-112)."""
    mod = _load("oracle_crs_listener")
    change_set = [("oraclehome", "/u01/grid"), ("endpoints", "TCP:1521")]
    assert mod.oracle_crs_listener.get_change(change_set, "endpoints") == "TCP:1521"
    assert mod.oracle_crs_listener.get_change(change_set, "missing") is None


def test_crs_listener_get_crs_config_rc_error(monkeypatch):
    """get_crs_config: crsctl returns error → fail_json (lines 131-134)."""
    mod = _load("oracle_crs_listener")
    responses = [
        (1, "", "crsctl error"),   # crsctl stat res → failure
    ]
    Mod = _make_mod(_listener_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_crs_listener_get_crs_config_name_without_ora_prefix(monkeypatch):
    """get_crs_config: NAME not starting with 'ora.' (line 148)."""
    mod = _load("oracle_crs_listener")
    raw_out = "NAME=listener.lsnr\nTYPE=ora.listener.type\nORACLE_HOME=%CRS_HOME%\nENDPOINTS=TCP:1521\n\n"
    responses = [
        (0, raw_out, ""),                          # crsctl stat res
        (0, "Listener is running.", ""),           # srvctl status listener
    ]
    Mod = _make_mod(_listener_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_crs_listener_add_with_skip(monkeypatch):
    """configure_listener: skip=True → -skip appended to srvctl add (line 175)."""
    mod = _load("oracle_crs_listener")
    responses = [
        (0, "", ""),   # crsctl stat res → not found
    ]
    Mod = _make_mod(_listener_params(skip=True), responses, check_mode=True)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("-skip" in c for c in exc.value.args[0]["commands"])


def test_crs_listener_ensure_state_enable(monkeypatch):
    """ensure_listener_state: ENABLED=0, enabled=True → srvctl enable listener (lines 209-210)."""
    mod = _load("oracle_crs_listener")
    lsnr_out = _crsctl_output("listener", "listener", {"ORACLE_HOME": "%CRS_HOME%", "ENABLED": "0"})
    responses = [
        (0, lsnr_out, ""),                        # crsctl stat res → found, disabled
        (0, "", ""),                              # srvctl enable listener
        (0, "Listener is running.", ""),          # srvctl status listener
    ]
    Mod = _make_mod(_listener_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("enable" in c for c in exc.value.args[0]["commands"])


def test_crs_listener_ensure_state_disable(monkeypatch):
    """ensure_listener_state: ENABLED=1, enabled=False → srvctl disable listener (lines 213-214)."""
    mod = _load("oracle_crs_listener")
    lsnr_out = _crsctl_output("listener", "listener", {"ORACLE_HOME": "%CRS_HOME%", "ENABLED": "1"})
    responses = [
        (0, lsnr_out, ""),                        # crsctl stat res → found, enabled
        (0, "", ""),                              # srvctl disable listener
        (0, "Listener is running.", ""),          # srvctl status listener
    ]
    Mod = _make_mod(_listener_params(enabled=False), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("disable" in c for c in exc.value.args[0]["commands"])


def test_crs_listener_ensure_state_running_unknown_fails(monkeypatch):
    """ensure_listener_state: unparseable status → fail_json (lines 225-228)."""
    mod = _load("oracle_crs_listener")
    lsnr_out = _crsctl_output("listener", "listener", {"ORACLE_HOME": "%CRS_HOME%"})
    responses = [
        (0, lsnr_out, ""),               # crsctl stat res → found
        (0, "Unknown status.", ""),      # srvctl status listener → no parse match
    ]
    Mod = _make_mod(_listener_params(), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_crs_listener_state_stopped_running(monkeypatch):
    """ensure_listener_state: state=stopped, listener running → srvctl stop (lines 232-233)."""
    mod = _load("oracle_crs_listener")
    lsnr_out = _crsctl_output("listener", "listener", {"ORACLE_HOME": "%CRS_HOME%"})
    responses = [
        (0, lsnr_out, ""),                        # crsctl stat res → found
        (0, "Listener is running.", ""),          # srvctl status listener → running
        (0, "", ""),                              # srvctl stop listener
    ]
    Mod = _make_mod(_listener_params(state="stopped"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("stop" in c for c in exc.value.args[0]["commands"])


def test_crs_listener_state_started_not_running(monkeypatch):
    """ensure_listener_state: state=started, not running → srvctl start (lines 236-237)."""
    mod = _load("oracle_crs_listener")
    lsnr_out = _crsctl_output("listener", "listener", {"ORACLE_HOME": "%CRS_HOME%"})
    responses = [
        (0, lsnr_out, ""),                            # crsctl stat res → found
        (0, "Listener is not running.", ""),          # srvctl status listener → not running
        (0, "", ""),                                  # srvctl start listener
    ]
    Mod = _make_mod(_listener_params(state="started"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("start" in c for c in exc.value.args[0]["commands"])


def test_crs_listener_state_restarted_running(monkeypatch):
    """ensure_listener_state: state=restarted, running → stop then start (lines 240-244)."""
    mod = _load("oracle_crs_listener")
    lsnr_out = _crsctl_output("listener", "listener", {"ORACLE_HOME": "%CRS_HOME%"})
    responses = [
        (0, lsnr_out, ""),                        # crsctl stat res → found
        (0, "Listener is running.", ""),          # srvctl status listener → running
        (0, "", ""),                              # srvctl stop listener
        (0, "", ""),                              # srvctl start listener
    ]
    Mod = _make_mod(_listener_params(state="restarted"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("stop" in c for c in result["commands"])
    assert any("start" in c for c in result["commands"])


def test_crs_listener_state_restarted_not_running(monkeypatch):
    """ensure_listener_state: state=restarted, not running → only start (lines 240-244)."""
    mod = _load("oracle_crs_listener")
    lsnr_out = _crsctl_output("listener", "listener", {"ORACLE_HOME": "%CRS_HOME%"})
    responses = [
        (0, lsnr_out, ""),                            # crsctl stat res → found
        (0, "Listener is not running.", ""),          # srvctl status listener → not running
        (0, "", ""),                                  # srvctl start listener
    ]
    Mod = _make_mod(_listener_params(state="restarted"), responses)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", FakeOracleHomes, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("start" in c for c in result["commands"])
    assert not any("stop" in c for c in result["commands"])


def test_crs_listener_gi_not_detected_fails(monkeypatch):
    """oracle_gi_managed=False → fail_json (line 267)."""
    mod = _load("oracle_crs_listener")

    class _NoGi(FakeOracleHomes):
        oracle_gi_managed = False

    Mod = _make_mod(_listener_params(), [])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _NoGi, raising=False)

    with pytest.raises(FailJson):
        mod.main()
