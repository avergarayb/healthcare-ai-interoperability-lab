#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
export DEMO_MODE="${DEMO_MODE:-local}"
export DEMO_RUN_DIR="${DEMO_RUN_DIR:-${TMPDIR:-/tmp}/demo-deploy-001/run}"
python="$here/../../services/ai-service/.venv/bin/python"
if [ ! -x "$python" ]; then
  python=python3
fi
"$python" "$here/prepare.py"
"$python" "$here/preflight.py"
docker compose -f "$here/compose.yaml" --profile peru --profile spain up -d --build "$@"
