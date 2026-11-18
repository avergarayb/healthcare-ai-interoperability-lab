$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
if (-not $env:PLATFORM_RUN_DIR) {
    $env:PLATFORM_RUN_DIR = Join-Path $env:TEMP "platform-001\run"
}
function Read-Local([string]$Url) {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
    if ($response.StatusCode -ne 200) {
        Write-Error "unhealthy $Url"
        exit 1
    }
    Write-Output "$Url $($response.StatusCode)"
}
Read-Local "http://127.0.0.1:18481/actuator/health"
Read-Local "http://127.0.0.1:18482/actuator/health"
Read-Local "http://127.0.0.1:18493/health"
Read-Local "http://127.0.0.1:18495/health"
docker compose -f (Join-Path $Here "compose.yaml") ps
exit $LASTEXITCODE
