# oracle_asmdg

## Description
Gere les ASM diskgroups (creation, attributs, suppression).

## Utilisation
Utiliser pour provisionner et maintenir les diskgroups ASM.

## Exemples
```yaml
- name: Creer un diskgroup ASM
  oracle_asmdg:
    hostname: localhost
    service_name: +ASM
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    name: DATA
    disks:
      - ORCL:DATA01
      - ORCL:DATA02
    redundancy: external
    state: present
```

```yaml
- name: Ajouter des disques
  oracle_asmdg:
    hostname: localhost
    service_name: +ASM
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    name: DATA
    disks:
      - ORCL:DATA03
    state: present
```

```yaml
- name: Supprimer un diskgroup
  oracle_asmdg:
    hostname: localhost
    service_name: +ASM
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    name: DATA
    state: absent
```
