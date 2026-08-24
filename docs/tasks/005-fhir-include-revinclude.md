# Task 005 — FHIR `_include` and `_revinclude`

## Objective

Learn and implement FHIR `_include` and `_revinclude` using the existing synthetic clinical data.

The goal is to understand how FHIR Search can return related Resources in the same `Bundle`, reducing unnecessary HTTP round trips.

Use:

```text
Patient/patient-001
Observation/obs-001
Condition/condition-001
```

with:

```text
Observation/obs-001
    subject → Patient/patient-001

Condition/condition-001
    subject → Patient/patient-001
```

This is an educational task. Keep the scope small.

## Branch

Create and use:

`feature/fhir-include-revinclude`

Do not work directly on `main`.

## Teaching Mode — Mandatory

Act as a senior instructor and implementation mentor.

Do not silently implement the task.

Execute the work step by step and explain:

1. What you are doing.
2. Why.
3. Files created/modified.
4. The FHIR HTTP request.
5. The equivalent HAPI FHIR Java operation.
6. Commands executed.
7. Results.
8. FHIR concept learned.
9. Java/HAPI concept learned.

Before implementing `_include` or `_revinclude`, explain the reference direction with a diagram.

If an error occurs, show the error, explain the cause and fix, apply it, rerun verification, and explain why it works.

At the end provide both a concise summary and a complete step-by-step report.

# Context

Repository:

`healthcare-ai-interoperability-lab`

Service:

`services/fhir-integration-service`

Technology:

- Java 21
- Spring Boot 3.5.x
- Maven
- HAPI FHIR 8.10.0
- FHIR R4 / `4.0.1`

FHIR server:

`http://localhost:8080/fhir`

Existing functionality:

- FHIR R4 client.
- CapabilityStatement retrieval.
- Patient read/search.
- Observation read/search.
- Condition read/search.
- Bundle handling.
- FHIR References.
- LOINC and SNOMED CT examples.
- Synthetic FHIR data.

Do not add dependencies unless absolutely necessary.

# Core Concept — Direction Matters

Current relationships:

```text
Observation/obs-001
        |
        | subject
        v
Patient/patient-001
```

```text
Condition/condition-001
        |
        | subject
        v
Patient/patient-001
```

Therefore:

```text
Observation → Patient
Condition   → Patient
```

## `_include`

Explain:

> `_include` follows a reference FROM the resources returned by the search and includes the referenced resource in the same Bundle.

Example:

```http
GET /Observation?patient=patient-001&_include=Observation:subject
```

Conceptual result:

```text
Bundle
├── Observation/obs-001
└── Patient/patient-001
```

## `_revinclude`

Explain:

> `_revinclude` finds resources that reference the resources returned by the primary search.

Example:

```http
GET /Patient?_id=patient-001&_revinclude=Observation:subject
```

Conceptual result:

```text
Bundle
├── Patient/patient-001
└── Observation/obs-001
```

Critical distinction:

```text
_include:
follow references FROM the search result

_revinclude:
find resources that reference the search result
```

# Part 1 — Baseline Without Include

First reproduce:

```http
GET /Observation?patient=patient-001
```

Expected:

```text
Bundle
└── Observation/obs-001
```

Explain that without `_include`, a client wanting the referenced Patient might need:

```text
GET /Observation?patient=patient-001
        ↓
Observation/obs-001
        ↓
GET /Patient/patient-001
        ↓
Patient/patient-001
```

Explain that `_include` can reduce round trips when the related resource is needed, but do not claim it is always preferable.

# Part 2 — `_include` HTTP

Implement:

```http
GET /Observation?patient=patient-001&_include=Observation:subject
```

Explain:

- `Observation` = primary resource.
- `patient=patient-001` = search filter.
- `_include` = request referenced resources.
- `Observation:subject` = reference path.
- `subject` is the FHIR element containing the reference.

Expected resources:

```text
Observation/obs-001
Patient/patient-001
```

Do not rely on Bundle entry order.

# Part 3 — HAPI FHIR `_include`

Implement the equivalent using the existing `IGenericClient`.

Conceptually:

```java
client.search()
    .forResource(Observation.class)
    .where(Observation.PATIENT.hasId("patient-001"))
    .include(Observation.INCLUDE_SUBJECT)
    .returnBundle(Bundle.class)
    .execute();
```

Do not copy blindly. Explain:

```text
search()
forResource()
where()
include()
returnBundle()
execute()
```

Explain what `Observation.INCLUDE_SUBJECT` represents.

If HAPI FHIR 8.10.0 uses a different equivalent API, use the correct syntax and explain the difference.

# Part 4 — Inspect the Include Bundle

Inspect every Bundle entry and distinguish Resource types.

The Bundle may conceptually be:

```text
Bundle
├── Observation
└── Patient
```

but ordering must not be assumed.

Assert that both logical IDs exist:

```text
obs-001
patient-001
```

Do not assume `entry[0]` is Observation.

# Part 5 — `_revinclude` HTTP

Explain the direction again:

```text
Observation
    |
    | subject
    v
Patient
```

Implement:

```http
GET /Patient?_id=patient-001&_revinclude=Observation:subject
```

Explain:

- primary search = Patient;
- `_revinclude` = find resources referencing the Patient;
- `Observation:subject` = Observations whose subject points to the Patient.

Expected:

```text
Patient/patient-001
Observation/obs-001
```

Do not depend on order.

# Part 6 — HAPI FHIR `_revinclude`

Implement the equivalent.

Conceptually:

```java
client.search()
    .forResource(Patient.class)
    .where(Patient.RES_ID.exactly().code("patient-001"))
    .revInclude(Observation.INCLUDE_SUBJECT)
    .returnBundle(Bundle.class)
    .execute();
```

If HAPI 8.10.0 uses another equivalent API, use it and explain it.

Explicitly compare:

```text
include()
```

versus:

```text
revInclude()
```

# Part 7 — `_revinclude` with Condition

Implement:

```http
GET /Patient?_id=patient-001&_revinclude=Condition:subject
```

Expected:

```text
Patient/patient-001
Condition/condition-001
```

Explain that different resource types can reference the same Patient.

# Part 8 — Combined `_revinclude`

If supported cleanly by HAPI/local HAPI, implement:

```http
GET /Patient?_id=patient-001&_revinclude=Observation:subject&_revinclude=Condition:subject
```

Expected resources:

```text
Patient/patient-001
Observation/obs-001
Condition/condition-001
```

Do not introduce unnecessary abstraction.

# Part 9 — Comparison

Document:

| Feature | `_include` | `_revinclude` |
|---|---|---|
| Primary search | Resource A | Resource B |
| Direction | A → referenced resource | resources → B |
| Example | Observation → Patient | Patient ← Observation |
| Search | `/Observation?...&_include=Observation:subject` | `/Patient?...&_revinclude=Observation:subject` |
| Result | Observation + Patient | Patient + Observation |

Use the actual synthetic resources.

# Part 10 — Do Not Confuse Search With Include

Explain:

```http
GET /Observation?patient=patient-001
```

means:

> find Observations for this Patient.

While:

```http
GET /Observation?patient=patient-001&_include=Observation:subject
```

means:

> find those Observations and also include the Patient referenced by them.

And:

```http
GET /Patient?_id=patient-001&_revinclude=Observation:subject
```

means:

> find the Patient and also include Observations that reference it.

# Part 11 — Bundle Entry Semantics

Explain that a Bundle may contain different Resource types:

```text
Bundle
├── Observation/obs-001
└── Patient/patient-001
```

or:

```text
Bundle
├── Patient/patient-001
├── Observation/obs-001
└── Condition/condition-001
```

Inspect `Bundle.entry[].resource` and its actual Resource type.

Do not map the whole Bundle to one resource type.

# Part 12 — Tests

## Unit tests

Mock `IGenericClient`.

Test:

- Observation search with `_include`.
- Patient search with `_revinclude=Observation:subject`.
- Patient search with `_revinclude=Condition:subject`.
- Combined `_revinclude`.
- Bundle entries containing multiple Resource types.
- error propagation.

Keep fluent-chain mocks readable.

## Integration tests

Use real HAPI FHIR.

Verify:

### Include

```text
GET /Observation?patient=patient-001&_include=Observation:subject
```

contains:

```text
Observation/obs-001
Patient/patient-001
```

### RevInclude Observation

```text
GET /Patient?_id=patient-001&_revinclude=Observation:subject
```

contains:

```text
Patient/patient-001
Observation/obs-001
```

### RevInclude Condition

```text
GET /Patient?_id=patient-001&_revinclude=Condition:subject
```

contains:

```text
Patient/patient-001
Condition/condition-001
```

### Combined RevInclude

If supported, verify:

```text
patient-001
obs-001
condition-001
```

Assertions must use Resource type + logical ID, never Bundle entry order.

# Part 13 — Error Handling

Preserve the existing `FhirClientException` strategy.

Do not redesign error handling.

If an include/revinclude search fails, preserve the underlying HAPI exception as the cause.

Do not silently return an empty Bundle on server failure.

# Part 14 — Documentation

Create:

`docs/fhir/fhir-include-revinclude.md`

Teach:

1. Multiple HTTP round trips.
2. `_include`.
3. `_revinclude`.
4. Reference direction.
5. `Observation:subject`.
6. `Condition:subject`.
7. Bundles containing different Resource types.
8. HTTP representation.
9. HAPI FHIR Java representation.
10. Practical use cases.
11. Why include/revinclude should not be used indiscriminately.

Include:

```text
_include

Observation
    |
    | subject
    v
Patient
```

and:

```text
_revinclude

Patient
   ^
   |
 subject
   |
Observation
```

# Part 15 — No New Architectural Layer

Do not create:

- generic IncludeService;
- generic Bundle framework;
- generic FHIR graph engine;
- DTOs solely for this task;
- new microservice;
- controller;
- API Gateway.

A small local helper to inspect Bundle entries is acceptable if clearly justified.

# Part 16 — Explicitly Out of Scope

Do NOT implement yet:

- chained search;
- `_has`;
- `_elements`;
- `_summary`;
- pagination framework;
- terminology server;
- `$expand`;
- `$validate-code`;
- SMART on FHIR;
- OAuth;
- Epic;
- Oracle Health;
- HL7 v2;
- AI;
- RAG;
- agents;
- MCP;
- Python;
- additional microservices;
- public REST API.

# Verification

Run:

```bash
java -version
```

```bash
cd services/fhir-integration-service
mvn test
```

```bash
docker compose -f ../../infra/docker/docker-compose.yml ps
```

```bash
mvn verify -Pintegration
```

Also verify raw endpoints when useful:

```http
GET http://localhost:8080/fhir/Observation?patient=patient-001&_include=Observation:subject
```

```http
GET http://localhost:8080/fhir/Patient?_id=patient-001&_revinclude=Observation:subject
```

```http
GET http://localhost:8080/fhir/Patient?_id=patient-001&_revinclude=Condition:subject
```

If supported:

```http
GET http://localhost:8080/fhir/Patient?_id=patient-001&_revinclude=Observation:subject&_revinclude=Condition:subject
```

Show relevant Bundle entries and Resource IDs/types, not huge payloads.

# Code Quality

Follow:

- constructor injection;
- reuse existing `IGenericClient`;
- no duplicated FHIR client creation;
- small methods;
- meaningful names;
- deterministic tests;
- synthetic data only;
- preserve existing error handling;
- no unnecessary abstractions;
- no unjustified dependencies.

# Expected Structure

Remain close to:

```text
services/fhir-integration-service/
└── src/
    ├── main/
    │   └── java/
    │       └── lab/healthcare/fhir/
    │           └── client/
    │               └── ...
    └── test/
        └── java/
            └── lab/healthcare/fhir/
                └── client/
                    └── ...

docs/fhir/
├── fhir-client.md
├── fhir-search.md
├── fhir-resources-and-references.md
└── fhir-include-revinclude.md
```

Do not rename working classes without a clear reason.

# Git Rules

Do not commit automatically.

At the end show:

```bash
git status
```

```bash
git diff --stat
```

Also show relevant source/configuration diffs.

Do not push.

Do not create a Pull Request.

The developer reviews before committing.

# Acceptance Criteria

- [ ] Work is on `feature/fhir-include-revinclude`.
- [ ] Baseline Observation search works.
- [ ] `_include=Observation:subject` works.
- [ ] Include Bundle contains Observation and Patient.
- [ ] `_revinclude=Observation:subject` works.
- [ ] RevInclude Bundle contains Patient and Observation.
- [ ] `_revinclude=Condition:subject` works.
- [ ] RevInclude Bundle contains Patient and Condition.
- [ ] Combined `_revinclude` works if supported.
- [ ] Bundle inspection handles multiple Resource types.
- [ ] Tests do not rely on Bundle entry order.
- [ ] Unit tests pass without Docker.
- [ ] Integration tests pass against local HAPI.
- [ ] Existing error handling is preserved.
- [ ] No generic graph framework is introduced.
- [ ] No REST controller is added.
- [ ] No unjustified DTO is introduced.
- [ ] No unrelated technologies are introduced.
- [ ] Documentation explains HTTP FHIR and HAPI Java representations.
- [ ] Direction difference between `_include` and `_revinclude` is explicitly explained.
- [ ] No real patient information is used.
- [ ] No Git commit is created by Cursor.
- [ ] Final report contains complete step-by-step execution history.

# Final Report Format

Do NOT provide only a summary.

## Step-by-step execution

### Step 1 — ...
- What I did:
- Why:
- Files:
- FHIR HTTP:
- HAPI FHIR Java:
- Commands:
- Result:
- FHIR concept:
- Java/HAPI concept:

### Step 2 — ...
...

## Relationship direction

Show and explain:

```text
Observation
    |
    | subject
    v
Patient
```

and how this determines `_include` versus `_revinclude`.

## FHIR operations implemented

For each:

```text
FHIR HTTP:
GET ...

HAPI FHIR Java:
...

Result:
...
```

## Bundle results

Show Resource types and logical IDs returned for:

- `_include`;
- `_revinclude=Observation:subject`;
- `_revinclude=Condition:subject`;
- combined `_revinclude`, if supported.

## Synthetic data

Confirm all resources are synthetic.

## Files created

List every new file.

## Files modified

List every modified file and explain each change.

## Dependencies

State whether dependencies were added. If none, explicitly say so.

## Tests

For each test command show exact command, result, and what was verified.

## Problems encountered

List each problem and resolution.

## Concepts learned

Explain:

- `_include`;
- `_revinclude`;
- reference direction;
- search parameters;
- Bundle;
- multiple Resource types in a Bundle;
- Observation:subject;
- Condition:subject;
- HTTP versus HAPI Java representation;
- reducing unnecessary round trips.

## Git status

Show actual output of:

```bash
git status
```

## Git diff stat

Show actual output of:

```bash
git diff --stat
```

## Next step

State only the next planned task.

Do not implement the next task.
