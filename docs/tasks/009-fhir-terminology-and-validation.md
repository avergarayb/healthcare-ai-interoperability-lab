# Task 009 — FHIR Terminology and Code Validation

## Objective

Learn how FHIR represents and validates clinical terminology.

This task builds on the concepts already studied:

- `Coding`
- `CodeableConcept`
- `CodeSystem`
- `ValueSet`
- LOINC
- SNOMED CT
- `Observation.code`
- `Condition.code`

The goal is to understand the difference between:

```text
CodeSystem
ValueSet
Coding
CodeableConcept
```

and then use the FHIR terminology operation:

```text
$validate-code
```

against the local HAPI FHIR server.

This task must remain focused on terminology.

Do not build a terminology server.

Do not create a custom code validation engine.

Do not introduce AI.

Do not integrate an external terminology server yet.

---

# Branch

Create and use:

```text
feature/fhir-terminology-validation
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
4. The FHIR HTTP operation.
5. The equivalent HAPI FHIR Java operation.
6. The command executed.
7. The result.
8. The FHIR concept being learned.
9. The Java/HAPI FHIR concept being learned.

Before writing Java code, explain the terminology concept and verify the raw FHIR operation against HAPI.

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
- CRUD.
- Advanced search.
- Chained search.
- `_has`.
- Bundle handling.
- Existing error handling.
- LOINC and SNOMED CT examples.
- Synthetic data.

Existing terminology examples:

```text
LOINC
system = http://loinc.org
code = 85354-9
```

```text
SNOMED CT
system = http://snomed.info/sct
code = 38341003
```

Existing resources:

```text
Observation/obs-001
    code → LOINC 85354-9

Condition/condition-001
    code → SNOMED CT 38341003
```

All clinical data is synthetic.

Reuse the existing `IGenericClient`.

Do not create another FHIR client.

---

# Part 1 — Terminology Fundamentals

Before coding, teach the following distinction.

## CodeSystem

A CodeSystem defines a set of codes and their meanings.

Examples:

```text
http://loinc.org
```

and:

```text
http://snomed.info/sct
```

Explain that a CodeSystem answers approximately:

> What codes exist and what do they mean?

Do not reduce CodeSystem to simply "a list of codes"; explain its role as the definition of a terminology system.

---

## Coding

A `Coding` identifies one coded concept.

Example:

```json
{
  "system": "http://loinc.org",
  "code": "85354-9",
  "display": "Blood pressure panel"
}
```

Explain:

```text
system
code
display
```

and why `system + code` is the important identity of the coded concept.

---

## CodeableConcept

A `CodeableConcept` represents a clinical concept and can contain one or more `Coding` elements.

Conceptually:

```text
CodeableConcept
    └── coding[]
          ├── system
          ├── code
          └── display
```

Explain why multiple Coding elements may be useful.

For example, one clinical concept may have representations in more than one terminology.

Do not create a translation service.

---

## ValueSet

A ValueSet defines the set of codes that are valid for a particular use/context.

Explain the difference:

```text
CodeSystem
→ defines concepts/codes

ValueSet
→ defines which codes are allowed/selected for a context
```

This distinction is a major learning objective.

---

# Part 2 — Inspect Existing Terminology

Read the existing synthetic:

```text
Observation/obs-001
Condition/condition-001
```

Explain how:

```text
Observation.code
```

and:

```text
Condition.code
```

are represented using `CodeableConcept`.

Show the actual relevant JSON fields, not the entire Resource.

Verify:

```text
LOINC 85354-9
```

and:

```text
SNOMED CT 38341003
```

---

# Part 3 — Search by Terminology Code

Before `$validate-code`, reinforce terminology-based Search.

Use:

```http
GET /Observation?code=85354-9
```

and, if useful:

```http
GET /Condition?code=38341003
```

Explain that Search asks:

> Which Resources have this coded concept?

Whereas `$validate-code` asks:

> Is this code valid in the specified terminology/context?

This distinction must be explicit.

---

# Part 4 — `$validate-code`

Introduce the FHIR terminology operation:

```text
$validate-code
```

Explain that `$validate-code` is an FHIR operation used to determine whether a code is valid in a terminology context.

Do not assume that validation means:

```text
"the patient has this diagnosis"
```

It means terminology validation.

---

# Part 5 — Validate LOINC

First test the raw HTTP operation against HAPI.

Use the appropriate R4 syntax supported by HAPI for:

```text
$validate-code
```

The validation must use:

```text
system = http://loinc.org
code = 85354-9
```

Verify the actual server response.

Explain:

- OperationOutcome;
- Parameters;
- validation result;
- message/details when provided.

Do not guess the exact response structure.

Inspect the actual response returned by HAPI.

---

# Part 6 — Validate an Invalid LOINC Code

Test an intentionally invalid/nonexistent synthetic code.

For example, use a clearly invalid code value such as:

```text
99999999
```

with:

```text
system = http://loinc.org
```

Verify that the result indicates failure/not-valid according to HAPI's actual response.

Explain the difference between:

```text
HTTP operation succeeded
```

and:

```text
terminology validation succeeded
```

This is important.

A terminology operation can return an HTTP-level response while the validation result itself is negative.

Do not interpret HTTP 200 alone as "the code is valid."

---

# Part 7 — Validate SNOMED CT

Validate:

```text
system = http://snomed.info/sct
code = 38341003
```

Use the appropriate HAPI-supported `$validate-code` syntax.

Verify the result.

Then perform an invalid SNOMED validation.

Use a clearly invalid synthetic code.

Document the actual result.

---

# Part 8 — ValueSet Context

Introduce the `ValueSet` role conceptually.

Explain that validation can be performed:

```text
against a CodeSystem
```

or:

```text
in a ValueSet/context
```

depending on the operation and server support.

Do not create a custom ValueSet server.

Do not invent a ValueSet URL.

First inspect whether the local HAPI instance already exposes terminology resources/ValueSets that can be used safely for demonstration.

If there is no suitable local ValueSet, document that fact.

Do not force a fake external ValueSet.

---

# Part 9 — HAPI FHIR Java API

For each terminology operation, verify the HAPI 8.10.0 Java API before implementation.

The implementation should use the existing:

```java
IGenericClient
```

and the appropriate operation mechanism.

HAPI FHIR commonly exposes FHIR operations through an API similar to:

```java
client
    .operation()
    ...
```

Do not assume exact method signatures.

Inspect the actual HAPI API available in the project.

The implementation should return a representation that allows the application/tests to determine:

```text
valid
invalid
message/details
```

Do not hide the FHIR terminology response behind an arbitrary boolean-only abstraction if doing so would lose useful FHIR information.

---

# Part 10 — Parameters Resource

Teach the FHIR:

```text
Parameters
```

Resource as the input/output mechanism commonly used by FHIR operations.

Explain:

```text
$validate-code
```

may use:

```text
Parameters
```

for operation input and output.

Show a concise example.

Do not confuse:

```text
Parameters
```

with:

```text
Bundle
```

Important distinction:

```text
Bundle
→ groups Resources

Parameters
→ carries named operation parameters
```

---

# Part 11 — OperationOutcome

Teach:

```text
OperationOutcome
```

and its role in FHIR responses.

Explain that it communicates:

- errors;
- warnings;
- informational messages;
- processing details.

Do not treat every OperationOutcome as an HTTP error.

Do not assume that a validation failure must always be represented by a transport-level 4xx status.

Inspect actual HAPI behavior.

---

# Part 12 — Coding vs CodeableConcept

Add a small Java/model exercise.

Create or inspect:

```text
Coding
CodeableConcept
```

and show how the existing Observation code maps to the Java R4 model.

Conceptually:

```java
Observation observation = ...;

CodeableConcept concept = observation.getCode();

Coding coding = concept.getCodingFirstRep();
```

Verify:

```text
coding.getSystem()
coding.getCode()
coding.getDisplay()
```

Do not create DTOs.

The purpose is to understand the HAPI model.

---

# Part 13 — Multiple Codings

Create a small synthetic in-memory example of a `CodeableConcept` containing two `Coding` elements.

Do not persist it unless useful for a test.

Explain:

```text
CodeableConcept
    ├── Coding #1
    └── Coding #2
```

Each Coding may use a different terminology system.

Do not imply that different codes are automatically equivalent.

Explain that semantic equivalence requires appropriate terminology mapping/knowledge.

Do not introduce ConceptMap yet.

---

# Part 14 — Unit Tests

Use mocks where appropriate.

Test at minimum:

- valid LOINC validation;
- invalid LOINC validation;
- valid SNOMED CT validation;
- invalid SNOMED CT validation;
- terminology response parsing;
- Parameters handling;
- OperationOutcome/error propagation.

If mocking HAPI's operation API becomes complicated, explain the tradeoff.

Do not hide the complexity.

---

# Part 15 — Integration Tests

Use real HAPI FHIR.

Verify:

### Valid LOINC

```text
system = http://loinc.org
code = 85354-9
```

### Invalid LOINC

```text
system = http://loinc.org
code = 99999999
```

### Valid SNOMED CT

```text
system = http://snomed.info/sct
code = 38341003
```

### Invalid SNOMED CT

Use a clearly invalid synthetic code.

For each test verify the actual validation result.

Do not assert only HTTP status.

If HAPI's terminology support has limitations, document exactly what was observed.

Do not fake a successful validation.

---

# Part 16 — Raw HTTP Verification

Use `curl.exe` or PowerShell.

Show the actual `$validate-code` request and a concise response.

Do not paste huge responses.

At minimum demonstrate:

```text
valid LOINC
invalid LOINC
valid SNOMED CT
invalid SNOMED CT
```

Show:

```text
HTTP status
validation result
message/details when available
```

---

# Part 17 — Important Terminology Distinctions

Document explicitly:

```text
CodeSystem
    ↓
defines terminology concepts/codes

ValueSet
    ↓
selects/defines allowed codes for a context

Coding
    ↓
one coded representation

CodeableConcept
    ↓
clinical concept represented by one or more Codings

$validate-code
    ↓
checks terminology validity in a context
```

Also distinguish:

```text
Search
→ finds Resources containing a code

$validate-code
→ validates a code
```

---

# Part 18 — Documentation

Create:

```text
docs/fhir/fhir-terminology-and-validation.md
```

Teach:

1. CodeSystem.
2. ValueSet.
3. Coding.
4. CodeableConcept.
5. LOINC.
6. SNOMED CT.
7. `$validate-code`.
8. Parameters.
9. OperationOutcome.
10. Terminology Search versus terminology validation.
11. HAPI FHIR terminology operation API.
12. Valid versus invalid terminology responses.
13. Multiple Codings.

Include concise JSON examples.

---

# Part 19 — Update Existing Documentation

Update only what is necessary:

```text
docs/fhir/README.md
docs/fhir/fhir-resources-and-references.md
docs/roadmap.md
```

Do not rewrite unrelated documentation.

---

# Part 20 — No External Terminology Yet

Do NOT connect to:

- external LOINC services;
- external SNOMED services;
- terminology vendors;
- UMLS;
- BioPortal;
- external terminology servers.

Use local HAPI capabilities only.

If local HAPI cannot perform a specific terminology operation as expected, document the limitation instead of introducing an external dependency.

---

# Part 21 — Explicitly Out of Scope

Do NOT implement yet:

- custom terminology server;
- terminology synchronization;
- ConceptMap;
- `$translate`;
- `$expand`;
- `$lookup`;
- `$subsumes`;
- terminology caching;
- external terminology services;
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
├── fhir-search-chaining.md
└── fhir-terminology-and-validation.md
```

Do not rename existing working classes without a clear reason.

---

# Acceptance Criteria

- [ ] Work is on `feature/fhir-terminology-validation`.
- [ ] CodeSystem is clearly explained.
- [ ] ValueSet is clearly explained.
- [ ] Coding is clearly explained.
- [ ] CodeableConcept is clearly explained.
- [ ] LOINC example is inspected.
- [ ] SNOMED CT example is inspected.
- [ ] `$validate-code` is tested against local HAPI.
- [ ] Valid LOINC is tested.
- [ ] Invalid LOINC is tested.
- [ ] Valid SNOMED CT is tested.
- [ ] Invalid SNOMED CT is tested.
- [ ] Parameters is explained.
- [ ] OperationOutcome is explained.
- [ ] Search by terminology code is distinguished from `$validate-code`.
- [ ] Multiple Codings are demonstrated in memory.
- [ ] HAPI FHIR 8.10.0 Java operation API is verified.
- [ ] Unit tests pass without Docker.
- [ ] Integration tests pass against local HAPI, or limitations are explicitly documented.
- [ ] Existing error handling is preserved.
- [ ] No custom terminology server is introduced.
- [ ] No external terminology service is introduced.
- [ ] No REST controller is added.
- [ ] No DTO is introduced without clear justification.
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

## Terminology model

Show:

```text
CodeSystem
    ↓
defines concepts

ValueSet
    ↓
selects allowed concepts

Coding
    ↓
system + code + display

CodeableConcept
    ↓
one or more Codings
```

## `$validate-code`

For every validation show:

```text
FHIR HTTP:
...

HAPI FHIR Java:
...

Result:
...

Validation:
VALID / INVALID
```

## Search vs validation

Explain:

```text
GET /Observation?code=...
```

versus:

```text
$validate-code
```

## Parameters vs Bundle

Explain the difference.

## OperationOutcome

Explain the actual behavior observed from HAPI.

## Synthetic terminology data

Confirm all clinical data is synthetic.

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

Show selected `$validate-code` requests and concise results.

## Problems encountered

List each problem and resolution.

## Concepts learned

Explain:

- CodeSystem;
- ValueSet;
- Coding;
- CodeableConcept;
- `$validate-code`;
- Parameters;
- OperationOutcome;
- terminology Search versus validation;
- multiple Codings.

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
