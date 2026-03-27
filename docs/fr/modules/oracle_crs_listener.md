# oracle_crs_listener

## Description
Gere les listeners en environnement CRS/HAS.

## Utilisation
Utiliser pour creer, demarrer, arreter et supprimer des listeners clusters.

## Exemples
```yaml
- name: Creer un listener CRS
  oracle_crs_listener:
    name: LISTENER_APP
    oracle_home: /u01/app/19.0.0/grid
    state: present
```

```yaml
- name: Demarrer le listener
  oracle_crs_listener:
    name: LISTENER_APP
    state: started
```

```yaml
- name: Supprimer le listener
  oracle_crs_listener:
    name: LISTENER_APP
    state: absent
```
