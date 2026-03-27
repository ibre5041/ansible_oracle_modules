# oracle_stats_prefs

## Description
Gere les preferences DBMS_STATS au niveau base/schema/table.

## Utilisation
Utiliser pour homogeneriser les politiques de statistiques.

## Exemples
```yaml
- name: Definir preference globale
  oracle_stats_prefs:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    preference_name: STALE_PERCENT
    preference_value: "5"
    state: present
```

```yaml
- name: Preference au niveau schema
  oracle_stats_prefs:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    owner: APP_OWNER
    preference_name: ESTIMATE_PERCENT
    preference_value: "AUTO_SAMPLE_SIZE"
    state: present
```

```yaml
- name: Supprimer override et revenir au default
  oracle_stats_prefs:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    owner: APP_OWNER
    preference_name: STALE_PERCENT
    state: absent
```
