# Task 003 — FHIR Search

## Objective

Implement the first real FHIR resource interactions in `fhir-integration-service`.

The service must learn and demonstrate:

1. FHIR `read` of a `Patient` by logical ID.
2. FHIR `search` of `Patient` resources using a search parameter.
3. FHIR `Bundle` as the response to a search.
4. Basic search result handling in Java using HAPI FHIR.
5. The relationship between the FHIR REST API and the HAPI FHIR Java client.

This is an educational implementation. Keep the scope small and understandable.

## Branch

Create and use:

`feature/fhir-search`

Do not work directly on `main`.

## Teaching Mode — Mandatory

Act as a senior instructor and implementation mentor.

Do not silently implement the task.

Execute the work step by step and explain the work as you proceed, as if you were teaching the developer.

Before implementing each FHIR operation, explain the FHIR/HTTP operation first and then show how HAPI FHIR represents it in Java.

For every significant step, show:

1. What you are doing.
2. Why you are doing it.
3. Which file is being created or modified.
4. The relevant code or configuration change.
5. The command executed.
6. The command result.
7. The FHIR/Java/software-engineering concept being learned.

Do not provide only a final summary.

When introducing a new dependency, explain:
- what it is;
- why it is needed;
- what responsibility it has;
- why it belongs in this service.

When introducing a new HAPI FHIR API/class, explain its purpose before using it.

If an error occurs:
1. Show the error.
2. Explain the likely cause.
3. Explain the chosen fix.
4. Apply the fix.
5. Re-run verification.
6. Explain why the fix works.

At the end provide both:
- a concise final summary; and
- a complete step-by-step execution report.

## Context

Repository:

`healthcare-ai-interoperability-lab`

Current integration service:

`services/fhir-integration-service`

Technology:

- Java 21
- Spring Boot 3.5.x
- Maven
- HAPI FHIR 8.10.0
- FHIR R4

Local FHIR server:

`http://localhost:8080/fhir`

Local FHIR version:

FHIR R4 / `4.0.1`

The previous task created an R4 HAPI FHIR client and a service capable of retrieving the server `CapabilityStatement` from `/metadata`.

The current application is a FHIR integration client.

HAPI FHIR is the local FHIR server.

## Important Learning Rule

For every operation implemented in this task, first show the conceptual REST request.

Example:

```http
GET /Patient/patient-001
```

Then explain the equivalent HAPI FHIR Java operation.

For search:

```http
GET /Patient?name=Maria
```

Then show the HAPI FHIR Java equivalent.

The developer must understand both representations.

## Architecture

For this task:

```text
FHIR Integration Service
        |
        | HAPI FHIR Client
        v
Local HAPI FHIR Server
        |
        +---- Patient
        |
        +---- Bundle
```

Do not create another microservice.

Do not introduce an API Gateway.

Do not add a public REST controller yet unless explicitly required by this task.

The service layer should remain the primary integration boundary.

## Phase 1 — Synthetic FHIR Data

Use only synthetic/non-sensitive data.

Create a small deterministic dataset in the local HAPI FHIR server so the search behavior is reproducible.

Create at least three `Patient` resources.

Suggested dataset:

### Patient 1

```text
logical id: patient-001
identifier: MRN-10001
family name: Garcia
given name: Maria
gender: female
birthDate: 1985-04-12
```

### Patient 2

```text
logical id: patient-002
identifier: MRN-10002
family name: Garcia
given name: Juan
gender: male
birthDate: 1980-08-20
```

### Patient 3

```text
logical id: patient-003
identifier: MRN-10003
family name: Lopez
given name: Maria
gender: female
birthDate: 1990-02-15
```

These are synthetic examples only.

Before creating the data, explain why deterministic test data is useful.

Do not use real patient data.

## Important FHIR Concept — Logical ID vs Identifier

Use the dataset to explicitly teach:

```text
Patient logical ID:
patient-001
```

versus:

```text
Patient.identifier:
MRN-10001
```

Explain that:

```http
GET /Patient/patient-001
```

uses the logical resource ID.

Whereas:

```http
GET /Patient?identifier=MRN-10001
```

uses a search parameter against the `identifier` element.

Do not incorrectly treat them as interchangeable.

## Part 1 — Read Patient by Logical ID

### FHIR operation

First explain:

```http
GET /Patient/patient-001
```

Expected response:

```text
Patient resource
```

not a Bundle.

### HAPI FHIR

Implement the equivalent using the existing `IGenericClient`.

Conceptually:

```java
client
    .read()
    .resource(Patient.class)
    .withId("patient-001")
    .execute();
```

Use appropriate application/service structure.

Do not duplicate FHIR client creation.

Reuse the existing FHIR client bean/service.

### Expected result

Return/handle:

```text
Patient
```

and verify at least:

- logical ID;
- family name;
- given name.

## Part 2 — Search Patient by Name

### FHIR operation

First explain:

```http
GET /Patient?name=Maria
```

Explain:

- `Patient` is the resource type.
- `name` is a FHIR search parameter.
- the response is a `Bundle`.
- each matching patient is an entry in the Bundle.

### HAPI FHIR

Implement the equivalent using HAPI FHIR.

Conceptually:

```java
client
    .search()
    .forResource(Patient.class)
    .where(Patient.NAME.matches().value("Maria"))
    .returnBundle(Bundle.class)
    .execute();
```

Do not copy this blindly. Explain each part.

### Expected result

The synthetic dataset should produce:

```text
Maria Garcia
Maria Lopez
```

The search should not return Juan Garcia.

## Part 3 — Search Patient by Identifier

### FHIR operation

Explain:

```http
GET /Patient?identifier=MRN-10001
```

Then implement the equivalent HAPI FHIR search.

Expected result:

- Bundle
- one matching Patient
- `patient-001`

This is an important exercise because it reinforces the difference between:

```text
logical ID
```

and:

```text
business/clinical identifier
```

## Part 4 — Bundle

Teach explicitly that search responses are normally represented by:

```text
Bundle
```

Inspect:

- Bundle type
- total
- entries
- resource inside each entry

The implementation should demonstrate how to access matching `Patient` resources from the Bundle.

Do not build a generic Bundle framework yet.

Keep the example specific to Patient.

## Part 5 — Search Result Mapping

For this task, create a small application-level representation only if it improves clarity.

If a DTO is introduced, explain why it is different from a FHIR `Patient` resource.

Do not create a broad "normalized healthcare model" yet.

Do not prematurely map every FHIR field.

A simple result representation may include:

```text
id
familyName
givenNames
gender
birthDate
```

But if returning the FHIR resource directly inside the service layer is clearer for this educational stage, that is acceptable.

Explain the decision.

## Part 6 — Tests

Separate unit tests from integration tests.

### Unit tests

Mock `IGenericClient`.

Test at least:

- read Patient by ID;
- search Patient by name;
- search Patient by identifier;
- basic handling of Bundle results;
- connection/server error propagation where relevant.

Do not make unit tests depend on HAPI Docker.

### Integration tests

Use the real local HAPI FHIR server.

Verify:

1. `patient-001` can be read.
2. `name=Maria` returns two synthetic patients.
3. `identifier=MRN-10001` returns exactly one patient.
4. The response is a Bundle for searches.
5. The returned resources have the expected IDs/names.

Use deterministic assertions.

Do not rely on result ordering unless the FHIR query explicitly guarantees it.

If necessary, collect IDs into a set before asserting.

## Part 7 — Search Parameter Explanation

Document the search parameters used:

```text
name
identifier
```

Explain that search parameters are part of the FHIR search mechanism and are not arbitrary Java method parameters.

Do not implement custom search syntax.

## Part 8 — Error Handling

Keep the existing `FhirClientException` strategy from Task 002.

Do not redesign error handling.

If a read or search fails because of an HTTP/FHIR server error, preserve the original cause.

Do not silently return null.

## Part 9 — Documentation

Create/update:

`docs/fhir/fhir-search.md`

The document must explain:

### Read

```http
GET /Patient/{id}
```

### Search

```http
GET /Patient?name=Maria
GET /Patient?identifier=MRN-10001
```

### Response differences

```text
Read → Patient
Search → Bundle<Patient>
```

### Logical ID vs Identifier

Explain with the synthetic examples.

### HAPI FHIR equivalents

Show the Java client operations.

### Bundle

Explain:

```text
Bundle
 └── entry[]
      └── resource
           └── Patient
```

Write this as study material, not merely API documentation.

## Data Creation Strategy

The synthetic dataset can be created using one of these approaches:

1. Postman/manual HTTP requests documented in the repository.
2. A reproducible script.
3. A test setup mechanism.

Prefer the simplest reproducible approach.

Do not add a database migration framework.

Do not modify HAPI FHIR internals.

If a script is created, place it under an appropriate existing project directory and explain why.

## No REST Controller

Do NOT create:

```java
@RestController
```

for this task.

We are still building the integration layer internally.

Later we may expose an API that other applications can consume, but that is a separate architectural decision.

## No New Dependencies Unless Necessary

Do not add dependencies unless there is a clear requirement.

The existing HAPI FHIR R4 dependencies should be sufficient.

If a dependency is proposed, stop and explain why before adding it.

## Verification

Run:

```bash
java -version
```

Run:

```bash
cd services/fhir-integration-service
mvn test
```

Then ensure HAPI FHIR is running:

```bash
docker compose -f ../../infra/docker/docker-compose.yml ps
```

Run integration verification:

```bash
mvn verify -Pintegration
```

If the synthetic data is created through a script or manual process, show exactly how it was created and how to reproduce it.

Verify directly when useful:

```http
GET http://localhost:8080/fhir/Patient/patient-001
```

```http
GET http://localhost:8080/fhir/Patient?name=Maria
```

```http
GET http://localhost:8080/fhir/Patient?identifier=MRN-10001
```

Show the important response characteristics, not entire large JSON payloads.

## Code Quality

Follow:

- constructor injection;
- clear naming;
- small services;
- no static mutable state;
- no duplicated FHIR client creation;
- no unnecessary abstractions;
- no unnecessary DTO mapping;
- meaningful tests;
- synthetic data only.

## Expected Structure

The exact structure may vary if there is a strong reason, but remain close to:

```text
services/fhir-integration-service/
└── src/
    ├── main/
    │   └── java/
    │       └── lab/healthcare/fhir/
    │           └── client/
    │               ├── FhirClientConfiguration.java
    │               ├── FhirServerProperties.java
    │               ├── FhirService.java
    │               └── ...
    │
    └── test/
        └── java/
            └── lab/healthcare/fhir/
                └── client/
                    └── ...
```

Do not rename existing working components without a clear reason.

## Git Rules

Do not commit automatically.

At the end show:

```bash
git status
```

```bash
git diff --stat
```

Also show the relevant source/configuration diffs.

The developer will review the implementation before committing.

## Acceptance Criteria

The task is complete only when:

- [ ] Work is on `feature/fhir-search`.
- [ ] At least three deterministic synthetic Patients exist in local HAPI FHIR.
- [ ] Patient can be read by logical ID.
- [ ] Patient can be searched by `name`.
- [ ] Patient can be searched by `identifier`.
- [ ] Read returns a Patient resource.
- [ ] Search returns a Bundle.
- [ ] Bundle entries can be inspected and matching Patients identified.
- [ ] Logical ID vs identifier is explicitly demonstrated.
- [ ] Unit tests pass without requiring HAPI Docker.
- [ ] Integration tests pass against local HAPI FHIR.
- [ ] Existing error handling is preserved.
- [ ] No REST controller is added.
- [ ] No unrelated technologies/components are introduced.
- [ ] Documentation explains both FHIR HTTP and HAPI Java representations.
- [ ] No real patient information is used.
- [ ] No Git commit is created by Cursor.
- [ ] Final report contains the complete step-by-step execution history.

## Final Report Format

Do NOT provide only a summary.

Use this structure:

### Step-by-step execution

#### Step 1 — ...
- What I did:
- Why:
- Files:
- Commands:
- Result:
- FHIR concept:
- Java concept:

#### Step 2 — ...
...

### FHIR operations implemented

For each operation show:

```text
FHIR HTTP:
GET ...

HAPI FHIR Java:
...

Result:
...
```

### Synthetic data

List the Patients created:

- ID
- identifier
- name
- gender
- birthDate

Confirm that all data is synthetic.

### Files created

List every new file.

### Files modified

List every modified file and explain the change.

### Tests

For every test command show:
- exact command;
- result;
- what was verified.

### FHIR verification

Show:
- read by ID result;
- search by name result;
- search by identifier result;
- Bundle characteristics.

### Problems encountered

List each problem and how it was resolved.

### Concepts learned

Explain:
- read;
- search;
- search parameters;
- logical ID;
- identifier;
- Bundle;
- HAPI FHIR mapping to HTTP.

### Git status

Show actual output of:

```bash
git status
```

### Git diff stat

Show actual output of:

```bash
git diff --stat
```

### Next step

State only the next planned task.

Do not implement the next task.
