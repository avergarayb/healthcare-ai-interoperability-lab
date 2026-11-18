param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("prepare", "hospital", "hospital-down", "longitudinal")]
    [string]$Action,
    [string]$CaseId = ""
)

$ErrorActionPreference = "Stop"
$Project = "demo-catalog-hospital"
if ($env:COMPOSE_PROJECT_NAME -in @("platform-001", "demo-deploy-001")) {
    throw "Refusing to touch a historical compose project."
}
$env:COMPOSE_PROJECT_NAME = $Project
$env:CATALOG_RUN_DIR = Join-Path $env:TEMP "demo-catalog-001\run"
$compose = Join-Path $PSScriptRoot "compose.yaml"

function New-Secret([string]$Name) {
    $path = Join-Path $env:CATALOG_RUN_DIR $Name
    if (-not (Test-Path $path)) {
        $bytes = New-Object byte[] 24
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        [Convert]::ToBase64String($bytes) | Set-Content -Path $path -NoNewline
    }
}

switch ($Action) {
    "prepare" {
        New-Item -ItemType Directory -Force -Path $env:CATALOG_RUN_DIR | Out-Null
        foreach ($name in @("his-token", "lis-token", "federation-token", "hl7-secret", "db-password")) {
            New-Secret $name
        }
        Write-Output "prepared run directory outside the repository"
    }
    "hospital" {
        if (-not $CaseId) {
            $token = [guid]::NewGuid().ToString("N").Substring(0, 6)
            $CaseId = "catalog-" + (Get-Date -Format "yyyyMMddHHmmssfff") + "-" + $token
        }
        $env:CATALOG_CASE_ID = $CaseId
        docker compose -f $compose up -d lis-db mini-lis mini-his federation
        docker compose -f $compose --profile run run --rm operator
    }
    "hospital-down" {
        if ($Project -notlike "demo-catalog-*") { throw "Refusing to stop a non-catalog project." }
        if ($env:CATALOG_EPHEMERAL -ne "true") {
            docker compose -f $compose stop
            Write-Output "stopped without deleting volumes"
        } else {
            docker compose -f $compose down
            Write-Output "removed catalog containers and the catalog network; volumes remain"
        }
    }
    "longitudinal" {
        Write-Output "DEMO-002 uses infra/demo-deploy-001 with a new project name demo-catalog-longitudinal."
        Write-Output "Do not set COMPOSE_PROJECT_NAME to demo-deploy-001 or platform-001."
        Write-Output "A consumed permit on an existing volume cannot be rerun. Use a fresh DEMO_RUN_DIR and fresh volumes."
    }
}
