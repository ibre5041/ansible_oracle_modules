#!/bin/bash -x

podman pull gvenzl/oracle-free:23-full

podman run -d --name oracle-free \
  -p 1521:1521 -p 5500:5500 \
  -e ORACLE_PASSWORD='Oracle_4U' \
  gvenzl/oracle-free:23-full


cp tests/integration/integration_config.yml.docker \
   ~/.ansible/collections/ansible_collections/ibre5041/ansible_oracle_modules/tests/integration/integration_config.yml

export CONTAINER_ID=$(docker ps -q --filter "ancestor=gvenzl/oracle-free:23-full")
podman exec "$CONTAINER_ID" /bin/rm -rf /opt/oracle/admin/FREE/wallet
podman exec "$CONTAINER_ID" /bin/mkdir -p /opt/oracle/admin/FREE/wallet
podman exec "$CONTAINER_ID" /bin/chown oracle:oinstall /opt/oracle/admin/FREE/wallet
podman exec "$CONTAINER_ID" /bin/chmod 0700 /opt/oracle/admin/FREE/wallet
podman exec "$CONTAINER_ID" /bin/rm -f /tmp/testpdb2_unplug.xml

FAILED_ROLES=()
for ROLE in \
    test_oracle_ping \
	test_oracle_tnsnames \
        test_oracle_sql \
        test_oracle_awr \
        test_oracle_directory \
        test_oracle_profile \
        test_oracle_role \
        test_oracle_user \
        test_oracle_tablespace \
        test_oracle_parameter \
        test_oracle_pdb \
        test_oracle_facts; do
    echo ""
    echo "════════════════════════════════════════"
    echo "  Running: $ROLE"
    echo "════════════════════════════════════════"
    make test ROLE=$ROLE || FAILED_ROLES+=($ROLE)
done

if [ ${#FAILED_ROLES[@]} -gt 0 ]; then
    echo ""
    echo "FAILED roles: ${FAILED_ROLES[*]}"
    exit 1
fi
