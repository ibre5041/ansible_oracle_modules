#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_redo
short_description: Manage Oracle redo related things
description:
    - Manage redogroups
    - Can be run locally on the controlmachine or on a remote host
version_added: "3.0.0"
options:
    hostname:
        description:
            - The Oracle database host
        required: false
        default: localhost
    port:
        description:
            - The listener port number on the host
        required: false
        default: 1521
    service_name:
        description:
            - The database service name to connect to
        required: true
    user:
        description:
            - The Oracle user name to connect to the database, must have DBA privilege
        required: False
    password:
        description:
            - The Oracle user password for 'user'
        required: False
    mode:
        description:
            - The mode with which to connect to the database
        required: true
        default: normal
        choices: ['normal','sysdba']
    size:
        description:
            - size of redologs
        required:
            - True
        default:
            - 50MB
    groups:
        description:
            - The number of redolog groups
        required:
            - False
    members:
        description:
            - Either to set the preference (present) or reset it to default (absent)
        required: true
        default: 1


notes:
    - cx_Oracle needs to be installed
requirements: [ "cx_Oracle" ]
author: 
    - Mikael Sandström, oravirt@gmail.com, @oravirt
    - Ivan Brezina
'''

EXAMPLES = '''
- hosts: all
  gather_facts: true
  vars:
      oracle_home: /u01/app/oracle/12.2.0.1/db1
      hostname: "{{ ansible_hostname }}"
      service_name: orclcdb
      user: system
      password: Oracle_123
      oracle_env:
             ORACLE_HOME: "{{ oracle_home }}"
             LD_LIBRARY_PATH: "{{ oracle_home }}/lib"

      redosize: 15M
      numgroups: 3
  tasks:
  - name: Manage redologs
    oracle_redo:
        service_name={{ service_name }}
        hostname={{ hostname}}
        user={{ user }}
        password={{ password }}
        groups={{ numgroups |default(omit) }}
        size={{ redosize |default(omit)}}
    environment: "{{ oracle_env }}"
    run_once: True
'''

try:
    import cx_Oracle
except ImportError:
    cx_oracle_exists = False
else:
    cx_oracle_exists = True

# Ansible code
def main():
    global lconn, conn, msg, module
    msg = ['']
    module = AnsibleModule(
        argument_spec = dict(
            hostname      = dict(default='localhost'),
            port          = dict(default=1521, type='int'),
            service_name  = dict(required=False),
            user          = dict(required=False),
            password      = dict(required=False, no_log=True),
            mode          = dict(default='normal', choices=["normal","sysdba"]),
            size          = dict(required=True),
            groups        = dict(required=True),
            log_type      = dict(default='redo', choices=["redo", "standby"])
            # threads       = dict(default=1)
        ),
    )

    hostname = module.params["hostname"]
    port = module.params["port"]
    service_name = module.params["service_name"]
    user = module.params["user"]
    password = module.params["password"]
    mode = module.params["mode"]
    size = module.params["size"]
    groups = module.params["groups"]
    log_type = module.params["log_type"]
    # threads = module.params["threads"]

    # Check for required modules
    if not cx_oracle_exists:
        module.fail_json(msg="The cx_Oracle module is required. 'pip install cx_Oracle' should do the trick. If cx_Oracle is installed, make sure ORACLE_HOME is set")

    conn = oracle_connect(module)

    #
    # if module.check_mode:
    #     module.exit_json(changed=False)
    #

    if not (size.endswith('M') or size.endswith('G') or size.endswith('T')):
        msg = 'You need to suffix the size with (M,G or T), i.e: %sM/%sG/%sT' % (size,size,size)
        module.fail_json(msg=msg, changed=False)

    redosql = """
DECLARE
    -- output
    v_redo_size_changes   number := 0;
    v_redo_group_changes   number := 0;
    v_msg       varchar2(100);
    -- input
    v_maxbytes  varchar2(20) ;
    v_groups number ;
    -- runtime
    v_maxbytes_actual  number(10,1);
    v_maxbytes_suffix varchar2(1);
    v_divisor number(20);
    v_sleep     number := 5;
    v_israc     VARCHAR2(3);
    v_existing_redogroups number ;
    v_max_groupnum  number;
    v_group_diff number;
    v_sql_sw_lf varchar2 (50);
    v_sql_cp    varchar2 (50);
    
    -- exceptions
    missing_suffix exception;
    
BEGIN
    v_maxbytes:= :redosize;
    v_groups:= :redogroups;
    
    -- Check if it is a RAC database or not (parallel = True -> RAC)
    select parallel into v_israc from v$instance;
    IF v_israc = 'YES' THEN
        v_sql_sw_lf := 'alter system switch all logfile';
        v_sql_cp := 'alter system checkpoint global';
    ELSE
        v_sql_sw_lf := 'alter system switch logfile';
        v_sql_cp := 'alter system checkpoint';
    END IF;

    -- Get the suffix to decide the divisor
    select substr(v_maxbytes,-1) into v_maxbytes_suffix from dual;
    IF upper(v_maxbytes_suffix) = 'M' THEN
        v_divisor := 1024*1024;
    ELSIF upper(v_maxbytes_suffix) = 'G' THEN
        v_divisor := 1024*1024*1024;
    ELSIF upper(v_maxbytes_suffix) = 'T' THEN
        v_divisor := 1024*1024*1024*1024;
    ELSE
        raise missing_suffix;
    END IF;

    -- Strip the suffix (M/G/T) from the input string
    IF upper(v_maxbytes_suffix) in ('M','G','T') THEN
        select substr (v_maxbytes, 0, (length (v_maxbytes)-1)) into v_maxbytes_actual from dual;
    END IF;

    FOR rec in (select thread#, group#, status, bytes from v$log order by thread#)
    LOOP
        IF rec.bytes/v_divisor != v_maxbytes_actual    THEN
            v_redo_size_changes := v_redo_size_changes+1;
            FOR chloop in (select thread#, group#, status from v$log where thread# = rec.thread# and group# = rec.group#)
            LOOP
                IF chloop.status in ('CURRENT','ACTIVE') THEN
                    --dbms_output.put_line('Current');
                    execute immediate v_sql_sw_lf;
                    execute immediate v_sql_cp;
                    dbms_lock.sleep(v_sleep);
                    execute immediate 'alter database add logfile thread '||chloop.thread# ||' size '||v_maxbytes ;
                    execute immediate 'alter database drop logfile group '||chloop.group# ;
                ELSE
                    execute immediate 'alter database add logfile thread '||chloop.thread# ||' size '||v_maxbytes ;
                    execute immediate 'alter database drop logfile group '||chloop.group# ;
                END IF;
            END LOOP;
        END IF;
    END LOOP;
    dbms_output.put_line(v_redo_size_changes);

    -- Get number of groups
    FOR t in (select * from v$thread where enabled != 'DISABLED')
    LOOP
        dbms_output.put_line('Thread: '||t.thread#);
        select count(*) into v_existing_redogroups from v$log where thread# = t.thread#;
        dbms_output.put_line('Thread: '||t.thread# ||' numgroups: '||v_existing_redogroups);
        IF v_existing_redogroups < v_groups THEN
            select v_groups-v_existing_redogroups into v_group_diff from dual;
            dbms_output.put_line('Adding '||v_group_diff ||' groups to thread: '||t.thread#);
            FOR grloop in 1..v_group_diff
            LOOP
                v_redo_group_changes := v_redo_group_changes+1;
                --v_max_groupnum := 0;
                select max(group#) into v_max_groupnum from v$log;
                v_max_groupnum := v_max_groupnum + 1;
                execute immediate 'alter database add logfile thread '|| t.thread# ||' group '||v_max_groupnum ||' size '||v_maxbytes;
                dbms_output.put_line('adding group '||v_max_groupnum ||' to thread '||t.thread#);
            END LOOP;
        ELSIF v_existing_redogroups > v_groups THEN
            --select count(*) into v_existing_redogroups from v$log where thread# = t.thread#;
            select v_existing_redogroups-v_groups into v_group_diff from dual;
            dbms_output.put_line('Removing ' ||v_group_diff ||' groups from thread: '||t.thread#);

            FOR grloop in 1..v_group_diff
            LOOP
                v_redo_group_changes := v_redo_group_changes+1;
                select max(group#) into v_max_groupnum from v$log where upper(status) not in ('ACTIVE','CURRENT') and thread# = t.thread#;
                execute immediate 'alter database drop logfile group '||v_max_groupnum ;
                dbms_output.put_line('dropping group '||v_max_groupnum ||' thread#: '||t.thread#);
            end loop;
        ELSE
            dbms_output.put_line('Nothing to do');
        END IF;
    END LOOP;

    :o_size_changed := v_redo_size_changes;
    :o_group_changed := v_redo_group_changes;
    IF v_redo_size_changes > 0 THEN
        :o_size_msg := 'All redologs have been changed to '||v_maxbytes;
    ELSE
        :o_size_msg := 'No size changes';
    END IF;

    IF v_redo_group_changes > 0 THEN
        :o_group_msg := 'Groups have been adjusted to '||v_groups ||' groups';
    ELSE
        :o_group_msg := 'No group changes';
    END IF;

EXCEPTION
WHEN missing_suffix THEN
    dbms_output.put_line('--------');
    dbms_output.put_line('You need to suffix the size with (M,G or T), i.e: '||v_maxbytes ||'M/'||v_maxbytes ||'G/' ||v_maxbytes ||'T');
    dbms_output.put_line('--------');
END;
"""

    standbysql = """
DECLARE
    -- output
    v_redo_size_changes   number := 0;
    v_redo_group_changes   number := 0;
    v_msg varchar2(100);
    -- input
    v_maxbytes varchar2(20) ;
    v_groups number ;
    -- runtime
    v_maxbytes_actual number(10,1);
    v_maxbytes_suffix varchar2(1);
    v_divisor number(20);
    v_sleep number := 5;
    v_israc VARCHAR2(3);
    v_existing_redogroups number ;
    v_max_groupnum  number;
    v_max_redo_groupnum number;
    v_log  number;
    v_group_diff number;
    v_sql_sw_lf varchar2 (50);
    v_sql_cp    varchar2 (50);
    
    -- exceptions
    missing_suffix exception;
    
    BEGIN
        v_maxbytes:= :redosize;
        v_groups:= :redogroups;
        
        -- Check if it is a RAC database or not (parallel = True -> RAC)
        select parallel into v_israc from v$instance;
        IF v_israc = 'YES' THEN
            v_sql_sw_lf := 'alter system switch all logfile';
            v_sql_cp := 'alter system checkpoint global';
        ELSE
            v_sql_sw_lf := 'alter system switch logfile';
            v_sql_cp := 'alter system checkpoint';
        END IF;

        -- Get the suffix to decide the divisor
        select substr(v_maxbytes,-1) into v_maxbytes_suffix from dual;
        IF upper(v_maxbytes_suffix) = 'M' THEN
            v_divisor := 1024*1024;
        ELSIF upper(v_maxbytes_suffix) = 'G' THEN
            v_divisor := 1024*1024*1024;
        ELSIF upper(v_maxbytes_suffix) = 'T' THEN
            v_divisor := 1024*1024*1024*1024;
        ELSE
           raise missing_suffix;
        END IF;

        -- Strip the suffix (M/G/T) from the input string
        IF upper(v_maxbytes_suffix) in ('M','G','T') THEN
            select substr (v_maxbytes, 0, (length (v_maxbytes)-1)) into v_maxbytes_actual from dual;
        END IF;

        FOR rec in (select thread#, group#, status, bytes from v$standby_log order by thread#)
        LOOP
            IF rec.bytes/v_divisor != v_maxbytes_actual THEN
            v_redo_size_changes := v_redo_size_changes+1;
         FOR chloop in (select thread#, group#, status from v$standby_log where thread# = rec.thread# and group# = rec.group#)
         LOOP
             IF chloop.status in ('CURRENT','ACTIVE') THEN
                 dbms_output.put_line('Current group: '||chloop.group#);
             execute immediate v_sql_sw_lf;
             execute immediate v_sql_cp;
             dbms_lock.sleep(v_sleep);
             execute immediate 'alter database add standby logfile thread '||chloop.thread# ||' size '||v_maxbytes ;
             execute immediate 'alter database drop standby logfile group '||chloop.group# ;
            ELSE
            execute immediate 'alter database add standby logfile thread '||chloop.thread# ||' size '||v_maxbytes ;
             execute immediate 'alter database drop standby logfile group '||chloop.group# ;
             END IF;
         END LOOP;
         END IF;
     END LOOP;
        dbms_output.put_line('standby redo size changes: '||v_redo_size_changes);

     -- Get number of groups
     FOR t in (select * from v$thread where enabled != 'DISABLED')
     LOOP
         dbms_output.put_line('Thread: '||t.thread#);
         select count(*) into v_existing_redogroups from v$standby_log where thread# = t.thread#;
         dbms_output.put_line('Thread: '||t.thread# ||' numgroups: '||v_existing_redogroups);
         IF v_existing_redogroups < v_groups THEN
             v_group_diff := v_groups - v_existing_redogroups;
         dbms_output.put_line('Adding '||v_group_diff ||' groups to thread: '||t.thread#);
         FOR grloop in 1..v_group_diff
         LOOP
             v_redo_group_changes := v_redo_group_changes+1;
             select max(group#) into v_max_redo_groupnum from v$log;
             v_max_redo_groupnum := ceil(log(10, v_max_redo_groupnum));
             v_max_redo_groupnum := power(10, v_max_redo_groupnum) + 1;
             --
             select nvl(max(GROUP#) + 1, 0) into v_max_groupnum from v$standby_log;
             v_max_groupnum := greatest(v_max_groupnum, v_max_redo_groupnum);
             execute immediate 'alter database add standby logfile thread '|| t.thread# ||' group '||v_max_groupnum ||' size '||v_maxbytes;
             dbms_output.put_line('adding group '||v_max_groupnum ||' to thread '||t.thread#);
         END LOOP;
         ELSIF v_existing_redogroups > v_groups THEN
             --select count(*) into v_existing_redogroups from v$standby_log where thread# = t.thread#;
         select v_existing_redogroups-v_groups into v_group_diff from dual;
         dbms_output.put_line('Removing ' ||v_group_diff ||' groups from thread: '||t.thread#);

         FOR grloop in 1..v_group_diff
         LOOP
             v_redo_group_changes := v_redo_group_changes+1;
            select max(group#) into v_max_groupnum from v$standby_log
            where upper(status) not in ('ACTIVE','CURRENT') and thread# = t.thread#;
            execute immediate 'alter database drop standby logfile group '||v_max_groupnum ;
            dbms_output.put_line('dropping group '||v_max_groupnum ||' thread#: '||t.thread#);
            END LOOP;
              ELSE
            dbms_output.put_line('Nothing to do');
        END IF;
       END LOOP;

       :o_size_changed := v_redo_size_changes;
       :o_group_changed := v_redo_group_changes;
       IF v_redo_size_changes > 0 THEN
           :o_size_msg := 'All redologs have been changed to '||v_maxbytes;
       ELSE
           :o_size_msg := 'No size changes';
       END IF;

       IF v_redo_group_changes > 0 THEN
           :o_group_msg := 'Groups have been adjusted to '||v_groups ||' groups';
       ELSE
           :o_group_msg := 'No group changes';
       END IF;

    EXCEPTION
    WHEN missing_suffix THEN
        dbms_output.put_line('--------');
        dbms_output.put_line('You need to suffix the size with (M,G or T), i.e: '||v_maxbytes ||'M/'||v_maxbytes ||'G/' ||v_maxbytes ||'T');
        dbms_output.put_line('--------');
END;
"""

    cur = conn.cursor()

    try:
        v_size_changed = cur.var(cx_Oracle.NUMBER)
        v_group_changed = cur.var(cx_Oracle.NUMBER)
        v_size_msg = cur.var(cx_Oracle.STRING)
        v_group_msg = cur.var(cx_Oracle.STRING)
        if log_type == 'redo':
            cur.execute(redosql, {
                'redosize': size,
                'redogroups': groups ,
                'o_size_changed': v_size_changed,
                'o_group_changed': v_group_changed,
                'o_size_msg': v_size_msg,
                'o_group_msg': v_group_msg}
            )
        else:
            cur.execute(standbysql, {
                'redosize': size,
                'redogroups': groups ,
                'o_size_changed': v_size_changed,
                'o_group_changed': v_group_changed,
                'o_size_msg': v_size_msg,
                'o_group_msg': v_group_msg}
            )            
    except cx_Oracle.DatabaseError as exc:
        error, = exc.args
        msg = '%s' % (error.message)
        module.fail_json(msg=msg, changed=False)

    size_result_changed = v_size_changed.getvalue()
    group_result_changed = v_group_changed.getvalue()
    #module.exit_json(msg=result_changed, changed=False)
    size_msg = v_size_msg.getvalue()
    group_msg = v_group_msg.getvalue()
    msg = "%s. %s." % (size_msg, group_msg)
    if (size_result_changed > 0 or group_result_changed > 0):
        changed = True
    else:
        changed = False
    #module.exit_json(msg=result_changed, changed=False)
    module.exit_json(msg=msg, changed=changed)


from ansible.module_utils.basic import *

# In thise we do import from local project project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No colletions are used
try:
    from ansible.module_utils.oracle_utils import oracle_connect
except:
    pass

# In thise we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracle_connect
except:
    pass


if __name__ == '__main__':
    main()
