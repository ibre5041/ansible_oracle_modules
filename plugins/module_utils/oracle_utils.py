from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.module_utils.basic import os
from ansible.module_utils.basic import *

try:
    import cx_Oracle
except ImportError:
    cx_oracle_exists = False
else:
    cx_oracle_exists = True

from ansible.module_utils.basic import *


def oracle_connect(module):
    """
    Connect to the database using parameter provided by Ansible module instance.
    Return: connection
    """

    try:
        import cx_Oracle
    except ImportError:
        cx_oracle_exists = False
    else:
        cx_oracle_exists = True

    if not cx_oracle_exists:
        module.fail_json(msg="The cx_Oracle module is required. 'pip install cx_Oracle' should do the trick. If cx_Oracle is installed, make sure ORACLE_HOME & LD_LIBRARY_PATH is set")
        
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
                conn = cx_Oracle.connect(sysdba_connect, mode=cx_Oracle.SYSDBA)
            else:
                connect = wallet_connect
                conn = cx_Oracle.connect(wallet_connect)

        elif (user and password ):
            if mode == 'sysdba':
                dsn = cx_Oracle.makedsn(host=hostname, port=port, service_name=service_name)
                connect = dsn
                conn = cx_Oracle.connect(user, password, dsn, mode=cx_Oracle.SYSDBA)
            else:
                dsn = cx_Oracle.makedsn(host=hostname, port=port, service_name=service_name)
                connect = dsn
                conn = cx_Oracle.connect(user, password, dsn)

        elif (not(user) or not(password)):
            module.fail_json(msg='Missing username or password for cx_Oracle')

    except cx_Oracle.DatabaseError as exc:
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

        if not cx_oracle_exists:
            module.fail_json(msg="The cx_Oracle module is required. 'pip install cx_Oracle' should do the trick.")

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
                    conn = cx_Oracle.connect(sysdba_connect, mode=cx_Oracle.SYSDBA)
                else:
                    connect = wallet_connect
                    conn = cx_Oracle.connect(wallet_connect)
            elif user and password: # Assume supplied user has SYSDBA role granted
                if mode == 'sysdba':
                    dsn = cx_Oracle.makedsn(host=hostname, port=port, service_name=service_name)
                    connect = dsn
                    conn = cx_Oracle.connect(user, password, dsn, mode=cx_Oracle.SYSDBA)
                else:
                    dsn = cx_Oracle.makedsn(host=hostname, port=port, service_name=service_name)
                    connect = dsn
                    conn = cx_Oracle.connect(user, password, dsn)
            elif not user or not password:
                module.fail_json(msg='Missing username or password for cx_Oracle')
        except cx_Oracle.DatabaseError as exc:
            error, = exc.args
            msg = 'Could not connect to database - %s, connect descriptor: %s' % (error.message, connect)
            module.fail_json(msg=msg, changed=False)
        self.conn = conn
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
        except cx_Oracle.DatabaseError as e:
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
        except cx_Oracle.DatabaseError as e:
            error = e.args[0]
            self.module.fail_json(msg=error.message, code=error.code, request=sql, params=params, ddls=self.ddls, changed=self.changed)


    def execute_ddl(self, request, no_change=False):
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
        except cx_Oracle.DatabaseError as e:
            error = e.args[0]
            self.module.fail_json(msg=error.message, code=error.code, request=request, ddls=self.ddls, changed=self.changed)


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
        # cx_Oracle's cursor's execute method returns a cursor object
        # -> return the correct cursor in the monkeypatched version as well!
        return self._original_cursor

    def __getattr__(self, attr):
        # anything other than the execute method: just go straight to the cursor
        return getattr(self._original_cursor, attr)
