# FHIR mapping foundation

This note adds a **transformation** layer in front of the FHIR client. Read it after [fhir-architecture.md](fhir-architecture.md). It does **not** replace [fhir-validation-and-profiles.md](fhir-validation-and-profiles.md) or [fhir-terminology-and-validation.md](fhir-terminology-and-validation.md).

There is still no `@RestController`, no mapping database, and no HL7 v2 / CDA engine.

## Why mapping exists

A FHIR client speaks `Patient`, `Observation`, and `Reference`. A hospital application often speaks something else:

```json
{
  "patient_id": "12345",
  "first_name": "John",
  "last_name": "Smith",
  "date_of_birth": "1980-05-20"
}
```

That JSON is not a FHIR Resource. Putting field names like `first_name` into `FhirService` would couple every FHIR operation to one customer's payload.

Mapping is the step in between:

```text
External JSON
      ↓
 MappingService
      ↓
 HAPI R4 Resource
      ↓
 FHIR validation   (Task 010, optional at this boundary)
      ↓
 FhirService
      ↓
 FHIR server
```

## Source payload

The mapper accepts a JSON **object**. It does not assume the source is FHIR, HL7 v2, or an EHR vendor model.

Top-level keys in the lab examples:

| Source | Meaning in the external app |
|---|---|
| `patient_id` | Business identifier, not necessarily a FHIR logical id |
| `first_name` / `last_name` | Human name parts |
| `date_of_birth` | Calendar date |
| `code` / `value` / `unit` | Observation payload in the lab example |

## Mapping definition

A mapping is a Java object, not a row in a database:

```text
MappingDefinition
 ├── resourceType   Patient | Observation
 └── fields[]
      ├── source         JSON key (required unless constant)
      ├── target         FHIR path this lab supports
      ├── conversion     STRING | DATE | DECIMAL | PATIENT_REFERENCE
      └── constant       optional literal (LOINC system, Observation.status)
```

Lab fixtures live in `LabMappingDefinitions`. They are examples, not a customer catalog.

Supported Patient targets:

```text
identifier.value
name.given[0]
name.family
birthDate
```

Supported Observation targets:

```text
subject.reference
code.coding[0].code
code.coding[0].system
valueQuantity.value
valueQuantity.unit
status
```

An unknown target throws `MappingException`. That is deliberate: this is a small path writer, not StructureMap.

## Patient example

Input:

```json
{
  "patient_id": "12345",
  "first_name": "John",
  "last_name": "Smith",
  "date_of_birth": "1980-05-20"
}
```

| Source | Target |
|---|---|
| `patient_id` | `Patient.identifier.value` |
| `first_name` | `Patient.name.given[0]` |
| `last_name` | `Patient.name.family` |
| `date_of_birth` | `Patient.birthDate` |

Output is `org.hl7.fhir.r4.model.Patient`, not a custom DTO.

`patient_id` becomes an **identifier**, not `Patient.id`. The FHIR logical id is assigned when `FhirService.createPatient` talks to the server.

## Observation example

Input:

```json
{
  "patient_id": "12345",
  "code": "85354-9",
  "value": 120,
  "unit": "mmHg"
}
```

| Source / constant | Target |
|---|---|
| `patient_id` | `Observation.subject.reference` → `Patient/12345` |
| `code` | `Observation.code.coding[0].code` |
| constant `http://loinc.org` | `Observation.code.coding[0].system` |
| `value` | `Observation.valueQuantity.value` |
| `unit` | `Observation.valueQuantity.unit` |
| constant `final` | `Observation.status` |

`status` and the LOINC **system** are part of the mapping definition. They are not invented when a source field is missing.

```text
Mapping ≠ terminology validation
```

Writing `85354-9` into a Coding does not prove that LOINC is loaded on the server or that `$validate-code` would succeed. Task 009 remains the terminology check.

## Type conversion

| Conversion | Use |
|---|---|
| `STRING` | identifier, names, code, unit |
| `DATE` | `birthDate` as `YYYY-MM-DD` |
| `DECIMAL` | `Quantity.value` |
| `PATIENT_REFERENCE` | `12345` → `Patient/12345` |

Invalid values fail. `date_of_birth = "not-a-date"` does not produce a Patient with a garbage date.

## Missing fields

Required source fields that are absent, null, or blank throw `MappingException`.

The mapper does not invent a name, identifier, or quantity to keep the Resource "complete".

## Validation boundary

`MappingService` constructs a Resource. It does not call `$validate`.

`FhirService.validateResource` from Task 010 is the FHIR validation boundary. The integration test maps, validates, then creates. Those are three different jobs.

## Independent of transport

`MappingService` does not:

- expose a REST controller;
- call HAPI;
- know OAuth or SMART;
- read `fhir.active-server`.

The same mapper can later sit behind a REST API, a queue, or a file drop. Transport is a separate concern from transformation. Destination selection is [fhir-routing.md](fhir-routing.md); mapping does not choose the FHIR server.

## Package

```text
lab.healthcare.fhir.mapping
├── MappingService
├── MappingDefinition
├── FieldMapping
├── MappingConversion
├── MappingException
└── LabMappingDefinitions
```

`FhirService` stays in `client` and still only performs FHIR operations.

## Future

This task only implements JSON → Patient / Observation.

A later pipeline can add HL7 v2, CSV, stored mapping definitions, or routing to another EHR **without** turning `FhirService` into a transformation engine.
