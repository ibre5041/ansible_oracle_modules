#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_parameter
short_description: Manage parameters in an Oracle database
description: 
  - Manage init parameters in an Oracle database
  - Also handles underscore parameters. That will require using mode=sysdba, to be able to read the X$ tables needed to verify the existence of the parameter.
  - See connection parameters for oracle_ping  
version_added: "3.0.2"
options:
  name:
    description: The parameter that is being changed
    required: false
    default: null
  value:
    description: The value of the parameter
    required: false
    default: null
  state:
    description: The intended state of the parameter (present means set to value, absent/reset means the value is reset to its default value).
    default: present
    choices: ['present','absent','reset']  
notes:
  - oracledb needs to be installed
requirements: [ "oracledb","re" ]
author: 
  - Mikael Sandström, oravirt@gmail.com, @oravirt
  - Ivan Brezina
'''


EXAMPLES = '''
- name: Set the value of db_recovery_file_dest
  oracle_parameter:
    mode: sysdba
    name: db_recovery_file_dest
    value: '+FRA'
    state: present
    scope: both
    sid: '*'

- name: Set the value of db_recovery_file_dest_size
  oracle_parameter:
    mode: sysdba    
    name: db_recovery_file_dest_size
    value: 100G
    state: present
    scope: both

- name: Set the numeric value of open_cursors
  oracle_parameter:
    mode: sysdba
    name: "open_cursors"
    value: "351"
    state: "present"

- name: Set boolean value of blank_trimming"
  oracle_parameter:
    mode: sysdba
    name: "blank_trimming"
    value: "TRUE"
    state: "present"
    scope: "spfile"
    
- name: Reset the value of open_cursors
  oracle_parameter:
    mode: sysdba    
    name: db_recovery_file_dest_size
    state: reset
    scope: spfile
'''


from collections import namedtuple


# Check if the parameter exists
def check_parameter_exists(conn, parameter_name):
    mode = conn.module.params['mode']

    # Check if parameter name is valid
    if parameter_name.startswith('_'):
        sql = """
        select lower(p.ksppinm) as name, 
        b.ksppstvl as CURRENT_VALUE, 
        b.ksppstdfl as DEFAULT_VALUE, 
        b.ksppstdf as ISDEFAULT, 
        b.ksppstdvl as DISPLAY_VALUE
        from x$ksppi p
        , x$ksppsv b -- X$KSPPSV (Parameter values at system level)
        where p.indx = b.indx
        and p.ksppinm = lower(:parameter_name)"""
        p = conn.execute_select_to_dict (sql, {"parameter_name": parameter_name}, fetchone=True)
        #{'name': 'compatible', 'current_value': '19.0.0', 'default_value': None, 'isdefault': 'FALSE',
        # 'display_value': '19.0.0'}
    else:
        sql = """
        select lower(name) as name, 
        value as CURRENT_VALUE, 
        ISMODIFIED,-- was modified since startup
        ISDEFAULT,
        DEFAULT_VALUE,
        DISPLAY_VALUE  
        from v$parameter where name = lower(:parameter_name)
        """
        p = conn.execute_select_to_dict(sql, {"parameter_name": parameter_name}, fetchone=True)

    if not p:
        conn.module.fail_json(msg="Invalid parameter: {}".format(parameter_name), changed=False)

    if mode == 'sysdba':
        sql = """
            select lower(KSPSPFFTCTXSPNAME) as name, KSPSPFFTCTXSPDVALUE as SPFILE_VALUE 
            from x$kspspfile where lower(KSPSPFFTCTXSPNAME) = lower(:parameter_name)
            """
        s = conn.execute_select_to_dict(sql, {"parameter_name": parameter_name}, fetchone=True)
    else:
        sql = "select lower(name) as name, DISPLAY_VALUE as SPFILE_VALUE from v$spparameter where name = lower(:parameter_name)"
        s = conn.execute_select_to_dict(sql, {"parameter_name": parameter_name}, fetchone=True)

    p.update(s)
    return namedtuple("Parameter", p.keys())(*p.values())


def modify_parameter(conn, module, parameter):
    parameter_name = module.params['parameter_name']
    value = module.params['value']
    comment = module.params['comment']
    scope = module.params['scope']
    sid = module.params['sid']

    if parameter_name.startswith("_"):
        parameter_name = '"{}"'.format(parameter_name)

    # Oracle doesn't accept string for all parameters.
    if value in ['TRUE', 'FALSE']:
        o_value = value
    elif re.search('[^0-9]', value):
        o_value = "'%s'" % value
    else:
        o_value = value

    sql = 'alter system set {}={} '.format(parameter_name, o_value)
    if comment:
        sql += " comment='%s'" % comment
    sql += " scope=%s sid='%s'" % (scope, sid)
    if sql in conn.ddls:
        return
    conn.execute_ddl(sql)
    msg = 'The parameter ({}) has been changed successfully, new: "{}", old: {}'.format(parameter_name, value, str(parameter))
    module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)


def reset_parameter(conn, module, parameter):
    parameter_name = module.params['parameter_name']
    scope = module.params['scope']
    sid = module.params['sid']

    if parameter_name.startswith("_"):
        parameter_name = '"{}"'.format(parameter_name)

    sql = "alter system reset {} scope={} sid='{}'".format(parameter_name, scope, sid)
    if sql in conn.ddls:
        return
    conn.execute_ddl(sql)
    msg = 'The parameter ({}) has been reset to its default value'.format(parameter_name)
    module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)


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

            parameter_name=dict(default=None, aliases=['parameter', 'name']),
            value=dict(default=None),
            comment=dict(default=None),
            state=dict(default="present", choices=["present", "absent", "reset"]),
            scope=dict(default="both", choices=["both", "spfile", "memory"]),
            sid=dict(default="*"),
        ),
        required_if=[('mode', 'normal', ('username', 'password', 'service_name')),
                     ('state', 'present', ['value'])],
        required_together=[['user', 'password']],
        supports_check_mode=True
    )

    parameter_name = module.params["parameter_name"]
    value = module.params["value"]
    mode = module.params["mode"]
    state = module.params["state"]
    scope = module.params["scope"]

    if parameter_name.startswith('_') and mode != 'sysdba':
        msg = 'You need sysdba privileges to verify underscore parameters (%s), mode: (%s)' % (parameter_name, mode)
        module.fail_json(msg=msg, changed=False)

    conn = oracleConnection(module)

    parameter = check_parameter_exists(conn, parameter_name)
    if state in ['reset', 'absent']:
        if parameter.spfile_value and scope in ['spfile', 'both']:
            reset_parameter(conn, module, parameter)
        elif parameter.default_value != parameter.current_value and scope in ['memory', 'both']:
            reset_parameter(conn, module, parameter)
        else:
            module.exit_json(msg="Nothing to do for: {}".format(str(parameter)), changed=False)
    elif state == 'present':
        if scope in ['spfile', 'both'] and parameter.spfile_value != value:
            modify_parameter(conn, module, parameter)
        elif scope in ['memory', 'both'] and parameter.display_value != value:
            modify_parameter(conn, module, parameter)
        else:
            module.exit_json(msg="Nothing to do for: {}".format(str(parameter)), changed=False)

    module.fail_json(msg='Unhandled exit', changed=False)


from ansible.module_utils.basic import *

# In this case we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
# try:
#    from ansible.module_utils.oracle_utils import oracleConnection
# except:
#    pass

# In this case we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracleConnection
except:
    pass

if __name__ == '__main__':
    main()
