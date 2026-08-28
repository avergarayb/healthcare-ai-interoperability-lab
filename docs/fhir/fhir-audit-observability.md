# FHIR audit and observability foundation

This note adds **traceability** around the integration flow. Read it after [fhir-routing.md](fhir-routing.md). It does not replace mapping, routing, OAuth, or SMART.

There is still no database, SIEM, OpenTelemetry collector, or audit UI.

## Why observability exists

A reusable integration component must answer operational questions without dumping clinical records into logs:

```text
Did Patient/patient-001 reach local-hapi?
How long did it take?
If it failed, was it routing or FHIR?
Which correlation ID ties the flow together?
```

Audit is not “log everything”. It is:

```text
Traceability + operational visibility + security-conscious diagnostics
```

## Audit event model

```text
FhirOperationContext
 ├── correlationId
 ├── destination
 ├── operation        READ (only the operation this task audits)
 ├── resourceType
 └── resourceId

FhirAuditEvent
 ├── timestamp
 ├── context
 ├── outcome          SUCCESS | FAILURE
 ├── status           HTTP/FHIR when known
 ├── durationMs
 └── error            FhirErrorCategory (NOT_FOUND, VALIDATION_ERROR, …)
```

Rendered line:

```text
FHIR_AUDIT correlationId=abc-123 destination=local-hapi operation=READ resourceType=Patient resourceId=patient-001 outcome=SUCCESS status=200 durationMs=41
```

Failed routing:

```text
FHIR_AUDIT correlationId=def-456 destination=does-not-exist operation=READ resourceType=Patient resourceId=patient-001 outcome=FAILURE durationMs=5 error=VALIDATION_ERROR
```

`FhirAuditRecorder` is the sink abstraction. The lab implementation (`LoggingFhirAuditRecorder`) writes that line to SLF4J and keeps a bounded in-memory buffer (not a database). A later recorder could target OpenTelemetry, SIEM, or an audit service without changing `FhirService`.

## Correlation ID

Callers may pass a correlation ID on `RoutingRequest`. If they omit it, `RoutingService` generates one UUID for that **integration operation**.

The same ID is reused for the audit event. Internal helpers (`resolve`, `client`) do not mint a new ID.

Mapping and authentication do not need to know the ID yet. The integration entry used here is routed Patient read.

## Success and failure

| Path | Outcome | error |
|---|---|---|
| `GET Patient/patient-001` on `local-hapi` | SUCCESS | — |
| destination `does-not-exist` | FAILURE | `VALIDATION_ERROR` |
| destination `example-org` (disabled) | FAILURE | `VALIDATION_ERROR` |
| FHIR HTTP 404 | FAILURE | `NOT_FOUND` |
| other classified FHIR/HAPI error | FAILURE | matching `FhirErrorCategory` |

Routing still selects the destination. Observability does not look up profiles.

## Duration

Elapsed time uses `System.nanoTime()` around the routed operation, then converts to milliseconds. Wall-clock `Instant` is only the event timestamp, not the duration source.

## Routing integration

```text
RoutingRequest (destination + optional correlationId)
      ↓
RoutingService.readPatient
      ↓
FhirService.readPatient   (unchanged FHIR logic)
      ↓
FhirAuditEvent
      ├── FhirAuditRecorder.record
      └── FhirMetricsRecorder.record
```

`FhirService` does not implement audit. Mapping does not record payloads. Metrics are a separate sink; see [fhir-metrics-observability.md](fhir-metrics-observability.md).

## Authentication safety

The audit line contains only structured fields from `FhirAuditEvent`. It does not include:

```text
access_token
client_secret
refresh_token
authorization_code
Bearer …
PKCE code_verifier
complete Patient / Observation JSON
```

Existing auth classes (`OAuth2TokenClient`, `BearerAccessTokenInterceptor`, `SmartTokenProvider`, `AuthorizationCodeClient`) still have no loggers. Task 021 did not add credential logging there.

`toLogLine()` refuses to emit a line that looks like it contains those credential markers.

## What is intentionally not logged

- Full FHIR Resource bodies
- Token responses
- Client secrets from YAML
- Search result Bundles

Logical ids such as `patient-001` are identifiers used for operations, not a dump of the Resource.

## Future

```text
FhirAuditRecorder
 ├── LoggingFhirAuditRecorder   (this task)
 ├── OpenTelemetry
 ├── SIEM
 ├── Database
 └── Audit service
```

Those sinks should not require rewriting mapping, routing, or `FhirService`.
