param([ValidateSet("pe-lab-demo-v1", "es-lab-demo-v1")][string]$Profile = "pe-lab-demo-v1")
$ErrorActionPreference = "Stop"
$service = $(if ($Profile -eq "pe-lab-demo-v1") { "ai-pe" } else { "ai-es" })
docker compose -f (Join-Path $PSScriptRoot "compose.yaml") exec -T $service python /opt/platform/recover.py
exit $LASTEXITCODE
