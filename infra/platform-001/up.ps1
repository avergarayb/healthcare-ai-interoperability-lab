$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
$Repo = (Resolve-Path (Join-Path $Here "..\..")).Path
if (-not $env:PLATFORM_RUN_DIR) {
    $env:PLATFORM_RUN_DIR = Join-Path $env:TEMP "platform-001\run"
}
$Python = Join-Path $Repo "services\ai-service\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "The AI service virtualenv is required."
    exit 1
}
& $Python (Join-Path $Here "prepare.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker compose -f (Join-Path $Here "compose.yaml") up -d --build
exit $LASTEXITCODE
