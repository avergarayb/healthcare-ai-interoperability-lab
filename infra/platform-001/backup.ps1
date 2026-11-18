$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
$Repo = (Resolve-Path (Join-Path $Here "..\..")).Path
if (-not $env:PLATFORM_RUN_DIR) {
    $env:PLATFORM_RUN_DIR = Join-Path $env:TEMP "platform-001\run"
}
$Destination = Join-Path $env:PLATFORM_RUN_DIR "backup"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
docker compose -f (Join-Path $Here "compose.yaml") cp ai-pe:/var/lab/platform-last.json $Destination
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker compose -f (Join-Path $Here "compose.yaml") cp ai-pe:/var/lab/backup $Destination
exit $LASTEXITCODE
