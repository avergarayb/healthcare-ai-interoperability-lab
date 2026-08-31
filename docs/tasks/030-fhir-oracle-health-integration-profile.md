# Task 030 — Oracle Health Integration Profile

**Branch:** `feature/fhir-oracle-health-integration-profile`  
**Baseline:** `main` after Task 029  
**Status:** Planned — no commit

---

## Objective

Task 030 adds an **Oracle Health vendor integration profile** without changing generic FHIR operations, routing, SMART foundations, or resilience.

The goal is to model what the platform needs to know about an Oracle Health/Cerner-style integration while remaining honest about runtime support.

This task does **not** connect to a real Oracle Health sandbox.

It prepares the architecture so that a later live integration can use:

- vendor-specific configuration,
- SMART on FHIR discovery,
- registered application credentials,
- runtime capability discovery,
- and the existing routing/resilience pipeline.

---

# 1. Why Oracle Health needs its own vendor profile

FHIR provides the common interoperability contract:

```text
Patient
Observation
Encounter
MedicationRequest
...
```

SMART on FHIR provides the authorization model.

But a vendor ecosystem can additionally define or document:

- developer registration workflows,
- application onboarding,
- sandbox environments,
- supported launch patterns,
- authentication expectations,
- API availability,
- organization-specific endpoints.

Therefore Oracle Health knowledge must not be scattered through:

```text
FhirService
RoutingService
FhirRetryExecutor
FhirCircuitBreaker
```

Instead:

```text
Generic FHIR Layer
        │
        ▼
Vendor Integration Layer
        │
   ┌────┴─────┐
   │          │
 Epic       Oracle Health
```

**Concept:** Vendor profile ≠ generic FHIR operation.

---

# 2. Package

Create:

```text
lab.healthcare.fhir.vendor.oracle
```

Suggested model:

| Type | Role |
|---|---|
| `OracleHealthIntegrationProfile` | Aggregates Oracle Health vendor metadata |
| `OracleHealthEnvironment` | SANDBOX / PRODUCTION |
| `OracleHealthLaunchMode` | Models supported launch readiness |
| `OracleHealthClientAuthentication` | Models authentication modes |
| `OracleHealthCapabilities` | Vendor-known capabilities |
| `OracleHealthKnownApiSurface` | Explicitly avoids assuming all R4 resources |
| `OracleHealthProfileValidator` | Validates configuration and runtime readiness |
| `OracleHealthProfileException` | Vendor-profile failure |
| `OracleHealthVendorConfiguration` | Spring configuration |

The exact class names may be adjusted only if the resulting responsibilities remain equivalent.

---

# 3. FHIR generic vs Oracle Health vendor knowledge

## WHAT

`FhirService` continues to execute generic HAPI FHIR R4 operations.

The server profile gains:

```text
vendor: ORACLE_HEALTH
```

Oracle-specific metadata lives only in:

```text
lab.healthcare.fhir.vendor.oracle
```

## WHY

Reading:

```text
GET /Patient/{id}
```

is a generic FHIR interaction.

It should not know:

- Oracle Health developer portals,
- Oracle-specific onboarding,
- sandbox registration details,
- launch modes,
- confidential-client configuration.

## HOW

The vendor profile is composed around the existing server profile.

The existing architecture remains:

```text
Routing
   ↓
Client Factory
   ↓
Authentication
   ↓
FHIR Client
   ↓
FhirService
```

No Oracle conditional belongs inside `FhirService`.

## CONCEPT

**Vendor knowledge is configuration/domain metadata; FHIR operations remain generic.**

---

# 4. Environment: SANDBOX vs PRODUCTION

## WHAT

Model at least:

```java
SANDBOX
PRODUCTION
```

## WHY

A public developer/test environment is not equivalent to an Oracle Health deployment used by a real healthcare organization.

Production endpoints must remain configuration supplied by the organization or deployment context.

## HOW

`OracleHealthEnvironment` represents the environment.

A future production profile provides its own:

- FHIR base URL,
- audience,
- discovery URL,
- application registration information.

Java must not manufacture production endpoints by concatenating vendor hostnames.

## CONCEPT

```text
Vendor sandbox
      ≠
Customer production deployment
```

---

# 5. Standalone SMART vs EHR launch readiness

## WHAT

Model the distinction between:

```text
STANDALONE
EHR_LAUNCH
```

without implementing a complete EHR launch flow.

## WHY

A standalone application initiates authorization itself.

An EHR launch involves context supplied by the EHR, commonly including values such as:

```text
iss
launch
```

These are different SMART contracts.

## HOW

`OracleHealthLaunchMode` represents the modes.

`OracleHealthCapabilities` reports what the platform/profile is prepared to model.

The current runtime remains based on the standalone SMART foundations already implemented in Task 028 unless a later task explicitly implements EHR launch.

## CONCEPT

**Launch readiness ≠ completed EHR launch implementation.**

---

# 6. Authentication modes

## WHAT

Represent authentication modes without pretending unsupported mechanisms work.

At minimum distinguish conceptually:

```text
PUBLIC_PKCE
CLIENT_SECRET
PRIVATE_KEY_JWT
```

## WHY

Different registered applications can have different security requirements.

Representing a mode in configuration is not the same as implementing token acquisition for that mode.

## HOW

The profile reports runtime support explicitly.

For this laboratory foundation:

```text
PUBLIC_PKCE
```

may reuse the existing SMART PKCE implementation.

Modes not implemented must fail explicitly when selected for runtime use.

Example concept:

```text
runtimeSupported() == false
```

→ deterministic `OracleHealthProfileException`

No fake JWT assertions.

No private keys committed to Git.

No secrets embedded in Java.

## CONCEPT

**Declared capability ≠ implemented runtime capability.**

---

# 7. Vendor-known capabilities vs server discovery

## WHAT

`OracleHealthCapabilities` represents what this platform knows about the vendor profile.

It does not claim that every Oracle Health server supports every FHIR R4 resource.

## WHY

Vendor documentation and actual server capability are different layers.

A server may expose a subset depending on:

- environment,
- API catalog,
- application registration,
- tenant,
- authorization scopes,
- implementation/version.

## HOW

`OracleHealthKnownApiSurface.assumesEveryR4Resource()` returns:

```text
false
```

Do not hardcode a giant resource catalog as universal truth.

Task 031 will inspect the actual server through:

```text
GET /metadata
```

and interpret the returned:

```text
CapabilityStatement
```

## CONCEPT

```text
Vendor metadata
       ≠
Runtime CapabilityStatement
```

They complement each other.

---

# 8. Configuration and secrets

The profile should be disabled by default.

Example conceptual YAML:

```yaml
fhir:
  servers:
    - name: oracle-health-sandbox
      vendor: ORACLE_HEALTH
      enabled: false
      base-url: ${ORACLE_HEALTH_SANDBOX_BASE_URL:}
      authentication:
        type: SMART
        client-id: ${ORACLE_HEALTH_SANDBOX_CLIENT_ID:}
        redirect-uri: ${ORACLE_HEALTH_SANDBOX_REDIRECT_URI:}
        scope: ${ORACLE_HEALTH_SANDBOX_SCOPE:}
        aud: ${ORACLE_HEALTH_SANDBOX_AUD:}
        smart-configuration-url: ${ORACLE_HEALTH_SANDBOX_SMART_CONFIGURATION_URL:}
```

The exact property names can follow the existing project conventions.

## Rules

- No client secret in Git.
- No private key in Git.
- No access token in Git.
- No authorization code in Git.
- Empty environment defaults are acceptable while the profile is disabled.

When enabled, runtime validation must require the information necessary for the selected authentication mode.

## CONCEPT

**Configuration placeholders are safe; credentials are registration material.**

---

# 9. Oracle Health readiness states

Use explicit readiness reporting.

Suggested states:

```text
NOT_CONFIGURED
CONFIGURED
SMART_COMPATIBLE
READY_FOR_SANDBOX
```

Do not introduce:

```text
CERTIFIED
PRODUCTION_READY
ORACLE_APPROVED
```

unless an external certification process actually supports those claims.

## Meaning

### NOT_CONFIGURED

Profile disabled and required registration values absent.

### CONFIGURED

Required profile values exist.

### SMART_COMPATIBLE

The configured/discovered SMART metadata is compatible with the supported flow.

### READY_FOR_SANDBOX

The profile contains the configuration required to attempt a sandbox integration.

This does **not** mean:

- a real OAuth flow succeeded,
- a token was issued,
- a real Patient was read,
- Oracle approved the application.

## CONCEPT

**Configuration readiness ≠ live interoperability proof.**

---

# 10. Reuse Task 028 SMART foundations

Oracle Health must reuse the existing generic SMART components:

```text
SmartConfigurationClient
SmartConfiguration
SmartCapabilities
SmartConfigurationValidator
SmartFlowRequirements
AuthorizationCodeClient
SmartTokenProvider
PKCE S256
```

Do not create:

```text
OracleSmartConfigurationClient
OraclePkce
OracleTokenProvider
```

unless Oracle genuinely requires behavior that cannot be represented by the generic SMART abstraction.

## WHY

Task 028 exists specifically to prevent vendor-specific OAuth duplication.

## CONCEPT

**Generic SMART core + vendor profile metadata.**

---

# 11. Routing and resilience remain unchanged

The request still enters through:

```text
RoutingService
```

The destination remains a named profile:

```text
oracle-health-sandbox
```

The pipeline remains:

```text
RoutingService
        ↓
Rate Limiter
        ↓
Bulkhead
        ↓
Circuit Breaker
        ↓
Retry
        ↓
FhirService.readPatient
```

Oracle vendor metadata must not change the pipeline.

## WHY

A vendor identity does not alter the responsibilities of:

- admission control,
- concurrency isolation,
- dependency health,
- transient retry,
- generic FHIR operations.

## CONCEPT

**Vendor integration ≠ a second execution pipeline.**

---

# 12. What is explicitly out of scope

Task 030 does NOT:

- connect to Oracle Health over the internet,
- register an application,
- obtain a real client ID,
- obtain a real OAuth token,
- read real sandbox data,
- implement DCR,
- implement private-key JWT assertions,
- implement a new OAuth grant,
- implement complete EHR launch,
- claim Oracle certification,
- hardcode production customer endpoints.

Those activities belong to the later live integration stage.

---

# 13. Tests

The task must test the architecture without contacting Oracle Health.

Suggested tests:

## Unit tests

### Vendor identity

- `ORACLE_HEALTH` is represented correctly.
- Generic profiles continue working.

### Profile validation

- disabled + empty registration values → valid configuration / `NOT_CONFIGURED`
- enabled + missing required values → explicit validation failure
- configured standalone PKCE profile → valid
- unsupported runtime authentication mode → `OracleHealthProfileException`

### Environment

- SANDBOX represented correctly
- PRODUCTION represented correctly
- no production URL is manufactured by Java

### Capabilities

- standalone readiness is explicit
- EHR launch readiness is represented but not implemented
- `assumesEveryR4Resource()` is false

### Architecture boundaries

- `FhirService` does not import Oracle vendor package
- Oracle package does not contain HAPI operation logic
- routing/resilience do not contain `if (vendor == ORACLE_HEALTH)`

## Integration test

Create a synthetic/local profile using:

```text
127.0.0.1
```

and existing SMART test infrastructure.

The test may demonstrate:

```text
NOT_CONFIGURED
    ↓
CONFIGURED
    ↓
SMART_COMPATIBLE
    ↓
READY_FOR_SANDBOX
```

without making HTTP calls to Oracle Health.

---

# 14. Documentation

Create:

```text
docs/fhir/vendors/oracle-health.md
```

Document:

- generic FHIR vs vendor profile,
- sandbox vs production,
- standalone vs EHR launch readiness,
- authentication modes,
- capability discovery boundary,
- secret hygiene,
- readiness states,
- explicit limitations.

Update relevant:

```text
docs/fhir/README.md
docs/fhir/fhir-architecture.md
docs/fhir/fhir-client.md
docs/fhir/fhir-smart-on-fhir.md
docs/fhir/vendors/epic.md
docs/roadmap.md
README.md
```

Also create:

```text
docs/tasks/030-oracle-health-integration-profile.md
```

---

# 15. Cursor implementation instructions

While implementing this task, explain important code portions using:

## WHAT

What does this class or block do?

## WHY

Why does this responsibility exist here?

## HOW

How does the implementation work?

## CONCEPT

What software/interoperability concept should be learned?

Important concepts to explain:

1. Vendor profile pattern
2. Generic abstraction vs vendor-specific metadata
3. Configuration-driven integration
4. Sandbox vs production environment separation
5. SMART standalone vs EHR launch
6. Public PKCE vs confidential client authentication
7. Declared capability vs implemented capability
8. Vendor-known metadata vs runtime capability discovery
9. Secret hygiene
10. Readiness state modeling
11. Architecture boundaries
12. Why routing/resilience remain vendor-neutral

Do not merely produce code. Explain the important implementation decisions so the project also serves as a learning laboratory.

---

# 16. Acceptance criteria

Task 030 is complete when:

1. Oracle Health is represented as a vendor profile.
2. `FhirService` remains vendor-neutral.
3. Existing Epic behavior remains unaffected.
4. Oracle profile is disabled by default.
5. No real Oracle credential exists in Git.
6. SANDBOX and PRODUCTION are modeled.
7. Standalone and EHR launch are distinguished.
8. Unsupported authentication modes fail explicitly at runtime.
9. Generic SMART components from Task 028 are reused.
10. Oracle does not get its own routing/resilience pipeline.
11. Vendor metadata does not claim every FHIR R4 resource is supported.
12. Readiness states are explicit and honest.
13. Tests do not contact Oracle Health.
14. All previous tasks remain green.
15. Documentation is updated.
16. Important code portions include WHAT / WHY / HOW / CONCEPT explanations.

---

# Expected result

After Task 030:

```text
                 Healthcare Interoperability Lab
                              │
                    Generic FHIR Platform
                              │
              ┌───────────────┴───────────────┐
              │                               │
          Epic Profile                 Oracle Health Profile
              │                               │
        Vendor Metadata                 Vendor Metadata
              │                               │
        SMART Readiness                 SMART Readiness
              │                               │
              └───────────────┬───────────────┘
                              │
                    Task 031 next
                              │
                  Capability Discovery
                    GET /metadata
                              │
                       Live Sandbox Stage
```

The next planned task after Task 030 is:

## Task 031 — FHIR Capability Discovery

That task will move the platform from **what we know about a vendor profile** toward **what a specific FHIR server actually declares at runtime**.
