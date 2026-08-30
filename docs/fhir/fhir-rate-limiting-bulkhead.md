# FHIR rate limiting and bulkhead foundation

This note adds **admission control** and **concurrency isolation** around routed Patient **READ**. Read it after [fhir-circuit-breaker.md](fhir-circuit-breaker.md). It does not replace classification, retry, or the circuit breaker.

This is an in-memory learning foundation. It is not Redis, Spring Cloud Gateway rate limiting, Resilience4j, or a distributed tenant quota.

## Why both exist

Tasks 023–025 protect the client from a failing dependency. This task protects the dependency (and the process) from too much demand.

| Control | Question | Default |
|---|---|---|
| Rate limiter | How many logical operations may **start** in a window? | 10 / 1 second |
| Bulkhead | How many operations may **run at once**? | 5 concurrent |

A rate limiter alone does not help if five slow READs hold sockets forever. A bulkhead alone does not stop a burst of 1,000 fast READs.

```text
Caller
  ↓
RoutingService
  ↓
Rate Limiter      frequency
  ↓
Bulkhead          concurrent capacity
  ↓
Circuit Breaker   dependency health
  ↓
Retry Executor    transient recovery
  ↓
FhirService.readPatient
  ↓
FHIR Server
```

## Packages

```text
lab.healthcare.fhir.resilience.ratelimit
├── FhirRateLimiterPolicy
├── FhirRateLimiter
├── FhirRateLimiterRegistry
└── RateLimitExceededException

lab.healthcare.fhir.resilience.bulkhead
├── FhirBulkheadPolicy
├── FhirBulkhead
├── FhirBulkheadRegistry
└── BulkheadFullException
```

`FhirService` and `MappingService` do not import these packages.

## Rate limiter — fixed window

```text
window starts at first accepted instant (or after the previous window ends)
    ↓
each accepted logical READ increments the counter
    ↓
10 accepted → next acquire throws RateLimitExceededException
    ↓
clock >= windowStart + 1s → counter resets
```

The counter increments **on admission**, before Bulkhead, Circuit Breaker, Retry, or FHIR HTTP. Retries inside one logical READ do not increment it again.

Production uses `Clock.systemUTC()`. Tests inject `MutableClock` and advance 1 second. The suite does not `Thread.sleep`.

## Bulkhead — semaphore permits

```text
5 permits
Request enters → tryAcquire
    ↓
execute Circuit → Retry → FHIR
    ↓
finally release
```

`tryAcquire` rejects immediately (`BulkheadFullException`). There is no wait queue.

`FhirBulkhead.execute` always releases in `finally` after success, FHIR failure, retry exhaustion, or a downstream exception. A leaked permit would shrink capacity permanently.

## Per-destination isolation

```text
local-hapi     own window + own 5 permits
secured-lab    own window + own 5 permits
```

A noisy destination must not consume another profile's quota.

Registries use `ConcurrentHashMap`. Each limiter is `synchronized`. Each bulkhead is a `Semaphore`.

## Local rejections

| Decision | Exception | Category | Retry | Circuit |
|---|---|---|---|---|
| Window full | `RateLimitExceededException` | `RATE_LIMITED` | no | no increment |
| Permits full | `BulkheadFullException` | `BULKHEAD_FULL` | no | no increment |
| Circuit OPEN | `CircuitBreakerOpenException` | `CIRCUIT_OPEN` | no | already open |

These are local resilience decisions. `FhirErrorClassifier` does not invent them from HAPI.

```text
FHIR_AUDIT … outcome=FAILURE attempt=1 error=RATE_LIMITED
FHIR_AUDIT … outcome=FAILURE attempt=1 error=BULKHEAD_FULL
```

Metrics count one logical **failed** operation. `retryAttempts` does not increase. This is “locally rejected”, not “FHIR HTTP failed”.

## What this task does not do

- protect CREATE / UPDATE / DELETE / search / bundles
- Redis / API Gateway / tenant billing quotas
- waiting queues
- Resilience4j
