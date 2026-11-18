param([ValidateSet("pe-lab-demo-v1", "es-lab-demo-v1")][string]$Profile = "pe-lab-demo-v1")
$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
if (-not $env:PLATFORM_RUN_DIR) {
    $env:PLATFORM_RUN_DIR = Join-Path $env:TEMP "platform-001\run"
}
$service = $(if ($Profile -eq "pe-lab-demo-v1") { "ai-pe" } else { "ai-es" })
$compose = Join-Path $Here "compose.yaml"
docker compose -f $compose exec -T $service python /opt/platform/e2e.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker compose -f $compose exec -T $service python /opt/platform/probe.py
exit $LASTEXITCODE
