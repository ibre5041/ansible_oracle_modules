Role Name
=========

This role pre-configures EC2 host for Oracle Installation

Requirements
------------

VM should have at least 8GB RAM and one unallocated disk for Oracle binaries.

Role Variables
--------------

All roles include dummy "default_vars_only". See `roles/default_vars_only/defaults/main.yml` first.
Variables imported from default_vars_only role:

 - oracle_install_dir_root: /oracle/u01
 - oracle_install_dir_temp: "{{ oracle_install_dir_root}}/tmp"
 - oracle_install_dir_base: "{{ oracle_install_dir_root}}/base"
 - oracle_install_dir_prod: "{{ oracle_install_dir_root}}/product"
 - oracle_inventory_location: "{{ oracle_install_dir_root}}/oraInventory"
 - oracle_os_user, oracle_os_uid, oracle_os_group, oracle_os_groups
 - ... and other or related

Variables defined in this role:

 - oracle_create_vg: true
 - oracle_vg: vg01 
 - oracle_create_swap: true
 - oracle_create_fs: true

These varibles determine whether separate VG should be created for Oracle binaries.
Whether mount point and directory structure should be created by this role.


Dependencies
------------

This role depends only on `default_vars_only`.

Example Playbook
----------------

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

    - hosts: servers
      collections:
        - ibre5041.ansible_oracle_modules
      become: yes
      become_user: root
      become_method: sudo
    
      roles:
        - { role: ibre5041.ansible_oracle_modules.base_oracle_ec2, oracle_vg: vg02, oracle_create_vg: false, oracle_create_swap: false }      

      roles:
        - role: ibre5041.ansible_oracle_modules.base_oracle_ec2
	    - oracle_vg: vg02
	    - oracle_create_vg: false
	    - oracle_create_swap: false	    
          tags: [ baseoracle]

License
-------

BSD

Author Information
------------------

Ivan Brezina

