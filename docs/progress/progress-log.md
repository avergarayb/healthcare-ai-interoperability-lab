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

## Task 058 — AI boundary preparation

- Status: COMPLETED
- `mvn test`: 711/0
- Epic sandbox live result (`GET /epic/sandbox/fhir/clinical-projection`, HTTP 200):
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `agentStub=SUCCEEDED`
  - `deterministicAgent=READY`
  - `aiBoundary=PREPARED`
  - `clinicalDataAvailable=true`
  - `modelCallAuthorized=false`
  - `aiModelCalled=false`
  - `medicationRequestsStatus=NOT_REQUESTED`
- Package `lab.healthcare.fhir.aiboundary` copies Model Boundary Contract v1 metadata plus `DeterministicAgentResult`
- `AiBoundaryMapper` does not call `DeterministicAgent.evaluate` or `AgentStub.observe`
- Separated judgments: pipeline status, clinical data availability, agent decision
- `READY` does not authorize a model: `modelCallAuthorized=false`, `modelCalled=false`, `requiresHumanReview=true`
- MedicationRequest absence stays `NOT_REQUESTED`
- New lab surfaces: `GET /lab/ai-boundary`, `GET /api/ai-boundary/v1` (Oracle-backed provider)
- Epic confirmation remains `GET /epic/sandbox/fhir/clinical-projection` and now also shows `aiBoundary=PREPARED`
- No Python `ai-service`, LLM, RAG, or vendor client was added
- Allowlist 042 was not expanded
- `.env` was not modified

## Task 059 — First isolated AI component

- Status: COMPLETED
- `mvn test`: 725/0
- Epic sandbox live result (`GET /epic/sandbox/fhir/clinical-projection`, HTTP 200):
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `agentStub=SUCCEEDED`
  - `deterministicAgent=READY`
  - `aiBoundary=PREPARED`
  - `clinicalDataAvailable=true`
  - `modelCallAuthorized=false`
  - `aiModelCalled=false`
  - `medicationRequestsStatus=NOT_REQUESTED`
  - `firstAiComponent=PREPARED`
  - `aiProcessingStatus=NOT_EXECUTED`
- Isolation option: package `lab.healthcare.fhir.firstai` inside `fhir-integration-service` because the repository has no separate AI module yet and a Python `ai-service` is out of scope
- The component consumes only `AiBoundaryResult`. `FirstAiMapper` / `FirstAiComponent` do not call `DeterministicAgent.evaluate` or `AgentStub.observe`
- `READY` stays distinct from model authorization: `componentStatus=PREPARED`, `processingStatus=NOT_EXECUTED`, `modelCallAuthorized=false`, `modelCalled=false`, `requiresHumanReview=true`
- MedicationRequest absence stays `NOT_REQUESTED`
- Existing confirmation surface reused: `GET /epic/sandbox/fhir/clinical-projection`
- New lab surfaces were required because `/lab/ai-boundary` exposes the boundary payload, not the first AI component result: `GET /lab/first-ai-component`, `GET /api/first-ai-component/v1` (Oracle-backed provider)
- No Python `ai-service`, LLM, RAG, LangGraph, or vendor client was added
- Allowlist 042 was not expanded
- `.env` was not modified

## Task 060 — AI execution gate

- Status: COMPLETED
- `mvn test`: 740/0
- Epic sandbox live result (`GET /epic/sandbox/fhir/clinical-projection`, HTTP 200):
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `agentStub=SUCCEEDED`
  - `deterministicAgent=READY`
  - `aiBoundary=PREPARED`
  - `clinicalDataAvailable=true`
  - `modelCallAuthorized=false`
  - `aiModelCalled=false`
  - `medicationRequestsStatus=NOT_REQUESTED`
  - `firstAiComponent=PREPARED`
  - `aiProcessingStatus=NOT_EXECUTED`
  - `aiExecutionGate=ELIGIBLE_BUT_NOT_AUTHORIZED`
- Package `lab.healthcare.fhir.aigateway` consumes only `FirstAiResult`
- `AiExecutionMapper` / `AiExecutionGate` do not call `DeterministicAgent.evaluate` or `AgentStub.observe`
- `READY` + `PREPARED` + clinical data is `ELIGIBLE_BUT_NOT_AUTHORIZED`; that is not model permission
- Premature `modelCallAuthorized=true` is rejected with `PREMATURE_MODEL_AUTHORIZATION`, not normalized to `false`
- `modelCalled=false`, `modelCallAuthorized=false`, `processingStatus=NOT_EXECUTED`, `requiresHumanReview=true`
- MedicationRequest absence stays `NOT_REQUESTED`
- Existing confirmation surface reused: `GET /epic/sandbox/fhir/clinical-projection` now also shows `aiExecutionGate=ELIGIBLE_BUT_NOT_AUTHORIZED`
- New lab surfaces were required because `/lab/first-ai-component` exposes the first AI result, not the gate: `GET /lab/ai-execution-gate`, `GET /api/ai-execution-gate/v1` (Oracle-backed provider)
- No Python `ai-service`, LLM, RAG, LangGraph, or vendor client was added
- Allowlist 042 was not expanded
- `.env` was not modified

## Task 061 — AI Consumer Contract v1

- Status: COMPLETED
- `mvn test`: 755/0
- Epic sandbox live result (`GET /epic/sandbox/fhir/clinical-projection`, HTTP 200):
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `agentStub=SUCCEEDED`
  - `deterministicAgent=READY`
  - `aiBoundary=PREPARED`
  - `clinicalDataAvailable=true`
  - `modelCallAuthorized=false`
  - `aiModelCalled=false`
  - `medicationRequestsStatus=NOT_REQUESTED`
  - `firstAiComponent=PREPARED`
  - `aiProcessingStatus=NOT_EXECUTED`
  - `aiExecutionGate=ELIGIBLE_BUT_NOT_AUTHORIZED`
  - `aiConsumerContract=v1`
  - `aiConsumerStatus=READY`
  - `aiDispatchStatus=NOT_DISPATCHED`
- Package `lab.healthcare.fhir.aiconsumer` consumes only `AiExecutionDecision`
- `AiConsumerContractMapper` / `AiConsumerContractService` do not call `DeterministicAgent.evaluate`, `AgentStub.observe`, or any HTTP client
- `ELIGIBLE_BUT_NOT_AUTHORIZED` becomes `contractStatus=READY` and `dispatchStatus=NOT_DISPATCHED`; that is not model permission and not delivery
- Premature `modelCallAuthorized=true` is rejected with `PREMATURE_MODEL_AUTHORIZATION`, not normalized to `false`
- `modelCalled=false`, `modelCallAuthorized=false`, `processingStatus=NOT_EXECUTED`, `requiresHumanReview=true`
- MedicationRequest absence stays `NOT_REQUESTED`
- Future consumer authentication, scopes, tenant, and schema checks are documented in `docs/fhir/ai-consumer-contract-v1.md` and are not implemented
- Existing confirmation surface reused: `GET /epic/sandbox/fhir/clinical-projection` now also shows `aiConsumerContract=v1`, `aiConsumerStatus=READY`, and `aiDispatchStatus=NOT_DISPATCHED`
- New lab surfaces were required because `/lab/ai-execution-gate` exposes the gate, not the contract: `GET /lab/ai-consumer-contract`, `GET /api/ai-consumer-contract/v1` (Oracle-backed provider)
- No Python `ai-service`, LLM, RAG, LangGraph, HTTP dispatch, or vendor client was added
- Allowlist 042 was not expanded
- `.env` was not modified

## Task 062 — AI consumer policy

- Status: COMPLETED
- `mvn test`: 774/0
- Epic sandbox live result (`GET /epic/sandbox/fhir/clinical-projection`, HTTP 200):
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `agentStub=SUCCEEDED`
  - `deterministicAgent=READY`
  - `aiBoundary=PREPARED`
  - `clinicalDataAvailable=true`
  - `modelCallAuthorized=false`
  - `aiModelCalled=false`
  - `medicationRequestsStatus=NOT_REQUESTED`
  - `firstAiComponent=PREPARED`
  - `aiProcessingStatus=NOT_EXECUTED`
  - `aiExecutionGate=ELIGIBLE_BUT_NOT_AUTHORIZED`
  - `aiConsumerContract=v1`
  - `aiConsumerStatus=READY`
  - `aiDispatchStatus=NOT_DISPATCHED`
  - `aiConsumerPolicy=ALLOWED_FOR_FUTURE_CONSUMPTION`
- Package `lab.healthcare.fhir.aiconsumerpolicy` consumes only `AiConsumerContract` plus synthetic consumer metadata
- Obligatory human review that blocks consumption is `contractStatus=REQUIRES_HUMAN_REVIEW`; the boolean `requiresHumanReview=true` stays copied and does not by itself block `ALLOWED_FOR_FUTURE_CONSUMPTION`
- Allowed future consumption is not dispatch and not model authorization
- Premature `modelCallAuthorized=true` remains rejected at the 061 contract constructor
- `DISPATCH_TO_AI_SERVICE` is `DISPATCH_NOT_SUPPORTED`; other non-read operations are `OPERATION_NOT_ALLOWED`
- `modelCalled=false`, `modelCallAuthorized=false`, `processingStatus=NOT_EXECUTED`, `dispatchStatus=NOT_DISPATCHED`, `requiresHumanReview=true`
- Existing confirmation surface reused: `GET /epic/sandbox/fhir/clinical-projection` now also shows `aiConsumerPolicy=ALLOWED_FOR_FUTURE_CONSUMPTION`
- New lab surfaces: `GET /lab/ai-consumer-policy`, `GET /api/ai-consumer-policy/v1` (Oracle-backed provider, synthetic `lab-consumer`)
- Policy rules are documented in `docs/fhir/ai-consumer-policy.md`
- No Python `ai-service`, real OAuth, LLM, RAG, HTTP dispatch, or vendor client was added
- Allowlist 042 was not expanded
- `.env` was not modified

## Task 063 — AI consumer readiness

- Status: COMPLETED
- `mvn test`: 793/0
- Epic sandbox live result (`GET /epic/sandbox/fhir/clinical-projection`, HTTP 200):
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `agentStub=SUCCEEDED`
  - `deterministicAgent=READY`
  - `aiBoundary=PREPARED`
  - `clinicalDataAvailable=true`
  - `modelCallAuthorized=false`
  - `aiModelCalled=false`
  - `medicationRequestsStatus=NOT_REQUESTED`
  - `firstAiComponent=PREPARED`
  - `aiProcessingStatus=NOT_EXECUTED`
  - `aiExecutionGate=ELIGIBLE_BUT_NOT_AUTHORIZED`
  - `aiConsumerContract=v1`
  - `aiConsumerStatus=READY`
  - `aiDispatchStatus=NOT_DISPATCHED`
  - `aiConsumerPolicy=ALLOWED_FOR_FUTURE_CONSUMPTION`
  - `aiConsumerReadiness=READY_FOR_FUTURE_HANDOFF`
- Package `lab.healthcare.fhir.aiconsumerreadiness` consumes only `AiConsumerPolicyResult`
- `READY_FOR_FUTURE_HANDOFF` is not handoff authorization and not dispatch
- Inconsistent execution flags are detected and blocked; they are not silently corrected
- `handoffAuthorized=false`, `dispatchPerformed=false`, `modelCallAuthorized=false`, `modelCalled=false`, `processingStatus=NOT_EXECUTED`, `dispatchStatus=NOT_DISPATCHED`, `requiresHumanReview=true`
- Existing confirmation surface reused: `GET /epic/sandbox/fhir/clinical-projection` now also shows `aiConsumerReadiness=READY_FOR_FUTURE_HANDOFF`
- New lab surfaces: `GET /lab/ai-consumer-readiness`, `GET /api/ai-consumer-readiness/v1` (Oracle-backed provider, synthetic `lab-consumer`)
- Readiness rules are documented in `docs/fhir/ai-consumer-readiness.md`
- No Python `ai-service`, real OAuth, LLM, RAG, HTTP dispatch, handoff, or vendor client was added
- Allowlist 042 was not expanded
- `.env` was not modified

## Task 064 — AI handoff authorization boundary

- Status: COMPLETED
- `mvn test`: 812/0
- Epic sandbox live result (`GET /epic/sandbox/fhir/clinical-projection`, HTTP 200):
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `agentStub=SUCCEEDED`
  - `deterministicAgent=READY`
  - `aiBoundary=PREPARED`
  - `clinicalDataAvailable=true`
  - `modelCallAuthorized=false`
  - `aiModelCalled=false`
  - `medicationRequestsStatus=NOT_REQUESTED`
  - `firstAiComponent=PREPARED`
  - `aiProcessingStatus=NOT_EXECUTED`
  - `aiExecutionGate=ELIGIBLE_BUT_NOT_AUTHORIZED`
  - `aiConsumerContract=v1`
  - `aiConsumerStatus=READY`
  - `aiDispatchStatus=NOT_DISPATCHED`
  - `aiConsumerPolicy=ALLOWED_FOR_FUTURE_CONSUMPTION`
  - `aiConsumerReadiness=READY_FOR_FUTURE_HANDOFF`
  - `aiHandoffAuthorization=HANDOFF_NOT_AUTHORIZED`
- Package `lab.healthcare.fhir.aihandoffauthorization` consumes only `AiConsumerReadinessResult`
- Deny-by-default: `READY_FOR_FUTURE_HANDOFF` still yields `HANDOFF_NOT_AUTHORIZED` / `REAL_AUTHORIZATION_NOT_IMPLEMENTED`
- Query parameters and headers cannot activate authorization
- Inconsistent execution flags are detected and blocked; they are not silently corrected
- `externalAuthorizationAvailable=false`, `handoffAuthorized=false`, `dispatchPerformed=false`, `modelCallAuthorized=false`, `modelCalled=false`, `processingStatus=NOT_EXECUTED`, `dispatchStatus=NOT_DISPATCHED`, `requiresHumanReview=true`
- Existing confirmation surface reused: `GET /epic/sandbox/fhir/clinical-projection` now also shows `aiHandoffAuthorization=HANDOFF_NOT_AUTHORIZED`
- New lab surfaces: `GET /lab/ai-handoff-authorization`, `GET /api/ai-handoff-authorization/v1` (Oracle-backed provider)
- Authorization rules are documented in `docs/fhir/ai-handoff-authorization-boundary.md`
- No Python `ai-service`, real OAuth, JWT, LLM, RAG, HTTP dispatch, handoff, or vendor client was added
- Allowlist 042 was not expanded
- `.env` was not modified

## Task 065 — AI consumer authorization boundary

- Status: COMPLETED
- `mvn test`: 827/0
- Epic sandbox live result (`GET /epic/sandbox/fhir/clinical-projection`, HTTP 200):
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `agentStub=SUCCEEDED`
  - `deterministicAgent=READY`
  - `aiBoundary=PREPARED`
  - `clinicalDataAvailable=true`
  - `modelCallAuthorized=false`
  - `aiModelCalled=false`
  - `medicationRequestsStatus=NOT_REQUESTED`
  - `firstAiComponent=PREPARED`
  - `aiProcessingStatus=NOT_EXECUTED`
  - `aiExecutionGate=ELIGIBLE_BUT_NOT_AUTHORIZED`
  - `aiConsumerContract=v1`
  - `aiConsumerStatus=READY`
  - `aiDispatchStatus=NOT_DISPATCHED`
  - `aiConsumerPolicy=ALLOWED_FOR_FUTURE_CONSUMPTION`
  - `aiConsumerReadiness=READY_FOR_FUTURE_HANDOFF`
  - `aiHandoffAuthorization=HANDOFF_NOT_AUTHORIZED`
  - `aiConsumerAuthentication=NOT_AUTHENTICATED`
  - `aiConsumerAuthorization=AUTHORIZATION_NOT_IMPLEMENTED`
  - `aiConsumerAuthorizationAvailable=false`
- Package `lab.healthcare.fhir.aiconsumerauthorization` consumes only `AiHandoffAuthorizationResult` plus a synthetic `ConsumerSecurityContext`
- Deny-by-default: a valid 064 result still yields `AUTHORIZATION_NOT_IMPLEMENTED`
- Declared identity is `NOT_AUTHENTICATED`; conceptual scope is `NOT_AUTHORIZED`; untrusted `true` assertions are `BLOCKED`
- Query parameters and headers cannot activate authentication or authorization
- `authenticationVerified=false`, `authorizationGranted=false`, `realSecurityProviderConfigured=false`, `consumerAuthorizationAvailable=false`, `handoffAuthorized=false`, `dispatchPerformed=false`, `externalAuthorizationAvailable=false`, `modelCallAuthorized=false`, `modelCalled=false`, `processingStatus=NOT_EXECUTED`, `dispatchStatus=NOT_DISPATCHED`, `requiresHumanReview=true`
- Existing confirmation surface reused: `GET /epic/sandbox/fhir/clinical-projection` now also shows `aiConsumerAuthentication=NOT_AUTHENTICATED`, `aiConsumerAuthorization=AUTHORIZATION_NOT_IMPLEMENTED`, `aiConsumerAuthorizationAvailable=false`
- New lab surfaces: `GET /lab/ai-consumer-authorization`, `GET /api/ai-consumer-authorization/v1` (Oracle-backed provider)
- Authorization rules are documented in `docs/fhir/ai-consumer-authorization-boundary.md`
- No Python `ai-service`, real OAuth, JWT, SMART, LLM, RAG, HTTP dispatch, handoff, or vendor client was added
- Allowlist 042 was not expanded
- `.env` was not modified

## Task 066 — AI consumer consent boundary

- Status: COMPLETED
- `mvn test`: 846/0
- Epic sandbox live result (`GET /epic/sandbox/fhir/clinical-projection`, HTTP 200):
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `agentStub=SUCCEEDED`
  - `deterministicAgent=READY`
  - `aiBoundary=PREPARED`
  - `clinicalDataAvailable=true`
  - `modelCallAuthorized=false`
  - `aiModelCalled=false`
  - `medicationRequestsStatus=NOT_REQUESTED`
  - `firstAiComponent=PREPARED`
  - `aiProcessingStatus=NOT_EXECUTED`
  - `aiExecutionGate=ELIGIBLE_BUT_NOT_AUTHORIZED`
  - `aiConsumerContract=v1`
  - `aiConsumerStatus=READY`
  - `aiDispatchStatus=NOT_DISPATCHED`
  - `aiConsumerPolicy=ALLOWED_FOR_FUTURE_CONSUMPTION`
  - `aiConsumerReadiness=READY_FOR_FUTURE_HANDOFF`
  - `aiHandoffAuthorization=HANDOFF_NOT_AUTHORIZED`
  - `aiConsumerAuthentication=NOT_AUTHENTICATED`
  - `aiConsumerAuthorization=AUTHORIZATION_NOT_IMPLEMENTED`
  - `aiConsumerAuthorizationAvailable=false`
  - `aiConsumerConsent=CONSENT_NOT_IMPLEMENTED`
  - `aiConsumerPurpose=PURPOSE_NOT_VERIFIED`
  - `aiConsumerDataScope=DATA_SCOPE_NOT_VERIFIED`
  - `aiConsumerConsentAvailable=false`
  - `aiClinicalDataAccessAllowed=false`
- Package `lab.healthcare.fhir.aiconsumerconsent` consumes only `AiConsumerAuthorizationResult` plus a synthetic `ConsumerConsentContext`
- Deny-by-default: a valid 065 result still yields `CONSENT_NOT_IMPLEMENTED`
- Untrusted `consentVerified` / `purposeApproved` / `dataScopeApproved` assertions are `BLOCKED`
- Query parameters and headers cannot activate consent, purpose approval, or clinical access
- `consentVerified=false`, `purposeApproved=false`, `dataScopeApproved=false`, `consentProviderConfigured=false`, `consentAvailable=false`, `clinicalDataAccessAllowed=false`, `authenticationVerified=false`, `authorizationGranted=false`, `realSecurityProviderConfigured=false`, `consumerAuthorizationAvailable=false`, `handoffAuthorized=false`, `dispatchPerformed=false`, `externalAuthorizationAvailable=false`, `modelCallAuthorized=false`, `modelCalled=false`, `processingStatus=NOT_EXECUTED`, `dispatchStatus=NOT_DISPATCHED`, `requiresHumanReview=true`
- Existing confirmation surface reused: `GET /epic/sandbox/fhir/clinical-projection` now also shows `aiConsumerConsent=CONSENT_NOT_IMPLEMENTED`, `aiConsumerPurpose=PURPOSE_NOT_VERIFIED`, `aiConsumerDataScope=DATA_SCOPE_NOT_VERIFIED`, `aiConsumerConsentAvailable=false`, `aiClinicalDataAccessAllowed=false`
- New lab surfaces: `GET /lab/ai-consumer-consent`, `GET /api/ai-consumer-consent/v1` (Oracle-backed provider)
- Consent rules are documented in `docs/fhir/ai-consumer-consent-boundary.md`
- No Python `ai-service`, real consent provider, OAuth, JWT, SMART, LLM, RAG, HTTP dispatch, handoff, or vendor client was added
- Allowlist 042 was not expanded
- `.env` was not modified

## Task 067 — AI consumer data scope boundary

- Status: COMPLETED
- `mvn test`: 863/0
- Epic sandbox live result (`GET /epic/sandbox/fhir/clinical-projection`, HTTP 200):
  - `controlledProjection=SUCCEEDED`
  - `modelBoundaryContract=v1`
  - `agentStub=SUCCEEDED`
  - `deterministicAgent=READY`
  - `aiBoundary=PREPARED`
  - `clinicalDataAvailable=true`
  - `modelCallAuthorized=false`
  - `aiModelCalled=false`
  - `medicationRequestsStatus=NOT_REQUESTED`
  - `firstAiComponent=PREPARED`
  - `aiProcessingStatus=NOT_EXECUTED`
  - `aiExecutionGate=ELIGIBLE_BUT_NOT_AUTHORIZED`
  - `aiConsumerContract=v1`
  - `aiConsumerStatus=READY`
  - `aiDispatchStatus=NOT_DISPATCHED`
  - `aiConsumerPolicy=ALLOWED_FOR_FUTURE_CONSUMPTION`
  - `aiConsumerReadiness=READY_FOR_FUTURE_HANDOFF`
  - `aiHandoffAuthorization=HANDOFF_NOT_AUTHORIZED`
  - `aiConsumerAuthentication=NOT_AUTHENTICATED`
  - `aiConsumerAuthorization=AUTHORIZATION_NOT_IMPLEMENTED`
  - `aiConsumerAuthorizationAvailable=false`
  - `aiConsumerConsent=CONSENT_NOT_IMPLEMENTED`
  - `aiConsumerPurpose=PURPOSE_NOT_VERIFIED`
  - `aiConsumerDataScope=DATA_SCOPE_NOT_VERIFIED`
  - `aiConsumerConsentAvailable=false`
  - `aiClinicalDataAccessAllowed=false`
  - `aiConsumerClinicalDataScope=NOT_READY_FOR_CLINICAL_DATA_ACCESS`
  - `aiConsumerScopeDeclared=false`
  - `aiConsumerScopeEvaluated=false`
  - `aiConsumerMinimizationEvaluated=false`
  - `aiConsumerPurposeScopeAlignmentEvaluated=false`
  - `aiClinicalDataScopeProviderConfigured=false`
  - `aiClinicalDataScopeApprovalAvailable=false`
  - `aiClinicalDataAccessRequested=false`
  - `aiClinicalDataAccessGranted=false`
- Package `lab.healthcare.fhir.aiconsumerscope` consumes only `AiConsumerConsentResult` plus a synthetic `ConsumerDataScopeContext`
- Deny-by-default: a valid 066 result still yields `NOT_READY_FOR_CLINICAL_DATA_ACCESS`
- Declared synthetic categories are `DATA_SCOPE_DECLARED_NOT_EVALUATED`; they are never approved
- Query parameters and headers cannot activate clinical access
- `scopeEvaluated=false`, `minimizationEvaluated=false`, `purposeScopeAlignmentEvaluated=false`, `clinicalDataScopeProviderConfigured=false`, `clinicalDataScopeApprovalAvailable=false`, `clinicalDataAccessRequested=false`, `clinicalDataAccessGranted=false`, `clinicalDataAccessAllowed=false`
- Existing confirmation surface reused: `GET /epic/sandbox/fhir/clinical-projection` now also shows `aiConsumerClinicalDataScope=NOT_READY_FOR_CLINICAL_DATA_ACCESS` and the related deny flags
- New lab surfaces: `GET /lab/ai-consumer-data-scope`, `GET /api/ai-consumer-data-scope/v1` (Oracle-backed provider)
- Scope rules are documented in `docs/fhir/ai-consumer-data-scope-boundary.md`
- No Python `ai-service`, real consent provider, OAuth, JWT, SMART, LLM, RAG, HTTP dispatch, handoff, FHIR read, or vendor client was added
- Allowlist 042 was not expanded
- `.env` was not modified




