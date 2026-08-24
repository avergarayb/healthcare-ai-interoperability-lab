# Task 007 — FHIR Advanced Search

## Objective

Extend the FHIR search capabilities of `fhir-integration-service` beyond simple `name`, `identifier`, and reference-based searches.

The goal is to understand how FHIR Search parameters become more expressive while still remaining standards-based.

This task focuses on:

- multiple search parameters;
- search modifiers;
- date search prefixes;
- `_sort`;
- `_count`;
- pagination concepts;
- searching `Observation` by patient and code;
- searching `Condition` by patient and clinical status;
- understanding how FHIR represents search results in `Bundle`.

Do not implement application-specific search syntax.

Do not create a generic search engine.

Do not introduce a public REST controller.

---

# Branch

Create and use:

```text
feature/fhir-advanced-search
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

Before implementing a search feature, explain the FHIR Search semantics first.

If an error occurs:

1. Show the error.
2. Explain the likely cause.
3. Explain the chosen fix.
4. Apply the fix.
5. Re-run verification.
6. Explain why the fix works.

Do not provide only a final summary.

At the end provide:

- concise summary;
- complete step-by-step execution report;
- HTTP FHIR operations;
- HAPI FHIR Java equivalents;
- test results;
- concepts learned;
- Git status;
- Git diff stat.

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
- Bundle handling.
- References.
- `_include`.
- `_revinclude`.
- CRUD write operations.
- LOINC and SNOMED CT.
- Synthetic data.
- Existing error handling through `FhirClientException`.

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

Use synthetic data only.

Reuse the existing `IGenericClient`.

Do not create another FHIR client.

---

# Part 1 — Search Parameters Recap

Before coding, reinforce the distinction between:

```http
GET /Patient/patient-001
```

and:

```http
GET /Patient?name=Maria
```

Explain:

```text
Read
→ one known Resource by logical ID

Search
→ matching Resources
→ Bundle/searchset
```

Then explain that FHIR Search supports multiple parameters.

Example:

```http
GET /Patient?name=Maria&gender=female
```

Conceptually:

```text
name = Maria
AND
gender = female
```

Verify this behavior against the local HAPI server.

Do not assume OR semantics between different parameters.

---

# Part 2 — Search Observation by Patient + Code

Use:

```text
Observation
```

with:

```text
patient=patient-001
code=85354-9
```

FHIR HTTP:

```http
GET /Observation?patient=patient-001&code=85354-9
```

Expected:

```text
Bundle/searchset
└── Observation/obs-001
```

Explain:

```text
patient
```

is a search parameter referring to the Observation's patient/subject relationship.

And:

```text
code
```

searches the coded clinical concept.

Implement the HAPI FHIR equivalent using the correct R4 search parameter API.

Do not blindly assume the Java syntax. Verify HAPI FHIR 8.10.0.

---

# Part 3 — Search Condition by Patient + Status

Use:

```http
GET /Condition?patient=patient-001&clinical-status=active
```

Expected:

```text
Condition/condition-001
```

Explain:

```text
clinical-status
```

is a FHIR Search parameter associated with the Condition resource.

Distinguish:

```text
Condition.clinicalStatus
```

from:

```text
Condition?clinical-status=active
```

The first is the Resource element.

The second is the FHIR Search parameter.

Implement the HAPI FHIR equivalent.

---

# Part 4 — Search Modifiers

Introduce search modifiers carefully.

Use a simple Patient search.

Demonstrate:

```http
GET /Patient?name:exact=Maria
```

Explain:

```text
name
```

versus:

```text
name:exact
```

The modifier changes how the search parameter is evaluated.

Before implementing, verify the local HAPI behavior with the synthetic dataset.

If HAPI's behavior for the exact-match example is not sufficiently deterministic with the current data, add or adjust synthetic data only if necessary and explain why.

Do not introduce arbitrary custom modifiers.

Do not implement unsupported modifiers.

---

# Part 5 — Date Search Prefixes

Use a date search on Patient birth date.

Teach the FHIR date search prefixes:

```text
eq
ne
lt
le
gt
ge
sa
eb
ap
```

Do not implement every prefix.

Implement at least:

```text
ge
```

and:

```text
lt
```

using:

```http
GET /Patient?birthdate=ge1985-01-01
```

and:

```http
GET /Patient?birthdate=lt1990-01-01
```

Explain that these are FHIR search semantics, not SQL operators.

Verify expected synthetic results.

Use the correct HAPI FHIR date search API.

Do not rely on implicit string comparison.

---

# Part 6 — `_sort`

Introduce:

```text
_sort
```

Explain that `_sort` controls result ordering.

Use:

```http
GET /Patient?_sort=birthdate
```

and, if useful:

```http
GET /Patient?_sort=-birthdate
```

Explain:

```text
birthdate
```

ascending and:

```text
-birthdate
```

descending.

Implement the HAPI equivalent.

Verify the ordering explicitly in the integration test.

Unlike previous Bundle tests, ordering is now intentionally part of the behavior being tested.

Do not confuse:

```text
_sort
```

with:

```text
_id
```

or with database-specific `ORDER BY`.

---

# Part 7 — `_count`

Introduce:

```text
_count
```

Example:

```http
GET /Patient?_count=2
```

Explain that `_count` controls the requested page size and does not mean:

```text
return exactly two total matches
```

The response is still a search Bundle.

Inspect:

```text
Bundle.total
```

and:

```text
Bundle.entry
```

Explain the difference.

If the local HAPI response contains pagination links, show:

```text
Bundle.link
```

when relevant.

Do not implement a custom pagination framework.

---

# Part 8 — Pagination Concepts

Teach the difference between:

```text
page size
```

and:

```text
total matching resources
```

Use `_count`.

If HAPI returns a `next` link, inspect it.

Explain:

```text
Bundle.total
```

versus:

```text
Bundle.entry.size()
```

versus:

```text
Bundle.link[next]
```

Do not manually construct pagination URLs unless needed for the demonstration.

Do not create a generic pagination service.

The objective is to understand the FHIR protocol behavior.

---

# Part 9 — Combine Search Parameters

Demonstrate a realistic search:

```http
GET /Observation?patient=patient-001&code=85354-9&_sort=-date&_count=10
```

Explain each part:

```text
patient
code
_sort
_count
```

Implement the HAPI equivalent.

If `date` is not the appropriate sortable element for the exact HAPI search syntax, use the correct FHIR search parameter and explain the choice.

Do not invent a custom parameter.

---

# Part 10 — SearchResult Model

Review the existing Bundle handling.

Explain:

```text
Bundle
├── type = searchset
├── total
├── entry[]
└── link[]
```

For this task, make the tests inspect:

```text
total
entry
link
```

when applicable.

Do not convert the Bundle into an application-specific DTO.

The purpose is to understand the FHIR wire model.

---

# Part 11 — Unit Tests

Mock `IGenericClient`.

Add unit tests for:

- Patient search with multiple parameters.
- Observation search by patient + code.
- Condition search by patient + clinical status.
- Patient search with `name:exact`.
- Patient date search.
- `_sort`.
- `_count`.
- combined search.
- error propagation.

Keep fluent mocks readable.

If deep stubs are used, explain why.

---

# Part 12 — Integration Tests

Use real HAPI FHIR.

Verify:

### Multiple parameters

```http
GET /Patient?name=Maria&gender=female
```

Expected:

```text
patient-001
patient-003
```

### Observation patient + code

```http
GET /Observation?patient=patient-001&code=85354-9
```

Expected:

```text
obs-001
```

### Condition patient + status

```http
GET /Condition?patient=patient-001&clinical-status=active
```

Expected:

```text
condition-001
```

### Exact modifier

```http
GET /Patient?name:exact=Maria
```

Verify actual local HAPI behavior.

### Date prefix

```http
GET /Patient?birthdate=ge1985-01-01
```

and:

```http
GET /Patient?birthdate=lt1990-01-01
```

Verify expected IDs.

### Sort

```http
GET /Patient?_sort=birthdate
```

Verify ascending order.

If descending is implemented:

```http
GET /Patient?_sort=-birthdate
```

verify descending order.

### Count

```http
GET /Patient?_count=2
```

Verify:

- Bundle type;
- `total`;
- number of returned entries;
- pagination link behavior if present.

### Combined

Verify a realistic multi-parameter search.

Tests must be deterministic.

---

# Part 13 — Raw HTTP Verification

When useful, verify selected searches directly against HAPI using `curl.exe` or PowerShell.

Examples:

```http
GET http://localhost:8080/fhir/Patient?name=Maria&gender=female
```

```http
GET http://localhost:8080/fhir/Observation?patient=patient-001&code=85354-9
```

```http
GET http://localhost:8080/fhir/Condition?patient=patient-001&clinical-status=active
```

```http
GET http://localhost:8080/fhir/Patient?name:exact=Maria
```

```http
GET http://localhost:8080/fhir/Patient?birthdate=ge1985-01-01
```

```http
GET http://localhost:8080/fhir/Patient?_sort=birthdate
```

```http
GET http://localhost:8080/fhir/Patient?_count=2
```

Do not paste huge responses.

Show relevant IDs, totals, and links.

---

# Part 14 — Search Semantics

Document explicitly:

## Multiple parameters

Different search parameters normally combine as:

```text
AND
```

Example:

```text
name=Maria
AND
gender=female
```

## Same parameter repeated

Do not assume the semantics.

If demonstrated, verify actual FHIR/HAPI behavior and document it.

Do not generalize beyond what was tested.

## Modifiers

Explain:

```text
name:exact
```

is different from:

```text
name
```

## Prefixes

Explain that date prefixes have defined FHIR semantics.

Do not treat them as SQL operators.

---

# Part 15 — Documentation

Create:

```text
docs/fhir/fhir-advanced-search.md
```

Teach:

1. Multiple search parameters.
2. Search parameter versus Resource element.
3. Search modifiers.
4. `name:exact`.
5. Date prefixes.
6. `_sort`.
7. `_count`.
8. Bundle `total`.
9. Bundle `entry`.
10. Bundle `link`.
11. Pagination concepts.
12. HAPI fluent search API.
13. FHIR HTTP versus HAPI Java.

Include concrete examples from the synthetic dataset.

---

# Part 16 — Update Existing Documentation

Update only what is necessary:

```text
docs/fhir/README.md
docs/roadmap.md
```

Do not rewrite unrelated material.

---

# Part 17 — No Generic Search Framework

Do NOT create:

- generic search builder;
- dynamic query language;
- SQL-like abstraction;
- generic FHIR query parser;
- generic pagination service;
- search DTOs;
- new microservice;
- REST controller;
- API Gateway.

The objective is to understand FHIR Search directly.

---

# Part 18 — Explicitly Out of Scope

Do NOT implement yet:

- chained search;
- `_has`;
- `_elements`;
- `_summary`;
- `_text`;
- `_content`;
- `$everything`;
- `$match`;
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
└── fhir-advanced-search.md
```

Do not rename existing working classes without a clear reason.

---

# Acceptance Criteria

- [ ] Work is on `feature/fhir-advanced-search`.
- [ ] Multiple search parameters are demonstrated.
- [ ] Observation search by patient + code works.
- [ ] Condition search by patient + clinical status works.
- [ ] `name:exact` is demonstrated and verified against local HAPI.
- [ ] Date search with `ge` works.
- [ ] Date search with `lt` works.
- [ ] `_sort` ascending works.
- [ ] `_sort` descending works if implemented.
- [ ] `_count` is demonstrated.
- [ ] Bundle `total` is distinguished from `entry.size()`.
- [ ] Bundle pagination links are inspected when present.
- [ ] Combined search parameters are demonstrated.
- [ ] HAPI Java equivalents are documented.
- [ ] Unit tests pass without Docker.
- [ ] Integration tests pass against local HAPI.
- [ ] Existing error handling is preserved.
- [ ] No generic search framework is introduced.
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

## Search examples

For every implemented search show:

```text
FHIR HTTP:
GET ...

HAPI FHIR Java:
...

Result:
...
```

## Search semantics

Explain:

- multiple parameters;
- search modifiers;
- date prefixes;
- `_sort`;
- `_count`;
- `Bundle.total`;
- `Bundle.entry`;
- `Bundle.link`.

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

- advanced FHIR Search;
- multiple search parameters;
- modifiers;
- date prefixes;
- sorting;
- count/page size;
- total vs entries;
- pagination links;
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
