from conftest import module_path


def test_sqldba_keeps_local_pdb_alter_session_feature():
    content = module_path("plugins", "modules", "oracle_sqldba.py").read_text(encoding="utf-8", errors="ignore")
    assert "alter session set container =" in content


def test_sqldba_masks_password_in_error_messages():
    content = module_path("plugins", "modules", "oracle_sqldba.py").read_text(encoding="utf-8", errors="ignore")
    assert "safe_sql_cmd" in content
    assert "'********'" in content


def test_sqldba_uses_oracle_sid_not_oracle_home():
    content = module_path("plugins", "modules", "oracle_sqldba.py").read_text(encoding="utf-8", errors="ignore")
    assert "os.environ['ORACLE_SID'] = oracle_sid.rstrip('/')" in content
    assert "os.environ['ORACLE_SID'] = oracle_home.rstrip('/')" not in content
