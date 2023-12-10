base_oracle_ec2
===============

This role pre-configures EC2 host for Oracle Installation

Requirements
------------

VM should have at least 8GB RAM and one unallocated disk(`/dev/nvme1n1`) for Oracle binaries.

Role Variables
--------------

All roles include dummy "default_vars_only". See `roles/default_vars_only/defaults/main.yml` first.
Variables imported from default_vars_only role:

 - `oracle_install_dir_root: /oracle/u01`
 - `oracle_install_dir_temp: "{{ oracle_install_dir_root}}/tmp"`
 - `oracle_install_dir_base: "{{ oracle_install_dir_root}}/base"`
 - `oracle_install_dir_prod: "{{ oracle_install_dir_root}}/product"`
 - `oracle_inventory_location: "{{ oracle_install_dir_root}}/oraInventory"`
 - `oracle_os_user, oracle_os_uid, oracle_os_group, oracle_os_groups`
 - ... and other or related

Variables defined in this role:

 - `oracle_create_vg: True`
 - `oracle_vg: vg01`
 - `oracle_create_swap: True`
 - `oracle_create_fs: True`

These varibles determine whether separate VG should be created for Oracle binaries.
Whether mount point and directory structure should be created by this role.


Dependencies
------------

This role depends only on `default_vars_only`.

Example Playbook
----------------

This playbook will:
  - Configure kernel parameters `/etc/sysctl.d/98-oracle.conf`
  - Install tuned.conf Oracle profile
  - Install necessary .rpm packages
  - Create OS groups and oracle user
  - Install security limits for oracle user `/etc/security/limits.d/99-oracle-limits.conf`
  - Create diskgroup vg01 on disk `/dev/nvme1n1` for Oracle binaries
  - Create swap device
  - Create FS for Oracle binaries

        - hosts: servers
          collections:
            - ibre5041.ansible_oracle_modules
          become: yes
          become_user: root
          become_method: sudo
        
          roles:
            - role: ibre5041.ansible_oracle_modules.base_oracle_ec2
    	      oracle_vg: vg01
    	      oracle_create_vg: True
    	      oracle_create_swap: True
            tags: [ baseoracle]

License
-------

BSD

Author Information
------------------

Ivan Brezina
