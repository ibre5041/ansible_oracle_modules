#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_directory
short_description: Manage users/schemas in an Oracle database
description:
    - Manage grants/privileges in an Oracle database
    - Handles role/sys privileges at the moment.
    - It is possible to add object privileges as well, but they are not considered when removing privs at the moment.
version_added: "1.9.1"
options:
    hostname:
        description:
            - The Oracle database host
        required: false
        default: localhost
    port:
        description:
            - The listener port number on the host
        required: false
        default: 1521
    service_name:
        description:
            - The database service name to connect to
        required: true
    user:
        description:
            - The Oracle user name to connect to the database
        required: true
    password:
        description:
            - The Oracle user password for 'user'
        required: true
    mode:
        description:
            - The mode with which to connect to the database
        required: true
        default: normal
        choices: ['normal','sysdba']
    directory_name:
        description:
            - The name of the directory
        required: True
        default: null
    path:
        description:
            - Where the directory should point
        required: false
        default: null

notes:
    - cx_Oracle needs to be installed
requirements: [ "cx_Oracle" ]
author: Mikael Sandström, oravirt@gmail.com, @oravirt
'''

EXAMPLES = '''


'''

try:
    import cx_Oracle
except ImportError:
    cx_oracle_exists = False
else:
    cx_oracle_exists = True

# Check if the directory exists
def check_directory_exists(module, msg, cursor, directory_name):

    if not(directory_name):
        module.fail_json(msg='Error: Missing directory name', changed=False)
        return False

    sql = 'select count(*) from dba_directories where directory_name= upper(\'%s\')' % directory_name


    try:
            cursor.execute(sql)
            result = cursor.fetchone()[0]
    except cx_Oracle.DatabaseError as exc:
            error, = exc.args
            msg = error.message+ 'sql: ' + sql
            return False

    if result > 0:
        return True
    else:
        return False

def ensure_directory(module, msg, cursor, directory_name, directory_path, directory_mode):

    if check_directory_exists(module, msg, cursor, directory_name):
        check_path_sql = 'select directory_path from dba_directories where directory_name = upper(\'%s\')' % directory_name
        _curr_path = execute_sql_get(module, msg, cursor, check_path_sql)

        if _curr_path[0][0] != directory_path:
            if directory_mode == 'enforce':
                directory_sql = 'create or replace directory %s as \'%s\'' % (directory_name, directory_path)
                if execute_sql(module,msg,cursor,directory_sql):
                    module.exit_json(msg='Directory %s, changed to path: %s (old path: %s)' % (directory_name, directory_path,_curr_path[0][0]), changed=True)
        else:
            module.exit_json(msg='Directory %s already exists (%s)' % (directory_name, directory_path), changed=False)
    else:
        directory_sql = 'create directory %s as \'%s\'' % (directory_name, directory_path)

        if execute_sql(module,msg,cursor,directory_sql):
            msg = 'Directory: %s, created with path: %s' % (directory_name, directory_path)
            module.exit_json(msg=msg, changed=True)

def drop_directory(module, msg, cursor, directory_name):
    drop_sql = 'drop directory %s' % (directory_name)

    if execute_sql(module,msg,cursor,drop_sql):
        module.exit_json(msg='Directory %s successfully dropped' % (directory_name), changed=True)


def execute_sql(module, msg, cursor, sql):

    try:
        cursor.execute(sql)
    except cx_Oracle.DatabaseError as exc:
        error, = exc.args
        msg = 'Something went wrong while executing sql - %s sql: %s' % (error.message, sql)
        module.fail_json(msg=msg, changed=False)
        return False
    return True


def execute_sql_get(module, msg, cursor, sql):

    try:
        cursor.execute(sql)
        result = (cursor.fetchall())
    except cx_Oracle.DatabaseError as exc:
        error, = exc.args
        msg = 'Something went wrong while executing sql_get - %s sql: %s' % (error.message, sql)
        module.fail_json(msg=msg, changed=False)
        return False
    return result



def main():

    msg = ['']
    global state
    module = AnsibleModule(
        argument_spec = dict(
            hostname      = dict(default='localhost'),
            port          = dict(default=1521, type='int'),
            service_name  = dict(required=False),
            user          = dict(required=False),
            password      = dict(required=False, no_log=True),
            mode          = dict(default='normal', choices=["normal","sysdba"]),
            directory_name = dict(default=None),
            directory_path = dict(default=None),
            directory_mode = dict(default="enforce", choices=["normal", "enforce"]),
            state          = dict(default="present", choices=["present", "absent"])

        )
    )

    directory_name = module.params["directory_name"]
    directory_path = module.params["directory_path"]
    directory_mode = module.params["directory_mode"]
    state = module.params["state"]

    if not cx_oracle_exists:
        module.fail_json(msg="The cx_Oracle module is required. 'pip install cx_Oracle' should do the trick. If cx_Oracle is installed, make sure ORACLE_HOME & LD_LIBRARY_PATH is set")

    conn = oracle_connect(module)
    cursor = conn.cursor()

    if state == 'present':
        ensure_directory(module, msg, cursor, directory_name, directory_path, directory_mode)
    elif state == 'absent':
        if check_directory_exists(module, msg, cursor, directory_name):
            drop_directory(module, msg, cursor, directory_name)
        else:
            msg = 'Directory %s doesn\'t exist' % (directory_name)
            module.exit_json(msg=msg, changed=False)

    else:
        module.fail_json(msg='Unhandled exit', changed=False)


from ansible.module_utils.basic import *

# In thise we do import from local project project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No colletions are used
try:
    from ansible.module_utils.oracle_utils import oracle_connect
except:
    pass

# In thise we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracle_connect
except:
    pass


if __name__ == '__main__':
    main()
