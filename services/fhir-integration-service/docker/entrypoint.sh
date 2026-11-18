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
if [ -s /run/secrets/his_token ]; then
  EXCHANGE_MINI_HIS_TOKEN=$(cat /run/secrets/his_token)
  export EXCHANGE_MINI_HIS_TOKEN
fi
if [ -s /run/secrets/lis_token ]; then
  CLINICAL_READ_MINI_LIS_SERVICE_TOKEN=$(cat /run/secrets/lis_token)
  export CLINICAL_READ_MINI_LIS_SERVICE_TOKEN
fi
if [ -s /run/secrets/hl7_secret ]; then
  EXCHANGE_MINI_LIS_HL7_SECRET=$(cat /run/secrets/hl7_secret)
  export EXCHANGE_MINI_LIS_HL7_SECRET
fi
echo "platform_start service=federation profile=${JURISDICTION_LAB_PROFILE:-unset} external=false"
exec java -XX:MaxRAMPercentage=75 -jar /app/fhir-integration-service.jar
