#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_sqldba
short_description: Execute sql (scripts) using sqlplus (BEQ) or catcon.pl
description:
    - Needed for post-installation tasks not covered by other modules
    - Uses sqlplus (BEQ connect, e.g. / as sysdba) or $OH//perl catcon.pl
options:
    sql:
        description:
            - Single SQL statement
            - Will be executed by sqlplus
            - Used for DDL and DML
        required: false
        default: None
    sqlscript:
        description:
            - Script name, optionally followed by parameters
            - Will be executed by sqlplus
        required: false
        default: None
    catcon_pl:
        description:
            - Script name, optionally followed by parameters
            - Will be executed by $OH//perl catcon.pl
        required: false
        default: None
    sqlselect:
        description:
            - Single SQL statement
            - Will be executed by sqlplus using dbms_xmlgen.getxml
            - Used for select only, returns dict in .state
            - To access the column "value" of the first row write: <<registered result>>.state.ROW[0].VALUE (use uppercase)
        required: false
        default: None
    creates_sql:
        description:
            - This is the check query to ensure idempotence.
            - Must be a single SQL select that results to no rows or a plain 0 if the catcon_pl/sqlscript/sql has to be executed. Any other result prevent the execution of catcon_pl/sqlscript/sql.
            - The catcon_pl/sqlscript/sql will be executed unconditionally if creates_sql is omitted.
            - Creates_sql must be omitted when sqlselect is used.
            - Creates_sql is executed with sqlplus / as sysdba in the root container. Write the sql query according to this fact.
            - If pdb_list is given (implicitely whith all_pdbs) creates_sql is executed in every PDB incl. CDB$ROOT. The pdb_list will be shortened according to the results of creates_sql in the PDBs.
        required: false
        default: None
    username:
        description:
            - Database username, defaults to "/ as sysdba"
        required: false
        default: None
    password:
        description:
            - Password of database user
        required: false
        default: None
    scope:
        description:
            - Shall the SQL be applied to CDB, PDBs, or both?
        values:
            - default: if catcon_pl is filled then all_pdbs else cdb
            - db: alias for cdb, allows for better readability for non-cdb
            - cdb: apply to root container or whole db
            - pdbs: apply to specified PDB's only (requires pdb_list)
            - all_pdbs: apply to all PDB's except PDB$SEED
        required: false
        default: cdb
    pdb_list:
        description:
            - Optional list of PDB names
            - Space separated, as catcon.pl wants
            - Gets used only if scope is "pdbs"
            - Will be automatically filled and used when scope = all_pdbs and action like sql%
        required: false
        default: None
    oracle_home:
        description:
            - content of $ORACLE_HOME
    oracle_db_name:
        description:
            - SID or DB_NAME, needed for BEQ connect
    nls_lang:
        description:
            - set NLS_LANG to the given value
    chdir:
        description:
            - Working directory for SQL/script execution

author: 
   - Dietmar Uhlig, Robotron (www.robotron.de)
   - Ivan Brezina
'''

EXAMPLES = '''
# Example call utlrp
- name: "Call @?/rdbms/admin/utlrp"
  oracle_sqldba:
    oh: "{{ oracle_db_new_home }}"
    sqlscript: "@?/rdbms/admin/utlrp"
  register: _oracle_utlrp

# Example 2, read sql result
- name: Read job_queue_processes
  oracle_sqldba:
    sqlselect: "select value from gv$parameter where name = 'job_queue_processes'"
    oracle_home: "{{ oracle_db_home }}"
    oracle_db_name: "{{ oracle_db_name }}"
  register: jqpresult

- name: Store job_queue_processes
  set_fact:
    job_queue_processes: "{{ jqpresult.state.ROW[0].VALUE }}"
    # Use all uppercase for "ROW" and for column names!

# Example mixed post installation tasks from inventory:
oracle_databases:
  - oracle_db_name: eek17ec
      home: 12.2.0.1-ee
      state: present
      init_parameters: "{{ init_parameters['12.2.0.1-EMS'] }}"
      profiles: "{{ db_profiles['12.2.0.1-EMS'] }}"
      postinstall: "{{ db_postinstall['12.2.0.1-EMS'] }}"

oracle_pdbs:
  - cdb: eek17ec
    pdb_name: eckpdb
  - cdb: eek17ec
    pdb_name: sckpdb

db_postinstall:
  12.2.0.1-EMS:
    - catcon_pl: "$ORACLE_HOME/ctx/admin/catctx.sql context SYSAUX TEMP NOLOCK"
      creates_sql: "select 1 from dba_registry where comp_id = 'CONTEXT'"
    - sqlscript: "?/rdbms/admin/initsqlj.sql"
      scope: pdbs
      creates_sql: "select count(*) from dba_tab_privs where table_name = 'SQLJUTL' and grantee = 'PUBLIC'"
    - sqlscript: "?/rdbms/admin/utlrp.sql"
    - sql: "alter pluggable database {{ pdb.pdb_name | default(omit) }} save state"
      scope: pdbs

# see role oradb-postinstall, loops over {{ oracle_databases }} = loop_var oradb

- name: Conditionally execute post installation tasks
  oracle_sqldba:
    sql: "{{ pitask.sql | default(omit) }}"
    sqlscript: "{{ pitask.sqlscript | default(omit) }}"
    catcon_pl: "{{ pitask.catcon_pl | default(omit) }}"
    creates_sql: "{{ pitask.creates_sql | default(omit) }}"
    username: "{{ pitask.username | default(omit) }}"
    password: "{%if pitask.username is defined%}{{ dbpasswords[oradb.oracle_db_name][pitask.username] }}{%endif%}"
    scope: "{{ pitask.scope | default(omit) }}"
    pdb_list: "{{ oracle_pdbs | default([]) | json_query('[?cdb==`' + oradb.oracle_db_name + '`].pdb_name') | join(' ') }}"
    oracle_home: "{{ db_homes_config[oradb.home].oracle_home }}"
    oracle_db_name: "{{ oradb.oracle_db_name }}"
  loop: "{{ oradb.postinstall }}"
  loop_control:
    loop_var: pitask

'''

import errno
import os
import re
import shlex
import shutil
import tempfile
from subprocess import Popen, PIPE
from threading import Timer
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native, to_text
import xml.etree.ElementTree as ET
from copy import copy

changed = False
err_msg = ""
result = ""


def dictify(r, root=True):
    """
    dictify is based on
    https://stackoverflow.com/questions/2148119/how-to-convert-an-xml-string-to-a-dictionary/10077069#10077069
    """
    if root:
        #return {r.tag : dictify(r, False)} # no, but...
        return dictify(r, False) # skip root node "ROWSET"
    d=copy(r.attrib)
    if r.text.strip():
        d["_text"]=r.text
    for x in r.findall("./*"):
        if x.tag not in d:
            d[x.tag]=[]
        if x.text.strip(): # assume scalar
            d[x.tag] = x.text
        else:
            d[x.tag].append(dictify(x,False))
    return d


def sqlplus(oracle_home):
    sql_bin = os.path.join(oracle_home, "bin", "sqlplus")
    return [sql_bin, "-l", "-s", "/nolog"]


def conn(username, password):
    if username is None:
        return "conn / as sysdba\n"
    else:
        return "conn " + "/".join([username, password]) + "\n"


def sql_input(sql, username, password, pdb):
    sql_scr  = "set heading off echo off feedback off termout on\n"
    sql_scr += "set long 1000000 pagesize 0 linesize 1000 trimspool on\n"
    sql_scr += conn(username, password)

    if pdb is not None:
        sql_scr += "alter session set container = " + pdb + ";\n"
    sql_scr += sql + "\n"
    sql_scr += "exit;\n"
    return sql_scr


def kill_process(timeout, sql_process):
    global err_msg
    sql_process.kill()
    err_msg = "Timeout occured after %d seconds. " % timeout


def run_sql_p(module, sql, username, password, scope, pdb_list):
    result = ""
    if scope == 'pdbs':
        for pdb in pdb_list.split():
            result += run_sql(sql, username, password, pdb)
    else:
        result = run_sql(module, sql, username, password, None)
    return result


def run_sql(module, sql, username=None, password=None, pdb=None):
    global changed, err_msg
    oracle_home = module.params["oracle_home"]
    timeout = module.params['timeout']

    t = None
    try:
        sql_cmd = sql_input(sql, username, password, pdb)
        sql_process = Popen(sqlplus(oracle_home), stdin=PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        if timeout > 0:
            t = Timer(timeout, function=kill_process, args=[timeout, sql_process])
            t.start()
        [sout, serr] = sql_process.communicate(input=sql_cmd)
    except Exception as e:
        err_msg += 'Could not call sqlplus. %s. called: %s.' % (to_native(e), " ".join(sqlplus()))
        return "[ERR]"
    finally:
        if timeout > 0 and t is not None:
            t.cancel()
    if sql_process.returncode != 0:
        err_msg += "called: %s\nreturncode: %d\nresult: %s. stderr = %s." % (sql_cmd, sql_process.returncode, sout, serr)
        return "[ERR]"
    sqlerr_pat = re.compile("^(ORA|TNS|SP2)-[0-9]+", re.MULTILINE)
    sqlplus_err = sqlerr_pat.search(sout)
    if sqlplus_err:
        err_msg += "[ERR] sqlplus: %s\nERR Code: %s.\n" % (sql_cmd, sqlplus_err.group())
        return "[ERR]\n%s\n" % sout.strip()

    changed = True
    return sout.strip()


def check_creates_sql(module, sql, scope, pdb_list):
    if not sql.endswith(";"):
        sql += ";"
    if scope == 'cdb':
        res = run_sql(module, sql, None, None, None)
        # error handling see call of check_creates_sql
        return [res] if not res or res == "0" else []
    else:
        checked_pdb_list = []
        for pdb in pdb_list:
            res = run_sql(module, sql, None, None, pdb)
            # error handling see call of check_creates_sql
            if not res or res == "0":
                checked_pdb_list.append(pdb)
        return checked_pdb_list


def is_container(module):
    return run_sql(module, "select cdb from gv$database;", None, None, None) == 'YES'


def get_all_pdbs(module):
    sql = """
    select listagg(pdb_name, ' ') within group (order by pdb_name) 
    from dba_pdbs where status = 'NORMAL' and pdb_name <> 'PDB$SEED';"""
    pdb_list = ['CDB$ROOT']
    pdb_list.extend(run_sql(module, sql, None, None, None).split(' '))
    return pdb_list


def run_catcon_pl(module, pdb_list, catcon_pl):
    # after pre-processing in main() the parameter scope is not necessary any more
    global changed, err_msg
    oracle_home = module.params["oracle_home"]
    timeout = module.params["timeout"]

    catcon_pl = re.sub("^(\$ORACLE_HOME|\?)", oracle_home, catcon_pl)
    logdir = tempfile.mkdtemp()
    catcon_cmd = [ os.path.join(oracle_home, "perl", "bin", "perl"),
                   os.path.join(oracle_home, "rdbms", "admin", "catcon.pl"),
                   "-l", logdir, "-b", "catcon" ]
    if pdb_list:
        catcon_cmd.extend(["-c", " ".join(pdb_list)])
    cc_script = shlex.split(catcon_pl)
    if len(cc_script) > 1:
        for i in range(1, len(cc_script)):
            cc_script[i] = "1" + cc_script[i]
        catcon_cmd += [ "-a", "1" ]
    catcon_cmd += [ "--" ] + cc_script
    try:
        sql_process = Popen(catcon_cmd, stdout = PIPE, stderr = PIPE, universal_newlines=True)
        if timeout > 0:
            t = Timer(timeout, function=kill_process, args=[timeout, sql_process])
            t.start()
        [sout, serr] = sql_process.communicate()
    except Exception as e:
        err_msg += 'Could not call perl. %s. called: %s.' % (to_native(e), " ".join(catcon_cmd))
        return
    finally:
        if timeout > 0:
            t.cancel()
        try:
            shutil.rmtree(logdir)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise
    if sql_process.returncode != 0:
        err_msg += "called: %s\nreturncode: %d\nresult: %s\nstderr = %s." % (" ".join(catcon_cmd), sql_process.returncode, sout, serr)
        return
    result += sout
    changed = True


def main():
    global changed, err_msg, result

    module = AnsibleModule(
        argument_spec = dict(
            sql            = dict(required = False),
            sqlscript      = dict(required = False),
            catcon_pl      = dict(required = False),
            sqlselect      = dict(required = False),
            creates_sql    = dict(required = False),
            username       = dict(required = False),
            password       = dict(required = False, no_log=True),
            scope          = dict(required = False, choices=["default", "db", "cdb", "pdbs", "all_pdbs"], default = 'default'),
            pdb_list       = dict(required = False, type='list', default=[]),
            oracle_home    = dict(required = False, aliases=['oh']),
            oracle_sid     = dict(required = False, aliases=['oracle_db_name']),
            nls_lang       = dict(required = False),
            chdir          = dict(required = False),
            # Maximum runtime for sqlplus and catcon.pl in seconds. 0 means no timeout.
            timeout        = dict(required = False, default=0, type='int')
        ),
        required_one_of=[('sql', 'sqlscript', 'catcon_pl', 'sqlselect')],
        mutually_exclusive=[['sql', 'sqlscript', 'catcon_pl', 'sqlselect'], ['sqlselect', 'creates_sql']],
        required_together=[('username', 'password')]
    )

    sql            = module.params["sql"]
    sqlscript      = module.params["sqlscript"]
    catcon_pl      = module.params["catcon_pl"]
    sqlselect      = module.params["sqlselect"]
    creates_sql    = module.params["creates_sql"]
    username       = module.params["username"]
    password       = module.params["password"]
    scope          = module.params["scope"]
    pdb_list       = module.params["pdb_list"]
    nls_lang       = module.params["nls_lang"]
    workdir        = module.params["chdir"]

    if "oracle_home" in module.params:
        oracle_home = module.params["oracle_home"]
    else:
        oracle_home = None
    if oracle_home is not None:
        os.environ['ORACLE_HOME'] = oracle_home.rstrip('/')
    elif 'ORACLE_HOME' in os.environ:
        oracle_home = os.environ['ORACLE_HOME']
        module.params["oracle_home"] = oracle_home
    else:
        module.fail_json(msg='ORACLE_HOME is not defined', changed=False)

    if "oracle_sid" in module.params:
        oracle_sid = module.params["oracle_sid"]
    else:
        oracle_sid = None
    if oracle_sid is not None:
        os.environ['ORACLE_SID'] = oracle_home.rstrip('/')
    elif 'ORACLE_SID' in os.environ:
        oracle_sid = os.environ['ORACLE_SID']
        module.params["oracle_sid"] = oracle_sid
    else:
        module.fail_json(msg='ORACLE_SID nor oracle_db_name is not defined', changed=False)

    os.environ["PATH"] += os.pathsep + os.path.join(oracle_home, "bin")
    if nls_lang is not None:
        os.environ["NLS_LANG"] = nls_lang

    if scope == 'db':
        scope = 'cdb'
    if scope == 'default':
        scope = "all_pdbs" if catcon_pl is not None else "cdb"
    if scope == 'pdbs' and (pdb_list is None or pdb_list.strip() == ""):
        module.exit_json(msg="scope = pdbs, but pdb_list is empty", changed=False)
    if scope == 'cdb' and catcon_pl is not None:
        scope = 'pdbs'
        pdb_list = 'CDB$ROOT'
    if scope == 'all_pdbs' and (catcon_pl is None or creates_sql is not None):
        if is_container(module):
            scope = 'pdbs'
            pdb_list = get_all_pdbs(module)
        else:
            scope = 'cdb'

    if workdir is not None:
        try:
            os.chdir(workdir)
        except Exception as e:
            module.fail_json(msg='Could not chdir to %s: %s.' % (workdir, to_native(e)), changed = False)

    if creates_sql is not None:
        pdb_list = check_creates_sql(module, creates_sql, scope, pdb_list)
        if err_msg:
            module.fail_json(msg="%s\n%s" % (result, err_msg), changed=False)
        else:
            if not pdb_list:
                module.exit_json(msg="Nothing to do", changed = False)

    if pdb_list:
        result = "Run on these PDBs: %s\n" % " ".join(pdb_list)
        
    if sqlselect is not None:
        if sqlselect.endswith(";"):
            sqlselect.rstrip(";")
        sqlselect = "select dbms_xmlgen.getxml('" + sqlselect.replace("'", "''") + "') from dual;"
        result = run_sql_p(module, sqlselect, username, password, scope, pdb_list)
    elif sql is not None:
        sql = os.linesep.join([s for s in sql.splitlines() if s.strip()])
        if not sql.endswith(";") and not sql.endswith("/"):
            sql += ";"
        result += run_sql_p(module, sql, username, password, scope, pdb_list)
    elif sqlscript is not None:
        if not sqlscript.startswith("@"):
            sqlscript = "@" + sqlscript
        result += run_sql_p(module, sqlscript, username, password, scope, pdb_list)
    elif catcon_pl is not None:
        run_catcon_pl(module, pdb_list, catcon_pl)

    if err_msg:
        module.fail_json(msg="%s: %s" % (result, err_msg), changed=changed)

    if sqlselect:
        res_dict = dictify(ET.fromstring(result)) if result else {"ROW": []}
        module.exit_json(msg=result, changed=False, state=res_dict)
    else:
        module.exit_json(msg=result, changed=changed)


if __name__ == '__main__':
    main()
