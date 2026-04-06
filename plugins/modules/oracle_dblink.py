#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_dblink
short_description: Manage Oracle database links
description:
  - Create, drop, and query database links
  - Supports public/private, fixed user, and connected user links
  - Compatible with Oracle 19c, 23ai, and 26ai
  - See connection parameters for oracle_ping
version_added: "3.4.0"
options:
  state:
    description: The intended state of the database link
    default: present
    choices: ['present', 'absent', 'status']
  link_name:
    description: Name of the database link
    required: true
  link_type:
    description: Whether the link is public or private
    default: private
    choices: ['public', 'private']
  connect_user:
    description: User to connect as on the remote database (for fixed-user links). Must be used with I(connect_password); mutually exclusive with I(current_user).
    required: false
  connect_password:
    description: Password for the remote user (required together with I(connect_user) for fixed-user links)
    required: false
    no_log: true
  connect_using:
    description: Connect string or service name for the remote database (required for state=present)
    required: false
  current_user:
    description: Create a CONNECTED USER link instead of a fixed-user link
    type: bool
    default: false
author:
  - Cyrille Modiano
'''

EXAMPLES = '''
- name: Create a private fixed-user database link
  oracle_dblink:
    mode: sysdba
    link_name: my_remote_link
    link_type: private
    connect_user: remote_user
    connect_password: secret
    connect_using: remote_db_service
    state: present

- name: Create a public database link
  oracle_dblink:
    mode: sysdba
    link_name: pub_remote_link
    link_type: public
    connect_user: remote_user
    connect_password: secret
    connect_using: "//remote-host:1521/ORCL"
    state: present

- name: Create a connected user (current_user) database link
  oracle_dblink:
    mode: sysdba
    link_name: cu_remote_link
    link_type: private
    current_user: true
    connect_using: remote_db_service
    state: present

- name: Drop a database link
  oracle_dblink:
    mode: sysdba
    link_name: my_remote_link
    link_type: private
    state: absent

- name: Get database link status
  oracle_dblink:
    mode: sysdba
    link_name: my_remote_link
    link_type: private
    state: status
  register: dblink_info
'''


def get_dblink(conn, link_name, link_type):
    """Query DBA_DB_LINKS for a database link."""
    if link_type == 'public':
        sql = """SELECT OWNER, DB_LINK, USERNAME, HOST, CREATED
                 FROM DBA_DB_LINKS WHERE DB_LINK = UPPER(:name) AND OWNER = 'PUBLIC'"""
    else:
        sql = """SELECT OWNER, DB_LINK, USERNAME, HOST, CREATED
                 FROM DBA_DB_LINKS WHERE DB_LINK = UPPER(:name) AND OWNER != 'PUBLIC'"""
    return conn.execute_select_to_dict(sql, {'name': link_name})


def dblink_exists(conn, link_name, link_type):
    return bool(get_dblink(conn, link_name, link_type))


def build_create_dblink_sql(module, redact_password=False):
    """Build CREATE DATABASE LINK DDL (optionally mask password for check-mode display)."""
    link_name = module.params["link_name"]
    link_type = module.params["link_type"]
    connect_user = module.params["connect_user"]
    connect_password = module.params["connect_password"]
    connect_using = module.params["connect_using"]
    current_user = module.params["current_user"]

    sql = 'CREATE'
    if link_type == 'public':
        sql += ' PUBLIC'
    sql += ' DATABASE LINK %s' % link_name

    if current_user:
        sql += ' CONNECT TO CURRENT_USER'
    elif connect_user:
        pwd = '********' if redact_password else connect_password
        sql += " CONNECT TO %s IDENTIFIED BY \"%s\"" % (connect_user, pwd)

    sql += ' USING \'%s\'' % connect_using
    return sql


def build_drop_dblink_sql(module):
    """Build DROP DATABASE LINK DDL."""
    link_name = module.params["link_name"]
    link_type = module.params["link_type"]
    sql = 'DROP'
    if link_type == 'public':
        sql += ' PUBLIC'
    sql += ' DATABASE LINK %s' % link_name
    return sql


def create_dblink(conn, module):
    """Create a database link."""
    conn.execute_ddl(build_create_dblink_sql(module, redact_password=False))


def drop_dblink(conn, module):
    """Drop a database link."""
    conn.execute_ddl(build_drop_dblink_sql(module))


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
            link_name=dict(required=True),
            link_type=dict(default='private', choices=['public', 'private']),
            connect_user=dict(required=False),
            connect_password=dict(required=False, no_log=True),
            connect_using=dict(required=False),
            current_user=dict(default=False, type='bool'),
        ),
        mutually_exclusive=[
            ('connect_user', 'current_user'),
        ],
        required_together=[
            ['connect_user', 'connect_password'],
        ],
        supports_check_mode=True,
    )
    sanitize_string_params(module.params)

    state = module.params["state"]
    link_name = module.params["link_name"]
    link_type = module.params["link_type"]
    conn = oracleConnection(module)

    if state == 'status':
        rows = get_dblink(conn, link_name, link_type)
        module.exit_json(changed=False, exists=bool(rows), dblink=rows)

    elif state == 'present':
        if dblink_exists(conn, link_name, link_type):
            module.exit_json(changed=False, msg='Database link already exists')
        if not module.params["connect_using"]:
            module.fail_json(msg='connect_using is required for state=present', changed=False)

        connect_user = module.params["connect_user"]
        connect_password = module.params["connect_password"]
        current_user = module.params["current_user"]
        if not current_user and not connect_user:
            module.fail_json(
                msg='Either connect_user (with connect_password) or current_user=true is required for state=present',
                changed=False,
            )
        if connect_user and (connect_password is None or connect_password == ''):
            module.fail_json(
                msg='connect_password is required when connect_user is set',
                changed=False,
            )

        if module.check_mode:
            sql = build_create_dblink_sql(module, redact_password=True)
            module.exit_json(
                changed=True,
                ddls=['--' + sql],
                msg='Database link would be created (check mode)',
            )
        create_dblink(conn, module)
        module.exit_json(changed=conn.changed, ddls=conn.ddls, msg='Database link created')

    elif state == 'absent':
        if not dblink_exists(conn, link_name, link_type):
            module.exit_json(changed=False, msg='Database link does not exist')
        if module.check_mode:
            sql = build_drop_dblink_sql(module)
            module.exit_json(
                changed=True,
                ddls=['--' + sql],
                msg='Database link would be dropped (check mode)',
            )
        drop_dblink(conn, module)
        module.exit_json(changed=conn.changed, ddls=conn.ddls, msg='Database link dropped')


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
