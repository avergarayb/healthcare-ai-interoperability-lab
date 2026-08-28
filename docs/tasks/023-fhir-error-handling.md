# Task 023 — FHIR Error Handling & Resilience Foundation

## Objective

Introduce a structured error-handling layer for the FHIR integration flow.

The goal is to make failures predictable, classifiable, observable, and safe to expose to callers without leaking implementation details, credentials, or clinical payloads.

The service should distinguish between:

```text
Validation / client error
Authentication error
Authorization error
Not found
Conflict
FHIR server error
Timeout
Connection error
Unknown integration error
```

This task establishes the foundation for resilience.

**Important:** retry, backoff, circuit breaker, idempotency, and asynchronous processing are future tasks. Task 023 only classifies and propagates errors correctly.

---

## Baseline

Task 023 starts from `main` after Task 022:

```text
019 → Mapping & Transformation Foundation
020 → Routing Foundation
021 → Audit & Observability Foundation
022 → Metrics & Observability Foundation
```

The existing exception:

```text
lab.healthcare.fhir.exception.FhirClientException
```

must evolve without breaking the existing architecture.

---

## Why error handling exists

A reusable interoperability component must distinguish:

```text
Patient not found
```

from:

```text
FHIR server unavailable
```

and:

```text
OAuth token rejected
```

These situations have completely different operational meanings.

For example:

```text
404 → NOT_FOUND
409 → CONFLICT
401 → AUTHENTICATION_ERROR
403 → AUTHORIZATION_ERROR
500 → SERVER_ERROR
timeout → TIMEOUT
connection refused → CONNECTION_ERROR
```

The objective is not simply to catch every exception.

The objective is to classify the failure so that future layers can decide what to do.

---

# Architecture

Create or extend:

```text
lab.healthcare.fhir.exception
```

Conceptually:

```text
exception
├── FhirClientException
├── FhirErrorCategory
└── FhirErrorDetails
```

The exact names may differ if the responsibilities remain clear.

---

# Error model

Create a bounded error classification.

Possible categories:

```text
VALIDATION_ERROR
AUTHENTICATION_ERROR
AUTHORIZATION_ERROR
NOT_FOUND
CONFLICT
SERVER_ERROR
TIMEOUT
CONNECTION_ERROR
UNKNOWN
```

Do not create dozens of categories.

The category should answer:

> What kind of integration failure occurred?

---

# FhirErrorDetails

Create a small immutable model containing safe diagnostic information.

Conceptually:

```text
FhirErrorDetails
 ├── category
 ├── status
 ├── operation
 ├── destination
 ├── resourceType
 ├── resourceId
 └── message
```

Do not include:

```text
access_token
client_secret
refresh_token
authorization_code
code_verifier
complete FHIR Resource
complete HTTP body
```

---

# FhirClientException

`FhirClientException` should provide structured information about the failure.

Conceptually:

```text
FhirClientException
    └── FhirErrorDetails
```

The existing callers should still be able to catch:

```java
FhirClientException
```

without needing to know the underlying HAPI exception type.

---

# Step 1 — Branch

Create:

```text
feature/fhir-error-handling
```

from `main`.

Do not work directly on `main`.

---

# Step 2 — Inspect current exception handling

Review:

```text
FhirService
RoutingService
FhirClientFactory
OAuth2TokenClient
AuthorizationCodeClient
SmartTokenProvider
```

Identify the current exceptions thrown by:

```text
HAPI
HTTP
OAuth
routing
```

Do not change behavior unnecessarily.

---

# Step 3 — Classify HTTP/FHIR failures

Map common HTTP/FHIR statuses.

Recommended baseline:

```text
400 → VALIDATION_ERROR
401 → AUTHENTICATION_ERROR
403 → AUTHORIZATION_ERROR
404 → NOT_FOUND
409 → CONFLICT
408 → TIMEOUT
429 → SERVER_ERROR
5xx → SERVER_ERROR
```

If the current HAPI client exposes a more specific exception for a case, use the observed exception/status rather than guessing.

Do not assume every HAPI exception contains a status.

---

# Step 4 — Classify connection failures

Connection failures should become:

```text
CONNECTION_ERROR
```

Examples:

```text
connection refused
DNS failure
network unreachable
socket connection failure
```

Do not expose raw infrastructure stack traces to the external caller.

The original exception may remain available as the cause for diagnostics.

---

# Step 5 — Classify timeouts

Timeouts should become:

```text
TIMEOUT
```

A timeout must remain distinguishable from:

```text
CONNECTION_ERROR
```

because future retry logic may treat them differently.

Do not implement retry in Task 023.

---

# Step 6 — Authentication failures

OAuth failures must remain distinguishable.

Examples:

```text
token acquisition failure
invalid client
invalid token
expired authorization
```

Depending on where the failure occurs, classify it as:

```text
AUTHENTICATION_ERROR
```

or:

```text
AUTHORIZATION_ERROR
```

Do not log:

```text
client_secret
access_token
refresh_token
authorization_code
```

The existing:

```text
OAuth2TokenException
```

may remain an implementation-level exception, but the integration boundary should expose a safe category.

---

# Step 7 — Routing failures

Existing routing errors such as:

```text
DESTINATION_NOT_FOUND
DESTINATION_DISABLED
```

must remain distinguishable from FHIR server failures.

They should map to an appropriate integration error category without making `FhirService` aware of routing.

Do not introduce fallback routing.

For example:

```text
unknown destination
        ↓
RoutingException
        ↓
audit FAILURE
metrics FAILURE
safe error category
```

---

# Step 8 — Preserve causes

The structured exception should preserve the original cause where possible.

Conceptually:

```text
FhirClientException
      │
      ├── category
      ├── safe details
      └── cause
              ↓
         HAPI / HTTP / OAuth
```

This allows internal diagnostics without exposing internal implementation details to callers.

---

# Step 9 — Integrate with Audit

Task 021 already records:

```text
FhirAuditEvent
```

Failures should continue to produce:

```text
outcome=FAILURE
```

The error information should use the new bounded error classification.

Example:

```text
FHIR_AUDIT
correlationId=abc-123
destination=local-hapi
operation=READ
resourceType=Patient
resourceId=does-not-exist
outcome=FAILURE
status=404
error=NOT_FOUND
```

Do not put the complete FHIR OperationOutcome into the audit line.

---

# Step 10 — Integrate with Metrics

Task 022 already aggregates:

```text
SUCCESS
FAILURE
```

Metrics should continue to count failures.

Do not use the detailed error message as a metric label.

Do not use:

```text
patientId
correlationId
FHIR URL
OperationOutcome text
```

as metric dimensions.

The existing bounded dimensions remain:

```text
operation
destination
resourceType
outcome
```

---

# Step 11 — Safe error messages

External-facing messages should be safe.

Good:

```text
FHIR resource not found
FHIR server unavailable
FHIR authentication failed
FHIR authorization failed
FHIR request timed out
FHIR connection failed
```

Avoid returning:

```text
java.net.ConnectException: ...
```

or:

```text
Bearer eyJ...
```

or:

```text
client_secret=...
```

or complete server responses containing clinical data.

---

# Step 12 — Unit tests

Create tests for:

```text
400 → VALIDATION_ERROR
401 → AUTHENTICATION_ERROR
403 → AUTHORIZATION_ERROR
404 → NOT_FOUND
409 → CONFLICT
5xx → SERVER_ERROR
timeout → TIMEOUT
connection failure → CONNECTION_ERROR
unknown exception → UNKNOWN
```

Also test:

```text
cause is preserved
safe details are present
credentials are not included
FHIR payload is not included
```

---

# Step 13 — Integration tests

Create:

```text
FhirErrorHandlingIT
```

Demonstrate real failures using the existing local infrastructure.

At minimum:

```text
Patient does-not-exist
        ↓
404
        ↓
NOT_FOUND
```

and:

```text
unknown routing destination
        ↓
RoutingException
        ↓
appropriate safe category
```

If practical, demonstrate one server-side or authentication failure using existing infrastructure.

Do not introduce a new external dependency just to create failures.

---

# Step 14 — Audit and metrics verification

The integration tests should confirm that a failure also reaches:

```text
Audit
Metrics
```

For example:

```text
404
 ↓
FhirErrorCategory.NOT_FOUND
 ↓
Audit FAILURE
 ↓
Metrics failure++
```

Do not duplicate instrumentation.

Reuse the existing Task 021/022 flow.

---

# Step 15 — Existing tests

Run:

```bash
cd services/fhir-integration-service
mvn clean test
```

Then:

```bash
mvn clean verify -Pintegration
```

All Tasks 001–022 must remain green.

Especially verify:

```text
CRUD
search
pagination
history
$everything
bundles
validation
OAuth 2.0
SMART
mapping
routing
audit
metrics
```

---

# Error flow

The intended model is:

```text
FHIR operation
      │
      ├── success
      │      ↓
      │   SUCCESS
      │
      └── exception
             ↓
       Error classification
             ↓
       FhirClientException
             │
       ┌─────┴─────┐
       ▼           ▼
     Audit       Metrics
```

The error classification should happen at the appropriate integration boundary.

---

# Example mappings

### Resource not found

```text
HTTP 404
    ↓
NOT_FOUND
    ↓
FhirClientException
    ↓
Audit FAILURE
Metrics failure++
```

### Wrong version

```text
HTTP 409
    ↓
CONFLICT
    ↓
FhirClientException
```

### Invalid token

```text
HTTP 401
    ↓
AUTHENTICATION_ERROR
```

### Insufficient scope

```text
HTTP 403
    ↓
AUTHORIZATION_ERROR
```

### Server unavailable

```text
HTTP 503 / 500
    ↓
SERVER_ERROR
```

### Timeout

```text
socket/request timeout
    ↓
TIMEOUT
```

### Connection refused

```text
connection refused
    ↓
CONNECTION_ERROR
```

---

# Important distinction: error handling vs resilience

Task 023:

```text
detect
classify
propagate
audit
measure
```

Future tasks:

```text
retry
backoff
circuit breaker
idempotency
queue
dead-letter handling
```

Do not implement those future mechanisms here.

For example:

```text
FHIR server returns 503
        ↓
Task 023
        ↓
SERVER_ERROR
```

Task 023 does **not** automatically call the server again.

---

# Commercial relevance

A reusable integration service should not force every customer to understand HAPI internals.

Instead of exposing:

```text
ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException
```

the integration platform can expose:

```text
NOT_FOUND
```

This gives customer applications a stable contract even if the underlying FHIR implementation changes.

For example:

```text
Customer Application
        ↓
FHIR Integration Service
        ↓
HAPI / Epic / other FHIR server
```

The customer's code should depend on the integration contract, not directly on HAPI exception classes.

---

# Future evolution

Task 023 prepares the architecture for:

```text
023 → Error Handling
024 → Retry / Backoff
025 → Circuit Breaker
026 → Idempotency
027 → Async Integration
```

The classification introduced here is important because future resilience decisions depend on it.

For example:

```text
NOT_FOUND
    → normally do not retry

VALIDATION_ERROR
    → do not retry

AUTHENTICATION_ERROR
    → refresh/re-authentication may be required

TIMEOUT
    → potentially retry

CONNECTION_ERROR
    → potentially retry

SERVER_ERROR
    → potentially retry

CONFLICT
    → requires business-specific handling
```

Task 023 only classifies. It does not implement these policies.

---

# Security considerations

The implementation must never intentionally expose:

```text
access_token
client_secret
refresh_token
authorization_code
code_verifier
Authorization header
complete Patient JSON
complete Observation JSON
clinical values
```

Safe operational information includes:

```text
category
HTTP status
operation
destination
resource type
resource logical ID
correlation ID
```

Even resource IDs should not be placed in metric labels.

---

# Documentation

Create:

```text
docs/fhir/fhir-error-handling.md
```

Document:

- error categories;
- HTTP/FHIR mapping;
- OAuth errors;
- routing errors;
- connection errors;
- timeout handling;
- audit integration;
- metrics integration;
- safe error messages;
- preserved causes;
- distinction between error handling and resilience.

Update:

```text
docs/fhir/README.md
docs/roadmap.md
README.md
```

---

# Acceptance criteria

- [ ] Branch `feature/fhir-error-handling`.
- [ ] Structured FHIR error category.
- [ ] Structured safe error details.
- [ ] `FhirClientException` remains the integration boundary exception.
- [ ] HTTP 400 classified.
- [ ] HTTP 401 classified.
- [ ] HTTP 403 classified.
- [ ] HTTP 404 classified.
- [ ] HTTP 409 classified.
- [ ] HTTP 5xx classified.
- [ ] Timeout classified.
- [ ] Connection failures classified.
- [ ] Unknown errors classified safely.
- [ ] Original cause preserved where possible.
- [ ] OAuth failures safely classified.
- [ ] Routing failures remain distinguishable.
- [ ] Audit receives failure events.
- [ ] Metrics count failures.
- [ ] No detailed error text used as metric label.
- [ ] No credentials logged.
- [ ] No complete FHIR payload logged.
- [ ] No retry implemented.
- [ ] No circuit breaker implemented.
- [ ] No database introduced.
- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Tasks 001–022 remain green.
- [ ] Documentation created and updated.

---

# Dependencies

No new external dependency should be required.

Reuse:

```text
Spring Boot
HAPI FHIR
JUnit
Mockito
```

and the existing authentication, routing, audit, and metrics infrastructure.

---

# Git

Do not commit automatically.

At the end run:

```bash
git status
git status --short
git diff --stat
git diff
```

Report:

- classes created/modified;
- error categories;
- HTTP mappings;
- timeout/connection handling;
- OAuth handling;
- routing handling;
- audit integration;
- metrics integration;
- security considerations;
- unit test count;
- integration test count;
- problems encountered;
- architectural decisions.

The commit will be performed separately.

---

# Definition of Done

Task 023 is complete when FHIR integration failures are converted into a stable, bounded, safe error model that callers can understand without depending on HAPI internals.

A failure must be:

```text
detected
   ↓
classified
   ↓
wrapped safely
   ↓
audited
   ↓
counted
```

without automatically retrying the operation.

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
   ≠
Error Handling
```

---

# Next step

Do not implement Task 024 as part of this task.
