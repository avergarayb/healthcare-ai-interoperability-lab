# Task 032 — Oracle Health Sandbox Connection Readiness

**Status:** Planned  
**Branch:** `feature/oracle-health-sandbox-readiness`  
**Baseline:** `main` @ latest merged Task 031  
**Phase:** Oracle Health Real Integration

---

## Objective

Prepare the Healthcare AI Interoperability Lab for a **real connection to an Oracle Health developer/sandbox environment** without yet implementing clinical workflows or claiming a successful production integration.

This task establishes a safe and explicit boundary between the existing local/synthetic laboratory environments, the Oracle Health vendor profile, external credentials/configuration, and future real authentication.

The outcome is **sandbox connection readiness**, not Oracle certification and not yet a complete live clinical integration.

---

# 1. Why this task exists

Tasks 028–031 prepared the architecture for real-world interoperability:

- Task 028: SMART on FHIR discovery and compatibility validation.
- Task 029: Epic vendor integration profile.
- Task 030: Oracle Health vendor integration profile.
- Task 031: runtime FHIR Capability Discovery through `GET /metadata`.

The next step is to prepare the application so that a real Oracle Health environment can be configured **without hardcoding vendor credentials, URLs, secrets, or tenant-specific assumptions into Java code**.

> **Oracle profile readiness is not the same as real Oracle connectivity.**

Task 032 closes the configuration and environment boundary required before attempting real authentication.

---

# 2. Scope

## Included

- Oracle Health sandbox environment configuration.
- Explicit separation between local, synthetic, sandbox, and production configuration.
- Environment-variable based configuration for external credentials.
- Secret hygiene and validation.
- Oracle endpoint configuration validation.
- Connectivity/readiness verification.
- Clear runtime readiness status.
- Documentation explaining Oracle environment configuration.
- Tests proving incomplete external configuration does not break local development.

## Not included

- Real OAuth authorization flow.
- Real Oracle user login.
- Patient reads.
- Clinical data access.
- Production credentials.
- Dynamic Client Registration.
- EHR Launch.
- AI Agent functionality.
- Epic live connectivity.

---

# 3. Target architecture

```text
Application Configuration
        |
        +----------------------+
        |                      |
        v                      v
Local / Lab Profiles      Oracle Health Profile
                               |
                               v
                       Environment Variables
                               |
                               v
                    OracleSandboxConfiguration
                               |
                               v
                     Readiness Validation
                               |
                               v
                    Connectivity Verification
```

No Oracle URL or credential belongs in `FhirService`.

---

# 4. Environment model

The platform should distinguish explicitly:

```text
LOCAL
SYNTHETIC
SANDBOX
PRODUCTION
```

The Oracle integration profile initially supports:

```text
SANDBOX
PRODUCTION
```

Only SANDBOX readiness is in runtime scope for this task.

## Concept

> **Environment identity is configuration, not application logic.**

Avoid vendor endpoint construction through Java conditionals.

---

# 5. Configuration model

Oracle external settings must come from environment variables or an external secret mechanism.

The repository may contain placeholders and documentation, but never real secrets.

Conceptually:

```yaml
fhir:
  servers:
    oracle-health-sandbox:
      enabled: ${ORACLE_HEALTH_SANDBOX_ENABLED:false}
      vendor: ORACLE_HEALTH
      environment: SANDBOX
      base-url: ${ORACLE_HEALTH_SANDBOX_BASE_URL:}
      authentication:
        client-id: ${ORACLE_HEALTH_SANDBOX_CLIENT_ID:}
        redirect-uri: ${ORACLE_HEALTH_SANDBOX_REDIRECT_URI:}
        scope: ${ORACLE_HEALTH_SANDBOX_SCOPE:}
        aud: ${ORACLE_HEALTH_SANDBOX_AUD:}
        smart-configuration-url: ${ORACLE_HEALTH_SANDBOX_SMART_CONFIGURATION_URL:}
```

Property names may be adapted to the existing configuration model from Tasks 028 and 030.

---

# 6. Disabled vs enabled external profile

## Disabled

When `enabled=false`:

- application starts normally;
- Oracle credentials are not required;
- no HTTP call to Oracle occurs;
- local HAPI and synthetic tests continue working.

## Enabled

When `enabled=true`, required configuration must be complete enough for the Oracle sandbox readiness contract.

Missing values must fail explicitly.

The application must not silently invent external defaults.

---

# 7. Configuration validation

Introduce or extend a validator responsible for answering:

> Is this Oracle sandbox profile sufficiently configured to attempt external connectivity?

Examples of invalid states:

- enabled Oracle profile with empty base URL;
- missing client identifier;
- malformed URI;
- missing audience when required;
- missing SMART discovery URL when required;
- unsupported runtime authentication mode.

Errors must be explicit and safe.

They must not expose secrets, tokens, authorization codes, PKCE verifiers, or environment dumps.

---

# 8. Readiness states

Suggested stable states:

```text
NOT_CONFIGURED
DISABLED
CONFIGURED
READY_FOR_CONNECTIVITY_CHECK
INVALID_CONFIGURATION
```

Do not introduce claims such as:

```text
ORACLE_CERTIFIED
PRODUCTION_READY
LIVE_INTEGRATED
```

unless later tasks actually prove them.

> **Configuration readiness is not successful interoperability.**

---

# 9. Connectivity verification

Introduce a small boundary capable of verifying whether a configured external endpoint is reachable.

It must not yet perform clinical workflows.

Responsibilities may include:

- validate the configured URI;
- contact the endpoint through an appropriate transport/protocol boundary;
- report status safely;
- classify failures through the existing error model.

A successful check means only:

> the configured endpoint responded at the expected integration boundary.

It does **not** mean Patient access works.

---

# 10. Existing error handling

Reuse Task 023 categories:

```text
timeout
    -> TIMEOUT

DNS / connection refused
    -> CONNECTION_ERROR

5xx
    -> SERVER_ERROR

invalid local configuration
    -> VALIDATION_ERROR
```

Local configuration errors must not be retried as Oracle outages.

---

# 11. Resilience boundaries

The existing pipeline remains:

```text
Routing
    ↓
Rate Limiter
    ↓
Bulkhead
    ↓
Circuit Breaker
    ↓
Retry
    ↓
FHIR / External Dependency
```

Configuration validation occurs before the remote operation.

Invalid configuration must not:

- consume retry attempts;
- open the circuit;
- be interpreted as dependency failure.

> **Local misconfiguration is not dependency failure.**

---

# 12. Security and secret hygiene

No real Oracle credentials may be committed.

Provide documented examples such as `.env.example` or equivalent configuration documentation.

Never commit:

- client secrets;
- private keys;
- access tokens;
- refresh tokens;
- authorization codes;
- PKCE verifiers.

---

# 13. Oracle vendor boundary

Oracle-specific knowledge remains inside the vendor/configuration boundary.

These layers must not gain Oracle-specific conditional logic:

- `FhirService`
- routing core
- resilience core
- generic capability model
- generic SMART model

Avoid:

```java
if (vendor == ORACLE_HEALTH) {
    ...
}
```

inside generic FHIR operations.

> **Vendor metadata configures the platform; it does not contaminate generic operations.**

---

# 14. Suggested implementation components

Names may be adapted to the existing codebase:

```text
vendor.oracle
    OracleSandboxConfiguration
    OracleSandboxProfileValidator
    OracleSandboxReadiness

connectivity
    FhirEndpointConnectivityVerifier
    FhirConnectivityStatus
```

Reuse existing abstractions instead of duplicating server profiles, SMART settings, vendor configuration, or error classification.

---

# 15. Important learning explanations

Cursor should explain important portions using:

## WHAT

What does the component do?

## WHY

Why is this responsibility located here?

## HOW

How does it work technically?

## CONCEPT

What architecture, interoperability, security, or distributed-systems concept does it demonstrate?

At minimum explain:

1. externalized configuration;
2. environment variables vs source-controlled configuration;
3. disabled vs enabled integration profiles;
4. fail-fast configuration validation;
5. configuration failure vs dependency failure;
6. secret hygiene;
7. environment isolation;
8. why Oracle logic does not belong in `FhirService`;
9. readiness vs successful integration.

---

# 16. Architecture boundaries

## `FhirService`

Must remain unaware of:

- Oracle environment variable names;
- Oracle sandbox URLs;
- readiness states;
- secret configuration.

## Resilience

Must remain unaware of:

- Oracle credential fields;
- vendor-specific authentication implementation details.

## Oracle vendor package

May understand:

- Oracle environment;
- Oracle integration profile;
- Oracle-specific configuration requirements.

## Configuration layer

May bind environment variables but must not contain clinical FHIR operations.

---

# 17. Testing strategy

## Unit tests

### Disabled profile

```text
enabled=false
→ application remains valid
→ no Oracle configuration required
```

### Valid sandbox configuration

```text
enabled=true
+ required configuration present
→ READY_FOR_CONNECTIVITY_CHECK
```

### Missing configuration

Examples:

```text
missing base URL
missing client ID
invalid URI
```

Expected:

```text
INVALID_CONFIGURATION
or explicit validation exception
```

according to existing project conventions.

### Secret safety

Verify exception messages and `toString()` do not expose secret values.

---

## Integration tests

Normal repository tests must remain independent from real Oracle accounts, internet access, and Oracle credentials.

Suggested separation:

```text
default tests
    → local / synthetic

oracle-live profile
    → optional
    → requires explicit environment configuration
```

A live Oracle test must never run accidentally in normal CI.

---

# 18. Acceptance criteria

Task 032 is complete when:

- [ ] Oracle sandbox can be represented through external configuration.
- [ ] Oracle profile is disabled by default.
- [ ] Local development does not require Oracle credentials.
- [ ] Enabling the profile validates required configuration explicitly.
- [ ] Missing or invalid configuration fails safely.
- [ ] No credentials are committed.
- [ ] Readiness can be inspected through a stable internal model.
- [ ] Connectivity verification has a clear boundary.
- [ ] Generic FHIR services remain vendor-agnostic.
- [ ] Existing resilience architecture remains intact.
- [ ] Normal tests remain offline and deterministic.
- [ ] Oracle live tests are explicitly opt-in.
- [ ] Tasks 001–031 remain green.

---

# 19. Out of scope reminder

Task 032 does not prove:

- real Oracle OAuth authentication;
- real SMART authorization;
- Patient access;
- clinical data access;
- production compatibility;
- Oracle certification.

Next planned tasks:

```text
Task 033
    Oracle Health Real Authentication

Task 034
    Oracle Health Live Capability Discovery

Task 035
    Oracle Health Patient Integration
```

---

# 20. Expected outcome

After this task, the platform should be able to state honestly:

> **Oracle Health sandbox integration is configured and validated for external connectivity, while local development remains independent from Oracle credentials.**

It must **not** yet claim that Oracle Health clinical integration is complete.

---

# Git

Suggested branch:

```text
feature/oracle-health-sandbox-readiness
```

Baseline:

```text
main @ latest Task 031 merge
```

Suggested commit message:

```text
feat: add Oracle Health sandbox connection readiness
```
