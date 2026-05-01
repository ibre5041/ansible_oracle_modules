# Create/Delete/Clone VMs on VMware/VCenter

Although there is support for VCenter in Ansible, this module can not create RAC cluster.
There is missing support to add multiple SCSI adapters, and to add shared disks.

clone.py and delete.py scripts can read either config file in proprietary format or ansible inventory file.
These scripts can also create/delete DNS records for VMs

    $ ./clone.py -h
    usage: clone.py [-h] [-f FILE | -i INVENTORY]
    
    optional arguments:
      -h, --help            show this help message and exit
      -f FILE, --file FILE  Config filename to process in .yaml format
      -i INVENTORY, --inventory INVENTORY
                            Config filename to process in ansible inventory format
    
    Create 2 node RAC cluster on VMware:
    
    $ ./clone.py -i ../inventory/rac19-b.050.inventory.yml
    {
        "scsi": [
            {
                "adapter": {
                    "pciSlotNumber": 16
                }
            },
            {
                "adapter": {
                    "pciSlotNumber": 32
                }
            }
        ],
        "disks": [
            {
                "disk": "rootdg",
                "size": "10g",
                "bus": 0
            },
            {
                "disk": "appdg",
                "size": "100g",
                "bus": 0
            }
        ],
        "network": [
            {
                "adapter": null,
                "pciSlotNumber": 192,
                "network": "Public Network"
            },
            {
                "adapter": null,
                "pciSlotNumber": 224,
                "network": "Barn Network"
            }
        ],
        "ram": "16G",
        "cpu": 2,
        "vmware": {
            "vm_folder": "VmFolder",
            "datastore": "Kingston890G"
        },
        "cluster": {
            "oracle_cluster_name": "rac19c-b",
            "disks": [
                {
                    "disk": {
                        "size": "8G",
                        "bus": 1,
                        "count": 4
                    }
                }
            ],
            "addresses": {
                "rac19-b-lis-1": "192.168.8.53",
                "rac19-b-lis-2": "192.168.8.54",
                "rac19-b-scan": [
                    "192.168.8.57",
                    "192.168.8.58",
                    "192.168.8.59"
                ]
            }
        },
        "oracle_crs_scan": "rac19-b-scan",
        "oracle_password": "Xb6a5ed2ff29f98d",
        "template": "RHEL9Template",
        "oracle_url_base": "http://kicklinux9/oracle/19c/",
        "oracle_gi_image": "LINUX.X64_193000_grid_home.zip",
        "inventory_file": "/root/ansible_oracle_modules_example/inventory/rac19-b.050.inventory.yml",
        "inventory_dir": "/root/ansible_oracle_modules_example/inventory",
        "address": "192.168.8.50",
        "oracle_crs_node_vip": "rac19-b-lis-1",
        "oracle_release": "19c",
        "oracle_install_type": "rac",
        "inventory_hostname": "rac19-b-node-1",
        "inventory_hostname_short": "rac19-b-node-1",
        "group_names": [
            "oracle"
        ],
        "ansible_facts": {},
        "playbook_dir": "/root/ansible_oracle_modules_example/tools",
        "ansible_playbook_python": "/usr/bin/python3",
        "groups": {
            "all": [
                "rac19-b-node-1",
                "rac19-b-node-2"
            ],
            "ungrouped": [],
            "oracle": [
                "rac19-b-node-1",
                "rac19-b-node-2"
            ]
        },
        "omit": "__omit_place_holder__27170210b5f6edc07d856a70e94802f094c9098d",
        "ansible_version": "Unknown"
    }
    2024-01-05 21:03:47,412 - config - DEBUG - _sanitize: rac19-b-node-1 Net adapter 0 IP:192.168.8.50 MAC:[00:50:56:00:00:50]
    2024-01-05 21:03:47,412 - config - DEBUG - _sanitize: rac19-b-node-1 Net adapter 1 IP:192.168.8.50 MAC:[00:50:56:01:00:50]
    2024-01-05 21:03:47,413 - config - DEBUG - createFromInventory: Machine loaded: rac19-b-node-1       CPU: 2  RAM: 16G  Storage: [{'disk': 'rootdg', 'size': '10g', 'bus': 0, 'sizeVSphere': '10g', 'pathVSphere': '[Kingston890G] rac19-b-node-1/rac19_b_node_1_rootdg.vdmk', 'scsiUnit': 0}, {'disk': 'appdg', 'size': '100g', 'bus': 0, 'sizeVSphere': '100g', 'pathVSphere': '[Kingston890G] rac19-b-node-1/rac19_b_node_1_appdg.vdmk', 'scsiUnit': 1}]
    2024-01-05 21:03:47,413 - config - DEBUG - createFromInventory: {'oracle_cluster_name': 'rac19c-b', 'disks': [{'disk': {'size': '8G', 'bus': 1, 'count': 4}}], 'addresses': {'rac19-b-lis-1': '192.168.8.53', 'rac19-b-lis-2': '192.168.8.54', 'rac19-b-scan': ['192.168.8.57', '192.168.8.58', '192.168.8.59']}}
    {
        "scsi": [
            {
                "adapter": {
                    "pciSlotNumber": 16
                }
            },
            {
                "adapter": {
                    "pciSlotNumber": 32
                }
            }
        ],
        "disks": [
            {
                "disk": "rootdg",
                "size": "10g",
                "bus": 0,
                "sizeVSphere": "10g",
                "pathVSphere": "[Kingston890G] rac19-b-node-1/rac19_b_node_1_rootdg.vdmk",
                "scsiUnit": 0
            },
            {
                "disk": "appdg",
                "size": "100g",
                "bus": 0,
                "sizeVSphere": "100g",
                "pathVSphere": "[Kingston890G] rac19-b-node-1/rac19_b_node_1_appdg.vdmk",
                "scsiUnit": 1
            }
        ],
        "network": [
            {
                "adapter": null,
                "pciSlotNumber": 192,
                "network": "Public Network",
                "mac": "00:50:56:00:00:50"
            },
            {
                "adapter": null,
                "pciSlotNumber": 224,
                "network": "Barn Network",
                "mac": "00:50:56:01:00:50"
            }
        ],
        "ram": "16G",
        "cpu": 2,
        "vmware": {
            "vm_folder": "VmFolder",
            "datastore": "Kingston890G"
        },
        "cluster": {
            "oracle_cluster_name": "rac19c-b",
            "disks": [
                {
                    "disk": {
                        "size": "8G",
                        "bus": 1,
                        "count": 4
                    }
                }
            ],
            "addresses": {
                "rac19-b-lis-1": "192.168.8.53",
                "rac19-b-lis-2": "192.168.8.54",
                "rac19-b-scan": [
                    "192.168.8.57",
                    "192.168.8.58",
                    "192.168.8.59"
                ]
            }
        },
        "oracle_crs_scan": "rac19-b-scan",
        "oracle_password": "Xb6a5ed2ff29f98d",
        "template": "RHEL9Template",
        "oracle_url_base": "http://kicklinux9/oracle/19c/",
        "oracle_gi_image": "LINUX.X64_193000_grid_home.zip",
        "inventory_file": "/root/ansible_oracle_modules_example/inventory/rac19-b.050.inventory.yml",
        "inventory_dir": "/root/ansible_oracle_modules_example/inventory",
        "address": "192.168.8.51",
        "oracle_crs_node_vip": "rac19-b-lis-2",
        "oracle_release": "19c",
        "oracle_install_type": "rac",
        "inventory_hostname": "rac19-b-node-2",
        "inventory_hostname_short": "rac19-b-node-2",
        "group_names": [
            "oracle"
        ],
        "ansible_facts": {},
        "playbook_dir": "/root/ansible_oracle_modules_example/tools",
        "ansible_playbook_python": "/usr/bin/python3",
        "groups": {
            "all": [
                "rac19-b-node-1",
                "rac19-b-node-2"
            ],
            "ungrouped": [],
            "oracle": [
                "rac19-b-node-1",
                "rac19-b-node-2"
            ]
        },
        "omit": "__omit_place_holder__27170210b5f6edc07d856a70e94802f094c9098d",
        "ansible_version": "Unknown"
    }
    2024-01-05 21:03:47,417 - config - DEBUG - _sanitize: rac19-b-node-2 Net adapter 0 IP:192.168.8.51 MAC:[00:50:56:00:00:51]
    2024-01-05 21:03:47,417 - config - DEBUG - _sanitize: rac19-b-node-2 Net adapter 1 IP:192.168.8.51 MAC:[00:50:56:01:00:51]
    2024-01-05 21:03:47,417 - config - DEBUG - createFromInventory: Machine loaded: rac19-b-node-2       CPU: 2  RAM: 16G  Storage: [{'disk': 'rootdg', 'size': '10g', 'bus': 0, 'sizeVSphere': '10g', 'pathVSphere': '[Kingston890G] rac19-b-node-2/rac19_b_node_2_rootdg.vdmk', 'scsiUnit': 0}, {'disk': 'appdg', 'size': '100g', 'bus': 0, 'sizeVSphere': '100g', 'pathVSphere': '[Kingston890G] rac19-b-node-2/rac19_b_node_2_appdg.vdmk', 'scsiUnit': 1}]
    2024-01-05 21:03:47,418 - config - DEBUG - load: {
        "config": {
            "hostname": "vcenter7.prod.vmware.haf",
            "password": "****",
            "username": "administrator@vsphere.local",
            "validateSSL": false
        }
    }
    2024-01-05 21:03:47,482 - config - DEBUG - validate: rac19-b-node-1 Datastore: Kingston890G True
    2024-01-05 21:03:47,491 - config - DEBUG - validate: rac19-b-node-1 VM Folder: VmFolder     True
    2024-01-05 21:03:47,492 - config - DEBUG - validate: rac19-b-node-1  VM Disk: rootdg       True
    2024-01-05 21:03:47,492 - config - DEBUG - validate: rac19-b-node-1  VM Disk: appdg        True
    2024-01-05 21:03:47,497 - config - DEBUG - validate: rac19-b-node-1  Net Adapter: Public Network True
    2024-01-05 21:03:47,501 - config - DEBUG - validate: rac19-b-node-1  Net Adapter: Barn Network True
    2024-01-05 21:03:47,506 - config - DEBUG - validate: rac19-b-node-2 Datastore: Kingston890G True
    2024-01-05 21:03:47,519 - config - DEBUG - validate: rac19-b-node-2 VM Folder: VmFolder     True
    2024-01-05 21:03:47,519 - config - DEBUG - validate: rac19-b-node-2  VM Disk: rootdg       True
    2024-01-05 21:03:47,519 - config - DEBUG - validate: rac19-b-node-2  VM Disk: appdg        True
    2024-01-05 21:03:47,527 - config - DEBUG - validate: rac19-b-node-2  Net Adapter: Public Network True
    2024-01-05 21:03:47,533 - config - DEBUG - validate: rac19-b-node-2  Net Adapter: Barn Network True
    2024-01-05 21:03:47,533 - clone - DEBUG - dns_for_vm: DNS Record: rac19-b-node-1 (192.168.8.50)
    2024-01-05 21:03:47,533 - utils - DEBUG - create_dns_record: DNS record A
    2024-01-05 21:03:47,533 - utils - DEBUG - create_dns_record:  rac19-b-node-1 (192.168.8.50)
    2024-01-05 21:03:47,539 - utils - DEBUG - create_dns_record:  A   DNS update response: NOERROR QR
    2024-01-05 21:03:47,539 - utils - DEBUG - create_dns_record: DNS record PTR
    2024-01-05 21:03:47,547 - utils - DEBUG - create_dns_record:  PTR DNS update response: NOERROR QR
    2024-01-05 21:03:47,547 - utils - DEBUG - create_dns_record: DNS record A
    2024-01-05 21:03:47,547 - utils - DEBUG - create_dns_record:  rac19-b-node-1 (10.0.0.50)
    2024-01-05 21:03:47,548 - utils - DEBUG - create_dns_record:  A   DNS update response: NOERROR QR
    2024-01-05 21:03:47,548 - utils - DEBUG - create_dns_record: DNS record PTR
    2024-01-05 21:03:47,549 - utils - DEBUG - create_dns_record:  PTR DNS update response: NOERROR QR
    2024-01-05 21:03:47,636 - clone - DEBUG - clone_vm: cloning template RHEL9Template into rac19-b-node-1...
    2024-01-05 21:03:56,720 - clone - DEBUG - clone_vm: rac19-b-node-1 created as clone of RHEL9Template
    2024-01-05 21:03:56,737 - clone - DEBUG - clone_vm: VM CPU: 2
    2024-01-05 21:03:56,737 - clone - DEBUG - clone_vm: VM RAM: 16384
    2024-01-05 21:03:56,903 - clone - DEBUG - clone_vm: Added SCSI adapter: 1 pciSlotNumber: 32
    2024-01-05 21:03:56,976 - clone - DEBUG - clone_vm: rac19-b-node-1 reconfigured
    2024-01-05 21:03:56,990 - clone - DEBUG - clone_vm: Device label: Hard disk 1
    2024-01-05 21:03:56,990 - clone - DEBUG - clone_vm: Device label: Hard disk 1 new disk size: 10240 MB
    2024-01-05 21:03:56,990 - clone - DEBUG - clone_vm: Device label: Hard disk 2
    2024-01-05 21:03:56,990 - clone - DEBUG - clone_vm: Device label: Hard disk 2 new disk size: 102400 MB
    2024-01-05 21:03:57,118 - clone - DEBUG - clone_vm: Net Adapter PCI: 192 assigning new MAC Address: generated
    2024-01-05 21:03:57,126 - clone - DEBUG - clone_vm: Net Adapter PCI: 192 assigning new network: Public Network
    2024-01-05 21:03:57,126 - clone - DEBUG - clone_vm: Net Adapter PCI: 224 assigning new MAC Address: generated
    2024-01-05 21:03:57,132 - clone - DEBUG - clone_vm: Net Adapter PCI: 224 assigning new network: Barn Network
    2024-01-05 21:03:57,737 - clone - DEBUG - clone_vm: rac19-b-node-1 booting...
    2024-01-05 21:03:57,737 - clone - DEBUG - clone_vm: Waiting for vmware tools...
    2024-01-05 21:03:58,760 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:03:59,785 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:00,809 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:01,834 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:02,859 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:03,886 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:04,919 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:05,948 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:06,978 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:08,009 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:09,038 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:10,067 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:11,099 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:12,129 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:13,160 - clone - DEBUG - clone_vm: rac19-b-node-1       guestToolsRunning   /12389                guestToolsUnmanaged           
    2024-01-05 21:04:13,162 - clone - DEBUG - clone_vm: Uploading mncli.sh:
    2024-01-05 21:04:13,253 - connectionpool - DEBUG - _new_conn: Starting new HTTPS connection (1): esxi-1.prod.vmware.haf:443
    2024-01-05 21:04:13,383 - connectionpool - DEBUG - _make_request: https://esxi-1.prod.vmware.haf:443 "PUT /guestFile?id=1017&token=52693445-17eb-9879-b073-8372da6686bc1017 HTTP/1.1" 200 33
    2024-01-05 21:04:15,504 - clone - DEBUG - clone_vm: Command "/root/nmcli.sh" exited with code: 0
    2024-01-05 21:04:15,552 - connectionpool - DEBUG - _new_conn: Starting new HTTPS connection (1): esxi-1.prod.vmware.haf:443
    2024-01-05 21:04:15,620 - connectionpool - DEBUG - _make_request: https://esxi-1.prod.vmware.haf:443 "GET /guestFile?id=1017&token=5284391d-33cb-9f24-96d4-005e1fcc8f4e1017 HTTP/1.1" 200 636
    2024-01-05 21:04:15,622 - clone - DEBUG - clone_vm: Content of /root/nmcli.log:
    2024-01-05 21:04:15,622 - clone - DEBUG - clone_vm:   Connection 'net-prod' (dfc1f4c1-2859-4db7-ab9f-64d6ea6ab780) successfully deleted.
    2024-01-05 21:04:15,622 - clone - DEBUG - clone_vm:   Connection 'net-barn' (6ba49605-0c38-4c78-a0a5-722465d00f57) successfully deleted.
    2024-01-05 21:04:15,622 - clone - DEBUG - clone_vm:   Connection 'lo' (33dd5b88-7b78-479a-a3e5-701273e23ee4) successfully deleted.
    2024-01-05 21:04:15,622 - clone - DEBUG - clone_vm:   Connection 'net-barn' (d736abae-801c-456b-a05c-29abf7a86f08) successfully added.
    2024-01-05 21:04:15,622 - clone - DEBUG - clone_vm:   Connection 'net-prod' (8c6536c1-58c3-487d-8b27-e16f952e5641) successfully added.
    2024-01-05 21:04:15,622 - clone - DEBUG - clone_vm:   STATE   CONNECTIVITY  WIFI-HW  WIFI     WWAN-HW  WWAN    
    2024-01-05 21:04:15,622 - clone - DEBUG - clone_vm:   asleep  none          missing  enabled  missing  enabled 
    2024-01-05 21:04:15,622 - clone - DEBUG - clone_vm:     Physical volume "/dev/sdb1" changed
    2024-01-05 21:04:15,623 - clone - DEBUG - clone_vm:     1 physical volume(s) resized or updated / 0 physical volume(s) not resized
    2024-01-05 21:04:15,623 - clone - DEBUG - dns_for_vm: DNS Record: rac19-b-node-2 (192.168.8.51)
    2024-01-05 21:04:15,623 - utils - DEBUG - create_dns_record: DNS record A
    2024-01-05 21:04:15,623 - utils - DEBUG - create_dns_record:  rac19-b-node-2 (192.168.8.51)
    2024-01-05 21:04:15,680 - utils - DEBUG - create_dns_record:  A   DNS update response: NOERROR QR
    2024-01-05 21:04:15,680 - utils - DEBUG - create_dns_record: DNS record PTR
    2024-01-05 21:04:15,683 - utils - DEBUG - create_dns_record:  PTR DNS update response: NOERROR QR
    2024-01-05 21:04:15,683 - utils - DEBUG - create_dns_record: DNS record A
    2024-01-05 21:04:15,683 - utils - DEBUG - create_dns_record:  rac19-b-node-2 (10.0.0.51)
    2024-01-05 21:04:15,684 - utils - DEBUG - create_dns_record:  A   DNS update response: NOERROR QR
    2024-01-05 21:04:15,684 - utils - DEBUG - create_dns_record: DNS record PTR
    2024-01-05 21:04:15,686 - utils - DEBUG - create_dns_record:  PTR DNS update response: NOERROR QR
    2024-01-05 21:04:15,775 - clone - DEBUG - clone_vm: cloning template RHEL9Template into rac19-b-node-2...
    2024-01-05 21:04:30,743 - clone - DEBUG - clone_vm: rac19-b-node-2 created as clone of RHEL9Template
    2024-01-05 21:04:30,814 - clone - DEBUG - clone_vm: VM CPU: 2
    2024-01-05 21:04:30,814 - clone - DEBUG - clone_vm: VM RAM: 16384
    2024-01-05 21:04:31,002 - clone - DEBUG - clone_vm: Added SCSI adapter: 1 pciSlotNumber: 32
    2024-01-05 21:04:31,101 - clone - DEBUG - clone_vm: rac19-b-node-2 reconfigured
    2024-01-05 21:04:31,112 - clone - DEBUG - clone_vm: Device label: Hard disk 1
    2024-01-05 21:04:31,112 - clone - DEBUG - clone_vm: Device label: Hard disk 1 new disk size: 10240 MB
    2024-01-05 21:04:31,112 - clone - DEBUG - clone_vm: Device label: Hard disk 2
    2024-01-05 21:04:31,112 - clone - DEBUG - clone_vm: Device label: Hard disk 2 new disk size: 102400 MB
    2024-01-05 21:04:31,254 - clone - DEBUG - clone_vm: Net Adapter PCI: 192 assigning new MAC Address: generated
    2024-01-05 21:04:31,263 - clone - DEBUG - clone_vm: Net Adapter PCI: 192 assigning new network: Public Network
    2024-01-05 21:04:31,263 - clone - DEBUG - clone_vm: Net Adapter PCI: 224 assigning new MAC Address: generated
    2024-01-05 21:04:31,270 - clone - DEBUG - clone_vm: Net Adapter PCI: 224 assigning new network: Barn Network
    2024-01-05 21:04:31,931 - clone - DEBUG - clone_vm: rac19-b-node-2 booting...
    2024-01-05 21:04:31,931 - clone - DEBUG - clone_vm: Waiting for vmware tools...
    2024-01-05 21:04:32,969 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:34,009 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:35,052 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:36,092 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:37,132 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:38,177 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:39,214 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:40,264 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:41,302 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:42,354 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:43,391 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:44,436 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:45,477 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:46,522 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsNotRunning/12389                guestToolsUnmanaged           
    2024-01-05 21:04:47,570 - clone - DEBUG - clone_vm: rac19-b-node-2       guestToolsRunning   /12389                guestToolsUnmanaged           
    2024-01-05 21:04:47,572 - clone - DEBUG - clone_vm: Uploading mncli.sh:
    2024-01-05 21:04:47,650 - connectionpool - DEBUG - _new_conn: Starting new HTTPS connection (1): esxi-1.prod.vmware.haf:443
    2024-01-05 21:04:47,748 - connectionpool - DEBUG - _make_request: https://esxi-1.prod.vmware.haf:443 "PUT /guestFile?id=1018&token=52986d91-0d69-a6f3-717d-6ca352b08f1d1018 HTTP/1.1" 200 33
    2024-01-05 21:04:49,857 - clone - DEBUG - clone_vm: Command "/root/nmcli.sh" exited with code: 0
    2024-01-05 21:04:49,904 - connectionpool - DEBUG - _new_conn: Starting new HTTPS connection (1): esxi-1.prod.vmware.haf:443
    2024-01-05 21:04:49,973 - connectionpool - DEBUG - _make_request: https://esxi-1.prod.vmware.haf:443 "GET /guestFile?id=1018&token=5236d189-b06d-ec3d-b101-d789d48e228a1018 HTTP/1.1" 200 636
    2024-01-05 21:04:49,974 - clone - DEBUG - clone_vm: Content of /root/nmcli.log:
    2024-01-05 21:04:49,974 - clone - DEBUG - clone_vm:   Connection 'net-prod' (cdd70758-aaea-42d8-adb0-31f22a90d38c) successfully deleted.
    2024-01-05 21:04:49,974 - clone - DEBUG - clone_vm:   Connection 'net-barn' (caabdbdb-c3a7-4cf2-96d4-6236940d573d) successfully deleted.
    2024-01-05 21:04:49,974 - clone - DEBUG - clone_vm:   Connection 'lo' (de55bd18-111a-4bb0-b8c5-3973f79d6404) successfully deleted.
    2024-01-05 21:04:49,974 - clone - DEBUG - clone_vm:   Connection 'net-barn' (a789d596-71c0-489d-b2c3-e1a183d2c8f4) successfully added.
    2024-01-05 21:04:49,974 - clone - DEBUG - clone_vm:   Connection 'net-prod' (cdbd5e30-9e73-428c-a0a9-c6ee2a363535) successfully added.
    2024-01-05 21:04:49,975 - clone - DEBUG - clone_vm:   STATE   CONNECTIVITY  WIFI-HW  WIFI     WWAN-HW  WWAN    
    2024-01-05 21:04:49,975 - clone - DEBUG - clone_vm:   asleep  none          missing  enabled  missing  enabled 
    2024-01-05 21:04:49,975 - clone - DEBUG - clone_vm:     Physical volume "/dev/sdb1" changed
    2024-01-05 21:04:49,975 - clone - DEBUG - clone_vm:     1 physical volume(s) resized or updated / 0 physical volume(s) not resized
    2024-01-05 21:04:49,975 - clone - DEBUG - dns_for_vm: DNS Record: rac19-b-lis-1 (192.168.8.53)
    2024-01-05 21:04:49,975 - utils - DEBUG - create_dns_record: DNS record A
    2024-01-05 21:04:49,975 - utils - DEBUG - create_dns_record:  rac19-b-lis-1 (192.168.8.53)
    2024-01-05 21:04:49,977 - utils - DEBUG - create_dns_record:  A   DNS update response: NOERROR QR
    2024-01-05 21:04:49,977 - utils - DEBUG - create_dns_record: DNS record PTR
    2024-01-05 21:04:49,980 - utils - DEBUG - create_dns_record:  PTR DNS update response: NOERROR QR
    2024-01-05 21:04:49,980 - utils - DEBUG - create_dns_record: DNS record A
    2024-01-05 21:04:49,980 - utils - DEBUG - create_dns_record:  rac19-b-lis-1 (10.0.0.53)
    2024-01-05 21:04:49,981 - utils - DEBUG - create_dns_record:  A   DNS update response: NOERROR QR
    2024-01-05 21:04:49,981 - utils - DEBUG - create_dns_record: DNS record PTR
    2024-01-05 21:04:49,983 - utils - DEBUG - create_dns_record:  PTR DNS update response: NOERROR QR
    2024-01-05 21:04:49,983 - clone - DEBUG - dns_for_vm: DNS Record: rac19-b-lis-2 (192.168.8.54)
    2024-01-05 21:04:49,983 - utils - DEBUG - create_dns_record: DNS record A
    2024-01-05 21:04:49,983 - utils - DEBUG - create_dns_record:  rac19-b-lis-2 (192.168.8.54)
    2024-01-05 21:04:49,985 - utils - DEBUG - create_dns_record:  A   DNS update response: NOERROR QR
    2024-01-05 21:04:49,985 - utils - DEBUG - create_dns_record: DNS record PTR
    2024-01-05 21:04:49,987 - utils - DEBUG - create_dns_record:  PTR DNS update response: NOERROR QR
    2024-01-05 21:04:49,987 - utils - DEBUG - create_dns_record: DNS record A
    2024-01-05 21:04:49,987 - utils - DEBUG - create_dns_record:  rac19-b-lis-2 (10.0.0.54)
    2024-01-05 21:04:49,988 - utils - DEBUG - create_dns_record:  A   DNS update response: NOERROR QR
    2024-01-05 21:04:49,988 - utils - DEBUG - create_dns_record: DNS record PTR
    2024-01-05 21:04:49,989 - utils - DEBUG - create_dns_record:  PTR DNS update response: NOERROR QR
    2024-01-05 21:04:49,990 - clone - DEBUG - dns_for_vm: DNS Record: rac19-b-scan (['192.168.8.57', '192.168.8.58', '192.168.8.59'])
    2024-01-05 21:04:49,990 - utils - DEBUG - add_dns_record: DNS record A
    2024-01-05 21:04:49,990 - utils - DEBUG - add_dns_record:  rac19-b-scan (192.168.8.57)
    2024-01-05 21:04:49,992 - utils - DEBUG - add_dns_record:  A   DNS update response: NOERROR QR
    2024-01-05 21:04:49,992 - utils - DEBUG - add_dns_record: DNS record A
    2024-01-05 21:04:49,992 - utils - DEBUG - add_dns_record:  rac19-b-scan (192.168.8.58)
    2024-01-05 21:04:49,994 - utils - DEBUG - add_dns_record:  A   DNS update response: NOERROR QR
    2024-01-05 21:04:49,994 - utils - DEBUG - add_dns_record: DNS record A
    2024-01-05 21:04:49,995 - utils - DEBUG - add_dns_record:  rac19-b-scan (192.168.8.59)
    2024-01-05 21:04:49,996 - utils - DEBUG - add_dns_record:  A   DNS update response: NOERROR QR
    2024-01-05 21:04:50,035 - add_shared_disk - DEBUG - _create_data_file: Creating data file: rac19-b-node-1, 1:15, 8388608KB
    2024-01-05 21:04:50,046 - add_shared_disk - DEBUG - _create_data_file: Creating VMDK capacityKb: 8388608; adapterType: lsiLogic; diskType: eagerZeroedThick
    2024-01-05 21:04:50,050 - add_shared_disk - DEBUG - _create_data_file: VMDK [Kingston890G] rac19-b-node-1//eager_data_1_15.vmdk creating
    2024-01-05 21:05:07,012 - add_shared_disk - DEBUG - _create_data_file: VMDK [Kingston890G] rac19-b-node-1//eager_data_1_15.vmdk created successfully
    2024-01-05 21:05:07,019 - add_shared_disk - DEBUG - _create_data_file: VMDK [Kingston890G] rac19-b-node-1//eager_data_1_15.vmdk UUID: 60 00 C2 98 9e b4 24 d0-b6 3a ea 1f bf 9d 8a bb
    2024-01-05 21:05:07,507 - add_shared_disk - DEBUG - add_shared_disk: rac19-b-node-1 Added disk 8GGB [Kingston890G] rac19-b-node-1//eager_data_1_15.vmdk
    2024-01-05 21:05:07,655 - add_shared_disk - DEBUG - add_shared_disk: rac19-b-node-2 Added disk 8GGB [Kingston890G] rac19-b-node-1//eager_data_1_15.vmdk
    2024-01-05 21:05:07,669 - add_shared_disk - DEBUG - _create_data_file: Creating data file: rac19-b-node-1, 1:14, 8388608KB
    2024-01-05 21:05:07,680 - add_shared_disk - DEBUG - _create_data_file: Creating VMDK capacityKb: 8388608; adapterType: lsiLogic; diskType: eagerZeroedThick
    2024-01-05 21:05:07,682 - add_shared_disk - DEBUG - _create_data_file: VMDK [Kingston890G] rac19-b-node-1//eager_data_1_14.vmdk creating
    2024-01-05 21:05:32,260 - add_shared_disk - DEBUG - _create_data_file: VMDK [Kingston890G] rac19-b-node-1//eager_data_1_14.vmdk created successfully
    2024-01-05 21:05:32,267 - add_shared_disk - DEBUG - _create_data_file: VMDK [Kingston890G] rac19-b-node-1//eager_data_1_14.vmdk UUID: 60 00 C2 92 f3 5c dd e3-a4 31 9a e5 01 e5 94 40
    2024-01-05 21:05:32,847 - add_shared_disk - DEBUG - add_shared_disk: rac19-b-node-1 Added disk 8GGB [Kingston890G] rac19-b-node-1//eager_data_1_14.vmdk
    2024-01-05 21:05:33,017 - add_shared_disk - DEBUG - add_shared_disk: rac19-b-node-2 Added disk 8GGB [Kingston890G] rac19-b-node-1//eager_data_1_14.vmdk
    2024-01-05 21:05:33,029 - add_shared_disk - DEBUG - _create_data_file: Creating data file: rac19-b-node-1, 1:13, 8388608KB
    2024-01-05 21:05:33,040 - add_shared_disk - DEBUG - _create_data_file: Creating VMDK capacityKb: 8388608; adapterType: lsiLogic; diskType: eagerZeroedThick
    2024-01-05 21:05:33,043 - add_shared_disk - DEBUG - _create_data_file: VMDK [Kingston890G] rac19-b-node-1//eager_data_1_13.vmdk creating
    2024-01-05 21:06:22,023 - add_shared_disk - DEBUG - _create_data_file: VMDK [Kingston890G] rac19-b-node-1//eager_data_1_13.vmdk created successfully
    2024-01-05 21:06:22,038 - add_shared_disk - DEBUG - _create_data_file: VMDK [Kingston890G] rac19-b-node-1//eager_data_1_13.vmdk UUID: 60 00 C2 92 4f 5f 1a 23-f7 0e 65 47 14 df e5 aa
    2024-01-05 21:06:22,760 - add_shared_disk - DEBUG - add_shared_disk: rac19-b-node-1 Added disk 8GGB [Kingston890G] rac19-b-node-1//eager_data_1_13.vmdk
    2024-01-05 21:06:23,144 - add_shared_disk - DEBUG - add_shared_disk: rac19-b-node-2 Added disk 8GGB [Kingston890G] rac19-b-node-1//eager_data_1_13.vmdk
    2024-01-05 21:06:23,167 - add_shared_disk - DEBUG - _create_data_file: Creating data file: rac19-b-node-1, 1:12, 8388608KB
    2024-01-05 21:06:23,182 - add_shared_disk - DEBUG - _create_data_file: Creating VMDK capacityKb: 8388608; adapterType: lsiLogic; diskType: eagerZeroedThick
    2024-01-05 21:06:23,185 - add_shared_disk - DEBUG - _create_data_file: VMDK [Kingston890G] rac19-b-node-1//eager_data_1_12.vmdk creating
    2024-01-05 21:07:03,291 - add_shared_disk - DEBUG - _create_data_file: VMDK [Kingston890G] rac19-b-node-1//eager_data_1_12.vmdk created successfully
    2024-01-05 21:07:03,297 - add_shared_disk - DEBUG - _create_data_file: VMDK [Kingston890G] rac19-b-node-1//eager_data_1_12.vmdk UUID: 60 00 C2 90 f7 53 8d 42-d5 56 37 6a 43 f9 a8 95
    2024-01-05 21:07:03,856 - add_shared_disk - DEBUG - add_shared_disk: rac19-b-node-1 Added disk 8GGB [Kingston890G] rac19-b-node-1//eager_data_1_12.vmdk
    2024-01-05 21:07:04,016 - add_shared_disk - DEBUG - add_shared_disk: rac19-b-node-2 Added disk 8GGB [Kingston890G] rac19-b-node-1//eager_data_1_12.vmdk
