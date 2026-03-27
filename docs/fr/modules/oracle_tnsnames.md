# oracle_tnsnames

## Description
Gere des entrees de `tnsnames.ora`/`listener.ora` de facon idempotente.

## Utilisation
Utiliser pour automatiser la configuration reseau Oracle et ses aliases.

## Exemples
```yaml
- name: Creer un alias TNS
  oracle_tnsnames:
    path: /u01/app/oracle/product/19/network/admin/tnsnames.ora
    alias: APPPDB1
    attribute_path: DESCRIPTION/CONNECT_DATA/SERVICE_NAME
    attribute_value: apppdb1
    state: present
```

```yaml
- name: Mettre a jour l'hote d'un alias
  oracle_tnsnames:
    path: /u01/app/oracle/product/19/network/admin/tnsnames.ora
    alias: APPPDB1
    attribute_path: DESCRIPTION/ADDRESS/ADDRESS/HOST
    attribute_value: db01.example.net
    state: present
```

```yaml
- name: Supprimer un alias
  oracle_tnsnames:
    path: /u01/app/oracle/product/19/network/admin/tnsnames.ora
    alias: APPPDB1
    state: absent
```
