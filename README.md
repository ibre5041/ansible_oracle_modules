# ansible-oracle-modules
**Oracle modules for Ansible**

- This project was forked from https://github.com/oravirt/ansible-oracle-modules, but also tries to consolidate fixes from other forks.  
- This fork uses different layout than original, db connection code is shared via module_utils
- This fork prefers to use `connect / as sysdba` over using a wallet, password or SQLNET over TCPIP 
- This fork uses `oracle_oratab` module to store list of databases as ansible facts

See project: https://github.com/ibre5041/ansible_oracle_modules_example.git as an example.

To use this collection place this in requirements.yml

    ---
    collections:
      - name: https://github.com/ibre5041/ansible_oracle_modules.git
        type: git
        version: main

And then execute: `ansible-galaxy collection install -r requirements.yml`

Most (if not all) requires `cx_Oracle` either on your on the managed node "control machine".
To install `cx_Oracle` you can use: `pip3 install --user cx_Oracle` (`/usr/libexec/platform-python -m pip install --user cx_Oracle` on RHEL8)

The default behaviour for the modules using `cx_Oracle` is this:

- If mode=='sysdba' connect internal `/ as sysdba` is used
- If neither username or password is passed as input to the module(s), the use of an Oracle wallet is assumed.
- In that case, the `cx_Oracle.makedsn` step is skipped, and the connection will use the `'/@<service_name>'` format instead.
- You then need to make sure that you're using the correct tns-entry (service_name) to match the credential stored in the wallet.

# These are the different modules:

## **oracle_db**

*pre-req: cx_Oracle*

- Create/remove databases (cdb/non-cdb)
- Can be created by passing in a responsefile or just by using parameters

        - name: create database
          oracle_db:
            oracle_home: '/oracle/u01/product/19.17.0.0'
            db_name: 'X01'
            sid: 'X01'
            db_unique_name: 'X01_A'
            sys_password: "{{ sys_password }}"
            #system_password:
            #dbsnmp_password:
            db_options:
              - JSERVER:true
              - ORACLE_TEXT:false
              - IMEDIA:false
              - CWMLITE:false
              - SPATIAL:false
              - OMS:false
              - APEX:false
              - DV:false
            initparams:
              - memory_target=0
              - memory_max_target=0
              - sga_target=1500MB
              - sga_max_size=1500MB
            storage_type: ASM
            datafile_dest: +XDATA
            state: present
        become_user: oracle
        become: yes


## **oracle_oratab**

- Parses oratab, crs_stat output to get list of databases
- Set facts as list of dict.
   See [sample playbook](https://github.com/ibre5041/ansible_oracle_modules_example/blob/main/oracle_oratab.yml):

        vars:
        # List of affected databases, this variable overrides default: sid_list.oracle_list.keys()
        # db_list | default(sid_list.oracle_list.keys())
        # Comment out this variable to apply playbook onto all databases
           db_list: [ TEST ]
        
        tasks:
          - oracle_oratab:
            register: sid_list

          - name: Print Facts
            debug:
              var: sid_list

          - oracle_role:
            mode: sysdba
              role: SOME_ROLE
            environment:
              ORACLE_HOME: "{{ sid_list.oracle_list[item].ORACLE_HOME }}"
              ORACLE_SID:  "{{ sid_list.oracle_list[item].ORACLE_SID }}"
            loop: "{{ db_list | default(sid_list.oracle_list.keys())}}"

## **oracle_facts**

*pre-req: cx_Oracle*

- Gathers facts about Oracle database

        - name: Oracle DB facts
          oracle_facts:
            mode: sysdba
            userenv: false
            database: false
            instance: false
            password_file: true
            redo: summary
            standby: summary
            parameter:
              - audit_file_dest
              - db_name
              - db_unique_name
              - instance_name
              - service_names
          register: database_facts
  
        - name: database facts
          debug:
            var: database_facts

## **oracle_tnsnames**

This module can query or amend content of Oracle's .ora files.

*Note*: It uses ANTLR3 generated parser for .ora files, manipulates parsed AST and the serializes it.
This results into situation when all white-noise characters are omited and resulting tnsnames.ora file has all aliases stored as one-liners. 

        - name: oracle_tnsnames
          oracle_tnsnames:
            path: /oracle/product/19.0.0/db1/network/admin/tnsnames.ora
            #alias: XXXXX01D
            aliases:
              - XXXXX01D
              - LISTENER_XXXXX01D
          register: alias
    
        - name: XXXXX01D alias
          debug:
            var: alias
    
        - name: oracle_tnsnames
          oracle_tnsnames:
            path: /oracle/product/19.0.0/db1/network/admin/tnsnames.ora
            alias: XXXXX01D_PRIMARY
            whole_value: '(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={{ dg_primary_hostname }})(PORT={{ dg_oracle_port}}))(CONNECT_DATA=(SERVER=DEDICATED)(SERVICE_NAME={{ dg_oracle_sid }})))'
          register: alias_pr

## **oracle_profile**

*pre-req cx_Oracle*

- Create/alter/drop database profile
  
        - name
          oracle_profile:
            mode: sysdba
            profile: unlimited_profile
            attribute_name:  ["PASSWORD_LIFE_TIME", "PASSWORD_REUSE_MAX"]
            attribute_value: ["UNLIMITED", "UNLIMITED"]
            state: present

## **oracle_role**

*pre-req: cx_Oracle*

- Manages roles in the database

        - name
          oracle_role:
            mode: sysdba        
            role: test_role
            state: present

## **oracle_user**

*pre-req: cx_Oracle*

- Creates & drops a user
- Does not suppot privileges (use oracle_grants for that)

        - name: sysdg user
          oracle_user:
            mode: sysdba
            schema: sample_user
            state: present
            profile: app_profile
            #schema_password_hash: 'T:BC3BF4B95DBAE1A9B6E633FB90FDB2351ACEFE5871A990806F565AD756D4C5C2312B4D2306A34C5BD0588E49F8AB8F0CBFF0DBE427B373B3E3BFE374904B6E01E2EC5166823A917227492E58556AE1D5' # pw: Xiejfkljfssgdhd123
            schema_password: Xiejfkljfssgdhd123
            default_tablespace: users


## **oracle_tablespace**

*pre-req: cx_Oracle*

- Manages normal(permanent), temp & undo tablespaces (create, drop, make read only/read write, offline/online)
- Tablespaces can be created as bigfile, autoextend, ...

        - name: USERS tablespace
          oracle_tablespace: 
            tablespace: test
            # use: db_create_file_dest parameter
            # datafile: '+DATA' 
            size: 100M
            state: present 
            bigfile: true 
            autoextend: true

## **oracle_redo**

*pre-req: cx_Oracle*

- Manage redo-groups and their size in RAC or single instance environments
- NOTE: For RAC environments, the database needs to be in ARCHIVELOG mode. This is not required for SI environments.

        - name: Manage redologs
          oracle_redo:
            mode: sysdba
            log_type: redo
            size: 200M
            groups: 4
  
        - name: Manage redologs
          oracle_redo:
            mode: sysdba
            log_type: standby
            size: 200M
            groups: 5


## **oracle_grants**

*pre-req: cx_Oracle*

- Manages privileges for a user
- Grants/revokes privileges
- Handles roles/sys privileges properly. Does NOT yet handle object/directory privs. They can be added but they are not considered while revoking privileges
- The grants can be added as a string (dba,'select any dictionary','create any table'), or in a list (ie.g for use with with_items)

        - name: append user privs
          oracle_grants:
            mode: sysdba
            schema: u_foo
            grants:
              - sysdg
              - select_catalog_role
            object_privs:
              - execute:dbms_random
            directory_privs:
              - read,write:data_pump_dir
            grant_mode: append

        - name: revoke user privs
          oracle_grants:
            mode: sysdba
            schema: u_foo
            grant_mode: exact


## **oracle_sql**

*pre-req: cx_Oracle*

- 2 modes: sql or script
- Executes arbitrary sql or runs a script

        tasks:
          - name: Query database
            oracle_sql:
              mode: sysdba
              sql: select host_name, instance_name from v$instance;
            register: dbinfo

          - name: dbinfo
            debug:
              var: dbinfo

        environment:
          ORACLE_HOME: "{{ ORACLE_HOME }}"
          ORACLE_SID:  "{{ ORACLE_SID }}"
        become: yes
        become_user: "{{ oracle_owner }}"
        become_method: sudo


**oracle_parameter**

pre-req: cx_Oracle

 - Manages init parameters in the database (i.e alter system set parameter...)
 - Also handles underscore parameters. That will require using mode=sysdba, to be able to read the X$ tables needed to verify the existence of the parameter.

**Note:**
 When specifying sga-parameters the database requests memory based on granules which are variable in size depending on the size requested,
 and that means the database may round the requested value to the nearest multiple of a granule.
 e.g sga_max_size=1500M will be rounded up to 1504 (which is 94 granules of 16MB). That will cause the displayed value to be 1504M, which has
 the effect that the next time the module is run with a desired value of 1500M it will be changed again.
 So that is something to consider when setting parameters that affects the SGA.


**oracle_services**

pre-req: cx_Oracle (if GI is not running)

  - Manages services in an Oracle database (RAC/Single instance)

**Note:**
At the moment, Idempotence only applies to the state (present,absent,started, stopped). No other options are considered.


**oracle_pdb**

pre-req: cx_Oracle

 - Manages pluggable databases in an Oracle container database
 - Creates/deletes/opens/closes the pdb
 - saves the state if you want it to. Default is yes
 - Can place the datafiles in a separate location


**oracle_asmdg**

pre-req: cx_Oracle

- Manages ASM diskgroup state. (absent/present)
- Takes a list of disks and makes sure those disks are part of the DG.
If the disk is removed from the disk it will be removed from the DG.
- Also manages attributes

**Note:**
- Supports redundancy levels, but does not yet handle specifying failuregroups


**oracle_asmvol**

- Manages ASM volumes. (absent/present)

**oracle_ldapuser**

pre-req: cx_Oracle, ldap, re

- Syncronises users/role grants from LDAP/Active Directory to the database

**oracle_privs**

pre-req: cx_Oracle, re

- Manages system and object level grants
- Object level grant support wildcards, so now it is possible to grant access to all tables in a schema and maintain it automatically!

**oracle_jobclass**

pre-req: cx_Oracle

- Manages DBMS_SCHEDULER job classes

**oracle_jobschedule**

pre-req: cx_Oracle, re

- Manages DBMS_SCHEDULER job schedules

**oracle_jobwindow**

pre-req: cx_Oracle, datetime

- Manages DBMS_SCHEDULER windows

**oracle_job**

pre-req: cx_Oracle, re

- Manages DBMS_SCHEDULER jobs

**oracle_rsrc_consgroup**

pre-req: cx_Oracle, re

- Manages resource manager consumer groups including its mappings and grants

**oracle_awr**

pre-req: cx_Oracle, datetime

- Manages AWR snapshot settings

**oracle_gi_facts**

- Gathers facts about Grid Infrastructure cluster configuration

**oracle_stats_prefs**

pre-req: cx_Oracle

- Managing DBMS_STATS global preferences
