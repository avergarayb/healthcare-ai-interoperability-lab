# Task 011 — FHIR Bundles, Batch and Transaction

## Objective

Learn how FHIR uses `Bundle` not only as the result of a search, but also to package multiple FHIR Resources and HTTP operations into a single interaction.

Until now:

```text
Bundle
→ search result
```

Now:

```text
Bundle
→ collection of Resources
→ optionally a set of HTTP operations
→ can be sent to a FHIR server
```

Main concepts:

- Bundle types
- `searchset` vs `transaction` vs `batch`
- `Bundle.entry`
- `entry.resource`
- `entry.request`
- `entry.response`
- transaction atomicity
- batch independence
- references between Resources
- transaction responses
- conditional create, if supported
- FHIR HTTP vs HAPI FHIR Java

Do not create a public REST controller, external EHR integration, second FHIR server, AI component, or custom transaction engine. All data remains synthetic.

---

# Branch

Create and use:

```text
feature/fhir-bundles-transactions
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
4. The raw FHIR HTTP operation.
5. The equivalent HAPI FHIR Java operation.
6. The command executed.
7. The result.
8. The FHIR concept being learned.
9. The Java/HAPI FHIR concept being learned.

Before implementing Java code, first verify the raw HTTP behavior against HAPI.

Do not guess HAPI 8.10.0 API signatures. Inspect the actual API when necessary.

If HAPI behaves differently from expectations, document the actual behavior rather than hiding it.

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

Existing synthetic resources:

```text
Patient/patient-001
MRN-10001
Maria Garcia

Observation/obs-001
subject → Patient/patient-001
LOINC 85354-9
130 mmHg

Condition/condition-001
subject → Patient/patient-001
SNOMED CT 38341003
clinicalStatus = active
```

Reuse the existing `IGenericClient`.

---

# Part 1 — What Is a Bundle?

We already used Bundle for search:

```http
GET /Patient?name=Maria
```

which returns:

```text
Bundle
  type = searchset
  entry[]
      └── Patient
```

Now explain that `Bundle` is a FHIR Resource with several possible purposes.

At minimum explain:

```text
searchset
transaction
batch
collection
document
message
history
```

Do not implement every Bundle type.

Focus this task on:

```text
searchset
transaction
batch
```

---

# Part 2 — Searchset vs Transaction vs Batch

Create a clear comparison.

## Searchset

Produced by a search:

```http
GET /Patient?name=Maria
```

```text
Bundle.type = searchset
```

Its entries contain matching Resources.

## Transaction

A client sends a Bundle containing multiple operations that must be processed as one atomic interaction.

Conceptually:

```text
Bundle
type = transaction

entry[]
  ├── POST Patient
  ├── POST Observation
  └── POST Condition
```

Explain:

```text
all succeed
    OR
none are committed
```

## Batch

A client sends multiple operations in one Bundle, but they are independent.

Conceptually:

```text
Bundle
type = batch

entry[]
  ├── POST Patient
  ├── POST Observation
  └── GET Patient/...
```

Explain the difference from transaction and verify actual HAPI behavior.

---

# Part 3 — Bundle.entry

Teach:

```text
Bundle
 └── entry[]
       ├── resource
       └── request
```

For transaction/batch:

```json
"request": {
  "method": "POST",
  "url": "Patient"
}
```

or:

```json
"request": {
  "method": "PUT",
  "url": "Patient/patient-001"
}
```

Explain:

```text
entry.resource
→ Resource payload

entry.request
→ HTTP operation to perform
```

---

# Part 4 — Raw HTTP First

Before Java implementation, construct a transaction Bundle manually.

Use synthetic Resources.

A good first example:

```text
Patient
Observation
```

where:

```text
Observation.subject
→ Patient reference
```

Submit:

```http
POST /fhir
Content-Type: application/fhir+json
```

with:

```json
{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [...]
}
```

Verify the actual response.

Do not assume the response status before testing.

---

# Part 5 — Transaction Atomicity

Design an experiment demonstrating why transaction differs from independent writes.

First create a valid transaction.

Then create an intentionally invalid transaction.

Example:

```text
entry 1 → valid Patient
entry 2 → invalid operation/resource
```

Observe what happens.

The objective is to demonstrate:

```text
transaction
→ atomic
```

If HAPI's exact behavior differs from the expected conceptual behavior, document the actual result.

Do not fake an atomicity test.

---

# Part 6 — Batch

Create a separate batch Bundle.

Include multiple independent operations.

Verify actual HAPI behavior and compare it with transaction.

The learner must understand:

```text
transaction
→ all-or-nothing

batch
→ independent operations
```

---

# Part 7 — Transaction Response

Explain that the server returns a Bundle response for a successful transaction/batch interaction.

Inspect:

```text
Bundle.type
Bundle.entry[]
Bundle.entry.response
```

Where present, inspect:

```text
entry.response.status
entry.response.location
entry.response.etag
```

Do not assume every field is present. Show the actual HAPI response.

---

# Part 8 — References Inside a Transaction

Connect this task with the previous Reference work.

Conceptual graph:

```text
Patient
   ↑
   │ subject
   │
Observation
```

Discuss the difference between:

```text
reference to an existing Resource
```

and:

```text
reference to a Resource being created in the same transaction
```

If temporary references are used, investigate FHIR transaction reference behavior and demonstrate it only if HAPI supports it cleanly.

Do not invent a custom mechanism.

---

# Part 9 — Conditional Create / Update

Introduce only after basic transaction behavior works.

Explain:

```text
POST /Patient
```

versus conditional create, conceptually:

```text
POST Patient
If-None-Exist: identifier=...
```

The goal is to understand how an integration can avoid blindly creating duplicates.

Only implement it if HAPI R4 local supports it cleanly.

If support is unclear, document the HTTP concept and limitation rather than expanding scope.

---

# Part 10 — HAPI FHIR Java

After raw HTTP verification, implement Java methods in:

```text
FhirService
```

Use the existing:

```java
IGenericClient
```

Investigate the appropriate HAPI API for transaction/batch execution.

Do not guess.

Conceptually the API will involve:

```java
Bundle
```

and a client interaction that sends the Bundle to the FHIR server.

Verify the actual HAPI 8.10.0 API.

Do not create another HTTP client.

---

# Part 11 — Bundle Construction in Java

Create Bundles using the R4 model.

Conceptually:

```java
Bundle bundle = new Bundle();
bundle.setType(Bundle.BundleType.TRANSACTION);
```

Then construct entries containing both:

```text
entry.resource
entry.request
```

Verify the exact HAPI API before implementation.

Demonstrate:

```text
FHIR JSON
        ↕
HAPI Bundle
        ↕
Java Resource
```

---

# Part 12 — Transaction Result

Create service methods that return the server's transaction/batch response.

Do not reduce the result to:

```text
boolean success
```

Preserve useful response information such as:

```text
response status
location
resource
```

when available.

Use existing exception handling.

---

# Part 13 — Unit Tests

Add unit tests using mocks.

Test at minimum:

- transaction Bundle construction;
- batch Bundle construction;
- correct `Bundle.type`;
- correct `entry.request.method`;
- correct `entry.request.url`;
- Resources attached to entries;
- server response parsing;
- error propagation.

Do not mock every FHIR detail into meaningless tests.

---

# Part 14 — Integration Tests

Use real HAPI.

Verify:

### Transaction

Create synthetic:

```text
Patient
Observation
```

in one transaction.

Verify both can be read back.

### Transaction failure

Submit a transaction containing an intentionally invalid operation.

Verify actual server behavior.

### Batch

Submit multiple independent operations.

Verify actual response behavior.

### Transaction response

Inspect:

```text
Bundle.type
entry.response.status
```

and Resource/location information where present.

### Reference

Verify the resulting Observation points to the intended Patient.

---

# Part 15 — Read Back the Resources

After transaction/batch execution, use the existing read methods:

```text
GET /Patient/{id}
GET /Observation/{id}
```

Connect:

```text
write via transaction
       ↓
read via existing client
       ↓
verify persistence
```

---

# Part 16 — Searchset vs Transaction Response

Make the distinction explicit.

Search:

```http
GET /Patient?name=Maria
```

returns:

```text
Bundle.type = searchset
```

Transaction:

```http
POST /fhir
```

with:

```text
Bundle.type = transaction
```

returns a response Bundle whose entries contain response information.

Therefore:

```text
Bundle
≠
only search results
```

This is one of the main learning objectives.

---

# Part 17 — Documentation

Create:

```text
docs/fhir/fhir-bundles-transactions.md
```

Teach:

1. Bundle.
2. searchset.
3. transaction.
4. batch.
5. Bundle.entry.
6. entry.resource.
7. entry.request.
8. entry.response.
9. transaction atomicity.
10. batch independence.
11. references inside transactions.
12. conditional create if implemented.
13. HAPI FHIR Java representation.
14. FHIR HTTP representation.

Include a comparison table and concise JSON examples.

---

# Part 18 — Update Existing Documentation

Update only what is necessary:

```text
docs/fhir/README.md
docs/fhir/fhir-crud-write-operations.md
docs/roadmap.md
```

Do not rewrite unrelated documentation.

---

# Part 19 — Out of Scope

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
- message broker integration;
- FHIR subscriptions;
- Bulk Data `$export`;
- full document Bundles;
- clinical document generation;
- ImplementationGuide;
- national profiles.

The goal is only to understand and implement Bundle transaction/batch interactions.

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
└── fhir-bundles-transactions.md

docs/tasks/
└── 011-fhir-bundles-transactions.md
```

Do not rename existing working classes without a clear reason.

---

# Acceptance Criteria

- [ ] Work is on `feature/fhir-bundles-transactions`.
- [ ] Bundle is explained as a general FHIR Resource.
- [ ] `searchset` is explained.
- [ ] `transaction` is explained.
- [ ] `batch` is explained.
- [ ] `Bundle.entry.resource` is understood.
- [ ] `Bundle.entry.request` is understood.
- [ ] `Bundle.entry.response` is understood.
- [ ] Raw transaction HTTP is verified against HAPI.
- [ ] A successful transaction is demonstrated.
- [ ] Transaction atomicity is tested.
- [ ] Raw batch HTTP is verified against HAPI.
- [ ] Batch behavior is demonstrated.
- [ ] Transaction response is inspected.
- [ ] References between Resources are demonstrated.
- [ ] Conditional create is demonstrated only if supported cleanly.
- [ ] HAPI FHIR 8.10.0 Java API is verified rather than guessed.
- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Resources created through transaction/batch can be read back.
- [ ] Searchset vs transaction response is clearly documented.
- [ ] No public REST controller is added.
- [ ] No external FHIR server is added.
- [ ] No external EHR is added.
- [ ] No AI is added.
- [ ] All clinical data is synthetic.
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

## Bundle model

Show:

```text
Bundle
 └── entry[]
       ├── resource
       ├── request
       └── response
```

Explain which fields are relevant for:

```text
searchset
transaction
batch
```

## Transaction

Show:

```text
FHIR HTTP:
...

Bundle:
...

Result:
...
```

## Batch

Show:

```text
FHIR HTTP:
...

Bundle:
...

Result:
...
```

## Atomicity

Show the successful and failing transaction experiments.

Explain the actual HAPI behavior.

## References

Explain how Resources relate inside the Bundle.

## Transaction response

Explain actual `entry.response` values returned by HAPI.

## Conditional create

If implemented, explain the request and result.

If not implemented, explain why.

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

## Raw HTTP verification

Show selected requests and concise results.

## Problems encountered

List each problem and resolution.

## Concepts learned

Explain:

- Bundle;
- searchset;
- transaction;
- batch;
- entry.resource;
- entry.request;
- entry.response;
- atomicity;
- references inside transactions;
- conditional create;
- transaction vs batch;
- search Bundle vs transaction response.

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
