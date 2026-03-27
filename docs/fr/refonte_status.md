# Etat de la refonte in-place

## Inventaire baseline

- 37 modules Python detectes dans `plugins/modules` (dont `oracle_sql` et tous les modules CRS/ASM/DB).
- Support check mode:
  - `supports_check_mode=True`: majorite des modules applicatifs.
  - `supports_check_mode=False` ou non specifie: modules systeme/patching (`oracle_db`, `oracle_opatch`, `oracle_datapatch`, etc.).

## Correctifs robustesse appliques

- `oracle_tnsnames`: plus d'ecriture disque en `check_mode`.
- `oracle_sql`: `changed` aligne sur l'execution reelle; support local PDB via `session_container` (ou `pdb_name` en compatibilite).
- `oracle_utils`:
  - sanitisation des erreurs (plus de SQL brut dans `fail_json`),
  - `ignore_errors=None` au lieu de liste mutable,
  - validation et helper `set_container()` pour `ALTER SESSION`.
- `oracle_sqldba`:
  - correction `ORACLE_SID`,
  - correction `rstrip` sur `sqlselect`,
  - masquage mot de passe dans traces d'erreur.
- `oracle_profile`: correction `required_together`.
- `oracle_ldapuser`: secrets marques `no_log=True`.
- `oracle_awr`: suppression de references a `conn` avant initialisation.
- `oracle_grant` / `oracle_pdb`: passage par helper `set_container()`.

## Tests Python

- Nouvelle suite `pytest` dans `tests/unit`.
- Couverture gate CI configuree a `>=80%`.
- Statut actuel local: `11 passed` avec couverture `88%` sur les modules couverts.

## Limites restantes

- La refonte complete de tous les modules n'est pas encore homogene sur le meme socle commun.
- Les tests unitaires couvrent actuellement les modules critiques corriges en priorite (`oracle_sql`, `oracle_tnsnames`) et la logique associee.
