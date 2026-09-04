# Oracle Health integration profile

Task 030 prepares an Oracle Health-specific integration profile. Task 032 adds **sandbox connection readiness**: environment-variable configuration, fail-fast validation, and a vendor-neutral metadata probe. Task 033 adds **interactive SMART Authorization Code + PKCE** against a configured Oracle Health Secure Sandbox. Task 034 validates **real CapabilityStatement discovery** (`GET /metadata`, public) through the existing provider-neutral model. Task 035 uses the issued token for a generic authenticated Patient `SEARCH_TYPE`. Task 036 adds an explicit sandbox Patient context and a capability-aware `GET /Patient/{id}`. Task 037 searches `Condition` for that same configured Patient. It does **not** assume EHR launch context or claim certification.

Read this after [epic.md](epic.md) and [fhir-smart-real-world-readiness.md](../fhir-smart-real-world-readiness.md).

## What this task is

Oracle Health is a **vendor profile**, not a fork of `FhirService`. Generic FHIR operations stay vendor-neutral. Routing still selects a destination name (`oracle-health-sandbox`). SMART types from Task 028 are reused. Epic from Task 029 stays unchanged.

```text
Generic FHIR Layer
        │
        ▼
Vendor Integration Layer
        │
   ┌────┴─────┐
   │          │
 Epic     Oracle Health
```

```text
FhirServerProfile (oracle-health-sandbox, disabled)
        ↓
FhirVendor = ORACLE_HEALTH
        ↓
OracleHealthIntegrationProfile
        ↓
OracleHealthCapabilities + OracleHealthReadinessState
        ↓
OracleHealthProfileValidator
```

Java does **not** concatenate Oracle/Cerner hostnames into a FHIR base URL. A later customer endpoint is configuration.

## YAML placeholder

Profile `oracle-health-sandbox` is **disabled** by default. Local startup still uses `local-hapi`. All registration values come from the environment; Git has empty defaults.

```yaml
oracle-health-sandbox:
  enabled: ${ORACLE_HEALTH_SANDBOX_ENABLED:false}
  vendor: ORACLE_HEALTH
  fhir-version: R4
  base-url: ${ORACLE_HEALTH_SANDBOX_BASE_URL:}
  authentication:
    type: SMART_AUTHORIZATION_CODE
    client-id: ${ORACLE_HEALTH_SANDBOX_CLIENT_ID:}
    redirect-uri: ${ORACLE_HEALTH_SANDBOX_REDIRECT_URI:}
    scope: ${ORACLE_HEALTH_SANDBOX_SCOPE:}
    aud: ${ORACLE_HEALTH_SANDBOX_AUD:}
    smart-configuration-url: ${ORACLE_HEALTH_SANDBOX_SMART_CONFIGURATION_URL:}
  vendor-integration:
    environment: SANDBOX
    launch-mode: STANDALONE
    user-context: PATIENT
    client-authentication: PUBLIC_PKCE
    patient-id: ${ORACLE_HEALTH_SANDBOX_PATIENT_ID:}
```

Do not commit client secrets, private keys, access tokens, or authorization codes.

## Environments, launch, auth

| Concept | Values | Runtime |
|---|---|---|
| Environment | `SANDBOX` (prepared), `PRODUCTION` (represented) | No customer production connection; production URLs are not manufactured in Java |
| Launch | `STANDALONE`, `EHR_LAUNCH` | EHR launch is readiness (`iss` / `launch`), not implemented |
| User context | `PATIENT`, `CLINICIAN_STAFF` | Metadata only |
| Client auth | `PUBLIC_PKCE`, `CLIENT_SECRET`, `PRIVATE_KEY_JWT` | Only `PUBLIC_PKCE` is implemented (Task 028) |

Unsupported modes fail with `OracleHealthProfileException` when selected for runtime use. The lab does not fake JWT assertion.

## Readiness is not certification

| State | Meaning |
|---|---|
| `NOT_CONFIGURED` | Disabled; registration values empty |
| `CONFIGURED` | Required fields present; auth mode may be unimplemented |
| `SMART_COMPATIBLE` | Authorization Code + PKCE S256 can be built from this profile |
| `READY_FOR_SANDBOX` | SMART-compatible sandbox configuration — **not** Oracle-approved |

There is no `CERTIFIED`, `PRODUCTION_READY`, or `ORACLE_APPROVED` state.

## Sandbox connection readiness (Task 032)

Deployment environments are configuration identity: `LOCAL`, `SYNTHETIC`, `SANDBOX`, `PRODUCTION`. Oracle connectivity runtime is **SANDBOX only**.

| Connection state | Meaning |
|---|---|
| `DISABLED` | `enabled=false`; local HAPI starts without Oracle credentials |
| `INVALID_CONFIGURATION` | enabled but missing/malformed URI or unsupported auth — `VALIDATION_ERROR`, no HTTP |
| `CONFIGURED` | PRODUCTION represented; not probed |
| `READY_FOR_CONNECTIVITY_CHECK` | SANDBOX fields and http(s) URIs are complete |

`OracleSandboxReadinessService.checkConnectivity` then uses [fhir-endpoint-connectivity.md](../fhir-endpoint-connectivity.md). Placeholders: [`.env.example`](../../../.env.example). Live IT is opt-in (`-Poracle-live` + `ORACLE_HEALTH_LIVE_IT=true`).

## Secure sandbox SMART authentication (Task 033)

Oracle configures the profile. Generic SMART types perform discovery, PKCE, callback `state` validation, and token exchange. There is no `OracleSmartConfigurationClient`, `OraclePkce`, or `OracleTokenProvider`.

```text
OracleHealthIntegrationProfile
        ↓
OracleSandboxAuthenticationService.inspect   (config only; disabled = no HTTP)
        ↓
READY_FOR_AUTHORIZATION
        ↓
discover /.well-known/smart-configuration
        ↓
SmartAuthorizationCoordinator.start
        ↓
browser login (manual)
        ↓
completeAuthorization → IssuedAccessTokenProvider
```

| Auth readiness | Meaning |
|---|---|
| `DISABLED` | `enabled=false`; no discovery |
| `NOT_CONFIGURED` | profile missing |
| `INVALID_CONFIGURATION` | enabled but incomplete URI or unsupported mode (`PRIVATE_KEY_JWT`) |
| `CONFIGURED` | PRODUCTION represented; not authorized here |
| `READY_FOR_AUTHORIZATION` | SANDBOX fields and `PUBLIC_PKCE` are complete |

Browser login is **not** admitted through the FHIR resilience pipeline. Interactive flow: [fhir-smart-interactive-authorization.md](../fhir-smart-interactive-authorization.md).

Live pages: `GET /oracle/sandbox/smart/start` then Oracle redirect to `GET /smart/callback`. See [fhir-smart-interactive-authorization.md](../fhir-smart-interactive-authorization.md).

If discovery lists only `client_secret_basic` and `private_key_jwt`, public PKCE is still attempted. A rejected token POST is Result B: an explicit incompatibility, not a fabricated confidential client.

Live auth IT discovers SMART and builds a real authorization URL. Completing Oracle login in a browser is a manual step. Synthetic `lab-oauth` proves callback → token → `AccessTokenProvider`.

## Vendor-known APIs vs CapabilityStatement

`OracleHealthKnownApiSurface.assumesEveryR4Resource()` is `false`. Runtime inspection of a server's `CapabilityStatement` (`GET /metadata`) is [fhir-capability-discovery.md](../fhir-capability-discovery.md). That API is vendor-neutral; Oracle Health identity does not imply Patient is available.

## Real capability discovery (Task 034)

Task 034 validates the existing `FhirCapabilityDiscoveryService` against the real Oracle Health Millennium FHIR R4 Code sandbox. It does **not** add `OracleCapabilityStatement` or duplicate interpret logic.

```text
OracleHealthIntegrationProfile
        ↓
inspect (disabled = no HTTP)
        ↓
FhirServerProfile copy with authentication NONE
        ↓
GET /metadata   (configured base URL; no Bearer)
        ↓
FhirCapabilityDiscoveryService
        ↓
FhirServerCapabilities
```

`RoutingService.discoverCapabilities("oracle-health-sandbox")` is the wrong entry point here: that profile is `SMART_AUTHORIZATION_CODE` and would request a synthetic SMART token.

### Configuration vs live result

| | Configuration assumption | Live validation |
|---|---|---|
| Endpoint | `{ORACLE_HEALTH_SANDBOX_BASE_URL}/metadata` | Same configured base URL |
| Auth | Unknown until measured | **Not required** (HTTP 200, no `Authorization`) |
| FHIR version | Profile `fhir-version: R4` | Document `fhirVersion` = `4.0.1` |
| Patient | Not assumed by `OracleHealthKnownApiSurface` | Declared, with `read` and `search-type` |
| Every R4 resource | `assumesEveryR4Resource() == false` | 44 types; `Medication` and `Claim` absent |

Other live findings: software name empty; publisher “Oracle Health”; Patient also declares `create` and `patch` (`patch` is omitted by the internal interaction enum); `update`/`delete` are not declared for Patient; CORS + SMART-on-FHIR appear on `rest.security` but are not copied into `FhirServerCapabilities`; Patient operations `health-cards-issue` and `export` are not in the internal model.

Live IT: `mvn verify -Poracle-live` with `ORACLE_HEALTH_LIVE_IT=true`. Default `mvn test` / `-Pintegration` stay disabled and do not call Oracle.

Do not persist tokens for this GET. Do not add `client_secret_basic` or `private_key_jwt`.

## Authenticated Patient search (Task 035)

Task 033 issued a token with `hasPatient=false`. Task 035 therefore does **not** call `GET /Patient/{id}`. The first authorized operation is a bounded type search.

Live finding: Oracle Millennium rejected an unqualified search.

```text
GET /Patient?_count=1
Authorization: Bearer <token>
→ HTTP 400 VALIDATION_ERROR
```

`_count` is not a qualifying Patient search parameter. The lab therefore sends a generic `name` plus `_count=1`. The name `LabNoMatch` is a sentinel, not a real patient id and not a vendor host.

```text
Task 033 token  →  IssuedAccessTokenProvider
Task 034 capabilities.supports("Patient", SEARCH_TYPE)
        ↓
RoutingService.searchPatients(destination, tokenProvider, name)
        ↓
FhirService.searchPatientsByNameWithCount(name, 1)
        ↓
GET /Patient?name=LabNoMatch&_count=1   Authorization: Bearer <token>
```

`FhirService` does not import Oracle. There is no `OraclePatientClient`. The issued token is stored on the generic SMART coordinator after `/smart/callback`; the Oracle orchestrator consumes `AccessTokenProvider` only.

### Diagnosis

| Outcome | Meaning |
|---|---|
| `AUTHENTICATED_READ_SUCCEEDED` | Oracle returned a FHIR Bundle |
| `AUTHENTICATION_REQUIRED` | No usable token (or sandbox disabled) — no Patient HTTP |
| `AUTHENTICATION_REJECTED` | HTTP 401 |
| `AUTHORIZATION_DENIED` | HTTP 403 |
| `CAPABILITY_UNSUPPORTED` | Runtime model lacks Patient `search-type` — no Patient HTTP |
| `DEPENDENCY_FAILURE` | Timeout, connection, 5xx, rate limit (existing taxonomy) |

Authenticated ≠ authorized for every resource. Capability ≠ SMART scope. Both must be true for a successful search.

Lab page: `GET /oracle/sandbox/fhir/patient-search` after SMART login. It returns only the diagnosis (no token, no Patient JSON). Maven live IT without a browser session is `AUTHENTICATION_REQUIRED`.

## Controlled Patient context and read (Task 036)

Patient search is not Patient context. Standalone SMART (Task 033) ended with `hasPatient=false`. `fhirUser` is the authenticated user, not the clinical subject.

```text
Patient search        ≠  Patient context
OAuth identity        ≠  clinical Patient
fhirUser              ≠  Patient ID
```

The laboratory therefore requires an explicit opt-in identifier:

```dotenv
ORACLE_HEALTH_SANDBOX_PATIENT_ID=
```

Empty by default. Absent configuration sends **no** Patient HTTP and does not enumerate or guess identifiers.

```text
configured Patient ID
        +
usable SMART token
        +
capabilities.supports("Patient", READ)
        ↓
RoutingService.readPatient(destination, tokenProvider, patientId)
        ↓
FhirService.readPatient(logicalId)
        ↓
GET /Patient/{id}   Authorization: Bearer <token>
```

`FhirService` does not import Oracle. There is no `OraclePatientClient`. EHR launch is out of scope.

### Diagnosis

| Outcome | Meaning |
|---|---|
| `PATIENT_READ_SUCCEEDED` | Oracle returned a FHIR Patient — JSON is not rendered |
| `PATIENT_CONTEXT_NOT_CONFIGURED` | No sandbox Patient ID — no Patient HTTP |
| `AUTHENTICATION_REQUIRED` | No usable token (or sandbox disabled) — no Patient HTTP |
| `AUTHENTICATION_REJECTED` | HTTP 401 |
| `AUTHORIZATION_DENIED` | HTTP 403 |
| `CAPABILITY_UNSUPPORTED` | Runtime model lacks Patient `read` — no Patient HTTP |
| `PATIENT_NOT_FOUND` | HTTP 404 — no fallback search |
| `DEPENDENCY_FAILURE` | Timeout, connection, 5xx, rate limit (existing taxonomy) |

Lab page: `GET /oracle/sandbox/fhir/patient` after SMART login **and** a configured Patient ID. It returns only the diagnosis (no token, no Patient JSON, no demographics).

## Authenticated Condition search by Patient (Task 037)

Patient context is not clinical-resource authorization. A successful Patient read does not imply `Condition` access.

```text
configured Patient ID
        +
usable SMART token
        +
capabilities.supports("Condition", SEARCH_TYPE)
        ↓
RoutingService.searchConditions(destination, tokenProvider, patientId)
        ↓
FhirService.searchConditionsByPatientWithCount(id, 5, "problem-list-item")
        ↓
GET /Condition?patient={id}&category=problem-list-item&_count=5
Authorization: Bearer <token>
```

No `GET /Condition` without `patient`. No Patient discovery. There is no `OracleConditionClient`.

If `ORACLE_HEALTH_SANDBOX_PATIENT_ID` is empty: `PATIENT_CONTEXT_NOT_CONFIGURED` and no clinical HTTP.

A 200 Bundle with `hasEntries=false` is still a valid authenticated search. HTTP 403 usually means the SMART scope is Patient-only (`user/Patient.read`); Condition needs a matching scope in Code Console and `.env` (`user/Condition.read`). Do not invent scopes in Java. The search is bounded with FHIR `category=problem-list-item`. Some sandbox Condition searches take 30–40 seconds and return a large Bundle; the client socket timeout is 60 seconds for every destination.

### Diagnosis

| Outcome | Meaning |
|---|---|
| `CONDITION_SEARCH_SUCCEEDED` | Oracle returned a FHIR Bundle — JSON is not rendered |
| `PATIENT_CONTEXT_NOT_CONFIGURED` | No sandbox Patient ID — no Condition HTTP |
| `AUTHENTICATION_REQUIRED` | No usable token (or sandbox disabled) |
| `AUTHENTICATION_REJECTED` | HTTP 401 |
| `AUTHORIZATION_DENIED` | HTTP 403 |
| `CAPABILITY_UNSUPPORTED` | Runtime model lacks Condition `search-type` |
| `DEPENDENCY_FAILURE` | Timeout, connection, 5xx, rate limit (existing taxonomy) |

Lab page: `GET /oracle/sandbox/fhir/condition-search` after SMART login and a configured Patient ID.

## Architecture rules

- `FhirService` does not import `lab.healthcare.fhir.vendor.oracle`.
- Routing and resilience do not contain `if (vendor == ORACLE_HEALTH)`.
- There is no `OracleSmartConfigurationClient`, `OraclePkce`, `OracleTokenProvider`, or `OracleCapabilityStatement`.
- Disabled missing credentials must not break `fhir.active-server=local-hapi`.
- `FhirService` does not import Oracle authentication types.
