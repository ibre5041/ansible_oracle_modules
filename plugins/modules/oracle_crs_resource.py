#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_crs_resource
short_description: Manage CRS/HAS resources
description:
    - Manage CRS/HAS resources
    - ASM instance, Database and Listener resources are supported
version_added: "3.1.7.0"
options:
    name:
        description:
            - Name of the resource
            - '"asm" for ASM instance'
            - "db unique name for database"
        required: true
        default: None
    type:
        description:
            - Type of the resource
        required: true
        default: None
        choices: ['asm', 'db', listener']
    listener:
        description:
            - ASM instance LISTENER
            - "Use only with: type=asm"
        required: false
    spfile:
        description:
            - ASM instance SPFILE
            - "Use only with: type=asm or type=db"       
        required: false
    pwfile:
        description:
            - ASM instance password file
            - "Use only with: type=asm or type=asm
        required: false
    diskstring:
        description:
            - ASM instance parameter diskstring
            - "Use only with: type=asm"
        required: false
    db:
        description:
            - "<db_unique_name> Unique name for the database"
            - "Use only with: type=db"
        required: false
    dbname:
        description:
            - "<db_name> Database name (DB_NAME), if different from the unique name given by the -db option"
            - "Use only with: type=db"
        required: false
    instance:
        description:
            - "<inst_name> Instance name"
            - "Use only with: type=db"
        required: false
    oraclehome:
        description:        
            - "oraclehome <path> Oracle home path"
            - "Use only with: type=db"
        required: false
    domain:
        description:
            - "<domain_name> Domain for database. Must be set if database has DB_DOMAIN set"
            - "Use only with: type=db"
        required: false
    role:
        description:
            - <role> Role of the database"
            - "Use only with: type=db"
        choices: ['PRIMARY', 'PHYSICAL_STANDBY', 'LOGICAL_STANDBY', 'SNAPSHOT_STANDBY']
        required: false
    startoptions:
        description:
            - "<start_options>   Startup options for the database"
            - "Use only with: type=db"
        choices: ['OPEN', 'MOUNT', 'READ ONLY']
        required: false
    stopoption:
        description:
            - "<stop_options> Stop options for the database"
            - "Use only with: type=db"
        choices: ['NORMAL', 'TRANSACTIONAL', 'IMMEDIATE', 'ABORT']
        required: false

notes:
    - cx_Oracle needs to be installed
requirements: [ "cx_Oracle" ]
author: Ivan Brezina
'''

EXAMPLES = '''
# Create a service
- name: Create service dbservice
  oracle_crs_resource:
    name: dbservice 
    type: service 

# Remove a service
oracle_crs_resource: 
    - name: dbservice
    - type:  service
    - state: absent

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


def configure_asm(config, module, ohomes):
    resource_name = module.params["name"]
    try:
        curent_resource = config[resource_name]
    except KeyError as e:
        curent_resource = set()
    listener = module.params["listener"]
    spfile = module.params["spfile"]
    pwfile = module.params["pwfile"]
    diskstring = module.params["diskstring"]
    state = module.params["state"]

    wanted_set = set()
    if spfile:
        wanted_set.add(('spfile', spfile))
    if pwfile:
        wanted_set.add(('pwfile', pwfile))
    if diskstring:
        wanted_set.add(('diskstring', diskstring))
    if listener:
        wanted_set.add(('listener', listener))

    current_set = set()
    if curent_resource and 'SPFILE' in config[resource_name]:
        current_set.add(('spfile', config[resource_name]['SPFILE']))
    if curent_resource and 'PWFILE' in config[resource_name]:
        current_set.add(('pwfile', config[resource_name]['PWFILE']))
    if curent_resource and 'ASM_DISKSTRING' in config[resource_name]:
        current_set.add(('diskstring', config[resource_name]['ASM_DISKSTRING']))

    changes = wanted_set.difference(current_set)

    srvctl = [os.path.join(ohomes.crs_home, "bin", "srvctl")]
    spfile = get_change(changes, 'spfile')
    pwfile = get_change(changes, 'pwfile')
    diskstring = get_change(changes, 'diskstring')
    listener = get_change(changes, 'listener')

    if (not curent_resource) and state == 'present':
        srvctl.extend(['add', 'asm'])
    elif curent_resource and state == 'present':
        srvctl.extend(['modify', 'asm'])
    elif state == 'absent':
        srvctl.extend(['remove', 'asm'])
    else:
        module.fail_json(msg='Unsupported state for ASM instance: {}'.format(state), changed=False)

    if listener:
        srvctl.extend(['-listener', listener])
    if spfile:
        srvctl.extend(['-spfile', spfile])
    if pwfile:
        srvctl.extend(['-pwfile', pwfile])
    if diskstring:
        srvctl.extend(['-diskstring', pwfile])

    if len(srvctl) <= 3:
        module.exit_json(msg='ASM instance is already in desired state'
                         # , resource=curent_resource
                         , command=[], changed=False)

    (rc, stdout, stderr) = module.run_command(srvctl)
    if rc or stderr:
        module.fail_json(msg='srvctl failed: {}'.format(stderr)
                         # , resource=curent_resource
                         , command=[' '.join(srvctl)], changed=True)
    module.exit_json(msg='ASM instance reconfigured'
                     # , resource=list(changes)
                     , command=[' '.join(srvctl)], changed=True)


def configure_db(config, module, ohomes):
    resource_name = module.params["name"].lower()
    try:
        curent_resource = config[resource_name]
    except KeyError as e:
        curent_resource = set()

    state = module.params["state"]

    wanted_set = set()
    for pname in ['spfile', 'pwfile', 'db', 'dbname', 'instance', 'oraclehome', 'domain', 'role', 'startoption',
                  'stopoption', 'diskgroup']:
        param = module.params[pname]
        if param:
            wanted_set.add((pname, param))

    current_set = set()
    if curent_resource and 'SPFILE' in config[resource_name]:
        current_set.add(('spfile', config[resource_name]['SPFILE']))
    if curent_resource and 'PWFILE' in config[resource_name]:
        current_set.add(('pwfile', config[resource_name]['PWFILE']))

    if curent_resource and 'DB_UNIQUE_NAME' in config[resource_name]:
        # -db <db_unique_name>           Unique name for the database
        current_set.add(('db', config[resource_name]['DB_UNIQUE_NAME']))

    if curent_resource and 'USR_ORA_DB_NAME' in config[resource_name]:
        # -dbname < db_name > Database name(DB_NAME), if different from the unique name given by the -db option
        current_set.add(('dbname', config[resource_name]['USR_ORA_DB_NAME']))

    if curent_resource and 'ORACLE_HOME' in config[resource_name]:
        current_set.add(('oraclehome', config[resource_name]['ORACLE_HOME']))

    if curent_resource and 'USR_ORA_DOMAIN' in config[resource_name]:
        current_set.add(('domain', config[resource_name]['USR_ORA_DOMAIN']))

    if curent_resource and 'ROLE' in config[resource_name]:
        current_set.add(('role', config[resource_name]['ROLE']))

    if curent_resource and 'USR_ORA_OPEN_MODE' in config[resource_name]:
        current_set.add(('startoption', config[resource_name]['USR_ORA_OPEN_MODE']))

    if curent_resource and 'USR_ORA_STOP_MODE' in config[resource_name]:
        current_set.add(('stopoption', config[resource_name]['USR_ORA_STOP_MODE']))

    # TODO: START_DEPENDENCIES=hard(ora.DG1.dg,ora.FRA1.dg) weak(type:ora.listener.type,uniform:ora.ons) pullup(ora.DG1.dg,ora.FRA1.dg)
    if curent_resource and 'START_DEPENDENCIES' in config[resource_name]:
        current_set.add(('diskgroup', config[resource_name]['START_DEPENDENCIES']))

    changes = wanted_set.difference(current_set)
    srvctl = [os.path.join(ohomes.crs_home, "bin", "srvctl")]
    if (not curent_resource) and state == 'present':
        srvctl.extend(['add', 'database', '-d', resource_name])
    elif curent_resource and state == 'present':
        srvctl.extend(['modify', 'database', '-d', resource_name])
    elif curent_resource and state == 'absent':
        srvctl.extend(['remove', 'database', '-d', resource_name, '-noprompt'])
    elif (not curent_resource) and state == 'absent':
        module.exit_json(msg='Database resource is already absent', command=[], changed=False)
    else:
        module.fail_json(msg='Unsupported state for Database instance: {}'.format(state), changed=False)

    for change in changes:
        (param, value) = change
        srvctl.extend(['-' + param, value])

    if len(srvctl) <= 5:
        module.exit_json(msg='Database resource is already in desired state'
                         # , resource=curent_resource
                         , command=[], changed=False)

    (rc, stdout, stderr) = module.run_command(srvctl)
    if rc or stderr:
        module.fail_json(msg='srvctl failed: {}'.format(stderr)
                         # , resource=curent_resource
                         , command=[' '.join(srvctl)], changed=True)
    module.exit_json(msg='Database resource reconfigured'
                     # , resource=list(changes)
                     , command=[' '.join(srvctl)], changed=True)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(required=True),
            type=dict(required=True, choices=['asm', 'db', 'listener']),
            state=dict(default="present", choices=["present", "absent", "started", "stopped", "restarted"]),
            # ASM parameters
            listener=dict(required=False),
            spfile=dict(required=False),
            pwfile=dict(required=False),
            diskstring=dict(required=False),
            # DB parameters
            db=dict(required=False),
            dbname=dict(required=False),
            instance=dict(required=False),
            oraclehome=dict(required=False),
            domain=dict(required=False),
            role=dict(required=False, choices=['PRIMARY', 'PHYSICAL_STANDBY', 'LOGICAL_STANDBY', 'SNAPSHOT_STANDBY']),
            startoption=dict(required=False),
            stopoption=dict(required=False),
            diskgroup=dict(required=False),
            # LISTENER parameters
            skip=dict(required=False, type=boolean),
            endpoints=dict(required=False, type=list),
        ),
        supports_check_mode=True,
    )

    ohomes = oracle_homes()
    ohomes.list_crs_instances()
    ohomes.list_processes()
    ohomes.parse_oratab()

    if not ohomes.oracle_gi_managed:
        module.fail_json(msg="Oracle CRS/HAS was not detected", changed=False)

    resource_type = module.params["type"]
    resource_name = module.params["name"]

    config = crs_config(resource_type, resource_name, module, ohomes)

    if resource_type == 'asm':
        configure_asm(config, module, ohomes)
    elif resource_type == 'db':
        configure_db(config, module, ohomes)

    module.exit_json(msg="Unhandled exit", changed=False)


if __name__ == '__main__':
    main()
