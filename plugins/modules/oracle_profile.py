#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_profile
short_description: Manage profiles in an Oracle database
description:
  - Manage profiles in an Oracle database
  - See connection parameters for oracle_ping  
version_added: "3.0.0"
options:
  name:
    description:  The name of the profile
    required: true
    default: None
    aliases: ['profile']
  state:
    description: The intended state of the profile.
    default: present
    choices: ['present','absent']
  attribute_name:
    description: The attribute name (e.g PASSWORD_REUSE_TIME)
    default: None
    aliases: ['an']
  attribute_value:
    description: The attribute value (e.g 10)
    default: None
    aliases: ['av']
notes:
    - oracledb needs to be installed
requirements: [ "oracledb" ]
author:
  - Mikael Sandström, oravirt@gmail.com, @oravirt
  - Ivan Brezina
'''

EXAMPLES = '''
- name: Create profile:
  oracle_profile:
    mode: sysdba
    profile: TEST_PROFILE
    attributes:
      PASSWORD_REUSE_MAX: "10"

- name: Alter existing profile
  oracle_profile:  
    mode: sysdba
    profile: TEST_PROFILE
    attributes:
      PASSWORD_LIFE_TIME: "365"
  register: _test_profile

- debug:
    msg: "{{ _test_profile.profile }}"

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


# Check if the profile exists
def check_profile_exists(conn, profile_name):
    sql = "select resource_name, limit from dba_profiles where upper(profile) = :profile_name"
    result = conn.execute_select(sql, {'profile_name': profile_name.upper()}, fetchone=False)
    return set(result)


def create_profile(conn, module):
    profile_name = module.params['profile']
    attribute_name = module.params['attribute_name']
    attribute_value = module.params['attribute_value']
    attributes = module.params['attributes']

    if attributes:
        keys = [x.upper() for x in attributes.keys()]
        values = [x.upper() for x in attributes.values()]
        wanted_set = list(zip(keys, values))
    else:
        wanted_set = list(zip(attribute_name, attribute_value))

    sql = 'create profile %s limit ' % profile_name
    for limit in wanted_set:
        sql += ' %s %s' % (limit[0], limit[1])

    conn.execute_ddl(sql)

    profile = check_profile_exists(conn, profile_name)
    msg = 'Successfully created profile %s ' % profile_name
    module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls, profile=dict(profile))


def remove_profile(conn, module):
    profile_name = module.params['profile']
    dropsql = 'drop profile %s' % profile_name
    conn.execute_ddl(dropsql)
    msg = 'Profile %s successfully removed' % profile_name
    module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls, profile=dict())


def ensure_profile_state(conn, module, current_set):
    profile_name = module.params['profile']
    attribute_name = module.params['attribute_name']
    attribute_value = module.params['attribute_value']
    attributes = module.params['attributes']

    if attributes:
        keys = [x.upper() for x in attributes.keys()]
        values = [str(x).upper() for x in attributes.values()]
        wanted_set = set(zip(keys, values))
    else:
        # Deal with attribute differences
        # Make sure attributes are upper case
        attribute_name = [x.upper() for x in attribute_name]
        attribute_value = [str(y).upper() for y in attribute_value]
        wanted_set = set(zip(attribute_name, attribute_value))

    sql = "alter profile %s limit " % profile_name
    changes = wanted_set.difference(current_set)

    if not changes:
        profile = check_profile_exists(conn, profile_name)
        module.exit_json(msg='Nothing to do', changed=conn.changed, ddls=conn.ddls, profile=dict(profile))

    # Process changed attributes
    for change in changes:
        sql += ' %s %s' % (change[0], change[1])

    conn.execute_ddl(sql)
    msg = 'Successfully altered the profile (%s) / %s' % (profile_name, str(changes))
    profile = check_profile_exists(conn, profile_name)
    module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls, profile=dict(profile))


def main():
    module = AnsibleModule(
        argument_spec = dict(
            user          = dict(required=False, aliases=['un', 'username']),
            password      = dict(required=False, no_log=True, aliases=['pw']),
            mode          = dict(default='normal', choices=["normal", "sysdba"]),
            hostname      = dict(required=False, default='localhost', aliases=['host']),
            port          = dict(required=False, default=1521, type='int'),
            service_name  = dict(required=False, aliases=['sn']),
            oracle_home   = dict(required=False, aliases=['oh']),
            
            profile             = dict(required=True, aliases=['name']),
            attribute_name      = dict(required=False, default=[], type='list', aliases=['an']),
            attribute_value     = dict(required=False, default=[], type='list', aliases=['av']),
            attributes          = dict(required=False, default={}, type='dict'),
            state               = dict(default="present", choices=["present", "absent"]),
        ),
        mutually_exclusive=['attribute_name', 'attributes'],
        required_together=[['user', 'password'], ['attribute_name, attribute_value']],
        supports_check_mode=True
    )

    attribute_name = module.params["attribute_name"]
    attribute_value = module.params["attribute_value"]
    if attribute_name and attribute_value:
        if len(attribute_name) != len(attribute_value):
            module.fail_json(msg="attribute_name and attribute_value must have same lengths", changed=False)

    name = module.params["profile"]
    state = module.params["state"]

    oc = oracleConnection(module)

    profile = check_profile_exists(oc, name)
    if state == 'present':
        if profile:
            ensure_profile_state(oc, module, profile)
        else:
            create_profile(oc, module)
    elif state == 'absent':
        if profile:
            remove_profile(oc, module)
        else:
            module.exit_json(msg="Profile %s doesn't exist" % name, changed=False, profile=dict())
    module.exit_json(msg="Unhandled exit", changed=False)


from ansible.module_utils.basic import *

# In these we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
#try:
#    from ansible.module_utils.oracle_utils import oracleConnection
#except:
#    pass

# In these we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracleConnection
except:
    pass


if __name__ == '__main__':
    main()
