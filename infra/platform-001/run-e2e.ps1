param([ValidateSet("pe-lab-demo-v1", "es-lab-demo-v1")][string]$Profile = "pe-lab-demo-v1")
$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
$Repo = (Resolve-Path (Join-Path $Here "..\..")).Path
if (-not $env:PLATFORM_RUN_DIR) {
    $env:PLATFORM_RUN_DIR = Join-Path $env:TEMP "platform-001\run"
}
$Python = Join-Path $Repo "services\ai-service\.venv\Scripts\python.exe"
$pe = $Profile -eq "pe-lab-demo-v1"
$env:PLATFORM_PROFILE = $Profile
$env:PLATFORM_FEDERATION_URL = $(if ($pe) { "http://127.0.0.1:18481" } else { "http://127.0.0.1:18482" })
$env:PLATFORM_AI_URL = $(if ($pe) { "http://127.0.0.1:18493" } else { "http://127.0.0.1:18495" })
$env:PLATFORM_TOKEN_FILE = Join-Path $env:PLATFORM_RUN_DIR "federation-token"
$name = $(if ($pe) { "pe" } else { "es" })
$env:PLATFORM_LEDGER_ROOT = Join-Path $env:PLATFORM_RUN_DIR "$name-ledger"
$env:PLATFORM_REVIEW_DB = Join-Path $env:PLATFORM_RUN_DIR "$name-review.sqlite3"
New-Item -ItemType Directory -Force -Path $env:PLATFORM_LEDGER_ROOT | Out-Null
$env:PYTHONPATH = Join-Path $Repo "services\ai-service"
Push-Location (Join-Path $Repo "services\ai-service")
try {
    & $Python (Join-Path $Here "e2e.py")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
$service = $(if ($pe) { "ai-pe" } else { "ai-es" })
docker compose -f (Join-Path $Here "compose.yaml") cp $env:PLATFORM_REVIEW_DB "${service}:/var/lab/review/lab-summary.sqlite3"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker compose -f (Join-Path $Here "compose.yaml") exec -T $service python /opt/platform/probe.py
exit $LASTEXITCODE
