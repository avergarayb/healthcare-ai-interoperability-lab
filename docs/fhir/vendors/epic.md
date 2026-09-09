# Epic integration profile

Task 029 prepares an Epic-specific integration profile. Task 046 adds interactive SMART Authorization Code + PKCE against a configured Epic sandbox. Task 047 validates **real CapabilityStatement discovery** (`GET /metadata`, public) through the existing provider-neutral model. Task 048 adds an explicit sandbox Patient context and a capability-aware `GET /Patient/{id}`. Task 049 searches `Condition` for that configured Patient. Task 050 searches `Observation` the same way. It does **not** search Patient or assemble a snapshot.

Read this after [fhir-smart-real-world-readiness.md](../fhir-smart-real-world-readiness.md) and [fhir-server-configuration.md](../fhir-server-configuration.md).

## What this task is

Epic is a **vendor profile**, not a fork of `FhirService`. Generic FHIR operations stay vendor-neutral. Routing still selects a destination name (`epic-sandbox`). SMART types from Task 028 are reused.

```text
FhirServerProfile (epic-sandbox, disabled)
        ↓
FhirVendor = EPIC
        ↓
EpicIntegrationProfile
        ↓
EpicCapabilities + EpicReadinessState
        ↓
EpicProfileValidator
```

Default tests do not log in to [Epic on FHIR](https://fhir.epic.com/). A local `.env` can enable `epic-sandbox`, start `GET /epic/sandbox/smart/start`, and open `GET /epic/sandbox/fhir/capabilities`. No Patient read against Epic.

## Official sandbox identifiers

Epic's public developer documentation (see [fhir.epic.com/Documentation](https://fhir.epic.com/Documentation), [Developer](https://fhir.epic.com/Developer/), [SMART test](https://fhir.epic.com/test/smart)) publishes an Epic-hosted non-production R4 base:

```text
https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/
```

That URL is a **public sandbox identifier**, not a customer production endpoint. A later customer-specific Interconnect URL is configuration, not a Java constant. Treat current official Epic documentation as authoritative if the sandbox URL changes.

## YAML placeholder

Profile `epic-sandbox` is **disabled** by default. Local startup still uses `local-hapi`. Credentials come from the environment; Git has empty defaults.

```yaml
epic-sandbox:
  enabled: ${EPIC_SANDBOX_ENABLED:false}
  vendor: EPIC
  base-url: https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/
  fhir-version: R4
  authentication:
    type: SMART_AUTHORIZATION_CODE
    client-id: ${EPIC_SANDBOX_CLIENT_ID:}
    redirect-uri: ${EPIC_SANDBOX_REDIRECT_URI:}
    scope: ${EPIC_SANDBOX_SCOPE:}
    aud: https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/
    smart-configuration-url: ${EPIC_SANDBOX_SMART_CONFIGURATION_URL:}
  vendor-integration:
    environment: SANDBOX
    launch-mode: STANDALONE
    user-context: PATIENT
    client-authentication: PUBLIC_PKCE
    patient-id: ${EPIC_SANDBOX_PATIENT_ID:}
```

Discovery is **not** concatenated from `fhir.epic.com` in Java. If Epic's well-known URL differs from an assumed pattern, `smart-configuration-url` wins. Do not commit `EPIC_SANDBOX_CLIENT_SECRET` or private keys.

## Environments, launch, users, auth

| Concept | Values in this task | Runtime |
|---|---|---|
| Environment | `SANDBOX` (prepared), `PRODUCTION` (represented, unused) | No production customer connection |
| Launch | `STANDALONE`, `EHR_LAUNCH` | EHR launch is readiness (`iss` / `launch`), not Hyperspace |
| User context | `PATIENT`, `CLINICIAN_STAFF` | Metadata only; scopes and Epic app registration decide access |
| Client auth | `PUBLIC_PKCE`, `CLIENT_SECRET`, `PRIVATE_KEY_JWT` | Only `PUBLIC_PKCE` is implemented (Task 028) |

Epic documents `private_key_jwt` for some confidential / backend scenarios and persistent access / refresh for qualifying confidential clients. This lab **represents** those modes and marks them unsupported at runtime. It does not fake JWT assertion.

## Readiness is not certification

| State | Meaning |
|---|---|
| `NOT_CONFIGURED` | Public sandbox URL may be present; client ID / discovery still empty |
| `CONFIGURED` | Required fields present; auth mode may be unimplemented |
| `SMART_COMPATIBLE` | Authorization Code + PKCE S256 can be built from this profile |
| `READY_FOR_SANDBOX` | SMART-compatible sandbox configuration — **not** Epic-certified |

There is no `CERTIFIED`, `PRODUCTION_READY`, or `EPIC_APPROVED` state.

## Vendor-known APIs vs CapabilityStatement

Epic publishes a resource/API catalog rather than implying every FHIR R4 interaction. `EpicKnownApiSurface` is a placeholder: this lab does **not** hardcode that catalog. Runtime inspection of a server's `CapabilityStatement` is Task 047 and [fhir-capability-discovery.md](../fhir-capability-discovery.md). That API is vendor-neutral; Epic identity does not imply Patient is available.

## Secure sandbox SMART authentication (Task 046)

When `EPIC_SANDBOX_ENABLED=true` and the SMART fields are set, `GET /epic/sandbox/smart/start` discovers the configured `/.well-known/smart-configuration` and starts Authorization Code + PKCE S256. The browser returns to the generic `GET /smart/callback`.

The token stays in memory. The page never prints the token, code, verifier, or client ID. Standalone `hasPatient=false` is valid. This task does not convert `fhirUser` into a Patient ID. Clinical Patient access starts at Task 048.

See [fhir-smart-interactive-authorization.md](../fhir-smart-interactive-authorization.md).

## Real capability discovery (Task 047)

Task 047 validates the existing `FhirCapabilityDiscoveryService` against the configured Epic sandbox. It does **not** add `EpicCapabilityStatement` or duplicate interpret logic.

```text
EpicIntegrationProfile
        ↓
enabled sandbox + configured base URL
        ↓
FhirServerProfile copy with authentication NONE
        ↓
GET /metadata   (configured base URL; no Bearer)
        ↓
FhirCapabilityDiscoveryService
        ↓
FhirServerCapabilities
```

`RoutingService.discoverCapabilities("epic-sandbox")` is the wrong entry point here: that profile is `SMART_AUTHORIZATION_CODE` and would request a synthetic SMART token.

Lab page: `GET /epic/sandbox/fhir/capabilities`. It shows only discovery status, HTTP status, FHIR version, destination, and the runtime resource-type count. It does not show the token, Patient ID, or raw CapabilityStatement JSON. Public `/metadata` does not use the SMART token from Task 046.

Live observation (Epic sandbox, no Authorization header):

| Observation | Value |
|---|---|
| HTTP | `200` |
| Auth required | No (Case A — public metadata) |
| `fhirVersion` | `4.0.1` |
| Resources declared | `60` types at runtime. Do not treat this as a catalog constant. |

The runtime resource count comes from the live `CapabilityStatement`. Do not infer it from Epic's application API catalog or from `EpicKnownApiSurface`.

Live IT: `mvn test -Pepic-live -Dtest=EpicSandboxCapabilityLiveIT` with `EPIC_SANDBOX_LIVE_IT=true`. Default `mvn test` / `-Pintegration` stay disabled and do not call Epic.

Do not persist tokens for this GET. Do not add `client_secret_basic` or `private_key_jwt`. This is **not** Patient search, Patient read, snapshot, projection, model boundary, or an agent.

## Controlled Patient context and read (Task 048)

Patient search is not Patient context. Standalone SMART (Task 046) ended with `hasPatient=false`. `fhirUser` is the authenticated user, not the clinical subject.

```text
OAuth identity        ≠  clinical Patient
fhirUser              ≠  Patient ID
hasPatient=false      ≠  no Patient exists
```

The laboratory therefore requires an explicit opt-in identifier:

```dotenv
EPIC_SANDBOX_PATIENT_ID=
```

Empty by default. Absent configuration sends **no** Patient HTTP and does not enumerate or guess identifiers.

```text
configured Patient ID
        +
usable SMART token (Task 046)
        +
capabilities.supports("Patient", READ)   (Task 047 path)
        ↓
RoutingService.readPatient(destination, tokenProvider, patientId)
        ↓
FhirService.readPatient(logicalId)
        ↓
GET /Patient/{id}   Authorization: Bearer <token>
```

`FhirService` does not import Epic. There is no `EpicPatientClient`. EHR launch is out of scope. Do not change Task 046 to obtain `hasPatient=true`.

### Diagnosis

| Outcome | Meaning |
|---|---|
| `PATIENT_READ_SUCCEEDED` | Epic returned a FHIR Patient — JSON is not rendered |
| `PATIENT_CONTEXT_NOT_CONFIGURED` | No sandbox Patient ID — no Patient HTTP |
| `AUTHENTICATION_REQUIRED` | No usable token (or sandbox disabled) — no Patient HTTP |
| `AUTHENTICATION_REJECTED` | HTTP 401 |
| `AUTHORIZATION_DENIED` | HTTP 403 |
| `CAPABILITY_UNSUPPORTED` | Runtime model lacks Patient `read` — no Patient HTTP |
| `PATIENT_NOT_FOUND` | HTTP 404 — no fallback search |
| `DEPENDENCY_FAILURE` | Timeout, connection, 5xx, rate limit (existing taxonomy) |

Lab page: `GET /epic/sandbox/fhir/patient` after SMART login **and** a configured Patient ID. It returns only the diagnosis (no token, no Patient ID, no Patient JSON, no demographics).

Maven LiveIT cannot complete browser login. With `EPIC_SANDBOX_LIVE_IT=true` it diagnoses `AUTHENTICATION_REQUIRED` or `PATIENT_CONTEXT_NOT_CONFIGURED` when the session or ID is absent. The SUCCESS evidence is the lab page after a human SMART login.

## Authenticated Condition search by Patient (Task 049)

Patient read is not a clinical collection. After Task 048, the laboratory runs one generic Condition `SEARCH_TYPE` for the same configured Patient.

```text
configured Patient ID
        +
usable SMART token (Task 046)
        +
capabilities.supports("Condition", SEARCH_TYPE)   (Task 047 path)
        ↓
RoutingService.searchConditions(destination, tokenProvider, patientId)
        ↓
FhirService.searchConditionsByPatientWithCount(id, 5, "problem-list-item")
        ↓
GET /Condition?patient={id}&_count=5&category=problem-list-item
```

`_count=5` is a request, not a retention ceiling. An empty Bundle is success with `hasEntries=false`. There is no `EMPTY` outcome and no Epic-specific category workaround.

### Diagnosis

| Outcome | Meaning |
|---|---|
| `CONDITION_SEARCH_SUCCEEDED` | Epic returned a FHIR Bundle — JSON is not rendered |
| `PATIENT_CONTEXT_NOT_CONFIGURED` | No sandbox Patient ID — no Condition HTTP |
| `AUTHENTICATION_REQUIRED` | No usable token (or sandbox disabled) — no Condition HTTP |
| `AUTHENTICATION_REJECTED` | HTTP 401 |
| `AUTHORIZATION_DENIED` | HTTP 403 |
| `CAPABILITY_UNSUPPORTED` | Runtime model lacks Condition `search-type` — no Condition HTTP |
| `DEPENDENCY_FAILURE` | Timeout, connection, 5xx, rate limit (existing taxonomy) |

Lab page: `GET /epic/sandbox/fhir/condition-search` after SMART login **and** a configured Patient ID. It returns only the diagnosis (no token, no Patient ID, no Condition JSON, no codes).

## Authenticated Observation search by Patient (Task 050)

After Task 049, the laboratory runs one generic Observation `SEARCH_TYPE` for the same configured Patient.

```text
configured Patient ID
        +
usable SMART token (Task 046)
        +
capabilities.supports("Observation", SEARCH_TYPE)   (Task 047 path)
        ↓
RoutingService.searchObservations(destination, tokenProvider, patientId)
        ↓
FhirService.searchObservationsByPatientWithCount(id, 5, "vital-signs")
        ↓
GET /Observation?patient={id}&_count=5&category=vital-signs
```

`_count=5` is a request, not a retention ceiling. The category is the generic HL7 `vital-signs` code, the same for Oracle and Epic. An empty Bundle is success with `hasEntries=false`. There is no `EMPTY` outcome and no Epic-specific query workaround.

### Diagnosis

| Outcome | Meaning |
|---|---|
| `OBSERVATION_SEARCH_SUCCEEDED` | Epic returned a FHIR Bundle — JSON is not rendered |
| `PATIENT_CONTEXT_NOT_CONFIGURED` | No sandbox Patient ID — no Observation HTTP |
| `AUTHENTICATION_REQUIRED` | No usable token (or sandbox disabled) — no Observation HTTP |
| `AUTHENTICATION_REJECTED` | HTTP 401 |
| `AUTHORIZATION_DENIED` | HTTP 403 |
| `CAPABILITY_UNSUPPORTED` | Runtime model lacks Observation `search-type` — no Observation HTTP |
| `DEPENDENCY_FAILURE` | Timeout, connection, 5xx, rate limit (existing taxonomy) |

Lab page: `GET /epic/sandbox/fhir/observation-search` after SMART login **and** a configured Patient ID. It returns only the diagnosis (no token, no Patient ID, no Observation JSON, no codes or values).

## Architecture rules

- `FhirService` does not import `lab.healthcare.fhir.vendor.epic`.
- `RoutingService` does not contain Epic OAuth logic.
- SMART discovery / PKCE stay in `lab.healthcare.fhir.smart`.
- Disabled missing credentials must not break `fhir.active-server=local-hapi`.
- Oracle Health is a sibling vendor profile; see [oracle-health.md](oracle-health.md).
