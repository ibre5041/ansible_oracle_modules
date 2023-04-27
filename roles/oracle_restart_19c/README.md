Role Name
=========

This role installs Oracle restart.
It also prepares OS configuration for Oracle ASM.

Requirements
------------

Assume you have EC2 server with several nvme disks.
/dev/nvme2
/dev/nvme2n1
/dev/nvme3
/dev/nvme3n1
/dev/nvme4
/dev/nvme4n1
...

This playbook then create partitions on these disks and installs udev rules to make them accessible to oracle os user.
/etc/udev/rules.d/55-usm.rules
/etc/udev/rules.d/12-dm-permissions.rules
/etc/udev/rules.d/10-scsi-asm.rules
/etc/udev/udevasm.sh

Role Variables
--------------

See `roles/default_vars_only/defaults/main.yml`
 - oracle_install_dir_root: /oracle/u01
 - oracle_install_dir_temp: "{{ oracle_install_dir_root}}/tmp"
 - oracle_install_dir_base: "{{ oracle_install_dir_root}}/base"
 - oracle_install_dir_prod: "{{ oracle_install_dir_root}}/product"
 - oracle_inventory_location: "{{ oracle_install_dir_root}}/oraInventory"
 - oracle_os_user, oracle_os_uid, oracle_os_group, oracle_os_groups

Also:
 - oracle_gi_media: name of golden image file
 - oracle_url_base: HTTP(S) base URL to download install image from

 - oracle_release: one of 18c, 19c, 21c, is used as a key in oracle_install_space

Dependencies
------------

You should run base_oracle_ec2 role before.

Example Playbook
----------------

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

    - hosts: all
      collections:
        - ibre5041.ansible_oracle_modules
      become: yes
      become_user: root
      become_method: sudo

    - role: oracle_restart_19c
      oracle_gi_media: "grid_home_2022_Oct.zip"
      oracle_url_base: "http://imageserver/oracle/"
      oracle_release: 19c
      tags: [ oraclerestart ]

License
-------

BSD

Author Information
------------------

Ivan Brezina

