# Task 012 — FHIR Pagination and Result Control

## Objective

Learn how FHIR controls large search results.

Until now we have searched Resources and received a `Bundle` of type `searchset`. In a real FHIR server, a search may return thousands or millions of matches, so results are divided into pages.

This task teaches:

- `_count`;
- `Bundle.total`;
- `Bundle.entry`;
- `Bundle.link`;
- `self`, `first`, `previous`, `next`, `last`;
- server-controlled pagination;
- following the next-page link;
- HAPI FHIR Java pagination;
- retrieving all pages safely;
- page size vs total matches.

Do not introduce AI, external EHR integrations, a second FHIR server, or a public REST controller. All data remains synthetic.

---

# Branch

Create and use:

```text
feature/fhir-pagination
```

Do not work directly on `main`.

---

# Teaching Mode — Mandatory

Act as a senior instructor and implementation mentor.

Do not silently implement the task.

For every significant step, show:

1. What you are doing.
2. Why.
3. Which file is created or modified.
4. Raw FHIR HTTP request.
5. Equivalent HAPI FHIR Java operation.
6. Command executed.
7. Result.
8. FHIR concept learned.
9. Java/HAPI concept learned.

Before implementing Java code, first verify raw HTTP behavior against HAPI.

Do not guess HAPI 8.10.0 API signatures. Inspect the actual API when necessary.

If HAPI behaves differently from expectations, document the actual behavior.

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

Existing synthetic Patients:

```text
patient-001
patient-002
patient-003
```

Existing client:

```text
IGenericClient
```

Reuse the existing client and service patterns.

---

# Part 1 — Why Pagination Exists

Demonstrate the problem:

```http
GET /Patient
```

may match many Resources.

Explain why returning all results in one response is inefficient.

Conceptually:

```text
100,000 Patients
       ↓
Page 1
Page 2
Page 3
...
```

The client navigates between pages.

---

# Part 2 — `_count`

Demonstrate:

```http
GET /Patient?_count=2
```

Compare it with an unbounded search.

Inspect:

```text
Bundle.total
Bundle.entry.length
Bundle.link
```

Explain the difference between:

```text
total matches
```

and:

```text
resources returned in this page
```

Do not assume:

```text
Bundle.total == Bundle.entry.size
```

when pagination is active.

---

# Part 3 — Deterministic Dataset

The existing dataset has only three Patients.

Create a deterministic synthetic dataset sufficient to demonstrate pagination, approximately:

```text
10–15 Patients
```

Use predictable IDs:

```text
pagination-patient-001
pagination-patient-002
...
```

Use synthetic names and identifiers.

Do not use PHI.

Create a reusable seed mechanism consistent with the existing project.

Do not create hundreds of unnecessary files.

---

# Part 4 — Raw HTTP Pagination

Before Java implementation, demonstrate pagination directly against HAPI.

Example:

```http
GET /Patient?_count=3
```

Inspect:

```text
Bundle.type
Bundle.total
Bundle.entry
Bundle.link
```

Then follow:

```text
Bundle.link[relation=next]
```

using the exact URL returned by the server.

Do not manually invent the next URL.

Repeat until there is no `next`.

Document:

```text
page 1
page 2
page 3
...
```

and the logical IDs on each page.

---

# Part 5 — Bundle.link

Teach:

```json
"link": [
  {
    "relation": "self",
    "url": "..."
  },
  {
    "relation": "next",
    "url": "..."
  }
]
```

Explain:

```text
self
first
previous
next
last
```

Do not assume all relations are present on every page.

The server decides which links it returns.

---

# Part 6 — Server-Controlled Pagination

Explain that:

```text
_count
```

is a request for a page size, not a guarantee that the server will return exactly that many entries.

Demonstrate actual HAPI behavior.

The client should rely on:

```text
Bundle.entry
+
Bundle.link
```

rather than assuming a fixed page size.

---

# Part 7 — Searchset Semantics

Connect pagination to previous search work.

For example:

```http
GET /Patient?name=Maria&_count=2
```

still returns:

```text
Bundle.type = searchset
```

Conceptually:

```text
Search
  ↓
searchset Bundle
  ↓
page 1
  ↓
next
  ↓
page 2
```

Pagination changes the amount returned per page, not the meaning of `searchset`.

---

# Part 8 — HAPI FHIR Java

After raw HTTP verification, inspect HAPI 8.10.0.

Investigate the correct mechanisms for:

- setting `_count`;
- obtaining the first search Bundle;
- obtaining/following the next page;
- detecting whether another page exists.

Do not guess method names.

Reuse:

```java
IGenericClient
```

and the existing FHIR R4 context.

Document the actual HAPI API used.

---

# Part 9 — First Page

Add a method to `FhirService` that performs a paginated Patient search.

Conceptually:

```text
searchPatientsPage(...)
        ↓
Bundle
```

Preserve the FHIR `Bundle`.

Do not introduce a custom pagination DTO unless there is a compelling reason. The objective is to see the FHIR wire model.

---

# Part 10 — Follow Next Page

Add a method that follows the server-provided next link.

Conceptually:

```text
page 1
   ↓
Bundle.link[next]
   ↓
page 2
```

Do not reconstruct the URL manually.

If HAPI provides an official helper, use it.

Otherwise use the official HAPI mechanism for executing the server-provided URL.

Document the actual implementation.

---

# Part 11 — Retrieve All Pages

Add a method that iterates through all pages.

Conceptually:

```text
first page
    ↓
process
    ↓
next?
 ┌──┴──┐
yes   no
 ↓     ↓
next   done
 ↓
process
```

Avoid infinite loops.

Consider safeguards such as:

- missing next link;
- repeated next URL;
- maximum page count.

If safeguards are added, explain why.

Do not build a generic pagination framework for every Resource.

---

# Part 12 — Meaningful Search

Use a deterministic search such as:

```http
GET /Patient?name=Maria&_count=2
```

or another search that produces multiple pages.

If the dataset does not produce enough matches, create a dedicated synthetic dataset.

---

# Part 13 — Unit Tests

Add unit tests for:

- `_count` being applied;
- first page returned;
- `Bundle.total` vs `entry.size`;
- next-link detection;
- following next link;
- no next page;
- multiple pages;
- repeated-next protection;
- error propagation.

Tests should verify meaningful FHIR behavior, not merely Mockito invocation counts.

---

# Part 14 — Integration Tests

Use real HAPI.

Verify at minimum:

### First page

```http
GET /Patient?_count=3
```

Verify:

- `Bundle.type = searchset`;
- total is greater than first page size;
- entries are limited by the server's page behavior;
- a `next` link exists when more results remain.

### Second page

Follow the server-provided `next` URL.

Verify:

- another `searchset`;
- entries differ from page 1;
- URL comes from the server.

### All pages

Retrieve all pages.

Verify:

- expected synthetic resources are eventually present;
- no duplicate logical IDs;
- all expected IDs appear.

### Last page

Verify that no `next` link remains when the last page is reached.

---

# Part 15 — Resource Identity

Verify that pagination does not change:

```text
Resource.id
```

or:

```text
identifier
```

Connect with the earlier lesson:

```text
logical ID
≠
identifier
```

---

# Part 16 — Controlled `_include` Experiment

Only after the main pagination behavior works, optionally test:

```http
GET /Observation?patient=patient-001&_include=Observation:subject&_count=...
```

Explain that pagination applies to the search Bundle and that included Resources can affect the entries in that Bundle.

Do not build a generic include-pagination framework.

If behavior is ambiguous, document it and keep the implementation focused on Patient pagination.

---

# Part 17 — `_revinclude` Experiment

Do not implement a generic solution.

If useful, perform one small experiment with an existing `_revinclude` query.

The purpose is only to observe whether a paginated search Bundle can contain mixed Resources.

Document actual behavior.

---

# Part 18 — Important Limits

Explain that pagination is not the same as:

```text
$everything
```

and not the same as:

```text
Bulk Data $export
```

Do not implement either.

Also explain why clients should not assume:

```text
_count = exact number returned
```

because server-side limits may exist.

---

# Part 19 — Documentation

Create:

```text
docs/fhir/fhir-pagination.md
```

Explain:

1. Why pagination exists.
2. `_count`.
3. `Bundle.total`.
4. `Bundle.entry`.
5. `Bundle.link`.
6. `self`.
7. `next`.
8. `previous`.
9. `first`.
10. `last`.
11. Server-controlled page navigation.
12. First vs subsequent pages.
13. HAPI FHIR Java pagination.
14. Retrieving all pages.
15. Searchset pagination.
16. `_include` pagination if actually tested.
17. Logical ID preservation.
18. Why clients should not reconstruct next URLs.

Include raw HTTP examples.

---

# Part 20 — Update Existing Documentation

Update only what is necessary:

```text
docs/fhir/README.md
docs/roadmap.md
```

Do not rewrite unrelated documentation.

---

# Part 21 — Out of Scope

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
- subscriptions;
- Bulk Data `$export`;
- `$everything`;
- generic pagination framework;
- frontend pagination UI.

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
mvn verify -Pintegration
```

Also perform raw HTTP pagination experiments against:

```text
http://localhost:8080/fhir
```

Finally:

```bash
git status
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

scripts/fhir/
└── ...

docs/fhir/
└── fhir-pagination.md

docs/tasks/
└── 012-fhir-pagination.md
```

Do not rename existing working classes without a clear reason.

---

# Acceptance Criteria

- [ ] Work is on `feature/fhir-pagination`.
- [ ] Pagination problem is explained.
- [ ] `_count` is demonstrated.
- [ ] `Bundle.total` is understood.
- [ ] `Bundle.entry.size` is understood.
- [ ] `Bundle.link` is understood.
- [ ] `self` is understood.
- [ ] `next` is understood.
- [ ] `previous` is understood.
- [ ] `first` is understood.
- [ ] `last` is understood.
- [ ] Deterministic synthetic dataset is created.
- [ ] Raw HTTP first page is verified.
- [ ] Raw HTTP next page is verified.
- [ ] Server-provided next link is followed.
- [ ] HAPI 8.10.0 pagination API is verified rather than guessed.
- [ ] Java first-page search is implemented.
- [ ] Java next-page navigation is implemented.
- [ ] Multi-page retrieval is implemented.
- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] All expected synthetic resources can be retrieved across pages.
- [ ] No duplicate logical IDs are introduced.
- [ ] `_include` behavior is documented only if actually tested.
- [ ] No public REST controller is added.
- [ ] No external EHR is added.
- [ ] No AI is added.
- [ ] All data is synthetic.
- [ ] No unnecessary dependencies are introduced.
- [ ] No Git commit is created automatically.
- [ ] Final report contains complete step-by-step execution history.

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

## Pagination model

Show:

```text
Search
  ↓
Bundle/searchset
  ├── total
  ├── entry[]
  └── link[]
       ├── self
       ├── first
       ├── previous
       ├── next
       └── last
```

Explain which links actually appeared.

## Raw HTTP

Show:

```text
Page 1:
GET ...

Page 2:
GET <server-provided next URL>

Page 3:
...
```

Do not hide actual server behavior.

## HAPI Java

Show:

- first-page search;
- `_count`;
- next-page navigation;
- all-page iteration.

## Results

Show:

- total;
- page sizes;
- logical IDs per page;
- next/previous behavior.

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

- pagination;
- `_count`;
- `Bundle.total`;
- `Bundle.entry`;
- `Bundle.link`;
- `next`;
- server-controlled navigation;
- page size vs total matches;
- HAPI pagination API;
- retrieving all pages;
- logical ID preservation.

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
