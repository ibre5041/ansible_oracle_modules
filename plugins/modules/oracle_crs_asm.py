#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_crs_asm
short_description: Manage CRS/HAS resource type asm
description:
  - Manage CRS/HAS ASM resource
version_added: "3.1.7.0"
options:
  name:
    description:
      - "<asm_name> ASM name (default name is ASM)"
    required: false
    default: ASM
  state:
    description:
      - Resource state
    choices: ['present', 'absent', 'started', 'stopped', 'restarted']
  enabled:
    description:
      - Enables the ASM
    type: bool
    default: true
  listener:
    description:
      - "<lsnr_name> ASM instance Listener name"
    required: false
  spfile:
    description:
      - "<spfile> Server parameter file path"
    required: false
  pwfile:
    description:
      - "<password_file_path> Password file path"
    required: false
  diskstring:
    description:
      - "<asm_diskstring> ASM diskgroup discovery string"
    required: false
notes:
  - Should be executed with privileges of Oracle CRS installation owner
author: Ivan Brezina
'''

EXAMPLES = '''
- name: Register listener ASM_LISTENER
  oracle_crs_asm:
    name: asm
    listener: LISTENER

- name: Restart ASM
  oracle_crs_asm:
    name: asm
    state: restarted
    force: true
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


class oracle_crs_asm:
    def __init__(self, module, ohomes):
        self.module = module
        self.ohomes = ohomes
        self.resource_name = module.params['name']
        self.commands = []
        self.changed = False
        self.curent_resource = None
        self.get_crs_config('asm')
        self.srvctl = os.path.join(self.ohomes.crs_home, "bin", "srvctl")

    def run_change_command(self, command):
        self.commands.append(command)
        self.changed = True
        if self.module.check_mode:
            return 0, '', ''
        (rc, stdout, stderr) = self.module.run_command(command)
        if rc or stderr:
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


    def configure_asm(self):
        state = self.module.params["state"]
        resource_name = self.module.params['name'].upper()

        wanted_set = set()
        for pname in ['listener', 'spfile', 'pwfile', 'diskstring']:
            param = self.module.params[pname]
            if param:
                wanted_set.add((pname, param))

        current_set = set()
        # current_set.add(('listener', self.curent_resource.get('LISTENER', None)))
        current_set.add(('spfile', self.curent_resource.get('SPFILE', None)))
        current_set.add(('pwfile', self.curent_resource.get('PWFILE', None)))
        current_set.add(('diskstring', self.curent_resource.get('ASM_DISKSTRING', None)))

        apply = False
        changes = wanted_set.difference(current_set)
        srvctl = [self.srvctl]
        if (not self.curent_resource) and state in ['present', 'started', 'stopped', 'restarted']:
            srvctl.extend(['add', 'asm'])
            apply = True
        elif self.curent_resource and state in ['present', 'started', 'stopped', 'restarted']:
            srvctl.extend(['modify', 'asm'])
        elif self.curent_resource and state == 'absent':
            srvctl.extend(['remove', 'asm'])
            apply = True
        elif (not self.curent_resource) and state == 'absent':
            self.module.exit_json(msg='ASM resource is already absent', commands=self.commands, changed=self.changed)
        else:
            self.module.fail_json(msg='Unsupported state for ASM resource: {}'.format(state)
                                  , commands=self.commands
                                  , changed=self.changed)

        for change in changes:
            (param, value) = change
            srvctl.extend(['-' + param, value])
            apply = True

        if changes or apply:
            (rc, stdout, stderr) = self.run_change_command(srvctl)


    def ensure_asm_state(self):
        enabled = self.curent_resource.get('ENABLED', '0') # 0/1 or '0'/'1'
        enabled = bool(int(enabled))
        enable = self.module.params['enabled']
        if enable and not enabled:
            srvctl = [self.srvctl, 'enable', 'asm']
            (rc, stdout, stderr) = self.run_change_command(srvctl)

        if not enable and enabled:
            srvctl = [self.srvctl, 'disable', self.resource_name]
            (rc, stdout, stderr) = self.run_change_command(srvctl)

        srvctl = [self.srvctl, 'status', 'asm']
        (rc, stdout, stderr) = self.module.run_command(srvctl)
        running = None
        for line in stdout.splitlines():
            if 'is not running' in line:
                running = False
            if 'is running' in line:
                running = True

        if running is None:
            self.module.fail_json("Could not check if {} is running".format(self.resource_name)
                                  , commands=self.commands
                                  , changed=self.changed)

        state = self.module.params['state']
        if state == 'stopped' and running:
            srvctl = [self.srvctl, 'stop', 'asm']
            if self.module.params['force']:
                srvctl.append('-force')
            (rc, stdout, stderr) = self.run_change_command(srvctl)

        if state == 'started' and not running:
            srvctl = [self.srvctl, 'start', 'asm']
            (rc, stdout, stderr) = self.run_change_command(srvctl)

        if state == 'restarted':
            if running:
                srvctl = [self.srvctl, 'stop', 'asm']
                if self.module.params['force']:
                    srvctl.append('-force')
                (rc, stdout, stderr) = self.run_change_command(srvctl)
            srvctl = [self.srvctl, 'start', 'asm']
            (rc, stdout, stderr) = self.run_change_command(srvctl)

def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(required=True),
            state=dict(default="present", choices=["present", "absent", "started", "stopped", "restarted"]),
            enabled=dict(default=True, required=False, type='bool'),
            # ASM parameters
            listener=dict(required=False),
            spfile=dict(required=False),
            pwfile=dict(required=False),
            diskstring=dict(required=False),
            force=dict(default=True, required=False, type='bool')
        ),
        supports_check_mode=True,
    )

    ohomes = oracle_homes()
    ohomes.list_crs_instances()
    ohomes.list_processes()
    ohomes.parse_oratab()

    if not ohomes.oracle_gi_managed:
        module.fail_json(msg="Oracle CRS/HAS was not detected", changed=False)

    asm = oracle_crs_asm(module, ohomes)
    asm.configure_asm()
    asm.ensure_asm_state()

    if asm.changed:
        module.exit_json(msg='ASM resource was reconfigured', commands=asm.commands, changed=asm.changed)
    module.exit_json(msg='ASM was already in intended state', commands=asm.commands, changed=asm.changed)


if __name__ == '__main__':
    main()
