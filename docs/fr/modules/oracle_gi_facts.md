# oracle_gi_facts

## Description
Collecte les informations Grid Infrastructure (CRS, ASM, homes, ressources).

## Utilisation
Utiliser pour inventorier un cluster GI/HAS et controler son etat.

## Exemples
```yaml
- name: Collecte GI de base
  oracle_gi_facts:
    oracle_home: /u01/app/19.0.0/grid
```

```yaml
- name: Collecte sur un noeud specifique
  oracle_gi_facts:
    oracle_home: /u01/app/19.0.0/grid
    hostname: node1
```

```yaml
- name: Export facts GI pour reporting
  oracle_gi_facts:
    oracle_home: /u01/app/19.0.0/grid
  register: gi_facts
```
