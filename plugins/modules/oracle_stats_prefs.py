#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_stats_prefs
short_description: Manage DBMS_STATS global preferences
description:
    - Manage DBMS_STATS global preferences
    - Can be run locally on the controlmachine or on a remote host
version_added: "2.4"
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
    preference_name:
        description:
            - DBMS_STATS preference name
        aliases:
            - pname
    preference_value:
        description:
            - Preference value
        aliases:
            - pvalue
    state:
        description:
            - Either to set the preference (present) or reset it to default (absent)
        required: true
        default: present
        choices: ['present','absent']
notes:
    - cx_Oracle needs to be installed
    - Oracle RDBMS 10gR2 or later required
requirements: [ "cx_Oracle" ]
author: Ilmar Kerm, ilmar.kerm@gmail.com, @ilmarkerm
'''

EXAMPLES = '''
---
- hosts: localhost
  vars:
    oraclehost: 192.168.56.102
    oracleport: 1521
    oracleservice: orcl
    oracleuser: system
    oraclepassword: oracle
    oracle_env:
      ORACLE_HOME: /usr/lib/oracle/12.1/client64
      LD_LIBRARY_PATH: /usr/lib/oracle/12.1/client64/lib
  tasks:
    - name: set dbms_stats settings
      oracle_stats_prefs:
        hostname: "{{ oraclehost }}"
        port: "{{ oracleport }}"
        service_name: "{{ oracleservice }}"
        user: "{{ oracleuser }}"
        password: "{{ oraclepassword }}"
        pname: TABLE_CACHED_BLOCKS
        pvalue: 16
      environment: "{{ oracle_env }}"
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
            preference_name  = dict(required=True, aliases=['pname']),
            preference_value = dict(aliases=['pvalue']),
            state         = dict(default='present', choices=["present","absent"])
        ),
        supports_check_mode=True
    )
    # Check for required modules
    if not cx_oracle_exists:
        module.fail_json(msg="The cx_Oracle module is required. 'pip install cx_Oracle' should do the trick. If cx_Oracle is installed, make sure ORACLE_HOME & LD_LIBRARY_PATH is set")
    # Connect to database
    conn = oracle_connect(module)
    
    if conn.version < "10.2":
        module.fail_json(msg="Database version must be 10gR2 or greater", changed=False)
    #
    if module.check_mode:
        module.exit_json(changed=False)
    #
    c = conn.cursor()
    var_changed = c.var(cx_Oracle.NUMBER)
    var_msg = c.var(cx_Oracle.STRING)
    c.execute("""
    DECLARE
        v_param_name VARCHAR2(100);
        v_param_value VARCHAR2(100);
        v_current_v VARCHAR2(100);
        v_state VARCHAR2(10);
        v_msg VARCHAR2(200):= 'Not changed';
        v_changed NUMBER:= 0;
    BEGIN
        v_param_name:= :pname;
        v_param_value:= :pvalue;
        v_state:= :state;
        v_current_v:= DBMS_STATS.GET_PREFS(v_param_name);
        IF v_state = 'present' AND upper(v_param_value) != upper(v_current_v) THEN
            DBMS_STATS.SET_GLOBAL_PREFS(v_param_name, v_param_value);
            v_changed:= 1;
            v_msg:= 'Old value '||v_current_v||' changed to '||v_param_value;
        ELSIF v_state = 'absent' THEN
            DBMS_STATS.SET_GLOBAL_PREFS(v_param_name, NULL);
            v_param_value:= DBMS_STATS.GET_PREFS(v_param_name);
            IF v_param_value != v_current_v THEN
                v_msg:= 'Value reset to default '||v_param_value;
                v_changed:= 1;
            END IF;
        END IF;
        :changed:= v_changed;
        :msg:= v_msg;
    END;
    """, {'pname': module.params['preference_name'],
          'pvalue': module.params['preference_value'],
          'state': module.params['state'],
          'changed': var_changed, 'msg': var_msg}
    )
    result_changed = var_changed.getvalue() > 0
    msg[0] = var_msg.getvalue()
    module.exit_json(msg=", ".join(msg), changed=result_changed)


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
