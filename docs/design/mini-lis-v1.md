# Mini LIS v1

## Decision

Mini LIS is a second laboratory system, not a module inside Mini HIS. It has its own Spring Boot process, its own PostgreSQL database, and its own organization id `org-mini-lis`. FHIR Integration Service already had one proprietary reader, Mini HIS. This increment adds a second reader beside it. It does not replace the Mini HIS reader and it does not turn the single `clinical-read.source` switch into a federated query.

A typed registry, `SourceRegistry`, lists systems from configuration: key, organization, display name, base URL, and capabilities. Mini HIS and Mini LIS are installed connectors. Another key, such as a future clinic, can be declared in configuration and will appear on `GET /api/interop/v1/sources` as `connector=declared`. Declaring it does not read that system. Reading it requires a new connector class. The Mini LIS normalizer does not have to change when that class is added.

`LaboratoryRecordService` is the business boundary. The REST controller translates HTTP into commands and calls that service. Persistence stays behind the repository.

## What this increment does not do

- It does not implement HL7 v2, MLLP, ORM, OML, ORU, or ACK.
- It does not write orders from Mini HIS into Mini LIS.
- It does not write FHIR into HAPI.
- It does not change LangGraph or the Human Review pages.
- It does not match patients by name.

## HL7 v2 extension

The next transport can be added without a second domain model:

1. An MLLP listener receives a message and parses it with HAPI HL7v2.
2. An ORM or OML mapper builds `NewOrder`. An ORU^R01 mapper builds `NewResult`. The version and profile are chosen by that mapper, not by the domain service.
3. The mapper calls `LaboratoryRecordService`. The unique keys `(requesting_organization_id, external_request_id)` and `(order_id, external_result_id)` are the idempotency boundary already enforced by PostgreSQL.
4. The listener returns an ACK after the service commits. A rejected transition becomes an AE acknowledgement. A duplicate external id is an idempotent success when the stored row matches the message, and a rejection when it does not. That comparison is future work; the unique constraint is already present.
5. Retries stay in the listener. The domain service does not store MLLP sockets.
6. The FHIR mapping already used by REST stays the read path. A v2 message does not need its own FHIR builder.

Acceptance for that later increment: one ORM creates the same order the REST API would create, one ORU adds a result through the same transition rules, a repeated message does not create a second order, and Clinical Read with `mini-lis` returns the same ServiceRequest and Observation shape documented in [mini-lis-fhir-v1](../contracts/mini-lis-fhir-v1.md).

## Next vertical slice

Exchange one order and its result between the two organizations: Mini HIS records a request for `org-mini-his`, Mini LIS accepts that request as `requestingOrganizationId`, and a later read can show the ServiceRequest `requester` together with the Mini HIS patient only through an explicit link stored for the synthetic scenario. That link is not a name match and it is not this increment.
