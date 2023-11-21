#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_sql
short_description: Execute arbitrary sql
description:
    - Execute arbitrary sql against an Oracle database
version_added: "2.1.0.0"
options:
    username:
        description:
            - The database username to connect to the database
        required: false
        default: None
        aliases: ['un']
    password:
        description:
            - The password to connect to the database
        required: false
        default: None
        aliases: ['pw']
    service_name:
        description:
            - The service_name to connect to the database
        required: false
        default: database_name
        aliases: ['sn']
    hostname:
        description:
            - The host of the database
        required: false
        default: localhost
        aliases: ['host']
    port:
        description:
            - The listener port to connect to the database
        required: false
        default: 1521
    sql:
        description:
            - The sql you want to execute
        required: false
    script:
        description:
            - The script you want to execute. Doesn't handle selects
        required: false
notes:
    - cx_Oracle needs to be installed
    - Oracle client libraries need to be installed along with ORACLE_HOME and LD_LIBRARY_PATH settings.
requirements: [ "cx_Oracle" ]
author: Mikael Sandström, oravirt@gmail.com, @oravirt
'''

EXAMPLES = '''
# Execute arbitrary sql
- oracle_sql:
    username: "{{ user }}"
    password: "{{ password }}"
    service_name: one.world
    sql: 'select username from dba_users'
# Execute arbitrary script1
- oracle_sql:
    username: "{{ user }}"
    password: "{{ password }}"
    service_name: one.world
    script: /u01/scripts/create-all-the-procedures.sql
# Execute arbitrary script2
- oracle_sql:
    username: "{{ user }}"
    password: "{{ password }}"
    service_name: one.world
    script: /u01/scripts/create-tables-and-insert-default-values.sql
'''
import os, re
from ansible.module_utils.basic import AnsibleModule

# In thise we do import from local project project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No colletions are used
#try:
#    from ansible.module_utils.oracle_utils import oracle_connect
#except:
#    pass

# In thise we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracleConnection
except:
    pass


try:
    import cx_Oracle
except ImportError:
    cx_oracle_exists = False
else:
    cx_oracle_exists = True


def rows_to_dict_list(cursor):
    columns = [i[0] for i in cursor.description]
    return [dict(zip(columns, row)) for row in cursor]

def execute_sql_get(module, cursor, sql):
    try:
        c = cursor.execute(sql)
        result = rows_to_dict_list(c)
        c.close()
    except cx_Oracle.DatabaseError as exc:
        error, = exc.args
        msg = 'Something went wrong while executing sql_get - %s sql: %s' % (error.message, sql)
        module.fail_json(msg=msg, changed=False)
        return False
    return result


def execute_sql(module, cursor, conn, sql):
    if 'insert' or 'delete' or 'update' in sql.lower():
        docommit = True
    else:
        docommit = False

    try:
        # module.exit_json(msg=sql.strip())
        cursor.execute(sql)
    except cx_Oracle.DatabaseError as exc:
        error, = exc.args
        msg = 'Something went wrong while executing sql - %s sql: %s' % (error.message, sql)
        module.fail_json(msg=msg, changed=False)
        return False
    if docommit:
        conn.commit()
    return True


def read_file(module, script):
    try:
        f = open(script, 'r')
        sqlfile = f.read()
        f.close()
        return sqlfile
    except IOError as e:
        msg = 'Couldn\'t open/read file: %s' % (e)
        module.fail_json(msg=msg, changed=False)
    return


def clean_sqlfile(sqlfile):
    sqlfile = sqlfile.strip()
    sqlfile = sqlfile.lstrip()
    sqlfile = sqlfile.lstrip()
    sqlfile = os.linesep.join([s for s in sqlfile.splitlines() if s])
    return sqlfile


def main():

    module = AnsibleModule(
        argument_spec=dict(
            oracle_home   = dict(required=False, aliases=['oh']),
            user=dict(required=False, aliases=['un', 'username']),
            password=dict(required=False, no_log=True, aliases=['pw']),
            mode=dict(default="normal", choices=["sysasm", "sysdba", "normal"]),
            service_name=dict(required=False, aliases=['sn']),
            hostname=dict(required=False, default='localhost', aliases=['host']),
            port=dict(required=False, default=1521, type='int'),
            sql=dict(required=False),
            script=dict(required=False),

        ),
        required_if=[('mode', 'normal', ('username', 'password', 'service_name'))],
        required_one_of=[('sql', 'script')],
        mutually_exclusive=[('sql', 'script')],
        required_together=[('username', 'password')],
        supports_check_mode=True
    )

    sql = module.params["sql"]
    script = module.params["script"]

    if not cx_oracle_exists:
        msg = "The cx_Oracle module is required. Also set ORACLE_HOME"
        module.fail_json(msg=msg)

    conn = oracleConnection(module)

    if sql:
        if re.match(r'^\s*(select|with)\s+', sql, re.IGNORECASE):
            result = conn.execute_select(sql)
            module.exit_json(msg='Select statement executed.', changed=False, data=result)
        if sql.lower().startswith('begin '):
            execute_sql(module, cursor, conn, sql)
            msg = 'SQL executed: %s' % (sql)
            module.exit_json(msg=msg, changed=True)

        else:
            sql = sql.rstrip(';')
            if sql.lower().startswith('select '):
                result = execute_sql_get(module, cursor, sql)
                module.exit_json(msg=result, changed=False)
            else:
                execute_sql(module, cursor, conn, sql)
                msg = 'SQL executed: %s' % (sql)
                module.exit_json(msg=msg, changed=True)
    else:
        sqlfile = read_file(module, script)
        if len(sqlfile) > 0:
            sqlfile = clean_sqlfile(sqlfile)
            
            if sqlfile.endswith('/') or ('create or replace') in sqlfile.lower():
                sqldelim = '/'
            else:
                sqldelim = ';'
            
            sqlfile = sqlfile.strip(sqldelim)
            sql = sqlfile.split(sqldelim)
            
            for q in sql:
                execute_sql(module, cursor, conn, q)
            msg = 'Finished running script %s \nContents: \n%s' % (script, sqlfile)
            module.exit_json(msg=msg, changed=True)
        else:
            module.fail_json(msg='SQL file seems to be empty')

    module.exit_json(msg="Unhandled exit", changed=False)


if __name__ == '__main__':
    main()
