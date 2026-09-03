# Task 036 — Oracle Health Patient Context & Controlled Patient Read

**Status:** Implemented
**Depends on:** Task 033, Task 034, Task 035
**Base branch:** `main` after merge of Task 035
**Destination:** `oracle-health-sandbox`

---

## 1. Objective

Extend the Oracle Health integration from the safe authenticated Patient search demonstrated in Task 035 to a **controlled Patient context and Patient read workflow**.

Task 035 proved:

```text
SMART authorization
        ↓
Access token issued
        ↓
Bearer accepted by Oracle Health
        ↓
GET /Patient?name=LabNoMatch&_count=1
        ↓
HTTP 200 + Bundle
```

Task 036 must determine how the laboratory can work with a **real sandbox Patient context** without turning the integration into an unrestricted clinical data browser.

The goal is not bulk patient discovery.

The goal is:

```text
Patient context
        ↓
Validated Patient identifier
        ↓
Capability check
        ↓
Authenticated FHIR read
        ↓
Safe diagnostic result
```

---

## 2. Architectural principle

### Patient identity is a boundary

The platform must not assume that a Patient identifier can be invented, guessed, scraped, or discovered through unrestricted searches.

```text
Patient search
        ≠
Patient context
        ≠
Patient read
```

A successful Patient search capability does not automatically provide a valid Patient context.

Task 036 must introduce an explicit representation of the Patient context used by the integration.

---

## 3. Scope

### A. Controlled Patient context

Introduce a generic model representing a Patient selected for a controlled integration workflow.

Conceptually:

```text
PatientContext
    destination
    patientId
    source
```

Possible sources:

- configured laboratory Patient ID
- future SMART launch context
- future application-selected context

Do not implement EHR launch in this task.

### B. Configured sandbox Patient ID

Support an opt-in local configuration:

```dotenv
ORACLE_HEALTH_SANDBOX_PATIENT_ID=
```

Rules:

- empty by default
- never committed with a real value
- `.env.example` contains only the placeholder
- absent configuration must not trigger network calls attempting to discover a Patient

### C. Capability-aware Patient read

Reuse runtime capabilities from Task 034.

Verify:

```text
Patient → read
```

Do not hard-code this assumption.

### D. Authenticated Patient read

When prerequisites are available:

```text
sandbox enabled
        +
usable SMART access token
        +
configured Patient ID
        +
Patient READ capability
        ↓
GET /Patient/{id}
        +
Bearer token
```

`FhirService` must remain vendor-neutral.

Do not create:

```text
OraclePatientClient
OraclePatientReadClient
```

### E. Safe result model

Suggested outcomes:

```text
PATIENT_READ_SUCCEEDED
PATIENT_CONTEXT_NOT_CONFIGURED
AUTHENTICATION_REQUIRED
AUTHENTICATION_REJECTED
AUTHORIZATION_DENIED
CAPABILITY_UNSUPPORTED
PATIENT_NOT_FOUND
DEPENDENCY_FAILURE
```

The result must not expose:

- access token
- authorization code
- PKCE verifier
- complete Patient JSON
- unnecessary patient demographics

---

## 4. Explicit safety rules

### Do not implement unrestricted patient enumeration

Forbidden:

```text
GET /Patient
GET /Patient?_count=100
search until a patient is found
try random identifiers
guess Patient IDs
```

Task 036 is not a patient directory.

### Do not use production data

Use Oracle sandbox data only.

### Do not log the Patient resource

No full FHIR Patient JSON in:

- logs
- exception messages
- diagnostic pages
- test output

### Do not persist the SMART token

Keep the existing in-memory lifecycle from Task 033.

---

## 5. Proposed architecture

```text
Oracle Sandbox Controller
        ↓
OracleSandboxPatientContextService
        ↓
Patient context validation
        ↓
Runtime capability check
        ↓
IssuedAccessTokenProvider
        ↓
RoutingService
        ↓
FhirService
        ↓
HAPI FHIR client
        ↓
Oracle Health Millennium
```

Dependency direction:

```text
vendor.oracle
        ↓
generic routing
        ↓
generic FHIR service
```

Never:

```text
generic FHIR service
        ↓
vendor.oracle
```

---

## 6. Patient context versus SMART context

Task 033 produced:

```text
hasPatient=false
```

Standalone SMART authorization did not provide an EHR Patient launch context.

Do not treat:

```text
fhirUser
```

as a Patient identifier.

```text
fhirUser       → authenticated user identity
Patient context → clinical subject identity
Patient ID      → resource identifier
```

Task 036 uses an explicitly configured sandbox Patient ID until a future EHR launch workflow exists.

---

## 7. HTTP laboratory endpoint

Recommended endpoint:

```text
GET /oracle/sandbox/fhir/patient
```

Expected flow:

```text
validate sandbox configuration
        ↓
validate Patient context
        ↓
validate access token
        ↓
check capability
        ↓
GET Patient/{configured-id}
        ↓
safe outcome
```

This must not become a generic patient browsing API.

---

## 8. Outcome behavior

### Outcome A — Success

```text
PATIENT_READ_SUCCEEDED
```

Conditions:

- sandbox enabled
- usable token
- Patient ID configured
- capability supported
- Oracle returns HTTP 200

Do not dump the Patient resource.

### Outcome B — Context missing

```text
PATIENT_CONTEXT_NOT_CONFIGURED
```

No Patient request must be sent.

### Outcome C — Authentication required

```text
AUTHENTICATION_REQUIRED
```

Examples:

- no issued token
- expired token
- service restarted

Do not manufacture a synthetic token.

### Outcome D — Authentication rejected

```text
AUTHENTICATION_REJECTED
```

HTTP 401.

### Outcome E — Authorization denied

```text
AUTHORIZATION_DENIED
```

HTTP 403.

### Outcome F — Capability unsupported

```text
CAPABILITY_UNSUPPORTED
```

Do not send the Patient read.

### Outcome G — Patient not found

```text
PATIENT_NOT_FOUND
```

HTTP 404.

Do not perform fallback searches.

### Outcome H — Dependency failure

Reuse existing dependency/resilience taxonomy for:

- timeout
- connection failure
- server error

401 and 403 must not be retried.

---

## 9. Configuration

Update `.env.example`:

```dotenv
# Controlled sandbox Patient context.
# Use only a sandbox Patient resource identifier.
# Never commit a real value.
ORACLE_HEALTH_SANDBOX_PATIENT_ID=
```

No token, secret, authorization code, verifier, or clinical JSON belongs in `.env`.

---

## 10. Testing requirements

### Unit tests

Cover:

#### Patient context

- missing ID
- blank ID
- valid configured ID

#### Authentication

- no token
- expired token
- usable token

#### Capability

- Patient READ supported
- Patient READ unsupported

#### HTTP/result mapping

- 200 → `PATIENT_READ_SUCCEEDED`
- 401 → `AUTHENTICATION_REJECTED`
- 403 → `AUTHORIZATION_DENIED`
- 404 → `PATIENT_NOT_FOUND`
- network/5xx → dependency taxonomy

#### Safety

Verify:

- no request when Patient ID is absent
- no request when capability is unsupported
- no Oracle imports in `FhirService`
- no token/resource leakage

---

## 11. Integration tests

Default integration tests must not require:

- Oracle network access
- Oracle credentials
- browser login
- Patient ID

Required commands:

```bash
mvn clean test
```

```bash
mvn clean verify -Pintegration
```

---

## 12. Optional live validation

Suggested opt-in:

```text
ORACLE_HEALTH_LIVE_IT=true
ORACLE_HEALTH_SANDBOX_ENABLED=true
```

Do not manufacture authentication.

Interactive validation:

```text
1. Start service

2. Open:
/oracle/sandbox/smart/start

3. Complete Oracle login

4. Confirm token exchange succeeded

5. Open:
/oracle/sandbox/fhir/patient

6. Observe safe diagnostic outcome
```

---

## 13. Documentation requirements

Explain:

- Task 035 authenticated search versus Task 036 controlled read
- Patient search versus Patient context
- standalone SMART versus EHR launch context
- why `fhirUser` is not a Patient ID
- why Patient ID is explicit local sandbox configuration
- why Patient JSON is not rendered
- capability check before Patient READ

Update relevant Oracle, FHIR architecture, routing, README, roadmap, and progress documentation.

---

## 14. Architecture boundary tests

Maintain or add tests enforcing:

```text
FhirService
    does not import vendor.oracle
```

```text
Oracle adapter
    does not bypass generic routing/FHIR boundaries
```

```text
No hard-coded Oracle hosts
```

```text
No Patient ID hard-coded in Java
```

```text
No clinical resource serialization in diagnostic output
```

---

## 15. Out of scope

Explicitly outside Task 036:

- EHR launch (`launch` scope + launch parameter)
- automatic Patient context extraction from Oracle launch
- patient browsing UI
- patient enumeration
- bulk Patient export
- `Condition` reads
- `Observation` reads
- `DiagnosticReport` reads
- `MedicationRequest` reads
- clinical snapshot aggregation
- AI Agent
- LLM integration
- write operations
- `client_secret_basic`
- `private_key_jwt`
- refresh-token architecture
- token persistence

---

## 16. Acceptance criteria

Task 036 is complete when:

- [ ] Patient context is explicitly modeled or validated
- [ ] Sandbox Patient ID is opt-in configuration
- [ ] No automatic Patient discovery/enumeration occurs
- [ ] Runtime capability check confirms Patient READ
- [ ] A usable SMART token is required
- [ ] Generic FHIR service remains Oracle-independent
- [ ] `GET /Patient/{id}` uses the generic authenticated FHIR path
- [ ] Success does not expose Patient JSON
- [ ] 401/403/404 are distinguished
- [ ] Missing Patient context sends no Patient network request
- [ ] Default tests pass without Oracle access
- [ ] Integration tests remain CI-safe
- [ ] Documentation is updated

---

## 17. Conceptual milestone

Task 035 proved:

```text
Authentication
        +
FHIR search authorization
        +
FHIR operation
```

Task 036 must prove:

```text
Explicit Patient context
        +
Capability-aware operation
        +
Authenticated Patient read
```

The architectural result:

```text
OAuth identity
        ≠
Clinical Patient context
```

After Task 036, the platform will have a controlled foundation for generic clinical resource reads and eventually a normalized clinical snapshot for AI systems.

---

## 18. Suggested branch and commit

Branch:

```text
feature/oracle-health-patient-context-read
```

Commit:

```text
feat: add Oracle Health controlled Patient context read
```
