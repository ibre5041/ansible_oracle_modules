#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_acl
short_description: Manage Oracle network Access Control Lists
description:
  - Create, drop, and manage network ACLs using DBMS_NETWORK_ACL_ADMIN
  - Assign host access and privileges
  - Compatible with Oracle 19c, 23ai, and 26ai
  - See connection parameters for oracle_ping
version_added: "3.4.0"
options:
  state:
    description: The intended state of the ACL entry
    default: present
    choices: ['present', 'absent', 'status']
  acl_name:
    description: Name of the ACL
    required: true
  host:
    description:
      - Network host or wildcard pattern
      - "Examples: '*.example.com', '10.0.0.0/24', 'db.internal'"
    required: false
  lower_port:
    description: Lower bound of the port range
    type: int
    required: false
  upper_port:
    description: Upper bound of the port range
    type: int
    required: false
  principal:
    description: Database user or role to grant or revoke access for
    required: false
  privilege:
    description: Network privilege to grant or deny
    default: connect
    choices: ['connect', 'resolve']
  is_grant:
    description: Whether to grant (true) or deny (false) the privilege
    type: bool
    default: true
notes:
  - Requires DBA or EXECUTE privilege on DBMS_NETWORK_ACL_ADMIN
  - oracledb Python module is required
  - Uses DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE / REMOVE_HOST_ACE (Oracle 12c+)
requirements: [ "oracledb" ]
author:
  - Cyrille Modiano
'''

EXAMPLES = '''
- name: Grant connect privilege for a host
  oracle_acl:
    mode: sysdba
    acl_name: my_acl
    host: "*.example.com"
    principal: APP_USER
    privilege: connect
    state: present

- name: Grant connect privilege with port range
  oracle_acl:
    mode: sysdba
    acl_name: smtp_acl
    host: mail.example.com
    lower_port: 25
    upper_port: 25
    principal: MAIL_USER
    privilege: connect
    state: present

- name: Deny connect privilege for a host
  oracle_acl:
    mode: sysdba
    acl_name: deny_acl
    host: "10.0.0.0/24"
    principal: UNTRUSTED_USER
    privilege: connect
    is_grant: false
    state: present

- name: Remove a specific ACE
  oracle_acl:
    mode: sysdba
    acl_name: my_acl
    host: "*.example.com"
    principal: APP_USER
    privilege: connect
    state: absent

- name: Get ACL status for a host
  oracle_acl:
    mode: sysdba
    acl_name: my_acl
    host: "*.example.com"
    state: status
  register: acl_info

- name: Get all ACL entries
  oracle_acl:
    mode: sysdba
    acl_name: all_acls
    state: status
  register: all_acl_info
'''


def get_acl(conn, host, lower_port, upper_port):
    """Query DBA_HOST_ACES for existing ACL entries."""
    sql = """SELECT HOST, LOWER_PORT, UPPER_PORT, ACE_ORDER,
                    PRINCIPAL, PRINCIPAL_TYPE, GRANT_TYPE, PRIVILEGE
             FROM DBA_HOST_ACES
             WHERE HOST = :host"""
    params = {'host': host}
    if lower_port is not None:
        sql += ' AND LOWER_PORT = :lower_port'
        params['lower_port'] = lower_port
    if upper_port is not None:
        sql += ' AND UPPER_PORT = :upper_port'
        params['upper_port'] = upper_port
    return conn.execute_select_to_dict(sql, params)


def ace_exists(conn, module):
    """Check if a specific ACE (Access Control Entry) exists."""
    host = module.params["host"]
    principal = module.params["principal"]
    privilege = module.params["privilege"]
    rows = get_acl(conn, host, module.params["lower_port"],
                   module.params["upper_port"])
    for row in rows:
        if (row.get('principal', '').upper() == principal.upper()
                and row.get('privilege', '').upper() == privilege.upper()):
            return True
    return False


def create_ace(conn, module):
    """Add a network ACL entry using DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE."""
    host = module.params["host"]
    lower_port = module.params["lower_port"]
    upper_port = module.params["upper_port"]
    principal = module.params["principal"]
    privilege = module.params["privilege"]
    is_grant = module.params["is_grant"]

    grant_type = 'TRUE' if is_grant else 'FALSE'

    # Build port parameters
    port_clause = ''
    if lower_port is not None:
        port_clause += ', lower_port => %d' % lower_port
    if upper_port is not None:
        port_clause += ', upper_port => %d' % upper_port

    sql = """BEGIN
  DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE(
    host => '%s'%s,
    ace => xs$ace_type(
      privilege_list => xs$name_list('%s'),
      principal_name => '%s',
      principal_type => xs_acl.ptype_db,
      is_grant => %s
    )
  );
END;""" % (host, port_clause, privilege, principal, grant_type)

    conn.execute_ddl(sql)


def remove_ace(conn, module):
    """Remove network ACL entries for a host."""
    host = module.params["host"]
    lower_port = module.params["lower_port"]
    upper_port = module.params["upper_port"]

    port_clause = ''
    if lower_port is not None:
        port_clause += ', lower_port => %d' % lower_port
    if upper_port is not None:
        port_clause += ', upper_port => %d' % upper_port

    sql = """BEGIN
  DBMS_NETWORK_ACL_ADMIN.REMOVE_HOST_ACE(
    host => '%s'%s,
    ace => xs$ace_type(
      privilege_list => xs$name_list('%s'),
      principal_name => '%s',
      principal_type => xs_acl.ptype_db
    )
  );
END;""" % (host, port_clause, module.params["privilege"], module.params["principal"])

    conn.execute_ddl(sql)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            user=dict(required=False, aliases=['un', 'username']),
            password=dict(required=False, no_log=True, aliases=['pw']),
            mode=dict(default='normal', choices=["normal", "sysdba", "sysdg", "sysoper", "sysasm"]),
            hostname=dict(required=False, default='localhost', aliases=['host']),
            port=dict(required=False, default=1521, type='int'),
            service_name=dict(required=False, aliases=['sn']),
            dsn=dict(required=False, aliases=['datasource_name']),
            oracle_home=dict(required=False, aliases=['oh']),
            session_container=dict(required=False),

            state=dict(default='present', choices=['present', 'absent', 'status']),
            acl_name=dict(required=True),
            host=dict(required=False),
            lower_port=dict(required=False, type='int'),
            upper_port=dict(required=False, type='int'),
            principal=dict(required=False),
            privilege=dict(default='connect', choices=['connect', 'resolve']),
            is_grant=dict(default=True, type='bool'),
        ),
        required_if=[
            ('state', 'present', ('host', 'principal')),
            ('state', 'absent', ('host', 'principal')),
        ],
        supports_check_mode=True,
    )
    sanitize_string_params(module.params)

    state = module.params["state"]
    conn = oracleConnection(module)

    if state == 'status':
        host = module.params["host"]
        if host:
            rows = get_acl(conn, host, module.params["lower_port"], module.params["upper_port"])
        else:
            # Return all ACEs
            sql = """SELECT HOST, LOWER_PORT, UPPER_PORT, ACE_ORDER,
                            PRINCIPAL, PRINCIPAL_TYPE, GRANT_TYPE, PRIVILEGE
                     FROM DBA_HOST_ACES ORDER BY HOST, ACE_ORDER"""
            rows = conn.execute_select_to_dict(sql)
        module.exit_json(changed=False, acl_entries=rows)

    elif state == 'present':
        if ace_exists(conn, module):
            module.exit_json(changed=False, msg='ACE already exists')
        create_ace(conn, module)
        module.exit_json(changed=conn.changed, ddls=conn.ddls, msg='ACE created')

    elif state == 'absent':
        if not ace_exists(conn, module):
            module.exit_json(changed=False, msg='ACE does not exist')
        remove_ace(conn, module)
        module.exit_json(changed=conn.changed, ddls=conn.ddls, msg='ACE removed')


from ansible.module_utils.basic import *  # noqa: F403

try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import (  # noqa: E501
        oracleConnection, sanitize_string_params,
    )
except ImportError:
    def sanitize_string_params(_params):
        pass

if __name__ == '__main__':
    main()
