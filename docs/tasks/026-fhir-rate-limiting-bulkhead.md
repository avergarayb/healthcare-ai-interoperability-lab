# Task 026 — FHIR Rate Limiting and Bulkhead Foundation

## Objective

Add a resource-protection layer to the Healthcare AI Interoperability Lab.

This task introduces:

1. **Rate Limiting** — limits how many logical integration operations may start during a time window.
2. **Bulkhead / Concurrency Limiting** — limits how many operations may execute concurrently.

Both protections must remain outside `FhirService`.

This is a learning and architecture foundation. Do not add Resilience4j, Redis, Spring Cloud Gateway rate limiting, or distributed quotas yet.

---

# 1. Why This Exists

Tasks 023–025 protect the integration service from failures:

```text
Task 023 → What type of error happened?
Task 024 → Should we retry?
Task 025 → Should we stop contacting an unhealthy dependency?
```

Task 026 protects against excessive demand:

```text
Too many requests
        ↓
Too many concurrent FHIR calls
        ↓
Connection exhaustion / overload / noisy clients
```

Example:

```text
Client A → 1,000 requests
Client B → normal traffic
Client C → normal traffic
```

Client A must not consume all available capacity.

---

# 2. Rate Limiting vs Bulkhead

## Rate Limiting

Question:

> How many operations may start during a period of time?

Initial example:

```text
10 operations / 1 second
```

Request 11 is rejected.

Concept:

```text
Rate = frequency over time
```

## Bulkhead

Question:

> How many operations may execute simultaneously?

Initial example:

```text
5 concurrent operations
```

If five operations are running:

```text
Request 6 → rejected immediately
```

Concept:

```text
Concurrency = simultaneous work
```

---

# 3. Why Both Are Needed

A rate limiter alone does not protect against slow requests.

A bulkhead alone does not control bursts of fast requests.

Therefore:

```text
Rate Limiter → controls frequency
Bulkhead     → controls concurrent capacity
```

---

# 4. Scope

Apply protection only to routed `Patient READ` operations.

Do not automatically add behavior to:

- CREATE
- UPDATE
- DELETE
- search
- bundles
- transactions

---

# 5. Required Architecture

```text
Caller
  ↓
RoutingService
  ↓
Rate Limiter
  ↓
Bulkhead
  ↓
Circuit Breaker
  ↓
Retry Executor
  ↓
FhirService.readPatient
  ↓
FHIR Server
```

Meaning:

```text
Admission control
        ↓
Capacity protection
        ↓
Dependency health
        ↓
Transient recovery
        ↓
FHIR operation
```

---

# 6. Ordering Rules

## Rate Limiter first

If the rate is exceeded:

```text
RATE_LIMIT_EXCEEDED
```

The request must not:

- consume a bulkhead permit
- execute the circuit breaker
- execute retry
- contact FHIR

## Bulkhead second

If concurrency capacity is exhausted:

```text
BULKHEAD_FULL
```

The request must not execute Circuit Breaker, Retry, or FHIR.

## Circuit Breaker third

If the circuit is OPEN:

```text
CIRCUIT_OPEN
```

Fail fast.

## Retry fourth

Retry handles transient failures only after all admission checks succeed.

---

# 7. Package Structure

Create:

```text
lab.healthcare.fhir.resilience.ratelimit
```

Suggested types:

```text
FhirRateLimiterPolicy
FhirRateLimiter
FhirRateLimiterRegistry
RateLimitExceededException
```

Create:

```text
lab.healthcare.fhir.resilience.bulkhead
```

Suggested types:

```text
FhirBulkheadPolicy
FhirBulkhead
FhirBulkheadRegistry
BulkheadFullException
```

Do not create unnecessary abstractions.

---

# 8. Rate Limiter Policy

Create an explicit policy object.

Initial values:

```text
maxOperations = 10
window = 1 second
```

A simple fixed-window algorithm is acceptable:

```text
window starts
    ↓
count accepted operations
    ↓
10 accepted
    ↓
next request rejected
    ↓
new window
    ↓
counter resets
```

Do not implement Redis, distributed coordination, tenant billing quotas, or API Gateway quotas.

---

# 9. Bulkhead Policy

Create an explicit policy:

```text
maxConcurrentOperations = 5
```

Use an appropriate Java concurrency primitive. A `Semaphore` is acceptable.

Concept:

```text
5 permits

Request enters
    ↓
acquire permit
    ↓
execute operation
    ↓
finally release permit
```

The permit must always be released after:

- success
- FHIR failure
- retry exhaustion
- downstream exception

Never leak capacity.

The initial implementation rejects immediately. Do not implement waiting queues.

---

# 10. Per-Destination Isolation

Both protections must be isolated by destination/profile name.

Example:

```text
local-hapi
    Rate Limit: independent
    Bulkhead: independent

secured-lab
    Rate Limit: independent
    Bulkhead: independent
```

A noisy destination must not consume another destination's capacity.

Conceptually:

```text
destination → registry → protection instance
```

Do not use one global limiter for all destinations.

---

# 11. Time Abstraction

Rate limiting depends on time.

Reuse the Task 025 principle:

```text
Time is a dependency.
```

Use `Clock` or another minimal abstraction.

Production:

```text
Clock.systemUTC()
```

Tests:

```text
MutableClock
```

Do not use `Thread.sleep(...)` to wait for a rate-limit window.

---

# 12. Rate Limiter Behavior

Example:

```text
10 operations / second
```

Requests:

```text
1–10 → allowed
11   → RateLimitExceededException
```

Advance controlled time:

```text
+1 second
```

Then:

```text
next request → allowed
```

Document precisely when the counter increments. The implementation must be deterministic.

---

# 13. Bulkhead Behavior

Example:

```text
maxConcurrentOperations = 5
```

```text
1 → running
2 → running
3 → running
4 → running
5 → running
6 → BulkheadFullException
```

When an operation completes, its permit is released and another operation may enter.

---

# 14. Exceptions

Create:

```text
RateLimitExceededException
BulkheadFullException
```

They must remain distinguishable from:

```text
FhirClientException
RoutingException
CircuitBreakerOpenException
```

Messages must not expose tokens, secrets, Authorization headers, Patient JSON, or FHIR payloads.

---

# 15. Structured Error Model

Extend the structured error model only where architecturally appropriate.

Suggested local categories:

```text
RATE_LIMITED
BULKHEAD_FULL
```

These are local resilience decisions.

They are not HTTP errors returned by HAPI/FHIR.

Do not modify the FHIR error classifier to pretend the external server generated them.

---

# 16. Observability

## Audit

Examples:

```text
error=RATE_LIMITED
error=BULKHEAD_FULL
```

These mean the operation was blocked locally.

Do not represent them as failed HTTP calls.

## Metrics

Each rejected caller request is still one logical operation, but it did not execute FHIR.

Metrics must distinguish:

```text
locally rejected
```

from:

```text
FHIR attempted and failed
```

Do not inflate retry attempts or HTTP attempt counts.

Avoid high-cardinality labels.

---

# 17. Integration with Circuit Breaker

Local capacity decisions do not affect destination health:

```text
RATE_LIMITED → does not increment circuit failures
BULKHEAD_FULL → does not increment circuit failures
```

The Circuit Breaker remains responsible for dependency health.

---

# 18. Integration with Retry

Locally rejected operations must not enter retry:

```text
RATE_LIMITED → NO RETRY
BULKHEAD_FULL → NO RETRY
```

---

# 19. RoutingService Integration

The orchestration should become:

```text
resolve destination
       ↓
rate limiter allows?
       ↓
bulkhead has capacity?
       ↓
circuit breaker allows?
       ↓
retry executor
       ↓
FhirService.readPatient
```

`FhirService` must remain unaware of rate limits, permits, windows, or concurrency policies.

`MappingService` must not import resilience.

---

# 20. Concurrency Safety

Explicitly address thread safety.

Explain:

```text
WHAT
WHY
HOW
CONCEPT
```

Mandatory concepts:

1. Why counters require synchronization/atomicity.
2. Why `Semaphore` protects concurrent capacity.
3. Why permits must be released in `finally`.
4. Why registries need concurrent-safe structures.

---

# 21. Mandatory Code Explanations

For every important component explain:

```text
WHAT:
What does this code do?

WHY:
Why does this responsibility exist?

HOW:
How does the implementation work?

CONCEPT:
What architecture/resilience/concurrency concept am I learning?
```

Mandatory topics:

1. Rate limiting vs concurrency limiting.
2. Fixed time window.
3. Why time is injectable.
4. Per-destination isolation.
5. Semaphore permits.
6. `try/finally` permit release.
7. Why admission checks happen before Circuit Breaker and Retry.
8. Why local rejections do not affect Circuit Breaker health.
9. Thread safety.

---

# 22. Unit Tests — Rate Limiting

At minimum:

### Within limit

```text
10 operations → allowed
```

### Exceeds limit

```text
11th operation → rejected
```

### New window

Advance controlled time:

```text
+1 second
```

Then:

```text
operation → allowed
```

### Per destination

```text
destination-a exhausted
destination-b still allowed
```

### Concurrent safety

Where practical, verify concurrent access does not exceed the configured limit.

---

# 23. Unit Tests — Bulkhead

At minimum:

### Capacity available

Operation enters successfully.

### Capacity exhausted

Hold all permits:

```text
next operation → BulkheadFullException
```

### Release on success

Permit becomes available after success.

### Release on failure

Permit becomes available after exception.

### Per destination isolation

```text
destination-a full
destination-b still available
```

---

# 24. Integration Tests

Create focused coverage:

```text
FhirRateLimitResilienceIT
FhirBulkheadResilienceIT
```

Demonstrate:

1. Healthy routed Patient READ succeeds.
2. Rate-limited operation is blocked before FHIR.
3. Bulkhead-rejected operation is blocked before FHIR.
4. Local rejection does not trigger retry.
5. Local rejection does not open the circuit.
6. Existing healthy behavior remains unchanged.

Keep tests deterministic.

Do not overload Docker/HAPI randomly.

---

# 25. Architecture Constraints

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

Within resilience:

```text
rate limiting
    ↓
bulkhead
    ↓
circuit breaker
    ↓
retry
```

Authentication and observability remain cross-cutting concerns.

Do not introduce:

```text
FhirService → rate limit
FhirService → bulkhead
mapping → resilience
```

Do not duplicate logic from Tasks 023–025.

---

# 26. Documentation

Create:

```text
docs/fhir/fhir-rate-limiting-bulkhead.md
```

Update when appropriate:

```text
docs/fhir/README.md
docs/fhir/fhir-architecture.md
docs/fhir/fhir-error-handling.md
docs/fhir/fhir-retry-resilience.md
docs/fhir/fhir-circuit-breaker.md
docs/fhir/fhir-audit-observability.md
docs/fhir/fhir-metrics-observability.md
docs/roadmap.md
README.md
```

Document:

- Rate Limiting vs Bulkhead
- configured limits
- fixed-window behavior
- concurrency permits
- per-destination isolation
- execution ordering
- local rejection behavior
- relationship with Circuit Breaker and Retry

Clearly state this is an in-memory learning foundation, not yet a distributed production rate-limiting solution.

---

# 27. Validation

Run:

```bash
mvn clean test
```

Then:

```bash
mvn clean verify -Pintegration
```

All Tasks 001–025 must remain green.

Do not report completion until both commands pass.

---

# 28. Git

Create:

```text
feature/fhir-rate-limiting-bulkhead
```

Baseline:

```text
main
```

Expected baseline:

```text
00c6fa5
```

Do not commit or push automatically.

At completion provide:

1. Files created.
2. Files modified.
3. Architecture summary.
4. Rate Limiter explanation.
5. Bulkhead explanation.
6. Important code explanations using WHAT / WHY / HOW / CONCEPT.
7. Thread-safety decisions.
8. Test results.
9. Problems encountered.
10. Git status.
11. Recommended commit message.

Recommended commit:

```text
feat: add FHIR rate limiting and bulkhead foundation
```

---

# Definition of Done

Task 026 is complete when:

- Rate Limiting is outside `FhirService`.
- Bulkhead protection is outside `FhirService`.
- Rate limiting is deterministic and testable.
- Bulkhead limits concurrent operations.
- Capacity is always released correctly.
- Protection is isolated per destination.
- Rate-limited requests fail before Bulkhead/Circuit/Retry/FHIR.
- Bulkhead-rejected requests fail before Circuit/Retry/FHIR.
- Local rejections do not open the Circuit Breaker.
- Local rejections do not trigger Retry.
- Thread safety is explicitly addressed.
- Tasks 001–025 remain green.
- Important code is explained using WHAT / WHY / HOW / CONCEPT.
- Documentation is updated.
