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
      - "-service <serv,...> Comma separated service names"
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
    required: false
  role:
    description:
      - "-role <role> Role of the service"
    choices: ['PRIMARY', 'PHYSICAL_STANDBY', 'LOGICAL_STANDBY', 'SNAPSHOT_STANDBY']
    required: false
  policy:
    description:
      - "-policy <policy> Management policy for the service (AUTOMATIC or MANUAL)"
    choices: ['AUTOMATIC', 'MANUAL']
    required: false
  failovertype:
    description:
      - "-failovertype (NONE | SESSION | SELECT | TRANSACTION | AUTO) Failover type"
    choices: ['NONE', 'SESSION', 'SELECT', 'TRANSACTION', 'AUTO']
    required: false
  failovermethod:
    description:
      - "-failovermethod (NONE | BASIC) Failover method"
    choices: ['NONE', 'BASIC']
    required: false
  failoverdelay:
    description:
      - "-failoverdelay <failover_delay> Failover delay (in seconds)"
    required: false
  failoverretry:
    description:
      - "-failoverretry <failover_retries> Number of attempts to retry connection"
    required: false
  failover_restore:
    description:
      - "-failover_restore <failover_restore> Option to restore initial environment for Application Continuity and TAF (NONE or LEVEL1)"
    choices: ['NONE', 'LEVEL1']
    required: false
  edition:
    description:
      - '-edition <edition> Edition (or "" for empty edition value)'
    required: false
  pdb:
    description:
      - "-pdb <pluggable_database> Pluggable database name"
    required: false
  maxlag:
    description:
      - "-maxlag <max_lag_time> Maximum replication lag time in seconds (Non-negative integer, default value is 'ANY')"
    required: false
  clbgoal:
    description:
      - "-clbgoal (SHORT | LONG) Connection Load Balancing Goal. Default is LONG."
    choices: ['SHORT', 'LONG']
    required: false
  rlbgoal:
    description:
      - "-rlbgoal (SERVICE_TIME | THROUGHPUT | NONE) Runtime Load Balancing Goal"
    choices: ['SERVICE_TIME', 'THROUGHPUT', 'NONE']
  notification:
    description:
      - "-notification (TRUE | FALSE)  Enable Fast Application Notification (FAN) for OCI connections"
    type: bool
  global:
    description:
      - "-global <global> Global attribute (TRUE or FALSE)"
    type: bool
  sql_translation_profile:
    description:
      - "-sql_translation_profile <sql_translation_profile> Specify a database object for SQL translation profile"
    required: false
  commit_outcome:
    description:
      - "-commit_outcome (TRUE | FALSE) Commit outcome"
    type: bool
    required: false
  retention:
    description:
      - "-retention <retention> Specifies the number of seconds the commit outcome is retained"
    required: false
  replay_init_time:
    description:
      - "-replay_init_time <replay_initiation_time> Seconds after which replay will not be initiated"
    required: false
  session_state:
    description:
      - "-session_state <session_state> Session state consistency (STATIC or DYNAMIC)"
    choices: ['STATIC', 'DYNAMIC']
    required: false
  tablefamilyid:
    description:
      - "-tablefamilyid <table_family_id> Set table family ID for a given service"
    required: false
  drain_timeout:
    description:
      - "-drain_timeout <drain_timeout> Service drain timeout specified in seconds"
    required: false
  stopoption:
    description:
      - "-stopoption <stop_options>     Options to stop service (e.g. TRANSACTIONAL or IMMEDIATE)"
    choices: ['TRANSACTIONAL', 'IMMEDIATE']
    required: false
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
    argument_spec=dict(
        name=dict(required=True),
        state=dict(default="present", choices=["present", "absent", "started", "stopped", "restarted"]),
        enabled=dict(default=True, required=False, type='bool'),
        force=dict(default=False, required=False, type='bool'),
        # service parameters
        # <db_unique_name> Unique name for the database
        db=dict(required=False),
        # <role> Role of the service (primary, physical_standby, logical_standby, snapshot_standby)
        role=dict(required=False, choices=['PRIMARY', 'PHYSICAL_STANDBY', 'LOGICAL_STANDBY', 'SNAPSHOT_STANDBY']),
        # <policy> Management policy for the service (AUTOMATIC or MANUAL)
        policy=dict(required=False, choices=['AUTOMATIC', 'MANUAL']),
        # Failover type (NONE | SESSION | SELECT | TRANSACTION | AUTO)
        failovertype=dict(required=False, choices=['NONE', 'SESSION', 'SELECT', 'TRANSACTION', 'AUTO']),
        # (NONE | BASIC) Failover method
        failovermethod=dict(required=False, choices=['NONE', 'BASIC']),
        # <failover_delay> Failover delay (in seconds)
        failoverdelay=dict(required=False),
        # <failover_retries> Number of attempts to retry connection
        failoverretry=dict(required=False),
        # <failover_restore> Option to restore initial environment for Application Continuity and TAF (NONE or LEVEL1)
        failover_restore=dict(required=False),
        # <edition> Edition (or "" for empty edition value)
        edition=dict(required=False),
        # <pluggable_database> Pluggable database name
        pdb=dict(required=False),
        # <max_lag_time> Maximum replication lag time in seconds (Non-negative integer, default value is 'ANY
        maxlag=dict(required=False),
        # (SHORT | LONG) Connection Load Balancing Goal. Default is LONG.
        clbgoal=dict(required=False, choices=['SHORT', 'LONG']),
        # (SERVICE_TIME | THROUGHPUT | NONE)     Runtime Load Balancing Goal
        rlbgoal=dict(required=False, choices=['SERVICE_TIME', 'THROUGHPUT', 'NONE']),
        # (TRUE | FALSE)  Enable Fast Application Notification (FAN) for OCI connections
        notification=dict(required=False, type='bool'),
        # <global> Global attribute (TRUE or FALSE)
        ## global=dict(required=False, type='bool'),
        # <sql_translation_profile> Specify a database object for SQL translation profile
        sql_translation_profile=dict(required=False),
        # (TRUE | FALSE) Commit outcome
        commit_outcome=dict(required=False, type='bool'),
        # <retention> Specifies the number of seconds the commit outcome is retained
        retention=dict(required=False),
        # <replay_initiation_time> Seconds after which replay will not be initiated
        replay_init_time=dict(required=False),
        # <session_state> Session state consistency (STATIC or DYNAMIC)
        session_state=dict(required=False, choices=['STATIC', 'DYNAMIC']),
        # <table_family_id> Set table family ID for a given service
        tablefamilyid=dict(required=False),
        # <drain_timeout> Service drain timeout specified in seconds
        drain_timeout=dict(required=False),
        # <stop_options> Options to stop service (e.g. TRANSACTIONAL or IMMEDIATE)
        stopoption=dict(required=False, choices=['TRANSACTIONAL', 'IMMEDIATE']),
    )
    # global is Python keyword, use this hack to use 'global' as ansible module parameter
    argument_spec.update({'global': dict(required=False, type='bool')})
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    
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
