from conftest import module_path


def test_oracle_utils_connection_errors_are_descriptive():
    """Verify oracleConnection in oracle_utils has proper error handling."""
    content = module_path("plugins", "module_utils", "oracle_utils.py").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert "Could not connect to database" in content
    assert "DPI-1047" in content


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
