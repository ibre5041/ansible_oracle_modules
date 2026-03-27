# oracle_acfs

## Description
Gere les systemes de fichiers ACFS bases sur des volumes ASM.

## Utilisation
Utiliser pour creer, monter et supprimer des filesystems ACFS.

## Exemples
```yaml
- name: Creer et monter un filesystem ACFS
  oracle_acfs:
    volume_name: VOL01
    diskgroup: DATA
    mountpoint: /acfs/data
    owner: oracle
    group: oinstall
    state: present
```

```yaml
- name: Monter un filesystem existant
  oracle_acfs:
    volume_name: VOL01
    diskgroup: DATA
    mountpoint: /acfs/data
    state: mounted
```

```yaml
- name: Supprimer un filesystem ACFS
  oracle_acfs:
    volume_name: VOL01
    diskgroup: DATA
    mountpoint: /acfs/data
    state: absent
```
