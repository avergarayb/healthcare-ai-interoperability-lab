# Creates or updates only the hospital-lab realm through the Admin API.
# It does not restart Keycloak, does not replace volumes, and does not print passwords.
param(
    [string]$Server = "http://127.0.0.1:18340",
    [string]$AdminPasswordFile = "",
    [string]$UserPassword = $env:HOSPITAL_OIDC_USER_PASSWORD
)
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($UserPassword) -or $UserPassword -eq "REPLACE_AT_IMPORT") {
    throw "HOSPITAL_OIDC_USER_PASSWORD is required and is not printed."
}
if ([string]::IsNullOrWhiteSpace($AdminPasswordFile) -or -not (Test-Path $AdminPasswordFile)) {
    throw "Pass -AdminPasswordFile for the existing bootstrap user. The password is not requested in chat."
}
$realmPath = Resolve-Path (Join-Path $PSScriptRoot "..\..\infra\healthcare-security-001\realm-hospital.json")
$raw = Get-Content -Raw -Path $realmPath
if ($raw -notmatch "REPLACE_AT_IMPORT") { throw "The realm file no longer has the password placeholder." }
$admin = (Get-Content -Raw $AdminPasswordFile).Trim()
$body = "grant_type=password&client_id=admin-cli&username=platform-001-bootstrap&password=" + [uri]::EscapeDataString($admin)
try {
    $tokenResponse = Invoke-RestMethod -Method Post -Uri "$Server/realms/master/protocol/openid-connect/token" -ContentType "application/x-www-form-urlencoded" -Body $body
} catch {
    throw "Keycloak admin login failed. The password was not printed."
}
$headers = @{ Authorization = "Bearer $($tokenResponse.access_token)" }
$before = Invoke-RestMethod -Headers $headers -Uri "$Server/admin/realms/platform-001/clients"
$beforeIds = @($before | ForEach-Object { $_.clientId }) | Sort-Object
$existing = $null
try {
    $existing = Invoke-RestMethod -Headers $headers -Uri "$Server/admin/realms/hospital-lab"
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw }
}
$representation = $raw.Replace("REPLACE_AT_IMPORT", $UserPassword) | ConvertFrom-Json
if ($null -eq $existing) {
    try {
        Invoke-RestMethod -Method Post -Headers $headers -Uri "$Server/admin/realms" -ContentType "application/json" -Body ($raw.Replace("REPLACE_AT_IMPORT", $UserPassword)) | Out-Null
    } catch {
        throw "Creating hospital-lab failed. The request body was not printed."
    }
} else {
    foreach ($client in $representation.clients) {
        $found = Invoke-RestMethod -Headers $headers -Uri "$Server/admin/realms/hospital-lab/clients?clientId=$($client.clientId)"
        if (@($found).Count -eq 0) {
            Invoke-RestMethod -Method Post -Headers $headers -Uri "$Server/admin/realms/hospital-lab/clients" -ContentType "application/json" -Body ($client | ConvertTo-Json -Depth 8) | Out-Null
        } else {
            $current = $found[0]
            $current.redirectUris = @($client.redirectUris)
            $current.webOrigins = @($client.webOrigins)
            $current.protocolMappers = @($client.protocolMappers)
            Invoke-RestMethod -Method Put -Headers $headers -Uri "$Server/admin/realms/hospital-lab/clients/$($current.id)" -ContentType "application/json" -Body ($current | ConvertTo-Json -Depth 8) | Out-Null
        }
    }
}
$after = Invoke-RestMethod -Headers $headers -Uri "$Server/admin/realms/platform-001/clients"
$afterIds = @($after | ForEach-Object { $_.clientId }) | Sort-Object
if (($beforeIds -join ",") -ne ($afterIds -join ",")) { throw "platform-001 clients changed. Stopping." }
$hospital = Invoke-RestMethod -Headers $headers -Uri "$Server/admin/realms/hospital-lab/clients"
$ids = @($hospital | ForEach-Object { $_.clientId })
foreach ($required in @("mini-his-web", "mini-lis-web", "hospital-ai")) {
    if ($ids -notcontains $required) { throw "Missing client $required" }
}
Write-Output "hospital-lab ready. platform-001 clients unchanged."
