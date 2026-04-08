#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_wallet
short_description: Manage Oracle TDE keystores (wallets)
description:
  - Manage Oracle TDE keystores (wallets) using ADMINISTER KEY MANAGEMENT SQL
  - Create, open, close, backup keystores
  - Create auto-login keystores (local or network)
  - Change keystore password
  - Manage secrets (credentials) stored in the keystore
  - Supports multitenant CONTAINER clause
  - Compatible with Oracle 19c, 23ai, and 26ai
  - In Oracle 26ai, WALLET_ROOT is mandatory (ENCRYPTION_WALLET_LOCATION is desupported)
  - See connection parameters for oracle_ping
version_added: "3.4.0"
options:
  state:
    description: The intended state of the keystore
    default: present
    choices: ['present', 'absent', 'open', 'closed', 'status']
  keystore_location:
    description:
      - Path where the keystore files are stored
      - If not set, the module queries WALLET_ROOT or V$ENCRYPTION_WALLET for the location
    required: false
  keystore_password:
    description: Password for the keystore
    required: false
  new_password:
    description: New password when changing keystore password (state=present with change_password=true)
    required: false
  auto_login:
    description: Type of auto-login keystore to create
    default: none
    choices: ['none', 'auto_login', 'local_auto_login']
  change_password:
    description: Whether to change the keystore password (requires new_password)
    default: false
    type: bool
  backup:
    description: Whether to create a backup before destructive operations (WITH BACKUP)
    default: true
    type: bool
  backup_location:
    description: Directory path for the backup file
    required: false
  backup_tag:
    description: Tag identifier for the backup file
    required: false
  secret:
    description: Secret value to store in the keystore
    required: false
  secret_client:
    description: Client identifier for the secret (e.g. TDE_WALLET, HSM_WALLET, or custom name)
    required: false
  secret_tag:
    description: Tag for the secret entry
    required: false
  secret_state:
    description: State of the secret entry
    choices: ['present', 'absent']
    required: false
  force_keystore:
    description: Use FORCE KEYSTORE clause (temporarily opens an auto-login keystore for the operation)
    default: false
    type: bool
  container:
    description: Container clause for multitenant environments
    default: current
    choices: ['current', 'all']
notes:
  - Requires ADMINISTER KEY MANAGEMENT or SYSKM privilege
  - oracledb Python module is required
  - Keystore passwords are never logged (no_log=True)
requirements: [ "oracledb" ]
author:
  - Cyrille Modiano
'''

EXAMPLES = '''
- name: Create a software keystore
  oracle_wallet:
    mode: sysdba
    state: present
    keystore_location: /opt/oracle/admin/wallets/tde
    keystore_password: "MyKeystorePass123"

- name: Open the keystore
  oracle_wallet:
    mode: sysdba
    state: open
    keystore_password: "MyKeystorePass123"

- name: Open the keystore for all PDBs
  oracle_wallet:
    mode: sysdba
    state: open
    keystore_password: "MyKeystorePass123"
    container: all

- name: Close the keystore
  oracle_wallet:
    mode: sysdba
    state: closed
    keystore_password: "MyKeystorePass123"

- name: Create auto-login keystore
  oracle_wallet:
    mode: sysdba
    state: present
    auto_login: auto_login
    keystore_password: "MyKeystorePass123"

- name: Create local auto-login keystore (host-bound)
  oracle_wallet:
    mode: sysdba
    state: present
    auto_login: local_auto_login
    keystore_password: "MyKeystorePass123"

- name: Backup keystore
  oracle_wallet:
    mode: sysdba
    state: present
    backup_tag: "before_upgrade"
    keystore_password: "MyKeystorePass123"
    backup_location: /opt/oracle/backup/wallets

- name: Change keystore password
  oracle_wallet:
    mode: sysdba
    state: present
    change_password: true
    keystore_password: "OldPass123"
    new_password: "NewPass456"

- name: Add a secret to the keystore
  oracle_wallet:
    mode: sysdba
    secret: "my_secret_value"
    secret_client: "MY_APP"
    secret_state: present
    keystore_password: "MyKeystorePass123"

- name: Remove a secret from the keystore
  oracle_wallet:
    mode: sysdba
    secret_client: "MY_APP"
    secret_state: absent
    keystore_password: "MyKeystorePass123"

- name: Get keystore status
  oracle_wallet:
    mode: sysdba
    state: status
  register: wallet_info
'''


import re as _re


def escape_sql_literal(value, quote_char):
    """Escape *value* for embedding in a SQL fragment bounded by *quote_char*.

    Oracle string literals double embedded single quotes; delimited strings
    double embedded double quotes. Newlines are rejected so DDL stays a single
    statement line.
    """
    if not isinstance(value, str):
        raise TypeError('escape_sql_literal expects a string value')
    if '\n' in value or '\r' in value:
        raise ValueError('SQL parameter values must not contain newline or carriage return characters')
    if quote_char == "'":
        return value.replace("'", "''")
    if quote_char == '"':
        return value.replace('"', '""')
    raise ValueError('quote_char must be single or double quote')


def escape_sql_literal_or_fail(value, quote_char, module):
    try:
        return escape_sql_literal(value, quote_char)
    except (TypeError, ValueError) as e:
        module.fail_json(msg=str(e), changed=False)


def _assert_sql_embeddable_str(module, value, quote_char):
    """Reject values that cannot legally be embedded in a SQL literal."""
    if value is None or value == '':
        return
    try:
        escape_sql_literal(value, quote_char)
    except (TypeError, ValueError) as e:
        module.fail_json(msg=str(e), changed=False)


def validate_wallet_inputs_before_connect(module):
    """Validate task arguments before opening any database connection."""
    state = module.params['state']
    secret_state = module.params['secret_state']
    change_password_flag = module.params['change_password']
    backup_tag = module.params['backup_tag']
    backup_location = module.params['backup_location']

    if secret_state:
        if not module.params.get('secret_client'):
            module.fail_json(msg='secret_client is required for secret management', changed=False)
        if not module.params.get('keystore_password'):
            module.fail_json(msg='keystore_password is required for secret management', changed=False)
        if secret_state == 'present' and not module.params.get('secret'):
            module.fail_json(msg='secret is required when secret_state=present', changed=False)
        _assert_sql_embeddable_str(module, module.params.get('secret_client'), "'")
        _assert_sql_embeddable_str(module, module.params.get('keystore_password'), '"')
        if module.params.get('secret'):
            _assert_sql_embeddable_str(module, module.params['secret'], "'")
        _assert_sql_embeddable_str(module, module.params.get('secret_tag'), "'")
        _assert_sql_embeddable_str(module, backup_tag, "'")
        return

    if state == 'absent':
        module.fail_json(
            msg='Oracle does not support dropping a keystore via SQL. '
                'Remove the keystore files manually from the filesystem.',
            changed=False,
        )

    if state == 'present':
        loc = module.params.get('keystore_location')
        if loc:
            _assert_sql_embeddable_str(module, loc, "'")
        _assert_sql_embeddable_str(module, backup_tag, "'")
        _assert_sql_embeddable_str(module, backup_location, "'")
        if change_password_flag:
            _assert_sql_embeddable_str(module, module.params.get('keystore_password'), '"')
            _assert_sql_embeddable_str(module, module.params.get('new_password'), '"')
        if (backup_tag or backup_location) and not change_password_flag:
            if not module.params.get('keystore_password'):
                module.fail_json(
                    msg='keystore_password is required when backup_tag or backup_location is set',
                    changed=False,
                )
        return

    if state == 'open':
        ks = module.params.get('keystore_password')
        if ks:
            _assert_sql_embeddable_str(module, ks, '"')
        return

    if state == 'closed':
        ks = module.params.get('keystore_password')
        if ks:
            _assert_sql_embeddable_str(module, ks, '"')


def _redact_ddls(ddls):
    """Redact passwords and secrets from DDL statements before returning to user.

    Backup identifiers in ``... USING 'tag'`` (BACKUP KEYSTORE / WITH BACKUP) are
    left visible; they are not credentials. ``USING TAG`` for secrets uses a
    different token sequence and is unaffected.
    """
    # Oracle doubles embedded quotes inside literals; match full quoted spans.
    _sq_lit = r"'(?:[^']|'')*'"
    _dq_lit = r'"(?:[^"]|"")*"'
    redacted = []
    for ddl in ddls:
        s = _re.sub(r'(IDENTIFIED\s+BY\s+)' + _dq_lit, r'\1"***"', ddl, flags=_re.IGNORECASE)
        s = _re.sub(r'(SECRET\s+)' + _sq_lit, r"\1'***'", s, flags=_re.IGNORECASE)
        s = _re.sub(
            r'(ALTER\s+KEYSTORE\s+PASSWORD\s+.*?SET\s+)' + _dq_lit,
            r"\1'***'",
            s,
            flags=_re.IGNORECASE,
        )
        s = _re.sub(
            r'(ALTER\s+KEYSTORE\s+PASSWORD\s+.*?SET\s+)' + _sq_lit,
            r"\1'***'",
            s,
            flags=_re.IGNORECASE,
        )
        redacted.append(s)
    return redacted


def _vwallet_field(row, col):
    """Read a V$ view column from a row dict (oracledb lower/upper keys)."""
    if not row:
        return ''
    lc, uc = col.lower(), col.upper()
    if lc in row:
        return row[lc]
    if uc in row:
        return row[uc]
    return ''


def _aggregate_wallet_rows(rows):
    """Merge multiple V$ENCRYPTION_WALLET rows when ``container`` is ``all``."""
    if not rows:
        return {}
    if len(rows) == 1:
        return rows[0]

    statuses = []
    for r in rows:
        st = (_vwallet_field(r, 'STATUS') or '').upper()
        statuses.append(st)

    def _is_open(s):
        return s in ('OPEN', 'OPEN_NO_MASTER_KEY')

    def _is_closed(s):
        return s in ('CLOSED', 'NOT_AVAILABLE') or not s

    all_open = bool(statuses) and all(_is_open(s) for s in statuses)
    all_closed = bool(statuses) and all(_is_closed(s) for s in statuses)
    all_not_available = bool(statuses) and all(
        s in ('NOT_AVAILABLE', '') or not s for s in statuses
    )
    if all_open:
        agg_status = 'OPEN'
    elif all_not_available:
        agg_status = 'NOT_AVAILABLE'
    elif all_closed:
        agg_status = 'CLOSED'
    else:
        agg_status = 'MIXED'

    first = rows[0]
    open_rows = [rows[i] for i, s in enumerate(statuses) if _is_open(s)]
    auto_types = ('AUTOLOGIN', 'LOCAL_AUTOLOGIN')

    def _wtype(r):
        return (_vwallet_field(r, 'WALLET_TYPE') or '').upper()

    if open_rows and not all(_wtype(r) in auto_types for r in open_rows):
        rep_wallet_type = 'PASSWORD'
    elif open_rows:
        rep_wallet_type = _vwallet_field(open_rows[0], 'WALLET_TYPE')
    else:
        rep_wallet_type = _vwallet_field(first, 'WALLET_TYPE')

    modes = {_vwallet_field(r, 'KEYSTORE_MODE') for r in rows if _vwallet_field(r, 'KEYSTORE_MODE')}
    keystore_mode = 'MIXED' if len(modes) > 1 else _vwallet_field(first, 'KEYSTORE_MODE')

    return {
        'wrl_type': _vwallet_field(first, 'WRL_TYPE'),
        'wrl_parameter': _vwallet_field(first, 'WRL_PARAMETER'),
        'status': agg_status,
        'wallet_type': rep_wallet_type,
        'wallet_order': _vwallet_field(first, 'WALLET_ORDER'),
        'keystore_mode': keystore_mode,
    }


def get_wallet_status(conn, container=None):
    """Query V$ENCRYPTION_WALLET for keystore status.

    With ``container='all'``, aggregates every row so open/close idempotency
    reflects all PDBs/containers, not an arbitrary single row.
    """
    base_sql = """SELECT WRL_TYPE, WRL_PARAMETER, STATUS, WALLET_TYPE, WALLET_ORDER, KEYSTORE_MODE
             FROM V$ENCRYPTION_WALLET"""
    if container == 'all':
        rows = conn.execute_select_to_dict(base_sql, fetchone=False)
        if not rows:
            return {}
        return _aggregate_wallet_rows(rows)
    sql = base_sql + "\n             WHERE ROWNUM = 1"
    return conn.execute_select_to_dict(sql, fetchone=True)


def get_wallet_root(conn):
    """Get WALLET_ROOT parameter value."""
    sql = "SELECT VALUE FROM V$PARAMETER WHERE NAME = 'wallet_root'"
    r = conn.execute_select_to_dict(sql, fetchone=True)
    return r.get('value') if r else None


def get_secrets(conn):
    """Query secrets stored in the keystore."""
    sql = "SELECT CLIENT, SECRET_TAG FROM V$CLIENT_SECRETS"
    return conn.execute_select_to_dict(sql, fail_on_error=False) or []


def secret_exists(conn, client_name, secret_tag=None):
    """Check if a secret exists for *client_name*, optionally scoped to *secret_tag*."""
    secrets = get_secrets(conn)
    if not secrets:
        return False
    c_upper = client_name.upper()
    want_tag = (secret_tag or '').strip()
    want_tag_u = want_tag.upper() if want_tag else None
    for s in secrets:
        cli = (_vwallet_field(s, 'CLIENT') or '').upper()
        if cli != c_upper:
            continue
        if want_tag_u is None:
            return True
        tag = (_vwallet_field(s, 'SECRET_TAG') or '').upper()
        if tag == want_tag_u:
            return True
    return False


def ensure_keystore_present(conn, module):
    """Create a software keystore if it doesn't exist."""
    status = get_wallet_status(conn, module.params["container"])
    keystore_location = module.params["keystore_location"]
    keystore_password = module.params["keystore_password"]

    # If keystore already exists (status is not NOT_AVAILABLE and not empty)
    current_status = status.get('status', '') if status else ''
    if current_status and current_status != 'NOT_AVAILABLE':
        return status

    if not keystore_password:
        module.fail_json(msg='keystore_password is required to create a keystore', changed=False)

    # Determine location
    if not keystore_location:
        wallet_root = get_wallet_root(conn)
        if wallet_root:
            keystore_location = wallet_root + '/tde'
        else:
            module.fail_json(
                msg='keystore_location is required when WALLET_ROOT is not set',
                changed=False
            )

    loc_esc = escape_sql_literal_or_fail(keystore_location, "'", module)
    pwd_esc = escape_sql_literal_or_fail(keystore_password, '"', module)
    sql = "ADMINISTER KEY MANAGEMENT CREATE KEYSTORE '%s' IDENTIFIED BY \"%s\"" % (
        loc_esc, pwd_esc
    )
    conn.execute_ddl(sql)
    return get_wallet_status(conn, module.params["container"])


def ensure_keystore_open(conn, module):
    """Open the keystore if it is closed."""
    status = get_wallet_status(conn, module.params["container"])
    current_status = status.get('status', '') if status else ''
    keystore_password = module.params["keystore_password"]
    container = module.params["container"]
    force_keystore = module.params["force_keystore"]

    if current_status in ('OPEN', 'OPEN_NO_MASTER_KEY'):
        return status

    if not keystore_password:
        module.fail_json(msg='keystore_password is required to open the keystore', changed=False)

    force = build_force_clause(force_keystore)
    container_clause = build_container_clause(container)
    pwd_esc = escape_sql_literal_or_fail(keystore_password, '"', module)

    sql = "ADMINISTER KEY MANAGEMENT %sSET KEYSTORE OPEN IDENTIFIED BY \"%s\"%s" % (
        force, pwd_esc, container_clause
    )
    conn.execute_ddl(sql)
    return get_wallet_status(conn, module.params["container"])


def ensure_keystore_closed(conn, module):
    """Close the keystore if it is open."""
    status = get_wallet_status(conn, module.params["container"])
    current_status = status.get('status', '') if status else ''
    keystore_password = module.params["keystore_password"]
    container = module.params["container"]

    if current_status in ('CLOSED', 'NOT_AVAILABLE', ''):
        return status

    container_clause = build_container_clause(container)
    wallet_type = status.get('wallet_type', '')

    # Auto-login wallets don't need password to close
    if wallet_type in ('AUTOLOGIN', 'LOCAL_AUTOLOGIN'):
        sql = "ADMINISTER KEY MANAGEMENT SET KEYSTORE CLOSE%s" % container_clause
    else:
        if not keystore_password:
            module.fail_json(msg='keystore_password is required to close a password-based keystore', changed=False)
        pwd_esc = escape_sql_literal_or_fail(keystore_password, '"', module)
        sql = "ADMINISTER KEY MANAGEMENT SET KEYSTORE CLOSE IDENTIFIED BY \"%s\"%s" % (
            pwd_esc, container_clause
        )
    conn.execute_ddl(sql)
    return get_wallet_status(conn, module.params["container"])


def create_auto_login(conn, module):
    """Create an auto-login keystore from the existing password keystore."""
    auto_login = module.params["auto_login"]
    keystore_password = module.params["keystore_password"]
    keystore_location = module.params["keystore_location"]

    if auto_login == 'none':
        return

    # Check if the desired auto-login type already exists
    status = get_wallet_status(conn, module.params["container"])
    current_type = status.get('wallet_type', '') if status else ''
    if auto_login == 'auto_login' and current_type == 'AUTOLOGIN':
        return
    if auto_login == 'local_auto_login' and current_type == 'LOCAL_AUTOLOGIN':
        return

    if not keystore_password:
        module.fail_json(msg='keystore_password is required to create auto-login keystore', changed=False)

    # Determine location
    if not keystore_location:
        status = get_wallet_status(conn, module.params["container"])
        keystore_location = status.get('wrl_parameter', '')
        if not keystore_location:
            wallet_root = get_wallet_root(conn)
            if wallet_root:
                keystore_location = wallet_root + '/tde'
            else:
                module.fail_json(
                    msg='Cannot determine keystore location for auto-login creation',
                    changed=False
                )

    local_clause = 'LOCAL ' if auto_login == 'local_auto_login' else ''

    loc_esc = escape_sql_literal_or_fail(keystore_location, "'", module)
    pwd_esc = escape_sql_literal_or_fail(keystore_password, '"', module)
    sql = "ADMINISTER KEY MANAGEMENT CREATE %sAUTO_LOGIN KEYSTORE FROM KEYSTORE '%s' IDENTIFIED BY \"%s\"" % (
        local_clause, loc_esc, pwd_esc
    )
    conn.execute_ddl(sql)


def backup_keystore(conn, module, identified_by_password=None):
    """Create a backup of the keystore.

    After ``ALTER KEYSTORE PASSWORD``, pass *identified_by_password* (the new
    password) so ``IDENTIFIED BY`` matches the current keystore password.
    """
    keystore_password = (
        identified_by_password
        if identified_by_password is not None
        else module.params["keystore_password"]
    )
    backup_tag = module.params["backup_tag"]
    backup_location = module.params["backup_location"]
    force_keystore = module.params["force_keystore"]

    if not keystore_password:
        module.fail_json(msg='keystore_password is required to backup the keystore', changed=False)

    force = build_force_clause(force_keystore)
    pwd_esc = escape_sql_literal_or_fail(keystore_password, '"', module)

    sql = "ADMINISTER KEY MANAGEMENT %sBACKUP KEYSTORE" % force
    if backup_tag:
        tag_esc = escape_sql_literal_or_fail(backup_tag, "'", module)
        sql += " USING '%s'" % tag_esc
    sql += " IDENTIFIED BY \"%s\"" % pwd_esc
    if backup_location:
        loc_esc = escape_sql_literal_or_fail(backup_location, "'", module)
        sql += " TO '%s'" % loc_esc
    conn.execute_ddl(sql)


def change_keystore_password(conn, module):
    """Change the keystore password."""
    keystore_password = module.params["keystore_password"]
    new_password = module.params["new_password"]
    backup = module.params["backup"]
    backup_tag = module.params["backup_tag"]
    force_keystore = module.params["force_keystore"]

    if not keystore_password or not new_password:
        module.fail_json(msg='Both keystore_password and new_password are required', changed=False)

    force = build_force_clause(force_keystore)
    backup_clause = build_backup_clause(backup, backup_tag)
    old_esc = escape_sql_literal_or_fail(keystore_password, '"', module)
    new_esc = escape_sql_literal_or_fail(new_password, '"', module)

    sql = "ADMINISTER KEY MANAGEMENT %sALTER KEYSTORE PASSWORD IDENTIFIED BY \"%s\" SET \"%s\"%s" % (
        force, old_esc, new_esc, backup_clause
    )
    conn.execute_ddl(sql)


def manage_secret(conn, module):
    """Add, update, or delete a secret in the keystore."""
    secret = module.params["secret"]
    secret_client = module.params["secret_client"]
    secret_state = module.params["secret_state"]
    secret_tag = module.params["secret_tag"]
    keystore_password = module.params["keystore_password"]
    backup = module.params["backup"]
    backup_tag = module.params["backup_tag"]
    force_keystore = module.params["force_keystore"]

    force = build_force_clause(force_keystore)
    backup_clause = build_backup_clause(backup, backup_tag)
    exists = secret_exists(conn, secret_client, secret_tag)

    safe_client = escape_sql_literal_or_fail(secret_client, "'", module)
    pwd_esc = escape_sql_literal_or_fail(keystore_password, '"', module)

    if secret_state == 'present':
        safe_secret = escape_sql_literal_or_fail(secret, "'", module)
        tag_clause = ""
        if secret_tag:
            safe_tag = escape_sql_literal_or_fail(secret_tag, "'", module)
            tag_clause = " USING TAG '%s'" % safe_tag

        if exists:
            sql = "ADMINISTER KEY MANAGEMENT %sUPDATE SECRET '%s' FOR CLIENT '%s'%s IDENTIFIED BY \"%s\"%s" % (
                force, safe_secret, safe_client, tag_clause, pwd_esc, backup_clause
            )
        else:
            sql = "ADMINISTER KEY MANAGEMENT %sADD SECRET '%s' FOR CLIENT '%s'%s IDENTIFIED BY \"%s\"%s" % (
                force, safe_secret, safe_client, tag_clause, pwd_esc, backup_clause
            )
        conn.execute_ddl(sql)

    elif secret_state == 'absent':
        if not exists:
            return  # Already absent, idempotent
        tag_clause = ""
        if secret_tag:
            safe_tag_del = escape_sql_literal_or_fail(secret_tag, "'", module)
            tag_clause = " USING TAG '%s'" % safe_tag_del
        sql = "ADMINISTER KEY MANAGEMENT %sDELETE SECRET FOR CLIENT '%s'%s IDENTIFIED BY \"%s\"%s" % (
            force, safe_client, tag_clause, pwd_esc, backup_clause
        )
        conn.execute_ddl(sql)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            user=dict(required=False, aliases=['un', 'username']),
            password=dict(required=False, no_log=True, aliases=['pw']),
            mode=dict(default='normal', choices=["normal", "sysdba", "sysdg", "sysoper", "sysasm"]),
            hostname=dict(required=False, default='localhost', aliases=['host']),
            port=dict(required=False, default=1521, type='int'),
            service_name=dict(required=False, aliases=['sn']),
            dsn=dict(required=False, aliases=['datasource_name']),
            oracle_home=dict(required=False, aliases=['oh']),
            session_container=dict(required=False),

            state=dict(default="present",
                       choices=["present", "absent", "open", "closed", "status"]),
            keystore_location=dict(required=False),
            keystore_password=dict(required=False, no_log=True),
            new_password=dict(required=False, no_log=True),
            auto_login=dict(default='none',
                           choices=['none', 'auto_login', 'local_auto_login']),
            change_password=dict(default=False, type='bool'),
            backup=dict(default=True, type='bool'),
            backup_location=dict(required=False),
            backup_tag=dict(required=False),
            force_keystore=dict(default=False, type='bool'),

            secret=dict(required=False, no_log=True),
            secret_client=dict(required=False),
            secret_tag=dict(required=False),
            secret_state=dict(required=False, choices=['present', 'absent']),

            container=dict(default='current', choices=['current', 'all']),
        ),
        required_if=[
            ('change_password', True, ('keystore_password', 'new_password')),
        ],
        supports_check_mode=True,
    )
    if not HAS_ORACLE_UTILS:
        module.fail_json(msg='oracle_utils is required for oracle_wallet: %s' % _ORACLE_UTILS_ERR)

    sanitize_string_params(module.params)

    state = module.params["state"]
    secret_state = module.params["secret_state"]
    auto_login = module.params["auto_login"]
    change_password_flag = module.params["change_password"]
    backup_tag = module.params["backup_tag"]
    backup_location = module.params["backup_location"]

    validate_wallet_inputs_before_connect(module)

    def _exit_status_query(conn_):
        status = get_wallet_status(conn_, module.params["container"])
        secrets = get_secrets(conn_)
        module.exit_json(
            changed=False,
            wallet_status=status.get('status', '') if status else '',
            wallet_type=status.get('wallet_type', '') if status else '',
            keystore_mode=status.get('keystore_mode', '') if status else '',
            wrl_type=status.get('wrl_type', '') if status else '',
            wrl_parameter=status.get('wrl_parameter', '') if status else '',
            secrets=[{'client': s.get('client', ''), 'tag': s.get('secret_tag', '')} for s in secrets],
        )

    if module.check_mode:
        if state == 'status':
            conn = oracleConnection(module)
            _exit_status_query(conn)
        module.exit_json(changed=False, msg='Check mode: no keystore operations executed')

    conn = oracleConnection(module)

    # Secret management takes priority if secret_state is set
    if secret_state:
        manage_secret(conn, module)
        status = get_wallet_status(conn, module.params["container"])
        module.exit_json(
            changed=conn.changed,
            ddls=_redact_ddls(conn.ddls),
            msg='Secret managed successfully',
            wallet_status=status.get('status', '') if status else '',
            wallet_type=status.get('wallet_type', '') if status else '',
            keystore_mode=status.get('keystore_mode', '') if status else '',
        )

    if state == 'status':
        _exit_status_query(conn)

    if state == 'present':
        status = ensure_keystore_present(conn, module)

        # Handle auto-login creation
        if auto_login != 'none':
            create_auto_login(conn, module)

        # Handle password change
        if change_password_flag:
            change_keystore_password(conn, module)

        # Explicit BACKUP KEYSTORE (WITH BACKUP on ALTER has no TO clause; if
        # backup_tag is set with backup=False, ALTER omits WITH BACKUP too).
        if backup_tag or backup_location:
            if change_password_flag:
                if backup_location or not module.params["backup"]:
                    backup_keystore(
                        conn, module,
                        identified_by_password=module.params["new_password"],
                    )
            else:
                backup_keystore(conn, module)

        status = get_wallet_status(conn, module.params["container"])
        module.exit_json(
            changed=conn.changed,
            ddls=_redact_ddls(conn.ddls),
            msg='Keystore managed successfully',
            wallet_status=status.get('status', '') if status else '',
            wallet_type=status.get('wallet_type', '') if status else '',
            keystore_mode=status.get('keystore_mode', '') if status else '',
        )

    elif state == 'open':
        ensure_keystore_open(conn, module)
        status = get_wallet_status(conn, module.params["container"])
        module.exit_json(
            changed=conn.changed,
            ddls=_redact_ddls(conn.ddls),
            msg='Keystore is open',
            wallet_status=status.get('status', '') if status else '',
            wallet_type=status.get('wallet_type', '') if status else '',
            keystore_mode=status.get('keystore_mode', '') if status else '',
        )

    elif state == 'closed':
        ensure_keystore_closed(conn, module)
        status = get_wallet_status(conn, module.params["container"])
        module.exit_json(
            changed=conn.changed,
            ddls=_redact_ddls(conn.ddls),
            msg='Keystore is closed',
            wallet_status=status.get('status', '') if status else '',
            wallet_type=status.get('wallet_type', '') if status else '',
            keystore_mode=status.get('keystore_mode', '') if status else '',
        )


from ansible.module_utils.basic import *  # noqa: F403

# In these we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
#try:
#    from ansible.module_utils.oracle_utils import (
#        oracleConnection, sanitize_string_params,
#        build_backup_clause, build_container_clause, build_force_clause,
#    )
#except:
#    pass

# In these we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import (  # noqa: E501
        oracleConnection, sanitize_string_params,
        build_backup_clause, build_container_clause, build_force_clause,
    )
except ImportError as e:
    HAS_ORACLE_UTILS = False
    _ORACLE_UTILS_ERR = str(e)

    def sanitize_string_params(module_params):
        for key, value in module_params.items():
            if isinstance(value, str):
                module_params[key] = value.strip()

    def _missing_oracle_utils(*_a, **_kw):
        raise ImportError(
            'oracle_utils is required for oracle_wallet: %s' % _ORACLE_UTILS_ERR
        )

    oracleConnection = _missing_oracle_utils  # noqa: F811
    build_backup_clause = _missing_oracle_utils
    build_container_clause = _missing_oracle_utils
    build_force_clause = _missing_oracle_utils
else:
    HAS_ORACLE_UTILS = True

if __name__ == '__main__':
    main()
