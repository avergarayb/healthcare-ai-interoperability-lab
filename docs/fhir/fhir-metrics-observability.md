# FHIR metrics and observability foundation

This note adds **aggregated operational metrics** next to the audit events from [fhir-audit-observability.md](fhir-audit-observability.md). Read that first. It does not replace mapping, routing, OAuth, SMART, or audit.

There is still no Prometheus server, Grafana dashboard, OpenTelemetry collector, or metrics database.

## Why metrics exist

Audit answers a single-operation question:

```text
What happened to correlationId=abc-123?
```

Metrics answer a platform question:

```text
How many FHIR operations succeeded?
Which destinations are failing?
How long do operations take on average?
```

Example audit event:

```text
correlationId=abc-123 destination=local-hapi operation=READ resourceType=Patient resourceId=patient-001 outcome=SUCCESS durationMs=41
```

The same completed operation increments counters:

```text
total=1 success=1 failed=0 avgDurationMs=41
operations[READ=1]
destinations[local-hapi=1]
resourceTypes[Patient=1]
outcomes[SUCCESS=1]
```

A thousand reads become `READ=1000`, not a thousand metric log lines.

## Audit vs metrics

| | Audit | Metrics |
|---|---|---|
| Unit | one operation | many operations |
| Identity | correlation ID, resource id | none |
| Shape | `FhirAuditEvent` | `FhirMetricSnapshot` |
| Sink | `FhirAuditRecorder` | `FhirMetricsRecorder` |

They are independent sinks. Neither recorder calls the other.

```text
                    FHIR Operation
                          │
                          ▼
                  FhirAuditEvent
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
   FhirAuditRecorder        FhirMetricsRecorder
             │                         │
             ▼                         ▼
       Audit output              Aggregated metrics
```

`RoutingService.readPatient` is the composition point: it publishes the same event to both.

## Metric model

```text
FhirMetricSnapshot
 ├── totalOperations
 ├── successfulOperations
 ├── failedOperations
 ├── operationsByType
 ├── operationsByDestination
 ├── operationsByResourceType
 ├── operationsByOutcome
 ├── totalDurationMs
 └── operationCount
```

Average latency:

```text
averageDurationMs = totalDurationMs / operationCount
```

That is integer (long) division. There is no histogram and no percentile (p50/p95) in this task.

`InMemoryFhirMetricsRecorder` holds counters only. It does not keep a list of `FhirAuditEvent`.

## Allowed dimensions

Bounded operational labels:

```text
operation       READ (the operation this lab currently records)
destination     named profile, e.g. local-hapi
resourceType    Patient, Observation, …
outcome         SUCCESS | FAILURE
```

Not used as labels:

```text
correlationId
resourceId / patient identifier
FHIR URL with query parameters
clinical values
access_token / client_secret / refresh_token
authorization_code / code_verifier
complete FHIR Resource
error category text as a metric label
```

High-cardinality labels would explode series count. Patient identifiers would put PHI into metrics.

## Duration

Task 021 already measures elapsed time with `System.nanoTime()` and stores `durationMs` on the audit event. Metrics add that value. They do not time the same operation twice.

## Success and failure

| Path | Counters |
|---|---|
| routed `GET Patient/patient-001` on `local-hapi` | `total++` `success++` `destinations[local-hapi]++` |
| destination `does-not-exist` | `total++` `failed++` `destinations[does-not-exist]++` |
| circuit OPEN (blocked before FHIR) | `total++` `failed++`; `retryAttempts` unchanged |

Routing still selects the destination. Metrics do not look up profiles.

## Routing integration

```text
RoutingRequest
      ↓
RoutingService.readPatient
      ↓
FhirService.readPatient   (unchanged FHIR logic)
      ↓
FhirAuditEvent
      ├── FhirAuditRecorder
      └── FhirMetricsRecorder
```

`FhirService` does not implement metrics. Mapping does not increment counters. Authentication does not appear as a metric dimension.

## In-memory implementation

`InMemoryFhirMetricsRecorder` is for local development, tests, and demonstration. It is a Spring `@Component` so integration tests can autowire a snapshot.

It is **not**:

```text
Prometheus
Micrometer registry
OpenTelemetry Metrics
a database
a log line per operation
```

## Security / PHI

The summary line looks like:

```text
FHIR_METRICS total=2 success=1 failed=1 durationMs=46 avgDurationMs=23 operations[READ=2] destinations[does-not-exist=1,local-hapi=1] resourceTypes[Patient=2] outcomes[FAILURE=1,SUCCESS=1]
```

It reuses the same credential-marker guard as audit (`access_token`, `client_secret`, `refresh_token`, `authorization_code`, `code_verifier`, `Bearer `). Auth classes still have no loggers.

## Future

```text
FhirMetricsRecorder
 ├── InMemoryFhirMetricsRecorder   (this task)
 ├── Micrometer / Prometheus
 ├── OpenTelemetry Metrics
 └── Cloud monitoring
```

A later backend could expose:

```text
fhir_operations_total
fhir_operation_duration
fhir_operation_failures_total
```

Those sinks should not require rewriting mapping, routing, authentication, or `FhirService`. This task does not add a Prometheus endpoint.
