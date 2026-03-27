# oracle_awr

## Description
Configure les snapshots AWR (intervalle, retention).

## Utilisation
Utiliser pour standardiser la collecte de performance et le diagnostic en production.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Regler AWR (1h / 8 jours)
  oracle_awr:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    snapshot_interval_min: 60
    snapshot_retention_days: 8
```

```yaml
- name: Desactiver snapshots automatiques
  oracle_awr:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    snapshot_interval_min: 0
```

```yaml
- name: Retention longue pour audit perf
  oracle_awr:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    snapshot_interval_min: 30
    snapshot_retention_days: 30
```
