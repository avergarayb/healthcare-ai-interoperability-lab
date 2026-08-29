# FHIR retry and resilience foundation

This note adds a **bounded retry** around routed Patient **READ** only. Read it after [fhir-error-handling.md](fhir-error-handling.md). It does not replace classification, routing, audit, or metrics.

There is still no Resilience4j, circuit breaker, jitter, or retry of CREATE/UPDATE/DELETE.

## Transient vs permanent

Task 023 answers *what kind of failure*. This task answers *should we try again?*

| Category | Retry | Why |
|---|---|---|
| `SERVER_ERROR` | yes | the FHIR server may recover |
| `TIMEOUT` | yes | a later attempt may complete |
| `CONNECTION_ERROR` | yes | a dropped socket is often brief |
| `NOT_FOUND` | no | the resource is not there |
| `VALIDATION_ERROR` | no | the request will fail again |
| `AUTHENTICATION_ERROR` | no | needs a new credential, not another identical call |
| `AUTHORIZATION_ERROR` | no | scope will still be insufficient |
| `CONFLICT` | no (default) | version/business conflict needs a new decision |
| `UNKNOWN` | no (default) | do not guess |

Retrying a 404 can hammer the server. Retrying CREATE can create duplicates. READ is idempotent, so it is the only operation retried here.

## Package

```text
lab.healthcare.fhir.resilience
├── FhirRetryPolicy
├── FhirRetryDecision
├── FhirRetryExecutor
├── FhirRetryAttempt
├── FhirRetryObserver
└── FhirSleeper
```

`FhirService` does not import this package. Routing orchestrates; resilience only runs the READ call.

```text
RoutingService
      │  destination + correlation + audit/metrics
      ▼
FhirRetryExecutor
      │  decide + backoff + bounded loop
      ▼
FhirService.readPatient
      ▼
FHIR server
```

## Bounded attempts

Default:

```text
maxAttempts = 3
initialDelay = 100 ms
```

`maxAttempts = 3` means **three executions**, not one plus three retries:

```text
attempt 1  (immediate)
   ↓ TIMEOUT
wait 100 ms
attempt 2
   ↓ TIMEOUT
wait 200 ms
attempt 3
   ↓ TIMEOUT
final FhirClientException category=TIMEOUT
```

## Exponential backoff

```text
delay before attempt n (n > 1) = 100 × 2^(n-2)
```

| Next attempt | Delay |
|---|---|
| 1 | 0 |
| 2 | 100 ms |
| 3 | 200 ms |

No jitter in this task. Tests inject `FhirSleeper.noop()` so the suite does not sleep.

## Observability

The same `correlationId` links every attempt of one logical READ.

```text
FHIR_AUDIT … outcome=FAILURE attempt=1 retry=true error=TIMEOUT
FHIR_AUDIT … outcome=SUCCESS attempt=2 status=200
```

Intermediate retry failures are audited. They are **not** counted as extra logical operations.

Metrics stay one row per logical operation:

```text
total=1 success=1 failed=0 retryAttempts=1 operationsRetried=1
```

`retryAttempts` is extra executions after the first (`attempt - 1` on the terminal event). Duration on the metric is the last FHIR attempt, not the sleep time.

## Final exception

When retries stop, the caller still receives the original `FhirClientException` (or `RoutingException` if the destination was invalid before any FHIR call). Category and cause are preserved. Routing failures are not retried.

## What this task does not do

- retry CREATE / UPDATE / DELETE
- retry OAuth token POST
- circuit breaker
- Resilience4j
- random jitter
- catch-all `Exception` retries
