# Task 027 — FHIR Resilience Pipeline and Configuration

## Objective

Close the current interoperability and resilience phase by consolidating the protections introduced in Tasks 023–026 into a coherent, configurable integration pipeline.

The objective is **not** to add another resilience pattern. The objective is to make the existing pipeline explicit, configurable and verifiable as one system:

- structured error classification;
- retry;
- circuit breaker;
- rate limiting;
- bulkhead;
- audit;
- metrics.

`FhirService` remains focused on FHIR operations.

---

## Why this task exists

Tasks 023–026 introduced several independent protections:

```text
Structured Errors
       ↓
Retry
       ↓
Circuit Breaker
       ↓
Rate Limiter
       ↓
Bulkhead
```

Each component works independently, but the platform now needs one explicit contract answering questions such as:

- What is the exact execution order?
- Which protections are configured globally?
- Which protections are isolated per destination?
- Which failures are local admission failures?
- Which failures represent dependency health?
- Which failures can be retried?
- What is counted as one logical operation?
- Can the complete pipeline be tested end-to-end?

Task 027 closes this phase by making those decisions explicit without moving resilience logic into `FhirService`.

---

# Architecture

The final execution pipeline for a routed Patient READ is:

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

Observability receives the result of the logical operation:

```text
                    ┌───────────────────┐
Logical Operation ──┤ FhirAuditRecorder │
                    └───────────────────┘

                    ┌─────────────────────┐
Logical Operation ──┤ FhirMetricsRecorder │
                    └─────────────────────┘
```

The layers have different responsibilities:

| Layer | Question answered |
|---|---|
| Mapping | How is external data transformed into FHIR? |
| Routing | Which named destination receives the operation? |
| Rate Limiter | Is another operation allowed to start now? |
| Bulkhead | Is there available concurrent capacity? |
| Circuit Breaker | Is the dependency currently healthy enough to call? |
| Retry | Should a transient failure be attempted again? |
| FhirService | Which FHIR interaction is executed? |
| Audit | What happened during this operation? |
| Metrics | What is happening in aggregate? |

---

# Scope

Task 027 adds a small configuration model for the resilience pipeline.

Suggested package:

```text
lab.healthcare.fhir.resilience
```

The existing subpackages remain responsible for their own implementations:

```text
resilience
├── FhirResilienceProperties
├── FhirResilienceConfiguration
├── ratelimit
├── bulkhead
├── circuit
└── retry
```

The exact class names may be adjusted if the existing codebase already has a clearer naming convention.

---

# Configuration

The resilience values must no longer depend exclusively on hardcoded defaults scattered through constructors.

A single configuration section should describe the policy:

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

These values represent defaults for the laboratory.

This task does **not** introduce a distributed configuration service, database, Redis or dynamic runtime administration.

---

# WHAT / WHY / HOW / CONCEPT

## 1. One resilience configuration boundary

### WHAT

`FhirResilienceProperties` represents the configuration of the resilience mechanisms.

### WHY

Rate limiting, bulkhead, circuit breaker and retry are parts of one integration policy. Configuration should be discoverable instead of scattered across constructors.

### HOW

Spring Boot binds the YAML configuration into one typed configuration model.

### CONCEPT

**Externalized configuration**: policy values can change without changing business logic.

---

## 2. Configuration is not business logic

### WHAT

The properties object stores values such as:

- maximum attempts;
- failure threshold;
- reset timeout;
- rate limit;
- concurrent capacity.

### WHY

Configuration answers **how much** protection exists, not **when** a failure is retryable.

### HOW

Eligibility remains based on `FhirErrorCategory` and the policies already introduced in previous tasks.

### CONCEPT

**Configuration ≠ policy decision**.

For example:

```text
maxAttempts = 3
```

does not mean:

```text
retry every exception
```

The retry policy still decides which categories are transient.

---

## 3. One explicit execution order

### WHAT

The pipeline order remains:

```text
Rate Limit
→ Bulkhead
→ Circuit Breaker
→ Retry
→ FHIR
```

### WHY

Changing the order changes system behavior.

For example:

- retrying a rate-limit rejection is meaningless;
- retrying `CIRCUIT_OPEN` is meaningless;
- placing the breaker inside each retry attempt can incorrectly treat intermediate failures as logical operation failures.

### HOW

`RoutingService` remains the orchestration boundary for the routed READ.

### CONCEPT

**Composition root / orchestration layer**.

---

## 4. Local admission failures

### WHAT

`RATE_LIMITED` and `BULKHEAD_FULL` are local failures.

### WHY

They do not indicate that the remote FHIR server is unhealthy.

### HOW

They stop before:

```text
Circuit Breaker
Retry
FHIR HTTP call
```

### CONCEPT

**Admission control**.

---

## 5. Dependency failures

### WHAT

These infrastructure categories can affect retry and circuit health:

```text
TIMEOUT
CONNECTION_ERROR
SERVER_ERROR
```

### WHY

These categories can indicate a temporary dependency problem.

### HOW

Retry evaluates them per attempt, while the circuit breaker evaluates the terminal outcome of the logical operation.

### CONCEPT

**Transient failure vs dependency health**.

---

## 6. Logical operation versus physical attempts

### WHAT

One caller request remains one logical operation.

Example:

```text
Attempt 1 → TIMEOUT
Attempt 2 → SUCCESS
```

The result is:

```text
logical operations = 1
success = 1
retry attempts = 1
```

### WHY

Metrics must not inflate traffic simply because resilience mechanisms performed recovery.

### HOW

The retry layer handles attempts while the terminal result is published to aggregate metrics.

### CONCEPT

**Business operation ≠ transport attempt**.

---

## 7. Per-destination isolation

### WHAT

The resilience state remains isolated by named FHIR destination.

Example:

```text
local-hapi
secured-lab
smart-lab
```

### WHY

A noisy or unhealthy destination must not automatically consume capacity or open protection for another destination.

### HOW

Existing registries continue using the destination/profile name as the isolation key.

### CONCEPT

**Bulkheading by dependency**.

---

## 8. No resilience inside FhirService

### WHAT

`FhirService` remains unchanged unless a minimal compilation-level adaptation is genuinely required.

### WHY

`FhirService` represents FHIR operations.

It should not know:

- retry counts;
- circuit states;
- rate windows;
- semaphore permits;
- metrics aggregation.

### CONCEPT

**Separation of concerns**.

---

# Configuration validation

Invalid resilience configuration must fail fast during application startup.

Examples:

| Invalid value | Expected behavior |
|---|---|
| `max-attempts < 1` | configuration failure |
| negative backoff | configuration failure |
| `failure-threshold < 1` | configuration failure |
| non-positive reset timeout | configuration failure |
| `max-operations < 1` | configuration failure |
| non-positive rate window | configuration failure |
| `max-concurrent-operations < 1` | configuration failure |

The application must not silently replace invalid values with arbitrary defaults.

---

# Observability contract

The existing audit and metrics model remains intact.

The task must preserve these distinctions:

### Audit

Audit can show individual attempts and the final outcome.

### Metrics

Metrics represent logical operations and aggregate dimensions.

### Sensitive information

The resilience configuration and observability output must not expose:

- access tokens;
- refresh tokens;
- client secrets;
- authorization codes;
- code verifiers;
- Patient JSON;
- clinical values.

---

# Integration tests

Task 027 should add an end-to-end resilience pipeline test proving the order and boundaries.

The test should cover at least:

## Scenario 1 — Successful operation

```text
Rate admitted
→ Bulkhead admitted
→ Circuit CLOSED
→ FHIR success
```

Expected:

```text
SUCCESS
```

---

## Scenario 2 — Rate limited

After consuming the configured admission capacity:

```text
RATE_LIMITED
```

Expected:

```text
No bulkhead acquisition
No circuit interaction
No retry
No FHIR call
```

---

## Scenario 3 — Bulkhead full

When concurrency capacity is exhausted:

```text
BULKHEAD_FULL
```

Expected:

```text
No circuit interaction
No retry
No FHIR call
```

---

## Scenario 4 — Transient failure with recovery

Example:

```text
Attempt 1 → CONNECTION_ERROR
Attempt 2 → SUCCESS
```

Expected:

```text
One logical success
Retry attempts recorded correctly
Circuit remains CLOSED
```

---

## Scenario 5 — Terminal infrastructure failures

After repeated logical infrastructure failures:

```text
Circuit → OPEN
```

The next operation should fail fast with:

```text
CIRCUIT_OPEN
```

Expected:

```text
No retry
No FHIR call
```

---

# Suggested unit tests

The final test names may follow the existing project conventions.

Recommended coverage:

```text
FhirResiliencePropertiesTest
FhirResilienceConfigurationTest
FhirResiliencePipelineTest
```

The pipeline tests should use deterministic dependencies:

- `MutableClock`;
- injectable sleeper;
- controlled FHIR supplier/stubs.

No test should require real waiting with `Thread.sleep`.

---

# Documentation

Create:

```text
docs/fhir/fhir-resilience.md
```

Update where appropriate:

```text
docs/fhir/README.md
docs/fhir/fhir-architecture.md
docs/fhir/fhir-routing.md
docs/fhir/fhir-error-handling.md
docs/fhir/fhir-retry.md
docs/fhir/fhir-circuit-breaker.md
docs/fhir/fhir-rate-limiting-bulkhead.md
docs/roadmap.md
README.md
```

The new resilience document should explain the complete pipeline rather than duplicating the individual documents.

---

# Non-goals

Task 027 does **not** add:

- Resilience4j;
- Redis;
- distributed rate limiting;
- Kafka;
- queues;
- database persistence;
- dynamic configuration APIs;
- dashboards;
- Prometheus;
- OpenTelemetry;
- new FHIR operations;
- Epic integration;
- Oracle Health integration;
- AI agents.

Those belong to later phases.

---

# Acceptance criteria

Task 027 is complete when:

1. resilience configuration is centralized and typed;
2. invalid configuration fails fast;
3. the execution order is explicit and preserved;
4. resilience remains outside `FhirService`;
5. isolation remains per destination;
6. rate limiting and bulkhead rejections do not affect circuit health;
7. retry and circuit breaker continue using structured error categories;
8. observability continues distinguishing attempts from logical operations;
9. an end-to-end resilience pipeline test proves the composition;
10. all previous tasks remain green.

---

# Commands

```bash
mvn clean test
```

```bash
mvn clean verify -Pintegration
```

Expected result:

```text
BUILD SUCCESS
```

---

# Branch

```text
feature/fhir-resilience-configuration
```

Baseline:

```text
main
```

Current baseline at task creation:

```text
1b5fa0f
```

---

# Suggested commit message

```text
feat: consolidate FHIR resilience configuration and pipeline
```

---

# Phase completion

Task 027 closes the current **FHIR integration foundation and resilience phase**.

At the end of this phase, the laboratory has:

```text
FHIR R4 operations
+ Validation
+ Search and pagination
+ History and versioning
+ $everything
+ Server profiles
+ OAuth 2.0
+ SMART on FHIR
+ Architecture boundaries
+ Mapping
+ Routing
+ Audit
+ Metrics
+ Structured errors
+ Retry
+ Circuit breaker
+ Rate limiting
+ Bulkhead
+ Consolidated resilience configuration
```

The next major phase can focus on **real interoperability targets and provider-specific integration**, such as:

```text
Epic
Oracle Health
Other FHIR implementations
Sandbox / developer environments
Real SMART authorization workflows
Provider-specific capability differences
```

The AI agent layer remains a later consumer of this interoperability platform, not a replacement for it.
