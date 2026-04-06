#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_jobclass
short_description: Manage DBMS_SCHEDULER job classes in Oracle database
description:
    - Manage DBMS_SCHEDULER job classes in Oracle database
    - Can be run locally on the controlmachine or on a remote host
version_added: "2.2.1"
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
        choices: ['normal','sysdba','sysdg','sysoper','sysasm']
    oracle_home:
        description:
            - The ORACLE_HOME path
        required: false
        aliases: ['oh']
    dsn:
        description:
            - Oracle Data Source Name (connect string or TNS alias), overrides hostname/port/service_name
        required: false
        aliases: ['datasource_name']
    state:
        description:
            - If present, job class is created if absent then job class is removed
        required: true
        choices: ['present','absent']
    name:
        description:
            - Job class name
        required: True
    resource_group:
        description:
            - Resource manager resource consumer group the class is associated with
        required: False
    service:
        description:
            - Database service under what jobs run as
        required: False
    logging:
        description:
            - How much information is logged
        default: failed runs
        choices: ["off","runs","failed runs","full"]
    history:
        description:
            - Number of days the logs for this job class are retained
            - If set to 0, no logs will be kept
        required: False
        type: int
    comments:
        description:
            - Comment about the class
        required: False

notes:
    - oracledb needs to be installed
    - Oracle RDBMS 10gR2 or later required
requirements: [ "oracledb" ]
author: Ilmar Kerm, ilmar.kerm@gmail.com, @ilmarkerm
'''

EXAMPLES = '''
---
- hosts: localhost
  vars:
    oraclehost: 192.168.56.101
    oracleport: 1521
    oracleservice: orcl
    oracleuser: system
    oraclepassword: oracle
    oracle_env:
      ORACLE_HOME: /usr/lib/oracle/12.1/client64
      LD_LIBRARY_PATH: /usr/lib/oracle/12.1/client64/lib
  tasks:
    - name: job class
      oracle_jobclass:
        hostname: "{{ oraclehost }}"
        port: "{{ oracleport }}"
        service_name: "{{ oracleservice }}"
        user: "{{ oracleuser }}"
        password: "{{ oraclepassword }}"
        state: present
        name: testclass
        logging: failed runs
        history: 14
      environment: "{{ oracle_env }}"
'''

import re



def apply_session_container(module, conn):
    session_container = module.params.get("session_container")
    if not session_container:
        return
    if not re.match(r'^[A-Za-z][A-Za-z0-9_$#]*$', session_container):
        module.fail_json(msg='Invalid session_container for alter session', changed=False)
    c = conn.cursor()
    c.execute('ALTER SESSION SET CONTAINER = %s' % session_container)

def query_existing(job_class_name):
    c = conn.cursor()
    c.execute("SELECT resource_consumer_group, service, logging_level, log_history, comments FROM all_scheduler_job_classes WHERE owner = 'SYS' AND job_class_name = :jobclass",
        {"jobclass": job_class_name.upper()})
    result = c.fetchone()
    if c.rowcount > 0:
        return {"exists": True, "resource_group": result[0], "service": result[1], "logging": result[2], "history": result[3], "comments": result[4]}
    else:
        return {"exists": False}

# Ansible code
def main():
    global lconn, conn, msg, module
    msg = ['']
    module = AnsibleModule(
        argument_spec = dict(
            hostname      = dict(default='localhost'),
            port          = dict(default=1521, type='int'),
            service_name  = dict(required=True),
            user          = dict(required=False),
            password      = dict(required=False, no_log=True),
            mode          = dict(default='normal', choices=["normal", "sysdba", "sysdg", "sysoper", "sysasm"]),
            oracle_home   = dict(required=False, aliases=['oh']),
            dsn           = dict(required=False, aliases=['datasource_name']),
            session_container = dict(required=False),
            state         = dict(default="present", choices=["present", "absent"]),
            name          = dict(required=True),
            resource_group= dict(required=False),
            service       = dict(required=False),
            logging       = dict(default="failed runs", choices=["off","runs","failed runs","full"]),
            history       = dict(required=False, type='int'),
            comments      = dict(required=False)
        ),
        supports_check_mode=True
    )
    sanitize_string_params(module.params)
    # Connect to database
    oc = oracleConnection(module)
    conn = oc.conn
    if conn.version < "10.2":
        module.fail_json(msg="Database version must be 10gR2 or greater", changed=False)
    apply_session_container(module, conn)
    #
    result = query_existing(module.params['name'])
    if module.check_mode:
        would_change = (
            (result['exists'] and module.params['state'] == "absent") or
            (not result['exists'] and module.params['state'] == "present") or
            (
                result['exists'] and module.params['state'] == "present" and (
                    (result['comments'] != module.params['comments']) or
                    (result['resource_group'] != module.params['resource_group']) or
                    (result['service'] != module.params['service']) or
                    (result['history'] != module.params['history']) or
                    (result['logging'] != module.params['logging'].upper())
                )
            )
        )
        module.exit_json(changed=would_change, msg='Check mode: no change executed')
    #
    #c = conn.cursor()
    result_changed = False
    if result['exists'] and module.params['state'] == "present":
        # Check attributes and modify if needed
        if (result['comments'] != module.params['comments']) or (result['resource_group'] != module.params['resource_group']) or (result['service'] != module.params['service']) or (result['history'] != module.params['history']) or (result['logging'] != module.params['logging'].upper()):
            c = conn.cursor()
            c.execute("""
            DECLARE
                v_name VARCHAR2(100);
                v_service VARCHAR2(100);
                v_logging PLS_INTEGER;
                v_history PLS_INTEGER;
                v_resource VARCHAR2(100);
                v_comments VARCHAR2(4000);
            BEGIN
                v_logging:= CASE :logging WHEN 'off' THEN DBMS_SCHEDULER.LOGGING_OFF
                                          WHEN 'runs' THEN DBMS_SCHEDULER.LOGGING_RUNS
                                          WHEN 'failed runs' THEN DBMS_SCHEDULER.LOGGING_FAILED_RUNS
                                          WHEN 'full' THEN DBMS_SCHEDULER.LOGGING_FULL
                            END;
                v_name:= 'SYS.'||:name;
                v_resource:= :resource;
                v_service:= :service;
                v_history:= :history;
                v_comments:= :comments;
                DBMS_SCHEDULER.SET_ATTRIBUTE(v_name, 'logging_level', v_logging);
                IF v_resource IS NOT NULL THEN
                    DBMS_SCHEDULER.SET_ATTRIBUTE(v_name, 'resource_consumer_group', v_resource);
                ELSE
                    DBMS_SCHEDULER.SET_ATTRIBUTE_NULL(v_name, 'resource_consumer_group');
                END IF;
                IF v_service IS NOT NULL THEN
                    DBMS_SCHEDULER.SET_ATTRIBUTE(v_name, 'service', v_service);
                ELSE
                    DBMS_SCHEDULER.SET_ATTRIBUTE_NULL(v_name, 'service');
                END IF;
                IF v_history IS NOT NULL THEN
                    DBMS_SCHEDULER.SET_ATTRIBUTE(v_name, 'log_history', v_history);
                ELSE
                    DBMS_SCHEDULER.SET_ATTRIBUTE_NULL(v_name, 'log_history');
                END IF;
                IF v_comments IS NOT NULL THEN
                    DBMS_SCHEDULER.SET_ATTRIBUTE(v_name, 'comments', v_comments);
                ELSE
                    DBMS_SCHEDULER.SET_ATTRIBUTE_NULL(v_name, 'comments');
                END IF;
            END;
            """, {
                "logging": module.params['logging'],
                "name": module.params['name'].upper(),
                "resource": module.params['resource_group'],
                "service": module.params['service'],
                "history": module.params['history'],
                "comments": module.params['comments']
            })
            result_changed = True
    elif result['exists'] and module.params['state'] == "absent":
        # Drop job class
        c = conn.cursor()
        c.execute("BEGIN DBMS_SCHEDULER.DROP_JOB_CLASS(:name); END;", {"name": module.params['name'].upper()})
        result_changed = True
    elif not result['exists'] and module.params['state'] == "present":
        # Create job class
        c = conn.cursor()
        c.execute("""
        DECLARE
            v_logging PLS_INTEGER;
        BEGIN
            v_logging:= CASE :logging WHEN 'off' THEN DBMS_SCHEDULER.LOGGING_OFF
                                      WHEN 'runs' THEN DBMS_SCHEDULER.LOGGING_RUNS
                                      WHEN 'failed runs' THEN DBMS_SCHEDULER.LOGGING_FAILED_RUNS
                                      WHEN 'full' THEN DBMS_SCHEDULER.LOGGING_FULL
                        END;
            DBMS_SCHEDULER.CREATE_JOB_CLASS(job_class_name=>:name, resource_consumer_group=>:resource, service=>:service,
                logging_level=>v_logging, log_history=>:history, comments=>:comments);
        END;""", {
            "logging": module.params['logging'],
            "name": module.params['name'].upper(),
            "resource": module.params['resource_group'],
            "service": module.params['service'],
            "history": module.params['history'],
            "comments": module.params['comments']
        })
        result_changed = True

    conn.commit()
    module.exit_json(msg=", ".join(msg), changed=result_changed)


from ansible.module_utils.basic import *
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import (  # noqa: E501
        oracleConnection, sanitize_string_params,
    )
except ImportError:
    def sanitize_string_params(module_params):
        for key, value in module_params.items():
            if isinstance(value, str):
                module_params[key] = value.strip()

    class oracleConnection:  # noqa: N801
        def __init__(self, module):
            module.fail_json(msg='oracle_utils is required. Ensure the collection is properly installed.', changed=False)
if __name__ == '__main__':
    main()
