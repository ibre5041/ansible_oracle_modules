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
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def module_path(*parts):
    return REPO_ROOT.joinpath(*parts)


def _ensure_fake_ansible_basic():
    if "ansible.module_utils.basic" in sys.modules:
        return

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
    text_mod.to_native = lambda v, **_kwargs: str(v)
    text_mod.to_text = lambda v, **_kwargs: str(v)

    sys.modules["ansible"] = ansible_mod
    sys.modules["ansible.module_utils"] = module_utils_mod
    sys.modules["ansible.module_utils.basic"] = basic_mod
    sys.modules["ansible.module_utils._text"] = text_mod

