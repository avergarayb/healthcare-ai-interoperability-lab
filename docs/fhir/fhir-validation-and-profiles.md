# FHIR resource validation and profiles

This note teaches how FHIR checks whether a **Resource** is conformant: first against the base R4 definition, then against an extra lab profile. Read it after [fhir-terminology-and-validation.md](fhir-terminology-and-validation.md).

The Java service remains a FHIR **client**. There is no custom validator, no ImplementationGuide publisher, and no DTO.

## Search vs `$validate-code` vs `$validate`

```text
Search
→ find Resources that match stored values

$validate-code
→ is this code valid in a CodeSystem / ValueSet?

$validate
→ is this Resource conformant to FHIR (and optionally a profile)?
```

A Resource can be valid JSON and still fail FHIR validation:

```json
{
  "resourceType": "Observation",
  "id": "invalid-observation"
}
```

That payload parses. It does not satisfy Observation's required elements (`status`, `code`). FHIR validation is not JSON Schema.

`$validate-code` on LOINC `85354-9` asks a terminology question. `$validate` on `Observation/obs-001` asks a resource-conformance question. They share a name fragment and nothing else.

## Validation model

```text
FHIR Resource
      ↓
Base StructureDefinition (R4 Observation)
      ↓
optional Profile (constraint)
      ↓
cardinality, datatypes, bindings, invariants
      ↓
$validate
      ↓
OperationOutcome (issues, not a boolean)
```

Local HAPI answers `$validate` with HTTP **200** and an `OperationOutcome` even when issues have `severity=error`. HTTP 200 means the operation ran. Look at issue severity.

## Base validation vs profile validation

```text
Base resource validation
→ http://hl7.org/fhir/StructureDefinition/Observation

Profile validation
→ additional constraints for a use case
```

A profile does **not** create a new Resource type. The instance is still an Observation:

```text
Observation
      ↓
Lab Blood Pressure Observation Profile
```

## StructureDefinition

`StructureDefinition` is the FHIR Resource that describes structure and constraints.

| Field | Role in this lab |
|---|---|
| `url` | canonical identity of the profile |
| `name` / `title` | human labels |
| `status` | `active` |
| `kind` | `resource` |
| `type` | `Observation` — still the same type |
| `baseDefinition` | which definition this one specializes |
| `derivation` | `constraint` (not a new type; extra rules) |
| `differential` | only the changes this profile introduces |
| `snapshot` | the complete resulting structure |

`baseDefinition` + `derivation=constraint` means: start from R4 Observation, then apply extra rules. It is not a fork of the type.

### Differential vs snapshot

```text
Differential
→ only the changes (subject 0..1 → 1..1, value[x] 0..1 → 1..1)

Snapshot
→ every element of Observation after those changes
```

This lab stores a **differential-only** StructureDefinition. HAPI can still validate against it. `POST /StructureDefinition/$snapshot` can materialize a snapshot (about 50 elements for this profile). Tests do not require persisting that snapshot.

## CapabilityStatement

```http
GET /metadata
```

Local HAPI **advertises** `validate` on Observation (and on every other resource type) as `OperationDefinition/Multi-it-validate`. It is instance-level and type-level. Advertised support is not a guarantee for every profile or terminology scenario — this lab still verified the live operation.

Observed OperationDefinition inputs:

| Parameter | Use |
|---|---|
| `resource` | Resource to validate (type-level POST body) |
| `mode` | optional |
| `profile` | canonical URL; on this server the **query** form works |

## Observed `$validate` HTTP

Instance (stored resource):

```http
GET /Observation/obs-001/$validate
```

Type (body is the Resource):

```http
POST /Observation/$validate
Content-Type: application/fhir+json
```

Explicit profile (query parameter — this is the form HAPI honored):

```http
POST /Observation/$validate?profile=https://example.org/fhir/StructureDefinition/lab-blood-pressure-observation
```

A `Parameters` body with `profile` as `valueUri` or `valueCanonical` returned `Invalid profile. Failed to retrieve profile` on this server. Do not use that form here.

### Valid `Observation/obs-001` (base)

HTTP **200**. Issues are **warnings** (unknown LOINC CodeSystem, missing narrative, performer, `effective[x]`). No `error`.

### Invalid Observation (`resourceType` + `id` only)

HTTP **200**. Errors include:

```text
Observation.status: minimum required = 1, but only found 0
  (from http://hl7.org/fhir/StructureDefinition/Observation|4.0.1)

Observation.code: minimum required = 1, but only found 0
```

Missing `subject` on an otherwise complete Observation is only a **best-practice warning** in base R4 (`0..1`).

## OperationOutcome

```text
OperationOutcome
    └── issue[]
          ├── severity   error | warning | information | fatal
          ├── code       processing (observed here)
          ├── diagnostics
          ├── location
          └── expression
```

Not every field is always populated. Several issues can appear together. This lab keeps `OperationOutcome`; it does not collapse `$validate` to a boolean-only API. `hasErrorIssue` is a helper for tests, not the HTTP contract.

## Synthetic lab profile

Canonical URL:

```text
https://example.org/fhir/StructureDefinition/lab-blood-pressure-observation
```

File: `scripts/fhir/profiles/lab-blood-pressure-observation.json`

Cardinality teaching:

```text
Observation.subject     0..1  →  1..1
Observation.value[x]    0..1  →  1..1
```

`0..1` means optional. `1..1` means required exactly once.

### How the profile is loaded

The StructureDefinition is **PUT** into the same local HAPI that stores Patients. Same pattern as synthetic CodeSystem in the terminology task. No second server. No external profile registry.

```http
PUT /StructureDefinition/lab-blood-pressure-observation
```

`$validate` of the profile itself returns HTTP 200 with only the `dom-6` narrative warning.

### Profile results (observed)

Observation with `subject` + `valueQuantity` against the profile: warnings only (same LOINC/narrative class as base).

Observation with status, code, and value but **no subject**:

```text
error  Observation.subject: minimum required = 1, but only found 0
       (from https://example.org/fhir/StructureDefinition/lab-blood-pressure-observation)
```

The same Observation **without** `?profile=` and **without** `meta.profile` does **not** produce that error. That is the profile constraint, not base FHIR.

## `meta.profile`

```json
"meta": {
  "profile": [
    "https://example.org/fhir/StructureDefinition/lab-blood-pressure-observation"
  ]
}
```

This is a **declaration**: “I intend this Resource to conform to this profile.”

```text
meta.profile  ≠  proof of conformance
```

On this HAPI, `$validate` **does** use declared `meta.profile` URLs as profiles to check. A Resource can declare the lab profile, omit `subject`, and still fail. The declaration was present; conformance was not. Proof is the `OperationOutcome`, not the meta field.

## HAPI FHIR Java (8.10.0)

Inspected API (do not assume extra fluent methods):

```text
IGenericClient.validate()
  → IValidate.resource(IBaseResource | String)
  → IValidateUntyped.execute()
  → MethodOutcome
```

`IValidateUntyped` has **no** `withProfile`. `validate().resource(r)` always wraps the Resource in `Parameters` and, if `r` has a logical ID, calls **instance** `$validate` (`GET /Observation/{id}/$validate`). That 404s for an in-memory invalid Observation that was never stored.

This lab therefore copies the Resource and clears the ID so HAPI posts **type-level** `$validate`. That matches:

```http
POST /Observation/$validate
```

with a `Parameters` body whose `resource` parameter is the Observation.

On this server, a `Parameters` `profile` input (`valueUri` / `valueCanonical`) returns `Invalid profile. Failed to retrieve profile`. `POST /Observation/$validate?profile=...` with a **raw Observation body** works. The Java client cannot send that raw-body + query form through `IValidate`. What **does** work through `validate().resource()` is nested `meta.profile` on the Observation inside Parameters — local HAPI then applies that profile. `FhirService.validateResourceAgainstProfile` copies the Resource, clears the ID, adds the canonical URL to `meta.profile`, and calls `validate()`. That does not mutate the caller's Resource and is not treated as proof of conformance.

```java
fhirClient.validate()
        .resource(typeLevelCopy)
        .execute();
```

`FhirService.validateResource` / `validateResourceAgainstProfile` return `MethodOutcome`. `operationOutcome`, `issueDiagnostics`, and `hasErrorIssue` read the issues. `declaredProfiles` reads `meta.profile` on the original Resource and does not validate.

## Out of scope

No custom validator, FSH/SUSHI, US Core, IPS, external IG registry, `$expand`, `$lookup`, `$translate`, or extra microservices.
