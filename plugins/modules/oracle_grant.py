#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_grant
short_description: Manage users/schemas in an Oracle database
description:
    - Manage grant/privileges in an Oracle database
    - Handles role/sys privileges at the moment.
    - It is possible to add object privileges as well, but they are not considered when removing privs at the moment.
version_added: "3.0.0"
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
    schema:
        description:
            - The schema that should get grant added/removed
        required: false
        default: null
    grant:
        description:
            - The privileges granted to the new schema. Can be a string or a list
        required: false
        default: null
    object_privs:
        description:
            - The privileges granted to specific objects
            - format: 'priv1,priv2,priv3:owner.object_name'
              e.g:
              - select,update,insert,delete:sys.dba_tablespaces
              - select:sys.v_$session
        required: false
        default: null
    grant_mode:
        description:
            - Should the list of grant be enforced, or just appended to.
            - enforce: Whatever is in the list of grant will be enforced, i.e grant/privileges will be removed if they are not in the list
            - append: Grant/privileges are just appended, nothing is removed
        default: append
        choices: ['enforce','append']
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
# Add grant to the user
oracle_grant: hostname=remote-db-server service_name=orcl user=system password=manager schema=myschema state=present grant='create session','create any table',connect,resource

# Revoke the 'create any table' grant
oracle_grant: hostname=localhost service_name=orcl user=system password=manager schema=myschema state=absent grant='create any table'

# Remove all grant from a user
oracle_grant: hostname=localhost service_name=orcl user=system password=manager schema=myschema state=REMOVEALL grant=


'''


def clean_string(item):
    item = item.replace("'", "").replace(", ", ",").lstrip(" ").rstrip(",").replace("[", "").replace("]", "")
    return item


def clean_list(item):
    item = [p.replace("'", "").replace(", ", ",").lstrip(" ").rstrip(",").replace("[", "").replace("]", "") for p in item]
    return item


# Check if the user/schema exists
def check_user_exists(conn, schema):
    """Check user exists, return user's attributes"""
    sql = """
    select username
        , account_status
        , default_tablespace
        , temporary_tablespace
        , profile
        , authentication_type
        , oracle_maintained
    from dba_users
    where username = upper(:schema_name)"""

    r = conn.execute_select_to_dict(sql, {"schema_name": schema}, fetchone=True)
    if r:
        acs = r['account_status']
        if acs == 'EXPIRED & LOCKED':
            r['account_status'] = 'LOCKED'
            r['password_status'] = 'EXPIRED'
        elif acs == 'EXPIRED':
            r['account_status'] = 'OPEN'
            r['password_status'] = 'EXPIRED'
        elif acs == 'LOCKED':
            r['account_status'] = 'LOCKED'
            r['password_status'] = 'UNEXPIRED'
        elif acs == 'OPEN':
            r['account_status'] = 'OPEN'
            r['password_status'] = 'UNEXPIRED'
        else:
            conn.fail_json(msg="Unsupported account state %s" % acs, ddls=conn.ddls, changed=conn.changed)

    return set(r.items())


# Check if the user/role exists
def check_role_exists(conn, role):
    role = clean_string(role)
    sql = 'select * from dba_roles where role = upper(:role_name)'
    r = conn.execute_select_to_dict(sql, {"role_name": role}, fetchone=True)
    return r


def get_dir_privs(conn, schema, directory_privs, grant_mode):
    total_sql_dir = []
    grant_list_dir = []
    revoke_list_dir = []

    # Directory Privs
    wanted_dirprivs_list = directory_privs
    w_object_name_l = [w.split(':')[1].lower() for w in wanted_dirprivs_list]
    w_object_priv_l = [w.split(':')[0].lower() for w in wanted_dirprivs_list]
    w_object_priv_l = [set(w.split(',')) for w in w_object_priv_l]
    wanted_privs_d = dict(zip(w_object_name_l, w_object_priv_l))

    currdsql_all = """
    select listagg(p.privilege, ',') within group (order by p.privilege), p.table_name
    from dba_tab_privs p, dba_objects o
    where p.grantee = upper(:grantee)
    and p.table_name = o.object_name
    and p.owner = o.owner
    and o.object_type = 'DIRECTORY'
    group by p.owner,p.table_name
    """
    result = conn.execute_select(currdsql_all, params={'grantee': schema}, fetchone=False)

    c_dir_name_l = [o[1].lower() for o in result]
    c_dir_priv_l = [o[0].lower() for o in result]
    c_dir_priv_l = [set(o[0].lower().split(',')) for o in result]
    current_dir_privs_d = dict(zip(c_dir_name_l, c_dir_priv_l))

    remove_completely_dir = set(c_dir_name_l).difference(w_object_name_l)
    for remove in remove_completely_dir:
        rdsql = 'revoke all on directory %s from %s' % (remove, schema)
        revoke_list_dir.append(rdsql)

    newstuff = set(w_object_name_l).difference(c_dir_name_l)
    if newstuff:
        for directory in newstuff:
            grants = wanted_privs_d[directory]
            nsql = "grant %s on directory %s to %s" % (','.join(grants), directory, schema)
            grant_list_dir.append(nsql)

    changedstuff = set(w_object_name_l).intersection(c_dir_name_l)
    for directory in changedstuff:
        wanted_grants = wanted_privs_d[directory]
        current_grants = current_dir_privs_d[directory]
        new_grants = wanted_grants.difference(current_grants)
        old_grants = current_grants.difference(wanted_grants)
        if new_grants:
            adsql = "grant %s on directory %s to %s" % (','.join(new_grants), directory, schema)
            grant_list_dir.append(adsql)
        if old_grants:
            rdsql = "revoke %s on directory %s from %s" % (','.join(old_grants), directory, schema)
            revoke_list_dir.append(rdsql)

    if grant_mode.lower() == 'enforce':
        total_sql_dir.extend(revoke_list_dir)

    total_sql_dir.extend(grant_list_dir)

    return total_sql_dir


def get_obj_privs(conn, schema, wanted_privs_list, grant_mode):
    total_sql_obj = []
    grant_list = []
    revoke_list = []

    # OBJECT PRIVS
    w_object_name_l = [w.split(':')[1].lower().strip() for w in wanted_privs_list]
    w_object_priv_l = [w.split(':')[0].lower().strip() for w in wanted_privs_list]
    w_object_priv_l = [set(w.split(',')) for w in w_object_priv_l]
    wanted_privs_d = dict(zip(w_object_name_l, w_object_priv_l))

    currsql_all = """
    select listagg(p.privilege,',') within group (order by p.privilege), p.owner||'.'||p.table_name
    from dba_tab_privs p, dba_objects o
    where p.grantee = upper(:schema)
    and p.table_name = o.object_name
    and p.owner = o.owner
    and o.object_type not in ('DIRECTORY','TABLE PARTITION','TABLE SUBPARTITION')
    group by p.owner,p.table_name
    """
    result = conn.execute_select(currsql_all, {'schema': schema}, fetchone=False)
    c_object_name_l = [o[1].lower() for o in result]
    c_object_priv_l = [set(o[0].lower().split(',')) for o in result]
    current_privs_d = dict(zip(c_object_name_l, c_object_priv_l))

    remove_completely = set(c_object_name_l).difference(w_object_name_l)
    for remove in remove_completely:
        rsql = 'revoke all on %s from %s' % (remove, schema)
        revoke_list.append(rsql)

    newstuff = set(w_object_name_l).difference(c_object_name_l)
    for obj in newstuff:
        grants = wanted_privs_d[obj]
        nsql = "grant %s on %s to %s" % (','.join(grants), obj, schema)
        grant_list.append(nsql)

    changedstuff = set(w_object_name_l).intersection(c_object_name_l)
    for obj in changedstuff:
        wanted_grants = wanted_privs_d[obj]
        current_grants = current_privs_d[obj]
        new_grants = wanted_grants.difference(current_grants)
        old_grants = current_grants.difference(wanted_grants)
        if new_grants:
            asql = "grant %s on %s to %s" % (','.join(new_grants), obj, schema)
            grant_list.append(asql)
        if old_grants:
            rsql = "revoke %s on %s from %s" % (','.join(old_grants), obj, schema)
            revoke_list.append(rsql)

    if grant_mode.lower() == 'enforce':
        total_sql_obj.extend(revoke_list)

    total_sql_obj.extend(grant_list)

    return total_sql_obj


# Add grant to the schema/role
def ensure_grant(module, conn, schema, wanted_grant_list, object_privs, directory_privs, grant_mode, container):
    add_sql = ''
    remove_sql = ''

    # If no privs are added, we set the 'wanted' lists to be empty.
    if wanted_grant_list is None or wanted_grant_list == ['']:
        wanted_grant_list = []
    if object_privs is None or object_privs == ['']:
        object_privs = []
    if directory_privs is None or directory_privs == ['']:
        directory_privs = []

    # This list will hold all grant the user currently has
    total_sql = []
    total_current = []

    obj_privs = get_obj_privs(conn, schema, object_privs, grant_mode)
    total_sql.extend(obj_privs)

    dir_privs = get_dir_privs(conn, schema, directory_privs, grant_mode)
    total_sql.extend(dir_privs)

    exceptions_list = ['DBA']
    exceptions_priv = ['UNLIMITED TABLESPACE']

    # Strip the list of unnecessary quotes etc
    wanted_grant_list = clean_list(wanted_grant_list)
    wanted_grant_list = [x.lower() for x in wanted_grant_list]
    wanted_grant_list_upper = [x.upper() for x in wanted_grant_list]
    schema = clean_string(schema)

    # Get the current role grant for the schema. If any are present, add them to the total
    curr_role_grant = get_current_role_grant(conn, schema)
    if any(curr_role_grant):
        total_current.extend(curr_role_grant)

    # Get the current sys privs for the schema. If any are present, add them to the total
    curr_sys_grant=get_current_sys_grant(conn, schema)
    if any(curr_sys_grant):
        total_current.extend(curr_sys_grant)

    # Get the difference between current grant and wanted grant
    grant_to_add = set(wanted_grant_list).difference(total_current)
    grant_to_remove = set(total_current).difference(wanted_grant_list)

    # Special case: If DBA is granted to a user, unlimited tablespace is also implicitly
    # granted -> on the next run, unlimited tablespace is removed from the user
    # since it is not part of the wanted grant.
    # The following removes 'unlimited tablespace' privilege from the grant_to_remove list, if DBA is also granted
    if any(x in exceptions_list for x in wanted_grant_list_upper):
        grant_to_remove = [x for x in grant_to_remove if x.upper() not in exceptions_priv]

    if grant_mode.lower() == 'enforce' and any(grant_to_remove):
        grant_to_remove = ','.join(grant_to_remove)
        grant_to_remove = clean_string(grant_to_remove)
        remove_sql += 'revoke %s from %s' % (grant_to_remove, schema)
        total_sql.append(remove_sql)

    if any(grant_to_add):
        grant_to_add = ','.join(grant_to_add)
        grant_to_add = clean_string(grant_to_add)
        add_sql += 'grant %s to %s' % (grant_to_add, schema)
        if container:
            add_sql += ' container=%s' % container
        total_sql.append(add_sql)

    if total_sql:
        for sql in total_sql:
            conn.execute_ddl(sql)
        module.exit_json(msg=total_sql, changed=conn.changed, ddls=conn.ddls)
    else:
        msg = 'Nothing to do'
        module.exit_json(msg=msg, changed=conn.changed)


# Remove grant to the schema
def remove_grant(module, conn, schema, remove_grant_list, state):
    sql = ''

    # This list will hold all grant/privs the user currently has
    total_current=[]

    # Strip the list of unnecessary quotes etc
    remove_grant_list = clean_list(remove_grant_list)
    schema = clean_string(schema)

    # Get the current role grant for the schema.
    # If any are present, add them to the total
    curr_role_grant = get_current_role_grant(conn, schema)
    if any(curr_role_grant):
        total_current.extend(curr_role_grant)

    # Get the current sys privs for the schema
    # If any are present, add them to the total
    curr_sys_grant = get_current_sys_grant(conn, schema)
    if any(curr_sys_grant):
        total_current.extend(curr_sys_grant)

    # Get the difference between current grant and wanted grant
    grant_to_remove = set(remove_grant_list).intersection(total_current)

    # If state=REMOVEALL is used, all grant/privs will be removed
    if state == 'REMOVEALL' and any(total_current):
        remove_all = ','.join(total_current)
        sql += 'revoke %s from %s' % (remove_all, schema)
        msg = 'All privileges/grant (%s) are removed from schema/role %s' % (remove_all, schema)
        conn.execute_ddl(conn, sql)
        module.exit_json(msg=msg, changed=changed)

    # if there are differences, they will be removed.
    elif not any(grant_to_remove):
        module.exit_json(msg="The schema/role (%s) doesn't have the grant(s) you want to remove" % schema, changed=False)

    else:
        # Convert the list of grant to a string & clean it
        grant_to_remove = ','.join(grant_to_remove)
        grant_to_remove = clean_string(grant_to_remove)
        sql += 'revoke %s from %s' % (grant_to_remove, schema)
        if grant_to_remove:
            conn.execute_ddl(conn, sql)
            msg = 'The grant(s) (%s) successfully removed from the schema/role %s' % (grant_to_remove, schema)
            module.exit_json(msg=msg, changed=changed)
        else:
            msg = 'Nothing to do'
            module.exit_json(msg=msg, changed=changed)


# Get the current role/sys grant
def get_current_role_grant(conn, schema):
    curr_role_grant = []
    sql = 'select granted_role from dba_role_privs where grantee = upper(:schema)'
    result = conn.execute_select(sql, {'schema': schema})
    for item in result:
        curr_role_grant.append(item[0].lower())

    sql = 'select * from v$pwfile_users where USERNAME = upper(:schema)'
    result = conn.execute_select_to_dict(sql, {'schema': schema}, fetchone=False)
    if result:
        for role in ['SYSDBA', 'SYSOPER', 'SYSASM', 'SYSBACKUP', 'SYSDG', 'SYSKM']:
            if role in result and result[role] == 'TRUE':
                curr_role_grant.append(role.lower())

    return curr_role_grant


# Get the current sys grant
def get_current_sys_grant(conn, schema):
    curr_sys_grant = []

    sql = 'select privilege from dba_sys_privs where grantee = upper(:schema)'
    result = conn.execute_select(sql, {'schema': schema}, fetchone=False)
    for item in result:
        curr_sys_grant.append(item[0].lower())

    return curr_sys_grant


def main():
    global changed
    module = AnsibleModule(
        argument_spec = dict(
            oracle_home   = dict(required=False, aliases=['oh']),
            hostname      = dict(default='localhost'),
            port          = dict(default=1521, type="int"),
            service_name  = dict(required=False, aliases=['tns']),
            user          = dict(required=False, aliases=['username']),
            password      = dict(required=False, no_log=True),
            mode          = dict(default='normal', choices=["normal", "sysdba"]),

            grantee       = dict(required=True, type='str', aliases=['name', 'schema_name', 'role', 'role_name']),

            grants        = dict(default=None, type="list", aliases=['privileges']),
            object_privs  = dict(default=None, type="list", aliases=['objprivs']),
            directory_privs = dict(default=None, type="list", aliases=['dirprivs']),
            grant_mode    = dict(default="append", choices=["append", "enforce"], aliases=['privs_mode']),
            container     = dict(default=None),
            state         = dict(default="present", choices=["present", "absent", "REMOVEALL"])
        )
    )

    grantee = module.params["grantee"]
    grants = module.params["grants"]
    object_privs = module.params["object_privs"]
    directory_privs = module.params["directory_privs"]
    grant_mode = module.params["grant_mode"]
    container = module.params["container"]
    state = module.params["state"]

    oc = oracleConnection(module)
    if state == 'present':
        if check_user_exists(oc, grantee):
            ensure_grant(module, oc, grantee, grants, object_privs, directory_privs, grant_mode, container)
        elif check_role_exists(oc, grantee):
            ensure_grant(module, oc, grantee, grants, object_privs, directory_privs, grant_mode, container)
        else:
            msg = "Schema/Role %s doesn't exist" % grantee
            module.fail_json(msg=msg, changed=False)
    elif state in ['absent', 'REMOVEALL']:
        if check_user_exists(oc, grantee):
            remove_grant(module, oc, grantee, grantee, state)
        elif check_role_exists(oc, grantee):
            remove_grant(oc, grantee, grantee, state)
        else:
            module.exit_json(msg="Schema/Role (%s) doesn't exist" % grantee, changed=False)

    module.fail_json(msg='Unknown object', changed=False)


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

