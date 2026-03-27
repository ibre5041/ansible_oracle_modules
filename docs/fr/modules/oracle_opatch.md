# oracle_opatch

## Description
Gere l'installation/suppression de patchs Oracle avec OPatch.

## Utilisation
Utiliser pour industrialiser le patching binaire et verifier l'etat de patch.

## Exemples
```yaml
- name: Appliquer un patch
  oracle_opatch:
    oracle_home: /u01/app/oracle/product/19.0.0/dbhome_1
    patch_base: /u01/patches/35742441
    state: present
```

```yaml
- name: Supprimer un patch
  oracle_opatch:
    oracle_home: /u01/app/oracle/product/19.0.0/dbhome_1
    patch_id: "35742441"
    state: absent
```

```yaml
- name: Lister les patchs installes
  oracle_opatch:
    oracle_home: /u01/app/oracle/product/19.0.0/dbhome_1
    state: lspatches
```
