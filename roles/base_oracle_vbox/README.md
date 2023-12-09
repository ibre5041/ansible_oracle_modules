Role Name
=========

This role pre-configures VirtualBox host for Oracle Installation

Requirements
------------

VM should have at least 8GB RAM and free space for Oracle binaries.
Prepare two VMs according this [article](https://balazspapp.wordpress.com/2020/04/05/installing-oracle-19c-rac-on-virtualbox-silent-installation-part-1/).

- Install necessary packages

        yum install -y bind-utils net-tools dnsmasq
        cp /etc/resolv.conf /etc/dnsmasq-resolv.conf
        sed -i -e 's:#resolv-file=.*:resolv-file=/etc/dnsmasq-resolv.conf:g' /etc/dnsmasq.conf
        systemctl start dnsmasq
        systemctl enable dnsmasq

- Prepare IP address plan, configure these IPs on nodes, add this into /etc/hosts on both servers and on client too. Use nmtui, also set DNS server to 127.0.0.1

        192.168.8.101    rac1.vbox      rac1       # public address of the first node(enp0s3)
        192.168.8.102    rac2.vbox      rac2       # public address of the second node
        192.168.8.103    rac1-vip.vbox  rac1-vip   # virtual address of the first node
        192.168.8.104    rac2-vip.vbox  rac2-vip   # virtual address of the second node
        192.168.8.105    rac-scan.vbox  rac-scan   # SCAN address of the cluster
        192.168.8.106    rac-scan.vbox  rac-scan   # SCAN address of the cluster
        192.168.8.107    rac-scan.vbox  rac-scan   # SCAN address of the cluster
        10.0.1.101       rac1-priv.vbox rac1-priv  # private address of the first node(enp0s8)
        10.0.1.102       rac2-priv.vbox rac2-priv  # private address of the second node

- Create two VBox networks:

        cd C:\Program Files\Oracle\VirtualBox
        VBoxManage natnetwork add --netname rac_public --enable --network 172.16.1.0/24
        VBoxManage natnetwork add --netname rac_private --enable --network 10.0.1.0/24

- Next, create & configure(CPUs, storage) the virtual machines:


        VBoxManage createvm --name rac1 --ostype Oracle_64 --register --groups "/rac" --basefolder "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs"
        Virtual machine 'rac1' is created and registered.
        UUID: e69baac6-a0b4-4e7e-8ce7-ff3ada7879f1
        Settings file: 'C:\Users\balaz\VirtualBox VMs\rac\rac1\rac1.vbox'
 
        VBoxManage createvm --name rac2 --ostype Oracle_64 --register --groups "/rac" --basefolder "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs"
 
        Virtual machine 'rac2' is created and registered.
        UUID: b7a000cd-f92e-45aa-ae01-ceac567f2549
        Settings file: 'C:\Users\...\VirtualBox VMs\rac\rac2\rac2.vbox'

        VboxManage modifyvm rac1 --cpus 2 --memory 10240 --nic1 natnetwork --nat-network1 rac_public --nic2 natnetwork --nat-network2 rac_private
        VboxManage modifyvm rac1 --cpus 2 --memory 10240 --nic1 natnetwork --nat-network1 rac_public --nic2 natnetwork --nat-network2 rac_private

        VBoxManage storagectl rac1 --name sata --add sata
        VBoxManage storagectl rac2 --name sata --add sata    
        VBoxManage storagectl rac1 --name datacrtl --add pcie
        VBoxManage storagectl rac2 --name datacrtl --add pcie

        VBoxManage createmedium --filename "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs\rac\rac1\rac1.vdi" --size 102400 --variant Standard

        0%...10%...20%...30%...40%...50%...60%...70%...80%...90%...100%
        Medium created. UUID: dd7c41bc-c21c-463d-b04e-9fa5be294fbd

        VBoxManage createmedium --filename "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs\rac\rac2\rac2.vdi" --size 102400 --variant Standard

        0%...10%...20%...30%...40%...50%...60%...70%...80%...90%...100%
        Medium created. UUID: d0fbfeaf-58f0-41d2-83f9-f2d492339fb0

        VBoxManage storageattach rac1 --storagectl datacrtl --port 0 --type hdd --medium "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs\rac\rac1\rac1.vdi"
        VBoxManage storageattach rac2 --storagectl datacrtl --port 0 --type hdd --medium "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs\rac\rac2\rac2.vdi"
        VBoxManage storageattach rac1 --storagectl datacrtl --port 1 --type dvddrive --medium emptydrive
        VBoxManage storageattach rac2 --storagectl datacrtl --port 1 --type dvddrive --medium emptydrive

- Install base minimal OS

- Configure VBOX drivers
- Mount VBOX drivers iso


        VboxManage storageattach rac1 --storagectl sata --port 1 --medium additions
        VboxManage storageattach rac2 --storagectl sata --port 1 --medium additions

- Install drivers(on both nodes)

        # yum install tar gzip net-tools bind-utils gcc bzip2 libX11 libXt libXext libXmu kernel-uek-devel
        # yum install epel-release
        # yum install dkms

        # mount /dev/cdrom /mnt/
        mount: /dev/sr0 is write-protected, mounting read-only
        # /mnt/VBoxLinuxAdditions.run --nox11
        Verifying archive integrity... All good.
        Uncompressing VirtualBox 6.1.4 Guest Additions for Linux........
        VirtualBox Guest Additions installer
        Copying additional installer modules ...
        Installing additional modules ...
        VirtualBox Guest Additions: Starting.
        VirtualBox Guest Additions: Building the VirtualBox Guest Additions kernel
        VirtualBox Guest Additions: To build modules for other installed kernels, run
        modules.  This may take a while.
        VirtualBox Guest Additions:   /sbin/rcvboxadd quicksetup <version>
        VirtualBox Guest Additions: or
        VirtualBox Guest Additions:   /sbin/rcvboxadd quicksetup all
        VirtualBox Guest Additions: Building the modules for kernel 4.14.35-1902.300.11.el7uek.x86_64.
        # umount /mnt
        # echo "blacklist vboxvideo" >> /etc/modprobe.d/local-dontload.conf
        # echo "install vboxvideo /bin/false" >> /etc/modprobe.d/local-dontload.conf
        # dracut --omit-drivers vboxvideo -f

- Add shared data disks

        VboxManage createmedium disk --filename "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs\rac\rac_DATA1.vdi" --format VDI --variant Fixed --size 10240
        VboxManage createmedium disk --filename "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs\rac\rac_DATA2.vdi" --format VDI --variant Fixed --size 10240

        VBoxManage modifymedium disk "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs\rac\rac_DATA1.vdi" --type shareable
        VBoxManage modifymedium disk "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs\rac\rac_DATA2.vdi" --type shareable
        VboxManage storageattach rac1 --storagectl rac1 --port 2 --type hdd --medium "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs\rac\rac_DATA1.vdi"
        VboxManage storageattach rac1 --storagectl rac1 --port 3 --type hdd --medium "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs\rac\rac_DATA2.vdi"
        VboxManage storageattach rac2 --storagectl rac2 --port 2 --type hdd --medium "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs\rac\rac_DATA1.vdi"
        VboxManage storageattach rac2 --storagectl rac2 --port 3 --type hdd --medium "%HOMEDRIVE%%HOMEPATH%\VirtualBox VMs\rac\rac_DATA2.vdi"

- Attach Oracle binaries to VMs

        VboxManage sharedfolder add rac1 --name install --hostpath I:\Oracle
        VboxManage sharedfolder add rac2 --name install --hostpath I:\Oracle

        mkdir /install
        mount -t vboxsf install /install

- Share Downloaded images

        VboxManage sharedfolder add rac1 --name Downloads --hostpath "%HOMEDRIVE%%HOMEPATH%\Downloads"
        add this into /etc/fstab
        Downloads /install     vboxsf rw,nodev,relatime,iocharset=utf8,uid=0,dmode=0775,fmode=0644 0 0

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

 - `oracle_create_vg: false`
 - `oracle_vg: vg01`
 - `oracle_create_swap: false`
 - `oracle_create_fs: false`

These variables determine whether separate VG should be created for Oracle binaries.
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
        - { role: ibre5041.ansible_oracle_modules.base_oracle_vbox, oracle_vg: vg02, oracle_create_vg: false, oracle_create_swap: false }      

      roles:
        - role: ibre5041.ansible_oracle_modules.base_oracle_vbox
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

