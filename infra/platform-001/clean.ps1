param([switch]$Confirm)
$ErrorActionPreference = "Stop"
if (-not $Confirm) {
    Write-Error "Pass -Confirm to remove only Docker volumes whose names start with platform-001_."
    exit 2
}
if (-not $env:PLATFORM_RUN_DIR) {
    $env:PLATFORM_RUN_DIR = Join-Path $env:TEMP "platform-001\run"
}
docker compose -f (Join-Path $PSScriptRoot "compose.yaml") down
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$names = @(docker volume ls --format "{{.Name}}")
foreach ($name in $names) {
    if ($name.StartsWith("platform-001_")) {
        docker volume rm $name
    }
}
