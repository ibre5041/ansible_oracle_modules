# Couverture des tests d'intégration

Ce document recense, pour chaque module de la collection `ibre5041.ansible_oracle_modules`, l'état de la couverture par les tests d'intégration exécutables dans le conteneur Docker de CI (`gvenzl/oracle-free:23-full`, CDB `FREE` + PDB `FREEPDB1`, connexion TCP client-only).

**Contraintes du conteneur** : pas d'ASM, pas de Grid Infrastructure/CRS, pas de standby Data Guard, pas d'OPatch, accès OS local non disponible (`running_on_client: true`, `running_on_server: false`).

**Source de vérité** :
- 45 modules dans `plugins/modules/`
- 26 cibles d'intégration dans `tests/integration/targets/`
- Liste des modules exercés par CI Docker : voir `Makefile::test-docker` et `.github/workflows/integration.yml`

---

## 1. Synthèse

| Catégorie | Nombre |
|---|---:|
| Modules totaux | 45 |
| Modules testés en CI Docker | 16 |
| Cibles existantes mais inactives/partielles | 7 |
| Modules sans tests mais **testables en Docker** (à créer) | 14 |
| Modules **non testables en Docker** (documentation seulement) | 15 |

---

## 2. Modules avec tests actifs en CI Docker (16)

| Module | Cible | Scénarios couverts | Manques identifiés |
|---|---|---|---|
| `oracle_ping` | `test_oracle_ping` | Modes A1/A2 (SYSDBA local/remote), B (session_container CDB→PDB), C (user normal) | — |
| `oracle_user` | `test_oracle_user` | create / delete / modify / change_state / check_mode ; auth password/external/none ; default+temp tablespace ; profile ; lock ; expire | proxy users, quotas (cf. `oracle_quota`) |
| `oracle_role` | `test_oracle_role` | create_delete, parameter, change_identified_method, every_identified_method, check_mode | grant de rôle à rôle, rôles applicatifs complexes |
| `oracle_parameter` | `test_oracle_parameter` | modification / reset ; scope memory/spfile/both ; types num/bool/string ; CDB-only ; no-sysdba | paramètres PDB-spécifiques, paramètres hidden _* exhaustifs |
| `oracle_tablespace` | `test_oracle_tablespace` | create/drop permanent/undo/temp, bigfile, multi-datafiles, modify, check_mode (create/drop), erreurs, valeurs nulles, idempotence | limites d'autoextend, chiffrement (couvert indirectement par `oracle_tde`) |
| `oracle_grant` | `test_oracle_grant` | append/remove/replace privilèges système ; append/remove/replace privilèges objet ; rôle ; directory ; ADB checks ; régression issue6 ; check_mode | WITH ADMIN / WITH GRANT OPTION exhaustifs |
| `oracle_pdb` | `test_oracle_pdb` | create/delete ; existence ; open/close ; read_only ; clone ; exclusive_options ; check_mode | unplug/plug (TODO désactivé), PDB snapshots |
| `oracle_sql` | `test_oracle_sql` | SELECT, DDL, bloc PL/SQL, exécution de fichier, dbms_output, cas spéciaux, check_mode, erreurs (ORA-942) | bind variables, scripts très longs, transactions explicites |
| `oracle_wallet` | `test_oracle_wallet` | create, open/close, change_password, backup, auto_login, secret, status, cleanup | keystore HSM (hors Docker) |
| `oracle_tde` | `test_oracle_tde` | setup_keystore, master_key, tablespace_encrypt/rekey/decrypt, status, cleanup | rotation master key planifiée, chiffrement online |
| `oracle_orapki` | `test_oracle_orapki` | wallet_create, certificates, secrets, cleanup | chaînes de confiance, `mkstore` |
| `oracle_directory` | `test_oracle_directory` | create, replace path, drop, check_mode, validation DDL | grants sur directory (partiellement via `oracle_grant`) |
| `oracle_tnsnames` | `test_oracle_tnsnames` | parse alias, add/remove attributs, paths, SQLNET params, modifs globales, listener, check_mode, idempotence | fichiers à emplacements non standard |
| `oracle_awr` | `test_oracle_awr` | `simple.yml` basique | modification intervalle/rétention + reset |
| `oracle_profile` | `test_oracle_profile` | `simple.yml` + régression `issue_4` | limites exhaustives (failed_login_attempts, password_life_time, password_verify_function) |
| `oracle_facts` | `test_oracle_facts` | compile, subset parameter/content, no_sysdba | facts standby/DG (hors Docker) |

---

## 3. Cibles existantes inactives ou partielles (7)

| Cible | État | Action recommandée |
|---|---|---|
| `test_oracle_db` | Squelette sans scénario | Non prioritaire (Docker fournit déjà la DB) |
| `test_oracle_quota` | `tasks.missing` — pas de `main.yml` opérationnel | **À finaliser (P2)** : grant quota unlimited/limited/none sur `ts_1`/`ts_2`/`ts_3` |
| `test_oracle_dataguard` | broker status/config/enable, skip si pas d'orapki | Limite fonctionnelle : pas de standby en Docker. Garder tel quel |
| `test_oracle_crs_db` | Pas de `main.yml` | Non testable Docker (CRS requis) |
| `test_oracle_crs_asm` | Pas de `main.yml` | Non testable Docker (CRS requis) |
| `test_oracle_crs_listener` | `simple.yml` conditionnel | Non testable Docker |
| `test_oracle_crs_service` | `simple.yml` + `complex.yml` conditionnels | Non testable Docker |
| `test_oracle_gi_facts` | Conditionnel CRS | Non testable Docker |
| `test_pwfilter` | Test du filtre `pwhash12c` | OK — pas un module DB |

---

## 4. Modules sans tests mais testables en Docker (14)

Ces modules n'ont actuellement **aucune** cible d'intégration et sont bons candidats pour une exécution CI dans le conteneur Oracle Free.

| Module | Catégorie | Dépendances Docker |
|---|---|---|
| `oracle_acl` | Sécurité réseau | — |
| `oracle_audit` | Audit unifié | CDB root |
| `oracle_dblink` | Objets DB | — (loopback sur FREEPDB1) |
| `oracle_flashback` | Sauvegarde | DB non-noarchivelog pour flashback guarantee |
| `oracle_job` | Scheduler | user dédié |
| `oracle_jobclass` | Scheduler | lié à `oracle_job` |
| `oracle_jobschedule` | Scheduler | lié à `oracle_job` |
| `oracle_jobwindow` | Scheduler | — |
| `oracle_privs` | Sécurité | — |
| `oracle_redo` | Storage | — |
| `oracle_rsrc_consgroup` | Resource Manager | lié à `oracle_rsrc_plan` |
| `oracle_rsrc_plan` | Resource Manager | — |
| `oracle_services` | Services DB | via `DBMS_SERVICE` (non-CRS) |
| `oracle_stats_prefs` | Optimiseur | — |

---

## 5. Modules non testables en Docker (15)

À documenter dans ce fichier mais **pas** à couvrir dans la CI Docker.

| Module | Raison |
|---|---|
| `oracle_acfs` | Requiert ASM |
| `oracle_asmdg` | Requiert ASM |
| `oracle_asmvol` | Requiert ASM |
| `oracle_crs_asm` | Requiert Grid Infrastructure |
| `oracle_crs_db` | Requiert CRS |
| `oracle_crs_listener` | Requiert CRS |
| `oracle_crs_service` | Requiert CRS |
| `oracle_gi_facts` | Requiert Grid Infrastructure |
| `oracle_dataguard` | Requiert instance standby (test partiel déjà présent) |
| `oracle_datapatch` | Requiert un patch à appliquer |
| `oracle_opatch` | Requiert OPatch et home patché |
| `oracle_ldapuser` | Requiert serveur LDAP/AD |
| `oracle_oratab` | Requiert accès OS local (`running_on_server`) |
| `oracle_sqldba` | Requiert sqlplus/catcon.pl local |
| `oracle_db` | Requiert DBCA / création de DB complète |

Pour ces modules, les utilisateurs disposant d'une infra RAC/CRS peuvent utiliser `tests/integration/integration_config.yml.template.crs`.

---

## 6. Plan priorisé d'ajout de tests

La priorité est proportionnelle à (fréquence d'usage réel) × (faible coût de mise en place).

### P1 — Forte valeur, faible coût (cycle 1)

| # | Cible à créer | Scénarios proposés | Dépendances |
|---|---|---|---|
| 1 | `test_oracle_dblink` | public/private dblink, present/absent, loopback sur `FREEPDB1`, check_mode | SYSTEM |
| 2 | `test_oracle_job` | create/delete job PL/SQL, enable/disable, run_once, idempotence | user `u_jobs` |
| 3 | `test_oracle_jobclass` | create/delete job class, attribution à un job | lié à `oracle_job` |
| 4 | `test_oracle_jobschedule` | create/delete schedule, attribution à un job, repeat_interval | lié à `oracle_job` |
| 5 | `test_oracle_jobwindow` | enabled/disabled/absent, schedule associé | — |
| 6 | `test_oracle_audit` | unified audit policy present/absent/enabled/disabled, status | CDB root |
| 7 | `test_oracle_flashback` | restore point create/drop, status (guarantee non activé si noarchivelog) | — |

### P2 — Finalisation de cibles existantes (cycle 2)

| # | Cible | Action |
|---|---|---|
| 8 | `test_oracle_quota` | Écrire `tasks/main.yml` : grant quota unlimited/limited/none sur `ts_1`/`ts_2`/`ts_3`, puis revocation |
| 9 | `test_oracle_awr` | Ajouter modification d'intervalle/rétention + reset |
| 10 | `test_oracle_profile` | Ajouter `failed_login_attempts`, `password_life_time`, `password_verify_function` |
| 11 | `test_oracle_pdb` | Activer les scénarios unplug/plug aujourd'hui en TODO |

### P3 — Administration avancée (cycle 3)

| # | Cible | Scénarios proposés |
|---|---|---|
| 12 | `test_oracle_privs` | Compléter par rapport à `oracle_grant` : WITH ADMIN / WITH GRANT OPTION granulaires |
| 13 | `test_oracle_acl` | host ACL create/absent, principals, privilèges (connect/resolve) |
| 14 | `test_oracle_redo` | add/drop redo log group, standby redo log, resize |
| 15 | `test_oracle_services` | Service DB create/start/stop/drop via `DBMS_SERVICE` |
| 16 | `test_oracle_rsrc_plan` | create simple plan, activate/deactivate |
| 17 | `test_oracle_rsrc_consgroup` | create/delete consumer group, rattachement à un plan |
| 18 | `test_oracle_stats_prefs` | set/reset des global stats preferences |

### P4 — Documentation

- Maintenir la section 5 (modules non testables) à jour.
- Pointer les utilisateurs CRS vers `tests/integration/integration_config.yml.template.crs`.

---

## 7. Patterns à suivre pour toute nouvelle cible

- `defaults/main.yml` : réutiliser les YAML anchors `&con_param_sys` / `&con_param_sys_pdb` / `&con_param_normal` (voir `test_oracle_user/defaults/main.yml`, `test_oracle_tnsnames/defaults/main.yml`).
- `tasks/main.yml` : bloc `include_tasks` conditionné par les flags `running_on_*` (cohérent avec les tests existants).
- Assertions : `register` + `failed_when` + contrôle du `.changed` + ré-exécution pour vérifier l'idempotence (cf. `test_oracle_tablespace`, `test_oracle_grant`).
- Nettoyage systématique via `cleanup.yml` (ex. `test_oracle_wallet/tasks/cleanup.yml`) ou bloc `always`.
- Ajouter la nouvelle cible dans :
  - la boucle `for ROLE in …` du `Makefile` (cibles `test-docker` et `test-docker-ee`)
  - la matrice du workflow `.github/workflows/integration.yml`

---

## 8. Vérification

1. `docker compose up -d` puis `make test ROLE=test_oracle_<nom>` localement jusqu'à succès + idempotence.
2. `make test-docker` intégral vert (tous modules, anciens + nouveaux).
3. Push + vérification du job GitHub Actions `integration.yml`.
4. Les tests unitaires (`pytest`) doivent rester ≥ 80 % de couverture.
