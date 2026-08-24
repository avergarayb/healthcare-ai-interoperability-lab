# FHIR search chaining and `_has`

This note teaches how FHIR Search can **walk References** without the client loading each Resource. Read it after [fhir-advanced-search.md](fhir-advanced-search.md) and [fhir-include-revinclude.md](fhir-include-revinclude.md).

The Java service remains a FHIR **client**. There is no generic query language and no graph engine.

## Why chaining exists

A Patient search only sees Patient fields:

```http
GET /Patient?name=Maria
```

Clinical facts live on other Resources. Example: *Patients who have an Observation coded LOINC `85354-9`*.

Without chaining, the application would:

```text
1. Search Observation by code
2. Read each Observation.subject
3. Read or search those Patients
4. Merge the result set
```

FHIR Search can express the relationship **in one query**.

## Relationship graph (synthetic)

```text
Observation/obs-001
        |
        | subject / patient
        v
Patient/patient-001   (Maria Garcia, MRN-10001)
        ^
        |
        | subject / patient
Condition/condition-001
```

## Chained search

The chain starts at the Resource type in the path. The dotted search parameter walks a Reference, then a field on the target.

```text
Chained search

Observation
    |
    | patient
    ↓
Patient
    |
    | name
    ↓
Maria
```

```http
GET /Observation?patient.name=Maria
```

| Piece | Meaning |
|---|---|
| `/Observation` | primary type (what the Bundle contains) |
| `patient` | Observation search parameter for the subject Reference |
| `.name` | Patient search parameter, evaluated on the referenced Patient |

The server filters Observations whose subject is a Patient named Maria. The primary result is still **Observation**, not Patient.

Synthetic match: `Observation/obs-001` (subject `Patient/patient-001`, given name Maria).

### HAPI FHIR Java (8.10.0)

```java
fhirClient.search()
        .forResource(Observation.class)
        .where(Observation.PATIENT.hasChainedProperty(
                Patient.NAME.matches().value("Maria")))
        .returnBundle(Bundle.class)
        .execute();
```

`ReferenceClientParam.hasChainedProperty(ICriterion)` is the typed form of `patient.name`.

## Chaining plus a local criterion (AND)

```http
GET /Observation?patient.name=Maria&code=85354-9
```

```text
patient.name=Maria     → walk the Reference
AND
code=85354-9           → Observation.code (LOINC)
```

Still **one** search. The client does not fetch the Patient first.

```java
.where(Observation.PATIENT.hasChainedProperty(Patient.NAME.matches().value("Maria")))
.and(Observation.CODE.exactly().code("85354-9"))
```

Result: `Observation/obs-001`.

## Chain through Condition

```http
GET /Condition?patient.name=Maria&clinical-status=active
```

```text
Condition
    |
    | patient
    ↓
Patient
    |
    | name
    ↓
Maria
```

`clinical-status` is the **search parameter**. `Condition.clinicalStatus` is the **Resource element**. They are related and not the same string.

Result: `Condition/condition-001`.

```java
.where(Condition.PATIENT.hasChainedProperty(Patient.NAME.matches().value("Maria")))
.and(Condition.CLINICAL_STATUS.exactly().code("active"))
```

## Chained search is not `_include`

| | Chained search | `_include` |
|---|---|---|
| Example | `GET /Observation?patient.name=Maria` | `GET /Observation?patient=patient-001&_include=Observation:subject` |
| Purpose | **Filter** Observations using a Patient field | **Return** the referenced Patient in the same Bundle |
| Typical identities | `Observation/obs-001` | `Observation/obs-001`, `Patient/patient-001` |

Chaining changes *which* primary Resources match. `_include` changes *what extra* Resources are added after the match.

## `_has` — reverse chaining

Problem: start from **Patient**, but the matching data is on Observation.

```text
_has

Patient
   ↑
   |
Observation.patient
   |
Observation.code = 85354-9
```

```http
GET /Patient?_has:Observation:patient:code=85354-9
```

| Token | Meaning |
|---|---|
| `_has` | reverse chain |
| `Observation` | type that **points at** the Patient |
| `patient` | search parameter on Observation that references Patient |
| `code` | criterion on that Observation |
| `85354-9` | LOINC code |

The Bundle contains **Patients**. The Observation is a filter, not an entry.

Synthetic match: `Patient/patient-001`.

### HAPI FHIR Java (8.10.0)

HAPI 8.10 has `hasChainedProperty` for forward chains. It does **not** expose a fluent `_has(...)` on `IQuery`. Reverse chain uses `HasParam` with `where(Map)`:

```java
Map<String, List<IQueryParameterType>> has = Map.of(
        "_has",
        List.of(new HasParam("Observation", "patient", "code", "85354-9")));

fhirClient.search()
        .forResource(Patient.class)
        .where(has)
        .returnBundle(Bundle.class)
        .execute();
```

`HasParam(targetType, referenceParam, paramName, value)` encodes `_has:Observation:patient:code=85354-9`. This is not a custom query language; it is HAPI's typed `_has` parameter.

## `_has` through Condition

```http
GET /Patient?_has:Condition:patient:clinical-status=active
```

```text
Patient
   ↑
   |
Condition.patient
   |
clinical-status = active
```

Result: `Patient/patient-001`. The Condition is not in the Bundle.

## `_has` versus `_revinclude`

```text
_revinclude

Patient
   ↑
   |
Observation.subject
```

| | `_has` | `_revinclude` |
|---|---|---|
| Example | `GET /Patient?_has:Observation:patient:code=85354-9` | `GET /Patient?_id=patient-001&_revinclude=Observation:subject` |
| Purpose | **Filter** Patients that have a matching Observation | **Add** Observations that point at the matching Patient |
| Typical identities | `Patient/patient-001` | `Patient/patient-001`, `Observation/obs-001` |

```text
_revinclude → add related Resources to the Bundle
_has        → filter the primary Resource using related Resources
```

## Combined `_has` and a Patient parameter

Local HAPI supports:

```http
GET /Patient?_has:Observation:patient:code=85354-9&gender=female
```

AND of reverse chain and `Patient.gender`. Result: `Patient/patient-001` (Maria). Juan Garcia has no matching Observation.

```java
.where(hasObservationCode)
.and(Patient.GENDER.exactly().code("female"))
```

## Chained identifier

External systems often know a business identifier, not `Patient/patient-001`.

```http
GET /Observation?patient.identifier=MRN-10001
```

```text
Observation
   |
   | patient
   ↓
Patient
   |
   | identifier
   ↓
MRN-10001
```

Local HAPI matches `Observation/obs-001` with the identifier value alone. `patient.identifier=https://example.org/lab/mrn|MRN-10001` also works (token `system|value`). This lab uses the value form from the task.

```java
.where(Observation.PATIENT.hasChainedProperty(
        Patient.IDENTIFIER.exactly().identifier("MRN-10001")))
```

## Interoperability use

| Need | FHIR Search |
|---|---|
| Observations for people named Maria | `Observation?patient.name=Maria` |
| Same, plus a LOINC code | `...&code=85354-9` |
| Observations for MRN-10001 | `Observation?patient.identifier=MRN-10001` |
| Patients who have that LOINC Observation | `Patient?_has:Observation:patient:code=85354-9` |
| Patient + Observation bodies together | `_include` / `_revinclude` (different task) |

## Out of scope

No generic chain builder, no `_has` combinator library, no `_elements` / `$everything`.
