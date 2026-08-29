# FHIR circuit breaker foundation

This note adds a **per-destination circuit breaker** around routed Patient **READ**. Read it after [fhir-retry-resilience.md](fhir-retry-resilience.md). It does not replace classification, retry, routing, audit, or metrics.

This is an internal learning foundation. It is not a replacement for Resilience4j, Hystrix, or Spring Cloud Circuit Breaker.

## Why a circuit breaker exists

Task 023 classifies a failure. Task 024 retries a transient one. If a destination stays down, every new READ still spends three attempts:

```text
Operation 1 → 3 attempts
Operation 2 → 3 attempts
Operation 3 → 3 attempts
```

A circuit breaker stops sending traffic to a destination already known to be unhealthy.

```text
Caller
  ↓
RoutingService
  ↓
Circuit Breaker
  ↓
Retry Executor
  ↓
FhirService
  ↓
FHIR Server
```

Retry still belongs **inside** an allowed logical operation. The breaker evaluates the **terminal** outcome of that operation, not each retry attempt.

## Package

```text
lab.healthcare.fhir.resilience
├── CircuitBreakerState
├── FhirCircuitBreakerPolicy
├── FhirCircuitBreaker
├── FhirCircuitBreakerRegistry
├── CircuitBreakerOpenException
├── FhirRetryPolicy
└── FhirRetryExecutor
```

`FhirService` does not import this package. Mapping does not import it either.

## States

```text
CLOSED  → requests allowed; retry may still run
OPEN    → fail fast; no FHIR HTTP; no retry loop
HALF_OPEN → one probe operation; success → CLOSED; infrastructure failure → OPEN
```

Defaults:

```text
failureThreshold = 3 logical operations
resetTimeout     = 30 seconds
```

Three **failed logical operations** open the circuit. A logical READ may contain two extra retry attempts. Those extra attempts do not increment the circuit counter.

```text
Attempt 1 → TIMEOUT
Attempt 2 → SUCCESS
```

The logical operation succeeded. The failure count does not increase.

## Categories that affect the circuit

Reuse Task 023 `FhirErrorCategory`. Only infrastructure/transient categories count:

| Category | Opens the circuit? |
|---|---|
| `SERVER_ERROR` | yes |
| `TIMEOUT` | yes |
| `CONNECTION_ERROR` | yes |
| `NOT_FOUND` | no |
| `VALIDATION_ERROR` | no |
| `AUTHENTICATION_ERROR` | no |
| `AUTHORIZATION_ERROR` | no |
| `CONFLICT` | no |
| `UNKNOWN` | no |
| `CIRCUIT_OPEN` | no (already blocked) |

A missing Patient is not an unhealthy FHIR destination.

### HALF_OPEN and non-retryable failures

A 404 (or validation / auth / conflict) during the probe means the server **answered**. That is not evidence that the destination is down.

Chosen behavior:

```text
HALF_OPEN + NOT_FOUND / VALIDATION / AUTH / AUTHZ / CONFLICT / UNKNOWN
        → CLOSED
        → failure count resets
        → the original exception is still thrown to the caller
```

The caller still sees `NOT_FOUND`. The circuit recovers because the destination is reachable.

## Per-destination isolation

```text
destination
    ↓
FhirCircuitBreakerRegistry
    ↓
breaker for that destination
```

```text
local-hapi  → CLOSED
secured-lab → OPEN
```

One global circuit would block a healthy server because another profile failed.

## Time

`Clock` is a dependency. Production uses `Clock.systemUTC()`. Tests use a mutable clock and **advance** 30 seconds. The suite does not `Thread.sleep(30000)`.

## Fail-fast

When OPEN (or a HALF_OPEN probe is already in flight):

```text
CircuitBreakerOpenException
  category = CIRCUIT_OPEN
  message  = FHIR destination circuit is open
```

Distinct from `FhirClientException` and `RoutingException`. No tokens, secrets, Patient JSON, or stack text in the message.

## Observability

| Path | Audit | Metrics |
|---|---|---|
| FHIR request attempted and failed | `FAILURE` + Task 023 category, `attempt` / `retry` as in Task 024 | one logical row on the terminal attempt |
| Circuit OPEN, request blocked | `FAILURE` `error=CIRCUIT_OPEN` `attempt=1` no `retry=true` | one logical **failed** operation; `retryAttempts` unchanged |

A blocked request is a logical operation from the caller. It did not execute an HTTP request. It must not look like a FHIR 5xx or inflate retry counters.

```text
FHIR_AUDIT … outcome=FAILURE attempt=1 error=CIRCUIT_OPEN
```

## What this task does not do

- circuit breaker on CREATE / UPDATE / DELETE / search / bundles
- Resilience4j / Hystrix / Spring Cloud Circuit Breaker
- percentage-based windows or sliding failure rates
- retry of a blocked OPEN request
