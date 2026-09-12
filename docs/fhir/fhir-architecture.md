# FHIR Integration Service architecture

This note is the package map after Tasks 001–017. It does **not** add a FHIR capability. Read it after [fhir-client.md](fhir-client.md). OAuth and SMART behavior is unchanged: see [fhir-oauth2-authentication.md](fhir-oauth2-authentication.md) and [fhir-smart-on-fhir.md](fhir-smart-on-fhir.md). Task 028 adds SMART readiness types in `smart` only; see [fhir-smart-real-world-readiness.md](fhir-smart-real-world-readiness.md). Task 029 adds an Epic vendor profile in `vendor` / `vendor.epic`; see [vendors/epic.md](vendors/epic.md). Task 030 adds Oracle Health in `vendor.oracle`; see [vendors/oracle-health.md](vendors/oracle-health.md). Neither connects to a live vendor sandbox. Task 031 adds runtime `GET /metadata` interpretation in `capability`; see [fhir-capability-discovery.md](fhir-capability-discovery.md). Task 032 adds vendor-neutral endpoint connectivity and Oracle sandbox connection readiness; see [fhir-endpoint-connectivity.md](fhir-endpoint-connectivity.md) and [vendors/oracle-health.md](vendors/oracle-health.md). Task 033 adds interactive SMART Authorization Code + PKCE (generic coordinator + Oracle orchestrator); see [fhir-smart-interactive-authorization.md](fhir-smart-interactive-authorization.md). Task 034 reuses that capability model against the real Oracle Health sandbox `GET /metadata` (public, no Bearer); see [vendors/oracle-health.md](vendors/oracle-health.md). Task 035 uses an issued SMART token through `AccessTokenProvider` for a generic Patient `SEARCH_TYPE`; see [vendors/oracle-health.md](vendors/oracle-health.md). Task 036 adds an explicit `PatientContext` and a capability-aware authenticated Patient read; see [vendors/oracle-health.md](vendors/oracle-health.md). Task 037 searches `Condition` for that configured Patient; see [vendors/oracle-health.md](vendors/oracle-health.md). Task 038 searches `Observation` the same way. Task 039 searches `DiagnosticReport` the same way. Task 040 searches `MedicationRequest` the same way. Task 041 assembles those operations into a controlled clinical snapshot of status and counts. Task 042 applies an application retention ceiling and an explicit allowlist as a controlled projection. Task 043 maps that projection onto a vendor-neutral v1 model boundary contract without calling a model. Task 044 exposes that contract on `GET /api/model-boundary/v1` as JSON, separate from the laboratory HTML page. Task 045 adds a contract-consuming agent stub that observes the contract and does not call a model. Task 046 starts interactive SMART Authorization Code + PKCE against `epic-sandbox` using the same generic coordinator as Oracle. Task 047 reuses the capability model against the configured Epic sandbox `GET /metadata` (public, no Bearer). Task 048 adds an explicit `PatientContext` and a capability-aware authenticated Patient read against `epic-sandbox`. Task 049 searches `Condition` for that configured Patient. Task 050 searches `Observation` the same way. Task 051 searches `DiagnosticReport` the same way. Task 052 assembles those Epic operations into a controlled clinical snapshot of status and counts. Task 053 applies the Task 042 retention ceiling and allowlist as a controlled projection of that Epic sequence. Task 054 validates that the generic agent stub consumes Epic and Oracle v1 contracts without vendor branches or a model call. Task 055 records the shared v1 invariants and allowed MedicationRequest difference; see [model-boundary-contract-v1.md](model-boundary-contract-v1.md). Task 056 adds a vendor-neutral pipeline diagnosis (`lab.healthcare.fhir.pipeline`) that aggregates stage statuses and sanitized errors without changing the v1 contract fields. Task 057 adds a deterministic boundary agent (`lab.healthcare.fhir.agent`) that consumes the v1 contract and pipeline diagnosis without calling a model. Task 058 adds an AI boundary (`lab.healthcare.fhir.aiboundary`) that copies that verdict for a future ai-service and keeps `modelCallAuthorized=false`. Task 059 adds the first isolated AI component (`lab.healthcare.fhir.firstai`) that consumes only `AiBoundaryResult` and keeps `processingStatus=NOT_EXECUTED`. Task 060 adds an AI execution gate (`lab.healthcare.fhir.aigateway`) that can mark an input `ELIGIBLE_BUT_NOT_AUTHORIZED` without setting `modelCallAuthorized=true`. Task 061 adds an internal AI Consumer Contract v1 (`lab.healthcare.fhir.aiconsumer`) that stays `NOT_DISPATCHED`. Task 062 adds a synthetic consumer policy (`lab.healthcare.fhir.aiconsumerpolicy`) that can mark `ALLOWED_FOR_FUTURE_CONSUMPTION` without dispatch or model authorization. Task 063 adds AI consumer readiness (`lab.healthcare.fhir.aiconsumerreadiness`) that can mark `READY_FOR_FUTURE_HANDOFF` without authorizing handoff or dispatch. Task 064 adds a deny-by-default handoff authorization boundary (`lab.healthcare.fhir.aihandoffauthorization`) that stays `HANDOFF_NOT_AUTHORIZED`. Task 065 adds a deny-by-default consumer authentication and authorization boundary (`lab.healthcare.fhir.aiconsumerauthorization`) that stays `AUTHORIZATION_NOT_IMPLEMENTED`. Task 066 adds a deny-by-default consent and purpose boundary (`lab.healthcare.fhir.aiconsumerconsent`) that stays `CONSENT_NOT_IMPLEMENTED`. Task 067 adds a deny-by-default clinical data-scope and minimization boundary (`lab.healthcare.fhir.aiconsumerscope`) that stays `NOT_READY_FOR_CLINICAL_DATA_ACCESS`. Task 068 adds a deny-by-default clinical data-access request boundary (`lab.healthcare.fhir.aiconsumeraccess`) that stays `NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS`. Task 069 adds a deny-by-default clinical data-access enforcement boundary (`lab.healthcare.fhir.aiconsumerenforcement`) that stays `NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS`. Task 070 adds a deny-by-default clinical data-access enforcement-execution boundary (`lab.healthcare.fhir.aiconsumerenforcementexecution`) that stays `NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS`.

There is still no product API or DTO layer. Lab HTTP pages are SMART start/callback, authenticated Patient search diagnosis, controlled Patient read diagnosis, authenticated Condition search diagnosis, authenticated Observation search diagnosis, authenticated DiagnosticReport search diagnosis, authenticated MedicationRequest search diagnosis, controlled clinical snapshot diagnosis, controlled clinical projection diagnosis, and vendor-neutral model boundary diagnosis. Task 044 adds a versioned machine surface (`GET /api/model-boundary/v1`) that returns the v1 contract as JSON. Task 045 adds a stub consumer (`GET /lab/agent-stub`, `GET /api/agent-stub/v1`) that observes that contract without calling a model. Task 046 adds Epic sandbox SMART start (`GET /epic/sandbox/smart/start`). Task 047 adds Epic public capability discovery (`GET /epic/sandbox/fhir/capabilities`). Task 048 adds Epic controlled Patient read (`GET /epic/sandbox/fhir/patient`). Task 049 adds Epic authenticated Condition search (`GET /epic/sandbox/fhir/condition-search`). Task 050 adds Epic authenticated Observation search (`GET /epic/sandbox/fhir/observation-search`). Task 051 adds Epic authenticated DiagnosticReport search (`GET /epic/sandbox/fhir/diagnostic-report-search`). Task 052 adds Epic controlled clinical snapshot (`GET /epic/sandbox/fhir/clinical-snapshot`). Task 053 adds Epic controlled clinical projection (`GET /epic/sandbox/fhir/clinical-projection`). Task 054 keeps `/api/model-boundary/v1` and `/lab/agent-stub` Oracle-backed and validates Epic stub consumption on the projection page. Task 055 adds shared Oracle/Epic contract compatibility tests. Task 056 adds `pipelineStatus`, `contractValid`, and `usable` on the Epic snapshot/projection pages without replacing the existing blind fields. Task 057 adds `GET /lab/deterministic-agent` and `GET /api/deterministic-agent/v1`, plus a deterministic verdict on the Epic projection page. Task 058 adds `GET /lab/ai-boundary` and `GET /api/ai-boundary/v1`. Task 059 adds `GET /lab/first-ai-component` and `GET /api/first-ai-component/v1`. Task 060 adds `GET /lab/ai-execution-gate` and `GET /api/ai-execution-gate/v1`. Task 061 adds `GET /lab/ai-consumer-contract` and `GET /api/ai-consumer-contract/v1`. Task 062 adds `GET /lab/ai-consumer-policy` and `GET /api/ai-consumer-policy/v1`. Task 063 adds `GET /lab/ai-consumer-readiness` and `GET /api/ai-consumer-readiness/v1`. Task 064 adds `GET /lab/ai-handoff-authorization` and `GET /api/ai-handoff-authorization/v1`. Task 065 adds `GET /lab/ai-consumer-authorization` and `GET /api/ai-consumer-authorization/v1`. Task 066 adds `GET /lab/ai-consumer-consent` and `GET /api/ai-consumer-consent/v1`. Task 067 adds `GET /lab/ai-consumer-data-scope` and `GET /api/ai-consumer-data-scope/v1`. Task 068 adds `GET /lab/ai-consumer-clinical-data-access` and `GET /api/ai-consumer-clinical-data-access/v1`. Task 069 adds `GET /lab/ai-consumer-clinical-data-enforcement` and `GET /api/ai-consumer-clinical-data-enforcement/v1`. Task 070 adds `GET /lab/ai-consumer-clinical-data-enforcement-execution` and `GET /api/ai-consumer-clinical-data-enforcement-execution/v1`. `READY` still does not authorize a model call, the consumer contract is not dispatched, and readiness is not handoff authorization.

## Previous architecture

After Task 017 every production class lived under one package:

```text
lab.healthcare.fhir.client
├── FhirService
├── FhirClientFactory
├── FhirClientConfiguration
├── FhirServerProfile / FhirServersProperties / FhirServerProfileRegistry
├── AccessToken / AccessTokenProvider / BearerAccessTokenInterceptor
├── OAuth2TokenClient
├── SmartConfigurationClient / AuthorizationCodeClient / Pkce / SmartTokenProvider
└── FhirClientException
```

That compiled and the tests passed. The package name `client` no longer described the contents.

## Why that structure does not scale

`client` mixed five different questions:

| Question | Example |
|---|---|
| Which FHIR operation? | `readPatient`, `$everything` |
| Which server? | `fhir.active-server`, `base-url` |
| How is the request authorized? | Bearer interceptor, token cache |
| How is a Client Credentials token obtained? | `POST /oauth/token` |
| How is SMART launched? | PKCE, well-known, authorization code |

A consulting or SaaS integration component will add Epic, Oracle Health, another grant type, or another FHIR operation. If all of those land in `client`, every change collides. The next developer cannot add an authentication mechanism without opening `FhirService`.

## New package structure

```text
lab.healthcare.fhir
│
├── client
│   ├── FhirClientConfiguration.java
│   ├── FhirClientFactory.java
│   └── FhirService.java
│
├── server
│   ├── FhirServerProfile.java
│   ├── FhirServersProperties.java
│   ├── FhirServerProfileRegistry.java
│   └── FhirDeploymentEnvironment.java
│
├── auth
│   ├── AccessToken.java
│   ├── AccessTokenProvider.java
│   ├── IssuedAccessTokenProvider.java
│   ├── BearerAccessTokenInterceptor.java
│   ├── CachingAccessTokenProvider.java
│   ├── FhirAuthenticationType.java
│   ├── FhirAuthenticationSettings.java
│   └── oauth2
│       ├── OAuth2TokenClient.java
│       ├── OAuth2TokenException.java
│       └── OAuth2TokenResponseParser.java
│
├── smart
│   ├── SmartConfiguration.java
│   ├── SmartConfigurationClient.java
│   ├── SmartDiscoveryUrl.java
│   ├── SmartCapabilities.java
│   ├── SmartFlowRequirements.java
│   ├── SmartConfigurationValidator.java
│   ├── SmartCompatibilityException.java
│   ├── SmartAuthorizationRequest.java
│   ├── AuthorizationCodeClient.java
│   ├── AuthorizationSession.java
│   ├── PendingAuthorizationSession.java
│   ├── AuthorizationSessionStore.java
│   ├── InMemoryAuthorizationSessionStore.java
│   ├── SmartAuthorizationCallback.java
│   ├── SmartAuthorizationStart.java
│   ├── SmartAuthorizationCoordinator.java
│   ├── SmartAuthorizationException.java
│   ├── SmartTokenExchangeDiagnoser.java
│   ├── SmartTokenProvider.java
│   ├── Pkce.java
│   └── web
│       ├── SmartAuthorizationCallbackController.java
│       └── SmartLabPages.java
│
├── mapping
│   ├── MappingService.java
│   ├── MappingDefinition.java
│   ├── FieldMapping.java
│   └── MappingException.java
│
├── patient
│   ├── PatientContext.java
│   ├── PatientContextSource.java
│   └── PatientContexts.java
│
├── snapshot
│   ├── ClinicalSnapshotOutcome.java
│   ├── ClinicalSnapshotResourceStatus.java
│   ├── ClinicalSnapshotResult.java
│   ├── ClinicalSnapshotStatuses.java
│   └── ClinicalSnapshotAssembler.java
│
├── projection
│   ├── RetentionCeiling.java
│   ├── ProjectedCollection.java
│   ├── RetainedPatient.java
│   ├── RetainedCondition.java
│   ├── RetainedObservation.java
│   ├── RetainedDiagnosticReport.java
│   ├── RetainedMedicationRequest.java
│   ├── ClinicalProjectionResult.java
│   ├── ClinicalProjectionMapper.java
│   └── ClinicalProjectionAssembler.java
│
├── modelboundary
│   ├── ModelBoundaryContractVersion.java
│   ├── BoundaryPatient.java
│   ├── BoundaryCondition.java
│   ├── BoundaryObservation.java
│   ├── BoundaryDiagnosticReport.java
│   ├── BoundaryMedicationRequest.java
│   ├── BoundaryCollection.java
│   ├── ModelBoundaryContract.java
│   ├── ModelBoundaryMapper.java
│   ├── ModelBoundaryContractProvider.java
│   ├── ModelBoundaryHttpStatuses.java
│   └── web
│       └── ModelBoundaryContractController.java
│
├── agentstub
│   ├── ObservedCollection.java
│   ├── AgentStubObservation.java
│   ├── AgentStub.java
│   └── web
│       └── AgentStubController.java
│
├── agent
│   ├── AgentDecision.java
│   ├── AgentReasonCodes.java
│   ├── AgentValidationException.java
│   ├── DeterministicAgentInput.java
│   ├── DeterministicAgentResult.java
│   ├── DeterministicAgent.java
│   └── web
│       └── DeterministicAgentController.java
│
├── aiboundary
│   ├── AiBoundaryInput.java
│   ├── AiBoundaryDecision.java
│   ├── AiBoundaryResult.java
│   ├── AiBoundaryMapper.java
│   ├── AiBoundaryService.java
│   └── web
│       └── AiBoundaryController.java
│
├── firstai
│   ├── FirstAiInput.java
│   ├── FirstAiComponentStatus.java
│   ├── FirstAiProcessingStatus.java
│   ├── FirstAiResult.java
│   ├── FirstAiMapper.java
│   ├── FirstAiComponent.java
│   └── web
│       └── FirstAiController.java
│
├── aigateway
│   ├── AiExecutionInput.java
│   ├── AiExecutionStatus.java
│   ├── AiExecutionReasonCodes.java
│   ├── AiExecutionDecision.java
│   ├── AiExecutionMapper.java
│   ├── AiExecutionGate.java
│   └── web
│       └── AiExecutionGateController.java
│
├── aiconsumer
│   ├── AiConsumerContractVersion.java
│   ├── AiConsumerContractStatus.java
│   ├── AiConsumerDispatchStatus.java
│   ├── AiConsumerReasonCodes.java
│   ├── AiConsumerContract.java
│   ├── AiConsumerContractMapper.java
│   ├── AiConsumerContractService.java
│   └── web
│       └── AiConsumerContractController.java
│
├── aiconsumerpolicy
│   ├── AiConsumerIdentity.java
│   ├── AiConsumerPolicyInput.java
│   ├── AiConsumerPolicyDecision.java
│   ├── AiConsumerPolicyReasonCodes.java
│   ├── AiConsumerPolicyOperations.java
│   ├── AiConsumerPolicyScopes.java
│   ├── AiConsumerPolicyResult.java
│   ├── AiConsumerPolicy.java
│   └── web
│       └── AiConsumerPolicyController.java
│
├── aiconsumerreadiness
│   ├── AiConsumerReadinessStatus.java
│   ├── AiConsumerReadinessReasonCodes.java
│   ├── AiConsumerReadinessInput.java
│   ├── AiConsumerReadinessResult.java
│   ├── AiConsumerReadiness.java
│   └── web
│       └── AiConsumerReadinessController.java
│
├── aihandoffauthorization
│   ├── AiHandoffAuthorizationStatus.java
│   ├── AiHandoffAuthorizationReasonCodes.java
│   ├── AiHandoffAuthorizationOperations.java
│   ├── AiHandoffAuthorizationScopes.java
│   ├── AiHandoffAuthorizationInput.java
│   ├── AiHandoffAuthorizationResult.java
│   ├── AiHandoffAuthorizationBoundary.java
│   └── web
│       └── AiHandoffAuthorizationController.java
│
├── aiconsumerauthorization
│   ├── AiConsumerAuthorizationStatus.java
│   ├── AiConsumerAuthorizationReasonCodes.java
│   ├── AiConsumerAuthorizationScopes.java
│   ├── ConsumerSecurityContext.java
│   ├── AiConsumerAuthorizationInput.java
│   ├── AiConsumerAuthorizationResult.java
│   ├── AiConsumerAuthorizationBoundary.java
│   └── web
│       └── AiConsumerAuthorizationController.java
│
├── aiconsumerconsent
│   ├── AiConsumerConsentStatus.java
│   ├── AiConsumerConsentReasonCodes.java
│   ├── ConsumerConsentPurpose.java
│   ├── ConsumerConsentDataScopes.java
│   ├── AiConsumerConsentOperations.java
│   ├── ConsumerConsentContext.java
│   ├── AiConsumerConsentInput.java
│   ├── AiConsumerConsentResult.java
│   ├── AiConsumerConsentBoundary.java
│   └── web
│       └── AiConsumerConsentController.java
│
├── aiconsumerscope
│   ├── AiConsumerDataScopeStatus.java
│   ├── AiConsumerDataScopeReasonCodes.java
│   ├── ConsumerDataScopeCategories.java
│   ├── PurposeScopeAlignmentStatus.java
│   ├── AiConsumerDataScopeOperations.java
│   ├── ConsumerDataScopeContext.java
│   ├── AiConsumerDataScopeInput.java
│   ├── AiConsumerDataScopeResult.java
│   ├── AiConsumerDataScopeBoundary.java
│   └── web
│       └── AiConsumerDataScopeController.java
│
├── aiconsumeraccess
│   ├── AiConsumerClinicalDataAccessStatus.java
│   ├── AiConsumerClinicalDataAccessReasonCodes.java
│   ├── AiConsumerClinicalDataAccessOperations.java
│   ├── ClinicalDataAccessRequestContext.java
│   ├── AiConsumerClinicalDataAccessInput.java
│   ├── AiConsumerClinicalDataAccessResult.java
│   ├── AiConsumerClinicalDataAccessBoundary.java
│   └── web
│       └── AiConsumerClinicalDataAccessController.java
│
├── aiconsumerenforcement
│   ├── AiConsumerClinicalDataEnforcementStatus.java
│   ├── AiConsumerClinicalDataEnforcementReasonCodes.java
│   ├── AiConsumerClinicalDataEnforcementOperations.java
│   ├── ClinicalDataEnforcementContext.java
│   ├── AiConsumerClinicalDataEnforcementInput.java
│   ├── AiConsumerClinicalDataEnforcementResult.java
│   ├── AiConsumerClinicalDataEnforcementBoundary.java
│   └── web
│       └── AiConsumerClinicalDataEnforcementController.java
│
├── aiconsumerenforcementexecution
│   ├── AiConsumerClinicalDataEnforcementExecutionStatus.java
│   ├── AiConsumerClinicalDataEnforcementExecutionReasonCodes.java
│   ├── AiConsumerClinicalDataEnforcementExecutionOperations.java
│   ├── ClinicalDataEnforcementExecutionContext.java
│   ├── AiConsumerClinicalDataEnforcementExecutionInput.java
│   ├── AiConsumerClinicalDataEnforcementExecutionResult.java
│   ├── AiConsumerClinicalDataEnforcementExecutionBoundary.java
│   └── web
│       └── AiConsumerClinicalDataEnforcementExecutionController.java
│
├── pipeline
│   ├── PipelineStageStatus.java
│   ├── PipelineErrorCodes.java
│   ├── PipelineErrorInfo.java
│   ├── PipelineStageDiagnosis.java
│   ├── PipelineDiagnosis.java
│   ├── PipelineAggregator.java
│   ├── PipelineStatuses.java
│   ├── PipelineDiagnoses.java
│   └── SafePipelineLog.java
│
├── routing
│   ├── RoutingService.java
│   ├── RoutingRequest.java
│   ├── RoutingException.java
│   ├── FhirAuthenticatedReadOutcome.java
│   ├── FhirAuthenticatedReadResult.java
│   ├── FhirAuthenticatedReadResults.java
│   ├── FhirPatientReadOutcome.java
│   ├── FhirPatientReadResult.java
│   ├── FhirPatientReadResults.java
│   ├── FhirConditionSearchOutcome.java
│   ├── FhirConditionSearchResult.java
│   ├── FhirConditionSearchResults.java
│   ├── FhirObservationSearchOutcome.java
│   ├── FhirObservationSearchResult.java
│   └── FhirObservationSearchResults.java
│
├── observability
│   ├── FhirOperationContext.java
│   ├── FhirAuditEvent.java
│   ├── FhirAuditRecorder.java
│   ├── LoggingFhirAuditRecorder.java
│   ├── FhirMetricsRecorder.java
│   ├── InMemoryFhirMetricsRecorder.java
│   └── FhirMetricSnapshot.java
│
├── exception
│   ├── FhirClientException.java
│   ├── FhirErrorCategory.java
│   ├── FhirErrorDetails.java
│   └── FhirErrorClassifier.java
│
├── resilience
    ├── FhirResilienceProperties.java
    ├── FhirResilienceConfiguration.java
    ├── FhirRetryPolicy.java
    ├── FhirRetryDecision.java
    ├── FhirRetryExecutor.java
    ├── CircuitBreakerState.java
    ├── FhirCircuitBreakerPolicy.java
    ├── FhirCircuitBreaker.java
    ├── FhirCircuitBreakerRegistry.java
    ├── CircuitBreakerOpenException.java
    ├── ratelimit
    │   ├── FhirRateLimiterPolicy.java
    │   ├── FhirRateLimiter.java
    │   ├── FhirRateLimiterRegistry.java
    │   └── RateLimitExceededException.java
    └── bulkhead
        ├── FhirBulkheadPolicy.java
        ├── FhirBulkhead.java
        ├── FhirBulkheadRegistry.java
        └── BulkheadFullException.java

├── capability
│   ├── FhirCapabilityDiscoveryService.java
│   ├── FhirServerCapabilities.java
│   ├── FhirResourceCapabilities.java
│   ├── FhirInteraction.java
│   └── FhirCapabilityException.java

├── connectivity
│   ├── FhirEndpointConnectivityVerifier.java
│   ├── FhirConnectivityStatus.java
│   └── FhirConnectivityOutcome.java

└── vendor
    ├── FhirVendor.java
    ├── FhirVendorProfile.java
    ├── epic
    │   └── … EpicIntegrationProfile, validator, capabilities …
    └── oracle
        ├── OracleHealthIntegrationProfile.java
        ├── OracleHealthProfileValidator.java
        ├── OracleHealthCapabilities.java
        ├── OracleHealthEnvironment.java
        ├── OracleHealthLaunchMode.java
        ├── OracleHealthUserContext.java
        ├── OracleHealthClientAuthentication.java
        ├── OracleHealthReadinessState.java
        ├── OracleHealthKnownApiSurface.java
        ├── OracleHealthProfileException.java
        ├── OracleHealthVendorConfiguration.java
        ├── OracleSandboxConfiguration.java
        ├── OracleSandboxProfileValidator.java
        ├── OracleSandboxReadiness.java
        ├── OracleSandboxReadinessState.java
        ├── OracleSandboxReadinessService.java
        ├── OracleSandboxAuthReadiness.java
        ├── OracleSandboxAuthReadinessState.java
        ├── OracleSandboxAuthenticationService.java
        ├── OracleSandboxCapabilityDiscoveryService.java
        ├── OracleSandboxAuthenticatedReadService.java
        ├── OracleSandboxAuthenticatedReadController.java
        ├── OracleSandboxPatientContextService.java
        ├── OracleSandboxPatientContextController.java
        ├── OracleSandboxConditionSearchService.java
        ├── OracleSandboxConditionSearchController.java
        ├── OracleSandboxObservationSearchService.java
        ├── OracleSandboxObservationSearchController.java
        ├── OracleSandboxDiagnosticReportSearchService.java
        ├── OracleSandboxDiagnosticReportSearchController.java
        ├── OracleSandboxMedicationRequestSearchService.java
        ├── OracleSandboxMedicationRequestSearchController.java
        ├── OracleSandboxClinicalSnapshotService.java
        ├── OracleSandboxClinicalSnapshotController.java
        ├── OracleSandboxClinicalProjectionService.java
        ├── OracleSandboxClinicalProjectionController.java
        ├── OracleSandboxModelBoundaryService.java
        ├── OracleSandboxModelBoundaryController.java
        ├── OracleSandboxModelBoundaryContractProvider.java
        └── OracleSandboxSmartInteractiveController.java
```

YAML keys (`fhir.active-server`, `fhir.servers`, nested `authentication`, optional `vendor` / `vendor-integration`, `fhir.resilience`) bind server profiles, vendor metadata, and the resilience policy. Spring still scans from `lab.healthcare.fhir`.

## Package responsibilities

| Package | Owns | Does not own |
|---|---|---|
| `client` | HAPI `FhirContext` / `IGenericClient` construction, FHIR operations | token URLs, PKCE, profile YAML binding |
| `server` | named profiles, which server is active, deployment environment identity | how to obtain a token |
| `auth` | token value, provider SPI, Bearer interceptor, cache for Client Credentials | SMART discovery, FHIR search |
| `auth.oauth2` | Client Credentials HTTP token POST and JSON parse | SMART authorize URL, `FhirService` |
| `smart` | well-known, capabilities, compatibility, PKCE, authorization request, interactive coordinator, authorization code, refresh | generic Client Credentials, FHIR operations, vendor hosts |
| `mapping` | external JSON → HAPI R4 Resource | FHIR HTTP, OAuth, terminology `$validate-code` |
| `patient` | explicit Patient context (destination, id, source) | FHIR HTTP, SMART launch, patient enumeration |
| `snapshot` | sequential assembly of status + counts for already-supported resources | clinical field models, IA, persistence, vendor hosts |
| `projection` | application retention ceiling and explicit allowlist over the same operations | clinical ranking, AI context, persistence, vendor hosts, raw Bundle |
| `modelboundary` | vendor-neutral v1 contract mapped from the projection, plus versioned JSON consumer surface | LLM calls, vendor contracts, HAPI types, new FHIR queries, agent runtime |
| `agentstub` | consumes the v1 contract and emits a blind observation (`modelCalled=false`) | LLM, prompts, `ai-service`, FHIR fetch, record republication |
| `pipeline` | normalized stage statuses, critical/non-critical aggregation, sanitized error codes, safe log lines | FHIR fetch, vendor branches, HAPI, tokens, clinical values, LLM |
| `agent` | deterministic rules over the v1 contract and pipeline diagnosis (`READY` / `BLOCKED` / `REQUIRES_HUMAN_REVIEW`) | LLM, RAG, LangGraph, FHIR fetch, vendor hosts, clinical advice |
| `aiboundary` | controlled payload for a future ai-service; copies 057 and keeps `modelCallAuthorized=false` | Python ai-service, OpenAI, RAG, LangGraph, FHIR fetch, vendor hosts |
| `firstai` | isolated first AI component; copies `AiBoundaryResult` and keeps `processingStatus=NOT_EXECUTED` | Python ai-service, OpenAI, RAG, LangGraph, FHIR fetch, vendor hosts, clinical advice |
| `aigateway` | local execution gate; `ELIGIBLE_BUT_NOT_AUTHORIZED` is not model permission | Python ai-service, OpenAI, RAG, LangGraph, FHIR fetch, vendor hosts, clinical advice |
| `aiconsumer` | internal AI Consumer Contract v1; `READY` is not dispatch | Python ai-service, HTTP client, OpenAI, RAG, LangGraph, FHIR fetch, vendor hosts |
| `aiconsumerpolicy` | synthetic consumer policy; allowed future consumption is not model permission | real OAuth, JWT, HTTP client, OpenAI, RAG, LangGraph, FHIR fetch, vendor hosts |
| `aiconsumerreadiness` | readiness over the policy; ready for a future handoff is not handoff authorization | real OAuth, HTTP client, handoff, dispatch, OpenAI, RAG, LangGraph, FHIR fetch, vendor hosts |
| `aihandoffauthorization` | deny-by-default handoff authorization; ready is not permission | real OAuth, JWT, HTTP client, handoff, dispatch, OpenAI, RAG, LangGraph, FHIR fetch, vendor hosts |
| `aiconsumerauthorization` | deny-by-default consumer authentication and authorization; identity is not permission | real OAuth, JWT, SMART, HTTP client, handoff, dispatch, OpenAI, RAG, LangGraph, FHIR fetch, vendor hosts |
| `aiconsumerconsent` | deny-by-default consent and purpose; authorization is not clinical access | real consent provider, OAuth, JWT, SMART, HTTP client, handoff, dispatch, OpenAI, RAG, LangGraph, FHIR fetch, vendor hosts |
| `aiconsumerscope` | deny-by-default clinical data-scope and minimization; declared scope is not access | real consent provider, FHIR read, OAuth, JWT, SMART, HTTP client, handoff, dispatch, OpenAI, RAG, LangGraph, vendor hosts |
| `aiconsumeraccess` | deny-by-default clinical data-access request; a declared request is not a grant | real access provider, FHIR read, OAuth, JWT, SMART, HTTP client, handoff, dispatch, OpenAI, RAG, LangGraph, vendor hosts |
| `aiconsumerenforcement` | deny-by-default clinical data-access enforcement decision; a request is not enforcement | real enforcement provider, FHIR read, OAuth, JWT, SMART, HTTP client, handoff, dispatch, OpenAI, RAG, LangGraph, vendor hosts |
| `aiconsumerenforcementexecution` | deny-by-default clinical data-access enforcement execution; a decision is not execution | real execution provider, FHIR read, OAuth, JWT, SMART, HTTP client, handoff, dispatch, OpenAI, RAG, LangGraph, vendor hosts |
| `routing` | destination profile name → enabled server + client | mapping, OAuth grant types, FHIR search logic |
| `observability` | correlation, outcome, duration, safe audit line, aggregated counters | FHIR payloads, tokens, destination lookup, Prometheus |
| `exception` | bounded failure category, safe details, `FhirClientException` | OAuth token POST (`OAuth2TokenException` stays in `auth.oauth2`), retry/circuit breaker |
| `resilience` | retry, circuit breaker, rate limit, bulkhead, YAML policy sizes | FHIR operations, destination lookup, OAuth, CREATE/UPDATE/DELETE |
| `capability` | interpret `CapabilityStatement` into `FhirServerCapabilities` | SMART well-known, vendor catalogs, cache, write-method generation |
| `connectivity` | transport `GET /metadata` reachability | Patient reads, CapabilityStatement interpretation, vendor secrets |
| `vendor` | bounded vendor identity (`GENERIC`, `EPIC`, `ORACLE_HEALTH`) | FHIR operations, SMART HTTP |
| `vendor.epic` | Epic sandbox profile, SMART start/callback orchestration, readiness, public metadata capability discovery, controlled Patient context and read, Condition and Observation search by Patient | Patient search, Hyperspace, `private_key_jwt` |
| `vendor.oracle` | Oracle Health sandbox profile, launch/auth metadata, sandbox connection readiness, SMART auth orchestration, public metadata capability discovery, authenticated Patient search, controlled Patient read, Condition search, Observation search, DiagnosticReport search, MedicationRequest search, controlled snapshot orchestration, controlled projection orchestration, model-boundary mapping, and the current `ModelBoundaryContractProvider` | Oracle OAuth protocol classes, EHR launch, `private_key_jwt`, `OraclePatientClient`, `OracleConditionClient`, `OracleObservationClient`, `OracleDiagnosticReportClient`, `OracleMedicationRequestClient`, `OracleSnapshotClient`, `OracleProjectionClient`, `OracleModelBoundaryClient`, `OracleContractClient` |

`FhirAuthenticationSettings` lives in `auth` because it is the **runtime** authentication model. `FhirServersProperties.AuthenticationSettings` stays nested in `server` as the YAML binding DTO. The registry maps one to the other. That keeps Spring Boot record binding on a single canonical constructor in the properties type.

`OAuth2TokenResponseParser` is public so SMART's `AuthorizationCodeClient` can reuse the same JSON mapping as Client Credentials without becoming an OAuth class.

## Dependency direction

```text
FhirService
    │  uses IGenericClient only
    ▼
client (factory + Spring composition root)
    │
    ├──► server   (which profile)
    ├──► auth     (AccessTokenProvider)
    ├──► oauth2   (OAuth2TokenClient bean)
    └──► smart    (SmartTokenProvider bean)

server ──► auth   (FhirAuthenticationSettings on the profile)

auth ──► oauth2   (CachingAccessTokenProvider calls OAuth2TokenClient)
oauth2 ──► auth   (AccessToken, FhirAuthenticationSettings)

smart ──► auth
smart ──► oauth2  (token JSON parse + OAuth2TokenException)

mapping  (no imports of client / auth / smart)

snapshot ──► routing     (existing read/search operations only)
snapshot ──► capability  (supports checks; one CapabilityStatement from the caller)
snapshot ──► auth        (AccessTokenProvider argument)
snapshot ──► patient     (PatientContextSource on the result)

projection ──► routing     (existing read/search operations only)
projection ──► capability  (supports checks; one CapabilityStatement from the caller)
projection ──► auth        (AccessTokenProvider argument)
projection ──► patient     (PatientContextSource on the result)
projection ──► snapshot    (reuses outcome and resource status enums)

modelboundary ──► projection  (maps retained projection only)
modelboundary ──► snapshot    (reuses outcome and resource status enums)
modelboundary ──► patient     (PatientContextSource on the contract)
modelboundary.web ──► modelboundary  (GET /api/model-boundary/v1; no vendor import)
agentstub ──► modelboundary  (observe contract only)
agentstub.web ──► agentstub
agentstub.web ──► modelboundary  (provider + HTTP statuses)
pipeline ──► snapshot / projection / modelboundary / agentstub  (diagnoses existing results only)
agent ──► modelboundary / pipeline / agentstub  (consumes authorized contract only)
aiboundary ──► agent / modelboundary / pipeline  (copies authorized verdict only; never evaluates READY itself)
aiboundary.web ──► aiboundary
aiboundary.web ──► modelboundary  (provider + HTTP statuses)
firstai ──► aiboundary  (consumes AiBoundaryResult only; never evaluates READY itself)
firstai.web ──► firstai
firstai.web ──► aiboundary / modelboundary  (assembles the boundary, then hands it to FirstAiComponent)
aigateway ──► firstai  (consumes FirstAiResult only; never evaluates READY itself)
aigateway.web ──► aigateway
aigateway.web ──► firstai / aiboundary / modelboundary  (assembles FirstAiResult, then hands it to AiExecutionGate)
aiconsumer ──► aigateway  (consumes AiExecutionDecision only; never dispatches)
aiconsumer.web ──► aiconsumer
aiconsumer.web ──► aigateway / firstai / aiboundary / modelboundary  (assembles the gate verdict, then hands it to AiConsumerContractService)
aiconsumerpolicy ──► aiconsumer  (consumes AiConsumerContract only; never authenticates for real)
aiconsumerpolicy.web ──► aiconsumerpolicy
aiconsumerpolicy.web ──► aiconsumer / aigateway / firstai / aiboundary / modelboundary
aiconsumerreadiness ──► aiconsumerpolicy  (consumes AiConsumerPolicyResult only; never authorizes handoff)
aiconsumerreadiness ──► aiconsumer  (dispatch and contract-version types only)
aiconsumerreadiness.web ──► aiconsumerreadiness
aiconsumerreadiness.web ──► aiconsumerpolicy / aiconsumer / aigateway / firstai / aiboundary / modelboundary
aihandoffauthorization ──► aiconsumerreadiness  (consumes AiConsumerReadinessResult only; never authorizes handoff)
aihandoffauthorization ──► aiconsumerpolicy / aiconsumer  (decision and dispatch types only)
aihandoffauthorization.web ──► aihandoffauthorization
aihandoffauthorization.web ──► aiconsumerreadiness / aiconsumerpolicy / aiconsumer / aigateway / firstai / aiboundary / modelboundary
aiconsumerauthorization ──► aihandoffauthorization  (consumes AiHandoffAuthorizationResult only; never authenticates for real)
aiconsumerauthorization.web ──► aiconsumerauthorization
aiconsumerauthorization.web ──► aihandoffauthorization / aiconsumerreadiness / aiconsumerpolicy / aiconsumer / aigateway / firstai / aiboundary / modelboundary
aiconsumerconsent ──► aiconsumerauthorization  (consumes AiConsumerAuthorizationResult only; never verifies consent)
aiconsumerconsent.web ──► aiconsumerconsent
aiconsumerconsent.web ──► aiconsumerauthorization / aihandoffauthorization / aiconsumerreadiness / aiconsumerpolicy / aiconsumer / aigateway / firstai / aiboundary / modelboundary
aiconsumerscope ──► aiconsumerconsent  (consumes AiConsumerConsentResult only; never grants clinical access)
aiconsumerscope.web ──► aiconsumerscope
aiconsumerscope.web ──► aiconsumerconsent / aiconsumerauthorization / aihandoffauthorization / aiconsumerreadiness / aiconsumerpolicy / aiconsumer / aigateway / firstai / aiboundary / modelboundary
aiconsumeraccess ──► aiconsumerscope  (consumes AiConsumerDataScopeResult only; never grants clinical access)
aiconsumeraccess.web ──► aiconsumeraccess
aiconsumeraccess.web ──► aiconsumerscope / aiconsumerconsent / aiconsumerauthorization / aihandoffauthorization / aiconsumerreadiness / aiconsumerpolicy / aiconsumer / aigateway / firstai / aiboundary / modelboundary
aiconsumerenforcement ──► aiconsumeraccess  (consumes AiConsumerClinicalDataAccessResult only; never enforces clinical access)
aiconsumerenforcement.web ──► aiconsumerenforcement
aiconsumerenforcement.web ──► aiconsumeraccess / aiconsumerscope / aiconsumerconsent / aiconsumerauthorization / aihandoffauthorization / aiconsumerreadiness / aiconsumerpolicy / aiconsumer / aigateway / firstai / aiboundary / modelboundary
aiconsumerenforcementexecution ──► aiconsumerenforcement  (consumes AiConsumerClinicalDataEnforcementResult only; never executes enforcement)
aiconsumerenforcementexecution.web ──► aiconsumerenforcementexecution
aiconsumerenforcementexecution.web ──► aiconsumerenforcement / aiconsumeraccess / aiconsumerscope / aiconsumerconsent / aiconsumerauthorization / aihandoffauthorization / aiconsumerreadiness / aiconsumerpolicy / aiconsumer / aigateway / firstai / aiboundary / modelboundary
agent.web ──► agent
agent.web ──► modelboundary  (provider + HTTP statuses)
vendor.epic ──► pipeline  (safe log + page fields; no Epic* codes)
vendor.oracle ──► pipeline
smart.web ──► pipeline

routing ──► server   (profile lookup)
routing ──► client   (FhirClientFactory, FhirAccessTokenProviders, FhirService)
routing ──► observability (audit event + metrics after destination is known)
routing ──► exception     (RoutingException details; FhirClientException details)
routing ──► resilience    (READ, PATIENT_SEARCH, CONDITION_SEARCH, OBSERVATION_SEARCH, DIAGNOSTIC_REPORT_SEARCH, MEDICATION_REQUEST_SEARCH, and CAPABILITY_DISCOVERY share rate → bulkhead → circuit → retry)
routing ──► capability    (discoverCapabilities; FhirService stays unaware of routing)

capability ──► client     (retrieveCapabilityStatement only)

server ──► vendor         (FhirVendor on the named profile)
vendor.epic ──► server    (EpicIntegrationProfile from FhirServerProfile)
vendor.epic ──► smart     (reuses SmartAuthorizationRequest / validator; does not duplicate discovery)
vendor.epic ──► vendor    (FhirVendorProfile)
vendor.epic ──► capability  (public GET /metadata; no Epic CapabilityStatement model)
vendor.epic ──► client      (FhirClientFactory with NONE auth for that metadata GET)
vendor.epic ──► exception   (FhirClientException mapping on the lab page)
vendor.epic ──► patient     (configured PatientContext; no Patient discovery)
vendor.epic ──► routing     (generic Patient READ, Condition SEARCH_TYPE, and Observation SEARCH_TYPE with issued AccessTokenProvider)
vendor.oracle ──► server
vendor.oracle ──► smart
vendor.oracle ──► vendor
vendor.oracle ──► connectivity
vendor.oracle ──► exception
vendor.oracle ──► capability  (public GET /metadata; no Oracle CapabilityStatement model)
vendor.oracle ──► client      (FhirClientFactory with NONE auth for that metadata GET)
vendor.oracle ──► patient     (configured PatientContext; no Patient discovery)
vendor.oracle ──► routing     (generic Patient SEARCH_TYPE / READ and clinical SEARCH_TYPE with issued AccessTokenProvider)
vendor.oracle ──► snapshot    (controlled assembly of status and counts)
vendor.oracle ──► projection  (controlled retention ceiling and allowlist)
vendor.oracle ──► modelboundary  (one projection, then v1 contract; implements ModelBoundaryContractProvider)

connectivity ──► exception
```

Intended runtime chain for an authenticated FHIR call:

```text
FhirService
    → IGenericClient
        → BearerAccessTokenInterceptor
            → AccessTokenProvider
                → CachingAccessTokenProvider   (Client Credentials)
                → SmartTokenProvider           (synthetic smart-lab Authorization Code + PKCE)
                → IssuedAccessTokenProvider    (interactive callback token)
```

The interceptor does not know which grant produced the token.

### Cycles that must not exist

These are forbidden and are not present in production code:

```text
auth → smart → auth
smart → client → smart
server → smart → server
FhirService → OAuth2TokenClient / Pkce / AuthorizationCodeClient
FhirService → vendor.epic
FhirService → vendor.oracle
FhirService → patient
FhirService → capability
FhirService → connectivity
FhirService → pipeline
FhirService → agent
snapshot → pipeline
projection → pipeline
modelboundary → pipeline
agentstub → pipeline
agentstub → agent
pipeline → agent
agent → vendor.epic
agent → vendor.oracle
agent → FhirService
FhirService → aiboundary
agent → aiboundary
pipeline → aiboundary
aiboundary → vendor.epic
aiboundary → vendor.oracle
aiboundary → FhirService
FhirService → firstai
aiboundary → firstai
agent → firstai
pipeline → firstai
firstai → vendor.epic
firstai → vendor.oracle
firstai → FhirService
FhirService → aigateway
firstai → aigateway
aiboundary → aigateway
agent → aigateway
aigateway → vendor.epic
aigateway → vendor.oracle
aigateway → FhirService
FhirService → aiconsumer
aigateway → aiconsumer
firstai → aiconsumer
aiconsumer → vendor.epic
aiconsumer → vendor.oracle
aiconsumer → FhirService
FhirService → aiconsumerpolicy
aiconsumer → aiconsumerpolicy
aiconsumerpolicy → vendor.epic
aiconsumerpolicy → vendor.oracle
aiconsumerpolicy → FhirService
FhirService → aiconsumerreadiness
aiconsumer → aiconsumerreadiness
aiconsumerpolicy → aiconsumerreadiness
aiconsumerreadiness → vendor.epic
aiconsumerreadiness → vendor.oracle
aiconsumerreadiness → FhirService
FhirService → aihandoffauthorization
aiconsumer → aihandoffauthorization
aiconsumerpolicy → aihandoffauthorization
aiconsumerreadiness → aihandoffauthorization
aihandoffauthorization → vendor.epic
aihandoffauthorization → vendor.oracle
aihandoffauthorization → FhirService
FhirService → aiconsumerauthorization
aihandoffauthorization → aiconsumerauthorization
aiconsumerauthorization → vendor.epic
aiconsumerauthorization → vendor.oracle
aiconsumerauthorization → FhirService
FhirService → aiconsumerconsent
aiconsumerauthorization → aiconsumerconsent
aiconsumerconsent → vendor.epic
aiconsumerconsent → vendor.oracle
aiconsumerconsent → FhirService
FhirService → aiconsumerscope
aiconsumerconsent → aiconsumerscope
aiconsumerscope → vendor.epic
aiconsumerscope → vendor.oracle
aiconsumerscope → FhirService
FhirService → aiconsumeraccess
aiconsumerscope → aiconsumeraccess
aiconsumeraccess → vendor.epic
aiconsumeraccess → vendor.oracle
aiconsumeraccess → FhirService
FhirService → aiconsumerenforcement
aiconsumeraccess → aiconsumerenforcement
aiconsumerenforcement → vendor.epic
aiconsumerenforcement → vendor.oracle
aiconsumerenforcement → FhirService
FhirService → aiconsumerenforcementexecution
aiconsumerenforcement → aiconsumerenforcementexecution
aiconsumerenforcementexecution → vendor.epic
aiconsumerenforcementexecution → vendor.oracle
aiconsumerenforcementexecution → FhirService
```

`auth` and `auth.oauth2` import each other. That is a **namespace** cycle, not a SMART/client cycle. `AccessToken` stays in `auth` because SMART also uses it. `CachingAccessTokenProvider` stays in `auth` because it is the Client Credentials `AccessTokenProvider`, not a SMART type. No extra interface was added solely to split those two packages.

`FhirClientConfiguration` is the composition root: it may depend on every layer. That is wiring, not FHIR business logic.

## Why FhirService stays independent of OAuth and SMART

`FhirService` methods are FHIR operations (`readPatient`, `searchPatients`, `getPatientEverything`, …). Authorization is an HTTP header on the HAPI client. If `FhirService` imported `Pkce` or `OAuth2TokenClient`, every new grant type would touch the operation layer.

The preferred result is the one this refactoring keeps:

```text
FhirService imports FhirClientException and HAPI types only.
```

A future developer can add another `AccessTokenProvider` (or another `FhirServerProfile`) without editing `FhirService`.

## How the layers work together

```text
application.yml
      │
      ▼
FhirServersProperties          server (YAML)
      │
      ▼
FhirServerProfileRegistry      server → auth settings
      │
      ▼
FhirClientFactory              client
      │
      +-- NONE → IGenericClient
      +-- OAUTH2_CLIENT_CREDENTIALS → interceptor + CachingAccessTokenProvider
      +-- SMART_AUTHORIZATION_CODE  → interceptor + SmartTokenProvider
      │
      ▼
FhirService                    FHIR only
      │
      ▼
gateway / HAPI
```

Server selection answers “where”. Authentication answers “with what credential”. FHIR answers “which resource interaction”.

## Future EHR integrations

Clean boundaries make this shape possible without rewriting operations:

```text
FHIR Integration Service
│
├── FHIR operations     (client.FhirService)
├── Server profiles     (HAPI today; Epic / Oracle Health later)
├── Authentication      (NONE, Client Credentials, SMART; later other grants)
└── Exceptions          (FHIR vs token acquisition)
```

Task 018 does **not** implement those providers. It only stops accumulating unrelated classes in `client`.

Do not invent interfaces for a single implementation. `AccessTokenProvider` already exists because NONE, Client Credentials, and SMART are three behaviors behind one interceptor.

## Tests

Unit and feature tests follow the production packages where practical:

| Production | Tests |
|---|---|
| `auth` / `auth.oauth2` | interceptor, token cache, `OAuth2TokenClient`, `FhirOauth2AuthenticationIT` |
| `smart` | PKCE, discovery, capabilities, validator, authorization request, coordinator, `FhirSmartOnFhirIT`, `SmartAuthorizationCoordinatorIT` |
| `server` | YAML binding, `FhirServerConfigurationIT` |
| `client` | `FhirService` unit tests and FHIR operation ITs (search, CRUD, bundles, …) |
| `mapping` | JSON → Patient/Observation unit tests, `FhirMappingIT` |
| `routing` | destination resolution unit tests, `FhirRoutingIT` |
| `observability` | audit event unit tests, `FhirAuditObservabilityIT`, metrics counters, `FhirMetricsObservabilityIT` |
| `exception` | classifier / details unit tests, `FhirErrorHandlingIT` |
| `resilience` | retry, circuit, rate/bulkhead, `FhirResiliencePipelineIT` |
| `vendor.epic` | Epic profile / validator unit tests, `EpicIntegrationProfileIT`, sandbox SMART, capability-discovery, controlled Patient-read, Condition-search, and Observation-search ITs |
| `vendor.oracle` | Oracle Health profile / validator unit tests, `OracleHealthIntegrationProfileIT`, sandbox readiness, auth, capability-discovery, and authenticated-read ITs |
| `capability` | interpret / supports queries, `FhirCapabilityDiscoveryIT` |
| `connectivity` | metadata URI / local probe unit tests |

Synthetic seed helpers stay next to the FHIR ITs in `client`.
