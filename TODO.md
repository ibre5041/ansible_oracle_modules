
- oracle_db - create cluster database
- oracle_db - module password/username ==> connect via listener

        fatal: [rac19-b-node-1]: FAILED! => {"changed": false, "msg": "Could not connect to database - ORA-12541: TNS:no listener, connect descriptor: (DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=localhost)(PORT=1521))(CONNECT_DATA=(SERVICE_NAME=TEST19C_1)))"}

- setcap cap_net_raw+ep  /usr/bin/ping (on Centos8)

