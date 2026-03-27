# oracle_sqldba

## Description
Execute SQLPlus/catcon.pl pour operations DBA avancees, avec gestion de timeout et scope CDB/PDB.

## Utilisation
Utiliser pour scripts post-installation, patch SQL, ou commandes SQL*Plus qui depassent les usages standard des autres modules.

## Exemples
```yaml
- name: SQL simple en SYSDBA
  oracle_sqldba:
    oracle_home: /u01/app/oracle/product/19.0.0/dbhome_1
    oracle_sid: CDB1
    sql: "alter system archive log current"
```

```yaml
- name: Script SQL sur PDBs cibles
  oracle_sqldba:
    oracle_home: /u01/app/oracle/product/19.0.0/dbhome_1
    oracle_sid: CDB1
    scope: pdbs
    pdb_list:
      - APPPDB1
      - APPPDB2
    sqlscript: "@/opt/sql/app_patch.sql"
```

```yaml
- name: catcon.pl sur tous les PDBs
  oracle_sqldba:
    oracle_home: /u01/app/oracle/product/19.0.0/dbhome_1
    oracle_sid: CDB1
    scope: all_pdbs
    catcon_pl: "$ORACLE_HOME/rdbms/admin/utlrp.sql"
    timeout: 1800
```
