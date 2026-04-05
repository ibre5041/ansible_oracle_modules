"""Unit tests for oracle_rsrc_plan module."""
import pytest
from conftest import ExitJson, FailJson, load_module_from_path, module_path
from helpers import BASE_CONN_PARAMS, BaseFakeConn, BaseFakeModule


def _load():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_rsrc_plan.py"), "oracle_rsrc_plan_test"
    )


def _plan_params(**overrides):
    base = {
        **BASE_CONN_PARAMS,
        "state": "present",
        "plan": "TEST_PLAN",
        "comment": None,
        "directives": None,
        "max_iops": None,
        "max_mbps": None,
    }
    base.update(overrides)
    return base


class _PlanConn(BaseFakeConn):
    """Simulates DBA_RSRC_PLANS, DBA_RSRC_PLAN_DIRECTIVES, and V$PARAMETER."""

    def __init__(self, module, plan_rows=None, directive_rows=None, active_plan=None):
        super().__init__(module)
        self._plan_rows = plan_rows if plan_rows is not None else []
        self._directive_rows = directive_rows if directive_rows is not None else []
        self._active_plan = active_plan if active_plan is not None else ''

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        sql_upper = sql.upper()
        if 'DBA_RSRC_PLANS' in sql_upper:
            return self._plan_rows
        if 'DBA_RSRC_PLAN_DIRECTIVES' in sql_upper:
            return self._directive_rows
        if 'V$PARAMETER' in sql_upper:
            if self._active_plan:
                row = {'value': self._active_plan}
            else:
                row = {'value': ''}
            return row if fetchone else [row]
        return [] if not fetchone else {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PLAN_ROW = {
    'plan': 'TEST_PLAN',
    'num_plan_directives': 2,
    'cpu_method': 'EMPHASIS',
    'mgmt_method': 'EMPHASIS',
    'status': None,
    'mandatory': 'NO',
}

_DIRECTIVE_ROW = {
    'plan': 'TEST_PLAN',
    'group_or_subplan': 'OTHER_GROUPS',
    'type': 'CONSUMER_GROUP',
    'cpu_p1': 100,
    'parallel_degree_limit_p1': None,
    'active_sess_pool_p1': None,
    'max_idle_time': None,
    'max_idle_blocker_time': None,
    'max_iops': None,
    'max_mbps': None,
}


# ===========================================================================
# Tests: state=status
# ===========================================================================

def test_plan_status(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _plan_params(state='status')

    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(
        mod, 'oracleConnection',
        lambda m: _PlanConn(m, plan_rows=[_PLAN_ROW], directive_rows=[_DIRECTIVE_ROW],
                            active_plan='OTHER_PLAN'),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert result['exists'] is True
    assert result['plan'] == [_PLAN_ROW]
    assert result['directives'] == [_DIRECTIVE_ROW]
    assert result['is_active'] is False


def test_plan_status_not_exists(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _plan_params(state='status')

    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(
        mod, 'oracleConnection',
        lambda m: _PlanConn(m, plan_rows=[], directive_rows=[], active_plan=''),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert result['exists'] is False
    assert result['plan'] == []
    assert result['directives'] == []
    assert result['is_active'] is False


# ===========================================================================
# Tests: state=present (create)
# ===========================================================================

def test_plan_create(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _plan_params(state='present', comment='My test plan')

    conn = _PlanConn(Mod(), plan_rows=[], directive_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'created' in result['msg']
    assert any('CREATE_PENDING_AREA' in d for d in conn.ddls)
    assert any('CREATE_PLAN' in d and 'TEST_PLAN' in d for d in conn.ddls)
    assert any('SUBMIT_PENDING_AREA' in d for d in conn.ddls)


def test_plan_create_with_directives(monkeypatch):
    mod = _load()

    directives = [
        {'group': 'OLTP_GROUP', 'cpu_p1': 70},
        {'group': 'BATCH_GROUP', 'cpu_p1': 20},
        {'group': 'OTHER_GROUPS', 'cpu_p1': 10},
    ]

    class Mod(BaseFakeModule):
        params = _plan_params(state='present', directives=directives)

    conn = _PlanConn(Mod(), plan_rows=[], directive_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'created' in result['msg']
    directive_ddls = [d for d in conn.ddls if 'CREATE_PLAN_DIRECTIVE' in d]
    assert len(directive_ddls) == 3
    assert any('OLTP_GROUP' in d and 'cpu_p1 => 70' in d for d in directive_ddls)
    assert any('BATCH_GROUP' in d and 'cpu_p1 => 20' in d for d in directive_ddls)
    assert any('OTHER_GROUPS' in d and 'cpu_p1 => 10' in d for d in directive_ddls)


def test_plan_create_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _plan_params(state='present')

    conn = _PlanConn(Mod(), plan_rows=[_PLAN_ROW], directive_rows=[_DIRECTIVE_ROW])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'already exists' in result['msg']
    assert conn.ddls == []


# ===========================================================================
# Tests: state=absent (drop)
# ===========================================================================

def test_plan_drop(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _plan_params(state='absent')

    conn = _PlanConn(Mod(), plan_rows=[_PLAN_ROW], directive_rows=[_DIRECTIVE_ROW],
                     active_plan='OTHER_PLAN')
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'dropped' in result['msg']
    assert any('DELETE_PLAN_CASCADE' in d and 'TEST_PLAN' in d for d in conn.ddls)
    assert any('CREATE_PENDING_AREA' in d for d in conn.ddls)
    assert any('SUBMIT_PENDING_AREA' in d for d in conn.ddls)


def test_plan_drop_active(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _plan_params(state='absent')

    conn = _PlanConn(Mod(), plan_rows=[_PLAN_ROW], directive_rows=[_DIRECTIVE_ROW],
                     active_plan='TEST_PLAN')
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'dropped' in result['msg']
    # Deactivate DDL must come before the drop DDL
    deactivate_idx = next(
        i for i, d in enumerate(conn.ddls)
        if 'RESOURCE_MANAGER_PLAN' in d and "''" in d
    )
    drop_idx = next(
        i for i, d in enumerate(conn.ddls)
        if 'DELETE_PLAN_CASCADE' in d
    )
    assert deactivate_idx < drop_idx


def test_plan_drop_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _plan_params(state='absent')

    conn = _PlanConn(Mod(), plan_rows=[], directive_rows=[], active_plan='')
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'does not exist' in result['msg']
    assert conn.ddls == []


# ===========================================================================
# Tests: state=active (activate)
# ===========================================================================

def test_plan_activate(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _plan_params(state='active')

    conn = _PlanConn(Mod(), plan_rows=[_PLAN_ROW], directive_rows=[_DIRECTIVE_ROW],
                     active_plan='OTHER_PLAN')
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'activated' in result['msg']
    assert any('RESOURCE_MANAGER_PLAN' in d and 'TEST_PLAN' in d for d in conn.ddls)


def test_plan_activate_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _plan_params(state='active')

    conn = _PlanConn(Mod(), plan_rows=[_PLAN_ROW], directive_rows=[_DIRECTIVE_ROW],
                     active_plan='TEST_PLAN')
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'already active' in result['msg']
    assert conn.ddls == []


def test_plan_activate_not_exists(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _plan_params(state='active')

    conn = _PlanConn(Mod(), plan_rows=[], directive_rows=[], active_plan='')
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'TEST_PLAN' in result['msg']
