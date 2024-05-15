#!/usr/bin/env python3

import os
import argparse


def t_hash(password, salt=""):
    """
     Based on
     https://www.trustwave.com/en-us/resources/blogs/spiderlabs-blog/changes-in-oracle-database-12c-password-hashes/
     T: style hash
    """
    import pbkdf2
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
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='pwhash',
        description='Generate Oracle password hash from plantext password',
        epilog="Use this hash for SQL: ALTER USER ... IDENTIFIED BY VALUES '...' ")

    parser.add_argument('-w', '--password', required=True)
    args = parser.parse_args()

    main(os.path.abspath(args.directory))
