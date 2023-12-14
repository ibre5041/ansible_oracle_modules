from __future__ import absolute_import, division, print_function

__metaclass__ = type

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
        self.oracle_gi_managed = False
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
                            self.oracle_restart = True
                            self.oracle_gi_managed = True
                        if local_only.upper() == 'FALSE':
                            self.oracle_install_type = 'CRS'
                            self.oracle_crs = True
                            self.oracle_gi_managed = True
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
            self.homes[ORACLE_HOME] = {'ORACLE_HOME': ORACLE_HOME, 'ORACLE_BASE': ORACLE_BASE}

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
            if ORACLE_HOME and ORACLE_HOME in self.homes[ORACLE_HOME]:
                ORACLE_BASE = self.homes[ORACLE_HOME]['ORACLE_BASE']
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
