# Load deterministic synthetic FHIR resources into local HAPI FHIR.
# Requires the FHIR server at http://localhost:8080/fhir
param(
    [string]$FhirBaseUrl = "http://localhost:8080/fhir"
)

$ErrorActionPreference = "Stop"
$files = Get-ChildItem -Path $PSScriptRoot -Filter *.json | Sort-Object {
    if ($_.Name -like "patient-*") { "0-$($_.Name)" } else { "1-$($_.Name)" }
}

foreach ($file in $files) {
    $json = Get-Content -Raw -Path $file.FullName | ConvertFrom-Json
    $uri = "$FhirBaseUrl/$($json.resourceType)/$($json.id)"
    Write-Host "PUT $uri"
    Invoke-RestMethod -Method Put -Uri $uri -ContentType "application/fhir+json" -InFile $file.FullName | Out-Null
}

Write-Host "Synthetic FHIR resources loaded from $PSScriptRoot"
