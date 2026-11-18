#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
export DEMO_RUN_DIR="${DEMO_RUN_DIR:-${TMPDIR:-/tmp}/demo-deploy-001/run}"
docker compose -f "$here/compose.yaml" --profile peru --profile spain down
