# oracle_sql

## Description
Execute des requetes SQL/PLSQL de facon idempotente avec support CDB/PDB.

## Utilisation
Utiliser pour les changements SQL applicatifs et DBA simples. Preferer connexion distante pour PDB, ou connexion locale + changement de container.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Requete SELECT
  oracle_sql:
    hostname: db01
    service_name: apppdb1
    user: app_admin
    password: "{{ vault_app_password }}"
    sql: "select count(*) from dual"
```

```yaml
- name: DDL dans un PDB local via CDB
  oracle_sql:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    pdb_name: APPPDB1
    sql: "create role APP_READONLY"
```

```yaml
- name: Execution d'un script SQL
  oracle_sql:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    script: "/opt/sql/init_app.sql"
```
