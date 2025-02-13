#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_crs_listener
short_description: Manage CRS/HAS resources type listener
description:
  - Manage CRS/HAS Listener resources
version_added: "3.1.7.0"
options:
  name:
    description:
      - "<lsnr_name> Listener name (default name is LISTENER)"
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
    state: restarted
'''

import os
from ansible.module_utils.basic import *

# In these we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
# try:
#    from ansible.module_utils.oracle_homes import OracleHomes
# except:
#    pass

# In these we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_homes import *
except:
    pass


class oracle_crs_listener:
    def __init__(self, module, ohomes):
        self.module = module
        self.ohomes = ohomes
        self.resource_name = module.params['name']
        self.commands = []
        self.changed = False
        self.curent_resource = None
        self.get_crs_config('listener')
        self.srvctl = os.path.join(self.ohomes.crs_home, "bin", "srvctl")

    def run_change_command(self, command):
        self.commands.append(' '.join(command))
        self.changed = True
        if self.module.check_mode:
            return 0, '', ''
        (rc, stdout, stderr) = self.module.run_command(command)
        if rc or stderr:
            for i in stderr.splitlines():
                self.module.warn(i)
            for i in stdout.splitlines():
                self.module.warn(i)                
            # TODO Check and do ignore:
            # PRCC-1010 : LISTENER was already enabled
            # PRCR-1002 : Resource ora.LISTENER.lsnr is already enabled
            self.module.fail_json(msg='srvctl failed({}): {} {}'.format(rc, stdout, stderr)
                                  , commands=self.commands
                                  , changed=self.changed)
        return rc, stdout, stderr

    @staticmethod
    def get_change(change_set, change):
        try:
            return next(v for (a, v) in change_set if a == change)
        except StopIteration:
            return None

    def get_crs_config(self, resource_type):
        if resource_type == 'asm':
            dfilter = '(TYPE = ora.asm.type)'
        elif resource_type == 'db':
            dfilter = '(TYPE = ora.database.type)'
        elif resource_type == 'listener':
            dfilter = '(TYPE = ora.listener.type)'
        elif resource_type == 'service':
            dfilter = '(TYPE = ora.service.type)'
        else:
            self.module.fail_json(msg='Unknown resource type: {}'.format(resource_type)
                                  , commands=self.commands
                                  , changed=self.changed)

        command = [self.ohomes.crsctl, 'stat', 'res', '-p', '-w', dfilter]
        (rc, stdout, stderr) = self.module.run_command(command)

        if rc or stderr:
            self.module.fail_json(msg='Failed command: crsctl stat res -p, {}'.format(stderr)
                                  , commands=self.commands
                                  , changed=self.changed)

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
        self.curent_resource = retval.get(self.resource_name.lower(), dict())


    def configure_listener(self):
        state = self.module.params["state"]
        resource_name = self.module.params['name'].upper()

        wanted_set = set()
        for pname in ['oraclehome', 'endpoints']:
            param = self.module.params[pname]
            if param:
                wanted_set.add((pname, param))

        current_set = set()
        current_set.add(('oraclehome', self.curent_resource.get('ORACLE_HOME', None)))
        current_set.add(('endpoints', self.curent_resource.get('ENDPOINTS', None)))

        apply = False
        changes = wanted_set.difference(current_set)
        srvctl = [self.srvctl]
        if (not self.curent_resource) and state in ['present', 'started', 'stopped', 'restarted']:
            srvctl.extend(['add', 'listener', '-l', resource_name])
            if self.module.params['skip']:
                srvctl.append('-skip')
            apply = True
        elif self.curent_resource and state in ['present', 'started', 'stopped', 'restarted']:
            srvctl.extend(['modify', 'listener', '-l', resource_name])
        elif self.curent_resource and state == 'absent':
            srvctl.extend(['remove', 'listener', '-l', resource_name])
            if self.module.params['force']:
                srvctl.append('-force')            
            apply = True
        elif (not self.curent_resource) and state == 'absent':
            self.module.exit_json(msg='Listener resource is already absent', commands=self.commands, changed=self.changed)
        else:
            self.module.fail_json(msg='Unsupported state for Listener resource: {}'.format(state)
                                  , commands=self.commands
                                  , changed=self.changed)

        for change in changes:
            (param, value) = change
            srvctl.extend(['-' + param, value])
            apply = True

        if changes or apply:
            (rc, stdout, stderr) = self.run_change_command(srvctl)


    def ensure_listener_state(self):
        if self.module.params['state'] == 'absent':
            return

        # Default value for listener ENABLED=1, when listener is created
        enabled = self.curent_resource.get('ENABLED', '1') # 0/1 or '0'/'1'
        enabled = bool(int(enabled))
        enable = self.module.params['enabled']
        if enable and not enabled:
            srvctl = [self.srvctl, 'enable', 'listener', '-l', self.resource_name]
            (rc, stdout, stderr) = self.run_change_command(srvctl)

        if not enable and enabled:
            srvctl = [self.srvctl, 'disable', 'listener', '-l', self.resource_name]
            (rc, stdout, stderr) = self.run_change_command(srvctl)

        srvctl = [self.srvctl, 'status', 'listener', '-l', self.resource_name]
        (rc, stdout, stderr) = self.module.run_command(srvctl)
        running = None
        for line in stdout.splitlines():
            if 'is not running' in line:
                running = False
            if 'is running' in line:
                running = True

        if running is None and not self.module.check_mode:
            self.module.fail_json("Could not check if {} is running".format(self.resource_name)
                                  , commands=self.commands
                                  , changed=self.changed)

        state = self.module.params['state']
        if state == 'stopped' and running:
            srvctl = [self.srvctl, 'stop', 'listener', '-l', self.resource_name]
            (rc, stdout, stderr) = self.run_change_command(srvctl)

        if state == 'started' and not running:
            srvctl = [self.srvctl, 'start', 'listener', '-l', self.resource_name]
            (rc, stdout, stderr) = self.run_change_command(srvctl)

        if state == 'restarted':
            if running:
                srvctl = [self.srvctl, 'stop', 'listener', '-l', self.resource_name]
                (rc, stdout, stderr) = self.run_change_command(srvctl)
            srvctl = [self.srvctl, 'start', 'listener', '-l', self.resource_name]
            (rc, stdout, stderr) = self.run_change_command(srvctl)

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
            force=dict(default=True, required=False, type='bool')
        ),
        supports_check_mode=True,
    )

    ohomes = OracleHomes()
    ohomes.list_crs_instances()
    ohomes.list_processes()
    ohomes.parse_oratab()

    if not ohomes.oracle_gi_managed:
        module.fail_json(msg="Oracle CRS/HAS was not detected", changed=False)

    listener = oracle_crs_listener(module, ohomes)
    listener.configure_listener()
    listener.ensure_listener_state()

    if listener.changed:
        module.exit_json(msg='Listener resource was reconfigured', commands=listener.commands, changed=listener.changed)
    module.exit_json(msg='Listener was already in intended state', commands=listener.commands, changed=listener.changed)


if __name__ == '__main__':
    main()
