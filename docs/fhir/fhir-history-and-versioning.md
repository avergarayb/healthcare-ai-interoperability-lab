# FHIR history and resource versioning

This note teaches how FHIR keeps previous versions of a Resource. Read it after [fhir-pagination.md](fhir-pagination.md) and [fhir-crud-write-operations.md](fhir-crud-write-operations.md).

The Java service remains a FHIR **client**. There is no event-sourcing framework and no public history API of our own.

## Why history exists

The current Resource is the latest state:

```http
GET /Patient/history-patient-001
```

That is not enough when an interoperability system also needs:

```text
What did this Patient look like yesterday?
When did the name change?
Which version did we send to the other system?
```

```text
Patient/history-patient-001
        │
        ├── version 1   given V1
        ├── version 2   given V2
        └── version 3   given V3  ← current
```

An update is not “overwrite and forget” on a server that keeps history. PUT creates a **new version** of the same logical ID.

## Logical ID vs version ID

| Identity | What it names | Example |
|---|---|---|
| Logical ID | the Resource across versions | `history-patient-001` |
| Version ID | one snapshot on **this** server | `1`, `2`, `3` |

Do not treat version IDs as globally meaningful. They belong to that Resource’s history on that FHIR server.

Identifier (`MRN-HIST-001`) is a third thing. History does not rewrite it.

## `meta.versionId` and `meta.lastUpdated`

Observed current read:

```http
GET /Patient/history-patient-001
```

```json
"meta": {
  "versionId": "3",
  "lastUpdated": "2026-08-27T00:31:44.669+00:00"
}
```

`id` stayed `history-patient-001`. `meta.versionId` moved `1` → `2` → `3` after each write.

## HTTP headers vs FHIR metadata

This HAPI returns both. They are related, not interchangeable.

| Header | Observed | Related FHIR field |
|---|---|---|
| `ETag` | `W/"3"` | `meta.versionId` = `3` |
| `Last-Modified` | `Thu, 27 Aug 2026 00:31:44 GMT` | `meta.lastUpdated` |
| `Content-Location` | `.../Patient/history-patient-001/_history/3` | version-specific URL |

`ETag` is a weak validator (`W/"…"`). `meta.versionId` is the FHIR field. Do not assume every client library sends the header in the same spelling (see If-Match below).

## Create multiple versions

Synthetic Patient `history-patient-001` (family `History`, identifier `MRN-HIST-001`):

```http
PUT /Patient/history-patient-001
```

| Write | given | `id` | `meta.versionId` | HTTP |
|---|---|---|---|---|
| first PUT | V1 | `history-patient-001` | `1` | `201` or `200` |
| second PUT | V2 | `history-patient-001` | `2` | `200` |
| third PUT | V3 | `history-patient-001` | `3` | `200` |

The first write of a new id was `201` with `ETag: W/"1"`. Later PUTs were `200` with a new ETag.

This HAPI recorded the **first** version in history as `POST` / `201 Created`, even though the client sent PUT. Later versions are `PUT` / `200 OK`. Document the server’s history labels; do not rewrite them as the HTTP verb you typed.

## Instance history

```http
GET /Patient/history-patient-001/_history
```

```text
GET /Patient/{id}/_history
              ↓
        Bundle/history
              ↓
           entry[]
              ├── resource
              ├── request
              └── response
```

Observed on this HAPI:

| Field | Present? |
|---|---|
| `Bundle.type` | `history` |
| `Bundle.total` | yes (`3` after three writes) |
| `entry.fullUrl` | `http://localhost:8080/fhir/Patient/history-patient-001` |
| `entry.resource` | Patient snapshot (except DELETE entries) |
| `entry.request.method` | `POST` / `PUT` / `DELETE` |
| `entry.request.url` | `Patient/{id}/_history/{vid}` |
| `entry.response.status` | `201 Created` or `200 OK` |
| `entry.response.etag` | `W/"1"`, `W/"2"`, … |
| `entry.response.location` | **not** in instance history entries |
| `entry.response.lastModified` | **not** in instance history entries |

Newest version is **first**. That is this server’s order, not a client sort.

`history` is not `searchset`, not `transaction-response`, and not `batch-response`.

## Version-specific read

Version IDs come from the server. Do not hardcode them in tests.

```http
GET /Patient/history-patient-001/_history/1
```

HTTP `200`, same logical ID, `meta.versionId` = `1`, given = `V1`.

```http
GET /Patient/history-patient-001
```

HTTP `200`, same logical ID, `meta.versionId` = `3`, given = `V3`.

```text
current read
    ↓
latest version

version-specific read
    ↓
requested historical version
```

## Delete and history

```http
PUT /Patient/history-delete-001
DELETE /Patient/history-delete-001
GET /Patient/history-delete-001
GET /Patient/history-delete-001/_history
GET /Patient/history-delete-001/_history/1
```

Observed:

| Request | Result |
|---|---|
| current GET after DELETE | **410 Gone** (`ResourceGoneException`). `Location: .../_history/2` |
| instance history | still `200`, `type=history`, `total=2` |
| DELETE history entry | **no** `resource`; `request.method=DELETE`; `response.status=200 OK`; `etag=W/"2"` |
| `GET .../_history/1` | still `200` with the pre-delete Patient |

DELETE itself is a new version. Current read is gone. History remains. A DELETE of an id that never existed was `200` with `SUCCESSFUL_DELETE_NOT_FOUND` and later GET was `404`, not `410`.

## Optimistic concurrency (`If-Match`)

Two systems must not silently overwrite each other.

```http
PUT /Patient/history-patient-001
If-Match: 3
```

When `3` was the current `meta.versionId`, this HAPI accepted the write (`200`, new `ETag: W/"4"`).

```http
PUT /Patient/history-patient-001
If-Match: W/"999999"
```

HTTP **409** `ResourceVersionConflictException`: not the current version. The Patient was unchanged.

The GET response advertises `ETag: W/"3"`. This HAPI also accepted a **bare** version id (`If-Match: 3`). A mangled value such as `W/3` (quotes stripped by the shell) was rejected as a non-current version. HAPI Java sends `If-Match: W/"{versionId}"` via `withAdditionalHeader`.

```text
correct version
    ↓
update accepted

wrong version
    ↓
409 Conflict
```

## Searchset vs history

```http
GET /Patient?name=Maria
```

`Bundle.type = searchset` — matching **current** Patients (`patient-001`, `patient-003`).

```http
GET /Patient/patient-001/_history
```

`Bundle.type = history` — versions/events for **one** Resource.

| | searchset | history |
|---|---|---|
| Question | which Resources match? | what happened to this Resource? |
| Typical entries | current matches | versions, including DELETE |
| Pagination | yes (`_count`, `next`) | yes (`_count`, `next`) |

## Type and system history

Verified on this HAPI (do not invent support):

```http
GET /Patient/_history?_count=2
GET /_history?_count=2
```

Both return `Bundle.type = history` with `next`. Type history had `total=121` in this lab database. System history had `total=160`. The Java service does **not** wrap those broad APIs. Instance history is the production method.

## Pagination of history

Pagination is not limited to `searchset`.

```http
GET /Patient/history-patient-001/_history?_count=1
```

Observed: `type=history`, `total=3`, one entry, `next` =

```text
.../Patient/history-patient-001/_history?_count=1&_offset=1
```

History `next` on this HAPI uses `_offset`, not the `_getpages` token used for search paging. Follow the server URL. `FhirService.nextPage` already does that with `loadPage().next(bundle)`.

Type/system history with `_count=2` also sent `next` (`_offset=2`) and `previous` on later pages.

## HAPI FHIR Java (8.10.0)

Inspected APIs, not guessed:

```text
IGenericClient.history()
  .onInstance(id) | .onType(type) | .onServer()
  .returnBundle(Bundle.class)
  .count(n)
  .execute()

IGenericClient.read()
  .resource(Patient.class)
  .withIdAndVersion(logicalId, versionId)
  .execute()

IGenericClient.vread(Patient.class, logicalId, versionId)

IUpdateExecutable.withAdditionalHeader("If-Match", "W/\"3\"")
IHistoryTyped.count(Integer)
```

Lab methods:

```java
fhirClient.history()
        .onInstance(new IdType("Patient", logicalId))
        .returnBundle(Bundle.class)
        .execute();

fhirClient.read()
        .resource(Patient.class)
        .withIdAndVersion(logicalId, versionId)
        .execute();

fhirClient.update()
        .resource(patient)
        .withAdditionalHeader("If-Match", "W/\"" + versionId + "\"")
        .execute();
```

`getPatientHistory` preserves the FHIR `Bundle`. There is no history DTO.

## Raw HTTP (observed)

```http
PUT /Patient/history-patient-001
→ 201/200  ETag: W/"1"  id=history-patient-001  versionId=1  given=V1

PUT /Patient/history-patient-001
→ 200  ETag: W/"2"  versionId=2  given=V2

PUT /Patient/history-patient-001
→ 200  ETag: W/"3"  versionId=3  given=V3

GET /Patient/history-patient-001
→ 200  ETag: W/"3"  Last-Modified: Thu, 27 Aug 2026 00:31:44 GMT
     Content-Location: .../_history/3

GET /Patient/history-patient-001/_history
→ Bundle type=history  total=3
     entry[0] version 3 PUT 200  etag W/"3"  given V3
     entry[1] version 2 PUT 200  etag W/"2"  given V2
     entry[2] version 1 POST 201 etag W/"1"  given V1

GET /Patient/history-patient-001/_history/1
→ 200  versionId=1  given=V1

DELETE /Patient/history-delete-001
→ 200  Content-Location: .../_history/2

GET /Patient/history-delete-001
→ 410 Gone

GET /Patient/history-delete-001/_history
→ history; DELETE entry has no resource

PUT /Patient/history-patient-001
If-Match: 3
→ 200  versionId=4   (when 3 was current)

PUT /Patient/history-patient-001
If-Match: W/"999999"
→ 409 Conflict
```
