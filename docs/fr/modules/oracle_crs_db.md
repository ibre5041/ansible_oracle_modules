# oracle_crs_db

## Description
Gere les ressources base de donnees dans CRS/HAS.

## Utilisation
Utiliser pour enregistrer une base dans CRS et piloter son etat.

## Exemples
```yaml
- name: Declarer une base dans CRS
  oracle_crs_db:
    name: CDB1
    oracle_home: /u01/app/oracle/product/19.0.0/dbhome_1
    state: present
```

```yaml
- name: Demarrer une base CRS
  oracle_crs_db:
    name: CDB1
    state: started
```

```yaml
- name: Arreter une base CRS
  oracle_crs_db:
    name: CDB1
    state: stopped
```
