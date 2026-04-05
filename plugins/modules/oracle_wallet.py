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


def get_wallet_status(conn):
    """Query V$ENCRYPTION_WALLET for current keystore status."""
    sql = """SELECT WRL_TYPE, WRL_PARAMETER, STATUS, WALLET_TYPE, WALLET_ORDER, KEYSTORE_MODE
             FROM V$ENCRYPTION_WALLET
             WHERE ROWNUM = 1"""
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


def secret_exists(conn, client_name):
    """Check if a specific secret client entry exists."""
    secrets = get_secrets(conn)
    if not secrets:
        return False
    for s in secrets:
        if s.get('client', '').upper() == client_name.upper():
            return True
    return False


def ensure_keystore_present(conn, module):
    """Create a software keystore if it doesn't exist."""
    status = get_wallet_status(conn)
    keystore_location = module.params["keystore_location"]
    keystore_password = module.params["keystore_password"]

    if not keystore_password:
        module.fail_json(msg='keystore_password is required to create a keystore', changed=False)

    # If keystore already exists (status is not NOT_AVAILABLE and not empty)
    current_status = status.get('status', '') if status else ''
    if current_status and current_status != 'NOT_AVAILABLE':
        return status

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

    sql = "ADMINISTER KEY MANAGEMENT CREATE KEYSTORE '%s' IDENTIFIED BY \"%s\"" % (
        keystore_location, keystore_password
    )
    conn.execute_ddl(sql)
    return get_wallet_status(conn)


def ensure_keystore_open(conn, module):
    """Open the keystore if it is closed."""
    status = get_wallet_status(conn)
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

    sql = "ADMINISTER KEY MANAGEMENT %sSET KEYSTORE OPEN IDENTIFIED BY \"%s\"%s" % (
        force, keystore_password, container_clause
    )
    conn.execute_ddl(sql)
    return get_wallet_status(conn)


def ensure_keystore_closed(conn, module):
    """Close the keystore if it is open."""
    status = get_wallet_status(conn)
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
        sql = "ADMINISTER KEY MANAGEMENT SET KEYSTORE CLOSE IDENTIFIED BY \"%s\"%s" % (
            keystore_password, container_clause
        )
    conn.execute_ddl(sql)
    return get_wallet_status(conn)


def create_auto_login(conn, module):
    """Create an auto-login keystore from the existing password keystore."""
    auto_login = module.params["auto_login"]
    keystore_password = module.params["keystore_password"]
    keystore_location = module.params["keystore_location"]

    if auto_login == 'none':
        return

    if not keystore_password:
        module.fail_json(msg='keystore_password is required to create auto-login keystore', changed=False)

    # Determine location
    if not keystore_location:
        status = get_wallet_status(conn)
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

    sql = "ADMINISTER KEY MANAGEMENT CREATE %sAUTO_LOGIN KEYSTORE FROM KEYSTORE '%s' IDENTIFIED BY \"%s\"" % (
        local_clause, keystore_location, keystore_password
    )
    conn.execute_ddl(sql)


def backup_keystore(conn, module):
    """Create a backup of the keystore."""
    keystore_password = module.params["keystore_password"]
    backup_tag = module.params["backup_tag"]
    backup_location = module.params["backup_location"]
    force_keystore = module.params["force_keystore"]

    if not keystore_password:
        module.fail_json(msg='keystore_password is required to backup the keystore', changed=False)

    force = build_force_clause(force_keystore)

    sql = "ADMINISTER KEY MANAGEMENT %sBACKUP KEYSTORE" % force
    if backup_tag:
        sql += " USING '%s'" % backup_tag
    sql += " IDENTIFIED BY \"%s\"" % keystore_password
    if backup_location:
        sql += " TO '%s'" % backup_location
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

    sql = "ADMINISTER KEY MANAGEMENT %sALTER KEYSTORE PASSWORD IDENTIFIED BY \"%s\" SET \"%s\"%s" % (
        force, keystore_password, new_password, backup_clause
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

    if not secret_client:
        module.fail_json(msg='secret_client is required for secret management', changed=False)
    if not keystore_password:
        module.fail_json(msg='keystore_password is required for secret management', changed=False)

    force = build_force_clause(force_keystore)
    backup_clause = build_backup_clause(backup, backup_tag)
    exists = secret_exists(conn, secret_client)

    if secret_state == 'present':
        if not secret:
            module.fail_json(msg='secret is required when secret_state=present', changed=False)

        tag_clause = ""
        if secret_tag:
            tag_clause = " USING TAG '%s'" % secret_tag

        if exists:
            sql = "ADMINISTER KEY MANAGEMENT %sUPDATE SECRET '%s' FOR CLIENT '%s'%s IDENTIFIED BY \"%s\"%s" % (
                force, secret, secret_client, tag_clause, keystore_password, backup_clause
            )
        else:
            sql = "ADMINISTER KEY MANAGEMENT %sADD SECRET '%s' FOR CLIENT '%s'%s IDENTIFIED BY \"%s\"%s" % (
                force, secret, secret_client, tag_clause, keystore_password, backup_clause
            )
        conn.execute_ddl(sql)

    elif secret_state == 'absent':
        if not exists:
            return  # Already absent, idempotent
        sql = "ADMINISTER KEY MANAGEMENT %sDELETE SECRET FOR CLIENT '%s' IDENTIFIED BY \"%s\"%s" % (
            force, secret_client, keystore_password, backup_clause
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
    sanitize_string_params(module.params)

    state = module.params["state"]
    secret_state = module.params["secret_state"]
    auto_login = module.params["auto_login"]
    change_password_flag = module.params["change_password"]
    backup_tag = module.params["backup_tag"]
    backup_location = module.params["backup_location"]

    conn = oracleConnection(module)

    # Secret management takes priority if secret_state is set
    if secret_state:
        manage_secret(conn, module)
        status = get_wallet_status(conn)
        module.exit_json(
            changed=conn.changed,
            ddls=conn.ddls,
            msg='Secret managed successfully',
            wallet_status=status.get('status', '') if status else '',
            wallet_type=status.get('wallet_type', '') if status else '',
            keystore_mode=status.get('keystore_mode', '') if status else '',
        )

    if state == 'status':
        status = get_wallet_status(conn)
        secrets = get_secrets(conn)
        module.exit_json(
            changed=False,
            wallet_status=status.get('status', '') if status else '',
            wallet_type=status.get('wallet_type', '') if status else '',
            keystore_mode=status.get('keystore_mode', '') if status else '',
            wrl_type=status.get('wrl_type', '') if status else '',
            wrl_parameter=status.get('wrl_parameter', '') if status else '',
            secrets=[{'client': s.get('client', ''), 'tag': s.get('secret_tag', '')} for s in secrets],
        )

    elif state == 'present':
        status = ensure_keystore_present(conn, module)

        # Handle auto-login creation
        if auto_login != 'none':
            create_auto_login(conn, module)

        # Handle password change
        if change_password_flag:
            change_keystore_password(conn, module)

        # Handle explicit backup request
        if backup_tag or backup_location:
            # Only backup if explicitly requested via tag or location
            if not change_password_flag:  # change_password already does WITH BACKUP
                backup_keystore(conn, module)

        status = get_wallet_status(conn)
        module.exit_json(
            changed=conn.changed,
            ddls=conn.ddls,
            msg='Keystore managed successfully',
            wallet_status=status.get('status', '') if status else '',
            wallet_type=status.get('wallet_type', '') if status else '',
            keystore_mode=status.get('keystore_mode', '') if status else '',
        )

    elif state == 'open':
        ensure_keystore_open(conn, module)
        status = get_wallet_status(conn)
        module.exit_json(
            changed=conn.changed,
            ddls=conn.ddls,
            msg='Keystore is open',
            wallet_status=status.get('status', '') if status else '',
            wallet_type=status.get('wallet_type', '') if status else '',
            keystore_mode=status.get('keystore_mode', '') if status else '',
        )

    elif state == 'closed':
        ensure_keystore_closed(conn, module)
        status = get_wallet_status(conn)
        module.exit_json(
            changed=conn.changed,
            ddls=conn.ddls,
            msg='Keystore is closed',
            wallet_status=status.get('status', '') if status else '',
            wallet_type=status.get('wallet_type', '') if status else '',
            keystore_mode=status.get('keystore_mode', '') if status else '',
        )

    elif state == 'absent':
        # Oracle does not have a DROP KEYSTORE command. Keystore removal is a filesystem operation.
        module.fail_json(
            msg='Oracle does not support dropping a keystore via SQL. '
                'Remove the keystore files manually from the filesystem.',
            changed=False,
        )


from ansible.module_utils.basic import *  # noqa: F403

try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import (  # noqa: E501
        oracleConnection, sanitize_string_params,
        build_backup_clause, build_container_clause, build_force_clause,
    )
except ImportError:
    def sanitize_string_params(_params):
        pass

if __name__ == '__main__':
    main()
