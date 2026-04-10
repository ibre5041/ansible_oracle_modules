import re
from pathlib import Path

from conftest import module_path


def _module_files():
    modules_dir = module_path("plugins", "modules")
    return sorted(p for p in modules_dir.glob("oracle_*.py"))


def test_all_modules_keep_original_name_prefix():
    files = _module_files()
    assert files, "expected at least one plugins/modules/oracle_*.py module"
    for module_file in files:
        assert module_file.name.startswith("oracle_")


def test_all_modules_have_minimum_contract_blocks():
    for module_file in _module_files():
        content = module_file.read_text(encoding="utf-8", errors="ignore")
        assert "DOCUMENTATION" in content, module_file.name
        assert "EXAMPLES" in content, module_file.name
        assert "def main(" in content, module_file.name


def test_all_modules_no_bare_except_blocks():
    bare_except = re.compile(r"^\s*except\s*:\s*$", re.MULTILINE)
    offenders = []
    for module_file in _module_files():
        content = module_file.read_text(encoding="utf-8", errors="ignore")
        if bare_except.search(content):
            offenders.append(module_file.name)
    assert offenders == []


def test_all_password_fields_are_no_log():
    missing = []
    for module_file in _module_files():
        lines = module_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in lines:
            if re.search(r"\bpassword\s*=\s*dict\(", line) and "no_log" not in line:
                missing.append(module_file.name)
    assert missing == []
