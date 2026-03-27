# oracle_facts

## Description
Collecte des facts Oracle (instance, base, params, redo, pdb, etc.) pour Ansible.

## Utilisation
Utiliser pour alimenter des playbooks dynamiques et des controles de conformite.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Collecte standard
  oracle_facts:
    hostname: db01
    service_name: cdb1
    user: system
    password: "{{ vault_db_password }}"
```

```yaml
- name: Collecte detaillee avec parameteres et redo
  oracle_facts:
    hostname: db01
    service_name: cdb1
    user: system
    password: "{{ vault_db_password }}"
    parameter:
      - open_cursors
      - processes
    redo: summary
    standby: summary
```

```yaml
- name: Collecte locale SYSDBA
  oracle_facts:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    database: true
    userenv: true
```
