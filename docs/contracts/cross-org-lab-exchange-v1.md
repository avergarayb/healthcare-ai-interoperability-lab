# CROSS_ORG_LAB_EXCHANGE_V1

Laboratory contract for one order and its results between two registered organizations. Synthetic data only. Not a production network. Not HL7 v2. Not a second HAPI FHIR server.

## Path

Mini HIS records the order and submits it to FHIR Integration Service. Java selects the destination from the source registry, builds a FHIR R4 ServiceRequest, and translates that resource into the Mini LIS REST command. Mini LIS stores the order in its own PostgreSQL database. Mini HIS later reads the result through Java. Mini HIS has no Mini LIS address.

Clinical Read keeps `local-hapi` as its checked-in default. This exchange does not change that switch.

## Authentication

`POST /api/exchange/v1/orders` and `GET /api/exchange/v1/orders/{sourceOrderId}/report` require `X-Service-Token`. The token selects the calling system. A blank token is not a laboratory default: the process rejects the call when the variable is unset. Tokens are not logged.

The calling system can read only correlations it submitted. Another registered system receives 404 for that order, and the body does not include the result value. A caller that puts another organization's id in `sourceOrganizationId` receives 403 `organization_forbidden`. Java does not call the destination.

Mini HIS calls the exchange with `MINI_HIS_EXCHANGE_TOKEN`. Java calls Mini LIS with `EXCHANGE_MINI_LIS_SERVICE_TOKEN`. Those values are not written in the checked-in configuration.

## Order

Mini HIS `POST /lab-orders` stores a local order for an existing patient. `POST /lab-orders/{orderId}/submission` sends:

- `sourceOrganizationId` from Mini HIS configuration
- `destinationSystemKey`
- `externalRequestId` equal to the Mini HIS order id
- test code, description, and `requestedAt`
- patient `identifierSystem` `https://lab.local/mini-his/patient` and `identifierValue` equal to the patient id

The name is sent only so Mini LIS can create a patient record. It is not the match key.

Java returns 201 `accepted` or 200 `duplicate`. The body contains `correlationId`, the source and destination parties, and `serviceRequest`. A second submission of the same Mini HIS order returns the same destination order id.

## Canonical ServiceRequest

The resource is FHIR R4. `meta.source` is `https://lab.local/exchange`. Identifiers are:

- `https://lab.local/exchange/service-request` for the correlation id
- `https://lab.local/{sourceOrganization}/service-request` for the Mini HIS order id
- `https://lab.local/exchange/destination-order` for the Mini LIS order id after acceptance

The subject is an identifier, not a name. The test coding system is `https://lab.local/{sourceSystem}/test`. Requester and performer are organization identifiers. The resource does not contain LOINC or UCUM.

## Results

The laboratory records results with the Mini LIS API. Mini HIS `GET /lab-orders/{orderId}/results` calls `GET /api/exchange/v1/orders/{sourceOrderId}/report`.

The report includes the canonical ServiceRequest, the Mini LIS ServiceRequest, the DiagnosticReport, and one Observation per result. Observation `basedOn` references the Mini LIS ServiceRequest. A numeric result keeps `valueQuantity.value` and `valueQuantity.unit` and does not add a unit system or code.

A report read after the order is accepted and before any result still returns 200. `observations` is empty and DiagnosticReport `result` is empty. The response does not invent a value. A read before the order has a destination id returns `destination_unavailable` and keeps the correlation id.

## Delivery and errors

| State or error | Meaning |
|---|---|
| `accepted` | Destination stored a new order |
| `duplicate` | The same source order already has a destination order id |
| `destination_unavailable` | Timeout or a destination error. The correlation id is kept. A later submission of the same order may retry |
| `destination_rejected` | Destination refused the command |
| `destination_not_routable` | The registry has no destination, it lacks `service-request`, or no connector is installed |
| `organization_forbidden` | The caller organization does not match the registered system |
| `exchange_unconfigured` | Mini HIS has no exchange URL or token |

A duplicate external request at Mini LIS is read back by `(requestingOrganizationId, externalRequestId)` and stored as `duplicate`. The exchange does not post the order a second time when the correlation already has a destination id.

## Patient correlation

The link key is source system, identifier system, identifier value, and destination system. The destination patient is sought by requesting organization and external id. The same key reuses the destination patient even if the submitted name differs. A different identifier creates another destination patient even when the name is the same.
