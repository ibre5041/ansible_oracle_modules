# oracle_job

## Description
Gere les jobs DBMS_SCHEDULER (creation, recreation sur changement, suppression).

## Utilisation
Utiliser pour planifier traitements SQL/PLSQL ou executables de maniere declarative.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Creer un job PLSQL
  oracle_job:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    job_name: APP_OWNER.JOB_PURGE
    job_type: plsql_block
    job_action: "begin app_owner.purge_data; end;"
    repeat_interval: "freq=daily;byhour=2;byminute=0;bysecond=0"
    enabled: true
    state: present
```

```yaml
- name: Desactiver un job
  oracle_job:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    job_name: APP_OWNER.JOB_PURGE
    enabled: false
    state: present
```

```yaml
- name: Supprimer un job
  oracle_job:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    job_name: APP_OWNER.JOB_PURGE
    state: absent
```
