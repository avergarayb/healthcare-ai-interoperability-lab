# FHIR Integration Service architecture

This note is the package map after Tasks 001–017. It does **not** add a FHIR capability. Read it after [fhir-client.md](fhir-client.md). OAuth and SMART behavior is unchanged: see [fhir-oauth2-authentication.md](fhir-oauth2-authentication.md) and [fhir-smart-on-fhir.md](fhir-smart-on-fhir.md). Task 028 adds SMART readiness types in `smart` only; see [fhir-smart-real-world-readiness.md](fhir-smart-real-world-readiness.md). Task 029 adds an Epic vendor profile in `vendor` / `vendor.epic`; see [vendors/epic.md](vendors/epic.md). Task 030 adds Oracle Health in `vendor.oracle`; see [vendors/oracle-health.md](vendors/oracle-health.md). Neither connects to a live vendor sandbox. Task 031 adds runtime `GET /metadata` interpretation in `capability`; see [fhir-capability-discovery.md](fhir-capability-discovery.md). Task 032 adds vendor-neutral endpoint connectivity and Oracle sandbox connection readiness; see [fhir-endpoint-connectivity.md](fhir-endpoint-connectivity.md) and [vendors/oracle-health.md](vendors/oracle-health.md). Task 033 adds interactive SMART Authorization Code + PKCE (generic coordinator + Oracle orchestrator); see [fhir-smart-interactive-authorization.md](fhir-smart-interactive-authorization.md). Task 034 reuses that capability model against the real Oracle Health sandbox `GET /metadata` (public, no Bearer); see [vendors/oracle-health.md](vendors/oracle-health.md). Task 035 uses an issued SMART token through `AccessTokenProvider` for a generic Patient `SEARCH_TYPE`; see [vendors/oracle-health.md](vendors/oracle-health.md). Task 036 adds an explicit `PatientContext` and a capability-aware authenticated Patient read; see [vendors/oracle-health.md](vendors/oracle-health.md). Task 037 searches `Condition` for that configured Patient; see [vendors/oracle-health.md](vendors/oracle-health.md). Task 038 searches `Observation` the same way. Task 039 searches `DiagnosticReport` the same way. Task 040 searches `MedicationRequest` the same way. Task 041 assembles those operations into a controlled clinical snapshot of status and counts. Task 042 applies an application retention ceiling and an explicit allowlist as a controlled projection. Task 043 maps that projection onto a vendor-neutral v1 model boundary contract without calling a model.

There is still no product API or DTO layer. Lab HTTP pages are SMART start/callback, authenticated Patient search diagnosis, controlled Patient read diagnosis, authenticated Condition search diagnosis, authenticated Observation search diagnosis, authenticated DiagnosticReport search diagnosis, authenticated MedicationRequest search diagnosis, controlled clinical snapshot diagnosis, controlled clinical projection diagnosis, and vendor-neutral model boundary diagnosis. Capability discovery has no extra HTTP page.

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
│   └── ModelBoundaryMapper.java
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
| `modelboundary` | vendor-neutral v1 contract mapped from the projection | LLM calls, vendor contracts, HAPI types, new FHIR queries |
| `routing` | destination profile name → enabled server + client | mapping, OAuth grant types, FHIR search logic |
| `observability` | correlation, outcome, duration, safe audit line, aggregated counters | FHIR payloads, tokens, destination lookup, Prometheus |
| `exception` | bounded failure category, safe details, `FhirClientException` | OAuth token POST (`OAuth2TokenException` stays in `auth.oauth2`), retry/circuit breaker |
| `resilience` | retry, circuit breaker, rate limit, bulkhead, YAML policy sizes | FHIR operations, destination lookup, OAuth, CREATE/UPDATE/DELETE |
| `capability` | interpret `CapabilityStatement` into `FhirServerCapabilities` | SMART well-known, vendor catalogs, cache, write-method generation |
| `connectivity` | transport `GET /metadata` reachability | Patient reads, CapabilityStatement interpretation, vendor secrets |
| `vendor` | bounded vendor identity (`GENERIC`, `EPIC`, `ORACLE_HEALTH`) | FHIR operations, SMART HTTP |
| `vendor.epic` | Epic sandbox profile, launch/auth metadata, readiness, honest unimplemented modes | live Epic OAuth, Hyperspace, `private_key_jwt` |
| `vendor.oracle` | Oracle Health sandbox profile, launch/auth metadata, sandbox connection readiness, SMART auth orchestration, public metadata capability discovery, authenticated Patient search, controlled Patient read, Condition search, Observation search, DiagnosticReport search, MedicationRequest search, controlled snapshot orchestration, controlled projection orchestration, and model-boundary mapping | Oracle OAuth protocol classes, EHR launch, `private_key_jwt`, `OraclePatientClient`, `OracleConditionClient`, `OracleObservationClient`, `OracleDiagnosticReportClient`, `OracleMedicationRequestClient`, `OracleSnapshotClient`, `OracleProjectionClient`, `OracleModelBoundaryClient` |

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
vendor.oracle ──► modelboundary  (one projection, then v1 contract; no second FHIR fetch)

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
| `vendor.epic` | Epic profile / validator unit tests, `EpicIntegrationProfileIT` |
| `vendor.oracle` | Oracle Health profile / validator unit tests, `OracleHealthIntegrationProfileIT`, sandbox readiness, auth, capability-discovery, and authenticated-read ITs |
| `capability` | interpret / supports queries, `FhirCapabilityDiscoveryIT` |
| `connectivity` | metadata URI / local probe unit tests |

Synthetic seed helpers stay next to the FHIR ITs in `client`.
