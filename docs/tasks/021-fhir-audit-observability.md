# Task 021 — FHIR Integration Audit & Observability Foundation

## Objective

Introduce a small, framework-independent audit and observability layer for the FHIR integration flow.

The goal is to make an integration request traceable without mixing audit concerns into `FhirService`, mapping, routing, authentication, or SMART.

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
```

This task is intentionally limited. It establishes the foundation for knowing **what happened, where it happened, and whether it succeeded or failed**, without storing complete clinical resources.

---

## Baseline

Task 021 starts from `main` after Task 020:

```text
018 → Architecture Refactoring
019 → Mapping & Transformation Foundation
020 → Routing Foundation
```

The existing package boundaries must remain intact.

---

## Why audit and observability exist

A reusable healthcare integration component needs to answer questions such as:

- Which destination was called?
- Which FHIR operation was executed?
- Which resource type was involved?
- Did the operation succeed?
- When did it happen?
- How long did it take?
- Which request belongs to which integration flow?
- If something failed, where did it fail?

For example:

```text
correlationId = 8f3...
destination   = local-hapi
operation     = READ
resourceType  = Patient
resourceId    = patient-001
status        = SUCCESS
durationMs    = 42
```

The purpose is **traceability**, not clinical-data storage.

---

## Scope

Implement a minimal audit/observability foundation that can capture:

1. correlation ID;
2. destination profile;
3. FHIR resource type;
4. FHIR operation;
5. logical resource ID when available;
6. success/failure;
7. HTTP/FHIR status when available;
8. execution duration;
9. timestamp;
10. error category/message without storing sensitive payloads.

The implementation should work with the current routing and FHIR client architecture.

---

## Non-goals

Do not implement:

- database persistence;
- Elasticsearch/OpenSearch;
- Grafana;
- Prometheus server;
- distributed tracing infrastructure;
- OpenTelemetry collector;
- Kafka;
- RabbitMQ;
- log aggregation platform;
- PHI persistence;
- complete FHIR Resource payload logging;
- access-log storage;
- complex compliance reporting;
- user-management/audit UI.

Those can be future tasks.

---

## Architecture

Create a dedicated package:

```text
lab.healthcare.fhir.observability
```

Conceptually:

```text
observability
├── FhirAuditEvent
├── FhirAuditRecorder
├── FhirOperationContext
└── AuditException (only if genuinely required)
```

The exact names may differ if the responsibilities remain clear.

---

## Responsibility boundaries

### Mapping

Responsible for:

```text
External JSON
      ↓
FHIR Resource
```

It should not record clinical payloads in audit events.

### Routing

Responsible for:

```text
FHIR Resource
      ↓
Destination
```

The selected destination should be available to the observability layer.

### Authentication

Responsible for:

```text
Credential acquisition
      ↓
FHIR request authorization
```

Do not log:

```text
access_token
client_secret
authorization_code
refresh_token
```

### FhirService

Responsible for:

```text
FHIR operation
```

Do not turn `FhirService` into an audit implementation.

### Observability

Responsible for:

```text
what happened
when
where
result
duration
correlation
```

---

# Audit event model

Create a small immutable model.

Conceptually:

```text
FhirAuditEvent
 ├── timestamp
 ├── correlationId
 ├── destination
 ├── operation
 ├── resourceType
 ├── resourceId
 ├── outcome
 ├── status
 ├── durationMs
 └── error
```

Possible outcomes:

```text
SUCCESS
FAILURE
```

Possible operations:

```text
READ
CREATE
UPDATE
DELETE
SEARCH
OPERATION
```

Only include operations actually supported by the current implementation.

Do not create a large enum containing every possible FHIR operation.

---

# Correlation ID

Every audited integration operation should have a correlation ID.

Example:

```text
8d4c7e2a-...
```

If the application already has a correlation ID, reuse it.

If not, generate one.

The same ID should allow the operation to be traced across:

```text
Mapping
Routing
Authentication
FHIR request
Audit
```

Do not generate a different ID for every internal method call.

---

# What should be logged

Good:

```text
destination=local-hapi
operation=READ
resourceType=Patient
resourceId=patient-001
outcome=SUCCESS
status=200
durationMs=38
correlationId=...
```

Bad:

```text
patient={complete Patient JSON}
access_token=...
client_secret=...
```

The audit layer must not intentionally persist or log full clinical payloads or credentials.

---

# Step 1 — Branch

Create:

```text
feature/fhir-audit-observability
```

from `main`.

Do not work directly on `main`.

---

# Step 2 — Inspect existing architecture

Review:

```text
FhirService
RoutingService
FhirClientFactory
FhirServerProfileRegistry
Authentication
```

The goal is to identify the smallest integration point.

Do not redesign Tasks 018–020.

---

# Step 3 — Define FhirOperationContext

Create a small context object containing information needed during an integration operation.

Conceptually:

```text
FhirOperationContext
 ├── correlationId
 ├── destination
 ├── operation
 ├── resourceType
 └── resourceId
```

Do not place authentication credentials in the context.

Do not place the complete FHIR Resource in the context.

---

# Step 4 — Define FhirAuditEvent

The event represents the completed operation.

Conceptually:

```text
FhirAuditEvent
 ├── context
 ├── timestamp
 ├── outcome
 ├── status
 ├── durationMs
 └── error
```

Keep it immutable where practical.

---

# Step 5 — Define FhirAuditRecorder

Create:

```text
FhirAuditRecorder
```

Its initial implementation may simply write structured information to the application logger.

Example:

```text
FHIR_AUDIT
correlationId=...
destination=local-hapi
operation=READ
resourceType=Patient
resourceId=patient-001
outcome=SUCCESS
status=200
durationMs=...
```

The first implementation does not need a database.

The abstraction exists so that a future implementation could send events to:

```text
database
SIEM
OpenTelemetry
message broker
audit service
```

without changing FHIR business logic.

---

# Step 6 — Audit successful operations

At least one real FHIR operation must generate an audit event.

Use an existing operation such as:

```text
Patient read
```

The event must include:

```text
destination
operation
resourceType
resourceId
outcome
duration
correlationId
```

---

# Step 7 — Audit failures

Demonstrate a failure, for example:

```text
unknown routing destination
```

or:

```text
FHIR resource not found
```

The audit event should indicate:

```text
outcome=FAILURE
```

and include a safe error category/message.

Do not include:

```text
access token
client secret
complete request payload
complete FHIR response
```

---

# Step 8 — Duration

Measure elapsed time around the actual operation.

Conceptually:

```text
start
  ↓
FHIR operation
  ↓
end
  ↓
durationMs
```

Use a monotonic clock for duration measurement where appropriate.

Do not use wall-clock timestamps to calculate elapsed time.

---

# Step 9 — Routing integration

The selected routing destination must appear in the audit event.

Example:

```text
RoutingRequest
destination=local-hapi
       ↓
RoutingService
       ↓
FHIR operation
       ↓
Audit
destination=local-hapi
```

Do not make the audit layer resolve destinations itself.

Routing remains responsible for destination selection.

---

# Step 10 — Authentication safety

Verify that the observability implementation does not log:

```text
Bearer token
client secret
authorization code
refresh token
PKCE verifier
```

Especially inspect logging around:

```text
OAuth2TokenClient
SmartTokenProvider
AuthorizationCodeClient
BearerAccessTokenInterceptor
```

Do not modify authentication behavior unless required to prevent credential leakage.

---

# Step 11 — Unit tests

Create tests covering:

```text
successful audit event
failed audit event
correlation ID
destination
operation
resource type
resource ID
duration
safe error handling
```

Also test that sensitive values are not present in the rendered/logged representation where practical.

---

# Step 12 — Integration test

Create:

```text
FhirAuditObservabilityIT
```

Demonstrate at least:

```text
RoutingService
      ↓
local-hapi
      ↓
Patient/patient-001
      ↓
audit event
```

and one failure.

The integration test should verify the behavior without requiring an external observability platform.

---

# Step 13 — Existing tests

Run:

```bash
cd services/fhir-integration-service
mvn clean test
```

Then:

```bash
mvn clean verify -Pintegration
```

All Tasks 001–020 must remain green.

Especially verify:

```text
CRUD
search
pagination
history
$everything
bundles
terminology validation
resource validation
OAuth 2.0
SMART
server configuration
mapping
routing
```

---

# Step 14 — Documentation

Create:

```text
docs/fhir/fhir-audit-observability.md
```

Document:

- why observability exists;
- audit event model;
- correlation IDs;
- successful operations;
- failures;
- duration;
- routing integration;
- authentication safety;
- what is intentionally not logged;
- future persistence/telemetry options.

Update:

```text
docs/fhir/README.md
docs/roadmap.md
README.md
```

---

# Model

```text
                  FhirOperationContext
                          │
                          ▼
                   FHIR operation
                          │
                    ┌─────┴─────┐
                    ▼           ▼
                 success      failure
                    │           │
                    └─────┬─────┘
                          ▼
                   FhirAuditEvent
                          │
                          ▼
                  FhirAuditRecorder
                          │
                          ▼
                    Application Log
```

---

# Example

Successful read:

```text
FHIR_AUDIT
correlationId=abc-123
destination=local-hapi
operation=READ
resourceType=Patient
resourceId=patient-001
outcome=SUCCESS
status=200
durationMs=41
```

Failed routing:

```text
FHIR_AUDIT
correlationId=def-456
destination=does-not-exist
operation=READ
resourceType=Patient
resourceId=patient-001
outcome=FAILURE
error=DESTINATION_NOT_FOUND
```

No credential or clinical payload should appear.

---

# Important distinction

Audit is not the same as logging everything.

The objective is:

```text
Traceability
+
Operational visibility
+
Security-conscious diagnostics
```

not:

```text
Store every FHIR payload
```

For healthcare integrations, minimizing PHI exposure in operational logs is a deliberate architectural constraint.

---

# Future evolution

This foundation should make it possible to later add:

```text
FhirAuditRecorder
       │
       ├── Logger
       ├── OpenTelemetry
       ├── SIEM
       ├── Database
       └── Audit Service
```

without changing:

```text
MappingService
RoutingService
FhirService
```

Future tasks may add:

- OpenTelemetry tracing;
- metrics;
- persistent audit records;
- dashboards;
- alerting;
- compliance-oriented audit reporting.

Those are out of scope for Task 021.

---

# Commercial relevance

A reusable integration service needs operational traceability.

A future customer may ask:

> "Did our Patient request reach the EHR?"

The integration platform should be able to answer:

```text
Yes

correlationId: ...
destination: Epic
operation: CREATE
resource: Patient
result: SUCCESS
duration: ...
```

without exposing the patient's complete clinical record in application logs.

This becomes an important part of a production integration platform.

---

# Acceptance criteria

- [ ] Branch `feature/fhir-audit-observability`.
- [ ] Dedicated `observability` package.
- [ ] Immutable audit event model.
- [ ] Correlation ID supported.
- [ ] Destination included.
- [ ] FHIR operation included.
- [ ] Resource type included.
- [ ] Resource ID included when available.
- [ ] Success and failure outcomes supported.
- [ ] Duration measured.
- [ ] Safe error information captured.
- [ ] No access tokens logged.
- [ ] No client secrets logged.
- [ ] No authorization codes logged.
- [ ] No refresh tokens logged.
- [ ] No complete FHIR payloads logged intentionally.
- [ ] Routing remains responsible for destination selection.
- [ ] FhirService does not become an audit implementation.
- [ ] No database introduced.
- [ ] No message broker introduced.
- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Tasks 001–020 remain green.
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

and the existing application logging infrastructure.

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
- package created;
- audit model;
- correlation strategy;
- routing integration;
- sensitive-data protection;
- unit test count;
- integration test count;
- problems encountered;
- architectural decisions.

The commit will be performed separately.

---

# Definition of Done

Task 021 is complete when a FHIR integration operation can be traced using a correlation ID and produces a structured audit event containing destination, operation, resource identity, outcome, status, and duration, without logging credentials or complete clinical payloads.

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
Observability
```

The implementation should remain small and replaceable so that future production telemetry or persistent auditing can be introduced without redesigning the FHIR business layer.

---

# Next step

Do not implement Task 022 as part of this task.
