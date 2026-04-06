from conftest import module_path


MODULES = [
    "oracle_job.py",
    "oracle_jobclass.py",
    "oracle_jobschedule.py",
    "oracle_jobwindow.py",
    "oracle_ldapuser.py",
    "oracle_privs.py",
    "oracle_rsrc_consgroup.py",
]


def test_connection_error_messages_are_sanitized():
    for module_name in MODULES:
        content = module_path("plugins", "modules", module_name).read_text(encoding="utf-8", errors="ignore")
        assert "connect descriptor" not in content
        assert "Oracle connection failed" in content
        assert "DPI-1047" in content
