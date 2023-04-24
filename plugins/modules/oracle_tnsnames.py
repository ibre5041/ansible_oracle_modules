#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_tnsnames
short_description: Manipulate Oracle's tnsnames.ora and other .ora files
description:
    - Manipulate Oracle's tnsnames.ora and other .ora files
    - Must be run on a remote host
version_added: "3.0.1"
options:
    path:
        description:
        - location of .ora file
        required: true
    backup:
        description:
        - Create a backup file including the timestamp information so you can get the original file back if you somehow clobbered it incorrectly.
        type: bool
        default: no

notes:
    - Each stanze is written on single line
    - Comments are not supported (yet)
author: ibre5041@ibrezina.net
'''

EXAMPLES = '''
---
- hosts: localhost
  vars:
    oracle_env:
      ORACLE_HOME: /u01/app/grid/product/12.1.0.2/grid
  tasks:
    - name: Modify tnsnames.ora
      oracle_tnsnames:
        path: "{{ oracle_env.ORACLE_HOME }}/network/admin/tnsnames.ora"
'''

try:
    from ansible.module_utils.dotora import *
except:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.dotora import *

from ansible.module_utils.basic import *

import sys
import os
import getopt
import tempfile
import unittest

def write_changes(module, content, dest):
    tmpfd, tmpfile = tempfile.mkstemp(dir=module.tmpdir)
    with os.fdopen(tmpfd, 'wb') as f:
        f.write(to_bytes(content))

    module.atomic_move(tmpfile,
                       to_native(os.path.realpath(to_bytes(dest, errors='surrogate_or_strict')), errors='surrogate_or_strict'),
                       unsafe_writes=True) #


# Ansible code
def main():
    global module
    msg = ['']
    module = AnsibleModule(
        argument_spec = dict(
            path        = dict(required=True),
            follow      = dict(default=True, required=False),
            backup      = dict(type='bool', default=False), # inherited from add_file_common_args
            state       = dict(default="present", choices=["present", "absent"]),
            alias       = dict(required=False),
            aliases     = dict(required=False, type="list"),
            whole_value = dict(required=False),
            cs_simple   = dict(required=False),
            cs_dg       = dict(required=False),
            attribute_path  = dict(required=False),
            attribute_value = dict(required=False),
        ),
        #add_file_common_args=True,
        supports_check_mode=True,
        mutually_exclusive=[['alias', 'aliases'],['whole_value', 'cs_simple', 'cs_dg', 'attribute_path']]
    )
    
    #if module._verbosity >= 3:
    #    module.exit_json(changed=True, debug=module.params)

    whole_value     = module.params['whole_value']
    cs_simple       = module.params['cs_simple']
    cs_dg           = module.params['cs_dg']
    attribute_value = module.params['attribute_value']
    
    # Preparation
    facts = {}

    filename = module.params["path"]

    if module.params["follow"]:
        while os.path.islink(filename):
            filename = os.readlink(filename)

    with open(filename, "r") as file:
        old_content = file.read()
        
    orafile = DotOraFile(filename)

    if module.params['alias'] and module.params['whole_value']:
        orafile.upsertalias(module.params['alias'], module.params['whole_value'])
        
    if module.params['alias']:
        alias = module.params['alias']
        try:
            param = next(p for p in orafile.params if p.name.casefold() == alias.casefold())
            facts.update({alias: str(param.valuesstr())})
        except StopIteration:
            facts.update({alias: None})


    if module.params['aliases']:
        for alias in module.params['aliases']:
            try:
                param = next(p for p in orafile.params if p.name.casefold() == alias.casefold())
                facts.update({alias: str(param.valuesstr())})
            except StopIteration:
                facts.update({alias: None})

    new_content = str(orafile)
    changed = bool((old_content != new_content) and (whole_value or attribute_value or cs_simple or cs_dg))
    if changed:
        if module.params['backup']:
            backup_file = module.backup_local(filename)
        write_changes(module, new_content, filename)
        
    # Output
    module.exit_json(msg=", ".join(msg), changed=changed, ansible_facts=facts)


if __name__ == '__main__':
    main()
