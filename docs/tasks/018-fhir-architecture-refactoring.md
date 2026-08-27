# Task 018 — FHIR Architecture Refactoring

## Objective

Refactor the Java architecture of `fhir-integration-service` after Tasks 001–017.

The current implementation works, but too many classes have accumulated under the same `client` package. This task reorganizes the code by responsibility so the project can evolve from a learning laboratory into a reusable **FHIR Integration Service** suitable for consulting projects and, potentially, a SaaS integration component.

The main rule is:

> Refactor the architecture without changing the functional behavior already implemented.

The task does not introduce a new FHIR capability. It establishes cleaner boundaries for future work.

---

# Baseline

Task 018 starts from the current `main`:

```text
197f3c5 Merge pull request #16 from avergarayb/feature/fhir-smart-on-fhir
1776841 feat: add synthetic SMART on FHIR authorization code flow
```

Tasks 001–017 are considered the functional baseline.

---

# Current architectural problem

The project currently has too many responsibilities concentrated in a single package.

Conceptually:

```text
lab.healthcare.fhir.client
├── FhirService
├── FhirClientFactory
├── FhirClientConfiguration
├── FhirServerProfile
├── FhirServerProfileRegistry
├── FhirServersProperties
├── OAuth2TokenClient
├── AuthorizationCodeClient
├── SmartTokenProvider
├── SmartConfiguration
├── SmartConfigurationClient
├── Pkce
├── ...
```

This makes the package represent several different concepts:

```text
FHIR client
server configuration
authentication
OAuth 2.0
SMART on FHIR
exceptions
```

That structure should not continue growing.

---

# Architectural goal

Move toward responsibility-based packages.

Target structure:

```text
lab.healthcare.fhir
│
├── auth
│   ├── AccessToken.java
│   ├── AccessTokenProvider.java
│   ├── BearerAccessTokenInterceptor.java
│   ├── CachingAccessTokenProvider.java
│   │
│   └── oauth2
│       ├── OAuth2TokenClient.java
│       └── OAuth2TokenException.java
│
├── smart
│   ├── SmartConfiguration.java
│   ├── SmartConfigurationClient.java
│   ├── AuthorizationCodeClient.java
│   ├── AuthorizationSession.java
│   ├── SmartTokenProvider.java
│   └── Pkce.java
│
├── client
│   ├── FhirClientConfiguration.java
│   ├── FhirClientFactory.java
│   └── FhirService.java
│
├── server
│   ├── FhirServerProfile.java
│   ├── FhirServersProperties.java
│   └── FhirServerProfileRegistry.java
│
└── exception
    └── FhirClientException.java
```

The exact final names may differ if the responsibilities remain equivalent.

---

# Architectural principles

## 1. FhirService is the FHIR application service

`FhirService` should contain FHIR operations such as:

```text
readPatient
searchPatients
searchObservationsByPatient
createPatient
updatePatient
deletePatient
getPatientHistory
readPatientVersion
getPatientEverything
nextPage
...
```

It should not contain:

```text
OAuth URLs
client secrets
PKCE
authorization codes
SMART discovery
token parsing
server profile selection
```

---

## 2. Authentication is infrastructure

Authentication should be behind abstractions such as:

```text
AccessTokenProvider
```

The FHIR client should only need an access token when authentication is configured.

Conceptually:

```text
FhirService
    ↓
IGenericClient
    ↓
BearerAccessTokenInterceptor
    ↓
AccessTokenProvider
```

The interceptor should not know whether the token came from:

```text
Client Credentials
Authorization Code
Refresh Token
```

---

## 3. OAuth 2.0 and SMART are different responsibilities

OAuth 2.0 infrastructure belongs under:

```text
auth.oauth2
```

SMART-specific behavior belongs under:

```text
smart
```

For example:

```text
OAuth2TokenClient
```

should not become a SMART class.

Likewise:

```text
SmartConfigurationClient
AuthorizationCodeClient
Pkce
```

should not be placed under generic FHIR client classes.

---

## 4. Server configuration is separate from authentication

FHIR server configuration belongs under:

```text
server
```

Example:

```text
FhirServerProfile
FhirServersProperties
FhirServerProfileRegistry
```

The server profile answers:

> Which FHIR server are we connecting to?

Authentication answers:

> How do we obtain authorization to call it?

These are separate concerns.

---

# Step 1 — Create branch

Create:

```text
feature/fhir-architecture-refactoring
```

from `main`.

Do not work directly on `main`.

---

# Step 2 — Inventory existing classes

Before moving anything, inspect the current source tree.

Identify:

- Java production classes.
- Unit tests.
- Integration tests.
- configuration classes.
- authentication classes.
- SMART classes.
- exception classes.

Do not move classes blindly.

For every class, identify its primary responsibility.

---

# Step 3 — Define package boundaries

Use these conceptual boundaries:

```text
client
    FHIR client construction and FHIR business operations

server
    FHIR server profiles and server selection

auth
    authentication/token infrastructure

auth.oauth2
    generic OAuth 2.0 implementation

smart
    SMART on FHIR-specific behavior

exception
    application exceptions
```

The goal is cohesion, not simply creating more folders.

---

# Step 4 — Move server configuration

Move:

```text
FhirServerProfile
FhirServersProperties
FhirServerProfileRegistry
```

to:

```text
lab.healthcare.fhir.server
```

Update imports and Spring configuration.

Verify that:

```text
fhir.active-server
fhir.servers
```

continue working.

---

# Step 5 — Move authentication infrastructure

Move generic authentication classes to:

```text
lab.healthcare.fhir.auth
```

Examples:

```text
AccessToken
AccessTokenProvider
BearerAccessTokenInterceptor
CachingAccessTokenProvider
```

The authentication package should not depend on `FhirService`.

---

# Step 6 — Separate OAuth 2.0

Move generic OAuth 2.0 classes to:

```text
lab.healthcare.fhir.auth.oauth2
```

Examples:

```text
OAuth2TokenClient
OAuth2TokenException
```

Keep the generic token acquisition logic independent of SMART.

Client Credentials from Task 016 must continue working.

---

# Step 7 — Move SMART

Move SMART-specific classes to:

```text
lab.healthcare.fhir.smart
```

Examples:

```text
SmartConfiguration
SmartConfigurationClient
AuthorizationCodeClient
AuthorizationSession
SmartTokenProvider
Pkce
```

SMART classes may use OAuth abstractions, but generic OAuth classes should not depend on SMART.

Conceptually:

```text
smart
   ↓
auth
   ↓
oauth2
```

Avoid circular dependencies.

---

# Step 8 — Keep FHIR client classes together

Keep:

```text
FhirClientConfiguration
FhirClientFactory
FhirService
```

under:

```text
lab.healthcare.fhir.client
```

These classes represent the FHIR client layer.

`FhirService` remains the main application-facing FHIR service.

---

# Step 9 — Exceptions

Move FHIR-specific application exceptions to:

```text
lab.healthcare.fhir.exception
```

For example:

```text
FhirClientException
```

OAuth-specific exceptions should remain associated with OAuth:

```text
auth.oauth2.OAuth2TokenException
```

Do not create a giant generic exception hierarchy without a real need.

---

# Step 10 — Review dependency direction

The intended dependency direction is approximately:

```text
                    FhirService
                         │
                         ▼
                     client
                         │
                         ▼
                  authentication
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
           OAuth 2.0             SMART
```

More precisely, SMART may depend on generic authentication/OAuth abstractions, while the generic authentication layer must not depend on SMART-specific implementation details.

Server configuration should remain independently usable:

```text
server
   ↓
client configuration/factory
```

Avoid:

```text
FhirService → SmartTokenProvider
FhirService → OAuth2TokenClient
FhirService → Pkce
```

---

# Step 11 — Configuration review

Review:

```text
application.yml
application-local.yml
```

and ensure configuration classes still bind correctly.

Do not change the external configuration contract unless necessary.

The following concepts must continue working:

```text
fhir.active-server
fhir.servers
authentication
OAuth configuration
SMART configuration
```

---

# Step 12 — Test package organization

Tests should follow the production package structure where practical.

For example:

```text
src/test/java/lab/healthcare/fhir
│
├── auth
│   ├── ...
│   └── oauth2
│
├── smart
│
├── client
│
├── server
│
└── ...
```

Integration tests can remain grouped according to their feature.

Do not perform a large test rewrite merely to move files.

---

# Step 13 — Preserve behavior

The following capabilities must remain unchanged:

```text
Patient read/search
Observation/Condition search
_include
_revinclude
CRUD
advanced search
search chaining
terminology validation
resource validation
Bundles
transactions
batch
pagination
history/versioning
$everything
server profiles
OAuth Client Credentials
SMART Authorization Code
PKCE
SMART discovery
SMART scopes
patient context
refresh token
```

This task is a structural refactoring.

It is not a functional rewrite.

---

# Step 14 — Unit tests

Run:

```bash
cd services/fhir-integration-service
mvn clean test
```

Expected:

```text
BUILD SUCCESS
```

All existing unit tests must pass.

If package changes require import changes, update tests accordingly.

Do not weaken assertions simply to make tests pass.

---

# Step 15 — Integration tests

Start infrastructure:

```bash
docker compose -f ../../infra/docker/docker-compose.yml up -d
```

Verify:

```bash
docker compose -f ../../infra/docker/docker-compose.yml ps
```

Expected:

```text
hapi-fhir       Up
postgres        healthy
lab-oauth       Up
fhir-gateway    Up
```

Then:

```bash
mvn clean verify -Pintegration
```

Expected:

```text
BUILD SUCCESS
```

All Tasks 001–017 integration tests must continue passing.

---

# Step 16 — Architecture verification

After refactoring, verify that the source tree reflects the intended boundaries.

Check that:

```text
client/
server/
auth/
auth/oauth2/
smart/
exception/
```

are clearly separated.

Check especially that:

```text
FhirService
```

does not import:

```text
Pkce
AuthorizationCodeClient
SmartConfigurationClient
OAuth2TokenClient
```

unless there is a documented architectural reason.

The preferred result is zero direct SMART/OAuth implementation dependencies from `FhirService`.

---

# Step 17 — Dependency-cycle review

Search imports to detect cycles.

The following should not occur:

```text
auth → smart → auth → smart
```

or:

```text
smart → client → smart
```

or:

```text
server → smart → server
```

If necessary, introduce an interface at the correct boundary instead of forcing a circular dependency.

---

# Step 18 — Documentation

Create:

```text
docs/fhir/fhir-architecture.md
```

Document:

- previous architecture;
- problems with the previous package structure;
- new package structure;
- responsibility of each package;
- dependency direction;
- why `FhirService` is independent of OAuth/SMART;
- relationship between `client`, `server`, `auth`, `oauth2`, and `smart`;
- how the architecture supports future EHR integrations;
- why this is useful for a reusable integration component.

Update:

```text
docs/fhir/README.md
docs/roadmap.md
README.md
```

---

# Architecture model

The final conceptual architecture should resemble:

```text
                         ┌─────────────────────┐
                         │     FhirService     │
                         │   FHIR operations   │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   FHIR Client       │
                         │ Factory/Config      │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │ Authentication      │
                         │ abstraction         │
                         └───────┬───────┬──────┘
                                 │       │
                         ┌───────▼───┐ ┌─▼──────────┐
                         │ OAuth 2.0 │ │   SMART    │
                         └───────────┘ └────────────┘
                                 │       │
                                 └───┬───┘
                                     ▼
                              Bearer Token
                                     │
                                     ▼
                               FHIR Gateway
                                     │
                                     ▼
                                  HAPI FHIR
```

Server selection remains independent:

```text
FhirServerProfile
       │
       ▼
FhirClientFactory
       │
       ▼
IGenericClient
```

---

# Future provider model

The refactoring should make this future architecture possible:

```text
FHIR Integration Service
│
├── FHIR Client
│
├── Server Profiles
│   ├── HAPI
│   ├── Epic
│   ├── Oracle Health
│   └── Other EHR
│
├── Authentication
│   ├── Client Credentials
│   ├── SMART Authorization Code
│   └── Future mechanisms
│
└── FHIR Operations
    ├── Patient
    ├── Observation
    ├── Condition
    ├── Encounter
    └── ...
```

Do not implement those future providers in Task 018.

Only prepare clean boundaries for them.

---

# Important architectural rule

Do not create abstractions merely because they look architecturally sophisticated.

For every new interface, ask:

1. Is there more than one implementation?
2. Is a future implementation reasonably expected?
3. Does the abstraction isolate a volatile dependency?
4. Does it make testing or substitution materially easier?

If the answer is no, prefer the simpler design.

---

# Acceptance criteria

- [ ] Branch `feature/fhir-architecture-refactoring`.
- [ ] Baseline is Task 017.
- [ ] `client` contains only FHIR client responsibilities.
- [ ] `server` contains FHIR server configuration.
- [ ] `auth` contains authentication infrastructure.
- [ ] `auth.oauth2` contains generic OAuth 2.0 implementation.
- [ ] `smart` contains SMART-specific implementation.
- [ ] FHIR exceptions are separated appropriately.
- [ ] No circular package dependencies.
- [ ] `FhirService` remains independent of SMART implementation.
- [ ] `FhirService` remains independent of OAuth token acquisition.
- [ ] Existing configuration continues to work.
- [ ] Task 016 Client Credentials continues working.
- [ ] Task 017 SMART continues working.
- [ ] `mvn clean test` → BUILD SUCCESS.
- [ ] `mvn clean verify -Pintegration` → BUILD SUCCESS.
- [ ] Documentation created.
- [ ] No functional regression introduced.

---

# Files expected

Potentially modified:

```text
FhirService.java
FhirClientConfiguration.java
FhirClientFactory.java
```

and classes whose packages are changed.

Potentially created:

```text
docs/fhir/fhir-architecture.md
docs/tasks/018-fhir-architecture-refactoring.md
```

The exact list depends on the current source tree.

---

# Git

Do not commit automatically.

At the end run:

```bash
git status
git diff --stat
git diff
```

Also verify:

```bash
git status --short
```

Report:

- classes moved;
- packages created;
- files modified;
- files deleted;
- interfaces introduced;
- dependency direction;
- tests executed;
- test counts;
- problems encountered;
- architectural decisions.

The commit will be performed separately.

---

# Definition of Done

Task 018 is complete when the project has the same functional capabilities as before the refactoring, but the codebase clearly separates:

```text
FHIR
Server Configuration
Authentication
OAuth 2.0
SMART on FHIR
Exceptions
```

The result should be easier to understand, test, maintain, and extend.

The task is successful if a future developer can add a new authentication mechanism or FHIR server without modifying `FhirService`.

---

# Next step

After Task 018, the next task should build a new interoperability capability on top of these boundaries rather than continuing to accumulate unrelated classes in `client`.

Do not implement Task 019 as part of this task.
