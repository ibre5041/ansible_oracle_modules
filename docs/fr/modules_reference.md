# Documentation FR des modules Oracle

La documentation est maintenant decoupee en **un fichier Markdown par module** sous `docs/fr/modules/`.

Chaque fichier suit le template:
- Description
- Utilisation
- Exemples (plusieurs cas representatifs)

## Conventions de connexion

- Connexion distante PDB: `hostname`, `port`, `service_name`, `username`, `password`.
- Connexion locale CDB vers PDB: connexion locale puis `ALTER SESSION SET CONTAINER=<PDB>`.
- Parametre unifie: `session_container` pour forcer le container de session sur les modules DB.
- `mode: sysdba` uniquement pour les operations d'administration.

## Index des modules

- [`oracle_acfs`](modules/oracle_acfs.md)
- [`oracle_asmdg`](modules/oracle_asmdg.md)
- [`oracle_asmvol`](modules/oracle_asmvol.md)
- [`oracle_awr`](modules/oracle_awr.md)
- [`oracle_crs_asm`](modules/oracle_crs_asm.md)
- [`oracle_crs_db`](modules/oracle_crs_db.md)
- [`oracle_crs_listener`](modules/oracle_crs_listener.md)
- [`oracle_crs_service`](modules/oracle_crs_service.md)
- [`oracle_datapatch`](modules/oracle_datapatch.md)
- [`oracle_db`](modules/oracle_db.md)
- [`oracle_directory`](modules/oracle_directory.md)
- [`oracle_facts`](modules/oracle_facts.md)
- [`oracle_gi_facts`](modules/oracle_gi_facts.md)
- [`oracle_grant`](modules/oracle_grant.md)
- [`oracle_job`](modules/oracle_job.md)
- [`oracle_jobclass`](modules/oracle_jobclass.md)
- [`oracle_jobschedule`](modules/oracle_jobschedule.md)
- [`oracle_jobwindow`](modules/oracle_jobwindow.md)
- [`oracle_ldapuser`](modules/oracle_ldapuser.md)
- [`oracle_opatch`](modules/oracle_opatch.md)
- [`oracle_oratab`](modules/oracle_oratab.md)
- [`oracle_parameter`](modules/oracle_parameter.md)
- [`oracle_pdb`](modules/oracle_pdb.md)
- [`oracle_ping`](modules/oracle_ping.md)
- [`oracle_privs`](modules/oracle_privs.md)
- [`oracle_profile`](modules/oracle_profile.md)
- [`oracle_redo`](modules/oracle_redo.md)
- [`oracle_role`](modules/oracle_role.md)
- [`oracle_rsrc_consgroup`](modules/oracle_rsrc_consgroup.md)
- [`oracle_services`](modules/oracle_services.md)
- [`oracle_sql`](modules/oracle_sql.md)
- [`oracle_sqldba`](modules/oracle_sqldba.md)
- [`oracle_stats_prefs`](modules/oracle_stats_prefs.md)
- [`oracle_tablespace`](modules/oracle_tablespace.md)
- [`oracle_tnsnames`](modules/oracle_tnsnames.md)
- [`oracle_user`](modules/oracle_user.md)
