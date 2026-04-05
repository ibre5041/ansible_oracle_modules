#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_dataguard
short_description: Manage Oracle Data Guard configurations
description:
  - Manage Oracle Data Guard via the Broker (DGMGRL) or via SQL direct
  - Create, enable, disable, and remove Data Guard configurations
  - Add, remove, enable, and disable standby databases
  - Perform switchover and failover operations
  - Convert databases between physical/snapshot standby
  - Manage Data Guard properties
  - Set protection modes (Maximum Protection, Maximum Availability, Maximum Performance)
  - Manage Fast-Start Failover (FSFO) and observers
  - Manage Far Sync instances
  - Query Data Guard status, lag, and health
  - SQL mode for environments without broker
  - Compatible with Oracle 19c, 23ai, and 26ai
  - "Oracle 26ai features: JSON output, PrimaryDatabaseCandidates, VALIDATE DGConnectIdentifier, tagging"
version_added: "3.4.0"
options:
  mode_dg:
    description:
      - Data Guard management mode
      - broker uses DGMGRL commands (recommended by Oracle)
      - sql uses direct SQL and V$ views (for environments without broker)
    default: broker
    choices: ['broker', 'sql']
  state:
    description: The intended state
    default: status
    choices:
      - present
      - absent
      - enabled
      - disabled
      - status
      - switchover
      - failover
      - snapshot_standby
      - physical_standby
  oracle_home:
    description: ORACLE_HOME path (required for DGMGRL in broker mode)
    required: false
    aliases: ['oh']
  dgmgrl_user:
    description:
      - Username for DGMGRL connection
      - If omitted (along with dgmgrl_password), OS authentication is used (/ AS SYSDG or / AS SYSDBA)
    required: false
  dgmgrl_password:
    description:
      - Password for DGMGRL connection
      - If omitted (along with dgmgrl_user), OS authentication is used
    required: false
  dgmgrl_connect_identifier:
    description: Connect identifier for DGMGRL (e.g. host:port/service)
    required: false
  dgmgrl_as:
    description:
      - DGMGRL connection privilege
      - Used for both password and OS authentication
    default: sysdg
    choices: ['sysdba', 'sysdg']
  configuration_name:
    description: Name of the Data Guard broker configuration
    required: false
  primary_database:
    description: DB_UNIQUE_NAME of the primary database
    required: false
  connect_identifier:
    description: Oracle Net connect identifier for the database being managed
    required: false
  database_name:
    description: DB_UNIQUE_NAME of the database to manage
    required: false
  properties:
    description:
      - Dictionary of broker properties to set on a database
      - "Example: {'LogXptMode': 'SYNC', 'NetTimeout': '60'}"
    type: dict
    required: false
  protection_mode:
    description: Data Guard protection mode
    choices: ['maximum_protection', 'maximum_availability', 'maximum_performance']
    required: false
  database_state:
    description: Desired state of redo transport/apply for a database
    choices: ['transport-on', 'transport-off', 'apply-on', 'apply-off']
    required: false
  fsfo:
    description: Fast-Start Failover state
    choices: ['enabled', 'disabled']
    required: false
  fsfo_target:
    description: Target database for Fast-Start Failover
    required: false
  far_sync_name:
    description: Name of the Far Sync instance
    required: false
  far_sync_connect_identifier:
    description: Connect identifier for Far Sync instance
    required: false
  observer_state:
    description: Observer state
    choices: ['started', 'stopped']
    required: false
  output_format:
    description:
      - Output format for DGMGRL (26ai supports JSON)
      - json provides structured output (Oracle 26ai+)
    default: text
    choices: ['text', 'json']
  force_logging:
    description: Enable or disable FORCE LOGGING (SQL mode)
    choices: ['enable', 'disable']
    required: false
  apply_state:
    description: Managed recovery state (SQL mode)
    choices: ['started', 'stopped']
    required: false
notes:
  - Broker mode requires DGMGRL binary in ORACLE_HOME/bin
  - "Broker mode supports OS authentication (/ AS SYSDG or / AS SYSDBA) when dgmgrl_user and dgmgrl_password are omitted"
  - "SQL mode supports OS authentication (mode: sysdba without user/password) when running as the oracle OS user"
  - SQL mode uses standard oracledb connection
  - Switchover and failover are non-idempotent operations - use with care
  - oracledb Python module is required for SQL mode
requirements: [ "oracledb" ]
author:
  - Cyrille Modiano
'''

EXAMPLES = '''
# --- Broker Mode (default) ---

# OS authentication (runs as oracle OS user, no username/password needed)
- name: Get Data Guard status with OS authentication as SYSDG
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    state: status

- name: Get Data Guard status with OS authentication as SYSDBA
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    dgmgrl_as: sysdba
    state: status

# Password authentication
- name: Get Data Guard status with password authentication
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    dgmgrl_user: sys
    dgmgrl_password: "SysPass123"
    dgmgrl_as: sysdg
    state: status

- name: Create a Data Guard broker configuration
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    state: present
    configuration_name: my_dg_config
    primary_database: PROD
    connect_identifier: "prod-host:1521/PROD"

- name: Add a standby database to the configuration
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    state: present
    database_name: STDBY
    connect_identifier: "stdby-host:1521/STDBY"

- name: Enable the configuration
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    state: enabled

- name: Set database properties
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    database_name: STDBY
    properties:
      LogXptMode: SYNC
      NetTimeout: "60"
      RedoCompression: ENABLE

- name: Set protection mode to Maximum Availability
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    protection_mode: maximum_availability

- name: Switchover to standby
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    state: switchover
    database_name: STDBY

- name: Failover to standby
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    state: failover
    database_name: STDBY

- name: Convert to snapshot standby
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    state: snapshot_standby
    database_name: STDBY

- name: Enable Fast-Start Failover
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    fsfo: enabled

- name: Disable the configuration
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    state: disabled

- name: Remove a standby database
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    state: absent
    database_name: STDBY

- name: Remove entire configuration
  oracle_dataguard:
    oracle_home: /u01/app/oracle/product/19c
    state: absent

# --- SQL Mode ---

# OS authentication (mode: sysdba, no user/password)
- name: Get Data Guard status via SQL with OS authentication
  oracle_dataguard:
    mode_dg: sql
    mode: sysdba
    state: status

# Password authentication
- name: Get Data Guard status via SQL with password
  oracle_dataguard:
    mode_dg: sql
    user: sys
    password: "SysPass123"
    mode: sysdba
    service_name: PROD
    state: status

- name: Start managed recovery (SQL mode)
  oracle_dataguard:
    mode_dg: sql
    mode: sysdba
    apply_state: started

- name: Stop managed recovery (SQL mode)
  oracle_dataguard:
    mode_dg: sql
    mode: sysdba
    apply_state: stopped

- name: Enable force logging (SQL mode)
  oracle_dataguard:
    mode_dg: sql
    mode: sysdba
    force_logging: enable

- name: Set protection mode via SQL
  oracle_dataguard:
    mode_dg: sql
    mode: sysdba
    protection_mode: maximum_availability
'''

import json
import os


# ============================================================================
# DGMGRL (Broker) Functions
# ============================================================================

def run_dgmgrl(module, commands, output_format='text'):
    """Execute DGMGRL commands and return output.

    Commands are passed via stdin to avoid shell injection.
    """
    oracle_home = module.params.get("oracle_home")
    if not oracle_home:
        if 'ORACLE_HOME' in os.environ:
            oracle_home = os.environ['ORACLE_HOME']
        else:
            module.fail_json(msg='oracle_home is required for broker mode', changed=False)

    dgmgrl_bin = os.path.join(oracle_home, 'bin', 'dgmgrl')
    if not os.path.exists(dgmgrl_bin):
        module.fail_json(msg='DGMGRL not found at %s' % dgmgrl_bin, changed=False)

    # Build connect string
    dgmgrl_user = module.params.get("dgmgrl_user")
    dgmgrl_password = module.params.get("dgmgrl_password")
    dgmgrl_connect_id = module.params.get("dgmgrl_connect_identifier")
    dgmgrl_as = module.params.get("dgmgrl_as")

    if dgmgrl_user and dgmgrl_password:
        if dgmgrl_connect_id:
            connect_string = '%s/%s@%s' % (dgmgrl_user, dgmgrl_password, dgmgrl_connect_id)
        else:
            connect_string = '%s/%s' % (dgmgrl_user, dgmgrl_password)
        if dgmgrl_as:
            connect_string += ' AS %s' % dgmgrl_as.upper()
    else:
        connect_string = '/ AS %s' % dgmgrl_as.upper()

    # Build command
    cmd = [dgmgrl_bin, '-silent']
    if output_format == 'json':
        cmd.extend(['-outputformat', 'json'])
    cmd.append(connect_string)

    # Build script from commands
    script = ';\n'.join(commands) + ';\n'

    rc, stdout, stderr = module.run_command(cmd, data=script)

    return rc, stdout, stderr


def parse_show_configuration(stdout):
    """Parse SHOW CONFIGURATION output into a dict."""
    result = {
        'name': '',
        'protection_mode': '',
        'status': '',
        'databases': [],
        'fast_start_failover': '',
    }
    for line in stdout.split('\n'):
        line = line.strip()
        if line.startswith('Configuration -'):
            result['name'] = line.split('-', 1)[1].strip()
        elif line.startswith('Protection Mode:'):
            result['protection_mode'] = line.split(':', 1)[1].strip()
        elif any(role in line for role in (
                'Primary database', 'Physical standby', 'Snapshot standby', 'Logical standby')):
            parts = line.split('-')
            if len(parts) >= 2:
                db_info = {
                    'name': parts[0].strip(),
                    'role': '',
                    'status': '',
                }
                desc = parts[1].strip()
                if 'Primary' in desc:
                    db_info['role'] = 'PRIMARY'
                elif 'Physical standby' in desc:
                    db_info['role'] = 'PHYSICAL STANDBY'
                elif 'Snapshot standby' in desc:
                    db_info['role'] = 'SNAPSHOT STANDBY'
                elif 'Logical standby' in desc:
                    db_info['role'] = 'LOGICAL STANDBY'
                result['databases'].append(db_info)
        elif line.startswith('Fast-Start Failover:'):
            result['fast_start_failover'] = line.split(':', 1)[1].strip()
        elif line.startswith('Configuration Status:'):
            result['status'] = line.split(':', 1)[1].strip()
    return result


def dgmgrl_show_configuration(module, output_format):
    """Run SHOW CONFIGURATION and return parsed result."""
    rc, stdout, stderr = run_dgmgrl(module, ['SHOW CONFIGURATION VERBOSE'], output_format)
    if rc != 0:
        if 'ORA-16532' in stdout or 'not yet created' in stdout.lower():
            return {'status': 'NOT_CONFIGURED', 'name': '', 'databases': []}
        module.fail_json(msg='DGMGRL SHOW CONFIGURATION failed: %s %s' % (stdout, stderr), changed=False)

    if output_format == 'json':
        try:
            return json.loads(stdout)
        except (ValueError, TypeError):
            return parse_show_configuration(stdout)
    return parse_show_configuration(stdout)


def dgmgrl_show_database(module, db_name, output_format):
    """Run SHOW DATABASE and return output."""
    rc, stdout, _stderr = run_dgmgrl(module, ['SHOW DATABASE %s VERBOSE' % db_name], output_format)
    if rc != 0:
        return None
    return stdout


def dgmgrl_create_configuration(module):
    """Create a Data Guard broker configuration."""
    config_name = module.params["configuration_name"]
    primary_db = module.params["primary_database"]
    connect_id = module.params["connect_identifier"]

    if not config_name or not primary_db or not connect_id:
        module.fail_json(
            msg='configuration_name, primary_database, and connect_identifier are required to create a configuration',
            changed=False
        )

    cmd = "CREATE CONFIGURATION %s AS PRIMARY DATABASE IS %s CONNECT IDENTIFIER IS '%s'" % (
        config_name, primary_db, connect_id
    )
    rc, stdout, stderr = run_dgmgrl(module, [cmd])
    if rc != 0 and 'already exists' not in stdout.lower():
        module.fail_json(msg='Failed to create configuration: %s %s' % (stdout, stderr), changed=False)
    return rc == 0 or 'already exists' in stdout.lower()


def dgmgrl_add_database(module):
    """Add a database to the Data Guard configuration."""
    db_name = module.params["database_name"]
    connect_id = module.params["connect_identifier"]

    if not db_name or not connect_id:
        module.fail_json(
            msg='database_name and connect_identifier are required to add a database',
            changed=False
        )

    cmd = "ADD DATABASE %s AS CONNECT IDENTIFIER IS '%s'" % (db_name, connect_id)
    rc, stdout, stderr = run_dgmgrl(module, [cmd])
    if rc != 0 and 'already' not in stdout.lower():
        module.fail_json(msg='Failed to add database: %s %s' % (stdout, stderr), changed=False)
    return True


def dgmgrl_remove_database(module, db_name):
    """Remove a database from the configuration."""
    rc, stdout, stderr = run_dgmgrl(module, ['REMOVE DATABASE %s' % db_name])
    if rc != 0 and 'not found' not in stdout.lower():
        module.fail_json(msg='Failed to remove database: %s %s' % (stdout, stderr), changed=False)
    return True


def dgmgrl_remove_configuration(module):
    """Remove the entire Data Guard configuration."""
    rc, stdout, stderr = run_dgmgrl(module, ['REMOVE CONFIGURATION'])
    if rc != 0 and 'not yet created' not in stdout.lower():
        module.fail_json(msg='Failed to remove configuration: %s %s' % (stdout, stderr), changed=False)
    return True


def dgmgrl_enable(module, target_type, target_name=None):
    """Enable configuration or database."""
    if target_type == 'configuration':
        cmd = 'ENABLE CONFIGURATION'
    else:
        cmd = 'ENABLE DATABASE %s' % target_name
    rc, stdout, stderr = run_dgmgrl(module, [cmd])
    if rc != 0 and 'already enabled' not in stdout.lower():
        module.fail_json(msg='Failed to enable %s: %s %s' % (target_type, stdout, stderr), changed=False)
    return True


def dgmgrl_disable(module, target_type, target_name=None):
    """Disable configuration or database."""
    if target_type == 'configuration':
        cmd = 'DISABLE CONFIGURATION'
    else:
        cmd = 'DISABLE DATABASE %s' % target_name
    rc, stdout, stderr = run_dgmgrl(module, [cmd])
    if rc != 0 and 'already disabled' not in stdout.lower():
        module.fail_json(msg='Failed to disable %s: %s %s' % (target_type, stdout, stderr), changed=False)
    return True


def dgmgrl_switchover(module, db_name):
    """Perform a switchover to the specified database."""
    if not db_name:
        module.fail_json(msg='database_name is required for switchover', changed=False)
    rc, stdout, stderr = run_dgmgrl(module, ['SWITCHOVER TO %s' % db_name])
    if rc != 0:
        module.fail_json(msg='Switchover failed: %s %s' % (stdout, stderr), changed=False)
    return True


def dgmgrl_failover(module, db_name):
    """Perform a failover to the specified database."""
    if not db_name:
        module.fail_json(msg='database_name is required for failover', changed=False)
    rc, stdout, stderr = run_dgmgrl(module, ['FAILOVER TO %s' % db_name])
    if rc != 0:
        module.fail_json(msg='Failover failed: %s %s' % (stdout, stderr), changed=False)
    return True


def dgmgrl_convert_database(module, db_name, target_type):
    """Convert database to snapshot or physical standby."""
    if not db_name:
        module.fail_json(msg='database_name is required for convert', changed=False)
    cmd = 'CONVERT DATABASE %s TO %s' % (db_name, target_type)
    rc, stdout, stderr = run_dgmgrl(module, [cmd])
    if rc != 0:
        module.fail_json(msg='Convert failed: %s %s' % (stdout, stderr), changed=False)
    return True


def dgmgrl_set_properties(module, db_name, properties):
    """Set properties on a database."""
    if not db_name or not properties:
        return
    commands = []
    for prop, value in properties.items():
        commands.append("EDIT DATABASE %s SET PROPERTY %s='%s'" % (db_name, prop, value))
    rc, stdout, stderr = run_dgmgrl(module, commands)
    if rc != 0:
        module.fail_json(msg='Failed to set properties: %s %s' % (stdout, stderr), changed=False)


def dgmgrl_set_protection_mode(module, protection_mode):
    """Set the protection mode."""
    mode_map = {
        'maximum_protection': 'MAXPROTECTION',
        'maximum_availability': 'MAXAVAILABILITY',
        'maximum_performance': 'MAXPERFORMANCE',
    }
    mode = mode_map.get(protection_mode)
    if not mode:
        module.fail_json(msg='Invalid protection mode: %s' % protection_mode, changed=False)

    cmd = 'EDIT CONFIGURATION SET PROTECTION MODE AS %s' % mode
    rc, stdout, stderr = run_dgmgrl(module, [cmd])
    if rc != 0:
        module.fail_json(msg='Failed to set protection mode: %s %s' % (stdout, stderr), changed=False)
    return True


def dgmgrl_set_state(module, db_name, db_state):
    """Set database transport/apply state."""
    cmd = "EDIT DATABASE %s SET STATE='%s'" % (db_name, db_state.upper())
    rc, stdout, stderr = run_dgmgrl(module, [cmd])
    if rc != 0:
        module.fail_json(msg='Failed to set state: %s %s' % (stdout, stderr), changed=False)
    return True


def dgmgrl_manage_fsfo(module, fsfo_state):
    """Enable or disable Fast-Start Failover."""
    if fsfo_state == 'enabled':
        cmd = 'ENABLE FAST_START FAILOVER'
    else:
        cmd = 'DISABLE FAST_START FAILOVER'
    rc, stdout, stderr = run_dgmgrl(module, [cmd])
    if rc != 0:
        module.fail_json(msg='Failed to manage FSFO: %s %s' % (stdout, stderr), changed=False)
    return True


def dgmgrl_manage_observer(module, observer_state):
    """Start or stop the FSFO observer."""
    if observer_state == 'started':
        cmd = 'START OBSERVER IN BACKGROUND'
    else:
        cmd = 'STOP OBSERVER'
    rc, stdout, stderr = run_dgmgrl(module, [cmd])
    if rc != 0:
        module.fail_json(msg='Failed to manage observer: %s %s' % (stdout, stderr), changed=False)
    return True


def dgmgrl_add_far_sync(module):
    """Add a Far Sync instance."""
    fs_name = module.params["far_sync_name"]
    fs_connect = module.params["far_sync_connect_identifier"]

    if not fs_name or not fs_connect:
        module.fail_json(
            msg='far_sync_name and far_sync_connect_identifier are required',
            changed=False
        )

    cmd = "ADD FAR_SYNC %s AS CONNECT IDENTIFIER IS '%s'" % (fs_name, fs_connect)
    rc, stdout, stderr = run_dgmgrl(module, [cmd])
    if rc != 0 and 'already' not in stdout.lower():
        module.fail_json(msg='Failed to add Far Sync: %s %s' % (stdout, stderr), changed=False)
    return True


def dgmgrl_validate(module, db_name):
    """Validate a database configuration."""
    cmd = 'VALIDATE DATABASE %s' % db_name
    rc, stdout, stderr = run_dgmgrl(module, [cmd])
    return {'rc': rc, 'output': stdout, 'errors': stderr}


# ============================================================================
# SQL Mode Functions
# ============================================================================

def sql_get_database_info(conn):
    """Get Data Guard related information from V$DATABASE."""
    sql = """SELECT DATABASE_ROLE, PROTECTION_MODE, PROTECTION_LEVEL,
                    SWITCHOVER_STATUS, DATAGUARD_BROKER, FORCE_LOGGING,
                    FLASHBACK_ON, DB_UNIQUE_NAME
             FROM V$DATABASE"""
    return conn.execute_select_to_dict(sql, fetchone=True)


def sql_get_dataguard_stats(conn):
    """Get transport and apply lag from V$DATAGUARD_STATS."""
    sql = "SELECT NAME, VALUE, UNIT, TIME_COMPUTED, DATUM_TIME FROM V$DATAGUARD_STATS"
    return conn.execute_select_to_dict(sql, fail_on_error=False) or []


def sql_get_archive_dest_status(conn):
    """Get archive destination status."""
    sql = """SELECT DEST_ID, STATUS, TYPE, DATABASE_MODE, RECOVERY_MODE,
                    GAP_STATUS, SYNCHRONIZED, ERROR, DB_UNIQUE_NAME
             FROM V$ARCHIVE_DEST_STATUS
             WHERE STATUS != 'INACTIVE'"""
    return conn.execute_select_to_dict(sql, fail_on_error=False) or []


def sql_get_dataguard_processes(conn):
    """Get active Data Guard processes."""
    sql = """SELECT ROLE, ACTION, CLIENT_ROLE, THREAD#, SEQUENCE#, BLOCK#
             FROM V$DATAGUARD_PROCESS"""
    return conn.execute_select_to_dict(sql, fail_on_error=False) or []


def sql_start_apply(conn, _module):
    """Start managed recovery (redo apply)."""
    # Check if MRP is already running
    processes = sql_get_dataguard_processes(conn)
    for p in processes:
        if p.get('action', '').upper() in ('APPLYING_LOG', 'APPLYING'):
            return  # Already running, idempotent

    conn.execute_ddl('ALTER DATABASE RECOVER MANAGED STANDBY DATABASE USING CURRENT LOGFILE DISCONNECT')


def sql_stop_apply(conn, _module):
    """Stop managed recovery."""
    processes = sql_get_dataguard_processes(conn)
    mrp_running = False
    for p in processes:
        if p.get('action', '').upper() in ('APPLYING_LOG', 'APPLYING'):
            mrp_running = True
            break
    if not mrp_running:
        return  # Already stopped, idempotent

    conn.execute_ddl('ALTER DATABASE RECOVER MANAGED STANDBY DATABASE CANCEL')


def sql_set_force_logging(conn, _module, enable):
    """Enable or disable force logging."""
    db_info = sql_get_database_info(conn)
    current = db_info.get('force_logging', 'NO')

    if enable == 'enable' and current == 'YES':
        return  # Already enabled
    if enable == 'disable' and current == 'NO':
        return  # Already disabled

    if enable == 'enable':
        conn.execute_ddl('ALTER DATABASE FORCE LOGGING')
    else:
        conn.execute_ddl('ALTER DATABASE NO FORCE LOGGING')


def sql_set_protection_mode(conn, module, protection_mode):
    """Set protection mode via SQL."""
    mode_map = {
        'maximum_protection': 'MAXIMIZE PROTECTION',
        'maximum_availability': 'MAXIMIZE AVAILABILITY',
        'maximum_performance': 'MAXIMIZE PERFORMANCE',
    }
    target = mode_map.get(protection_mode)
    if not target:
        module.fail_json(msg='Invalid protection mode: %s' % protection_mode, changed=False)

    db_info = sql_get_database_info(conn)
    current = db_info.get('protection_mode', '')

    if target.replace('MAXIMIZE ', 'MAXIMUM ') == current:
        return  # Already set

    conn.execute_ddl('ALTER DATABASE SET STANDBY DATABASE TO %s' % target)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            # Standard connection params (for SQL mode)
            user=dict(required=False, aliases=['un', 'username']),
            password=dict(required=False, no_log=True, aliases=['pw']),
            mode=dict(default='normal', choices=["normal", "sysdba", "sysdg", "sysoper", "sysasm"]),
            hostname=dict(required=False, default='localhost', aliases=['host']),
            port=dict(required=False, default=1521, type='int'),
            service_name=dict(required=False, aliases=['sn']),
            dsn=dict(required=False, aliases=['datasource_name']),
            oracle_home=dict(required=False, aliases=['oh']),
            session_container=dict(required=False),

            # Data Guard mode
            mode_dg=dict(default='broker', choices=['broker', 'sql']),
            state=dict(default='status',
                       choices=['present', 'absent', 'enabled', 'disabled', 'status',
                                'switchover', 'failover', 'snapshot_standby', 'physical_standby']),

            # DGMGRL connection
            dgmgrl_user=dict(required=False),
            dgmgrl_password=dict(required=False, no_log=True),
            dgmgrl_connect_identifier=dict(required=False),
            dgmgrl_as=dict(default='sysdg', choices=['sysdba', 'sysdg']),

            # Configuration
            configuration_name=dict(required=False),
            primary_database=dict(required=False),
            connect_identifier=dict(required=False),

            # Database member
            database_name=dict(required=False),

            # Properties
            properties=dict(required=False, type='dict'),

            # Protection mode
            protection_mode=dict(required=False,
                                choices=['maximum_protection', 'maximum_availability',
                                         'maximum_performance']),

            # Database state
            database_state=dict(required=False,
                               choices=['transport-on', 'transport-off',
                                        'apply-on', 'apply-off']),

            # Fast-Start Failover
            fsfo=dict(required=False, choices=['enabled', 'disabled']),
            fsfo_target=dict(required=False),

            # Far Sync
            far_sync_name=dict(required=False),
            far_sync_connect_identifier=dict(required=False),

            # Observer
            observer_state=dict(required=False, choices=['started', 'stopped']),

            # Output format (26ai JSON)
            output_format=dict(default='text', choices=['text', 'json']),

            # SQL mode specific
            force_logging=dict(required=False, choices=['enable', 'disable']),
            apply_state=dict(required=False, choices=['started', 'stopped']),
        ),
        supports_check_mode=True,
    )

    sanitize_string_params(module.params)

    if module.params["mode_dg"] == 'broker':
        _run_broker_mode(module)
    else:
        _run_sql_mode(module)


def _run_broker_mode(module):
    """Handle all broker (DGMGRL) operations."""
    state = module.params["state"]
    database_name = module.params["database_name"]
    output_format = module.params["output_format"]

    if module.check_mode:
        module.exit_json(changed=False, msg='Check mode: no broker operations executed')

    if state == 'status':
        _broker_status(module, database_name, output_format)
    elif state == 'present':
        _broker_present(module, database_name, output_format)
    elif state == 'absent':
        _broker_absent(module, database_name)
    elif state == 'enabled':
        _broker_enable_disable(module, database_name, enable=True)
    elif state == 'disabled':
        _broker_enable_disable(module, database_name, enable=False)
    elif state == 'switchover':
        dgmgrl_switchover(module, database_name)
        module.exit_json(changed=True, msg='Switchover to %s completed' % database_name)
    elif state == 'failover':
        dgmgrl_failover(module, database_name)
        module.exit_json(changed=True, msg='Failover to %s completed' % database_name)
    elif state == 'snapshot_standby':
        dgmgrl_convert_database(module, database_name, 'SNAPSHOT STANDBY')
        module.exit_json(changed=True, msg='Converted %s to snapshot standby' % database_name)
    elif state == 'physical_standby':
        dgmgrl_convert_database(module, database_name, 'PHYSICAL STANDBY')
        module.exit_json(changed=True, msg='Converted %s to physical standby' % database_name)


def _broker_status(module, database_name, output_format):
    """Handle broker status query."""
    config = dgmgrl_show_configuration(module, output_format)
    db_detail = None
    validate_result = None
    if database_name:
        db_detail = dgmgrl_show_database(module, database_name, output_format)
        validate_result = dgmgrl_validate(module, database_name)
    module.exit_json(
        changed=False,
        configuration=config,
        database_detail=db_detail,
        validate=validate_result,
    )


def _broker_present(module, database_name, output_format):
    """Handle broker present state (create/add/configure)."""
    changed = False
    config = dgmgrl_show_configuration(module, 'text')

    if module.params["configuration_name"] and config.get('status') == 'NOT_CONFIGURED':
        dgmgrl_create_configuration(module)
        changed = True

    if database_name and config.get('status') != 'NOT_CONFIGURED':
        existing_dbs = [d['name'] for d in config.get('databases', [])]
        if database_name.upper() not in [d.upper() for d in existing_dbs]:
            dgmgrl_add_database(module)
            changed = True

    if module.params["far_sync_name"]:
        dgmgrl_add_far_sync(module)
        changed = True
    if module.params["properties"] and database_name:
        dgmgrl_set_properties(module, database_name, module.params["properties"])
        changed = True
    if module.params["protection_mode"]:
        dgmgrl_set_protection_mode(module, module.params["protection_mode"])
        changed = True
    if module.params["database_state"] and database_name:
        dgmgrl_set_state(module, database_name, module.params["database_state"])
        changed = True
    if module.params["fsfo"]:
        dgmgrl_manage_fsfo(module, module.params["fsfo"])
        changed = True
    if module.params["observer_state"]:
        dgmgrl_manage_observer(module, module.params["observer_state"])
        changed = True

    config = dgmgrl_show_configuration(module, output_format)
    module.exit_json(changed=changed, configuration=config, msg='Data Guard configuration updated')


def _broker_absent(module, database_name):
    """Handle broker absent state (remove)."""
    config = dgmgrl_show_configuration(module, 'text')
    if config.get('status') == 'NOT_CONFIGURED':
        module.exit_json(changed=False, msg='No configuration exists')

    changed = False
    if database_name:
        existing_dbs = [d['name'] for d in config.get('databases', [])]
        if database_name.upper() in [d.upper() for d in existing_dbs]:
            dgmgrl_remove_database(module, database_name)
            changed = True
    else:
        dgmgrl_remove_configuration(module)
        changed = True

    module.exit_json(changed=changed, msg='Data Guard resources removed')


def _broker_enable_disable(module, database_name, enable):
    """Handle broker enable/disable operations."""
    func = dgmgrl_enable if enable else dgmgrl_disable
    if database_name:
        func(module, 'database', database_name)
    else:
        func(module, 'configuration')
    action = 'Enabled' if enable else 'Disabled'
    module.exit_json(changed=True, msg='%s successfully' % action)


def _run_sql_mode(module):
    """Handle all SQL mode operations."""
    state = module.params["state"]
    protection_mode = module.params["protection_mode"]
    conn = oracleConnection(module)

    if state == 'status':
        module.exit_json(
            changed=False,
            database=sql_get_database_info(conn),
            dataguard_stats=sql_get_dataguard_stats(conn),
            archive_dest_status=sql_get_archive_dest_status(conn),
            dataguard_processes=sql_get_dataguard_processes(conn),
        )

    apply_state = module.params["apply_state"]
    if apply_state == 'started':
        sql_start_apply(conn, module)
    elif apply_state == 'stopped':
        sql_stop_apply(conn, module)

    force_logging = module.params["force_logging"]
    if force_logging:
        sql_set_force_logging(conn, module, force_logging)

    if protection_mode:
        sql_set_protection_mode(conn, module, protection_mode)

    module.exit_json(
        changed=conn.changed,
        ddls=conn.ddls,
        database=sql_get_database_info(conn),
        msg='Data Guard SQL operations completed',
    )


from ansible.module_utils.basic import *  # noqa: F403

try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import (  # noqa: E501
        oracleConnection, sanitize_string_params,
    )
except ImportError:
    def sanitize_string_params(_params):
        pass

if __name__ == '__main__':
    main()
