#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_user
short_description: Manage users/schemas in an Oracle database
description:
  - Manage users/schemas in an Oracle database
  - Can be run locally on the control machine or on a remote host
  - See connection parameters for oracle_ping 
version_added: "3.0.0"
options:
  schema:
    description: The schema that you want to manage
    required: false
    default: None
  schema_password:
    description: The password for the new schema. i.e '..identified by password'
    required: false
    default: null
  schema_password_hash:
    description: The password hash for the new schema. i.e '..identified by values "XXXXXXX"'
    required: false
    default: None
  default_tablespace:
    description: The default tablespace for the new schema. The tablespace must exist
    required: false
    default: None
  default_temp_tablespace:
    description: The default tablespace for the new schema. The tablespace must exist
    required: false
    default: None
  authentication_type:
    description: The type of authentication for the user
    required: false
    default: password
    choices: ['password', 'external', 'global', 'none']
  profile:
    description: The profile for the user
    required: false
    default: None
  state:
    description: Whether the user should exist. Absent removes the user (cascade)
    required: False
    default: present
    choices: ['present','absent']
  expired:
    description:
      - Expire password
      - If not specified for a new user, Oracle default will be used.
    required: false
    type: bool
  locked:
    description:
      - Lock or unlock account.
      - If not specified for a new user, Oracle default will be used.
    required: false
    type: bool  
notes:
  - cx_Oracle needs to be installed
  - optionaly depends on pbkdf2 to validate password hashes in PBKDF2 format
requirements:
  - "cx_Oracle"
  - pbkdf2
author:
  - Mikael Sandström, oravirt@gmail.com, @oravirt
  - Ivan Brezina
'''

EXAMPLES = '''

- name: create user sample_user
  oracle_user:
    mode: sysdba
    schema: sample_user
    state: present
    profile: app_profile
    #schema_password_hash: 'T:BC3BF4B95DBAE1A9B6E633FB90FDB2351ACEFE5871A990806F565AD756D4C5C2312B4D2306A34C5BD0588E49F8AB8F0CBFF0DBE427B373B3E3BFE374904B6E01E2EC5166823A917227492E58556AE1D5'
    schema_password: Xiejfkljfssgdhd123
    default_tablespace: users

- name: create user scott
  oracle_user:
    mode: sysdba
    schema: scott
    state: present
    schema_password_hash: "{{'tiger' | ibre5041.ansible_oracle_modules.pwhash12c }}"
    default_tablespace: users

- name: Create a new schema on a remote db by running the module on the controlmachine  (i.e: delegate_to: localhost)
  oracle_user: 
    hostname: remote-db-server
    service_name: orcl
    user: system
    password: manager
    schema: myschema
    schema_password: mypass
    default_tablespace: test
    state: present
  delegate_to: localhost
  
- name: Create a new schema on a remote db
  oracle_user:
    mode: sysdba
    schema: myschema
    schema_password: mypass
    default_tablespace: test
    state: present
  environment:
    ORACLE_HOME: "{{ oracle_home }}"
    ORACLE_SID: "{{ oracle_sid }}"

- name: Change users default_tablespace
  oracle_user:
    mode: sysdba
    schema: mypass
    default_tablespace: USERS
    
- name: Drop a schema
  oracle_user:
    mode: sysdba
    schema: myschema
    state: absent
'''


import hashlib
import string
from binascii import unhexlify


# Check if the user/schema exists
def check_user_exists(conn, schema):
    """Check user exists, return user's attributes"""
    sql = """
    select username
        , account_status
        , default_tablespace
        , temporary_tablespace
        , profile
        , authentication_type
        , oracle_maintained
    from dba_users
    where username = upper(:schema_name)"""

    r = conn.execute_select_to_dict(sql, {"schema_name": schema}, fetchone=True)
    if r:
        acs = r['account_status']
        if acs == 'EXPIRED & LOCKED':
            r['account_status'] = 'LOCKED'
            r['password_status'] = 'EXPIRED'
        elif acs == 'EXPIRED':
            r['account_status'] = 'OPEN'
            r['password_status'] = 'EXPIRED'
        elif acs == 'LOCKED':
            r['account_status'] = 'LOCKED'
            r['password_status'] = 'UNEXPIRED'
        elif acs == 'OPEN':
            r['account_status'] = 'OPEN'
            r['password_status'] = 'UNEXPIRED'
        else:
            conn.fail_json(msg="Unsupported account state %s" % acs, ddls=conn.ddls, changed=conn.changed)

    return set(r.items())


# Create the user/schema
def create_user(conn, module):
    schema = module.params["schema"]
    schema_password = module.params["schema_password"]
    schema_password_hash = module.params["schema_password_hash"]
    default_tablespace = module.params["default_tablespace"]
    default_temp_tablespace = module.params["default_temp_tablespace"]
    profile = module.params["profile"]
    authentication_type = module.params["authentication_type"]
    container = module.params["container"]
    container_data = module.params["container_data"]

    if authentication_type is None and (schema_password_hash or schema_password):
        # Override authentication_type when password provided
        authentication_type = 'password'
    elif authentication_type is None and not schema_password_hash and not schema_password:
        authentication_type = 'none'

    if not schema_password and not schema_password_hash and authentication_type == 'password':
        msg = 'Error: Missing schema password or password hash'
        module.fail_json(msg=msg, Changed=False)

    if authentication_type == 'password':
        if schema_password_hash:
            sql = '''create user %s identified by values '%s' ''' % (schema, schema_password_hash)
        else:
            sql = '''create user %s identified by "%s" ''' % (schema, schema_password)
    elif authentication_type == 'global':
        sql = 'create user %s identified globally ' % schema
    elif authentication_type == 'external':
        sql = 'create user %s identified externally ' % schema
    elif authentication_type == 'none':
        sql = 'create user %s no authentication ' % schema

    if default_tablespace:
        sql += 'default tablespace %s ' % default_tablespace
        sql += 'quota unlimited on %s ' % default_tablespace

    if default_temp_tablespace:
        sql += 'temporary tablespace %s ' % default_temp_tablespace

    if profile:
        sql += ' profile %s' % profile

    if container:
        sql += ' container=%s' % container

    if module.params['locked']:
        sql += ' account lock'

    if module.params['expired']:
        sql += ' password expire'

    conn.execute_ddl(sql)

    if container_data:
        alter_sql = 'alter user %s set container_data=%s container=current' % (schema, container)
        conn.execute_ddl(module, alter_sql)

    msg = 'The schema %s has been created successfully' % schema
    module.exit_json(msg=msg, changed=conn.changed, ddls=conn.ddls)


# Get the current password hash for the user
def get_user_password_hash(conn, schema):
    sql = "select spare4 from sys.user$ where name = upper(:schema_name)"
    r = conn.execute_select_to_dict(sql, {"schema_name": schema}, fetchone=True, fail_on_error=False)
    return r['spare4'] if 'spare4' in r and r['spare4'] else ''


# Check plaintext password against retrieved hash
# currently works with S:/T: hashes only, returns false otherwise
def password_matches_hash(password, password_hash):
    # Based on OPITZ commit 4056d76c67cf4f3da75011fcdcc52c458f410a56
    # S: style hash
    if 'S:' in password_hash:
        h = password_hash.split('S:')[1][:60]
        if not set(h).issubset(string.hexdigits) or len(h) % 2 != 0:
            return False  # not a valid hex string character found, should not happen
        h_sh = password_hash.split('S:')[1][:40]
        salt = password_hash.split('S:')[1][40:60]
        sha1 = hashlib.sha1()
        sha1.update(password.encode('utf-8'))
        sha1.update(unhexlify(salt))
        return h_sh.upper() == sha1.hexdigest().upper()

    # Based on
    # https://www.trustwave.com/en-us/resources/blogs/spiderlabs-blog/changes-in-oracle-database-12c-password-hashes/
    # T: style hash
    try:
        import pbkdf2
        if 'T:' in password_hash:
            h = password_hash.split('T:')[1][:160]
            if not set(h).issubset(string.hexdigits) or len(h) % 2 != 0:
                return False  # not a valid hex string character found, should not happen

            h_sh = password_hash.split('T:')[1][:128]

            AUTH_VFR_DATA = password_hash.split('T:')[1][128:160].encode('utf-8')
            AUTH_VFR_DATA = unhexlify(AUTH_VFR_DATA)
            salt = AUTH_VFR_DATA + b'AUTH_PBKDF2_SPEEDY_KEY'
            key = pbkdf2.PBKDF2(password, salt, 4096, hashlib.sha512)  # Password
            key_64bytes = key.read(64)

            t = hashlib.sha512()
            t.update(key_64bytes)
            t.update(AUTH_VFR_DATA)
            return h_sh.upper() == t.hexdigest().upper()
    except:
        pass
    # no supported hashes found
    return False


def get_change(change_set, change):
    try:
        return next(v for (a, v) in change_set if a == change)
    except StopIteration:
        return None


# Modify the user/schema
def modify_user(conn, module, user):
    schema = module.params["schema"]
    schema_password = module.params["schema_password"]
    schema_password_hash = module.params["schema_password_hash"]
    authentication_type = module.params["authentication_type"]
    container = module.params["container"]
    container_data = module.params["container_data"]

    sql = 'alter user %s ' % schema

    if authentication_type is None and (schema_password_hash or schema_password):
        # Override authentication_type when password provided
        authentication_type = 'PASSWORD'

    current_set = user
    try:
        old_pw_hash = get_user_password_hash(conn, schema)
    except Exception:
        module.warn("Failed to get password hash for schema %s" % schema)
        old_pw_hash = ''
    wanted_set = set()

    if authentication_type == 'PASSWORD':
        if schema_password_hash and schema_password_hash != old_pw_hash:
            wanted_set.add(('password_hash', schema_password_hash))
        elif schema_password and not password_matches_hash(schema_password, old_pw_hash):
            wanted_set.add(('password', schema_password))
        wanted_set.add(('authentication_type', 'PASSWORD'))
    elif authentication_type == 'external':
        wanted_set.add(('authentication_type', 'IDENTIFIED EXTERNALLY'))
    elif authentication_type == 'global':
        wanted_set.add(('authentication_type', 'IDENTIFIED GLOBALLY'))
    elif authentication_type == 'none':
        wanted_set.add(('authentication_type', 'NONE'))

    if module.params['locked']:
        wanted_set.add(('account_status', 'LOCKED'))
    else:
        wanted_set.add(('account_status', 'OPEN'))

    if module.params['expired']:
        wanted_set.add(('password_status', 'EXPIRED'))
    else:
        wanted_set.add(('password_status', 'UNEXPIRED'))

    if module.params['default_tablespace']:
        wanted_set.add(('default_tablespace', module.params['default_tablespace'].upper()))

    if module.params["default_temp_tablespace"]:
        wanted_set.add(('temporary_tablespace', module.params["default_temp_tablespace"].upper()))

    if module.params['profile']:
        wanted_set.add(('profile', module.params['profile'].upper()))

    changes = wanted_set.difference(current_set)

    authentication_type = get_change(changes, 'authentication_type')
    password_status = get_change(changes, 'password_status')
    schema_password = get_change(changes, 'password')
    schema_password_hash = get_change(changes, 'password_hash')
    if authentication_type == 'PASSWORD' \
            or (password_status and password_status == 'UNEXPIRED') \
            or schema_password \
            or schema_password_hash:
        if schema_password_hash:
            sql += ''' identified by values '%s' ''' % schema_password_hash
        elif schema_password:
            sql += ''' identified by "%s" ''' % schema_password
        else:
            # In this case we have to try to re-set the same password as we do already have
            # Either by entering the same password or by resupplying own computed hash(TODO)
            schema_password = module.params['schema_password']
            schema_password_hash = module.params['schema_password_hash']
            if schema_password_hash:
                sql += ''' identified by "%s" ''' % schema_password_hash
            elif schema_password:
                sql += ''' identified by "%s" ''' % schema_password
            else:
                module.fail_json(msg="Can on un-expire password, without providing password(or hash)", changed=conn.changed, ddls=conn.ddls)
    elif authentication_type == 'IDENTIFIED EXTERNALLY':
        sql += ''' identified externally '''
    elif authentication_type == 'IDENTIFIED GLOBALLY':
        wanted_set.add(('authentication_type', 'IDENTIFIED EXTERNALLY'))
    elif authentication_type == 'global':
        sql += ''' identified globally '''
    elif authentication_type == 'NONE':
        sql += ''' no authentication '''

    account_status = get_change(changes, 'account_status')
    if account_status == 'LOCKED':
        sql += ' account lock'
    elif account_status == 'OPEN':
        sql += ' account unlock'

    if password_status and password_status == 'EXPIRED':
        sql += ' password expire'

    default_tablespace = get_change(changes, 'default_tablespace')
    if default_tablespace:
        sql += ' default tablespace %s' % default_tablespace
        sql += ' quota unlimited on %s ' % default_tablespace

    default_temp_tablespace = get_change(changes, 'temporary_tablespace')
    if default_temp_tablespace:
        sql += ' temporary tablespace %s ' % default_temp_tablespace

    profile = get_change(changes, 'profile')
    if profile:
        sql += ' profile "%s" ' % profile

    if changes:
        conn.execute_ddl(sql)

    if container_data:
        alter_sql = 'alter user %s set container_data=%s container=current' % (schema, container)
        conn.execute_ddl(module, alter_sql)

    # wanted list is subset of current settings, do not do anything
    if not changes and not container_data:
        module.exit_json(msg='The schema (%s) is in the intended state' % schema, changed=conn.changed, ddls=conn.ddls)

    module.exit_json(msg='Successfully altered the user (%s) / %s' % (schema, str(changes)), changed=conn.changed, ddls=conn.ddls)


# Drop the user
def drop_user(conn, module, user):
    schema = module.params["schema"]
    oracle_maintained = next(v for (a, v) in user if a == 'oracle_maintained')
    if oracle_maintained == 'Y':
        msg = 'Trying to drop an internal user: %s. Not allowed' % schema
        module.fail_json(msg=msg, changed=conn.changed, ddls=conn.ddls)

    sql = 'drop user %s cascade' % schema
    conn.execute_ddl(sql)
    module.exit_json(msg='Successfully dropped the user (%s)' % schema, changed=conn.changed, ddls=conn.ddls)


def main():
    msg = ['']
    module = AnsibleModule(
        argument_spec=dict(
            user          = dict(required=False, aliases=['un', 'username']),
            password      = dict(required=False, no_log=True, aliases=['pw']),
            mode          = dict(default='normal', choices=["normal", "sysdba"]),
            hostname      = dict(required=False, default='localhost', aliases=['host']),
            port          = dict(required=False, default=1521, type='int'),
            service_name  = dict(required=False, aliases=['sn']),
            dsn           = dict(required=False, aliases=['datasource_name']),
            oracle_home   = dict(required=False, aliases=['oh']),

            schema        = dict(required=True, type='str', aliases=['name', 'schema_name']),
            schema_password = dict(default=None, no_log=True),
            schema_password_hash = dict(default=None, no_log=True),
            state         = dict(default="present", choices=["present", "absent"]),
            expired       = dict(type='bool', default=None),
            locked        = dict(type='bool', default=None),
            default_tablespace = dict(default=None),
            default_temp_tablespace = dict(default=None, aliases=['temporary_tablespace']),
            profile       = dict(default=None),
            authentication_type = dict(default=None, choices=['password', 'external', 'global', 'none']),
            container     = dict(default=None),
            container_data = dict(default=None)
        ),
        required_together=[['user', 'password']],
        mutually_exclusive=[['schema_password', 'schema_password_hash']],
        supports_check_mode=True,
    )

    schema = module.params["schema"]
    state = module.params["state"]

    oc = oracleConnection(module)

    user = check_user_exists(oc, schema)
    if state not in ['absent']:
        if user:
            modify_user(oc, module, user)
        else:
            create_user(oc, module)

    elif state == 'absent':
        if user:
            drop_user(oc, module, user)
        else:
            module.exit_json(msg="The schema (%s) doesn't exist" % schema, changed=False)

    module.exit_json(msg='Unhandled exit', changed=False)


from ansible.module_utils.basic import *

# In these we do import from local project sub-directory <project-dir>/module_utils
# While this file is placed in <project-dir>/library
# No collections are used
#try:
#    from ansible.module_utils.oracle_utils import oracleConnection
#except:
#    pass

# In these we do import from collections
try:
    from ansible_collections.ibre5041.ansible_oracle_modules.plugins.module_utils.oracle_utils import oracleConnection
except:
    pass


if __name__ == '__main__':
    main()
