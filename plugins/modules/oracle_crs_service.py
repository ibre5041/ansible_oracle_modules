#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_crs_service
short_description: Manage CRS/HAS resources type service
description:
  - Manage CRS/HAS Database services
version_added: "3.1.7.0"
options:
  name:
    description:
      - "-service "<serv,...>" Comma separated service names"
      - "Or just this for single service name"
    required: true
  db:
    description:
      - "-db <db_unique_name> Unique name for the database"
    required: true
  state:
    description:
      - Resource state
    choices: ['present', 'absent', 'started', 'stopped', 'restarted']
  enabled:
    description:
      - Enables the service
    type: bool
    default: true
  force:
    description:
      - "Force stop, will stop database and any associated services and any dependent resources"
      - "Force remove (ignore dependencies)"
      - "Force the add operation even though a listener is not configured for a network"
    type: bool
    default: false
    -role <role>                   Role of the service (primary, physical_standby, logical_standby, snapshot_standby)
    -policy <policy>               Management policy for the service (AUTOMATIC or MANUAL)
    -failovertype                  (NONE | SESSION | SELECT | TRANSACTION | AUTO)      Failover type
    -failovermethod                (NONE | BASIC)     Failover method
    -failoverdelay <failover_delay> Failover delay (in seconds)
    -failoverretry <failover_retries> Number of attempts to retry connection
    -failover_restore <failover_restore>  Option to restore initial environment for Application Continuity and TAF (NONE or LEVEL1)
    -edition <edition>             Edition (or "" for empty edition value)
    -pdb <pluggable_database>      Pluggable database name
    -maxlag <max_lag_time>         Maximum replication lag time in seconds (Non-negative integer, default value is 'ANY')
    -clbgoal                       (SHORT | LONG)                   Connection Load Balancing Goal. Default is LONG.
    -rlbgoal                       (SERVICE_TIME | THROUGHPUT | NONE)     Runtime Load Balancing Goal
    -notification                  (TRUE | FALSE)  Enable Fast Application Notification (FAN) for OCI connections
    -global <global>               Global attribute (TRUE or FALSE)
    -sql_translation_profile <sql_translation_profile> Specify a database object for SQL translation profile
    -commit_outcome                (TRUE | FALSE)          Commit outcome
    -retention <retention>         Specifies the number of seconds the commit outcome is retained
    -replay_init_time <replay_initiation_time> Seconds after which replay will not be initiated
    -session_state <session_state> Session state consistency (STATIC or DYNAMIC)
    -tablefamilyid <table_family_id> Set table family ID for a given service
    -drain_timeout <drain_timeout> Service drain timeout specified in seconds
    -stopoption <stop_options>     Options to stop service (e.g. TRANSACTIONAL or IMMEDIATE)

    
notes:
  - Should be executed with privileges of Oracle CRS installation owner
author: Ivan Brezina
'''

EXAMPLES = '''
- name: Register Database
  oracle_crs_service:
    name: TMP12102 

- name: Restart Database
  oracle_crs_service:
    name: TMP12102
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


class oracle_crs_service:
    def __init__(self, module, ohomes):
        self.module = module
        self.ohomes = ohomes
        self.resource_name = module.params['name']
        self.commands = []
        self.changed = False
        self.curent_resource = None
        self.get_crs_config('db')
        self.srvctl = os.path.join(self.ohomes.crs_home, "bin", "srvctl")

    def run_change_command(self, command):
        self.commands.append(' '.join(command))
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

    def configure_db(self):
        state = self.module.params["state"]
        resource_name = self.module.params['name'].upper()

        wanted_set = set()
        for pname in ['oraclehome', 'domain', 'spfile', 'pwfile', 'role', 'startoption', 'stopoption'
            , 'dbname', 'instance', 'policy', 'diskgroup']:
            param = self.module.params[pname]
            if param:
                wanted_set.add((pname, param))

        current_set = set()
        current_set.add(('oraclehome', self.curent_resource.get('ORACLE_HOME', None)))
        current_set.add(('domain', self.curent_resource.get('USR_ORA_DOMAIN', None)))
        current_set.add(('spfile', self.curent_resource.get('SPFILE', None)))
        current_set.add(('pwfile', self.curent_resource.get('PWFILE', None)))
        current_set.add(('role', self.curent_resource.get('ROLE', None)))
        current_set.add(('startoption', self.curent_resource.get('USR_ORA_OPEN_MODE', None)))
        current_set.add(('stopoption', self.curent_resource.get('USR_ORA_STOP_MODE', None)))
        current_set.add(('dbname', self.curent_resource.get('USR_ORA_DB_NAME', None)))
        # current_set.add(('instance', self.curent_resource.get('ENDPOINTS', None)))
        current_set.add(('policy', self.curent_resource.get('MANAGEMENT_POLICY', None)))
        # current_set.add(('diskgroup', self.curent_resource.get('ENDPOINTS', None)))

        apply = False
        changes = wanted_set.difference(current_set)
        srvctl = [self.srvctl]
        if (not self.curent_resource) and state in ['present', 'started', 'stopped', 'restarted']:
            srvctl.extend(['add', 'database', '-d', resource_name])
            apply = True
        elif self.curent_resource and state in ['present', 'started', 'stopped', 'restarted']:
            srvctl.extend(['modify', 'database', '-d', resource_name])
        elif self.curent_resource and state == 'absent':
            srvctl.extend(['remove', 'database', '-d', resource_name, '-noprompt'])
            if self.module.params['force']:
                srvctl.append('-force')
            apply = True
        elif (not self.curent_resource) and state == 'absent':
            self.module.exit_json(msg='db resource is already absent', commands=self.commands, changed=self.changed)
        else:
            self.module.fail_json(msg='Unsupported state for db resource: {}'.format(state)
                                  , commands=self.commands
                                  , changed=self.changed)

        for change in changes:
            (param, value) = change
            srvctl.extend(['-' + param, value])
            apply = True

        if changes or apply:
            (rc, stdout, stderr) = self.run_change_command(srvctl)

    def ensure_db_state(self):
        if self.module.params['state'] == 'absent':
            return

        enabled = self.curent_resource.get('ENABLED', '1')  # 0/1 or '0'/'1'
        enabled = bool(int(enabled))
        enable = self.module.params['enabled']
        if enable and not enabled:
            srvctl = [self.srvctl, 'enable', 'database', '-d', self.resource_name]
            (rc, stdout, stderr) = self.run_change_command(srvctl)

        if not enable and enabled:
            srvctl = [self.srvctl, 'disable', 'database', '-d', self.resource_name]
            (rc, stdout, stderr) = self.run_change_command(srvctl)

        srvctl = [self.srvctl, 'status', 'database', '-d', self.resource_name]
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
            srvctl = [self.srvctl, 'stop', 'database', '-d', self.resource_name]
            (rc, stdout, stderr) = self.run_change_command(srvctl)

        if state == 'started' and not running:
            srvctl = [self.srvctl, 'start', 'database', '-d', self.resource_name]
            (rc, stdout, stderr) = self.run_change_command(srvctl)

        if state == 'restarted':
            if running:
                srvctl = [self.srvctl, 'stop', 'database', '-d', self.resource_name]
                (rc, stdout, stderr) = self.run_change_command(srvctl)
            srvctl = [self.srvctl, 'start', 'database', '-d', self.resource_name]
            (rc, stdout, stderr) = self.run_change_command(srvctl)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(required=True),
            state=dict(default="present", choices=["present", "absent", "started", "stopped", "restarted"]),
            enabled=dict(default=True, required=False, type='bool'),
            force=dict(default=False, required=False, type='bool'),
            # db parameters
            oraclehome=dict(required=False),
            domain=dict(required=False),
            spfile=dict(required=False),
            pwfile=dict(required=False),
            role=dict(required=False, choices=['PRIMARY', 'PHYSICAL_STANDBY', 'LOGICAL_STANDBY', 'SNAPSHOT_STANDBY']),
            startoption=dict(required=False, choices=['OPEN', 'MOUNT', 'READ ONLY']),
            stopoption=dict(required=False, choices=['NORMAL', 'TRANSACTIONAL', 'IMMEDIATE', 'ABORT']),
            dbname=dict(required=False),
            instance=dict(required=False),
            policy=dict(required=False, choices=['AUTOMATIC', 'MANUAL', 'NORESTART', 'USERONLY']),
            diskgroup=dict(required=False),
        ),
        required_if=[('present', 'present', ('oraclehome'))],
        supports_check_mode=True,
    )

    ohomes = oracle_homes()
    ohomes.list_crs_instances()
    ohomes.list_processes()
    ohomes.parse_oratab()

    if not ohomes.oracle_gi_managed:
        module.fail_json(msg="Oracle CRS/HAS was not detected", changed=False)

    db = oracle_crs_service(module, ohomes)
    db.configure_db()
    db.ensure_db_state()

    if db.changed:
        module.exit_json(msg='Database resource was reconfigured', commands=db.commands, changed=db.changed)
    module.exit_json(msg='Database was already in intended state', commands=db.commands, changed=db.changed)


if __name__ == '__main__':
    main()
