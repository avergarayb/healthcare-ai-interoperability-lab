# Load deterministic synthetic Patient resources into local HAPI FHIR.
# Requires the FHIR server at http://localhost:8080/fhir
param(
    [string]$FhirBaseUrl = "http://localhost:8080/fhir"
)

$ErrorActionPreference = "Stop"
$patients = @(
    (Join-Path $PSScriptRoot "patient-001.json"),
    (Join-Path $PSScriptRoot "patient-002.json"),
    (Join-Path $PSScriptRoot "patient-003.json")
)

foreach ($file in $patients) {
    $id = [System.IO.Path]::GetFileNameWithoutExtension($file)
    $uri = "$FhirBaseUrl/Patient/$id"
    Write-Host "PUT $uri"
    Invoke-RestMethod -Method Put -Uri $uri -ContentType "application/fhir+json" -InFile $file | Out-Null
}

Write-Host "Synthetic patients loaded: patient-001, patient-002, patient-003"
