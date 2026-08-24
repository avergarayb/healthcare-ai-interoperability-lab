# Task 006 — FHIR CRUD and Write Operations

## Objective

Move from FHIR read/search operations to **write operations** against the local HAPI FHIR R4 server.

The goal is to understand the FHIR lifecycle:

```text
CREATE → READ → UPDATE → DELETE
```

and how these operations map to HTTP and HAPI FHIR Java.

Use the existing synthetic clinical data and the existing `IGenericClient`.

This task is intentionally focused on the mechanics and semantics of FHIR writes. Do not move into transactions, conditional updates, batch/transaction Bundles, optimistic locking, or external EHRs yet.

---

## Branch

Create and use:

`feature/fhir-crud-write-operations`

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
4. The FHIR HTTP operation.
5. The equivalent HAPI FHIR Java operation.
6. The command executed.
7. The result.
8. The FHIR concept being learned.
9. The Java/HAPI FHIR concept being learned.

Before writing code, explain the HTTP semantics.

If there are multiple ways to perform an operation, explain the alternatives before choosing one.

If an error occurs:

1. Show the error.
2. Explain the likely cause.
3. Explain the chosen fix.
4. Apply the fix.
5. Re-run verification.
6. Explain why the fix works.

At the end provide:

- concise summary;
- complete step-by-step execution report;
- FHIR HTTP operations;
- HAPI FHIR Java equivalents;
- concepts learned;
- test results;
- Git status.

Do not provide only a final summary.

---

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
- References.
- `_include`.
- `_revinclude`.
- LOINC and SNOMED CT examples.
- Synthetic data.
- Existing error handling through `FhirClientException`.

Reuse the existing `IGenericClient`.

Do not create another FHIR client.

Do not create a public `@RestController`.

Do not introduce DTOs merely for this task.

---

# Part 1 — Understand FHIR CRUD

Teach the conceptual mapping first.

## Create

FHIR HTTP:

```http
POST /Patient
```

Meaning:

> Create a new Patient resource and let the server assign its logical ID.

HAPI FHIR:

```java
client.create()
    .resource(patient)
    .execute();
```

The response is an HTTP-created result containing the created Resource identity.

Important:

```text
POST /Patient
```

does not mean:

```text
Patient ID = whatever we put in the URL
```

The server assigns the logical ID.

---

## Read

FHIR HTTP:

```http
GET /Patient/{id}
```

Example:

```http
GET /Patient/patient-001
```

HAPI:

```java
client.read()
    .resource(Patient.class)
    .withId("patient-001")
    .execute();
```

Result:

```text
Patient
```

not a search Bundle.

---

## Update

FHIR HTTP:

```http
PUT /Patient/{id}
```

Example:

```http
PUT /Patient/patient-001
```

HAPI:

```java
client.update()
    .resource(patient)
    .execute();
```

Explain that the Resource's logical ID determines which resource is updated.

This is different from `POST`.

---

## Delete

FHIR HTTP:

```http
DELETE /Patient/{id}
```

Example:

```http
DELETE /Patient/patient-001
```

HAPI:

```java
client.delete()
    .resourceById("Patient", "patient-001")
    .execute();
```

Explain that the server removes the resource from normal retrieval.

Do not introduce versioning or history in this task.

---

# Part 2 — POST Create

Create a new synthetic Patient using Java.

Use a new ID assigned by HAPI.

Example data:

```text
Name: Ana Torres
Gender: female
Birth date: 1992-06-10
Identifier: MRN-10004
```

The Patient is synthetic.

Before implementation, explain:

```text
POST /Patient
```

versus:

```text
PUT /Patient/patient-004
```

Do not confuse server-assigned ID with client-assigned logical ID.

Implement a method such as:

```java
Patient createPatient(Patient patient)
```

Use the existing `IGenericClient`.

The method should return the created Patient or an appropriate result from which its logical ID can be obtained.

Do not create a controller.

---

# Part 3 — Inspect the Create Response

Explain that FHIR create normally returns a created resource identity and HTTP `201 Created`.

Inspect the HAPI response.

Teach:

```text
MethodOutcome
```

and how to retrieve the created resource ID.

Do not assume that the server will assign a particular ID.

The integration test must capture the actual returned logical ID.

Do not hardcode the generated ID.

---

# Part 4 — Read the Created Patient

After creation:

```http
GET /Patient/{generated-id}
```

Verify that the newly created Patient can be read.

The flow is:

```text
create()
   ↓
generated logical ID
   ↓
read()
   ↓
Patient
```

Explain why this is an important integration test.

---

# Part 5 — Update With PUT

Use the newly created Patient.

Change a field, for example:

```text
family name:
Torres
→
Torres-Gomez
```

Perform:

```http
PUT /Patient/{generated-id}
```

through HAPI:

```java
client.update()
    .resource(patient)
    .execute();
```

Then read it again and verify the change.

Explain:

```text
PUT
```

is an update of a resource at a known logical ID.

Do not introduce PATCH yet.

---

# Part 6 — PUT With a Client-Assigned ID

Demonstrate, separately, the FHIR behavior of:

```http
PUT /Patient/patient-write-001
```

using a synthetic Patient.

Explain that FHIR allows a client to create/update a resource at a known logical ID using PUT when the server permits it.

Use a distinct test resource:

```text
Patient/patient-write-001
MRN-10005
Carlos Mendoza
```

Use HAPI's update operation with the Patient carrying:

```text
id = patient-write-001
```

Verify that it can subsequently be read.

Explain the distinction:

```text
POST /Patient
```

→ server assigns ID.

```text
PUT /Patient/patient-write-001
```

→ client specifies logical ID.

This distinction is a major learning objective.

---

# Part 7 — Delete

Delete the dynamically created Patient from Part 2.

FHIR:

```http
DELETE /Patient/{generated-id}
```

HAPI:

```java
client.delete()
    .resourceById("Patient", generatedId)
    .execute();
```

Then verify that reading the deleted resource produces the appropriate not-found behavior.

Use the existing exception strategy.

Do not silently convert a 404 into `null`.

---

# Part 8 — CRUD Lifecycle

Document and demonstrate:

```text
CREATE
  POST /Patient
       ↓
server assigns ID
       ↓
READ
  GET /Patient/{id}
       ↓
UPDATE
  PUT /Patient/{id}
       ↓
READ
  GET /Patient/{id}
       ↓
DELETE
  DELETE /Patient/{id}
       ↓
READ
  GET /Patient/{id}
       ↓
404 / not found
```

Explain that this is a Resource lifecycle, not a SQL CRUD abstraction.

---

# Part 9 — Observation Create

Create a synthetic Observation linked to the existing:

```text
Patient/patient-001
```

Use a new logical ID assigned by POST.

Keep the existing terminology model:

```text
LOINC 85354-9
Blood pressure panel
```

and use a synthetic value.

The goal is to reinforce that References can be written into newly created resources.

Example:

```json
{
  "resourceType": "Observation",
  "status": "final",
  "code": {
    "coding": [
      {
        "system": "http://loinc.org",
        "code": "85354-9",
        "display": "Blood pressure panel"
      }
    ]
  },
  "subject": {
    "reference": "Patient/patient-001"
  }
}
```

If the R4 model requires fields, use the correct model and explain why.

Create it with:

```java
client.create()
    .resource(observation)
    .execute();
```

Verify that the returned logical ID exists.

Then read it.

Do not add a new resource type beyond Observation.

---

# Part 10 — Conditional Operations Are Out of Scope

Explicitly explain that this task does NOT implement:

```text
conditional create
conditional update
conditional delete
```

For example:

```http
POST /Patient?identifier=...
```

is not part of this task.

Do not implement these operations.

They will be covered later if the roadmap requires them.

---

# Part 11 — No PATCH Yet

Do not implement:

```http
PATCH /Patient/{id}
```

Explain briefly:

```text
PUT
```

replaces the representation at the logical ID.

FHIR PATCH changes selected elements.

We will study PATCH later.

---

# Part 12 — Unit Tests

Use mocks for `IGenericClient`.

Test at minimum:

- create Patient;
- extract created logical ID;
- update Patient;
- delete Patient;
- create Observation;
- error propagation.

Tests must not require Docker.

Keep mocks readable.

If HAPI's fluent API makes deep mocking awkward, explain the tradeoff rather than hiding it.

---

# Part 13 — Integration Tests

Use real HAPI FHIR.

Create an integration test that demonstrates a complete lifecycle.

At minimum:

### Patient lifecycle

1. Create Patient with POST.
2. Capture server-assigned ID.
3. Read Patient.
4. Modify Patient.
5. Update with PUT.
6. Read again.
7. Verify update.
8. Delete Patient.
9. Verify not found.

### Client-assigned ID

1. Create/update `Patient/patient-write-001` using PUT.
2. Read it.
3. Verify logical ID.

### Observation

1. Create Observation.
2. Capture generated ID.
3. Read Observation.
4. Verify `subject.reference = Patient/patient-001`.
5. Verify LOINC code.

Use deterministic synthetic data.

Clean up created resources when appropriate.

Do not let test data make subsequent test runs nondeterministic.

---

# Part 14 — HTTP Verification

Where useful, verify raw FHIR behavior with `curl.exe` or PowerShell.

Do not require the user to manually execute every request if integration tests already demonstrate the behavior.

Show concise examples:

```http
POST /Patient
```

```http
GET /Patient/{id}
```

```http
PUT /Patient/{id}
```

```http
DELETE /Patient/{id}
```

Explain the HTTP status semantics observed.

Do not paste unnecessarily large JSON responses.

---

# Part 15 — Documentation

Create:

`docs/fhir/fhir-crud-write-operations.md`

Teach:

1. FHIR Create.
2. FHIR Read.
3. FHIR Update.
4. FHIR Delete.
5. POST versus PUT.
6. Server-assigned logical IDs.
7. Client-assigned logical IDs.
8. `MethodOutcome`.
9. HTTP status semantics.
10. Resource lifecycle.
11. Reference preservation during writes.
12. Why PATCH is different from PUT.
13. Why conditional operations are different from normal CRUD.

Include a table:

| Operation | HTTP | HAPI FHIR | Result |
|---|---|---|---|
| Create | POST | `client.create()` | created resource identity |
| Read | GET | `client.read()` | Resource |
| Update | PUT | `client.update()` | updated resource identity |
| Delete | DELETE | `client.delete()` | delete outcome |

# Part 16 — Existing Documentation

Update relevant links in:

```text
docs/fhir/README.md
docs/roadmap.md
```

Do not rewrite unrelated documentation.

# Part 17 — No New Architecture

Do not create:

- CRUD controller;
- REST API;
- generic repository;
- generic persistence abstraction;
- generic FHIR graph engine;
- DTO layer;
- new microservice;
- API Gateway;
- database tables for FHIR resources.

HAPI FHIR remains the FHIR server.

Our Spring service remains the FHIR client/integration layer.

---

# Part 18 — Explicitly Out of Scope

Do NOT implement yet:

- PATCH;
- conditional create;
- conditional update;
- conditional delete;
- transaction Bundles;
- batch Bundles;
- optimistic locking;
- version history;
- `$validate`;
- `$validate-code`;
- terminology server;
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

Check Git:

```bash
git status
```

```bash
git diff --stat
```

No commit should be created by Cursor.

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
└── fhir-crud-write-operations.md
```

Do not rename existing working classes without a clear reason.

---

# Acceptance Criteria

- [ ] Work is on `feature/fhir-crud-write-operations`.
- [ ] Patient can be created with POST.
- [ ] Server-assigned logical ID is captured dynamically.
- [ ] Created Patient can be read.
- [ ] Created Patient can be updated with PUT.
- [ ] Updated Patient can be read and verified.
- [ ] Created Patient can be deleted.
- [ ] Deleted Patient produces appropriate not-found behavior.
- [ ] Client-assigned logical ID using PUT is demonstrated.
- [ ] Observation can be created with POST.
- [ ] Created Observation can be read.
- [ ] Observation preserves `subject.reference`.
- [ ] Observation preserves LOINC `85354-9`.
- [ ] Unit tests pass without Docker.
- [ ] Integration tests pass against local HAPI.
- [ ] Existing error handling is preserved.
- [ ] POST versus PUT is explicitly explained.
- [ ] `MethodOutcome` is explicitly explained.
- [ ] No PATCH is implemented.
- [ ] No conditional operations are implemented.
- [ ] No transaction/batch operations are implemented.
- [ ] No REST controller is added.
- [ ] No DTO is introduced without clear justification.
- [ ] No unrelated technology is introduced.
- [ ] Documentation explains HTTP and HAPI FHIR representations.
- [ ] All data is synthetic.
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

## CRUD lifecycle

Show:

```text
POST
 ↓
created ID
 ↓
GET
 ↓
PUT
 ↓
GET
 ↓
DELETE
 ↓
GET → not found
```

## FHIR operations implemented

For each:

```text
FHIR HTTP:
...

HAPI FHIR Java:
...

Result:
...
```

## ID behavior

Explicitly explain:

```text
POST /Patient
```

versus:

```text
PUT /Patient/{id}
```

and show the actual generated ID from the integration test.

## Synthetic data

List the synthetic Patient/Observation data used.

## Files created

List every new file.

## Files modified

List every modified file and explain each change.

## Dependencies

State whether dependencies were added.

If none were added, explicitly say so.

## Tests

For each command show:

- exact command;
- result;
- what was verified.

## Problems encountered

List each problem and resolution.

## Concepts learned

Explain:

- Create;
- Read;
- Update;
- Delete;
- POST;
- PUT;
- server-assigned logical ID;
- client-assigned logical ID;
- MethodOutcome;
- HTTP status semantics;
- Reference preservation;
- PUT versus PATCH.

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
