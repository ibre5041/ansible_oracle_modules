#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_flashback
short_description: Manage Oracle restore points and flashback database
description:
  - Create and drop restore points (normal and guaranteed)
  - Query restore point status
  - Compatible with Oracle 19c, 23ai, and 26ai
  - See connection parameters for oracle_ping
version_added: "3.4.0"
options:
  state:
    description: The intended state of the restore point
    default: present
    choices: ['present', 'absent', 'status']
  restore_point:
    description: Name of the restore point
    required: true
  guaranteed:
    description:
      - Create a guaranteed restore point
      - Requires a configured flashback recovery area
    type: bool
    default: false
  scn:
    description: Optional SCN (System Change Number) for the restore point
    type: int
    required: false
  preserve:
    description:
      - Preserve the restore point so it does not age out automatically
    type: bool
    default: false
author:
  - Cyrille Modiano
'''

EXAMPLES = '''
- name: Create a normal restore point
  oracle_flashback:
    mode: sysdba
    restore_point: BEFORE_UPGRADE
    state: present

- name: Create a guaranteed restore point
  oracle_flashback:
    mode: sysdba
    restore_point: GUARANTEED_RP
    guaranteed: true
    state: present

- name: Create a restore point at a specific SCN
  oracle_flashback:
    mode: sysdba
    restore_point: AT_SCN_RP
    scn: 1234567
    state: present

- name: Create a preserved restore point
  oracle_flashback:
    mode: sysdba
    restore_point: PRESERVED_RP
    preserve: true
    state: present

- name: Drop a restore point
  oracle_flashback:
    mode: sysdba
    restore_point: BEFORE_UPGRADE
    state: absent

- name: Get restore point status
  oracle_flashback:
    mode: sysdba
    restore_point: BEFORE_UPGRADE
    state: status
  register: rp_info
'''


def get_restore_point(conn, name):
    """Query V$RESTORE_POINT for a restore point."""
    sql = """SELECT NAME, SCN, TIME, STORAGE_SIZE,
                    GUARANTEE_FLASHBACK_DATABASE, PRESERVED
             FROM V$RESTORE_POINT
             WHERE NAME = UPPER(:name)"""
    return conn.execute_select_to_dict(sql, {'name': name})


def restore_point_exists(conn, name):
    return bool(get_restore_point(conn, name))


def create_restore_point(conn, module):
    """Create a restore point."""
    name = module.params["restore_point"]
    guaranteed = module.params["guaranteed"]
    scn = module.params["scn"]
    preserve = module.params["preserve"]

    sql = 'CREATE RESTORE POINT %s' % name

    if scn:
        sql += ' AS OF SCN %d' % scn

    if preserve:
        sql += ' PRESERVE'

    if guaranteed:
        sql += ' GUARANTEE FLASHBACK DATABASE'

    conn.execute_ddl(sql)


def drop_restore_point(conn, module):
    """Drop a restore point."""
    name = module.params["restore_point"]
    conn.execute_ddl('DROP RESTORE POINT %s' % name)


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
                       choices=['present', 'absent', 'status']),
            restore_point=dict(required=True),
            guaranteed=dict(default=False, type='bool'),
            scn=dict(required=False, type='int'),
            preserve=dict(default=False, type='bool'),
        ),
        supports_check_mode=True,
    )
    sanitize_string_params(module.params)

    state = module.params["state"]
    name = module.params["restore_point"]
    conn = oracleConnection(module)

    if state == 'status':
        rows = get_restore_point(conn, name)
        module.exit_json(
            changed=False,
            exists=bool(rows),
            restore_point=rows,
        )

    elif state == 'present':
        if restore_point_exists(conn, name):
            module.exit_json(changed=False, msg='Restore point already exists')
        create_restore_point(conn, module)
        module.exit_json(
            changed=conn.changed, ddls=conn.ddls,
            msg='Restore point created',
        )

    elif state == 'absent':
        if not restore_point_exists(conn, name):
            module.exit_json(changed=False, msg='Restore point does not exist')
        drop_restore_point(conn, module)
        module.exit_json(
            changed=conn.changed, ddls=conn.ddls,
            msg='Restore point dropped',
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
