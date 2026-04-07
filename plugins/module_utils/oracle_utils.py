from __future__ import absolute_import, division, print_function

__metaclass__ = type

import re

from ansible.module_utils.basic import os
from ansible.module_utils.basic import *

try:
    import oracledb
except ImportError:
    oracledb_exists = False
else:
    oracledb_exists = True


# Mapping from module 'mode' parameter to oracledb auth-mode constants.
# 'normal' is omitted — it means "no special mode flag".
# Entries whose constant is None (unsupported by the installed oracledb) are
# excluded so that _AUTH_MODES.get(mode) returns None only for 'normal'.
_AUTH_MODES = {}
if oracledb_exists:
    _AUTH_MODES = {
        k: v for k, v in {
            'sysdba': oracledb.SYSDBA,
            'sysdg': getattr(oracledb, 'SYSDG', getattr(oracledb, 'AUTH_MODE_SYSDG', None)),
            'sysoper': getattr(oracledb, 'SYSOPER', getattr(oracledb, 'AUTH_MODE_SYSOPER', None)),
            'sysasm': getattr(oracledb, 'SYSASM', getattr(oracledb, 'AUTH_MODE_SYSASM', None)),
        }.items() if v is not None
    }


def _is_dpi_1047(error_obj):
    msg = str(getattr(error_obj, "message", error_obj))
    return "DPI-1047" in msg


def _ensure_oracle_client(module, oracle_home=None, required=False):
    """
    Initialize python-oracledb thick mode only when needed.

    Returns True when client is initialized (or already initialized), False if skipped.
    Fails only when required=True and initialization cannot be completed.
    """
    if not oracledb_exists:
        if required:
            module.fail_json(msg="The oracledb module is required. Install it with 'pip install oracledb'.", changed=False)
        return False

    init_errors = []
    candidates = []
    if oracle_home:
        candidates.append({"lib_dir": os.path.join(oracle_home.rstrip("/"), "lib")})  # Full DB install
        candidates.append({"lib_dir": oracle_home.rstrip("/")})  # Instant Client
    candidates.append({})  # System default (LD_LIBRARY_PATH, ORACLE_HOME env, etc.)

    for kwargs in candidates:
        try:
            oracledb.init_oracle_client(**kwargs)
            return True
        except oracledb.ProgrammingError:
            # Oracle client has already been initialized in this Python process.
            return True
        except oracledb.DatabaseError as exc:
            error = exc.args[0] if exc.args else exc
            init_errors.append(error)
            # Continue to next candidate regardless of error type.

    # All candidates exhausted.
    if not required:
        return False
    has_dpi_1047 = any(_is_dpi_1047(e) for e in init_errors)
    if has_dpi_1047:
        module.fail_json(
            msg=(
                "Oracle Client libraries are required for this operation but cannot be loaded "
                "(DPI-1047). Install Oracle Instant Client or set LD_LIBRARY_PATH to include "
                "$ORACLE_HOME/lib."
            ),
            changed=False,
        )
    detail = str(init_errors[-1]) if init_errors else "unknown error"
    module.fail_json(msg="Unable to initialize Oracle Client: %s" % detail, changed=False)
    return False

# ---------------------------------------------------------------------------
# Shared SQL clause builders (used by oracle_wallet, oracle_tde, etc.)
# ---------------------------------------------------------------------------

def sql_single_quoted_literal(value):
    if value is None:
        return ''
    s = str(value)
    if s.startswith("'") and s.endswith("'"):
        s = s[1:-1]
    return s.replace("'", "''")


def build_force_clause(force_keystore):
    """Build FORCE KEYSTORE clause for ADMINISTER KEY MANAGEMENT."""
    if force_keystore:
        return 'FORCE KEYSTORE '
    return ''


def build_container_clause(container):
    """Build CONTAINER clause for ADMINISTER KEY MANAGEMENT."""
    if container == 'all':
        return ' CONTAINER = ALL'
    return ''


def build_backup_clause(backup=True, backup_tag=None):
    """Build WITH BACKUP clause for ADMINISTER KEY MANAGEMENT."""
    if not backup:
        return ''
    clause = ' WITH BACKUP'
    if backup_tag:
        clause += " USING '%s'" % sql_single_quoted_literal(backup_tag)
    return clause


def sanitize_string_params(module_params):
    """Strip leading/trailing whitespace from every string value in module.params.

    Mutates the dict in place so all downstream reads of module.params are
    automatically cleaned without changing any call site. Non-string values
    (None, int, bool, list, dict) are left untouched.
    """
    for key, value in module_params.items():
        if isinstance(value, str):
            module_params[key] = value.strip()


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

    auth_mode = _AUTH_MODES.get(mode)
    if mode != 'normal' and auth_mode is None:
        module.fail_json(msg="Auth mode '%s' is not supported by the installed oracledb driver" % mode, changed=False)

    try:
        if not user and not password:  # OS authentication or wallet
            _ensure_oracle_client(module, oracle_home=oracle_home, required=True)
            if auth_mode and service_name:
                # TNS via wallet: /@service_name as sysdba
                connect = wallet_connect
                conn = oracledb.connect(wallet_connect, mode=auth_mode)
            elif auth_mode:
                # BEQ/OS auth: / as sysdba (local instance, no listener)
                connect = '/'
                conn = oracledb.connect(mode=auth_mode)
            else:
                connect = wallet_connect
                conn = oracledb.connect(wallet_connect)

        elif user and password:
            dsn = oracledb.makedsn(host=hostname, port=port, service_name=service_name)
            connect = dsn
            if auth_mode:
                conn = oracledb.connect(user=user, password=password, dsn=dsn, mode=auth_mode)
            else:
                conn = oracledb.connect(user=user, password=password, dsn=dsn)

        elif not user or not password:
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

        try:
            dsn = module.params["dsn"]
        except KeyError as exc:
            dsn = None

        wallet_connect = '/@%s' % service_name
        # Thick mode is only required for OS-authenticated connections (no user/password).
        # SYSDBA/SYSDG/SYSOPER/SYSASM over TCP with explicit credentials works in
        # python-oracledb thin mode (2.x+).
        requires_thick = not user and not password
        _ensure_oracle_client(module, oracle_home=self.oracle_home, required=requires_thick)

        auth_mode = _AUTH_MODES.get(mode)
        if mode != 'normal' and auth_mode is None:
            module.fail_json(msg="Auth mode '%s' is not supported by the installed oracledb driver" % mode, changed=False)

        connect = '<unresolved>'
        try:
            if not user and not password:  # OS authentication or wallet
                if auth_mode and service_name:
                    # TNS via wallet: /@service_name as sysdba
                    connect = wallet_connect
                    conn = oracledb.connect(wallet_connect, mode=auth_mode)
                elif auth_mode:
                    # BEQ/OS auth: / as sysdba (local instance, no listener)
                    connect = '/'
                    conn = oracledb.connect(mode=auth_mode)
                else:
                    connect = wallet_connect
                    conn = oracledb.connect(wallet_connect)
            elif user and password:
                if not dsn and hostname:
                    dsn = oracledb.makedsn(host=hostname, port=port, service_name=service_name)
                connect = dsn
                if auth_mode:
                    conn = oracledb.connect(user=user, password=password, dsn=dsn, mode=auth_mode)
                else:
                    conn = oracledb.connect(user=user, password=password, dsn=dsn)
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
        session_container = module.params.get("session_container")
        if session_container:
            self.set_container(session_container)


    def execute_select(self, sql, params=None, fetchone=False, fail_on_error=True):
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
            if fail_on_error:
                self.module.fail_json(msg=error.message, code=error.code, ddls=self.ddls, changed=self.changed)
            else:
                self.module.warn(error.message)

    def execute_select_to_dict(self, sql, params=None, fetchone=False, fail_on_error=True):
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
            if fail_on_error:
                self.module.fail_json(msg=error.message, code=error.code, ddls=self.ddls, changed=self.changed)
            else:
                self.module.warn(error.message)


    def execute_ddl(self, request, params=None, no_change=False, ignore_errors=None, ddls_entry=None):
        """Execute a DDL request and keep trace it in ddls attribute.
        request -- SQL or anonymous PL/SQL block; optional bind parameters via params.
        In check mode, query is not executed.
        ddls_entry -- If set, this string is recorded in ``ddls`` and shown for ``-vvv``
            instead of ``request`` after success. Use to avoid returning secrets in the
            module result while still executing ``request`` on the database.
        """
        if ignore_errors is None:
            ignore_errors = []
        trace = ddls_entry if ddls_entry is not None else request
        try:
            if self.module._verbosity >= 3:
                self.module.warn("SQL: --{}".format(trace))
            if not self.module.check_mode:
                with self.conn.cursor() as cursor:
                    cursor.execute(request, params)
                    self.ddls.append(trace)
            else:
                self.ddls.append('--' + trace)
            if not no_change: # In case of alter session, do not set changed to True
                self.changed = True
        except oracledb.DatabaseError as e:
            error = e.args[0]
            if error.code not in ignore_errors:
                self.module.fail_json(msg=error.message, code=error.code, ddls=self.ddls, changed=self.changed)
            else:
                pass

            
    def execute_statement(self, statement, params=None):
        """Execute a statement, can be a query or a procedure and return lines of dbms_output.put_line().

        statement -- SQL request or PL/SQL block

        In check mode, statement is not executed.
        If PL/SQL block contains put_line, the output will be returned.
        """
        if params is None:
            params = {}
        output_lines = []
        try:
            if not self.module.check_mode:
                if 'dbms_output.put_line' in statement.lower():
                    with self.conn.cursor() as cursor:
                        cursor.callproc('dbms_output.enable', [None])
                        cursor.execute(statement, params)

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
                        cursor.execute(statement, params)
                        _READONLY_PREFIXES = ('SELECT', 'WITH', '(')
                        trimmed = statement.strip().upper()
                        is_mutating = not trimmed.startswith(_READONLY_PREFIXES) or cursor.rowcount > 0
                    self.ddls.append(statement)
                    if is_mutating:
                        self.changed = True
            else:
                self.ddls.append('--' + statement)
            return output_lines
        except oracledb.DatabaseError as e:
            error = e.args[0]
            self.module.fail_json(msg=error.message, code=error.code)

    def set_container(self, pdb_name):
        if not pdb_name:
            return
        if not re.match(r'^[A-Za-z][A-Za-z0-9_$#]*$', pdb_name):
            self.module.fail_json(msg='Invalid pdb_name for alter session', changed=self.changed, ddls=self.ddls)
        self.execute_ddl('ALTER SESSION SET CONTAINER = %s' % pdb_name, no_change=True)

    def resolve_object_name(self, object_name):
        statement = """
        DECLARE
            v_result1 VARCHAR2(200);
            v_result2 VARCHAR2(200);
        BEGIN
            -- 1. Check YOUR objects first (highest priority)
            BEGIN
                SELECT user, object_name INTO v_result1, v_result2
                FROM user_objects
                WHERE object_name = :object_name and object_type <> 'SYNONYM' AND ROWNUM = 1;
                :owner := v_result1;
                :name  := v_result2;
                --dbms_output.put_line('1:'|| v_result1);
                RETURN;
            EXCEPTION WHEN NO_DATA_FOUND THEN
                --dbms_output.put_line('1: not found: ' || :object_name); 
                NULL;
            END;
            -- 2. Check YOUR private synonyms
            BEGIN
                SELECT table_owner, table_name INTO v_result1, v_result2
                FROM user_synonyms 
                WHERE synonym_name = :object_name AND ROWNUM = 1;
                :owner := v_result1;
                :name  := v_result2;
                dbms_output.put_line('2:'|| v_result1);
                RETURN;
            EXCEPTION WHEN NO_DATA_FOUND THEN
                --dbms_output.put_line('2: not found' || :object_name);
                NULL;
            END;
            -- 3. Check PUBLIC synonyms (final fallback)
            BEGIN
                SELECT table_owner, table_name INTO v_result1, v_result2
                FROM all_synonyms 
                WHERE owner = 'PUBLIC' AND synonym_name = :object_name AND ROWNUM = 1;
                :owner := v_result1;
                :name  := v_result2;
                --dbms_output.put_line('3:'|| v_result1);
                RETURN;
            EXCEPTION WHEN NO_DATA_FOUND THEN
                --dbms_output.put_line('3: not found: ' || :object_name || ' by user: ' || user);
                :owner := NULL;
                :name  := NULL;
            END;
        END;
        """

        with self.conn.cursor() as cursor:
            schema = cursor.var(str)
            name = cursor.var(str)
            try:
                cursor.execute(statement, {'object_name': object_name.upper(), 'owner': schema, 'name': name})
                if schema.getvalue() and name.getvalue():
                    return schema.getvalue() + "." + name.getvalue()
            except oracledb.DatabaseError as e:
                pass
        return ''


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
