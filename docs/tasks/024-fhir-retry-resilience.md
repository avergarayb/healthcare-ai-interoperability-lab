# Task 024 — FHIR Retry and Resilience

## Objective

Add a **small, explicit resilience layer** to the FHIR Integration Service that retries only failures classified as transient by the existing error-handling foundation.

This task builds directly on:

- Task 020 — Routing Foundation
- Task 021 — Audit and Observability
- Task 022 — Metrics
- Task 023 — Structured Error Handling

The goal is **not** to add a generic enterprise resilience framework everywhere.

The goal is to learn and implement:

- transient vs permanent failures
- retry eligibility
- bounded retries
- exponential backoff
- retry observability
- preserving the existing architecture

---

# Learning requirement — IMPORTANT

While implementing this task, do not only generate code.

For the most important code sections, explain **what the code does and why it exists**.

After each significant implementation block, provide a short explanation:

```text
WHAT:
WHY:
HOW:
CONCEPT:
```

Explain practical portions such as:

1. retry decision logic
2. relationship between `FhirErrorCategory` and retry eligibility
3. retry loop
4. exponential backoff calculation
5. why retries are bounded
6. why permanent errors fail immediately
7. retry audit behavior
8. metrics: attempts vs logical operations
9. exception preservation
10. why resilience does not belong inside `FhirService`

Do not explain trivial getters, imports, or every line.

The repository must continue being both a **learning laboratory** and the foundation of a reusable healthcare interoperability component.

---

# 1. Problem

Task 023 gives the platform a structured error contract:

```text
NOT_FOUND
VALIDATION_ERROR
AUTHENTICATION_ERROR
AUTHORIZATION_ERROR
CONFLICT
SERVER_ERROR
TIMEOUT
CONNECTION_ERROR
UNKNOWN
```

Classification alone does not answer:

> Should the integration try again?

These failures are fundamentally different:

```text
Patient does not exist
```

versus:

```text
The FHIR server temporarily did not respond
```

The first should normally fail immediately.

The second may succeed if retried.

---

# 2. Architecture principle

Do not put retry logic inside `FhirService`.

Bad:

```text
FhirService
    ├── call server
    ├── classify exception
    ├── sleep
    ├── retry
    ├── metrics
    └── audit
```

Instead:

```text
Routing
   │
   ▼
Resilience Layer
   │
   ├── attempt
   ├── classify failure
   ├── decide retry
   └── backoff
           │
           ▼
      FhirService
           │
           ▼
      FHIR Server
```

Responsibilities:

```text
client         → FHIR operations
exception      → failure classification
resilience     → retry policy and execution
routing        → integration orchestration
observability  → audit and metrics
```

---

# 3. Package

Create:

```text
lab.healthcare.fhir.resilience
```

Target structure:

```text
lab.healthcare.fhir
├── client
├── server
├── auth
├── smart
├── mapping
├── routing
├── observability
├── exception
└── resilience
```

Do not move unrelated classes.

Task 024 is about resilience behavior, not another architecture refactor.

---

# 4. Retry model

Create a small explicit retry model.

Suggested concepts:

```text
FhirRetryPolicy
FhirRetryDecision
FhirRetryExecutor
```

The exact design may vary slightly if a cleaner implementation is justified, but responsibilities must remain explicit.

---

## 4.1 Retry policy

The policy answers:

> Given a classified FHIR error, should another attempt be made?

Use Task 023 structured error categories.

Suggested defaults:

| Category | Retry |
|---|---:|
| VALIDATION_ERROR | No |
| AUTHENTICATION_ERROR | No |
| AUTHORIZATION_ERROR | No |
| NOT_FOUND | No |
| CONFLICT | No by default |
| SERVER_ERROR | Yes |
| TIMEOUT | Yes |
| CONNECTION_ERROR | Yes |
| UNKNOWN | No by default |

Do not retry everything.

---

# 5. Bounded retries

Retries must always be bounded.

Suggested default:

```text
maxAttempts = 3
```

Meaning:

```text
Attempt 1
   ↓ failure
Attempt 2
   ↓ failure
Attempt 3
   ↓ failure
Final failure
```

Important:

```text
maxAttempts = 3
```

means three total executions.

It does **not** mean:

```text
1 execution + 3 retries
```

Implementation and tests must make this explicit.

---

# 6. Backoff

Use exponential backoff.

Suggested example:

```text
attempt 1 → immediate
attempt 2 → wait 100 ms
attempt 3 → wait 200 ms
```

Conceptually:

```text
delay = initialDelay × 2^(retryNumber - 1)
```

Suggested defaults:

```text
initialDelay = 100 ms
maxAttempts = 3
```

Do not add random jitter yet.

Keep this version deterministic and easy to test.

---

# 7. Retry execution

Create a retry executor responsible for:

```text
execute(operation)
```

Conceptually:

```text
attempt operation

if success:
    return result

if failure:
    classify error

    if retryable and attempts remain:
        wait
        retry

    otherwise:
        throw final failure
```

The executor must not know:

- Patient JSON
- destination URLs
- OAuth secrets
- SMART details

It operates on an executable integration operation.

---

# 8. Integration with RoutingService

Integrate resilience at the orchestration level:

```text
RoutingService
      │
      ▼
FhirRetryExecutor
      │
      ▼
FhirService.readPatient(...)
```

Routing still owns:

- destination selection
- configured client acquisition
- correlation context
- publishing audit events

Resilience owns:

- retry decision
- attempt counting
- delay calculation
- repeated execution

Do not add retry conditionals throughout `FhirService`.

---

# 9. Observability

Retries must be observable.

A failure that succeeds after retry should not look identical to an operation that succeeded immediately.

At minimum, audit must represent something equivalent to:

```text
attempt 1 → FAILURE → retry
attempt 2 → SUCCESS
```

Do not log:

- access tokens
- client secrets
- refresh tokens
- authorization codes
- Patient JSON
- clinical payloads

Correlation IDs from Task 021 must continue linking the logical operation.

---

# 10. Metrics

Clarify:

## Logical operation

Example:

```text
Read Patient patient-001
```

One integration operation.

## Attempts

Example:

```text
Attempt 1 → timeout
Attempt 2 → success
```

Two execution attempts.

For this task, preserve existing logical-operation metrics behavior unless retry metrics are explicitly added.

Do not accidentally count one logical operation as multiple successful operations.

Optional retry metrics:

```text
retryAttempts
operationsRetried
```

Only add them if they remain simple and well tested.

---

# 11. Exception behavior

The final caller must still receive a meaningful structured exception.

Examples:

```text
NOT_FOUND
```

fails immediately.

```text
TIMEOUT
```

may retry until attempts are exhausted.

When retries are exhausted:

- preserve structured error category
- preserve cause
- do not replace with an unstructured generic error
- do not expose credentials or sensitive payloads

---

# 12. Tests

Add focused unit tests.

## Retry policy

```text
VALIDATION_ERROR → no retry
NOT_FOUND → no retry
AUTHENTICATION_ERROR → no retry
SERVER_ERROR → retry
TIMEOUT → retry
CONNECTION_ERROR → retry
UNKNOWN → no retry
```

## Retry executor

Test:

### Success on first attempt

```text
attempts = 1
```

### Temporary failure then success

```text
attempt 1 → TIMEOUT
attempt 2 → SUCCESS
```

### Retry exhaustion

```text
attempt 1 → CONNECTION_ERROR
attempt 2 → CONNECTION_ERROR
attempt 3 → CONNECTION_ERROR
final failure
```

### Permanent failure

```text
NOT_FOUND
```

Expected:

```text
attempts = 1
```

### Backoff

Test calculation separately.

Avoid unnecessary real sleeps.

Prefer an injectable waiting abstraction if needed, or test delay calculation independently.

The test suite must not become slow because of `Thread.sleep`.

---

# 13. Integration test

Add integration-level coverage demonstrating:

```text
transient failure → retry → success
```

A deterministic fake/test operation is acceptable.

Do not depend on the public internet.

Existing tests for:

- local-hapi
- OAuth Client Credentials
- SMART
- mapping
- routing
- audit
- metrics
- error handling

must continue passing.

---

# 14. What NOT to implement

Do not add yet:

- Resilience4j
- Circuit Breaker
- Bulkhead
- Kafka
- RabbitMQ integration
- Dead Letter Queue
- database persistence
- distributed retry coordination
- unrelated OAuth retry behavior
- retrying permanent validation errors
- generic `catch (Exception)` retries
- automatic retries for non-idempotent CREATE/POST operations

This task focuses on a safe first resilience foundation.

---

# 15. Important constraint: READ only

Current routing functionality is centered around:

```text
READ Patient
```

Retry behavior initially applies to this safe, idempotent operation.

Do not automatically generalize retries to:

```text
CREATE
UPDATE
DELETE
```

Retrying non-idempotent operations can produce duplicates or unintended effects.

Future tasks can address idempotency explicitly.

---

# 16. Documentation

Create:

```text
docs/fhir/fhir-retry-resilience.md
```

Document:

1. transient vs permanent failures
2. retry categories
3. bounded retries
4. exponential backoff
5. max attempts semantics
6. READ idempotency
7. why CREATE is not retried automatically
8. relationship with Task 023
9. retry observability

Update where appropriate:

```text
docs/fhir/README.md
docs/fhir/fhir-architecture.md
docs/roadmap.md
README.md
```

---

# 17. Dependency flow

Target:

```text
Mapping
   │
   ▼
Routing
   │
   ├──────────────► Observability
   │
   ▼
Resilience
   │
   ▼
FhirService
   │
   ▼
FHIR Server
```

Error flow:

```text
FHIR failure
     │
     ▼
FhirErrorClassifier
     │
     ▼
Structured FhirErrorDetails
     │
     ▼
FhirRetryPolicy
     │
 ┌───┴────┐
 │        │
Retry     Fail
 │        │
 ▼        ▼
Backoff  Final exception
 │
 ▼
Retry operation
```

---

# 18. Acceptance criteria

Task 024 is complete when:

- [ ] A dedicated resilience package exists.
- [ ] Retry eligibility uses Task 023 structured categories.
- [ ] Permanent errors fail immediately.
- [ ] Transient errors can retry.
- [ ] Retries are bounded.
- [ ] Exponential backoff is deterministic and tested.
- [ ] Retry logic is not embedded in `FhirService`.
- [ ] `RoutingService` integrates resilience cleanly.
- [ ] Correlation/audit behavior remains meaningful.
- [ ] Metrics do not incorrectly double-count logical operations.
- [ ] Sensitive credentials and clinical payloads are not logged.
- [ ] Retry exhaustion preserves structured error information.
- [ ] Existing Tasks 001–023 continue passing.
- [ ] Unit tests are added.
- [ ] Integration coverage is added.
- [ ] Documentation is added.
- [ ] Important code sections are explained using WHAT / WHY / HOW / CONCEPT.

---

# 19. Branch

Create the branch from current `main`:

```bash
git checkout main
git pull origin main
git checkout -b feature/fhir-retry-resilience
```

Baseline:

```text
5419930
```

Expected commit message:

```text
feat: add FHIR retry and resilience foundation
```

---

# Expected learning outcome

After Task 024, you should be able to explain:

- what makes an error transient
- why retrying everything is dangerous
- the difference between retries and attempts
- why exponential backoff exists
- why idempotency matters
- why retries belong outside `FhirService`
- how structured error classification enables resilience policies
- how retry behavior can be observed without leaking healthcare data

---

# Next step

After completing Task 024, do not commit automatically.

First provide:

1. implementation summary
2. architecture decisions
3. important code explanations using WHAT / WHY / HOW / CONCEPT
4. test results
5. problems encountered
6. `git status`
7. `git diff --stat`

No commit or push until explicitly requested.
