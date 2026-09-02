# Task 033 — Oracle Health Secure Sandbox SMART Authentication

**Branch:** `feature/oracle-health-secure-sandbox-auth`
**Baseline:** `main` @ `b544e26`

## Objective

Move from Oracle Health sandbox readiness to a real SMART on FHIR authentication flow against an Oracle Health Secure Sandbox.

This task must prove the authentication boundary with a real Oracle-issued access token when valid Oracle developer credentials and sandbox access are provided.

**It does not yet perform the first real Patient read.** That remains Task 035.

---

## Architecture

```text
Developer / User
        ↓
Oracle Health application registration
        ↓
client_id + redirect URI + scopes
        ↓
Healthcare AI Interoperability Lab
        ↓
Oracle Health profile
        ↓
SMART discovery
/.well-known/smart-configuration
        ↓
Authorization Code + PKCE S256
        ↓
Oracle authorization / login / consent
        ↓
Authorization code
        ↓
Token exchange
        ↓
Oracle-issued access token
        ↓
AccessTokenProvider
```

The boundaries remain:

```text
SMART/OAuth authentication ≠ FHIR operations
Vendor configuration ≠ generic FHIR client
Authentication ≠ resilience
```

`FhirService` must not import Oracle-specific authentication classes.

---

# Part A — Manual Oracle Health onboarding

This part is intentionally outside Cursor and outside Git.

The developer must complete the Oracle Health developer onboarding required for the Secure Sandbox and register an application using the currently available Oracle Health developer tooling.

Expected outcomes:

- developer access available;
- application registered;
- Oracle-issued `client_id` obtained;
- redirect URI registered;
- required SMART scopes configured;
- Secure Sandbox environment identified;
- FHIR base URL identified;
- SMART configuration URL identified or discoverable;
- authentication mode confirmed.

## Never commit

- access tokens;
- refresh tokens;
- authorization codes;
- client secrets;
- private keys;
- PKCE verifiers;
- browser session cookies.

Only placeholders belong in `.env.example`.

---

# Part B — Runtime configuration

Extend the Oracle sandbox profile with the minimum information required for real SMART authentication.

```yaml
oracle-health-sandbox:
  enabled: ${ORACLE_HEALTH_SANDBOX_ENABLED:false}
  vendor: ORACLE_HEALTH
  base-url: ${ORACLE_HEALTH_SANDBOX_BASE_URL:}

  authentication:
    client-id: ${ORACLE_HEALTH_SANDBOX_CLIENT_ID:}
    redirect-uri: ${ORACLE_HEALTH_SANDBOX_REDIRECT_URI:}
    scope: ${ORACLE_HEALTH_SANDBOX_SCOPE:}
    aud: ${ORACLE_HEALTH_SANDBOX_AUD:}
    smart-configuration-url: ${ORACLE_HEALTH_SANDBOX_SMART_CONFIGURATION_URL:}
```

Actual authorization/token endpoints must come from configuration or SMART discovery.

Java must not hardcode Oracle hosts.

---

# 1. Reuse SMART infrastructure from Task 028

### WHAT

Reuse the generic SMART infrastructure:

- `SmartConfigurationClient`
- `SmartConfiguration`
- `SmartCapabilities`
- `SmartConfigurationValidator`
- `SmartAuthorizationRequest`
- PKCE S256
- `AuthorizationSession`
- `AccessTokenProvider`

### WHY

Oracle is a vendor profile using SMART. Creating a second OAuth implementation under `vendor.oracle` would duplicate protocol logic.

### HOW

Oracle-specific code configures and validates the profile. Generic SMART classes perform discovery and protocol operations.

### CONCEPT

**Vendor adapter ≠ OAuth protocol implementation.**

---

# 2. Real Authorization Code + PKCE flow

### WHAT

The runtime flow is Authorization Code with PKCE S256.

### HOW

1. Discover SMART metadata.
2. Validate compatibility.
3. Generate `state`.
4. Generate PKCE verifier/challenge.
5. Build authorization URL.
6. User authenticates in Oracle.
7. Redirect returns authorization code.
8. Validate `state`.
9. Exchange code for token.
10. Expose token through `AccessTokenProvider`.

### CONCEPT

**Authorization is interactive; token exchange is HTTP.**

---

# 3. Browser interaction is explicit

The laboratory must not pretend OAuth login can be completed invisibly.

Provide an explicit integration boundary that can:

- create an authorization URL;
- expose it safely for manual browser navigation;
- accept/process the redirect callback;
- exchange the authorization code after callback validation.

Authorization codes must not persist in logs after processing.

---

# 4. State validation

Each authorization request generates a strong `state` value associated with one authorization session.

Reject:

- missing state;
- mismatched state;
- expired/unknown session.

No token exchange occurs after failed state validation.

### CONCEPT

**State protects the authorization transaction.**

---

# 5. PKCE verifier lifecycle

The `code_verifier` belongs to one authorization session.

Lifecycle:

```text
generate
   ↓
store for pending session
   ↓
send only to token endpoint
   ↓
invalidate after terminal completion
```

It must never appear in logs, audit, metrics labels, exceptions, or Git.

---

# 6. Token response handling

Use a minimal internal token representation.

Possible fields:

- access token;
- token type;
- expiration;
- granted scope;
- refresh token only if actually returned and explicitly supported.

The rest of the application depends on `AccessTokenProvider`, not Oracle raw JSON.

`toString()` and exception messages must redact credentials.

### CONCEPT

**External OAuth JSON → internal authentication contract.**

---

# 7. No generalized refresh-token subsystem

Do not add generalized refresh-token persistence/rotation unless the real Oracle flow requires a minimal explicitly supported path.

Refresh lifecycle introduces secure persistence, rotation, revocation, expiration and concurrency.

### CONCEPT

**Authenticate first; lifecycle management later.**

---

# 8. Authentication failure classification

Keep authentication failures distinct from FHIR server failures.

Examples:

- invalid authorization response;
- state mismatch;
- token endpoint rejection;
- OAuth authentication failure.

A rejected authorization code does not mean the FHIR server is unavailable.

Transport failure reaching an OAuth endpoint must remain distinguishable from protocol rejection.

### CONCEPT

**Authentication failure ≠ clinical FHIR failure ≠ dependency outage.**

---

# 9. Resilience boundary

The existing FHIR pipeline remains:

```text
Rate Limit
    ↓
Bulkhead
    ↓
Circuit Breaker
    ↓
Retry
    ↓
FHIR operation
```

Task 033 must not automatically route browser authorization through this pipeline.

OAuth resilience should be designed explicitly in a future task if needed.

---

# 10. Oracle authentication mode

Verify the authentication mode actually available for the registered Oracle Secure Sandbox application.

Before enabling runtime authentication:

- validate configured mode;
- validate profile;
- validate SMART metadata compatibility;
- reject unsupported runtime modes explicitly.

If Oracle onboarding requires a mode not implemented, document the gap rather than simulating success.

### CONCEPT

**Configuration representation ≠ runtime implementation.**

---

# 11. Security requirements

Never commit or log:

- access tokens;
- refresh tokens;
- authorization codes;
- client secrets;
- private keys;
- PKCE verifier;
- cookies;
- browser session identifiers.

Safe observability may record destination, operation, outcome, safe status and duration.

Metrics must not use tokens, patient identifiers or authorization codes as labels.

---

# 12. Required learning explanations

Cursor must explain important portions using:

**WHAT / WHY / HOW / CONCEPT**

At minimum:

### A. SMART discovery
Why authorization/token endpoints come from discovery rather than Java constants.

### B. Authorization Code

Explain:

```text
authorization request
        ≠
authorization code
        ≠
access token
```

### C. PKCE

Explain:

```text
code_verifier
        ↓
SHA-256
        ↓
code_challenge
```

and why the verifier is sent only during token exchange.

### D. state
Why validation occurs before token exchange.

### E. Redirect URI
Why the callback must match registered OAuth configuration.

### F. AccessTokenProvider
Why `FhirService` depends on a generic token provider rather than Oracle classes.

### G. Authentication vs FHIR
Why obtaining a token and reading `Patient` are separate tasks.

### H. Secrets lifecycle

```text
Long-lived configuration:
client_id / redirect URI

Ephemeral authorization session:
state / PKCE verifier / authorization code

Runtime credential:
access token
```

---

# Expected architecture/files

Exact names may adapt to the repository, but equivalents should exist for:

## Generic SMART

- authorization coordinator/service;
- authorization session manager/store;
- callback/state validator;
- authorization-code token exchange client;
- safe token response model.

## Oracle

- Oracle Secure Sandbox authentication orchestrator/configuration;
- Oracle authentication profile validation;
- Oracle authentication/readiness status model.

## Configuration

- `application.yml`;
- `.env.example`;
- documentation for local Oracle variables.

---

# Tests

## Mandatory unit tests

Cover:

1. authorization URL generation;
2. `aud` propagation;
3. PKCE S256;
4. state mismatch rejection;
5. callback without code rejection;
6. incompatible SMART metadata rejection;
7. unsupported authentication mode rejection;
8. secrets absent from exceptions;
9. `FhirService` has no Oracle authentication imports;
10. disabled Oracle profile performs no real HTTP.

## Integration tests

Normal integration must run without Oracle credentials.

Synthetic/local tests may verify:

```text
Authorization request
    ↓
callback validation
    ↓
synthetic token endpoint
    ↓
AccessTokenProvider
```

## Live Oracle test

Live authentication must be opt-in:

```text
mvn verify -Poracle-live
```

and require:

```text
ORACLE_HEALTH_LIVE_IT=true
```

Normal CI must never require Oracle credentials.

---

# Definition of Done

Task 033 is complete when:

- Oracle Secure Sandbox profile is externally configurable;
- SMART metadata is discovered from the configured environment;
- compatibility is validated;
- Authorization Code + PKCE S256 is implemented;
- authorization URL generation is real;
- callback state validation is implemented;
- authorization-code exchange is implemented;
- a real Oracle access token can be obtained when valid access is available;
- no secrets are committed;
- `FhirService` remains vendor-neutral;
- normal tests run without Oracle credentials;
- live Oracle authentication is explicit opt-in;
- important code is explained with WHAT / WHY / HOW / CONCEPT.

---

# Explicitly out of scope

- first real `Patient` READ;
- generalized refresh-token lifecycle;
- EHR launch implementation;
- Oracle production connectivity;
- Epic runtime authentication;
- AI agent;
- patient data persistence;
- vendor-specific FHIR operations;
- certification claims.

---

# Next tasks

## Task 034 — Oracle Health Live Capability Discovery

Use the authenticated/accessible Oracle environment to obtain and interpret:

```text
GET /metadata
```

## Task 035 — Oracle Health First Real Patient Read

Execute the first controlled real FHIR `Patient` READ through the platform boundaries.

## Task 036 — AI Agent Foundation

Begin the AI layer on proven interoperability primitives.

---

# Suggested Git message

```text
feat: add Oracle Health secure sandbox SMART authentication
```
