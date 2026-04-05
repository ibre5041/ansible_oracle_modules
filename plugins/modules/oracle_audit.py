#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_audit
short_description: Manage Oracle Unified Auditing policies
description:
  - Create, alter, and drop Unified Audit policies
  - Enable and disable audit policies on users or roles
  - Query audit policy status and configuration
  - Supports privilege, action, role, and condition-based auditing
  - Compatible with Oracle 19c, 23ai, and 26ai
  - See connection parameters for oracle_ping
version_added: "3.4.0"
options:
  state:
    description: The intended state of the audit policy
    default: present
    choices: ['present', 'absent', 'enabled', 'disabled', 'status']
  policy_name:
    description: Name of the Unified Audit policy
    required: true
  audit_actions:
    description:
      - List of actions to audit (e.g. SELECT, INSERT, DELETE, UPDATE)
      - "Can include object-specific actions: SELECT ON schema.table"
    type: list
    elements: str
    required: false
  audit_privileges:
    description:
      - List of system privileges to audit (e.g. CREATE TABLE, ALTER USER, DROP ANY TABLE)
    type: list
    elements: str
    required: false
  audit_roles:
    description:
      - List of roles whose privileges should be audited
    type: list
    elements: str
    required: false
  audit_condition:
    description:
      - "A condition expression for conditional auditing (e.g. SYS_CONTEXT('USERENV','IP_ADDRESS') != '10.0.0.1')"
    required: false
  evaluate_per:
    description:
      - Frequency of condition evaluation
    choices: ['statement', 'session', 'instance']
    required: false
  container:
    description:
      - Container clause for multitenant
    choices: ['current', 'all']
    default: current
  enabled_users:
    description:
      - List of users to enable the policy for (empty list means all users)
      - Use special value ALL for all users
    type: list
    elements: str
    required: false
  enabled_except_users:
    description:
      - List of users to exclude when enabling for all users
    type: list
    elements: str
    required: false
notes:
  - Requires AUDIT SYSTEM or AUDIT_ADMIN role
  - oracledb Python module is required
  - Uses Unified Auditing (available since Oracle 12c)
requirements: [ "oracledb" ]
author:
  - Cyrille Modiano
'''

EXAMPLES = '''
- name: Create a privilege audit policy
  oracle_audit:
    mode: sysdba
    policy_name: priv_audit_pol
    audit_privileges:
      - CREATE TABLE
      - ALTER USER
      - DROP ANY TABLE
    state: present

- name: Create an action audit policy
  oracle_audit:
    mode: sysdba
    policy_name: dml_audit_pol
    audit_actions:
      - SELECT ON hr.employees
      - INSERT ON hr.employees
      - DELETE ON hr.employees
    state: present

- name: Create a role-based audit policy
  oracle_audit:
    mode: sysdba
    policy_name: dba_role_audit
    audit_roles:
      - DBA
      - SYSDBA
    state: present

- name: Create a conditional audit policy
  oracle_audit:
    mode: sysdba
    policy_name: external_access_audit
    audit_actions:
      - SELECT
      - UPDATE
    audit_condition: "SYS_CONTEXT('USERENV','IP_ADDRESS') NOT LIKE '10.%'"
    evaluate_per: session
    state: present

- name: Enable audit policy for all users
  oracle_audit:
    mode: sysdba
    policy_name: priv_audit_pol
    state: enabled

- name: Enable audit policy for specific users
  oracle_audit:
    mode: sysdba
    policy_name: dml_audit_pol
    state: enabled
    enabled_users:
      - HR
      - SCOTT

- name: Enable policy for all users except some
  oracle_audit:
    mode: sysdba
    policy_name: dml_audit_pol
    state: enabled
    enabled_except_users:
      - SYS
      - SYSTEM

- name: Disable audit policy
  oracle_audit:
    mode: sysdba
    policy_name: priv_audit_pol
    state: disabled

- name: Drop audit policy
  oracle_audit:
    mode: sysdba
    policy_name: priv_audit_pol
    state: absent

- name: Get audit policy status
  oracle_audit:
    mode: sysdba
    policy_name: priv_audit_pol
    state: status
  register: audit_info
'''


def get_policy(conn, policy_name):
    """Query AUDIT_UNIFIED_POLICIES for a policy definition."""
    sql = """SELECT POLICY_NAME, AUDIT_OPTION, AUDIT_OPTION_TYPE,
                    OBJECT_SCHEMA, OBJECT_NAME, OBJECT_TYPE,
                    AUDIT_CONDITION, CONDITION_EVAL_OPT
             FROM AUDIT_UNIFIED_POLICIES
             WHERE POLICY_NAME = UPPER(:name)"""
    return conn.execute_select_to_dict(sql, {'name': policy_name})


def get_policy_enabled(conn, policy_name):
    """Query AUDIT_UNIFIED_ENABLED_POLICIES for enabled state."""
    sql = """SELECT POLICY_NAME, ENABLED_OPTION, ENTITY_NAME, ENTITY_TYPE, SUCCESS, FAILURE
             FROM AUDIT_UNIFIED_ENABLED_POLICIES
             WHERE POLICY_NAME = UPPER(:name)"""
    return conn.execute_select_to_dict(sql, {'name': policy_name})


def policy_exists(conn, policy_name):
    """Check if a policy exists."""
    rows = get_policy(conn, policy_name)
    return bool(rows)


def policy_is_enabled(conn, policy_name):
    """Check if a policy is enabled."""
    rows = get_policy_enabled(conn, policy_name)
    return bool(rows)


def create_policy(conn, module):
    """Create a Unified Audit policy."""
    policy_name = module.params["policy_name"]
    audit_actions = module.params["audit_actions"]
    audit_privileges = module.params["audit_privileges"]
    audit_roles = module.params["audit_roles"]
    audit_condition = module.params["audit_condition"]
    evaluate_per = module.params["evaluate_per"]
    container = module.params["container"]

    clauses = []

    if audit_privileges:
        clauses.append('PRIVILEGES %s' % ', '.join(audit_privileges))

    if audit_actions:
        clauses.append('ACTIONS %s' % ', '.join(audit_actions))

    if audit_roles:
        clauses.append('ROLES %s' % ', '.join(audit_roles))

    if not clauses:
        module.fail_json(
            msg='At least one of audit_actions, audit_privileges, or audit_roles is required',
            changed=False,
        )

    sql = 'CREATE AUDIT POLICY %s %s' % (policy_name, ' '.join(clauses))

    if audit_condition:
        sql += " CONDITION '%s'" % audit_condition
        if evaluate_per:
            sql += ' EVALUATE PER %s' % evaluate_per.upper()

    if container == 'all':
        sql += ' CONTAINER = ALL'

    conn.execute_ddl(sql)


def drop_policy(conn, module):
    """Drop a Unified Audit policy."""
    policy_name = module.params["policy_name"]
    conn.execute_ddl('DROP AUDIT POLICY %s' % policy_name)


def enable_policy(conn, module):
    """Enable a Unified Audit policy."""
    policy_name = module.params["policy_name"]
    enabled_users = module.params["enabled_users"]
    enabled_except_users = module.params["enabled_except_users"]

    sql = 'AUDIT POLICY %s' % policy_name

    if enabled_users:
        sql += ' BY %s' % ', '.join(enabled_users)
    elif enabled_except_users:
        sql += ' EXCEPT %s' % ', '.join(enabled_except_users)

    conn.execute_ddl(sql)


def disable_policy(conn, module):
    """Disable a Unified Audit policy."""
    policy_name = module.params["policy_name"]
    conn.execute_ddl('NOAUDIT POLICY %s' % policy_name)


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

            state=dict(default='present',
                       choices=['present', 'absent', 'enabled', 'disabled', 'status']),
            policy_name=dict(required=True),
            audit_actions=dict(required=False, type='list', elements='str'),
            audit_privileges=dict(required=False, type='list', elements='str'),
            audit_roles=dict(required=False, type='list', elements='str'),
            audit_condition=dict(required=False),
            evaluate_per=dict(required=False,
                             choices=['statement', 'session', 'instance']),
            container=dict(default='current', choices=['current', 'all']),
            enabled_users=dict(required=False, type='list', elements='str'),
            enabled_except_users=dict(required=False, type='list', elements='str'),
        ),
        mutually_exclusive=[
            ('enabled_users', 'enabled_except_users'),
        ],
        supports_check_mode=True,
    )
    sanitize_string_params(module.params)

    state = module.params["state"]
    policy_name = module.params["policy_name"]
    conn = oracleConnection(module)

    if state == 'status':
        policy_rows = get_policy(conn, policy_name)
        enabled_rows = get_policy_enabled(conn, policy_name)
        module.exit_json(
            changed=False,
            exists=bool(policy_rows),
            enabled=bool(enabled_rows),
            policy=policy_rows,
            enabled_details=enabled_rows,
        )

    elif state == 'present':
        if policy_exists(conn, policy_name):
            module.exit_json(changed=False, msg='Policy already exists')
        create_policy(conn, module)
        module.exit_json(
            changed=conn.changed, ddls=conn.ddls,
            msg='Audit policy created',
        )

    elif state == 'absent':
        if not policy_exists(conn, policy_name):
            module.exit_json(changed=False, msg='Policy does not exist')
        # Disable first if enabled
        if policy_is_enabled(conn, policy_name):
            disable_policy(conn, module)
        drop_policy(conn, module)
        module.exit_json(
            changed=conn.changed, ddls=conn.ddls,
            msg='Audit policy dropped',
        )

    elif state == 'enabled':
        if not policy_exists(conn, policy_name):
            module.fail_json(msg='Policy %s does not exist' % policy_name, changed=False)
        if policy_is_enabled(conn, policy_name):
            module.exit_json(changed=False, msg='Policy already enabled')
        enable_policy(conn, module)
        module.exit_json(
            changed=conn.changed, ddls=conn.ddls,
            msg='Audit policy enabled',
        )

    elif state == 'disabled':
        if not policy_is_enabled(conn, policy_name):
            module.exit_json(changed=False, msg='Policy already disabled')
        disable_policy(conn, module)
        module.exit_json(
            changed=conn.changed, ddls=conn.ddls,
            msg='Audit policy disabled',
        )


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
