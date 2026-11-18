#!/bin/sh
set -eu
if [ -x /usr/sbin/ip ]; then
  /usr/sbin/ip route del default || true
fi
mkdir -p /var/lab/federation-audit
if [ ! -s /run/secrets/federation_token ]; then
  echo "platform_start service=federation outcome=missing_token" >&2
  exit 1
fi
FEDERATION_MINI_HIS_TOKEN=$(cat /run/secrets/federation_token)
export FEDERATION_MINI_HIS_TOKEN
echo "platform_start service=federation profile=${JURISDICTION_LAB_PROFILE:-unset} external=false"
exec java -XX:MaxRAMPercentage=75 -jar /app/fhir-integration-service.jar
