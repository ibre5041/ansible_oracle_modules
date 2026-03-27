# oracle_directory

## Description
Gere les objets DIRECTORY Oracle.

## Utilisation
Utiliser pour exposer des chemins OS aux traitements Oracle (external tables, datapump, etc.).
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Creer un directory
  oracle_directory:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    directory_name: ETL_DIR
    directory_path: /u02/etl
    state: present
```

```yaml
- name: Mettre a jour le chemin d'un directory
  oracle_directory:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    directory_name: ETL_DIR
    directory_path: /u03/etl
    state: present
```

```yaml
- name: Supprimer un directory
  oracle_directory:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    directory_name: ETL_DIR
    state: absent
```
