- https://astoradba.wordpress.com/2021/02/09/how-to-disable-mgmtdb/
- crsctl stop res ora.crf -init -f -unsupported
- crsctl modify resource ora.crf -attr AUTO_START=never -init -unsupported

- module.no_log_values = frozenset({ password })
  from ansible.module_utils.basic import heuristic_log_sanitize
  msg = heuristic_log_sanitize('token="secret", user="person", token_entry="test=secret"', frozenset(['secret']))

- oracle_db - create cluster database
- oracle_db - module password/username ==> connect via listener
- oracle_db - -enableArchive
- oracle_db_home - add option for RO ORACLE_HOME
  ./bin/roohctl -enable  -nodeList rac19-b-node-1,rac19-b-node-2
  ./bin/roohctl -disable -nodeList rac19-b-node-1,rac19-b-node-2

- adrpure: ADR base = "/oracle/u01/base" + show home | grep SID => alert log location

        fatal: [rac19-b-node-1]: FAILED! => {"changed": false, "msg": "Could not connect to database - ORA-12541: TNS:no listener, connect descriptor: (DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=localhost)(PORT=1521))(CONNECT_DATA=(SERVICE_NAME=TEST19C_1)))"}

- setcap cap_net_raw+ep  /usr/bin/ping (on Centos8)

- export CV_ASSUME_DISTID=RHEL8
- /etc/init.d/init.ohasd: Error: Full cgroupv2 environment not supported 
  Cluster Fails to Start With "/etc/init.d/init.ohasd: Waiting for ohasd.bin PID <PID> to move" Message in /var/log/messages After Enabling CGroup v2 (Doc ID 2941336.1)
  How to enable cgroup-v1 in Red Hat Enterprise Linux 9

  [ $(stat -fc %T /sys/fs/cgroup/) = "cgroup2fs" ] && echo "unified" || ( [ -e /sys/fs/cgroup/unified/ ] && echo "hybrid" || echo "legacy")
  grubby --update-kernel=/boot/vmlinuz-$(uname -r) --args="systemd.unified_cgroup_hierarchy=0 systemd.legacy_systemd_cgroup_controller"

