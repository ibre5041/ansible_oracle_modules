Role Name
=========

This role downloads and unpacks Oracle instalation image at predefined path.

Requirements
------------

ORACLE_HOME has to be created. You should have some central HTTP repository wherefrom you can download Oracle golden images.
Or you can prepare them direcly on the DB server.

Role Variables
--------------

- oracle_install_dir_temp: temporary directory where to store downloaded .zip/.tgz package
- oracle_url_base: HTTP(S) url base wherefrom download Oracle golden images
- oracle_dir_base: local directory on DB server where Oracle golden images are prepared (alternative to oracle_url_base)
- oracle_image_name: filename of Oracle golden image archive
- oracle_install_dir_temp: temporary place where to download .zip/.tgz packages
- oracle_home: ORACLE_HOME where to unarchive Oracle golden images

Dependencies
------------



Example Playbook
----------------

This role should not be used directly

    - hosts: servers
      roles:
         - role: oracle_download_package
           oracle_url_base: http://localserver/oracle/
           oracle_image_name: LINUX.X64_193000_db_home.zip
           oracle_home: /u01/oracle/product/19.0.0.0

License
-------

BSD

Author Information
------------------

Ivan Brezina
