#!/bin/sh
# Restauración aislada. Crea volúmenes y contenedores propios y los retira al terminar.
# No ejecuta docker compose down -v y no toca healthcare-deploy-001 ni el laboratorio.
set -eu
if command -v cygpath >/dev/null 2>&1; then
  export MSYS2_ARG_CONV_EXCL='*'
  winpath() { cygpath -m "$1"; }
else
  winpath() { printf '%s\n' "$1"; }
fi
started=$(date +%s)
project="hc-deploy-restore-$$"
dump=$(mktemp)
password_file=$(mktemp)
trap 'rm -f "$password_file" "$dump"; docker rm -f "$project-src" "$project-dst" >/dev/null 2>&1 || true; docker volume rm "$project-pg-src" "$project-pg-dst" "$project-sqlite" >/dev/null 2>&1 || true; docker network rm "$project-net" >/dev/null 2>&1 || true' EXIT
umask 077
od -An -N18 -tx1 /dev/urandom | tr -d ' \n' > "$password_file"
if [ ! -s "$password_file" ]; then
  echo "restore=FAIL reason=secret_unavailable" >&2
  exit 1
fi

docker network create "$project-net" >/dev/null
docker volume create "$project-pg-src" >/dev/null
docker volume create "$project-pg-dst" >/dev/null
docker volume create "$project-sqlite" >/dev/null

run_pg() {
  name="$1"
  volume="$2"
  docker run -d --name "$name" --network "$project-net" \
    -e POSTGRES_DB=lab \
    -e POSTGRES_USER=lab \
    -e POSTGRES_PASSWORD_FILE=/run/secret \
    -v "$volume:/var/lib/postgresql/data" \
    -v "$(winpath "$password_file"):/run/secret:ro" \
    postgres:16.10-alpine >/dev/null
}

wait_pg() {
  name="$1"
  i=0
  while [ "$i" -lt 45 ]; do
    if docker exec "$name" pg_isready -U lab -d lab >/dev/null 2>&1; then
      return 0
    fi
    i=$((i + 1))
    sleep 1
  done
  echo "restore=FAIL reason=postgres_unavailable" >&2
  docker logs "$name" 2>&1 | grep -vi password | tail -n 20 >&2 || true
  exit 1
}

run_pg "$project-src" "$project-pg-src"
wait_pg "$project-src"
sql=$(mktemp)
cat > "$sql" <<'EOF'
CREATE TABLE drill(id text primary key, marker text not null);
INSERT INTO drill VALUES ('case-deploy-001','synthetic-order-kept');
EOF
docker exec -i "$project-src" sh -c 'PGPASSWORD=$(cat /run/secret) psql -U lab -d lab -v ON_ERROR_STOP=1' < "$sql" >/dev/null
rm -f "$sql"
docker exec "$project-src" sh -c 'PGPASSWORD=$(cat /run/secret) pg_dump -U lab -d lab' > "$dump"
bytes=$(wc -c < "$dump" | tr -d ' ')
sum=$(sha256sum "$dump" | awk '{print $1}')
if ! grep -q 'synthetic-order-kept' "$dump"; then
  echo "restore=FAIL reason=dump_missing_marker" >&2
  exit 1
fi

run_pg "$project-dst" "$project-pg-dst"
wait_pg "$project-dst"
docker exec -i "$project-dst" sh -c 'PGPASSWORD=$(cat /run/secret) psql -U lab -d lab -v ON_ERROR_STOP=1' < "$dump" >/dev/null
found=$(docker exec "$project-dst" sh -c 'PGPASSWORD=$(cat /run/secret) psql -U lab -d lab -tA -c "SELECT marker FROM drill WHERE id='"'"'case-deploy-001'"'"';"')
found=$(printf '%s' "$found" | tr -d '[:space:]')
if [ "$found" != "synthetic-order-kept" ]; then
  echo "restore=FAIL reason=marker_missing" >&2
  exit 1
fi

docker run --rm -v "$project-sqlite:/data" python:3.13-slim \
  python -c "import sqlite3; c=sqlite3.connect('/data/live.sqlite'); c.execute('create table drill(id text primary key, marker text)'); c.execute(\"insert into drill values ('case-deploy-001','synthetic-order-kept')\"); c.commit(); b=sqlite3.connect('/data/copy.sqlite'); c.backup(b); b.close(); c.close()"
sqlite_marker=$(docker run --rm -v "$project-sqlite:/data:ro" python:3.13-slim \
  python -c "import sqlite3; print(sqlite3.connect('/data/copy.sqlite').execute(\"select marker from drill\").fetchone()[0])")
if [ "$sqlite_marker" != "synthetic-order-kept" ]; then
  echo "restore=FAIL reason=sqlite_marker" >&2
  exit 1
fi

elapsed=$(( $(date +%s) - started ))
stats=$(docker stats --no-stream --format 'mem={{.MemUsage}} cpu={{.CPUPerc}}' "$project-dst")
rm -f "$dump"
echo "backup=PASS bytes=$bytes sha256=$sum"
echo "restore=PASS elapsed_seconds=$elapsed postgres=synthetic-order-kept sqlite=synthetic-order-kept"
echo "rollback_drill=PASS method=second_volume_not_source"
echo "resource_sample=$stats"
