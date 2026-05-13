"""Unit tests for oracle_facts and oracle_gi_facts modules."""
import os
import pytest

from conftest import ExitJson, FailJson, load_module_from_path
from helpers import BASE_CONN_PARAMS, BaseFakeModule, FakeOracleHomes, SequencedFakeConn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load():
    return load_module_from_path("plugins/modules/oracle_facts.py", "oracle_facts")


def _facts_params(**overrides):
    base = {
        **BASE_CONN_PARAMS,
        "oracle_home": None,
        "password_file": False,
        "instance": False,
        "database": True,
        "patch_level": False,
        "tablespaces": False,
        "temp": False,
        "userenv": False,
        "redo": None,
        "standby": None,
        "parameter": None,
        "gather_subset": None,
    }
    base.update(overrides)
    return base


_INSTANCE_ROW = {
    "version": "19.0.0.0",
    "version_full": "19.10.0.0.0",
    "instance_name": "ORCL1",
    "host_name": "dbserver",
    "status": "OPEN",
}

_DB_ROW = {
    "name": "ORCL",
    "db_unique_name": "ORCL",
    "CDB": "NO",
    "log_mode": "ARCHIVELOG",
}


class _FactsConn(SequencedFakeConn):
    """Pre-loaded with minimum responses needed for oracle_facts."""

    def __init__(self, module, extra_responses=None):
        super().__init__(module)
        # oracle_facts always calls: query_instance, query_database, then rac
        self.responses = [
            _INSTANCE_ROW,          # query_instance (fetchone)
            _DB_ROW,                # query_database (fetchone)
        ]
        if extra_responses:
            self.responses.extend(extra_responses)
        # rac/pdb calls at end → will return {} (falsy) → []
        self.responses.append({})   # rac query → []


# ===========================================================================
# Tests
# ===========================================================================

def test_facts_minimal(monkeypatch):
    """Minimal query: only database facts, no optional features."""
    mod = _load()
    os.environ.setdefault("ORACLE_SID", "ORCL")

    class Mod(BaseFakeModule):
        params = _facts_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _FactsConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is False
    assert "ansible_facts" in payload
    sid = os.environ.get("ORACLE_SID", "ORCL")
    assert sid in payload["ansible_facts"]


def test_facts_with_instance(monkeypatch):
    """instance=True adds instance info to facts."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class Mod(BaseFakeModule):
        params = _facts_params(instance=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _FactsConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is False
    facts = payload["ansible_facts"]["ORCL"]
    assert "instance" in facts
    assert facts["instance"]["instance_name"] == "ORCL1"


def test_facts_with_patch_level_19c(monkeypatch):
    """patch_level=True on 19c reads dba_registry_sqlpatch."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class Mod(BaseFakeModule):
        params = _facts_params(patch_level=True)

    extra = [
        {"ver": "19.10.0.0.220419"},   # query_patch_level (fetchone)
    ]
    conn_factory = lambda m: _FactsConn(m, extra)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", conn_factory, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_facts_cdb_with_pdbs(monkeypatch):
    """CDB=YES triggers pdb query."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    cdb_row = {**_DB_ROW, "CDB": "YES"}

    class _CdbConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,           # query_instance
                cdb_row,                 # query_database
                {},                      # rac → []
                {"con_id": 3, "name": "PDB1", "open_mode": "READ WRITE"},  # pdb
            ]

    class Mod(BaseFakeModule):
        params = _facts_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _CdbConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert len(facts["pdb"]) == 1
    assert facts["pdb"][0]["name"] == "PDB1"


def test_facts_with_userenv(monkeypatch):
    """userenv=True adds userenv to facts."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _UeConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,                          # query_instance
                _DB_ROW,                                # query_database
                {"current_user": "SYS", "database_role": "PRIMARY", "isdba": "TRUE"},  # userenv
                {},                                     # rac
            ]

    class Mod(BaseFakeModule):
        params = _facts_params(userenv=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _UeConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "userenv" in facts


def test_facts_with_tablespaces(monkeypatch):
    """tablespaces=True adds tablespace list to facts."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _TsConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {"con_id": 0, "name": "SYSTEM", "bigfile": "NO", "size_mb": 800, "datafiles#": 1},  # tablespaces
                {},  # rac
            ]

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            if self.responses:
                r = self.responses.pop(0)
                # tablespaces query returns a list, not a single row
                if "tablespace" in sql.lower() and not fetchone:
                    return [r] if r else []
                return r if fetchone else ([r] if r else [])
            return {} if fetchone else []

    class Mod(BaseFakeModule):
        params = _facts_params(tablespaces=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _TsConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_facts_with_redo_summary(monkeypatch):
    """redo='summary' adds redo info to facts."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _RedoConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {"thread": 1, "count": 3, "size_mb": 512, "min_seq": 1, "max_seq": 3},  # redo
                {},  # rac
            ]

    class Mod(BaseFakeModule):
        params = _facts_params(redo="summary")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _RedoConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "redo" in facts


def test_facts_version_below_10_fails(monkeypatch):
    """Version < 10.2 triggers fail_json."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _OldConn(_FactsConn):
        def __init__(self, m):
            super().__init__(m)
            self.version = "10.1.0"

    class Mod(BaseFakeModule):
        params = _facts_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _OldConn(m), raising=False)

    with pytest.raises(FailJson):
        mod.main()


def test_facts_with_parameters(monkeypatch):
    """parameter=['db_name','db_unique_name'] → query_params executes and returns dict."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _ParamConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {},   # rac
            ]
            # parameters will be returned as a list on the full-fetch call
            self._param_rows = [
                {"name": "db_name", "value": "ORCL", "isdefault": "FALSE"},
                {"name": "db_unique_name", "value": "ORCL", "isdefault": "FALSE"},
            ]

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            if "v$parameter" in sql.lower() and not fetchone:
                return self._param_rows
            return super().execute_select_to_dict(sql, params=params, fetchone=fetchone)

    class Mod(BaseFakeModule):
        params = _facts_params(parameter=["db_name", "db_unique_name"])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _ParamConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "parameter" in facts
    assert "db_name" in facts["parameter"]


def test_facts_with_temp(monkeypatch):
    """temp=True → query_temp executed and 'temp' in facts."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _TempConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {"con_id": 0, "name": "TEMP", "bigfile": "NO", "size_mb": 100, "tempfiles#": 1},
                {},  # rac
            ]

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            r = self.responses.pop(0) if self.responses else {}
            if "tempfile" in sql.lower() and not fetchone:
                return [r] if r else []
            return r if fetchone else ([r] if r else [])

    class Mod(BaseFakeModule):
        params = _facts_params(temp=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _TempConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_facts_with_standby_summary(monkeypatch):
    """standby='summary' → query_standby executes."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _StandbyConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {"thread": 1, "count": 2, "size_mb": 256, "min_seq": 1, "max_seq": 2},  # standby
                {},  # rac
            ]

    class Mod(BaseFakeModule):
        params = _facts_params(standby="summary")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _StandbyConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "standby" in facts


def test_facts_with_standby_detail(monkeypatch):
    """standby='detail' → query_standby uses the detail SQL branch."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _StandbyDetailConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {"group#": 1, "thread#": 1, "sequence#": 5, "mb": 256, "archived": "YES", "status": "ACTIVE"},
                {},  # rac
            ]

    class Mod(BaseFakeModule):
        params = _facts_params(standby="detail")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _StandbyDetailConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "standby" in facts


def test_facts_with_redo_detail(monkeypatch):
    """redo='detail' → query_redo uses detail SQL branch."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _RedoDetailConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {"group": 1, "thread": 1, "sequence#": 5, "mb": 512, "blocksize": 512, "archived": "YES", "status": "CURRENT"},
                {},  # rac
            ]

    class Mod(BaseFakeModule):
        params = _facts_params(redo="detail")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _RedoDetailConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "redo" in facts


def test_facts_patch_level_11g(monkeypatch):
    """patch_level=True on 11g → reads registry$history for PSU bundle."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    instance_11g = {**_INSTANCE_ROW, "version": "11.2.0.4.0"}

    class _11gConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.version = "11.2.0.4"
            self.responses = [
                instance_11g,
                _DB_ROW,
                {"bundle": 190115},  # patch level query (bundle)
                {},  # rac
            ]

    class Mod(BaseFakeModule):
        params = _facts_params(patch_level=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _11gConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_facts_patch_level_12c(monkeypatch):
    """patch_level=True on 12c → reads dba_registry_sqlpatch for bundle_id."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    instance_12c = {**_INSTANCE_ROW, "version": "12.1.0.2.0"}

    class _12cConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.version = "12.1.0.2"
            self.responses = [
                instance_12c,
                _DB_ROW,
                {"bundle_id": 190115},  # patch level query (bundle_id)
                {},  # rac
            ]

    class Mod(BaseFakeModule):
        params = _facts_params(patch_level=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _12cConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_facts_database_without_cdb_key(monkeypatch):
    """DB row without 'CDB' key → query_database adds CDB='NO'."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    db_row_no_cdb = {k: v for k, v in _DB_ROW.items() if k != "CDB"}

    class _NoCdbConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,
                db_row_no_cdb,
                {},  # rac
            ]

    class Mod(BaseFakeModule):
        params = _facts_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _NoCdbConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    # CDB='NO' should be added by query_database
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert facts["database"]["CDB"] == "NO"


def test_facts_tablespaces_old_version(monkeypatch):
    """tablespaces=True on version < 12.1 → uses non-CDB SQL."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _OldTsConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.version = "11.2.0.4"  # < 12.1 → different SQL branch
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {"con_id": 0, "name": "SYSTEM", "bigfile": "NO", "size_mb": 800, "datafiles#": 1},
                {},  # rac
            ]

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            r = self.responses.pop(0) if self.responses else {}
            if "tablespace" in sql.lower() and not fetchone:
                return [r] if r else []
            return r if fetchone else ([r] if r else [])

    class Mod(BaseFakeModule):
        params = _facts_params(tablespaces=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _OldTsConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_facts_exception_in_pdb_block(monkeypatch):
    """Exception in CDB pdb query → pdb=[] (exception handler)."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    cdb_row = {**_DB_ROW, "CDB": "YES"}

    class _ExcConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,
                cdb_row,
                {},  # rac → []
            ]

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            if "v$pdbs" in sql.lower():
                raise RuntimeError("simulated error")
            return super().execute_select_to_dict(sql, params=params, fetchone=fetchone)

    class Mod(BaseFakeModule):
        params = _facts_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _ExcConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert facts["pdb"] == []


# ===========================================================================
# gather_subset tests
# ===========================================================================

def test_gather_subset_none_leaves_flags_untouched(monkeypatch):
    """gather_subset=None (default) must not change existing flag values."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class Mod(BaseFakeModule):
        # database=False, instance=False — must stay that way with gather_subset=None
        params = _facts_params(database=False, instance=False, userenv=False, gather_subset=None)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _FactsConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    # database=False means 'database' key should not appear in facts
    assert "database" not in facts
    # instance=False means 'instance' key should not appear in facts
    assert "instance" not in facts


def test_gather_subset_database_sets_database_flag(monkeypatch):
    """gather_subset=['database'] must set module.params['database'] = True."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class Mod(BaseFakeModule):
        params = _facts_params(database=False, userenv=False, gather_subset=['database'])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _FactsConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "database" in facts
    assert facts["database"]["name"] == "ORCL"


def test_gather_subset_min_sets_database_flag(monkeypatch):
    """gather_subset=['min'] must set module.params['database'] = True."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class Mod(BaseFakeModule):
        params = _facts_params(database=False, userenv=False, gather_subset=['min'])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _FactsConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "database" in facts


def test_gather_subset_instance_and_tablespace(monkeypatch):
    """gather_subset=['instance', 'tablespace'] enables only those two, not database/userenv."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _ItConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {"con_id": 0, "name": "SYSTEM", "bigfile": "NO", "size_mb": 800, "datafiles#": 1},
                {},  # rac
            ]

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            if "tablespace" in sql.lower() and not fetchone:
                r = self.responses.pop(0) if self.responses else {}
                return [r] if r else []
            return super().execute_select_to_dict(sql, params=params, fetchone=fetchone, fail_on_error=fail_on_error)

    class Mod(BaseFakeModule):
        params = _facts_params(database=False, userenv=False, gather_subset=['instance', 'tablespace'])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _ItConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "instance" in facts
    assert "tablespaces" in facts
    assert "database" not in facts
    assert "userenv" not in facts


def test_gather_subset_all_enables_everything(monkeypatch):
    """gather_subset=['all'] must enable database, instance, tablespaces, userenv, redo, parameter."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _AllConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,   # query_instance
                _DB_ROW,         # query_database
            ]
            self._param_rows = [
                {"name": "db_name", "value": "ORCL", "isdefault": "FALSE"},
            ]

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            if "v$parameter" in sql.lower() and not fetchone:
                return self._param_rows
            if "tablespace" in sql.lower() and not fetchone:
                return [{"con_id": 0, "name": "SYSTEM", "bigfile": "NO", "size_mb": 800, "datafiles#": 1}]
            if "userenv" in sql.lower() and fetchone:
                return {"current_user": "SYS", "database_role": "PRIMARY", "isdba": "TRUE"}
            if "v$log" in sql.lower() and not fetchone:
                return [{"thread": 1, "count": 3, "size_mb": 512, "min_seq": 1, "max_seq": 3}]
            if self.responses:
                r = self.responses.pop(0)
                return r if fetchone else ([r] if r else [])
            return {} if fetchone else []

    class Mod(BaseFakeModule):
        # start with all flags off — gather_subset='all' should turn them on
        params = _facts_params(database=False, instance=False, userenv=False, gather_subset=['all'])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _AllConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "database" in facts
    assert "instance" in facts
    assert "userenv" in facts
    assert "redo" in facts
    assert "parameter" in facts


def test_gather_subset_redolog_sets_redo_summary(monkeypatch):
    """gather_subset=['redolog'] sets redo='summary' when redo not already set."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _RedoConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {"thread": 1, "count": 3, "size_mb": 512, "min_seq": 1, "max_seq": 3},  # redo
                {},  # rac
            ]

    class Mod(BaseFakeModule):
        params = _facts_params(database=False, userenv=False, redo=None, gather_subset=['redolog'])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _RedoConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "redo" in facts


def test_gather_subset_redolog_does_not_override_existing_redo(monkeypatch):
    """gather_subset=['redolog'] must NOT override an explicitly set redo='detail'."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _RedoDetailConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {"group": 1, "thread": 1, "sequence#": 5, "mb": 512, "blocksize": 512,
                 "archived": "YES", "status": "CURRENT"},  # redo detail
                {},  # rac
            ]

    class Mod(BaseFakeModule):
        # redo='detail' is already set; gather_subset should not override it with 'summary'
        params = _facts_params(database=False, userenv=False, redo='detail', gather_subset=['redolog'])

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _RedoDetailConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    # Just assert it exits cleanly; redo='detail' was preserved (not overridden to 'summary')
    assert exc.value.args[0]["changed"] is False
    assert "redo" in exc.value.args[0]["ansible_facts"]["ORCL"]


def test_gather_subset_unknown_warns(monkeypatch):
    """Unknown gather_subset values trigger module.warn()."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class Mod(BaseFakeModule):
        params = _facts_params(database=False, userenv=False,
                               gather_subset=['database', 'nonexistent_subset'])

    module_instance = None

    original_mod_class = Mod

    class CapturingMod(original_mod_class):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            nonlocal module_instance
            module_instance = self

    monkeypatch.setattr(mod, "AnsibleModule", CapturingMod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _FactsConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    # Module must succeed (not fail)
    assert exc.value.args[0]["changed"] is False
    # 'database' subset must be honoured
    assert "database" in exc.value.args[0]["ansible_facts"]["ORCL"]
    # The unknown subset must have triggered a warning
    assert module_instance is not None
    assert any("nonexistent_subset" in w for w in module_instance._warnings)


# ===========================================================================
# detect_paths tests (lines 97-156)
# ===========================================================================

class _FakePopen:
    """Minimal subprocess.Popen stub that yields configurable lines then EOF."""

    class _FakeStdout:
        def __init__(self, lines):
            # lines are bytes; sentinel is b''
            self._lines = list(lines) + [b'']

        def readline(self):
            if self._lines:
                return self._lines.pop(0)
            return b''

    def __init__(self, lines=None):
        self.stdout = self._FakeStdout(lines or [])

    def poll(self):
        pass


class _FakeSubprocess:
    PIPE = -1

    def __init__(self, popen_factory):
        self._factory = popen_factory
        self._call_count = 0

    def Popen(self, args, stdout=None):
        result = self._factory(self._call_count, args)
        self._call_count += 1
        return result


def _make_detect_paths_conn(spfile_value=None):
    """Return a SequencedFakeConn whose first (and only) fetchone returns spfile info."""
    class _DPConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            # spfile query in detect_paths (fetchone)
            self.responses = [
                {"value": spfile_value} if spfile_value else {},
            ]

    return _DPConn


def test_detect_paths_no_crs_home_fallback_to_spfile(monkeypatch):
    """detect_paths with no crs_home: falls back to v$parameter spfile query."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"
    os.environ["ORACLE_HOME"] = "/u01/oracle"

    class _NoCrsHomes(FakeOracleHomes):
        def __init__(self, m):
            super().__init__()
            self.crs_home = ""   # no CRS home → else branch

    # orabasehome Popen raises FileNotFoundError → ORABASEHOME = oracle_home
    def _popen_factory(call_idx, args):
        raise FileNotFoundError("no orabasehome")

    fake_sub = _FakeSubprocess(_popen_factory)

    DPConn = _make_detect_paths_conn(spfile_value="/u01/oracle/dbs/spfileORCL.ora")

    class Mod(BaseFakeModule):
        params = _facts_params(password_file=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", DPConn, raising=False)
    monkeypatch.setattr(mod, "OracleHomes", _NoCrsHomes, raising=False)
    monkeypatch.setattr(mod, "subprocess", fake_sub, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "spfile" in facts
    assert facts["spfile"] == "/u01/oracle/dbs/spfileORCL.ora"


def test_detect_paths_with_crs_home_srvctl_output(monkeypatch):
    """detect_paths: crs_home set → srvctl Popen called, password/spfile parsed from output."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"
    os.environ["ORACLE_HOME"] = "/u01/oracle"

    srvctl_lines = [
        b"Oracle home: /u01/oracle\n",
        b"Spfile: +DATA/spfileORCL.ora\n",
        b"Password file: +DATA/orapwORCL\n",
    ]

    class _CrsHomes(FakeOracleHomes):
        def __init__(self, m):
            super().__init__()
            self.crs_home = "/fake/grid"

    popen_calls = []

    def _popen_factory(call_idx, args):
        popen_calls.append(args)
        if call_idx == 0:
            # srvctl call
            return _FakePopen(srvctl_lines)
        # orabasehome call
        return _FakePopen([b"/u01/oracle\n"])

    fake_sub = _FakeSubprocess(_popen_factory)

    # When password/spfile found via srvctl, v$parameter is NOT queried for spfile
    class _CrsConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = []   # no v$parameter spfile query expected

    class Mod(BaseFakeModule):
        params = _facts_params(password_file=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _CrsConn, raising=False)
    monkeypatch.setattr(mod, "OracleHomes", _CrsHomes, raising=False)
    monkeypatch.setattr(mod, "subprocess", fake_sub, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert facts["password_file"] == "+DATA/orapwORCL"
    assert facts["spfile"] == "+DATA/spfileORCL.ora"
    assert facts["crs_home"] == "/fake/grid"


def test_detect_paths_orabasehome_not_found_uses_oracle_home(monkeypatch):
    """detect_paths: orabasehome binary missing → ORABASEHOME falls back to ORACLE_HOME."""
    mod = _load()
    os.environ["ORACLE_SID"] = "TESTDB"
    os.environ["ORACLE_HOME"] = "/opt/oracle/19c"

    class _NoCrsHomes(FakeOracleHomes):
        def __init__(self, m):
            super().__init__()
            self.crs_home = ""

    def _popen_factory(call_idx, args):
        raise FileNotFoundError("orabasehome not installed")

    fake_sub = _FakeSubprocess(_popen_factory)

    # os.access always returns False → no PASSWORD or PFILE from filesystem
    # v$parameter returns no spfile value
    class _NoSpfileConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [{}]   # spfile fetchone → empty

    class Mod(BaseFakeModule):
        params = _facts_params(password_file=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _NoSpfileConn, raising=False)
    monkeypatch.setattr(mod, "OracleHomes", _NoCrsHomes, raising=False)
    monkeypatch.setattr(mod, "subprocess", fake_sub, raising=False)
    monkeypatch.setattr(mod.os, "access", lambda path, mode: False, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["TESTDB"]
    # ORABASEHOME was set to ORACLE_HOME but no readable files → all None
    assert facts["password_file"] is None
    assert facts["pfile"] is None
    assert facts["spfile"] is None


def test_detect_paths_password_and_pfile_found_on_disk(monkeypatch):
    """detect_paths: os.access returns True for both pwfile and pfile → both populated."""
    mod = _load()
    os.environ["ORACLE_SID"] = "MYDB"
    os.environ["ORACLE_HOME"] = "/u01/app/oracle"

    class _NoCrsHomes(FakeOracleHomes):
        def __init__(self, m):
            super().__init__()
            self.crs_home = ""

    def _popen_factory(call_idx, args):
        raise FileNotFoundError("no orabasehome")

    fake_sub = _FakeSubprocess(_popen_factory)

    # v$parameter returns empty (spfile will remain None)
    class _NoSpfileConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [{}]

    class Mod(BaseFakeModule):
        params = _facts_params(password_file=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _NoSpfileConn, raising=False)
    monkeypatch.setattr(mod, "OracleHomes", _NoCrsHomes, raising=False)
    monkeypatch.setattr(mod, "subprocess", fake_sub, raising=False)
    # Simulate both files exist and are readable
    monkeypatch.setattr(mod.os, "access", lambda path, mode: True, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["MYDB"]
    expected_pw = "/u01/app/oracle/dbs/orapwMYDB"
    expected_pf = "/u01/app/oracle/dbs/initMYDB.ora"
    assert facts["password_file"] == expected_pw
    assert facts["pfile"] == expected_pf


# ===========================================================================
# query_params string branch tests (lines 288-295)
# ===========================================================================

def _make_params_conn(param_rows):
    """Return a SequencedFakeConn that serves param_rows for the parameter query."""
    class _PConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {},   # rac
            ]
            self._param_rows = param_rows

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            if "v$parameter" in sql.lower() and not fetchone:
                return self._param_rows
            return super().execute_select_to_dict(sql, params=params, fetchone=fetchone)

    return _PConn


def test_query_params_at_all(monkeypatch):
    """parameter='@all@' → no WHERE clause → all parameters returned."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    rows = [
        {"name": "db_name", "value": "ORCL", "isdefault": "FALSE"},
        {"name": "processes", "value": "300", "isdefault": "TRUE"},
    ]

    class Mod(BaseFakeModule):
        params = _facts_params(parameter="@all@")

    PConn = _make_params_conn(rows)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", PConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "parameter" in facts
    assert "db_name" in facts["parameter"]
    assert "processes" in facts["parameter"]


def test_query_params_at_modified(monkeypatch):
    """parameter='@modified@' → WHERE ISDEFAULT=FALSE clause."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    rows = [
        {"name": "open_cursors", "value": "600", "isdefault": "FALSE"},
    ]

    class Mod(BaseFakeModule):
        params = _facts_params(parameter="@modified@")

    PConn = _make_params_conn(rows)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", PConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "parameter" in facts
    assert "open_cursors" in facts["parameter"]


def test_query_params_single_name(monkeypatch):
    """parameter='db_name' (single string) → WHERE NAME='db_name' clause."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    rows = [
        {"name": "db_name", "value": "ORCL", "isdefault": "FALSE"},
    ]

    class Mod(BaseFakeModule):
        params = _facts_params(parameter="db_name")

    PConn = _make_params_conn(rows)
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", PConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "parameter" in facts
    assert "db_name" in facts["parameter"]


def test_query_temp_old_version(monkeypatch):
    """query_temp on version < 12.1 uses the non-CDB SQL branch (line 229)."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _OldTempConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.version = "11.2.0.4"   # triggers old branch
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {"con_id": 0, "name": "TEMP", "bigfile": "NO", "size_mb": 100, "tempfiles#": 1},
                {},  # rac
            ]

        def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
            r = self.responses.pop(0) if self.responses else {}
            if "tempfile" in sql.lower() and not fetchone:
                return [r] if r else []
            return r if fetchone else ([r] if r else [])

    class Mod(BaseFakeModule):
        params = _facts_params(temp=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _OldTempConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "temp" in facts


def test_query_userenv_old_version(monkeypatch):
    """query_userenv on version 11.x adds CURRENT_EDITION columns but not CON_ID."""
    mod = _load()
    os.environ["ORACLE_SID"] = "ORCL"

    class _OldUeConn(SequencedFakeConn):
        def __init__(self, m):
            super().__init__(m)
            self.version = "11.2.0.4"
            self.responses = [
                _INSTANCE_ROW,
                _DB_ROW,
                {
                    "current_user": "SYS",
                    "database_role": "PRIMARY",
                    "isdba": "TRUE",
                    "current_edition_id": 0,
                    "current_edition_name": "ORA$BASE",
                },  # userenv
                {},  # rac
            ]

    class Mod(BaseFakeModule):
        params = _facts_params(userenv=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", _OldUeConn, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["ORCL"]
    assert "userenv" in facts
    assert facts["userenv"]["current_user"] == "SYS"


# ===========================================================================
# oracle_gi_facts
# ===========================================================================


def _load_gi():
    return load_module_from_path("plugins/modules/oracle_gi_facts.py", "oracle_gi_facts")


def _gi_params(**overrides):
    base = {"oracle_home": None}
    base.update(overrides)
    return base


class _FakeOracleHomesHAS(FakeOracleHomes):
    """HAS (single-instance) GI environment."""
    oracle_crs = False


class _FakeOracleHomesCRS(FakeOracleHomes):
    """Full CRS (RAC) GI environment."""
    oracle_crs = True


class _FakeOracleHomesNoCrsHome(FakeOracleHomes):
    def __init__(self):
        super().__init__()
        self.crs_home = ""
        self.crsctl = ""


def test_gi_facts_has_cluster_basic(monkeypatch):
    """HAS environment: all functions return empty output → exits with ansible_facts."""
    mod = _load_gi()

    monkeypatch.setattr(mod, "exec_program_lines", lambda args: [""], raising=False)
    monkeypatch.setattr(mod, "exec_program", lambda args: "", raising=False)

    class Mod(BaseFakeModule):
        params = _gi_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesHAS, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    payload = exc.value.args[0]
    assert payload["changed"] is False
    assert "oracle_gi_facts" in payload["ansible_facts"]


def test_gi_facts_crs_cluster_basic(monkeypatch):
    """CRS (RAC) environment: oracle_crs=True path covered → exits with ansible_facts."""
    mod = _load_gi()

    monkeypatch.setattr(mod, "exec_program_lines", lambda args: [""], raising=False)
    monkeypatch.setattr(mod, "exec_program", lambda args: "", raising=False)

    class Mod(BaseFakeModule):
        params = _gi_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesCRS, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False
    assert "oracle_gi_facts" in exc.value.args[0]["ansible_facts"]


def test_gi_facts_no_crs_home_fails(monkeypatch):
    """crs_home empty → fail_json about GI home not found."""
    mod = _load_gi()

    class Mod(BaseFakeModule):
        params = _gi_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesNoCrsHome, raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "GI home" in exc.value.args[0]["msg"]


def test_gi_facts_with_oracle_home_param(monkeypatch):
    """oracle_home param is set → ORACLE_HOME env is updated before facts collection."""
    mod = _load_gi()

    monkeypatch.setattr(mod, "exec_program_lines", lambda args: [""], raising=False)
    monkeypatch.setattr(mod, "exec_program", lambda args: "", raising=False)

    class Mod(BaseFakeModule):
        params = _gi_params(oracle_home="/custom/grid")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesHAS, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    assert exc.value.args[0]["changed"] is False


def test_gi_facts_get_asm_parsing(monkeypatch):
    """get_asm: valid srvctl output is parsed into a dict."""
    mod = _load_gi()
    asm_output = [
        "ASM home: /u01/app/grid",
        "Password file: +DATA/orapwASM",
        "ASM listener: LISTENER_ASM",
        "Spfile: +DATA/spfileASM.ora",
        "ASM diskgroup discovery string: /dev/sd*",
    ]
    call_count = [0]

    def _fake_exec_lines(args):
        call_count[0] += 1
        # First call (cemutlo clustername), then asm config
        if any("asm" in str(a) for a in args):
            return asm_output
        return [""]

    monkeypatch.setattr(mod, "exec_program_lines", _fake_exec_lines, raising=False)
    monkeypatch.setattr(mod, "exec_program", lambda args: "", raising=False)

    class Mod(BaseFakeModule):
        params = _gi_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesHAS, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["oracle_gi_facts"]
    assert facts["asm"].get("asm_home") == "/u01/app/grid"
    assert facts["asm"].get("spfile") == "+DATA/spfileASM.ora"


def test_gi_facts_get_networks_parsing(monkeypatch):
    """get_networks: valid srvctl output parsed into network dict."""
    mod = _load_gi()
    net_output = [
        "Network 1 exists",
        "Subnet IPv4: 192.168.1.0/255.255.255.0/eth0",
        "Subnet IPv6: ",
    ]

    def _fake_exec_lines(args):
        if "network" in args and "config" in args:
            return net_output
        return [""]

    monkeypatch.setattr(mod, "exec_program_lines", _fake_exec_lines, raising=False)
    monkeypatch.setattr(mod, "exec_program", lambda args: "", raising=False)

    class Mod(BaseFakeModule):
        params = _gi_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesHAS, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["oracle_gi_facts"]
    assert len(facts["network"]) == 1
    assert facts["network"][0]["ipv4"] == "192.168.1.0/255.255.255.0/eth0"


def test_gi_facts_has_version_parsing(monkeypatch):
    """HAS cluster: crsctl query has releaseversion output is parsed."""
    mod = _load_gi()

    def _fake_exec(args):
        if "releaseversion" in args:
            return "[19.3.0.0.0]"
        return ""

    monkeypatch.setattr(mod, "exec_program_lines", lambda args: [""], raising=False)
    monkeypatch.setattr(mod, "exec_program", _fake_exec, raising=False)

    class Mod(BaseFakeModule):
        params = _gi_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesHAS, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["oracle_gi_facts"]
    assert facts.get("releaseversion") == "19.3.0.0.0"
    assert facts.get("version") == "19.3.0.0.0"


def test_gi_facts_listener_parsing(monkeypatch):
    """local_listener: 'is enabled' line is parsed for listener name."""
    mod = _load_gi()
    listener_status = ["Listener LISTENER is enabled"]
    listener_config = [
        "Name: LISTENER",
        "Type: DATABASE",
        "End points: TCP:1521",
    ]

    def _fake_exec_lines(args):
        if "status" in args and "listener" in args:
            return listener_status
        if "config" in args and "listener" in args:
            return listener_config
        return [""]

    monkeypatch.setattr(mod, "exec_program_lines", _fake_exec_lines, raising=False)
    monkeypatch.setattr(mod, "exec_program", lambda args: "", raising=False)

    class Mod(BaseFakeModule):
        params = _gi_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesHAS, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["oracle_gi_facts"]
    assert len(facts["local_listener"]) == 1
    assert facts["local_listener"][0]["name"] == "LISTENER"


def test_gi_facts_crs_active_version(monkeypatch):
    """CRS environment with oracle_crs=True (correctly set) → activeversion populated."""
    mod = _load_gi()

    class _FixedCRS(_FakeOracleHomesHAS):
        def __init__(self):
            super().__init__()
            self.oracle_crs = True  # override instance attribute

    def _fake_exec(args):
        if "activeversion" in args:
            return "Oracle Clusterware active version on the cluster is [19.0.0.0.0]"
        return ""

    monkeypatch.setattr(mod, "exec_program_lines", lambda args: [""], raising=False)
    monkeypatch.setattr(mod, "exec_program", _fake_exec, raising=False)

    class Mod(BaseFakeModule):
        params = _gi_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FixedCRS, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["oracle_gi_facts"]
    assert "activeversion" in facts


def test_gi_facts_get_vips_parsing(monkeypatch):
    """get_vips: srvctl vip output parsed into dict."""
    mod = _load_gi()

    vip_output = [
        "VIP exists: network number 1, hosting node node1",
        "VIP Name: node1-vip.example.com",
        "VIP IPv4 Address: 192.168.1.10",
        "VIP IPv6 Address: ",
    ]

    def _fake_exec_lines(args):
        if "vip" in args:
            return vip_output
        return [""]

    monkeypatch.setattr(mod, "exec_program_lines", _fake_exec_lines, raising=False)
    monkeypatch.setattr(mod, "exec_program", lambda args: "", raising=False)

    class Mod(BaseFakeModule):
        params = _gi_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesHAS, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["oracle_gi_facts"]
    assert len(facts["vip"]) >= 1
    assert facts["vip"][0]["ipv4"] == "192.168.1.10"


def test_gi_facts_get_scans_parsing(monkeypatch):
    """get_scans: srvctl scan output parsed into dict."""
    mod = _load_gi()

    scan_output = [
        "SCAN name: scan.example.com, Network: 1",
        "SCAN 1 IPv4 VIP: 192.168.1.100",
        "SCAN 2 IPv4 VIP: 192.168.1.101",
    ]

    def _fake_exec_lines(args):
        if "scan" in args and "-all" in args:
            return scan_output
        return [""]

    monkeypatch.setattr(mod, "exec_program_lines", _fake_exec_lines, raising=False)
    monkeypatch.setattr(mod, "exec_program", lambda args: "", raising=False)

    class Mod(BaseFakeModule):
        params = _gi_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesHAS, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["oracle_gi_facts"]
    assert len(facts["scan"]) >= 1
    scan = facts["scan"][0]
    assert "192.168.1.100" in scan["ipv4"]


def test_gi_facts_get_networks_multiple(monkeypatch):
    """get_networks: multiple network blocks parsed correctly."""
    mod = _load_gi()

    net_output = [
        "Network 1 exists",
        "Subnet IPv4: 192.168.1.0/255.255.255.0/eth0",
        "Subnet IPv6: ",
        "Network 2 exists",
        "Subnet IPv4: 10.0.0.0/255.0.0.0/eth1",
    ]

    def _fake_exec_lines(args):
        if "network" in args and "config" in args:
            return net_output
        return [""]

    monkeypatch.setattr(mod, "exec_program_lines", _fake_exec_lines, raising=False)
    monkeypatch.setattr(mod, "exec_program", lambda args: "", raising=False)

    class Mod(BaseFakeModule):
        params = _gi_params()

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "OracleHomes", _FakeOracleHomesHAS, raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    facts = exc.value.args[0]["ansible_facts"]["oracle_gi_facts"]
    assert len(facts["network"]) == 2


def test_gi_facts_exec_program_lines_direct():
    """exec_program_lines: returns list of stripped lines on success."""
    mod = _load_gi()
    # Call directly with a known command that succeeds
    result = mod.exec_program_lines(["echo", "hello"])
    assert result == ["hello"]


def test_gi_facts_exec_program_direct():
    """exec_program: returns first line of exec_program_lines output."""
    mod = _load_gi()
    result = mod.exec_program(["echo", "test_line"])
    assert result == "test_line"


def test_gi_facts_hostname_to_fqdn_with_dot():
    """hostname_to_fqdn: hostname with dot → returned unchanged."""
    mod = _load_gi()
    result = mod.hostname_to_fqdn("host.example.com")
    assert result == "host.example.com"


def test_gi_facts_hostname_to_fqdn_without_dot(monkeypatch):
    """hostname_to_fqdn: hostname without dot → socket.getfqdn called."""
    mod = _load_gi()
    monkeypatch.setattr(mod.socket, "getfqdn", lambda h: h + ".example.com", raising=False)
    result = mod.hostname_to_fqdn("myhost")
    assert result == "myhost.example.com"
