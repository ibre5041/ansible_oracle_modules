# oracle_asmvol

## Description
Gere les volumes ASM au sein des diskgroups.

## Utilisation
Utiliser pour preparer des volumes ASM destines a ACFS ou autres usages.

## Exemples
```yaml
- name: Creer un volume ASM
  oracle_asmvol:
    hostname: localhost
    service_name: +ASM
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    diskgroup: DATA
    name: VOL01
    size: 100G
    state: present
```

```yaml
- name: Redimensionner un volume ASM
  oracle_asmvol:
    hostname: localhost
    service_name: +ASM
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    diskgroup: DATA
    name: VOL01
    size: 150G
    state: present
```

```yaml
- name: Supprimer un volume ASM
  oracle_asmvol:
    hostname: localhost
    service_name: +ASM
    mode: sysdba
    user: sys
    password: "{{ vault_sys_password }}"
    diskgroup: DATA
    name: VOL01
    state: absent
```
