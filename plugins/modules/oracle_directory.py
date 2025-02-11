#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_directory
short_description: Create/drop DIRECTORY in an Oracle database
description:
  - Create/drop DIRECTORY in an Oracle database
  - See connection parameters for oracle_ping
version_added: "3.0.0"
options:
  connection:
    description: See M(ibre5041.ansible_oracle_modules.oracle_ping)
  directory_name:
    description: The name of the directory
    required: True
  path:
    description: Where the directory should point to
    required: False
notes:
    - oracledb needs to be installed
requirements: [ "oracledb" ]
author: 
    - Mikael Sandström, oravirt@gmail.com, @oravirt
    - Ivan Brezina
'''

EXAMPLES = '''
- name: create a directory
  oracle_directory:
    mode: sysdba
    directory_name: TEST_DIRECTORY
    directory_path: /oracle/directory
    state: present
    
- name: drop a directory
  oracle_directory:
    mode: sysdba
    directory_name: TEST_DIRECTORY
    state: absent
'''


# Check if the directory exists
def check_directory_exists(conn, directory_name):
    sql = "select directory_name, directory_path from dba_directories where directory_name = upper(:directory_name)"
    r = conn.execute_select_to_dict(sql, {"directory_name": directory_name}, fetchone=True)
    return set(r.items())


def ensure_directory(conn, module, current_directory):
    directory_path = module.params["directory_path"]
    directory_name = module.params["directory_name"]

    if current_directory:
        current_path = next(v for (a, v) in current_directory if a == 'directory_path')
        if current_path == directory_path:
            msg = 'Directory %s already exists (%s)' % (directory_name, directory_path)
            module.exit_json(msg=msg, changed=False)
        else:
            directory_sql = 'create or replace directory %s as \'%s\'' % (directory_name, directory_path)
            conn.execute_ddl(directory_sql)
            msg = 'Directory %s, changed to path: %s (old path: %s)'% (directory_name, directory_path, current_path)
            module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)
    else:
        directory_sql = "create directory %s as '%s'" % (directory_name, directory_path)
        conn.execute_ddl(directory_sql)
        msg = 'Directory: %s, created with path: %s' % (directory_name, directory_path)
        module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)


def drop_directory(conn, module):
    directory_name = module.params["directory_name"]
    drop_sql = 'drop directory %s' % directory_name

    conn.execute_ddl(drop_sql)
    msg = 'Directory %s successfully dropped' % directory_name
    module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)


def main():
    module = AnsibleModule(
        argument_spec = dict(
            user          = dict(required=False, aliases=['un', 'username']),
            password      = dict(required=False, no_log=True, aliases=['pw']),
            mode          = dict(default='normal', choices=["normal", "sysdba"]),
            hostname      = dict(required=False, default='localhost', aliases=['host']),
            port          = dict(required=False, default=1521, type='int'),
            service_name  = dict(required=False, aliases=['sn']),
            oracle_home   = dict(required=False, aliases=['oh']),
            
            directory_name = dict(default=None),
            directory_path = dict(default=None),
            state          = dict(default="present", choices=["present", "absent"])
        ),
        required_together=[['user', 'password']],
        required_if=[('state', 'present', ('directory_name', 'directory_path'))],
        supports_check_mode=True
    )

    directory_name = module.params["directory_name"]
    state = module.params["state"]

    oc = oracleConnection(module)

    current_directory = check_directory_exists(oc, directory_name)
    if state == 'present':
        ensure_directory(oc, module, current_directory)
    elif state == 'absent':
        if current_directory:
            drop_directory(oc, module)
        else:
            msg = "Directory %s doesn't exist" % directory_name
            module.exit_json(msg=msg, changed=False)

    module.fail_json(msg='Unhandled exit', changed=False)


from ansible.module_utils.basic import *

# In these we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
#try:
#    from ansible.module_utils.oracle_utils import oracleConnection
#except:
#    pass

# In these we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracleConnection
except:
    pass


if __name__ == '__main__':
    main()
