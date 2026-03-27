# oracle_crs_asm

## Description
Gere la ressource ASM en environnement CRS/HAS.

## Utilisation
Utiliser pour declarer et piloter l'etat ASM dans le cluster.

## Exemples
```yaml
- name: Declarer ASM dans CRS
  oracle_crs_asm:
    name: +ASM
    state: present
```

```yaml
- name: Demarrer ASM
  oracle_crs_asm:
    name: +ASM
    state: started
```

```yaml
- name: Arreter ASM
  oracle_crs_asm:
    name: +ASM
    state: stopped
```
