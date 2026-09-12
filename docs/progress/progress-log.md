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

## Task 053 — Controlled projection for Epic Sandbox

- Status: COMPLETED
- Destination: `epic-sandbox`
- Authentication: existing SMART Authorization Code + PKCE
- Operation: generic `ClinicalProjectionAssembler` over Patient read, Condition search, Observation search (`vital-signs`), and DiagnosticReport search
- Allowlist: exact Task 042 fields (`Patient.resourceType`, `Condition.clinicalStatusCode`, `Observation.status`, `DiagnosticReport.status`)
- MedicationRequest is omitted (`ClinicalSnapshotContents.withoutMedicationRequests()`); absence is not rewritten as an empty collection
- Lab page: `GET /epic/sandbox/fhir/clinical-projection`
- The page maps the projection through `ModelBoundaryMapper` and `AgentStub.observe` without an `EpicModelBoundaryService`
- `GET /api/model-boundary/v1` remains the Oracle-backed machine surface until Task 054
- Epic sandbox live result:
  - HTTP 200
  - `clinicalSnapshot=SUCCEEDED`
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `modelBoundary=SUCCEEDED`
  - `agentStub=SUCCEEDED`
  - `sensitiveFieldsExposed=false`
  - `rawFhirExposed=false`
  - `hasClinicalData=true`
- No resource-specific FHIR client was added. There is no `EpicProjectionClient` or `EpicControlledProjection`
- Reused existing generic abstractions: `ClinicalProjectionAssembler`, `ClinicalProjectionMapper`, `RetentionCeiling`, `ModelBoundaryMapper`, and `AgentStub`

## Task 054 — Agent stub consumes Model Boundary Contract v1

- Status: COMPLETED
- Destination: vendor-neutral `AgentStub` over Epic (`epic-sandbox`) and Oracle (`oracle-health-sandbox`) contracts
- The stub now rejects non-`v1` versions and complete/partial contracts missing Patient or included collections
- `hasClinicalData` is derived from retained counts; record values are not republished
- Epic `MedicationRequest` remains `null`; Oracle may include MedicationRequest
- `GET /api/model-boundary/v1` and `GET /lab/agent-stub` stay Oracle-backed
- Epic laboratory confirmation remains `GET /epic/sandbox/fhir/clinical-projection`
- Epic sandbox live result:
  - HTTP 200
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `modelBoundary=SUCCEEDED`
  - `agentStub=SUCCEEDED`
  - `sensitiveFieldsExposed=false`
  - `rawFhirExposed=false`
  - `hasClinicalData=true`
- No `EpicAgentStub`, `OracleAgentStub`, LLM, or real agent was added
- Allowlist 042 was not expanded
- `.env` was not modified

## Task 055 — Oracle/Epic contract compatibility

- Status: IMPLEMENTED (pending live)
- Shared v1 invariants are documented in `docs/fhir/model-boundary-contract-v1.md`
- Allowed difference: Epic `MedicationRequest=null`; Oracle may include MedicationRequest
- Same `AgentStub` consumes both destinations; no `if Epic` / `if Oracle` in mapper or stub
- Shared tests: `OracleEpicContractCompatibilityTest` and assembler retention for both contents
- `GET /api/model-boundary/v1` and `GET /lab/agent-stub` stay Oracle-backed
- Epic laboratory confirmation remains `GET /epic/sandbox/fhir/clinical-projection`
- Allowlist 042 was not expanded; MedicationRequest was not added to Epic
- No LLM or real agent was added
- `.env` was not modified

## Task 056 — Safe pipeline error handling

- Status: COMPLETED
- `mvn test`: 686/0
- Epic sandbox live result (`GET /epic/sandbox/fhir/clinical-projection`, HTTP 200):
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `agentStub=SUCCEEDED`
  - `hasClinicalData=true`
  - `pipelineStatus=SUCCESS`
  - `contractValid=true`
  - `usable=true`
  - `medicationRequestsPipeline=NOT_REQUESTED`
- Package `lab.healthcare.fhir.pipeline` aggregates vendor-neutral stage statuses
- Critical stages: patient, snapshot/projection, contract, agentStub
- Non-critical collections: Condition, Observation, DiagnosticReport, MedicationRequest
- Expected absence (`MedicationRequest=null` on Epic) is `NOT_REQUESTED`, not a failure
- Non-critical timeout or unavailable stays `PARTIAL` and usable
- Invalid contract is `REJECTED`; critical patient failure is `FAILED`
- `ClinicalSnapshotResourceStatus.TIMEOUT` is a persisted operational status, not a new v1 field
- Epic pages add `pipelineStatus`, `contractValid`, `usable`, and per-stage pipeline lines without replacing existing blind fields
- Controllers log `SafePipelineLog` lines only (no tokens, Patient IDs, or FHIR JSON)
- `GET /api/model-boundary/v1` and `GET /lab/agent-stub` stay Oracle-backed
- Allowlist 042 was not expanded; no LLM or real agent was added
- `.env` was not modified

## Task 057 — Deterministic agent

- Status: COMPLETED
- `mvn test`: 699/0
- Epic sandbox live result (`GET /epic/sandbox/fhir/clinical-projection`, HTTP 200):
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `agentStub=SUCCEEDED`
  - `hasClinicalData=true`
  - `pipelineStatus=SUCCESS`
  - `deterministicAgent=READY`
  - `agentReason=READY_FOR_BOUNDARY`
  - `requiresHumanReview=true`
  - `agentModelCalled=false`
  - `warnings=not-requested:medicationRequests`
- Package `lab.healthcare.fhir.agent` evaluates Model Boundary Contract v1 plus `PipelineDiagnosis`
- Decisions: `READY`, `BLOCKED`, `REQUIRES_HUMAN_REVIEW`
- Invalid contract or unusable pipeline is `BLOCKED`; empty clinical data or `PARTIAL` is `REQUIRES_HUMAN_REVIEW`
- `requiresHumanReview=true` and `modelCalled=false` on every verdict
- Warnings are operational codes only (`truncated:conditions`, `not-requested:medicationRequests`)
- Lab surfaces: `GET /lab/deterministic-agent`, `GET /api/deterministic-agent/v1` (Oracle-backed provider)
- Epic confirmation remains `GET /epic/sandbox/fhir/clinical-projection`
- AgentStub is reused for contract validation; no LLM, RAG, or vendor client
- Allowlist 042 was not expanded
- `.env` was not modified
