# oracle_ldapuser

## Description
Synchronise des utilisateurs LDAP vers Oracle (creation, update, verrouillage/suppression selon politique).

## Utilisation
Utiliser pour gerer des comptes bases sur annuaire et roles associes.
Pour une connexion locale CDB vers un PDB, utiliser `session_container` pour appliquer `ALTER SESSION SET CONTAINER`.

## Exemples
```yaml
- name: Synchronisation LDAP standard
  oracle_ldapuser:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    ldap_connect: ldaps://ldap.example.net:636
    ldap_binddn: "CN=svc_ldap,OU=Svc,DC=example,DC=net"
    ldap_bindpassword: "{{ vault_ldap_bind_password }}"
    ldap_user_basedn: "OU=Users,DC=example,DC=net"
```

```yaml
- name: Mapping groupes LDAP -> roles Oracle
  oracle_ldapuser:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    ldap_connect: ldaps://ldap.example.net:636
    ldap_binddn: "CN=svc_ldap,OU=Svc,DC=example,DC=net"
    ldap_bindpassword: "{{ vault_ldap_bind_password }}"
    ldap_user_basedn: "OU=Users,DC=example,DC=net"
    group_role_map:
      - dn: "CN=APP-READ,OU=Groups,DC=example,DC=net"
        group: APP_READONLY
```

```yaml
- name: Verrouiller les utilisateurs absents de LDAP
  oracle_ldapuser:
    hostname: db01
    service_name: apppdb1
    user: system
    password: "{{ vault_db_password }}"
    ldap_connect: ldaps://ldap.example.net:636
    ldap_binddn: "CN=svc_ldap,OU=Svc,DC=example,DC=net"
    ldap_bindpassword: "{{ vault_ldap_bind_password }}"
    ldap_user_basedn: "OU=Users,DC=example,DC=net"
    deleted_user_mode: lock
```
