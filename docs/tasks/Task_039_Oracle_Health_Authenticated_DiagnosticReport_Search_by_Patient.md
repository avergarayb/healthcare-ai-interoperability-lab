# Task 039 — Oracle Health Authenticated DiagnosticReport Search by Patient

## Objective

Implement and validate an authenticated Oracle Health Millennium FHIR R4 search for `DiagnosticReport` resources associated with an explicit Patient context.

This task continues the controlled interoperability sequence established in Tasks 033–038.

---

## Background

The Oracle Health sandbox integration has already demonstrated:

| Task | Capability | Live result |
|---|---|---|
| 033 | SMART Authorization Code + PKCE S256 | Access token issued |
| 034 | Oracle CapabilityStatement discovery | HTTP 200 |
| 035 | Authenticated Patient search | HTTP 200 Bundle |
| 036 | Controlled Patient read | HTTP 200 Patient |
| 037 | Authenticated Condition search by Patient | HTTP 200 Bundle |
| 038 | Authenticated Observation search by Patient | HTTP 200 Bundle |

Task 039 validates a different clinical resource.

A successful Observation search does not imply DiagnosticReport authorization or runtime support.

---

# WHAT

Implement:

```text
GET /DiagnosticReport?patient={patientId}&_count=5
Authorization: Bearer <SMART access token>
```

Expose a safe laboratory endpoint:

```text
GET /oracle/sandbox/fhir/diagnostic-report-search
```

The endpoint must return only a diagnostic result.

It must not expose:

- access tokens
- raw OAuth responses
- Patient demographics
- DiagnosticReport JSON
- report contents
- clinical attachments

---

# WHY

The purpose is to independently demonstrate that Oracle Health accepts an authenticated FHIR request for `DiagnosticReport`.

The architecture must prove:

```text
SMART authentication

        +

explicit Patient context

        +

runtime CapabilityStatement support

        +

DiagnosticReport SMART authorization

        ↓

real clinical FHIR operation
```

These are separate concerns.

```text
Condition access
        ≠
Observation access
        ≠
DiagnosticReport access
```

A successful HTTP 200 for one resource must never be interpreted as authorization for another resource.

---

# HOW

## 1. Patient context

Reuse the existing Task 036 Patient context model.

The Patient ID must come only from the explicit configured context:

```text
ORACLE_HEALTH_SANDBOX_PATIENT_ID
```

No Patient enumeration.

No ID guessing.

No fallback search.

No extraction from `fhirUser`.

The existing context source remains:

```text
CONFIGURED
```

---

## 2. Capability validation

Before the FHIR request, verify runtime support using the Oracle CapabilityStatement discovered by Task 034.

Required capability:

```text
DiagnosticReport + SEARCH_TYPE
```

Conceptually:

```java
capabilities.supports("DiagnosticReport", SEARCH_TYPE)
```

If unsupported:

```text
CAPABILITY_UNSUPPORTED
```

Do not perform the FHIR search.

---

## 3. Authentication

Reuse the token issued by the Task 033 interactive SMART flow.

Use:

```text
IssuedAccessTokenProvider
```

Do not:

- generate synthetic tokens
- add client secrets
- implement `client_secret_basic`
- implement `private_key_jwt`
- persist tokens
- print token values

The operation must use the real Bearer token obtained from the current in-memory SMART authorization session.

---

## 4. Routing

Follow the existing generic architecture:

```text
vendor.oracle
        ↓
RoutingService
        ↓
FhirService
        ↓
HAPI FHIR
```

Add the generic routing operation required for DiagnosticReport search.

The generic FHIR layer must not import Oracle-specific classes.

Do not create:

```text
OracleDiagnosticReportClient
OracleDiagnosticReportSearchClient
```

---

## 5. Generic FHIR service

Add a generic operation equivalent to:

```text
searchDiagnosticReportsByPatientWithCount(patientId, 5)
```

The request must be bounded:

```text
DiagnosticReport?patient={patientId}&_count=5
```

Do not use an unqualified:

```text
GET /DiagnosticReport
```

The laboratory must remain explicitly scoped to one configured Patient.

---

## 6. Timeout behavior

Reuse the existing generic timeout configuration of 60 seconds.

Do not add:

```text
if Oracle
```

or any Oracle-specific timeout.

The same transport policy must remain reusable for other FHIR destinations.

A timeout is classified through the existing dependency taxonomy.

---

# Expected outcomes

The operation must produce a safe diagnostic result.

Recommended outcomes:

| Outcome | Meaning |
|---|---|
| `DIAGNOSTIC_REPORT_SEARCH_SUCCEEDED` | Oracle returned HTTP 200 Bundle |
| `PATIENT_CONTEXT_NOT_CONFIGURED` | No configured Patient ID; zero Patient HTTP calls |
| `AUTHENTICATION_REQUIRED` | No usable SMART token |
| `AUTHENTICATION_REJECTED` | HTTP 401 |
| `AUTHORIZATION_DENIED` | HTTP 403 |
| `CAPABILITY_UNSUPPORTED` | Runtime capabilities do not declare DiagnosticReport search-type |
| `DEPENDENCY_FAILURE` | Timeout, network failure, or server-side dependency failure |

A successful empty Bundle is still:

```text
DIAGNOSTIC_REPORT_SEARCH_SUCCEEDED
```

with:

```text
hasEntries=false
```

A successful Bundle with entries must not expose the reports themselves.

---

# Scope

## In scope

- Oracle Health sandbox
- FHIR R4
- DiagnosticReport
- explicit configured Patient context
- authenticated search
- bounded `_count=5`
- runtime capability validation
- safe diagnostic response
- unit tests
- integration tests
- optional live validation

## Out of scope

Do not implement:

- DiagnosticReport detail read
- attachment download
- Binary retrieval
- DocumentReference
- PDF extraction
- report interpretation
- clinical summarization
- AI or LLM processing
- patient browsing
- Patient ID discovery
- bulk export
- writes
- EHR launch
- automatic SMART launch Patient extraction
- `client_secret_basic`
- `private_key_jwt`
- refresh-token persistence

---

# Security constraints

The implementation must preserve the established laboratory boundaries.

Never log or expose:

- access token
- authorization code
- PKCE verifier
- Patient demographics
- raw DiagnosticReport Bundle
- report text
- attachments

The browser endpoint should expose only metadata such as:

```text
outcome
destination
resourceType
responseType
httpStatus
contextSource
hasPatientContext
hasEntries
detail
```

---

# Architecture principle

Preserve:

```text
OAuth identity
        ≠
Clinical Patient context
        ≠
FHIR resource authorization
        ≠
Clinical interpretation
```

Also preserve the dependency direction:

```text
vendor.oracle
        ↓
routing
        ↓
FhirService
        ↓
HAPI FHIR
```

Never:

```text
FhirService → vendor.oracle
```

---

# Configuration

Task 039 should reuse:

```properties
ORACLE_HEALTH_SANDBOX_ENABLED=true
ORACLE_HEALTH_SANDBOX_CLIENT_ID=...
ORACLE_HEALTH_SANDBOX_BASE_URL=...
ORACLE_HEALTH_SANDBOX_AUD=...
ORACLE_HEALTH_SANDBOX_REDIRECT_URI=http://localhost:8081/smart/callback
ORACLE_HEALTH_SANDBOX_SCOPE=...
ORACLE_HEALTH_SANDBOX_SMART_CONFIGURATION_URL=...
ORACLE_HEALTH_SANDBOX_PATIENT_ID=...
```

For the live DiagnosticReport operation, the registered Oracle application and requested SMART scope must include the appropriate DiagnosticReport read permission, expected to be:

```text
user/DiagnosticReport.read
```

Do not commit real values from `.env`.

---

# Tests

## Unit tests

Cover:

- successful Bundle response
- empty Bundle
- Patient context missing
- token missing or expired
- capability unsupported
- HTTP 401
- HTTP 403
- timeout / dependency failure
- generic architecture boundaries

## Integration tests

The integration suite must not require Oracle network access by default.

```bash
mvn clean verify -Pintegration
```

must remain deterministic when the Oracle sandbox is disabled.

## Live validation

Live Oracle validation remains explicit and opt-in.

The browser SMART login is interactive and cannot be fabricated by Maven.

Suggested validation flow:

1. Configure `.env`.
2. Start the service:

```bash
cd services/fhir-integration-service
mvn spring-boot:run
```

3. Start a fresh SMART authorization:

```text
http://localhost:8081/oracle/sandbox/smart/start
```

4. Complete Oracle login.
5. Confirm that the callback issued an access token without exposing it.
6. Open:

```text
http://localhost:8081/oracle/sandbox/fhir/diagnostic-report-search
```

Expected technical success:

```text
outcome=DIAGNOSTIC_REPORT_SEARCH_SUCCEEDED
resourceType=DiagnosticReport
responseType=Bundle
httpStatus=200
```

`hasEntries` may be either `true` or `false`.

---

# Acceptance criteria

Task 039 is complete when:

- [ ] DiagnosticReport runtime `search-type` capability is checked.
- [ ] The request uses an explicit Patient context.
- [ ] No Patient enumeration occurs.
- [ ] A real SMART Bearer token is used.
- [ ] No token is exposed.
- [ ] The search is bounded with `_count=5`.
- [ ] The generic FHIR layer remains vendor-independent.
- [ ] No Oracle-specific FHIR client is created.
- [ ] 401 and 403 are diagnosed separately.
- [ ] Timeout/network failures map to dependency failure.
- [ ] Raw clinical JSON is not rendered.
- [ ] Unit tests pass.
- [ ] Integration tests pass without requiring Oracle by default.
- [ ] Live validation is opt-in.
- [ ] If Oracle returns HTTP 200, the operation is recorded as a successful authenticated DiagnosticReport search.

---

# Proposed branch

```text
feature/oracle-health-authenticated-diagnostic-report-search
```

# Proposed commit

```text
feat: add Oracle Health authenticated DiagnosticReport search by Patient
```

---

# Next architectural boundary

Task 039 still does **not** create a clinical snapshot or AI input.

After Patient, Condition, Observation, and DiagnosticReport interoperability has been independently demonstrated, a later task can evaluate a controlled aggregation layer.

That future layer must explicitly define:

- which resources are collected
- maximum counts
- timeout budget
- partial failure behavior
- normalization
- data minimization
- privacy boundaries
- what, if anything, is allowed to reach an AI system

No such aggregation belongs in Task 039.
