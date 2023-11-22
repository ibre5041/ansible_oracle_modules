#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_parameter
short_description: Manage parameters in an Oracle database
description:
    - Manage init parameters in an Oracle database

version_added: "3.0.2"
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
    name:
        description:
            - The parameter that is being changed
        required: false
        default: null
    value:
        description:
            - The value of the parameter
        required: false
        default: null
    state:
        description:
            - The intended state of the parameter (present means set to value, absent/reset means the value is reset to its default value).
        default: present
        choices: ['present','absent','reset']
notes:
    - cx_Oracle needs to be installed
requirements: [ "cx_Oracle","re" ]
author: 
    - Mikael Sandström, oravirt@gmail.com, @oravirt
    - Ivan Brezina
'''

EXAMPLES = '''
# Set the value of db_recovery_file_dest
oracle_parameter: hostname=remote-db-server service_name=orcl user=system password=manager name=db_recovery_file_dest value='+FRA' state=present scope=both sid='*'

# Set the value of db_recovery_file_dest_size
oracle_parameter: hostname=remote-db-server service_name=orcl user=system password=manager name=db_recovery_file_dest_size value=100G state=present scope=both

# Reset the value of open_cursors
oracle_parameter: hostname=remote-db-server service_name=orcl user=system password=manager name=db_recovery_file_dest_size state=reset scope=spfile


'''


# Check if the parameter exists
def check_parameter_exists(conn, parameter_name):
    mode = conn.module.params['mode']
    scope = conn.module.params['scope']

    if parameter_name.startswith('_') and mode != 'sysdba':
        msg = 'You need sysdba privs to verify underscore parameters (%s), mode: (%s)' % (parameter_name, mode)
        conn.module.fail_json(msg=msg, changed=False)
    elif parameter_name.startswith('_') and mode == 'sysdba':
        sql = "select lower(ksppinm) from sys.x$ksppi where ksppinm = lower(:parameter_name)"
    else:
        sql = "select lower(name) from v$parameter where name = lower(:parameter_name)"
    r1 = conn.execute_select(sql, {"parameter_name": parameter_name}, fetchone=True)

    if scope == 'spfile':
        parameter_source = 'v$spparameter'
    else:
        parameter_source = 'v$parameter'

    if mode == 'sysdba':
        if scope == 'spfile':
            sql = "select lower(KSPSPFFTCTXSPDVALUE) from x$kspspfile where lower(KSPSPFFTCTXSPNAME) = lower(:parameter_name)"
        else:
            sql = "select lower(y.ksppstdvl) from sys.x$ksppi x, sys.x$ksppcv y where x.indx = y.indx and x.ksppinm = lower(:parameter_name)"
    else:
        sql = "select lower(display_value) from %s where name = lower(:parameter_name)" % parameter_source
    r2 = conn.execute_select(sql, {"parameter_name": parameter_name}, fetchone=True)

    return r1, r2


def modify_parameter(conn, module, current_parameter):
    parameter_name = module.params['parameter_name']
    value = module.params['value']
    comment = module.params['comment']
    scope = module.params['scope']
    sid = module.params['sid']

    if current_parameter == value.lower() or not current_parameter and value == "''":
        module.exit_json(msg='The parameter (%s) is already set to %s' % (parameter_name, value), changed=False)
        return True

    sql = 'alter system set %s=%s ' % (parameter_name, value)
    if comment:
        sql += " comment='%s'" % comment

    sql += " scope=%s sid='%s'" % (scope, sid)
    conn.execute_ddl(sql)
    msg = 'The parameter (%s) has been changed successfully, new: %s, old: %s' % (parameter_name, value, current_parameter)
    module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)


def reset_parameter(conn, module):
    parameter_name = module.params['parameter_name']
    scope = module.params['scope']
    sid = module.params['sid']

    sql = "alter system reset %s scope=%s sid='%s'" % (parameter_name, scope, sid)
    conn.execute_ddl(sql)
    msg = 'The parameter (%s) has been reset to its default value' % parameter_name
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
            parameter_name = dict(default=None, aliases=['parameter', 'name']),
            value         = dict(default=None),
            comment       = dict(default=None),
            state         = dict(default="present", choices=["present", "absent", "reset"]),
            scope         = dict(default="both", choices=["both", "spfile", "memory"]),
            sid           = dict(default="*"),
        ),
        required_if=[('mode', 'normal', ('username', 'password', 'service_name')),
                     ('state', 'present', ['value'])],
        required_together=[['user', 'password']],
        supports_check_mode=True
    )

    parameter_name = module.params["parameter_name"]
    state = module.params["state"]

    oc = oracleConnection(module)

    parameter = check_parameter_exists(oc, parameter_name)
    if state == 'present':
        if parameter:
            modify_parameter(oc, module)
    elif state == 'reset' or state == 'absent':
        if parameter:
            reset_parameter(oc, module)
        else:
            module.fail_json(msg="Parameter %s doesn't exist or sysdba privileges needed.", changed=False)
    module.fail_json(msg='Unhandled exit', changed=False)


from ansible.module_utils.basic import *

# In this case we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
#try:
#    from ansible.module_utils.oracle_utils import oracle_connect
#except:
#    pass

# In this case we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracleConnection
except:
    pass


if __name__ == '__main__':
    main()
