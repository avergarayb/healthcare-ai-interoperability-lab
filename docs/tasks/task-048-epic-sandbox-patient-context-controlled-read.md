# Task 048 — Epic Sandbox Patient Context + Controlled Patient Read

## WHAT

Implement the explicitly configured Patient context and one controlled real FHIR operation against `epic-sandbox`:

```http
GET /Patient/{id}
```

Flow:

```text
SMART token in memory (Task 046)
        +
EPIC_SANDBOX_PATIENT_ID from .env
        +
FhirServerCapabilities from Task 047
        ↓
capability.supports("Patient", READ)
        ↓
RoutingService.readPatient("epic-sandbox", issuedTokenProvider, patientId)
        ↓
FhirService.readPatient(logicalId)
        ↓
GET /Patient/{id}
Authorization: Bearer <token>
        ↓
FhirPatientReadResult
        ↓
blind lab
```

STOP after the controlled Patient read. No Patient search, snapshot, projection, contract, agent, LLM, or `ai-service`.

## WHY

Task 047 proved live Epic `/metadata` discovery:

```text
status=SUCCESS
httpStatus=200
destination=epic-sandbox
fhirVersion=4.0.1
resourceTypes=60
```

Task 046 proved SMART Authorization Code + PKCE authentication, but the standalone launch ended with:

```text
hasPatient=false
```

Therefore `fhirUser` and SMART launch context must not be interpreted as a Patient ID. Patient context for this task is exclusively the configured `EPIC_SANDBOX_PATIENT_ID`.

This mirrors Oracle Task 036 while respecting the Epic standalone SMART behavior.

## FIRST STEP — INSPECT EXISTING CODE

Before implementation, inspect:

```text
PatientContext
PatientContextSource
PatientContexts
RoutingService.readPatient
FhirPatientReadOutcome
FhirPatientReadResult
EpicSandboxCapabilityDiscoveryService
EpicSandboxAuthenticationService
```

Also inspect the Oracle Task 036 implementation and its lab/controller pattern.

Reuse the existing generic abstractions. Do not create Epic-specific equivalents.

## HARD BOUNDARIES

### In scope

- `epic-sandbox`
- SMART token from Task 046
- configured Patient context
- capability result from Task 047
- `supports("Patient", READ)`
- `RoutingService.readPatient(...)`
- generic `FhirService.readPatient(...)`
- exactly one real `GET /Patient/{id}`
- existing generic Patient-read result
- blind lab
- unit/integration tests
- opt-in Epic LiveIT

### Out of scope

Do not implement:

- Patient search or fallback search
- Condition
- Observation
- DiagnosticReport
- MedicationRequest
- snapshot
- projection
- `ModelBoundaryContract`
- agent
- LLM
- `ai-service`
- Production Epic
- confidential OAuth
- new SMART flow
- Epic-specific FHIR client
- cache
- Patient ID enumeration

## PATIENT CONTEXT

Reuse:

```java
PatientContext
PatientContextSource.CONFIGURED
PatientContexts.fromConfigured(...)
```

or the exact generic equivalent already present.

The real value must exist only in local `.env`.

Add only this empty placeholder to `.env.example`:

```dotenv
EPIC_SANDBOX_PATIENT_ID=
```

Never put a real or invented Patient ID in:

- source code
- tests
- `.env.example`
- documentation
- README
- commits
- PR
- screenshots
- logs
- lab output
- chat

Do not derive the Patient ID from `fhirUser`, token claims, SMART launch context, search, enumeration, scraping, or guessing.

## CAPABILITY CHECK

Reuse the capability discovery established by Task 047:

```text
EpicSandboxCapabilityDiscoveryService
        ↓
FhirCapabilityDiscoveryService
        ↓
FhirServerCapabilities
```

Before the Patient HTTP operation, check:

```java
capabilities.supports("Patient", READ)
```

If unsupported:

```text
CAPABILITY_UNSUPPORTED
HTTP 409
```

and perform zero Patient HTTP requests.

Do not use Patient search as fallback.

Do not assume capability from Epic documentation or app registration. The runtime `CapabilityStatement` is authoritative.

## SMART TOKEN

Reuse:

```text
IssuedAccessTokenProvider
```

from Task 046.

Do not implement another authentication flow, token store, refresh implementation, confidential client, callback, or login.

The token remains in memory and must never be exposed in the lab or logs.

## PATIENT READ

After token, configured context, and Patient READ capability are available, invoke:

```java
RoutingService.readPatient(
    "epic-sandbox",
    issuedTokenProvider,
    patientId
)
```

Reuse:

```text
RoutingService
    ↓
FhirService
    ↓
HAPI FHIR
```

The real operation must be:

```http
GET /Patient/{id}
Authorization: Bearer <token>
```

No search or fallback.

## DO NOT MODIFY FhirService FOR EPIC

Do not add Epic branches such as:

```java
if (destination.equals("epic-sandbox"))
```

Do not add:

```text
readEpicPatient(...)
EpicFhirService
EpicPatientService
```

`FhirService.readPatient(logicalId)` must remain generic.

Do not introduce imports from `vendor.epic`, capability, SMART, snapshot, projection, modelboundary, or agent layers into `FhirService`.

## NO EPIC-SPECIFIC CLIENT

Do not create:

```text
EpicPatientClient
EpicPatientContext
EpicFhirService
EpicPatientService
EpicPatientRepository
```

Epic-specific code remains only at the vendor boundary required to resolve/configure the Epic destination and connect existing generic abstractions.

## OUTCOMES

Reuse the existing generic taxonomy where possible.

| Outcome | HTTP | Required behavior |
|---|---:|---|
| `PATIENT_READ_SUCCEEDED` | 200 | Controlled Patient read succeeded; no JSON exposed |
| `PATIENT_CONTEXT_NOT_CONFIGURED` | 409 | Zero clinical HTTP |
| `AUTHENTICATION_REQUIRED` | 401 | No token exposed |
| `AUTHENTICATION_REJECTED` | 401 | No fallback |
| `AUTHORIZATION_DENIED` | 403 | No fallback |
| `CAPABILITY_UNSUPPORTED` | 409 | Zero Patient HTTP |
| `PATIENT_NOT_FOUND` | 404 | No fallback search |
| `DEPENDENCY_FAILURE` | 502 | Use generic diagnostics/error model |

Do not create an Epic-only error taxonomy if an existing generic taxonomy fits.

## CONTROLLED READ SEMANTICS

The configured value represents the FHIR logical ID.

The operation is:

```http
GET /Patient/{logicalId}
```

The lab endpoint:

```http
GET /epic/sandbox/fhir/patient
```

must use configured context and must not accept an arbitrary Patient ID as a query/path parameter.

This prevents Patient enumeration.

## LAB

Add:

```http
GET /epic/sandbox/fhir/patient
```

Blind output may contain only safe operational data, for example:

```text
status=SUCCESS
httpStatus=200
destination=epic-sandbox
patientRead=SUCCEEDED
```

Never expose:

- Patient ID
- Patient JSON
- name
- DOB
- identifiers
- gender
- address
- telecom
- narrative
- clinical fields
- token
- Authorization header
- raw FHIR body

A successful FHIR Patient response must not be returned by the lab.

## EPIC-SPECIFIC MATIZ

Do not modify Task 046 to obtain `hasPatient=true`.

For this standalone flow:

```text
hasPatient=false
```

is expected.

Do not interpret:

```text
fhirUser
```

as a Patient ID.

Do not introduce `launch/patient` into this standalone flow.

## URL / HOST BOUNDARY

Do not add new Epic hosts to Java under `vendor.epic`.

In particular, do not introduce:

```java
https://fhir.epic.com
```

as a new hardcoded host.

Reuse the existing Epic configuration.

The existing allowed `EpicSandboxEndpoints.FHIR_R4_BASE` exception from Task 029 remains unchanged.

## NO CACHE

Do not introduce caching of:

- Patient context
- CapabilityStatement
- `FhirServerCapabilities`
- Patient resource

The in-memory token from Task 046 is existing authentication state, not a new Task 048 cache.

## TEST STRATEGY

### Default tests

`*Test.java` and `*IT.java` must not require Epic network access.

### Unit tests

Cover at least:

1. configured Patient context produces `PatientContextSource.CONFIGURED`;
2. missing context produces `PATIENT_CONTEXT_NOT_CONFIGURED` / HTTP 409 and does not invoke Patient read;
3. supported `Patient READ` delegates to `RoutingService.readPatient(...)`;
4. unsupported Patient READ produces `CAPABILITY_UNSUPPORTED` / HTTP 409 and zero Patient HTTP;
5. authentication required maps to HTTP 401;
6. authentication rejected maps to HTTP 401;
7. authorization denied maps to HTTP 403;
8. Patient not found maps to HTTP 404 and performs no fallback search;
9. dependency failure maps to HTTP 502.

### HTTP-level test

If the project has a reusable local HTTP test-server pattern, verify:

```http
GET /Patient/{configuredId}
Authorization: Bearer <synthetic-test-token>
```

Assert:

- method GET;
- path `/Patient/{id}`;
- Authorization header is present;
- no Patient search occurs;
- generic Patient-read result is produced;
- raw clinical JSON is not exposed by the lab.

Use only synthetic test data.

## LIVE TEST

Create/adapt a `*LiveIT.java`.

Epic live execution must be opt-in:

```powershell
$env:EPIC_SANDBOX_LIVE_IT="true"
```

Without the flag:

```text
SKIPPED
```

with zero Epic network access.

LiveIT must:

1. reuse SMART authentication from Task 046;
2. resolve `EPIC_SANDBOX_PATIENT_ID`;
3. verify Patient READ capability;
4. perform one controlled Patient read;
5. verify the result;
6. never print Patient ID;
7. never print token;
8. never print raw Patient JSON.

## ACCEPTANCE CRITERIA

- [ ] SMART authentication from Task 046 is reused.
- [ ] `hasPatient=false` is handled as expected.
- [ ] Patient context comes exclusively from `EPIC_SANDBOX_PATIENT_ID`.
- [ ] `.env.example` contains an empty `EPIC_SANDBOX_PATIENT_ID=`.
- [ ] No real Patient ID exists outside local `.env`.
- [ ] Existing generic Patient context abstractions are reused.
- [ ] Existing generic Patient-read result is reused.
- [ ] `RoutingService.readPatient(...)` is reused.
- [ ] Generic `FhirService.readPatient(...)` is reused.
- [ ] `FhirService` receives no Epic-specific logic.
- [ ] No Epic-specific Patient client/service/context is created.
- [ ] Patient capability is checked before Patient HTTP.
- [ ] `supports("Patient", READ)` is used.
- [ ] Capability comes from the Task 047 discovery path.
- [ ] Missing context returns `PATIENT_CONTEXT_NOT_CONFIGURED` / 409.
- [ ] Missing context causes zero clinical HTTP.
- [ ] Unsupported capability returns `CAPABILITY_UNSUPPORTED` / 409.
- [ ] Unsupported capability causes zero Patient HTTP.
- [ ] Patient read uses the Task 046 SMART access token.
- [ ] Real operation is `GET /Patient/{id}`.
- [ ] No Patient search exists.
- [ ] No Patient search fallback exists.
- [ ] 404 maps to `PATIENT_NOT_FOUND`.
- [ ] Authentication-required maps to 401.
- [ ] Authentication-rejected maps to 401.
- [ ] Authorization-denied maps to 403.
- [ ] Dependency failure maps to 502.
- [ ] Lab endpoint is `GET /epic/sandbox/fhir/patient`.
- [ ] Lab output is blind.
- [ ] Patient ID is not exposed.
- [ ] Patient JSON is not exposed.
- [ ] Demographics are not exposed.
- [ ] Token is not exposed.
- [ ] Default tests do not access Epic.
- [ ] LiveIT requires `EPIC_SANDBOX_LIVE_IT=true`.
- [ ] No new Epic host is hardcoded.
- [ ] Generic timeout remains unchanged.
- [ ] No cache is introduced.
- [ ] No snapshot/projection/contract/agent/LLM/`ai-service` work is introduced.

## DOCUMENTATION / PROGRESS

Update:

```text
docs/progress/progress-log.md
```

with safe evidence such as:

```text
Task 048 — Epic Sandbox Patient Context + Controlled Read
status=SUCCESS
destination=epic-sandbox
patientRead=SUCCEEDED
httpStatus=200
patientContextSource=CONFIGURED
```

Never include Patient ID, token, Patient JSON, or demographics.

## GIT

Branch:

```text
feature/epic-sandbox-patient-context-read
```

Commit:

```text
feat: add Epic sandbox patient context and controlled read
```

Never commit:

```text
.env
```

or any file containing secrets, tokens, client IDs, or real Patient IDs.

## VALIDATION

Run normal Maven verification.

For PowerShell:

- do not use `&&`;
- use `curl.exe`.

Keep local tests separate from Epic LiveIT.

## CONCEPT

The architectural proof is:

```text
                    Epic Sandbox
                         │
              SMART Authorization Code
                       + PKCE
                         │
                         ▼
             IssuedAccessTokenProvider
                         │
                         │ Bearer token
                         │
EPIC_SANDBOX_PATIENT_ID ─┤
                         ▼
               PatientContext
                  CONFIGURED
                         │
                         ▼
          FhirServerCapabilities
             supports Patient READ
                         │
                         ▼
               RoutingService
                         │
                         ▼
                  FhirService
                         │
                         ▼
              HAPI FHIR Client
                         │
                         ▼
             GET /Patient/{id}
                         │
                         ▼
             FhirPatientReadResult
                         │
                         ▼
                  Blind Lab UI
```

Authentication and Patient context are controlled inputs. Capability support is discovered dynamically. The Patient read remains vendor-neutral.

## STOP CONDITION

Once this is proven:

```text
configured Patient context
        +
SMART access token
        +
Patient READ capability
        ↓
GET /Patient/{id}
        ↓
FhirPatientReadResult
        ↓
blind lab
```

**STOP.**

Do not continue into Patient search, Condition, Observation, DiagnosticReport, MedicationRequest, snapshot, projection, contract, agent, LLM, or `ai-service`.
