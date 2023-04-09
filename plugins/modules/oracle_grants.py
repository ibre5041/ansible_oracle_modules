#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_grants
short_description: Manage users/schemas in an Oracle database
description:
    - Manage grants/privileges in an Oracle database
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
            - The schema that should get grants added/removed
        required: false
        default: null
    grants:
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
    grants_mode:
        description:
            - Should the list of grants be enforced, or just appended to.
            - enforce: Whatever is in the list of grants will be enforced, i.e grants/privileges will be removed if they are not in the list
            - append: Grants/privileges are just appended, nothing is removed
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
# Add grants to the user
oracle_grants: hostname=remote-db-server service_name=orcl user=system password=manager schema=myschema state=present grants='create session','create any table',connect,resource

# Revoke the 'create any table' grant
oracle_grants: hostname=localhost service_name=orcl user=system password=manager schema=myschema state=absent grants='create any table'

# Remove all grants from a user
oracle_grants: hostname=localhost service_name=orcl user=system password=manager schema=myschema state=REMOVEALL grants=


'''

try:
    import cx_Oracle
except ImportError:
    cx_oracle_exists = False
else:
    cx_oracle_exists = True

# Default value for "changed" module's parameter
changed = False

# define Python user-defined exceptions
class ModuleExecutionException(Exception):
    "Raised when execution of some SQL fails"
    pass

    def __init__(self, message=""):
        self.message = message
        super().__init__(self.message)


def clean_string(item):
    item = item.replace("'","").replace(", ",",").lstrip(" ").rstrip(",").replace("[","").replace("]","")
    return item

def clean_list(item):
    item = [p.replace("'","").replace(", ",",").lstrip(" ").rstrip(",").replace("[","").replace("]","") for p in item]
    return item


# Check if the user/schema exists
def check_user_exists(conn, schema):
    with conn.cursor() as cursor:
        schema = clean_string(schema)
        sql = 'select count(*) from dba_users where username = upper(\'%s\')' % schema
        try:
            cursor.execute(sql)
            result = cursor.fetchone()[0]
            return bool(result)
        except cx_Oracle.DatabaseError as exc:
            error, = exc.args
            msg = error.message+ 'sql: ' + sql
            raise ModuleExecutionException(msg)


# Check if the user/role exists
def check_role_exists(conn, role):
    role = clean_string(role)
    with conn.cursor() as cursor:
        sql = 'select count(*) from dba_roles where role = upper(\'%s\')' % role
        try:
            cursor.execute(sql)
            result = cursor.fetchone()[0]
            return bool(result)
        except cx_Oracle.DatabaseError as exc:
            error, = exc.args
            msg = error.message + 'sql: ' + sql
            raise ModuleExecutionException(msg)


def get_dir_privs(conn, schema, directory_privs, grants_mode):

    total_sql_dir = []
    # Directory Privs

    # module.exit_json(msg=directory_privs)
    wanted_dirprivs_list = directory_privs
    w_object_name_l = [w.split(':')[1].lower() for w in wanted_dirprivs_list]
    w_object_priv_l = [w.split(':')[0].lower() for w in wanted_dirprivs_list]
    currdsql_all="""
    select lower(listagg(p.privilege,',') within group (order by p.privilege) ||':'||p.owner||'.'||p.table_name)
    from dba_tab_privs p, dba_objects o
    where p.grantee = upper(\'%s\')
    and p.table_name = o.object_name
    and p.owner = o.owner
    and o.object_type = 'DIRECTORY'
    group by p.owner,p.table_name
    """ % (schema)

    result = execute_sql_get(conn, currdsql_all)

    grant_list_dir = []
    revoke_list_dir = []
    current_privs_l = [a[0] for a in result] # Turn list of tuples into list from resultset
    c_dir_name_l = [ o.split(':')[1].lower() for o in current_privs_l]
    c_dir_priv_l = [ o.split(':')[0].lower() for o in current_privs_l]
    remove_completely_dir = set(c_dir_name_l).difference(w_object_name_l)
    if len(list(remove_completely_dir)) > 0:
       for remove in list(remove_completely_dir):
           rdsql = 'revoke all on directory %s from %s' % (remove,schema)
           revoke_list_dir.append(rdsql)

    newstuff = set(w_object_name_l).difference(c_dir_name_l)
    if len(list(newstuff)) > 0:
       for index,value in enumerate(w_object_name_l):
           if value in list(newstuff):
               nsql = "grant %s on directory %s to %s" % (wanted_dirprivs_list[index].split(':')[0], value, schema)
               grant_list_dir.append(nsql)

    if len(current_privs_l) > 0 and len(wanted_dirprivs_list) > 0:
       for cp in current_privs_l:
           object_owner = cp.split(':').pop().split('.')[0]
           object_name = cp.split(':').pop().split('.')[1]
           cp_privs = cp.split(':')[0].lower()
           for wp in wanted_dirprivs_list:
               wp_object = wp.split(':')[1].lower()
               if wp.split(':')[1].lower() == cp.split(':')[1].lower(): # Compare object_names
                   cp_privs = cp.split(':')[0].lower().split(',')
                   wp_privs = wp.split(':')[0].lower().split(',')
                   priv_add = set(wp_privs).difference(cp_privs)
                   priv_revoke = set(cp_privs).difference(wp_privs)
                   if len(list(priv_add)) > 0:
                       adsql = "grant %s on directory %s to %s" % (','.join(a for a in priv_add),wp_object,schema)
                       grant_list_dir.append(adsql)
                   if len(list(priv_revoke)) > 0:
                       rdsql = "revoke %s on directory %s from %s" % (','.join(a for a in priv_revoke),wp_object,schema)
                       revoke_list_dir.append(rdsql)

    for a in grant_list_dir:
        total_sql_dir.append(a)

    if grants_mode.lower() == 'enforce':
        for a in revoke_list_dir:
            total_sql_dir.append(a)

    return total_sql_dir


def get_obj_privs (conn, schema, object_privs, grants_mode):

    total_sql_obj = []
    # OBJECT PRIVS
    wanted_privs_list = object_privs
    w_object_name_l = [w.split(':')[1].lower() for w in wanted_privs_list]
    w_object_priv_l = [w.split(':')[0].lower() for w in wanted_privs_list]
    currsql_all="""
    select lower(listagg(p.privilege,',') within group (order by p.privilege) ||':'||p.owner||'.'||p.table_name)
    from dba_tab_privs p, dba_objects o
    where p.grantee = upper(\'%s\')
    and p.table_name = o.object_name
    and p.owner = o.owner
    and o.object_type not in ('DIRECTORY','TABLE PARTITION','TABLE SUBPARTITION')
    group by p.owner,p.table_name
    """ % (schema)

    result = execute_sql_get(conn, currsql_all)

    grant_list = []
    revoke_list = []
    current_privs_l = [a[0] for a in result] # Turn list of tuples into list from resultset
    c_object_name_l = [ o.split(':')[1].lower() for o in current_privs_l]
    c_object_priv_l = [ o.split(':')[0].lower() for o in current_privs_l]
    remove_completely = set(c_object_name_l).difference(w_object_name_l)
    if len(list(remove_completely)) > 0:
        for remove in list(remove_completely):
            rsql = 'revoke all on %s from %s' % (remove,schema)
            revoke_list.append(rsql)

    newstuff = set(w_object_name_l).difference(c_object_name_l)
    if len(list(newstuff)) > 0:
        for index,value in enumerate(w_object_name_l):
            if value in list(newstuff):
                nsql = "grant %s on %s to %s" % (wanted_privs_list[index].split(':')[0], value, schema)
                grant_list.append(nsql)

    if len(current_privs_l) > 0 and len(wanted_privs_list) > 0:
        for cp in current_privs_l:
            object_owner = cp.split(':').pop().split('.')[0]
            object_name = cp.split(':').pop().split('.')[1]
            cp_privs = cp.split(':')[0].lower()
            for wp in wanted_privs_list:
                wp_object = wp.split(':')[1].lower()
                if wp.split(':')[1].lower() == cp.split(':')[1].lower(): # Compare object_names
                    cp_privs = cp.split(':')[0].lower().split(',')
                    wp_privs = wp.split(':')[0].lower().split(',')
                    priv_add = set(wp_privs).difference(cp_privs)
                    priv_revoke = set(cp_privs).difference(wp_privs)
                    if len(list(priv_add)) > 0:
                        asql = "grant %s on %s to %s" % (','.join(a for a in priv_add),wp_object,schema)
                        grant_list.append(asql)
                    if len(list(priv_revoke)) > 0:
                        rsql = "revoke %s on %s from %s" % (','.join(a for a in priv_revoke),wp_object,schema)
                        revoke_list.append(rsql)

    if grants_mode.lower() == 'enforce':
        for a in revoke_list:
            total_sql_obj.append(a)

    for a in grant_list:
        total_sql_obj.append(a)

    return total_sql_obj

# Add grants to the schema/role
def ensure_grants(module, conn, schema, wanted_grants_list, object_privs, directory_privs, grants_mode, container):
    global changed
    add_sql = ''
    remove_sql = ''

    # If no privs are added, we set the 'wanted' lists to be empty.
    if wanted_grants_list is None or wanted_grants_list == ['']:
        wanted_grants_list = []
    if object_privs is None or object_privs == ['']:
        object_privs = []
    if directory_privs is None or directory_privs == ['']:
        directory_privs = []

    # This list will hold all grants the user currently has
    dir_privs = []
    obj_privs = []
    total_sql=[]
    total_current=[]

    dir_privs = get_dir_privs(conn, schema, directory_privs, grants_mode)
    for d in dir_privs:
        total_sql.append(d)

    obj_privs = get_obj_privs(conn, schema, object_privs, grants_mode)
    for o in obj_privs:
        total_sql.append(o)

    exceptions_list=['DBA']
    exceptions_priv=['UNLIMITED TABLESPACE']

    # Strip the list of unnecessary quotes etc
    wanted_grants_list = clean_list(wanted_grants_list)
    wanted_grants_list = [x.lower() for x in wanted_grants_list]
    wanted_grants_list_upper = [x.upper() for x in wanted_grants_list]
    schema = clean_string(schema)

    # Get the current role grants for the schema. If any are present, add them to the total
    curr_role_grants=get_current_role_grants(conn, schema)
    if any(curr_role_grants):
        total_current.extend(curr_role_grants)

    # Get the current sys privs for the schema. If any are present, add them to the total
    curr_sys_grants=get_current_sys_grants(conn, schema)
    if any(curr_sys_grants):
        total_current.extend(curr_sys_grants)

    # Get the difference between current grants and wanted grants
    grants_to_add=set(wanted_grants_list).difference(total_current)
    grants_to_remove=set(total_current).difference(wanted_grants_list)

    # Special case: If DBA is granted to a user, unlimited tablespace is also implicitly
    # granted -> on the next run, unlimited tablespace is removed from the user
    # since it is not part of the wanted grants.
    # The following removes 'unlimited tablespace' privilege from the grants_to_remove list, if DBA is also granted
    if any(x in exceptions_list for x in wanted_grants_list_upper):
        grants_to_remove = [x for x in grants_to_remove if x.upper() not in exceptions_priv]

    if grants_mode.lower() == 'enforce' and any(grants_to_remove):
        grants_to_remove = ','.join(grants_to_remove)
        grants_to_remove = clean_string(grants_to_remove)
        remove_sql += 'revoke %s from %s' % (grants_to_remove, schema)
        total_sql.append(remove_sql)

    if any(grants_to_add):
        grants_to_add = ','.join(grants_to_add)
        grants_to_add = clean_string(grants_to_add)
        add_sql += 'grant %s to %s' % (grants_to_add, schema)
        if container:
            add_sql += ' container=%s' % (container)
        total_sql.append(add_sql)

    if total_sql:
        ensure_grants_state_sql(conn, total_sql)
        module.exit_json(msg=total_sql, changed=changed)
    else:
        msg = 'Nothing to do'
        module.exit_json(msg=msg, changed=changed)


def ensure_grants_state_sql(cursor, total_sql):
    for a in total_sql:
        execute_sql(cursor, a, change=True)


def execute_sql(conn, sql, change=False):
    global changed
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            changed = bool(changed or change)
        except cx_Oracle.DatabaseError as exc:
            error, = exc.args
            msg = 'Something went wrong while executing sql - %s sql: %s' % (error.message, sql)
            raise ModuleExecutionException(msg)

# Remove grants to the schema
def remove_grants(module, conn, schema, remove_grants_list, state):
    sql = ''

    # This list will hold all grants/privs the user currently has
    total_current=[]

    # Strip the list of unnecessary quotes etc
    remove_grants_list = clean_list(remove_grants_list)
    schema = clean_string(schema)

    # Get the current role grants for the schema.
    # If any are present, add them to the total
    curr_role_grants = get_current_role_grants(conn, schema)
    if any(curr_role_grants):
        total_current.extend(curr_role_grants)

    # Get the current sys privs for the schema
    # If any are present, add them to the total
    curr_sys_grants = get_current_sys_grants(conn, schema)
    if any(curr_sys_grants):
        total_current.extend(curr_sys_grants)

    # Get the difference between current grants and wanted grants
    grants_to_remove = set(remove_grants_list).intersection(total_current)

    # If state=REMOVEALL is used, all grants/privs will be removed
    if state == 'REMOVEALL' and any(total_current):
        remove_all = ','.join(total_current)
        sql += 'revoke %s from %s' % (remove_all, schema)
        msg = 'All privileges/grants (%s) are removed from schema/role %s' % (remove_all, schema)
        ensure_grants_state_sql(conn, [sql])
        module.exit_json(msg=msg, changed=changed)

    # if there are differences, they will be removed.
    elif not any(grants_to_remove):
        module.exit_json(msg="The schema/role (%s) doesn\'t have the grant(s) you want to remove" % schema, changed=False)

    else:
        # Convert the list of grants to a string & clean it
        grants_to_remove = ','.join(grants_to_remove)
        grants_to_remove = clean_string(grants_to_remove)
        sql += 'revoke %s from %s' % (grants_to_remove, schema)
        if grants_to_remove:
            ensure_grants_state_sql(conn, [sql])
            msg = 'The grant(s) (%s) successfully removed from the schema/role %s' % (grants_to_remove, schema)
            module.exit_json(msg=msg, changed=changed)
        else:
            msg = 'Nothing to do'
            module.exit_json(msg=msg, changed=changed)



# Get the current role/sys grants
def get_current_role_grants(conn, schema):
    curr_role_grants=[]
    with conn.cursor() as cursor:
        sql = 'select granted_role from dba_role_privs where grantee = upper(\'%s\') '% schema
        try:
            cursor.execute(sql)
            result = cursor.fetchall()
        except cx_Oracle.DatabaseError as exc:
            error, = exc.args
            msg = error.message+ 'sql: ' + sql
            raise ModuleExecutionException(msg)
        for item in result:
            curr_role_grants.append(item[0].lower())

    with conn.cursor() as cursor:
        dict_cursor = dictcur(cursor)
        sql = 'select * from v$pwfile_users where USERNAME = upper(\'%s\')' % schema
        try:
            dict_cursor.execute(sql)
            result = dict_cursor.fetchone()
            if result:
                for role in ['SYSDBA', 'SYSOPER', 'SYSASM', 'SYSBACKUP', 'SYSDG', 'SYSKM']:
                    if role in result and result[role] == 'TRUE':
                        curr_role_grants.append(role.lower())

        except cx_Oracle.DatabaseError as exc:
            error, = exc.args
            msg = error.message + 'sql: ' + sql
            raise ModuleExecutionException(msg)

    return curr_role_grants

# Get the current sys grants
def get_current_sys_grants(conn, schema):
    curr_sys_grants=[]

    with conn.cursor() as cursor:
        sql = 'select privilege from dba_sys_privs where grantee = upper(\'%s\') ' % schema
        try:
            cursor.execute(sql)
            result = cursor.fetchall()
        except cx_Oracle.DatabaseError as exc:
            error, = exc.args
            msg = error.message+ 'sql: ' + sql
            raise ModuleExecutionException(msg)

    for item in result:
        curr_sys_grants.append(item[0].lower())

    return curr_sys_grants


def execute_sql_get(conn, sql):
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            result = (cursor.fetchall())
            return result
        except cx_Oracle.DatabaseError as exc:
            error, = exc.args
            msg = 'Something went wrong while executing sql_get - %s sql: %s' % (error.message, sql)
            raise ModuleExecutionException(msg)


def main():
    global changed
    module = AnsibleModule(
        argument_spec = dict(
            oracle_home   = dict(required=False, aliases=['oh']),
            hostname      = dict(default='localhost'),
            port          = dict(default=1521, type="int"),
            service_name  = dict(required=False),
            user          = dict(required=False),
            password      = dict(required=False, no_log=True),
            mode          = dict(default='normal', choices=["normal","sysdba"]),
            schema        = dict(default=None),
            role          = dict(default=None),
            grants        = dict(default=None, type="list"),
            object_privs  = dict(default=None, type="list",aliases=['objprivs']),
            directory_privs = dict(default=None, type="list",aliases=['dirprivs']),
            grants_mode   = dict(default="append", choices=["append", "enforce"],aliases=['privs_mode']),
            container     = dict(default=None),
            state         = dict(default="present", choices=["present", "absent", "REMOVEALL"])

        ),
        mutually_exclusive=[['schema', 'role']],
        required_one_of=[['schema', 'role']]
    )

    schema = module.params["schema"]
    role = module.params["role"]
    grants = module.params["grants"]
    object_privs = module.params["object_privs"]
    directory_privs = module.params["directory_privs"]
    grants_mode = module.params["grants_mode"]
    container = module.params["container"]
    state = module.params["state"]

    if not cx_oracle_exists:
        module.fail_json(msg="The cx_Oracle module is required. 'pip install cx_Oracle' should do the trick. If cx_Oracle is installed, make sure ORACLE_HOME is set")

    try:
        conn = oracle_connect(module)

        if state == 'present' and schema:
            if check_user_exists(conn, schema):
                ensure_grants(module, conn, schema, grants, object_privs, directory_privs, grants_mode, container)
            else:
                msg = 'Schema %s doesn\'t exist' % (schema)
                module.fail_json(msg=msg, changed=False)

        elif state == 'present' and role:
            if check_role_exists(conn, role):
                ensure_grants(module, conn, role, grants, object_privs,directory_privs, grants_mode, container)
            else:
                msg = 'Role %s doesn\'t exist' % (role)
                module.fail_json(msg=msg, changed=False)

        elif state in ['absent', 'REMOVEALL'] and schema:
            if check_user_exists(conn, schema):
                remove_grants(module, conn, schema, grants, state)
            else:
                module.exit_json(msg='The schema (%s) doesn\'t exist' % schema, changed=False)

        elif state in ['absent', 'REMOVEALL'] and role:
            if check_role_exists(conn, role):
                remove_grants(conn, role, grants, state)
            else:
                module.exit_json(msg='The role (%s) doesn\'t exist' % role, changed=False)

        module.fail_json(msg='Unknown object', changed=False)
    except ModuleExecutionException as e:
        module.fail_json(msg=e.message, changed=changed)


from ansible.module_utils.basic import *

# In thise we do import from local project project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No colletions are used
try:
    from ansible.module_utils.oracle_utils import oracle_connect
    from ansible.module_utils.oracle_utils import dictcur
except:
    pass

# In thise we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracle_connect
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import dictcur
except:
    pass


if __name__ == '__main__':
    main()

