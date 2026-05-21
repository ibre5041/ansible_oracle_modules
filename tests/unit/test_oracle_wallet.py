"""Unit tests for oracle_wallet module."""
import pytest

from conftest import ExitJson, FailJson, load_module_from_path, module_path
from helpers import BASE_CONN_PARAMS, BaseFakeConn, BaseFakeModule, SequencedFakeConn


def _load():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_wallet.py"), "oracle_wallet_test"
    )


def test_escape_sql_literal_doubles_quotes():
    mod = _load()
    assert mod.escape_sql_literal("a'b", "'") == "a''b"
    assert mod.escape_sql_literal('a"b', '"') == 'a""b'


def test_escape_sql_literal_rejects_newlines():
    mod = _load()
    with pytest.raises(ValueError):
        mod.escape_sql_literal("a\nb", "'")
    with pytest.raises(ValueError):
        mod.escape_sql_literal("a\rb", '"')


def test_redact_ddls_handles_doubled_quotes_in_secret():
    mod = _load()
    ddl = (
        "ADMINISTER KEY MANAGEMENT FORCE ADD SECRET 'foo''bar' FOR CLIENT 'X' "
        'IDENTIFIED BY "***"'
    )
    out = mod._redact_ddls([ddl])[0]
    assert "foo" not in out
    assert "SECRET '***'" in out


def _wallet_params(**overrides):
    base = {
        **BASE_CONN_PARAMS,
        "state": "present",
        "open": None,
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

    def __init__(
        self, module, wallet_status='NOT_AVAILABLE', wallet_type='', keystore_mode='NONE',
        secrets=None, wallet_rows=None,
    ):
        super().__init__(module)
        self._wallet_status = wallet_status
        self._wallet_type = wallet_type
        self._keystore_mode = keystore_mode
        self._secrets = secrets or []
        self._wallet_rows = wallet_rows

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        sql_upper = sql.upper()
        if 'V$ENCRYPTION_WALLET' in sql_upper:
            if self._wallet_rows is not None:
                rows = self._wallet_rows
                return rows[0] if fetchone else rows
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


def test_wallet_present_idempotent_without_password_when_already_exists(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present", keystore_password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


# ===========================================================================
# Tests: open=True (open keystore)
# ===========================================================================

def test_wallet_open_when_closed(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present", open=True)

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
        params = _wallet_params(state="present", open=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


def test_wallet_open_with_container_all(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present", open=True, container="all")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'CLOSED', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("CONTAINER = ALL" in d for d in result["ddls"])


# ===========================================================================
# Tests: open=False (close keystore)
# ===========================================================================

def test_wallet_close_when_open(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present", open=False)

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
        params = _wallet_params(state="present", open=False)

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
    joined = "\n".join(result["ddls"])
    assert "NewPass456" not in joined
    assert "TestKeystorePass123" not in joined
    assert "SET '***'" in joined


def test_wallet_change_password_with_backup_location_runs_backup_keystore(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(
            state="present",
            change_password=True,
            new_password="NewPass456",
            backup_location="/opt/oracle/backup/wallets",
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    ddls = result["ddls"]
    assert any("ALTER KEYSTORE PASSWORD" in d for d in ddls)
    assert any("BACKUP KEYSTORE" in d for d in ddls)
    assert any("TO '/opt/oracle/backup/wallets'" in d for d in ddls)


def test_wallet_change_password_backup_false_still_honors_backup_tag(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(
            state="present",
            change_password=True,
            new_password="NewPass456",
            backup=False,
            backup_tag="before_pw_change",
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    ddls = result["ddls"]
    assert any("ALTER KEYSTORE PASSWORD" in d for d in ddls)
    backup_ddls = [d for d in ddls if "BACKUP KEYSTORE" in d]
    assert backup_ddls
    assert any("USING 'before_pw_change'" in d for d in backup_ddls)


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

    # Tagless secret — matches the tagless query from params above.
    secrets = [{'client': 'MY_APP', 'secret_tag': ''}]
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

    # Tagless secret — matches the tagless delete from params above.
    secrets = [{'client': 'MY_APP', 'secret_tag': ''}]
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


def test_wallet_secret_task_not_blocked_by_state_absent(monkeypatch):
    """secret_state validation runs before the state==absent keystore guard."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(
            state="absent",
            secret_state="absent",
            secret_client="MY_APP",
            keystore_password="pw",
        )

    secrets = [{'client': 'MY_APP', 'secret_tag': 'tag1'}]
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection",
        lambda m: _WalletConn(m, 'OPEN', 'PASSWORD', secrets=secrets),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["msg"] == "Secret managed successfully"


def test_wallet_delete_secret_includes_using_tag_when_requested(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(
            secret_client="MY_APP",
            secret_state="absent",
            secret_tag="mytag",
            keystore_password="pw",
        )

    secrets = [{'client': 'MY_APP', 'secret_tag': 'mytag'}]
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection",
        lambda m: _WalletConn(m, 'OPEN', 'PASSWORD', secrets=secrets),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    ddl = "\n".join(exc.value.args[0]["ddls"])
    assert "DELETE SECRET" in ddl
    assert "USING TAG 'mytag'" in ddl


def test_wallet_open_container_all_mixed_runs_open(monkeypatch):
    mod = _load()
    rows = [
        {
            'wrl_type': 'FILE', 'wrl_parameter': '/a', 'status': 'OPEN',
            'wallet_type': 'PASSWORD', 'wallet_order': 'SINGLE', 'keystore_mode': 'UNITED',
        },
        {
            'wrl_type': 'FILE', 'wrl_parameter': '/b', 'status': 'CLOSED',
            'wallet_type': 'PASSWORD', 'wallet_order': 'SINGLE', 'keystore_mode': 'UNITED',
        },
    ]

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present", open=True, container="all")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection",
        lambda m: _WalletConn(m, wallet_rows=rows),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("SET KEYSTORE OPEN" in d for d in exc.value.args[0]["ddls"])


def test_wallet_open_container_all_idempotent_when_all_open(monkeypatch):
    mod = _load()
    rows = [
        {
            'wrl_type': 'FILE', 'wrl_parameter': '/a', 'status': 'OPEN',
            'wallet_type': 'PASSWORD', 'wallet_order': 'SINGLE', 'keystore_mode': 'UNITED',
        },
        {
            'wrl_type': 'FILE', 'wrl_parameter': '/b', 'status': 'OPEN_NO_MASTER_KEY',
            'wallet_type': 'PASSWORD', 'wallet_order': 'SINGLE', 'keystore_mode': 'UNITED',
        },
    ]

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present", open=True, container="all")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection",
        lambda m: _WalletConn(m, wallet_rows=rows),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_aggregate_wallet_rows_autologin_uses_open_row():
    """When open rows are all autologin, wallet_type should come from an open row, not first."""
    mod = _load()
    rows = [
        {
            'wrl_type': 'FILE', 'wrl_parameter': '/a', 'status': 'CLOSED',
            'wallet_type': '', 'wallet_order': 'SINGLE', 'keystore_mode': 'UNITED',
        },
        {
            'wrl_type': 'FILE', 'wrl_parameter': '/b', 'status': 'OPEN',
            'wallet_type': 'AUTOLOGIN', 'wallet_order': 'SINGLE', 'keystore_mode': 'UNITED',
        },
    ]
    result = mod._aggregate_wallet_rows(rows)
    assert result['wallet_type'] == 'AUTOLOGIN'


def test_aggregate_wallet_rows_all_not_available():
    """All-NOT_AVAILABLE rows must aggregate to NOT_AVAILABLE, not CLOSED."""
    mod = _load()
    rows = [
        {
            'wrl_type': 'FILE', 'wrl_parameter': '/a', 'status': 'NOT_AVAILABLE',
            'wallet_type': '', 'wallet_order': 'SINGLE', 'keystore_mode': 'NONE',
        },
        {
            'wrl_type': 'FILE', 'wrl_parameter': '/b', 'status': 'NOT_AVAILABLE',
            'wallet_type': '', 'wallet_order': 'SINGLE', 'keystore_mode': 'NONE',
        },
    ]
    result = mod._aggregate_wallet_rows(rows)
    assert result['status'] == 'NOT_AVAILABLE'


def test_wallet_present_container_all_not_available_creates(monkeypatch):
    """state=present with container=all and all NOT_AVAILABLE should create the keystore."""
    mod = _load()
    rows = [
        {
            'wrl_type': 'FILE', 'wrl_parameter': '/a', 'status': 'NOT_AVAILABLE',
            'wallet_type': '', 'wallet_order': 'SINGLE', 'keystore_mode': 'NONE',
        },
        {
            'wrl_type': 'FILE', 'wrl_parameter': '/b', 'status': 'NOT_AVAILABLE',
            'wallet_type': '', 'wallet_order': 'SINGLE', 'keystore_mode': 'NONE',
        },
    ]

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present", container="all")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection",
        lambda m: _WalletConn(m, wallet_rows=rows),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert any("CREATE KEYSTORE" in d for d in exc.value.args[0]["ddls"])


# ===========================================================================
# Tests: state=absent
# ===========================================================================

def test_wallet_absent_skips_connection(monkeypatch):
    mod = _load()
    called = []

    def _track_conn(m):
        called.append(1)
        return _WalletConn(m, 'OPEN')

    class Mod(BaseFakeModule):
        params = _wallet_params(state="absent")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _track_conn, raising=False)

    with pytest.raises(FailJson):
        mod.main()
    assert called == []


def test_wallet_secret_missing_value_skips_connection(monkeypatch):
    mod = _load()
    called = []

    def _track_conn(m):
        called.append(1)
        return _WalletConn(m, 'OPEN', 'PASSWORD')

    class Mod(BaseFakeModule):
        params = _wallet_params(
            secret_state="present",
            secret_client="MY_APP",
            secret=None,
            keystore_password="pw",
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _track_conn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "secret is required" in exc.value.args[0]["msg"]
    assert called == []


def test_wallet_check_mode_secret_skips_connection(monkeypatch):
    mod = _load()
    called = []

    def _track_conn(m):
        called.append(1)
        return _WalletConn(m, 'OPEN', 'PASSWORD')

    class Mod(BaseFakeModule):
        check_mode = True
        params = _wallet_params(
            secret_state="present",
            secret_client="MY_APP",
            secret="s",
            keystore_password="pw",
        )

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _track_conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert called == []


def test_wallet_check_mode_status_opens_connection(monkeypatch):
    mod = _load()
    called = []

    def _track_conn(m):
        called.append(1)
        return _WalletConn(m, 'OPEN', 'PASSWORD', secrets=[])

    class Mod(BaseFakeModule):
        check_mode = True
        params = _wallet_params(state="status")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _track_conn, raising=False)

    with pytest.raises(ExitJson):
        mod.main()
    assert called == [1]


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


# ===========================================================================
# Tests: open parameter validation
# ===========================================================================

def test_wallet_open_rejected_with_status_state(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="status", open=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'OPEN'), raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "only valid with state='present'" in exc.value.args[0]["msg"]


def test_wallet_open_rejected_with_secret_state(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present", open=True, secret_state="present",
                                secret_client="APP", secret="val", keystore_password="pass")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "cannot be combined with secret_state" in exc.value.args[0]["msg"]


def test_wallet_open_true_requires_password(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present", open=True, keystore_password=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'CLOSED'), raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "keystore_password" in exc.value.args[0]["msg"]


def test_wallet_present_open_none_does_not_open_or_close(monkeypatch):
    """open=None (default) should not open or close the keystore."""
    mod = _load()

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present", open=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _WalletConn(m, 'CLOSED', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert not any("SET KEYSTORE OPEN" in d for d in result.get("ddls", []))
    assert not any("SET KEYSTORE CLOSE" in d for d in result.get("ddls", []))


# ===========================================================================
# Tests: tde_key_exists()
# ===========================================================================

def test_tde_key_exists_returns_true_when_count_positive():
    """tde_key_exists returns True when V$ENCRYPTION_KEYS has rows."""
    mod = _load()

    class _KeyConn(BaseFakeConn):
        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            if 'V$ENCRYPTION_KEYS' in sql.upper():
                return {'cnt': 3} if fetchone else [{'cnt': 3}]
            return {} if fetchone else []

    conn = _KeyConn(None)
    assert mod.tde_key_exists(conn) is True


def test_tde_key_exists_returns_false_when_count_zero():
    """tde_key_exists returns False when V$ENCRYPTION_KEYS is empty."""
    mod = _load()

    class _KeyConn(BaseFakeConn):
        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            if 'V$ENCRYPTION_KEYS' in sql.upper():
                return {'cnt': 0} if fetchone else [{'cnt': 0}]
            return {} if fetchone else []

    conn = _KeyConn(None)
    assert mod.tde_key_exists(conn) is False


def test_tde_key_exists_returns_false_on_exception():
    """tde_key_exists returns False when the view raises any exception (e.g. ORA-00942)."""
    mod = _load()

    class _ErrorConn(BaseFakeConn):
        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            raise Exception("ORA-00942: table or view does not exist")

    conn = _ErrorConn(None)
    assert mod.tde_key_exists(conn) is False


def test_wallet_status_includes_tde_key_present(monkeypatch):
    """state=status output must include tde_key_present field."""
    mod = _load()

    class _TdeWalletConn(_WalletConn):
        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            if 'V$ENCRYPTION_KEYS' in sql.upper():
                return {'cnt': 1} if fetchone else [{'cnt': 1}]
            return super().execute_select_to_dict(sql, params=params, fetchone=fetchone, fail_on_error=fail_on_error)

    class Mod(BaseFakeModule):
        params = _wallet_params(state="status")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeWalletConn(m, 'OPEN', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert "tde_key_present" in result
    assert result["tde_key_present"] is True


def test_wallet_present_includes_tde_key_present(monkeypatch):
    """state=present output must include tde_key_present field."""
    mod = _load()

    class _TdeWalletConn(_WalletConn):
        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            if 'V$ENCRYPTION_KEYS' in sql.upper():
                return {'cnt': 0} if fetchone else [{'cnt': 0}]
            return super().execute_select_to_dict(sql, params=params, fetchone=fetchone, fail_on_error=fail_on_error)

    class Mod(BaseFakeModule):
        params = _wallet_params(state="present")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _TdeWalletConn(m, 'OPEN', 'PASSWORD'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert "tde_key_present" in result
    assert result["tde_key_present"] is False
