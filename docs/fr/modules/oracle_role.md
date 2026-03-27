# oracle_role

## Description
Gere les roles Oracle (creation, attributs, suppression).

## Utilisation
Utiliser pour structurer les droits applicatifs avant attribution aux utilisateurs.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Creer un role
  oracle_role:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    role: APP_READONLY
    state: present
```

```yaml
- name: Modifier options du role
  oracle_role:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    role: APP_READONLY
    auth: none
    state: present
```

```yaml
- name: Supprimer un role
  oracle_role:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    role: APP_READONLY
    state: absent
```
