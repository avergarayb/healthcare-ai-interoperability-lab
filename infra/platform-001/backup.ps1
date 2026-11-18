$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
if (-not $env:PLATFORM_RUN_DIR) {
    $env:PLATFORM_RUN_DIR = Join-Path $env:TEMP "platform-001\run"
}
$Destination = Join-Path $env:PLATFORM_RUN_DIR "backup"
New-Item -ItemType Directory -Force -Path (Join-Path $Destination "pe") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Destination "es") | Out-Null
$compose = Join-Path $Here "compose.yaml"
docker compose -f $compose cp ai-pe:/var/lab/ledger/platform-last.json (Join-Path $Destination "pe\platform-last.json")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker compose -f $compose cp ai-pe:/var/lab/ledger/backup (Join-Path $Destination "pe\backup")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker compose -f $compose cp ai-es:/var/lab/ledger/platform-last.json (Join-Path $Destination "es\platform-last.json")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker compose -f $compose cp ai-es:/var/lab/ledger/backup (Join-Path $Destination "es\backup")
exit $LASTEXITCODE
