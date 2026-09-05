# Task 042 — Clinical Data Minimization and Controlled Projection

## Status

**Specification ready for implementation**

Depends on:

- Task 041 — Controlled Clinical Snapshot Assembly
- Task 036 — Controlled Patient Context Read
- Task 033 — Oracle Health SMART Authorization Code + PKCE

This task does **not** introduce AI, LLMs, prompts, timelines, persistence, or an `ai-service`.

---

# 1. WHAT

Task 042 introduces a controlled projection layer over the clinical data assembled by Task 041.

The purpose is to distinguish:

```text
Entries requested from the EHR
        !=
Entries received from the EHR
        !=
Entries retained by the application
```

Oracle Health demonstrated that `_count=5` is not always enforced by the server:

```text
Condition requested: 5
Condition received: 1489
```

Task 042 establishes an application-controlled retention ceiling and projects only an explicit allowlist of fields.

The projection is intentionally minimal.

It is **not** a clinical summary.

It is **not** an AI-ready context.

It is **not** a clinical ranking.

---

# 2. WHY

Task 041 proved that successful HTTP operations can still return much more data than requested.

Therefore:

```text
HTTP 200
    !=
small response
    !=
safe retained context
```

The application must control how many resources it retains after receiving a Bundle.

Task 042 ensures that a large Bundle can be processed without preserving the entire clinical payload.

---

# 3. RETENTION POLICY

## 3.1 Application retention ceiling

The v1 retention ceiling is:

```text
N = 5
```

This applies independently to every collection:

- Condition
- Observation
- DiagnosticReport
- MedicationRequest

The Patient remains a single resource projection.

The value `5` matches the current request limit used by Tasks 037–040, but retention remains an independent application policy.

The EHR is allowed to return more than five entries.

The application retains at most five.

## 3.2 First N semantics

The retained entries are the first N entries received from the FHIR Bundle.

This is an operational ceiling only.

```text
First N
    !=
most important N
    !=
highest severity N
    !=
clinically ranked N
```

Task 042 introduces no sorting, ranking, prioritization, or clinical interpretation.

---

# 4. CONCRETE ALLOWLIST

Task 042 retains only the following fields.

## 4.1 Patient

Allowed:

```text
resourceType
```

Explicitly not retained:

- id
- name
- birthDate
- identifier
- address
- telecom
- raw JSON

## 4.2 Condition

Allowed:

```text
resourceType
clinicalStatus.code
```

Explicitly not retained:

- Condition.code
- code display
- narrative text
- subject
- identifiers
- notes
- raw JSON

## 4.3 Observation

Allowed:

```text
resourceType
status
```

Explicitly not retained:

- Observation.code
- code display
- value[x]
- interpretation
- subject
- components
- notes
- raw JSON

## 4.4 DiagnosticReport

Allowed:

```text
resourceType
status
```

Explicitly not retained:

- code
- code display
- text
- presentedForm
- conclusion
- subject
- results
- raw JSON

## 4.5 MedicationRequest

Allowed:

```text
resourceType
status
intent
```

Explicitly not retained:

- medication
- medication display
- dosageInstruction
- dose
- subject
- requester
- notes
- raw JSON

---

# 5. EXPLICIT BLOCKLIST

The projection must never retain or expose:

- Patient ID
- patient names
- birth dates
- addresses
- telephone numbers
- identifiers
- clinical codes
- clinical code displays
- laboratory values
- observation values
- interpretations
- diagnostic report text
- conclusions
- attachments
- medication names
- medication doses
- dosage instructions
- FHIR narratives
- raw FHIR JSON
- OAuth access tokens
- authorization codes
- PKCE verifiers

The laboratory output must remain blind to clinical content.

---

# 6. RECEIVED VS RETAINED

Each collection projection must expose:

```text
receivedCount
retainedCount
truncated
```

Example:

```text
receivedCount=1489
retainedCount=5
truncated=true
```

Rules:

```text
receivedCount <= 5
    -> retainedCount = receivedCount
    -> truncated = false

receivedCount > 5
    -> retainedCount = 5
    -> truncated = true
```

An empty Bundle remains successful:

```text
receivedCount=0
retainedCount=0
truncated=false
status=SUCCESS
```

`EMPTY` must not become a separate failure status.

---

# 7. ARCHITECTURE

The projection layer must remain independent of Oracle and HAPI.

```text
vendor.oracle
        ↓
Clinical snapshot orchestration
        ↓
RoutingService
        ↓
FHIR/HAPI result
        ↓
projection package
        ↓
Controlled retained projection
```

Rules:

- No `OracleProjectionClient`.
- No Oracle-specific projection model.
- `FhirService` remains vendor-neutral.
- `FhirService` must not import `vendor.oracle`.
- No `FhirService.searchEverything`.
- No second OAuth client.
- Reuse the SMART token issued by Task 033.
- Reuse the configured Patient context from Task 036.

The package for the new model is:

```text
projection
```

It must not be mixed into the Task 041 snapshot assembly package.

---

# 8. EXECUTION MODEL

Task 042 consumes the results of the controlled clinical operations already demonstrated.

The projection does not issue a new clinical browsing strategy.

It applies:

```text
FHIR result
    ↓
received count
    ↓
first N retention ceiling
    ↓
allowlist mapping
    ↓
controlled projection
```

The projection does not promise that the original HTTP response will be small.

Oracle may still send:

```text
1489 Conditions
```

Task 042 may receive that result, but retains only:

```text
5 projected Condition records
```

---

# 9. LABORATORY ENDPOINT

The laboratory endpoint is:

```text
GET /oracle/sandbox/fhir/clinical-projection
```

The response must expose diagnostics only.

Allowed output:

```text
outcome
destination
contextSource

patient status

conditions status
conditions receivedCount
conditions retainedCount
conditions truncated

observations status
observations receivedCount
observations retainedCount
observations truncated

diagnosticReports status
diagnosticReports receivedCount
diagnosticReports retainedCount
diagnosticReports truncated

medicationRequests status
medicationRequests receivedCount
medicationRequests retainedCount
medicationRequests truncated
```

The page must not show:

- projected field values;
- Patient ID;
- names;
- diagnoses;
- laboratory values;
- report text;
- medications;
- doses;
- raw JSON;
- tokens.

---

# 10. OUTCOME SEMANTICS

Task 042 preserves the controlled status semantics from Task 041.

Collection status:

```text
SUCCESS
UNAVAILABLE
UNAUTHORIZED
FAILED
```

Global outcomes remain controlled by the snapshot prerequisites:

```text
SNAPSHOT_COMPLETE
SNAPSHOT_PARTIAL
SNAPSHOT_UNAVAILABLE
PATIENT_CONTEXT_NOT_CONFIGURED
AUTHENTICATION_REQUIRED
```

A successful empty collection remains:

```text
SUCCESS
receivedCount=0
retainedCount=0
truncated=false
```

---

# 11. MODEL REQUIREMENTS

The projection model must be:

- independent of Oracle;
- independent of HAPI resource classes;
- independent of raw Bundle serialization;
- limited to the explicit allowlist;
- impossible to populate accidentally with arbitrary FHIR JSON.

Do not create rich clinical models containing SNOMED, LOINC, quantities, displays, narratives, dates, or medication details in this task.

---

# 12. TESTS

Unit and integration coverage must include:

## Retention

- received 0 → retained 0, not truncated;
- received 1 → retained 1;
- received 5 → retained 5;
- received 6 → retained 5, truncated;
- received 1489 → retained 5, truncated.

## Allowlist

Verify that each resource projection contains only the explicitly approved fields.

## Blocklist

Verify that prohibited fields cannot appear in the projection.

## Status

- empty Bundle remains `SUCCESS`;
- capability unavailable remains `UNAVAILABLE`;
- authorization failure remains controlled;
- dependency failure remains controlled.

## Architecture boundaries

Verify:

- projection does not import Oracle vendor implementation;
- projection does not expose HAPI resources;
- `FhirService` does not import `vendor.oracle`.

Default commands must remain offline from Oracle:

```bash
mvn clean test
mvn clean verify -Pintegration
```

Live validation remains opt-in.

---

# 13. LIVE VALIDATION

The live Oracle validation should demonstrate a case where the server returns more entries than the application retains.

Expected example:

```text
conditions
receivedCount=1489
retainedCount=5
truncated=true
```

The laboratory page must still reveal no clinical content.

---

# 14. OUT OF SCOPE

Explicitly outside Task 042:

- AI;
- LLMs;
- prompts;
- OpenAI;
- Gemini;
- RAG;
- `ai-service`;
- clinical timelines;
- clinical interpretation;
- recommendations;
- ranking;
- sorting by clinical importance;
- persistence;
- database storage;
- new Oracle clients;
- patient browsing;
- raw Bundle exposure.

The prohibited architecture remains:

```text
FHIR Bundle
    ↓
LLM
```

---

# 15. ACCEPTANCE CRITERIA

Task 042 is complete when:

1. Application retention is explicitly capped at `N = 5`.
2. Every collection exposes `receivedCount`, `retainedCount`, and `truncated`.
3. The concrete allowlist is implemented exactly as specified.
4. The explicit blocklist cannot leak through the projection.
5. Empty Bundles remain successful.
6. The model is independent of Oracle and HAPI.
7. The laboratory endpoint is available at:

```text
GET /oracle/sandbox/fhir/clinical-projection
```

8. The laboratory output remains blind to clinical content.
9. A large Oracle response can be reduced to five retained records.
10. No AI functionality is introduced.

---

# 16. CONCEPT

Task 042 establishes the next boundary:

```text
FHIR response received
        ↓
application-controlled retention
        ↓
explicit allowlist
        ↓
controlled projection
```

It does not establish:

```text
controlled projection
        ↓
AI
```

That explicit model boundary belongs to a later task.
