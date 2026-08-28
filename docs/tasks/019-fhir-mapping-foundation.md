# Task 019 — FHIR Mapping & Transformation Foundation

## Objective

Introduce the first reusable mapping/transformation capability of the `fhir-integration-service`.

The goal is to transform an external application payload into a FHIR R4 Resource without coupling `FhirService` to the source system's JSON structure.

This task establishes the foundation for a future interoperability layer capable of connecting:

```text
Legacy / External System
        ↓
   Transformation
        ↓
     FHIR R4
        ↓
FHIR Integration Service
        ↓
      EHR / FHIR Server
```

The implementation must remain deliberately small.

This task does **not** implement a complete enterprise mapping engine, HL7 v2 parser, CDA transformation, X12, or EHR-specific mapping.

---

# Baseline

Task 019 starts from the current `main` after Task 018:

```text
Task 016 → OAuth 2.0
Task 017 → SMART on FHIR
Task 018 → Architecture Refactoring
```

The package boundaries established in Task 018 must be preserved.

---

# Business motivation

A real interoperability project rarely receives data already modeled as FHIR.

A customer may have:

```json
{
  "patient_id": "12345",
  "first_name": "John",
  "last_name": "Smith",
  "date_of_birth": "1980-05-20"
}
```

while the FHIR endpoint expects:

```text
Patient
 ├── identifier
 ├── name.given
 ├── name.family
 └── birthDate
```

The integration component should therefore be able to perform:

```text
Source payload
      ↓
Mapping
      ↓
FHIR Resource
      ↓
Validation
      ↓
FHIR Server
```

This is one of the capabilities that can eventually differentiate the component from a simple FHIR client library.

---

# Scope

Implement a minimal mapping foundation supporting at least:

```text
External JSON → Patient
```

and:

```text
External JSON → Observation
```

The implementation should demonstrate:

- source field extraction;
- destination FHIR field mapping;
- basic type conversion;
- creation of valid HAPI FHIR R4 resources;
- validation of required mapping inputs;
- deterministic behavior;
- unit tests;
- integration verification where appropriate.

---

# Non-goals

Do not implement:

- HL7 v2 parsing;
- CDA parsing;
- X12;
- FHIR-to-FHIR generic transformation engine;
- graphical mapping editor;
- database-backed mapping definitions;
- customer-specific EHR mappings;
- scripting engine;
- JavaScript execution;
- arbitrary expression language;
- production-grade rules engine;
- terminology translation between LOINC/SNOMED/etc.;
- full StructureMap implementation.

These may become future tasks.

---

# Architecture

The mapping capability should live in a dedicated package.

Recommended:

```text
lab.healthcare.fhir
│
├── client
├── server
├── auth
├── smart
├── mapping
│   ├── MappingService
│   ├── MappingDefinition
│   ├── FieldMapping
│   └── ...
└── exception
```

Do not place mapping classes under:

```text
client
```

unless there is a strong documented reason.

---

# Architectural principle

Separate:

```text
FHIR client
```

from:

```text
data transformation
```

`FhirService` should remain responsible for FHIR operations.

It should not become responsible for:

```text
parsing arbitrary customer JSON
mapping source fields
transforming external payloads
```

Preferred conceptual flow:

```text
External Payload
       ↓
 MappingService
       ↓
 FHIR Resource
       ↓
 FhirService
       ↓
 IGenericClient
       ↓
 FHIR Server
```

---

# Step 1 — Branch

Create:

```text
feature/fhir-mapping-foundation
```

from `main`.

Do not work directly on `main`.

---

# Step 2 — Define the mapping model

Create a minimal model representing a mapping.

For example:

```text
MappingDefinition
 ├── resourceType
 └── fields[]

FieldMapping
 ├── source
 ├── target
 └── transformation (optional)
```

Conceptual example:

```text
source                 target
------------------------------------------------
patient_id             identifier.value
first_name             name.given[0]
last_name              name.family
date_of_birth          birthDate
```

The implementation does not need to use exactly these class names.

Keep the model simple.

---

# Step 3 — Define source payload

Use a generic JSON representation for the external payload.

For example:

```json
{
  "patient_id": "12345",
  "first_name": "John",
  "last_name": "Smith",
  "date_of_birth": "1980-05-20"
}
```

The mapping layer should not assume that the source system itself is FHIR.

---

# Step 4 — Patient mapping

Implement:

```text
External JSON
      ↓
Patient
```

Minimum fields:

```text
patient_id
first_name
last_name
date_of_birth
```

Expected FHIR representation:

```text
Patient
 ├── identifier.value = 12345
 ├── name.given[0] = John
 ├── name.family = Smith
 └── birthDate = 1980-05-20
```

The resulting object must be an actual HAPI R4:

```text
org.hl7.fhir.r4.model.Patient
```

Do not create a custom class called `Patient` to represent FHIR.

---

# Step 5 — Observation mapping

Implement a small Observation example.

Example external payload:

```json
{
  "patient_id": "12345",
  "code": "85354-9",
  "value": 120,
  "unit": "mmHg"
}
```

Map to:

```text
Observation
 ├── subject.reference
 ├── code.coding[0].code
 └── valueQuantity
```

The Observation may use:

```text
system = http://loinc.org
code = 85354-9
unit = mmHg
```

The terminology value must not be described as validated merely because it was mapped.

Task 009 already established the distinction between:

```text
mapping
```

and:

```text
terminology validation
```

Mapping creates the Coding.

Validation is a separate concern.

---

# Step 6 — Type conversion

Support only basic conversions required by the examples.

Examples:

```text
String → String
String → date
Number → Quantity.value
```

Invalid conversions must fail explicitly.

Example:

```text
date_of_birth = "not-a-date"
```

must not silently create an invalid Patient.

---

# Step 7 — Missing fields

Define deterministic behavior for missing source fields.

For example:

```text
Required source field missing
        ↓
MappingException
```

Do not silently invent clinical data.

Examples:

```text
missing patient_id
missing first_name
invalid birthDate
invalid Observation value
```

should be handled explicitly.

---

# Step 8 — FHIR validation boundary

The mapping layer creates a FHIR Resource.

It does not replace FHIR validation.

Conceptually:

```text
External JSON
      ↓
Mapping
      ↓
FHIR Resource
      ↓
FHIR validation
      ↓
FHIR server
```

If Task 010 validation utilities are reusable, use them.

Do not duplicate validation logic.

---

# Step 9 — Mapping service

Create a service responsible for transformation.

Conceptually:

```text
MappingService
```

with operations similar to:

```text
mapPatient(payload, definition)
mapObservation(payload, definition)
```

The exact API may differ.

The service should:

1. receive the external payload;
2. apply the mapping definition;
3. construct the HAPI FHIR Resource;
4. return the Resource;
5. report mapping errors explicitly.

---

# Step 10 — Do not couple mapping to HTTP

The initial mapping service should not require:

```text
REST Controller
```

and should not call the FHIR server automatically.

Keep transformation separate from transport.

This allows future flows such as:

```text
REST API
   ↓
Mapping
   ↓
FHIR
```

or:

```text
Message Queue
   ↓
Mapping
   ↓
FHIR
```

or:

```text
File
   ↓
Mapping
   ↓
FHIR
```

without rewriting the mapper.

---

# Step 11 — Optional persistence

Do not introduce database persistence in Task 019.

Mapping definitions can remain:

```text
Java objects
```

or:

```text
test fixtures
```

The goal is to prove the architecture before introducing configuration storage.

---

# Step 12 — Unit tests

Create comprehensive unit tests for:

### Patient

```text
valid payload
missing patient_id
missing name
invalid date
```

### Observation

```text
valid payload
missing patient reference
invalid value
missing code
```

### Generic mapping

```text
source field → target field
multiple fields
missing source
unsupported target
```

Tests must verify actual FHIR fields, not just that an object was returned.

Example:

```text
patient.getIdentifierFirstRep().getValue()
patient.getNameFirstRep().getFamily()
patient.getBirthDateElement()
```

---

# Step 13 — Integration test

If useful, create:

```text
FhirMappingIT
```

to demonstrate:

```text
External JSON
      ↓
MappingService
      ↓
Patient / Observation
      ↓
FhirService
      ↓
HAPI
      ↓
GET resource
```

At minimum, demonstrate that a mapped Patient can be sent to the local HAPI server and read back.

Do not create unnecessary integration tests for every mapping field if unit tests already cover them.

---

# Step 14 — Test against existing functionality

The mapping implementation must not break:

```text
Tasks 001–018
```

Especially:

```text
FHIR CRUD
validation
pagination
history
$everything
OAuth
SMART
server configuration
```

---

# Step 15 — Documentation

Create:

```text
docs/fhir/fhir-mapping.md
```

Document:

- why mapping exists;
- source payload;
- mapping definition;
- Patient example;
- Observation example;
- type conversion;
- missing-field behavior;
- relationship with FHIR validation;
- why mapping is independent of transport;
- future possibilities.

Update:

```text
docs/fhir/README.md
docs/roadmap.md
README.md
```

---

# Mapping example

Input:

```json
{
  "patient_id": "12345",
  "first_name": "John",
  "last_name": "Smith",
  "date_of_birth": "1980-05-20"
}
```

Mapping:

```text
patient_id       → Patient.identifier.value
first_name       → Patient.name.given
last_name        → Patient.name.family
date_of_birth    → Patient.birthDate
```

Output:

```text
Patient
 ├── identifier = 12345
 ├── name.given = John
 ├── name.family = Smith
 └── birthDate = 1980-05-20
```

---

# Observation example

Input:

```json
{
  "patient_id": "12345",
  "code": "85354-9",
  "value": 120,
  "unit": "mmHg"
}
```

Mapping:

```text
patient_id → Observation.subject.reference
code       → Observation.code.coding[0].code
value      → Observation.valueQuantity.value
unit       → Observation.valueQuantity.unit
```

Output:

```text
Observation
 ├── subject
 ├── code
 │    └── Coding
 │         ├── system = http://loinc.org
 │         └── code = 85354-9
 └── valueQuantity
      ├── value = 120
      └── unit = mmHg
```

Again:

```text
Mapping ≠ terminology validation
```

The code may be syntactically mapped without being validated against a loaded CodeSystem.

---

# Future architecture

Task 019 should prepare for a future pipeline:

```text
                External Systems
                       │
             ┌─────────┼─────────┐
             ▼         ▼         ▼
            JSON      HL7       CSV
             │
             └─────────┬─────────┘
                       ▼
                Transformation
                       │
                       ▼
                  FHIR R4
                       │
                 Validation
                       │
                       ▼
                    Routing
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
            HAPI      Epic     Other EHR
```

Only the first transformation step is implemented in Task 019.

---

# Commercial relevance

This task begins moving the project from:

```text
FHIR client library
```

toward:

```text
FHIR Integration Platform
```

A future consulting proposal could offer:

### Option A — Custom integration

```text
Build the interoperability layer specifically for the customer.
```

### Option B — Accelerated integration

```text
Use our existing FHIR Integration Service
and customize the mappings/connectors.
```

The second option can reduce implementation time because common integration capabilities become reusable assets.

Task 019 is therefore foundational, but it must remain technically modest.

---

# Acceptance criteria

- [ ] Branch `feature/fhir-mapping-foundation`.
- [ ] Dedicated `mapping` package.
- [ ] Generic external JSON input.
- [ ] Patient mapping implemented.
- [ ] Observation mapping implemented.
- [ ] Basic type conversion implemented.
- [ ] Missing/invalid fields fail explicitly.
- [ ] Actual HAPI R4 resources are produced.
- [ ] Mapping does not perform terminology validation implicitly.
- [ ] Mapping does not depend on HTTP transport.
- [ ] `FhirService` is not overloaded with mapping logic.
- [ ] No database introduced for mapping definitions.
- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Tasks 001–018 remain green.
- [ ] Documentation created and updated.

---

# Dependencies

No new external dependency should be required unless the existing project cannot perform the required JSON parsing.

Prefer libraries already present in the project.

Do not introduce a mapping framework in this task.

---

# Git

Do not commit automatically.

At the end run:

```bash
git status
git diff --stat
git diff
```

Report:

- classes created;
- packages created;
- mapping model;
- supported transformations;
- tests;
- integration results;
- problems encountered;
- architectural decisions.

The commit will be performed separately.

---

# Definition of Done

Task 019 is complete when an external JSON payload can be transformed into valid HAPI FHIR R4 `Patient` and `Observation` resources through a dedicated mapping layer, without coupling the mapping implementation to `FhirService`, OAuth, SMART, or HTTP transport.

The resulting architecture must make it possible to add future source formats and mappings without turning `FhirService` into a transformation engine.

---

# Next step

Do not implement Task 020 as part of this task.

The next task should build on the mapping foundation and address another independent interoperability concern.
