#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_db
short_description: Manage an Oracle database
description:
  - Create/delete a database using dbca
  - Stop/Start database
  - If a responsefile is available, it will be used. If initparams is defined, those will be attached to the createDatabase command
  - If no responsefile is created, the database will be created based on all other parameters
version_added: "3.0.0"
options:
  oracle_home:
    description:
      - The home where the database will be created
      - If not provided, environment variable ORACLE_HOME has to be set
    required: False
    aliases: ['oh']
  sid:
    description:
      - "Sid(System identifier) of newly created database"
      - "NOTE: Database can have SID, DB_NAME, DB_UNIQUE_NAME and Cluster resource name. DBCA is quite cryptic when generating these names"
      - "When sid is omitted, db_name=TESTDB, db_unique_name=TESTDB_LA, ORACLE_SID becomes TESTDBLA1, Cluster resource name becomes testdb_la"
      - "db_unique_name has precedence over db_name when sid is not specified"
    required: False
    aliases: ['oracle_sid']  
  db_name:
    description: The name of the database
    required: True
    aliases: ['db', 'database_name', 'name']
  db_unique_name:
    description: The database db_unique_name
    required: False
    default: None
    aliases: ['dbunqn', 'unique_name']
  sys_password:
    description: Password for the sys user
    required: False
    default: None
    aliases: ['syspw', 'sysdbapassword', 'sysdbapw']
  system_password:
    description:
      - Password for the system user
      - If not set, defaults to sys_password
    required: False
    default: None
    aliases: ['systempw']
  dbsnmp_password:
    description:
      - Password for the dbsnmp user
      - If not set, defaults to sys_password
    required: False
    default: None
    aliases: ['dbsnmppw']
  responsefile:
    description: The name of responsefile
    required: True
    default: None
  template:
    description: The template the database will be based off
    required: False
    default: General_Purpose.dbc
  db_options:
    required: False
    type: dict
    description:
      - "JSERVER: true"
      - "ORACLE_TEXT:false"
      - "IMEDIA: false"
      - "CWMLITE: false"
      - "SPATIAL: false"
      - "OMS: false"
      - "APEX: false"
      - "DV: false"
  listeners:
    required: False
    default: None
    description: ...
  cdb:
    description: Should the database be a container database
    required: False
    default: False
    aliases: ['container']
    type: bool
  datafile_dest:
    description: Where the database files should be placed (ASM diskgroup or filesystem path)
    required: True
    aliases: ['dfd']
  recoveryfile_dest:
    description: Where the database files should be placed (ASM diskgroup or filesystem path)
    required: False
    default: None
    aliases: ['rfd']
  storage_type:
    description: Type of underlying storage (Filesystem or ASM)
    required: False
    default: FS
    aliases: ['storage']
    choices: ['FS', 'ASM']
  omf:
    description: Use OMF (Oracle manageded files)
    required: False
    default: True
    type: bool
  dbconfig_type:
    description: Type of database (SI,RAC,RON)
    required: False
    default: SI on standalone, RAC on clustered environment
    choices: ['SI', 'RAC', 'RACONENODE']
  db_type:
    description: Default Type of database (MULTIPURPOSE, OLTP, DATA_WAREHOUSING)
    required: False
    default: MULTIPURPOSE
    choices: ['MULTIPURPOSE', 'OLTP', 'DATA_WAREHOUSING']
  racone_service:
    description:
      - If dbconfig_type = RACONENODE, a service has to be created along with the DB. This is the name of that service
      - If no name is defined, the service will be called "{{ db_name }}_ronserv"
    required: False
    default: None
    aliases: ['ron_service']
  characterset:
    description: The database characterset
    required: False
    default: AL32UTF8
  memory_percentage:
    description: The database total memory in % of available memory
    required: False
  memory_totalmb:
    description: The database total memory in MB. Defaults to 2G
    required: False
    default: ['2048']
  nodelist:
    description: The list of nodes a RAC DB should be created on
    default: On RAC cluster default value is a list of all nodes
    required: False
  amm:
    description: Should Automatic Memory Management be used (memory_target, memory_max_target)
    required: False
    default: False
    choices: ['True', 'False']
  initparams:
    required: False
    type: dict
    description:
      - "List of key=value pairs"
      - 'e.g. initparams: { "sga_target": "1GB", "sga_max_size": "1GB" }'
  customscripts:
    description:
      - "List of scripts to run after database is created"
      - "e.g customScripts: [/tmp/xxx.sql, /tmp/yyy.sql]"
    required: False
  default_tablespace_type:
    description: Database default tablespace type (DEFAULT_TBS_TYPE)
    default: bigfile
    choices: ['smallfile', 'bigfile']
  default_tablespace:
    description: Database default permanent tablespace (DEFAULT_PERMANENT_TABLESPACE)
    default: None
    required: False
  default_temp_tablespace:
    description: Database default temporary tablespace (DEFAULT_TEMP_TABLESPACE)
    default: None
    required: False
  archivelog:
    description: Puts the database is archivelog mode
    required: False
    default: False
    choices: ['True', 'False']
    type: bool
  force_logging:
    description: Enables force logging for the Database
    required: False
    default: False
    choices: ['True', 'False']
    type: bool
  supplemental_logging:
    description: Enables supplemental (minimal) logging for the Database (basically 'add supplemental log data')
    required: False
    default: False
    choices: ['True', 'False']
    type: bool
  flashback:
    description: Enables flashback for the database
    required: False
    default: False
    choices: ['True', 'False']
    type: bool
  state:
    description: The intended state of the database
    default: present
    choices: ['present', 'absent', 'stopped', 'started', 'restarted']
notes:
    - oracledb needs to be installed
    - 'Parameters initparams and db_options used to be of type list of strings ["JSERVER:true", "APEX:false"]'
    - 'Now they are a dictionary { "JSERVER": true, "APEX": false}'
requirements: ["oracledb"]
author: 
    - Mikael Sandström, oravirt@gmail.com, @oravirt
    - Ivan Brezina
'''

EXAMPLES = '''
- name: Create database
  oracle_db:
    oracle_home: '/oracle/u01/product/19.17.0.0'
    db_name: 'X01'
    db_unique_name: 'X01_A'
    sys_password: "{{ sys_password }}"
    #system_password:
    #dbsnmp_password:
    #template:
    db_options:
      JSERVER: True
      ORACLE_TEXT: False
      IMEDIA: False
      CWMLITE: False
      SPATIAL: False
      OMS: False
      APEX: False
      DV: False
    initparams:
      memory_target: 0
      memory_max_target: 0
      sga_target: 1500MB
      sga_max_size: 1500MB
    storage_type: ASM
    datafile_dest: +XDATA
    state: present
  become_user: oracle
  become: yes

- name: Drop database
  oracle_db:
    oracle_home: '/oracle/u01/product/19.17.0.0'
    db_name: 'X01'
    sys_password: "{{ sys_password }}"
    state: absent
'''

import os, re, time


def get_version(module, oracle_home):
    command = os.path.join(oracle_home, 'bin', 'sqlplus')
    (rc, stdout, stderr) = module.run_command([command, '-V'])
    if rc != 0:
        msg = 'Error - STDOUT: %s, STDERR: %s, COMMAND: %s' % (stdout, stderr, command)
        module.fail_json(msg=msg, changed=False)
    else:
        return stdout.split(' ')[2][0:4]


# Check if the database exists
def check_db_exists(module, ohomes):
    oracle_home    = module.params["oracle_home"]
    db_name        = module.params["db_name"]
    db_unique_name = module.params["db_unique_name"]

    sid = guess_oracle_sid(module, ohomes, fail=False)
    if sid:
        return True

    if ohomes.oracle_gi_managed:
        if db_unique_name:
            checkdb = db_unique_name
        else:
            checkdb = db_name
        srvctl = os.path.join(oracle_home, 'bin', 'srvctl')
        command = [srvctl, 'config', 'database', '-d', checkdb]
        (rc, stdout, stderr) = module.run_command(command)
        # module.warn("\n".join(command))
        # module.warn('srvctl config database: %s' % stdout)
        # module.warn('srvctl config database: %s' % stderr)
        # module.warn('srvctl config database: %s' % rc)
        if rc != 0:
            if 'PRCD-1229' in stdout: #<-- DB is created, but with a different ORACLE_HOME
                msg = 'Database %s already exists in a different home. Stdout -> %s' % (db_name, stdout)
                module.fail_json(msg=msg, changed=False)
            elif db_name in stdout: #<-- db doesn't exist
                # module.warn('Database %s does not exist' % checkdb)
                return False
            else:
                msg = 'Error: command is  %s. stdout is %s' % (command, stdout)
                # module.warn(msg)
                # module.warn('Database %s does not exist' % checkdb)
                return False
        elif 'Database name: {}'.format(db_name) in stdout: #<-- Database already exist
            # module.warn('Database {} does exist'.format(checkdb))
            return True
        else:
            msg = stdout
            # module.warn(msg)
            # module.warn('Database %s does exist' % checkdb)
            return True
    else:
        if db_name not in ohomes.facts_item.keys():
            return False

        current_oracle_home = ohomes.facts_item[db_name]['ORACLE_HOME']
        if current_oracle_home.rstrip('/') != oracle_home.rstrip('/'):
            msg = 'Database {} already exists in a different ORACLE_HOME ({})'.format(db_name, current_oracle_home)
            module.fail_json(msg=msg, changed=False)
        return True


def create_db(module, ohomes):
    oracle_home         = module.params["oracle_home"]
    db_name             = module.params["db_name"]
    db_unique_name      = module.params["db_unique_name"]
    sys_password        = module.params["sys_password"]
    system_password     = module.params["system_password"]
    dbsnmp_password     = module.params["dbsnmp_password"]
    responsefile        = module.params["responsefile"]
    template            = module.params["template"]
    db_options          = module.params["db_options"] or {}
    listeners           = module.params["listeners"]
    cdb                 = module.params["cdb"]
    local_undo          = module.params["local_undo"]
    datafile_dest       = module.params["datafile_dest"]
    omf                 = module.params["omf"]
    recoveryfile_dest   = module.params["recoveryfile_dest"]
    storage_type        = module.params["storage_type"]
    dbconfig_type       = module.params["dbconfig_type"]
    racone_service      = module.params["racone_service"]
    characterset        = module.params["characterset"]
    memory_percentage   = module.params["memory_percentage"]
    memory_totalmb      = module.params["memory_totalmb"]
    nodelist            = module.params["nodelist"]
    db_type             = module.params["db_type"]
    amm                 = module.params["amm"]
    initparams          = module.params["initparams"] or {}
    customscripts       = module.params["customscripts"]
    domain              = module.params["domain"]

    # Get the Oracle version
    major_version = get_version(module, oracle_home)

    for i in initparams:
        if i.lower().startswith('sga_target'):
            skip_memory = True
            break
        if i.lower().startswith('memory_target'):
            skip_memory = True
            break
    else:
        skip_memory = False

    # Override dbconfig_type on RAC when not specified
    if not dbconfig_type and ohomes.oracle_crs:
        module.params['dbconfig_type'] = dbconfig_type = 'RAC'

    if not nodelist and dbconfig_type == 'RAC':
        olsnodes_bin = os.path.join(os.path.dirname(ohomes.crsctl), 'olsnodes')
        (rc, stdout, stderr) = module.run_command(olsnodes_bin)
        if rc == 0:
            nodelist = stdout.splitlines()
            module.params['nodelist'] = nodelist
        else:
            module.fail_json(msg="Error executing olsnodes, {}, {}".format(stdout, stderr),
                             changed=True, stdout=stdout, stderr=stderr)

    command = "%s/bin/dbca -createDatabase -silent " % oracle_home
    if responsefile is not None:
        if os.path.exists(responsefile):
            command += ' -responseFile %s ' % responsefile
        else:
            msg="Responsefile %s doesn't exist" % responsefile
            module.fail_json(msg=msg, changed=False)

    if dbconfig_type == 'RAC' and nodelist:
        nodelist = ",".join(nodelist)
        command += ' -nodelist %s ' % nodelist
    if template:
        command += ' -templateName \"%s\"' % template
    if db_options:
        # Convert dict to list of k:v pairs and then join it.
        command += ' -dbOptions ' + ",".join(["{}:{}".format(_[0], str(_[1]).lower()) for _ in db_options.items()])
    if listeners:
        command += ' -listeners %s' % listeners
    if major_version > '11.2':
        if cdb:
            command += ' -createAsContainerDatabase true '
            if local_undo:
                command += ' -useLocalUndoForPDBs true'
            else:
                command += ' -useLocalUndoForPDBs false'
        else:
            command += ' -createAsContainerDatabase false '
    if datafile_dest:
        command += ' -datafileDestination %s ' % datafile_dest
    if recoveryfile_dest:
        command += ' -recoveryAreaDestination %s ' % recoveryfile_dest
    if storage_type:
        command += ' -storageType %s ' % storage_type
    if omf and storage_type == 'FS':
        command += ' -useOMF %s ' % str(omf).lower()
    if dbconfig_type == 'SI':
        dbconfig_type = 'SINGLE'
    if dbconfig_type:
        if major_version == '12.1':
            command += ' -databaseConfType %s ' % dbconfig_type
        else:
            command += ' -databaseConfigType %s ' % dbconfig_type
    if dbconfig_type == 'RACONENODE':
        if racone_service is None:
            racone_service = db_name+'_ronserv'
        command += ' -RACOneNodeServiceName %s ' % racone_service
    if characterset:
        command += ' -characterSet %s ' % characterset
    if memory_percentage and not skip_memory:
        command += ' -memoryPercentage %s ' % memory_percentage
    if memory_totalmb and not skip_memory:
        command += ' -totalMemory %s ' % memory_totalmb
    if db_type:
        command += ' -databaseType %s ' % db_type
    if amm:
        if major_version == '12.2':
            if amm:
                command += ' -memoryMgmtType AUTO '
            else:
                command += ' -memoryMgmtType AUTO_SGA '
        elif major_version == '12.1':
            command += ' -automaticMemoryManagement %s ' % (str(amm).lower())
        elif major_version == '11.2':
            if amm:
                command += ' -automaticMemoryManagement '
    elif not amm and major_version.startswith('19'):
        command += ' -memoryMgmtType AUTO_SGA '
            
    if customscripts:
        scriptlist = ",".join(customscripts)
        command += ' -customScripts %s ' % scriptlist

    command += ' -gdbName %s' % db_name

    if sys_password:
        command += ' -sysPassword \"%s\"' % sys_password
    if system_password:
        command += ' -systemPassword \"%s\"' % system_password
    else:
        if responsefile and os.path.exists(responsefile):
            with open(responsefile) as rspfile:
                for line in rspfile:
                    if re.match('systemPassword=.+', line):
                        break
                else:
                    system_password = sys_password # set system_password to sys_password when system password was not suplied
        else:
            system_password = sys_password
        command += ' -systemPassword \"%s\"' % system_password
    if dbsnmp_password:
        command += ' -dbsnmpPassword \"%s\"' % dbsnmp_password
    else:
        dbsnmp_password = sys_password
        command += ' -dbsnmpPassword \"%s\"' % dbsnmp_password

    sid = module.params["sid"]
    if sid:
        command += ' -sid %s' % sid

    paramslist = dict()
    if db_unique_name:
        # DBCA Silent Mode Is Not Setting DB_UNIQUE_NAME Even Though It Is Specified In DBCA Template File. (Doc ID 1508337.1)
        # The workaround is to set the DB_UNIQUE_NAME in the command line parameter '-initParams db_unique_name=<a value>', e.g.
        # TODO SID parameter?
        # https://community.oracle.com/mosc/discussion/4328864/dbca-create-database-with-db-name-db-unique-name
        paramslist.update({'db_name': db_name})
        paramslist.update({'db_unique_name': db_unique_name})

    if domain:
        paramslist.update({'db_domain': domain})

    if initparams:
        paramslist.update(initparams)

    if paramslist:
        # Convert dict to list of k:v pairs and then join it.
        command += ' -initParams ' + ",".join(["{}={}".format(_[0], str(_[1])) for _ in paramslist.items()])

    msg = "command: %s" % command
    module.warn(msg)
    env = {'ORACLE_HOME': oracle_home, 'PATH': '%s/bin/:/bin:/sbin:/usr/bin:/usr/sbin' % oracle_home}
    (rc, stdout, stderr) = module.run_command(command, environ_update=env)
    # module.warn('dcdba: %s ' % stdout)
    # module.warn('dcdba: %s ' % stderr)
    # module.warn('dcdba: %s ' % rc)
    if rc != 0:
        msg = 'Error - STDOUT: %s, STDERR: %s, COMMAND: %s' % (stdout, stderr, command)
        module.fail_json(msg=msg, changed=True, stdout=stdout, stderr=stderr)
    else:
        return 'STDOUT: %s, STDERR: %s COMMAND: %s' % (stdout, stderr, command)


def remove_db(module, ohomes):
    oracle_home = module.params["oracle_home"]
    db_name = module.params["db_name"]
    db_unique_name = module.params["db_unique_name"] or ''
    sys_password = module.params["sys_password"]

    sid = guess_oracle_sid(module, ohomes)
    if ohomes.oracle_gi_managed:
        if db_unique_name:
            db_to_remove = db_unique_name
        else:
            db_to_remove = db_name
    else:
        db_to_remove = db_name

    dbca = os.path.join(oracle_home, 'bin', 'dbca')
    command = [dbca, '-deleteDatabase', '-silent', '-sourceDB', db_to_remove, '-sysDBAUserName', 'sys', '-sysDBAPassword', sys_password]
    (rc, stdout, stderr) = module.run_command(command)
    if 0 < rc <= 6:
        module.warn(stdout)
        module.warn(stdout)
    if rc <= 6:
        msg = 'STDOUT: %s,  COMMAND: %s' % (stdout, command)
        msg = 'Successfully removed database %s' % db_name
        module.exit_json(msg=msg, changed=True, stdout=stdout, stderr=stderr)
    else:
        msg = 'Removal of database %s failed: %s' % (db_name, stdout)
        module.fail_json(msg=msg, changed=True, stdout=stdout, stderr=stderr)


def guess_oracle_sid(module, ohomes, fail=True):
    db_name = module.params["db_name"]
    db_unique_name = module.params["db_unique_name"] or ''

    db_unique_name = db_unique_name.replace('_', '')

    if 'ORACLE_SID' in os.environ:
        return os.environ['ORACLE_SID']

    # Try to guess what ORACLE_SID of newly created database is
    if 'ORACLE_SID' not in os.environ:
        if db_name in ohomes.facts_item:
            os.environ['ORACLE_SID'] = db_name
            return db_name
        elif ohomes.oracle_crs:
            for sid in ohomes.facts_item.keys():
                # check if sid = db_name + digit
                if sid.startswith(db_name) and len(sid) == len(db_name) + 1 and bool(re.search(r'\d+$', sid)):
                    os.environ['ORACLE_SID'] = sid
                    return sid
                # ORACLE_SID for database unique name TESTRAC_B is TESTRACB1 when -sid is not passed to dbca
                if sid.startswith(db_unique_name) and len(sid) == len(db_unique_name) + 1 and bool(re.search(r'\d+$', sid)):
                    os.environ['ORACLE_SID'] = sid
                    return sid

    if fail:
        module.fail_json("Could not deduce ORACLE_SID for db_name: {}".format(db_name))


def ensure_db_state(module, ohomes, newdb):
    # module.warn('ensure_db_state')
    db_name        = module.params["db_name"]
    archivelog     = module.params["archivelog"]
    force_logging  = module.params["force_logging"]
    flashback      = module.params["flashback"]
    supplemental_logging = module.params["supplemental_logging"]
    default_tablespace_type = module.params["default_tablespace_type"].upper()
    default_tablespace = module.params["default_tablespace"]
    default_temp_tablespace = module.params["default_temp_tablespace"]
    timezone       = module.params["timezone"]

    wanted_set = set()
    wanted_set.add(('log_mode', "ARCHIVELOG" if archivelog else "NOARCHIVELOG"))
    wanted_set.add(('force_logging', "YES" if force_logging else "NO"))
    wanted_set.add(('flashback_on', "YES" if flashback else "NO"))
    wanted_set.add(('supplemental_logging', "YES" if supplemental_logging else "NO"))
    wanted_set.add(('DEFAULT_TBS_TYPE', default_tablespace_type))
    if default_tablespace:
        wanted_set.add(('DEFAULT_PERMANENT_TABLESPACE', default_tablespace_type))
    if default_temp_tablespace:
        wanted_set.add(('DEFAULT_TEMP_TABLESPACE', default_temp_tablespace))
    if timezone:
        wanted_set.add(('timezone', timezone))

    sid = guess_oracle_sid(module, ohomes)
    conn = oracleConnection(module)

    propsql = """
    select property_name, property_value 
    from database_properties 
    where property_name in ('DEFAULT_TBS_TYPE','DEFAULT_PERMANENT_TABLESPACE','DEFAULT_TEMP_TABLESPACE', 'DBTIMEZONE') 
    order by 1"""

    result = conn.execute_select(propsql, {}, fetchone=False)
    db_parameters = dict(result)

    #tzsql = "select property_value from database_properties where property_name = 'DBTIMEZONE'"

    curr_time_zone = db_parameters['DBTIMEZONE'].upper()
    def_tbs_type   = db_parameters['DEFAULT_TBS_TYPE'].upper()
    def_tbs        = db_parameters['DEFAULT_PERMANENT_TABLESPACE'].upper()
    def_temp_tbs   = db_parameters['DEFAULT_TEMP_TABLESPACE'].upper()

    # def_tbs_type,def_tbs,def_temp_tbs = execute_sql_get(module, cursor, propsql)

    israc_sql = 'select parallel, instance_name, host_name from v$instance'
    result = conn.execute_select_to_dict(israc_sql, {}, fetchone=True)
    db_parameters.update(result)
    instance_name = db_parameters['instance_name']
    israc = bool(db_parameters['parallel'] == 'YES')
    ohomes.facts_item[sid]['israc'] = israc
    change_restart_sql = []
    change_db_sql = []

    # NOTE: No column SUPPLEMENTAL_LOG_DATA_SR in 12.2 database
    supp_log_check_sql = """
        select SUPPLEMENTAL_LOG_DATA_MIN
        ,SUPPLEMENTAL_LOG_DATA_PL
        ,SUPPLEMENTAL_LOG_DATA_SR
        ,SUPPLEMENTAL_LOG_DATA_PK
        ,SUPPLEMENTAL_LOG_DATA_UI from v$database
    """
    supp_log_check_sql = 'select SUPPLEMENTAL_LOG_DATA_MIN from v$database'
    log_check_sql = 'select log_mode, force_logging, flashback_on from v$database'

    log_sql = 'select SUPPLEMENTAL_LOG_DATA_MIN as supplemental_logging, log_mode, force_logging, flashback_on from v$database'
    result = conn.execute_select_to_dict(log_sql, {}, fetchone=True)
    db_parameters.update(result)
    c_supplemental_log_data_min = db_parameters['supplemental_logging']
    c_log_mode      = db_parameters['log_mode']
    c_force_logging = db_parameters['force_logging']
    c_flashback_on  = db_parameters['flashback_on']

    #supp_log_check_ = execute_sql_get(module, cursor, supp_log_check_sql)
    #log_check_ = execute_sql_get(module, cursor, log_check_sql)

    if archivelog:
        archcomp = 'ARCHIVELOG'
        archsql = 'alter database archivelog'
    else:
        archcomp = 'NOARCHIVELOG'
        archsql = 'alter database noarchivelog'

    if force_logging:
        flcomp = 'YES'
        flsql = 'alter database force logging'
    else:
        flcomp = 'NO'
        flsql = 'alter database no force logging'

    if flashback:
        fbcomp = 'YES'
        fbsql = 'alter database flashback on'
    else:
        fbcomp = 'NO'
        fbsql = 'alter database flashback off'

    if supplemental_logging:
        slcomp = 'YES'
        slsql = 'alter database add supplemental log data'
    else:
        slcomp = 'NO'
        slsql = 'alter database drop supplemental log data'

    if def_tbs_type != default_tablespace_type:
        deftbstypesql = 'alter database set default %s tablespace ' % default_tablespace_type
        change_db_sql.append(deftbstypesql)

    if default_tablespace and def_tbs != default_tablespace.upper():
        deftbssql = 'alter database default tablespace %s' % default_tablespace
        change_db_sql.append(deftbssql)

    if default_temp_tablespace and def_temp_tbs != default_temp_tablespace.upper():
        deftempsql = 'alter database default temporary tablespace %s' % default_temp_tablespace
        change_db_sql.append(deftempsql)

    if timezone and curr_time_zone != timezone.upper():
        deftzsql = "alter database set time_zone = '%s'" % timezone
        change_db_sql.append(deftzsql)

    if c_log_mode != archcomp:
        change_restart_sql.append(archsql)

    if c_force_logging != flcomp:
        change_db_sql.append(flsql)

    if c_flashback_on != fbcomp:
        change_db_sql.append(fbsql)

    if c_supplemental_log_data_min != slcomp:
        change_db_sql.append(slsql)

    changes = wanted_set.difference(set(db_parameters.items()))

    if change_db_sql or change_restart_sql:
        return_ddls = []
        # Flashback database needs to be turned off before archivelog is turned off
        if c_log_mode == 'ARCHIVELOG' and c_flashback_on == 'YES' and not archivelog and not flashback:
            # <- Apply changes that does not require a restart
            if change_db_sql:
                ddls = apply_norestart_changes(module, change_db_sql)
                return_ddls.append(ddls)

            # <- Apply changes that requires database in mount state
            if change_restart_sql:
                ddls = apply_restart_changes(module, ohomes, instance_name, change_restart_sql)
                return_ddls.append(ddls)
        else:
            # <- Apply changes that requires database in mount state
            if change_restart_sql:
                ddls = apply_restart_changes(module, ohomes, instance_name, change_restart_sql)
                return_ddls.append(ddls)
            # <- Apply changes that does not require a restart
            if change_db_sql:
                ddls = apply_norestart_changes(module, change_db_sql)
                return_ddls.append(ddls)

        msg = 'Database %s has been put in the intended state - Archivelog: %s, Force Logging: %s, Flashback: %s, Supplemental Logging: %s, Timezone: %s' %\
                (db_name, archivelog, force_logging, flashback, supplemental_logging, timezone)
        module.exit_json(msg=msg, changed=True, ddls=return_ddls)
    else:
        if newdb:
            msg = 'Database %s successfully created created (%s) ' % (db_name, archcomp)
        else:
            msg = 'Database %s already exists and is in the intended state - Archivelog: %s, Force Logging: %s, Flashback: %s, Supplemental Logging: %s, Timezone: %s' %\
                    (db_name, archivelog, force_logging, flashback, supplemental_logging, timezone)
        module.exit_json(msg=msg, changed=newdb)


def apply_restart_changes(module, ohomes, instance_name, change_restart_sql):
    stop_db(module, ohomes)
    start_instance(module, ohomes, 'mount', instance_name)
    time.sleep(10) #<- To allow the DB to register with the listener
    conn = oracleConnection(module)

    for sql in change_restart_sql:
        conn.execute_ddl(sql)
    stop_db(module, ohomes)
    start_db(module, ohomes)
    return conn.ddls


def apply_norestart_changes(module, change_db_sql):
    conn = oracleConnection(module)
    for sql in change_db_sql:
        conn.execute_ddl(sql)
    return conn.ddls


def stop_db(module, ohomes):
    oracle_home    = module.params["oracle_home"]
    db_name        = module.params["db_name"]
    db_unique_name = module.params["db_unique_name"]
    sid = guess_oracle_sid(module, ohomes)
    if ohomes.oracle_gi_managed:
        crsname = ohomes.facts_item[sid]['crsname']
        if not crsname and db_unique_name:
            crsname = db_unique_name
        if not crsname:
            crsname = db_name
        srvctl = os.path.join(oracle_home, 'bin', 'srvctl')
        command = [srvctl, 'stop', 'database', '-d', crsname, '-o', 'immediate']
        (rc, stdout, stderr) = module.run_command(command)
        if rc != 0 or stdout.startswith('PRCD-') or stderr.startswith('PRCD-'):
            msg = 'Error - STDOUT: %s, STDERR: %s, COMMAND: %s' % (stdout, stderr, " ".join(command))
            module.fail_json(msg=msg, changed=False)
    else:
        os.environ['ORACLE_SID'] = sid
        shutdown_sql = '''
        connect / as sysdba
        shutdown immediate;
        exit
        '''
        sqlplus_bin = os.path.join(oracle_home, 'bin', 'sqlplus')
        p = subprocess.Popen([sqlplus_bin, '/nolog'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate(shutdown_sql.encode('utf-8'))
        rc = p.returncode
        if rc != 0:
            msg = 'Error - STDOUT: %s, STDERR: %s, COMMAND: %s' % (stdout, stderr, shutdown_sql)
            module.fail_json(msg=msg, changed=False)


def start_db(module, ohomes):
    oracle_home    = module.params["oracle_home"]
    db_name        = module.params["db_name"]
    db_unique_name = module.params["db_unique_name"]
    sid = guess_oracle_sid(module, ohomes)

    if ohomes.oracle_gi_managed:
        crsname = ohomes.facts_item[sid]['crsname']
        if not crsname and db_unique_name:
            crsname = db_unique_name
        if not crsname:
            crsname = db_name
        srvctl = os.path.join(oracle_home, 'bin', 'srvctl')
        command = [srvctl, 'start', 'database', '-d', crsname]
        (rc, stdout, stderr) = module.run_command(command)
        if rc != 0 or stdout.startswith('PRCD') or stderr.startswith('PRCD'):
            msg = 'Error - STDOUT: %s, STDERR: %s, COMMAND: %s' % (stdout, stderr, " ".join(command))
            module.fail_json(msg=msg, changed=True, stdout=stdout, stderr=stderr)
    else:
        os.environ['ORACLE_SID'] = sid
        startup_sql = '''
        connect / as sysdba
        startup;
        exit
        '''
        sqlplus_bin = os.path.join(oracle_home, 'bin', 'sqlplus')
        p = subprocess.Popen([sqlplus_bin, '/nolog'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate(startup_sql.encode('utf-8'))
        rc = p.returncode
        if rc != 0:
            msg = 'Error - STDOUT: %s, STDERR: %s, COMMAND: %s' % (stdout, stderr, startup_sql)
            module.fail_json(msg=msg, changed=True, stdout=stdout, stderr=stderr)


def start_instance(module, ohomes, open_mode, instance_name):
    oracle_home    = module.params["oracle_home"]
    db_name        = module.params["db_name"]
    db_unique_name = module.params["db_unique_name"]
    sid = guess_oracle_sid(module, ohomes)

    if ohomes.oracle_gi_managed:
        crsname = ohomes.facts_item[sid]['crsname']
        if not crsname and db_unique_name:
            crsname = db_unique_name
        if not crsname:
            crsname = db_name

        srvctl = os.path.join(oracle_home, 'bin', 'srvctl')
        if ohomes.facts_item[sid]['israc']:
            command = [srvctl, 'start', 'instance', '-d', crsname, '-i', instance_name]
        else:
            command = [srvctl, 'start', 'database', '-d', crsname]
        if open_mode:
            command.extend(['-o', open_mode])
        (rc, stdout, stderr) = module.run_command(command)
        if rc != 0:
            msg = 'Error - STDOUT: %s, STDERR: %s, COMMAND: %s' % (stdout, stderr, " ".join(command))
            module.fail_json(msg=msg, changed=False)
    else:
        os.environ['ORACLE_SID'] = sid
        if open_mode == 'mount':
            startup_sql = '''
            connect / as sysdba
            startup mount;
            exit
            '''
        else:
            startup_sql = '''
            connect / as sysdba
            startup;
            exit
            '''
        sqlplus_bin = os.path.join(oracle_home, 'bin', 'sqlplus')
        p = subprocess.Popen([sqlplus_bin, '/nolog'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate(startup_sql.encode('utf-8'))
        rc = p.returncode
        if rc != 0:
            msg = 'Error - STDOUT: %s, STDERR: %s, COMMAND: %s' % (stdout, stderr, startup_sql)
            module.fail_json(msg=msg, changed=False)


def main():
    module = AnsibleModule(
        argument_spec = dict(
            oracle_home         = dict(default=None, aliases=['oh']),
            sid                 = dict(required=False, aliases=['oracle_sid']),
            db_name             = dict(required=True, aliases=['db', 'database_name', 'name']),
            db_unique_name      = dict(required=False, aliases=['dbunqn', 'unique_name']),
            sys_password        = dict(required=False, no_log=True, aliases=['syspw', 'sysdbapassword', 'sysdbapw']),
            system_password     = dict(required=False, no_log=True, aliases=['systempw']),
            dbsnmp_password     = dict(required=False, no_log=True, aliases=['dbsnmppw']),
            responsefile        = dict(required=False),
            template            = dict(default='General_Purpose.dbc'),
            db_options          = dict(required=False, type='dict'),
            listeners           = dict(required=False, aliases=['listener']),
            cdb                 = dict(default=False, type='bool', aliases=['container']),
            local_undo          = dict(default=True, type='bool'),
            datafile_dest       = dict(required=False, aliases=['dfd']),
            recoveryfile_dest   = dict(required=False, aliases=['rfd']),
            storage_type        = dict(default='FS', aliases=['storage'], choices=['FS', 'ASM']),
            omf                 = dict(default=True, type='bool'),
            dbconfig_type       = dict(default=None, choices=['SI', 'RAC', 'RACONENODE']),
            db_type             = dict(default='MULTIPURPOSE', choices=['MULTIPURPOSE', 'DATA_WAREHOUSING', 'OLTP']),
            racone_service      = dict(required=False, aliases=['ron_service']),
            characterset        = dict(default='AL32UTF8'),
            memory_percentage   = dict(required=False),
            memory_totalmb      = dict(default='2048'),
            nodelist            = dict(required=False, type='list'),
            amm                 = dict(default=False, type='bool', aliases=['automatic_memory_management']),
            initparams          = dict(required=False, type='dict'),
            customscripts       = dict(required=False, type='list'),
            default_tablespace_type = dict(default='bigfile', choices=['smallfile', 'bigfile']),
            default_tablespace  = dict(required=False),
            default_temp_tablespace = dict(required=False),
            archivelog          = dict(default=False, type='bool'),
            force_logging       = dict(default=False, type='bool'),
            supplemental_logging = dict(default=False, type='bool'),
            flashback           = dict(default=False, type='bool'),
            domain              = dict(required=False),
            timezone            = dict(required=False),
            state               = dict(default="present", choices=["present", "absent", "started", "stopped", "restarted"])
        ),
        mutually_exclusive=[['memory_percentage', 'memory_totalmb']],
        supports_check_mode=False,
        required_if=[
            ["state", "present", ["datafile_dest", "sys_password"]],
            ["state", "absent", ["sys_password"]]
        ]
    )

    oracle_home         = module.params["oracle_home"]
    db_name             = module.params["db_name"]
    db_unique_name      = module.params["db_unique_name"]
    domain              = module.params["domain"]
    state               = module.params["state"]

    # Dummy module params to make oracleConnection class happy
    module.params["hostname"] = None
    module.params["port"] = None
    module.params["user"] = None
    module.params["password"] = None
    module.params["mode"] = 'sysdba'

    if oracle_home:
        os.environ['ORACLE_HOME'] = oracle_home.rstrip('/')
    elif 'ORACLE_HOME' in os.environ:
        oracle_home = os.environ['ORACLE_HOME']
        module.params["oracle_home"] = oracle_home
    else:
        msg = 'ORACLE_HOME variable not set. Please set it and re-run the command'
        module.fail_json(msg=msg, changed=False)

    # Unset ORACLE_SID, we will deduce it later, this should fix RAC deployments
    os.environ.pop('ORACLE_SID', None)

    ohomes = oracle_homes()
    ohomes.list_crs_instances()
    ohomes.list_processes()
    ohomes.parse_oratab()
    #ohomes.oracle_gi_managed = False# TODO REMOVE - override GI presence for testing

    # Connection details for database
    if db_unique_name:
        service_name = db_unique_name
    else:
        service_name = db_name

    if domain:
        service_name = "%s.%s" % (service_name, domain)

    module.params["service_name"] = service_name
    # module.warn("service_name {}".format(service_name))

    if state == 'started':
        sid = guess_oracle_sid(module, ohomes)
        msg = "oracle_home: %s db_name: %s sid: %s db_unique_name: %s" % (oracle_home, db_name, sid, db_unique_name)
        if not check_db_exists(module, ohomes):
            msg = "Database not found. %s" % msg
            module.fail_json(msg=msg, changed=False)
        elif ohomes.facts_item[sid]['running']:
            module.exit_json(msg="Database is already running", changed=False)
        else:
            start_db(module, ohomes)
            module.exit_json(msg="Database started", changed=True)

    if state == 'stopped':
        sid = guess_oracle_sid(module, ohomes)
        msg = "oracle_home: %s db_name: %s sid: %s db_unique_name: %s" % (oracle_home, db_name, sid, db_unique_name)
        if not check_db_exists(module, ohomes):
            msg = "Database not found. %s" % msg
            module.fail_json(msg=msg, changed=False)
        elif not ohomes.facts_item[sid]['running']:
            module.exit_json(msg="Database is already stopped", changed=False)
        else:
            stop_db(module, ohomes)
            module.exit_json(msg="Database stopped", changed=True)

    if state == 'restarted':
        sid = guess_oracle_sid(module, ohomes)
        msg = "oracle_home: %s db_name: %s sid: %s db_unique_name: %s" % (oracle_home, db_name, sid, db_unique_name)
        if not check_db_exists(module, ohomes):
            msg = "Database not found. %s" % msg
            module.fail_json(msg=msg, changed=False)
        if ohomes.facts_item[sid]['running']:
            stop_db(module, ohomes)
        start_db(module, ohomes)
        module.exit_json(msg="Database restarted", changed=True)

    elif state == 'present':
        if not check_db_exists(module, ohomes):
            msg = create_db(module, ohomes)
            if 'WARNING' in msg:
                module.warn(msg)
            # Try to detect ORACLE_SID of the new running database
            ohomes.list_crs_instances()
            ohomes.list_processes()
            ohomes.parse_oratab()
            ensure_db_state(module, ohomes, newdb=True)
        else:
            ensure_db_state(module, ohomes, newdb=False)

    elif state == 'absent':
        if check_db_exists(module, ohomes):
            remove_db(module, ohomes)
        else:
            msg = "Database %s doesn't exist" % db_name
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
