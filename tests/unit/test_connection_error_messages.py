import sys
import types

import pytest
from conftest import REPO_ROOT, FailJson, module_path


def test_oracle_utils_connection_errors_are_descriptive(monkeypatch):
    """Verify oracleConnection wraps DatabaseError with a helpful message."""
    import importlib.util

    # Ensure fake ansible.module_utils.basic is in place (conftest helper)
    from conftest import _ensure_fake_ansible_basic
    _ensure_fake_ansible_basic()

    # Build a fake oracledb whose connect() raises DatabaseError
    fake_oracledb = types.ModuleType("oracledb")

    class _FakeError:
        def __init__(self, message):
            self.message = message

    class _FakeDBError(Exception):
        pass

    fake_oracledb.DatabaseError = _FakeDBError
    fake_oracledb.ProgrammingError = type("ProgrammingError", (Exception,), {})
    fake_oracledb.SYSDBA = 2
    fake_oracledb.makedsn = lambda **kw: "fake_dsn"
    fake_oracledb.init_oracle_client = lambda **kw: None

    def _raise_connect(*a, **kw):
        err = _FakeError("DPI-1047: Cannot locate a 64-bit Oracle Client library")
        raise _FakeDBError(err)

    fake_oracledb.connect = _raise_connect

    monkeypatch.setitem(sys.modules, "oracledb", fake_oracledb)

    # Load oracle_utils freshly so it picks up the fake oracledb
    spec = importlib.util.spec_from_file_location(
        "oracle_utils_test",
        str(REPO_ROOT / "plugins" / "module_utils" / "oracle_utils.py"),
    )
    ou = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ou)

    # Build a minimal fake module
    captured = {}

    class FakeModule:
        params = dict(
            hostname="localhost", port=1521, service_name="svc",
            user="u", password="p", mode="normal",
            oracle_home=None, dsn=None, session_container=None,
        )

        def fail_json(self, **kwargs):
            captured.update(kwargs)
            raise FailJson(kwargs)

    with pytest.raises(FailJson):
        ou.oracleConnection(FakeModule())

    assert "Could not connect to database" in captured["msg"]
    assert "DPI-1047" in captured["msg"]


LEGACY_MODULES = [
    "oracle_job.py",
    "oracle_jobclass.py",
    "oracle_jobschedule.py",
    "oracle_jobwindow.py",
    "oracle_ldapuser.py",
    "oracle_privs.py",
    "oracle_rsrc_consgroup.py",
]


def test_legacy_modules_use_oracleConnection():
    """Verify refactored modules use oracleConnection instead of inline connect."""
    for module_name in LEGACY_MODULES:
        content = module_path("plugins", "modules", module_name).read_text(
            encoding="utf-8", errors="ignore"
        )
        assert "oracleConnection" in content, (
            "%s should use oracleConnection from oracle_utils" % module_name
        )
