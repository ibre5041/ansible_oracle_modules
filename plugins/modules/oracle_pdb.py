#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_pdb
short_description: Manage pluggable databases in Oracle
description:
    - Manage pluggable databases in Oracle.
version_added: "3.0.0"
options:
    name:
        description:
            - The name of the pdb
        required: True
        default: None
    oracle_home:
        description:
            - The ORACLE_HOME to use
        required: False
        default: None
    sourcedb:
        description:
            - The container database which will house the pdb
        required: True
        default: None
        aliases: ['db']
    state:
        description:
            - The intended state of the pdb. 'status' will just show the status of the pdb
        default: present
        choices: ['present','absent', 'status']
    pdb_admin_username:
        description:
            - The username for the pdb admin user
        required: false
        default: pdb_admin
        aliases: ['un']
    pdb_admin_password:
        description:
            - The password for the pdb admin user
        required: false
        default: pdb_admin
        aliases: ['pw']
    datafile_dest:
        description:
            - The path where the datafiles will be placed
        required: false
        default: None
        aliases: ['dfd']
    unplug_dest:
        description:
            - The path where the 'unplug' xml-file will be placed. Also used when plugging in a pdb
        required: false
        default: None
        aliases: ['plug_dest','upd','pd']
    username:
        description:
            - The database username to connect to the database
        required: false
        default: None
        aliases: ['un']
    password:
        description:
            - The password to connect to the database
        required: false
        default: None
        aliases: ['pw']
    service_name:
        description:
            - The service_name to connect to the database
        required: false
        default: database_name
        aliases: ['sn']
    hostname:
        description:
            - The host of the database
        required: false
        default: localhost
        aliases: ['host']
    port:
        description:
            - The listener port to connect to the database
        required: false
        default: 1521

notes:
    - cx_Oracle needs to be installed
requirements: [ "cx_Oracle" ]
author: Mikael Sandström, oravirt@gmail.com, @oravirt
'''

EXAMPLES = '''
# Creates a pdb on a different filesystem
oracle_pdb: name=pdb1 sourcedb=cdb1 dfd=/u02/oradata/pdb1 state=present un=system pw=Oracle123 oracle_home=/u01/app/oracle/12.2.0.1/db

# Remove a pdb
oracle_pdb: name=pdb1 sourcedb=cdb1 state=absent un=system pw=Oracle123 oracle_home=/u01/app/oracle/12.2.0.1/db

# Check the status for a pdb
oracle_pdb: name=pdb1 sourcedb=cdb1 state=status un=system pw=Oracle123 oracle_home=/u01/app/oracle/12.2.0.1/db


# Unplug a pdb
oracle_pdb:
    name=pdb1
    sourcedb=cdb1
    unplug_dest=/tmp/unplugged-pdb.xml
    state=unplugged
    un=sys
    pw=Oracle123
    mode=sysdba
    sn=cdb1
    oracle_home=/u01/app/oracle/12.2.0.1/db1

# plug in a pdb
oracle_pdb:
    name=plug1
    sourcedb=cdb2
    plug_dest=/tmp/unplugged-pdb.xml
    state=present
    un=sys
    pw=Oracle123
    mode=sysdba
    sn=cdb1
    oracle_home=/u01/app/oracle/12.2.0.1/db2

'''
import os


# Check if the pdb exists
def check_pdb_exists(conn, pdb_name):
    sql = sql = 'select name, open_mode, restricted from v$pdbs where upper(name) = :pdb_name'
    result = conn.execute_select_to_dict(sql, {"pdb_name": pdb_name}, fetchone=True)

    if not result:
        return set()

    if not result['open_mode'].startswith('READ'):
        return set(result.items())

    _changed = conn.changed # Push current change state
    conn.execute_ddl('ALTER SESSION SET CONTAINER = %s' % pdb_name)
    conn.changed = _changed # Pop current change state. ALTER SESSION does not modify database

    sql = "select property_name, property_value" \
          " from database_properties " \
          " where property_name in ('DEFAULT_TBS_TYPE','DEFAULT_PERMANENT_TABLESPACE','DEFAULT_TEMP_TABLESPACE', 'DBTIMEZONE') " \
          " order by 1"
    prop = conn.execute_select(sql, None, fetchone=False)
    result.update(dict(prop))

    return set(result.items())


def unplug_pdb(conn, module):
    pdb_name = module.params['pdb_name']
    plug_file = module.params['plug_file'] # clone from XML
    run_sql = []
    close_sql = 'alter pluggable database %s close immediate instances=all' % pdb_name
    unplug_sql = "alter pluggable database %s unplug into '%s'" % (pdb_name, plug_file)
    drop_sql = 'drop pluggable database %s keep datafiles ' % pdb_name

    run_sql.append(close_sql)
    run_sql.append(unplug_sql)
    run_sql.append(drop_sql)
    for sql in run_sql:
        conn.execute_ddl(sql)
    msg = "Pluggable database %s successfully unplugged into '%s'" % (pdb_name, unplug_dest)
    module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)


def create_pdb(conn, module):
    pdb_name = module.params['pdb_name']
    plug_file = module.params['plug_file'] # clone from XML
    sourcedb = module.params['sourcedb'] # clone from DB
    pdb_admin_username = module.params['pdb_admin_username'] # clone form seed
    pdb_admin_password = module.params['pdb_admin_password']
    roles = module.params['roles']

    datafile_dest = module.params['datafile_dest']
    file_name_convert = module.params['file_name_convert']
    save_state = module.params['save_state']
    run_sql = []

    createsql = 'create pluggable database %s' % pdb_name
    #opensql = 'alter pluggable database %s open instances=all' % pdb_name

    if plug_file:
        # TODO: copy/nocopy tempfile reuse
        createsql += " using %s"
    elif sourcedb:
        # TODO: snapshot copy
        createsql += " from %s"
    elif pdb_admin_username:
        createsql += " admin user %s identified by \"%s\" " % (pdb_admin_username, pdb_admin_password)
    else:
        module.fail_json("Missing one parameter: [plug_file, sourcedb, pdb_admin_password]", changed=conn.changed, ddls=conn.ddls)

    if roles:
        createsql += ' roles = (%s)' % ','.join(roles)

    if file_name_convert:
        quoted = ','.join([ "'%s', '%s'" % (x[0], x[1]) for x in zip(file_name_convert.keys(), file_name_convert.values())])
        createsql += ' file_name_convert = (%s)' % quoted

    if datafile_dest:
        createsql += " create_file_dest = '%s'" % datafile_dest

    run_sql.append(createsql)

    for sql in run_sql:
        conn.execute_ddl(sql)

    # TODO: select a.name,b.state from v$pdbs a , dba_pdb_saved_states b where a.con_id = b.con_id;
    if save_state:
        sql = 'alter pluggable database %s save state instances=all' % pdb_name
        conn.execute_ddl(sql)


def remove_pdb(conn, module, current_state):
    pdb_name = module.params['pdb_name']
    run_sql = []
    close_sql = 'alter pluggable database %s close immediate instances=all' % pdb_name
    dropsql = 'drop pluggable database %s including datafiles' % pdb_name

    if dict(current_state)['open_mode'].startswith('READ'):
        run_sql.append(close_sql)
    run_sql.append(dropsql)
    for sql in run_sql:
        conn.execute_ddl(sql)
    msg = 'Pluggable database %s successfully removed' % pdb_name
    module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)


def ensure_pdb_state(conn, module, current_state):
    pdb_name = module.params['pdb_name']
    state = module.params['state']
    default_tablespace_type = module.params['default_tablespace_type']
    default_tablespace = module.params['default_tablespace']
    default_temp_tablespace = module.params['default_temp_tablespace']
    timezone = module.params['timezone']
    save_state = module.params['save_state']

    change_db_sql = []

    wanted_state = {}
    ensure_sql = 'alter pluggable database %s ' % pdb_name
    if state in ('present', 'open', 'read_write'):
        wanted_state.update({'open_mode': 'READ WRITE'})
        ensure_sql += ' open force'
    elif state == 'closed':
        wanted_state.update({'open_mode': 'CLOSED'})
        ensure_sql += ' close immediate'
    elif state == 'read_only':
        wanted_state.update({'open_mode': 'READ ONLY'})
        ensure_sql += 'open read only force'
    # elif state == 'restricted':
    #     wanted_state = [('read write', 'yes')]
    #     ensure_sql += 'open restricted force'

    if default_tablespace_type:
        wanted_state.update({'DEFAULT_TBS_TYPE': default_tablespace_type.upper()})

    if default_tablespace:
        wanted_state.update({'DEFAULT_PERMANENT_TABLESPACE': default_tablespace.upper()})

    if default_temp_tablespace:
        wanted_state.update({'DEFAULT_TEMP_TABLESPACE': default_temp_tablespace.upper()})

    if timezone:
        wanted_state.update({'DBTIMEZONE': timezone})

    changes = set(wanted_state.items()).difference(current_state)

    if 'open_mode' in dict(changes):
        change_db_sql.append(ensure_sql)

    if 'DEFAULT_TBS_TYPE' in dict(changes):
        sql = 'alter PLUGGABLE database %s set default %s tablespace' % (pdb_name, default_tablespace_type)
        change_db_sql.append(sql)

    if 'DEFAULT_PERMANENT_TABLESPACE' in dict(changes):
        sql = 'alter PLUGGABLE database %s default tablespace %s' % (pdb_name, default_tablespace)
        change_db_sql.append(sql)

    if 'DEFAULT_TEMP_TABLESPACE' in dict(changes):
        sql = 'alter PLUGGABLE database %s default temporary tablespace %s' % (pdb_name, default_temp_tablespace)
        change_db_sql.append(sql)

    if 'DBTIMEZONE' in dict(changes):
        sql = "alter PLUGGABLE database %s set time_zone = '%s'" % (pdb_name, timezone)
        change_db_sql.append(sql)

    if changes and save_state:
        sql = 'alter pluggable database %s save state instances=all' % pdb_name
        change_db_sql.append(sql)

    if not changes:
        if conn.changed:
            msg = 'Successfully created pluggable database %s' % pdb_name
            module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)
        msg = 'Pluggable database %s already in the intended state' % pdb_name
        module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)

    for sql in change_db_sql:
        conn.execute_ddl(sql)
    msg = 'Pluggable database %s has been put in the intended state: %s' % (pdb_name, state)
    module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)


def check_pdb_status(conn, module):
    sql = "select name, con_id, con_uid, open_mode,restricted" \
          " ,to_char(open_time,'HH24:MI:SS YYYY-MM-DD')" \
          " ,recovery_status " \
          " from v$pdbs where upper(name) = :pdb_name"
    result = conn.execute_select_to_dict(sql, {"pdb_name": module.params['pdb_name'].upper()}, fetchone=True)
    return result


def main():
    module = AnsibleModule(
        argument_spec = dict(
            user                   = dict(required=False, aliases=['un', 'username']),
            password               = dict(required=False, no_log=True, aliases=['pw']),
            mode                   = dict(default='normal', choices=["normal", "sysdba"]),
            hostname               = dict(required=False, default='localhost', aliases=['host']),
            port                   = dict(required=False, default=1521, type='int'),
            service_name           = dict(required=False, aliases=['sn']),
            oracle_home            = dict(required=False, aliases=['oh']),

            pdb_name               = dict(required=True, aliases=['pdb', 'name']),

            sourcedb               = dict(required=False, aliases=['db', 'container', 'cdb']),
            plug_file              = dict(required=False, aliases=['plug_file_xml']),
            pdb_admin_username     = dict(required=False, default='pdb_admin', aliases=['pdbadmun']),
            pdb_admin_password     = dict(required=False, no_log=True, default='pdb_admin', aliases=['pdbadmpw']),

            roles                  = dict(type='list', elements='str', default=[]),

            state                  = dict(default="present", choices=["absent", "present", "open", "closed", "read_only"]),

            save_state             = dict(default=True, type='bool'),
            datafile_dest          = dict(required=False, aliases=['dfd', 'create_file_dest']),
            #unplug_dest            = dict(required=False, aliases=['plug_dest', 'upd', 'pd']),
            file_name_convert      = dict(type='dict', required=False, aliases=['fnc']),
            service_name_convert   = dict(type='dict', required=False, aliases=['snc']),
            default_tablespace_type = dict(default='smallfile', choices=['smallfile', 'bigfile']),
            default_tablespace  = dict(required=False),
            default_temp_tablespace = dict(required=False),
            timezone            = dict(required=False)
        ),
        required_together=[['user', 'password'], ['pdb_admin_username', 'pdb_admin_password']],
        #mutually_exclusive=[['datafile_dest', 'file_name_convert']],
        mutually_exclusive=[['pdb_admin_username', 'clone_from', 'plug_file']],
        required_if=[('state', 'present', ('pdb_admin_username', 'pdb_admin_password'))],
        supports_check_mode=True
    )

    pdb_name = module.params["pdb_name"]
    state = module.params["state"]

    oc = oracleConnection(module)
    pdb = check_pdb_exists(oc, pdb_name)
    if state in ['present', 'closed', 'open', 'restricted', 'read_only', 'read_write']:
        if not pdb:
            create_pdb(oc, module)
            ensure_pdb_state(oc, module, pdb)
        else:
            ensure_pdb_state(oc, module, pdb)

    elif state == 'absent':
        if pdb:
            remove_pdb(oc, module, pdb)
        else:
            msg = "Pluggable database %s doesn't exist" % pdb_name
            module.exit_json(msg=msg, changed=False)

    elif state == 'unplugged':
        if pdb:
            unplug_pdb(oc, module)
        else:
            msg = "Pluggable database %s doesn't exist" % pdb_name
            module.exit_json(msg=msg, changed=False)

    elif state == 'status':
        if pdb:
            pdb = check_pdb_status(oc, module)
            msg = 'pdb name: %s, con_id: %s, con_uid: %s, open_mode: %s, restricted: %s,  open_time: %s' % \
                  () #  (a[0].lower(), a[1], a[2], a[3], a[4], a[5])
            module.exit_json(msg=msg, changed=False)
        else:
            msg = "Pluggable database %s doesn't exist" % pdb_name
            module.exit_json(msg=msg, changed=False)

    module.exit_json(msg="Unhandled exit", changed=False)


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


from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()