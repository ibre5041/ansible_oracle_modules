# oracle_profile

## Description
Gere les profils de securite Oracle et leurs attributs.

## Utilisation
Utiliser pour imposer des politiques de mot de passe et de ressources.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Creer un profil securise
  oracle_profile:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    profile: APP_PROFILE
    attribute_name: PASSWORD_LIFE_TIME
    attribute_value: "90"
    state: present
```

```yaml
- name: Mettre a jour verrouillage apres echecs
  oracle_profile:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    profile: APP_PROFILE
    attribute_name: FAILED_LOGIN_ATTEMPTS
    attribute_value: "5"
    state: present
```

```yaml
- name: Supprimer un profil
  oracle_profile:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    profile: APP_PROFILE
    state: absent
```
