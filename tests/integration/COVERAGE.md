# Integration Test Coverage

Reference document for the `ibre5041.ansible_oracle_modules` collection.
Lists all 45 modules, their integration test target (if any), the scenarios covered, and Docker CI status.

**CI environment**: `gvenzl/oracle-free:23-full` — CDB `FREE` + PDB `FREEPDB1`, TCP-only client connection.  
**Docker constraints**: no ASM, no Grid Infrastructure / CRS, no Data Guard standby, no OPatch, no local OS access (`running_on_client: true`, `running_on_server: false`).

---

## Module reference

| Module | Test target | Docker CI | Scenarios covered |
|---|---|:---:|---|
| `oracle_acfs` | — | ❌ | Not testable: requires ASM |
| `oracle_acl` | `test_oracle_acl` | ✅ | — |
| `oracle_asmdg` | — | ❌ | Not testable: requires ASM |
| `oracle_asmvol` | — | ❌ | Not testable: requires ASM |
| `oracle_audit` | `test_oracle_audit` | ✅ | — |
| `oracle_awr` | `test_oracle_awr` | ✅ | Basic AWR interval query (`simple.yml`) |
| `oracle_crs_asm` | `test_oracle_crs_asm` | ❌ | Not testable: requires Grid Infrastructure (skeleton target only) |
| `oracle_crs_db` | `test_oracle_crs_db` | ❌ | Not testable: requires CRS (skeleton target only) |
| `oracle_crs_listener` | `test_oracle_crs_listener` | ❌ | Not testable: requires CRS (conditional target) |
| `oracle_crs_service` | `test_oracle_crs_service` | ❌ | Not testable: requires CRS (conditional target) |
| `oracle_dataguard` | `test_oracle_dataguard` | ✅ | Broker status / config / enable (skipped if orapki absent); full standby not possible in Docker |
| `oracle_datapatch` | — | ❌ | Not testable: requires a patch to apply |
| `oracle_db` | `test_oracle_db` | ❌ | Not testable: requires DBCA / full DB creation (skeleton target only) |
| `oracle_dblink` | `test_oracle_dblink` | ✅ | — |
| `oracle_directory` | `test_oracle_directory` | ✅ | create, replace path, drop, check_mode, DDL validation |
| `oracle_facts` | `test_oracle_facts` | ✅ | Compile check, subset parameter/content, no-sysdba mode |
| `oracle_flashback` | `test_oracle_flashback` | ✅ | — |
| `oracle_gi_facts` | `test_oracle_gi_facts` | ❌ | Not testable: requires Grid Infrastructure (conditional target) |
| `oracle_grant` | `test_oracle_grant` | ✅ | append/remove/replace system privileges; append/remove/replace object privileges; roles; directories; ADB checks; issue-6 regression; check_mode |
| `oracle_job` | `test_oracle_job` | ✅ | — |
| `oracle_jobclass` | `test_oracle_jobclass` | ✅ | — |
| `oracle_jobschedule` | `test_oracle_jobschedule` | ✅ | — |
| `oracle_jobwindow` | `test_oracle_jobwindow` | ✅ | — |
| `oracle_ldapuser` | — | ❌ | Not testable: requires LDAP / Active Directory server |
| `oracle_opatch` | — | ❌ | Not testable: requires OPatch and a patched Oracle home |
| `oracle_orapki` | `test_oracle_orapki` | ✅ | wallet create, certificates, secrets, cleanup |
| `oracle_oratab` | — | ❌ | Not testable: requires local OS access (`running_on_server`) |
| `oracle_parameter` | `test_oracle_parameter` | ✅ | modify / reset; scope memory / spfile / both; numeric, boolean, string types; CDB-only parameter; no-sysdba mode |
| `oracle_pdb` | `test_oracle_pdb` | ✅ | create / delete; existence check; open / close; read_only; clone; exclusive options; check_mode |
| `oracle_ping` | `test_oracle_ping` | ✅ | SYSDBA local (A1), SYSDBA remote (A2), session_container CDB→PDB (B), normal user (C) |
| `oracle_privs` | `test_oracle_privs` | ✅ | — |
| `oracle_profile` | `test_oracle_profile` | ✅ | Basic profile create/modify (`simple.yml`), issue-4 regression |
| `oracle_quota` | `test_oracle_quota` | ✅ | — (no standalone `oracle_quota` module; target tests tablespace quota via `oracle_user`) |
| `oracle_redo` | — | ❌ | Not testable: `ALTER DATABASE ADD LOGFILE` without explicit path fails ORA-02236 even with OMF configured (Oracle 26ai Free limitation) |
| `oracle_role` | `test_oracle_role` | ✅ | create / delete, idempotence, identified methods, check_mode |
| `oracle_rsrc_consgroup` | `test_oracle_rsrc_consgroup` | ✅ | — |
| `oracle_rsrc_plan` | `test_oracle_rsrc_plan` | ✅ | — |
| `oracle_services` | `test_oracle_services` | ✅ | create / start / stop / status / drop; check_mode; idempotence; non-GI (DBMS_SERVICE) path |
| `oracle_sql` | `test_oracle_sql` | ✅ | SELECT, DDL, PL/SQL block, SQL file execution, DBMS_OUTPUT, special cases, check_mode, ORA-942 error handling |
| `oracle_sqldba` | — | ❌ | Not testable: requires local sqlplus / catcon.pl |
| `oracle_stats_prefs` | `test_oracle_stats_prefs` | ✅ | — |
| `oracle_tablespace` | `test_oracle_tablespace` | ✅ | create/drop permanent / undo / temp; bigfile; multi-datafile; modify; check_mode (create + drop); error handling; null values; idempotence |
| `oracle_tde` | `test_oracle_tde` | ✅ | keystore setup, master key, tablespace encrypt / rekey / decrypt, status, cleanup |
| `oracle_tnsnames` | `test_oracle_tnsnames` | ✅ | parse alias, attribute add/remove, paths, SQLNET parameters, global modifications, listener, check_mode, idempotence |
| `oracle_user` | `test_oracle_user` | ✅ | create / delete / modify / change state / check_mode; auth password / external / none; default + temp tablespace; profile; lock; expire |
| `oracle_wallet` | `test_oracle_wallet` | ✅ | create, open/close, change password, backup, auto_login, secret, status, cleanup |

**Legend**: ✅ active in Docker CI (`make test-docker`) · ❌ not testable in Docker

> Targets without listed scenarios (`—`) have a test target wired into CI but the scenario detail has not yet been documented here.  
> For CRS-dependent modules, users with a RAC/Grid Infrastructure environment can use `tests/integration/integration_config.yml.template.crs`.
