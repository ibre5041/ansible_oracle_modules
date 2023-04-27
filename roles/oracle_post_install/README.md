Role Name
=========

This installs ~oracle/.bash_profile and other utility scripts.

Requirements
------------


Role Variables
--------------


Dependencies
------------


Example Playbook
----------------

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

    - hosts: oracle
      collections:
        - ibre5041.ansible_oracle_modules
      become: yes
      become_user: root
      become_method: sudo
    
      roles:
         - role: oracle_post_install
           tags: [ oraclepost ]


License
-------

BSD

Author Information
------------------

Ivan Brezina

