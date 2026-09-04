# Task 040 — Oracle Health Authenticated MedicationRequest Search by Patient

## Objective

Implement and validate an authenticated Oracle Health Millennium FHIR R4 search for `MedicationRequest` resources associated with an explicit Patient context.

This task continues the controlled Oracle Health interoperability sequence demonstrated in Tasks 033–039.

---

# Background

The Oracle Health sandbox integration has already demonstrated:

| Task | Capability | Live result |
|---|---|---|
| 033 | SMART Authorization Code + PKCE S256 | Access token issued |
| 034 | Oracle CapabilityStatement discovery | HTTP 200 |
| 035 | Authenticated Patient search | HTTP 200 Bundle |
| 036 | Controlled Patient read | HTTP 200 Patient |
| 037 | Authenticated Condition search by Patient | HTTP 200 Bundle |
| 038 | Authenticated Observation search by Patient | HTTP 200 Bundle |
| 039 | Authenticated DiagnosticReport search by Patient | HTTP 200 Bundle |

Task 040 validates `MedicationRequest` independently.

A successful operation on Condition, Observation, or DiagnosticReport must never be interpreted as authorization for MedicationRequest.

---

# WHAT

Implement an authenticated bounded search:

```text
GET /MedicationRequest?patient={patientId}&_count=5
Authorization: Bearer <SMART access token>
```

Expose a safe laboratory endpoint:

```text
GET /oracle/sandbox/fhir/medication-request-search
```

The endpoint must return only a diagnostic result.

It must not expose:

- access tokens
- authorization codes
- PKCE verifiers
- raw OAuth responses
- Patient demographics
- MedicationRequest JSON
- medication names
- dosage instructions
- prescription details
- clinical history

---

# WHY

MedicationRequest represents a separate clinical authorization boundary.

The purpose of Task 040 is to demonstrate that the Oracle Health sandbox accepts a real authenticated FHIR operation for this resource.

The chain is:

```text
SMART authentication

        +

explicit Patient context

        +

runtime CapabilityStatement support

        +

MedicationRequest SMART authorization

        ↓

real authenticated clinical FHIR operation
```

Therefore:

```text
Patient access
        ≠
Condition access
        ≠
Observation access
        ≠
DiagnosticReport access
        ≠
MedicationRequest access
```

Each resource must be demonstrated independently.

---

# HOW

## 1. Reuse explicit Patient context

Reuse the Patient context introduced in Task 036.

The Patient ID must come only from:

```text
ORACLE_HEALTH_SANDBOX_PATIENT_ID
```

Current context source:

```text
CONFIGURED
```

Do not:

- enumerate Patients
- guess Patient IDs
- search for a fallback Patient
- derive a Patient ID from `fhirUser`
- use OAuth login identity as clinical context

If the Patient context is absent:

```text
PATIENT_CONTEXT_NOT_CONFIGURED
```

No MedicationRequest HTTP request must be made.

---

## 2. Validate runtime capability

Before calling Oracle, validate the real CapabilityStatement discovered in Task 034.

Required capability:

```text
MedicationRequest + SEARCH_TYPE
```

Conceptually:

```java
capabilities.supports("MedicationRequest", SEARCH_TYPE)
```

If unsupported:

```text
CAPABILITY_UNSUPPORTED
```

Do not perform the FHIR search.

Capability support and OAuth authorization remain separate checks.

---

## 3. Reuse SMART authentication

Use the real access token issued by the Task 033 interactive SMART Authorization Code + PKCE flow.

Reuse:

```text
IssuedAccessTokenProvider
```

Do not:

- generate synthetic tokens
- create fake credentials
- add a client secret
- implement `client_secret_basic`
- implement `private_key_jwt`
- persist tokens
- print token values

The operation must use the current in-memory token.

If no usable token exists:

```text
AUTHENTICATION_REQUIRED
```

---

## 4. Routing architecture

Preserve the generic dependency direction:

```text
vendor.oracle
        ↓
RoutingService
        ↓
FhirService
        ↓
HAPI FHIR
```

Add the required generic routing operation.

Do not create:

```text
OracleMedicationRequestClient
OracleMedicationRequestSearchClient
```

The generic FHIR layer must remain independent of Oracle.

Never introduce:

```text
FhirService → vendor.oracle
```

---

## 5. Generic FHIR operation

Add a generic operation equivalent to:

```text
searchMedicationRequestsByPatientWithCount(patientId, 5)
```

The request must remain bounded:

```text
GET /MedicationRequest?patient={patientId}&_count=5
```

Do not perform:

```text
GET /MedicationRequest
```

The laboratory must remain explicitly scoped to the configured Patient.

---

## 6. Search parameters

Start with the minimal Patient-qualified search:

```text
patient={patientId}
_count=5
```

Do not add additional filters unless Oracle runtime validation demonstrates that they are required.

Do not prematurely introduce:

- status filters
- intent filters
- medication filters
- date filters
- vendor-specific parameters

The first objective is interoperability validation, not medication interpretation.

If Oracle rejects the search because an additional qualifier is required, document the runtime behavior before modifying the request.

---

## 7. Timeout behavior

Reuse the existing generic timeout configuration of 60 seconds.

Do not add Oracle-specific timeout logic.

Do not add:

```java
if (destination.equals("oracle-health-sandbox"))
```

The transport policy must remain reusable across FHIR vendors.

Timeouts and transport failures must use the existing dependency taxonomy.

---

# Expected outcomes

The endpoint must return a safe diagnostic result.

| Outcome | Meaning |
|---|---|
| `MEDICATION_REQUEST_SEARCH_SUCCEEDED` | Oracle returned HTTP 200 Bundle |
| `PATIENT_CONTEXT_NOT_CONFIGURED` | No configured Patient ID; zero MedicationRequest HTTP calls |
| `AUTHENTICATION_REQUIRED` | No usable SMART token |
| `AUTHENTICATION_REJECTED` | HTTP 401 |
| `AUTHORIZATION_DENIED` | HTTP 403 |
| `CAPABILITY_UNSUPPORTED` | Runtime capabilities do not declare MedicationRequest search-type |
| `DEPENDENCY_FAILURE` | Timeout, network failure, or dependency/server failure |

A successful empty Bundle remains a technical success:

```text
MEDICATION_REQUEST_SEARCH_SUCCEEDED
hasEntries=false
```

A Bundle with entries must not expose medication data.

---

# Safe response contract

The browser endpoint may expose only diagnostic metadata such as:

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

Never render:

- medication names
- dosage
- frequency
- prescription status
- prescriber information
- raw FHIR JSON

This task validates interoperability only.

It does not build a medication profile.

---

# Scope

## In scope

- Oracle Health sandbox
- FHIR R4
- MedicationRequest
- explicit configured Patient context
- authenticated search
- bounded `_count=5`
- runtime capability validation
- safe diagnostic result
- generic routing
- generic FHIR service operation
- unit tests
- integration tests
- optional live validation

## Out of scope

Do not implement:

- MedicationRequest detail read
- Medication resource retrieval
- MedicationAdministration
- MedicationDispense
- medication reconciliation
- medication interaction checking
- medication interpretation
- dosage interpretation
- clinical recommendations
- AI or LLM processing
- clinical snapshot aggregation
- patient browsing
- Patient ID discovery
- bulk export
- writes
- EHR launch
- automatic Patient extraction from launch context
- client_secret_basic
- private_key_jwt
- token persistence

---

# Security constraints

Preserve all established laboratory boundaries.

Never log or expose:

- access token
- authorization code
- PKCE verifier
- Patient demographics
- MedicationRequest Bundle
- medication names
- dosage instructions
- prescription details

The laboratory proves technical access without becoming a clinical data viewer.

---

# Architecture principles

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

Also preserve:

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

Reuse the existing Oracle sandbox configuration:

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

For live validation, the Oracle application registration and requested SMART scope must include:

```text
user/MedicationRequest.read
```

Do not commit `.env`.

Do not commit Patient IDs or credentials.

---

# Tests

## Unit tests

Cover at minimum:

- successful Bundle
- empty Bundle
- Patient context missing
- token missing
- expired/unusable token
- capability unsupported
- HTTP 401
- HTTP 403
- timeout
- dependency failure
- architecture boundaries

## Integration tests

The normal integration suite must not require Oracle network access.

```bash
mvn clean verify -Pintegration
```

must remain deterministic when Oracle sandbox integration is disabled.

## Live validation

Live validation is explicit and interactive.

Maven must not fabricate browser credentials.

Suggested flow:

### 1. Configure `.env`

Ensure the required MedicationRequest scope is present.

### 2. Start the service

```bash
cd services/fhir-integration-service
mvn spring-boot:run
```

### 3. Start fresh SMART authorization

```text
http://localhost:8081/oracle/sandbox/smart/start
```

### 4. Complete Oracle login

Confirm that SMART authentication succeeds without exposing the token.

### 5. Execute MedicationRequest search

Open:

```text
http://localhost:8081/oracle/sandbox/fhir/medication-request-search
```

Expected technical success:

```text
outcome=MEDICATION_REQUEST_SEARCH_SUCCEEDED
resourceType=MedicationRequest
responseType=Bundle
httpStatus=200
```

`hasEntries` may be:

```text
true
```

or:

```text
false
```

Both are valid technical outcomes when HTTP 200 and a Bundle are returned.

---

# Acceptance criteria

Task 040 is complete when:

- [ ] MedicationRequest runtime `search-type` capability is checked.
- [ ] An explicit Patient context is required.
- [ ] No Patient enumeration occurs.
- [ ] No Patient ID is guessed.
- [ ] A real SMART Bearer token is used.
- [ ] No token is exposed.
- [ ] The request is bounded with `_count=5`.
- [ ] The request is qualified by Patient.
- [ ] The generic FHIR layer remains vendor-independent.
- [ ] No Oracle-specific MedicationRequest client exists.
- [ ] HTTP 401 and 403 are diagnosed separately.
- [ ] Timeout/network failures map to dependency failure.
- [ ] Raw MedicationRequest JSON is not rendered.
- [ ] Medication details are not rendered.
- [ ] Unit tests pass.
- [ ] Integration tests pass without Oracle by default.
- [ ] Live validation remains opt-in.
- [ ] A successful Oracle HTTP 200 Bundle is classified as `MEDICATION_REQUEST_SEARCH_SUCCEEDED`.

---

# Proposed branch

```text
feature/oracle-health-authenticated-medication-request-search
```

# Proposed commit

```text
feat: add Oracle Health authenticated MedicationRequest search by Patient
```

---

# Next architectural boundary

Task 040 still does not create a clinical snapshot and does not send clinical data to AI.

After independently demonstrating access to:

```text
Patient
Condition
Observation
DiagnosticReport
MedicationRequest
```

a future task may evaluate a controlled clinical aggregation layer.

That future layer must explicitly define:

- allowed resource types
- maximum result counts
- timeout budget
- partial failure behavior
- normalization
- data minimization
- privacy boundaries
- audit behavior
- what information, if any, may be supplied to an AI system

No aggregation or AI processing belongs in Task 040.
