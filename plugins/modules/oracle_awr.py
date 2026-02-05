#!/usr/bin/python
# -*- coding: utf-8 -*-


DOCUMENTATION = '''
---
module: oracle_awr
short_description: Manage AWR configuration
description:
  - Manage AWR configuration
  - Can be run locally on the controlmachine or on a remote host
version_added: "2.2.1"
options:
  hostname:
    description: The Oracle database host
    required: False
    default: localhost
    aliases: ['host']
  port:
    description: The listener port number on the host
    required: False
    default: 1521
  service_name:
    description: The database service name to connect to
    required: False
    aliases: ['sn']
  dsn:
    description: "Oracle Data Source Name, i.e. Oracle connection string or TNS alias. This parameter has precedence over hostname, port and service_name"
    required: False
    aliases: ['datasource_name']
  user:
    description: The Oracle user name to connect to the database
    required: False    
    aliases: ['un', 'username']
  password:
    description: The Oracle user password for the user
    required: False
    aliases: ['pw']
  mode:
    description: The mode with which to connect to the database
    required: False
    default: normal
    choices: ['normal','sysdba']
  snapshot_interval_min:
    description: AWR snapshot interval in minutes; 0 disables
    default: 60
    type: int
    aliases: ['interval']
  snapshot_retention_days:
    description: AWR snapshot retention time in days
    default: 8
    type: int
    aliases: ['retention']
notes:
  - oracledb needs to be installed
  - Oracle RDBMS 10gR2 or later required
requirements: [ "oracledb" ]
author: "Ilmar Kerm, ilmar.kerm@gmail.com, @ilmarkerm"
'''

EXAMPLES = '''
---
- hosts: localhost
  vars:
    oraclehost: 192.168.56.101
    oracleport: 1521
    oracleservice: orcl12c
    oracleuser: system
    oraclepassword: oracle
    oracle_env:
      ORACLE_HOME: /usr/lib/oracle/12.1/client64
      LD_LIBRARY_PATH: /usr/lib/oracle/12.1/client64/lib
  tasks:
    - name: set AWR settings
      oracle_awr:
        hostname: "{{ oraclehost }}"
        port: "{{ oracleport }}"
        service_name: "{{ oracleservice }}"
        user: "{{ oracleuser }}"
        password: "{{ oraclepassword }}"
        interval: 30
        retention: 40
      environment: "{{ oracle_env }}"
'''

from datetime import timedelta

def query_existing(conn):
    # PDB / ADB way
    sql_adb = """
    SELECT
    c.snap_interval
    , c.retention
    , p.dbid
    , src_dbname
    , c.con_id as con_id
    FROM dba_hist_wr_control c
    JOIN v$pdbs p ON c.dbid = p.dbid and c.con_id = p.con_id
    WHERE p.name = SYS_CONTEXT('USERENV', 'CON_NAME')
    """
    # Non CDB way
    sql_19c = """
        SELECT
    c.snap_interval
    , c.retention
    FROM dba_hist_wr_control c
    WHERE c.dbid in (select dbid from v$database)
    """
    r = conn.execute_select_to_dict(sql_adb, fetchone=True)
    if not r:
        r = conn.execute_select_to_dict(sql_19c, fetchone=True)        
    return r


# Ansible code
def main():
    global lconn, conn, msg, module
    msg = ['']
    module = AnsibleModule(
        argument_spec = dict(
            user          = dict(required=False, aliases=['un', 'username']),
            password      = dict(required=False, no_log=True, aliases=['pw']),
            mode          = dict(default='normal', choices=["normal", "sysdba"]),
            hostname      = dict(required=False, default='localhost', aliases=['host']),
            port          = dict(required=False, default=1521, type='int'),
            service_name  = dict(required=False, aliases=['sn']),
            dsn           = dict(required=False, aliases=['datasource_name']),
            oracle_home   = dict(required=False, aliases=['oh']),
            snapshot_interval_min = dict(default=None, type='int', aliases=['interval']), # Oracle default: 60 min
            snapshot_retention_days = dict(default=None, type='int', aliases=['retention']) # Oracle default 8 days
        ),
        required_together=[('user', 'password')],
        #required_one_of=[('snapshot_interval_min', 'snapshot_retention_days')],
        supports_check_mode=True
    )

    # Check input parameters
    snapshot_interval_min = module.params['snapshot_interval_min']
    snapshot_retention_days = module.params['snapshot_retention_days']

    if snapshot_interval_min is not None and 0 < snapshot_interval_min <= 10:
        module.fail_json(msg="Snapshot interval must be >= 10 or 0", changed=conn.changed, ddls=conn.ddls)
    if snapshot_interval_min is not None and snapshot_interval_min > 1000:
        module.fail_json(msg="You probably entered incorrect snapshot interval time", changed=conn.changed, ddls=conn.ddls)

    if snapshot_retention_days and snapshot_retention_days < 0:
        module.fail_json(msg="Snapshot retention must be >= 0", changed=conn.changed, ddls=conn.ddls)

    # Connect to database
    conn = oracleConnection(module)

    if conn.version < "10.2":
        module.fail_json(msg="Database version must be 10gR2 or greater", changed=False)
    #
    snap_retention = timedelta(days=snapshot_retention_days) if snapshot_retention_days is not None else None
    snap_interval = timedelta(minutes=snapshot_interval_min) if snapshot_interval_min is not None else None

    result = query_existing(conn)
    if not result:
        module.fail_json(msg="Failed to query AWR settings", changed=False)
    params = dict()
    if snap_retention is not None and snap_retention != result['retention']:
        params['retention'] = snapshot_retention_days * 1440
    else:
        params['retention'] = None

    if snap_interval is not None and snap_interval != result['snap_interval']:
        params['interval'] = snapshot_interval_min
    else:
        params['interval'] = None

    if any(params.values()):
        conn.execute_ddl("CALL DBMS_WORKLOAD_REPOSITORY.MODIFY_SNAPSHOT_SETTINGS(interval=>:interval, retention=>:retention)", params=params)

    if conn.changed:
        msg = "AWR snapshots have been updated"
    else:
        msg = "AWR snapshots have not been updated"
    result = query_existing(conn)
    snap_interval = int(result['snap_interval'].total_seconds() // 60)
    retention = int(result['retention'].total_seconds() // 60 // 60 // 24)
    module.exit_json(msg=msg,  changed=conn.changed, ddls=conn.ddls, retention=retention, snap_interval=snap_interval)


from ansible.module_utils.basic import *

# In thise we do import from local project project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No colletions are used
#try:
#    from ansible.module_utils.oracle_utils import oracleConnection
#except:
#    pass

# In thise we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracleConnection    
except:
    pass


if __name__ == '__main__':
    main()
