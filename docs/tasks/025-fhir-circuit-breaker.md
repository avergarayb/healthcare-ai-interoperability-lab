# Task 025 — FHIR Circuit Breaker Foundation

## Objective

Add a circuit breaker resilience layer to the Healthcare AI Interoperability Lab.

The circuit breaker must protect routed FHIR operations when a destination is repeatedly failing. It must work together with Task 023 structured error handling and Task 024 retry/backoff without putting resilience logic inside `FhirService`.

This task is a learning and architecture foundation. Do not add Resilience4j or another external resilience library yet.

---

## 1. Problem

Task 023 classifies failures. Task 024 retries transient failures.

If a destination remains unavailable, every new operation could repeat the retry sequence:

```text
Operation 1 → 3 attempts
Operation 2 → 3 attempts
Operation 3 → 3 attempts
```

A Circuit Breaker prevents continuously sending traffic to a destination known to be unhealthy.

Expected flow:

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

---

## 2. Circuit Breaker States

Implement the standard three-state model:

```text
                 ┌──────────────┐
                 │    CLOSED    │
                 │ Normal mode  │
                 └──────┬───────┘
                        │
                 failure threshold
                        │
                        ▼
                 ┌──────────────┐
                 │     OPEN     │
                 │ Fail Fast    │
                 └──────┬───────┘
                        │
                  reset timeout
                        │
                        ▼
                 ┌──────────────┐
                 │  HALF_OPEN   │
                 │ Probe mode   │
                 └──────┬───────┘
                        │
              ┌─────────┴─────────┐
              │                   │
            SUCCESS             FAILURE
              │                   │
              ▼                   ▼
            CLOSED               OPEN
```

### CLOSED
Requests are allowed normally. Transient failures may still be retried according to Task 024.

### OPEN
The failure threshold has been reached. New requests fail fast. No FHIR HTTP request and no retry sequence should execute.

### HALF_OPEN
After the reset timeout, one operation may probe the destination.

- success → CLOSED
- retryable infrastructure failure → OPEN

Keep the first implementation simple and deterministic.

---

## 3. Scope

Implement the circuit breaker only for routed `Patient READ` operations.

Do not automatically add circuit breaker behavior to:

- CREATE
- UPDATE
- DELETE
- search
- bundles
- transactions

Different operations may have different idempotency requirements.

---

## 4. Package and Components

Extend:

```text
lab.healthcare.fhir.resilience
```

Suggested types:

```text
CircuitBreakerState
FhirCircuitBreaker
FhirCircuitBreakerRegistry
FhirCircuitBreakerPolicy
CircuitBreakerOpenException
```

Names may be refined when necessary, but responsibilities must remain clear.

Do not create unnecessary abstractions.

---

## 5. Policy

Create an explicit policy object.

Initial concepts:

```text
failureThreshold = 3
resetTimeout = 30 seconds
```

Meaning:

```text
3 failed logical operations
        ↓
CLOSED → OPEN
```

Important: a logical operation may contain multiple retry attempts.

Example:

```text
Attempt 1 → TIMEOUT
Attempt 2 → SUCCESS
```

The logical operation is successful and must not increment the circuit failure count.

The Circuit Breaker evaluates the terminal outcome, not every retry attempt.

---

## 6. Failure Eligibility

Reuse `FhirErrorCategory` from Task 023.

Only infrastructure/transient categories should affect the circuit:

```text
TIMEOUT
CONNECTION_ERROR
SERVER_ERROR
```

These categories must not open the circuit:

```text
NOT_FOUND
VALIDATION_ERROR
AUTHENTICATION_ERROR
AUTHORIZATION_ERROR
CONFLICT
UNKNOWN
```

A missing Patient does not mean the FHIR destination is unhealthy.

---

## 7. Per-Destination Isolation

Circuit state must be isolated by destination/profile name.

Example:

```text
local-hapi  → CLOSED
secured-lab → OPEN
```

A failing destination must not block another destination.

Conceptually:

```text
destination
    ↓
FhirCircuitBreakerRegistry
    ↓
breaker for that destination
```

Do not use one global circuit for all FHIR servers.

---

## 8. Time Abstraction

Tests must not depend on real waiting.

Use an injectable time abstraction where necessary. `Clock` is acceptable.

Production uses real time.

Tests must control time deterministically.

Do not write tests that sleep for 30 seconds.

Concept:

```text
Time is a dependency.
```

---

## 9. HALF_OPEN Behavior

After reset timeout:

```text
OPEN
  ↓
timeout elapsed
  ↓
HALF_OPEN
```

Allow one probe operation.

Success:

```text
HALF_OPEN → CLOSED
failure count resets
```

Retryable infrastructure failure:

```text
HALF_OPEN → OPEN
```

Do not silently treat a 404 as evidence that the server is unavailable.

Document the chosen behavior for non-retryable failures in HALF_OPEN.

---

## 10. Integration with Retry

Required order:

```text
Circuit Breaker
        ↓
Retry Executor
        ↓
FHIR operation
```

### Circuit CLOSED

```text
allow operation
    ↓
Retry Executor
    ↓
FHIR
```

### Circuit OPEN

```text
fail immediately
```

The retry executor must not run.

Do not put the circuit breaker inside each retry attempt. The breaker evaluates the final result of the logical operation.

---

## 11. RoutingService Integration

The resilience orchestration belongs around the routed operation:

```text
RoutingService
   │
   ├── resolve destination
   │
   ├── obtain circuit breaker
   │
   └── execute logical operation
           │
           ├── circuit allows?
           │
           └── retry executor
                   │
                   └── FhirService.readPatient()
```

`FhirService` must remain unaware of:

- circuit breaker states
- thresholds
- reset timeouts
- retry policies

---

## 12. Exceptions

Create:

```text
CircuitBreakerOpenException
```

It should safely communicate that the destination was not contacted because protection is active.

Do not expose:

- access tokens
- client secrets
- authorization headers
- Patient JSON
- internal stack traces

Keep it distinguishable from:

```text
FhirClientException
RoutingException
```

---

## 13. Observability

Integrate with Tasks 021 and 022 carefully.

### Audit

Distinguish:

```text
FHIR request attempted and failed
```

from:

```text
Circuit OPEN → request blocked before FHIR call
```

Never log clinical payloads or credentials.

### Metrics

Do not inflate logical operation counts.

A blocked request is a logical operation from the caller perspective, but it did not execute an HTTP request.

Preserve existing audit and metrics behavior and document how blocked operations are treated.

Avoid high-cardinality labels.

---

## 14. No External Library Yet

Do not add:

- Resilience4j
- Hystrix
- Spring Cloud Circuit Breaker

The purpose is to understand:

```text
state machine
failure threshold
OPEN
HALF_OPEN
per-destination isolation
```

A future task can evaluate a production-grade library.

---

## 15. Unit Tests

At minimum test:

### CLOSED

```text
operation succeeds
state remains CLOSED
```

### Threshold

Three retryable failed logical operations:

```text
CLOSED → OPEN
```

### OPEN

Verify:

```text
operation fails fast
FHIR supplier is not executed
retry executor is not executed
```

### Reset timeout

Advance controlled time:

```text
OPEN → HALF_OPEN
```

### HALF_OPEN success

```text
probe succeeds
HALF_OPEN → CLOSED
failure count resets
```

### HALF_OPEN failure

```text
probe fails
HALF_OPEN → OPEN
```

### Non-retryable failures

Verify that NOT_FOUND, VALIDATION_ERROR, AUTHENTICATION_ERROR, AUTHORIZATION_ERROR and CONFLICT do not open the circuit.

### Per destination

```text
destination-a → OPEN
destination-b → CLOSED
```

---

## 16. Integration Tests

Create focused coverage:

```text
FhirCircuitBreakerResilienceIT
```

Demonstrate:

1. Healthy `local-hapi` request succeeds.
2. Deterministic synthetic failures open a circuit.
3. OPEN fails fast.
4. No additional FHIR call occurs while OPEN.
5. Controlled time supports recovery/HALF_OPEN behavior where practical.

Do not make the suite dependent on intentionally crashing external services unless deterministic.

---

## 17. Mandatory Code Explanations

For each important component, explain:

```text
WHAT:
What does this class/code do?

WHY:
Why does this responsibility exist?

HOW:
How does the implementation work?

CONCEPT:
What architecture or resilience concept am I learning?
```

Mandatory topics:

1. State machine: CLOSED, OPEN, HALF_OPEN.
2. Failure threshold: logical operations vs retry attempts.
3. Per-destination registry.
4. Time abstraction.
5. Why `Circuit Breaker → Retry → FHIR`.
6. Fail-fast behavior.
7. HALF_OPEN probe.
8. Why NOT_FOUND does not normally open a circuit.

---

## 18. Architecture Constraints

Maintain:

```text
mapping
    ↓
routing
    ↓
resilience
    ↓
client
```

Authentication and observability remain cross-cutting concerns.

Do not introduce:

```text
FhirService → resilience
mapping → resilience
```

Do not duplicate error classification from Task 023.

Reuse existing contracts.

---

## 19. Documentation

Create:

```text
docs/fhir/fhir-circuit-breaker.md
```

Update when appropriate:

```text
docs/fhir/README.md
docs/fhir/fhir-architecture.md
docs/fhir/fhir-error-handling.md
docs/fhir/fhir-retry-resilience.md
docs/roadmap.md
README.md
```

Document:

- three states
- failure threshold
- retryable categories
- per-destination isolation
- retry ordering
- fail-fast behavior
- HALF_OPEN recovery

Clearly state that this is an internal learning foundation, not yet a replacement for Resilience4j.

---

## 20. Validation

Run:

```bash
mvn clean test
```

Then:

```bash
mvn clean verify -Pintegration
```

All Tasks 001–024 must remain green.

Do not report completion until both commands pass.

---

## 21. Git

Branch:

```text
feature/fhir-circuit-breaker
```

Baseline:

```text
main
```

Do not commit or push automatically.

At completion provide:

1. Files created
2. Files modified
3. Architecture summary
4. Circuit breaker state transitions
5. Important code explanations
6. Test results
7. Problems encountered
8. Git status
9. Recommended commit message

Recommended commit:

```text
feat: add FHIR circuit breaker resilience foundation
```

---

# Definition of Done

Task 025 is complete when:

- Circuit breaker is outside `FhirService`
- CLOSED, OPEN and HALF_OPEN work
- Circuit state is isolated per destination
- Only infrastructure/transient categories affect the circuit
- Retry runs only when the circuit allows the operation
- OPEN fails fast without executing FHIR/retry
- HALF_OPEN can recover to CLOSED
- Tests control time deterministically
- Existing Tasks 001–024 remain green
- Important code is explained using WHAT / WHY / HOW / CONCEPT
- Documentation is updated
