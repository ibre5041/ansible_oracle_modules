#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_crs_resource
short_description: Manage CRS/HAS resources
description:
    - Manage CRS/HAS resources
version_added: "3.1.7.0"
options:
    name:
        description:
            - Name of the resource
        required: true
        default: None
    type:
        description:
            - Type of the resource
        required: true
        default: None
        choices: ['asm', 'db', listener', 'service']
    listener:
        description:
            - ASM instance LISTENER
            - "Use only with: type=asm"
        required: false
    spfile:
        description:
            - ASM instance SPFILE
            - "Use only with: type=asm"            
        required: false
    pwfile:
        description:
            - ASM instance password file
            - "Use only with: type=asm"
        required: false
    diskstring:
        description:
            - ASM instance parameter diskstring
            - "Use only with: type=asm"
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


def get_change(change_set, change):
    try:
        return next(v for (a, v) in change_set if a == change)
    except StopIteration:
        return None

# Check if the service exists
def check_service_exists(oc, module, msg, name, database_name):
    oracle_home = module.params["oracle_home"]
    if gimanaged:
        command = "%s/bin/srvctl config service -d %s -s %s" % (oracle_home, database_name, name)
        (rc, stdout, stderr) = module.run_command(command)
        if rc != 0:
            if 'PRCR-1001' in stdout: #<-- service doesn't exist
                return False
            else:
                msg = 'Error: command: %s. stdout: %s, stderr: %s' % (command, stdout, stderr)
                return False
        elif 'Service name: %s' % name in stdout: #<-- service already exist
            #msg = 'Service %s already exists in database %s' % (name, database_name)
            return True
        else:
            msg = stdout
            return True


def create_service(oc, module, msg):
    oracle_home = module.params["oracle_home"]

    database_name       = module.params["database_name"]
    name                = module.params["name"]
    preferred_instances = module.params["preferred_instances"]
    available_instances = module.params["available_instances"]
    role                = module.params["role"]
    pdb                 = module.params["pdb"]
    clbgoal             = module.params["clbgoal"]
    rlbgoal             = module.params["rlbgoal"]

    if gimanaged:
        command = "%s/bin/srvctl add service -d %s -s %s" % (oracle_home, database_name, name)
        if preferred_instances:
            command += ' -r %s' % preferred_instances

        if available_instances:
            command += ' -a %s' % available_instances

        if pdb:
            command += ' -pdb %s' % pdb

        if role:
            command += ' -l %s' % role

        if clbgoal:
            command += ' -clbgoal %s' % clbgoal

        if rlbgoal:
            command += ' -rlbgoal %s' % rlbgoal

        # module.fail_json(msg=command)
        (rc, stdout, stderr) = module.run_command(command)
        if rc != 0:
            if 'PRKO-3117' in stdout: #<-- service already exist
                msg = 'Service %s already exists in database %s' % (name, database_name)
                module.exit_json(msg=msg, changed=False)
            else:
                msg = 'Error: %s, command is %s' % (stdout, command)
                return False
        else:
            if pdb:
                database_name = pdb
            return True


def ensure_service_state(oc, module, msg):
    oracle_home = module.params["oracle_home"]

    database_name       = module.params["database_name"]
    name                = module.params["name"]
    state               = module.params["state"]
    preferred_instances = module.params["preferred_instances"]
    available_instances = module.params["available_instances"]
    clbgoal             = module.params["clbgoal"]
    rlbgoal             = module.params["rlbgoal"]

    configchange = False
    if not newservice:
        _wanted_ai = ['']
        _wanted_pi = ['']
        _wanted_config = {}
        if rlbgoal is not None:
            _wanted_config['rlb'] = rlbgoal
        else:
            _wanted_config['rlb'] = 'NONE'
            rlbgoal = 'NONE'
        if clbgoal is not None:
            _wanted_config['clb'] = clbgoal
        else:
            _wanted_config['clb'] = 'LONG'
            clbgoal = 'LONG'

        modify_conf = '%s/bin/srvctl modify service -d %s -s %s' % (oracle_home, database_name, name)
        modify_inst = '%s/bin/srvctl modify service -d %s -s %s -modifyconfig' % (oracle_home, database_name, name)
        _inst_temp = ""
        _conf_temp = ""
        total_mod = []

        if available_instances and available_instances is not None:
            _wanted_ai = available_instances.split(',')
        if preferred_instances and preferred_instances is not None:
            _wanted_pi = preferred_instances.split(',')

        _curr_config,_curr_config_ai,_curr_config_pi = _get_service_config(oc, module, msg, oracle_home, name, database_name)

        # Compare instance configurations
        if _wanted_pi != _curr_config_pi:
            _inst_temp += ' -preferred %s' % preferred_instances
        if _wanted_ai != _curr_config_ai and '' not in _wanted_ai:
            _inst_temp += ' -available %s' % available_instances

        if len(_inst_temp) > 0:
            modify_inst += _inst_temp
            total_mod.append(modify_inst)

        # Compare other configuration
        if not _wanted_config == _curr_config:
            _conf_temp += ' -clbgoal %s -rlbgoal %s' % (clbgoal, rlbgoal)
            # if clbgoal is not None:
            #     _conf_temp += ' -clbgoal %s ' % (clbgoal)
            # if rlbgoal is not None:
            #     _conf_temp += ' -rlbgoal %s' % (rlbgoal)
            modify_conf += _conf_temp
            total_mod.append(modify_conf)

        # module.exit_json(msg="%s,     %s, %s" % (total_mod, _wanted_config, _curr_config))
        if len(total_mod) > 0:
            for cmd in total_mod:
                (rc, stdout, stderr) = module.run_command(cmd)
                if rc != 0:
                    if rc != 0:
                        msg = "Error modifying service. Command: %s, stdout: %s, stderr: %s" % (cmd,stdout,stderr)
                        module.fail_json(msg=msg, changed=False)
            configchange = True

    if state == 'present':
        if newservice:
            module.exit_json(msg="Service %s (%s) successfully created" % (name, database_name), changed=True)
        else:
            msg = "Service %s (%s) is in the intended state" % (name, database_name)
            if configchange:
                msg += 'after configchanges had been applied'
                change=True
            module.exit_json(msg=msg, changed=change)

    if state == 'started':
        change = False
        if start_service(oc, module, msg, name, database_name, configchange):
            change = True
            msg = 'Service %s (%s) successfully created/started' % (name, database_name)
            if configchange:
                msg += ' and config changes have been applied'
                change = True
            module.exit_json(msg=msg, changed=change)

    if state == 'stopped':
        if stop_service(oc, module, msg, name, database_name):
            msg = 'Service %s (%s) successfully stopped' % (name, database_name)
            change = True
            if configchange:
                msg += ' and config changes have been applied'
                change=True
            module.exit_json(msg=msg, changed=change)
        else:
            msg = 'Service %s (%s) already stopped' % (name, database_name)
            change = False
            if configchange:
                msg += ' but config changes have been applied'
                change=True
            module.exit_json(msg=msg, changed=change)


def remove_service(oc, module, msg, name, database_name, force):
    oracle_home = module.params["oracle_home"]
    stop_service(oc, module, msg, name, database_name)
    if gimanaged:
        command = "%s/bin/srvctl remove service -d %s -s %s" % (oracle_home, database_name, name)
        if force:
            command += ' -f'

        (rc, stdout, stderr) = module.run_command(command)
        if rc != 0:
            if 'PRCR-1001' in stdout: #<-- service doesn' exist
                return False
            else:
                msg = 'Removal of service %s in database %s failed: %s' % (name,database_name,stdout)
                module.fail_json(msg=msg, changed=False)
        else:
            return True


def check_service_status(cursor, module, msg, name, database_name, state):
    oracle_home = module.params["oracle_home"]
    if gimanaged:
        command = "%s/bin/srvctl status service -d %s -s %s" % (oracle_home, database_name, name)
        (rc, stdout, stderr) = module.run_command(command)

        if rc != 0:
            msg = 'Checking status of service %s in database %s failed: %s' % (name,database_name,stdout)
            module.fail_json(msg=msg, changed=False)

        elif state == "status":
            module.exit_json(msg=stdout.rstrip('\n'), changed=False)

        elif 'is not running' in stdout:
            return False
        else:
            #msg = 'service %s already running in database %s' % (name,database_name)
            return True


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
        module.fail_json(msg='crsctl stat res -p', changed=False)

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
                    name = value[len('ora.'):]
                else:
                    name = value
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
        current_set.add(('SPFILE', config[resource_name]['SPFILE']))
    if curent_resource and 'PWFILE' in config[resource_name]:
        current_set.add(('PWFILE', config[resource_name]['PWFILE']))
    if curent_resource and 'ASM_DISKSTRING' in config[resource_name]:
        current_set.add(('ASM_DISKSTRING', config[resource_name]['ASM_DISKSTRING']))

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
                         #, resource=curent_resource
                         , command=[], changed=False)

    (rc, stdout, stderr) = module.run_command(srvctl)
    if rc or stderr:
        module.fail_json(msg='srvctl failed: {}'.format(stderr)
                         #, resource=curent_resource
                         , command=[' '.join(srvctl)], changed=True)
    module.exit_json(msg='ASM instance reconfigured'
                     #, resource=list(changes)
                     , command=[' '.join(srvctl)], changed=True)



def main():
    module = AnsibleModule(
        argument_spec = dict(
            name      = dict(required=True),
            type      = dict(required=True, choices=['asm', 'db', 'listener', 'service']),
            state     = dict(default="present", choices=["present", "absent", "started", "stopped", "restarted"]),
            # ASM parameters
            listener  = dict(required=False),
            spfile    = dict(required=False),
            pwfile    = dict(required=False),
            diskstring= dict(required=False)
        ),
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

    module.exit_json(msg="Unhandled exit", changed=False)


from ansible.module_utils.basic import *

# In these we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
#try:
#    from ansible.module_utils.oracle_utils import oracleConnection
#    from ansible.module_utils.oracle_homes import oracle_homes
#except:
#    pass

# In these we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracleConnection
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_homes import *
except:
    pass


if __name__ == '__main__':
    main()
