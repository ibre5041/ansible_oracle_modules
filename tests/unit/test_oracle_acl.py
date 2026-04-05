"""Unit tests for oracle_acl module."""
import pytest
from conftest import ExitJson, FailJson, load_module_from_path, module_path
from helpers import BASE_CONN_PARAMS, BaseFakeConn, BaseFakeModule


def _load():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_acl.py"), "oracle_acl_test"
    )


def _acl_params(**overrides):
    base = {
        **BASE_CONN_PARAMS,
        "state": "present",
        "acl_name": "test_acl",
        "host": "dbserver.example.com",
        "lower_port": None,
        "upper_port": None,
        "principal": "HR",
        "privilege": "connect",
        "is_grant": True,
    }
    base.update(overrides)
    return base


class _AclConn(BaseFakeConn):
    """Simulates DBA_HOST_ACES for ACL unit tests."""

    def __init__(self, module, ace_rows=None):
        super().__init__(module)
        self._ace_rows = ace_rows if ace_rows is not None else []

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        return self._ace_rows


# ---------------------------------------------------------------------------
# Shared sample row
# ---------------------------------------------------------------------------

_ACE_ROW = {
    'host': 'dbserver.example.com',
    'lower_port': None,
    'upper_port': None,
    'ace_order': 1,
    'principal': 'HR',
    'principal_type': 'DB_USER',
    'grant_type': 'GRANT',
    'privilege': 'connect',
}


# ===========================================================================
# Tests: state=status
# ===========================================================================

def test_acl_status(monkeypatch):
    """state=status with a host filter returns matching ACEs."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='status')

    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(
        mod, 'oracleConnection',
        lambda m: _AclConn(m, ace_rows=[_ACE_ROW]),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert result['acl_entries'] == [_ACE_ROW]


def test_acl_status_all(monkeypatch):
    """state=status without a host returns all ACEs."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='status', host=None)

    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(
        mod, 'oracleConnection',
        lambda m: _AclConn(m, ace_rows=[_ACE_ROW]),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert result['acl_entries'] == [_ACE_ROW]


# ===========================================================================
# Tests: state=present (create ACE)
# ===========================================================================

def test_acl_create_ace(monkeypatch):
    """state=present creates an ACE when none exists."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='present')

    conn = _AclConn(Mod(), ace_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'ACE created' in result['msg']
    assert len(conn.ddls) == 1
    ddl = conn.ddls[0]
    assert 'DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE' in ddl
    assert "host => 'dbserver.example.com'" in ddl
    assert "xs$name_list('connect')" in ddl
    assert "principal_name => 'HR'" in ddl
    assert 'is_grant => TRUE' in ddl


def test_acl_create_ace_with_ports(monkeypatch):
    """state=present includes port range in the DDL when lower/upper_port are set."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='present', lower_port=25, upper_port=25)

    conn = _AclConn(Mod(), ace_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    ddl = conn.ddls[0]
    assert 'DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE' in ddl
    assert 'lower_port => 25' in ddl
    assert 'upper_port => 25' in ddl


def test_acl_create_ace_deny(monkeypatch):
    """state=present with is_grant=False generates is_grant => FALSE."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='present', is_grant=False)

    conn = _AclConn(Mod(), ace_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    ddl = conn.ddls[0]
    assert 'DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE' in ddl
    assert 'is_grant => FALSE' in ddl


def test_acl_create_ace_resolve(monkeypatch):
    """state=present with privilege=resolve uses the resolve privilege in DDL."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='present', privilege='resolve')

    conn = _AclConn(Mod(), ace_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    ddl = conn.ddls[0]
    assert 'DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE' in ddl
    assert "xs$name_list('resolve')" in ddl


def test_acl_create_idempotent(monkeypatch):
    """state=present when ACE already exists returns changed=False without DDL."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='present')

    conn = _AclConn(Mod(), ace_rows=[_ACE_ROW])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'already exists' in result['msg']
    assert conn.ddls == []


# ===========================================================================
# Tests: state=absent (remove ACE)
# ===========================================================================

def test_acl_remove_ace(monkeypatch):
    """state=absent removes an existing ACE."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='absent')

    conn = _AclConn(Mod(), ace_rows=[_ACE_ROW])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'ACE removed' in result['msg']
    assert len(conn.ddls) == 1
    ddl = conn.ddls[0]
    assert 'DBMS_NETWORK_ACL_ADMIN.REMOVE_HOST_ACE' in ddl
    assert "host => 'dbserver.example.com'" in ddl
    assert "xs$name_list('connect')" in ddl
    assert "principal_name => 'HR'" in ddl


def test_acl_remove_ace_with_ports(monkeypatch):
    """state=absent includes port range in the REMOVE_HOST_ACE call."""
    mod = _load()

    _ace_with_ports = {**_ACE_ROW, 'lower_port': 25, 'upper_port': 25}

    class Mod(BaseFakeModule):
        params = _acl_params(state='absent', lower_port=25, upper_port=25)

    conn = _AclConn(Mod(), ace_rows=[_ace_with_ports])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    ddl = conn.ddls[0]
    assert 'DBMS_NETWORK_ACL_ADMIN.REMOVE_HOST_ACE' in ddl
    assert 'lower_port => 25' in ddl
    assert 'upper_port => 25' in ddl


def test_acl_remove_idempotent(monkeypatch):
    """state=absent when ACE does not exist returns changed=False without DDL."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='absent')

    conn = _AclConn(Mod(), ace_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'does not exist' in result['msg']
    assert conn.ddls == []
