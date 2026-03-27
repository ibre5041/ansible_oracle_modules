# oracle_jobclass

## Description
Gere les classes de jobs Oracle Scheduler.

## Utilisation
Utiliser pour organiser les jobs, leur logging et resource consumer group.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Creer une classe de jobs
  oracle_jobclass:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    name: APP_CLASS
    resource_group: APP_GROUP
    logging: full
    state: present
```

```yaml
- name: Mettre a jour historique et commentaires
  oracle_jobclass:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    name: APP_CLASS
    history: 30
    comments: "Classe jobs applicatifs"
    state: present
```

```yaml
- name: Supprimer une classe de jobs
  oracle_jobclass:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    name: APP_CLASS
    state: absent
```
