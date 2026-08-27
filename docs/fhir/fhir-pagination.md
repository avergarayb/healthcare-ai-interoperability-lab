# FHIR pagination and result control

This note teaches how FHIR splits large search results into pages. Read it after [fhir-advanced-search.md](fhir-advanced-search.md), which introduced `_count` without walking pages.

The Java service remains a FHIR **client**. There is no pagination UI and no generic paging framework.

## Why pagination exists

```http
GET /Patient
```

can match far more Resources than a client should download at once.

```text
100,000 Patients
       ↓
Page 1
Page 2
Page 3
...
```

The server returns one `searchset` page. The client follows `Bundle.link` until there is no `next`.

Pagination is **not** `$everything` and **not** Bulk Data `$export`. Those are different operations. This lab does not implement them.

## `_count` vs `total` vs `entry`

```http
GET /Patient?family=PageLab&_count=3
```

| Field | Meaning |
|---|---|
| `_count` | requested page size (not a guarantee) |
| `Bundle.total` | number of **matches**, when the server includes it |
| `Bundle.entry.length` | Resources on **this** page (matches plus any `_include` / `_revinclude`) |

Do not assume `Bundle.total == Bundle.entry.size` when paging is active.

Observed on local HAPI:

| Search | `total` | `entry.length` | `next` |
|---|---|---|---|
| `GET /Patient?family=PageLab&_count=3` | **12** | 3 | yes |
| `GET /Patient?_count=3` (unbounded) | **omitted** | 3 | yes |
| `GET /Patient?name=Maria&_count=2` | **2** | 2 | no (both Marias fit) |

`_count` is a request. This HAPI honored 3 and 2 for those searches. A server may still cap the page. Clients must read `entry` and `link`, not invent offsets.

## Pagination model

```text
Search
  ↓
Bundle/searchset
  ├── total        (optional)
  ├── entry[]      this page
  └── link[]
       ├── self
       ├── first      (not sent by this HAPI)
       ├── previous   (from page 2 onward)
       ├── next       (until the last page)
       └── last       (not sent by this HAPI)
```

The server decides which relations appear. On this HAPI, `first` and `last` were **absent**. Page 1 had `self` + `next`. Middle pages had `self` + `next` + `previous`. The last page had `self` + `previous` only.

## Server-controlled next URL

Do not reconstruct the next page.

HAPI's `next` looks like:

```text
http://localhost:8080/fhir?_getpages={uuid}&_getpagesoffset=3&_count=3&_bundletype=searchset
```

Follow that URL as returned. `_getpages` is a server paging token, not a public search parameter we design.

## Synthetic dataset

Twelve Patients, family `PageLab`, given names `P001` … `P012`, logical IDs `pagelab-patient-001` … `pagelab-patient-012`, identifiers `MRN-PAG-001` … `MRN-PAG-012`. The family is not `Maria`/`Pagination` so existing `name=Maria` tests still match only `patient-001` and `patient-003`.

`GET /Patient?name=Maria&_count=2` matches those two seeded Marias. With `_count=2` they fit on one page, so that search is a poor multi-page demo. Multi-page search in this lab is:

```http
GET /Patient?family=PageLab&_count=3
```

Seed: `SyntheticPaginationPatients` (same PUT-by-id pattern as `SyntheticPatients`).

Logical ID is not the identifier. Pagination does not rewrite either.

## Raw HTTP pages (`family=PageLab`, `_count=3`)

```text
Page 1:
GET /Patient?family=PageLab&_count=3
ids: pagelab-patient-001, 002, 003
links: self, next

Page 2:
GET <server next>
ids: 004, 005, 006
links: self, next, previous

Page 3:
GET <server next>
ids: 007, 008, 009
links: self, next, previous

Page 4:
GET <server next>
ids: 010, 011, 012
links: self, previous
(no next)
```

`searchset` throughout. Pagination changes page size, not Bundle type.

## `_include` / `_revinclude` (observed)

```http
GET /Observation?patient=patient-001&_include=Observation:subject&_count=1
```

`total=2` (matching Observations). `entry.length=2` on page 1: `Observation/obs-001` **and** included `Patient/patient-001`. `_count` limits **matches**, not the length of `entry[]` after includes. A `next` link remained because another Observation matched.

```http
GET /Patient?_id=patient-001&_revinclude=Observation:subject&_count=1
```

`total=1` (one Patient). `entry.length=3`: Patient plus reverse-included Observations. No `next`.

Pagination still applies to the searchset. Included Resources share that Bundle.

## HAPI FHIR Java (8.10.0)

Inspected API:

```text
IQuery.count(int)                 → _count
IGenericClient.loadPage()
  .next(bundle).execute()         → follow Bundle.link next
  .previous(bundle).execute()     → follow previous (not required here)
  .byUrl(url).andReturnBundle(...)
```

```java
fhirClient.search()
        .forResource(Patient.class)
        .where(Patient.FAMILY.matches().value("PageLab"))
        .count(3)
        .returnBundle(Bundle.class)
        .execute();

fhirClient.loadPage()
        .next(page1)
        .execute();
```

`FhirService.searchPatientsByFamilyWithCount` / `searchPatientsByNameWithCount` return the first page Bundle. `nextPage` uses `loadPage().next`. `fetchAllPages` walks `next` until it is absent.

Safeguards on `fetchAllPages`:

- stop when there is no `next`;
- reject a repeated next URL (avoids a loop);
- cap at 20 pages (this lab's dataset is 4 pages at `_count=3`).

Existing `searchPatientsWithCount` remains the unbounded `GET /Patient?_count=...` helper from advanced search.

## Out of scope

No `$everything`, `$export`, UI pager, or pagination engine for every Resource type.
