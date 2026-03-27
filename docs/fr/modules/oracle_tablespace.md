# oracle_tablespace

## Description
Gere les tablespaces (creation, extension, suppression, attributs).

## Utilisation
Utiliser pour provisionner les espaces de donnees applicatifs et les maintenir dans le temps.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Creer un tablespace
  oracle_tablespace:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    tablespace: APP_DATA
    datafile: /u02/oradata/apppdb1/app_data01.dbf
    size: 2G
    state: present
```

```yaml
- name: Activer autoextend
  oracle_tablespace:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    tablespace: APP_DATA
    autoextend: true
    next: 256M
    maxsize: 32G
    state: present
```

```yaml
- name: Supprimer un tablespace
  oracle_tablespace:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    tablespace: APP_DATA
    state: absent
```
