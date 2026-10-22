# CLINICAL_READ_V1

## Status

Laboratory contract for the read-only HTTP surface in `services/fhir-integration-service`. It records the behavior of the current source. It does not record a test execution, a production deployment, or an organizational exchange.

The contract version string is `clinical-read-v1`.

## Responsibility

Java returns Patient, Encounter, Observation, and Appointment facts to an authenticated service caller. With `clinical-read.source=local-hapi` it reads the configured local HAPI destination. With `clinical-read.source=mini-his` it reads the Mini HIS Simulator over proprietary REST and normalizes that JSON to FHIR R4. The caller receives one envelope. It does not receive the proprietary payload and it does not choose a FHIR server URL.

Model Boundary v1 is a different contract. This API does not replace `GET /api/model-boundary/v1`.

Python's operational follow-up factories call this API through `ClinicalReadClient`. Python does not call Mini HIS. Review state stays in the Python SQLite database. This API has no write route.

## Authentication

`ClinicalReadServiceAuthFilter` applies to `/api/clinical-read/v1/*`. It requires the header `X-Service-Token`, the same shared secret as Model Boundary v1 (`ModelBoundaryServiceTokenSettings`). A missing configuration, a missing header, an empty header, or a mismatch returns HTTP 401 and writes no response body. The token value is not logged.

## Source configuration

| Property | Behavior in source |
|---|---|
| `clinical-read.source` | Default `local-hapi`. The other implemented value is `mini-his`. Any other value makes the HAPI path return HTTP 409 `destination_not_supported`. |
| Active FHIR server | For `local-hapi`, the active server name must also be `local-hapi`. Otherwise the HAPI path returns HTTP 409 `destination_not_supported`. |
| `clinical-read.mini-his.base-url` | Default `http://127.0.0.1:8095`. Used only when the source is `mini-his`. |
| `clinical-read.mini-his.connect-timeout` | Default `2s`. Values outside 1 ms through 30 s fail client construction. |
| `clinical-read.mini-his.read-timeout` | Default `5s`. Same bound. Redirects are not followed. |

If the source is `mini-his` and the Mini HIS source bean is absent, reads return HTTP 503 `unavailable`.

## Endpoints

All routes are `GET` and produce `application/json`.

| Route | Required query |
|---|---|
| `/api/clinical-read/v1/patients/{logicalId}` | None |
| `/api/clinical-read/v1/patients` | `identifierSystem`, `identifierValue` |
| `/api/clinical-read/v1/encounters/{logicalId}` | None |
| `/api/clinical-read/v1/encounters` | `patient`, `status` |
| `/api/clinical-read/v1/observations/{logicalId}` | None |
| `/api/clinical-read/v1/observations` | `patient`, `status` |
| `/api/clinical-read/v1/appointments/{logicalId}` | None |
| `/api/clinical-read/v1/appointments` | `patient` |

Supported resource types are only those four. There is no Condition, DiagnosticReport, MedicationRequest, or CapabilityStatement route on this API.

`logicalId` and a search `patient` value must match `[A-Za-z0-9\-.]{1,64}`. A search `status` must match `[A-Za-z0-9\-]{1,64}`. An identifier token is required, must be non-blank after trim, at most 200 characters, and must not contain `|`. Anything else is HTTP 400 `invalid_request`.

## Success envelopes

An exact read:

```json
{
  "contractVersion": "clinical-read-v1",
  "destination": "local-hapi",
  "resource": {}
}
```

A search:

```json
{
  "contractVersion": "clinical-read-v1",
  "destination": "mini-his",
  "collectionStatus": "complete",
  "resourceType": "Observation",
  "resources": []
}
```

`destination` is `local-hapi` or `mini-his`, matching the source that served the call. `collectionStatus` is `complete` or `incomplete`. `resource` and each entry of `resources` are JSON FHIR R4 resources. HAPI responses are the encoded server resources. Mini HIS responses are the normalizer output, including `meta.source` `https://lab.local/mini-his`.

## Limits

`ClinicalReadLimits` fixes page size 25, maximum pages 4, and maximum resources 100.

On `local-hapi`, search follows the FHIR next link. The collection is `incomplete` when a further page exists after 4 pages or when a further matching resource exists after 100 unique ids. Duplicate ids are skipped. A missing id, a repeated next link, a null page, or an encode failure is HTTP 503 `unavailable`. An exact read whose type or id does not match the request is also `unavailable`. An exact read classified as not found is HTTP 404 `not_found`.

On `mini-his`, list calls append `limit=100`. `X-More-Results: true` marks the collection `incomplete`. `X-More-Results: false` marks it `complete`. If that header is absent, an array of 100 or more items is treated as truncated. Patient identifier search does not return an incomplete collection: a Mini HIS 404, or an empty array, is a `complete` empty Patient collection; more than one match or a truncated list is HTTP 422 `invalid_source`. A 404 on encounter, observation, or appointment search or exact read is HTTP 404 `not_found`. Any Mini HIS status other than 200 or 404, a transport failure, or a body that is not JSON is HTTP 503 `unavailable`.

## Errors

`ClinicalReadException` is rendered as `{"error":"<code>"}` and the code is logged. The body has no clinical payload.

| HTTP | `error` | When the current methods emit it |
|---|---|---|
| 400 | `invalid_request` | Logical id, status, or identifier token fails the checks above. |
| 401 | none | Authentication filter. Empty body. This row is not the exception renderer. |
| 404 | `not_found` | Exact HAPI read classified as not found, or Mini HIS 404 on a route that maps absence to not found. |
| 409 | `destination_not_supported` | Source is not `local-hapi` while the call is on the HAPI path, or the active FHIR server is not `local-hapi`. |
| 422 | `invalid_source` | Mini HIS payload fails normalization, the returned id does not match, or a patient identifier search is ambiguous or truncated. |
| 503 | `unavailable` | Transport, unexpected status, missing Mini HIS bean, or a HAPI failure that is not a classified not-found exact read. |

`ClinicalReadException.operationNotSupported()` defines HTTP 409 `operation_not_supported`. The current read methods do not throw it.

## Limitations

- The default source is local HAPI, not Mini HIS.
- Epic and Oracle are not Clinical Read destinations. Sandbox HTML and Model Boundary v1 stay on their own routes.
- There is no write, no transaction, and no `$everything` on this API.
- Collection `incomplete` must not be treated as an empty or complete clinical set.
- Mini HIS normalization covers the fields the simulator sends. Observation `code` is text. Appointment `participant.status` is `needs-action` because the simulator has no participant response. Terminology and unit limits are in [mini-his-terminology-v1](mini-his-terminology-v1.md).
- This document does not claim that a suite was executed while it was written.
