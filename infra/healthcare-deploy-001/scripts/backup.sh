#!/bin/sh
set -eu
. "$(CDPATH= cd -- "$(dirname "$0")" && pwd)/lib.sh"
"$here/prepare.sh" >/dev/null

stamp=$(date -u +%Y%m%dT%H%M%SZ)
dest="$DEPLOY_RUN_DIR/backup/$stamp"
mkdir -p "$dest"
manifest="$dest/manifest.txt"
: > "$manifest"

record() {
  file="$1"
  bytes=$(wc -c < "$file" | tr -d ' ')
  sum=$(sha256sum "$file" | awk '{print $1}')
  printf 'file=%s bytes=%s sha256=%s\n' "$(basename "$file")" "$bytes" "$sum" >> "$manifest"
}

dump_postgres() {
  service="$1"
  database="$2"
  user="$3"
  out="$dest/$database.sql"
  compose exec -T "$service" sh -c "PGPASSWORD=\$(cat //run/secrets/db_password) pg_dump -U $user -d $database" > "$out"
  record "$out"
}

dump_postgres keycloak-db keycloak keycloak
dump_postgres minilis-db minilis minilis

backup_volume() {
  volume="$1"
  source="$2"
  name="$3"
  docker run --rm \
    -v "${volume}:/data:ro" \
    -v "$dest:/backup" \
    python:3.13-slim \
    python -c "import sqlite3,sys; src,dst=sys.argv[1],sys.argv[2];
con=sqlite3.connect(src); out=sqlite3.connect(dst); con.backup(out); out.close(); con.close()" \
    "/data/$source" "/backup/$name"
  record "$dest/$name"
}

project=healthcare-deploy-001
backup_volume "${project}_his-data" mini-his.sqlite his.sqlite || echo "backup_skip=his"
backup_volume "${project}_exchange-data" exchange/correlation.sqlite exchange.sqlite || echo "backup_skip=exchange"
backup_volume "${project}_ai-data" ledger/hospital-lab/processing.sqlite3 ai-ledger.sqlite || echo "backup_skip=ai-ledger"

{
  echo "id=$stamp"
  echo "created=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "profile=$DEPLOY_PROFILE"
  echo "result=written"
} >> "$manifest"
echo "backup=written id=$stamp"
