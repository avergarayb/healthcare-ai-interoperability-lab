# Task 010 — FHIR Resource Validation and Profiles

## Objective

Learn how FHIR validates a Resource against the FHIR R4 structure and against an implementation-specific profile.

This task moves from:

```text
"Is this code valid?"
```

from Task 009, to:

```text
"Is this Resource structurally and semantically conformant to the rules that apply to it?"
```

The central concepts are:

- FHIR validation
- `StructureDefinition`
- profiles
- differential vs snapshot
- cardinality
- required elements
- datatypes
- bindings
- invariants
- `meta.profile`
- `$validate`
- `OperationOutcome`

Do not build a custom validation engine, public REST API, terminology server, or external EHR integration.

---

# Branch

Create and use:

```text
feature/fhir-resource-validation
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
4. The FHIR HTTP operation.
5. The equivalent HAPI FHIR Java operation.
6. The command executed.
7. The result.
8. The FHIR concept being learned.
9. The Java/HAPI FHIR concept being learned.

Before writing Java code, first verify the raw FHIR operation against HAPI.

If HAPI local does not support a proposed validation scenario, do not fake the result. Explain the limitation and adapt the exercise using a local/synthetic profile when appropriate.

If an error occurs, show the error, explain the cause, apply the fix, re-run verification, and explain why it works.

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

Existing functionality includes:

- FHIR R4 client
- CapabilityStatement
- Patient read/search
- Observation read/search
- Condition read/search
- References
- `_include`
- `_revinclude`
- CRUD
- Advanced search
- Chained search
- `_has`
- `$validate-code`
- Coding / CodeableConcept
- CodeSystem / ValueSet
- Parameters / OperationOutcome

Synthetic resources:

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

# Part 1 — What FHIR Validation Means

Explain the difference between:

```text
Search
→ find Resources

$validate-code
→ validate terminology/code

Resource validation
→ validate Resource conformance
```

A Resource can be valid JSON and still fail FHIR validation.

Example:

```json
{
  "resourceType": "Observation"
}
```

Explain that FHIR validation can inspect:

- structure
- required elements
- cardinality
- datatypes
- terminology bindings
- references
- invariants
- profile constraints

Do not reduce FHIR validation to JSON Schema validation.

---

# Part 2 — Base FHIR Validation vs Profile Validation

Teach:

```text
Base resource validation
→ validates against the base FHIR R4 definition

Profile validation
→ validates against additional constraints for a use case
```

A profile does not create a new Resource type.

Conceptually:

```text
Observation
      ↓
Lab Blood Pressure Observation Profile
```

---

# Part 3 — StructureDefinition

Explain:

```text
StructureDefinition
```

as the FHIR Resource that defines structure and constraints.

Teach these concepts:

```text
url
name
title
status
kind
type
baseDefinition
derivation
differential
snapshot
```

Explain why `baseDefinition` and `derivation` matter.

---

# Part 4 — Differential vs Snapshot

Explain:

```text
Differential
→ only the changes/constraints introduced by the profile

Snapshot
→ complete resulting structure
```

Use a simple conceptual example.

Do not create a custom profile generator.

---

# Part 5 — Inspect CapabilityStatement

Before implementing validation, inspect:

```http
GET /metadata
```

Determine whether HAPI advertises support for:

```text
$validate
```

Explain:

- CapabilityStatement tells clients what the server advertises.
- Actual behavior must still be verified.

Do not assume advertised support means every profile/terminology scenario is supported.

---

# Part 6 — Validate a Basic Observation

Start with:

```text
Observation/obs-001
```

Verify:

```http
GET /Observation/obs-001
```

Then invoke the R4 `$validate` operation using the actual syntax supported by HAPI.

First test raw HTTP.

Do not guess.

Inspect the response:

- HTTP status
- OperationOutcome
- severity
- issue code
- diagnostics
- location/expression when available

Do not assume a particular HTTP status before observing HAPI.

---

# Part 7 — Intentionally Invalid Resource

Create an in-memory or test-only invalid Observation:

```json
{
  "resourceType": "Observation",
  "id": "invalid-observation"
}
```

Do not persist it unless necessary.

Validate it and inspect the resulting `OperationOutcome`.

Explain the actual:

```text
severity
code
diagnostics
location/expression
```

returned by HAPI.

---

# Part 8 — Validation Using HAPI Java

Verify the HAPI 8.10.0 API before implementation.

Use the existing:

```java
IGenericClient
```

The API may resemble:

```java
client
    .validate()
    .resource(resource)
    .execute();
```

but do not assume this exact signature.

Inspect the actual API.

Preserve useful validation information. Do not reduce everything to a boolean if that discards `OperationOutcome` details.

---

# Part 9 — OperationOutcome

Deepen the concept:

```text
OperationOutcome
    └── issue[]
          ├── severity
          ├── code
          ├── details
          ├── diagnostics
          ├── location
          └── expression
```

Explain that validation may produce multiple issues.

Do not assume every field is always populated.

---

# Part 10 — Synthetic Profile

Create a small synthetic profile for this lab.

Recommended Resource:

```text
Observation
```

Suggested canonical URL:

```text
https://example.org/fhir/StructureDefinition/lab-blood-pressure-observation
```

Keep it simple and educational.

Constrain at least:

```text
Observation.subject
```

and/or:

```text
Observation.code
```

and/or:

```text
Observation.value[x]
```

Use realistic cardinalities.

The profile must demonstrate:

```text
valid Resource against profile
```

and:

```text
invalid Resource against profile
```

Do not over-engineer it.

---

# Part 11 — Profile Cardinality

Demonstrate at least one cardinality constraint.

For example:

```text
Observation.subject
0..1
```

becomes:

```text
1..1
```

Explain:

```text
0..1
→ optional

1..1
→ required exactly once
```

Validate:

```text
Observation with subject
```

and:

```text
Observation without subject
```

If HAPI requires additional dependencies/profile support, document the actual behavior and adapt only as necessary.

---

# Part 12 — Profile URL and meta.profile

Explain:

```text
meta.profile
```

as a declaration that a Resource is intended to conform to a profile.

Example:

```json
"meta": {
  "profile": [
    "https://example.org/fhir/StructureDefinition/lab-blood-pressure-observation"
  ]
}
```

Important:

```text
meta.profile
≠ proof of conformance
```

It is a declaration. The Resource still needs validation.

---

# Part 13 — Validate Against Explicit Profile

Demonstrate profile-specific validation:

```text
Observation
      ↓
$validate
      ↓
profile URL
      ↓
StructureDefinition
      ↓
validation result
```

First validate a conformant Observation.

Then validate a non-conformant Observation.

Use the actual HAPI-supported syntax.

Do not guess the profile parameter.

---

# Part 14 — Profile Loading

Determine how the local HAPI environment can access the synthetic profile.

Possible approaches:

- store the `StructureDefinition` in HAPI;
- use a local validator context;
- load it from application resources;
- another HAPI-supported mechanism.

Investigate before implementing.

Do not create a second FHIR server.

Do not use an external profile registry.

The profile must be reproducible for tests.

Document why the selected approach was chosen.

---

# Part 15 — Profile Resource

Create the synthetic profile as a real FHIR R4 `StructureDefinition` JSON resource.

Suggested location:

```text
scripts/fhir/profiles/
```

Suggested filename:

```text
lab-blood-pressure-observation.json
```

Do not create arbitrary JSON that merely resembles a StructureDefinition.

Validate the profile itself if the local environment supports it.

---

# Part 16 — Unit Tests

Add unit tests using mocks.

Test at minimum:

- valid base Observation;
- invalid base Observation;
- OperationOutcome extraction;
- valid profile validation;
- invalid profile validation;
- preservation of validation details;
- error propagation.

If HAPI's validation API requires complex context setup, explain the testing strategy.

Do not mock away the entire validation concept.

---

# Part 17 — Integration Tests

Use real HAPI or the project's local validation context.

Verify:

### Base valid Observation

```text
Observation/obs-001
```

Expected:

```text
validation succeeds
```

### Base invalid Observation

```text
Observation with missing required data
```

Expected:

```text
validation issue
```

### Profile-conformant Observation

Expected:

```text
profile validation succeeds
```

### Profile-nonconformant Observation

Expected:

```text
profile validation issue
```

Assertions should inspect meaningful validation information, not only HTTP status.

---

# Part 18 — Raw HTTP Verification

Use `curl.exe` or PowerShell.

Show concise examples for:

1. valid base validation;
2. invalid base validation;
3. profile validation;
4. invalid profile validation.

Do not paste large OperationOutcome responses.

Show:

```text
HTTP status
issue severity
issue code
diagnostics/expression when available
```

---

# Part 19 — Validation vs $validate-code

Document explicitly:

```text
$validate-code
→ validates terminology/code

$validate
→ validates Resource conformance
```

Example:

```text
$validate-code
LOINC 85354-9
```

versus:

```text
$validate
Observation/obs-001
```

This distinction must be very clear.

---

# Part 20 — Validation vs Profile Declaration

Document:

```text
meta.profile
```

means:

```text
"I intend this Resource to conform to this profile."
```

while:

```text
$validate
```

means:

```text
"Check whether it actually conforms."
```

Do not treat `meta.profile` as validation.

---

# Part 21 — Documentation

Create:

```text
docs/fhir/fhir-validation-and-profiles.md
```

Teach:

1. Resource validation.
2. `$validate`.
3. StructureDefinition.
4. Profile.
5. baseDefinition.
6. derivation.
7. differential.
8. snapshot.
9. cardinality.
10. meta.profile.
11. OperationOutcome.
12. base validation vs profile validation.
13. `$validate` vs `$validate-code`.
14. How the lab profile is loaded.
15. HAPI FHIR Java validation API.

Include concise JSON examples and diagrams.

---

# Part 22 — Update Existing Documentation

Update only what is necessary:

```text
docs/fhir/README.md
docs/fhir/fhir-terminology-and-validation.md
docs/roadmap.md
```

Do not rewrite unrelated content.

---

# Part 23 — No Custom Validator

Do NOT create:

- custom FHIR validator;
- manual cardinality checker;
- custom profile parser;
- JSON Schema validator;
- terminology validation engine;
- generic validation framework;
- validation microservice.

The purpose is to learn and consume the FHIR/HAPI validation mechanisms.

---

# Part 24 — Explicitly Out of Scope

Do NOT implement yet:

- custom ImplementationGuide;
- US Core;
- IPS;
- Da Vinci;
- FHIR Shorthand (FSH);
- SUSHI;
- external profile registries;
- external terminology servers;
- ConceptMap;
- `$translate`;
- `$expand`;
- `$lookup`;
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

scripts/fhir/
└── profiles/
    └── lab-blood-pressure-observation.json

docs/fhir/
├── fhir-client.md
├── fhir-search.md
├── fhir-resources-and-references.md
├── fhir-include-revinclude.md
├── fhir-crud-write-operations.md
├── fhir-advanced-search.md
├── fhir-search-chaining.md
├── fhir-terminology-and-validation.md
└── fhir-validation-and-profiles.md
```

Do not rename existing working classes without a clear reason.

---

# Acceptance Criteria

- [ ] Work is on `feature/fhir-resource-validation`.
- [ ] Base FHIR Resource validation is demonstrated.
- [ ] `$validate` is verified against the local HAPI implementation.
- [ ] A valid Observation is validated.
- [ ] An intentionally invalid Observation is validated.
- [ ] OperationOutcome is inspected and explained.
- [ ] StructureDefinition is explained.
- [ ] Profile is explained.
- [ ] `baseDefinition` is explained.
- [ ] `derivation` is explained.
- [ ] differential vs snapshot is explained.
- [ ] A synthetic Observation profile is created.
- [ ] At least one meaningful cardinality constraint is demonstrated.
- [ ] A conformant Resource passes profile validation.
- [ ] A non-conformant Resource produces a profile validation issue.
- [ ] `meta.profile` is demonstrated.
- [ ] `meta.profile` is clearly distinguished from actual validation.
- [ ] `$validate` is distinguished from `$validate-code`.
- [ ] HAPI FHIR 8.10.0 Java validation API is verified.
- [ ] Unit tests pass without Docker where applicable.
- [ ] Integration validation passes against the local validation environment, or limitations are explicitly documented.
- [ ] Existing error handling is preserved.
- [ ] No custom validation engine is introduced.
- [ ] No external profile registry is introduced.
- [ ] No external terminology service is introduced.
- [ ] No REST controller is added.
- [ ] No unnecessary DTO is introduced.
- [ ] All clinical data is synthetic.
- [ ] Documentation explains HTTP and HAPI FHIR representations.
- [ ] No Git commit is created by Cursor.
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

## Validation model

Show:

```text
FHIR Resource
      ↓
Base definition
      ↓
Profile
      ↓
Constraints
      ↓
Validation
      ↓
OperationOutcome / result
```

## Base validation

For every implemented operation show:

```text
FHIR HTTP:
...

HAPI FHIR Java:
...

Result:
...
```

## Profile validation

Show:

```text
Profile URL:
...

Constraint:
...

Valid Resource:
...

Invalid Resource:
...
```

## StructureDefinition

Explain:

- baseDefinition;
- derivation;
- differential;
- snapshot.

## meta.profile

Explain declaration vs actual validation.

## OperationOutcome

Explain actual behavior observed from HAPI.

## `$validate` vs `$validate-code`

Explain with concrete examples.

## Synthetic profile

Confirm that the profile is synthetic and created only for the lab.

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

Show selected validation requests and concise results.

## Problems encountered

List each problem and resolution.

## Concepts learned

Explain:

- validation;
- StructureDefinition;
- profile;
- baseDefinition;
- derivation;
- differential;
- snapshot;
- cardinality;
- meta.profile;
- OperationOutcome;
- `$validate`;
- `$validate-code`.

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
