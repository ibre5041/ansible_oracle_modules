base_oracle_vmware
==================

This role pre-configures VMWare host for Oracle Installation.

Requirements
------------

VM should have at least 8GB RAM and diskgroup(vg01) for Oracle binaries.
This is how mine VM storage layout looks like.

 - 1st SCSI adapter pciSlotNumber(16) has two disks on it (vg00 Centos/RHEL OS, vg01 oracle binaries)
 - 2nd SCSI adapter pciSlotNumber(32) - contains shared SCSI disks, intended for RAC/HAS data (ASM disk group)
 - In case of RAC cluster, disks on 2nd SCSI are shared

        03:00.0 Serial Attached SCSI controller: VMware PVSCSI SCSI Controller (rev 02)
        1b:00.0 Serial Attached SCSI controller: VMware PVSCSI SCSI Controller (rev 02)

        [root@rac19-b-node-1 ~]# lsblk -a -f
        NAME             FSTYPE      LABEL UUID                                   MOUNTPOINT
        sda
        ├─sda1           ext4              b3eff446-ae7b-4b29-a052-242cdc760595   /boot
        ├─sda2           LVM2_member       2s39vW-RWxm-6cRh-Alwu-r5DF-0Mc8-ODccTs
        │ ├─vg00-lv_root ext4              2cf36159-1446-40dc-b2e1-e53d2f1d47c8   /
        │ ├─vg00-lv_tmp  ext4              3c409959-54ba-47f3-b1fb-fa26e903ba9e   /tmp
        │ └─vg00-lv_var  ext4              5507180e-2471-4b2d-b955-c5bf3d734b81   /var
        └─sda3           swap              c13100bd-b5e9-4199-ac8e-72980fa76e33   [SWAP]
        sdb
        └─sdb1           LVM2_member       z3w15P-gw5b-yrTo-dHmX-lZIL-CKgR-RMULg4
          └─vg01-u01     ext4              af3ee9b8-c97c-46cc-a4fb-d6edc7b95fb6   /oracle
        sdc
        └─sdc1           oracleasm
        sdd
        └─sdd1           oracleasm
        sde
        └─sde1           oracleasm
        sdf
        └─sdf1           oracleasm

        [root@rac19-b-node-1 ~]# lsscsi
        [0:0:0:0]    disk    VMware   Virtual disk     2.0   /dev/sda
        [0:0:1:0]    disk    VMware   Virtual disk     2.0   /dev/sdb
        [1:0:12:0]   disk    VMware   Virtual disk     2.0   /dev/sdc
        [1:0:13:0]   disk    VMware   Virtual disk     2.0   /dev/sdd
        [1:0:14:0]   disk    VMware   Virtual disk     2.0   /dev/sde
        [1:0:15:0]   disk    VMware   Virtual disk     2.0   /dev/sdf

This is how storage is configured in VMware .vmx file

        [root@esx:rac19-b-node-1] grep -i scsi rac19-b-node-1.vmx | sort
        sched.scsi0:0.shares = "normal"
        sched.scsi0:0.throughputCap = "off"
        sched.scsi0:1.shares = "normal"
        sched.scsi0:1.throughputCap = "off"
        scsi0.pciSlotNumber = "160"
        scsi0.present = "TRUE"
        scsi0.sasWWID = "50 05 05 6e d0 eb 5e b0"
        scsi0.virtualDev = "pvscsi"
        scsi0:0.deviceType = "scsi-hardDisk"
        scsi0:0.fileName = "rhel8_template_rootdg.vdmk"
        scsi0:0.present = "TRUE"
        scsi0:0.redo = ""
        scsi0:1.deviceType = "scsi-hardDisk"
        scsi0:1.fileName = "rhel8_template_appdg.vdmk"
        scsi0:1.present = "TRUE"
        scsi0:1.redo = ""
        scsi1.pciSlotNumber = "256"
        scsi1.present = "TRUE"
        scsi1.sasWWID = "50 05 05 6e d0 eb 5f b0"
        scsi1.sharedBus = "virtual"
        scsi1.virtualDev = "pvscsi"
        scsi1:12.deviceType = "scsi-hardDisk"
        scsi1:12.fileName = "eager_data_1_12.vmdk"
        scsi1:12.present = "TRUE"
        scsi1:12.redo = ""
        scsi1:12.sharing = "multi-writer"
        scsi1:12.writeThrough = "TRUE"
        scsi1:13.deviceType = "scsi-hardDisk"
        scsi1:13.fileName = "eager_data_1_13.vmdk"
        scsi1:13.present = "TRUE"
        scsi1:13.redo = ""
        scsi1:13.sharing = "multi-writer"
        scsi1:13.writeThrough = "TRUE"
        scsi1:14.deviceType = "scsi-hardDisk"
        scsi1:14.fileName = "eager_data_1_14.vmdk"
        scsi1:14.present = "TRUE"
        scsi1:14.redo = ""
        scsi1:14.sharing = "multi-writer"
        scsi1:14.writeThrough = "TRUE"
        scsi1:15.deviceType = "scsi-hardDisk"
        scsi1:15.fileName = "eager_data_1_15.vmdk"
        scsi1:15.present = "TRUE"
        scsi1:15.redo = ""
        scsi1:15.sharing = "multi-writer"
        scsi1:15.writeThrough = "TRUE"

This is how networking HW is configured:

- 1st NIC adapter pciSlotNumber(192) is connected to ESXi's Network "Public Network" 192.168.8.0/24
- 2st NIC adapter pciSlotNumber(224) is connected to ESXi's Network "Barn Network" 10.0.0.0/24, this is also interface there DHCP,TFTP listens on. This interface it used foe RAC interconnect

        # lspci
        0b:00.0 Ethernet controller: VMware VMXNET3 Ethernet Controller (rev 01)
        13:00.0 Ethernet controller: VMware VMXNET3 Ethernet Controller (rev 01)

        # ifconfig -a
        ens192: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
                inet 192.168.8.50  netmask 255.255.255.0  broadcast 192.168.8.255
                inet6 fe80::1b51:8df6:ac07:19b1  prefixlen 64  scopeid 0x20<link>
                ether 00:50:56:97:fb:aa  txqueuelen 1000  (Ethernet)
                RX packets 5111  bytes 698425 (682.0 KiB)
                RX errors 0  dropped 33  overruns 0  frame 0
                TX packets 3957  bytes 456165 (445.4 KiB)
                TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0
        
        ens224: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
                inet 10.0.0.50  netmask 255.255.255.0  broadcast 10.0.0.255
                inet6 fe80::db1:d305:828d:41f  prefixlen 64  scopeid 0x20<link>
                ether 00:50:56:97:9b:8f  txqueuelen 1000  (Ethernet)
                RX packets 45181  bytes 37955904 (36.1 MiB)
                RX errors 0  dropped 30  overruns 0  frame 0
                TX packets 51143  bytes 90955318 (86.7 MiB)
                TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

This is how networking is configured in VMware .vmx file

        [root@esx:rac19-b-node-1] grep -i ethernet rac19-b-node-1.vmx | sort
        ethernet0.addressType = "vpx"
        ethernet0.generatedAddress = "00:50:56:97:fb:aa"
        ethernet0.networkName = "Public Network"
        ethernet0.pciSlotNumber = "192"
        ethernet0.present = "TRUE"
        ethernet0.uptCompatibility = "TRUE"
        ethernet0.virtualDev = "vmxnet3"
        ethernet1.addressType = "vpx"
        ethernet1.generatedAddress = "00:50:56:97:9b:8f"
        ethernet1.networkName = "Barn Network"
        ethernet1.pciSlotNumber = "224"
        ethernet1.present = "TRUE"
        ethernet1.uptCompatibility = "TRUE"
        ethernet1.virtualDev = "vmxnet3"

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

 - `oracle_vg: vg01` 
 - `oracle_create_swap: True`
 - `oracle_create_fs: True`

These variables determine whether separate VG should be created for Oracle binaries.
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
  - Create swap device
  - Create FS for Oracle binaries

        - hosts: servers
          collections:
            - ibre5041.ansible_oracle_modules
          become: yes
          become_user: root
          become_method: sudo
        
          roles:
            - role: ibre5041.ansible_oracle_modules.base_oracle_vmware
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

