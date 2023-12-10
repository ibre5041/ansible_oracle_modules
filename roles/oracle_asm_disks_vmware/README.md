oracle_asm_disks_vmware
=======================

This role prepares partitions on disks to be members of Oracle ASM disk group.
Also installs Oracle ASM specific udev rules.

Requirements
------------

On VMware data disk should be on a separate 2nd SCSI adapter. See `udevasm.sh` script.

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

