# FHIR resilience pipeline

This note is the map of Tasks 023–027. It does not replace [fhir-error-handling.md](fhir-error-handling.md), [fhir-retry-resilience.md](fhir-retry-resilience.md), [fhir-circuit-breaker.md](fhir-circuit-breaker.md), or [fhir-rate-limiting-bulkhead.md](fhir-rate-limiting-bulkhead.md).

The pipeline is an in-memory learning foundation. There is no Resilience4j, Redis, Kafka, Prometheus, or dynamic admin API.

## Pipeline

```text
Caller
  ↓
RoutingService
  ↓
Rate Limiter          admission (frequency)
  ↓
Bulkhead              admission (concurrency)
  ↓
Circuit Breaker       dependency health
  ↓
Retry Executor        transient recovery
  ↓
FhirService.readPatient
  ↓
FHIR Server
```

`RoutingService` is the composition root. `FhirService` only executes FHIR.

| Layer | Question |
|---|---|
| Mapping | How is external JSON turned into FHIR? |
| Routing | Which named destination? |
| Rate limiter | May another logical operation start in this window? |
| Bulkhead | Is a concurrent permit free? |
| Circuit breaker | Is this destination healthy enough to call? |
| Retry | Should this transient attempt run again? |
| FhirService | Which FHIR interaction? |
| Audit | What happened on this operation (and each attempt)? |
| Metrics | What is happening in aggregate? |

## Configuration

YAML owns **how much** protection exists. Category eligibility still lives on the policy objects.

```yaml
fhir:
  resilience:
    rate-limit:
      max-operations: 10
      window: 1s
    bulkhead:
      max-concurrent-operations: 5
    circuit-breaker:
      failure-threshold: 3
      reset-timeout: 30s
    retry:
      max-attempts: 3
      initial-backoff: 100ms
```

```text
lab.healthcare.fhir.resilience
├── FhirResilienceProperties
├── FhirResilienceConfiguration
├── retry / circuit types
├── ratelimit/
└── bulkhead/
```

Invalid values fail at startup. The application does not silently clamp them.

`maxAttempts = 3` is not “retry every exception”. Only `TIMEOUT`, `CONNECTION_ERROR`, and `SERVER_ERROR` retry.

## Local vs dependency failures

| Category | Kind | Retry | Opens circuit |
|---|---|---|---|
| `RATE_LIMITED` | local admission | no | no |
| `BULKHEAD_FULL` | local admission | no | no |
| `CIRCUIT_OPEN` | local fail-fast | no | already open |
| `TIMEOUT` / `CONNECTION_ERROR` / `SERVER_ERROR` | dependency | yes | yes (terminal logical outcome) |
| `NOT_FOUND` and other 4xx-style | FHIR answer | no | no |

## Logical operation vs attempts

```text
Attempt 1 → TIMEOUT
Attempt 2 → SUCCESS
```

```text
logical operations = 1
success = 1
retryAttempts = 1
```

Audit may list both attempts. Metrics count one logical row.

## Per-destination isolation

`local-hapi`, `secured-lab`, and `smart-lab` each have their own rate window, permits, and circuit. A noisy destination does not consume another profile's capacity.
