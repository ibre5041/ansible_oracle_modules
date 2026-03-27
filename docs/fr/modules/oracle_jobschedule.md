# oracle_jobschedule

## Description
Gere les schedules Oracle Scheduler.

## Utilisation
Utiliser pour factoriser les calendriers d'execution et les reutiliser sur plusieurs jobs.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Creer un schedule
  oracle_jobschedule:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    name: APP_OWNER.SCH_NIGHTLY
    repeat_interval: "freq=daily;byhour=1;byminute=0;bysecond=0"
    comments: "Schedule de nuit"
    state: present
```

```yaml
- name: Mettre a jour un schedule
  oracle_jobschedule:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    name: APP_OWNER.SCH_NIGHTLY
    repeat_interval: "freq=daily;byhour=2;byminute=0;bysecond=0"
    state: present
```

```yaml
- name: Supprimer un schedule
  oracle_jobschedule:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    name: APP_OWNER.SCH_NIGHTLY
    state: absent
```
