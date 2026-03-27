# oracle_crs_service

## Description
Gere les services CRS rattaches a une base cluster.

## Utilisation
Utiliser pour exposer des services applicatifs HA et piloter leur etat.

## Exemples
```yaml
- name: Creer un service CRS
  oracle_crs_service:
    db: CDB1
    service: APP_SVC
    preferred_instances: CDB11,CDB12
    state: present
```

```yaml
- name: Demarrer un service CRS
  oracle_crs_service:
    db: CDB1
    service: APP_SVC
    state: started
```

```yaml
- name: Supprimer un service CRS
  oracle_crs_service:
    db: CDB1
    service: APP_SVC
    state: absent
```
