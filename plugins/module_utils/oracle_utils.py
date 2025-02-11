from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.module_utils.basic import os
from ansible.module_utils.basic import *

try:
    import oracledb
except ImportError:
    oracledb_exists = False
else:
    oracledb_exists = True

from ansible.module_utils.basic import *


def oracle_connect(module):
    """
    Connect to the database using parameter provided by Ansible module instance.
    Return: connection
    """

    try:
        import oracledb
    except ImportError:
        oracledb_exists = False
    else:
        oracledb_exists = True

    if not oracledb_exists:
        module.fail_json(msg="The oracledb module is required. 'pip install oracledb' should do the trick. If oracledb is installed, make sure ORACLE_HOME is set")
        
    if "oracle_home" in module.params:
        oracle_home = module.params["oracle_home"]
    else:
        oracle_home = None
    hostname = module.params["hostname"]
    port = module.params["port"]
    service_name = module.params["service_name"]
    user = module.params["user"]
    password = module.params["password"]
    mode = module.params["mode"]

    if oracle_home is not None:
        os.environ['ORACLE_HOME'] = oracle_home.rstrip('/')
    elif 'ORACLE_HOME' in os.environ:
        oracle_home = os.environ['ORACLE_HOME']

    wallet_connect = '/@%s' % service_name

    sysdba_connect = '/'
    try:
        if (not user and not password ): # If neither user or password is supplied, the use of an oracle wallet is assumed
            if mode == 'sysdba':
                connect = sysdba_connect
                conn = oracledb.connect(sysdba_connect, mode=oracledb.SYSDBA)
            else:
                connect = wallet_connect
                conn = oracledb.connect(wallet_connect)

        elif (user and password ):
            if mode == 'sysdba':
                dsn = oracledb.makedsn(host=hostname, port=port, service_name=service_name)
                connect = dsn
                conn = oracledb.connect(user, password, dsn, mode=oracledb.SYSDBA)
            else:
                dsn = oracledb.makedsn(host=hostname, port=port, service_name=service_name)
                connect = dsn
                conn = oracledb.connect(user, password, dsn)

        elif (not(user) or not(password)):
            module.fail_json(msg='Missing username or password for oracledb')
            
    except oracledb.DatabaseError as exc:
        error, = exc.args
        msg = 'Could not connect to database - %s, connect descriptor: %s' % (error.message, connect)
        module.fail_json(msg=msg, changed=False)

    return conn


class oracleConnection:
    """
    Connect to the database using parameter provided by Ansible module instance.
    Return: connection
    """

    def __init__(self, module):
        self.module = module
        self.chaged = False

        if not oracledb_exists:
            module.fail_json(msg="The oracledb module is required. 'pip install oracledb' should do the trick.")

        if "oracle_home" in module.params and module.params["oracle_home"]:
            self.oracle_home = module.params["oracle_home"]
            os.environ['ORACLE_HOME'] = self.oracle_home.rstrip('/')
        elif 'ORACLE_HOME' in os.environ:
            self.oracle_home = os.environ['ORACLE_HOME']
        else:
            self.oracle_home = None

        hostname = module.params["hostname"]
        port = module.params["port"]
        service_name = module.params["service_name"]
        user = module.params["user"]
        password = module.params["password"]
        mode = module.params["mode"]

        wallet_connect = '/@%s' % service_name
        sysdba_connect = '/'

        try:
            if not user and not password: # If neither user or password is supplied, the use of an oracle connect internal or wallet is assumed
                if mode == 'sysdba':
                    connect = sysdba_connect
                    conn = oracledb.connect(sysdba_connect, mode=oracledb.SYSDBA)
                else:
                    connect = wallet_connect
                    conn = oracledb.connect(wallet_connect)
            elif user and password: # Assume supplied user has SYSDBA role granted
                if mode == 'sysdba':
                    dsn = oracledb.makedsn(host=hostname, port=port, service_name=service_name)
                    connect = dsn
                    conn = oracledb.connect(user, password, dsn, mode=oracledb.SYSDBA)
                else:
                    dsn = oracledb.makedsn(host=hostname, port=port, service_name=service_name)
                    connect = dsn
                    conn = oracledb.connect(user, password, dsn)
            elif not user or not password:
                module.fail_json(msg='Missing username or password for oracledb')
        except oracledb.DatabaseError as exc:
            error, = exc.args
            msg = 'Could not connect to database - %s, connect descriptor: %s' % (error.message, connect)
            module.fail_json(msg=msg, changed=False)
        self.conn = conn
        self.conn.autocommit = True
        self.version = self.conn.version
        self.ddls = []
        self.changed = False


    def execute_select(self, sql, params=None, fetchone=False):
        """Execute a select query and return fetched data.

        sql -- SQL query
        params -- Dictionary of bind parameters (default {})
        fetchone -- If True, fetch one row, otherwise fetch all rows (default False)
        """
        if params is None:
            params = {}
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone() if fetchone else cursor.fetchall()
        except oracledb.DatabaseError as e:
            error = e.args[0]
            self.module.fail_json(msg=error.message, code=error.code, request=sql, params=params, ddls=self.ddls, changed=self.changed)


    def execute_select_to_dict(self, sql, params=None, fetchone=False):
        """Execute a select query and return a list of dictionaries : one dictionary for each row.

        sql -- SQL query
        params -- Dictionary of bind parameters (default {})
        """
        if params is None:
            params = {}
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(sql, params)
                column_names = [description[0].lower() for description in cursor.description]  # First element is the column name.
                if fetchone:
                    row = cursor.fetchone()
                    if row:
                        return dict(zip(column_names, row))
                    else:
                        return dict()
                else:
                    return [dict(zip(column_names, row)) for row in cursor]
        except oracledb.DatabaseError as e:
            error = e.args[0]
            self.module.fail_json(msg=error.message, code=error.code, request=sql, params=params, ddls=self.ddls, changed=self.changed)


    def execute_ddl(self, request, no_change=False, ignore_errors = []):
        """Execute a DDL request and keep trace it in ddls attribute.
        request -- SQL query, no bind parameter allowed on DDL request.
        In check mode, query is not executed.
        """
        try:
            if self.module._verbosity >= 3:
                self.module.warn("SQL: --{}".format(request))
            if not self.module.check_mode:
                with self.conn.cursor() as cursor:
                    cursor.execute(request)
                    self.ddls.append(request)
            else:
                self.ddls.append('--' + request)
            if not no_change: # In case of alter session, do not set changed to True
                self.changed = True
        except oracledb.DatabaseError as e:
            error = e.args[0]
            if error.code not in ignore_errors:
                self.module.fail_json(msg=error.message, code=error.code, request=request, ddls=self.ddls, changed=self.changed)
            else:
                pass

            
    def execute_statement(self, statement):
        """Execute a statement, can be a query or a procedure and return lines of dbms_output.put_line().

        statement -- SQL request or PL/SQL block

        In check mode, statement is not executed.
        If PL/SQL block contains put_line, the output will be returned.
        """
        output_lines = []
        try:
            if not self.module.check_mode:
                if 'dbms_output.put_line' in statement.lower():
                    with self.conn.cursor() as cursor:
                        cursor.callproc('dbms_output.enable', [None])
                        cursor.execute(statement)

                        chunk_size = 100  # Get lines by batch of 100
                        # create variables to hold the output
                        lines_var = cursor.arrayvar(str, chunk_size)  # out variable
                        num_lines_var = cursor.var(int)  # in/out variable
                        num_lines_var.setvalue(0, chunk_size)

                        # fetch the text that was added by PL/SQL
                        while True:
                            cursor.callproc('dbms_output.get_lines', (lines_var, num_lines_var))
                            num_lines = num_lines_var.getvalue()
                            output_lines.extend(lines_var.getvalue()[:num_lines])
                            if num_lines < chunk_size:  # if less lines than the chunk value was fetched, it's the end
                                break
                else:
                    with self.conn.cursor() as cursor:                    
                        cursor.execute(statement)
                self.ddls.append(statement)
            else:
                self.ddls.append('--' + statement)
            return output_lines
        except oracledb.DatabaseError as e:
            error = e.args[0]
            self.module.fail_json(msg=error.message, code=error.code, request=statement)

            
class dictcur(object):
    # need to monkeypatch the built-in execute function to always return a dict
    def __init__(self, cursor):
        self._original_cursor = cursor

    def execute(self, *args, **kwargs):
        # rowfactory needs to be set AFTER EACH execution!
        self._original_cursor.execute(*args, **kwargs)
        self._original_cursor.rowfactory = lambda *a: dict(
            zip([d[0] for d in self._original_cursor.description], a)
        )
        # oracledb's cursor's execute method returns a cursor object
        # -> return the correct cursor in the monkeypatched version as well!
        return self._original_cursor

    def __getattr__(self, attr):
        # anything other than the execute method: just go straight to the cursor
        return getattr(self._original_cursor, attr)
