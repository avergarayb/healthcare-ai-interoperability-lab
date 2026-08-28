# Task 020 — FHIR Routing Foundation

## Objective

Introduce a small routing layer into `fhir-integration-service`.

The goal is to allow the integration component to decide **which configured FHIR server should receive a FHIR Resource**, without putting routing logic inside `FhirService`.

```text
External JSON
      ↓
 MappingService
      ↓
 FHIR R4 Resource
      ↓
 RoutingService
      ↓
 FHIR Server Profile
      ↓
 FhirService
      ↓
 FHIR Server
```

This task is intentionally limited. It establishes routing boundaries without introducing a database, message broker, workflow engine, or complex enterprise routing rules.

---

## Baseline

Task 020 starts from `main` after Task 019:

```text
Task 018 → Architecture Refactoring
Task 019 → FHIR Mapping & Transformation Foundation
```

The package boundaries established in Task 018 must be preserved.

---

## Why routing exists

A real integration platform may connect to more than one FHIR server.

```text
Integration Service
       │
       ├── local-hapi
       ├── secured-lab
       └── another configured FHIR server
```

The application should not need to know how to construct the destination client.

```text
Business/application input
        ↓
Routing decision
        ↓
Configured destination
        ↓
FHIR client
```

This keeps destination selection separate from FHIR operations.

---

## Scope

Implement a minimal routing foundation based on the existing FHIR server profiles from Tasks 015 and 018.

The routing layer must be able to:

1. receive a routing request;
2. identify a destination server profile;
3. verify that the destination exists and is enabled;
4. obtain/use the appropriate FHIR client;
5. execute a FHIR operation against the selected destination;
6. fail explicitly when the destination is invalid.

---

## Non-goals

Do not implement:

- database-backed routing rules;
- Kafka;
- RabbitMQ routing;
- message queues;
- workflow orchestration;
- complex rule engines;
- geographic routing;
- load balancing;
- retry orchestration;
- circuit breakers;
- tenant routing;
- production-grade service discovery;
- dynamic configuration UI;
- EHR-specific routing;
- automatic Epic/Oracle routing;
- routing based on clinical data.

These may become future tasks.

---

## Architecture

Create:

```text
lab.healthcare.fhir.routing
```

Conceptually:

```text
routing
├── RoutingService
├── RoutingRequest
└── RoutingException
```

The exact class names may differ if responsibilities remain clear.

---

## Responsibility boundaries

### MappingService

Responsible for:

```text
External payload
        ↓
FHIR Resource
```

It does not decide the destination.

### RoutingService

Responsible for:

```text
FHIR Resource
        ↓
Destination selection
```

It does not transform the Resource.

### FhirService

Responsible for:

```text
FHIR operation
        ↓
FHIR server
```

It should not contain routing rules.

### FhirServerProfileRegistry

Already responsible for configured server profiles.

Reuse it. Do not duplicate server configuration inside the routing package.

---

## Target flow

```text
              External System
                    │
                    ▼
             MappingService
                    │
                    ▼
               FHIR Resource
                    │
                    ▼
             RoutingService
                    │
             destination
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
     FHIR Client A       FHIR Client B
          │                   │
          ▼                   ▼
        HAPI A              HAPI B
```

---

## Step 1 — Branch

Create:

```text
feature/fhir-routing-foundation
```

from `main`.

Do not work directly on `main`.

---

## Step 2 — Inspect existing server profiles

Reuse:

```text
FhirServerProfile
FhirServersProperties
FhirServerProfileRegistry
FhirClientFactory
```

Understand how Task 015 currently creates clients.

Do not create another configuration mechanism.

---

## Step 3 — Define RoutingRequest

Create a minimal routing request.

Conceptually:

```text
RoutingRequest
 ├── destination
 └── resource
```

Example:

```text
destination = local-hapi
resource = Patient
```

The destination should reference an existing configured server profile.

Do not put `baseUrl`, `clientSecret`, OAuth URLs, or SMART settings inside `RoutingRequest`.

Those belong to server/auth configuration.

---

## Step 4 — Define RoutingService

Create:

```text
RoutingService
```

Its responsibility is:

```text
RoutingRequest
      ↓
resolve destination
      ↓
obtain FHIR client
      ↓
execute requested operation
```

Keep the API small.

Do not create a generic workflow engine.

---

## Step 5 — Destination resolution

Given:

```text
destination = local-hapi
```

resolve:

```text
local-hapi
     ↓
FhirServerProfile
     ↓
FHIR client
```

If the destination does not exist:

```text
RoutingException
```

If the profile exists but is disabled:

```text
RoutingException
```

Do not silently fall back to another server.

---

## Step 6 — Reuse FhirClientFactory

Do not instantiate `FhirContext` or `IGenericClient` directly inside `RoutingService` if the existing factory can provide the client.

The factory remains the central location for FHIR client construction.

---

## Step 7 — Keep FhirService independent

Do not change `FhirService` to contain:

```text
if destination == ...
```

or:

```text
switch destination
```

Routing belongs outside it.

Preferred:

```text
RoutingService
      ↓
FhirClientFactory
      ↓
IGenericClient
```

while `FhirService` remains the FHIR operation service.

If a small composition change is required, document it rather than embedding routing rules in `FhirService`.

---

## Step 8 — First routing scenario

Demonstrate:

```text
RoutingRequest
destination = local-hapi
resource = Patient
```

Then perform a read:

```text
GET /Patient/patient-001
```

Expected:

```text
Patient/patient-001
```

The test must prove that the request went through the selected configured profile.

---

## Step 9 — Multiple configured destinations

Use the existing configuration mechanism to declare at least two profiles where practical.

Example:

```yaml
fhir:
  active-server: local-hapi

  servers:
    local-hapi:
      base-url: http://localhost:8080/fhir
      fhir-version: R4
      enabled: true

    example-org:
      base-url: https://example.org/fhir
      fhir-version: R4
      enabled: false
```

Do not make `example.org` an integration test dependency.

The purpose is to demonstrate that routing resolves by profile name, not by hardcoded URL.

---

## Step 10 — Invalid destination behavior

Test:

```text
destination = does-not-exist
```

Expected:

```text
RoutingException
```

Also test:

```text
destination = disabled-profile
```

Expected:

```text
RoutingException
```

Do not silently use `local-hapi`.

---

## Step 11 — Authentication compatibility

Routing must not bypass the authentication architecture created in Tasks 016–018.

```text
RoutingService
      ↓
FhirClientFactory
      ↓
profile
      ↓
authentication configuration
      ↓
IGenericClient
```

If a destination uses `NONE`, it remains unauthenticated.

If a destination uses `Client Credentials`, the existing token provider is used.

If a destination uses `SMART`, the existing SMART architecture remains responsible for authentication.

Task 020 does not implement new authentication.

---

## Step 12 — Mapping compatibility

The mapping layer from Task 019 must remain independent.

```text
External JSON
      ↓
MappingService
      ↓
Patient / Observation
      ↓
RoutingService
      ↓
FHIR destination
```

Do not make `MappingService` depend on `RoutingService`.

Preserve:

```text
mapping ≠ routing
```

---

## Step 13 — Unit tests

Create routing unit tests covering:

```text
valid destination
unknown destination
disabled destination
correct profile resolution
FHIR client acquisition
```

Tests should not require a real HAPI server when testing routing logic alone.

Use mocks where appropriate, but do not mock everything unnecessarily.

---

## Step 14 — Integration test

Create:

```text
FhirRoutingIT
```

Demonstrate:

```text
RoutingRequest
      ↓
RoutingService
      ↓
local-hapi
      ↓
Patient/patient-001
```

Where possible, verify the selected profile/base URL through the actual integration path.

Do not make external internet services part of the test.

---

## Step 15 — Existing tests

Run:

```bash
cd services/fhir-integration-service
mvn clean test
```

Then:

```bash
mvn clean verify -Pintegration
```

All Tasks 001–019 must remain green.

Especially verify:

```text
CRUD
pagination
history
$everything
terminology validation
resource validation
OAuth Client Credentials
SMART
mapping
server configuration
```

---

## Step 16 — Documentation

Create:

```text
docs/fhir/fhir-routing.md
```

Document:

- why routing exists;
- RoutingRequest;
- RoutingService;
- relationship with FhirServerProfile;
- relationship with FhirClientFactory;
- mapping vs routing;
- authentication compatibility;
- invalid destination behavior;
- why routing is intentionally simple;
- future evolution.

Update:

```text
docs/fhir/README.md
docs/roadmap.md
README.md
```

---

## Routing model

```text
                    RoutingRequest
                          │
                          ▼
                  RoutingService
                          │
                          ▼
              FhirServerProfileRegistry
                          │
                          ▼
                  FhirServerProfile
                          │
                          ▼
                   FhirClientFactory
                          │
                          ▼
                    IGenericClient
                          │
                          ▼
                      FHIR Server
```

---

## Important distinction

Routing answers:

> Where should this request go?

Mapping answers:

> How do I transform this data into FHIR?

Authentication answers:

> How am I authorized to call that destination?

FHIR client answers:

> How do I perform the FHIR operation?

These responsibilities must remain separate.

---

## Future evolution

Task 020 should make this future architecture possible:

```text
                    Integration Service
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
             Mapping               Routing
                │                     │
                └──────────┬──────────┘
                           ▼
                     FHIR Resource
                           │
                ┌──────────┼──────────┐
                ▼          ▼          ▼
              HAPI       Epic       Oracle
```

Future routing could eventually use:

```text
tenant
source system
destination
resource type
organization
environment
business rule
```

Those are out of scope for Task 020.

---

## Commercial relevance

Routing is a foundational capability for a reusable integration component.

A future customer could have:

```text
Application
    ↓
FHIR Integration Service
    ├── Development FHIR
    ├── Test FHIR
    └── Production FHIR
```

or:

```text
HealthTech
    ↓
Integration Service
    ├── Customer A → Epic
    ├── Customer B → Oracle
    └── Customer C → HAPI
```

Task 020 only establishes the basic destination-selection boundary.

---

## Acceptance criteria

- [ ] Branch `feature/fhir-routing-foundation`.
- [ ] Dedicated `routing` package.
- [ ] Routing is based on existing FHIR server profiles.
- [ ] No duplicate server configuration.
- [ ] No hardcoded destination URL in RoutingService.
- [ ] Unknown destination fails explicitly.
- [ ] Disabled destination fails explicitly.
- [ ] FhirClientFactory is reused.
- [ ] Existing authentication architecture remains intact.
- [ ] MappingService remains independent of routing.
- [ ] FhirService does not contain routing rules.
- [ ] No database introduced.
- [ ] No message broker introduced.
- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Tasks 001–019 remain green.
- [ ] Documentation created and updated.

---

## Dependencies

No new external dependency should be required.

Reuse existing:

```text
Spring Boot
HAPI FHIR
Jackson
JUnit
Mockito
```

where applicable.

---

## Git

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
- routing model;
- destination resolution;
- integration tests;
- unit test count;
- integration test count;
- problems encountered;
- architectural decisions.

The commit will be performed separately.

---

## Definition of Done

Task 020 is complete when the integration service can select a configured FHIR server by profile name and execute a FHIR operation against that destination without coupling routing logic to `FhirService`.

The architecture must preserve:

```text
Mapping
   ≠
Routing
   ≠
Authentication
   ≠
FHIR Operations
```

The implementation should be small enough to understand and strong enough to support future multi-destination integrations.

---

## Next step

Do not implement Task 021 as part of this task.
