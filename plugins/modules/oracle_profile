#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_profile
short_description: Manage profiles in an Oracle database
description:
    - Manage profiles in an Oracle database
version_added: "3.0.0"
options:
    name:
        description:
            - The name of the profile
        required: true
        default: None
        aliases: ['profile']
    state:
        description:
            - The intended state of the profile.
        default: present
        choices: ['present','absent']
    attribute_name:
        description:
            - The attribute name (e.g PASSWORD_REUSE_TIME)
        default: None
        aliases: ['an']
    attribute_value:
        description:
            - The attribute value (e.g 10)
        default: None
        aliases: ['av']
    username:
        description:
            - The DB username
        required: false
        default: sys
        aliases: ['un']
    password:
        description:
            - The password for the DB user
        required: false
        default: None
        aliases: ['pw']
    service_name:
        description:
            - The profile_name to connect to the database.
        required: false
        aliases: ['sn']
    hostname:
        description:
            - The host of the database if using dbms_profile
        required: false
        default: localhost
        aliases: ['host']
    port:
        description:
            - The listener port to connect to the database if using dbms_profile
        required: false
        default: 1521
    oracle_home:
        description:
            - The DB ORACLE_HOME
        required: false
        default: None
        aliases: ['oh']


notes:
    - cx_Oracle needs to be installed
requirements: [ "cx_Oracle" ]
author: Mikael Sandström, oravirt@gmail.com, @oravirt
'''

EXAMPLES = '''
# Create a profile
- hosts: dbserver
  vars:
      oracle_home: /u01/app/oracle/12.2.0.1/db1
      hostname: "{{ inventory_hostname }}"
      service_name: orclpdb
      user: system
      password: Oracle_123
      oracle_env:
             ORACLE_HOME: "{{ oracle_home }}"
             LD_LIBRARY_PATH: "{{ oracle_home }}/lib"
      profiles:
               - name: profile1
                 attribute_name:
                            - password_reuse_max
                            - password_reuse_time
                            - sessions_per_user
                 attribute_value:
                            - 6
                            - 20
                            - 5
                 state: present
  tasks:
  - name: Manage profiles
    oracle_profile:
            name={{ item.name }}
            attribute_name={{ item.attribute_name}}
            attribute_value={{ item.attribute_value}}
            state={{ item.state }}
            hostname={{ hostname }}
            service_name={{ service_name }}
            user={{ user }}
            password={{ password }}
    environment: "{{oracle_env}}"
    with_items: "{{ profiles }}"

'''
import os
from ansible.module_utils.basic import AnsibleModule

# In thise we do import from local project project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No colletions are used
try:
    from ansible.module_utils.oracle_utils import oracle_connect
except:
    pass

# In thise we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracle_connect
except:
    pass


try:
    import cx_Oracle
except ImportError:
    cx_oracle_exists = False
else:
    cx_oracle_exists = True

changed = False

# define Python user-defined exceptions
class ModuleExecutionException(Exception):
    "Raised when execution of some SQL fails"
    pass

    def __init__(self, message=""):
        self.message = message
        super().__init__(self.message)


# Check if the profile exists
def check_profile_exists(conn, name):
    with conn.cursor() as cursor:
        sql = "select count(*) from dba_profiles where upper(profile) = '%s'" % (name.upper())
        try:
            cursor.execute(sql)
            result = cursor.fetchone()[0]
            return bool(result)
        except cx_Oracle.DatabaseError as exc:
            error, = exc.args
            msg = error.message + 'sql: ' + sql
            raise ModuleExecutionException(msg)


def create_profile(module, conn, name, attribute_name, attribute_value):
    add_attr = False
    if not any(x == 'None' for x in attribute_name):
        add_attr = True
    if not any(x == None for x in attribute_name):
        add_attr = True

    if add_attr:
        attributes = ' '.join(['' + str(n) + ' ' + str(v) + '' for n, v in zip(attribute_name,attribute_value)])

    sql = 'create profile %s limit ' % name
    if add_attr:
        sql += ' %s' % (attributes.lower())

    execute_sql(conn, sql, change=True)
    msg = 'Successfully created profile %s ' % name
    module.exit_json(msg=msg, changed=changed)


def remove_profile(module, conn, name):
    global changed
    dropsql = 'drop profile %s' % (name)
    execute_sql(conn, dropsql, changed=True)
    msg = 'Profile %s successfully removed' % name
    module.exit_json(msg=msg, changed=changed)


def ensure_profile_state(module, conn, name, state, attribute_name, attribute_value):
    global changed
    total_sql = []

    # Deal with attribute differences
    if attribute_name and attribute_value:
        # Make sure attributes are lower case
        attribute_name = [x.lower() for x in attribute_name]
        attribute_value = [str(y).lower() for y in attribute_value]
        wanted_attributes = set(zip(attribute_name, attribute_value))

        # Check the current attributes
        attribute_names_ = ','.join(["'{}'".format(x) for (x, _,) in wanted_attributes])
        if attribute_names_:
            current_attributes = get_current_attributes(conn, name, attribute_names_)
            current_attributes = set(current_attributes)

            changes = wanted_attributes.difference(current_attributes)
            for i in changes:
                total_sql.append("alter profile %s limit %s %s " % (name, i[0], i[1]))

    if total_sql:
        ensure_profile_state_sql(conn, total_sql)
        msg = 'profile %s has been put in the intended state' % name
        module.exit_json(msg=msg, changed=changed)
    else:
        msg = 'Nothing to do'
        module.exit_json(msg=msg, changed=False)


def ensure_profile_state_sql(conn, total_sql):
    for sql in total_sql:
        execute_sql(conn, sql)


def get_current_attributes(conn, name, attribute_names_):
    sql =  """
    select lower(resource_name),lower(limit)
    from dba_profiles
    where lower(profile) = '%s' 
    and lower(resource_name) in (%s) """ % (name.lower(), attribute_names_.lower())
    result = execute_sql_get(conn, sql)
    return result


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


def main():
    global changed
    module = AnsibleModule(
        argument_spec = dict(
            user                = dict(required=False, aliases=['un', 'username']),
            password            = dict(required=False, no_log=True, aliases=['pw']),
            mode                = dict(default='normal', choices=["normal", "sysdba"]),
            hostname            = dict(required=False, default='localhost', aliases=['host']),
            port                = dict(required=False, default=1521, type='int'),
            service_name        = dict(required=False, aliases=['sn']),
            oracle_home         = dict(required=False, aliases=['oh']),
            name                = dict(required=True, aliases=['profile']),
            attribute_name      = dict(required=True, type='list', aliases=['an']),
            attribute_value     = dict(required=True, type='list', aliases=['av']),
            state               = dict(default="present", choices=["present", "absent"]),
        ),
    )

    name                = module.params["name"]
    attribute_name      = module.params["attribute_name"]
    attribute_value     = module.params["attribute_value"]
    state               = module.params["state"]

    if not cx_oracle_exists:
        msg = "The cx_Oracle module is required. 'pip install cx_Oracle' should do the trick. If cx_Oracle is installed, make sure ORACLE_HOME & LD_LIBRARY_PATH is set"
        module.fail_json(msg=msg)

    try:
        conn = oracle_connect(module)
        if state == 'present':
            if not check_profile_exists(conn, name):
                create_profile(module, conn, name, attribute_name, attribute_value)
            else:
                ensure_profile_state(module, conn, name, state, attribute_name, attribute_value)
        elif state == 'absent' and attribute_name:
            module.fail_json(msg='Attributes are only allowed when state=present', changed=False)
        elif state == 'absent':
            if check_profile_exists(conn, name):
                remove_profile(module, conn, name)
            else:
                msg = 'Profile %s doesn\'t exist' % (name)
                module.exit_json(msg=msg, changed=False)
        module.exit_json(msg="Unhandled exit", changed=False)
    except ModuleExecutionException as e:
        module.fail_json(msg=e.message, changed=changed)


if __name__ == '__main__':
    main()
