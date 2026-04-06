#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_jobschedule
short_description: Manage DBMS_SCHEDULER job schedules in Oracle database
description:
    - Manage DBMS_SCHEDULER job schedules in Oracle database
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
        choices: ['normal','sysdba']
    state:
        description:
            - If present, job schedule is created, if absent then schedule is dropped
        required: true
        choices: ['present','absent']
    name:
        description:
            - Job schedule name
        required: True
    repeat_interval:
        description:
            - Schedule repeat interval using DBMS_SCHEDULER calendaring syntax
        required: True
        aliases:
            - interval
    comments:
        description:
            - Comment about the class
        required: False
    convert_to_upper:
        description:
            - Schedule name automatically converted to upper case
        required: false
        default: True
        type: bool

notes:
    - oracledb needs to be installed
    - Oracle RDBMS 10gR2 or later required
requirements: [ "oracledb", "re" ]
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
    - name: job schedule
      oracle_jobschedule:
        hostname: "{{ oraclehost }}"
        port: "{{ oracleport }}"
        service_name: "{{ oracleservice }}"
        user: "{{ oracleuser }}"
        password: "{{ oraclepassword }}"
        state: present
        name: hr.hourly_schedule
        interval: FREQ=HOURLY; INTERVAL=1
        comments: Just for testing
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

def query_existing(owner, name):
    c = conn.cursor()
    c.execute("SELECT repeat_interval, comments FROM all_scheduler_schedules WHERE owner = :owner AND schedule_name = :name",
        {"owner": owner, "name": name})
    result = c.fetchone()
    if c.rowcount > 0:
        return {"exists": True, "repeat_interval": result[0], "comments": result[1]}
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
            repeat_interval = dict(required=True, aliases=['interval']),
            comments      = dict(required=False),
            convert_to_upper = dict(default=True, type='bool')
        ),
        supports_check_mode=True
    )
    sanitize_string_params(module.params)
    # Check input parameters
    re_name = re.compile("^[A-Za-z0-9_\$#]+\.[A-Za-z0-9_\$#]+$")
    if not re_name.match(module.params['name']):
        module.fail_json(msg="Invalid schedule name")
    job_fullname = module.params['name'].upper() if module.params['convert_to_upper'] else module.params['name']
    job_parts = job_fullname.split(".")
    job_owner = job_parts[0]
    job_name = job_parts[1]
    job_fullname = "\"%s\".\"%s\"" % (job_owner, job_name)
    # Connect to database
    oc = oracleConnection(module)
    conn = oc.conn
    apply_session_container(module, conn)
    #
    result = query_existing(job_owner, job_name)
    if module.check_mode:
        would_change = (
            (result['exists'] and module.params['state'] == "absent") or
            (not result['exists'] and module.params['state'] == "present") or
            (
                result['exists'] and module.params['state'] == "present" and (
                    (result['comments'] != module.params['comments']) or
                    (result['repeat_interval'] != module.params['repeat_interval'])
                )
            )
        )
        module.exit_json(changed=would_change, msg='Check mode: no change executed')
    #
    #c = conn.cursor()
    result_changed = False
    if result['exists'] and module.params['state'] == "present":
        # Check attributes and modify if needed
        if (result['comments'] != module.params['comments']) or (result['repeat_interval'] != module.params['repeat_interval']):
            c = conn.cursor()
            c.execute("""
            DECLARE
                v_name VARCHAR2(100);
                v_interval VARCHAR2(1000);
                v_comments VARCHAR2(4000);
            BEGIN
                v_name:= :name;
                v_interval:= :interval;
                v_comments:= :comments;
                DBMS_SCHEDULER.SET_ATTRIBUTE(v_name, 'repeat_interval', v_interval);
                IF v_comments IS NOT NULL THEN
                    DBMS_SCHEDULER.SET_ATTRIBUTE(v_name, 'comments', v_comments);
                ELSE
                    DBMS_SCHEDULER.SET_ATTRIBUTE_NULL(v_name, 'comments');
                END IF;
            END;
            """, {
                "name": job_fullname,
                "interval": module.params['repeat_interval'],
                "comments": module.params['comments']
            })
            result_changed = True
    elif result['exists'] and module.params['state'] == "absent":
        # Drop job class
        c = conn.cursor()
        c.execute("BEGIN DBMS_SCHEDULER.DROP_SCHEDULE(:name); END;", {"name": job_fullname})
        result_changed = True
    elif not result['exists'] and module.params['state'] == "present":
        # Create job class
        c = conn.cursor()
        c.execute("""
        BEGIN
            DBMS_SCHEDULER.CREATE_SCHEDULE(schedule_name=>:name, repeat_interval=>:interval, comments=>:comments);
        END;""", {
            "name": job_fullname,
            "interval": module.params['repeat_interval'],
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
if __name__ == '__main__':
    main()
