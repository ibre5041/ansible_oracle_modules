"""Unit tests for oracle_dblink module."""
import pytest

from conftest import ExitJson, FailJson, load_module_from_path, module_path
from helpers import BASE_CONN_PARAMS, BaseFakeConn, BaseFakeModule


def _load():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_dblink.py"), "oracle_dblink_test"
    )


def _dblink_params(**overrides):
    base = {
        **BASE_CONN_PARAMS,
        "state": "present",
        "link_name": "TEST_LINK",
        "link_type": "private",
        "connect_user": None,
        "connect_password": None,
        "connect_using": "remote_db",
        "current_user": False,
    }
    base.update(overrides)
    return base


class _DblinkConn(BaseFakeConn):
    """Simulates DBA_DB_LINKS query results."""

    def __init__(self, module, dblink_rows=None):
        super().__init__(module)
        self._dblink_rows = dblink_rows if dblink_rows is not None else []

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        return self._dblink_rows


# ---------------------------------------------------------------------------
# Sample rows
# ---------------------------------------------------------------------------

_PRIVATE_LINK_ROW = {
    "owner": "SCOTT",
    "db_link": "TEST_LINK",
    "username": "REMOTE_USER",
    "host": "remote_db",
    "created": "2024-01-01",
}

_PUBLIC_LINK_ROW = {
    "owner": "PUBLIC",
    "db_link": "TEST_LINK",
    "username": "REMOTE_USER",
    "host": "remote_db",
    "created": "2024-01-01",
}


# ===========================================================================
# Tests: state=status
# ===========================================================================

def test_dblink_status(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(state="status")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection",
        lambda m: _DblinkConn(m, dblink_rows=[_PRIVATE_LINK_ROW]),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert result["exists"] is True
    assert result["dblink"] == [_PRIVATE_LINK_ROW]


def test_dblink_status_not_exists(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(state="status")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(
        mod, "oracleConnection",
        lambda m: _DblinkConn(m, dblink_rows=[]),
        raising=False,
    )

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert result["exists"] is False
    assert result["dblink"] == []


# ===========================================================================
# Tests: state=present (create)
# ===========================================================================

def test_dblink_create_private(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(
            state="present",
            link_type="private",
            connect_user="REMOTE_USER",
            connect_password="secret",
            connect_using="remote_db",
        )

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert "created" in result["msg"]
    assert len(conn.ddls) == 1
    ddl = conn.ddls[0]
    assert "CREATE DATABASE LINK TEST_LINK" in ddl
    assert "PUBLIC" not in ddl
    assert "CONNECT TO REMOTE_USER IDENTIFIED BY" in ddl
    assert 'IDENTIFIED BY "********"' in ddl
    assert "secret" not in ddl
    assert "USING 'remote_db'" in ddl


def test_dblink_create_escapes_double_quote_in_password(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(
            state="present",
            connect_user="REMOTE_USER",
            connect_password='p"a"ss',
            connect_using="remote_db",
        )

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    ddl = conn.ddls[0]
    assert 'IDENTIFIED BY "********"' in ddl
    assert 'p"a"ss' not in ddl
    assert 'IDENTIFIED BY "p""a""ss"' in conn._last_executed_ddl


def test_dblink_create_escapes_quote_in_connect_using(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(
            state="present",
            connect_user="REMOTE_USER",
            connect_password="secret",
            connect_using="ORA$''@//host:1521/XEPDB1",
        )

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    ddl = conn.ddls[0]
    assert "USING 'ORA$''''@//host:1521/XEPDB1'" in ddl


def test_dblink_create_quotes_link_name_when_not_plain_identifier(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(
            state="present",
            link_name="EGG--INJECT",
            connect_user="REMOTE_USER",
            connect_password="secret",
            connect_using="remote_db",
        )

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    ddl = conn.ddls[0]
    assert 'DATABASE LINK "EGG--INJECT"' in ddl
    assert "USING 'remote_db'" in ddl


def test_dblink_create_quotes_connect_user_when_not_plain_identifier(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(
            state="present",
            connect_user="rem-user",
            connect_password="secret",
            connect_using="remote_db",
        )

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is True
    ddl = conn.ddls[0]
    assert 'CONNECT TO "rem-user" IDENTIFIED BY' in ddl


def test_dblink_create_public(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(
            state="present",
            link_type="public",
            connect_user="REMOTE_USER",
            connect_password="secret",
            connect_using="remote_db",
        )

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert "created" in result["msg"]
    ddl = conn.ddls[0]
    assert "CREATE PUBLIC DATABASE LINK TEST_LINK" in ddl
    assert "CONNECT TO REMOTE_USER IDENTIFIED BY" in ddl
    assert 'IDENTIFIED BY "********"' in ddl
    assert "secret" not in ddl
    assert "USING 'remote_db'" in ddl


def test_dblink_create_current_user(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(
            state="present",
            link_type="private",
            connect_user=None,
            connect_password=None,
            connect_using="remote_db",
            current_user=True,
        )

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert "created" in result["msg"]
    ddl = conn.ddls[0]
    assert "CREATE DATABASE LINK TEST_LINK" in ddl
    assert "CONNECT TO CURRENT_USER" in ddl
    assert "USING 'remote_db'" in ddl


def test_dblink_create_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(state="present")

    conn = _DblinkConn(Mod(), dblink_rows=[_PRIVATE_LINK_ROW])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert "already exists" in result["msg"]
    assert conn.ddls == []


def test_dblink_create_no_connect_using(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(state="present", connect_using=None)

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert "connect_using" in result["msg"]


def test_dblink_create_connect_user_without_password(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(
            state="present",
            connect_user="REMOTE_USER",
            connect_password=None,
            connect_using="remote_db",
        )

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert "connect_password" in result["msg"]
    assert conn.ddls == []


def test_dblink_create_connect_user_empty_password(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(
            state="present",
            connect_user="REMOTE_USER",
            connect_password="",
            connect_using="remote_db",
        )

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert "connect_password" in result["msg"]
    assert conn.ddls == []


def test_dblink_create_present_neither_fixed_nor_current_user(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(
            state="present",
            connect_user=None,
            connect_password=None,
            current_user=False,
            connect_using="remote_db",
        )

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert "current_user=true" in result["msg"]
    assert conn.ddls == []


def test_dblink_create_connect_user_and_current_user_mutually_exclusive(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(
            state="present",
            connect_user="REMOTE_USER",
            connect_password="secret",
            connect_using="remote_db",
            current_user=True,
        )

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert "mutually exclusive" in result["msg"]
    assert conn.ddls == []


def test_dblink_create_check_mode_no_ddl(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(
            state="present",
            connect_user="REMOTE_USER",
            connect_password="secret",
            connect_using="remote_db",
        )
        check_mode = True

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert "check mode" in result["msg"]
    assert conn.ddls == []
    assert len(result["ddls"]) == 1
    preview = result["ddls"][0]
    assert preview.startswith("--CREATE ")
    assert "IDENTIFIED BY \"********\"" in preview
    assert "secret" not in preview


# ===========================================================================
# Tests: state=absent (drop)
# ===========================================================================

def test_dblink_drop(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(state="absent", link_type="private")

    conn = _DblinkConn(Mod(), dblink_rows=[_PRIVATE_LINK_ROW])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert "dropped" in result["msg"]
    assert len(conn.ddls) == 1
    ddl = conn.ddls[0]
    assert "DROP DATABASE LINK TEST_LINK" in ddl
    assert "PUBLIC" not in ddl


def test_dblink_drop_public(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(state="absent", link_type="public")

    conn = _DblinkConn(Mod(), dblink_rows=[_PUBLIC_LINK_ROW])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert "dropped" in result["msg"]
    ddl = conn.ddls[0]
    assert "DROP PUBLIC DATABASE LINK TEST_LINK" in ddl


def test_dblink_drop_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(state="absent")

    conn = _DblinkConn(Mod(), dblink_rows=[])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert "does not exist" in result["msg"]
    assert conn.ddls == []


def test_dblink_drop_check_mode_no_ddl(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dblink_params(state="absent", link_type="private")
        check_mode = True

    conn = _DblinkConn(Mod(), dblink_rows=[_PRIVATE_LINK_ROW])
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: conn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert "check mode" in result["msg"]
    assert conn.ddls == []
    assert result["ddls"] == ["--DROP DATABASE LINK TEST_LINK"]
