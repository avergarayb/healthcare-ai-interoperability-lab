# Progress log

Safe laboratory evidence only. Do not record tokens, Patient identifiers, FHIR JSON, codes, or clinical values.

## Task 051 — Epic authenticated DiagnosticReport search by Patient

- Status: COMPLETED
- Destination: `epic-sandbox`
- Authentication: existing SMART Authorization Code + PKCE
- Operation: authenticated DiagnosticReport search by the configured Patient
- Generic query: `patient` + `_count=5` (`_count=5` is a request, not a retention ceiling)
- Lab page: `GET /epic/sandbox/fhir/diagnostic-report-search`
- Epic sandbox live result:
  - HTTP 200
  - `diagnosticReportSearch=SUCCEEDED`
  - `hasEntries=true`
- No resource-specific FHIR client was added. There is no `EpicDiagnosticReportClient`.
- Reused existing generic abstractions: `RoutingService.searchDiagnosticReports` and `FhirService.searchDiagnosticReportsByPatientWithCount`.
- Commit: `feat: add Epic sandbox authenticated DiagnosticReport search by Patient`
- Change submitted via pull request

## Task 052 — Clinical snapshot for Epic Sandbox

- Status: COMPLETED
- Destination: `epic-sandbox`
- Authentication: existing SMART Authorization Code + PKCE
- Operation: generic `ClinicalSnapshotAssembler` over Patient read, Condition search, Observation search (`vital-signs`), and DiagnosticReport search
- MedicationRequest is omitted from this snapshot (`ClinicalSnapshotContents.withoutMedicationRequests()`)
- Lab page: `GET /epic/sandbox/fhir/clinical-snapshot`
- Epic sandbox live result:
  - HTTP 200
  - `clinicalSnapshot=SUCCEEDED`
  - `patientRead=SUCCEEDED`
  - `conditionSearch=SUCCEEDED`
  - `observationSearch=SUCCEEDED`
  - `diagnosticReportSearch=SUCCEEDED`
  - `hasClinicalData=true`
- No resource-specific FHIR client was added. There is no `EpicSnapshotClient`.
- Reused existing generic abstractions: `ClinicalSnapshotAssembler`, `RoutingService`, and `FhirService`
- Capability discovery uses the existing Task 047 path, not `RoutingService.discoverCapabilities("epic-sandbox")`
