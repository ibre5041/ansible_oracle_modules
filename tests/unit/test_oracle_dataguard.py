"""Unit tests for oracle_dataguard module."""
import pytest

from conftest import ExitJson, FailJson, load_module_from_path, module_path
from helpers import BASE_CONN_PARAMS, BaseFakeConn, BaseFakeModule


def _load():
    return load_module_from_path(
        module_path("plugins", "modules", "oracle_dataguard.py"), "oracle_dataguard_test"
    )


def _dg_params(**overrides):
    base = {
        **BASE_CONN_PARAMS,
        "mode_dg": "broker",
        "state": "status",
        "enabled": None,
        "dgmgrl_user": None,
        "dgmgrl_password": None,
        "dgmgrl_connect_identifier": None,
        "dgmgrl_as": "sysdg",
        "configuration_name": None,
        "primary_database": None,
        "connect_identifier": None,
        "database_name": None,
        "properties": None,
        "protection_mode": None,
        "database_state": None,
        "fsfo": None,
        "fsfo_target": None,
        "far_sync_name": None,
        "far_sync_connect_identifier": None,
        "observer_state": None,
        "validate_connect_identifier": None,
        "primary_database_candidates": None,
        "tags": None,
        "reset_tags": None,
        "output_format": "text",
        "force_logging": None,
        "apply_state": None,
    }
    base.update(overrides)
    return base


# ===========================================================================
# DGMGRL output fixtures
# ===========================================================================

SHOW_CONFIG_OUTPUT = """Configuration - my_dg_config

  Protection Mode: MaxPerformance
  Members:
  PROD    - Primary database
    STDBY   - Physical standby database

Fast-Start Failover:  Disabled

Configuration Status:
SUCCESS   (status updated 5 seconds ago)
"""

SHOW_CONFIG_NOT_CONFIGURED = """ORA-16532: Oracle Data Guard broker configuration does not exist
Configuration details cannot be determined by DGMGRL
"""


class _DgBrokerModule(BaseFakeModule):
    """Module that stubs run_command for DGMGRL."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dgmgrl_responses = getattr(type(self), '_dgmgrl_responses', {})
        self._run_command_calls = getattr(type(self), '_run_command_calls', [])

    def run_command(self, command, **kwargs):
        self._run_command_calls.append((command, kwargs))
        data = kwargs.get('data', '')
        # Check which commands are in the script
        for key, (rc, stdout, stderr) in self._dgmgrl_responses.items():
            if key in data.upper():
                return (rc, stdout, stderr)
        # Default: show configuration
        return (0, SHOW_CONFIG_OUTPUT, '')


# ===========================================================================
# Tests: Broker mode - status
# ===========================================================================

def test_dg_broker_status(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(oracle_home="/fake/oracle")
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert result["configuration"]["name"] == "my_dg_config"
    assert result["configuration"]["protection_mode"] == "MaxPerformance"


def test_dg_broker_status_not_configured(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(oracle_home="/fake/oracle")
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (1, SHOW_CONFIG_NOT_CONFIGURED, ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["configuration"]["status"] == "NOT_CONFIGURED"


# ===========================================================================
# Tests: Broker mode - create configuration
# ===========================================================================

def test_dg_broker_create_config(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="present",
            configuration_name="my_dg",
            primary_database="PROD",
            connect_identifier="prod-host:1521/PROD",
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (1, SHOW_CONFIG_NOT_CONFIGURED, ''),
            'CREATE CONFIGURATION': (0, 'Succeeded.', ''),
        }
        _call_count = 0

        def run_command(self, command, **kwargs):
            data = kwargs.get('data', '')
            # First call: show config returns not configured
            # Second call: create succeeds
            # Third call: show config returns success
            self.__class__._call_count += 1
            if self.__class__._call_count <= 1:
                return (1, SHOW_CONFIG_NOT_CONFIGURED, '')
            elif 'CREATE' in data.upper():
                return (0, 'Succeeded.', '')
            else:
                return (0, SHOW_CONFIG_OUTPUT, '')

    Mod._call_count = 0
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


# ===========================================================================
# Tests: Broker mode - absent (remove)
# ===========================================================================

def test_dg_broker_remove_database(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="absent",
            database_name="STDBY",
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
            'REMOVE DATABASE': (0, 'Succeeded.', ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


def test_dg_broker_remove_configuration(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="absent",
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
            'REMOVE CONFIGURATION': (0, 'Succeeded.', ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


def test_dg_broker_absent_when_not_configured(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="absent",
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (1, SHOW_CONFIG_NOT_CONFIGURED, ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


# ===========================================================================
# Tests: Broker mode - enable/disable
# ===========================================================================

def test_dg_broker_enable_configuration(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(oracle_home="/fake/oracle", state="present", enabled=True)
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
            'ENABLE CONFIGURATION': (0, 'Succeeded.', ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


def test_dg_broker_disable_database(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(oracle_home="/fake/oracle", state="present", enabled=False, database_name="STDBY")
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
            'DISABLE DATABASE': (0, 'Succeeded.', ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


# ===========================================================================
# Tests: Broker mode - switchover/failover
# ===========================================================================

def test_dg_broker_switchover(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(oracle_home="/fake/oracle", state="switchover", database_name="STDBY")
        _dgmgrl_responses = {
            'SWITCHOVER TO': (0, 'Switchover succeeded.', ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert "switchover" in result["msg"].lower()


def test_dg_broker_failover(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(oracle_home="/fake/oracle", state="failover", database_name="STDBY")
        _dgmgrl_responses = {
            'FAILOVER TO': (0, 'Failover succeeded.', ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


# ===========================================================================
# Tests: Broker mode - convert
# ===========================================================================

def test_dg_broker_convert_snapshot(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(oracle_home="/fake/oracle", state="snapshot_standby", database_name="STDBY")
        _dgmgrl_responses = {
            'CONVERT DATABASE': (0, 'Succeeded.', ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert "snapshot" in result["msg"].lower()


# ===========================================================================
# Tests: SQL mode - status
# ===========================================================================

class _DgSqlConn(BaseFakeConn):
    """Simulates V$DATABASE, V$DATAGUARD_STATS, etc."""

    def __init__(self, module, db_role='PRIMARY', force_logging='YES',
                 protection_mode='MAXIMUM PERFORMANCE', dg_processes=None):
        super().__init__(module)
        self._db_role = db_role
        self._force_logging = force_logging
        self._protection_mode = protection_mode
        self._dg_processes = dg_processes or []

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
        sql_upper = sql.upper()
        if 'V$DATABASE' in sql_upper:
            row = {
                'database_role': self._db_role,
                'protection_mode': self._protection_mode,
                'protection_level': self._protection_mode,
                'switchover_status': 'TO STANDBY',
                'dataguard_broker': 'ENABLED',
                'force_logging': self._force_logging,
                'flashback_on': 'YES',
                'db_unique_name': 'PROD',
            }
            return row if fetchone else [row]
        if 'V$DATAGUARD_STATS' in sql_upper:
            return [
                {'name': 'transport lag', 'value': '+00 00:00:00', 'unit': 'day(2) to second(0) interval', 'time_computed': '2024-01-01', 'datum_time': '2024-01-01'},
                {'name': 'apply lag', 'value': '+00 00:00:02', 'unit': 'day(2) to second(0) interval', 'time_computed': '2024-01-01', 'datum_time': '2024-01-01'},
            ]
        if 'V$ARCHIVE_DEST_STATUS' in sql_upper:
            return [{'dest_id': 2, 'status': 'VALID', 'type': 'PHYSICAL', 'database_mode': 'MOUNTED',
                     'recovery_mode': 'MANAGED REAL TIME APPLY', 'gap_status': 'NO GAP',
                     'synchronized': 'YES', 'error': '', 'db_unique_name': 'STDBY'}]
        if 'V$DATAGUARD_PROCESS' in sql_upper:
            return self._dg_processes
        return {} if fetchone else []


def test_dg_sql_status(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dg_params(mode_dg="sql", state="status")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _DgSqlConn(m), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert result["database"]["database_role"] == "PRIMARY"
    assert len(result["dataguard_stats"]) == 2


# ===========================================================================
# Tests: SQL mode - apply management
# ===========================================================================

def test_dg_sql_start_apply(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dg_params(mode_dg="sql", state="present", apply_state="started")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _DgSqlConn(m, db_role='PHYSICAL STANDBY'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("RECOVER MANAGED STANDBY" in d for d in result["ddls"])


def test_dg_sql_start_apply_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dg_params(mode_dg="sql", state="present", apply_state="started")

    processes = [{'role': 'MRP', 'action': 'APPLYING_LOG', 'client_role': '', 'thread#': 1, 'sequence#': 100, 'block#': 1}]
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _DgSqlConn(m, dg_processes=processes), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


def test_dg_sql_stop_apply(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dg_params(mode_dg="sql", state="present", apply_state="stopped")

    processes = [{'role': 'MRP', 'action': 'APPLYING_LOG', 'client_role': '', 'thread#': 1, 'sequence#': 100, 'block#': 1}]
    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _DgSqlConn(m, dg_processes=processes), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("CANCEL" in d for d in result["ddls"])


# ===========================================================================
# Tests: SQL mode - force logging
# ===========================================================================

def test_dg_sql_enable_force_logging(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dg_params(mode_dg="sql", state="present", force_logging="enable")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _DgSqlConn(m, force_logging='NO'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("FORCE LOGGING" in d for d in result["ddls"])


def test_dg_sql_force_logging_idempotent(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dg_params(mode_dg="sql", state="present", force_logging="enable")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _DgSqlConn(m, force_logging='YES'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False


# ===========================================================================
# Tests: SQL mode - protection mode
# ===========================================================================

def test_dg_sql_set_protection_mode(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dg_params(mode_dg="sql", state="present", protection_mode="maximum_availability")

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: _DgSqlConn(m, protection_mode='MAXIMUM PERFORMANCE'), raising=False)

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    assert any("MAXIMIZE AVAILABILITY" in d for d in result["ddls"])


# ===========================================================================
# Tests: FSFO Target
# ===========================================================================

def test_dg_broker_fsfo_enable_with_target(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="present",
            fsfo="enabled",
            fsfo_target="STDBY",
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
            'ENABLE FAST_START FAILOVER': (0, 'Succeeded.', ''),
        }
        _run_command_calls = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    # Verify the target was included in the command
    calls = [kwargs.get('data', '') for args, kwargs in Mod._run_command_calls]
    assert any('TARGET TO STDBY' in c for c in calls)


def test_dg_broker_fsfo_enable_without_target(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="present",
            fsfo="enabled",
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
            'ENABLE FAST_START FAILOVER': (0, 'Succeeded.', ''),
        }
        _run_command_calls = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    calls = [kwargs.get('data', '') for args, kwargs in Mod._run_command_calls]
    assert any('ENABLE FAST_START FAILOVER' in c and 'TARGET' not in c for c in calls)


# ===========================================================================
# Tests: VALIDATE DGConnectIdentifier (26ai)
# ===========================================================================

def test_dg_broker_validate_connect_identifier(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="status",
            validate_connect_identifier="stdby-host:1521/STDBY",
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
            'VALIDATE DGCONNECTIDENTIFIER': (0, 'Validation succeeded.', ''),
            'SHOW': (0, '', ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
    assert result["validate_connect_identifier"] is not None
    assert result["validate_connect_identifier"]["rc"] == 0


def test_dg_broker_validate_connect_identifier_injection(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="status",
            validate_connect_identifier="host:1521/SVC; DROP CONFIGURATION",
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert 'Invalid' in exc.value.args[0]['msg']


# ===========================================================================
# Tests: PrimaryDatabaseCandidates (26ai)
# ===========================================================================

def test_dg_broker_set_primary_db_candidates(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="present",
            primary_database_candidates=["PROD", "STDBY"],
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
            'PRIMARYDATABASECANDIDATES': (0, 'Succeeded.', ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True


def test_dg_broker_primary_db_candidates_invalid_name(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="present",
            primary_database_candidates=["PROD", "BAD NAME"],
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert 'Invalid' in exc.value.args[0]['msg']


def test_dg_broker_primary_db_candidates_unsupported(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="present",
            primary_database_candidates=["PROD"],
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
            'PRIMARYDATABASECANDIDATES': (1, 'ORA-16599: invalid property', ''),
        }
        _warnings = []

        def warn(self, msg):
            type(self)._warnings.append(msg)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    # changed=False because the feature was skipped
    assert any('not supported' in w for w in Mod._warnings)


# ===========================================================================
# Tests: Tagging (26ai)
# ===========================================================================

def test_dg_broker_set_tags_database(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="present",
            database_name="STDBY",
            tags={"environment": "production", "tier": "dr"},
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
            'SET TAG': (0, 'Succeeded.', ''),
        }
        _run_command_calls = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    calls = [kwargs.get('data', '') for args, kwargs in Mod._run_command_calls]
    assert any('EDIT DATABASE STDBY SET TAG' in c for c in calls)


def test_dg_broker_set_tags_configuration(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="present",
            tags={"site": "dc1"},
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
            'SET TAG': (0, 'Succeeded.', ''),
        }
        _run_command_calls = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    calls = [kwargs.get('data', '') for args, kwargs in Mod._run_command_calls]
    assert any('EDIT CONFIGURATION SET TAG' in c for c in calls)


def test_dg_broker_reset_tags(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="present",
            database_name="STDBY",
            reset_tags=["environment"],
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
            'RESET TAG': (0, 'Succeeded.', ''),
        }
        _run_command_calls = []

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is True
    calls = [kwargs.get('data', '') for args, kwargs in Mod._run_command_calls]
    assert any('EDIT DATABASE STDBY RESET TAG environment' in c for c in calls)


def test_dg_broker_show_tags_in_status(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="status",
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
            'SHOW': (0, 'environment=production\ntier=dr\n', ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["tags"] is not None


def test_dg_broker_tags_invalid_name(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(
            oracle_home="/fake/oracle",
            state="present",
            tags={"bad tag!": "value"},
        )
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert 'Invalid tag name' in exc.value.args[0]['msg']


# ===========================================================================
# Tests: parse_show_configuration
# ===========================================================================

def test_parse_show_configuration():
    mod = _load()
    result = mod.parse_show_configuration(SHOW_CONFIG_OUTPUT)
    assert result["name"] == "my_dg_config"
    assert result["protection_mode"] == "MaxPerformance"
    assert result["fast_start_failover"] == "Disabled"
    assert len(result["databases"]) == 2
    assert result["databases"][0]["role"] == "PRIMARY"
    assert result["databases"][1]["role"] == "PHYSICAL STANDBY"
    assert result["status"] == "SUCCESS"


# ===========================================================================
# Helpers
# ===========================================================================

class _FakeOs:
    """Fake os module that makes path.exists return True for oracle_home."""

    def __init__(self, oracle_home):
        self.environ = dict(ORACLE_HOME=oracle_home)

    class path:
        @classmethod
        def exists(cls, path_str):
            return True

        @classmethod
        def join(cls, *args):
            import os as _os
            return _os.path.join(*args)

    def __getattr__(self, name):
        import os as _os
        return getattr(_os, name)


# ===========================================================================
# Tests: enabled parameter validation
# ===========================================================================

def test_dg_enabled_rejected_with_non_present_state(monkeypatch):
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(oracle_home="/fake/oracle", state="status", enabled=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "only valid with state='present'" in exc.value.args[0]["msg"]


def test_dg_enabled_rejected_in_sql_mode(monkeypatch):
    mod = _load()

    class Mod(BaseFakeModule):
        params = _dg_params(mode_dg="sql", state="present", enabled=True)

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "oracleConnection", lambda m: BaseFakeConn(m), raising=False)

    with pytest.raises(FailJson) as exc:
        mod.main()
    assert "only supported in broker mode" in exc.value.args[0]["msg"]


def test_dg_broker_present_enabled_none_no_enable(monkeypatch):
    """enabled=None should not call enable or disable."""
    mod = _load()

    class Mod(_DgBrokerModule):
        params = _dg_params(oracle_home="/fake/oracle", state="present", enabled=None)
        _dgmgrl_responses = {
            'SHOW CONFIGURATION': (0, SHOW_CONFIG_OUTPUT, ''),
        }

    monkeypatch.setattr(mod, "AnsibleModule", Mod)
    monkeypatch.setattr(mod, "os", _FakeOs("/fake/oracle"))

    with pytest.raises(ExitJson) as exc:
        mod.main()
    result = exc.value.args[0]
    assert result["changed"] is False
