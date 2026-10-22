# MINI_LIS_REST_V1

Laboratory contract for the proprietary REST API in `services/mini-lis-service`. Synthetic data only. Not a clinical system of record. Not HL7 v2. Not a FHIR server.

## Identity

Patients belong to organization `org-mini-lis`. Orders in the seed name the requesting organization `org-mini-his`. An identifier is unique inside its organization. A family name never links two patients.

The service token header is `X-Service-Token`. `/health` does not require it. Every other route returns HTTP 401 with an empty body when the token is missing or wrong. The token is not logged.

The process binds `127.0.0.1` unless `mini-lis.allow-external-bind` is true. Docker sets that flag so the published port can reach the process. The database is a PostgreSQL instance of its own. Flyway applies `V1__schema.sql`. The service does not open the HAPI database or the Mini HIS SQLite file.

## Domain

`LaboratoryRecordService` is the only writer. REST calls it. A future HL7 v2 adapter must call it and must not write SQL itself.

Order states: `ORDERED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`.

Result states: `PRELIMINARY`, `FINAL`, `CANCELLED`.

A result is accepted only while the order is `ORDERED` or `IN_PROGRESS`. The first result moves `ORDERED` to `IN_PROGRESS`. Further results, including more than one `FINAL`, stay on `IN_PROGRESS`. `POST /orders/{orderId}/completion` moves that order to `COMPLETED` only when at least one `FINAL` result exists. Completion of an already completed order returns the same order. A `FINAL` result cannot be added to a `COMPLETED` or `CANCELLED` order. Cancellation is refused when a `FINAL` result exists. A result time before the order time is HTTP 400 `invalid_request`.

## Routes

| Method and path | Success | Failure |
|---|---|---|
| `GET /health` | 200 `{"status":"up"}` | |
| `POST /patients` | 201 patient | 400 `invalid_request`, 409 `duplicate` |
| `GET /patients` | 200 list. Optional `organizationId` and `externalId` together | 400 when only one of those parameters is present |
| `GET /patients/{patientId}` | 200 patient | 404 `not_found` |
| `POST /orders` | 201 order in `ORDERED` | 404 unknown patient, 409 duplicate external request |
| `GET /orders` and `GET /orders/{orderId}` | 200 | 404 for an unknown id |
| `GET /patients/{patientId}/orders` | 200 | 404 unknown patient |
| `POST /orders/{orderId}/results` | 201 result | 400 invalid body, 404 unknown order, 409 `invalid_transition` or `duplicate` |
| `GET /orders/{orderId}/results` | 200 | 404 unknown order |
| `GET /results/{resultId}` | 200 | 404 |
| `GET /patients/{patientId}/results` | 200 | 404 unknown patient |
| `POST /orders/{orderId}/completion` | 200 | 409 when the order cannot be completed |
| `POST /orders/{orderId}/cancellation` | 200 | 409 when a final result exists |

List limits default to 50 and reject values outside 1 through 100. Domain errors are `{"error":"<code>"}` and do not echo the submitted clinical value.

## Synthetic seed

Loaded once when the patient table is empty:

| Patient | Order | State |
|---|---|---|
| `MLS-PAT-001` / `EXT-PAT-001` | `MLS-ORD-001` glucose, requested by `org-mini-his` | `ORDERED`, no result |
| `MLS-PAT-002` / `EXT-PAT-002` | `MLS-ORD-002`, result `MLS-RES-002` hemoglobin `13.5` `g/dL` | `COMPLETED` |
| `MLS-PAT-003` / `EXT-PAT-003` | `MLS-ORD-003`, results `MLS-RES-003` and `MLS-RES-004` | `COMPLETED` |

`POST` of the same external patient or the same external request id returns 409. An unknown order id returns 404. A final result on `MLS-ORD-002` after completion returns 409.

## Tests

`mvn -f services/mini-lis-service/pom.xml test` uses PostgreSQL 16 through Testcontainers for the API tests. `OrderTransitionTest` does not need Docker.
