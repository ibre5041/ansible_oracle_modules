# ansible-oracle-modules
**Oracle modules for Ansible**

- This project was forked from [oravirt/ansible-oracle-modules](https://github.com/oravirt/ansible-oracle-modules), but also tries to consolidate fixes from other forks.  
- This fork uses different layout than original, db connection code is shared via module_utils
- This fork prefers to use `connect / as sysdba` over using wallet, password or SQLNET over TCPIP 
- This fork adds modules `oracle_oratab` to query list od databases, `oracle_tnsnames` to manipulate Oracle .ora files
- This project also contains roles to install Database, Oracle RAC, Oracle HAS on VMware, EC2, on-premise HW.
- See project: [ibre5041/ansible_oracle_modules_example](https://github.com/ibre5041/ansible_oracle_modules_example.git) as an example.

To use this collection place this in requirements.yml

    ---
    collections:
      - name: https://github.com/ibre5041/ansible_oracle_modules.git
        type: git
        version: main

And then execute: `ansible-galaxy collection install -r collections/requirements.yml`

Most (if not all) modules require `cx_Oracle` either on your  managed node or on "control machine".
To install `cx_Oracle` you can use: `pip3 install --user cx_Oracle` (`/usr/libexec/platform-python -m pip install --user cx_Oracle` on RHEL8)

The default behaviour for the modules using `cx_Oracle` is this:

- If mode=='sysdba' connect internal `/ as sysdba` is used
- If neither username and password is passed as input to the module(s), the use of an Oracle wallet is assumed.
- In that case, the `cx_Oracle.makedsn` step is skipped, and the connection will use the `'/@<service_name>'` format instead.
- You then need to make sure that you're using the correct tns-entry (service_name) to match the credential stored in the wallet.

# Modules:

| Module						    | Description |
| :-------------------------------------------------------- | :---------- |
| [oracle_ping](../content/module/oracle_ping/)		    | Test database connection |
| [oracle_acfs](../content/module/oracle_acfs/)		    | Manage ACFS filesystems |
| [oracle_asmdg](../content/module/oracle_asmdg/)	    | Manage diskgroups in an Oracle database |
| [oracle_asmvol](../content/module/oracle_asmvol/)	    | Manage Oracle ASMCMD Volumes |
| [oracle_awr](../content/module/oracle_awr/)		    | Manage AWR configuration |
| [oracle_datapatch](../content/module/oracle_datapatch/)   | Manage datapatch functionality |
| [oracle_db](../content/module/oracle_db/)		    | Create/delete a database using dbca |
| [oracle_crs_asm](../content/module/oracle_crs_asm/)       | Manage CRS/HAS resource ASM instance |
| [oracle_crs_db](../content/module/oracle_crs_db/)         | Manage CRS/HAS resource database |
| [oracle_crs_listener](../content/module/oracle_crs_listener/) | Manage CRS/HAS resource listener |
| [oracle_crs_service](../content/module/oracle_crs_service/) Manage CRS/HAS resource database service |
| [oracle_directory](../content/module/oracle_directory/)   | Create/drop DIRECTORY in an Oracle database |
| [oracle_facts](../content/module/oracle_facts/)	    | Returns some facts about Oracle DB |
| [oracle_gi_facts](../content/module/oracle_gi_facts/)	    | Returns some facts about Grid Infrastructure environment |
| [oracle_grant](../content/module/oracle_grant/)	    | Manage grant/privileges in an Oracle database |
| [oracle_jobclass](../content/module/oracle_jobclass/)	    |
| [oracle_job](../content/module/oracle_job/)		    |
| [oracle_jobschedule](../content/module/oracle_jobschedule/)|
| [oracle_jobwindow](../content/module/oracle_jobwindow/)   |
| [oracle_ldapuser](../content/module/oracle_ldapuser/)	    |
| [oracle_opatch](../content/module/oracle_opatch/)	    | Manage patches in an Oracle environment |
| [oracle_oratab](../content/module/oracle_oratab/)	    | Reads oratab to ansible_facts |
| [oracle_parameter](../content/module/oracle_parameter/)   | Manage parameters in an Oracle database |
| [oracle_pdb](../content/module/oracle_pdb/)		    | Manage pluggable databases in Oracle |
| [oracle_privs](../content/module/oracle_privs/)	    | 
| [oracle_profile](../content/module/oracle_profile/)	    | Manage profiles in an Oracle database |
| [oracle_redo](../content/module/oracle_redo/)		    | Manage Oracle redo related things |
| [oracle_role](../content/module/oracle_role/)		    | Manage users/roles in an Oracle database |
| [oracle_rsrc_consgroup](../content/module/oracle_rsrc_consgroup/)| 
| [oracle_services](../content/module/oracle_services/)	    |
| [oracle_sqldba](../content/module/oracle_sqldba/)	    | Execute sql (scripts) using sqlplus (BEQ) or catcon.pl |
| [oracle_sql](../content/module/oracle_sql/)		    | Execute arbitrary sql
| [oracle_stats_prefs](../content/module/oracle_stats_prefs/)| 
| [oracle_tablespace](../content/module/oracle_tablespace/) | Manage tablespaces in an Oracle database
| [oracle_tnsnames](../content/module/oracle_tnsnames/)	    | Manipulate Oracle's tnsnames.ora and other .ora files
| [oracle_user](../content/module/oracle_user/)		    | Manage users/schemas in an Oracle database

# Roles

| Role   						    | Description |
| :-------------------------------------------------------- | :---------- |
| [default_vars_only](../content/role/default_vars_only/)   | Role containing configuration space, variables used by other roles |
| [base_oracle_ec2](../content/role/base_oracle_ec2/)	    | Basic OS configuration for Oracle on EC2 |
| [base_oracle_vbox](../content/role/base_oracle_vbox/)	    | Basic OS configuration for Oracle on VirtualBox |
| [base_oracle_vmware](../content/role/base_oracle_vmware/) | Basic OS configuration for Oracle on VMware ESX |
| [oracle_asm_disks_ec2](../content/role/oracle_asm_disks_ec2/)| Configure ASM store, install udev rules for EC2 |
| [oracle_asm_disks_vbox](../content/role/oracle_asm_disks_vbox/)| Configure ASM store, install udev rules for VirtualBox |
| [oracle_asm_disks_vmware](../content/role/oracle_asm_disks_vmware/)| Configure ASM store, install udev rules for VMware ESX |
| [oracle_crs_os_setup](../content/role/oracle_crs_os_setup/)| RAC specific OS tasks, ssh-equiv, shared disk partitions |
| [oracle_crs_19c](../content/role/oracle_crs_19c/)	    | Install Oracle RAC |
| [oracle_restart_19c](../content/role/oracle_restart_19c/) | Install Oracle HAS |
| [oracle_db_home](../content/role/oracle_db_home/)	    | Install Oracle RDBMS binaries |
| [oracle_download_package](../content/role/oracle_download_package/)| Downloaded and unpack Oracle (golden) image .zip file |
| [oracle_post_install](../content/role/oracle_post_install/)| Post installation task, Oracle .bash_profile and other utility scripts |
| [oracle_systemd](../content/role/oracle_systemd/)	    | Systemd startup unit file and scripts |

# Virtual Hardware

- VMware, VirtualBox and EC2 are suppored
- Oracle RAC is suppported only in VMware and VirtualBox

- [VMware](../content/role/base_oracle_vmware/)
- [VirtualBox](../content/role/base_oracle_vbox/)
- [EC2](../content/role/base_oracle_ec2/)
