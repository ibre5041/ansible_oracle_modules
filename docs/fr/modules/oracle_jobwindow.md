# oracle_jobwindow

## Description
Gere les windows DBMS_SCHEDULER (intervalle, duree, priorite, enable/disable).

## Utilisation
Utiliser pour definir des fenetres de maintenance et de planification.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Creer une window hebdo
  oracle_jobwindow:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    name: APP_WINDOW
    repeat_interval: "freq=weekly;byday=sat;byhour=1;byminute=0;bysecond=0"
    duration_hour: 4
    state: enabled
```

```yaml
- name: Desactiver une window
  oracle_jobwindow:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    name: APP_WINDOW
    repeat_interval: "freq=weekly;byday=sat;byhour=1;byminute=0;bysecond=0"
    duration_hour: 4
    state: disabled
```

```yaml
- name: Supprimer une window
  oracle_jobwindow:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    name: APP_WINDOW
    repeat_interval: "freq=weekly;byday=sat;byhour=1;byminute=0;bysecond=0"
    duration_hour: 4
    state: absent
```
