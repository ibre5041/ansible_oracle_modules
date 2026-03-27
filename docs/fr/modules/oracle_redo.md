# oracle_redo

## Description
Gere les redo logs et standby redo logs.

## Utilisation
Utiliser pour aligner taille/nombre de groupes selon les standards HA et performance.

## Exemples
```yaml
- name: Ajuster redo logs
  oracle_redo:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    size: 1024M
    groups: 6
```

```yaml
- name: Configurer standby redo
  oracle_redo:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    standby: true
    size: 1024M
    groups: 8
```

```yaml
- name: Verifier etat actuel
  oracle_redo:
    hostname: localhost
    service_name: cdb1
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    state: status
```
