#!/usr/bin/env bash
set -eux

# Find Oracle container
ORACLE_CONTAINER=$(docker ps -q --filter "ancestor=gvenzl/oracle-free:23-full" 2>/dev/null | head -1)
if [ -z "$ORACLE_CONTAINER" ]; then
    echo "SKIP: Oracle container not found"
    exit 0
fi

# Detect Python interpreter inside the container
PYTHON_INTERP=""
for p in /usr/bin/python3 /usr/libexec/platform-python; do
    if docker exec "$ORACLE_CONTAINER" "$p" --version &>/dev/null; then
        PYTHON_INTERP="$p"
        break
    fi
done
if [ -z "$PYTHON_INTERP" ]; then
    echo "SKIP: No Python interpreter found in container"
    exit 0
fi

# Build temporary inventory
INVENTORY=$(mktemp)
trap 'rm -f "$INVENTORY"' EXIT
cat > "$INVENTORY" <<EOF
oracle ansible_connection=community.docker.docker ansible_host=$ORACLE_CONTAINER ansible_python_interpreter=$PYTHON_INTERP
EOF

ansible-playbook runme.yml -i "$INVENTORY" -e @../../integration_config.yml -v
