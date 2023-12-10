oracle_asm_disks_ec2
====================

This role prepares partitions on disks to be members of Oracle ASM disk group.
Also installs Oracle ASM specific udev rules.

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

ASM Disks have names: /dev/nvme2 - /dev/nvme9
See: `udevasm.sh`

Role Variables
--------------

NONE

Dependencies
------------

NONE

Example Playbook
----------------

This role is included from other roles.

License
-------

BSD

Author Information
------------------

Ivan Brezina

