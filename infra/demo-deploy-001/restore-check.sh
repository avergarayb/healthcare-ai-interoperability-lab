#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
export DEMO_RUN_DIR="${DEMO_RUN_DIR:-${TMPDIR:-/tmp}/demo-deploy-001/run}"
root="$DEMO_RUN_DIR/backup"
test -s "$root/keycloak.sql"
python3 "$here/verify_restore.py" "$root"
compose="docker compose -f $here/compose.yaml --profile peru --profile spain"
$compose exec -T keycloak-db sh -c 'PGPASSWORD=$(cat /run/secrets/db_password) psql -U keycloak -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS keycloak_restore_check"'
$compose exec -T keycloak-db sh -c 'PGPASSWORD=$(cat /run/secrets/db_password) psql -U keycloak -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE keycloak_restore_check"'
$compose exec -T keycloak-db sh -c 'PGPASSWORD=$(cat /run/secrets/db_password) psql -U keycloak -d keycloak_restore_check -v ON_ERROR_STOP=1' < "$root/keycloak.sql" >/dev/null
realms=$(printf '%s\n' "SELECT count(*) FROM realm WHERE name = 'demo-deploy';" | $compose exec -T keycloak-db sh -c 'PGPASSWORD=$(cat /run/secrets/db_password) psql -U keycloak -d keycloak_restore_check -tA')
$compose exec -T keycloak-db sh -c 'PGPASSWORD=$(cat /run/secrets/db_password) psql -U keycloak -d postgres -c "DROP DATABASE keycloak_restore_check"' >/dev/null
$compose exec -T ai-pe python /opt/demo/consume_check.py /var/lab/backup/pe-ledger pe-longitudinal-001
$compose exec -T ai-es python /opt/demo/consume_check.py /var/lab/backup/es-ledger es-longitudinal-001
echo "restore_check=passed demo_deploy_realms=$(echo "$realms" | tr -d '[:space:]')"
