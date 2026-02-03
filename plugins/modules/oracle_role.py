#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_role
short_description: Manage roles in an Oracle database
description:
  - CREATE/DROP Oracle ROLE
  - Supports also idenfified roles
  - See connection parameters for oracle_ping
version_added: "3.0.1"
options:
  role:
    description: The role that should be added/removed
    required: True
  state:
    description: The intended state of the role
    default: present
    choices: ['present','absent']
notes:
  - cx_Oracle needs to be installed
requirements: [ "cx_Oracle" ]
author:
  - Mikael Sandström, oravirt@gmail.com, @oravirt
  - Ivan Brezina
'''

EXAMPLES = '''
- name: Add grants to the user
  oracle_role:
    mode: sysdba
    role: myrole
    state: present

- name: Create idenfified role
  oracle_role:
    mode: sysdba    
    role: "foo"
    identified_method: "password"
    identified_value: "bar"
'''


# Check if the user/role exists
def check_role_exists(conn, role):
    sql = "select role, authentication_type from dba_roles where upper(role) = upper(:role_name)"
    r = conn.execute_select_to_dict(sql, {'role_name': role}, fetchone=True)
    return set(r.items())


# Create the role
def create_role(conn, module):
    role = module.params["role"]
    auth = module.params["auth"]
    auth_conf = module.params["auth_conf"]

    # This is the default role creation
    sql = 'create role %s' % role

    if auth == 'password':
        if not auth_conf:
            module.fail_json(msg='Missing password', changed=conn.changed, ddls=conn.ddls)
        else:
            sql += ' identified by %s' % auth_conf
    elif auth == 'application':
        if auth_conf:
            module.fail_json(msg='Missing authentication package (schema.name)', changed=False)
        else:
            sql += ' identified using %s' % auth_conf
    elif auth == 'external':
        sql += ' identified externally'

    elif auth == 'global':
        sql += ' identified globally'

    conn.execute_ddl(sql)
    msg = 'The role (%s) has been created successfully, authentication: "%s"' % (role, auth)
    module.exit_json(msg=msg , changed=conn.changed, ddls=conn.ddls)


def modify_role(conn, module, current_set):
    role = module.params["role"]
    auth = module.params["auth"]
    auth_conf = module.params["auth_conf"]

    sql = 'alter role %s' % role

    current_auth = next(v for (a, v) in current_set if a == 'authentication_type')
    if current_auth.upper() == auth.upper():
        module.exit_json(msg='The role (%s) already exists' % role, changed=conn.changed, ddls=conn.ddls)

    if auth == 'none':
        sql += ' not identified'
    elif auth == 'password':
        if not auth_conf:
            module.fail_json(msg='Missing password for authentication_type %s' % auth, changed=False)
        else:
            sql += ' identified by %s' % auth_conf
    elif auth == 'application':
        if not auth_conf:
            module.fail_json(msg='Missing authentication package (schema.name)', changed=False)
        else:
            sql += ' identified using %s' % auth_conf
    elif auth == 'external':
        sql += ' identified externally'
    elif auth == 'global':
        sql += ' identified globally'

    conn.execute_ddl(sql)
    msg = 'The role (%s) has been changed successfully, authentication: %s, previous: %s' % (role, auth, current_auth)
    module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)


# Drop the role
def drop_role(conn, module):
    role = module.params["role"]
    sql = 'drop role %s' % role

    conn.execute_ddl(sql)
    msg = 'The role (%s) has been successfully dropped' % role
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
            dsn           = dict(required=False, aliases=['datasource_name']),
            oracle_home   = dict(required=False, aliases=['oh']),

            role          = dict(required=True, type='str'),
            state         = dict(default="present", choices=["present", "absent"]),
            auth          = dict(default='none', choices=["none", "password", "external", "global", "application"], aliases=['identified_method']),
            auth_conf     = dict(default=None, aliases=['identified_value'])
        ),
        required_together=[['user', 'password']],
        supports_check_mode=True
    )

    role = module.params["role"]
    state = module.params["state"]

    oc = oracleConnection(module)

    current_role = check_role_exists(oc, role)
    if state == 'present':
        if not current_role:
            create_role(oc, module)
        else:
            modify_role(oc, module, current_role)

    elif state == 'absent':
        if current_role:
            drop_role(oc, module)
        else:
            module.exit_json(msg="The role (%s) doesn't exist" % role, changed=False)

    module.fail_json(msg='Unhandled exit', changed=oc.changed, ddls=oc.ddls)


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
