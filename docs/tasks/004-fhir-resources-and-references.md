# Task 004 — FHIR Resources and References

## Objective

Extend `fhir-integration-service` from standalone `Patient` interactions to related clinical FHIR resources.

Implement and demonstrate:

1. `Observation` resources related to a `Patient`.
2. `Condition` resources related to a `Patient`.
3. FHIR `Reference` elements.
4. `Observation.subject`.
5. `Condition.subject`.
6. `Coding`, `CodeableConcept`, and terminology systems.
7. Searches for related resources by patient.
8. Logical ID versus references and business identifiers.

This is an educational implementation. Keep the scope small and explain every new concept.

## Branch

Create and use:

`feature/fhir-resources-references`

Do not work directly on `main`.

## Teaching Mode — Mandatory

Act as a senior instructor and implementation mentor.

Do not silently implement the task.

Execute the work step by step and explain it as you proceed, as if teaching the developer.

Before implementing each resource or FHIR operation, explain the FHIR concept first.

For every significant step, show:

1. What you are doing.
2. Why you are doing it.
3. Which file is being created or modified.
4. The relevant code or JSON.
5. The command executed.
6. The command result.
7. The FHIR concept being learned.
8. The Java/HAPI FHIR concept being learned.

Do not provide only a final summary.

When introducing a new FHIR resource, explain what it represents and why it is appropriate.

When introducing a new HAPI FHIR class/API, explain its purpose before using it.

If an error occurs:
1. Show the error.
2. Explain the likely cause.
3. Explain the chosen fix.
4. Apply the fix.
5. Re-run verification.
6. Explain why the fix works.

At the end provide both a concise summary and the complete step-by-step execution report.

## Context

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

- HAPI FHIR R4 client.
- CapabilityStatement retrieval.
- Patient read by logical ID.
- Patient search by `name`.
- Patient search by `identifier`.
- Bundle handling.
- Synthetic Patient dataset.

Existing synthetic Patients:

```text
Patient/patient-001
MRN-10001
Maria Garcia

Patient/patient-002
MRN-10002
Juan Garcia

Patient/patient-003
MRN-10003
Maria Lopez
```

Use synthetic data only.

## Architecture

Maintain:

```text
FHIR Integration Service
        |
        | HAPI FHIR Client
        v
Local HAPI FHIR Server
        |
        +---- Patient
        |
        +---- Observation
        |
        +---- Condition
```

Do not create another microservice, API Gateway, or public `@RestController`.

Reuse the existing `IGenericClient`. Do not create another FHIR client bean.

# Part 1 — Resource Graph

Before coding, explain:

```text
                    Patient/patient-001
                    /               \
                   /                 \
                  v                   v
      Observation/obs-001      Condition/condition-001
             |                         |
             | subject                 | subject
             +------------+------------+
                          v
                   Patient/patient-001
```

Explain that Patient, Observation, and Condition are independent FHIR Resources. They are connected through `Reference`; Observation is not embedded inside Patient.

Teach:

```text
Patient logical ID:
patient-001
```

versus:

```text
Reference:
Patient/patient-001
```

# Part 2 — Observation

Explain what `Observation` represents.

Create synthetic:

```text
Observation/obs-001
```

referencing:

```text
Patient/patient-001
```

Use LOINC:

```text
system: http://loinc.org
code: 85354-9
display: Blood pressure panel
```

Use a simple blood-pressure-related observation. If representing a numeric quantity, use `130 mmHg` and explicitly explain that a clinically complete blood pressure panel normally contains systolic/diastolic components. Do not expand into advanced vital-sign modeling; the learning goal is Resource + Reference + Coding.

Conceptual JSON:

```json
{
  "resourceType": "Observation",
  "id": "obs-001",
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

If the R4 model requires additional fields, use the correct model and explain why.

Teach the Java mapping:

```text
Observation
 ├── status
 ├── code
 │    └── CodeableConcept
 │         └── Coding
 └── subject
      └── Reference
```

Use the appropriate R4 classes.

# Part 3 — Condition

Explain what `Condition` represents and how it differs from `Observation`.

Create:

```text
Condition/condition-001
```

for:

```text
Patient/patient-001
```

Use SNOMED CT:

```text
system: http://snomed.info/sct
code: 38341003
display: Hypertensive disorder
```

Conceptual JSON:

```json
{
  "resourceType": "Condition",
  "id": "condition-001",
  "subject": {
    "reference": "Patient/patient-001"
  },
  "code": {
    "coding": [
      {
        "system": "http://snomed.info/sct",
        "code": "38341003",
        "display": "Hypertensive disorder"
      }
    ]
  }
}
```

If the R4 model requires additional fields, use the correct R4 representation and explain it.

# Part 4 — Terminology

Explicitly reinforce:

### Coding

A coded concept contains:

```text
system
code
display
```

Example:

```text
system = http://loinc.org
code = 85354-9
```

### CodeSystem

Explain that:

```text
http://loinc.org
```

identifies the terminology system; the `code` identifies the concept within that system.

Similarly:

```text
http://snomed.info/sct
```

identifies SNOMED CT.

### CodeableConcept

Explain:

```text
CodeableConcept
    └── coding[]
          └── Coding
```

and why multiple `Coding` elements can represent the same clinical concept in different coding systems.

Do not implement terminology translation.

# Part 5 — Synthetic Resources

Create reproducible files under:

```text
scripts/fhir/
```

Add:

```text
observation-001.json
condition-001.json
```

Reuse the existing synthetic-data loading strategy where possible.

Do not create a second unrelated data-loading architecture.

Explain exactly how the resources are loaded into HAPI.

All data must be synthetic.

# Part 6 — Read Observation and Condition

Before coding, explain:

```http
GET /Observation/obs-001
GET /Condition/condition-001
```

Explain that both use logical IDs.

Implement with the existing client, conceptually:

```java
client.read()
    .resource(Observation.class)
    .withId("obs-001")
    .execute();
```

and:

```java
client.read()
    .resource(Condition.class)
    .withId("condition-001")
    .execute();
```

Do not duplicate client creation.

# Part 7 — Search Observations by Patient

First explain:

```http
GET /Observation?patient=patient-001
```

Explain that `patient` is a FHIR search parameter, while the resource element is `subject`.

Then implement the HAPI FHIR equivalent using the correct R4 search parameter.

Expected result:

```text
Bundle
  obs-001
```

Do not rely on result ordering.

# Part 8 — Search Conditions by Patient

First explain:

```http
GET /Condition?patient=patient-001
```

Then implement the HAPI FHIR equivalent.

Expected:

```text
Bundle
  condition-001
```

Do not rely on ordering.

# Part 9 — Follow the Reference

Retrieve the Observation and inspect its subject reference.

Expected:

```text
Patient/patient-001
```

Do the same for Condition.

Explain that this is a FHIR `Reference` represented in Java.

Do not implement a generic graph traversal engine.

# Part 10 — Bundle

For:

```http
GET /Observation?patient=patient-001
GET /Condition?patient=patient-001
```

show that searches return:

```text
Bundle
 └── entry[]
      └── resource
```

Reinforce:

```text
Read → resource
Search → Bundle
```

Do not implement `_include` or `_revinclude` yet.

# Part 11 — Tests

Separate unit and integration tests.

## Unit tests

Mock `IGenericClient`.

Test at least:

- read Observation;
- read Condition;
- search Observation by patient;
- search Condition by patient;
- subject reference extraction;
- error propagation.

Unit tests must not require Docker.

## Integration tests

Use local HAPI.

Verify:

1. Observation `obs-001` exists.
2. Condition `condition-001` exists.
3. Observation references `Patient/patient-001`.
4. Condition references `Patient/patient-001`.
5. Observation search by patient returns `obs-001`.
6. Condition search by patient returns `condition-001`.
7. Observation uses LOINC `85354-9`.
8. Condition uses SNOMED CT `38341003`.

Use deterministic assertions and do not depend on Bundle entry ordering.

# Part 12 — Documentation

Create:

`docs/fhir/fhir-resources-and-references.md`

Teach:

- FHIR Resource.
- Observation.
- Condition.
- Reference.
- `subject`.
- logical ID.
- identifier.
- Coding.
- CodeableConcept.
- CodeSystem.
- LOINC.
- SNOMED CT.
- search by patient.
- Bundle.
- HTTP FHIR operation versus HAPI FHIR Java operation.

Include examples such as:

```json
"subject": {
  "reference": "Patient/patient-001"
}
```

Write this as study material, not only API documentation.

# Part 13 — No DTO Yet

Do not introduce DTOs merely for architectural fashion.

The objective is to understand the FHIR wire model.

If a DTO is proposed, explain the boundary and reason before adding it.

Do not create a generic healthcare domain model.

# Part 14 — Explicitly Out of Scope

Do NOT implement:

- `_include`
- `_revinclude`
- chained search
- `_has`
- pagination framework
- terminology server
- `$expand`
- `$validate-code`
- SMART on FHIR
- OAuth
- Epic
- Oracle Health
- HL7 v2
- AI
- RAG
- agents
- MCP
- Python
- additional microservices
- API Gateway
- public REST controllers

# Verification

Run:

```bash
java -version
```

```bash
cd services/fhir-integration-service
mvn test
```

Verify infrastructure:

```bash
docker compose -f ../../infra/docker/docker-compose.yml ps
```

Run:

```bash
mvn verify -Pintegration
```

Verify directly when useful:

```http
GET http://localhost:8080/fhir/Observation/obs-001
GET http://localhost:8080/fhir/Condition/condition-001
GET http://localhost:8080/fhir/Observation?patient=patient-001
GET http://localhost:8080/fhir/Condition?patient=patient-001
```

Show important response characteristics, not unnecessarily large payloads.

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
- no unnecessary abstractions.

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
├── patient-001.json
├── patient-002.json
├── patient-003.json
├── observation-001.json
└── condition-001.json

docs/fhir/
├── fhir-client.md
├── fhir-search.md
└── fhir-resources-and-references.md
```

Do not rename existing working classes without a clear reason.

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

The developer will review before committing.

# Acceptance Criteria

- [ ] Work is on `feature/fhir-resources-references`.
- [ ] Synthetic Observation exists.
- [ ] Synthetic Condition exists.
- [ ] Observation references `Patient/patient-001`.
- [ ] Condition references `Patient/patient-001`.
- [ ] Observation can be read by logical ID.
- [ ] Condition can be read by logical ID.
- [ ] Observation can be searched by patient.
- [ ] Condition can be searched by patient.
- [ ] Search responses are handled as Bundles.
- [ ] `Reference` is explicitly demonstrated.
- [ ] `Coding` is explicitly demonstrated.
- [ ] `CodeableConcept` is explicitly demonstrated.
- [ ] LOINC `85354-9` is used for Observation.
- [ ] SNOMED CT `38341003` is used for Condition.
- [ ] Logical ID vs identifier is explicitly explained.
- [ ] Unit tests pass without Docker.
- [ ] Integration tests pass against local HAPI FHIR.
- [ ] Existing error handling is preserved.
- [ ] No unjustified DTO is introduced.
- [ ] No REST controller is added.
- [ ] No `_include` or `_revinclude` is implemented.
- [ ] No unrelated technologies/components are introduced.
- [ ] Documentation explains FHIR HTTP and HAPI Java representations.
- [ ] No real patient information is used.
- [ ] No Git commit is created by Cursor.
- [ ] Final report contains complete step-by-step execution history.

# Final Report Format

Do NOT provide only a summary.

Use:

## Step-by-step execution

### Step 1 — ...
- What I did:
- Why:
- Files:
- Commands:
- Result:
- FHIR concept:
- Java/HAPI concept:

### Step 2 — ...
...

## Resource model

Explain:

```text
Patient
   |
   +-- Observation
   |
   +-- Condition
```

and how `Reference` connects them.

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

## Synthetic data

List Patients, Observations, Conditions, and terminology codes. Confirm all data is synthetic.

## Files created

List every new file.

## Files modified

List every modified file and explain each change.

## Dependencies

State whether dependencies were added. If none, explicitly say so.

## Tests

For each command show exact command, result, and what was verified.

## FHIR verification

Show:

- Observation read;
- Condition read;
- Observation search by patient;
- Condition search by patient;
- subject references;
- terminology codes.

## Problems encountered

List each problem and how it was resolved.

## Concepts learned

Explain:

- Resource;
- Observation;
- Condition;
- Reference;
- logical ID;
- identifier;
- Coding;
- CodeableConcept;
- CodeSystem;
- LOINC;
- SNOMED CT;
- search by reference;
- Bundle.

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
