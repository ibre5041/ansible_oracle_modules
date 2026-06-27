===============================================
Ibre5041.Ansible\_Oracle\_Modules Release Notes
===============================================

.. contents:: Topics

v3.4.0
======

New Modules
-----------

- ibre5041.ansible_oracle_modules.oracle_acl - Manage Oracle network Access Control Lists
- ibre5041.ansible_oracle_modules.oracle_audit - Manage Oracle Unified Auditing policies
- ibre5041.ansible_oracle_modules.oracle_dataguard - Manage Oracle Data Guard configurations
- ibre5041.ansible_oracle_modules.oracle_dblink - Manage Oracle database links
- ibre5041.ansible_oracle_modules.oracle_flashback - Manage Oracle restore points and flashback database
- ibre5041.ansible_oracle_modules.oracle_orapki - Manage Oracle PKI wallets, certificates, and credentials via orapki
- ibre5041.ansible_oracle_modules.oracle_rsrc_plan - Manage Oracle Resource Manager plans
- ibre5041.ansible_oracle_modules.oracle_tde - Manage Oracle Transparent Data Encryption (TDE)
- ibre5041.ansible_oracle_modules.oracle_wallet - Manage Oracle TDE keystores (wallets)

v3.3.0
======

Minor Changes
-------------

- fixes for oracle_grant, oracle_profile, oracle_user

Breaking Changes / Porting Guide
--------------------------------

- does not depend on cx_Oracle anymore, use oracledb

v3.2.5
======

Minor Changes
-------------

- Fix for oracle_user paramters locked and expired
- Fix for profile names having special characters in it

v3.2.4
======

Breaking Changes / Porting Guide
--------------------------------

- oracle_tablespace rewritten, default values changed

v3.2.3
======

Minor Changes
-------------

- CRS build fixes

v3.2.2
======

New Plugins
-----------

Filter
~~~~~~

- ibre5041.ansible_oracle_modules.pwhash12c - Compute hash of Oracle password

v3.2.1
======

Minor Changes
-------------

- oracle_crs_db fixes
- oracle_gi_facts fixes
- oracle_oratab fixes

v3.2.0
======

Minor Changes
-------------

- oracle_gi_facts detects ORACLE_HOME

v3.1.10
=======

Minor Changes
-------------

- added support for names ORACLE_HOMEs (oracle_home_name)

v3.1.9
======

Minor Changes
-------------

- more documentation
- more tests
- suppot for RAC on RHEL 9

Breaking Changes / Porting Guide
--------------------------------

- oracle_db interface changed, fixes, support for RAC

v3.1.8
======

