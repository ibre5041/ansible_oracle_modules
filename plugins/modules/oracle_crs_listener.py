#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
---
module: oracle_crs_resource
short_description: Manage CRS/HAS resources type listener
description:
  - Manage CRS/HAS Listener resources
version_added: "3.1.7.0"
options:
  name:
    description:
      - "<lsnr_name>          Listener name (default name is LISTENER)"
    required: false
    default: LISTENER
  state:
    description:
      - Resource state
    choices: ['present', 'absent', 'started', 'stopped', 'restarted']
  enabled:
    description:
      - Enables the listener
    type: bool
    default: true
  oraclehome:
    description:
      - "<path> Oracle home path (default value is CRS_HOME)"
    required: false      
    default: CRS_HOME      
  skip:
    description:
      - Skip the checking of ports
    required: false
    type: bool
  endpoints:
    description:
      - "Comma separated TCP ports or listener endpoints"
      - "[TCP:]<port>[, ...][/IPC:<key>][/NMP:<pipe_name>][/TCPS:<s_port>][/SDP:<port>][/EXADIRECT:<port>]"
    required: false
notes:
  - Should be executed with privileges of Oracle CRS installation owner
author: Ivan Brezina
'''

EXAMPLES = '''
- name: Register listener ASM_LISTENER
  oracle_crs_listener:
    name: ASM_LISTENER
    endpoints: TCP:1522
    enabled: true

- name: Restart listener ASM_LISTENER
  oracle_crs_resource:
    name: ASM_LISTENER
    endpoints: TCP:1521
    state: restarted
'''

import os
from ansible.module_utils.basic import *

# In these we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
# try:
#    from ansible.module_utils.oracle_homes import oracle_homes
# except:
#    pass

# In these we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_homes import *
except:
    pass


def get_change(change_set, change):
    try:
        return next(v for (a, v) in change_set if a == change)
    except StopIteration:
        return None


def crs_config(resource_type, resource_name, module, ohomes):
    if resource_type == 'asm':
        dfilter = '(TYPE = ora.asm.type)'
    elif resource_type == 'db':
        dfilter = '(TYPE = ora.database.type)'
    elif resource_type == 'listener':
        dfilter = '(TYPE = ora.listener.type)'
    elif resource_type == 'service':
        dfilter = '(TYPE = ora.service.type)'
    else:
        module.fail_json(msg='Unknown resource type: {}'.format(resource_type), changed=False)

    command = [ohomes.crsctl, 'stat', 'res', '-p', '-w', dfilter]
    (rc, stdout, stderr) = module.run_command(command)

    if rc or stderr:
        module.fail_json(msg='Failed command: crsctl stat res -p, {}'.format(stderr), changed=False)

    name = None
    retval = dict()
    resource = dict()
    for line in stdout.splitlines():
        try:
            (key, value) = line.split('=', 1)
            if value:
                resource.update({key: value})
            if key == 'NAME':
                if value.startswith('ora.'):
                    name = value[len('ora.'):].split('.')[0].lower()
                else:
                    name = value.split('.')[0].lower()
        except ValueError as e:
            retval[name] = resource
            resource = dict()
    return retval



def configure_listener(config, module, ohomes):
    resource_name = module.params["name"].lower()
    try:
        curent_resource = config[resource_name]
    except KeyError as e:
        curent_resource = set()

    state = module.params["state"]

    wanted_set = set()
    for pname in ['oraclehome', 'endpoints']:
        param = module.params[pname]
        if param:
            wanted_set.add((pname, param))

    current_set = set()
    if curent_resource and 'ORACLE_HOME' in config[resource_name]:
        current_set.add(('oraclehome', config[resource_name]['ORACLE_HOME']))

    if curent_resource and 'ENDPOINTS' in config[resource_name]:
        current_set.add(('endpoints', config[resource_name]['ENDPOINTS']))

    apply = False
    changes = wanted_set.difference(current_set)
    srvctl = [os.path.join(ohomes.crs_home, "bin", "srvctl")]
    if (not curent_resource) and state == 'present':
        srvctl.extend(['add', 'listener', '-l', resource_name])
        if module.params['skip']:
            srvctl.append('-skip')
        apply = True
    elif curent_resource and state == 'present':
        srvctl.extend(['modify', 'listener', '-l', resource_name])
    elif curent_resource and state == 'absent':
        srvctl.extend(['remove', 'listener', '-l', resource_name])
        apply = True        
    elif (not curent_resource) and state == 'absent':
        module.exit_json(msg='Listener resource is already absent', command=[], changed=False)
    else:
        module.fail_json(msg='Unsupported state for Listener resource: {}'.format(state), changed=False)

    for change in changes:
        (param, value) = change
        srvctl.extend(['-' + param, value])
        apply = True        

    if not changes and not apply:
        module.exit_json(msg='Listener resource is already in desired state', command=[], changed=False)

    (rc, stdout, stderr) = module.run_command(srvctl)
    if rc or stderr:
        module.fail_json(msg='srvctl failed: {}'.format(stderr), command=[' '.join(srvctl)], changed=True)
    module.exit_json(msg='Listener resource reconfigured', command=[' '.join(srvctl)], changed=True)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(required=True),
            state=dict(default="present", choices=["present", "absent", "started", "stopped", "restarted"]),
            enabled=dict(default=True, required=False, type='bool'),
            # LISTENER parameters
            oraclehome=dict(default='%CRS_HOME%', required=False),
            skip=dict(default=False, required=False, type='bool'),
            endpoints=dict(required=False),
        ),
        supports_check_mode=True,
    )

    ohomes = oracle_homes()
    ohomes.list_crs_instances()
    ohomes.list_processes()
    ohomes.parse_oratab()

    if not ohomes.oracle_gi_managed:
        module.fail_json(msg="Oracle CRS/HAS was not detected", changed=False)

    resource_name = module.params["name"]

    config = crs_config(resource_type, resource_name, module, ohomes)
    configure_listener(config, module, ohomes)        
    module.exit_json(msg="Unhandled exit", changed=False)


if __name__ == '__main__':
    main()
