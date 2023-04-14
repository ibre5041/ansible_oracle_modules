#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_role
short_description: Manage users/roles in an Oracle database
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
    role:
        description:
            - The role that should get grants added/removed
        required: false
        default: null
    grants:
        description:
            - The privileges granted to the new role. Can be a string or a list
        required: false
        default: null
    state:
        description:
            - The intended state of the priv (present=added to the user, absent=removed from the user). REMOVEALL will remove ALL role/sys privileges
        default: present
        choices: ['present','absent','REMOVEALL']
notes:
    - cx_Oracle needs to be installed
requirements: [ "cx_Oracle" ]
author: Mikael Sandström, oravirt@gmail.com, @oravirt
'''

EXAMPLES = '''
# Add grants to the user
oracle_role: hostname=remote-db-server service_name=orcl user=system password=manager role=myrole state=present grants='create session','create any table',connect,resource

# Revoke the 'create any table' grant
oracle_role: hostname=localhost service_name=orcl user=system password=manager role=myrole state=absent grants='create any table'

# Remove all grants from a user
oracle_role: hostname=localhost service_name=orcl user=system password=manager role=myrole state=REMOVEALL grants=


'''


# Check if the user/role exists
def check_role_exists(conn, role):
    sql = "select upeper(role), authentication_type from dba_roles where upper(role) = upper(:role_name)"
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

    current_auth = next(v for (a, v) in current_set if a == 'AUTHENTICATION_TYPE')
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
        if auth_conf:
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
            oracle_home   = dict(required=False, aliases=['oh']),
            hostname      = dict(default='localhost'),
            port          = dict(default=1521, type="int"),
            service_name  = dict(required=False, aliases=['tns']),
            user          = dict(required=False, aliases=['username']),
            password      = dict(required=False, no_log=True),
            mode          = dict(default='normal', choices=["normal","sysdba"]),
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
try:
    from ansible.module_utils.oracle_utils import oracleConnection
except:
    pass

# In these we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracleConnection
except:
    pass


if __name__ == '__main__':
    main()
