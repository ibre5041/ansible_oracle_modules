#!/usr/bin/env python3

import argparse
import string
import hashlib
import sys
from binascii import unhexlify
from random import randbytes
import secrets

def t_hash(password, salt):
    """
     Based on
     https://www.trustwave.com/en-us/resources/blogs/spiderlabs-blog/changes-in-oracle-database-12c-password-hashes/
     T: style hash
    """
    import pbkdf2
    AUTH_VFR_DATA = secrets.token_bytes(16)
    if salt and len(salt) == 32:
        AUTH_VFR_DATA = unhexlify(salt)
    # # alter user abc1 identified by values 'T:1420C5A7597BCF0411C5BFAF364DB0E89A9CA18862AF6D7BADDE20F36A4C4C12A84418B2789C6F9718A5C820403889077040B99B8412344B0ECE782B8030BEBFD6F263E73560779D9D21DF7050EB1EF5';
    # h = 'B3A79BAF933DFCA8BEC114436A93153248952BFF276F51A58B5C87AA14CC7A2E2D7C5CBE2238A7A6EA3D831B57C1A1598CDE3FE3271644335D05F8529769F9141C4C81E69EEC007DCD54E5AF4CE63942'
    # AUTH_VFR_DATA = h[128:160]
    # AUTH_VFR_DATA = unhexlify(AUTH_VFR_DATA)

    # 1st PBKDF2 hash
    salt_ext = AUTH_VFR_DATA + b'AUTH_PBKDF2_SPEEDY_KEY'
    key = pbkdf2.PBKDF2(password, salt_ext, 4096, hashlib.sha512)  # Password used
    key_64bytes = key.read(64)
    # 2nd SHA512 hash
    hash = hashlib.sha512()
    hash.update(key_64bytes)
    hash.update(AUTH_VFR_DATA)
    hash_string = 'T:{}{}'.format(hash.hexdigest().upper(), AUTH_VFR_DATA.hex().upper())
    return hash_string

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='pwhash',
        description='Generate Oracle password hash from plantext password',
        epilog="Use this hash for SQL: ALTER USER ... IDENTIFIED BY VALUES '...' ")

    parser.add_argument('-w', '--password', required=True)
    parser.add_argument('-s', '--salt', required=False)
    args = parser.parse_args()
    h = t_hash(args.password, args.salt)
    print("alter user abc1 identified by values '{}';".format(h))



