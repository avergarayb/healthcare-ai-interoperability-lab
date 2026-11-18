#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
export DEMO_RUN_DIR="${DEMO_RUN_DIR:-${TMPDIR:-/tmp}/demo-deploy-001/run}"
dest="$DEMO_RUN_DIR/backup"
mkdir -p "$dest"
compose="docker compose -f $here/compose.yaml --profile peru --profile spain"

copy_sqlite() {
  service="$1"
  source="$2"
  name="$3"
  if ! $compose exec -T "$service" sh -c "test -f '$source'"; then
    echo "backup_skip=$name"
    return 0
  fi
  $compose exec -T "$service" python /opt/platform/sqlite_backup.py copy "$source" "/var/lab/backup/$name"
  rm -rf "$dest/$name"
  $compose cp "$service:/var/lab/backup/$name" "$dest/$name"
}

$compose exec -T keycloak-db \
  sh -c 'PGPASSWORD=$(cat /run/secrets/db_password) pg_dump -U keycloak -d keycloak' > "$dest/keycloak.sql"
copy_sqlite ai-pe /var/lab/ledger/pe-lab-demo-v1/processing.sqlite3 pe-ledger
copy_sqlite ai-es /var/lab/ledger/es-lab-demo-v1/processing.sqlite3 es-ledger
copy_sqlite ai-pe /var/lab/review/lab-summary.sqlite3 pe-review
copy_sqlite ai-es /var/lab/review/lab-summary.sqlite3 es-review
copy_sqlite ai-pe /var/lab/federation-audit/security-audit.sqlite pe-federation-audit
copy_sqlite ai-es /var/lab/federation-audit/security-audit.sqlite es-federation-audit
copy_sqlite ai-pe /var/lab/iam/session.sqlite3 pe-iam
copy_sqlite ai-es /var/lab/iam/session.sqlite3 es-iam
echo "backup=written"
