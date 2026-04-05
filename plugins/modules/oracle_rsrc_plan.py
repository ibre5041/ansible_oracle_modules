#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_rsrc_plan
short_description: Manage Oracle Resource Manager plans
description:
  - Create, update, drop, and activate Resource Manager plans
  - Manage plan directives
  - Compatible with Oracle 19c, 23ai, and 26ai
  - See connection parameters for oracle_ping
version_added: "3.4.0"
options:
  state:
    description: The intended state of the resource plan
    default: present
    choices: ['present', 'absent', 'active', 'status']
  plan:
    description: Name of the resource plan
    required: true
  comment:
    description: Description/comment for the plan
    required: false
  directives:
    description:
      - List of plan directives
      - Each directive is a dict with keys group, cpu_p1, parallel_degree_limit_p1,
        active_sess_pool_p1, max_idle_time, max_idle_blocker_time
    type: list
    elements: dict
    required: false
  max_iops:
    description: Max I/O operations per second per session
    type: int
    required: false
  max_mbps:
    description: Max megabytes per second per session
    type: int
    required: false
author:
  - Cyrille Modiano
'''

EXAMPLES = '''
- name: Create a resource plan with directives
  oracle_rsrc_plan:
    mode: sysdba
    plan: MY_PLAN
    comment: Custom resource plan
    directives:
      - group: OLTP_GROUP
        cpu_p1: 70
      - group: BATCH_GROUP
        cpu_p1: 20
      - group: OTHER_GROUPS
        cpu_p1: 10
    state: present

- name: Activate a resource plan
  oracle_rsrc_plan:
    mode: sysdba
    plan: MY_PLAN
    state: active

- name: Drop a resource plan
  oracle_rsrc_plan:
    mode: sysdba
    plan: MY_PLAN
    state: absent

- name: Check resource plan status
  oracle_rsrc_plan:
    mode: sysdba
    plan: MY_PLAN
    state: status
  register: rsrc_plan_info
'''


def get_plan(conn, plan_name):
    """Query DBA_RSRC_PLANS for a resource plan."""
    sql = """SELECT PLAN, NUM_PLAN_DIRECTIVES, CPU_METHOD,
                    MGMT_METHOD, STATUS, MANDATORY
             FROM DBA_RSRC_PLANS
             WHERE PLAN = UPPER(:name)"""
    return conn.execute_select_to_dict(sql, {'name': plan_name})


def get_plan_directives(conn, plan_name):
    """Query DBA_RSRC_PLAN_DIRECTIVES for plan directives."""
    sql = """SELECT PLAN, GROUP_OR_SUBPLAN, TYPE, CPU_P1,
                    PARALLEL_DEGREE_LIMIT_P1, ACTIVE_SESS_POOL_P1,
                    MAX_IDLE_TIME, MAX_IDLE_BLOCKER_TIME,
                    MAX_IOPS, MAX_MBPS
             FROM DBA_RSRC_PLAN_DIRECTIVES
             WHERE PLAN = UPPER(:name)"""
    return conn.execute_select_to_dict(sql, {'name': plan_name})


def plan_exists(conn, plan_name):
    return bool(get_plan(conn, plan_name))


def get_active_plan(conn):
    """Get the currently active resource plan."""
    sql = """SELECT VALUE FROM V$PARAMETER
             WHERE NAME = 'resource_manager_plan'"""
    row = conn.execute_select_to_dict(sql, fetchone=True)
    return row.get('value', '') if row else ''


def create_plan(conn, module):
    """Create a resource plan with directives."""
    plan = module.params["plan"]
    comment = module.params["comment"] or ''
    directives = module.params["directives"] or []

    # Create pending area
    conn.execute_ddl("BEGIN DBMS_RESOURCE_MANAGER.CREATE_PENDING_AREA(); END;")

    # Create plan
    conn.execute_ddl(
        "BEGIN DBMS_RESOURCE_MANAGER.CREATE_PLAN("
        "plan => '%s', comment => '%s'); END;" % (plan, comment)
    )

    # Create directives
    for d in directives:
        _create_directive(conn, plan, d)

    # Submit pending area
    conn.execute_ddl("BEGIN DBMS_RESOURCE_MANAGER.SUBMIT_PENDING_AREA(); END;")


def _create_directive(conn, plan, directive):
    """Create a single plan directive."""
    group = directive['group']
    parts = ["plan => '%s'" % plan, "group_or_subplan => '%s'" % group]

    for key, param in [('cpu_p1', 'cpu_p1'),
                       ('parallel_degree_limit_p1', 'parallel_degree_limit_p1'),
                       ('active_sess_pool_p1', 'active_sess_pool_p1'),
                       ('max_idle_time', 'max_idle_time'),
                       ('max_idle_blocker_time', 'max_idle_blocker_time'),
                       ('max_iops', 'max_iops'),
                       ('max_mbps', 'max_mbps')]:
        if directive.get(key) is not None:
            parts.append('%s => %d' % (param, directive[key]))

    conn.execute_ddl(
        "BEGIN DBMS_RESOURCE_MANAGER.CREATE_PLAN_DIRECTIVE(%s); END;" % ', '.join(parts)
    )


def drop_plan(conn, module):
    """Drop a resource plan."""
    plan = module.params["plan"]
    conn.execute_ddl("BEGIN DBMS_RESOURCE_MANAGER.CREATE_PENDING_AREA(); END;")
    conn.execute_ddl(
        "BEGIN DBMS_RESOURCE_MANAGER.DELETE_PLAN_CASCADE(plan => '%s'); END;" % plan
    )
    conn.execute_ddl("BEGIN DBMS_RESOURCE_MANAGER.SUBMIT_PENDING_AREA(); END;")


def activate_plan(conn, module):
    """Set the active resource plan."""
    plan = module.params["plan"]
    conn.execute_ddl(
        "ALTER SYSTEM SET RESOURCE_MANAGER_PLAN = '%s'" % plan
    )


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
                       choices=['present', 'absent', 'active', 'status']),
            plan=dict(required=True),
            comment=dict(required=False),
            directives=dict(required=False, type='list', elements='dict'),
            max_iops=dict(required=False, type='int'),
            max_mbps=dict(required=False, type='int'),
        ),
        supports_check_mode=True,
    )
    sanitize_string_params(module.params)

    state = module.params["state"]
    plan_name = module.params["plan"]
    conn = oracleConnection(module)

    if state == 'status':
        plan_rows = get_plan(conn, plan_name)
        directive_rows = get_plan_directives(conn, plan_name)
        active = get_active_plan(conn)
        module.exit_json(
            changed=False,
            exists=bool(plan_rows),
            plan=plan_rows,
            directives=directive_rows,
            active_plan=active,
            is_active=(active.upper() == plan_name.upper() if active else False),
        )

    elif state == 'present':
        if plan_exists(conn, plan_name):
            module.exit_json(changed=False, msg='Resource plan already exists')
        create_plan(conn, module)
        module.exit_json(
            changed=conn.changed, ddls=conn.ddls,
            msg='Resource plan created',
        )

    elif state == 'absent':
        if not plan_exists(conn, plan_name):
            module.exit_json(changed=False, msg='Resource plan does not exist')
        # Deactivate if active
        active = get_active_plan(conn)
        if active and active.upper() == plan_name.upper():
            conn.execute_ddl("ALTER SYSTEM SET RESOURCE_MANAGER_PLAN = ''")
        drop_plan(conn, module)
        module.exit_json(
            changed=conn.changed, ddls=conn.ddls,
            msg='Resource plan dropped',
        )

    elif state == 'active':
        if not plan_exists(conn, plan_name):
            module.fail_json(msg='Plan %s does not exist' % plan_name, changed=False)
        active = get_active_plan(conn)
        if active and active.upper() == plan_name.upper():
            module.exit_json(changed=False, msg='Plan already active')
        activate_plan(conn, module)
        module.exit_json(
            changed=conn.changed, ddls=conn.ddls,
            msg='Resource plan activated',
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
