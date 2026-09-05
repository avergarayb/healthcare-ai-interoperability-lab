# Task 043 — Vendor-Neutral Explicit Model Boundary Contract

## Status

**Specification**

Depends on:

- Task 042 — Clinical Data Minimization and Controlled Projection
- Task 041 — Controlled Clinical Snapshot Assembly
- Tasks 033–040 — Authenticated FHIR interoperability operations

Task 043 defines a **vendor-neutral explicit model boundary contract** for data that could be consumed by a model in a future architecture.

Task 043 does not call a model.

---

# 1. Objective

Introduce a reusable, vendor-neutral contract that sits after the controlled projection from Task 042.

The architecture is:

```text
Oracle Health
Epic
other FHIR R4 EHRs
        ↓
fhir-integration-service
        ↓
controlled snapshot
        ↓
controlled projection
        ↓
Task 043 explicit model boundary contract
        ↓
STOP
```

The same contract must be reusable regardless of whether the upstream EHR is:

```text
Oracle Health
Epic
another FHIR R4 EHR
```

Task 043 does not introduce any new EHR integration.

---

# 2. WHAT

Create a generic contract representing the only data shape that could cross a future model boundary.

The contract is built from Task 042 projection data.

It must not:

- fetch Oracle again;
- fetch Epic;
- call raw FHIR Bundles;
- bypass Task 042 retention;
- create vendor-specific context classes;
- invoke an LLM.

The boundary is:

```text
Task 042 retained projection
        ↓
generic boundary mapper
        ↓
vendor-neutral model boundary contract
        ↓
STOP
```

---

# 3. WHY

Task 042 proved:

```text
requested != received != retained
```

Task 043 adds:

```text
retained projection != model boundary contract
```

A future model consumer must not depend directly on:

- Oracle-specific classes;
- Epic-specific classes;
- HAPI FHIR resource types;
- raw FHIR Bundles;
- snapshot implementation details.

The contract must remain stable even when additional EHR vendors are added later.

---

# 4. CONCEPT

Prohibited architectures:

```text
FHIR Bundle → LLM
```

and:

```text
projection → LLM
```

Also prohibited:

```text
Oracle projection → Oracle model contract
Epic projection   → Epic model contract
```

Instead:

```text
FHIR vendor adapters
        ↓
generic projection
        ↓
single generic model boundary contract
        ↓
STOP
```

---

# 5. Multi-EHR requirement

Oracle Health is the first live EHR used to validate the laboratory.

It is not the final architecture.

The contract must be designed so that later:

```text
Oracle Health
        ↓
same projection
        ↓
same model boundary contract
```

and:

```text
Epic
        ↓
same projection
        ↓
same model boundary contract
```

without redefining the contract.

No new Epic connection is implemented in Task 043.

No Epic-specific code is added.

---

# 6. Input

Task 043 consumes only the Task 042 controlled projection.

It must not:

- re-run the original large Oracle search;
- process the original 1489 Condition resources again;
- bypass retainedCount=5;
- introduce a new FHIR query path.

The input boundary is:

```text
lab.healthcare.fhir.projection
```

---

# 7. Contract purpose

The contract defines only:

1. which resource categories are represented;
2. which controlled fields may cross the boundary;
3. statuses;
4. received counts;
5. retained counts;
6. truncation state;
7. source-neutral operational metadata.

It is not:

- an AI-ready context;
- a clinical summary;
- an insight;
- a recommendation;
- a timeline;
- a patient profile.

---

# 8. Contract package

Use a dedicated generic package:

```text
lab.healthcare.fhir.modelboundary
```

The package must be independent of:

```text
vendor.oracle
vendor.epic
HAPI
IGenericClient
Bundle
OAuth
SMART implementation classes
```

Dependency direction:

```text
projection
    ↓
modelboundary
```

Never:

```text
modelboundary → vendor.oracle
```

or:

```text
modelboundary → vendor.epic
```

---

# 9. Contract version

The first version must declare explicitly:

```text
contractVersion = v1
```

The version exists so future consumers can depend on an explicit contract rather than accidental Java implementation details.

Task 043 does not introduce migration infrastructure or multiple versions.

---

# 10. Top-level contract

The v1 boundary contract may expose only:

```text
contractVersion
destination
contextSource
generatedAt
outcome
patient
conditions
observations
diagnosticReports
medicationRequests
```

The contract must not expose:

- Patient ID;
- Oracle tenant ID;
- Epic tenant ID;
- OAuth tokens;
- authorization codes;
- raw FHIR JSON;
- vendor-specific transport objects.

---

# 11. Patient section

Allowed:

```text
status
resourceType
```

No additional Patient fields are introduced in Task 043.

---

# 12. Condition collection

Allowed collection metadata:

```text
status
receivedCount
retainedCount
truncated
records
```

Each retained record may contain only:

```text
resourceType
clinicalStatusCode
```

No new clinical fields.

---

# 13. Observation collection

Allowed collection metadata:

```text
status
receivedCount
retainedCount
truncated
records
```

Each retained record may contain only:

```text
resourceType
status
```

---

# 14. DiagnosticReport collection

Allowed collection metadata:

```text
status
receivedCount
retainedCount
truncated
records
```

Each retained record may contain only:

```text
resourceType
status
```

---

# 15. MedicationRequest collection

Allowed collection metadata:

```text
status
receivedCount
retainedCount
truncated
records
```

Each retained record may contain only:

```text
resourceType
status
intent
```

---

# 16. Mapping rules

The Task 043 mapper must:

- copy only fields permitted by the contract;
- preserve `receivedCount`;
- preserve `retainedCount`;
- preserve `truncated`;
- preserve status values;
- preserve empty successful collections;
- preserve partial failures.

It must not:

- enrich records;
- add vendor metadata;
- add Oracle identifiers;
- add Epic identifiers;
- add clinical rankings;
- add inferred values;
- add clinical codes not present in Task 042;
- add interpretations.

---

# 17. Empty collection semantics

A successful empty collection remains:

```text
status=SUCCESS
receivedCount=0
retainedCount=0
truncated=false
records=[]
```

Task 043 must not reinterpret this as:

```text
FAILED
UNAVAILABLE
clinically normal
clinically negative
```

---

# 18. Partial result semantics

Task 043 preserves the upstream state.

Example:

```text
conditions=SUCCESS
observations=FAILED
diagnosticReports=SUCCESS
medicationRequests=SUCCESS
```

The contract must preserve:

```text
observations=FAILED
```

It must not convert failure to:

```text
SUCCESS with []
```

---

# 19. Vendor-neutral destination metadata

The contract may preserve:

```text
destination
```

as operational provenance.

But consumers must not require Oracle-specific destination names to understand the contract.

The contract shape must remain identical for:

```text
oracle-health-sandbox
epic-sandbox
future-fhir-destination
```

Vendor identity must not alter contract structure.

---

# 20. Laboratory endpoint

The initial laboratory validation may remain under the Oracle sandbox route because Oracle is currently the live EHR.

Endpoint:

```text
GET /oracle/sandbox/fhir/model-boundary
```

This endpoint validates the generic contract using Oracle-backed data.

The **contract itself remains vendor-neutral**.

A future Epic validation should reuse the same model boundary classes rather than create a new contract.

---

# 21. Blind laboratory page

The page may display only structural diagnostics:

```text
contractVersion
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

Do not display:

- retained record values;
- Patient ID;
- names;
- DOB;
- diagnoses;
- clinical codes;
- laboratory values;
- DiagnosticReport text;
- medication names;
- dosage;
- raw JSON;
- tokens.

---

# 22. FhirService boundary

`FhirService` must remain independent of:

```text
vendor.oracle
vendor.epic
projection
modelboundary
```

Task 043 must not add model-boundary behavior to `FhirService`.

---

# 23. No vendor clients

Do not create:

```text
OracleModelBoundaryClient
EpicModelBoundaryClient
OracleModelContext
EpicModelContext
OracleContractMapper
EpicContractMapper
```

The mapping layer is generic.

---

# 24. Tests

## Generic mapping

Verify:

- Task 042 projection maps to v1 contract;
- only permitted fields are present;
- counts are preserved;
- truncation is preserved;
- statuses are preserved.

## Empty collection

Verify:

```text
SUCCESS
receivedCount=0
retainedCount=0
truncated=false
records=[]
```

## Partial failure

Verify:

```text
FAILED != SUCCESS with []
UNAVAILABLE != SUCCESS with []
UNAUTHORIZED != SUCCESS with []
```

## Vendor independence

Tests must prove:

- `modelboundary` does not import `vendor.oracle`;
- `modelboundary` does not import `vendor.epic`;
- no Oracle-specific field exists in the contract;
- no Epic-specific field exists in the contract.

## HAPI independence

The contract must not expose:

```text
Patient
Condition
Observation
DiagnosticReport
MedicationRequest
Bundle
IGenericClient
```

from HAPI as public contract types.

## No AI dependencies

Verify no dependency or import for:

- OpenAI;
- Gemini;
- Anthropic;
- model SDKs;
- prompt frameworks;
- RAG;
- agents.

---

# 25. Live validation

Live validation currently uses Oracle because Oracle is the first real EHR integrated.

Representative result from Task 042:

```text
conditions
receivedCount=1489
retainedCount=5
truncated=true
```

Task 043 must preserve:

```text
receivedCount=1489
retainedCount=5
truncated=true
```

without exposing the five Condition records in the lab page.

The live proof is:

```text
Oracle Health
    ↓
generic projection
    ↓
generic model boundary contract
    ↓
STOP
```

No Oracle-specific contract is permitted.

---

# 26. Out of scope

Task 043 explicitly does not implement:

- new Oracle FHIR operations;
- Epic sandbox connection;
- Epic OAuth;
- Epic live validation;
- additional EHR adapters;
- AI;
- LLM;
- prompts;
- OpenAI;
- Gemini;
- Anthropic;
- RAG;
- agents;
- `ai-service`;
- inference;
- embeddings;
- vector database;
- timeline;
- clinical interpretation;
- recommendations;
- ranking;
- persistence.

---

# 27. Acceptance criteria

Task 043 is complete when:

1. Task 042 projection is reused directly.
2. No raw FHIR Bundle is re-fetched.
3. A dedicated `lab.healthcare.fhir.modelboundary` package exists.
4. `contractVersion=v1` is explicit.
5. The contract is vendor-neutral.
6. The same contract shape can represent Oracle, Epic, or another FHIR R4 source.
7. No Oracle-specific model classes exist.
8. No Epic-specific model classes exist.
9. No HAPI resource type crosses the public contract boundary.
10. Only Task 042-allowed fields are mapped.
11. Counts and truncation are preserved.
12. Partial failures remain explicit.
13. The Oracle laboratory endpoint exists at:

```text
GET /oracle/sandbox/fhir/model-boundary
```

14. The laboratory page remains blind.
15. No model SDK is added.
16. No model is called.
17. `FhirService` remains vendor-neutral.

---

# 28. Final concept

After Task 043:

```text
Oracle Health
Epic
other FHIR R4 EHRs
        ↓
vendor-neutral interoperability core
        ↓
controlled snapshot
        ↓
controlled projection
        ↓
single vendor-neutral model boundary contract
        ↓
STOP
```

This contract is the architectural boundary.

It is not yet a model input pipeline.

A future task may decide whether and how a separate model consumer is allowed to consume this contract.

That future decision is outside Task 043.
