# FHIR advanced search

This note teaches **more expressive FHIR Search** against local HAPI FHIR. Read it after [fhir-search.md](fhir-search.md) and [fhir-crud-write-operations.md](fhir-crud-write-operations.md).

The Java service is still a FHIR **client**. There is no generic query builder, no search DTO, and no public REST controller.

## Read versus search (recap)

```http
GET /Patient/patient-001
```

returns **one** Patient, or 404/410. The logical ID is in the path.

```http
GET /Patient?name=Maria
```

returns a **Bundle** of type `searchset`. Matches can be zero, one, or many.

```text
Read  → one known Resource by logical ID
Search → matching Resources in Bundle/searchset
```

## The search Bundle

```text
Bundle
├── type = searchset
├── total          how many Resources match (server-wide, not just this page)
├── entry[]        the Resources on this page
└── link[]         self, next, previous, …
```

`total` is not `entry.length`. `_count` sizes the page. Pagination, when needed, is a `link` with `relation = next`, not a URL we invent.

## Multiple parameters are AND

```http
GET /Patient?name=Maria&gender=female
```

```text
name = Maria
AND
gender = female
```

Different search parameters combine as **AND**. Juan Garcia (`patient-002`) is named Garcia but is male, so he is out. Maria Garcia and Maria Lopez remain.

Do not assume OR between different parameters. Repeating the **same** parameter (OR vs AND) is server-defined; this lab does not generalize that case.

### HAPI FHIR Java

```java
fhirClient.search()
        .forResource(Patient.class)
        .where(Patient.NAME.matches().value("Maria"))
        .and(Patient.GENDER.exactly().code("female"))
        .returnBundle(Bundle.class)
        .execute();
```

`.and(...)` is the second criterion. It is not a Java `&&` on objects we already loaded.

## Search parameter versus Resource element

| Kind | Example | Where it lives |
|---|---|---|
| Resource element | `Condition.clinicalStatus` | JSON body of the Condition |
| Search parameter | `clinical-status` | Query string: `?clinical-status=active` |

The names are related and **not** identical. Hyphens appear in search parameter names. HAPI maps them to constants such as `Condition.CLINICAL_STATUS`.

## Observation: patient + code

```http
GET /Observation?patient=patient-001&code=85354-9
```

| Parameter | Meaning |
|---|---|
| `patient` | search on the Observation's subject/patient relationship |
| `code` | coded concept (here LOINC `85354-9`) |

Expected seeded match: `Observation/obs-001`.

```java
.where(Observation.PATIENT.hasId("patient-001"))
.and(Observation.CODE.exactly().code("85354-9"))
```

`code=85354-9` is a token search by code. It is not a string contains on `Observation.code.text`.

## Condition: patient + clinical-status

```http
GET /Condition?patient=patient-001&clinical-status=active
```

Expected seeded match: `Condition/condition-001`.

`clinicalStatus` on the Resource uses the code system `http://terminology.hl7.org/CodeSystem/condition-clinical`. The search parameter is still the token `active`.

```java
.where(Condition.PATIENT.hasId("patient-001"))
.and(Condition.CLINICAL_STATUS.exactly().code("active"))
```

## Modifiers: `name` versus `name:exact`

A **modifier** changes how one search parameter is evaluated.

```http
GET /Patient?name=Maria
GET /Patient?name:exact=Maria
```

On this synthetic set both return `patient-001` and `patient-003` (given name Maria). The modifier is easier to see with a prefix:

| Query | Local HAPI result |
|---|---|
| `name=Gar` | `patient-001`, `patient-002` (family **Garcia**, default string match) |
| `name:exact=Gar` | no seeded Patients (family is Garcia, not Gar) |
| `name:exact=Garcia` | `patient-001`, `patient-002` |
| `name:exact=Maria` | `patient-001`, `patient-003` |

No extra synthetic data was added. Default `name` is not SQL `LIKE`; it is the FHIR string search for that server. `:exact` requires the string to match a name part exactly.

```java
Patient.NAME.matches().value("Maria");       // name=Maria
Patient.NAME.matchesExactly().value("Maria"); // name:exact=Maria
```

This lab does not invent custom modifiers.

## Date prefixes

FHIR date search uses **prefixes**, not SQL operators.

| Prefix | Meaning (FHIR) | Implemented here |
|---|---|---|
| `eq` | equal | no |
| `ne` | not equal | no |
| `lt` | less than / before | yes |
| `le` | less or equal | no |
| `gt` | greater than / after | no |
| `ge` | greater or equal / on or after | yes |
| `sa` | starts after | no |
| `eb` | ends before | no |
| `ap` | approximately | no |

Synthetic birth dates:

| Patient | birthDate |
|---|---|
| `patient-002` Juan Garcia | 1980-08-20 |
| `patient-001` Maria Garcia | 1985-04-12 |
| `patient-003` Maria Lopez | 1990-02-15 |

```http
GET /Patient?birthdate=ge1985-01-01
```

Maria Garcia and Maria Lopez. Juan is out.

```http
GET /Patient?birthdate=lt1990-01-01
```

Juan and Maria Garcia. Maria Lopez is out.

```java
Patient.BIRTHDATE.afterOrEquals().day("1985-01-01"); // ge
Patient.BIRTHDATE.before().day("1990-01-01");        // lt
```

HAPI's `afterOrEquals` / `before` are the typed form of those prefixes. Do not compare date strings in Java and then filter a Bundle.

## `_sort`

```http
GET /Patient?_sort=birthdate
GET /Patient?_sort=-birthdate
```

`birthdate` is a search parameter used as a sort key. `-` means descending. This is not SQL `ORDER BY` and not `_id`.

Among the seeded Patients, ascending is:

```text
patient-002 (1980) → patient-001 (1985) → patient-003 (1990)
```

Descending reverses that. Unfiltered `_sort` still uses HAPI's default `_count` (20). Later lab seeds (`pagelab-*`, history, leftover numeric ids) can push those three ids off the first page. Integration tests walk `next` pages and then check **relative order** of the three ids in the full sorted searchset.

```java
.sort().ascending(Patient.BIRTHDATE);
.sort().descending(Patient.BIRTHDATE);
```

## `_count`, `total`, and `next`

```http
GET /Patient?_count=2
```

`_count` is the **requested page size**. It does not mean "there are only two Patients".

On a server with three seeded Patients:

| Field | Typical value |
|---|---|
| `Bundle.total` | 3 (all matches) |
| `Bundle.entry.length` | 2 (this page) |
| `link[self]` | this search |
| `link[next]` | the following page |

HAPI's `next` URL often uses `_getpages=...`, not a URL we assemble by hand. This lab does not implement a pagination service. It reads `Bundle.link` when the server sends it.

```java
fhirClient.search()
        .forResource(Patient.class)
        .count(2)
        .returnBundle(Bundle.class)
        .execute();
```

## Combined search

```http
GET /Observation?patient=patient-001&code=85354-9&_sort=-date&_count=10
```

| Piece | Role |
|---|---|
| `patient` | AND filter on subject |
| `code` | AND filter on LOINC `85354-9` |
| `_sort=-date` | newest first by Observation `date` (effective) |
| `_count=10` | page size |

`date` is the FHIR Search parameter for Observation timing (`Observation.DATE` in HAPI). The seeded `obs-001` has no `effective[x]`; with a single match, sort still returns that one Observation.

```java
.where(Observation.PATIENT.hasId("patient-001"))
.and(Observation.CODE.exactly().code("85354-9"))
.sort()
.descending(Observation.DATE)
.count(10)
```

## Out of scope

Not implemented: chained search, `_has`, `_elements`, `_summary`, `$everything`, a generic search engine, or PATCH-style query languages.
