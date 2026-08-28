# Task 022 — FHIR Metrics & Telemetry Foundation

## Objective

Extend the observability foundation from Task 021 with a small metrics layer for FHIR integration operations.

The goal is to answer operational questions such as:

- How many FHIR operations succeeded?
- How many failed?
- Which operation types are being used?
- Which destinations have failures?
- How long do FHIR operations take?
- Are failures concentrated on one destination?

This task adds **metrics**, not a full monitoring platform.

The flow becomes:

```text
External request
      ↓
   Mapping
      ↓
   Routing
      ↓
 Authentication
      ↓
 FHIR operation
      ↓
 Audit / Observability
      ├── Audit event
      └── Metrics
```

---

## Baseline

Task 022 starts from `main` after Task 021:

```text
019 → Mapping & Transformation Foundation
020 → Routing Foundation
021 → Audit & Observability Foundation
```

Task 021 already provides:

```text
FhirOperationContext
FhirAuditEvent
FhirAuditRecorder
LoggingFhirAuditRecorder
```

Reuse the existing observability model.

Do not redesign Tasks 018–021.

---

## Why metrics exist

Audit answers:

> What happened to this particular operation?

Metrics answer:

> What is happening across many operations?

Example audit event:

```text
correlationId=abc-123
destination=local-hapi
operation=READ
resourceType=Patient
resourceId=patient-001
outcome=SUCCESS
durationMs=41
```

A metric can aggregate many operations:

```text
FHIR operations:
READ     120
CREATE    45
UPDATE    18
DELETE     7
```

Or:

```text
FHIR failures:
local-hapi      2
secured-lab     5
```

The two mechanisms complement each other.

---

## Scope

Implement a minimal metrics foundation that captures:

1. total FHIR operations;
2. successful operations;
3. failed operations;
4. operation type;
5. destination;
6. resource type where available;
7. operation duration.

The implementation should be replaceable and must not require an external monitoring server.

---

## Non-goals

Do not implement:

- Prometheus server;
- Grafana;
- OpenTelemetry Collector;
- Kubernetes monitoring;
- distributed tracing;
- alerting;
- dashboards;
- persistent metrics database;
- Kafka;
- RabbitMQ;
- complex SLO/SLA management;
- high-cardinality metrics;
- PHI metrics;
- full request/response logging.

Those may be future tasks.

---

## Architecture

Create or extend:

```text
lab.healthcare.fhir.observability
```

Conceptually:

```text
observability
├── FhirOperationContext
├── FhirAuditEvent
├── FhirAuditRecorder
├── LoggingFhirAuditRecorder
├── FhirMetricsRecorder
└── InMemoryFhirMetricsRecorder
```

The exact names may differ if responsibilities remain clear.

---

## Responsibility boundaries

### Audit

Answers:

```text
What happened to this operation?
```

It retains operation-level information such as:

```text
correlationId
destination
operation
resource identity
outcome
status
duration
```

### Metrics

Answers:

```text
How many operations are happening?
How many succeed/fail?
How long do they take?
```

Metrics must aggregate rather than retain individual clinical payloads.

### Routing

Remains responsible for:

```text
destination selection
```

Metrics must not resolve destinations.

### Authentication

Remains responsible for:

```text
credential acquisition
request authorization
```

Metrics must not expose credentials.

### FhirService

Remains responsible for:

```text
FHIR operations
```

Do not turn it into a metrics implementation.

---

# Metrics model

Define a small metric model.

Conceptually:

```text
FhirMetricSnapshot
 ├── totalOperations
 ├── successfulOperations
 ├── failedOperations
 ├── operationsByType
 ├── operationsByDestination
 └── duration statistics
```

Duration statistics may initially be simple:

```text
totalDurationMs
operationCount
```

which allows an average to be calculated.

Do not introduce a complex histogram implementation unless it is necessary.

---

# Metric dimensions

Allowed dimensions should remain bounded:

```text
operation
destination
resourceType
outcome
```

Do not use:

```text
patientId
identifier
correlationId
FHIR URL with query parameters
clinical values
```

as metric labels/dimensions.

These would create high-cardinality or sensitive metrics.

---

# Step 1 — Branch

Create:

```text
feature/fhir-metrics-observability
```

from `main`.

Do not work directly on `main`.

---

# Step 2 — Inspect Task 021

Review:

```text
FhirOperationContext
FhirAuditEvent
FhirAuditRecorder
LoggingFhirAuditRecorder
RoutingService
```

The metrics implementation should consume the same operation context/event information.

Do not duplicate operation metadata unnecessarily.

---

# Step 3 — Define FhirMetricsRecorder

Create a replaceable abstraction:

```text
FhirMetricsRecorder
```

Conceptually:

```java
record(FhirAuditEvent event)
```

or an equivalent small API.

The important point is that metrics can be replaced later without changing routing or FHIR business logic.

---

# Step 4 — In-memory implementation

Create:

```text
InMemoryFhirMetricsRecorder
```

This implementation is for:

```text
local development
tests
demonstration
```

It should aggregate counters rather than store complete audit events.

For example:

```text
totalOperations = 10
successfulOperations = 8
failedOperations = 2
```

and:

```text
READ = 6
CREATE = 3
UPDATE = 1
```

---

# Step 5 — Duration metrics

Use the duration already captured by Task 021.

Do not measure the same operation twice if the audit event already contains:

```text
durationMs
```

For example:

```text
totalDurationMs += event.durationMs
operationCount += 1
```

Then:

```text
averageDurationMs =
    totalDurationMs / operationCount
```

Use integer/long arithmetic carefully.

Do not claim percentile metrics unless they are actually implemented.

---

# Step 6 — Successful operation metrics

For:

```text
outcome=SUCCESS
```

increment:

```text
totalOperations
successfulOperations
```

and the appropriate bounded dimensions.

Example:

```text
destination=local-hapi
operation=READ
resourceType=Patient
```

---

# Step 7 — Failed operation metrics

For:

```text
outcome=FAILURE
```

increment:

```text
totalOperations
failedOperations
```

and the bounded dimensions.

Example:

```text
destination=local-hapi
operation=READ
resourceType=Patient
outcome=FAILURE
```

Do not include sensitive error details as metric labels.

---

# Step 8 — Integrate with Task 021

The intended composition is:

```text
FHIR operation
      ↓
FhirAuditEvent
      ├──────────────► FhirAuditRecorder
      │
      └──────────────► FhirMetricsRecorder
```

The audit recorder and metrics recorder are independent sinks.

Do not make:

```text
MetricsRecorder → AuditRecorder
```

or:

```text
AuditRecorder → MetricsRecorder
```

unless there is a compelling implementation reason.

Prefer a small composition point that records the same completed operation to both.

---

# Step 9 — Logging safety

Metrics must never contain:

```text
access_token
client_secret
refresh_token
authorization_code
code_verifier
complete FHIR Resource
patient identifier
clinical value
```

Metrics should contain only bounded operational dimensions.

---

# Step 10 — Unit tests

Create tests covering:

```text
successful operation increments success counters
failed operation increments failure counters
total operation counter
operation aggregation
destination aggregation
resource type aggregation
duration aggregation
average duration
```

Also test that high-cardinality/sensitive fields are not used as dimensions.

---

# Step 11 — Integration test

Create:

```text
FhirMetricsObservabilityIT
```

Demonstrate at least:

```text
RoutingService
      ↓
local-hapi
      ↓
Patient/patient-001
      ↓
SUCCESS metric
```

and one failure:

```text
unknown destination
      ↓
FAILURE metric
```

Verify that the aggregated metrics reflect both operations.

Do not require Prometheus, Grafana, or external services.

---

# Step 12 — Existing tests

Run:

```bash
cd services/fhir-integration-service
mvn clean test
```

Then:

```bash
mvn clean verify -Pintegration
```

All Tasks 001–021 must remain green.

Especially verify:

```text
FHIR CRUD
search
pagination
history
$everything
bundles
terminology validation
resource validation
OAuth 2.0
SMART
mapping
routing
audit
```

---

# Step 13 — Documentation

Create:

```text
docs/fhir/fhir-metrics-observability.md
```

Document:

- why metrics exist;
- audit vs metrics;
- metric model;
- allowed dimensions;
- duration aggregation;
- success/failure counters;
- in-memory implementation;
- security/PHI considerations;
- future Prometheus/OpenTelemetry integration.

Update:

```text
docs/fhir/README.md
docs/roadmap.md
README.md
```

---

# Model

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

---

# Audit vs Metrics

Use this distinction:

```text
AUDIT
-----
One operation
Correlation ID
Destination
Resource identity
Outcome
Status
Duration


METRICS
-------
Many operations
Counters
Aggregations
Operation type
Destination
Resource type
Duration statistics
```

For example:

```text
Audit:

correlationId=abc
Patient/patient-001
READ
SUCCESS
41ms
```

Metrics:

```text
READ / Patient / local-hapi
operations=120
success=117
failure=3
avgDurationMs=44
```

---

# Important distinction: metrics are not logs

Do not implement:

```text
one log line = one metric
```

Instead, metrics should aggregate:

```text
1000 READ operations
        ↓
counter = 1000
```

This keeps the metrics layer efficient and avoids excessive operational data.

---

# Future evolution

This foundation should make it possible to replace:

```text
InMemoryFhirMetricsRecorder
```

with:

```text
Prometheus
OpenTelemetry Metrics
Micrometer
Cloud monitoring
```

without modifying:

```text
MappingService
RoutingService
FhirService
Authentication
```

A future production implementation could expose:

```text
fhir_operations_total
fhir_operation_duration
fhir_operation_failures_total
```

but Task 022 does not require a Prometheus endpoint.

---

# Commercial relevance

A customer using an integration platform eventually asks:

> Is the integration healthy?

Metrics provide a platform-level answer:

```text
FHIR operations today: 18,421
Success rate: 99.7%
Average latency: 182 ms
Failures: 55
```

while audit can answer:

> What happened to this specific request?

The combination is much more useful than either alone.

---

# Acceptance criteria

- [ ] Branch `feature/fhir-metrics-observability`.
- [ ] Dedicated metrics abstraction.
- [ ] Metrics reuse Task 021 operation information.
- [ ] Total operation counter.
- [ ] Success counter.
- [ ] Failure counter.
- [ ] Operation aggregation.
- [ ] Destination aggregation.
- [ ] Resource type aggregation where available.
- [ ] Duration aggregation.
- [ ] Average duration calculation.
- [ ] Dimensions remain bounded.
- [ ] No patient ID as a metric dimension.
- [ ] No correlation ID as a metric dimension.
- [ ] No credentials in metrics.
- [ ] No complete FHIR payloads in metrics.
- [ ] Audit remains independent from metrics.
- [ ] Routing remains responsible for destination selection.
- [ ] FhirService does not become a metrics implementation.
- [ ] No database introduced.
- [ ] No Prometheus server required.
- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Tasks 001–021 remain green.
- [ ] Documentation created and updated.

---

# Dependencies

No new external dependency should be required.

Reuse existing:

```text
Spring Boot
HAPI FHIR
JUnit
Mockito
```

and the existing observability infrastructure.

---

# Git

Do not commit automatically.

At the end run:

```bash
git status
git diff --stat
git diff
```

Also:

```bash
git status --short
```

Report:

- classes created;
- metrics model;
- aggregation strategy;
- bounded dimensions;
- audit integration;
- security considerations;
- unit test count;
- integration test count;
- problems encountered;
- architectural decisions.

The commit will be performed separately.

---

# Definition of Done

Task 022 is complete when the integration service can aggregate FHIR operation counts and duration statistics by bounded operational dimensions while keeping metrics separate from audit, routing, authentication, mapping, and FHIR business logic.

The architecture must preserve:

```text
Mapping
   ≠
Routing
   ≠
Authentication
   ≠
FHIR Operations
   ≠
Audit
   ≠
Metrics
```

The implementation should remain small and replaceable so that a production metrics backend can be introduced later without redesigning the integration flow.

---

# Next step

Do not implement Task 023 as part of this task.
