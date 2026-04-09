#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_tde
short_description: Manage Oracle Transparent Data Encryption (TDE)
description:
  - Manage TDE master encryption keys (create, activate, rotate)
  - Encrypt/decrypt tablespaces (online and offline)
  - Query encryption status of tablespaces and keys
  - Export and import encryption keys
  - Configure TDE-related database parameters
  - Supports multitenant (CDB/PDB) environments
  - Compatible with Oracle 19c, 23ai, and 26ai
  - In Oracle 26ai, AES256 is the default algorithm, AES-XTS for tablespace, GCM for column
  - 3DES168, GOST256, and SEED128 are desupported in Oracle 26ai
  - Does NOT manage the keystore itself (use oracle_wallet for that)
  - See connection parameters for oracle_ping
version_added: "3.4.0"
options:
  state:
    description: The intended state
    default: present
    choices: ['present', 'absent', 'status']
  master_key_action:
    description: Action to perform on master encryption key
    choices: ['set_key', 'rotate_key', 'create_key', 'export_keys', 'import_keys']
    required: false
  algorithm:
    description:
      - Encryption algorithm for master key or tablespace encryption
      - AES256 is the default and recommended algorithm
      - 3DES168, GOST256, SEED128 are desupported in Oracle 26ai
    default: AES256
    choices: ['AES128', 'AES192', 'AES256', 'ARIA128', 'ARIA192', 'ARIA256']
  key_tag:
    description: User-defined tag for the master encryption key
    required: false
  keystore_password:
    description: Password for the keystore (required for most operations)
    required: false
  tablespace:
    description: Name of the tablespace to encrypt, decrypt, or rekey
    required: false
  tablespace_state:
    description: Desired encryption state of the tablespace
    choices: ['encrypted', 'decrypted', 'rekeyed']
    required: false
  file_name_convert:
    description:
      - Dictionary mapping old datafile names to new names for online conversion
      - "Example: {'old_file.dbf': 'new_file.dbf'}"
    type: dict
    required: false
  online:
    description: Whether to perform online (true) or offline (false) tablespace conversion
    default: true
    type: bool
  export_file:
    description: File path for key export/import operations
    required: false
  export_secret:
    description: Secret passphrase for key export/import file encryption
    required: false
  tablespace_encryption_policy:
    description:
      - Database-level tablespace encryption policy parameter
      - AUTO_ENABLE encrypts all new tablespaces automatically
      - MANUAL_ENABLE requires explicit ENCRYPTION clause in CREATE TABLESPACE
      - DECRYPT_ONLY allows decryption but prevents new encryption
    choices: ['AUTO_ENABLE', 'MANUAL_ENABLE', 'DECRYPT_ONLY']
    required: false
  force_keystore:
    description: Use FORCE KEYSTORE clause (temporarily opens auto-login keystore)
    default: false
    type: bool
  container:
    description: Container clause for multitenant environments
    default: current
    choices: ['current', 'all']
notes:
  - The keystore must be open before most TDE operations (use oracle_wallet state=open)
  - A master encryption key must exist before encrypting tablespaces
  - oracledb Python module is required
  - Requires ADMINISTER KEY MANAGEMENT or SYSKM privilege
requirements: [ "oracledb" ]
author:
  - Cyrille Modiano
'''

EXAMPLES = '''
- name: Create and activate a master encryption key
  oracle_tde:
    mode: sysdba
    master_key_action: set_key
    keystore_password: "MyKeystorePass123"

- name: Create a master key with specific algorithm and tag
  oracle_tde:
    mode: sysdba
    master_key_action: set_key
    algorithm: AES256
    key_tag: "production_key_2024"
    keystore_password: "MyKeystorePass123"

- name: Rotate the master encryption key
  oracle_tde:
    mode: sysdba
    master_key_action: rotate_key
    keystore_password: "MyKeystorePass123"

- name: Encrypt a tablespace online
  oracle_tde:
    mode: sysdba
    tablespace: USERS
    tablespace_state: encrypted
    algorithm: AES256
    keystore_password: "MyKeystorePass123"

- name: Decrypt a tablespace online
  oracle_tde:
    mode: sysdba
    tablespace: USERS
    tablespace_state: decrypted
    keystore_password: "MyKeystorePass123"

- name: Rekey a tablespace with a new algorithm
  oracle_tde:
    mode: sysdba
    tablespace: USERS
    tablespace_state: rekeyed
    algorithm: AES256
    keystore_password: "MyKeystorePass123"

- name: Export encryption keys
  oracle_tde:
    mode: sysdba
    master_key_action: export_keys
    export_file: /tmp/keys_export.exp
    export_secret: "ExportSecret123"
    keystore_password: "MyKeystorePass123"

- name: Import encryption keys
  oracle_tde:
    mode: sysdba
    master_key_action: import_keys
    export_file: /tmp/keys_export.exp
    export_secret: "ExportSecret123"
    keystore_password: "MyKeystorePass123"

- name: Set tablespace encryption policy to AUTO_ENABLE (26ai)
  oracle_tde:
    mode: sysdba
    tablespace_encryption_policy: AUTO_ENABLE

- name: Get TDE status
  oracle_tde:
    mode: sysdba
    state: status
  register: tde_info

- name: Create and activate key for all PDBs
  oracle_tde:
    mode: sysdba
    master_key_action: set_key
    keystore_password: "MyKeystorePass123"
    container: all
'''


import re as _re


def _redact_ddls(ddls):
    """Redact passwords and secrets from DDL statements before returning to user."""
    redacted = []
    for ddl in ddls:
        s = _re.sub(r'(IDENTIFIED\s+BY\s+)"([^"]|"")*"', r'\1"***"', ddl, flags=_re.IGNORECASE)
        s = _re.sub(r"(SECRET\s+)'([^']|'')*'", r"\1'***'", s, flags=_re.IGNORECASE)
        redacted.append(s)
    return redacted


def get_wallet_status(conn):
    """Check keystore status - prerequisite for TDE operations."""
    sql = "SELECT STATUS, WALLET_TYPE, KEYSTORE_MODE FROM V$ENCRYPTION_WALLET WHERE ROWNUM = 1"
    return conn.execute_select_to_dict(sql, fetchone=True)


def get_active_master_key(conn):
    """Get the currently active master encryption key."""
    sql = """SELECT KEY_ID, TAG, CREATION_TIME, ACTIVATION_TIME, KEY_USE, KEYSTORE_TYPE, ORIGIN
             FROM V$ENCRYPTION_KEYS
             WHERE ACTIVATION_TIME IS NOT NULL
             ORDER BY ACTIVATION_TIME DESC"""
    rows = conn.execute_select_to_dict(sql)
    return rows[0] if rows else {}


def get_encrypted_tablespaces(conn):
    """Get list of encrypted tablespaces with their encryption details."""
    sql = """SELECT t.NAME AS TABLESPACE_NAME, e.ENCRYPTIONALG, e.ENCRYPTEDTS, e.STATUS, e.KEY_VERSION
             FROM V$ENCRYPTED_TABLESPACES e
             JOIN V$TABLESPACE t ON e.TS# = t.TS#"""
    return conn.execute_select_to_dict(sql, fail_on_error=False) or []


def is_tablespace_encrypted(conn, tablespace_name):
    """Check if a specific tablespace is encrypted."""
    sql = """SELECT e.ENCRYPTIONALG, e.ENCRYPTEDTS, e.STATUS
             FROM V$ENCRYPTED_TABLESPACES e
             JOIN V$TABLESPACE t ON e.TS# = t.TS#
             WHERE UPPER(t.NAME) = UPPER(:tablespace)
             AND e.ENCRYPTEDTS = 'YES'"""
    r = conn.execute_select_to_dict(sql, {'tablespace': tablespace_name}, fetchone=True)
    return bool(r)


def check_prerequisites(conn, module, honor_force_keystore=False):
    """Verify that keystore is open before TDE operations.

    When honor_force_keystore is True **and** force_keystore is set, skip the
    check — the FORCE KEYSTORE clause tells Oracle to use the password-based
    keystore even when an auto-login keystore is active, so the password
    keystore may appear CLOSED.  Tablespace operations never emit FORCE
    KEYSTORE, so they must always validate the keystore state.
    """
    if honor_force_keystore and module.params.get("force_keystore"):
        return get_wallet_status(conn)
    status = get_wallet_status(conn)
    if not status or status.get('status') not in ('OPEN', 'OPEN_NO_MASTER_KEY'):
        module.fail_json(
            msg='Keystore is not open (status: %s). Use oracle_wallet state=open first.' % (
                status.get('status', 'UNKNOWN') if status else 'NOT_AVAILABLE'
            ),
            changed=False
        )
    return status


def set_master_key(conn, module):
    """Create and activate a new master encryption key."""
    check_prerequisites(conn, module, honor_force_keystore=True)
    keystore_password = module.params["keystore_password"]
    algorithm = module.params["algorithm"]
    key_tag = module.params["key_tag"]
    force_keystore = module.params["force_keystore"]
    container = module.params["container"]

    if not keystore_password:
        module.fail_json(msg='keystore_password is required for set_key', changed=False)

    force = build_force_clause(force_keystore)
    container_clause = build_container_clause(container)

    sql = "ADMINISTER KEY MANAGEMENT %sSET KEY" % force
    if algorithm:
        sql += " USING ALGORITHM '%s'" % algorithm
    if key_tag:
        sql += " USING TAG '%s'" % key_tag.replace("'", "''")
    sql += " IDENTIFIED BY \"%s\"" % keystore_password.replace('"', '""')
    sql += build_backup_clause()
    sql += container_clause

    conn.execute_ddl(sql, ddls_entry=_redact_ddls([sql])[0])


def create_master_key(conn, module):
    """Create a master key without activating it."""
    check_prerequisites(conn, module, honor_force_keystore=True)
    keystore_password = module.params["keystore_password"]
    algorithm = module.params["algorithm"]
    key_tag = module.params["key_tag"]
    force_keystore = module.params["force_keystore"]
    container = module.params["container"]

    if not keystore_password:
        module.fail_json(msg='keystore_password is required for create_key', changed=False)

    force = build_force_clause(force_keystore)
    container_clause = build_container_clause(container)

    sql = "ADMINISTER KEY MANAGEMENT %sCREATE KEY" % force
    if algorithm:
        sql += " USING ALGORITHM '%s'" % algorithm
    if key_tag:
        sql += " USING TAG '%s'" % key_tag.replace("'", "''")
    sql += " IDENTIFIED BY \"%s\"" % keystore_password.replace('"', '""')
    sql += build_backup_clause()
    sql += container_clause

    conn.execute_ddl(sql, ddls_entry=_redact_ddls([sql])[0])


def export_keys(conn, module):
    """Export encryption keys to a file."""
    check_prerequisites(conn, module, honor_force_keystore=True)
    keystore_password = module.params["keystore_password"]
    export_file = module.params["export_file"]
    export_secret = module.params["export_secret"]
    force_keystore = module.params["force_keystore"]

    if not keystore_password:
        module.fail_json(msg='keystore_password is required for export_keys', changed=False)
    if not export_file:
        module.fail_json(msg='export_file is required for export_keys', changed=False)
    if not export_secret:
        module.fail_json(msg='export_secret is required for export_keys', changed=False)

    force = build_force_clause(force_keystore)

    safe_secret = export_secret.replace("'", "''")
    safe_file = export_file.replace("'", "''")
    sql = "ADMINISTER KEY MANAGEMENT %sEXPORT KEYS WITH SECRET '%s' TO '%s' IDENTIFIED BY \"%s\"" % (
        force, safe_secret, safe_file, keystore_password.replace('"', '""')
    )
    conn.execute_ddl(sql, ddls_entry=_redact_ddls([sql])[0])


def import_keys(conn, module):
    """Import encryption keys from a file."""
    check_prerequisites(conn, module, honor_force_keystore=True)
    keystore_password = module.params["keystore_password"]
    export_file = module.params["export_file"]
    export_secret = module.params["export_secret"]
    force_keystore = module.params["force_keystore"]

    if not keystore_password:
        module.fail_json(msg='keystore_password is required for import_keys', changed=False)
    if not export_file:
        module.fail_json(msg='export_file is required for import_keys', changed=False)
    if not export_secret:
        module.fail_json(msg='export_secret is required for import_keys', changed=False)

    force = build_force_clause(force_keystore)

    safe_secret = export_secret.replace("'", "''")
    safe_file = export_file.replace("'", "''")
    sql = "ADMINISTER KEY MANAGEMENT %sIMPORT KEYS WITH SECRET '%s' FROM '%s' IDENTIFIED BY \"%s\"%s" % (
        force, safe_secret, safe_file, keystore_password.replace('"', '""'), build_backup_clause()
    )
    conn.execute_ddl(sql, ddls_entry=_redact_ddls([sql])[0])


def encrypt_tablespace(conn, module):
    """Encrypt a tablespace."""
    check_prerequisites(conn, module)
    tablespace = module.params["tablespace"]
    algorithm = module.params["algorithm"]
    online = module.params["online"]
    file_name_convert = module.params["file_name_convert"]

    if not tablespace:
        module.fail_json(msg='tablespace is required for encryption', changed=False)

    # Check if already encrypted
    if is_tablespace_encrypted(conn, tablespace):
        return  # Already encrypted, idempotent

    # Verify master key exists
    key = get_active_master_key(conn)
    if not key:
        module.fail_json(
            msg='No active master key found. Use master_key_action=set_key first.',
            changed=False
        )

    mode = 'ONLINE' if online else 'OFFLINE'

    safe_ts = '"%s"' % tablespace.upper().replace('"', '""')
    sql = "ALTER TABLESPACE %s ENCRYPTION %s" % (safe_ts, mode)
    if algorithm and online:
        sql += " USING '%s'" % algorithm
    sql += " ENCRYPT"

    if file_name_convert and online:
        pairs = ', '.join("'%s', '%s'" % (k.replace("'", "''"), v.replace("'", "''")) for k, v in file_name_convert.items())
        sql += " FILE_NAME_CONVERT = (%s)" % pairs

    conn.execute_ddl(sql)


def decrypt_tablespace(conn, module):
    """Decrypt a tablespace."""
    check_prerequisites(conn, module)
    tablespace = module.params["tablespace"]
    online = module.params["online"]
    file_name_convert = module.params["file_name_convert"]

    if not tablespace:
        module.fail_json(msg='tablespace is required for decryption', changed=False)

    # Check if already decrypted
    if not is_tablespace_encrypted(conn, tablespace):
        return  # Already decrypted, idempotent

    mode = 'ONLINE' if online else 'OFFLINE'

    safe_ts = '"%s"' % tablespace.upper().replace('"', '""')
    sql = "ALTER TABLESPACE %s ENCRYPTION %s DECRYPT" % (safe_ts, mode)

    if file_name_convert and online:
        pairs = ', '.join("'%s', '%s'" % (k.replace("'", "''"), v.replace("'", "''")) for k, v in file_name_convert.items())
        sql += " FILE_NAME_CONVERT = (%s)" % pairs

    conn.execute_ddl(sql)


def rekey_tablespace(conn, module):
    """Rekey a tablespace (change encryption key/algorithm)."""
    check_prerequisites(conn, module)
    tablespace = module.params["tablespace"]
    algorithm = module.params["algorithm"]
    online = module.params["online"]
    file_name_convert = module.params["file_name_convert"]

    if not tablespace:
        module.fail_json(msg='tablespace is required for rekeying', changed=False)

    mode = 'ONLINE' if online else 'OFFLINE'

    safe_ts = '"%s"' % tablespace.upper().replace('"', '""')
    sql = "ALTER TABLESPACE %s ENCRYPTION %s" % (safe_ts, mode)
    if algorithm and online:
        sql += " USING '%s'" % algorithm
    sql += " REKEY"

    if file_name_convert and online:
        pairs = ', '.join("'%s', '%s'" % (k.replace("'", "''"), v.replace("'", "''")) for k, v in file_name_convert.items())
        sql += " FILE_NAME_CONVERT = (%s)" % pairs

    conn.execute_ddl(sql)


def set_encryption_parameter(conn, module):
    """Set tablespace encryption policy parameter."""
    policy = module.params["tablespace_encryption_policy"]
    if not policy:
        return

    container = module.params["container"]

    # Check current value
    sql = "SELECT VALUE FROM V$PARAMETER WHERE NAME = 'tablespace_encryption'"
    r = conn.execute_select_to_dict(sql, fetchone=True)
    current = r.get('value', '') if r else ''

    if current and current.upper() == policy.upper():
        return  # Already set, idempotent

    container_clause = build_container_clause(container)
    conn.execute_ddl("ALTER SYSTEM SET TABLESPACE_ENCRYPTION = '%s' SCOPE=SPFILE%s" % (policy, container_clause))


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

            state=dict(default="present", choices=["present", "absent", "status"]),
            master_key_action=dict(required=False,
                                   choices=['set_key', 'rotate_key', 'create_key',
                                            'export_keys', 'import_keys']),
            algorithm=dict(default='AES256',
                          choices=['AES128', 'AES192', 'AES256',
                                   'ARIA128', 'ARIA192', 'ARIA256']),
            key_tag=dict(required=False),
            keystore_password=dict(required=False, no_log=True),

            tablespace=dict(required=False),
            tablespace_state=dict(required=False,
                                  choices=['encrypted', 'decrypted', 'rekeyed']),
            file_name_convert=dict(required=False, type='dict'),
            online=dict(default=True, type='bool'),

            export_file=dict(required=False),
            export_secret=dict(required=False, no_log=True),

            tablespace_encryption_policy=dict(required=False,
                                              choices=['AUTO_ENABLE', 'MANUAL_ENABLE',
                                                       'DECRYPT_ONLY']),

            force_keystore=dict(default=False, type='bool'),
            container=dict(default='current', choices=['current', 'all']),
        ),
        required_if=[
            ('master_key_action', 'export_keys', ('export_file', 'export_secret')),
            ('master_key_action', 'import_keys', ('export_file', 'export_secret')),
        ],
        supports_check_mode=True,
    )
    sanitize_string_params(module.params)

    state = module.params["state"]
    master_key_action = module.params["master_key_action"]
    tablespace_state = module.params["tablespace_state"]
    tablespace_encryption_policy = module.params["tablespace_encryption_policy"]

    conn = oracleConnection(module)

    if state == 'status':
        wallet = get_wallet_status(conn)
        master_key = get_active_master_key(conn)
        encrypted_ts = get_encrypted_tablespaces(conn)
        module.exit_json(
            changed=False,
            wallet_status=wallet.get('status', '') if wallet else '',
            master_key=master_key,
            encrypted_tablespaces=encrypted_ts,
        )

    if state == 'present':
        # Handle encryption policy parameter
        if tablespace_encryption_policy:
            set_encryption_parameter(conn, module)

        # Handle master key operations
        if master_key_action in ('set_key', 'rotate_key'):
            set_master_key(conn, module)
        elif master_key_action == 'create_key':
            create_master_key(conn, module)
        elif master_key_action == 'export_keys':
            export_keys(conn, module)
        elif master_key_action == 'import_keys':
            import_keys(conn, module)

        # Handle tablespace encryption
        if tablespace_state == 'encrypted':
            encrypt_tablespace(conn, module)
        elif tablespace_state == 'decrypted':
            decrypt_tablespace(conn, module)
        elif tablespace_state == 'rekeyed':
            rekey_tablespace(conn, module)

        # Gather final status
        master_key = get_active_master_key(conn)
        encrypted_ts = get_encrypted_tablespaces(conn)
        module.exit_json(
            changed=conn.changed,
            ddls=_redact_ddls(conn.ddls),
            msg='TDE operations completed successfully',
            master_key=master_key,
            encrypted_tablespaces=encrypted_ts,
        )

    elif state == 'absent':
        # Decrypt tablespace — requires tablespace parameter
        if not module.params["tablespace"]:
            module.fail_json(
                msg='state=absent requires a tablespace to decrypt',
                changed=False,
            )
        decrypt_tablespace(conn, module)
        encrypted_ts = get_encrypted_tablespaces(conn)
        module.exit_json(
            changed=conn.changed,
            ddls=_redact_ddls(conn.ddls),
            msg='Tablespace decryption completed',
            encrypted_tablespaces=encrypted_ts,
        )


from ansible.module_utils.basic import *  # noqa: F403

# In these we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
#try:
#    from ansible.module_utils.oracle_utils import oracleConnection
#except:
#    pass

# In these we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import (  # noqa: E501
        oracleConnection, sanitize_string_params,
        build_backup_clause, build_container_clause, build_force_clause,
    )
except ImportError as e:
    _oracle_utils_err = e

    def sanitize_string_params(module_params):
        for key, value in module_params.items():
            if isinstance(value, str):
                module_params[key] = value.strip()

    def oracleConnection(*args, **kwargs):
        raise ImportError("oracle_utils is required: %s" % _oracle_utils_err)

    def build_backup_clause(*args, **kwargs):
        raise ImportError("oracle_utils is required: %s" % _oracle_utils_err)

    def build_container_clause(*args, **kwargs):
        raise ImportError("oracle_utils is required: %s" % _oracle_utils_err)

    def build_force_clause(*args, **kwargs):
        raise ImportError("oracle_utils is required: %s" % _oracle_utils_err)

if __name__ == '__main__':
    main()
