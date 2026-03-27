# oracle_grant

## Description
Attribue ou revoque des privileges systeme/objet/directory.

## Utilisation
Utiliser pour gerer les droits fins sur schemas et objets de facon declarative.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Donner des privileges systeme
  oracle_grant:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    grantee: APP_USER
    grants:
      - create session
      - create table
    state: present
```

```yaml
- name: Donner privilege objet
  oracle_grant:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    grantee: APP_USER
    object_name: APP_OWNER.ORDERS
    grants:
      - select
      - update
    state: present
```

```yaml
- name: Revoquer privilege
  oracle_grant:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    grantee: APP_USER
    grants:
      - create table
    state: absent
```
