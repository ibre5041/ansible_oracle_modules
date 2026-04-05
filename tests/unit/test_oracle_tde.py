"""Unit tests for oracle_tde module."""
import pytest

from conftest import ExitJson, FailJson, load_module_from_path, module_path
from helpers import BASE_CONN_PARAMS, BaseFakeConn, BaseFakeModule


def _load():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_tde.py"), "oracle_tde_test"
    )


def _tde_params(**overrides):
    base = {
        **BASE_CONN_PARAMS,
        "state": "present",
        "master_key_action": None,
        "algorithm": "AES256",
        "key_tag": None,
        "keystore_password": "TestKeystorePass123",
        "tablespace": None,
        "tablespace_state": None,
        "file_name_convert": None,
        "online": True,
        "export_file": None,
        "export_secret": None,
        "tablespace_encryption_policy": None,
        "force_keystore": False,
        "container": "current",
    }
    base.update(overrides)
    return base


class _TdeConn(BaseFakeConn):
    """Simulates V$ENCRYPTION_WALLET, V$ENCRYPTION_KEYS, V$ENCRYPTED_TABLESPACES."""

    def __init__(self, module, wallet_status='OPEN', has_master_key=True,
                 encrypted_tablespaces=None, param_value=None):
        super().__init__(module)
        self._wallet_status = wallet_status
        self._has_master_key = has_master_key
        self._encrypted_tablespaces = encrypted_tablespaces or []
        self._param_value = param_value

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        sql_upper = sql.upper()
        if 'V$ENCRYPTION_WALLET' in sql_upper:
            row = {'status': self._wallet_status, 'wallet_type': 'PASSWORD', 'keystore_mode': 'UNITED'}
            return row if fetchone else [row]
        if 'V$ENCRYPTION_KEYS' in sql_upper:
            if self._has_master_key:
                row = {
                    'key_id': 'AABBCCDD11223344',
                    'tag': 'test_key',
                    'creation_time': '2024-01-01',
                    'activation_time': '2024-01-01',
                    'key_use': 'TDE IN PDB',
                    'keystore_type': 'SOFTWARE KEYSTORE',
                    'origin': 'LOCAL',
                }
                return [row]
            return []
        if 'V$ENCRYPTED_TABLESPACES' in sql_upper:
            if params and params.get('tablespace'):
                ts_name = params['tablespace'].upper()
                for ts in self._encrypted_tablespaces:
                    if ts['tablespace_name'].upper() == ts_name:
                        return ts if fetchone else [ts]
                return {} if fetchone else []
            return self._encrypted_tablespaces
        if 'V$PARAMETER' in sql_upper:
            row = {'value': self._param_value}
            return row if fetchone else [row]
        return {} if fetchone else []


# ===========================================================================
# Tests: state=status
# ===========================================================================

def test_tde_status(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(state="status")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert result["wallet_status"] == "OPEN"
    assert result["master_key"]["key_id"] == "AABBCCDD11223344"


# ===========================================================================
# Tests: set_key
# ===========================================================================

def test_tde_set_key(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(master_key_action="set_key")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("SET KEY" in d for d in result["ddls"])


def test_tde_set_key_with_algorithm_and_tag(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(master_key_action="set_key", algorithm="AES128", key_tag="prod_key")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    ddl = result["ddls"][0]
    assert "AES128" in ddl
    assert "prod_key" in ddl


def test_tde_set_key_with_container_all(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(master_key_action="set_key", container="all")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert any("CONTAINER = ALL" in d for d in result["ddls"])


# ===========================================================================
# Tests: rotate_key
# ===========================================================================

def test_tde_rotate_key(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(master_key_action="rotate_key")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("SET KEY" in d for d in result["ddls"])


# ===========================================================================
# Tests: create_key
# ===========================================================================

def test_tde_create_key(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(master_key_action="create_key")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("CREATE KEY" in d for d in result["ddls"])


# ===========================================================================
# Tests: encrypt_tablespace
# ===========================================================================

def test_tde_encrypt_tablespace(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(tablespace="USERS", tablespace_state="encrypted")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("ENCRYPT" in d and "USERS" in d for d in result["ddls"])


def test_tde_encrypt_tablespace_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(tablespace="USERS", tablespace_state="encrypted")

    encrypted_ts = [{'tablespace_name': 'USERS', 'encryptionalg': 'AES256', 'encryptedts': 'YES', 'status': 'NORMAL', 'key_version': 1}]
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m, encrypted_tablespaces=encrypted_ts), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


# ===========================================================================
# Tests: decrypt_tablespace
# ===========================================================================

def test_tde_decrypt_tablespace(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(tablespace="USERS", tablespace_state="decrypted")

    encrypted_ts = [{'tablespace_name': 'USERS', 'encryptionalg': 'AES256', 'encryptedts': 'YES', 'status': 'NORMAL', 'key_version': 1}]
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m, encrypted_tablespaces=encrypted_ts), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("DECRYPT" in d for d in result["ddls"])


def test_tde_decrypt_tablespace_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(tablespace="USERS", tablespace_state="decrypted")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m, encrypted_tablespaces=[]), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


# ===========================================================================
# Tests: rekey_tablespace
# ===========================================================================

def test_tde_rekey_tablespace(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(tablespace="USERS", tablespace_state="rekeyed")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("REKEY" in d for d in result["ddls"])


# ===========================================================================
# Tests: export_keys
# ===========================================================================

def test_tde_export_keys(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(
            master_key_action="export_keys",
            export_file="/tmp/keys.exp",
            export_secret="ExportPass123",
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("EXPORT" in d for d in result["ddls"])


# ===========================================================================
# Tests: import_keys
# ===========================================================================

def test_tde_import_keys(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(
            master_key_action="import_keys",
            export_file="/tmp/keys.exp",
            export_secret="ExportPass123",
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("IMPORT" in d for d in result["ddls"])


# ===========================================================================
# Tests: prerequisites check
# ===========================================================================

def test_tde_fails_when_keystore_not_open(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(master_key_action="set_key")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m, wallet_status='CLOSED'), raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "not open" in exc.value.args[0]["msg"]


def test_tde_encrypt_fails_without_master_key(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(tablespace="USERS", tablespace_state="encrypted")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m, has_master_key=False), raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "master key" in exc.value.args[0]["msg"].lower()


# ===========================================================================
# Tests: tablespace_encryption_policy
# ===========================================================================

def test_tde_set_encryption_policy(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(tablespace_encryption_policy="AUTO_ENABLE")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m, param_value='DDL'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("TABLESPACE_ENCRYPTION" in d for d in result["ddls"])


def test_tde_set_encryption_policy_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _tde_params(tablespace_encryption_policy="AUTO_ENABLE")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeConn(m, param_value='AUTO_ENABLE'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
