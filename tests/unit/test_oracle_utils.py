from conftest import FailJson, module_path, load_module_from_path


class DummyModule:
    def __init__(self, check_mode=False):
        self.check_mode = check_mode
        self._verbosity = 0
        self.failed = None
        self.warnings = []

    def fail_json(self, **kwargs):
        self.failed = kwargs
        raise FailJson(kwargs)

    def warn(self, _msg):
        self.warnings.append(_msg)
        return None


def _new_conn_instance(utils_module, check_mode=False):
    conn = utils_module.oracleConnection.__new__(utils_module.oracleConnection)
    conn.module = DummyModule(check_mode=check_mode)
    conn.conn = None
    conn.ddls = []
    conn.changed = False
    return conn


def test_execute_ddl_marks_changed_in_check_mode():
    utils = load_module_from_path(module_path("plugins", "module_utils", "oracle_utils.py"), "oracle_utils_test_1")
    conn = _new_conn_instance(utils, check_mode=True)

    conn.execute_ddl("create user foo identified by bar")

    assert conn.changed is True
    assert conn.ddls[0].startswith("--")


def test_set_container_rejects_invalid_name():
    utils = load_module_from_path(module_path("plugins", "module_utils", "oracle_utils.py"), "oracle_utils_test_2")
    conn = _new_conn_instance(utils, check_mode=True)

    try:
        conn.set_container("BAD NAME")
    except FailJson as exc:
        payload = exc.args[0]
        assert "Invalid pdb_name" in payload["msg"]
    else:
        raise AssertionError("set_container should fail on invalid pdb name")


class _DummyCursor:
    def execute(self, _sql, _params=None):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


class _DummyConn:
    def cursor(self):
        return _DummyCursor()


def test_set_container_valid_does_not_mark_changed_in_check_mode():
    utils = load_module_from_path(module_path("plugins", "module_utils", "oracle_utils.py"), "oracle_utils_test_3")
    conn = _new_conn_instance(utils, check_mode=True)
    conn.conn = _DummyConn()

    conn.set_container("PDB1")

    assert conn.changed is False
    assert conn.ddls == []


def test_execute_statement_check_mode_records_statement():
    utils = load_module_from_path(module_path("plugins", "module_utils", "oracle_utils.py"), "oracle_utils_test_4")
    conn = _new_conn_instance(utils, check_mode=True)

    out = conn.execute_statement("begin null; end;")

    assert out == []
    assert conn.ddls == ["--begin null; end;"]


def test_ensure_oracle_client_tries_oracle_home_lib_first():
    """When oracle_home is given, $ORACLE_HOME/lib is tried before $ORACLE_HOME itself."""
    import os
    utils = load_module_from_path(module_path("plugins", "module_utils", "oracle_utils.py"), "oracle_utils_test_lib_dir")
    module = DummyModule(check_mode=False)

    tried_lib_dirs = []

    class FakeOracleDb:
        class ProgrammingError(Exception):
            pass

        class DatabaseError(Exception):
            pass

        @staticmethod
        def init_oracle_client(**kwargs):
            tried_lib_dirs.append(kwargs.get("lib_dir"))
            # Succeed on the first call to stop iteration
            return None

    utils.oracledb_exists = True
    utils.oracledb = FakeOracleDb

    utils._ensure_oracle_client(module, oracle_home="/u01/app/oracle/product/19c/dbhome_1", required=True)

    # First candidate must be ORACLE_HOME/lib (full DB install)
    assert tried_lib_dirs[0] == os.path.join("/u01/app/oracle/product/19c/dbhome_1", "lib")


def test_ensure_oracle_client_falls_back_to_oracle_home_direct():
    """When $ORACLE_HOME/lib fails, $ORACLE_HOME is tried (Instant Client compat)."""
    import os
    utils = load_module_from_path(module_path("plugins", "module_utils", "oracle_utils.py"), "oracle_utils_test_fallback")
    module = DummyModule(check_mode=False)

    tried_lib_dirs = []

    class FakeErrorObj:
        message = "DPI-1047: Oracle Client library cannot be loaded"

    class FakeOracleDb:
        class ProgrammingError(Exception):
            pass

        class DatabaseError(Exception):
            pass

        @staticmethod
        def init_oracle_client(**kwargs):
            tried_lib_dirs.append(kwargs.get("lib_dir"))
            if kwargs.get("lib_dir", "").endswith("/lib"):
                # First candidate fails (no libs in ORACLE_HOME/lib)
                raise FakeOracleDb.DatabaseError(FakeErrorObj())
            # Second candidate succeeds (Instant Client layout)
            return None

    utils.oracledb_exists = True
    utils.oracledb = FakeOracleDb

    result = utils._ensure_oracle_client(module, oracle_home="/opt/oracle/instantclient_21_1", required=True)

    assert result is True
    assert len(tried_lib_dirs) == 2
    assert tried_lib_dirs[0] == os.path.join("/opt/oracle/instantclient_21_1", "lib")
    assert tried_lib_dirs[1] == "/opt/oracle/instantclient_21_1"


def test_ensure_oracle_client_falls_back_to_system_default():
    """When both ORACLE_HOME/lib and ORACLE_HOME fail, system default (no lib_dir) is tried."""
    utils = load_module_from_path(module_path("plugins", "module_utils", "oracle_utils.py"), "oracle_utils_test_sysdefault")
    module = DummyModule(check_mode=False)

    tried_lib_dirs = []

    class FakeErrorObj:
        message = "DPI-1047: Oracle Client library cannot be loaded"

    class FakeOracleDb:
        class ProgrammingError(Exception):
            pass

        class DatabaseError(Exception):
            pass

        @staticmethod
        def init_oracle_client(**kwargs):
            tried_lib_dirs.append(kwargs.get("lib_dir"))
            if "lib_dir" in kwargs:
                raise FakeOracleDb.DatabaseError(FakeErrorObj())
            # System default succeeds (LD_LIBRARY_PATH has the right path)
            return None

    utils.oracledb_exists = True
    utils.oracledb = FakeOracleDb

    result = utils._ensure_oracle_client(module, oracle_home="/u01/app/oracle/product/19c/dbhome_1", required=True)

    assert result is True
    assert len(tried_lib_dirs) == 3
    assert tried_lib_dirs[2] is None  # System default (no lib_dir)


def test_ensure_oracle_client_optional_dpi1047_does_not_fail():
    utils = load_module_from_path(module_path("plugins", "module_utils", "oracle_utils.py"), "oracle_utils_test_5")
    module = DummyModule(check_mode=False)

    class FakeErrorObj:
        message = "DPI-1047: Oracle Client library cannot be loaded"

    class FakeOracleDb:
        class ProgrammingError(Exception):
            pass

        class DatabaseError(Exception):
            pass

        @staticmethod
        def init_oracle_client(**_kwargs):
            raise FakeOracleDb.DatabaseError(FakeErrorObj())

    utils.oracledb_exists = True
    utils.oracledb = FakeOracleDb

    initialized = utils._ensure_oracle_client(module, oracle_home="/no/client", required=False)
    assert initialized is False
    assert module.failed is None
    assert module.warnings == []


def test_ensure_oracle_client_required_dpi1047_fails():
    utils = load_module_from_path(module_path("plugins", "module_utils", "oracle_utils.py"), "oracle_utils_test_6")
    module = DummyModule(check_mode=False)

    class FakeErrorObj:
        message = "DPI-1047: Oracle Client library cannot be loaded"

    class FakeOracleDb:
        class ProgrammingError(Exception):
            pass

        class DatabaseError(Exception):
            pass

        @staticmethod
        def init_oracle_client(**_kwargs):
            raise FakeOracleDb.DatabaseError(FakeErrorObj())

    utils.oracledb_exists = True
    utils.oracledb = FakeOracleDb

    try:
        utils._ensure_oracle_client(module, oracle_home="/must/fail", required=True)
    except FailJson as exc:
        payload = exc.args[0]
        assert "DPI-1047" in payload["msg"]
    else:
        raise AssertionError("required thick mode should fail on DPI-1047")
