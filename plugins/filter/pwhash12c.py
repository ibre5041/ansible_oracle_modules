# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = '''
name: pwhash12c
short_description: Compute hash of Oracle password
version_added: 3.2.2
author:
  - Ivan Brezina
description:
  - Uses PBKDF2 hash function to compute passord hash in latest format
options:
  _input:
    description:
      - Password in plaintext format 
    type: string
    required: true
'''

EXAMPLES = '''
- name: reset users password
  ansible.builtin.debug:
    msg: "alter user scott identified by values '{{ 'tigger' | pwhash12c }}';"
'''

RETURN = '''
  _value:
    description:
      - "Oracle 12c password hash starting with T:"
    type: string
'''

from ansible.errors import AnsibleFilterError
from ansible.module_utils.six import string_types
from ansible.module_utils.common.text.converters import to_bytes, to_native

import string
import hashlib
import sys
from binascii import unhexlify
from random import randbytes
import secrets
import pbkdf2

from ansible_collections.community.crypto.plugins.plugin_utils.filter_module import FilterModuleMock

def pwhash12c(password, salt=""):
    """
     Based on
     https://www.trustwave.com/en-us/resources/blogs/spiderlabs-blog/changes-in-oracle-database-12c-password-hashes/
     T: style hash
    """
    if not isinstance(password, string_types):
        raise AnsibleFilterError('The input must be a text type, not %s' % type(data))
    
    AUTH_VFR_DATA = secrets.token_bytes(16)
    if salt and len(salt) == 32:
        AUTH_VFR_DATA = unhexlify(salt)
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

class FilterModule(object):
    '''Ansible jinja2 filters'''

    def filters(self):
        return {
            'pwhash12c': pwhash12c
        }
