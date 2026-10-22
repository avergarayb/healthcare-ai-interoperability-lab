# Cross-organization laboratory order exchange v1

## Decision

FHIR Integration Service is the only hop between Mini HIS and Mini LIS. Mini HIS records a laboratory order and calls `/api/exchange/v1`. Java builds the canonical FHIR R4 ServiceRequest, derives the Mini LIS command from that resource, and stores the correlation in its own SQLite file. That file is not the HAPI database, the Mini HIS database, or the Mini LIS database.

Routing is a registry lookup plus a connector list. A destination is eligible when it is a different registered system, declares `service-request`, and has an installed connector. Declaring `clinic-b` does not deliver an order there. Adding a later system means a registry entry, a participant token, and a class that implements `OrderDestination` and `ResultSource`. It does not require a new router.

`LaboratoryRecordService` remains the only writer inside Mini LIS. The connector calls the existing REST API. A future HL7 v2 adapter must produce the same `OrderSubmission` or call `LaboratoryRecordService` through the same command shape. It must not write the exchange tables or the Mini LIS tables itself.

## What this increment does not do

- It does not implement MLLP, ORM, OML, ORU^R01, or ACK.
- It does not open a direct socket from Mini HIS to Mini LIS.
- It does not match patients by name.
- It does not invent LOINC or UCUM.
- It does not change the Clinical Read default `local-hapi`.
- It does not change LangGraph or the Healthcare AI service.
- It does not add a broker.
- It does not federate Clinical Read. Selecting `mini-lis` still replaces the single Clinical Read source.
- It is not a bidirectional messaging engine and it is not multi-system federation.

## Correlation and delivery

The correlation id is the FHIR identifier `https://lab.local/exchange/service-request`. The same row stores the Mini HIS order id and, after acceptance, the Mini LIS order id and patient id. Delivery states are `pending`, `accepted`, `duplicate`, `destination_unavailable`, and `rejected`.

A caller retry is safe. If the destination id is already stored, Java returns `duplicate` and does not post again. If the destination accepted the order but the response was lost, the connector treats HTTP 409 `duplicate` as success and reads the order back by requesting organization and external request id.

Timeouts are bounded. A destination failure keeps the correlation id and the error code. Logs contain those identifiers and the error code. They do not contain names, result values, or tokens.

## Authorization

Each participant has its own service token, supplied by environment variable and left blank in the checked-in file. The token selects the system. The submitted `sourceOrganizationId` must equal that system's registered organization. A mismatch is `organization_forbidden` and does not create an order. The report query is limited to correlations whose source system is that caller. Another organization does not receive the result.

After acceptance and before any laboratory result, the report returns the DiagnosticReport with an empty `result` array. It does not synthesize an Observation.

## HL7 v2 extension

The transport can be added later without a second order model:

1. An MLLP listener parses ORM^O01 or OML^O21 with HAPI HL7v2.
2. The mapper builds `OrderSubmission` from the placer order number, the assigning authority, and the universal service identifier. The placer number is the external request id. The assigning authority supplies the organization. The mapper does not match a patient by name.
3. `ExchangeService.submit` performs correlation, the FHIR ServiceRequest, routing, and the Mini LIS write.
4. The listener returns ACK after the exchange commits. A lost ACK is safe because the same placer number is `duplicate`.
5. ORU^R01 is recorded by the laboratory through `LaboratoryRecordService`. The existing report path returns DiagnosticReport and Observation. The v2 mapper, when added, reads that report and builds the ORU. It does not query Mini HIS directly.
6. Retries stay in the listener. The domain service does not store MLLP sockets.

Acceptance for that later increment: one ORM creates the same Mini LIS order as `POST /lab-orders`, a repeated message does not create a second order, and the Mini HIS result read still returns the same Observation.
