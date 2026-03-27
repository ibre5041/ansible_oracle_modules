# oracle_services

## Description
Gere les services Oracle en mode base seule ou GI/CRS.

## Utilisation
Utiliser pour creer, demarrer, arreter et supprimer des services applicatifs.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Creer un service
  oracle_services:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    name: APP_SVC
    database_name: CDB1
    state: present
```

```yaml
- name: Demarrer un service
  oracle_services:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    name: APP_SVC
    database_name: CDB1
    state: started
```

```yaml
- name: Supprimer un service
  oracle_services:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    name: APP_SVC
    database_name: CDB1
    state: absent
```
