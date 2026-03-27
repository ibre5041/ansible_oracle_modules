# oracle_datapatch

## Description
Execute datapatch apres application de patchs RDBMS/OPatch.

## Utilisation
Utiliser apres patch binaire pour appliquer les scripts SQL de patch en base.

## Exemples
```yaml
- name: Lancer datapatch sur CDB
  oracle_datapatch:
    oracle_home: /u01/app/oracle/product/19.0.0/dbhome_1
    db_name: CDB1
    password: "{{ vault_sys_password }}"
```

```yaml
- name: Lancer datapatch en verbose
  oracle_datapatch:
    oracle_home: /u01/app/oracle/product/19.0.0/dbhome_1
    db_name: CDB1
    password: "{{ vault_sys_password }}"
    output: verbose
```

```yaml
- name: Datapatch sur cible locale differente
  oracle_datapatch:
    oracle_home: /u01/app/oracle/product/21.0.0/dbhome_1
    db_name: CDB2
    password: "{{ vault_sys_password }}"
```
