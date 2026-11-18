$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Service = Join-Path $Repo "services\ai-service"
$Python = Join-Path $Service ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "The AI service virtualenv is required."
    exit 1
}
if (-not $env:PLATFORM_PYTEST_BASE) {
    $env:PLATFORM_PYTEST_BASE = Join-Path $env:TEMP "platform-001\pytest"
}
New-Item -ItemType Directory -Force -Path $env:PLATFORM_PYTEST_BASE | Out-Null
Push-Location $Service
try {
    & $Python -m pytest --basetemp $env:PLATFORM_PYTEST_BASE @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
