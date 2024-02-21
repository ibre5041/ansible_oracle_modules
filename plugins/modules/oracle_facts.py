#!/bin/python3
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_facts
short_description: Returns some facts about Oracle DB
description:
  - Returns some facts about Oracle DB
  - See connection parameters for oracle_ping
version_added: "3.0.0"
options:
  password_file:
    description: Detect location of password file
    required: false
  instance:
    description: Query values from v$instance
    required: false
    default: false
  database:
    description: Query values from v$database
    required: false
    default: true
  userenv:
    description: Query values from userenv
    required: false
    default: true
  option:
    description: Query values from v$option
    required: false
    default: false
  parameter:
    description: Query values from userenv
    required: false
    default: false
  tablespaces:
    description: Dislay information about permanent tablespaces
    required: false
    default: false
  temp:
    description: Dislay information about temporary tablespaces
    required: false
    default: false
  redo:
    description: Query info about redologs
    required: false
    default: None
    choices: [None, 'detail', 'summary']
  standby:
    description: Query info about standby redologs
    required: false
    default: None
    choices: [None, 'detail', 'summary']
notes:
  - cx_Oracle needs to be installed
  - Oracle RDBMS 10gR2 or later required
requirements: ["cx_Oracle"]
author:
  - Ilmar Kerm, ilmar.kerm@gmail.com, @ilmarkerm
  - Ivan Brezina
'''

EXAMPLES = '''
- name: Oracle DB facts
  oracle_facts:
    mode: sysdba
    userenv: false
    database: false
    instance: false
    password_file: true
    redo: summary
    standby: summary
    parameter:
      - audit_file_dest
      - db_name
      - db_unique_name
      - instance_name
      - service_names
  register: database_facts

- name: database facts
  debug:
    var: database_facts
'''

import os
import sys


def rows_to_dict_list(cursor):
    columns = [i[0] for i in cursor.description]
    return [dict(zip(columns, row)) for row in cursor]


def query_result(connection, query, params = []):
    c = connection.cursor()
    c.execute(query, params)
    res = rows_to_dict_list(c)
    c.close()
    return res


def star_query(connection, rowsource):
    return query_result(connection, "SELECT * FROM %s" % rowsource)


def detect_password_file(module):
    oracle_sid = sid = os.environ['ORACLE_SID']
    oracle_home = sid = os.environ['ORACLE_HOME']

    h = oracle_homes(module)
    h.list_crs_instances()
    h.list_processes()
    h.parse_oratab()

    if h.crs_home:
        srvctl = os.path.join(h.crs_home, 'bin', 'srvctl')
        proc = subprocess.Popen([srvctl, 'config', 'database', '-d', oracle_sid], stdout=subprocess.PIPE)

        for line in iter(proc.stdout.readline, ''):
            if line.decode('utf-8').startswith('Oracle home:'):
                ORACLE_HOME = line.decode('utf-8').split(': ')[1].strip()
            if line.decode('utf-8').startswith('Spfile:'):
                SPFILE = line.decode('utf-8').split(': ')[1].strip()
            if line.decode('utf-8').startswith('Password file:'):
                PASSWORD = line.decode('utf-8').split(': ')[1].strip()
            proc.poll()
            if line == b'':
                break
    else:
        ORACLE_HOME = None
        SPFILE = None
        PASSWORD = None

    if not PASSWORD:
        orabasehome = os.path.join(h.crs_home, 'bin', 'orabasehome')
        ORABASEHOME = None
        try:
            proc = subprocess.Popen([orabasehome], stdout=subprocess.PIPE)
            for line in iter(proc.stdout.readline, ''):
                if line.decode('utf-8').strip():
                    ORABASEHOME = line.decode('utf-8').strip()
                proc.poll()
                if line == b'':
                    break
        except FileNotFoundError as e:
            # assuming were on Oracle 12c or lower, $ORACLE_HOME/bin/orabasehome is not present
            ORABASEHOME = oracle_home

        if ORABASEHOME:
            pwfile = os.path.join(ORABASEHOME, 'dbs', 'orapw{}'.format(oracle_sid))
            if os.access(pwfile, os.R_OK):
                PASSWORD = pwfile

    return PASSWORD


def query_database(module, conn):
    database = star_query(conn, 'v$database')[0]
    if 'CDB' not in database:
        database.update({'CDB': 'NO'})
    return database

def query_instance(module, conn):
    instance = star_query(conn, 'v$instance')[0]
    return instance


def query_tablespaces(module, conn):
    if conn.version >= '12.1':
        SQL = """
        select ts.con_id, ts.name, ts.bigfile, round(sum(bytes)/1024/1024) size_mb, count(*) datafiles#
        from v$tablespace ts
        join v$datafile df on df.ts#=ts.ts# and df.con_id=ts.con_id
        group by ts.name, ts.bigfile, ts.con_id 
        order by 1,2"""
    else:
        SQL = """
        select 0 con_id, ts.name, ts.bigfile, round(sum(bytes)/1024/1024) size_mb, count(*) datafiles#
        from v$tablespace ts 
        join v$datafile df on df.ts#=ts.ts# 
        group by ts.name, ts.bigfile 
        order by 1,2"""

    tablespaces = query_result(conn, SQL)
    return tablespaces


def query_temp(module, conn):
    if conn.version >= '12.1':
        SQL = """
        select ts.con_id, ts.name, ts.bigfile, round(sum(bytes)/1024/1024) size_mb, count(*) tempfiles# 
        from v$tablespace ts 
        join v$tempfile df on df.ts#=ts.ts# and df.con_id=ts.con_id 
        group by ts.name, ts.bigfile, ts.con_id 
        order by 1,2"""
    else:
        SQL = """
        select 0 con_id, ts.name, ts.bigfile, round(sum(bytes)/1024/1024) size_mb, count(*) tempfiles# 
        from v$tablespace ts 
        join v$tempfile df on df.ts#=ts.ts# 
        group by ts.name, ts.bigfile 
        order by 1,2"""

    temp = query_result(conn, SQL)
    return temp


def query_userenv(module, conn):
    # USERENV
    sql = """
    SELECT sys_context('USERENV','CURRENT_USER') current_user
        , sys_context('USERENV','DATABASE_ROLE') database_role
        , sys_context('USERENV','ISDBA') isdba """
    if conn.version >= '12.1':
        sql += ", to_number(sys_context('USERENV','CON_ID')) con_id " \
               ", sys_context('USERENV','CON_NAME') con_name "
    if conn.version >= '11.1':
        sql += ", to_number(sys_context('USERENV','CURRENT_EDITION_ID')) CURRENT_EDITION_ID " \
               ", sys_context('USERENV','CURRENT_EDITION_NAME') CURRENT_EDITION_NAME "
    sql += " FROM DUAL"
    userenv = query_result(conn, sql)[0]
    return userenv


def query_redo(module, conn):
    if module.params['redo'].lower() == 'summary':
        SQL = "select thread# THREAD, count(1) as COUNT, max(round(bytes/1024/1024)) as SIZE_MB" \
              ", min(group#) min_seq, max(group#) max_seq " \
              "from v$log group by THREAD#"
    else:
        SQL = "select group#, thread#, sequence#, round(bytes/1024/1024) mb, blocksize, archived, status " \
              "from v$log order by thread#,group#"
    redolog = query_result(conn, SQL)
    return redolog


def query_standby(module, conn):
    if module.params['standby'].lower() == 'summary':
        SQL = "select thread# THREAD, count(1) as COUNT, max(round(bytes/1024/1024)) as SIZE_MB" \
              ", min(group#) min_seq, max(group#) max_seq " \
              "from v$standby_log group by THREAD#"
    else:
        SQL = "select group#, thread#, sequence#, round(bytes/1024/1024) mb, blocksize, archived, status " \
              "from v$standby_log order by thread#,group#"
    redolog = query_result(conn, SQL)
    return redolog


def query_params(module, conn):
    params = module.params['parameter']
    if isinstance(params, list):
        p = ','.join(["'{}'".format(p.lower()) for p in params])
        filter = ' WHERE NAME in ({})'.format(p)
    elif params.lower() == '@all@':
        filter = ''
    elif params.lower() == '@modified@':
        filter = " WHERE ISDEFAULT = FALSE"
    elif params.lower():
        filter = " WHERE NAME = '{}'".format(params.lower())
    else:
        filter = ''
    SQL = 'select name, value, isdefault from v$parameter ' + filter
    resultset = query_result(conn, SQL)
    result = {}
    for p in resultset:
        result[p['NAME']] = {'isdefault': p['ISDEFAULT'], 'value': p['VALUE']}
    return result


def main():
    module = AnsibleModule(
        argument_spec=dict(
            user          = dict(required=False, aliases=['un', 'username']),
            password      = dict(required=False, no_log=True, aliases=['pw']),
            mode          = dict(default='normal', choices=["normal", "sysdba"]),
            hostname      = dict(required=False, default='localhost', aliases=['host']),
            port          = dict(required=False, default=1521, type='int'),
            service_name  = dict(required=False, aliases=['sn']),
            oracle_home   = dict(required=False, aliases=['oh']),
            
            password_file=dict(default=False, type='bool'),
            instance=dict(default=False, type='bool'),
            database=dict(default=True, type='bool'),
            userenv=dict(default=True, type='bool'),
            option=dict(default=False, type='bool'),
            parameter=dict(default=[], type='list'),
            tablespaces=dict(default=False, type='bool'),
            temp=dict(default=False, type='bool'),
            redo=dict(default=None, choices=[None, "detail", "summary"]),
            standby=dict(default=None, choices=[None, "detail", "summary"])
        ),
        supports_check_mode=True
    )

    # Connect to database
    conn = oracle_connect(module)

    if conn.version < "10.2":
        module.fail_json(msg="Database version must be 10gR2 or greater", changed=False)
    #
    if module.check_mode:
        module.exit_json(changed=False)
    #
    sid = os.environ['ORACLE_SID']
    facts = {sid: {'version': conn.version}}
    db = facts[sid]

    if module.params["password_file"]:
        password_file = detect_password_file(module)
        db.update({'password_file': password_file})

    if module.params["instance"]:
        instance = query_instance(module, conn)
        db.update({'database': instance})

    if module.params["database"]:
        database = query_database(module, conn)
        db.update({'database': database})

    if module.params["tablespaces"]:
        tablespaces = query_tablespaces(module, conn)
        db.update({'tablespaces': tablespaces})

    if module.params["temp"]:
        temp = query_temp(module, conn)
        db.update({'temp': temp})

    if module.params['userenv']:
        userenv = query_userenv(module, conn)
        db.update({sid: {'userenv': userenv}})

    if module.params['redo']:
        redo = query_redo(module, conn)
        db.update({'redo': redo})

    if module.params['standby']:
        standby = query_standby(module, conn)
        db.update({'standby': standby})

    if module.params['option']:
        option = star_query(conn, "v$option")
        db.update({'option': option})

    if module.params['parameter']:
        parameters = query_params(module, conn)
        db.update({'parameter': parameters})

    rac = query_result(conn, "SELECT inst_id, instance_name, host_name, startup_time FROM gv$instance ORDER BY inst_id")

    try:
        if database['CDB'] == 'YES':
            pdb = query_result(conn, "SELECT con_id, rawtohex(guid) guid_hex, name, open_mode FROM v$pdbs ORDER BY name")
        else:
            pdb = []
    except:
        pdb = []

    db.update({'rac': rac, 'pdb': pdb})
    module.exit_json(msg='', changed=False, ansible_facts=facts)


from ansible.module_utils.basic import *

# In these we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used                              
#try:
#    from ansible.module_utils.oracle_utils import oracle_connect
#    from ansible.module_utils.oracle_homes import oracle_homes
#except:
#    pass

try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracle_connect
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_homes import oracle_homes
except:    
    pass


if __name__ == '__main__':
    main()
