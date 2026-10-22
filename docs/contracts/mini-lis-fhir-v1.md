# MINI_LIS_FHIR_V1

Mapping from the Mini LIS proprietary JSON to FHIR R4 inside FHIR Integration Service. Structural encoding uses the JSON shape accepted by HAPI FHIR R4 structures. It is not a full terminology validation and it does not create a second HAPI server.

The connector reads Mini LIS over HTTP. It sends `X-Service-Token` and does not follow redirects. The base URL must be HTTP on a loopback host. A transport failure or a status other than 200 or 404 is Clinical Read `unavailable`. A 404 on an exact read is `not_found`. A body that cannot supply a required field is `invalid_source`.

`meta.source` is `https://lab.local/mini-lis` on every mapped resource.

## Codes

Test codes stay in `https://lab.local/mini-lis/test`. The code is the proprietary value, such as `HGB` or `GLU`. A description, when the order has one, is `code.text`. This mapping does not add LOINC. A numeric result with a unit becomes `valueQuantity.value` and `valueQuantity.unit`. `valueQuantity.system` and `valueQuantity.code` are omitted, including when the unit text is `g/dL`. A non-numeric value becomes `valueString`. A reference range is `referenceRange.text` and is not split into low and high.

## Resources

| Mini LIS | FHIR | Identity |
|---|---|---|
| Patient | `Patient` | `id` is `patientId`. Identifiers: `https://lab.local/mini-lis/patient` and `https://lab.local/mini-lis/organization/{organizationId}/patient` |
| Order | `ServiceRequest` | `id` is `orderId`. Identifier system `https://lab.local/mini-lis/order`. `intent` is `order`. `authoredOn` is the request time |
| Result | `Observation` | `id` is `resultId`. `basedOn` is `ServiceRequest/{orderId}`. Category `laboratory` |
| Order plus its results | `DiagnosticReport` | `id` is the same `orderId` as the ServiceRequest. `basedOn` points at that ServiceRequest. `result` points at each Observation |

Organization identifiers use `https://lab.local/mini-lis/organization`. The patient carries `managingOrganization`. The service request carries `requester` for the requesting organization. Those are explicit identifiers. Names are not used to correlate organizations.

## Status

| Order | ServiceRequest | DiagnosticReport |
|---|---|---|
| `ORDERED` | `active` | `registered` |
| `IN_PROGRESS` | `active` | `partial` |
| `COMPLETED` | `completed` | `final` |
| `CANCELLED` | `revoked` | `cancelled` |

| Result | Observation |
|---|---|
| `PRELIMINARY` | `preliminary` |
| `FINAL` | `final` |
| `CANCELLED` | `cancelled` |

## Clinical Read

The active source remains one value. `clinical-read.source=mini-lis` selects this connector. `local-hapi` remains the default. Patient and Observation use the existing Clinical Read routes. ServiceRequest and DiagnosticReport use the added routes and return `operation_not_supported` for any other source. Encounter and Appointment return `operation_not_supported` for `mini-lis`. The envelope `destination` is `mini-lis`.

This is a read. Mini LIS does not receive a FHIR write, and this mapping does not place an order into Mini HIS.
