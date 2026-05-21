"""Unit tests for oracle_ldapuser module.

oracle_ldapuser.py requires real LDAP and Oracle database connections for the
main() body, which are infeasible to mock without extensive shims.  We test
the pure-Python helpers and the early-exit validation paths in main().
"""
import pytest

from conftest import ExitJson, FailJson, load_module_from_path
from helpers import BaseFakeModule


def _load():
    return load_module_from_path("plugins/modules/oracle_ldapuser.py", "oracle_ldapuser")


# ---------------------------------------------------------------------------
# clean_string tests (lines 178-187)
# ---------------------------------------------------------------------------

def test_clean_string_valid_simple(monkeypatch):
    """clean_string: valid two-char identifier → uppercased."""
    mod = _load()
    assert mod.clean_string("AB") == "AB"


def test_clean_string_valid_with_digits_and_underscores(monkeypatch):
    """clean_string: letters, digits, underscores → uppercased (regex path)."""
    mod = _load()
    # oraclepattern is None on first call → compiles regex (line 184)
    mod.oraclepattern = None  # reset so line 184 is hit
    result = mod.clean_string("My_User1")
    assert result == "MY_USER1"


def test_clean_string_too_long(monkeypatch):
    """clean_string: string >32 chars → raises (line 185-186)."""
    mod = _load()
    with pytest.raises(Exception):
        mod.clean_string("A" * 33)


def test_clean_string_starts_with_digit(monkeypatch):
    """clean_string: starts with digit → fails regex → raises (line 185-186)."""
    mod = _load()
    with pytest.raises(Exception):
        mod.clean_string("1BadName")


def test_clean_string_ends_with_underscore(monkeypatch):
    """clean_string: ends with underscore → fails regex → raises."""
    mod = _load()
    with pytest.raises(Exception):
        mod.clean_string("BadName_")


def test_clean_string_single_char(monkeypatch):
    """clean_string: single char → fails regex (needs at least 2) → raises."""
    mod = _load()
    with pytest.raises(Exception):
        mod.clean_string("A")


# ---------------------------------------------------------------------------
# apply_session_container tests (lines 190-197)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# main() early validation tests (lines 256-264)
# ---------------------------------------------------------------------------

def _make_ldap_mod(params):
    class Mod(BaseFakeModule):
        pass
    Mod.params = params
    return Mod


def _ldap_params(**overrides):
    base = {
        "hostname": "localhost",
        "port": 1521,
        "service_name": "svc",
        "user": "u",
        "password": "p",
        "oracle_home": None,
        "dsn": None,
        "session_container": None,
        "mode": "normal",
        "user_default_tablespace": "USERS",
        "user_quota_on_default_tbs_mb": None,
        "user_temp_tablespace": "TEMP",
        "user_profile": "LDAP_USER",
        "user_default_password": None,
        "user_grants": ["create session"],
        "ldap_connect": "ldap://localhost:389",
        "ldap_binddn": "reader@domain.int",
        "ldap_bindpassword": "pass",
        "ldap_user_basedn": "DC=domain,DC=int",
        "ldap_user_subtree": True,
        "ldap_user_filter": "(objectClass=user)",
        "ldap_username_attribute": "sAMAccountName",
        "deleted_user_mode": "lock",
        "group_role_map": None,
    }
    base.update(overrides)
    return base


def test_main_default_profile_fails(monkeypatch):
    """main(): user_profile='DEFAULT' → fail_json (lines 256-257)."""
    mod = _load()
    Mod = _make_ldap_mod(_ldap_params(user_profile="default"))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "dedicated profile" in exc.value.args[0]["msg"]


def test_main_system_tablespace_fails(monkeypatch):
    """main(): user_default_tablespace='SYSTEM' → fail_json (lines 258-259)."""
    mod = _load()
    Mod = _make_ldap_mod(_ldap_params(user_default_tablespace="SYSTEM"))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "non-system tablespace" in exc.value.args[0]["msg"]


def test_main_sysaux_tablespace_fails(monkeypatch):
    """main(): user_default_tablespace='SYSAUX' → fail_json (lines 258-259)."""
    mod = _load()
    Mod = _make_ldap_mod(_ldap_params(user_default_tablespace="sysaux"))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "non-system tablespace" in exc.value.args[0]["msg"]


def test_main_oracledb_not_exists_fails(monkeypatch):
    """main(): oracledb_exists=False → fail_json (lines 261-262)."""
    mod = _load()
    monkeypatch.setattr(mod, "oracledb_exists", False, raising=False)
    Mod = _make_ldap_mod(_ldap_params())
    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "oracledb" in exc.value.args[0]["msg"]


def test_main_ldap_not_exists_fails(monkeypatch):
    """main(): ldap_module_exists=False → fail_json (lines 263-264)."""
    mod = _load()
    monkeypatch.setattr(mod, "oracledb_exists", True, raising=False)
    monkeypatch.setattr(mod, "ldap_module_exists", False, raising=False)
    Mod = _make_ldap_mod(_ldap_params())
    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "ldap" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# query_ldap_users tests (lines 203-221)
# ---------------------------------------------------------------------------

def _setup_ldap_globals(monkeypatch, mod, FakeLdap, users):
    """Set up the globals that query_ldap_users() needs."""
    class FakeLconn:
        def search_s(self, basedn, scope, filter_str, attrs):
            # Return strings (not bytes) — clean_string expects str, not bytes
            return [(("cn=%s,dc=domain" % u["sAMAccountName"]),
                    {"sAMAccountName": [u["sAMAccountName"]]})
                   for u in users]

    monkeypatch.setattr(mod, "ldap", FakeLdap, raising=False)
    monkeypatch.setattr(mod, "lconn", FakeLconn(), raising=False)
    monkeypatch.setattr(mod, "lparam", {
        "username": "sAMAccountName",
        "basedn": "dc=domain,dc=int",
        "subtree": True,
        "filter": "(objectClass=user)",
    }, raising=False)


def test_query_ldap_users_returns_users(monkeypatch):
    """query_ldap_users: LDAP search returns users → list of dicts (lines 203-221)."""
    mod = _load()

    class FakeLdap:
        SCOPE_SUBTREE = 2
        SCOPE_ONELEVEL = 1
        LDAPError = Exception

    fake_users = [{"sAMAccountName": "user1"}, {"sAMAccountName": "user2"}]

    class FakeMod(BaseFakeModule):
        params = {"group_role_map": None}

    monkeypatch.setattr(mod, "module", FakeMod(), raising=False)
    _setup_ldap_globals(monkeypatch, mod, FakeLdap, fake_users)

    users = mod.query_ldap_users()
    assert len(users) == 2
    assert users[0]["username"] == "USER1"
    assert users[1]["username"] == "USER2"


def test_query_ldap_users_filters_invalid(monkeypatch):
    """query_ldap_users: LDAP returns invalid names → filtered out (line 213, 217-218)."""
    mod = _load()

    class FakeLdap:
        SCOPE_SUBTREE = 2
        SCOPE_ONELEVEL = 1
        LDAPError = Exception

    class FakeLconn:
        def search_s(self, basedn, scope, filter_str, attrs):
            return [
                ("cn=valid,dc=domain", {"sAMAccountName": ["VALID1"]}),
                ("cn=123bad,dc=domain", {"sAMAccountName": ["123BAD"]}),  # invalid start
            ]

    class FakeMod(BaseFakeModule):
        params = {"group_role_map": None}

    monkeypatch.setattr(mod, "ldap", FakeLdap, raising=False)
    monkeypatch.setattr(mod, "lconn", FakeLconn(), raising=False)
    monkeypatch.setattr(mod, "lparam", {
        "username": "sAMAccountName",
        "basedn": "dc=domain,dc=int",
        "subtree": True,
        "filter": "(objectClass=user)",
    }, raising=False)
    monkeypatch.setattr(mod, "module", FakeMod(), raising=False)

    users = mod.query_ldap_users()
    assert len(users) == 1
    assert users[0]["username"] == "VALID1"


# ---------------------------------------------------------------------------
# main() comprehensive test with all dependencies mocked (lines 266-539)
# ---------------------------------------------------------------------------

class _FakeLdapModule:
    """Fake ldap Python module."""
    OPT_REFERRALS = 0
    SCOPE_SUBTREE = 2
    SCOPE_ONELEVEL = 1
    LDAPError = Exception

    class _FakeLconn:
        def set_option(self, option, value):
            pass

        def simple_bind_s(self, dn, password):
            pass

        def search_s(self, basedn, scope, filter_str, attrs):
            # Return strings (not bytes) — clean_string expects str
            return [("cn=user1,dc=domain", {"sAMAccountName": ["USER1"]})]

        def unbind(self):
            pass

    @classmethod
    def initialize(cls, url):
        return cls._FakeLconn()


class _FakeVar:
    def __init__(self, value=0):
        self._value = value

    def getvalue(self):
        return self._value


class _FakeCursor:
    def __init__(self):
        self.ddls = []

    def var(self, typ):
        return _FakeVar(0)

    def arrayvar(self, typ, values, size=None):
        return values

    def execute(self, sql, params=None):
        self.ddls.append(sql)


class _FakeOradbConn:
    def cursor(self):
        return _FakeCursor()

    def commit(self):
        pass


class _FakeOradb:
    """Fake oracledb module for oracle_ldapuser tests.

    Kept so that references to oracledb.STRING, oracledb.NUMBER, and
    oracledb.DatabaseError inside oracle_ldapuser.main() still resolve.
    """
    STRING = str
    NUMBER = int
    SYSDBA = 2
    DatabaseError = Exception

    @staticmethod
    def connect(*args, **kwargs):
        return _FakeOradbConn()

    @staticmethod
    def makedsn(**kwargs):
        return "fake_dsn"


class _FakeOracleConnection:
    """Fake oracleConnection(module) result.

    The refactored oracle_ldapuser.main() does:
        oc = oracleConnection(module)
        conn = oc.conn
    So this object must have a .conn attribute pointing to a raw DB connection,
    and a .version attribute.
    """

    def __init__(self, module):
        self.conn = _FakeOradbConn()
        self.version = "19.0.0"


def test_main_success_with_mocked_dependencies(monkeypatch):
    """main(): all dependencies mocked → runs through to exit_json (lines 266-539)."""
    mod = _load()

    monkeypatch.setattr(mod, "oracledb_exists", True, raising=False)
    monkeypatch.setattr(mod, "ldap_module_exists", True, raising=False)
    monkeypatch.setattr(mod, "ldap", _FakeLdapModule, raising=False)
    monkeypatch.setattr(mod, "oracledb", _FakeOradb, raising=False)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOracleConnection, raising=False)

    Mod = _make_ldap_mod(_ldap_params())
    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    # Should exit with the processed user list
    assert exc.value.args[0]["changed"] is False  # var_changes.getvalue() == 0


def test_main_check_mode_exits_early(monkeypatch):
    """main(): check_mode=True → exit_json early without DB ops (lines 322-326)."""
    mod = _load()

    monkeypatch.setattr(mod, "oracledb_exists", True, raising=False)
    monkeypatch.setattr(mod, "ldap_module_exists", True, raising=False)
    monkeypatch.setattr(mod, "ldap", _FakeLdapModule, raising=False)
    monkeypatch.setattr(mod, "oracledb", _FakeOradb, raising=False)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOracleConnection, raising=False)

    class CheckMod(BaseFakeModule):
        params = _ldap_params()
        check_mode = True

    monkeypatch.setattr(mod, "AnsibleModule", CheckMod)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    assert "Check mode" in exc.value.args[0]["msg"]


def test_main_no_users_found_fails(monkeypatch):
    """main(): LDAP returns no users → fail_json (line 352)."""
    mod = _load()

    monkeypatch.setattr(mod, "oracledb_exists", True, raising=False)
    monkeypatch.setattr(mod, "ldap_module_exists", True, raising=False)

    class EmptyLdap(_FakeLdapModule):
        class _FakeLconn(_FakeLdapModule._FakeLconn):
            def search_s(self, basedn, scope, filter_str, attrs):
                return []  # no users found

        @classmethod
        def initialize(cls, url):
            return cls._FakeLconn()

    monkeypatch.setattr(mod, "ldap", EmptyLdap, raising=False)
    monkeypatch.setattr(mod, "oracledb", _FakeOradb, raising=False)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOracleConnection, raising=False)

    Mod = _make_ldap_mod(_ldap_params())
    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "No users found in LDAP" in exc.value.args[0]["msg"]


def test_main_wallet_connection(monkeypatch):
    """main(): no user/password → wallet connection path (lines 287-293)."""
    mod = _load()

    monkeypatch.setattr(mod, "oracledb_exists", True, raising=False)
    monkeypatch.setattr(mod, "ldap_module_exists", True, raising=False)
    monkeypatch.setattr(mod, "ldap", _FakeLdapModule, raising=False)
    monkeypatch.setattr(mod, "oracledb", _FakeOradb, raising=False)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOracleConnection, raising=False)

    Mod = _make_ldap_mod(_ldap_params(user=None, password=None))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(ExitJson):
        mod.main()


def test_main_group_role_map(monkeypatch):
    """main(): group_role_map set → memberOf included in user processing (lines 336-348)."""
    mod = _load()

    monkeypatch.setattr(mod, "oracledb_exists", True, raising=False)
    monkeypatch.setattr(mod, "ldap_module_exists", True, raising=False)

    class LdapWithGroups(_FakeLdapModule):
        class _FakeLconn(_FakeLdapModule._FakeLconn):
            def search_s(self, basedn, scope, filter_str, attrs):
                return [("cn=user1,dc=domain", {
                    "sAMAccountName": ["USER1"],
                    "memberOf": ["CN=prod_db_reader,OU=SG,DC=domain,DC=int"],
                })]

        @classmethod
        def initialize(cls, url):
            return cls._FakeLconn()

    monkeypatch.setattr(mod, "ldap", LdapWithGroups, raising=False)
    monkeypatch.setattr(mod, "oracledb", _FakeOradb, raising=False)
    monkeypatch.setattr(mod, "oracleConnection", _FakeOracleConnection, raising=False)

    group_map = [{"dn": "CN=prod_db_reader,OU=SG,DC=domain,DC=int", "group": "prod_db_reader"}]
    Mod = _make_ldap_mod(_ldap_params(group_role_map=group_map))
    monkeypatch.setattr(mod, "AnsibleModule", Mod)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
