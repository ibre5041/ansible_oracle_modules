===============================================
Ibre5041.Ansible\_Oracle\_Modules Release Notes
===============================================

.. contents:: Topics

v3.2.5
======

- Fix for profile names having special characters in it
- Fix for oracle_user paramters locked and expired

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

