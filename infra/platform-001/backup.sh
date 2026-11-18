#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
dest=${PLATFORM_RUN_DIR:-/tmp/platform-001/run}/backup
mkdir -p "$dest/pe" "$dest/es"
docker compose -f "$here/compose.yaml" cp ai-pe:/var/lab/ledger/platform-last.json "$dest/pe/platform-last.json"
docker compose -f "$here/compose.yaml" cp ai-pe:/var/lab/ledger/backup "$dest/pe/backup"
docker compose -f "$here/compose.yaml" cp ai-es:/var/lab/ledger/platform-last.json "$dest/es/platform-last.json"
docker compose -f "$here/compose.yaml" cp ai-es:/var/lab/ledger/backup "$dest/es/backup"
