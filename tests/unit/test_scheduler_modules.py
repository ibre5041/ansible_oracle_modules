"""Unit tests for DBMS_SCHEDULER modules (oracle_jobclass, oracle_jobschedule,
oracle_jobwindow, oracle_rsrc_consgroup).

These modules call oracleConnection(module) from oracle_utils and use
cursor.rowcount, so we mock oracleConnection with a factory that controls
_fetchone_row.
"""
import pytest
from datetime import timedelta

from conftest import ExitJson, FailJson, load_module_from_path
from helpers import BASE_CONN_PARAMS, BaseFakeModule, FakeOracleConn, FakeOracleDb


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load(name):
    return load_module_from_path(f"plugins/modules/{name}.py", name)


_SCHED_CONN_BASE = dict(
    hostname="localhost",
    port=1521,
    service_name="svc",
    user="u",
    password="p",
    mode="normal",
    oracle_home=None,
    dsn=None,
    session_container=None,
)


def _make_fake_db(fetchone_row=None):
    """Return (FakeOracleConnection class, FakeOracleConn instance)."""
    _conn = FakeOracleConn()
    _conn._fetchone_row = fetchone_row

    class _FakeOC:
        def __init__(self, module):
            self.conn = _conn
            self.version = _conn.version

    return _FakeOC, _conn


# ===========================================================================
# oracle_jobclass
# ===========================================================================

def _jc_params(**overrides):
    base = {
        **_SCHED_CONN_BASE,
        "state": "present",
        "name": "TESTCLASS",
        "resource_group": None,
        "service": None,
        "logging": "failed runs",
        "history": None,
        "comments": None,
    }
    base.update(overrides)
    return base


def test_jobclass_creates_new(monkeypatch):
    """state=present, class doesn't exist → creates it."""
    mod = _load("oracle_jobclass")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _jc_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is True


def test_jobclass_no_change_when_same(monkeypatch):
    """state=present, class already exists with same attrs → no change."""
    mod = _load("oracle_jobclass")
    existing_row = (None, None, "FAILED RUNS", None, None)   # resource_group,service,logging,history,comments
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _jc_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_jobclass_absent_drops(monkeypatch):
    """state=absent, class exists → drops it."""
    mod = _load("oracle_jobclass")
    existing_row = (None, None, "FAILED_RUNS", None, None)
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _jc_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobclass_absent_missing_no_change(monkeypatch):
    """state=absent, class doesn't exist → no change."""
    mod = _load("oracle_jobclass")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _jc_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_jobclass_check_mode(monkeypatch):
    """check_mode=True → reports would_change but doesn't change."""
    mod = _load("oracle_jobclass")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _jc_params()
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobclass_modifies_existing_attributes(monkeypatch):
    """Existing class with different comments → modify path, changed=True."""
    mod = _load("oracle_jobclass")
    # resource_group, service, logging, history, comments
    existing_row = (None, None, "FAILED RUNS", None, "old comment")
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _jc_params(comments="new comment")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobclass_check_mode_existing_change(monkeypatch):
    """check_mode, existing class with different comments → would_change=True."""
    mod = _load("oracle_jobclass")
    existing_row = (None, None, "FAILED RUNS", None, "old comment")
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _jc_params(comments="new comment")
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobclass_wallet_connect(monkeypatch):
    """No user/password → wallet connect path used (normal mode)."""
    mod = _load("oracle_jobclass")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _jc_params(user=None, password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobclass_sysdba_connect(monkeypatch):
    """user+password with mode=sysdba → sysdba connect path."""
    mod = _load("oracle_jobclass")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _jc_params(mode="sysdba")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobclass_connect_error(monkeypatch):
    """Connection error → fail_json."""
    mod = _load("oracle_jobclass")

    class _ErrorOC:
        def __init__(self, module):
            module.fail_json(msg="Could not connect to database - ORA-12541: no listener")

    class Mod(BaseFakeModule):
        params = _jc_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _ErrorOC)

    with pytest.raises(FailJson):
        mod.main()


# ===========================================================================
# oracle_jobschedule
# ===========================================================================

def _js_params(**overrides):
    base = {
        **_SCHED_CONN_BASE,
        "state": "present",
        "name": "SYS.TESTSCHEDULE",
        "repeat_interval": "FREQ=DAILY",
        "comments": None,
        "convert_to_upper": True,
    }
    base.update(overrides)
    return base


def test_jobschedule_creates_new(monkeypatch):
    mod = _load("oracle_jobschedule")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _js_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobschedule_no_change_when_same(monkeypatch):
    """Existing schedule with same interval → no change."""
    mod = _load("oracle_jobschedule")
    existing_row = ("FREQ=DAILY", None)   # repeat_interval, comments
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _js_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_jobschedule_absent_drops(monkeypatch):
    mod = _load("oracle_jobschedule")
    existing_row = ("FREQ=DAILY", None)
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _js_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobschedule_absent_missing_no_change(monkeypatch):
    mod = _load("oracle_jobschedule")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _js_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_jobschedule_invalid_name_fails(monkeypatch):
    """Name without owner.name format → fail_json."""
    mod = _load("oracle_jobschedule")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _js_params(name="BADNAME")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(FailJson):
        mod.main()


def test_jobschedule_modifies_existing(monkeypatch):
    """Existing schedule with different repeat_interval → modify path, changed=True."""
    mod = _load("oracle_jobschedule")
    existing_row = ("FREQ=WEEKLY", None)   # different repeat_interval
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _js_params()   # wants FREQ=DAILY

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobschedule_check_mode_would_change(monkeypatch):
    """check_mode, existing schedule with different interval → would_change=True."""
    mod = _load("oracle_jobschedule")
    existing_row = ("FREQ=WEEKLY", None)
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _js_params()   # wants FREQ=DAILY
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobschedule_check_mode_no_change(monkeypatch):
    """check_mode, existing schedule with same interval → would_change=False."""
    mod = _load("oracle_jobschedule")
    existing_row = ("FREQ=DAILY", None)
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _js_params()
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_jobschedule_wallet_connect(monkeypatch):
    """No user/password → wallet connect path (normal mode)."""
    mod = _load("oracle_jobschedule")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _js_params(user=None, password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobschedule_sysdba_connect(monkeypatch):
    """user+password with mode=sysdba → sysdba connect path."""
    mod = _load("oracle_jobschedule")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _js_params(mode="sysdba")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobschedule_connect_error(monkeypatch):
    """Connection error → fail_json."""
    mod = _load("oracle_jobschedule")

    class _ErrorOC:
        def __init__(self, module):
            module.fail_json(msg="Could not connect to database - ORA-12541: no listener")

    class Mod(BaseFakeModule):
        params = _js_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _ErrorOC)

    with pytest.raises(FailJson):
        mod.main()


# ===========================================================================
# oracle_jobwindow
# ===========================================================================

def _jw_params(**overrides):
    base = {
        **_SCHED_CONN_BASE,
        "state": "enabled",
        "name": "TESTWINDOW",
        "resource_plan": "DEFAULT_PLAN",
        "duration_min": 60,
        "duration_hour": None,
        "window_priority": "low",
        "repeat_interval": "FREQ=DAILY;BYHOUR=22",
        "comments": None,
    }
    base.update(overrides)
    return base


def test_jobwindow_creates_new(monkeypatch):
    mod = _load("oracle_jobwindow")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _jw_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobwindow_no_change(monkeypatch):
    """Existing window already matching → no change."""
    mod = _load("oracle_jobwindow")
    # resource_plan, duration, window_priority, enabled, repeat_interval, comments
    existing_row = ("DEFAULT_PLAN", timedelta(minutes=60), "LOW", "TRUE", "FREQ=DAILY;BYHOUR=22", None)
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _jw_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_jobwindow_absent_drops(monkeypatch):
    mod = _load("oracle_jobwindow")
    existing_row = ("DEFAULT_PLAN", timedelta(minutes=60), "LOW", "TRUE", "FREQ=DAILY;BYHOUR=22", None)
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _jw_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobwindow_absent_missing_no_change(monkeypatch):
    mod = _load("oracle_jobwindow")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _jw_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_jobwindow_zero_duration_fails(monkeypatch):
    """duration_hour=0 → new_duration_min=0 → fail_json (< 1)."""
    mod = _load("oracle_jobwindow")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _jw_params(duration_min=None, duration_hour=0)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "duration" in exc.value.args[0]["msg"].lower()


def test_jobwindow_check_mode_would_change(monkeypatch):
    """check_mode, existing window with different repeat_interval → would_change=True."""
    mod = _load("oracle_jobwindow")
    # resource_plan, duration, window_priority, enabled, repeat_interval, comments
    existing_row = ("DEFAULT_PLAN", timedelta(minutes=60), "LOW", "TRUE", "FREQ=WEEKLY", None)
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _jw_params()   # wants FREQ=DAILY;BYHOUR=22
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobwindow_check_mode_no_change(monkeypatch):
    """check_mode, existing window that matches → would_change=False."""
    mod = _load("oracle_jobwindow")
    existing_row = ("DEFAULT_PLAN", timedelta(minutes=60), "LOW", "TRUE", "FREQ=DAILY;BYHOUR=22", None)
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _jw_params()
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_jobwindow_modifies_existing_attributes(monkeypatch):
    """Existing window with different repeat_interval → modify path, changed=True."""
    mod = _load("oracle_jobwindow")
    existing_row = ("DEFAULT_PLAN", timedelta(minutes=60), "LOW", "TRUE", "FREQ=WEEKLY", None)
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _jw_params()   # wants FREQ=DAILY;BYHOUR=22

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobwindow_disables_existing(monkeypatch):
    """Existing enabled window → state=disabled → disable path, changed=True."""
    mod = _load("oracle_jobwindow")
    # Window is enabled (TRUE), all attributes match, but state=disabled desired
    existing_row = ("DEFAULT_PLAN", timedelta(minutes=60), "LOW", "TRUE", "FREQ=DAILY;BYHOUR=22", None)
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _jw_params(state="disabled")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobwindow_enables_existing(monkeypatch):
    """Existing disabled window → state=enabled → enable path, changed=True."""
    mod = _load("oracle_jobwindow")
    # Window is disabled (FALSE), all attributes match, but state=enabled desired
    existing_row = ("DEFAULT_PLAN", timedelta(minutes=60), "LOW", "FALSE", "FREQ=DAILY;BYHOUR=22", None)
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _jw_params(state="enabled")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobwindow_wallet_connect(monkeypatch):
    """No user/password → wallet connect path (normal mode)."""
    mod = _load("oracle_jobwindow")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _jw_params(user=None, password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobwindow_sysdba_connect(monkeypatch):
    """user+password with mode=sysdba → sysdba connect path."""
    mod = _load("oracle_jobwindow")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _jw_params(mode="sysdba")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_jobwindow_connect_error(monkeypatch):
    """Connection error → fail_json."""
    mod = _load("oracle_jobwindow")

    class _ErrorOC:
        def __init__(self, module):
            module.fail_json(msg="Could not connect to database - ORA-12541: no listener")

    class Mod(BaseFakeModule):
        params = _jw_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _ErrorOC)

    with pytest.raises(FailJson):
        mod.main()


def test_jobwindow_no_duration_fails(monkeypatch):
    """Neither duration_min nor duration_hour → fail_json."""
    mod = _load("oracle_jobwindow")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _jw_params(duration_min=None, duration_hour=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "duration" in exc.value.args[0]["msg"].lower()


# ===========================================================================
# oracle_rsrc_consgroup
# ===========================================================================

def _rg_params(**overrides):
    base = {
        **_SCHED_CONN_BASE,
        "state": "present",
        "name": "TESTGROUP",
        "mgmt_mth": "round-robin",
        "category": "other",
        "comments": None,
        "grant_name": None,
        "grant_user_profile": None,
        # map_* params
        "map_client_id": None,
        "map_client_machine": None,
        "map_client_os_user": None,
        "map_client_program": None,
        "map_module_name": None,
        "map_module_name_action": None,
        "map_oracle_function": None,
        "map_oracle_user": None,
        "map_oracle_user_profile": None,
        "map_service_module": None,
        "map_service_module_action": None,
        "map_service_name": None,
    }
    base.update(overrides)
    return base


def test_rsrc_consgroup_creates_new(monkeypatch):
    mod = _load("oracle_rsrc_consgroup")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _rg_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_absent_missing_no_change(monkeypatch):
    mod = _load("oracle_rsrc_consgroup")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _rg_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_rsrc_consgroup_absent_drops(monkeypatch):
    mod = _load("oracle_rsrc_consgroup")
    existing_row = ("ROUND-ROBIN", None, "OTHER")   # mgmt_method, comments, category
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _rg_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_check_mode(monkeypatch):
    """check_mode for new group → changed=True."""
    mod = _load("oracle_rsrc_consgroup")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _rg_params()
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_modifies_existing(monkeypatch):
    """Existing group with different comments → modify path executed."""
    mod = _load("oracle_rsrc_consgroup")
    existing_row = ("ROUND-ROBIN", "Old comment", "OTHER")
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _rg_params(comments="New comment")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_no_change_when_identical(monkeypatch):
    """Existing group with matching attributes → no change."""
    mod = _load("oracle_rsrc_consgroup")
    existing_row = ("ROUND-ROBIN", None, "OTHER")
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _rg_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_rsrc_consgroup_creates_with_grant_name(monkeypatch):
    """Create new group with grant_name → new_grants_list queries dba_users."""
    from helpers import SequencedFakeOracleConn
    mod = _load("oracle_rsrc_consgroup")

    seq_conn = SequencedFakeOracleConn(fetchall_sequence=[
        [],   # grants query (no existing grants for new group) — rowcount=0 path
        [],   # mappings query
        [("APPUSER",)],  # new_grants_list: SELECT username FROM dba_users/dba_roles
    ])

    class _FakeOC:
        def __init__(self, module):
            self.conn = seq_conn
            self.version = seq_conn.version

    class Mod(BaseFakeModule):
        params = _rg_params(grant_name=["APPUSER"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_check_mode_existing_no_change(monkeypatch):
    """check_mode for existing identical group → changed=False."""
    mod = _load("oracle_rsrc_consgroup")
    existing_row = ("ROUND-ROBIN", None, "OTHER")
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _rg_params()
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_rsrc_consgroup_oracledb_missing_fails(monkeypatch):
    """oracledb not installed → fail_json immediately."""
    mod = _load("oracle_rsrc_consgroup")

    class Mod(BaseFakeModule):
        params = _rg_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracledb_exists", False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "oracledb" in exc.value.args[0]["msg"].lower()


def test_rsrc_consgroup_wallet_sysdba_connect(monkeypatch):
    """No user/password, mode=sysdba → wallet+sysdba connect path."""
    mod = _load("oracle_rsrc_consgroup")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _rg_params(user=None, password=None, mode="sysdba")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_wallet_normal_connect(monkeypatch):
    """No user/password, mode=normal → wallet+normal connect path."""
    mod = _load("oracle_rsrc_consgroup")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _rg_params(user=None, password=None, mode="normal")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_check_mode_absent_existing(monkeypatch):
    """check_mode + state=absent + group exists → changed=True."""
    mod = _load("oracle_rsrc_consgroup")
    existing_row = ("ROUND-ROBIN", None, "OTHER")
    FakeOC, conn = _make_fake_db(fetchone_row=existing_row)

    class Mod(BaseFakeModule):
        params = _rg_params(state="absent")
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_check_mode_present_grant_diff(monkeypatch):
    """check_mode + existing group + grants differ → would_change=True."""
    from helpers import SequencedFakeOracleConn
    mod = _load("oracle_rsrc_consgroup")

    # _SeqFakeCursor.fetchone() pops from _fetchall_seq when non-empty.
    # rowcount is driven by _fetchone_row (must be non-None for exists=True).
    # Sequence: fetchone(SELECT mgmt..), fetchall(grants), fetchall(mappings),
    #           fetchall(new_grants_list dba_users/roles)
    _existing = ("ROUND-ROBIN", None, "OTHER")
    seq_conn = SequencedFakeOracleConn(fetchall_sequence=[
        [_existing],          # fetchone → existing group row
        [("EXISTUSER",)],     # fetchall → existing grants
        [],                   # fetchall → existing mappings
        [("APPUSER",)],       # fetchall → new_grants_list result
    ])
    seq_conn._fetchone_row = _existing  # rowcount > 0

    class _FakeOC:
        def __init__(self, module):
            self.conn = seq_conn
            self.version = seq_conn.version

    class Mod(BaseFakeModule):
        params = _rg_params(grant_name=["APPUSER"])
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_check_mode_present_mapping_diff(monkeypatch):
    """check_mode + existing group + map_oracle_user differs → would_change=True."""
    from helpers import SequencedFakeOracleConn
    mod = _load("oracle_rsrc_consgroup")

    # Existing group: no grants, no mappings. We request a mapping.
    _existing = ("ROUND-ROBIN", None, "OTHER")
    seq_conn = SequencedFakeOracleConn(fetchall_sequence=[
        [_existing],  # fetchone → existing group row
        [],           # fetchall → grants (none)
        [],           # fetchall → mappings (none)
    ])
    seq_conn._fetchone_row = _existing  # rowcount > 0

    class _FakeOC:
        def __init__(self, module):
            self.conn = seq_conn
            self.version = seq_conn.version

    class Mod(BaseFakeModule):
        params = _rg_params(map_oracle_user=["SCOTT"])
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_modify_with_grants_and_mappings(monkeypatch):
    """Existing group, add + remove grants, add + remove mappings → changed=True."""
    from helpers import SequencedFakeOracleConn
    mod = _load("oracle_rsrc_consgroup")

    # query_existing: existing group with EXISTUSER grant and ORACLE_USER:OLDUSER mapping
    # Then new_grants_list returns NEWUSER
    _existing = ("ROUND-ROBIN", None, "OTHER")
    seq_conn = SequencedFakeOracleConn(fetchall_sequence=[
        [_existing],                             # fetchone → existing group row
        [("EXISTUSER",)],                        # fetchall → existing grants
        [("ORACLE_USER", "OLDUSER")],            # fetchall → existing mappings (attr:value)
        [("NEWUSER",)],                          # fetchall → new_grants_list: dba_users/roles
    ])
    seq_conn._fetchone_row = _existing  # rowcount > 0

    class _FakeOC:
        def __init__(self, module):
            self.conn = seq_conn
            self.version = seq_conn.version

    class Mod(BaseFakeModule):
        params = _rg_params(grant_name=["NEWUSER"], map_oracle_user=["NEWMAPPING"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_create_with_mappings(monkeypatch):
    """Create new group with map_service_name → mapping SQL executed."""
    from helpers import SequencedFakeOracleConn
    mod = _load("oracle_rsrc_consgroup")

    # query_existing returns not-found (rowcount=0)
    seq_conn = SequencedFakeOracleConn(fetchall_sequence=[])
    seq_conn._fetchone_row = None  # rowcount=0 → not exists

    class _FakeOC:
        def __init__(self, module):
            self.conn = seq_conn
            self.version = seq_conn.version

    class Mod(BaseFakeModule):
        params = _rg_params(map_service_name=["APP1", "APP2"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_create_with_oracle_user_profile(monkeypatch):
    """Create new group with map_oracle_user_profile → profile_list_to_users called."""
    from helpers import SequencedFakeOracleConn
    mod = _load("oracle_rsrc_consgroup")

    # query_existing: not found, new_mappings_dict calls profile_list_to_users
    seq_conn = SequencedFakeOracleConn(fetchall_sequence=[
        [("PROFUSER",)],  # profile_list_to_users: SELECT username FROM dba_users WHERE profile IN (...)
    ])
    seq_conn._fetchone_row = None  # not exists

    class _FakeOC:
        def __init__(self, module):
            self.conn = seq_conn
            self.version = seq_conn.version

    class Mod(BaseFakeModule):
        params = _rg_params(map_oracle_user_profile=["HR_PROFILE"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_grant_user_profile(monkeypatch):
    """Create new group with grant_user_profile → profile_list_to_users called for grants."""
    from helpers import SequencedFakeOracleConn
    mod = _load("oracle_rsrc_consgroup")

    # grant_user_profile path: new_grants_list calls profile_list_to_users
    seq_conn = SequencedFakeOracleConn(fetchall_sequence=[
        [("PROFUSER",)],  # profile_list_to_users SELECT username FROM dba_users WHERE profile IN ...
    ])
    seq_conn._fetchone_row = None  # not exists

    class _FakeOC:
        def __init__(self, module):
            self.conn = seq_conn
            self.version = seq_conn.version

    class Mod(BaseFakeModule):
        params = _rg_params(grant_user_profile=["HR_PROFILE"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_sysdba_connect(monkeypatch):
    """user+password with mode=sysdba → sysdba connect path."""
    mod = _load("oracle_rsrc_consgroup")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _rg_params(mode="sysdba")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_rsrc_consgroup_missing_password_fails(monkeypatch):
    """Only user provided, no password → fail_json."""
    mod = _load("oracle_rsrc_consgroup")

    class _ErrorOC:
        def __init__(self, module):
            module.fail_json(msg="Missing username or password for oracledb")

    class Mod(BaseFakeModule):
        params = _rg_params(user="u", password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _ErrorOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "missing" in exc.value.args[0]["msg"].lower()


def test_rsrc_consgroup_session_container_applied(monkeypatch):
    """session_container set → ALTER SESSION executed after connect."""
    mod = _load("oracle_rsrc_consgroup")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _rg_params(session_container="MYPDB")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    # ALTER SESSION SET CONTAINER should be in the executed DDLs
    assert any("ALTER SESSION SET CONTAINER" in str(sql) for sql in conn.ddls)


def test_rsrc_consgroup_invalid_session_container_fails(monkeypatch):
    """session_container with invalid name → fail_json."""
    mod = _load("oracle_rsrc_consgroup")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _rg_params(session_container="1INVALID!")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "session_container" in exc.value.args[0]["msg"].lower()


def test_rsrc_consgroup_existing_grants_populated(monkeypatch):
    """query_existing with existing group populates grants and mappings."""
    from helpers import SequencedFakeOracleConn
    mod = _load("oracle_rsrc_consgroup")

    # Existing group with grants and mappings, matching what we request → no change.
    # Mapping row: (attribute, "value1:value2") - the module splits on ":"
    _existing = ("ROUND-ROBIN", None, "OTHER")
    seq_conn = SequencedFakeOracleConn(fetchall_sequence=[
        [_existing],                             # fetchone → existing group row
        [("APPUSER",)],                          # fetchall → existing grants
        [("ORACLE_USER", "APPUSER")],            # fetchall → existing mappings
        [("APPUSER",)],                          # fetchall → new_grants_list result
    ])
    seq_conn._fetchone_row = _existing  # rowcount > 0

    class _FakeOC:
        def __init__(self, module):
            self.conn = seq_conn
            self.version = seq_conn.version

    class Mod(BaseFakeModule):
        params = _rg_params(grant_name=["APPUSER"], map_oracle_user=["APPUSER"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    # Both grants and mappings match → no change
    assert exc.value.args[0]["changed"] is False


# ===========================================================================
# oracle_job
# ===========================================================================

_JOB_CONN_BASE = dict(
    hostname="localhost",
    port=1521,
    service_name="svc",
    user="u",
    password="p",
    mode="normal",
    oracle_home=None,
    dsn=None,
    session_container=None,
)


def _job_params(**overrides):
    base = {
        **_JOB_CONN_BASE,
        "state": "present",
        "enabled": True,
        "job_name": "SYS.TESTJOB",
        "job_class": "DEFAULT_JOB_CLASS",
        "job_type": "plsql_block",
        "job_action": "BEGIN NULL; END;",
        "job_arguments": None,
        "lightweight": False,
        "credential": None,
        "destination": None,
        "restartable": False,
        "repeat_interval": None,
        "logging_level": None,
        "program_name": None,
        "schedule_name": None,
        "comments": None,
        "auto_drop": False,
        "convert_to_upper": True,
    }
    base.update(overrides)
    return base


# A job tuple matching the default _job_params (no change expected):
# (job_style, prog_owner, prog_name, job_type, job_action, num_args,
#  sched_owner, sched_name, sched_type, repeat_interval, job_class,
#  enabled, restartable, state, logging_level, instance_stickiness,
#  dest_owner, destination, cred_owner, cred_name, comments, auto_drop)
_EXISTING_JOB_ROW = (
    "REGULAR", None, None, "PLSQL_BLOCK", "BEGIN NULL; END;", 0,
    None, None, "ONCE", None, "DEFAULT_JOB_CLASS",
    "TRUE", "FALSE", "DISABLED", "RUNS", "TRUE",
    None, None, None, None, None, "FALSE",
)


def test_job_absent_missing_no_change(monkeypatch):
    """state=absent, job doesn't exist → no change."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _job_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_job_present_creates_new(monkeypatch):
    """state=present, job doesn't exist → creates it, changed=True."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _job_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_job_present_already_matches_no_change(monkeypatch):
    """state=present, job exists and matches all params → no change."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=_EXISTING_JOB_ROW)

    class Mod(BaseFakeModule):
        params = _job_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_job_absent_existing_drops(monkeypatch):
    """state=absent, job exists → drops it, changed=True."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=_EXISTING_JOB_ROW)

    class Mod(BaseFakeModule):
        params = _job_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_job_present_modified_recreates(monkeypatch):
    """state=present, job exists with different job_class → drop+recreate."""
    mod = _load("oracle_job")
    row = list(_EXISTING_JOB_ROW)
    row[10] = "OTHER_CLASS"  # different job_class
    FakeOC, conn = _make_fake_db(fetchone_row=tuple(row))

    class Mod(BaseFakeModule):
        params = _job_params()  # wants DEFAULT_JOB_CLASS

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_job_invalid_name_fails(monkeypatch):
    """job_name without OWNER.NAME format → fail_json."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _job_params(job_name="BADJOBNAME")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(FailJson):
        mod.main()


def test_job_check_mode_new(monkeypatch):
    """check_mode, job doesn't exist → would_change=True."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _job_params()
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_job_check_mode_existing_no_diff(monkeypatch):
    """check_mode, job exists and matches → would_change=False."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=_EXISTING_JOB_ROW)

    class Mod(BaseFakeModule):
        params = _job_params()
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_job_lightweight_without_program_fails(monkeypatch):
    """lightweight=True without program_name → fail_json."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _job_params(lightweight=True, program_name=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "lightweight" in exc.value.args[0]["msg"].lower()


def test_job_present_no_action_no_program_fails(monkeypatch):
    """state=present, no job_action and no program_name → fail_json."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _job_params(job_action=None, program_name=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(FailJson):
        mod.main()


def test_job_lightweight_restartable_fails(monkeypatch):
    """lightweight=True AND restartable=True → fail_json (line 419)."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _job_params(lightweight=True, restartable=True, program_name="SYS.MYPROG", job_action=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "restartable" in exc.value.args[0]["msg"].lower()


def test_job_program_name_invalid_format_fails(monkeypatch):
    """program_name without OWNER.NAME format → fail_json (line 423)."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _job_params(program_name="INVALID_NO_DOT", job_action=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "program" in exc.value.args[0]["msg"].lower()


def test_job_schedule_name_invalid_format_fails(monkeypatch):
    """schedule_name without OWNER.NAME format → fail_json (line 425)."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _job_params(schedule_name="INVALID", repeat_interval=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "schedule" in exc.value.args[0]["msg"].lower()


def test_job_wallet_connect(monkeypatch):
    """No user/password → wallet connect path."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _job_params(user=None, password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_job_sysdba_mode(monkeypatch):
    """user+password with mode=sysdba → SYSDBA connect."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _job_params(mode="sysdba")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_job_partial_auth_fails(monkeypatch):
    """user set but password=None → fail_json."""
    mod = _load("oracle_job")

    class _ErrorOC:
        def __init__(self, module):
            module.fail_json(msg="Missing username or password for oracledb")

    class Mod(BaseFakeModule):
        params = _job_params(user="u", password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _ErrorOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "missing" in exc.value.args[0]["msg"].lower()


def test_job_low_version_fails(monkeypatch):
    """conn.version < '10.2' → fail_json.

    Note: oracle_job uses lexicographic comparison, so '1.0.0' < '10.2' is True.
    """
    mod = _load("oracle_job")

    _conn = FakeOracleConn()
    _conn.version = "1.0.0"  # lexicographically less than "10.2"

    class _OldOC:
        def __init__(self, module):
            self.conn = _conn
            self.version = _conn.version

    class Mod(BaseFakeModule):
        params = _job_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _OldOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "10g" in exc.value.args[0]["msg"].lower()


def test_job_create_with_program_name(monkeypatch):
    """program_name='SYS.MYPROG' → covers create_job program_name branch."""
    mod = _load("oracle_job")
    FakeOC, conn = _make_fake_db(fetchone_row=None)

    class Mod(BaseFakeModule):
        params = _job_params(program_name="SYS.MYPROG", job_action=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_job_check_mode_existing_with_changes(monkeypatch):
    """Existing job with different program_name → check_mode → would_change=True (covers compare_with_owner)."""
    mod = _load("oracle_job")
    # Use a row where program_name differs from params (triggers compare_with_owner else branch)
    row = list(_EXISTING_JOB_ROW)
    row[1] = "SYS"      # program_owner
    row[2] = "MYPROG"   # program_name  → stored as SYS.MYPROG
    FakeOC, conn = _make_fake_db(fetchone_row=tuple(row))

    class Mod(BaseFakeModule):
        params = _job_params(program_name="SYS.OTHERPROG", job_action=None)
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


# ===========================================================================
# oracle_privs
# ===========================================================================


def _privs_params(**overrides):
    base = {
        **_JOB_CONN_BASE,
        "state": "present",
        "privs": ["SELECT"],
        "objs": None,
        "objtypes": ["TABLE", "VIEW"],
        "roles": ["TESTROLE"],
        "convert_to_upper": True,
        "quiet": True,
    }
    base.update(overrides)
    return base


class _PrivsZeroConn(FakeOracleConn):
    """FakeOracleConn whose vars return 0 (no error, no changes)."""

    class _ZeroVar:
        def __init__(self):
            self._value = 0

        def getvalue(self):
            return self._value

    def cursor(self):
        return _PrivsZeroCursor(self)


class _PrivsZeroCursor:
    """Cursor stub: vars return 0, execute/fetch are no-ops."""

    def __init__(self, conn):
        self._conn = conn

    def var(self, typ):
        return _PrivsZeroConn._ZeroVar()

    def arrayvar(self, typ, values, size=None):
        return values

    def execute(self, sql, params=None):
        self._conn.ddls.append(sql)  # record for assertions

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        pass

    @property
    def rowcount(self):
        return 0


def _make_privs_db():
    _conn = _PrivsZeroConn()

    class _FakeOC:
        def __init__(self, module):
            self.conn = _conn
            self.version = _conn.version

    return _FakeOC, _conn


def test_privs_check_mode_always_changed(monkeypatch):
    """check_mode → exits with changed=True (conservative estimate)."""
    mod = _load("oracle_privs")
    _FakeOC, _conn = _make_privs_db()

    class Mod(BaseFakeModule):
        params = _privs_params()
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True


def test_privs_grant_sys_no_objs_no_changes(monkeypatch):
    """System privilege grant (no objs) → vars return 0 → changed=False."""
    mod = _load("oracle_privs")
    _FakeOC, _conn = _make_privs_db()

    class Mod(BaseFakeModule):
        params = _privs_params()  # objs=None → system privilege path

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_privs_invalid_privilege_fails(monkeypatch):
    """Invalid privilege name (with '!') → fail_json before connecting."""
    mod = _load("oracle_privs")

    class Mod(BaseFakeModule):
        params = _privs_params(privs=["BAD!PRIV"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(FailJson):
        mod.main()


def test_privs_invalid_role_fails(monkeypatch):
    """Reserved role 'SYS' → fail_json before connecting."""
    mod = _load("oracle_privs")

    class Mod(BaseFakeModule):
        params = _privs_params(roles=["SYS"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(FailJson):
        mod.main()


def test_privs_invalid_obj_fails(monkeypatch):
    """Object without schema.name format → fail_json."""
    mod = _load("oracle_privs")

    class Mod(BaseFakeModule):
        params = _privs_params(objs=["BADOBJ"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(FailJson):
        mod.main()


def test_privs_grant_with_objs_no_changes(monkeypatch):
    """Object privilege grant (objs specified) → vars return 0 → changed=False."""
    mod = _load("oracle_privs")
    _FakeOC, _conn = _make_privs_db()

    class Mod(BaseFakeModule):
        params = _privs_params(objs=["HR.EMPLOYEES"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_privs_absent_no_objs_no_changes(monkeypatch):
    """state=absent, system privilege revoke → vars return 0 → changed=False."""
    mod = _load("oracle_privs")
    _FakeOC, _conn = _make_privs_db()

    class Mod(BaseFakeModule):
        params = _privs_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


# ---------------------------------------------------------------------------
# Additional oracle_privs coverage tests
# ---------------------------------------------------------------------------


def test_privs_oracledb_not_exists_fails(monkeypatch):
    """oracledb_exists=False -> fail_json (line 219)."""
    mod = _load("oracle_privs")

    class Mod(BaseFakeModule):
        params = _privs_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracledb_exists", False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "oracledb" in exc.value.args[0]["msg"].lower()


def test_privs_invalid_objtype_fails(monkeypatch):
    """Invalid objtype -> fail_json (line 236)."""
    mod = _load("oracle_privs")

    class Mod(BaseFakeModule):
        params = _privs_params(objtypes=["BAD!TYPE"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "object type" in exc.value.args[0]["msg"].lower()


def test_privs_wallet_sysdba_connect(monkeypatch):
    """No user/password + mode=sysdba -> wallet+SYSDBA path."""
    mod = _load("oracle_privs")
    _FakeOC, _conn = _make_privs_db()

    class Mod(BaseFakeModule):
        params = _privs_params(user=None, password=None, mode="sysdba")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_privs_wallet_normal_connect(monkeypatch):
    """No user/password + mode=normal -> wallet path."""
    mod = _load("oracle_privs")
    _FakeOC, _conn = _make_privs_db()

    class Mod(BaseFakeModule):
        params = _privs_params(user=None, password=None, mode="normal")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_privs_user_password_sysdba_connect(monkeypatch):
    """user+password + mode=sysdba -> SYSDBA path."""
    mod = _load("oracle_privs")
    _FakeOC, _conn = _make_privs_db()

    class Mod(BaseFakeModule):
        params = _privs_params(mode="sysdba")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_privs_database_error_dpi1047_fails(monkeypatch):
    """Connection error with DPI-1047 message -> fail_json with DPI-1047."""
    mod = _load("oracle_privs")

    class _ErrorOC:
        def __init__(self, module):
            module.fail_json(msg="DPI-1047: cannot load Oracle Client library")

    class Mod(BaseFakeModule):
        params = _privs_params(mode="sysdba")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _ErrorOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "DPI-1047" in exc.value.args[0]["msg"]


def test_privs_database_error_generic_fails(monkeypatch):
    """Connection error -> fail_json."""
    mod = _load("oracle_privs")

    class _ErrorOC:
        def __init__(self, module):
            module.fail_json(msg="Oracle connection failed: ORA-12541: TNS:no listener")

    class Mod(BaseFakeModule):
        params = _privs_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _ErrorOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "Oracle connection failed" in exc.value.args[0]["msg"]


def test_privs_low_version_fails(monkeypatch):
    """conn.version < '11.2' -> fail_json."""
    mod = _load("oracle_privs")
    _FakeOC, _conn = _make_privs_db()
    _conn.version = "10.2.0"

    class _OldOC:
        def __init__(self, module):
            self.conn = _conn
            self.version = _conn.version

    class Mod(BaseFakeModule):
        params = _privs_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _OldOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "11g" in exc.value.args[0]["msg"].lower()


def test_privs_session_container_applied(monkeypatch):
    """Valid session_container -> ALTER SESSION executed."""
    mod = _load("oracle_privs")

    executed_sqls = []

    class _TrackingCursor(_PrivsZeroCursor):
        def execute(self, sql, params=None):
            executed_sqls.append(sql)

    class _TrackingConn(_PrivsZeroConn):
        def cursor(self):
            return _TrackingCursor(self)

    _track_conn = _TrackingConn()

    class _FakeOC:
        def __init__(self, module):
            self.conn = _track_conn
            self.version = _track_conn.version

    class Mod(BaseFakeModule):
        params = _privs_params(session_container="MYPDB")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(ExitJson):
        mod.main()
    assert any("ALTER SESSION" in sql for sql in executed_sqls)


def test_privs_invalid_session_container_fails(monkeypatch):
    """Invalid session_container name -> fail_json."""
    mod = _load("oracle_privs")
    _FakeOC, _conn = _make_privs_db()

    class Mod(BaseFakeModule):
        params = _privs_params(session_container="1INVALID!")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "session_container" in exc.value.args[0]["msg"].lower()


def test_privs_var_error_triggers_rollback_and_fail(monkeypatch):
    """var_error.getvalue() > 0 -> rollback + fail_json."""
    mod = _load("oracle_privs")

    rolled_back = []

    class _IndexedVar:
        def __init__(self, index):
            self._index = index

        def getvalue(self):
            if self._index == 1:
                return 1
            if self._index == 2:
                return "PL/SQL error detail"
            return 0

    class _ErrConn(_PrivsZeroConn):
        def rollback(self):
            rolled_back.append(True)

        def cursor(self):
            return _ErrCursor(self)

    class _ErrCursor(_PrivsZeroCursor):
        def __init__(self, conn):
            super().__init__(conn)
            self._var_idx = 0

        def var(self, typ):
            v = _IndexedVar(self._var_idx)
            self._var_idx += 1
            return v

    _err_conn = _ErrConn()

    class _FakeOC:
        def __init__(self, module):
            self.conn = _err_conn
            self.version = _err_conn.version

    class Mod(BaseFakeModule):
        params = _privs_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOC)

    with pytest.raises(FailJson):
        mod.main()
    assert rolled_back, "rollback() should have been called"
