"""Shared test helpers for ansible_oracle_modules unit tests."""
from datetime import timedelta

from conftest import ExitJson, FailJson


class BaseFakeModule:
    """Minimal AnsibleModule replacement for unit tests.

    Subclass and set ``params`` as a class-level dict before calling main():

        class FakeModule(BaseFakeModule):
            params = {**BASE_CONN_PARAMS, "role": "MYROLE", "state": "present", ...}
    """

    params = {}
    check_mode = False

    def __init__(self, **_kwargs):
        self.params = dict(self.__class__.params)
        self._warnings = []
        self._verbosity = 0

    def exit_json(self, **kwargs):
        raise ExitJson(kwargs)

    def fail_json(self, *args, **kwargs):
        if args:
            kwargs.setdefault("msg", args[0])
        raise FailJson(kwargs)

    def warn(self, msg):
        self._warnings.append(msg)

    def run_command(self, command, **_kwargs):
        """Default stub – override per test."""
        return (0, "", "")


class BaseFakeConn:
    """Minimal oracleConnection replacement for unit tests.

    Attributes
    ----------
    data :
        Return value for execute_select_to_dict / execute_select.
        For fetchone=True calls the first element is returned (or {} / () for
        empty list).  Override per-test to simulate different DB states.
    """

    def __init__(self, module):
        self.changed = False
        self.ddls = []
        self.data = []          # list of dicts (execute_select_to_dict)
        self.rows = []          # list of tuples (execute_select)
        self.version = "19.0.0"
        self.module = module
        self.container = None

    # ---- standard oracleConnection API --------------------------------

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        if fetchone:
            return self.data[0] if self.data else {}
        return self.data

    def execute_select(self, sql, params=None, fetchone=False):
        if fetchone:
            return self.rows[0] if self.rows else ()
        return self.rows

    def execute_ddl(self, request, params=None, no_change=False, ignore_errors=None, ddls_entry=None):
        self._last_executed_ddl = request
        trace = ddls_entry if ddls_entry is not None else request
        self.ddls.append(trace)
        if not no_change:
            self.changed = True

    def execute_statement(self, sql, params=None):
        self.ddls.append(sql)
        self.changed = True
        return []

    def set_container(self, pdb_name):
        self.container = pdb_name

    def fail_json(self, *args, **kwargs):
        """Some modules call conn.fail_json directly."""
        if args:
            kwargs.setdefault("msg", args[0])
        raise FailJson(kwargs)

    def resolve_object_name(self, object_name):
        """Default: return the name unchanged (no synonym resolution)."""
        return object_name


# ---------------------------------------------------------------------------
# Standard connection params dict – merge with module-specific params
# ---------------------------------------------------------------------------

BASE_CONN_PARAMS = dict(
    user="u",
    password="p",
    mode="normal",
    hostname="localhost",
    port=1521,
    service_name="svc",
    dsn=None,
    oracle_home=None,
    session_container=None,
)


# ---------------------------------------------------------------------------
# Helpers for AWR-style timedelta return data
# ---------------------------------------------------------------------------

def awr_result(interval_min=60, retention_days=8, dbid=1234):
    """Return a dict that looks like a dba_hist_wr_control row."""
    return {
        "snap_interval": timedelta(minutes=interval_min),
        "retention": timedelta(days=retention_days),
        "dbid": dbid,
        "con_id": 0,
    }


# ---------------------------------------------------------------------------
# Sequenced FakeConn – returns different responses per call index
# ---------------------------------------------------------------------------

class SequencedFakeConn(BaseFakeConn):
    """FakeConn that returns responses from a list in order.

    Set ``responses`` to a list of dicts.  Each call to
    ``execute_select_to_dict`` pops the first entry; when the list is
    exhausted, returns ``{}`` (fetchone) or ``[]`` (fetchall).

    Usage::

        conn = SequencedFakeConn(module)
        conn.responses = [
            {'name': 'open_cursors', 'current_value': '300', ...},  # 1st call
            {'name': 'open_cursors', 'spfile_value': '300'},         # 2nd call
        ]
    """

    def __init__(self, module):
        super().__init__(module)
        self.responses = []

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        if self.responses:
            r = self.responses.pop(0)
            return r if fetchone else ([r] if r else [])
        return {} if fetchone else []


# ---------------------------------------------------------------------------
# Fake oracledb module stub (for modules that call oracledb.connect directly)
# ---------------------------------------------------------------------------

class _FakeVar:
    def __init__(self, value=None):
        self._value = value

    def getvalue(self):
        return self._value


class _FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self.vars = {}

    def var(self, typ):
        v = _FakeVar()
        return v

    def arrayvar(self, typ, values, size=None):
        """Stub for oracledb arrayvar – returns the values list unchanged."""
        return values

    def execute(self, sql, params=None):
        self._conn.ddls.append(sql)

    def fetchone(self):
        return self._conn._fetchone_row

    def fetchall(self):
        return self._conn._fetchall_rows

    def close(self):
        pass

    def callfunc(self, name, return_type, args=None):
        return None

    @property
    def rowcount(self):
        """1 if _fetchone_row was set (simulates a matching row), else 0."""
        return 1 if self._conn._fetchone_row is not None else 0


class FakeOracleConn:
    """Raw oracledb.connect()-style connection for modules using cursor API."""

    NUMBER = int
    STRING = str

    def __init__(self):
        self.changed = False
        self.ddls = []
        self.version = "19.0.0"
        self._fetchone_row = None
        self._fetchall_rows = []
        self.outputtypehandler = None
        self.autocommit = True

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        pass

    def close(self):
        pass


class SequencedFakeOracleConn(FakeOracleConn):
    """FakeOracleConn that returns different fetchall() results per call.

    Set ``fetchall_sequence`` to a list of lists; each call to
    cursor.fetchall() pops the first entry.  When exhausted, returns
    ``_fetchall_rows``.
    """

    def __init__(self, fetchall_sequence=None):
        super().__init__()
        self._fetchall_seq = list(fetchall_sequence) if fetchall_sequence else []

    def cursor(self):
        return _SeqFakeCursor(self)


class _SeqFakeCursor(_FakeCursor):
    def fetchall(self):
        if self._conn._fetchall_seq:
            return self._conn._fetchall_seq.pop(0)
        return self._conn._fetchall_rows

    def fetchone(self):
        if self._conn._fetchall_seq:
            result = self._conn._fetchall_seq.pop(0)
            return result[0] if result else None
        return self._conn._fetchone_row


class FakeOracleDb:
    """Mock for the oracledb module itself."""

    NUMBER = int
    STRING = str
    SYSDBA = 2
    DatabaseError = Exception

    @staticmethod
    def connect(*args, **kwargs):
        return FakeOracleConn()

    @staticmethod
    def makedsn(**kwargs):
        return "fake_dsn"


# ---------------------------------------------------------------------------
# Fake OracleHomes stub (for CRS/ASM modules that call OracleHomes())
# ---------------------------------------------------------------------------

class FakeOracleHomes:
    """Minimal OracleHomes replacement for unit tests of CRS/ASM modules.

    Set attributes to simulate a GI-managed environment:
        oracle_gi_managed = True   (default)
        crs_home          = "/fake/grid"
        crsctl            = "/fake/grid/bin/crsctl"
        oracle_crs        = True
    """

    def __init__(self):
        self.crs_home = "/fake/grid"
        self.crsctl = "/fake/grid/bin/crsctl"
        self.oracle_gi_managed = True
        self.oracle_crs = False   # False = HAS (single-instance), avoids olsnodes calls
        self.facts_item = {}

    def list_crs_instances(self):
        pass

    def list_processes(self):
        pass

    def parse_oratab(self):
        pass
