# oracle_privs

## Description
Gere en masse les privileges et roles sur un ensemble d'objets et de grantees.

## Utilisation
Utiliser pour synchroniser un modele de droits complet, avec grants et revokes automatiques.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Synchroniser privileges sur tables
  oracle_privs:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    state: present
    roles: ["APP_USER"]
    objs: ["APP_OWNER.%"]
    objtypes: ["TABLE", "VIEW"]
    privs: ["SELECT"]
```

```yaml
- name: Ajouter execute sur packages
  oracle_privs:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    state: present
    roles: ["APP_BATCH"]
    objs: ["APP_OWNER.%"]
    objtypes: ["PROCEDURE", "FUNCTION", "PACKAGE"]
    privs: ["EXECUTE"]
```

```yaml
- name: Revoquer droits d'un role
  oracle_privs:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    state: absent
    roles: ["APP_OLD_ROLE"]
    objs: ["APP_OWNER.%"]
    objtypes: ["TABLE"]
    privs: ["SELECT", "INSERT", "UPDATE", "DELETE"]
```
