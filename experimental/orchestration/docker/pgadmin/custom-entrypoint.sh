#!/bin/sh
set -eu

cat > /tmp/servers.json <<EOF
{
  "Servers": {
    "1": {
      "Name": "AMLGuardian Postgres",
      "Group": "Servers",
      "Host": "${POSTGRES_HOST}",
      "Port": ${POSTGRES_PORT},
      "MaintenanceDB": "${POSTGRES_DB}",
      "Username": "${POSTGRES_USER}",
      "SSLMode": "prefer",
      "PassFile": "/tmp/pgpassfile"
    }
  }
}
EOF

printf '%s:%s:*:%s:%s\n' "${POSTGRES_HOST}" "${POSTGRES_PORT}" "${POSTGRES_USER}" "${POSTGRES_PASSWORD}" > /tmp/pgpassfile
chmod 600 /tmp/pgpassfile

exec /entrypoint.sh
