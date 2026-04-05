"""Unit tests for oracle_flashback module."""
import pytest
from conftest import ExitJson, FailJson, load_module_from_path, module_path
from helpers import BASE_CONN_PARAMS, BaseFakeConn, BaseFakeModule


def _load():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_flashback.py"), "oracle_flashback_test"
    )


def _flashback_params(**overrides):
    base = {
        **BASE_CONN_PARAMS,
        "state": "present",
        "restore_point": "TEST_RP",
        "guaranteed": False,
        "scn": None,
        "preserve": False,
    }
    base.update(overrides)
    return base


class _FlashbackConn(BaseFakeConn):
    """Simulates V$RESTORE_POINT queries."""

    def __init__(self, module, rp_rows=None):
        super().__init__(module)
        self._rp_rows = rp_rows if rp_rows is not None else []

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        if 'V$RESTORE_POINT' in sql:
            return self._rp_rows
        return [] if not fetchone else {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RP_ROW = {
    'name': 'TEST_RP',
    'scn': 1000000,
    'time': None,
    'storage_size': 0,
    'guarantee_flashback_database': 'NO',
    'preserved': 'NO',
}


# ===========================================================================
# Tests: state=status
# ===========================================================================

def test_flashback_status(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _flashback_params(state='status')

    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(
        mod, 'oracleConnection',
        lambda m: _FlashbackConn(m, rp_rows=[_RP_ROW]),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert result['exists'] is True
    assert result['restore_point'] == [_RP_ROW]


def test_flashback_status_not_exists(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _flashback_params(state='status')

    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(
        mod, 'oracleConnection',
        lambda m: _FlashbackConn(m, rp_rows=[]),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert result['exists'] is False
    assert result['restore_point'] == []


# ===========================================================================
# Tests: state=present (create)
# ===========================================================================

def test_flashback_create(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _flashback_params(state='present')

    conn = _FlashbackConn(Mod(), rp_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'created' in result['msg']
    assert len(conn.ddls) == 1
    ddl = conn.ddls[0]
    assert 'CREATE RESTORE POINT' in ddl
    assert 'TEST_RP' in ddl


def test_flashback_create_guaranteed(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _flashback_params(state='present', guaranteed=True)

    conn = _FlashbackConn(Mod(), rp_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    ddl = conn.ddls[0]
    assert 'CREATE RESTORE POINT' in ddl
    assert 'GUARANTEE FLASHBACK DATABASE' in ddl


def test_flashback_create_scn(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _flashback_params(state='present', scn=12345)

    conn = _FlashbackConn(Mod(), rp_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    ddl = conn.ddls[0]
    assert 'CREATE RESTORE POINT' in ddl
    assert 'AS OF SCN 12345' in ddl


def test_flashback_create_preserve(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _flashback_params(state='present', preserve=True)

    conn = _FlashbackConn(Mod(), rp_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    ddl = conn.ddls[0]
    assert 'CREATE RESTORE POINT' in ddl
    assert 'PRESERVE' in ddl


def test_flashback_create_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _flashback_params(state='present')

    conn = _FlashbackConn(Mod(), rp_rows=[_RP_ROW])
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

def test_flashback_drop(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _flashback_params(state='absent')

    conn = _FlashbackConn(Mod(), rp_rows=[_RP_ROW])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is True
    assert 'dropped' in result['msg']
    assert len(conn.ddls) == 1
    assert 'DROP RESTORE POINT' in conn.ddls[0]
    assert 'TEST_RP' in conn.ddls[0]


def test_flashback_drop_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _flashback_params(state='absent')

    conn = _FlashbackConn(Mod(), rp_rows=[])
    monkeypatch.setattr(mod, 'AnsibleModule', Mod)
    monkeypatch.setattr(mod, 'oracleConnection', lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result['changed'] is False
    assert 'does not exist' in result['msg']
    assert conn.ddls == []
