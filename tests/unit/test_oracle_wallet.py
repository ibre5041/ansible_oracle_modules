"""Unit tests for oracle_wallet module."""
import pytest

from conftest import ExitJson, FailJson, load_module_from_path, module_path
from helpers import BASE_CONN_PARAMS, BaseFakeConn, BaseFakeModule, SequencedFakeConn


def _load():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_wallet.py"), "oracle_wallet_test"
    )


def _wallet_params(**overrides):
    base = {
        **BASE_CONN_PARAMS,
        "state": "present",
        "keystore_location": "/opt/oracle/wallets/tde",
        "keystore_password": "TestKeystorePass123",
        "new_password": None,
        "auto_login": "none",
        "change_password": False,
        "backup": True,
        "backup_location": None,
        "backup_tag": None,
        "force_keystore": False,
        "secret": None,
        "secret_client": None,
        "secret_tag": None,
        "secret_state": None,
        "container": "current",
    }
    base.update(overrides)
    return base


class _WalletConn(BaseFakeConn):
    """Simulates V$ENCRYPTION_WALLET responses."""

    def __init__(self, module, wallet_status='NOT_AVAILABLE', wallet_type='', keystore_mode='NONE', secrets=None):
        super().__init__(module)
        self._wallet_status = wallet_status
        self._wallet_type = wallet_type
        self._keystore_mode = keystore_mode
        self._secrets = secrets or []

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        sql_upper = sql.upper()
        if 'V$ENCRYPTION_WALLET' in sql_upper:
            row = {
                'wrl_type': 'FILE',
                'wrl_parameter': '/opt/oracle/wallets/tde',
                'status': self._wallet_status,
                'wallet_type': self._wallet_type,
                'wallet_order': 'SINGLE',
                'keystore_mode': self._keystore_mode,
            }
            return row if fetchone else [row]
        if 'V$CLIENT_SECRETS' in sql_upper:
            return self._secrets
        if 'V$PARAMETER' in sql_upper:
            return {'value': '/opt/oracle/admin/wallets'} if fetchone else [{'value': '/opt/oracle/admin/wallets'}]
        return {} if fetchone else []


# ===========================================================================
# Tests: state=status
# ===========================================================================

def test_wallet_status(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="status")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD', 'UNITED'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert result["wallet_status"] == "OPEN"
    assert result["wallet_type"] == "PASSWORD"
    assert result["keystore_mode"] == "UNITED"


# ===========================================================================
# Tests: state=present (create keystore)
# ===========================================================================

def test_wallet_create_when_not_exists(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present")

    conn = _WalletConn(None, 'NOT_AVAILABLE')

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'NOT_AVAILABLE'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert len(result["ddls"]) >= 1
    assert "CREATE KEYSTORE" in result["ddls"][0]


def test_wallet_create_idempotent_when_exists(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


# ===========================================================================
# Tests: state=open
# ===========================================================================

def test_wallet_open_when_closed(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="open")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'CLOSED', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("SET KEYSTORE OPEN" in d for d in result["ddls"])


def test_wallet_open_idempotent_when_already_open(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="open")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


def test_wallet_open_with_container_all(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="open", container="all")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'CLOSED', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("CONTAINER = ALL" in d for d in result["ddls"])


# ===========================================================================
# Tests: state=closed
# ===========================================================================

def test_wallet_close_when_open(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="closed")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("SET KEYSTORE CLOSE" in d for d in result["ddls"])


def test_wallet_close_idempotent_when_already_closed(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="closed")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'CLOSED'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


# ===========================================================================
# Tests: auto-login
# ===========================================================================

def test_wallet_create_auto_login(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present", auto_login="auto_login")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("AUTO_LOGIN KEYSTORE" in d for d in result["ddls"])


def test_wallet_create_local_auto_login(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present", auto_login="local_auto_login")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("LOCAL AUTO_LOGIN" in d for d in result["ddls"])


# ===========================================================================
# Tests: change_password
# ===========================================================================

def test_wallet_change_password(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(
            state="present", change_password=True,
            new_password="NewPass456"
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("ALTER KEYSTORE PASSWORD" in d for d in result["ddls"])


# ===========================================================================
# Tests: secret management
# ===========================================================================

def test_wallet_add_secret(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(
            secret="my_secret", secret_client="MY_APP",
            secret_state="present"
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("ADD SECRET" in d for d in result["ddls"])


def test_wallet_update_existing_secret(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(
            secret="new_value", secret_client="MY_APP",
            secret_state="present"
        )

    secrets = [{'client': 'MY_APP', 'secret_tag': 'tag1'}]
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD', secrets=secrets), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("UPDATE SECRET" in d for d in result["ddls"])


def test_wallet_delete_secret(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(
            secret_client="MY_APP", secret_state="absent"
        )

    secrets = [{'client': 'MY_APP', 'secret_tag': 'tag1'}]
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD', secrets=secrets), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("DELETE SECRET" in d for d in result["ddls"])


def test_wallet_delete_secret_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(
            secret_client="MY_APP", secret_state="absent"
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD', secrets=[]), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


# ===========================================================================
# Tests: state=absent
# ===========================================================================

def test_wallet_absent_fails(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN'), raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "does not support dropping" in exc.value.args[0]["msg"]


# ===========================================================================
# Tests: missing password
# ===========================================================================

def test_wallet_create_without_password_fails(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present", keystore_password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'NOT_AVAILABLE'), raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "keystore_password" in exc.value.args[0]["msg"]
