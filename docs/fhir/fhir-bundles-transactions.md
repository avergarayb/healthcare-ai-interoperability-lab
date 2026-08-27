# FHIR Bundles, batch, and transaction

This note teaches `Bundle` as more than a search result: it can carry a set of HTTP operations to the FHIR server in one request. Read it after [fhir-crud-write-operations.md](fhir-crud-write-operations.md).

The Java service remains a FHIR **client**. There is no custom transaction engine and no extra HTTP client.

## Bundle is a Resource

Search already returned:

```http
GET /Patient?name=Maria
```

```text
Bundle.type = searchset
entry[].resource = matching Patients
```

`Bundle` is still a FHIR Resource. Its `type` selects the purpose:

| Type | Role in this lab |
|---|---|
| `searchset` | search result (already used) |
| `transaction` | client-sent atomic set of operations |
| `batch` | client-sent independent operations |
| `collection` | grouping without implied HTTP ops |
| `document` | clinical document (out of scope) |
| `message` | messaging (out of scope) |
| `history` | version history (out of scope) |

This lab implements **searchset** (existing), **transaction**, and **batch**.

```text
searchset     → server answers a query
transaction   → client asks the server to apply several operations as one unit
batch         → client asks the server to apply several operations independently
```

## Bundle.entry

```text
Bundle
 └── entry[]
       ├── fullUrl     (optional; urn:uuid:... for new Resources in a transaction)
       ├── resource    payload
       ├── request     HTTP operation to perform (transaction / batch)
       └── response    HTTP result (transaction-response / batch-response)
```

Request example:

```json
"request": {
  "method": "POST",
  "url": "Patient"
}
```

```text
entry.resource  → the Patient / Observation / ...
entry.request   → POST Patient, PUT Patient/{id}, GET Patient/{id}, ...
entry.response  → status, location, etag, optional outcome
```

Searchset entries typically have `resource` (and search metadata). They do **not** carry `request`. Transaction/batch **requests** carry `request`. Transaction/batch **responses** carry `response`.

## searchset vs transaction vs batch

| | searchset | transaction | batch |
|---|---|---|---|
| Who sends it | server (search) | client | client |
| HTTP | `GET /Patient?...` | `POST /` | `POST /` |
| Atomic? | n/a | conceptually all-or-nothing | independent |
| Response type | `searchset` | `transaction-response` | `batch-response` |
| Entry focus | `resource` | `request` then `response` | `request` then `response` |

```text
Bundle ≠ only search results
```

## Observed HTTP — successful transaction

CapabilityStatement `rest.interaction` on this HAPI lists `transaction` and `history-system`. It does **not** list `batch`. `POST` of `type=batch` still works. Advertised support is not the whole story.

```http
POST /fhir
Content-Type: application/fhir+json
```

Body: `scripts/fhir/bundles/patient-observation-transaction.json` (`type=transaction`, Patient + Observation, Observation.subject = `urn:uuid:...`).

Observed:

```text
HTTP 200
Bundle.type = transaction-response
entry[0].response.status = 201 Created
entry[0].response.location = Patient/{id}/_history/1
entry[0].response.etag = 1
entry[1].response.status = 201 Created
entry[1].response.location = Observation/{id}/_history/1
```

Resources are **not** echoed in the response entries by default. Read them back:

```http
GET /Patient/{id}
GET /Observation/{id}
```

`Observation.subject` is rewritten from `urn:uuid:...` to `Patient/{assigned-id}`.

### Temporary vs existing references

```text
Patient (created in this Bundle)
   ↑ subject = urn:uuid:...
Observation
```

versus:

```text
Patient/patient-001  (already on the server)
   ↑ subject = Patient/patient-001
Observation
```

`urn:uuid:` is FHIR's literal temporary identity for a Resource that does not have a logical ID yet. HAPI resolved it. A literal `Patient/patient-001` is a reference to an existing Resource; that also worked (`POST Observation` in a transaction → 201).

## Transaction atomicity (actual HAPI)

Conceptually:

```text
all succeed  OR  none are committed
```

**Verified all-or-nothing:** transaction with `POST Patient` plus `PUT Patient/patient-001` with a stale `If-Match` (`W/"999999"`).

```text
HTTP 409
resourceType = OperationOutcome
HAPI-0550 / HAPI-0989: not the current version
search for the new Patient identifier → total = 0
Patient/patient-001 family still Garcia
```

The POST would have been 201 if it had stood alone. The 409 aborted the Bundle; the new Patient was **not** stored.

**Not atomic on this server:** transaction with `POST Patient` plus `GET Patient/missing`.

```text
HTTP 200
Bundle.type = transaction-response
entry[0] 201 Created
entry[1] 404 Not Found
the POSTed Patient is persisted
```

FHIR R4 says a failed transaction should commit nothing. This HAPI still committed the POST when the other entry was a GET 404. The lab does **not** fake spec atomicity for that case. The `If-Match` experiment is the honest atomicity demo.

Parse errors (invalid `gender`, unknown `request.url`) return HTTP **400** OperationOutcome and persist nothing — that happens **before** execution, for both transaction and batch.

## Batch (actual HAPI)

Same `POST /fhir`, `type=batch`.

Independence demo that worked:

```text
POST Patient
GET Patient/this-patient-does-not-exist-batch
GET Patient/patient-001
```

```text
HTTP 200
Bundle.type = batch-response
entry[0] 201 Created   (Patient stored)
entry[1] 404 Not Found (OperationOutcome HAPI-2001)
entry[2] 200 OK        (resource = Patient/patient-001)
```

`If-Match` mismatch in a **batch** (contrast with transaction):

```text
HTTP 200
entry[0] 201 Created  (new Patient stored)
entry[1] 409 Conflict (Patient/patient-001 unchanged)
```

```text
transaction → 409 + rollback of the POST
batch       → 200 + POST kept, PUT conflict isolated
```

## Conditional create

```text
POST /Patient
If-None-Exist: identifier=https://example.org/lab/mrn|MRN-10001
```

Inside a Bundle:

```json
"request": {
  "method": "POST",
  "url": "Patient",
  "ifNoneExist": "identifier=https://example.org/lab/mrn|MRN-10001"
}
```

Observed:

| Situation | `response.status` | location |
|---|---|---|
| `MRN-10001` already exists | `200 OK` | `Patient/patient-001/_history/1` |
| new identifier | `201 Created` | `Patient/{new-id}/_history/1` |
| same new identifier again | `200 OK` | same `{new-id}` |

No second Patient for Maria. This HAPI supports conditional create cleanly.

## HAPI FHIR Java (8.10.0)

Inspected API:

```text
IGenericClient.transaction()
  → ITransaction.withBundle(Bundle | String)
  → ITransactionTyped.execute()
  → Bundle
```

The **same** `transaction()` call sends both `type=transaction` and `type=batch`. The Bundle `type` selects the semantics.

```java
fhirClient.transaction()
        .withBundle(bundle)
        .execute();
```

Construction uses the R4 model:

```java
Bundle bundle = new Bundle();
bundle.setType(Bundle.BundleType.TRANSACTION);
entry.getRequest().setMethod(Bundle.HTTPVerb.POST).setUrl("Patient");
entry.setFullUrl("urn:uuid:" + UUID.randomUUID());
```

`FhirService.executeTransaction` / `executeBatch` return the response Bundle (`transaction-response` / `batch-response`). Helpers read `entry.response.status` and `location`. They do not collapse the interaction to a boolean.

## Out of scope

No document Bundles, messaging, subscriptions, `$export`, or a custom transaction manager.
