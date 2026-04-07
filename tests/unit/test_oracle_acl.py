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
        self.ddl_binds = []

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        """Narrow sample rows by host/port clauses (mirrors DBA_HOST_ACES queries)."""
        rows = list(self._ace_rows)
        p = dict(params or {})
        sql_norm = ' '.join(sql.split()).upper()

        h = p.get('host')
        if h is not None:
            rows = [r for r in rows if r.get('host') == h]

        if 'LOWER_PORT IS NULL' in sql_norm:
            rows = [r for r in rows if r.get('lower_port') is None]
        elif 'LOWER_PORT = :LOWER_PORT' in sql_norm and p.get('lower_port') is not None:
            rows = [r for r in rows if r.get('lower_port') == p['lower_port']]

        if 'UPPER_PORT IS NULL' in sql_norm:
            rows = [r for r in rows if r.get('upper_port') is None]
        elif 'UPPER_PORT = :UPPER_PORT' in sql_norm and p.get('upper_port') is not None:
            rows = [r for r in rows if r.get('upper_port') == p['upper_port']]

        return rows

    def execute_ddl(self, sql, params=None, no_change=False, ignore_errors=None, ddls_entry=None):
        trace = ddls_entry if ddls_entry is not None else sql
        self.ddls.append(trace)
        self.ddl_binds.append(dict(params) if params else {})
        if not no_change:
            self.changed = True


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
    binds = conn.ddl_binds[0]
    assert 'DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE' in ddl
    assert 'host => :host' in ddl
    assert 'xs$name_list(:privilege)' in ddl
    assert 'principal_name => :principal' in ddl
    assert 'granted => :granted' in ddl
    assert binds['host'] == 'dbserver.example.com'
    assert binds['privilege'] == 'connect'
    assert binds['principal'] == 'HR'
    assert binds['granted'] is True
    assert binds['lower_port'] is None
    assert binds['upper_port'] is None


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
    binds = conn.ddl_binds[0]
    assert 'DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE' in ddl
    assert 'lower_port => :lower_port' in ddl
    assert 'upper_port => :upper_port' in ddl
    assert binds['lower_port'] == 25
    assert binds['upper_port'] == 25


def test_acl_present_creates_when_only_port_scoped_ace_exists(monkeypatch):
    """Host-wide present must not treat a port-scoped ACE as the same entry."""
    mod = _load()
    row_25 = {**_ACE_ROW, 'lower_port': 25, 'upper_port': 25}

    class Mod(BaseFakeModule):
        params = _acl_params(state='present')

    conn = _AclConn(Mod(), ace_rows=[row_25])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'ACE created' in result['msg']


def test_acl_present_idempotent_host_wide_ignores_other_port_ace(monkeypatch):
    """Host-wide idempotent match must ignore a different port-scoped ACE."""
    mod = _load()
    row_25 = {**_ACE_ROW, 'lower_port': 25, 'upper_port': 25}
    row_wide = dict(_ACE_ROW)

    class Mod(BaseFakeModule):
        params = _acl_params(state='present')

    conn = _AclConn(Mod(), ace_rows=[row_25, row_wide])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'already exists' in result['msg']


def test_acl_absent_host_wide_noop_when_only_port_scoped_ace(monkeypatch):
    """state=absent host-wide must not match a port-only ACE."""
    mod = _load()
    row_25 = {**_ACE_ROW, 'lower_port': 25, 'upper_port': 25}

    class Mod(BaseFakeModule):
        params = _acl_params(state='absent')

    conn = _AclConn(Mod(), ace_rows=[row_25])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'does not exist' in result['msg']
    assert conn.ddls == []


def test_acl_create_ace_deny(monkeypatch):
    """state=present with is_grant=False binds granted => false in xs$ace_type."""
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
    assert 'granted => :granted' in ddl
    assert conn.ddl_binds[0]['granted'] is False


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
    assert 'xs$name_list(:privilege)' in ddl
    assert conn.ddl_binds[0]['privilege'] == 'resolve'


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


def test_acl_create_when_grant_exists_but_deny_requested(monkeypatch):
    """state=present with is_grant=False is not idempotent on a GRANT-only row."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='present', is_grant=False)

    conn = _AclConn(Mod(), ace_rows=[_ACE_ROW])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'ACE created' in result['msg']
    assert conn.ddl_binds[0]['granted'] is False


def test_acl_create_idempotent_deny(monkeypatch):
    """state=present with is_grant=False matches DENY grant_type from DBA_HOST_ACES."""
    mod = _load()

    deny_row = {**_ACE_ROW, 'grant_type': 'DENY'}

    class Mod(BaseFakeModule):
        params = _acl_params(state='present', is_grant=False)

    conn = _AclConn(Mod(), ace_rows=[deny_row])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'already exists' in result['msg']
    assert conn.ddls == []


# ===========================================================================
# Tests: check mode (no DDL via create_ace / remove_ace)
# ===========================================================================

def test_acl_present_check_mode_would_create(monkeypatch):
    """state=present in check mode reports planned APPEND_HOST_ACE without execute_ddl."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='present')
        check_mode = True

    conn = _AclConn(Mod(), ace_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'check mode' in result['msg']
    assert conn.ddls == []
    assert len(result['ddls']) == 1
    assert result['ddls'][0].startswith('--')
    assert 'DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE' in result['ddls'][0]


def test_acl_present_check_mode_idempotent(monkeypatch):
    """state=present in check mode is unchanged when ACE already exists."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='present')
        check_mode = True

    conn = _AclConn(Mod(), ace_rows=[_ACE_ROW])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'already exists' in result['msg']
    assert conn.ddls == []


def test_acl_absent_check_mode_would_remove(monkeypatch):
    """state=absent in check mode reports planned REMOVE_HOST_ACE without execute_ddl."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='absent')
        check_mode = True

    conn = _AclConn(Mod(), ace_rows=[_ACE_ROW])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'check mode' in result['msg']
    assert conn.ddls == []
    assert result['ddls'][0].startswith('--')
    assert 'DBMS_NETWORK_ACL_ADMIN.REMOVE_HOST_ACE' in result['ddls'][0]


def test_acl_absent_check_mode_idempotent(monkeypatch):
    """state=absent in check mode is unchanged when ACE does not exist."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _acl_params(state='absent')
        check_mode = True

    conn = _AclConn(Mod(), ace_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'does not exist' in result['msg']
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
    binds = conn.ddl_binds[0]
    assert 'DBMS_NETWORK_ACL_ADMIN.REMOVE_HOST_ACE' in ddl
    assert 'host => :host' in ddl
    assert 'xs$name_list(:privilege)' in ddl
    assert 'principal_name => :principal' in ddl
    assert 'granted => :granted' in ddl
    assert binds['host'] == 'dbserver.example.com'
    assert binds['privilege'] == 'connect'
    assert binds['principal'] == 'HR'
    assert binds['granted'] is True


def test_acl_remove_ace_deny(monkeypatch):
    """state=absent with is_grant=False removes a DENY ACE (bind matches grant type)."""
    mod = _load()

    deny_row = {**_ACE_ROW, 'grant_type': 'DENY'}

    class Mod(BaseFakeModule):
        params = _acl_params(state='absent', is_grant=False)

    conn = _AclConn(Mod(), ace_rows=[deny_row])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert conn.ddl_binds[0]['granted'] is False


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
    binds = conn.ddl_binds[0]
    assert 'DBMS_NETWORK_ACL_ADMIN.REMOVE_HOST_ACE' in ddl
    assert 'lower_port => :lower_port' in ddl
    assert 'upper_port => :upper_port' in ddl
    assert binds['lower_port'] == 25
    assert binds['upper_port'] == 25
    assert binds['granted'] is True


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
