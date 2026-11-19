#!/bin/sh
set -eu

here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
root=$(CDPATH= cd -- "$here/.." && pwd)
repo=$(CDPATH= cd -- "$root/../.." && pwd)
export DEPLOY_RUN_DIR="${DEPLOY_RUN_DIR:-$root/run}"
export DEPLOY_PROFILE="${DEPLOY_PROFILE:-hospital}"

compose() {
  docker compose -p healthcare-deploy-001 -f "$root/compose.yaml" --profile "$DEPLOY_PROFILE" "$@"
}

new_secret() {
  od -An -N24 -tx1 /dev/urandom | tr -d ' \n'
}

write_secret() {
  name="$1"
  path="$DEPLOY_RUN_DIR/secrets/$name"
  if [ -s "$path" ]; then
    return 0
  fi
  umask 077
  new_secret > "$path"
  chmod 600 "$path" 2>/dev/null || true
}

die() {
  echo "deploy_error=$1" >&2
  exit 1
}
