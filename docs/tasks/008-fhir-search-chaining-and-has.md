# Task 008 — FHIR Search Chaining and `_has`

## Objective

Learn how FHIR Search can traverse relationships between Resources without the application manually loading each Resource.

This task introduces two important FHIR Search capabilities:

- **chained search**
- **reverse chained search with `_has`**

The goal is to understand how FHIR expresses relationship-aware searches through the standard query language.

Use the existing synthetic clinical graph:

```text
Patient/patient-001
    ↑
    │ subject
    │
Observation/obs-001
    └── code → LOINC 85354-9

Patient/patient-001
    ↑
    │ subject
    │
Condition/condition-001
    └── clinicalStatus = active
```

The application must continue to act as a FHIR client.

Do not create an application-specific query language.

Do not create a generic query engine.

Do not create a public REST controller.

---

# Branch

Create and use:

```text
feature/fhir-search-chaining
```

Do not work directly on `main`.

---

# Teaching Mode — Mandatory

Act as a senior instructor and implementation mentor.

Do not silently implement the task.

Execute the work step by step and explain it as you proceed.

For every significant step, show:

1. What you are doing.
2. Why you are doing it.
3. Which file is being created or modified.
4. The FHIR HTTP request.
5. The equivalent HAPI FHIR Java operation.
6. The command executed.
7. The result.
8. The FHIR concept being learned.
9. The Java/HAPI FHIR concept being learned.

Before writing code, explain the relationship graph and the search direction.

If an error occurs:

1. Show the error.
2. Explain the likely cause.
3. Explain the chosen fix.
4. Apply the fix.
5. Re-run verification.
6. Explain why the fix works.

Do not provide only a final summary.

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

Existing functionality:

- FHIR R4 client.
- CapabilityStatement retrieval.
- Patient read/search.
- Observation read/search.
- Condition read/search.
- References.
- `_include`.
- `_revinclude`.
- CRUD write operations.
- Advanced search.
- `_sort`.
- `_count`.
- date prefixes.
- search modifiers.
- Bundle handling.
- LOINC and SNOMED CT.
- synthetic data.
- existing `FhirClientException`.

Existing synthetic data:

```text
Patient/patient-001
MRN-10001
Maria Garcia
female
1985-04-12

Patient/patient-002
MRN-10002
Juan Garcia
male
1980-08-20

Patient/patient-003
MRN-10003
Maria Lopez
female
1990-02-15

Observation/obs-001
subject → Patient/patient-001
LOINC 85354-9
130 mmHg

Condition/condition-001
subject → Patient/patient-001
SNOMED CT 38341003
clinicalStatus = active
```

All data is synthetic.

Reuse the existing `IGenericClient`.

Do not create another FHIR client.

---

# Part 1 — Why Chaining Exists

Start with a normal Patient search:

```http
GET /Patient?name=Maria
```

Then explain that the Patient itself contains:

```text
Patient.name
Patient.gender
Patient.birthDate
...
```

But sometimes we want to search Patients based on data stored in another Resource.

Example:

> Find Patients who have an Observation with LOINC code `85354-9`.

The Observation contains:

```text
Observation.code
Observation.subject → Patient
```

Instead of doing this in application code:

```text
1. Search Observation
2. Extract Patient references
3. Search/read Patient resources
4. Build result set
```

FHIR Search can express the relationship in the query itself.

This is the purpose of **chained search**.

---

# Part 2 — Chained Search

Use:

```http
GET /Observation?patient.name=Maria
```

Explain the chain:

```text
Observation
    |
    | patient
    ↓
Patient
    |
    | name
    ↓
Maria
```

The search parameter:

```text
patient.name
```

means:

```text
Observation.patient
        ↓
Patient.name
```

Verify this directly against HAPI before implementing Java code.

Expected result with current synthetic data:

```text
Observation/obs-001
```

because its subject is:

```text
Patient/patient-001
```

and:

```text
patient-001.name = Maria Garcia
```

---

# Part 3 — Chained Search With Multiple Criteria

Build a more specific query.

Use:

```http
GET /Observation?patient.name=Maria&code=85354-9
```

Explain:

```text
patient.name=Maria
AND
code=85354-9
```

The first criterion traverses the reference.

The second criterion searches the Observation itself.

Expected:

```text
Observation/obs-001
```

Explain that chained search does not mean the application retrieves the Patient first.

It is expressed as one FHIR Search request.

---

# Part 4 — Chained Search Through Condition

Demonstrate another chain.

Use:

```http
GET /Condition?patient.name=Maria&clinical-status=active
```

Relationship:

```text
Condition
    |
    | patient
    ↓
Patient
    |
    | name
    ↓
Maria
```

Expected:

```text
Condition/condition-001
```

Explain that:

```text
Condition.clinicalStatus
```

is searched using:

```text
clinical-status
```

while:

```text
patient.name
```

traverses the Patient reference.

---

# Part 5 — Chained Search Is Not `_include`

Explicitly compare:

## Chained search

```http
GET /Observation?patient.name=Maria
```

Purpose:

> Filter Observations based on a property of the referenced Patient.

Result:

```text
Observation/obs-001
```

## `_include`

```http
GET /Observation?patient=patient-001&_include=Observation:subject
```

Purpose:

> Return the Observation and include the referenced Patient in the Bundle.

Result:

```text
Observation/obs-001
Patient/patient-001
```

This distinction must be clearly documented.

---

# Part 6 — Chained Search Direction

Explain that the chain starts from the Resource being searched.

For:

```http
GET /Observation?patient.name=Maria
```

the direction is:

```text
Observation
    |
    | patient
    ↓
Patient
    |
    | name
    ↓
value
```

The primary Resource remains:

```text
Observation
```

The Patient is used to filter the Observation search.

The Patient is not returned as the primary result.

---

# Part 7 — `_has`

Now introduce reverse chaining.

Explain the problem:

> Find Patients who have an Observation with a specific LOINC code.

The relationship is:

```text
Observation
    |
    | subject
    ↓
Patient
```

But the search starts from:

```text
Patient
```

We want to find Patients based on a Resource that references them.

FHIR provides:

```text
_has
```

Use:

```http
GET /Patient?_has:Observation:patient:code=85354-9
```

Explain each component carefully:

```text
_has:
Observation:
patient:
code
```

Conceptually:

```text
Patient
   ↑
   |
Observation.patient
   |
code = 85354-9
```

Verify the exact behavior against HAPI before implementing Java.

Expected:

```text
Patient/patient-001
```

Do not guess the HAPI syntax.

---

# Part 8 — `_has` With Condition

Use:

```http
GET /Patient?_has:Condition:patient:clinical-status=active
```

Expected:

```text
Patient/patient-001
```

Explain:

```text
Patient
   ↑
   |
Condition.patient
   |
clinical-status = active
```

The primary search result is still Patient.

The Condition is only used as the reverse relationship criterion.

---

# Part 9 — `_has` vs `_revinclude`

This distinction is critical.

Compare:

## `_revinclude`

```http
GET /Patient?_id=patient-001&_revinclude=Observation:subject
```

Purpose:

> Return the Patient and also include Observations that reference it.

Result:

```text
Patient/patient-001
Observation/obs-001
```

## `_has`

```http
GET /Patient?_has:Observation:patient:code=85354-9
```

Purpose:

> Find Patients that have an Observation matching the condition.

Result:

```text
Patient/patient-001
```

Therefore:

```text
_revinclude
→ add related Resources to the Bundle

_has
→ filter the primary Resource based on related Resources
```

This difference must be explicit in the documentation.

---

# Part 10 — Combined `_has` Criteria

If supported cleanly by local HAPI, demonstrate:

```http
GET /Patient?_has:Observation:patient:code=85354-9&gender=female
```

Explain:

```text
_has:Observation:patient:code=85354-9
AND
gender=female
```

Expected:

```text
Patient/patient-001
```

Do not create an application-specific filtering layer.

---

# Part 11 — Chaining Through Identifier

If supported cleanly by HAPI, demonstrate:

```http
GET /Observation?patient.identifier=MRN-10001
```

Explain:

```text
Observation
   |
   | patient
   ↓
Patient
   |
   | identifier
   ↓
MRN-10001
```

Expected:

```text
Observation/obs-001
```

This is an important interoperability example because the external system may know the patient's business identifier rather than the FHIR logical ID.

If HAPI requires a specific token syntax for the chained identifier search, use the correct syntax and explain it.

Do not force the example if local HAPI does not support the exact form being attempted. Document the actual server capability/result.

---

# Part 12 — HAPI FHIR Java API

For each supported operation, implement the equivalent HAPI fluent search.

Do not blindly assume method names.

First verify HAPI FHIR 8.10.0.

Conceptually:

```java
client.search()
    .forResource(Observation.class)
    .where(
        Observation.PATIENT.hasChainedProperty(
            Patient.NAME.matches().value("Maria")
        )
    )
    .returnBundle(Bundle.class)
    .execute();
```

The exact HAPI API may differ.

Use the actual API available in HAPI 8.10.0.

For `_has`, verify the correct HAPI representation of reverse chaining.

If HAPI's fluent API does not expose a clean method for the exact `_has` expression, it is acceptable to use the appropriate search parameter mechanism supported by HAPI, but explain why.

Do not hide this implementation detail.

---

# Part 13 — HTTP First, Java Second

For every operation follow this teaching sequence:

```text
1. FHIR HTTP
        ↓
2. HAPI local verification
        ↓
3. HAPI Java equivalent
        ↓
4. Unit test
        ↓
5. Integration test
        ↓
6. Documentation
```

Do not start by writing Java and then guessing what the HTTP query means.

---

# Part 14 — Unit Tests

Add unit tests using mocks.

Test at minimum:

- Observation chained search by `patient.name`;
- Observation chained search by `patient.name + code`;
- Condition chained search by `patient.name + clinical-status`;
- Patient `_has` Observation by code;
- Patient `_has` Condition by clinical-status;
- combined `_has` + Patient parameter;
- chained identifier search if implemented;
- error propagation.

Keep fluent mocks readable.

If deep stubs are required, explain why.

---

# Part 15 — Integration Tests

Use real HAPI FHIR.

Verify:

### Chained Observation

```http
GET /Observation?patient.name=Maria
```

Expected:

```text
Observation/obs-001
```

### Chained Observation + code

```http
GET /Observation?patient.name=Maria&code=85354-9
```

Expected:

```text
Observation/obs-001
```

### Chained Condition

```http
GET /Condition?patient.name=Maria&clinical-status=active
```

Expected:

```text
Condition/condition-001
```

### `_has` Observation

```http
GET /Patient?_has:Observation:patient:code=85354-9
```

Expected:

```text
Patient/patient-001
```

### `_has` Condition

```http
GET /Patient?_has:Condition:patient:clinical-status=active
```

Expected:

```text
Patient/patient-001
```

### Combined `_has`

If supported:

```http
GET /Patient?_has:Observation:patient:code=85354-9&gender=female
```

Expected:

```text
Patient/patient-001
```

### Chained identifier

If supported:

```http
GET /Observation?patient.identifier=MRN-10001
```

Expected:

```text
Observation/obs-001
```

Assertions must use Resource type + logical ID.

Do not depend on Bundle entry order unless ordering is explicitly part of the query.

---

# Part 16 — Raw HTTP Verification

Use `curl.exe` or PowerShell against:

```text
http://localhost:8080/fhir
```

Show concise results for:

```http
GET /Observation?patient.name=Maria
```

```http
GET /Observation?patient.name=Maria&code=85354-9
```

```http
GET /Condition?patient.name=Maria&clinical-status=active
```

```http
GET /Patient?_has:Observation:patient:code=85354-9
```

```http
GET /Patient?_has:Condition:patient:clinical-status=active
```

And optionally:

```http
GET /Observation?patient.identifier=MRN-10001
```

Do not paste huge Bundle payloads.

Show:

```text
Bundle.type
Bundle.total
Resource type
Resource logical ID
```

---

# Part 17 — Documentation

Create:

```text
docs/fhir/fhir-search-chaining.md
```

Teach:

1. What chained search is.
2. Search direction.
3. `patient.name`.
4. Chaining with multiple criteria.
5. Chained search versus `_include`.
6. What `_has` is.
7. `_has` syntax.
8. `_has` versus `_revinclude`.
9. Chained identifier search.
10. HAPI FHIR fluent API.
11. HTTP versus HAPI Java.
12. Practical interoperability use cases.

Include these diagrams:

```text
Chained search

Observation
    |
    | patient
    ↓
Patient
    |
    | name
    ↓
Maria
```

and:

```text
_has

Patient
   ↑
   |
Observation.patient
   |
Observation.code = 85354-9
```

and:

```text
_revinclude

Patient
   ↑
   |
Observation.subject
```

---

# Part 18 — Update Existing Documentation

Update only what is necessary:

```text
docs/fhir/README.md
docs/roadmap.md
```

Do not rewrite unrelated content.

---

# Part 19 — No Generic Query Framework

Do NOT create:

- generic search builder;
- query parser;
- dynamic query language;
- SQL abstraction;
- generic FHIR graph engine;
- generic chaining framework;
- pagination framework;
- DTOs solely for search;
- new microservice;
- REST controller;
- API Gateway.

The objective is to understand standard FHIR Search.

---

# Part 20 — Explicitly Out of Scope

Do NOT implement yet:

- `_include` beyond what already exists;
- `_revinclude` beyond what already exists;
- `_elements`;
- `_summary`;
- `_text`;
- `_content`;
- `$everything`;
- `$match`;
- `$member-match`;
- terminology services;
- `$expand`;
- `$validate-code`;
- `$translate`;
- ConceptMap;
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

Do not jump ahead to external EHR integration.

---

# Verification

Run:

```bash
java -version
```

Then:

```bash
cd services/fhir-integration-service
mvn test
```

Verify infrastructure:

```bash
docker compose -f ../../infra/docker/docker-compose.yml ps
```

Then:

```bash
mvn verify -Pintegration
```

Check:

```bash
git status
```

and:

```bash
git diff --stat
```

Do not commit automatically.

Do not push.

Do not create a Pull Request.

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
- no new dependencies unless justified.

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

docs/fhir/
├── fhir-client.md
├── fhir-search.md
├── fhir-resources-and-references.md
├── fhir-include-revinclude.md
├── fhir-crud-write-operations.md
├── fhir-advanced-search.md
└── fhir-search-chaining.md
```

Do not rename existing working classes without a clear reason.

---

# Acceptance Criteria

- [ ] Work is on `feature/fhir-search-chaining`.
- [ ] Chained search using `patient.name` works against local HAPI.
- [ ] Chained Observation search + code works.
- [ ] Chained Condition search + clinical-status works.
- [ ] Difference between chained search and `_include` is documented.
- [ ] `_has` Observation search works if supported by local HAPI.
- [ ] `_has` Condition search works if supported by local HAPI.
- [ ] Difference between `_has` and `_revinclude` is documented.
- [ ] Combined `_has` search is demonstrated if supported.
- [ ] Chained identifier search is demonstrated if supported.
- [ ] HAPI Java equivalents are verified against HAPI 8.10.0.
- [ ] Unit tests pass without Docker.
- [ ] Integration tests pass against local HAPI.
- [ ] Existing error handling is preserved.
- [ ] No generic search/query framework is introduced.
- [ ] No REST controller is added.
- [ ] No DTO is introduced without clear justification.
- [ ] No unrelated technology is introduced.
- [ ] All data is synthetic.
- [ ] Documentation explains HTTP and HAPI FHIR representations.
- [ ] No Git commit is created by Cursor.
- [ ] Final report contains complete step-by-step execution history.

---

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

Show:

```text
Observation
    |
    | patient
    ↓
Patient
    |
    | name
    ↓
Maria
```

and:

```text
Patient
   ↑
   |
Observation.patient
   |
code = 85354-9
```

Explain the difference.

## Search examples

For every implemented operation show:

```text
FHIR HTTP:
GET ...

HAPI FHIR Java:
...

Result:
...
```

## Chained search vs `_include`

Explain the difference with concrete requests and Bundle results.

## `_has` vs `_revinclude`

Explain the difference with concrete requests and Bundle results.

## Synthetic data

Confirm all data is synthetic.

## Files created

List every new file.

## Files modified

List every modified file and explain each change.

## Dependencies

State whether dependencies were added.

If none were added, explicitly say so.

## Tests

For every command show:

- exact command;
- result;
- what was verified.

## Raw HTTP verification

Show selected HTTP requests and concise results.

## Problems encountered

List each problem and resolution.

## Concepts learned

Explain:

- chained search;
- search direction;
- `patient.name`;
- chained token/reference searches;
- `_has`;
- `_has` versus `_revinclude`;
- chained identifier;
- HTTP versus HAPI Java.

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
