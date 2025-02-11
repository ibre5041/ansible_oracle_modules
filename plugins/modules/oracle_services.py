#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_services
short_description: Manage services in an Oracle database
description:
    - Manage services in an Oracle database
version_added: "2.1.0.0"
options:
    name:
        description:
            - The name of the service
        required: true
        default: None
    oracle_home:
        description:
            - The name of the service
        required: true
        default: None
        aliases: ['oh']
    database_name:
        description:
            - The database in which the service will run
        required: True
        default: None
        aliases: ['db']
    state:
        description:
            - The intended state of the service. 'status' will just show the status of the service
        default: present
        choices: ['present','absent','started','stopped', 'status']
    preferred_instances:
        description:
            - The RAC instances on which the service will actively run. Comma-separated list
        required: false
        default: None
        aliases: ['pi']
    available_instances:
        description:
            - The RAC instances on which the service can run in case of failure of preferred_instances. Comma-separated list
        required: false
        default: None
        aliases: ['ai']
    pdb:
        description:
            - The pdb which the service is attached to
        required: false
        default: None
    role:
        description: 
            - Role of the service (primary, physical_standby, logical_standby, snapshot_standby)
        required: false
        default: None
        choices: ['primary', 'physical_standby', 'logical_standby', 'snapshot_standby']
    force:
        description:
            - Adds the 'force' flag to the srvctl command
        default: False
        choices: ['true','false']
    username:
        description:
            - The database username to connect to the database if using dbms_service
        required: false
        default: None
        aliases: ['un']
    password:
        description:
            - The password to connect to the database if using dbms_service
        required: false
        default: None
        aliases: ['pw']
    service_name:
        description:
            - The service_name to connect to the database if using dbms_service.
        required: false
        default: database_name. Will be set to the pdb-name if pdb is set
        aliases: ['sn']
    hostname:
        description:
            - The host of the database if using dbms_service
        required: false
        default: localhost
        aliases: ['host']
    port:
        description:
            - The listener port to connect to the database if using dbms_service
        required: false
        default: 1521

notes:
    - oracledb needs to be installed
requirements: [ "oracledb" ]
author: Mikael Sandström, oravirt@gmail.com, @oravirt
'''

EXAMPLES = '''
# Create a service
oracle_services: name=service1 database_name=db1 state=present

# Start a service
oracle_services: name=service1 database_name=db1 state=started

# Stop a service
oracle_services: name=service1 database_name=db1 state=stopped

# Remove a service
oracle_services: name=service1 database_name=db1 state=absent

# Create a service in a RAC pdb and run it on a subset of nodes/instances
oracle_services: name=service1 database_name=raccdb oh=/u01/app/oracle/12.1.0.2/db1 pdb=mypdb pi=raccdb1 ai=raccdb2,raccdb3 state=present

'''

import os


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
    else:
        sql = 'select lower(name) from dba_services where lower (name) = \'%s\'' % (name.lower())
        if execute_sql_get(module, msg, cursor, sql):
            return True
        else:
            return False


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
    else:
        #if pdb != None:
        #    database_name = pdb:

        sql = 'BEGIN dbms_service.create_service('
        sql_end = '); END;'
        sql += 'service_name => \'%s\', network_name => \'%s\'' % (name, name)
        sql += sql_end

        if execute_sql(module, msg, cursor, sql):
            return True
        else:
            return False


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
    else:
        sql = 'BEGIN dbms_service.delete_service('
        sql_end = '); END;'
        sql += 'service_name => \'%s\'' % (name)
        sql += sql_end

        if execute_sql(module, msg, cursor, sql):
            return True
        else:
            return False


def _get_service_config(cursor, module, msg, name, database_name):
    oracle_home = module.params["oracle_home"]
    _curr_config_dict = {}
    _curr_config_inst_ai = []
    _curr_config_inst_pi = []
    command = '%s/bin/srvctl config service -d %s -s %s' % (oracle_home, database_name, name)
    (rc, stdout, stderr) = module.run_command(command)
    if rc != 0:
        msg = "Error getting service configuration. Command: %s, stdout: %s, stderr: %s" % (command,stdout,stderr)

    for l in stdout.splitlines():
        a = l.split(': ')
        if a[0] == 'Connection Load Balancing Goal':
            _curr_config_dict['clb'] = a[1]
        if a[0] == 'Runtime Load Balancing Goal':
            _curr_config_dict['rlb'] = a[1]
        if a[0] == 'Available instances':
            _curr_config_inst_ai = a[1].split(',')
        if a[0] == 'Preferred instances':
            _curr_config_inst_pi = a[1].split(',')

    return _curr_config_dict, _curr_config_inst_ai,_curr_config_inst_pi


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
    else:
        sql = '''
            select lower(s.name)
            from v$active_services s
            where lower(s.name) = \'%s\'
              ''' % (name.lower())
        #if execute_sql_get(module, msg, cursor, sql):
        if execute_sql_get(module, msg, cursor, sql):
            return True
        else:
            return False


def start_service(oc, module, msg, name, database_name, configchange):
    oracle_home = module.params["oracle_home"]
    if gimanaged:
        command = "%s/bin/srvctl start service -d %s -s %s" % (oracle_home, database_name, name)
        (rc, stdout, stderr) = module.run_command(command)
        if rc != 0:
            if 'PRCR-1001' in stdout:
                msg = 'Service %s doesn\'t exist in database %s' % (name, database_name)
                module.fail_json(msg=msg, changed=False)
            elif 'PRCC-1014' in stdout or 'PRCR-1120' in stdout: #<-- service already running
                msg= 'Service %s (%s) already running' % (name, database_name)
                change = False
                if configchange:
                    msg += ' but config changes have been applied'
                    change=True
                module.exit_json(msg=msg, changed=change)
            else:
                msg = 'Starting service %s in database %s failed: %s' % (name,database_name,stdout)
                module.fail_json(msg=msg, changed=False)

        else:
            return True
    else:
        if check_service_exists(oc, module, msg, name, database_name):
            if not check_service_status(oc, module, msg, name, database_name, 'status'):
                sql = 'BEGIN dbms_service.start_service('
                sql_end = '); END;'
                sql += 'service_name => \'%s\'' % (name)
                sql += sql_end

                if execute_sql(module, msg, cursor, sql):
                    return True
                else:
                    return False
            else:
                return False
        else:
            msg = 'Service %s doesn\'t exist in database %s' % (name, database_name)
            module.fail_json(msg=msg, changed=False)


def stop_service(oc, module, msg, name, database_name):
    oracle_home = module.params["oracle_home"]
    if gimanaged:
        command = "%s/bin/srvctl stop service -d %s -s %s" % (oracle_home, database_name, name)
        (rc, stdout, stderr) = module.run_command(command)

        if rc != 0:
            if 'PRCR-1005' in stdout or 'CRS-2500' or 'PRCD-1316' in stdout: # Already stopped
                return False
            elif 'PRCR-1001' in stdout or 'PRCD-1132' in stdout:
                msg = 'Service %s doesn\'t exist in database %s' % (name, database_name)
                module.exit_json(msg=msg, changed=False)
            else:
                msg = 'Stopping service %s (%s) failed: %s' % (name, database_name, stdout)
                module.fail_json(msg=msg, changed=False)
        else:
            return True
    else:
        if check_service_exists(oc, module, msg, name, database_name):
            if check_service_status(oc, module, msg, name, database_name, 'status'):
                sql = 'BEGIN dbms_service.stop_service('
                sql_end = '); END;'
                sql += 'service_name => \'%s\'' % name
                sql += sql_end

                if execute_sql(module, msg, cursor, sql):
                    return True
                else:
                    return False
            else:
                return False
        else:
            msg = 'Service %s doesn\'t exist in database %s' % (name, database_name)
            module.exit_json(msg=msg, changed=False)


def execute_sql_get(module, msg, cursor, sql):
    #module.exit_json(msg="In execute_sql_get", changed=False)
    try:
        cursor.execute(sql)
        result = (cursor.fetchone())
    except oracledb.DatabaseError as exc:
        error, = exc.args
        msg = 'Something went wrong while executing sql_get - %s sql: %s' % (error.message, sql)
        module.fail_json(msg=msg, changed=False)
        return False

    if result > 0:
        return True
    else:
        return False

def execute_sql(module, msg, cursor, sql):
    try:
        cursor.execute(sql)
    except oracledb.DatabaseError as exc:
        error, = exc.args
        msg = 'Something went wrong while executing sql - %s sql: %s' % (error.message, sql)
        module.fail_json(msg=msg, changed=False)
        return False
    return True


def main():
    global gimanaged
    global newservice
    global configchange
    configchange = False
    newservice = False
    module = AnsibleModule(
        argument_spec = dict(
            user               = dict(required=False, aliases=['un', 'username']),
            password           = dict(required=False, no_log=True, aliases=['pw']),
            mode               = dict(default='normal', choices=["normal", "sysdba"]),
            hostname           = dict(required=False, default='localhost', aliases=['host']),
            port               = dict(required=False, default=1521, type='int'),
            service_name       = dict(required=False, aliases=['sn']),
            oracle_home        = dict(required=False, aliases=['oh']),

            name                = dict(required=True, aliases=['service']),
            database_name       = dict(required=True, aliases=['db']),
            state               = dict(default="present", choices=["present", "absent", "started", "stopped", "status", "restarted"]),
            preferred_instances = dict(required=False, aliases=['pi']),
            available_instances = dict(required=False, aliases=['ai']),
            pdb                 = dict(required=False),
            role                = dict(required=False, choices=["primary", "physical_standby", "logical_standby", "snapshot_standby"]),
            clbgoal             = dict(required=False, aliases=['clb']),
            rlbgoal             = dict(required=False, aliases=['rlb']),
            force               = dict(default=False, type='bool')
        ),
    )

    name                = module.params["name"]
    oracle_home         = module.params["oracle_home"]
    database_name       = module.params["database_name"]
    state               = module.params["state"]
    preferred_instances = module.params["preferred_instances"]
    available_instances = module.params["available_instances"]
    pdb                 = module.params["pdb"]
    role                = module.params["role"]
    clbgoal             = module.params["clbgoal"]
    rlbgoal             = module.params["rlbgoal"]
    force               = module.params["force"]
    service_name        = module.params["service_name"]

    if oracle_home:
        os.environ['ORACLE_HOME'] = oracle_home.rstrip('/')
    elif 'ORACLE_HOME' in os.environ:
        oracle_home = os.environ['ORACLE_HOME']
        module.params["oracle_home"] = oracle_home
    else:
        msg = 'ORACLE_HOME variable not set. Please set it and re-run the command'
        module.fail_json(msg=msg, changed=False)

    ohomes = oracle_homes()
    ohomes.list_crs_instances()
    ohomes.list_processes()
    ohomes.parse_oratab()
    #ohomes.oracle_gi_managed = False# TODO REMOVE - override GI presence for testing

    # Decide whether to use srvctl or sqlplus
    if ohomes.oracle_gi_managed:
        oc = None
    else:
        oc = oracleConnection(module)

    if not service_name:
        service_name = database_name

    if pdb and not service_name:
        service_name  = pdb
        database_name = pdb

    if state in ('present', 'started', 'stopped'):
        if not check_service_exists(oc, module, msg, name, database_name):
            if create_service(oc, module, msg):
                newservice = True
                ensure_service_state(oc, module, msg, name, database_name, state, preferred_instances,available_instances, pdb, role, clbgoal, rlbgoal)
            else:
                module.fail_json(msg=msg, changed=False)
        else:
            ensure_service_state(oc, module, msg, name, database_name, state, preferred_instances,available_instances, pdb, role, clbgoal, rlbgoal)
            # msg = 'Service %s already exists in database %s' % (name, database_name)
            # module.exit_json(msg=msg, changed=False)

    elif state == 'absent':
        if check_service_exists(oc, module, msg, name, database_name):
            if remove_service(oc, module, msg, name, database_name, force):
                msg = 'Service %s (%s) successfully removed' % (name, database_name)
                module.exit_json(msg=msg, changed=True)
            else:
                module.exit_json(msg=msg, changed=False)
        else:
            msg = 'Service %s (%s) doesn\'t exist' % (name, database_name)
            module.exit_json(msg=msg, changed=False)

    # elif state == 'started':
    #     if start_service(oc, module, msg, name, database_name):
    #         msg = "Service %s started successfully in database %s" % (name, database_name)
    #         module.exit_json(msg=msg, changed=True)
    #     else:
    #         msg = "Service %s already running in database %s" % (name, database_name)
    #         module.exit_json(msg=msg, changed=False)
    #
    # elif state == 'stopped':
    #     if stop_service(oc, module, msg, name, database_name):
    #         msg = "Service %s stopped successfully in database %s" % (name, database_name)
    #         module.exit_json(msg=msg, changed=True)
    #     else:
    #         msg = "Service %s already stopped in database %s" % (name, database_name)
    #         module.exit_json(msg=msg, changed=False)

    elif state == 'restarted':
        if stop_service(oc, module, msg, name, database_name):
            if start_service(oc, module, msg, name, database_name):
                msg = "Service %s restarted in database %s" % (name, database_name)
                module.exit_json(msg=msg, changed=True)
            else:
                module.fail_json(msg=msg, changed=True)
        else:
            module.fail_json(msg=msg, changed=True)

    elif state == 'status':
        if check_service_exists(oc, module, msg, name, database_name):
            if check_service_status(oc, module, msg, name, database_name,state):
                msg = 'Service %s is running in database %s' % (name, database_name)
                module.exit_json(msg=msg, changed=False)
            else:
                msg = 'Service %s is not running in database %s' % (name, database_name)
                module.exit_json(msg=msg, changed=False)
        else:
            msg = "Service %s doesn\'t exist in database %s" % (name, database_name)
            module.exit_json(msg=msg, changed=False)
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
