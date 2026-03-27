# oracle_rsrc_consgroup

## Description
Gere les consumer groups du Resource Manager et leurs mappings/grants.

## Utilisation
Utiliser pour controler la priorisation des workloads Oracle.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Creer un consumer group
  oracle_rsrc_consgroup:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    name: APP_GROUP
    mgmt_mth: round-robin
    category: other
    state: present
```

```yaml
- name: Ajouter grants et mappings
  oracle_rsrc_consgroup:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    name: APP_GROUP
    grant_name:
      - APP_USER
    map_oracle_user:
      - APP_USER
    state: present
```

```yaml
- name: Supprimer un consumer group
  oracle_rsrc_consgroup:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    name: APP_GROUP
    state: absent
```
