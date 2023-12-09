Role Name
=========

Setup OS for Oracle RAC installation.

Requirements
------------

VMware, on-premise and VBOX HW is supported.

Role Variables
--------------

Variables for this role are defined in `default_vars_only`

Dependencies
------------

You should run `base_oracle_...` role before this role.

Example Playbook
----------------

        - hosts: all
          collections:
            - ibre5041.ansible_oracle_modules
          become: yes
          become_user: root
          become_method: sudo
        
          any_errors_fatal: true
          roles:
          - role: default_vars_only
        
          - role: base_oracle_vmware
            tags: [ base, baseoracle ]
            when: is_vmware_environment
        
          - role: base_oracle_vbox
            tags: [ base, baseoracle ]
            when: is_vbox_environment
        
          - role: oracle_crs_19c
            tags: [ oracle, oraclecrs ]

License
-------

BSD

Author Information
------------------

Ivan Brezina

