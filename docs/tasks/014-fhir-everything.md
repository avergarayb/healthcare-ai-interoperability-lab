# Task 014 — FHIR `$everything` and Patient-Centric Retrieval

## Objective

Learn how FHIR can retrieve a broad set of clinical information related to one Patient using the `$everything` operation.

Until now we have learned several ways to retrieve related information:

- `GET /Patient/{id}`
- `GET /Observation?patient={id}`
- `GET /Condition?patient={id}`
- `_include`
- `_revinclude`
- search chaining
- pagination
- history and versioning
- transactions and batch

The next concept is different.

Instead of manually deciding:

```text
Patient
   ↓
Observation
   ↓
Condition
   ↓
MedicationRequest
   ↓
Encounter
   ↓
...
```

FHIR can expose a Patient-centric operation:

```http
GET /Patient/{id}/$everything
```

The operation asks the FHIR server for the Resources associated with that Patient that the server chooses to include according to the operation's rules and implementation.

This task is about understanding the operation, not building a generic clinical aggregation engine.

---

# Branch

Create and use:

```text
feature/fhir-everything
```

Do not work directly on `main`.

---

# Teaching Mode — Mandatory

Act as a senior instructor and implementation mentor.

Do not silently implement the task.

For every significant step, show:

1. What you are doing.
2. Why you are doing it.
3. Which file is being created or modified.
4. The raw FHIR HTTP request.
5. The equivalent HAPI FHIR Java operation.
6. The command executed.
7. The result.
8. The FHIR concept being learned.
9. The Java/HAPI FHIR concept being learned.

Before implementing Java production code, first demonstrate the relevant HTTP behavior against HAPI.

Do not guess HAPI 8.10.0 API signatures.

Inspect the actual HAPI API when necessary using `javap` or dependency inspection.

If HAPI behaves differently from the FHIR specification or from assumptions in this task, document the observed behavior rather than hiding it.

At the end provide a complete step-by-step report.

---

# Context

Repository:

```text
healthcare-ai-interoperability-lab
```

Service:

```text
services/fhir-integration-service
```

Technology:

- Java 21
- Spring Boot 3.5.x
- Maven
- HAPI FHIR 8.10.0
- FHIR R4 / `4.0.1`

FHIR server:

```text
http://localhost:8080/fhir
```

Existing client:

```text
IGenericClient
```

Existing synthetic data includes:

```text
Patient/patient-001
Observation/obs-001
Condition/condition-001
```

The existing resources use:

```text
Observation.subject → Patient/patient-001
Condition.subject   → Patient/patient-001
```

Reuse the existing client and service patterns.

---

# Part 1 — Understand `$everything`

Start with the conceptual difference.

Previously:

```http
GET /Patient/patient-001
```

returns one Patient.

And:

```http
GET /Observation?patient=patient-001
```

returns matching Observations.

With:

```http
GET /Patient/patient-001/$everything
```

the request is an operation on the Patient.

Conceptually:

```text
Patient
   │
   ├── Observation
   ├── Condition
   ├── Encounter
   ├── MedicationRequest
   └── other patient-related Resources
```

The result is a:

```text
Bundle
```

Explain why this is different from manually executing several searches.

---

# Part 2 — Verify Capability and Operation Support

Before writing Java code, inspect the local HAPI server.

Check:

```http
GET /metadata
```

Determine whether the CapabilityStatement explicitly advertises support for `$everything`.

Do not assume that the operation is advertised simply because HAPI may execute it.

Then test the actual operation.

Document both:

```text
advertised support
```

and:

```text
observed support
```

if they differ.

---

# Part 3 — Raw HTTP `$everything`

Execute:

```http
GET /Patient/patient-001/$everything
```

Inspect:

```text
HTTP status
Bundle.type
Bundle.entry
Bundle.total
Bundle.link
```

Identify every Resource returned.

For example:

```text
Bundle
 type = searchset
    │
    ├── Patient/patient-001
    ├── Observation/obs-001
    └── Condition/condition-001
```

Do not assume the Bundle type.

Verify it from the actual response.

---

# Part 4 — Compare `$everything` with `_include` / `_revinclude`

This comparison is mandatory.

Previously:

```http
GET /Observation?patient=patient-001&_include=Observation:subject
```

means approximately:

```text
Find Observations
      ↓
include their subject
      ↓
Patient
```

Whereas:

```http
GET /Patient/patient-001/$everything
```

is:

```text
Start with Patient
      ↓
retrieve the Patient-related clinical data
```

Explain why these are not interchangeable.

Create a comparison:

```text
Search + _include
    ↓
controlled search result + referenced resources

Search + _revinclude
    ↓
resources pointing to the search result

$everything
    ↓
Patient-centric operation
```

---

# Part 5 — Inspect the Returned Bundle

Inspect:

```text
entry[]
```

For every returned Resource record:

```text
resourceType
id
```

Build a Resource inventory.

Example:

```text
Patient/patient-001
Observation/obs-001
Condition/condition-001
```

Do not assume ordering.

Use Resource identity:

```text
resourceType + "/" + id
```

as learned in previous tasks.

---

# Part 6 — Understand Operation vs Search

Explain the difference between:

```http
GET /Patient?name=Maria
```

and:

```http
GET /Patient/patient-001/$everything
```

The first is a FHIR search.

The second is a FHIR operation.

Explain:

```text
Search
    ↓
search parameters

Operation
    ↓
operation definition
```

Also explain why `$everything` is not simply another search parameter.

---

# Part 7 — Parameters

Investigate whether the local HAPI implementation supports parameters for `$everything`, such as:

```text
_start
_end
_type
```

Do not implement a parameter unless it is actually supported by this HAPI version.

For each parameter investigated:

1. Show the raw HTTP request.
2. Show the response.
3. Determine whether it changes the result.
4. Document actual HAPI behavior.

Pay particular attention to `_type`.

If supported, compare:

```http
GET /Patient/patient-001/$everything?_type=Observation
```

with:

```http
GET /Patient/patient-001/$everything
```

Do not assume the result is a pure Observation-only Bundle; verify it.

---

# Part 8 — Pagination

Connect this task with Task 012.

Determine whether `$everything` can return:

```text
Bundle.link[next]
```

when enough Resources exist.

If pagination is supported:

```text
$everything
    ↓
Bundle
    ↓
next
    ↓
next
    ↓
last page
```

Reuse the existing `nextPage` logic.

Do not create a second pagination implementation.

If the current dataset is too small, create enough synthetic patient-related Resources to make pagination observable.

Use deterministic synthetic data.

---

# Part 9 — Synthetic Clinical Dataset

If additional Resources are required, add synthetic Resources only.

Suggested Resources:

```text
Patient
Observation
Condition
Encounter
MedicationRequest
```

Only add Resources that are useful for demonstrating `$everything`.

Do not create a large artificial clinical model.

Keep the dataset small and deterministic.

Every Resource must be linked to:

```text
Patient/patient-001
```

through the appropriate FHIR relationship.

Do not fabricate relationships that violate the R4 model.

---

# Part 10 — HAPI FHIR Java API

After the raw HTTP behavior is understood, inspect the HAPI FHIR 8.10.0 API.

Determine the correct Java invocation for:

```text
Patient/$everything
```

Possible HAPI operation patterns may involve:

```java
client.operation()
```

but do not assume the exact API.

Inspect the actual library.

Determine:

- operation name;
- target Resource;
- parameter representation;
- return type;
- pagination handling.

Document the exact API discovered.

---

# Part 11 — Implement `$everything` in `FhirService`

Add a focused method such as:

```text
getPatientEverything(patientId)
```

Return the native:

```text
Bundle
```

Do not introduce a DTO.

Do not build a generic "clinical summary" abstraction.

The purpose is to understand the native FHIR operation.

Reuse:

```text
IGenericClient
```

and existing Bundle helpers where appropriate.

---

# Part 12 — Optional Parameter Support

Only if verified against HAPI, expose focused methods for useful parameters.

For example:

```text
getPatientEverything(patientId, start, end)
```

or:

```text
getPatientEverythingByTypes(patientId, types)
```

Do not add methods for unsupported parameters.

Do not create a generic parameter map unless there is a demonstrated need.

---

# Part 13 — `$everything` vs Manual Aggregation

This is an important architectural lesson.

Compare:

```text
Manual aggregation

GET Patient
GET Observation?patient=...
GET Condition?patient=...
GET Encounter?patient=...
GET MedicationRequest?patient=...
```

against:

```text
GET Patient/{id}/$everything
```

Discuss:

- number of requests;
- server responsibility;
- returned Bundle;
- pagination;
- consistency considerations;
- implementation differences;
- why a client cannot assume `$everything` returns every possible clinical Resource in every FHIR server.

Do not claim that `$everything` is universally identical across implementations.

---

# Part 14 — Unit Tests

Add unit tests for:

- `$everything` returns a Bundle;
- correct Patient ID is used;
- returned Bundle is handled correctly;
- Resource identities are extracted without assuming order;
- pagination reuses the existing `nextPage`;
- operation errors propagate through `FhirClientException`;
- optional parameters, only if implemented.

Mock only the HAPI interactions needed by the service.

---

# Part 15 — Integration Tests

Use real HAPI.

At minimum verify:

### Basic operation

```http
GET /Patient/patient-001/$everything
```

### Resource inventory

Verify that the expected synthetic Resources are returned.

At minimum, if supported by HAPI:

```text
Patient/patient-001
Observation/obs-001
Condition/condition-001
```

### Bundle

Verify the actual:

```text
Bundle.type
```

Do not hardcode an assumed type without checking the response.

### Pagination

If supported, create enough data and verify:

```text
next
```

and traverse all pages.

### Parameters

Only if the local HAPI supports the parameter being tested.

---

# Part 16 — Error Handling

Test at least one invalid/nonexistent Patient:

```http
GET /Patient/does-not-exist/$everything
```

Determine the actual HAPI response.

Document whether it is:

```text
404
OperationOutcome
other behavior
```

The service must not silently return an empty Bundle when the server reports an error.

Preserve the original cause through:

```text
FhirClientException
```

where appropriate.

---

# Part 17 — Documentation

Create:

```text
docs/fhir/fhir-everything.md
```

Explain:

1. What `$everything` is.
2. Why it exists.
3. Patient-centric retrieval.
4. Operation vs search.
5. `$everything` vs `_include`.
6. `$everything` vs `_revinclude`.
7. Bundle returned.
8. Resource inventory.
9. Supported parameters discovered.
10. Pagination.
11. HAPI Java invocation.
12. Error behavior.
13. Limitations and implementation differences.

Include raw HTTP examples and equivalent HAPI Java examples.

---

# Part 18 — Update Existing Documentation

Update only what is necessary:

```text
docs/fhir/README.md
docs/roadmap.md
```

Do not rewrite unrelated documentation.

---

# Out of Scope

Do NOT implement:

- public REST controller;
- external EHR;
- Epic;
- Oracle Health;
- SMART on FHIR;
- OAuth;
- HL7 v2;
- AI;
- RAG;
- agents;
- MCP;
- Python service;
- Bulk Data `$export`;
- generic clinical aggregation engine;
- generic FHIR operation framework;
- production patient-summary UI.

Important:

```text
$everything ≠ $export
```

Do not mix Patient `$everything` with Bulk Data export.

---

# Code Quality

Follow:

- constructor injection;
- reuse existing `IGenericClient`;
- no duplicated FHIR client creation;
- small methods;
- meaningful names;
- deterministic tests;
- synthetic data only;
- preserve existing `FhirClientException`;
- no unnecessary abstractions;
- no unnecessary dependencies.

Reuse the existing pagination helper instead of duplicating it.

---

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

scripts/fhir/
└── ...

docs/fhir/
└── fhir-everything.md

docs/tasks/
└── 014-fhir-everything.md
```

Do not rename existing working classes without a clear reason.

---

# Acceptance Criteria

- [ ] Work is on `feature/fhir-everything`.
- [ ] `$everything` is explained from a beginner perspective.
- [ ] Raw HTTP behavior is verified before Java implementation.
- [ ] HAPI 8.10.0 operation API is inspected rather than guessed.
- [ ] CapabilityStatement support is investigated.
- [ ] `Patient/{id}/$everything` is tested against real HAPI.
- [ ] Returned Bundle type is verified from the actual response.
- [ ] Returned Resource identities are inspected.
- [ ] `$everything` is compared with `_include`.
- [ ] `$everything` is compared with `_revinclude`.
- [ ] `$everything` is compared with manual multi-search aggregation.
- [ ] Supported parameters are experimentally verified.
- [ ] Unsupported parameters are not implemented.
- [ ] Pagination is investigated.
- [ ] Existing `nextPage` logic is reused where applicable.
- [ ] Synthetic data remains deterministic.
- [ ] No public REST controller is added.
- [ ] No external EHR is added.
- [ ] No AI is added.
- [ ] No Python service is added.
- [ ] No Bulk Data `$export` is implemented.
- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] No unnecessary dependency is introduced.
- [ ] No Git commit is created automatically.
- [ ] No push is performed automatically.
- [ ] Final report contains complete step-by-step execution history.

---

# Verification

Run:

```bash
java -version
```

Then:

```bash
cd services/fhir-integration-service
mvn clean test
```

Verify infrastructure:

```bash
docker compose -f ../../infra/docker/docker-compose.yml ps
```

Then:

```bash
mvn clean verify -Pintegration
```

Perform raw HTTP verification separately.

Finally:

```bash
git status
git diff --stat
```

Do not commit automatically.

Do not push.

Do not create a Pull Request.

---

# Final Report Format

Do NOT provide only a summary.

## Step-by-step execution

For every step:

- What I did:
- Why:
- Files:
- FHIR HTTP:
- HAPI FHIR Java:
- Commands:
- Result:
- FHIR concept:
- Java/HAPI concept:

## `$everything` model

Show:

```text
Patient/patient-001
        │
        ├── Observation/obs-001
        ├── Condition/condition-001
        └── other returned Resources
```

Explain that `$everything` is a Patient-centric FHIR operation.

## Comparison

Show:

```text
Patient read
Observation search
_include
_revinclude
$everything
```

Explain when each mechanism is used.

## Raw HTTP

Show actual requests and responses for:

- CapabilityStatement;
- `$everything`;
- supported parameters;
- pagination;
- invalid Patient.

## Bundle results

Show:

- actual Bundle type;
- total if present;
- entries;
- links;
- Resource identities.

## HAPI Java

Show the exact HAPI 8.10.0 API used.

## Results

Show:

- Resources returned;
- Bundle type;
- pagination behavior;
- supported parameters;
- error behavior.

## Files created

List every new file.

## Files modified

List every modified file and explain each change.

## Dependencies

State whether dependencies were added.

## Tests

For every command show:

- exact command;
- result;
- what was verified.

## Problems encountered

List each problem and resolution.

## Concepts learned

Explain:

- FHIR operation;
- `$everything`;
- Patient-centric retrieval;
- operation vs search;
- `_include` vs `_revinclude`;
- `$everything` vs manual aggregation;
- Bundle;
- pagination;
- operation parameters;
- implementation differences.

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
