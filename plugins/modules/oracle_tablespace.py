#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_tablespace
short_description: Manage tablespaces in an Oracle database
description:
  - Manage tablespaces in an Oracle database (create, drop, put in read only/read write, offline/online)
  - Can be run locally on the control machine or on a remote host
  - See connection parameters for oracle_ping    
version_added: "1.9.1"
options:
  tablespace:
    description: The tablespace that should be managed
    required: True
  state:
    description: The intended state of the tablespace
    default: present
    choices: ['present', 'absent', 'online', 'offline', 'read_only', 'read_write']
  bigfile:
    description: Should the tablespace be created as a bigfile tablespace
    default: True
    choices: ['True', 'False']
  datafile:
    description:
      - "Where to put the datafile. Can be an ASM diskgroup or a filesystem datafile (i.e '+DATA', '/u01/oradata/testdb/test01.dbf')"
      - mutually_exclusive with numfiles
    required: False
    aliases: ['df', 'path']
  numfiles:
    description:
      - "If OMF (db_create_file_dest) is set, you can just specify the number of datafiles you want attached to the tablespace"
      - "mutually_exclusive with datafile"
    required: False
  size:
    description: "The size of the datafile (10M, 10G, 150G etc)"
    required: False
    default: 100M
  content:
    description: "The type of tablespace (permanent, temporary or undo)"
    default: permanent
    choices: ['permanent', 'temp', 'undo']
  autoextend:
    description: Should the datafile be autoextended
    default: false
    choices: ['True','False']
  nextsize:
    description: "If autoextend, the size of the next extent allocated (1M, 50M, 1G etc)"
    aliases: ['next']
  maxsize:
    description: "If autoextend, the maximum size of the datafile (1M, 50M, 1G etc). If empty, defaults to database limits"
    aliases: ['max']
notes:
  - oracledb needs to be installed
requirements: [ "oracledb" ]
author:
  - Mikael Sandström, oravirt@gmail.com, @oravirt
  - Ivan Brezina
'''

EXAMPLES = '''
- name: USERS tablespace
  oracle_tablespace: 
    tablespace: test
    # use: db_create_file_dest parameter
    # datafile: '+DATA' 
    size: 100M
    state: present 
    bigfile: true 
    autoextend: true

- name: Drop a tablespace
  oracle_tablespace:
    mode: sysdba
    tablespace: test
    state: absent

- name: Make a tablespace read only
  oracle_tablespace:  
    mode: sysdba
    tablespace: test
    state: read_only

- name: Make a tablespace read write
  oracle_tablespace:
    mode: sysdba    
    tablespace: test
    state: read_write

- name: Make a tablespace offline
  oracle_tablespace:
    mode: sysdba
    tablespace: test
    state: offline

- name: Make a tablespace online
  oracle_tablespace:
    mode: sysdba    
    tablespace: test
    state: online

- name: create small file temp tablespace
  oracle_tablespace:
    mode: sysdba
    tablespace: "ts_temp"
    size: "2M"
    datafiles:
      - "/tmp/ts_temp1.dbf"
      - "/tmp/ts_temp2.dbf"
    state: "present"
    bigfile: no
    content: "temp"

- name: create tablespace
  oracle_tablespace:
    mode: sysdba
    tablespace: "ts"
    size: "1M"
    datafiles:
      - "/tmp/ts1.dbf"
    state: "present"
    bigfile: no
    
- name: add datafile
  oracle_tablespace:
    mode: sysdba    
    tablespace: "ts"
    size: "2M"
    datafiles:
      - "/tmp/ts2.dbf"
      - "/tmp/ts3.dbf"
    state: "present"
    bigfile: no
    autoextend: yes
    nextsize: "1M"
    maxsize: "10M"
'''


# Check if the tablespace exists
def check_tablespace_exists(conn, tablespace):
    sql = 'select tablespace_name, status from dba_tablespaces where tablespace_name = upper(:tablespace)'
    r = conn.execute_select_to_dict(sql, {"tablespace": tablespace}, fetchone=True)
    return set(r.items())


# Create the tablespace
def create_tablespace(conn, module):
    tablespace = module.params["tablespace"]
    state = module.params["state"]
    bigfile = module.params["bigfile"]
    datafile = module.params["datafile"]
    numfiles = module.params["numfiles"]
    size = module.params["size"]
    content = module.params["content"]
    autoextend = module.params["autoextend"]
    nextsize = module.params["nextsize"]
    maxsize = module.params["maxsize"]

    # Check if OMF is enabled
    checksql = 'select value from v$parameter where lower(name) = lower(:param)'
    r = conn.execute_select_to_dict(checksql, {"param": 'db_create_file_dest'}, fetchone=True)
    if r['value']:
        skip_datafile = True
    else:
        skip_datafile = False

    if numfiles is None:
        numfiles = 1

    if not autoextend and not maxsize:
        autoextend = True
        nextsize = '100M'
        maxsize = 'unlimited'
        # msg = 'Error: Missing parameter - size'
        # module.fail_json(msg=msg, changed=False)

    if bigfile and datafile is not None:
        if len(datafile)>1 or int(numfiles) > 1:
            msg='Only one datafile allowed in BIGFILE tablespace'
            module.fail_json(msg=msg, changed=False)

    if not datafile and skip_datafile:
        if autoextend and nextsize and not maxsize:
            datafile_list = ','.join(' size %s autoextend on next %s' % (size,nextsize) for d in range(int(numfiles)) )
        elif autoextend and nextsize and maxsize:
            datafile_list = ','.join(' size %s autoextend on next %s maxsize %s' % (size,nextsize,maxsize) for d in range(int(numfiles) ))
        else:
            datafile_list = ','.join(' size %s ' % (size) for d in range(int(numfiles) ))

        # If db_create_file_dest IS set, and we're missing the datafile datafile we CAN continue because of OMF
        if content == 'undo':
            if bigfile:
                sql = f'create bigfile undo tablespace {tablespace} datafile size {size}'
            else:
                sql = f'create undo tablespace {tablespace} datafile {datafile_list}'

        elif content == 'temp':
            if bigfile:
                sql = f'create bigfile temporary tablespace {tablespace} tempfile size {size}'
            else:
                sql = f'create temporary tablespace tablespace tempfile {datafile_list}'

        else:
            if bigfile:
                sql = f'create bigfile tablespace {tablespace} datafile size {size}'
            else:
                sql = f'create tablespace {tablespace} datafile  {datafile_list}'

        conn.execute_ddl(sql)
        return

    if not datafile and not skip_datafile:
        # If db_create_file_dest is NOT set, and we're missing the datafile datafile we can't continue
        msg = 'Error: Missing datafile name/datafile. Either set db_create_file_dest or specify one or more datafiles'
        module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)

    if datafile:
        # Everything is ok, tablespace + datafile provided so just continue
        if autoextend and not nextsize:
            module.fail_json(msg='Error: Missing NEXT size for autoextend',changed=False)
        elif autoextend and nextsize and not maxsize:
            datafile_list = ','.join('\''+ d + '\' size %s autoextend on next %s' % (size,nextsize) for d in datafile )
        elif autoextend and nextsize and maxsize:
            datafile_list = ','.join('\''+ d + '\' size %s autoextend on next %s maxsize %s' % (size,nextsize,maxsize) for d in datafile )
        else:
            datafile_list = ','.join('\''+ d + '\' size %s ' % (size) for d in datafile )

        if content == 'undo':
            if bigfile:
                sql = f'create bigfile undo tablespace {tablespace} datafile {datafile_list}'
            else:
                sql = f'create undo tablespace {tablespace} datafile {datafile_list}'

        elif content == 'temp':
            if bigfile:
                sql = f'create bigfile temporary tablespace {tablespace} tempfile {datafile_list}'
            else:
                sql = f'create temporary tablespace {tablespace} tempfile {datafile_list}'

        else:
            if bigfile:
                sql = f'create bigfile tablespace {tablespace} datafile {datafile_list}'
            else:
                sql = f'create tablespace {tablespace} datafile {datafile_list}'

        conn.execute_ddl(sql)
        return


def map_status(state, current_status):
    wanted_status = ''
    enforcesql = ''
    if state == 'read_only':
        wanted_status = 'READ ONLY'
        enforcesql = 'read only'
    elif state == 'read_write':
        if current_status == 'ONLINE':
            wanted_status = 'ONLINE'
            enforcesql = 'online'
        elif current_status == 'OFFLINE':
            wanted_status = 'ONLINE'
            enforcesql = 'online'
        else:
            wanted_status = 'ONLINE'
            enforcesql = 'read write'
    elif state == 'online':
        wanted_status = 'ONLINE'
        enforcesql = 'online'
    if state == 'present':
        if current_status == 'READ ONLY':
            wanted_status = 'ONLINE'
            enforcesql = 'read write'
        elif current_status == 'OFFLINE':
            wanted_status = 'ONLINE'
            enforcesql = 'online'
        elif current_status == 'ONLINE':
            wanted_status = 'ONLINE'
            enforcesql = 'online'
    elif state == 'offline':
        wanted_status = 'OFFLINE'
        enforcesql = 'offline'

    return wanted_status, enforcesql

def ensure_tablespace_state (conn, module, tbs_just_created=False):
    if module.check_mode and tbs_just_created:
        # Nothing to do here, do not fail i check mode
        return

    tablespace = module.params["tablespace"]
    state = module.params["state"]
    bigfile = module.params["bigfile"]
    datafile = module.params["datafile"]
    numfiles = module.params["numfiles"]
    size = module.params["size"]
    content = module.params["content"]
    autoextend = module.params["autoextend"]
    nextsize = module.params["nextsize"]
    maxsize = module.params["maxsize"]

    alter_tbs_list = []
    wanted_list_dbf = []

    #module.exit_json(msg=alter_tbs_list, changed=False)
    checksql = 'select value from v$parameter where lower(name) = lower(:param)'
    r = conn.execute_select_to_dict(checksql, {"param": 'db_create_file_dest'}, fetchone=True)
    if r['value']:
        skip_datafile = True
    else:
        skip_datafile = False

    if content == 'temp':
        (dftype, dfsource, tbstype) = ('tempfile', 'dba_temp_files', 'Temporary tablespace')
    elif content == 'undo':
        (dftype, dfsource, tbstype) = ('datafile', 'dba_data_files', 'Undo tablespace')
    elif content == 'permanent':
        (dftype, dfsource, tbstype) = ('datafile', 'dba_data_files', 'Tablespace')

    statussql = 'select status from dba_tablespaces where tablespace_name = upper(:tablespace)'
    r = conn.execute_select_to_dict(statussql, {"tablespace": tablespace}, fetchone=True)
    current_status = r['status']
    wanted_status, enforcesql = map_status(state,current_status)
    if wanted_status != current_status:
        sql = 'alter tablespace %s %s' % (tablespace, enforcesql)
        alter_tbs_list.append(sql)

    alter_tbs_sql = f'alter tablespace {tablespace} '
    numfiles_curr_sql = f"select count(*) as count from {dfsource} where tablespace_name = upper(:tablespace)"
    r = conn.execute_select_to_dict(numfiles_curr_sql, {"tablespace": tablespace}, fetchone=True)
    crfiles = r['count']

    # The following if/elif deals with adding data/temp-files
    if not skip_datafile and datafile is None:
        msg = 'Error: Missing datafile name/datafile. Either set db_create_file_dest or specify one or more datafiles'
        module.fail_json(msg=msg, changed=conn.changed, ddls=conn.ddls)

    elif numfiles is not None and int(crfiles) < int(numfiles) and not bigfile and skip_datafile:
        '''
        This should only run if:
        - db_create_file_dest is set (OMF is in use)
        - Tablespace is not bigfile
        - numfiles is set to a higher value than the existing number of datafiles
        '''
        newfiles = abs(int(numfiles) - int(crfiles))

        if autoextend and not nextsize:
            module.fail_json(msg='Error: Missing NEXT size for autoextend',changed=False)
        elif autoextend and nextsize and not maxsize:
            wanted_list_dbf = ','.join(' size %s autoextend on next %s' % (size,nextsize) for d in range(int(newfiles)) )
        elif autoextend and nextsize and maxsize:
            wanted_list_dbf = ','.join(' size %s autoextend on next %s maxsize %s' % (size,nextsize,maxsize) for d in range(int(newfiles) ))
        else:
            wanted_list_dbf = ','.join(' size %s ' % (size) for d in range(int(newfiles) ))

        alter_tbs_sql += f' add {dftype} {wanted_list_dbf}'
        alter_tbs_list.append(alter_tbs_sql)
        #crfiles = numfiles

    elif numfiles is None and not bigfile and datafile is not None and int(crfiles) < int(len(datafile)):
        '''
        This should only run if:
        - 'datafile' is set
        - Tablespace is not bigfile
        - The number of files (len(datafile)) are higher than the existing number of datafiles
        '''

        # Get the current list of datafiles
        currfiles_perm = get_tablespace_files(conn ,tablespace)
        # Compare the current list with the 'wanted_list_dbf'
        wanted_list_dbf = list(set(datafile) - set(currfiles_perm))
        if wanted_list_dbf:
            if autoextend and not nextsize:
                module.fail_json(msg='Error: Missing NEXT size for autoextend',changed=False)
            elif autoextend and nextsize and not maxsize:
                datafile_list = ','.join('\''+ d + '\' size %s autoextend on next %s' % (size,nextsize) for d in wanted_list_dbf )
            elif autoextend and nextsize and maxsize:
                datafile_list = ','.join('\''+ d + '\' size %s autoextend on next %s maxsize %s' % (size,nextsize,maxsize) for d in wanted_list_dbf )
            else:
                datafile_list = ','.join('\''+ d + '\' size %s ' % (size) for d in wanted_list_dbf )

            alter_tbs_sql += ' add %s %s ' % (dftype,datafile_list)
            alter_tbs_list.append(alter_tbs_sql)
            crfiles = len(datafile)

    ensure_tablespace_attributes(conn,tablespace, autoextend, nextsize, maxsize)
    # Enforce actual changes (if there are any)
    for sql in alter_tbs_list:
        conn.execute_ddl(sql)


def ensure_tablespace_attributes (conn, tablespace, autoextend, nextsize, maxsize):

    ensure_sql = """
    DECLARE
       -- output
       v_autoextend_change number := 0;
       v_nextsize_change number := 0;
       v_maxsize_change number := 0;
       -- input
       v_tablespace varchar2(30); --:= 'blergh';
       v_autoextend  varchar2(5); --:= 'True';
       v_nextsize varchar2(20); --:= '10M' ;
       v_maxsize varchar2(20); --:= '500M' ;
       -- runtime
       v_nextsize_suffix varchar2(1);
       v_maxsize_suffix varchar2(1);
       v_divisor_nextsize number(20);
       v_divisor_maxsize number(20);
       v_next_change number;
       v_max_change number;
       v_autoextend_ varchar2(3);
       v_autoextend_sql varchar2(30);
       v_nextsize_current varchar2(20) ;
       v_maxsize_current varchar2(20) ;
       v_nextsize_wanted varchar2(20) ;
       v_maxsize_wanted varchar2(20) ;
       v_content varchar2(30) ;
       v_tbs_source varchar2(30);
       v_df_source varchar2(50);
       v_df_file varchar2(50);
       -- exceptions
       missing_suffix exception;

       BEGIN
           v_tablespace:= :tablespace;
           v_autoextend:= :autoextend;
           v_nextsize:= :nextsize;
           v_maxsize:= :maxsize;
           -- Check what type of tablespace it is
           select contents into v_tbs_source from dba_tablespaces where tablespace_name = upper(''||v_tablespace||'');
           IF upper(v_tbs_source) = 'TEMPORARY' THEN
               v_content := 'temp';
           ELSE
               v_content := 'permanent';
           END IF;

           IF upper(v_autoextend) = 'TRUE' THEN
                v_autoextend_ := 'YES';
                v_autoextend_sql := 'on';
           ELSE
                v_autoextend_ := 'NO';
                v_autoextend_sql := 'off';
           END IF;
           -- Get the suffix to decide the divisor
           select substr(v_nextsize,-1),substr(v_maxsize,-1) into v_nextsize_suffix,v_maxsize_suffix from dual;
           IF upper(v_nextsize_suffix) = 'M' THEN
               v_divisor_nextsize := 1024*1024;
           ELSIF upper(v_nextsize_suffix) = 'G' THEN
               v_divisor_nextsize := 1024*1024*1024;
           ELSIF upper(v_nextsize_suffix) = 'T' THEN
               v_divisor_nextsize := 1024*1024*1024*1024;
           ELSE
               NULL;
           END IF;

           IF upper(v_maxsize_suffix) = 'M' THEN
               v_divisor_maxsize := 1024*1024;
           ELSIF upper(v_maxsize_suffix) = 'G' THEN
               v_divisor_maxsize := 1024*1024*1024;
           ELSIF upper(v_maxsize_suffix) = 'T' THEN
               v_divisor_maxsize := 1024*1024*1024*1024;
           ELSE
               NULL;
           END IF;

           -- Strip the suffix (M/G/T) from the input string
          IF upper(v_nextsize_suffix) in ('K','M','G','T') THEN
              select substr (v_nextsize, 0, (length (v_nextsize)-1)) into v_nextsize_wanted from dual;
          END IF;
          IF upper(v_maxsize_suffix) in ('K','M','G','T') THEN
              select substr (v_maxsize, 0, (length (v_maxsize)-1)) into v_maxsize_wanted from dual;
          END IF;

               -- Loop over files in the tablespace and makes changes if needed
               IF upper(v_content) = 'TEMP' THEN
                    v_df_file := 'tempfile';
                    FOR rec in (select df.file_name, df.autoextensible, dt.block_size, df.increment_by, df.maxbytes
                                from dba_tablespaces dt, dba_temp_files df
                                where dt.tablespace_name = df.tablespace_name
                                and dt.tablespace_name = upper(''||v_tablespace||''))

                    LOOP
                        v_nextsize_current := ((rec.block_size*rec.increment_by)/v_divisor_nextsize);
                        v_maxsize_current := ((rec.maxbytes)/v_divisor_maxsize);

                        IF (rec.autoextensible != v_autoextend_) THEN
                            v_autoextend_change := v_autoextend_change+1;
                            --dbms_output.put_line ('alter database '||v_df_file ||' '''||rec.file_name ||''' autoextend '||v_autoextend_sql );
                            execute immediate 'alter database '||v_df_file ||' '''||rec.file_name ||''' autoextend '||v_autoextend_sql;
                        END IF;
                        IF upper(v_autoextend) = 'TRUE' THEN
                            IF (v_nextsize_current != v_nextsize_wanted) THEN
                                v_nextsize_change := v_nextsize_change+1;
                                --dbms_output.put_line ('alter database tempfile '''||rec.file_name ||''' autoextend on next '||v_nextsize );
                                execute immediate 'alter database '||v_df_file ||' '''||rec.file_name ||''' autoextend on next '||v_nextsize;
                            END IF;
                            IF (v_maxsize_current != v_maxsize_wanted) THEN
                                v_maxsize_change := v_maxsize_change+1;
                                --dbms_output.put_line ('alter database tempfile '''||rec.file_name ||''' autoextend on maxsize '||v_maxsize );
                                execute immediate 'alter database '||v_df_file ||' '''||rec.file_name ||''' autoextend on maxsize '||v_maxsize;
                            END IF;
                        END IF;
                    END LOOP;

                    ELSE
                        v_df_file := 'datafile';
                        FOR rec in (select df.file_name, df.autoextensible, dt.block_size, df.increment_by, df.maxbytes
                                    from dba_tablespaces dt, dba_data_files df
                                    where dt.tablespace_name = df.tablespace_name
                                    and dt.tablespace_name = upper(''||v_tablespace||''))

                        LOOP
                            v_nextsize_current := ((rec.block_size*rec.increment_by)/v_divisor_nextsize);
                            v_maxsize_current := ((rec.maxbytes)/v_divisor_maxsize);

                            IF (rec.autoextensible != v_autoextend_) THEN
                                v_autoextend_change := v_autoextend_change+1;
                                --dbms_output.put_line ('alter database '||v_df_file ||' '''||rec.file_name ||''' autoextend '||v_autoextend_sql );
                                execute immediate 'alter database '||v_df_file ||' '''||rec.file_name ||''' autoextend '||v_autoextend_sql;
                            END IF;
                            IF upper(v_autoextend) = 'TRUE' THEN
                                IF (v_nextsize_current != v_nextsize_wanted) THEN
                                    v_nextsize_change := v_nextsize_change+1;
                                    --dbms_output.put_line ('alter database '||v_df_file ||' '''||rec.file_name ||''' autoextend on next '||v_nextsize );
                                    execute immediate 'alter database '||v_df_file ||' '''||rec.file_name ||''' autoextend on next '||v_nextsize;
                                END IF;
                                IF (v_maxsize_current != v_maxsize_wanted) THEN
                                    v_maxsize_change := v_maxsize_change+1;
                                    --dbms_output.put_line ('alter database '||v_df_file ||' '''||rec.file_name ||''' autoextend on maxsize '||v_maxsize );
                                    execute immediate 'alter database '||v_df_file ||' '''||rec.file_name ||''' autoextend on maxsize '||v_maxsize;
                                END IF;
                            END IF;
                        END LOOP;
               END IF;
               --:o_autoextend_changed := v_autoextend_change;
               --:o_nextsize_changed := v_nextsize_change;
               --:o_maxsize_changed := v_maxsize_change;
               IF v_autoextend_change > 0 or v_nextsize_change > 0 or v_maxsize_change > 0 THEN
                  dbms_output.put_line ('auto: '||v_autoextend_change);
                  dbms_output.put_line ('next: '||v_nextsize_change);
                  dbms_output.put_line ('max: '||v_maxsize_change);
                  dbms_output.put_line ('Changes applied');
               END IF;
       END;
    """

    r = conn.execute_statement(ensure_sql,
                           {'tablespace': tablespace,
                            'autoextend': str(autoextend),
                            'nextsize': nextsize,
                            'maxsize': maxsize})
    if conn.module._verbosity >= 3:
        conn.module.warn(str(r))

    if r:
        conn.changed = True


# Get the existing datafiles for the tablespace
def get_tablespace_files(conn, tablespace):

    sql = """select f.file_name from dba_data_files f, dba_tablespaces d
    where f.tablespace_name = d.tablespace_name
    and d.tablespace_name = upper(:tablespace)"""

    r = conn.execute_select_to_dict(sql, {'tablespace': tablespace})
    return [f['file_name'] for f in r]


# Make tablespace read only
def manage_tablespace(module, msg, cursor, tablespace, state):

    if state == 'read_only':
        sql = 'alter tablespace %s read only' % tablespace
        msg = 'Tablespace %s has been put in read only mode' % tablespace
    elif state == 'read_write':
        sql = 'alter tablespace %s read write' % tablespace
        msg = 'Tablespace %s has been put in read write mode' % tablespace
    elif state == 'offline':
        sql = 'alter tablespace %s offline' % tablespace
        msg = 'Tablespace %s has been put offline' % tablespace
    elif state == 'online':
        sql = 'alter tablespace %s online' % tablespace
        msg = 'Tablespace %s has been put online' % tablespace

    try:
        cursor.execute(sql)
    except oracledb.DatabaseError as exc:
        error, = exc.args
        msg = error.message+ 'sql: ' + sql
        return False


    return True, msg


# Drop the tablespace
def drop_tablespace(conn, module, tablespace):
    drop_sql = f'drop tablespace {tablespace} including contents and datafiles'
    conn.execute_ddl(drop_sql)


def main():
    module = AnsibleModule(
        argument_spec = dict(
            user          = dict(required=False, aliases=['un', 'username']),
            password      = dict(required=False, no_log=True, aliases=['pw']),
            mode          = dict(default='normal', choices=["normal", "sysdba"]),
            hostname      = dict(required=False, default='localhost', aliases=['host']),
            port          = dict(required=False, default=1521, type='int'),
            service_name  = dict(required=False, aliases=['sn']),
            dsn           = dict(required=False, aliases=['datasource_name']),
            oracle_home   = dict(required=False, aliases=['oh']),

            tablespace    = dict(required=True, aliases=['name','ts']),
            state         = dict(default="present", choices=["present", "absent", "read_only", "read_write", "offline", "online" ]),
            bigfile       = dict(default=True, type='bool'),
            datafile      = dict(required=False, type='list', aliases=['datafiles','df']),
            numfiles      = dict(required=False),
            size          = dict(required=False, default='100M'),
            content       = dict(default='permanent', choices=['permanent', 'temp', 'undo']),
            autoextend    = dict(default=False, type='bool'),
            nextsize      = dict(required=False, aliases=['next']),
            maxsize       = dict(required=False, aliases=['max']),
        ),
        mutually_exclusive = [('datafile', 'numfiles')],
        required_if=[('autoextend', True, ('nextsize',))],
        supports_check_mode=True
    )

    tablespace = module.params["tablespace"]
    state = module.params["state"]

    conn = oracleConnection(module)

    if state in ('present', 'read_only', 'read_write', 'offline', 'online'):
        if not check_tablespace_exists(conn, tablespace):
            create_tablespace(conn, module)
            ensure_tablespace_state(conn, module, tbs_just_created=True)
            msg = f'The tablespace {tablespace} has been created successfully'
            module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)
        else:
            ensure_tablespace_state(conn, module, tbs_just_created=False)
            msg = f'The tablespace {tablespace} has been altered successfully'
            module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)

    elif state == 'absent':
        if check_tablespace_exists(conn, tablespace):
            drop_tablespace(conn, module, tablespace)
            msg = f'The tablespace {tablespace} has been dropped successfully'
            module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)
        msg = f'Nothing to do for {tablespace}'
        module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)


from ansible.module_utils.basic import *

# In these we do import from local project project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
#try:
#    from ansible.module_utils.oracle_utils import oracleConnection
#except:
#    pass

# In these we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracleConnection
except:
    pass

if __name__ == '__main__':
    main()
