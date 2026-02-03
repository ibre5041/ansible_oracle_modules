#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_ping
short_description: Test connection to Oracle database
description: Test connection to Oracle database
version_added: "3.1.5"
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
notes:
    - Returns information from v$instance
    - All other modules use the same parameters to connect to the database
requirements: ["cx_Oracle"]
author: 
    - Mikael Sandström, oravirt@gmail.com, @oravirt
    - Ivan Brezina
'''

EXAMPLES = '''
- name: Connect as sysdba
  oracle_ping:
    mode: sysdba
  register: _oracle_instance

- name: Connect remotely from control node
  oracle_ping:
    mode: normal
    hostname: dbhost
    port: 1521
    service_name: DBSERVICE
    user: SYSTEM
    password: Oracle123
  delegate_to: localhost

- name: Connect remotely from control node using wallet
  oracle_ping:
    mode: normal
    hostname: dbhost
    port: 1521
    service_name: DBSERVICE
  delegate_to: localhost
'''


def check_connection(conn):
    sql = "select * from v$instance"
    r = conn.execute_select_to_dict(sql, {}, fetchone=True)
    return set(r.items())


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
            oracle_home   = dict(required=False, aliases=['oh'])
        ),
        required_together=[['user', 'password']],
        supports_check_mode=True
    )

    oracleConnection(module)
    module.exit_json(msg="Connection successful", changed=False)


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
