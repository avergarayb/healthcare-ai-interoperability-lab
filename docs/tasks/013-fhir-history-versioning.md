# Task 013 — FHIR History and Resource Versioning

## Objective

Learn how FHIR keeps the history of Resources over time.

Until now we have learned how to:

- read a Resource;
- search Resources;
- create, update and delete Resources;
- use conditional create;
- use transactions and batches;
- paginate search results.

The next important concept is that a FHIR Resource is not necessarily static.

A Resource can have multiple versions:

```text
Patient/patient-001
    │
    ├── version 1
    ├── version 2
    ├── version 3
    └── ...
```

FHIR exposes this through the history interaction.

This task teaches:

- resource versioning;
- `meta.versionId`;
- `meta.lastUpdated`;
- `ETag`;
- `Last-Modified`;
- `_history`;
- instance history;
- system/type history;
- version-specific reads;
- `Bundle.type = history`;
- `history` entries;
- `entry.request`;
- `entry.response`;
- update vs new version;
- optimistic concurrency with `If-Match`;
- HAPI FHIR history APIs;
- differences between logical ID and version ID.

Do not introduce AI.

Do not introduce external EHR integrations.

Do not introduce a public REST controller.

Do not introduce a second FHIR server.

All data must remain synthetic.

---

# Branch

Create and use:

```text
feature/fhir-history-versioning
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

Do not guess HAPI 8.10.0 API signatures. Inspect the actual API when necessary.

If HAPI behaves differently from expectations, document the actual behavior.

Do not silently replace observed behavior with an assumed specification behavior.

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

Existing synthetic Resources include:

```text
Patient/patient-001
Patient/patient-002
Patient/patient-003
Observation/obs-001
Condition/condition-001
```

Reuse the existing client and service patterns.

---

# Part 1 — Why History Exists

Start with the basic problem.

Suppose:

```text
Patient/patient-001
```

is created today.

Later:

```text
name changes
phone changes
address changes
```

The current Resource represents the current state.

But an interoperability system may also need to know:

```text
What did this Patient look like yesterday?
What changed?
When did it change?
Which version was returned?
```

FHIR provides history for this purpose.

Conceptually:

```text
Patient/patient-001
       │
       ├── v1
       ├── v2
       └── v3  ← current
```

Explain that:

```text
logical ID
```

identifies the Resource across versions, while:

```text
version ID
```

identifies a particular version.

---

# Part 2 — `meta.versionId`

Inspect a Resource:

```http
GET /Patient/patient-001
```

Look at:

```json
"meta": {
  "versionId": "...",
  "lastUpdated": "..."
}
```

Explain:

```text
Patient/patient-001
        │
        └── meta.versionId = specific version
```

The logical ID remains:

```text
patient-001
```

while the version can change:

```text
1
2
3
```

Do not assume version IDs are globally meaningful.

They are associated with the Resource's version history on that server.

---

# Part 3 — HTTP Headers

Inspect the response headers from HAPI.

Look for:

```text
ETag
Last-Modified
```

Explain their relationship to:

```text
meta.versionId
meta.lastUpdated
```

Do not assume that HTTP headers and FHIR metadata are interchangeable.

Document the actual HAPI response.

---

# Part 4 — Create Multiple Versions

Use a dedicated synthetic Patient for this task.

For example:

```text
history-patient-001
```

Create it.

Then update it at least twice.

Conceptually:

```text
POST /Patient
       ↓
version 1

PUT /Patient/history-patient-001
       ↓
version 2

PUT /Patient/history-patient-001
       ↓
version 3
```

After each operation inspect:

```text
id
meta.versionId
meta.lastUpdated
```

Verify that:

```text
id
```

remains stable while:

```text
meta.versionId
```

changes.

Use synthetic data only.

---

# Part 5 — Instance History

First demonstrate the raw FHIR HTTP operation:

```http
GET /Patient/history-patient-001/_history
```

Inspect:

```text
Bundle.type
Bundle.entry
```

Explain that the result is a:

```text
Bundle
type = history
```

This is different from:

```text
searchset
transaction-response
batch-response
```

The Bundle contains historical entries.

---

# Part 6 — History Entry Structure

Inspect one history Bundle entry.

Explain the difference between:

```text
entry.resource
entry.request
entry.response
```

For history, the entry can describe what happened to a Resource.

Inspect:

```text
response.status
response.location
response.etag
response.lastModified
```

and the Resource when present.

Build a diagram:

```text
Bundle
 type = history
    │
    └── entry[]
          ├── resource
          ├── request
          └── response
```

Document which fields HAPI actually returns.

---

# Part 7 — Version-Specific Read

FHIR supports addressing a specific version.

Demonstrate:

```http
GET /Patient/history-patient-001/_history/{versionId}
```

using an actual version ID obtained from HAPI.

Verify:

```text
HTTP 200
Patient
same logical ID
specific meta.versionId
historical field values
```

Do not hardcode a version number unless the server actually generated that version.

The test must discover the version IDs from the server response.

---

# Part 8 — Current Read vs Historical Read

Compare:

```http
GET /Patient/history-patient-001
```

with:

```http
GET /Patient/history-patient-001/_history/{versionId}
```

Explain:

```text
current read
    ↓
latest version

version-specific read
    ↓
requested historical version
```

This is one of the most important concepts of the task.

---

# Part 9 — HAPI FHIR Java API

After HTTP verification, inspect the HAPI 8.10.0 APIs.

Investigate the correct methods for:

- instance history;
- version-specific read;
- obtaining a historical Bundle;
- extracting historical Resources;
- reading version metadata.

Use actual HAPI APIs.

Do not guess method names.

Use `javap` or inspect the dependency classes when necessary.

---

# Part 10 — Implement Instance History

Add methods to `FhirService` for:

```text
getPatientHistory(patientId)
```

and:

```text
readPatientVersion(patientId, versionId)
```

Preserve the FHIR `Bundle` for history.

Do not create a custom history DTO.

The purpose is to learn the native FHIR model.

---

# Part 11 — History and CRUD

Connect history to the CRUD task.

Demonstrate:

```text
CREATE
   ↓
version 1

UPDATE
   ↓
version 2

UPDATE
   ↓
version 3
```

Then:

```http
GET /Patient/{id}/_history
```

should expose the sequence of changes supported by the server.

Explain that an update is not simply:

```text
overwrite and forget
```

in a FHIR server that maintains history.

---

# Part 12 — Delete and History

Perform a controlled synthetic experiment.

Create a dedicated Patient.

Then delete it:

```http
DELETE /Patient/history-delete-001
```

Inspect:

```http
GET /Patient/history-delete-001/_history
```

Determine how HAPI represents the delete in history.

Do not assume the Resource will be present as a normal current Resource.

Inspect:

```text
entry.response.status
entry.resource
```

and document actual behavior.

Then verify the current read behavior:

```http
GET /Patient/history-delete-001
```

Document whether HAPI returns 404 and how history remains available.

If HAPI's behavior differs from expectations, document it.

---

# Part 13 — Optimistic Concurrency

Connect history with the previous `If-Match` experiment.

Read the current Patient and obtain its version.

Conceptually:

```text
current version = 3
```

Then perform:

```http
PUT /Patient/history-patient-001
If-Match: W/"3"
```

This should allow the update when the version matches.

Then try:

```http
PUT /Patient/history-patient-001
If-Match: W/"999999"
```

Observe the result.

Expected conceptual behavior:

```text
correct version
    ↓
update accepted

wrong version
    ↓
409 Conflict
```

Use the actual HAPI behavior as the source of truth.

Explain why this matters when multiple systems update the same Patient.

---

# Part 14 — History vs Search

Explicitly compare:

```http
GET /Patient?name=Maria
```

with:

```http
GET /Patient/patient-001/_history
```

First:

```text
Bundle.type = searchset
```

Second:

```text
Bundle.type = history
```

Explain:

```text
searchset
    = matching Resources

history
    = versions/events for a Resource
```

This distinction must be documented.

---

# Part 15 — System / Type History Investigation

Investigate whether the local HAPI server supports:

```http
GET /Patient/_history
```

and:

```http
GET /_history
```

Do not implement broad history APIs unless the behavior is useful and clean.

The goal is to learn the scope levels:

```text
instance history
type history
system history
```

Document:

- which are supported;
- what Bundle is returned;
- whether pagination applies;
- any observed limitations.

Do not invent support.

---

# Part 16 — Pagination Connection

Connect Task 013 with Task 012.

History itself may contain many entries.

Investigate whether:

```text
Bundle.type = history
```

can contain:

```text
Bundle.link.next
```

when enough history exists.

If supported, demonstrate a small paginated history.

Explain that pagination is not limited to `searchset`.

Do not build another generic pagination framework.

Reuse the concepts learned in Task 012.

---

# Part 17 — Unit Tests

Add unit tests for:

- current Patient read;
- history Bundle;
- `Bundle.type = history`;
- version-specific read;
- extracting version IDs;
- current vs historical version;
- delete-history response;
- optimistic concurrency;
- error propagation.

Mock only the HAPI interactions needed by the service.

Tests should verify meaningful FHIR behavior.

---

# Part 18 — Integration Tests

Use real HAPI.

Verify at minimum:

### Version creation

Create one Patient and update it twice.

Verify:

```text
same logical ID
different version IDs
```

### Instance history

Verify:

```text
GET /Patient/{id}/_history
```

returns:

```text
Bundle.type = history
```

and contains the expected historical entries.

### Version-specific read

Obtain a historical version ID dynamically.

Read it.

Verify that the historical content corresponds to that version.

### Delete

Create and delete a synthetic Patient.

Verify the current read and history behavior.

### If-Match

Verify:

```text
correct version → accepted
incorrect version → rejected
```

### Pagination

If HAPI generates enough history and exposes pagination, verify the next link.

---

# Part 19 — Synthetic Data

Create dedicated synthetic data for this task.

Suggested IDs:

```text
history-patient-001
history-delete-001
```

Do not reuse a production-like Patient merely to create history.

This avoids test pollution and makes integration tests reproducible.

---

# Part 20 — Documentation

Create:

```text
docs/fhir/fhir-history-and-versioning.md
```

Explain:

1. Why FHIR history exists.
2. Logical ID vs version ID.
3. `meta.versionId`.
4. `meta.lastUpdated`.
5. ETag.
6. Last-Modified.
7. Instance history.
8. `Bundle.type = history`.
9. History `entry[]`.
10. Version-specific reads.
11. Current vs historical reads.
12. Delete history.
13. `If-Match`.
14. Optimistic concurrency.
15. Searchset vs history.
16. Type/system history if verified.
17. Pagination of history if verified.
18. HAPI FHIR Java APIs.

Include raw HTTP examples.

---

# Part 21 — Update Existing Documentation

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
- subscriptions;
- Bulk Data `$export`;
- `$everything`;
- audit logging platform;
- generic event-sourcing framework;
- generic history framework for every Resource.

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

Also perform raw HTTP verification.

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
- no unnecessary dependencies.

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
└── fhir-history-and-versioning.md

docs/tasks/
└── 013-fhir-history-versioning.md
```

Do not rename existing working classes without a clear reason.

---

# Acceptance Criteria

- [ ] Work is on `feature/fhir-history-versioning`.
- [ ] History problem is explained.
- [ ] Logical ID vs version ID is demonstrated.
- [ ] `meta.versionId` is observed.
- [ ] `meta.lastUpdated` is observed.
- [ ] ETag is observed if HAPI returns it.
- [ ] Last-Modified is observed if HAPI returns it.
- [ ] Multiple synthetic versions are created.
- [ ] Instance history is retrieved.
- [ ] `Bundle.type = history` is verified.
- [ ] History entries are inspected.
- [ ] Version-specific read is verified.
- [ ] Current vs historical Resource is demonstrated.
- [ ] Delete behavior is experimentally verified.
- [ ] `If-Match` optimistic concurrency is experimentally verified.
- [ ] Searchset vs history is documented.
- [ ] Type/system history is investigated without assuming support.
- [ ] History pagination is investigated.
- [ ] HAPI 8.10.0 APIs are verified rather than guessed.
- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] All data is synthetic.
- [ ] No public REST controller is added.
- [ ] No external EHR is added.
- [ ] No AI is added.
- [ ] No unnecessary dependency is introduced.
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

## Version model

Show:

```text
Patient/history-patient-001
        │
        ├── version 1
        ├── version 2
        └── version 3
```

Explain logical ID vs version ID.

## History model

Show:

```text
GET /Patient/{id}/_history
              ↓
        Bundle/history
              ↓
           entry[]
              ├── resource
              ├── request
              └── response
```

Explain the actual fields returned by HAPI.

## Raw HTTP

Show:

- create;
- update;
- current read;
- instance history;
- version-specific read;
- delete;
- `If-Match`.

Use actual generated version IDs.

## HAPI Java

Show:

- history API;
- version-specific read;
- concurrency mechanism;
- relevant Bundle handling.

## Results

Show:

- logical ID;
- version IDs;
- version count;
- history entry statuses;
- current version;
- historical version;
- concurrency result.

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

- FHIR history;
- versioning;
- logical ID;
- version ID;
- `meta.versionId`;
- `meta.lastUpdated`;
- ETag;
- `_history`;
- `Bundle.type = history`;
- version-specific read;
- delete history;
- `If-Match`;
- optimistic concurrency;
- searchset vs history;
- HAPI history APIs.

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
