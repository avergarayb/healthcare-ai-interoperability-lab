#!/bin/sh
set -eu
. "$(CDPATH= cd -- "$(dirname "$0")" && pwd)/lib.sh"
"$here/prepare.sh" >/dev/null

if [ "$DEPLOY_PROFILE" = "longitudinal" ]; then
  echo "longitudinal=delegated package=infra/demo-deploy-001"
  echo "Perú y España siguen en su Compose aislado. Este perfil no crea otro realm ni otro volumen."
  exit 0
fi

compose up -d caddy keycloak-db minilis-db
if [ "$DEPLOY_PROFILE" != "maintenance" ]; then
  compose up -d keycloak
fi
echo "start=dependencies profile=$DEPLOY_PROFILE"
if [ "$DEPLOY_PROFILE" = "maintenance" ]; then
  exit 0
fi

echo "start=waiting_for_caddy_ca"
i=0
while [ "$i" -lt 30 ]; do
  if compose cp caddy:/data/caddy/pki/authorities/local/root.crt "$DEPLOY_RUN_DIR/caddy-root.crt" 2>/dev/null; then
    break
  fi
  i=$((i + 1))
  sleep 2
done
if ! grep -q "BEGIN CERTIFICATE" "$DEPLOY_RUN_DIR/caddy-root.crt"; then
  die "caddy_ca_unavailable"
fi
compose up -d
echo "start=requested profile=$DEPLOY_PROFILE"
