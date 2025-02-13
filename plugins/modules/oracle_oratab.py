#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_oratab
short_description: Reads oratab to ansible_facts
description:
  - "Reads SID and ORACLE_HOME path from oratab, crs and running processes to ansible_facts"
  - "Should be able to detect all ORACLE_HOMEs on a server crs, restart, database, client, golden gate"
  - "More datailed example is here:"
  - "https://github.com/ibre5041/ansible_oracle_modules_example/blob/main/oracle_oratab.yml"
version_added: "3.0.0"
options:
  writable_only:
    description: Return only databases openned READ WRITE
    required: false
    default: false
  asm_only:
    description: Return only ASM instances
    required: false
    default: false
  running_only:
    description: Return only instances which are running
    required: false
    default: false
  open_only:
    description: Return only databases which are OPEN
    required: false
    default: false
notes:
  - Has to run either as root or oracle db owner
requirements:
  - xml.dom
author: 
  - Ivan Brezina
'''

EXAMPLES = '''

vars:
# List of affected databases, this variable overrides default: sid_list.oracle_list.keys()
# db_list | default(sid_list.oracle_list.keys())
# Comment out this variable to apply playbook onto all databases
   db_list: [ TEST ]

tasks:
  - oracle_oratab:
      writable_only: True
    register: sid_list

  - name: Print Facts
    debug:
      var: sid_list

  - oracle_role:
      mode: sysdba
      role: SOME_ROLE
    environment:
      ORACLE_HOME: "{{ sid_list.oracle_list[item].ORACLE_HOME }}"
      ORACLE_SID:  "{{ sid_list.oracle_list[item].ORACLE_SID }}"
    loop: "{{ db_list | default(sid_list.oracle_list.keys())}}"

- name: Read oratab, detect all ORACLE_HOMEs and writable database
  oracle_oratab:
    writable_only: True
  register: sid_list

- debug:
    var: sid_list

# More detailed example is here: 
# https://github.com/ibre5041/ansible_oracle_modules_example/blob/main/oracle_oratab.yml
# 
'''

import fcntl
import os
import pwd
import subprocess
import re
import glob
import subprocess
import socket
from pwd import getpwuid
from xml.dom import minidom

from ansible.module_utils.basic import AnsibleModule

# In these we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
#try:
#    from ansible.module_utils.oracle_homes import OracleHomes
#except:
#    pass

# In these we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_homes import OracleHomes
except:
    pass

# Ansible code
def main():
    oracle_list = []
    module = AnsibleModule(
        argument_spec = dict(
            asm_only = dict(default=False, type="bool"),            
            running_only = dict(default=False, type="bool"),
            open_only = dict(default=False, type="bool"),
            writable_only = dict(default=False, type="bool"),
            homes = dict(default=None, choices=[None, 'all', 'client', 'server', 'crs', 'gateway']),
            facts_item = dict()
         ),
        supports_check_mode=True
    )
    asm_only = module.params['asm_only']    
    running_only = module.params['running_only']
    open_only = module.params['open_only']
    writable_only = module.params['writable_only']
    homes = module.params['homes']
    
    h = OracleHomes(module)
    h.list_crs_instances()
    h.list_processes()
    h.parse_oratab()

    for sid in list(h.facts_item):
        try:
            sqlplus_path = os.path.join(h.facts_item[sid]['ORACLE_HOME'], 'bin', 'oracle')
            oracle_owner = getpwuid(os.stat(sqlplus_path).st_uid).pw_name
            h.facts_item[sid]['owner'] = oracle_owner
        except:
            pass

        if h.facts_item[sid]["running"]:
            status = h.query_db_status(oracle_owner = h.facts_item[sid]['owner']
                                       , oracle_home = h.facts_item[sid]['ORACLE_HOME']
                                       , oracle_sid = h.facts_item[sid]['ORACLE_SID'])
            h.facts_item[sid]['status'] = status
        else:
            h.facts_item[sid]['status'] = ['DOWN']
        
    if running_only:
        for sid in list(h.facts_item):
            if not h.facts_item[sid]["running"]:
                del h.facts_item[sid]
                module.warn('ORACLE_SID: {} is down'.format(sid))

    if asm_only:
        for sid in list(h.facts_item):
            if 'ASM' not in h.facts_item[sid]["status"]:
                del h.facts_item[sid]
                module.warn('ORACLE_SID: {} is not ASM'.format(sid))
                
    if running_only:
        for sid in list(h.facts_item):
            if not h.facts_item[sid]["running"]:
                del h.facts_item[sid]
                module.warn('ORACLE_SID: {} is down'.format(sid))

    if open_only:
        for sid in list(h.facts_item):
            if 'OPEN' not in h.facts_item[sid]["status"]:
                del h.facts_item[sid]
                module.warn('ORACLE_SID: {} is not open'.format(sid))

    if writable_only:
        for sid in list(h.facts_item):
            if 'READ WRITE' not in h.facts_item[sid]["status"]:
                del h.facts_item[sid]
                module.warn('ORACLE_SID: {} is not open'.format(sid))
                
    #module.warn('uid {}'.format(os.getuid()))

    if homes:
        for home in list(h.homes):
            if homes == 'all':
                continue
            elif homes == 'client' and h.homes[home]['home_type'] != 'client':
                del h.homes[home]
            elif homes == 'server' and h.homes[home]['home_type'] != 'server':
                del h.homes[home]
            elif homes == 'crs' and h.homes[home]['home_type'] != 'crs':
                del h.homes[home]
            elif homes == 'gateway' and h.homes[home]['home_type'] != 'gateway':
                del h.homes[home]

    module.exit_json(oracle_list=h.facts_item, OracleHomes=h.homes, changed=False)


if __name__ == '__main__':
    main()
