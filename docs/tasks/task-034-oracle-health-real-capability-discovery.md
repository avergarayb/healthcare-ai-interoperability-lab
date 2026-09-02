# Task 034 — Oracle Health Real Capability Discovery

**Project:** Healthcare AI Interoperability Lab  
**Status:** Planned  
**Prerequisite:** Task 033 completed and merged into `main` through PR
\#32  
**Base branch:** `main`

------------------------------------------------------------------------

## 1. Context

Task 033 successfully validated the Oracle Health SMART on FHIR
authentication flow against the real Oracle Health sandbox.

The real flow completed successfully with:

- Authorization Code flow
- PKCE using `S256`
- Provider sandbox login
- OAuth callback validation
- Token exchange
- HTTP `200`
- Access token issued

Observed result:

``` text
tokenIssued=true
publicPkceAttempted=true
incompatibility=NONE
httpStatus=200
detail=Token exchange succeeded with public PKCE

hasAccessToken=true
hasScope=true
hasPatient=false
```

An important finding from Task 033 is that the Oracle SMART discovery
document advertised confidential token endpoint authentication methods,
but the real Authorization Code + Public PKCE flow nevertheless
succeeded.

Therefore, the architecture must preserve the validated PUBLIC_PKCE
implementation. Do not add `client_secret_basic` or `private_key_jwt` as
part of this task.

------------------------------------------------------------------------

## 2. Goal

Validate the existing provider-neutral **FHIR Capability Discovery**
implementation against the real Oracle Health Millennium FHIR R4
endpoint.

The objective is to confirm that the capability discovery architecture
implemented previously can consume and normalize a real Oracle Health
`CapabilityStatement`.

------------------------------------------------------------------------

## 3. Architectural Context

Relevant repository evolution:

``` text
PR #28 — Epic Integration Profile
        ↓
PR #29 — Oracle Health Integration Profile
        ↓
PR #30 — FHIR Capability Discovery
        ↓
PR #31 — Oracle Health Sandbox Connection Readiness
        ↓
PR #32 — Oracle Health Secure Sandbox SMART Authentication
        ↓
Task 034 — Oracle Health Real Capability Discovery
```

Current repository HEAD:

``` text
9a51ca6 Merge pull request #32 from avergarayb/feature/oracle-health-secure-sandbox-auth
```

The implementation should build on the existing architecture rather than
creating Oracle-specific duplicate capability discovery logic.

------------------------------------------------------------------------

## 4. Scope

### In scope

1.  Start from current `main`.
2.  Create a dedicated feature branch.
3.  Reuse the existing Oracle Health Integration Profile.
4.  Reuse the existing FHIR Capability Discovery abstractions from PR
    \#30.
5.  Connect to the real Oracle Health Millennium FHIR R4 `/metadata`
    endpoint.
6.  Retrieve the real Oracle `CapabilityStatement`.
7.  Parse it using the existing provider-neutral architecture where
    possible.
8.  Validate transformation into the project’s normalized capability
    representation.
9.  Document Oracle-specific validation findings.
10. Keep live Oracle validation opt-in.
11. Ensure normal tests do not require Oracle credentials or network
    access.

### Out of scope

- Reading clinical patient data.
- Searching for patients.
- Implementing Patient read operations.
- Implementing EHR launch context.
- Adding `client_secret_basic`.
- Adding `private_key_jwt`.
- Changing the validated PUBLIC_PKCE architecture.
- Persisting OAuth access tokens.
- Logging OAuth secrets, tokens, codes, or PKCE verifiers.
- Implementing provider-specific duplicate capability models.

------------------------------------------------------------------------

## 5. Functional Requirements

### 5.1 Oracle endpoint configuration

The Oracle Health host must not be hardcoded in Java source code.

Configuration must continue to come from environment variables and/or
integration profile configuration.

The implementation should resolve:

``` text
{FHIR_BASE_URL}/metadata
```

or use the existing architecture’s equivalent endpoint resolution
mechanism.

### 5.2 Capability discovery

The implementation must retrieve server metadata through:

``` text
GET /metadata
```

The returned resource is expected to be a FHIR R4 `CapabilityStatement`.

Interpret relevant information where supported by the existing
architecture:

- FHIR version
- server capabilities
- supported resources
- supported interactions
- supported search capabilities
- supported operations
- implementation metadata
- relevant security information

Do not invent Oracle capabilities that are not present in the actual
response.

### 5.3 Provider-neutral normalization

Use the existing normalized capability representation.

Target architecture:

``` text
Oracle Health Integration Profile
            ↓
FHIR endpoint resolution
            ↓
GET /metadata
            ↓
Oracle CapabilityStatement
            ↓
Existing Capability Discovery
            ↓
Normalized FhirServerCapabilities
```

Avoid a parallel Oracle-only implementation unless a documented
architectural limitation makes it necessary.

------------------------------------------------------------------------

## 6. Authentication Considerations

Determine from real Oracle behavior whether `/metadata` requires an
access token.

Possible outcomes:

### Outcome A — Public metadata

Capability discovery can execute without OAuth authentication.

### Outcome B — Protected metadata

Live validation may reuse the existing authenticated Oracle integration
flow where architecturally appropriate.

In either case:

- Do not persist tokens unnecessarily.
- Do not expose tokens in logs.
- Do not commit credentials.
- Document the actual Oracle behavior.

------------------------------------------------------------------------

## 7. Testing Requirements

The following must remain independent from live Oracle access:

``` bash
mvn clean test
```

``` bash
mvn clean verify -Pintegration
```

Live Oracle validation must remain explicitly opt-in.

Do not introduce a design requiring:

- real credentials during unit tests
- Oracle network access during normal integration tests
- committed secrets
- committed tokens

Use the existing live-test opt-in mechanism where possible, for example:

``` text
ORACLE_HEALTH_LIVE_IT=true
```

------------------------------------------------------------------------

## 8. Security Requirements

Never commit:

- access tokens
- refresh tokens
- authorization codes
- PKCE verifiers
- client secrets
- private keys

Never log sensitive OAuth values.

Configuration containing local credentials must remain ignored by Git.

The Oracle Health hostname must not be unnecessarily duplicated or
hardcoded across Java source files.

------------------------------------------------------------------------

## 9. Documentation Requirements

Update or create documentation describing:

1.  The purpose of Oracle Health real capability discovery.
2.  The Oracle `/metadata` endpoint validation.
3.  Whether authentication was required.
4.  The real Oracle FHIR version returned.
5.  Relevant capability discovery findings.
6.  Differences from previously tested FHIR providers, if observed.
7.  Architectural conclusions.

Clearly distinguish configuration assumptions from actual live
validation results.

------------------------------------------------------------------------

## 10. Expected Deliverables

Before committing, provide:

### Architecture summary

Explain:

- how existing capability discovery was reused
- how Oracle configuration is resolved
- whether authentication is required for `/metadata`
- how Oracle capabilities are normalized

### Files changed

List:

- production files
- test files
- configuration files
- documentation files

### Tests executed

Report results for:

``` bash
mvn clean test
```

and:

``` bash
mvn clean verify -Pintegration
```

### Live Oracle validation

Report:

- endpoint tested
- HTTP result
- whether authentication was required
- FHIR version
- high-level capability discovery result

Do not include sensitive tokens or credentials.

### Proposed commit message

Provide a conventional commit message.

**Do not commit or merge until reviewed.**

------------------------------------------------------------------------

## 11. Acceptance Criteria

- [ ] Implementation starts from current `main`.
- [ ] A dedicated feature branch exists.
- [ ] Oracle `/metadata` is reached through configuration, not hardcoded
  Java hosts.
- [ ] Real Oracle `CapabilityStatement` is retrieved during opt-in live
  validation.
- [ ] Existing capability discovery architecture is reused where
  possible.
- [ ] Oracle capabilities are normalized into the existing project
  model.
- [ ] No Oracle-specific duplicate capability architecture is introduced
  without justification.
- [ ] Normal unit tests do not require Oracle access.
- [ ] Standard integration tests do not require Oracle credentials.
- [ ] Live validation is explicitly opt-in.
- [ ] Sensitive OAuth values are not logged or committed.
- [ ] Documentation includes real Oracle validation findings.
- [ ] `mvn clean test` passes.
- [ ] `mvn clean verify -Pintegration` passes.
- [ ] Architecture summary and proposed commit are reviewed before
  commit.

------------------------------------------------------------------------

## 12. Next Task

After Task 034:

# Task 035 — Oracle Health Authenticated FHIR Clinical Data Read

Task 033 produced:

``` text
hasPatient=false
```

Therefore, Task 035 must not assume that a Patient context is
automatically available.

The correct Oracle sandbox strategy for identifying and reading an
authorized Patient must be determined from the real environment and
documented.

Potential flow:

``` text
Oracle SMART Authentication
        ↓
Access Token
        ↓
FHIR Authorization
        ↓
Determine permitted patient access
        ↓
Patient search or read
        ↓
Real Oracle FHIR response
        ↓
Normalization into project architecture
```
