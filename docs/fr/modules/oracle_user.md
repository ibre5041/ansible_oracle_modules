# oracle_user

## Description
Gere les schemas/utilisateurs Oracle (creation, modification, suppression, verrouillage, profil, tablespaces).

## Utilisation
Utiliser pour maintenir les comptes techniques et applicatifs de maniere idempotente.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Creer un utilisateur applicatif
  oracle_user:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    schema: app_user
    schema_password: "{{ vault_app_password }}"
    default_tablespace: APP_DATA
    state: present
```

```yaml
- name: Mettre a jour profil et etat du compte
  oracle_user:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    schema: app_user
    profile: APP_PROFILE
    locked: false
    expired: false
    state: present
```

```yaml
- name: Supprimer un utilisateur
  oracle_user:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    schema: app_user
    state: absent
```
