# AI clinical federation consumer v1

## Status

Laboratory consumer in `services/ai-service`. It calls the Java endpoint specified in [clinical-federation-v1](clinical-federation-v1.md). It does not change that endpoint and it does not replace [Clinical Read v1](clinical-read-v1.md).

The default is `AI_CLINICAL_CONTEXT_MODE=single`. Single mode does not call this endpoint.

This is not a master patient index and it is not a production federation client.

## Configuration

The base URL is `MODEL_BOUNDARY_BASE_URL`, the same Java process as Clinical Read. The token is `AI_FEDERATION_PARTICIPANT_TOKEN`. It is a federation participant token, not `MODEL_BOUNDARY_SERVICE_TOKEN`.

| Variable | Use |
|---|---|
| `AI_CLINICAL_CONTEXT_MODE` | `single` or `federated`. Default `single`. |
| `AI_FEDERATION_PARTICIPANT_TOKEN` | `X-Service-Token` for the caller system. Blank fails closed at query time. |
| `AI_FEDERATION_REQUESTING_ORGANIZATION_ID` | Must be the caller's registry organization. |
| `AI_FEDERATION_PATIENT_SYSTEM_KEY` | Must be the authenticated system, for example `mini-his`. |
| `AI_FEDERATION_PATIENT_IDENTIFIER_SYSTEM` | Identifier system sent to Java. |
| `AI_FEDERATION_SOURCES` | Comma-separated grant members. Default `mini-his,mini-lis`. |
| `AI_FEDERATION_TIMEOUT_SECONDS` | Client timeout. Default 20. |

The workflow case id is the identifier value. A prompt cannot add a source, a name, a birth date, or another organization.

Checked-in examples leave the token blank. Do not commit a token.

## Request

`POST /api/clinical-federation/v1/context`.

The client always asks for Patient, Encounter, Observation, Appointment, ServiceRequest, and DiagnosticReport. Java returns its federation envelope. The body is not a FHIR Bundle. Each `entries[].resource` is a FHIR R4 resource.

## Outcomes the client keeps

| Java result | Python result |
|---|---|
| HTTP 200 `complete` | Context `complete`. A source with `resourceCount` 0 stays `no_resources:<source>`. That is not an identity miss and not a normal result. |
| HTTP 200 `partial` | Context `partial`. Warnings include `federation_partial` and the failing source outcome. The protocol result is not presented as a complete review. |
| HTTP 200 `failed` | `federation_failed`. No clinical entries. The graph status is `failed`. |
| HTTP 401 | `federation_unauthenticated`. No fallback. |
| HTTP 403 | `federation_unauthorized`. No fallback. |
| HTTP 400 | `federation_rejected`. |
| Timeout | `federation_timeout`. |
| Unexpected body, including a FHIR Bundle | `federation_unavailable`. |

`identity_unresolved` stays attached to that source. The client does not search by name.

## Provenance

The adapted state keeps `sourceKey`, `meta.source`, `fullUrl`, identifier system and value, clinical status, instant, and the original value and unit when the resource already has them. Code system and code are copied only when present. Two resources with the same code and value remain two resources. The persisted workflow view does not copy patient names. `fullUrl` is a locator in the envelope, not a server to call.

## Protocol evaluation

A `complete` envelope is evaluated by the existing structural rules. The contract is [federated protocol evaluation v1](federated-protocol-evaluation-v1.md). A `partial` or truncated envelope stays `insufficient` with `federated_context_partial` and does not become a match. `failed`, HTTP 401, HTTP 403, and timeout stay graph failures and do not fall back to Clinical Read.

In federated mode the narrative quotes that evidence and does not call Gemini. A match still opens Human Review and pauses at `await_human`. The open-case JSON projection does not call Clinical Read.

## What this consumer does not do

It does not connect to Mini HIS or Mini LIS. It does not emit a FHIR Provenance resource. It does not invent a protocol from laboratory values. It does not turn a partial context into a complete clinical review.
