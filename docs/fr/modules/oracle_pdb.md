# oracle_pdb

## Description
Gere les PDB: creation, ouverture/fermeture, clone, suppression et lecture de statut.

## Utilisation
Utiliser en SYSDBA sur le CDB. Pour les operations applicatives, cibler ensuite le service PDB.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Creer un PDB depuis seed
  oracle_pdb:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    pdb_name: APPPDB1
    pdb_admin_username: app_admin
    pdb_admin_password: "{{ vault_app_admin_password }}"
    state: opened
```

```yaml
- name: Cloner un PDB depuis un source
  oracle_pdb:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    pdb_name: APPPDB2
    sourcedb: APPPDB1
    snapshot_copy: true
    state: opened
```

```yaml
- name: Supprimer un PDB
  oracle_pdb:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    pdb_name: APPPDB2
    state: absent
```
