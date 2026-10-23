# CLINICAL_FEDERATION_V1

## Status

Laboratory contract for `POST /api/clinical-federation/v1/context` in `services/fhir-integration-service`. The contract version string is `clinical-federation-v1`.

This endpoint does not replace [Clinical Read v1](clinical-read-v1.md). `clinical-read.source` stays `local-hapi` unless an operator changes it for a single-source read. Python `ClinicalReadClient` and LangGraph are unchanged.

This is a laboratory read across two implemented connectors. It is not a master patient index and it is not a production federation platform.

A registered system is not proof that a connector is running.

## Authentication

`FederationParticipantFilter` applies to `/api/clinical-federation/v1/*`. It requires `X-Service-Token`. The token map is `federation.participants.<system>.service-token`. Blank tokens are omitted. An empty map, a missing header, or a mismatch returns HTTP 401 and no body. Tokens must be distinct. The token value is not logged.

The caller system is the map key of the matching token. The client cannot choose another caller by a body field.

Checked-in tokens are blank. Set `FEDERATION_MINI_HIS_TOKEN` and `FEDERATION_MINI_LIS_TOKEN` outside the repository. Do not commit those values.

## Authorization

Grants are explicit in `federation.grants`. The checked-in grants are:

| Caller | May read |
|---|---|
| `mini-his` | `mini-his`, `mini-lis` |
| `mini-lis` | `mini-lis` |

`requestingOrganizationId` must be the caller's organization in the source registry. `patient.systemKey` must be the caller system. If `sources` is omitted, the grant list is used. If `sources` names anything outside the grant, the whole request is HTTP 403 `source_not_authorized`. That response has no `entries` array and no clinical payload.

Other authorization codes, also HTTP 403 and also without clinical entries:

| Code | Condition |
|---|---|
| `organization_mismatch` | The organization is not the caller's registry organization. |
| `identity_system_mismatch` | `patient.systemKey` is not the authenticated system. |
| `unauthenticated` | The request reached the controller without a caller. |

An authorization failure is not an empty chart.

## Request

`Content-Type: application/json`. Unknown fields are rejected with HTTP 400 `invalid_request`. `patient` accepts only `systemKey`, `identifierSystem`, and `identifierValue`. A name, birth date, or sex in this body is invalid. Those fields are not a match key.

```json
{
  "requestingOrganizationId": "org-mini-his",
  "patient": {
    "systemKey": "mini-his",
    "identifierSystem": "https://lab.local/mini-his/patient",
    "identifierValue": "MHS-PAT-001"
  },
  "sources": ["mini-his", "mini-lis"],
  "resourceTypes": ["Patient", "Encounter", "Observation", "Appointment", "ServiceRequest", "DiagnosticReport"],
  "correlationId": "FED-FLOW-0001"
}
```

`sources` and `resourceTypes` are optional. Omitted resource types mean the six types above. At most `federation.max-sources` sources are accepted (default 4). `correlationId`, when present, must match `[A-Za-z0-9.-]{8,64}`. When absent, the server generates `FED-` plus 16 hexadecimal characters.

## Identity

On the caller source, the connector searches that exact identifier system and value. Zero patients is `identity_unresolved`. The service does not search by name, birth date, or text similarity.

On another source, the only correspondence is `exchange_patient_link`: caller system, identifier system, identifier value, destination system, destination logical id. The exchange writes that row when it accepts an order. If the row is absent, the outcome is `identity_unresolved` and that connector is not called. A resolved patient with no clinical resources is `complete` and `resourceCount` 0. That is not an identity miss.

The link is directional. A Mini LIS identifier does not by itself resolve a Mini HIS patient.

## Response

HTTP 200 for `complete`, `partial`, and `failed`. The status is in the body. The body is a federation envelope. It is not a FHIR `Bundle`. Each `entries[].resource` is a FHIR R4 resource.

| Status | Meaning |
|---|---|
| `complete` | Every selected source outcome is `complete`, and the entry cap was not hit. |
| `partial` | At least one source is `complete` and at least one is not, or the entry cap was hit. |
| `failed` | No selected source is `complete`. |

```json
{
  "contractVersion": "clinical-federation-v1",
  "correlationId": "FED-FLOW-0001",
  "requestingOrganizationId": "org-mini-his",
  "callerSystem": "mini-his",
  "status": "partial",
  "truncated": false,
  "sources": [
    {"sourceKey": "mini-his", "organizationId": "org-mini-his", "outcome": "complete", "resourceCount": 4},
    {"sourceKey": "mini-lis", "organizationId": "org-mini-lis", "outcome": "identity_unresolved", "resourceCount": 0}
  ],
  "entries": []
}
```

Source outcomes:

| Outcome | Meaning |
|---|---|
| `complete` | Identity resolved. The resource list may be empty. |
| `identity_unresolved` | No exact patient on the caller source, or no stored link for another source. |
| `unavailable` | The connector failed or the query budget expired. `error` is `timeout`, `source_error`, or a connector code such as `unavailable`. |
| `connector_unavailable` | The system is registered and granted, and no connector bean exists. |
| `not_registered` | The granted key is not in the source registry. |
| `capability_unsupported` | The source declares none of the requested resource types. |
| `limit_reached` | The entry cap was already reached, so this source was not queried. |

`unavailable.error` does not include response bodies, names, values, or tokens.

## Provenance and references

Each entry has `sourceKey`, `organizationId`, `fullUrl`, and `resource`. `fullUrl` is `{registry base URL}/{resourceType}/{id}`. It keeps local ids from different organizations apart. It is not a claim that Mini HIS or Mini LIS is a FHIR server.

Existing `meta.source` is left as the connector wrote it (`https://lab.local/mini-his` or `https://lab.local/mini-lis`). Federation does not replace it. Relative references such as `Patient/{id}` are rewritten to the same base URL. Absolute references are left unchanged.

This version does not add a FHIR `Provenance` resource. The entry is the response provenance.

## Deduplication

Two keys suppress a repeated resource:

- `sourceKey` + resource type + logical id
- resource type + `meta.source` + identifier system + identifier value, only when `meta.source` is present

The same code and the same value from two sources remain two resources. Federation does not invent LOINC, SNOMED CT, or UCUM. A unit system that Mini HIS already maps, such as `g/dL`, stays as that connector produced it.

## Limits

| Property | Default |
|---|---|
| `federation.max-sources` | 4 |
| `federation.max-entries` | 100 |
| `federation.query-budget-seconds` | 20 |
| Connector connect timeout | 2s, from the existing Clinical Read connector settings |
| Connector read timeout | 5s, from those same settings |

Sources are queried in order. The budget is checked before each source. An in-flight connector call ends at that connector's read timeout.

Mini HIS observations are requested for `final`, `preliminary`, and `corrected`. Encounters are requested for `finished`, `in-progress`, `planned`, and `cancelled`. Mini LIS searches are not status-filtered.

## Later AI Service use

A future Python client can `POST /api/clinical-federation/v1/context` with the participant token of the requesting organization and read `status`, `sources`, and `entries`. It should keep using Clinical Read v1 until that client exists. Adapter, identity, and protocol logic stay in Java.

## Not in this contract

Probabilistic matching, a second HAPI FHIR server, Kafka, RabbitMQ, a new user interface, LangGraph changes, and cross-organization reads without a grant.
