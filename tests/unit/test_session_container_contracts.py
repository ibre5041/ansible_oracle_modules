from conftest import module_path


DB_MODULES_WITH_SESSION_CONTAINER = [
    "oracle_awr.py",
    "oracle_db.py",
    "oracle_directory.py",
    "oracle_facts.py",
    "oracle_grant.py",
    "oracle_job.py",
    "oracle_jobclass.py",
    "oracle_jobschedule.py",
    "oracle_jobwindow.py",
    "oracle_ldapuser.py",
    "oracle_parameter.py",
    "oracle_pdb.py",
    "oracle_ping.py",
    "oracle_privs.py",
    "oracle_profile.py",
    "oracle_role.py",
    "oracle_rsrc_consgroup.py",
    "oracle_services.py",
    "oracle_sql.py",
    "oracle_tablespace.py",
    "oracle_user.py",
]


def test_all_db_modules_expose_session_container_argument():
    for filename in DB_MODULES_WITH_SESSION_CONTAINER:
        content = module_path("plugins", "modules", filename).read_text(encoding="utf-8", errors="ignore")
        assert "session_container" in content and "dict(required=False" in content, filename


def test_oracle_utils_applies_session_container_automatically():
    content = module_path("plugins", "module_utils", "oracle_utils.py").read_text(encoding="utf-8", errors="ignore")
    assert 'session_container = module.params.get("session_container")' in content
    assert "self.set_container(session_container)" in content


def test_sql_keeps_backward_compatibility_with_pdb_name():
    content = module_path("plugins", "modules", "oracle_sql.py").read_text(encoding="utf-8", errors="ignore")
    assert "(not session_container) and pdb_name" in content


def test_grant_keeps_backward_compatibility_with_container():
    content = module_path("plugins", "modules", "oracle_grant.py").read_text(encoding="utf-8", errors="ignore")
    assert "effective_container = session_container or container" in content


def test_oracle_user_container_semantics_are_preserved():
    content = module_path("plugins", "modules", "oracle_user.py").read_text(encoding="utf-8", errors="ignore")
    assert 'container     = dict(default=None, choices=["all", "current"])' in content
