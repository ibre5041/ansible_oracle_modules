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
        active_sess_pool_p1, max_idle_time, max_idle_blocker_time, max_iops, max_mbps
      - Per-directive C(max_iops) and C(max_mbps) override the module-level options below
    type: list
    elements: dict
    required: false
  max_iops:
    description:
      - Default max I/O operations per second per session for each plan directive when
        creating the plan (O(state=present))
      - Ignored unless O(directives) is non-empty; each directive can set its own C(max_iops)
    type: int
    required: false
  max_mbps:
    description:
      - Default max megabytes per second per session for each plan directive when
        creating the plan (O(state=present))
      - Ignored unless O(directives) is non-empty; each directive can set its own C(max_mbps)
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
    sql = """SELECT PLAN, COMMENTS, NUM_PLAN_DIRECTIVES, CPU_METHOD,
                    MGMT_METHOD, STATUS, MANDATORY
             FROM DBA_RSRC_PLANS
             WHERE PLAN = UPPER(:name)"""
    return conn.execute_select_to_dict(sql, {'name': plan_name})


def get_plan_directives(conn, plan_name):
    """Query DBA_RSRC_PLAN_DIRECTIVES for plan directives.

    MAX_IOPS and MAX_MBPS may not be present on all Oracle editions or
    versions (ORA-00904 on Oracle Free / Standard Edition). Fall back to
    a query without those columns when the full query fails.
    """
    # execute_select_to_dict calls module.fail_json() on DB errors (raises SystemExit),
    # so a bare except Exception cannot catch it. Use fail_on_error=False to get None
    # back on error, then fall back to the edition-safe query without MAX_IOPS/MAX_MBPS.
    sql = """SELECT PLAN, GROUP_OR_SUBPLAN, TYPE, CPU_P1,
                    PARALLEL_DEGREE_LIMIT_P1, ACTIVE_SESS_POOL_P1,
                    MAX_IDLE_TIME, MAX_IDLE_BLOCKER_TIME,
                    MAX_IOPS, MAX_MBPS
             FROM DBA_RSRC_PLAN_DIRECTIVES
             WHERE PLAN = UPPER(:name)"""
    result = conn.execute_select_to_dict(sql, {'name': plan_name}, fail_on_error=False)
    if result is not None:
        return result
    # Fallback: MAX_IOPS/MAX_MBPS columns absent on this Oracle edition
    sql = """SELECT PLAN, GROUP_OR_SUBPLAN, TYPE, CPU_P1,
                    PARALLEL_DEGREE_LIMIT_P1, ACTIVE_SESS_POOL_P1,
                    MAX_IDLE_TIME, MAX_IDLE_BLOCKER_TIME
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
    val = row.get('value') if row else None
    return '' if val is None else val


_DIRECTIVE_COMPARE_KEYS = (
    'cpu_p1',
    'parallel_degree_limit_p1',
    'active_sess_pool_p1',
    'max_idle_time',
    'max_idle_blocker_time',
    'max_iops',
    'max_mbps',
)


def _row_keys_lower(row):
    return {(k or '').lower(): v for k, v in row.items()}


def _norm_scalar(val):
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return val


def _open_pending_area(conn):
    conn.execute_ddl(
        "BEGIN "
        "DBMS_RESOURCE_MANAGER.CLEAR_PENDING_AREA(); "
        "DBMS_RESOURCE_MANAGER.CREATE_PENDING_AREA(); "
        "END;"
    )


def _validate_and_normalize_directive_group(module, merged, index):
    """Require a non-empty group for each user-supplied directive; normalize whitespace."""
    raw = merged.get('group')
    if raw is None:
        module.fail_json(
            msg='Each directive must include a non-empty "group" key '
                 '(missing at directives[%s]).' % index,
            changed=False,
        )
    name = raw.strip() if isinstance(raw, str) else str(raw).strip()
    if not name:
        module.fail_json(
            msg='Each directive must include a non-empty "group" value '
                 '(invalid at directives[%s]).' % index,
            changed=False,
        )
    merged['group'] = name


def _merge_directives_for_plan(module):
    directives = module.params['directives'] or []
    default_max_iops = module.params.get('max_iops')
    default_max_mbps = module.params.get('max_mbps')
    out = []
    for index, d in enumerate(directives):
        merged = dict(d)
        _validate_and_normalize_directive_group(module, merged, index)
        if default_max_iops is not None and merged.get('max_iops') is None:
            merged['max_iops'] = default_max_iops
        if default_max_mbps is not None and merged.get('max_mbps') is None:
            merged['max_mbps'] = default_max_mbps
        out.append(merged)
    return out


def _consumer_group_directives_from_db(rows):
    out = []
    if not rows:
        return out
    for r in rows:
        rd = _row_keys_lower(r)
        # DBA_RSRC_PLAN_DIRECTIVES.TYPE is CONSUMER_GROUP or PLAN (subplan); not SUBPLAN.
        if (rd.get('type') or '').upper() != 'CONSUMER_GROUP':
            continue
        g = rd.get('group_or_subplan')
        if not g:
            continue
        d = {'group': g}
        for k in _DIRECTIVE_COMPARE_KEYS:
            d[k] = rd.get(k)
        out.append(d)
    return out


def _directive_compare_map(directive):
    return {k: _norm_scalar(directive.get(k)) for k in _DIRECTIVE_COMPARE_KEYS}


def _directive_values_equal(live_d, want_d):
    return _directive_compare_map(live_d) == _directive_compare_map(want_d)


def resource_plan_has_drift(module, live_plan_row, live_directive_rows):
    """Return (needs_update, detail_message_or_None)."""
    notes = []
    if module.params.get('comment') is not None:
        want_c = (module.params.get('comment') or '').strip()
        live_raw = live_plan_row.get('comments') or live_plan_row.get('COMMENTS')
        live_c = (live_raw or '').strip()
        if want_c != live_c:
            notes.append('comment (desired=%r, live=%r)' % (want_c, live_c))
    if module.params.get('directives') is not None:
        want_dirs = _merge_directives_for_plan(module)
        live_dirs = _consumer_group_directives_from_db(live_directive_rows)
        live_by = {x['group'].upper(): x for x in live_dirs}
        want_by = {x['group'].upper(): x for x in want_dirs}
        if set(live_by) != set(want_by):
            notes.append(
                'directive consumer groups differ (desired=%s, live=%s)'
                % (sorted(want_by), sorted(live_by))
            )
        else:
            for g in sorted(want_by):
                if not _directive_values_equal(live_by[g], want_by[g]):
                    notes.append(
                        'directive %s differs (desired=%s, live=%s)'
                        % (g, _directive_compare_map(want_by[g]),
                           _directive_compare_map(live_by[g]))
                    )
    if not notes:
        return False, None
    return True, '; '.join(notes)


def update_resource_plan(conn, module):
    """Apply comment and/or directive changes (pending area)."""
    plan = module.params['plan']
    live_rows = get_plan(conn, plan)
    live_plan_row = live_rows[0]
    live_directive_rows = get_plan_directives(conn, plan)
    merged_directives = None
    if module.params.get('directives') is not None:
        merged_directives = _merge_directives_for_plan(module)
    _open_pending_area(conn)
    if module.params.get('comment') is not None:
        want_c = (module.params.get('comment') or '').strip()
        live_raw = live_plan_row.get('comments') or live_plan_row.get('COMMENTS')
        live_c = (live_raw or '').strip()
        if want_c != live_c:
            conn.execute_ddl(
                "BEGIN DBMS_RESOURCE_MANAGER.UPDATE_PLAN("
                "plan => :plan, new_comment => :comment); END;",
                {'plan': plan, 'comment': want_c},
            )
    if merged_directives is not None:
        want_by = {x['group'].upper(): x for x in merged_directives}
        live_by = {x['group'].upper(): x for x in _consumer_group_directives_from_db(live_directive_rows)}
        for g in sorted(set(live_by) - set(want_by)):
            conn.execute_ddl(
                "BEGIN DBMS_RESOURCE_MANAGER.DELETE_PLAN_DIRECTIVE("
                "plan => :plan, group_or_subplan => :group); END;",
                {'plan': plan, 'group': g},
            )
        for g in sorted(want_by):
            spec = want_by[g]
            if g not in live_by:
                _create_directive(conn, plan, spec)
            elif not _directive_values_equal(live_by[g], spec):
                conn.execute_ddl(
                    "BEGIN DBMS_RESOURCE_MANAGER.DELETE_PLAN_DIRECTIVE("
                    "plan => :plan, group_or_subplan => :group); END;",
                    {'plan': plan, 'group': g},
                )
                _create_directive(conn, plan, spec)
    conn.execute_ddl("BEGIN DBMS_RESOURCE_MANAGER.SUBMIT_PENDING_AREA(); END;")


def create_plan(conn, module):
    """Create a resource plan with directives."""
    plan = module.params["plan"]
    comment = module.params["comment"] or ''
    merged_directives = _merge_directives_for_plan(module)

    _open_pending_area(conn)

    # Create plan
    conn.execute_ddl(
        "BEGIN DBMS_RESOURCE_MANAGER.CREATE_PLAN("
        "plan => :plan, comment => :comment); END;",
        {'plan': plan, 'comment': comment},
    )

    for d in merged_directives:
        _create_directive(conn, plan, d)

    # Submit pending area
    conn.execute_ddl("BEGIN DBMS_RESOURCE_MANAGER.SUBMIT_PENDING_AREA(); END;")


def _create_directive(conn, plan, directive):
    """Create a single plan directive."""
    grp = directive.get('group')
    if grp is None:
        raise ValueError(
            'CREATE_PLAN_DIRECTIVE requires directive["group"]; '
            'user directives must be validated via _merge_directives_for_plan.'
        )
    name = grp.strip() if isinstance(grp, str) else str(grp).strip()
    if not name:
        raise ValueError(
            'CREATE_PLAN_DIRECTIVE requires a non-empty directive["group"].'
        )
    fragments = [
        "BEGIN DBMS_RESOURCE_MANAGER.CREATE_PLAN_DIRECTIVE(",
        "plan => :plan, group_or_subplan => :group_or_subplan",
    ]
    params = {'plan': plan, 'group_or_subplan': name}

    for key, param in [('cpu_p1', 'cpu_p1'),
                       ('parallel_degree_limit_p1', 'parallel_degree_limit_p1'),
                       ('active_sess_pool_p1', 'active_sess_pool_p1'),
                       ('max_idle_time', 'max_idle_time'),
                       ('max_idle_blocker_time', 'max_idle_blocker_time'),
                       ('max_iops', 'max_iops'),
                       ('max_mbps', 'max_mbps')]:
        if directive.get(key) is not None:
            fragments.append(', %s => :%s' % (param, param))
            params[param] = directive[key]

    fragments.append('); END;')
    conn.execute_ddl(''.join(fragments), params)


def drop_plan(conn, module):
    """Drop a resource plan."""
    plan = module.params["plan"]
    _open_pending_area(conn)
    conn.execute_ddl(
        "BEGIN DBMS_RESOURCE_MANAGER.DELETE_PLAN_CASCADE(plan => :plan); END;",
        {'plan': plan},
    )
    conn.execute_ddl("BEGIN DBMS_RESOURCE_MANAGER.SUBMIT_PENDING_AREA(); END;")


def activate_plan(conn, module):
    """Set the active resource plan."""
    plan = module.params["plan"]
    conn.execute_ddl(
        "BEGIN EXECUTE IMMEDIATE 'ALTER SYSTEM SET RESOURCE_MANAGER_PLAN = ' "
        "|| DBMS_ASSERT.ENQUOTE_LITERAL(:plan); END;",
        {'plan': plan},
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
        plan_rows = get_plan(conn, plan_name)
        if not plan_rows:
            if module.check_mode:
                module.exit_json(
                    changed=True,
                    msg='Resource plan would be created (check mode)',
                )
            create_plan(conn, module)
            module.exit_json(
                changed=conn.changed, ddls=conn.ddls,
                msg='Resource plan created',
            )
        drift, drift_detail = resource_plan_has_drift(
            module, plan_rows[0], get_plan_directives(conn, plan_name),
        )
        if not drift:
            module.exit_json(
                changed=False,
                msg='Resource plan already matches desired state',
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                msg='Resource plan would be updated (check mode): %s' % drift_detail,
            )
        update_resource_plan(conn, module)
        module.exit_json(
            changed=conn.changed, ddls=conn.ddls,
            msg='Resource plan updated: %s' % drift_detail,
        )

    elif state == 'absent':
        if not plan_exists(conn, plan_name):
            module.exit_json(changed=False, msg='Resource plan does not exist')
        active = get_active_plan(conn)
        if module.check_mode:
            module.exit_json(
                changed=True,
                msg='Resource plan would be dropped (check mode)',
            )
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
        if module.check_mode:
            module.exit_json(
                changed=True,
                msg='Resource plan would be activated (check mode)',
            )
        activate_plan(conn, module)
        module.exit_json(
            changed=conn.changed, ddls=conn.ddls,
            msg='Resource plan activated',
        )


from ansible.module_utils.basic import *  # noqa: F403

# In this case we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
#try:
#    from ansible.module_utils.oracle_utils import oracleConnection, sanitize_string_params
#except:
#    pass

# In this case we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import (  # noqa: E501
        oracleConnection, sanitize_string_params,
    )
except ImportError:
    def sanitize_string_params(_params):
        pass

if __name__ == '__main__':
    main()
