# oracle_db

## Description
Gere le cycle de vie d'une base Oracle (creation, etat, suppression) via outillage Oracle.

## Utilisation
Utiliser pour provisionner une base de reference, gerer son etat de demarrage, ou la retirer proprement.
Quand une session SQL locale est utilisee dans ce module, `session_container` permet de cibler un PDB via `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Creer une base CDB
  oracle_db:
    state: present
    oracle_home: /u01/app/oracle/product/19.0.0/dbhome_1
    db_name: CDB1
    sys_password: "{{ vault_sys_password }}"
    system_password: "{{ vault_system_password }}"
    datafile_dest: /u02/oradata
```

```yaml
- name: S'assurer que la base est demarree
  oracle_db:
    state: started
    oracle_home: /u01/app/oracle/product/19.0.0/dbhome_1
    db_name: CDB1
```

```yaml
- name: Supprimer une base
  oracle_db:
    state: absent
    oracle_home: /u01/app/oracle/product/19.0.0/dbhome_1
    db_name: CDB1
```
