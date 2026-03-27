# oracle_ping

## Description
Verifie la connectivite Oracle et valide les parametres de connexion.

## Utilisation
Utiliser ce module en pre-check avant les taches d'administration ou de deploiement.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Ping Oracle distant
  oracle_ping:
    hostname: db01
    port: 1521
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
```

```yaml
- name: Ping local en SYSDBA
  oracle_ping:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
```

```yaml
- name: Ping avec wallet
  oracle_ping:
    hostname: db01
    service_name: apppdb1
```
