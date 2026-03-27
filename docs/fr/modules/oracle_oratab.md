# oracle_oratab

## Description
Lit les homes/instances Oracle (oratab, process, CRS) et expose des facts.

## Utilisation
Utiliser pour detecter automatiquement les SIDs, homes et etats DB/ASM sur les serveurs.

## Exemples
```yaml
- name: Inventaire global des instances
  oracle_oratab:
```

```yaml
- name: Ne garder que les instances ouvertes
  oracle_oratab:
    open_only: true
    running_only: true
```

```yaml
- name: Ne garder que ASM et homes CRS
  oracle_oratab:
    asm_only: true
    homes: crs
```
