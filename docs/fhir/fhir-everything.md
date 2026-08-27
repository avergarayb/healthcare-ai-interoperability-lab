# FHIR `$everything` and Patient-centric retrieval

This note teaches the Patient `$everything` operation. Read it after [fhir-include-revinclude.md](fhir-include-revinclude.md) and [fhir-pagination.md](fhir-pagination.md).

The Java service remains a FHIR **client**. There is no clinical-summary engine and no Bulk Data `$export`.

```text
$everything ≠ $export
```

`$everything` is one Patient’s related Resources, returned as a Bundle. `$export` is a bulk job for many Patients. This lab does not implement `$export`.

## Why `$everything` exists

A Patient is not one Resource. Clinical context is a graph:

```text
Patient/patient-001
        │
        ├── Observation/obs-001
        ├── Condition/condition-001
        ├── Encounter/encounter-001
        └── MedicationRequest/medreq-001
```

Until now the client chose each query:

```http
GET /Patient/patient-001
GET /Observation?patient=patient-001
GET /Condition?patient=patient-001
```

`$everything` asks the **server** for the Patient-centric set it implements:

```http
GET /Patient/patient-001/$everything
```

That is one operation, not a client-side aggregator.

## Operation vs search

```http
GET /Patient?name=Maria
```

is a **search**. Parameters select matching current Resources. The result is a `searchset`.

```http
GET /Patient/patient-001/$everything
```

is an **operation** (`$` name) on one Patient instance. Parameters belong to the OperationDefinition, not to Patient search.

`$everything` is not a search parameter. You cannot write `GET /Patient?everything=true`.

This HAPI still returns `Bundle.type = searchset` for `$everything`. The HTTP interaction is an operation; the Bundle type is what the server actually sent.

## Advertised vs observed support

`GET /metadata` **advertises** Patient operation `everything` with definition:

```text
http://hl7.org/fhir/OperationDefinition/Patient-everything
```

`GET /OperationDefinition/Patient-everything` on this server is **404**. The CapabilityStatement points at the HL7 URL; the Resource is not stored locally.

**Observed:** `GET /Patient/patient-001/$everything` returns HTTP 200.

Encounter also advertises `everything`. This lab only implements Patient `$everything`.

## Raw HTTP — basic operation

```http
GET /Patient/patient-001/$everything
```

Observed:

| Field | Value |
|---|---|
| HTTP | `200` |
| `Bundle.type` | **`searchset`** (not `collection`) |
| `Bundle.total` | number of compartment matches |
| `Bundle.link` | `self`; `next` only when `_count` pages the result |
| `entry.search.mode` | **`match`** for every entry |

Inventory on the seeded lab Patient (plus any leftover Observations already on that subject):

```text
Patient/patient-001
Condition/condition-001
Observation/obs-001
Encounter/encounter-001
MedicationRequest/medreq-001
Observation/everything-obs-dated
```

Do not assume order. Identity is `resourceType + "/" + id`.

## `$everything` vs `_include` / `_revinclude`

```text
Search + _include
    ↓
controlled search result + referenced resources

Search + _revinclude
    ↓
resources pointing to the search result

$everything
    ↓
Patient-centric operation
```

Observed comparison for `patient-001`:

| Mechanism | Starts from | Patient mode | Related mode | Encounter / MedicationRequest |
|---|---|---|---|---|
| `GET /Observation?patient=…&_include=Observation:subject` | Observation search | `include` | `match` | not returned |
| `GET /Patient?_id=…&_revinclude=Observation:subject&_revinclude=Condition:subject` | Patient search | `match` | `include` | not returned unless revincluded |
| `GET /Patient/{id}/$everything` | Patient operation | `match` | `match` | returned by this HAPI |

They are not interchangeable. `_include` / `_revinclude` extend a **search you designed**. `$everything` is the **server’s Patient compartment** (as that server implements it). A client cannot assume every FHIR server returns the same types.

## Manual aggregation vs one operation

```text
Manual
  GET Patient
  GET Observation?patient=...
  GET Condition?patient=...
  GET Encounter?patient=...
  GET MedicationRequest?patient=...
      ↓
  several round trips
  client decides completeness

$everything
  GET Patient/{id}/$everything
      ↓
  one round trip (plus pages)
  server decides completeness
```

Consistency: one operation sees one server-side snapshot of the compartment (still paged). Manual searches can interleave with writes. Completeness is **implementation-specific**. This HAPI returned Encounter and MedicationRequest for the synthetic subject; another server might omit them.

## Parameters

### `_type` — supported

```http
GET /Patient/patient-001/$everything?_type=Observation
```

Result: Observations only. **Patient is omitted.** Not a mixed Patient+Observation Bundle.

```http
GET /Patient/patient-001/$everything?_type=Observation,Condition
```

Result: Observation and Condition only.

```http
GET /Patient/patient-001/$everything?_type=Patient
```

Result: `Patient/patient-001` only.

### `_count` — supported (pagination)

```http
GET /Patient/patient-001/$everything?_count=1
```

`total` stays the full count; `entry` has 1 Resource; `next` uses `_getpages` (same paging token as search). Follow that URL. `FhirService.nextPage` already does.

### `_start` / `_end` — accepted, no membership change here

```http
GET /Patient/patient-001/$everything?_start=2099-01-01
GET /Patient/patient-001/$everything?_end=2000-01-01
GET /Patient/patient-001/$everything?_end=2019-01-01
```

All still returned the same Resources, including `Observation/everything-obs-dated` with `effectiveDateTime=2020-06-15`. The lab does **not** expose start/end methods. Do not invent date filtering this server did not demonstrate.

## Pagination

```text
$everything?_count=2
    ↓
Bundle/searchset  (page 1 + next)
    ↓
loadPage().next
    ↓
page 2
```

Reuse Task 012. Do not build a second pager.

## Error behavior

```http
GET /Patient/does-not-exist/$everything
```

HTTP **404**, `OperationOutcome`, diagnostics `HAPI-2841: Resource [[TokenParam[system=,value=does-not-exist]]] is not known.`

`FhirService` wraps that in `FhirClientException`. It does not return an empty Bundle.

## HAPI FHIR Java (8.10.0)

Inspected APIs:

```text
IGenericClient.operation()
  .onInstance(IdType)
  .named("$everything")
  .withNoParameters(Parameters.class)
  | withParameter(Parameters.class, name, value)
  .useHttpGet()
  .returnResourceType(Bundle.class)
  .execute()
```

`returnResourceType(Bundle.class)` is required. The default operation return type is `Parameters`. `$everything` returns a Bundle.

```java
fhirClient.operation()
        .onInstance(new IdType("Patient", logicalId))
        .named("$everything")
        .withNoParameters(Parameters.class)
        .useHttpGet()
        .returnResourceType(Bundle.class)
        .execute();

fhirClient.operation()
        .onInstance(new IdType("Patient", logicalId))
        .named("$everything")
        .withParameter(Parameters.class, "_type", new StringType("Observation"))
        .useHttpGet()
        .returnResourceType(Bundle.class)
        .execute();
```

Lab methods: `getPatientEverything(id)`, `getPatientEverything(id, pageSize)`, `getPatientEverythingByTypes(id, types…)`.

## Limitations

- Completeness is this HAPI’s compartment, not a universal clinical record.
- Leftover Observations for `patient-001` (for example a CRUD-test id) also appear. Tests assert **contains**, not an exclusive inventory.
- `_start` / `_end` are not implemented in the client.
- Not `$export`. Not `$everything` on Encounter in this lab.
