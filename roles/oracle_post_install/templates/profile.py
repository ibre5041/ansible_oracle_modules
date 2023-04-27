#!/usr/bin/python3

import glob
import os
import argparse
import subprocess
import signal
import time
import json
import sys
import socket
import cx_Oracle

class database():
    
    def __init__(self):
        try:
            connection = cx_Oracle.connect(user='/', mode=cx_Oracle.SYSDBA)
            self._cursor = connection.cursor()
            self.ora_banner = None
            self.ora_alert_log = None
            self.ora_dbid = None
            self.ora_dg_on = None
            self.ora_dg_role = None
            self.ora_rac_nodes = None
            self.ora_rac_on = None
            self.ora_status = None
            self.ora_uptime = None
            self.ora_version = None
            self.ora_sgapga = None
            self.ora_type = ''
            self.sys_tbls = None

        except:
            self._cursor = None
            pass


    def fetch_single_value(self, sql):
        try:
            if not self._cursor:
                return None
            self._cursor.execute(sql)
            (retval,) = self._cursor.fetchone()
            return retval
        except (cx_Oracle.OperationalError, cx_Oracle.DatabaseError, cx_Oracle.InterfaceError) as e:
            #sys.stderr.write("{} failed with: {}".format(sql, str(e)))
            #raise BaseException("{} failed with: {}".format(sql, str(e)))
            return ""
        
    def instance(self):
        uptime = self.fetch_single_value(" select NUMTODSINTERVAL(sysdate - startup_time, 'day') from v$instance ")
        self.ora_uptime = str(uptime) if uptime else None
        status = self.fetch_single_value(" select status from v$instance ")
        self.ora_status = status if status else 'DOWN'

        self.ora_dbid = self.fetch_single_value(" SELECT dbid FROM v$database ")

        if self.ora_status not in ['STARTED', 'MOUNTED', 'DOWN']:
            self.sys_tbls = self.fetch_single_value(
                " SELECT file_name FROM dba_data_files WHERE tablespace_name = 'SYSTEM' AND ROWNUM = 1 ")
        else:
            self.sys_tbls = None
                
        self.ora_banner = self.fetch_single_value(" SELECT banner FROM v$version WHERE banner LIKE '%Oracle Database%' ")
        self.ora_version = self.fetch_single_value(" SELECT version from v$instance ")
        
        # This will fail on ASM, DBA_* views are nor accessible
        if self.ora_status not in ['STARTED', 'MOUNTED', 'DOWN']:
            if self.ora_version.startswith('11'):
                bundle = self.fetch_single_value(
                    """ SELECT nvl(max(ID) KEEP (DENSE_RANK LAST ORDER BY ACTION_TIME),0) 
                    FROM sys.registry$history where BUNDLE_SERIES='PSU' """)
                if bundle:
                    self.ora_version = self.ora_version.rstrip('0') + str(bundle)
            if self.ora_version.startswith('12'):
                bundle = self.fetch_single_value(
                    """ select MIN(BUNDLE_ID) KEEP (DENSE_RANK LAST ORDER BY ACTION_TIME) BUNDLE_ID 
                    from dba_registry_sqlpatch where status = 'SUCCESS' """)
                if bundle:
                    self.ora_version = self.ora_version.rstrip('0') + str(bundle)
            elif int(self.ora_version[0:2]) >= 18:
                bundle = self.fetch_single_value(
                    """ SELECT distinct REGEXP_SUBSTR(description, '[0-9]{2}.[0-9]{1,2}.[0-9].[0-9].[0-9]{6}') as VER
                    from dba_registry_sqlpatch 
                    where TARGET_VERSION in 
                    (SELECT max(TARGET_VERSION) KEEP (DENSE_RANK LAST ORDER BY ACTION_TIME) as VER 
                    FROM dba_registry_sqlpatch where status='SUCCESS' and FLAGS not like '%J%') and ACTION = 'APPLY' """)
                if bundle:
                    self.ora_version = str(bundle)

        # Alert log dest
        diag_dest = self.fetch_single_value(
            " SELECT max(value) as diag_dest FROM v$parameter WHERE name = 'diagnostic_dest' ")
        if diag_dest:
            self.ora_alert_log = self.fetch_single_value(
                " SELECT REPLACE(value,'cdump','trace') as alert_log from v$parameter where name ='core_dump_dest' ")
        else:
            self.ora_alert_log = self.fetch_single_value(
                " SELECT value as alert_log FROM v$parameter WHERE name = 'background_dump_dest' ")

        # RAC
        self.ora_rac_on = self.fetch_single_value(
            " SELECT value as ora_rac_on FROM v$parameter WHERE name = 'cluster_database' ")
        self.ora_rac_nodes = self.fetch_single_value(
            " SELECT count(*) as ora_rac_nodes FROM v$active_instances ")
        if self.ora_rac_on == 'TRUE':
            self.ora_type = 'RAC'

        self.ora_dg_role = self.fetch_single_value(" SELECT database_role FROM v$database ")
        self.ora_dg_on = self.fetch_single_value(
            " SELECT count(*) as ora_dg_on FROM v$archive_dest WHERE status = 'VALID' AND target = 'STANDBY' ")
        ora_apply = self.fetch_single_value(" select count(1) from V$MANAGED_STANDBY where process like ('MRP%') ")
        if ora_apply and ora_apply > 0:
            self.ora_type += 'DG-'
        elif self.ora_dg_on and self.ora_dg_on > 0:
            self.ora_type += 'DG+'

        self.ora_sgapga = self.fetch_single_value(
            """ select max(case when name='sga_target' then display_value end) 
            ||'/'|| max(case when name='pga_aggregate_target' then display_value end) as SGAPGA
            from v$parameter where name in ('pga_aggregate_target','sga_target') """)

    def status(self):
        diag_dest = self.fetch_single_value(
            " SELECT max(value) as diag_dest FROM v$parameter WHERE name = 'diagnostic_dest' ")
        if diag_dest:
            self.ora_alert_log = self.fetch_single_value(
                " SELECT REPLACE(value,'cdump','trace') as alert_log from v$parameter where name ='core_dump_dest' ")
        else:
            self.ora_alert_log = self.fetch_single_value(
                " SELECT value as alert_log FROM v$parameter WHERE name = 'background_dump_dest' ")

        self.ora_sgapga = self.fetch_single_value(
            """ select max(case when name='sga_target' then display_value end) 
            ||'/'|| max(case when name='pga_aggregate_target' then display_value end) as SGAPGA
            from v$parameter where name in ('pga_aggregate_target','sga_target') """)

    def __str__(self):
        retval = ''
        for attribute, value in sorted(self.__dict__.items()):
            if attribute.startswith('_'):
                continue
            if value is None:
                value = ''
            retval += "{}='{}'\n".format(attribute, value)
        return retval


class homes():

    def __init__(self):
        self.facts_item = {}
        self.running_only = False
        self.oracle_restart = False
        self.oracle_crs = False
        self.oracle_standalone = False
        self.oracle_install_type = None
        self.crs_home = None
        self.homes = {}
        self.ora_inventory = None
        self.orabase = None
        self.crsctl = None
        
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


    def parse_oratab(self):
        #Reads SID and ORACLE_HOME from oratab
        with open('/etc/oratab','r') as oratab:
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
                            proc = subprocess.Popen([self.crsctl, 'stat', 'res', '-p', '-w', dfilter], stdout=subprocess.PIPE)
                            for line in iter(proc.stdout.readline,''):
                                if line.decode('utf-8').startswith('ORACLE_HOME='):
                                    (_, ORACLE_HOME,) = line.decode('utf-8').strip().split('=')
                                proc.poll()
                                if proc.returncode is not None:
                                    break
                        pass
                    
                    if ORACLE_HOME:
                        self.add_sid(ORACLE_SID=ORACLE_SID, ORACLE_HOME=ORACLE_HOME, running=True)

            #except FileNotFoundError: # Python3
            except EnvironmentError as e:
                #print("Missing file ignored: {} ({})".format(cmd_line_file, e))
                pass


    def list_crs_instances(self):
        hostname = socket.gethostname().split('.')[0]
        if self.crsctl:
            for dfiltertype in ['ora.database.type']: # ora.asm.type does not report ORACLE_HOME
            #for dfiltertype in ['ora.asm.type', 'ora.database.type']:
                dfilter = '(TYPE = {})'.format(dfiltertype)
                proc = subprocess.Popen([self.crsctl, 'stat', 'res', '-p', '-w', dfilter], stdout=subprocess.PIPE)
                (ORACLE_HOME, ORACLE_SID) = (None, None)
                for line in iter(proc.stdout.readline,''):
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
            for line in iter(proc.stdout.readline,''):
                if line.strip():
                    ORACLE_BASE = line.strip().decode()
                else:
                    break
        return ORACLE_BASE
    

    def add_home(self, ORACLE_HOME):
        if ORACLE_HOME not in self.homes:
            ORACLE_BASE = self.base_from_home(ORACLE_HOME)
            self.homes[ORACLE_HOME] = {'ORACLE_HOME': ORACLE_HOME, 'ORACLE_BASE': ORACLE_BASE}

    
    def add_sid(self, ORACLE_SID, ORACLE_HOME = None, running = False):
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
            self.facts_item[ORACLE_SID] = {'ORACLE_SID': ORACLE_SID
                                           , 'ORACLE_HOME': ORACLE_HOME
                                           , 'ORACLE_BASE': self.homes[ORACLE_HOME]['ORACLE_BASE']
                                           , 'running': running}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-l', '--homes',    required=False, action='store_true', help='List Oracle HOMEs')
    group.add_argument('-i', '--instance', required=False, action='store_true', help='Describe database instance')
    group.add_argument('-s', '--status', required=False, action='store_true', help='Status of database instance')
    
    parser.add_argument('-d', '--debug', required=False, action='store_true', help='Debug')

    parser.add_argument('-S', '--sid', required=False, action='store', help='ORACLE_SID')
    parser.add_argument('-H', '--home', required=False, action='store', help='ORACLE_HOME')

    args = parser.parse_args()

    if args.homes:
        h = homes()
        h.list_crs_instances()
        h.list_processes()
        h.parse_oratab()

        if args.debug:
            print(json.dumps(h.facts_item, indent=4))
        else:
            for k in sorted(h.facts_item.keys()):
                print("{ORACLE_SID}\t{ORACLE_HOME}\t{ORACLE_BASE}"
                      .format(ORACLE_SID=k
                              , ORACLE_HOME=h.facts_item[k]['ORACLE_HOME']
                              , ORACLE_BASE=h.facts_item[k]['ORACLE_BASE']))

    if args.instance:
        if args.sid:
            os.environ["ORACLE_SID"] = args.sid
        if args.home:
            os.environ["ORACLE_HOME"] = args.home
        d = database()
        d.instance()
        print(str(d))

    if args.status:
        if args.sid:
            os.environ["ORACLE_SID"] = args.sid
        if args.home:
            os.environ["ORACLE_HOME"] = args.home
        d = database()
        d.status()
        print(str(d))
