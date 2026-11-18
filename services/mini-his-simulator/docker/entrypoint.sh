#!/bin/sh
set -eu
if [ ! -s /run/secrets/his_token ]; then
  echo "catalog_start service=mini-his outcome=missing_token" >&2
  exit 1
fi
MINI_HIS_EXCHANGE_TOKEN=$(cat /run/secrets/his_token)
export MINI_HIS_EXCHANGE_TOKEN
echo "catalog_start service=mini-his bind=${MINI_HIS_ALLOW_CONTAINER_BIND:-false}"
exec java -jar /app/mini-his-simulator.jar
