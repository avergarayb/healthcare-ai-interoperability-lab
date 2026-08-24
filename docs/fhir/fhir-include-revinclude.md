# FHIR `_include` and `_revinclude`

This note teaches how FHIR Search can return **related Resources in the same Bundle**. Read it after [fhir-resources-and-references.md](fhir-resources-and-references.md).

The Java service is still a FHIR **client**. There is no REST controller, no DTO, and no generic graph engine.

## Direction of the reference

The synthetic data still looks like this:

```text
Observation/obs-001
        |
        | subject
        v
Patient/patient-001
```

```text
Condition/condition-001
        |
        | subject
        v
Patient/patient-001
```

The arrow always goes **from** Observation/Condition **to** Patient. `_include` and `_revinclude` are two ways to walk that arrow during search.

## Baseline: search without include

```http
GET /Observation?patient=patient-001
```

This means: *find Observations for this Patient*. The Bundle contains `Observation/obs-001`. It does **not** contain the Patient.

If the client also needs the Patient body, it would normally make a second request:

```text
GET /Observation?patient=patient-001
        ↓
Observation/obs-001  (subject = Patient/patient-001)
        ↓
GET /Patient/patient-001
        ↓
Patient/patient-001
```

That is two round trips. `_include` / `_revinclude` can collapse them into one search **when you actually need the related resource**. They are not always better: they enlarge the Bundle and can surprise clients that expected a single resource type.

## `_include` — follow references FROM the result

```text
_include

Observation
    |
    | subject
    v
Patient
```

`_include` starts with the resources the search already returned, then follows a **forward** reference on those resources.

```http
GET /Observation?patient=patient-001&_include=Observation:subject
```

| Piece | Meaning |
|---|---|
| `/Observation` | primary resource type |
| `patient=patient-001` | search filter |
| `_include` | also return referenced resources |
| `Observation:subject` | follow the `subject` element on each matching Observation |

`subject` is the FHIR element. `Observation:subject` is the include path (`Resource:searchParam-or-element`).

Expected identities (order is **not** guaranteed):

```text
Observation/obs-001
Patient/patient-001
```

HAPI:

```java
fhirClient.search()
    .forResource(Observation.class)
    .where(Observation.PATIENT.hasId("patient-001"))
    .include(Observation.INCLUDE_SUBJECT)
    .returnBundle(Bundle.class)
    .execute();
```

| Call | Meaning |
|---|---|
| `search()` | FHIR search |
| `forResource(Observation.class)` | `/Observation` |
| `where(Observation.PATIENT.hasId(...))` | `?patient=` |
| `include(Observation.INCLUDE_SUBJECT)` | `&_include=Observation:subject` |
| `returnBundle(Bundle.class)` | parse a searchset |
| `execute()` | send HTTP |

`Observation.INCLUDE_SUBJECT` is HAPI's constant for that include path. It is the same idea as `Observation:subject` on the wire.

This is **not** the same as `GET /Observation?patient=patient-001` alone. The filter finds Observations; `_include` additionally pulls in the Patient they reference.

## `_revinclude` — find resources that POINT AT the result

```text
_revinclude

Patient
   ^
   |
 subject
   |
Observation
```

`_revinclude` starts with the primary search result, then finds **other** resources whose reference points at it.

```http
GET /Patient?_id=patient-001&_revinclude=Observation:subject
```

| Piece | Meaning |
|---|---|
| `/Patient` | primary resource |
| `_id=patient-001` | that Patient |
| `_revinclude` | also return resources that reference it |
| `Observation:subject` | Observations whose `subject` is this Patient |

Expected:

```text
Patient/patient-001
Observation/obs-001
```

HAPI:

```java
fhirClient.search()
    .forResource(Patient.class)
    .where(Patient.RES_ID.exactly().code("patient-001"))
    .revInclude(Observation.INCLUDE_SUBJECT)
    .returnBundle(Bundle.class)
    .execute();
```

`Patient.RES_ID` is the `_id` search parameter. `revInclude(...)` is `_revinclude`. The **same** `Observation.INCLUDE_SUBJECT` constant is used, but the direction is reversed: include follows it from Observation; revInclude uses it to find Observations pointing at the Patient.

`include()` vs `revInclude()`:

| Method | HTTP | Direction |
|---|---|---|
| `include()` | `_include` | from match → referenced resource |
| `revInclude()` | `_revinclude` | from match ← resources that reference it |

## Condition uses the same Patient

```http
GET /Patient?_id=patient-001&_revinclude=Condition:subject
```

```java
.revInclude(Condition.INCLUDE_SUBJECT)
```

Expected: `Patient/patient-001` and `Condition/condition-001`. Observation and Condition are different types that can both reference the same Patient.

## Combined `_revinclude`

HAPI accepts more than one `revInclude()`:

```http
GET /Patient?_id=patient-001&_revinclude=Observation:subject&_revinclude=Condition:subject
```

```java
.revInclude(Observation.INCLUDE_SUBJECT)
.revInclude(Condition.INCLUDE_SUBJECT)
```

Expected identities:

```text
Patient/patient-001
Observation/obs-001
Condition/condition-001
```

## Comparison

| Feature | `_include` | `_revinclude` |
|---|---|---|
| Primary search | Resource A (Observation) | Resource B (Patient) |
| Direction | A → referenced resource | resources → B |
| Example | Observation → Patient | Patient ← Observation |
| Search | `/Observation?patient=patient-001&_include=Observation:subject` | `/Patient?_id=patient-001&_revinclude=Observation:subject` |
| Result | `obs-001` + `patient-001` | `patient-001` + `obs-001` |

## Bundles with more than one Resource type

A searchset is not "a list of Observation". After include/revinclude it can mix types:

```text
Bundle
 ├── Observation/obs-001
 └── Patient/patient-001
```

or

```text
Bundle
 ├── Patient/patient-001
 ├── Observation/obs-001
 └── Condition/condition-001
```

Inspect `entry[].resource` and its actual type. `FhirService.resourceIdentities()` returns strings like `Observation/obs-001`. Never assume `entry[0]` is the primary resource.

## When to use this

Useful when the next screen needs the related resource and you want one HTTP call.

Not automatic policy: larger Bundles, extra server work, and mixed types. This lab does **not** use `_include` on every search. Search without include remains the default.

## Tests

```bash
cd services/fhir-integration-service
mvn test
mvn verify -Pintegration
```

Unit tests mock `IGenericClient`. Integration tests need local HAPI and the synthetic Patients / Observation / Condition.
