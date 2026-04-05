#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_orapki
short_description: Manage Oracle PKI wallets, certificates, and credentials via orapki
description:
  - Manage Oracle PKI wallets (TLS/SSL, password stores, observer wallets) using the orapki CLI
  - Create, delete, and display wallets (PKCS#12 and auto-login SSO)
  - Add, remove, and export certificates (trusted CA, user/server, self-signed)
  - Manage credentials and secrets via orapki secretstore (replaces mkstore)
  - Supports Data Guard observer wallet setup, OUD wallets, TLS listener wallets
  - Does NOT manage TDE keystores (use oracle_wallet for that)
  - Compatible with Oracle 19c, 23ai, and 26ai
  - In Oracle 26ai, mkstore is deprecated - use orapki secretstore instead
version_added: "3.4.0"
options:
  oracle_home:
    description: ORACLE_HOME path where orapki binary is located
    required: true
    aliases: ['oh']
  state:
    description: The intended state of the wallet
    default: present
    choices: ['present', 'absent', 'status']
  wallet_location:
    description: Path to the wallet directory (where ewallet.p12 / cwallet.sso reside)
    required: true
  wallet_password:
    description: Password for the wallet
    required: false
  new_password:
    description: New password when changing wallet password (with change_password=true)
    required: false
  change_password:
    description: Whether to change the wallet password
    default: false
    type: bool
  auto_login:
    description:
      - Type of auto-login wallet to create
      - auto_login creates cwallet.sso alongside ewallet.p12
      - local_auto_login creates a host-bound auto-login wallet
      - auto_login_only creates only cwallet.sso without ewallet.p12
    default: none
    choices: ['none', 'auto_login', 'local_auto_login', 'auto_login_only']
  cert_state:
    description: State of certificate management operation
    choices: ['present', 'absent', 'exported']
    required: false
  cert_type:
    description:
      - Type of certificate to add (required when cert_state=present)
      - trusted_cert for CA certificates
      - user_cert for server/client identity certificates
      - self_signed for test/development self-signed certificates
    choices: ['trusted_cert', 'user_cert', 'self_signed']
    required: false
  cert_file:
    description: Path to certificate file (for trusted_cert and user_cert)
    required: false
  cert_dn:
    description: Distinguished Name for the certificate (e.g. CN=myserver,O=MyOrg)
    required: false
  cert_alias:
    description: Alias name for the certificate (Oracle 26ai+)
    required: false
  cert_keysize:
    description: Key size for self-signed certificate generation
    default: 2048
    type: int
  cert_validity:
    description: Validity period in days for self-signed certificates
    default: 3650
    type: int
  cert_export_file:
    description: Output file path for certificate export
    required: false
  credential_state:
    description: State of credential/secret management operation
    choices: ['present', 'absent']
    required: false
  credential_type:
    description:
      - Type of secret store entry
      - credential for database connection credentials (alias/db/user/password)
      - entry for generic secret values
    default: credential
    choices: ['credential', 'entry']
  credential_alias:
    description: Alias name for the credential or entry
    required: false
  credential_db:
    description: Database connect string / TNS alias for the credential
    required: false
  credential_user:
    description: Username for the credential
    required: false
  credential_password:
    description: Password for the credential (no_log)
    required: false
  credential_secret:
    description: Secret value for a generic entry (no_log)
    required: false
notes:
  - Requires orapki binary in ORACLE_HOME/bin
  - Does not require a database connection (pure CLI tool)
  - For TDE keystore management, use oracle_wallet instead
  - In Oracle 26ai, mkstore is deprecated - this module uses orapki secretstore
  - Wallet passwords are never logged (no_log=True)
requirements: []
author:
  - Cyrille Modiano
'''

EXAMPLES = '''
# --- TLS Wallet ---
- name: Create TLS wallet with local auto-login
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    state: present
    wallet_location: /opt/oracle/wallets/tls
    wallet_password: "WalletPass123"
    auto_login: local_auto_login

- name: Add trusted CA certificate
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    wallet_location: /opt/oracle/wallets/tls
    wallet_password: "WalletPass123"
    cert_state: present
    cert_type: trusted_cert
    cert_file: /tmp/ca-root.crt

- name: Add server certificate
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    wallet_location: /opt/oracle/wallets/tls
    wallet_password: "WalletPass123"
    cert_state: present
    cert_type: user_cert
    cert_file: /tmp/server.crt

- name: Create self-signed certificate for testing
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    wallet_location: /opt/oracle/wallets/test
    wallet_password: "TestPass123"
    cert_state: present
    cert_type: self_signed
    cert_dn: "CN=testserver.local,O=TestOrg"
    cert_keysize: 4096
    cert_validity: 365

- name: Remove a certificate by DN
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    wallet_location: /opt/oracle/wallets/tls
    wallet_password: "WalletPass123"
    cert_state: absent
    cert_dn: "CN=oldserver.example.com"

- name: Export certificate to file
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    wallet_location: /opt/oracle/wallets/tls
    cert_state: exported
    cert_dn: "CN=myserver.example.com"
    cert_export_file: /tmp/myserver.crt

# --- Observer Wallet ---
- name: Create observer wallet with auto-login
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    state: present
    wallet_location: /opt/oracle/wallets/observer
    wallet_password: "ObsPass123"
    auto_login: auto_login

- name: Add primary DB credential to observer wallet
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    wallet_location: /opt/oracle/wallets/observer
    wallet_password: "ObsPass123"
    credential_state: present
    credential_alias: primary_db
    credential_db: PROD
    credential_user: sys
    credential_password: "SysPass123"

- name: Add standby DB credential to observer wallet
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    wallet_location: /opt/oracle/wallets/observer
    wallet_password: "ObsPass123"
    credential_state: present
    credential_alias: standby_db
    credential_db: STDBY
    credential_user: sys
    credential_password: "SysPass123"

# --- OUD Wallet ---
- name: Add OUD credential
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    wallet_location: /opt/oracle/wallets/oud
    wallet_password: "OudPass123"
    credential_state: present
    credential_alias: oud_server
    credential_db: "oud.example.com:1636"
    credential_user: "cn=admin"
    credential_password: "LdapPass123"

# --- Password Store ---
- name: Add generic secret entry
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    wallet_location: /opt/oracle/wallets/secrets
    wallet_password: "StorePass123"
    credential_state: present
    credential_type: entry
    credential_alias: api_key
    credential_secret: "sk-abc123..."

# --- Status / Cleanup ---
- name: Display wallet contents
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    state: status
    wallet_location: /opt/oracle/wallets/tls
  register: wallet_info

- name: Delete a wallet
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    state: absent
    wallet_location: /opt/oracle/wallets/old

- name: Change wallet password
  oracle_orapki:
    oracle_home: /u01/app/oracle/product/19c
    state: present
    wallet_location: /opt/oracle/wallets/tls
    change_password: true
    wallet_password: "OldPass123"
    new_password: "NewPass456"
'''

import os


# ============================================================================
# Core orapki execution
# ============================================================================

def _get_orapki_bin(module):
    """Resolve the orapki binary path from oracle_home."""
    oracle_home = module.params["oracle_home"]
    orapki_bin = os.path.join(oracle_home, 'bin', 'orapki')
    if not os.path.exists(orapki_bin):
        module.fail_json(
            msg='orapki not found at %s' % orapki_bin, changed=False
        )
    return orapki_bin


def _run_orapki(module, args):
    """Execute an orapki command and return (stdout, stderr).

    Uses list-form command to avoid shell injection.
    Fails the module on non-zero return code.
    """
    cmd = [_get_orapki_bin(module)] + args
    rc, stdout, stderr = module.run_command(cmd)
    if rc != 0:
        module.fail_json(
            msg='orapki failed: %s' % (stderr or stdout).strip(),
            rc=rc,
            cmd=' '.join(args),
            changed=False,
        )
    return stdout, stderr


# ============================================================================
# Output parsing
# ============================================================================

def _parse_wallet_display(stdout):
    """Parse 'orapki wallet display' output into structured data.

    Returns dict with keys: requested_certs, user_certs, trusted_certs (lists of DNs).
    """
    result = {
        'requested_certs': [],
        'user_certs': [],
        'trusted_certs': [],
    }
    current_section = None
    section_map = {
        'requested certificates:': 'requested_certs',
        'user certificates:': 'user_certs',
        'trusted certificates:': 'trusted_certs',
    }

    for line in stdout.split('\n'):
        stripped = line.strip().lower()
        if stripped in section_map:
            current_section = section_map[stripped]
            continue
        if current_section and line.strip().startswith('Subject:'):
            dn = line.split(':', 1)[1].strip()
            result[current_section].append(dn)

    return result


def _parse_list_credentials(stdout):
    """Parse 'orapki secretstore list_credentials' output.

    Returns list of alias strings extracted from output lines.
    """
    aliases = []
    for line in stdout.split('\n'):
        line = line.strip()
        if '=' in line and line.startswith('oracle.security.client'):
            alias = line.split('=', 1)[1].strip()
            if alias:
                aliases.append(alias)
    return aliases


# ============================================================================
# Wallet lifecycle
# ============================================================================

def _wallet_exists(wallet_location):
    """Check if a wallet exists at the given location."""
    p12 = os.path.join(wallet_location, 'ewallet.p12')
    sso = os.path.join(wallet_location, 'cwallet.sso')
    return os.path.isfile(p12) or os.path.isfile(sso)


def _wallet_display(module):
    """Run orapki wallet display and return parsed result."""
    wallet_location = module.params["wallet_location"]
    wallet_password = module.params["wallet_password"]

    args = ['wallet', 'display', '-wallet', wallet_location]
    if wallet_password:
        args.extend(['-pwd', wallet_password])

    stdout, _stderr = _run_orapki(module, args)
    parsed = _parse_wallet_display(stdout)
    parsed['raw_output'] = stdout
    return parsed


def _ensure_wallet_present(module):
    """Create a wallet if it doesn't exist."""
    wallet_location = module.params["wallet_location"]
    wallet_password = module.params["wallet_password"]
    auto_login = module.params["auto_login"]

    if _wallet_exists(wallet_location):
        return False

    if module.check_mode:
        return True

    if auto_login == 'auto_login_only':
        args = ['wallet', 'create', '-wallet', wallet_location,
                '-auto_login_only']
    else:
        if not wallet_password:
            module.fail_json(
                msg='wallet_password is required to create a wallet',
                changed=False,
            )
        args = ['wallet', 'create', '-wallet', wallet_location,
                '-pwd', wallet_password]
        if auto_login == 'auto_login':
            args.append('-auto_login')
        elif auto_login == 'local_auto_login':
            args.append('-auto_login_local')

    _run_orapki(module, args)
    return True


def _ensure_wallet_absent(module):
    """Delete a wallet if it exists."""
    wallet_location = module.params["wallet_location"]

    if not _wallet_exists(wallet_location):
        return False

    if module.check_mode:
        return True

    _run_orapki(module, ['wallet', 'delete', '-wallet', wallet_location])
    return True


def _change_wallet_password(module):
    """Change the wallet password."""
    wallet_location = module.params["wallet_location"]
    wallet_password = module.params["wallet_password"]
    new_password = module.params["new_password"]

    if not wallet_password or not new_password:
        module.fail_json(
            msg='Both wallet_password and new_password are required',
            changed=False,
        )

    if module.check_mode:
        return True

    _run_orapki(module, [
        'wallet', 'change_pwd', '-wallet', wallet_location,
        '-oldpwd', wallet_password, '-newpwd', new_password,
    ])
    return True


# ============================================================================
# Certificate management
# ============================================================================

def _cert_exists_in_wallet(module, dn=None, alias=None):
    """Check if a certificate with given DN or alias exists in the wallet."""
    try:
        parsed = _wallet_display(module)
    except SystemExit:
        return False

    if dn:
        all_certs = (parsed['trusted_certs']
                     + parsed['user_certs']
                     + parsed['requested_certs'])
        for cert_dn in all_certs:
            if cert_dn.upper() == dn.upper():
                return True

    if alias:
        raw = parsed.get('raw_output', '')
        if alias in raw:
            return True

    return False


def _manage_cert(module):
    """Add, remove, or export certificates."""
    cert_state = module.params["cert_state"]

    if cert_state == 'present':
        return _add_cert(module)

    if cert_state == 'absent':
        return _remove_cert(module)

    if cert_state == 'exported':
        cert_dn = module.params["cert_dn"]
        cert_export_file = module.params["cert_export_file"]
        wallet_location = module.params["wallet_location"]
        if not cert_dn:
            module.fail_json(
                msg='cert_dn is required for certificate export',
                changed=False,
            )
        if module.check_mode:
            return True
        _run_orapki(module, [
            'wallet', 'export', '-wallet', wallet_location,
            '-dn', cert_dn, '-cert', cert_export_file,
        ])
        return True

    return False


def _add_cert(module):
    """Add a certificate to the wallet."""
    cert_type = module.params["cert_type"]
    cert_file = module.params["cert_file"]
    cert_dn = module.params["cert_dn"]
    cert_keysize = module.params["cert_keysize"]
    cert_validity = module.params["cert_validity"]
    wallet_location = module.params["wallet_location"]
    wallet_password = module.params["wallet_password"]
    if cert_type in ('trusted_cert', 'user_cert'):
        if not cert_file:
            module.fail_json(
                msg='cert_file is required for %s' % cert_type,
                changed=False,
            )
        # For trusted/user certs, check DN from file would require parsing
        # the cert. Instead, we let orapki handle duplicates (it will error).
        # For self_signed, we can check by DN.
        if module.check_mode:
            return True
        type_flag = '-trusted_cert' if cert_type == 'trusted_cert' else '-user_cert'
        args = ['wallet', 'add', '-wallet', wallet_location,
                type_flag, '-cert', cert_file]
        if wallet_password:
            args.extend(['-pwd', wallet_password])
        _run_orapki(module, args)
        return True

    if cert_type == 'self_signed':
        if not cert_dn:
            module.fail_json(
                msg='cert_dn is required for self_signed certificates',
                changed=False,
            )
        if _cert_exists_in_wallet(module, dn=cert_dn):
            return False
        if module.check_mode:
            return True
        args = ['wallet', 'add', '-wallet', wallet_location,
                '-dn', cert_dn, '-keysize', str(cert_keysize),
                '-self_signed', '-validity', str(cert_validity)]
        if wallet_password:
            args.extend(['-pwd', wallet_password])
        _run_orapki(module, args)
        return True

    return False


def _remove_cert(module):
    """Remove a certificate from the wallet."""
    cert_dn = module.params["cert_dn"]
    cert_alias = module.params["cert_alias"]
    wallet_location = module.params["wallet_location"]
    wallet_password = module.params["wallet_password"]
    if not cert_dn and not cert_alias:
        module.fail_json(
            msg='cert_dn or cert_alias is required to remove a certificate',
            changed=False,
        )

    if not _cert_exists_in_wallet(module, dn=cert_dn, alias=cert_alias):
        return False

    if module.check_mode:
        return True

    args = ['wallet', 'remove', '-wallet', wallet_location]
    if cert_dn:
        args.extend(['-dn', cert_dn])
    elif cert_alias:
        args.extend(['-alias', cert_alias])
    if wallet_password:
        args.extend(['-pwd', wallet_password])

    _run_orapki(module, args)
    return True


# ============================================================================
# Credential / secret store management
# ============================================================================

def _credential_exists(module, alias):
    """Check if a credential alias exists in the wallet."""
    wallet_location = module.params["wallet_location"]
    wallet_password = module.params["wallet_password"]

    args = ['secretstore', 'list_credentials',
            '-wallet', wallet_location]
    if wallet_password:
        args.extend(['-pwd', wallet_password])

    try:
        stdout, _stderr = _run_orapki(module, args)
    except SystemExit:
        return False

    aliases = _parse_list_credentials(stdout)
    return alias in aliases


def _manage_credential(module):
    """Create, modify, or delete credentials/entries."""
    credential_state = module.params["credential_state"]
    credential_type = module.params["credential_type"]
    credential_alias = module.params["credential_alias"]
    wallet_location = module.params["wallet_location"]
    wallet_password = module.params["wallet_password"]

    exists = _credential_exists(module, credential_alias)

    if credential_state == 'present':
        return _upsert_credential(module, exists)

    if credential_state == 'absent':
        if not exists:
            return False
        if module.check_mode:
            return True
        subcmd = 'delete_credential' if credential_type == 'credential' else 'delete_entry'
        args = ['secretstore', subcmd,
                '-wallet', wallet_location,
                '-alias', credential_alias]
        if wallet_password:
            args.extend(['-pwd', wallet_password])
        _run_orapki(module, args)
        return True

    return False


def _upsert_credential(module, exists):
    """Create or modify a credential/entry."""
    credential_type = module.params["credential_type"]
    credential_alias = module.params["credential_alias"]
    wallet_location = module.params["wallet_location"]
    wallet_password = module.params["wallet_password"]
    if module.check_mode:
        return True

    if credential_type == 'credential':
        credential_db = module.params["credential_db"]
        credential_user = module.params["credential_user"]
        credential_password = module.params["credential_password"]

        if exists:
            args = ['secretstore', 'modify_credential',
                    '-wallet', wallet_location,
                    '-alias', credential_alias]
            if credential_user:
                args.extend(['-user', credential_user])
            if credential_password:
                args.extend(['-pwd', credential_password])
        else:
            if not credential_db:
                module.fail_json(
                    msg='credential_db is required to create a credential',
                    changed=False,
                )
            args = ['secretstore', 'create_credential',
                    '-wallet', wallet_location,
                    '-alias', credential_alias,
                    '-db', credential_db]
            if credential_user:
                args.extend(['-user', credential_user])
            if credential_password:
                args.extend(['-pwd', credential_password])
        _run_orapki(module, args)
        return True

    if credential_type == 'entry':
        credential_secret = module.params["credential_secret"]
        if not credential_secret:
            module.fail_json(
                msg='credential_secret is required for entry type',
                changed=False,
            )

        if exists:
            subcmd = 'modify_entry'
        else:
            subcmd = 'create_entry'

        args = ['secretstore', subcmd,
                '-wallet', wallet_location,
                '-alias', credential_alias,
                '-secret', credential_secret]
        if wallet_password:
            args.extend(['-pwd', wallet_password])
        _run_orapki(module, args)
        return True

    return False


# ============================================================================
# Main dispatch
# ============================================================================

def _handle_wallet(module):
    """Handle wallet lifecycle operations."""
    state = module.params["state"]
    change_password_flag = module.params["change_password"]

    if state == 'status':
        result = _wallet_display(module)
        module.exit_json(changed=False, **result)

    elif state == 'present':
        changed = _ensure_wallet_present(module)
        if change_password_flag:
            _change_wallet_password(module)
            changed = True
        module.exit_json(changed=changed, msg='Wallet managed successfully')

    elif state == 'absent':
        changed = _ensure_wallet_absent(module)
        module.exit_json(changed=changed, msg='Wallet removed')


def _handle_certs(module):
    """Handle certificate management operations."""
    changed = _manage_cert(module)
    module.exit_json(changed=changed, msg='Certificate managed successfully')


def _handle_credentials(module):
    """Handle credential/secret store operations."""
    changed = _manage_credential(module)
    module.exit_json(changed=changed, msg='Credential managed successfully')


def main():
    module = AnsibleModule(
        argument_spec=dict(
            oracle_home=dict(required=True, aliases=['oh']),

            state=dict(default='present',
                       choices=['present', 'absent', 'status']),
            wallet_location=dict(required=True, type='path'),
            wallet_password=dict(required=False, no_log=True),
            new_password=dict(required=False, no_log=True),
            change_password=dict(default=False, type='bool'),
            auto_login=dict(default='none',
                           choices=['none', 'auto_login',
                                    'local_auto_login', 'auto_login_only']),

            cert_state=dict(required=False,
                           choices=['present', 'absent', 'exported']),
            cert_type=dict(required=False,
                          choices=['trusted_cert', 'user_cert', 'self_signed']),
            cert_file=dict(required=False, type='path'),
            cert_dn=dict(required=False),
            cert_alias=dict(required=False),
            cert_keysize=dict(required=False, type='int', default=2048),
            cert_validity=dict(required=False, type='int', default=3650),
            cert_export_file=dict(required=False, type='path'),

            credential_state=dict(required=False,
                                 choices=['present', 'absent']),
            credential_type=dict(default='credential',
                                choices=['credential', 'entry']),
            credential_alias=dict(required=False),
            credential_db=dict(required=False),
            credential_user=dict(required=False),
            credential_password=dict(required=False, no_log=True),
            credential_secret=dict(required=False, no_log=True),
        ),
        required_if=[
            ('cert_state', 'present', ('cert_type',)),
            ('cert_state', 'exported', ('cert_export_file',)),
            ('credential_state', 'present', ('credential_alias',)),
            ('credential_state', 'absent', ('credential_alias',)),
            ('change_password', True, ('wallet_password', 'new_password')),
        ],
        mutually_exclusive=[
            ('cert_state', 'credential_state'),
        ],
        supports_check_mode=True,
    )

    credential_state = module.params["credential_state"]
    cert_state = module.params["cert_state"]

    if credential_state:
        _handle_credentials(module)
    elif cert_state:
        _handle_certs(module)
    else:
        _handle_wallet(module)


from ansible.module_utils.basic import *  # noqa: F403

if __name__ == '__main__':
    main()
