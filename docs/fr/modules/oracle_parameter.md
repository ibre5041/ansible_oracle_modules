# oracle_parameter

## Description
Gere les parametres d'instance Oracle (SPFILE/MEMORY/BOTH).

## Utilisation
Utiliser pour standardiser les reglages d'instance et assurer leur conformite.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Definir open_cursors
  oracle_parameter:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    parameter: open_cursors
    value: "1000"
    scope: both
```

```yaml
- name: Activer audit_trail au prochain restart
  oracle_parameter:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    parameter: audit_trail
    value: "DB,EXTENDED"
    scope: spfile
```

```yaml
- name: Remettre un parametre a sa valeur par defaut
  oracle_parameter:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    parameter: session_cached_cursors
    state: reset
```
