$ErrorActionPreference = "Stop"
if (-not $env:PLATFORM_RUN_DIR) {
    $env:PLATFORM_RUN_DIR = Join-Path $env:TEMP "platform-001\run"
}
docker compose -f (Join-Path $PSScriptRoot "compose.yaml") down
exit $LASTEXITCODE
