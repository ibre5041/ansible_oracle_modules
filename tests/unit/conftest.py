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


def _ensure_fake_ansible_basic():
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

    # Inject a minimal fake oracle_utils so modules that do
    #   from ansible_collections...oracle_utils import oracleConnection
    # get a stub oracleConnection.  Individual tests monkeypatch mod.oracleConnection
    # to control behaviour.
    _ou_path = "ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils"
    if _ou_path not in sys.modules:
        class _StubOracleConnection:
            """Stub that raises RuntimeError — tests must monkeypatch mod.oracleConnection."""
            def __init__(self, module):
                raise RuntimeError(
                    "oracleConnection called without monkeypatching — "
                    "set monkeypatch.setattr(mod, 'oracleConnection', FakeOC) in the test."
                )

        _ou_mod = types.ModuleType(_ou_path)
        _ou_mod.oracleConnection = _StubOracleConnection
        _ou_mod.sanitize_string_params = lambda _params: None
        sys.modules[_ou_path] = _ou_mod

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

