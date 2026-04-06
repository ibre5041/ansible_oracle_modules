"""Unit tests for oracle_audit module."""
import pytest

from conftest import ExitJson, FailJson, load_module_from_path, module_path
from helpers import BASE_CONN_PARAMS, BaseFakeConn, BaseFakeModule


def _load():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_audit.py"), "oracle_audit_test"
    )


def _audit_params(**overrides):
    base = {
        **BASE_CONN_PARAMS,
        "state": "present",
        "policy_name": "TEST_AUDIT_POL",
        "audit_actions": None,
        "audit_privileges": None,
        "audit_roles": None,
        "audit_condition": None,
        "evaluate_per": None,
        "container": "current",
        "enabled_users": None,
        "enabled_except_users": None,
    }
    base.update(overrides)
    return base


class _AuditConn(BaseFakeConn):
    """Simulates AUDIT_UNIFIED_POLICIES and AUDIT_UNIFIED_ENABLED_POLICIES."""

    def __init__(self, module, policy_rows=None, enabled_rows=None):
        super().__init__(module)
        self._policy_rows = policy_rows if policy_rows is not None else []
        self._enabled_rows = enabled_rows if enabled_rows is not None else []

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        sql_upper = sql.upper()
        if 'AUDIT_UNIFIED_ENABLED_POLICIES' in sql_upper:
            return self._enabled_rows
        if 'AUDIT_UNIFIED_POLICIES' in sql_upper:
            return self._policy_rows
        return [] if not fetchone else {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_POLICY_ROW = {
    'policy_name': 'TEST_AUDIT_POL',
    'audit_option': 'CREATE TABLE',
    'audit_option_type': 'SYSTEM PRIVILEGE',
    'object_schema': None,
    'object_name': None,
    'object_type': None,
    'audit_condition': None,
    'condition_eval_opt': None,
}

_ENABLED_ROW = {
    'policy_name': 'TEST_AUDIT_POL',
    'enabled_option': 'BY USER',
    'entity_name': 'ALL USERS',
    'entity_type': 'USER',
    'success': 'YES',
    'failure': 'YES',
}


# ===========================================================================
# Tests: state=status
# ===========================================================================

def test_audit_status(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='status')

    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(
        mod, 'oracleConnection',
        lambda m: _AuditConn(m, policy_rows=[_POLICY_ROW], enabled_rows=[_ENABLED_ROW]),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert result['exists'] is True
    assert result['enabled'] is True
    assert result['policy'] == [_POLICY_ROW]
    assert result['enabled_details'] == [_ENABLED_ROW]


def test_audit_status_not_exists(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='status')

    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(
        mod, 'oracleConnection',
        lambda m: _AuditConn(m, policy_rows=[], enabled_rows=[]),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert result['exists'] is False
    assert result['enabled'] is False
    assert result['policy'] == []
    assert result['enabled_details'] == []


# ===========================================================================
# Tests: state=present (create)
# ===========================================================================

def test_audit_create_privileges(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='present', audit_privileges=['CREATE TABLE', 'ALTER USER'])

    conn = _AuditConn(Mod(), policy_rows=[], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'Audit policy created' in result['msg']
    assert len(conn.ddls) == 1
    ddl = conn.ddls[0]
    assert 'CREATE AUDIT POLICY' in ddl
    assert 'PRIVILEGES CREATE TABLE, ALTER USER' in ddl


def test_audit_create_actions(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(
            state='present',
            audit_actions=['SELECT ON hr.employees', 'INSERT ON hr.employees'],
        )

    conn = _AuditConn(Mod(), policy_rows=[], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    ddl = conn.ddls[0]
    assert 'CREATE AUDIT POLICY' in ddl
    assert 'ACTIONS SELECT ON hr.employees, INSERT ON hr.employees' in ddl


def test_audit_create_roles(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='present', audit_roles=['DBA', 'SYSDBA'])

    conn = _AuditConn(Mod(), policy_rows=[], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    ddl = conn.ddls[0]
    assert 'CREATE AUDIT POLICY' in ddl
    assert 'ROLES DBA, SYSDBA' in ddl


def test_audit_create_combined(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(
            state='present',
            audit_privileges=['CREATE TABLE'],
            audit_actions=['SELECT'],
            audit_condition="SYS_CONTEXT('USERENV','IP_ADDRESS') != '10.0.0.1'",
            evaluate_per='session',
        )

    conn = _AuditConn(Mod(), policy_rows=[], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    ddl = conn.ddls[0]
    assert 'CREATE AUDIT POLICY' in ddl
    assert 'PRIVILEGES CREATE TABLE' in ddl
    assert 'ACTIONS SELECT' in ddl
    assert 'CONDITION' in ddl
    # Inner single quotes must be doubled for valid Oracle syntax
    assert "SYS_CONTEXT(''USERENV'',''IP_ADDRESS'') != ''10.0.0.1''" in ddl
    assert 'EVALUATE PER SESSION' in ddl


def test_audit_create_condition_escapes_single_quotes(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(
            state='present',
            audit_privileges=['CREATE TABLE'],
            audit_condition="FOO = 'bar'",
        )

    conn = _AuditConn(Mod(), policy_rows=[], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson):
        mod.main()
    ddl = conn.ddls[0]
    assert "CONDITION 'FOO = ''bar'''" in ddl


def test_audit_create_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='present', audit_privileges=['CREATE TABLE'])

    conn = _AuditConn(Mod(), policy_rows=[_POLICY_ROW], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'already exists' in result['msg']
    assert conn.ddls == []


def test_audit_create_no_clauses(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='present')

    conn = _AuditConn(Mod(), policy_rows=[], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'audit_actions' in result['msg'] or 'audit_privileges' in result['msg']


def test_audit_create_container_all(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(
            state='present',
            audit_privileges=['CREATE TABLE'],
            container='all',
        )

    conn = _AuditConn(Mod(), policy_rows=[], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'CONTAINER = ALL' in conn.ddls[0]


# ===========================================================================
# Tests: state=absent (drop)
# ===========================================================================

def test_audit_drop(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='absent')

    conn = _AuditConn(Mod(), policy_rows=[_POLICY_ROW], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'dropped' in result['msg']
    assert any('DROP AUDIT POLICY' in d for d in conn.ddls)


def test_audit_drop_enabled(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='absent')

    conn = _AuditConn(Mod(), policy_rows=[_POLICY_ROW], enabled_rows=[_ENABLED_ROW])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert len(conn.ddls) == 2
    assert 'NOAUDIT POLICY' in conn.ddls[0]
    assert 'DROP AUDIT POLICY' in conn.ddls[1]


def test_audit_drop_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='absent')

    conn = _AuditConn(Mod(), policy_rows=[], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'does not exist' in result['msg']
    assert conn.ddls == []


# ===========================================================================
# Tests: state=enabled
# ===========================================================================

def test_audit_enable(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='enabled')

    conn = _AuditConn(Mod(), policy_rows=[_POLICY_ROW], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'enabled' in result['msg']
    ddl = conn.ddls[0]
    assert 'AUDIT POLICY' in ddl
    assert 'TEST_AUDIT_POL' in ddl


def test_audit_enable_users(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='enabled', enabled_users=['HR', 'SCOTT'])

    conn = _AuditConn(Mod(), policy_rows=[_POLICY_ROW], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    ddl = conn.ddls[0]
    assert 'AUDIT POLICY' in ddl
    assert 'BY HR, SCOTT' in ddl


def test_audit_enable_except_users(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='enabled', enabled_except_users=['SYS', 'SYSTEM'])

    conn = _AuditConn(Mod(), policy_rows=[_POLICY_ROW], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    ddl = conn.ddls[0]
    assert 'AUDIT POLICY' in ddl
    assert 'EXCEPT SYS, SYSTEM' in ddl


def test_audit_enable_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='enabled')

    conn = _AuditConn(Mod(), policy_rows=[_POLICY_ROW], enabled_rows=[_ENABLED_ROW])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'already enabled' in result['msg']
    assert conn.ddls == []


def test_audit_enable_idempotent_by_users_order(monkeypatch):
    """Same BY set in different order must be idempotent (set comparison)."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='enabled', enabled_users=['HR', 'SCOTT'])

    enabled = [
        {
            'policy_name': 'TEST_AUDIT_POL',
            'enabled_option': 'BY USER',
            'entity_name': 'SCOTT',
            'entity_type': 'USER',
            'success': 'YES',
            'failure': 'YES',
        },
        {
            'policy_name': 'TEST_AUDIT_POL',
            'enabled_option': 'BY USER',
            'entity_name': 'HR',
            'entity_type': 'USER',
            'success': 'YES',
            'failure': 'YES',
        },
    ]
    conn = _AuditConn(Mod(), policy_rows=[_POLICY_ROW], enabled_rows=enabled)
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert conn.ddls == []


def test_audit_enable_scope_mismatch_all_to_by(monkeypatch):
    """Enabled for all users but task requests BY must re-apply (NOAUDIT then AUDIT)."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='enabled', enabled_users=['HR'])

    conn = _AuditConn(Mod(), policy_rows=[_POLICY_ROW], enabled_rows=[_ENABLED_ROW])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert len(conn.ddls) == 2
    assert 'NOAUDIT POLICY' in conn.ddls[0]
    assert 'AUDIT POLICY' in conn.ddls[1]
    assert 'BY HR' in conn.ddls[1]


def test_audit_enable_idempotent_except(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='enabled', enabled_except_users=['SYS', 'SYSTEM'])

    enabled = [
        {
            'policy_name': 'TEST_AUDIT_POL',
            'enabled_option': 'EXCEPT USER',
            'entity_name': 'SYSTEM',
            'entity_type': 'USER',
            'success': 'YES',
            'failure': 'YES',
        },
        {
            'policy_name': 'TEST_AUDIT_POL',
            'enabled_option': 'EXCEPT USER',
            'entity_name': 'SYS',
            'entity_type': 'USER',
            'success': 'YES',
            'failure': 'YES',
        },
    ]
    conn = _AuditConn(Mod(), policy_rows=[_POLICY_ROW], enabled_rows=enabled)
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert conn.ddls == []


def test_audit_enable_scope_mismatch_by_to_all(monkeypatch):
    """Enabled BY specific users but task requests all users must re-apply."""
    mod = _load()

    by_hr = {
        'policy_name': 'TEST_AUDIT_POL',
        'enabled_option': 'BY USER',
        'entity_name': 'HR',
        'entity_type': 'USER',
        'success': 'YES',
        'failure': 'YES',
    }

    class Mod(BaseFakeModule):
        params = _audit_params(state='enabled')

    conn = _AuditConn(Mod(), policy_rows=[_POLICY_ROW], enabled_rows=[by_hr])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert len(conn.ddls) == 2
    assert 'NOAUDIT POLICY' in conn.ddls[0]
    assert conn.ddls[1].startswith('AUDIT POLICY')
    assert 'BY' not in conn.ddls[1]


def test_audit_enable_not_exists(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='enabled')

    conn = _AuditConn(Mod(), policy_rows=[], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'TEST_AUDIT_POL' in result['msg']


# ===========================================================================
# Tests: state=disabled
# ===========================================================================

def test_audit_disable(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='disabled')

    conn = _AuditConn(Mod(), policy_rows=[_POLICY_ROW], enabled_rows=[_ENABLED_ROW])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'disabled' in result['msg']
    ddl = conn.ddls[0]
    assert 'NOAUDIT POLICY' in ddl
    assert 'TEST_AUDIT_POL' in ddl


def test_audit_disable_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='disabled')

    conn = _AuditConn(Mod(), policy_rows=[_POLICY_ROW], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'already disabled' in result['msg']
    assert conn.ddls == []


def test_audit_disable_policy_not_exists(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='disabled')

    conn = _AuditConn(Mod(), policy_rows=[], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'does not exist' in result['msg']
    assert 'cannot disable' in result['msg']


def test_audit_reject_invalid_policy_name(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(state='status', policy_name='X; INJECTION')

    conn = _AuditConn(Mod(), policy_rows=[], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    msg = exc.value.args[0]['msg'].lower()
    assert 'identifier' in msg


def test_audit_reject_clause_sql_metacharacters(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _audit_params(
            state='present',
            audit_privileges=["CREATE TABLE; DROP USER X --"],
        )

    conn = _AuditConn(Mod(), policy_rows=[], enabled_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert 'audit_privileges' in exc.value.args[0]['msg'].lower()
