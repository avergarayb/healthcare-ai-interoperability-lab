#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
profile=${1:-pe-lab-demo-v1}
case "$profile" in
  pe-lab-demo-v1) service=ai-pe ;;
  es-lab-demo-v1) service=ai-es ;;
  *) echo "profile_rejected" >&2; exit 1 ;;
esac
docker compose -f "$here/compose.yaml" exec -T "$service" python /opt/platform/recover.py
