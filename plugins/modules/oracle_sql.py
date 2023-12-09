#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_sql
short_description: Execute arbitrary sql
description:
  - Execute arbitrary sql against an Oracle database
  - This module can be used to execute arbitrary SQL queries or PL/SQL blocks against an Oracle database.
  - If the SQL query is a select statement, the result will be returned.
  - If the script contains dbms_output.put_line(), the output will be returned.
  - Connection is set to autocommit. There is no rollback mechanism implemented.
  - See connection parameters for oracle_ping
version_added: "2.1.0.0"
options:
  sql:
    description: The sql you want to execute
    required: False
  script:
    description: The script you want to execute. Doesn't handle selects
    required: False
notes:
  - cx_Oracle needs to be installed
  - Oracle client libraries need to be installed along with ORACLE_HOME settings.
  - Oracle basic tools.
  - Check mode is supported.
  - In check mode, the select query are executed.
  - Diff mode is not supported.
requirements: [ "cx_Oracle" ]
author: 
  - Mikael Sandström, oravirt@gmail.com, @oravirt
  - Ari Stark (@ari-stark)
  - Ivan Brezina
'''

EXAMPLES = '''
# Execute one arbitrary SQL statement (no trailing semicolon)
- oracle_sql:
    mode: sysdba
    sql: "select username from dba_users"

# Execute several arbitrary SQL statements (each statement must end with a semicolon at end of line)
- oracle_sql:
    hostname: "foo.server.net"
    username: "foo"
    password: "bar"
    service_name: "pdb001"
    script: |
        insert into foo (f1, f2) values ('ab', 'cd');
        update foo set f2 = 'fg' where f1 = 'ab';

# Execute several arbitrary PL/SQL blocks (must end with a trailing slash)
- oracle_sql:
    hostname: "foo.server.net"
    username: "foo"
    password: "bar"
    service_name: "pdb001"
    script: |
        begin
            [...]
        end;
        /
        begin
            [...]
        end;
        /

# Execute arbitrary SQL file
- oracle_sql:
    hostname: "foo.server.net"
    username: "foo"
    password: "bar"
    service_name: "pdb001"
    script: '@/u01/scripts/create-all-the-procedures.sql'
'''

import os, re
from ansible.module_utils.basic import AnsibleModule

# In this case we do import from local project project sub-directory <project-dir>/module_utils
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


output_lines = []


def execute_statements(conn, script):
    """Execute several statements.

    This function determines if it's dealing with PL/SQL blocks or multi-statement queries. It cannot deal with both.
    PL/SQL blocks is defined by a trailing slash (/).
    If there is no trailing slash, it's considered multi-statement queries separated by a semicolon.
    """
    global output_lines

    if re.search(r'/\s*$', script):  # If it's PL/SQL blocks
        seperator = r'^\s*/\s*$'
    else:  # If it's SQL statements
        seperator = r';\s*$'

    for query in re.split(seperator, script, flags=re.MULTILINE):
        if query.strip():
            output_lines += conn.execute_statement(query.strip())


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

            sql=dict(required=False),
            script=dict(required=False),            
        ),
        required_if=[('mode', 'normal', ('username', 'password', 'service_name'))],
        required_one_of=[('sql', 'script')],
        mutually_exclusive=[('sql', 'script')],
        required_together=[('username', 'password')],
        supports_check_mode=True
    )

    script = module.params["script"]
    sql = module.params["sql"]
    
    conn = oracleConnection(module)

    # Single SELECT or DML, ALTER, DROP, ... statement
    if sql:
        if re.match(r'^\s*(select|with)\s+', sql, re.IGNORECASE):
            result = conn.execute_select_to_dict(sql.rstrip().rstrip(';'))
            module.exit_json(msg='Select statement executed.', changed=False, data=result)
        else:
            conn.execute_ddl(sql.rstrip().rstrip(';'))
            module.exit_json(msg='SQL executed: %s' % (sql), changed=True, ddls=conn.ddls)
    # SQL script embeded in .yaml playbook
    elif script and not script.startswith('@'):
        execute_statements(conn, script)
        module.exit_json(msg='DML or DDL statements executed.', changed=True, ddls=conn.ddls, output_lines=output_lines)
    # SQL file
    else:
        try:
            file_name = script.lstrip('@')
            with open(file_name, 'r') as f:
                execute_statements(conn, f.read())
            module.exit_json(msg='DML or DDL statements executed.', changed=True, ddls=conn.ddls, output_lines=output_lines)
        except IOError as e:
            module.fail_json(msg=str(e), changed=False)

    module.exit_json(msg="Unhandled exit", changed=False)


if __name__ == '__main__':
    main()
