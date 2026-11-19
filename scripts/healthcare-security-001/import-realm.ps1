# Imports the hospital realm into the existing laboratory Keycloak.
# Does not print passwords, does not delete realms, and does not restart the server.
param(
    [string]$Container = "",
    [string]$AdminPasswordFile = "",
    [string]$UserPassword = $env:HOSPITAL_OIDC_USER_PASSWORD
)
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($UserPassword)) {
    throw "HOSPITAL_OIDC_USER_PASSWORD is required and is not printed."
}
if ($UserPassword -eq "REPLACE_AT_IMPORT") {
    throw "Choose a password that is not the placeholder."
}
$realmFile = Join-Path $PSScriptRoot "..\..\infra\healthcare-security-001\realm-hospital.json"
$raw = Get-Content -Raw -Path (Resolve-Path $realmFile)
if ($raw -notmatch "REPLACE_AT_IMPORT") {
    throw "The realm file no longer has the password placeholder. Refusing to import."
}
$temp = Join-Path $env:TEMP ("hospital-realm-" + [guid]::NewGuid().ToString() + ".json")
try {
    [IO.File]::WriteAllText($temp, $raw.Replace("REPLACE_AT_IMPORT", $UserPassword))
    if (-not $Container) {
        $Container = (docker ps --format "{{.Names}}" | Where-Object { $_ -like "*keycloak*" } | Select-Object -First 1)
    }
    if (-not $Container) { throw "No running Keycloak container. The existing server was not started or reset." }
    if (-not $AdminPasswordFile) { throw "Pass -AdminPasswordFile. The script does not search for secrets." }
    $admin = (Get-Content -Raw $AdminPasswordFile).Trim()
    docker cp $temp "${Container}:/tmp/hospital-realm.json" | Out-Null
    docker exec $Container /opt/keycloak/bin/kcadm.sh config credentials --server http://127.0.0.1:8080 --realm master --user platform-001-bootstrap --password $admin | Out-Null
    docker exec $Container /opt/keycloak/bin/kcadm.sh create realms -f /tmp/hospital-realm.json
    docker exec $Container rm -f /tmp/hospital-realm.json | Out-Null
    Write-Output "hospital-lab imported into the existing Keycloak. Peru and Spain realms were not modified."
}
finally {
    if (Test-Path $temp) { Remove-Item -Force $temp }
}
