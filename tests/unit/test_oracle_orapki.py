"""Unit tests for oracle_orapki module."""
import pytest

from conftest import ExitJson, FailJson, load_module_from_path, module_path
from helpers import BaseFakeModule


def _load():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_orapki.py"), "oracle_orapki_test"
    )


def _orapki_params(**overrides):
    base = {
        "oracle_home": "/fake/oracle",
        "state": "present",
        "wallet_location": "/opt/oracle/wallets/test",
        "wallet_password": "TestPass123",
        "new_password": None,
        "change_password": False,
        "auto_login": "none",
        "cert_state": None,
        "cert_type": None,
        "cert_file": None,
        "cert_dn": None,
        "cert_alias": None,
        "cert_keysize": 2048,
        "cert_validity": 3650,
        "cert_export_file": None,
        "credential_state": None,
        "credential_type": "credential",
        "credential_alias": None,
        "credential_db": None,
        "credential_user": None,
        "credential_password": None,
        "credential_secret": None,
    }
    base.update(overrides)
    return base


WALLET_DISPLAY_OUTPUT = """Oracle PKI Tool Release 19.0.0.0.0
Requested Certificates:
User Certificates:
Subject:        CN=myserver.example.com,O=MyCompany
Trusted Certificates:
Subject:        CN=RootCA,O=MyCompany
Subject:        CN=IntermediateCA,O=MyCompany
"""

WALLET_DISPLAY_EMPTY = """Oracle PKI Tool Release 19.0.0.0.0
Requested Certificates:
User Certificates:
Trusted Certificates:
"""

LIST_CREDENTIALS_OUTPUT = """List credential (index: connect_string username)
1: primary_db sys
2: standby_db admin
"""

LIST_CREDENTIALS_EMPTY = ""

LIST_ENTRIES_OUTPUT = """List secret store entries:
1: primary_db
2: standby_db
"""


class _OrapkiModule(BaseFakeModule):
    """Module that stubs run_command for orapki."""

    _orapki_responses = {}
    _commands_run = []

    def run_command(self, command, **kwargs):
        self.__class__._commands_run.append(command)
        # Match on subcommand keywords in the command list
        cmd_str = ' '.join(command) if isinstance(command, list) else command
        for key, response in self._orapki_responses.items():
            if key in cmd_str:
                return response
        # Default: success with empty output
        return (0, '', '')


class _FakeOs:
    """Fake os module for path checks."""

    def __init__(self, orapki_exists=True, wallet_exists=False):
        self._orapki_exists = orapki_exists
        self._wallet_exists = wallet_exists
        self.environ = {}

    class path:
        _orapki_exists = True
        _wallet_exists = False
        _p12_exists = False
        _sso_exists = False
        _wallet_location = '/opt/oracle/wallets/test'

        @classmethod
        def exists(cls, path_str):
            if 'orapki' in path_str:
                return cls._orapki_exists
            return cls._wallet_exists

        @classmethod
        def isfile(cls, path_str):
            if 'ewallet.p12' in path_str:
                return cls._p12_exists
            if 'cwallet.sso' in path_str:
                return cls._sso_exists
            return False

        @classmethod
        def join(cls, *args):
            return '/'.join(args)


def _make_fake_os(orapki_exists=True, wallet_exists=False, sso_only=False):
    """Create a _FakeOs with specific settings."""
    fake = _FakeOs(orapki_exists, wallet_exists)
    fake.path._orapki_exists = orapki_exists
    fake.path._wallet_exists = wallet_exists
    if wallet_exists:
        if sso_only:
            fake.path._p12_exists = False
            fake.path._sso_exists = True
        else:
            fake.path._p12_exists = True
            fake.path._sso_exists = True
    else:
        fake.path._p12_exists = False
        fake.path._sso_exists = False
    return fake


# ===========================================================================
# Tests: Wallet lifecycle
# ===========================================================================

def test_orapki_wallet_create(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params()
        _orapki_responses = {'wallet create': (0, '', '')}
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True, wallet_exists=False))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


def test_orapki_wallet_create_idempotent(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params()
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True, wallet_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


def test_orapki_wallet_create_auto_login(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(auto_login="auto_login")
        _orapki_responses = {'wallet create': (0, '', '')}
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True, wallet_exists=False))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    # Verify -auto_login was in the command
    cmd_str = ' '.join(Mod._commands_run[-1])
    assert '-auto_login' in cmd_str


def test_orapki_wallet_create_local_auto_login(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(auto_login="local_auto_login")
        _orapki_responses = {'wallet create': (0, '', '')}
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True, wallet_exists=False))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    cmd_str = ' '.join(Mod._commands_run[-1])
    assert '-auto_login_local' in cmd_str


def test_orapki_wallet_create_auto_login_only(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(auto_login="auto_login_only", wallet_password=None)
        _orapki_responses = {'wallet create': (0, '', '')}
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True, wallet_exists=False))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    cmd_str = ' '.join(Mod._commands_run[-1])
    assert '-auto_login_only' in cmd_str


def test_orapki_wallet_absent(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(state="absent")
        _orapki_responses = {'wallet delete': (0, '', '')}
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True, wallet_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


def test_orapki_wallet_absent_idempotent(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(state="absent")
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True, wallet_exists=False))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


def test_orapki_wallet_status(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(state="status")
        _orapki_responses = {'wallet display': (0, WALLET_DISPLAY_OUTPUT, '')}
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert 'CN=RootCA,O=MyCompany' in result["trusted_certs"]
    assert 'CN=myserver.example.com,O=MyCompany' in result["user_certs"]
    assert len(result["trusted_certs"]) == 2


def test_orapki_wallet_change_password(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(change_password=True, new_password="NewPass456")
        _orapki_responses = {'change_pwd': (0, '', '')}
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True, wallet_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


def test_orapki_missing_binary_fails(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params()
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=False, wallet_exists=False))

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "orapki not found" in exc.value.args[0]["msg"]


# ===========================================================================
# Tests: Certificate management
# ===========================================================================

def test_orapki_add_trusted_cert(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            cert_state="present", cert_type="trusted_cert",
            cert_file="/tmp/ca.crt",
        )
        _orapki_responses = {'wallet add': (0, '', '')}
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    cmd_str = ' '.join(Mod._commands_run[-1])
    assert '-trusted_cert' in cmd_str


def test_orapki_add_user_cert(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            cert_state="present", cert_type="user_cert",
            cert_file="/tmp/server.crt",
        )
        _orapki_responses = {'wallet add': (0, '', '')}
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    cmd_str = ' '.join(Mod._commands_run[-1])
    assert '-user_cert' in cmd_str


def test_orapki_add_self_signed(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            cert_state="present", cert_type="self_signed",
            cert_dn="CN=test.local,O=TestOrg",
            cert_keysize=4096, cert_validity=365,
        )
        _orapki_responses = {
            'wallet display': (0, WALLET_DISPLAY_EMPTY, ''),
            'wallet add': (0, '', ''),
        }
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    cmd_str = ' '.join(Mod._commands_run[-1])
    assert '-self_signed' in cmd_str
    assert '4096' in cmd_str
    assert '365' in cmd_str


def test_orapki_add_self_signed_idempotent(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            cert_state="present", cert_type="self_signed",
            cert_dn="CN=myserver.example.com,O=MyCompany",
        )
        _orapki_responses = {
            'wallet display': (0, WALLET_DISPLAY_OUTPUT, ''),
        }
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


def test_orapki_remove_cert(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            cert_state="absent", cert_dn="CN=RootCA,O=MyCompany",
        )
        _orapki_responses = {
            'wallet display': (0, WALLET_DISPLAY_OUTPUT, ''),
            'wallet remove': (0, '', ''),
        }
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


def test_orapki_remove_cert_idempotent(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            cert_state="absent", cert_dn="CN=nonexistent.com",
        )
        _orapki_responses = {
            'wallet display': (0, WALLET_DISPLAY_OUTPUT, ''),
        }
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


def test_orapki_export_cert(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            cert_state="exported",
            cert_dn="CN=myserver.example.com",
            cert_export_file="/tmp/export.crt",
        )
        _orapki_responses = {'wallet export': (0, '', '')}
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


# ===========================================================================
# Tests: Credential management
# ===========================================================================

def test_orapki_create_credential(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            credential_state="present",
            credential_alias="primary_db",
            credential_db="PROD",
            credential_user="sys",
            credential_password="SysPass123",
        )
        _orapki_responses = {
            'list_credentials': (0, LIST_CREDENTIALS_EMPTY, ''),
            'create_credential': (0, '', ''),
        }
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    # Verify correct orapki flags
    cmd = Mod._commands_run[-1]
    assert '-connect_string' in cmd, "should use -connect_string flag"
    assert cmd[cmd.index('-connect_string') + 1] == 'PROD'
    assert '-username' in cmd, "should use -username flag"
    assert cmd[cmd.index('-username') + 1] == 'sys'
    assert '-password' in cmd, "credential password should use -password flag"
    assert cmd[cmd.index('-password') + 1] == 'SysPass123'
    assert '-pwd' in cmd, "wallet password should use -pwd flag"
    assert cmd[cmd.index('-pwd') + 1] == 'TestPass123'


def test_orapki_modify_credential(monkeypatch):
    mod = _load()

    # Simulate a wallet where credential_db "PROD" already exists
    existing_creds = "List credential (index: connect_string username)\n1: PROD sys\n"

    class Mod(_OrapkiModule):
        params = _orapki_params(
            credential_state="present",
            credential_alias="primary_db",
            credential_db="PROD",
            credential_user="newsys",
            credential_password="NewPass123",
        )
        _orapki_responses = {
            'list_credentials': (0, existing_creds, ''),
            'modify_credential': (0, '', ''),
        }
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    # Verify correct orapki flags for modify — uses credential_db (connect_string)
    cmd = Mod._commands_run[-1]
    assert '-connect_string' in cmd, "should use -connect_string for modify"
    assert cmd[cmd.index('-connect_string') + 1] == 'PROD'
    assert '-username' in cmd, "should use -username flag"
    assert cmd[cmd.index('-username') + 1] == 'newsys'
    assert '-password' in cmd
    assert cmd[cmd.index('-password') + 1] == 'NewPass123'
    assert '-pwd' in cmd
    assert cmd[cmd.index('-pwd') + 1] == 'TestPass123'


def test_orapki_delete_credential(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            credential_state="absent",
            credential_alias="primary_db",
            credential_db="primary_db",
        )
        _orapki_responses = {
            'list_credentials': (0, LIST_CREDENTIALS_OUTPUT, ''),
            'delete_credential': (0, '', ''),
        }
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    cmd = Mod._commands_run[-1]
    assert '-connect_string' in cmd
    assert cmd[cmd.index('-connect_string') + 1] == 'primary_db'


def test_orapki_delete_credential_idempotent(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            credential_state="absent",
            credential_alias="nonexistent",
            credential_db="nonexistent",
        )
        _orapki_responses = {
            'list_credentials': (0, LIST_CREDENTIALS_EMPTY, ''),
        }
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


def test_orapki_create_entry(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            credential_state="present",
            credential_type="entry",
            credential_alias="api_key",
            credential_secret="sk-abc123",
        )
        _orapki_responses = {
            'list_entries': (0, '', ''),
            'create_entry': (0, '', ''),
        }
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


def test_orapki_modify_entry(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            credential_state="present",
            credential_type="entry",
            credential_alias="primary_db",
            credential_secret="new-secret-value",
        )
        _orapki_responses = {
            'list_entries': (0, LIST_ENTRIES_OUTPUT, ''),
            'modify_entry': (0, '', ''),
        }
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


def test_orapki_delete_entry(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            credential_state="absent",
            credential_type="entry",
            credential_alias="primary_db",
        )
        _orapki_responses = {
            'list_entries': (0, LIST_ENTRIES_OUTPUT, ''),
            'delete_entry': (0, '', ''),
        }
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


def test_orapki_credential_requires_credential_db(monkeypatch):
    """credential_type='credential' must have credential_db set."""
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(
            credential_state="present",
            credential_alias="myalias",
            credential_user="sys",
            credential_password="pass",
        )
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True))

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert 'credential_db is required' in exc.value.args[0]['msg']


def test_orapki_wallet_delete_sso_only(monkeypatch):
    """Deleting an SSO-only wallet should use -sso flag."""
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(state="absent", wallet_password=None)
        _orapki_responses = {'wallet delete': (0, '', '')}
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True, wallet_exists=True, sso_only=True))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    cmd = Mod._commands_run[-1]
    assert '-sso' in cmd


def test_orapki_wallet_add_auto_login_to_existing(monkeypatch):
    """Adding auto-login to an existing PKCS#12 wallet (no cwallet.sso yet)."""
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params(auto_login="auto_login")
        _orapki_responses = {'wallet create': (0, '', '')}
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    # Wallet exists with p12 but no sso
    fake_os = _make_fake_os(orapki_exists=True, wallet_exists=True)
    fake_os.path._sso_exists = False
    monkeypatch.setattr(mod, "os", fake_os)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    cmd_str = ' '.join(Mod._commands_run[-1])
    assert '-auto_login' in cmd_str


# ===========================================================================
# Tests: Check mode
# ===========================================================================

def test_orapki_check_mode_no_commands(monkeypatch):
    mod = _load()

    class Mod(_OrapkiModule):
        params = _orapki_params()
        check_mode = True
        _commands_run = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _make_fake_os(orapki_exists=True, wallet_exists=False))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    # No orapki commands should have been run
    assert len(Mod._commands_run) == 0


# ===========================================================================
# Tests: Parser
# ===========================================================================

def test_parse_wallet_display():
    mod = _load()
    result = mod._parse_wallet_display(WALLET_DISPLAY_OUTPUT)
    assert len(result['user_certs']) == 1
    assert result['user_certs'][0] == 'CN=myserver.example.com,O=MyCompany'
    assert len(result['trusted_certs']) == 2
    assert 'CN=RootCA,O=MyCompany' in result['trusted_certs']
    assert 'CN=IntermediateCA,O=MyCompany' in result['trusted_certs']


def test_parse_list_credentials():
    mod = _load()
    result = mod._parse_list_credentials(LIST_CREDENTIALS_OUTPUT)
    assert 'primary_db' in result
    assert 'standby_db' in result
    assert len(result) == 2


def test_parse_list_credentials_empty():
    mod = _load()
    result = mod._parse_list_credentials(LIST_CREDENTIALS_EMPTY)
    assert result == []


def test_parse_list_entries():
    mod = _load()
    result = mod._parse_list_entries(LIST_ENTRIES_OUTPUT)
    assert 'primary_db' in result
    assert 'standby_db' in result
    assert len(result) == 2


def test_parse_list_entries_empty():
    mod = _load()
    result = mod._parse_list_entries('')
    assert result == []
