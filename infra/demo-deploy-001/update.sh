#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
export DEMO_RUN_DIR="${DEMO_RUN_DIR:-${TMPDIR:-/tmp}/demo-deploy-001/run}"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
record="$DEMO_RUN_DIR/image-ids"
mkdir -p "$record"
for image in demo-deploy-ai:0.1.0 demo-deploy-federation:0.1.0; do
  safe=$(printf '%s' "$image" | tr ':/' '--')
  docker image inspect "$image" --format '{{.Id}}' > "$record/${safe}-${stamp}.txt"
done
echo "previous_image_id_recorded=$stamp"
echo "same_tag_rebuild_is_not_a_version_rollback"
sh "$here/backup.sh"
sh "$here/up.sh"
echo "update=images_rebuilt"
echo "rollback=retarget_the_recorded_image_id_and_restore_the_backup_if_a_database_migration_ran"
