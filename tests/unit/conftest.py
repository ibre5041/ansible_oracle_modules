import importlib.util
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class ExitJson(Exception):
    pass


class FailJson(Exception):
    pass


def load_module_from_path(module_path, module_name):
    _ensure_fake_ansible_basic()
    path = Path(module_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def module_path(*parts):
    return REPO_ROOT.joinpath(*parts)


_OU_PATH = "ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils"


def _sql_single_quoted_literal_stub(value):
    if value is None:
        return ''
    return str(value).replace("'", "''")


def _ensure_fake_oracle_utils():
    """Register (or patch) the collection shim so dynamic module loads always see required symbols."""
    if _OU_PATH not in sys.modules:
        class _StubOracleConnection:
            """Stub that raises RuntimeError — tests must monkeypatch mod.oracleConnection."""
            def __init__(self, module):
                raise RuntimeError(
                    "oracleConnection called without monkeypatching — "
                    "set monkeypatch.setattr(mod, 'oracleConnection', FakeOC) in the test."
                )

        _ou_mod = types.ModuleType(_OU_PATH)
        _ou_mod.oracleConnection = _StubOracleConnection
        _ou_mod.sanitize_string_params = lambda _params: None
        _ou_mod.sql_single_quoted_literal = _sql_single_quoted_literal_stub
        _ou_mod.build_force_clause = lambda fk: 'FORCE KEYSTORE ' if fk else ''
        _ou_mod.build_container_clause = lambda c: ' CONTAINER = ALL' if c == 'all' else ''

        def _build_backup(backup=True, backup_tag=None):
            if not backup:
                return ''
            clause = ' WITH BACKUP'
            if backup_tag:
                clause += " USING '%s'" % backup_tag
            return clause

        _ou_mod.build_backup_clause = _build_backup
        sys.modules[_OU_PATH] = _ou_mod
        return

    ou = sys.modules[_OU_PATH]
    if not hasattr(ou, 'sql_single_quoted_literal'):
        ou.sql_single_quoted_literal = _sql_single_quoted_literal_stub
    if not hasattr(ou, 'build_force_clause'):
        ou.build_force_clause = lambda fk: 'FORCE KEYSTORE ' if fk else ''
    if not hasattr(ou, 'build_container_clause'):
        ou.build_container_clause = lambda c: ' CONTAINER = ALL' if c == 'all' else ''

    if not hasattr(ou, 'build_backup_clause'):
        def _build_backup(backup=True, backup_tag=None):
            if not backup:
                return ''
            clause = ' WITH BACKUP'
            if backup_tag:
                clause += " USING '%s'" % backup_tag
            return clause
        ou.build_backup_clause = _build_backup


def _ensure_fake_ansible_basic():
    _ensure_fake_oracle_utils()

    if "ansible.module_utils.basic" in sys.modules:
        return

    # Inject a minimal fake oracledb so modules that do
    #   try: import oracledb / except ImportError: oracledb_exists = False
    # get oracledb_exists = True even when oracledb is not installed in the
    # test environment.  Individual tests can still monkeypatch mod.oracledb
    # or mod.oracledb_exists to control behaviour.
    if "oracledb" not in sys.modules:
        _fake_oracledb = types.ModuleType("oracledb")
        _fake_oracledb.DatabaseError = Exception
        _fake_oracledb.NUMBER = int
        _fake_oracledb.STRING = str
        _fake_oracledb.SYSDBA = 2
        _fake_oracledb.connect = lambda *a, **kw: None
        _fake_oracledb.makedsn = lambda **kw: "fake_dsn"
        sys.modules["oracledb"] = _fake_oracledb

    ansible_mod = types.ModuleType("ansible")
    module_utils_mod = types.ModuleType("ansible.module_utils")
    basic_mod = types.ModuleType("ansible.module_utils.basic")
    text_mod = types.ModuleType("ansible.module_utils._text")

    class _DummyAnsibleModule:  # pragma: no cover
        def __init__(self, **kwargs):
            raise RuntimeError("Test should monkeypatch AnsibleModule before use")

    def _missing_required_lib(name):
        return "missing library: %s" % name

    basic_mod.AnsibleModule = _DummyAnsibleModule
    basic_mod.missing_required_lib = _missing_required_lib
    basic_mod.to_bytes = lambda v, **_kwargs: v.encode() if isinstance(v, str) else v
    basic_mod.to_native = lambda v, **_kwargs: str(v)
    basic_mod.os = __import__("os")
    basic_mod.re = __import__("re")
    text_mod.to_native = lambda v, **_kwargs: str(v)
    text_mod.to_text = lambda v, **_kwargs: str(v)

    sys.modules["ansible"] = ansible_mod
    sys.modules["ansible.module_utils"] = module_utils_mod
    sys.modules["ansible.module_utils.basic"] = basic_mod
    sys.modules["ansible.module_utils._text"] = text_mod

