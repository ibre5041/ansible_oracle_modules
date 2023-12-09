#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_oratab
short_description: Reads oratab to ansible_facts
description:
  - Reads SID and ORACLE_HOME path from oratab, crs and running processes to ansible_facts
  - Should be able to detect all ORACLE_HOMEs on a server crs, restart, database, client, golden gate
  - More datailed example is here: 
  - "https://github.com/ibre5041/ansible_oracle_modules_example/blob/main/oracle_oratab.yml"
version_added: "3.0.0"
options:
  writable_only:
    description: Return only databases openned READ WRITE
    required: False
    default: False
  asm_only:
    description: Return only ASM instances
    required: False
    default: False
  running_only:
    description: Return only instances which are running
    required: False
    default: False
  open_only:
    description: Return only databases which are OPEN
    required: False
    default: False
notes:
  - Has to run either as root or oracle db owner
requirements:
  - xml.dom
author: 
  - Ivan Brezina
'''

EXAMPLES = '''
- name: Read oratab, detect all ORACLE_HOMEs and writable database
  oracle_oratab:
    writable_only: True
  register: sid_list

- debug:
    var: sid_list

# More datailed example is here: 
# https://github.com/ibre5041/ansible_oracle_modules_example/blob/main/oracle_oratab.yml
# 
'''

import fcntl
import os
from pathlib import Path
import pwd
import subprocess
import re
import glob
import subprocess
import socket
from pwd import getpwuid
from xml.dom import minidom

from ansible.module_utils.basic import AnsibleModule

class oracle_homes():

    def __init__(self, module = None):
        self.facts_item = {}
        self.running_only = False
        self.open_only = False
        self.writable_only = False        
        self.oracle_restart = False
        self.oracle_crs = False
        self.oracle_standalone = False
        self.oracle_install_type = None
        self.crs_home = None
        self.homes = {}
        self.ora_inventory = None
        self.orabase = None
        self.crsctl = None
        self.module = module      # possible reference onto AnsibleModule

        # Check whether CRS/HAS is installed
        try:
            with open('/etc/oracle/ocr.loc') as f:
                for line in f:
                    if line.startswith('local_only='):
                        (_, local_only,) = line.strip().split('=')
                        if local_only.upper() == 'TRUE':
                            self.oracle_install_type = 'RESTART'
                        if local_only.upper() == 'FALSE':
                            self.oracle_install_type = 'CRS'
        except:
            pass

        # Try to detect CRS_HOME
        try:
            with open('/etc/oracle/olr.loc') as f:
                for line in f:
                    if line.startswith('crs_home='):
                        (_, crs_home,) = line.strip().split('=')
                        self.crs_home = crs_home

                        crsctl = os.path.join(crs_home, 'bin', 'crsctl')
                        if os.access(crsctl, os.X_OK):
                            self.crsctl = crsctl
        except:
            pass

        # Try to parse inventory.xml file to get list of ORACLE_HOMEs
        try:
            with open('/etc/oraInst.loc') as f:
                for line in f:
                    if line.startswith('inventory_loc='):
                        (_, oraInventory,) = line.strip().split('=')
                        self.ora_inventory = oraInventory

            from xml.dom import minidom
            inv_tree = minidom.parse(os.path.join(self.ora_inventory, 'ContentsXML', 'inventory.xml'))
            homes = inv_tree.getElementsByTagName('HOME')
            for home in homes:
                # TODO: skip for deleted ORACLE_HOME
                self.add_home(home.attributes['LOC'].value)
        except:
            pass

        
    def module_warn(msg):
        if self.module:
            module.warn(msg)


    def module_fail_json(msg='', changed=False):
        if self.module:
            module.fail_json(msg=msg, changed=changed)
        else:
            os.exit(1)

        
    def parse_oratab(self):
        # Reads SID and ORACLE_HOME from oratab
        with open('/etc/oratab', 'r') as oratab:
            for line in oratab:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    continue

                ORACLE_SID, ORACLE_HOME, _ = line.split(':')
                self.add_sid(ORACLE_SID=ORACLE_SID, ORACLE_HOME=ORACLE_HOME)

    def list_processes(self):
        """
        # Emulate trick form tanelpoder
        # https://tanelpoder.com/2011/02/28/finding-oracle-homes-with/
        #
        # printf "%6s %-20s %-80s\n" "PID" "NAME" "ORACLE_HOME"
        # pgrep -lf _pmon_ |
        #  while read pid pname  y ; do
        #    printf "%6s %-20s %-80s\n" $pid $pname `ls -l /proc/$pid/exe | awk -F'>' '{ print $2 }' | sed 's/bin\/oracle$//' | sort | uniq`
        #  done
        #
        # It s basically looking up all PMON process IDs and then using /proc/PID/exe link to find out where is the oracle binary of a running process located
        #
        """
        for cmd_line_file in glob.glob('/proc/[0-9]*/cmdline'):
            try:
                with open(cmd_line_file) as x:
                    cmd_line = x.read().rstrip("\x00")
                    if not cmd_line.startswith('ora_pmon_') and not cmd_line.startswith('asm_pmon_'):
                        continue
                    _, _, ORACLE_SID = cmd_line.split('_', 2)

                    piddir = os.path.dirname(cmd_line_file)
                    exefile = os.path.join(piddir, 'exe')

                    try:
                        if self.facts_item[ORACLE_SID]['ORACLE_HOME']:
                            self.add_sid(ORACLE_SID, running=True)
                            continue
                    except:
                        pass

                    try:
                        if not os.path.islink(exefile):
                            continue
                        oraclefile = os.readlink(exefile)
                        ORACLE_HOME = os.path.dirname(oraclefile)
                        ORACLE_HOME = os.path.dirname(ORACLE_HOME)
                    except:
                        # In case oracle binary is suid, ptrace does not work,
                        # stat/readlink /proc/<pid>/exec does not work
                        # fails with: Permission denied
                        # Then try to query the same information from CRS (if possible)
                        ORACLE_HOME = None

                        if self.crsctl:
                            if cmd_line.startswith('asm'):
                                dfiltertype = 'ora.asm.type'
                                ORACLE_HOME = self.crs_home
                            else:
                                dfiltertype = 'ora.database.type'
                            dfilter = '((TYPE = {}) and (GEN_USR_ORA_INST_NAME = {}))'.format(dfiltertype, ORACLE_SID)
                            proc = subprocess.Popen([self.crsctl, 'stat', 'res', '-p', '-w', dfilter],
                                                    stdout=subprocess.PIPE)
                            for line in iter(proc.stdout.readline, ''):
                                if line.decode('utf-8').startswith('ORACLE_HOME='):
                                    (_, ORACLE_HOME,) = line.decode('utf-8').strip().split('=')
                                proc.poll()
                                if proc.returncode is not None:
                                    break
                        pass                    
                    if not ORACLE_HOME:
                        own_uid = os.geteuid()
                        ora_uid = os.stat(cmd_line_file).st_uid
                        if self.crsctl:
                            crs_uid = os.stat(self.crsctl).st_uid
                        else:
                            crs_uid = None
                        if own_uid != 0 and own_uid != ora_uid:
                            module_fail_json(msg='I(uid={}) am not oracle process owner(uid={}) and I am not root'.format(own_uid, ora_uid), changed=False)

                    self.add_sid(ORACLE_SID=ORACLE_SID, ORACLE_HOME=ORACLE_HOME, running=True)

            # except FileNotFoundError: # Python3
            except EnvironmentError as e:
                # print("Missing file ignored: {} ({})".format(cmd_line_file, e))
                pass

    def list_crs_instances(self):
        hostname = socket.gethostname().split('.')[0]
        if self.crsctl:
            for dfiltertype in ['ora.database.type']:  # ora.asm.type does not report ORACLE_HOME
                # for dfiltertype in ['ora.asm.type', 'ora.database.type']:
                dfilter = '(TYPE = {})'.format(dfiltertype)
                proc = subprocess.Popen([self.crsctl, 'stat', 'res', '-p', '-w', dfilter], stdout=subprocess.PIPE)
                (ORACLE_HOME, ORACLE_SID) = (None, None)
                for line in iter(proc.stdout.readline, ''):
                    line = line.decode('utf-8')
                    if not line.strip():
                        (ORACLE_HOME, ORACLE_SID) = (None, None)
                    if 'SERVERNAME({})'.format(hostname) in line and line.startswith('GEN_USR_ORA_INST_NAME'):
                        (_, ORACLE_SID,) = line.strip().split('=')
                    if line.startswith('ORACLE_HOME='):
                        (_, ORACLE_HOME,) = line.strip().split('=')
                    if ORACLE_SID and ORACLE_HOME:
                        self.add_sid(ORACLE_SID=ORACLE_SID, ORACLE_HOME=ORACLE_HOME)
                        (ORACLE_HOME, ORACLE_SID) = (None, None)
                    proc.poll()
                    if proc.returncode is not None:
                        break

    def base_from_home(self, ORACLE_HOME):
        """ execute $ORACLE_HOME/bin/orabase to get ORACLE_BASE """
        orabase = os.path.join(ORACLE_HOME, 'bin', 'orabase')
        ORACLE_BASE = None
        if os.access(orabase, os.X_OK):
            proc = subprocess.Popen([orabase], stdout=subprocess.PIPE, env={'ORACLE_HOME': ORACLE_HOME})
            for line in iter(proc.stdout.readline, ''):
                if line.strip():
                    ORACLE_BASE = line.strip().decode()
                else:
                    break
        return ORACLE_BASE

    def add_home(self, ORACLE_HOME):
        if ORACLE_HOME and ORACLE_HOME not in self.homes:
            ORACLE_BASE = self.base_from_home(ORACLE_HOME)

            try:
                inventory_path = os.path.join(ORACLE_HOME, 'inventory', 'ContentsXML', 'comps.xml')
                inv_tree = minidom.parse(inventory_path)
                components = inv_tree.getElementsByTagName('COMP')
                oracle_owner = getpwuid(os.stat(inventory_path).st_uid).pw_name
                for comp in components:
                    component_name = comp.attributes['NAME'].value
                    if component_name == "oracle.client":
                        component_name = 'client'
                        break
                    elif component_name == "oracle.server":
                        component_name = "server"
                        break
                    elif component_name == "oracle.crs":
                        component_name = "crs"
                        break
                    elif component_name == "oracle.tg":
                        component_name = "gateway"
                        break
            except:
                component_name = 'unknown'
                oracle_owner = 'unknown'
            self.homes[ORACLE_HOME] = {'ORACLE_HOME': ORACLE_HOME
                , 'ORACLE_BASE': ORACLE_BASE
                , 'home_type': component_name
                , 'owner': oracle_owner}

    def add_sid(self, ORACLE_SID, ORACLE_HOME=None, running=False):
        if ORACLE_SID in self.facts_item:
            sid = self.facts_item[ORACLE_SID]
            if ORACLE_HOME:
                sid['ORACLE_HOME'] = ORACLE_HOME
            if running:
                sid['running'] = running
            if running is not None and sid['running'] is not True:
                sid['running'] = running
        else:
            self.add_home(ORACLE_HOME)
            if ORACLE_HOME and ORACLE_HOME in self.homes:
                ORACLE_BASE = self.homes[ORACLE_HOME]['ORACLE_BASE']
            elif ORACLE_HOME:
                ORACLE_BASE = self.base_from_home(ORACLE_HOME)
            else:
                ORACLE_BASE = None
            self.facts_item[ORACLE_SID] = {'ORACLE_SID': ORACLE_SID
                , 'ORACLE_HOME': ORACLE_HOME
                , 'ORACLE_BASE': ORACLE_BASE
                , 'running': running}
            
    def query_db_status(self, oracle_owner, oracle_home, oracle_sid):
        sqlplus_path = Path(oracle_home, 'bin', 'sqlplus')
        args = [str(sqlplus_path), '-S', '/', 'as', 'sysdba']
        pw_record = pwd.getpwnam(oracle_owner)
        user_name      = pw_record.pw_name
        user_home_dir  = pw_record.pw_dir
        user_uid       = pw_record.pw_uid
        user_gid       = pw_record.pw_gid
        user_gids      = os.getgrouplist(user_name, user_gid)
        env = os.environ.copy()
        env[ 'HOME'     ]   = user_home_dir
        env[ 'LOGNAME'  ]   = user_name
        env[ 'PWD'      ]   = '/'
        env[ 'USER'     ]   = user_name
        env[ 'ORACLE_HOME'] = oracle_home
        env[ 'ORACLE_SID']  = oracle_sid

        if os.getuid() == 0:
            process = subprocess.Popen(args,
                                       preexec_fn=self.demote(user_uid, user_gid, user_gids),
                                       cwd='/', env=env, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        elif os.getuid() == user_uid:        
            process = subprocess.Popen(args,
                                       cwd='/', env=env, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        else:
            self.module_fail_json(msg='Can not execute sqlplus(uid={})'.format(user_uid), changed=False)
            return []

        sql = """
        select status from v$instance;
        select open_mode from v$database;
        select count(*) as ora_dg_on from v$archive_dest where status = 'VALID' AND target = 'STANDBY';
        select database_role from v$database;
        EXIT
        """

        header = None
        delim  = False
        value  = None
        r      = {}
        out = process.communicate(input=sql.encode(), timeout=5)
        for l in out[0].decode('utf-8').splitlines():
            #module_warn("{}:{}".format(oracle_sid,l.rstrip()))
            if l.strip() in ('STATUS', 'OPEN_MODE', 'ORA_DG_ON', 'DATABASE_ROLE'):
                header = l.strip()
                delim  = False
                value  = None
            elif l.rstrip().startswith('-------'):
                delim  = True
                value = None
            elif l.rstrip() and header and delim and value is None:
                value = l.strip()
                r[header] = value
                header = None
                delim  = False
                value  = False        
        #module_warn(str(r))
        #module_warn("Exit code {}".format(process.returncode))
        if oracle_sid.startswith('+ASM') and r['STATUS'] == 'STARTED':
            return ['ASM', 'STARTED']
        elif oracle_sid.startswith('+ASM'):
            return ['ASM']

        if r['STATUS'] == 'STARTED':
            return ['STARTED']
        elif r['STATUS'] == 'MOUNTED' and int(r['ORA_DG_ON']):
            return ['MOUNTED', 'STANDBY']
        elif r['STATUS'] == 'MOUNTED':
            return ['MOUNTED']    
        elif r['STATUS'] == 'OPEN' and int(r['ORA_DG_ON']):
            return ['OPEN', 'PRIMARY', r['OPEN_MODE']]
        elif r['STATUS'] == 'OPEN':
            return ['OPEN', r['OPEN_MODE']]

    @staticmethod    
    def demote(user_uid, user_gid, supplementary_groups):
        def result():
            os.setgroups(supplementary_groups)
            os.setgid(user_gid)
            os.setegid(user_gid)
            os.setuid(user_uid)
            os.seteuid(user_uid)
        return result


# Ansible code
def main():
    oracle_list = []
    module = AnsibleModule(
        argument_spec = dict(
            asm_only = dict(default=False, type="bool"),            
            running_only = dict(default=False, type="bool"),
            open_only = dict(default=False, type="bool"),
            writable_only = dict(default=False, type="bool"),
            homes = dict(default=None, choices=[None, 'all', 'client', 'server', 'crs', 'gateway']),
            facts_item = dict()
         ),
        supports_check_mode=True
    )
    asm_only = module.params['asm_only']    
    running_only = module.params['running_only']
    open_only = module.params['open_only']
    writable_only = module.params['writable_only']
    homes = module.params['homes']

    h = oracle_homes(module)
    h.list_crs_instances()
    h.list_processes()
    h.parse_oratab()

    for sid in list(h.facts_item):
        try:
            sqlplus_path = Path(h.facts_item[sid]['ORACLE_HOME'], 'bin', 'oracle')
            oracle_owner = getpwuid(os.stat(sqlplus_path).st_uid).pw_name
            h.facts_item[sid]['owner'] = oracle_owner
        except:
            pass

        if h.facts_item[sid]["running"]:
            status = h.query_db_status(oracle_owner = h.facts_item[sid]['owner']
                                       , oracle_home = h.facts_item[sid]['ORACLE_HOME']
                                       , oracle_sid = h.facts_item[sid]['ORACLE_SID'])
            h.facts_item[sid]['status'] = status
        else:
            h.facts_item[sid]['status'] = ['DOWN']
        
    if running_only:
        for sid in list(h.facts_item):
            if not h.facts_item[sid]["running"]:
                del h.facts_item[sid]
                module.warn('ORACLE_SID: {} is down'.format(sid))

    if asm_only:
        for sid in list(h.facts_item):
            if 'ASM' not in h.facts_item[sid]["status"]:
                del h.facts_item[sid]
                module.warn('ORACLE_SID: {} is not ASM'.format(sid))
                
    if running_only:
        for sid in list(h.facts_item):
            if not h.facts_item[sid]["running"]:
                del h.facts_item[sid]
                module.warn('ORACLE_SID: {} is down'.format(sid))

    if open_only:
        for sid in list(h.facts_item):
            if 'OPEN' not in h.facts_item[sid]["status"]:
                del h.facts_item[sid]
                module.warn('ORACLE_SID: {} is not open'.format(sid))

    if writable_only:
        for sid in list(h.facts_item):
            if 'READ WRITE' not in h.facts_item[sid]["status"]:
                del h.facts_item[sid]
                module.warn('ORACLE_SID: {} is not open'.format(sid))
                
    #module.warn('uid {}'.format(os.getuid()))

    if homes:
        for home in list(h.homes):
            if homes == 'all':
                continue
            elif homes == 'client' and h.homes[home]['home_type'] != 'client':
                del h.homes[home]
            elif homes == 'server' and h.homes[home]['home_type'] != 'server':
                del h.homes[home]
            elif homes == 'crs' and h.homes[home]['home_type'] != 'crs':
                del h.homes[home]
            elif homes == 'gateway' and h.homes[home]['home_type'] != 'gateway':
                del h.homes[home]

    module.exit_json(oracle_list=h.facts_item, oracle_homes=h.homes, changed=False)


if __name__ == '__main__':
    main()
