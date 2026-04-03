oracle_crs_26ai
===============

Install and configure Oracle Grid Infrastructure (CRS) 26ai, including OS-level prerequisites for ASM disks and RAC-oriented bootstrap steps.

Requirements
------------

- Linux host with required OS packages and kernel parameters.
- Oracle Grid Infrastructure media available via variables used by `oracle_download_package`.
- Inventory variables for network interfaces and cluster topology.

Role Variables
--------------

Commonly used variables are defined in:

- `defaults/main.yml` (for example `oracle_home`, `oracle_gi_response_file`, `oracle_crs_public_iface`)
- `vars/main.yml` (for example `first_rac_node`)
- shared defaults from `default_vars_only`

Dependencies
------------

- `default_vars_only`
- `oracle_crs_os_setup`
- `oracle_download_package`

Example Playbook
----------------

```yaml
- hosts: rac_nodes
  become: true
  roles:
    - role: oracle_crs_26ai
      vars:
        oracle_release: "26ai"
        oracle_install_type: "rac"
```

Golden Image HOWTO
------------------

Reference procedure used during image preparation:

- `http://www.ludovicocaldara.net/dba/2018/11/`
- `mv OPatch OPatch.old`
- `wget http://192.168.8.200/oracle/OPatch/p6880880_190000_Linux-x86-64.zip`
- `unzip p6880880_190000_Linux-x86-64.zip`
- `rm p6880880_190000_Linux-x86-64.zip`
- `./gridSetup.sh -applyRU /home/oracle/30783556/30805684`
- `./gridSetup.sh -applyRU /home/oracle/30783556/30899722`
- `./gridSetup.sh -silent -responseFile /home/oracle/grid.swonly.rsp ORACLE_HOME_NAME=crs1907`
- `lvextend /oracle/u01/gi/ (+30g)`
- `./gridSetup.sh -createGoldImage -destinationLocation /oracle/u01/gi/ -silent`

License
-------

MIT

Author Information
------------------

Maintained by Ivan Brezina and contributors in this fork.
