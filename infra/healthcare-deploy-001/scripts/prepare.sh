#!/bin/sh
set -eu
. "$(CDPATH= cd -- "$(dirname "$0")" && pwd)/lib.sh"

case "$DEPLOY_RUN_DIR" in
  *platform-001*|*local-hapi*|*demo-deploy-001*)
    die "run_dir_refuses_existing_project"
    ;;
esac

umask 077
mkdir -p "$DEPLOY_RUN_DIR/secrets" "$DEPLOY_RUN_DIR/backup"
for name in db_password bootstrap_password his_token lis_token hl7_secret federation_token boundary_token signing_secret user_password; do
  write_secret "$name"
done

if [ ! -s "$DEPLOY_RUN_DIR/caddy-root.crt" ]; then
  printf '%s\n' "placeholder" > "$DEPLOY_RUN_DIR/caddy-root.crt"
fi
cp "$repo/infra/healthcare-security-001/bindings.json" "$DEPLOY_RUN_DIR/bindings.json"

user_password=$(cat "$DEPLOY_RUN_DIR/secrets/user_password")
sed \
  -e 's|https://127.0.0.1:8445|https://127.0.0.1:18445|g' \
  -e 's|https://127.0.0.1:8444|https://127.0.0.1:18444|g' \
  -e "s|REPLACE_AT_IMPORT|$user_password|g" \
  "$repo/infra/healthcare-security-001/realm-hospital.json" > "$DEPLOY_RUN_DIR/realm-hospital.json"
chmod 600 "$DEPLOY_RUN_DIR/realm-hospital.json" "$DEPLOY_RUN_DIR/secrets/"* 2>/dev/null || true
echo "prepare=ready profile=$DEPLOY_PROFILE run_dir=configured"
