import re
from pathlib import Path

from conftest import module_path


CORE_MODULES = [
    "oracle_sql.py",
    "oracle_sqldba.py",
    "oracle_user.py",
    "oracle_role.py",
    "oracle_grant.py",
    "oracle_privs.py",
    "oracle_profile.py",
    "oracle_parameter.py",
    "oracle_tablespace.py",
    "oracle_directory.py",
    "oracle_stats_prefs.py",
    "oracle_pdb.py",
]


def _read_module(name):
    return module_path("plugins", "modules", name).read_text(encoding="utf-8", errors="ignore")


def test_core_modules_have_no_bare_except():
    bare_except = re.compile(r"^\s*except\s*:\s*$", re.MULTILINE)
    offenders = []
    for module_name in CORE_MODULES:
        content = _read_module(module_name)
        if bare_except.search(content):
            offenders.append(module_name)
    assert offenders == []


def test_core_modules_have_documentation_and_examples():
    for module_name in CORE_MODULES:
        content = _read_module(module_name)
        assert "DOCUMENTATION" in content
        assert "EXAMPLES" in content


def test_pdb_local_routing_contract_present_for_core():
    sql_content = _read_module("oracle_sql.py")
    grant_content = _read_module("oracle_grant.py")
    pdb_content = _read_module("oracle_pdb.py")

    assert "pdb_name" in sql_content
    assert "set_container(" in sql_content
    assert "set_container(" in grant_content
    assert "set_container(" in pdb_content
