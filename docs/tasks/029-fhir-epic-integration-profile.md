# Task 029 — Epic Integration Profile

## Objective

Add an Epic-specific integration profile/readiness layer to the FHIR Integration Service without connecting to Epic's sandbox yet.

Task 028 prepared SMART on FHIR for real-world authorization servers.

Task 029 now answers:

> What Epic-specific configuration, capabilities, constraints, and conventions must our platform understand before we perform a real Epic sandbox integration?

The goal is to make Epic a vendor profile, not to spread `if (vendor == EPIC)` logic throughout the application.

This task must preserve the separation established in Tasks 018–028.

---

## Baseline

Start from `main` after Task 028 is merged.

Expected previous capability:

```text
Generic FHIR
    +
OAuth 2.0
    +
SMART on FHIR
    +
Real-world SMART readiness
    +
Mapping
    +
Routing
    +
Observability
    +
Resilience
```

Task 029 adds:

```text
Epic vendor awareness
```

It does not yet add:

```text
real Epic sandbox credentials
real Epic authorization
real Epic patient data
```

---

## Why this task exists

FHIR and SMART provide standards, but a real EHR vendor still has:

- its own developer ecosystem;
- its own application registration process;
- vendor-specific endpoint conventions;
- supported FHIR resource catalog;
- launch models;
- client authentication choices;
- sandbox behavior;
- implementation-specific operational constraints.

The platform should therefore distinguish:

```text
Generic FHIR behavior
```

from:

```text
Epic-specific integration profile
```

without coupling FHIR operations to Epic.

---

## Official Epic facts to account for

At task creation time, Epic's public developer documentation indicates:

- Epic provides an Epic-hosted non-production sandbox.
- Epic's public sandbox exposes an R4 FHIR base URL.
- Epic on FHIR supports application registration and non-production client IDs.
- Epic documentation includes SMART on FHIR / OAuth 2.0 flows.
- Epic applications may have different primary user types, such as patients or clinicians/staff.
- Epic documentation discusses persistent access and refresh tokens for qualifying confidential clients.
- Epic documentation also describes `private_key_jwt` for some client authentication scenarios.
- Epic publishes a resource/API catalog rather than implying that every FHIR capability is universally supported.

Do not infer broader Epic support than official documentation states.

---

## Vendor profile architecture

Create a vendor-aware package.

Suggested:

```text
lab.healthcare.fhir.vendor
```

with:

```text
vendor
├── FhirVendor
├── FhirVendorProfile
└── epic
    ├── EpicIntegrationProfile
    ├── EpicProfileValidator
    └── EpicCapabilities
```

The exact class names may differ if a cleaner design fits the current project.

Do not create a giant vendor abstraction prematurely.

---

## FhirVendor

Introduce a small bounded vendor identity model.

Example:

```text
GENERIC
EPIC
```

Do not add Oracle Health implementation yet.

Vendor identity should be descriptive metadata, not a switch controlling unrelated business logic.

---

## EpicIntegrationProfile

The Epic profile should describe the information our platform needs to know before a real connection.

Suggested concepts:

```text
vendor = EPIC
fhirVersion = R4
fhirBaseUrl
smartConfigurationUrl
clientId
redirectUri
requestedScopes
launchMode
clientAuthenticationMethod
environment
```

Do not store secrets in source code.

Do not commit:

- client secrets;
- private keys;
- JWT signing keys;
- access tokens;
- refresh tokens.

---

## Epic environments

Model the concept of environment explicitly.

Suggested:

```text
SANDBOX
PRODUCTION
```

Task 029 only prepares `SANDBOX`.

No production Epic customer connection is performed.

The profile must not assume that every Epic installation has the same production URL.

A future customer-specific Epic endpoint will be configuration, not hardcoded Java.

---

## Epic sandbox base configuration

Use configuration placeholders rather than secrets.

Conceptual YAML:

```yaml
fhir:
  servers:
    epic-sandbox:
      enabled: false
      vendor: EPIC
      base-url: https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/
      fhir-version: R4

      authentication:
        type: SMART
        client-id: ${EPIC_SANDBOX_CLIENT_ID:}
        redirect-uri: ${EPIC_SANDBOX_REDIRECT_URI:}
        scope: ${EPIC_SANDBOX_SCOPE:}
        aud: https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/
        smart-configuration-url: ${EPIC_SANDBOX_SMART_CONFIGURATION_URL:}
```

Important:

- Keep the Epic profile disabled by default.
- Do not require an Epic account for normal local startup.
- Do not hardcode a real client ID.
- Do not commit private credentials.
- If Epic's actual discovery endpoint differs from an assumed pattern, configuration must win.

---

## Launch modes

Model only the distinction needed for readiness.

Suggested:

```text
STANDALONE
EHR_LAUNCH
```

Do not implement a complete Epic launch workflow yet.

### Standalone

The application initiates authorization itself.

### EHR Launch

The EHR launches the application with context such as:

```text
iss
launch
```

Task 029 should model/readiness-check these concepts.

Do not implement a production Hyperspace launch.

---

## Epic user context

Suggested:

```text
PATIENT
CLINICIAN_STAFF
```

This is configuration metadata.

Do not encode clinical authorization decisions directly in Java based only on this enum.

The actual scopes and Epic app registration determine access.

---

## Client authentication method

Model Epic-relevant client authentication choices without implementing all of them yet.

Suggested:

```text
PUBLIC_PKCE
CLIENT_SECRET
PRIVATE_KEY_JWT
```

Task 028 already supports Authorization Code + PKCE S256.

Task 029 should:

- recognize `PUBLIC_PKCE` as compatible with the existing public-client flow;
- represent `CLIENT_SECRET` as a possible confidential-client mode;
- represent `PRIVATE_KEY_JWT` as a known Epic-relevant mode;
- clearly mark unimplemented authentication methods as unsupported by the current runtime.

Do not implement `private_key_jwt` in Task 029 unless it already exists.

Do not fake support.

---

## EpicCapabilities

Create a small model describing what our platform currently knows about the Epic integration profile.

Examples:

```text
supportsSmartAuthorizationCode
supportsPkceS256
supportsR4
supportsStandaloneLaunch
supportsEhrLaunchReadiness
supportsPersistentAccessReadiness
```

Be precise:

```text
readiness
```

is not:

```text
certified working integration
```

Do not mark sandbox functionality as validated until a later real sandbox task executes it.

---

## EpicProfileValidator

Create a validator that answers:

> Is this Epic profile sufficiently configured for the integration mode we intend to use?

Possible checks:

```text
vendor == EPIC
FHIR version == R4 for our current implementation
base URL present
client ID present when enabling real use
redirect URI present for Authorization Code flow
SMART configuration URL present/configurable
aud present
requested scopes present
supported client authentication mode
```

When the profile is disabled, missing credentials should not break normal application startup unless the existing server configuration rules already require them.

---

## Readiness states

Create a bounded readiness model if useful.

Example:

```text
NOT_CONFIGURED
CONFIGURED
SMART_COMPATIBLE
READY_FOR_SANDBOX
```

Do not use:

```text
CERTIFIED
PRODUCTION_READY
EPIC_APPROVED
```

Task 029 does not prove those claims.

---

## Resource/API awareness

Do not assume Epic supports every FHIR R4 resource and operation.

Create a clear architectural placeholder for provider capability information.

Task 029 should not hardcode a huge list of Epic APIs.

The later Capability Discovery task will handle runtime capability inspection.

---

## Relationship with Capability Discovery

Task 029 represents:

```text
Vendor-known metadata
```

Task 031 will represent:

```text
Server-discovered capabilities
```

These are complementary.

---

## Relationship with Task 028

Task 028 already provides:

```text
SmartConfiguration
SmartCapabilities
SmartConfigurationValidator
SmartAuthorizationRequest
PKCE
```

Task 029 must reuse these.

Do not duplicate SMART discovery inside the Epic package.

---

## Relationship with FhirService

`FhirService` must remain vendor-neutral.

It must not know:

```text
Epic
Hyperspace
Epic Sandbox
Epic OAuth URL
Epic client ID
```

Mandatory architecture assertion:

```text
FhirService must not import lab.healthcare.fhir.vendor.epic.*
```

Add a test or architectural assertion if appropriate.

---

## Relationship with Routing

Routing continues selecting:

```text
destination = epic-sandbox
```

The routing layer should not contain Epic-specific OAuth logic.

---

## Security requirements

No secrets in Git.

Potential variables:

```text
EPIC_SANDBOX_CLIENT_ID
EPIC_SANDBOX_REDIRECT_URI
EPIC_SANDBOX_SCOPE
EPIC_SANDBOX_SMART_CONFIGURATION_URL
```

If confidential-client support is represented:

```text
EPIC_SANDBOX_CLIENT_SECRET
```

must never receive a committed default value.

If `private_key_jwt` is represented:

- no private key in repository;
- configuration should reference an external location or future secret-management mechanism;
- Task 029 does not need to implement key storage.

---

## Tests

Add unit tests for:

### EpicIntegrationProfile

Validate:

- vendor = EPIC;
- environment;
- FHIR version;
- launch mode;
- auth method;
- requested scopes;
- aud.

### EpicProfileValidator

Accept:

- complete sandbox profile for supported public PKCE mode.

Reject:

- wrong vendor;
- unsupported FHIR version;
- missing base URL;
- enabled profile missing client ID;
- enabled Authorization Code profile missing redirect URI;
- missing `aud`;
- unsupported runtime auth mode when marked required.

### Security

Verify logs/toString/exceptions do not expose secrets.

### Architecture

Verify `FhirService` remains independent from Epic classes.

---

## Integration test

Create an integration/readiness test that does not contact Epic.

Suggested:

```text
EpicIntegrationProfileIT
```

It should prove:

1. Epic sandbox profile can be bound from configuration.
2. Profile is disabled by default.
3. Real credentials are not required for the normal local profile.
4. Epic profile can be validated when synthetic test configuration supplies required values.
5. Generic SMART components can consume the profile.
6. No internet request to Epic occurs.

---

## Mandatory learning explanations

Cursor must explain important code using:

```text
WHAT
WHY
HOW
CONCEPT
```

Mandatory explanations:

1. Generic FHIR vs vendor-specific profile.
2. Why Epic does not belong inside `FhirService`.
3. Epic sandbox vs Epic customer production endpoint.
4. Standalone SMART vs EHR launch readiness.
5. Public PKCE vs confidential client vs `private_key_jwt`.
6. Vendor-known capabilities vs runtime CapabilityStatement.
7. Why credentials remain outside Git.
8. Why "ready for sandbox" is not "Epic-certified".

---

## Documentation

Create:

```text
docs/fhir/vendors/epic.md
```

Create `docs/fhir/vendors/` if necessary.

Update where appropriate:

```text
docs/fhir/README.md
docs/fhir/fhir-architecture.md
docs/fhir/fhir-server-configuration.md
docs/fhir/fhir-smart-real-world-readiness.md
docs/roadmap.md
README.md
```

Document clearly:

```text
Task 029 prepares an Epic-specific integration profile.
It does not yet perform the real Epic sandbox authorization flow.
```

---

## Official references

Use official Epic sources during implementation and documentation:

- https://fhir.epic.com/
- https://fhir.epic.com/Developer/
- https://fhir.epic.com/test/smart
- https://fhir.epic.com/Documentation

At task creation time, Epic publicly documents an R4 sandbox base URL under:

```text
https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/
```

Treat current official Epic documentation as authoritative if values change.

---

## Out of scope

Task 029 does NOT include:

- logging into Epic on FHIR;
- creating the real Epic application registration;
- receiving a real Epic client ID;
- executing real Epic OAuth;
- accessing Epic sandbox Patient data;
- production Epic customer deployment;
- `private_key_jwt` implementation;
- dynamic client registration;
- Oracle Health;
- AI Agent;
- database persistence.

---

## Acceptance criteria

Task 029 is complete when:

1. Epic is represented as a vendor profile without contaminating generic FHIR code.
2. Epic sandbox configuration exists but is disabled by default.
3. No real credentials are committed.
4. Epic environment, launch mode, user context, and client auth mode can be represented.
5. Existing SMART components are reused.
6. Unsupported authentication modes are represented honestly rather than faked.
7. Epic profile validation exists.
8. Vendor-known capabilities remain distinct from runtime capability discovery.
9. `FhirService` remains vendor-neutral.
10. CI does not require internet/Epic availability.
11. Existing Tasks 001–028 remain green.
12. Documentation uses official Epic references.
13. Important code is explained using WHAT / WHY / HOW / CONCEPT.

---

## Validation

Run:

```bash
mvn clean test
```

Then:

```bash
mvn clean verify -Pintegration
```

Expected:

```text
BUILD SUCCESS
```

---

## Git

Branch:

```text
feature/fhir-epic-integration-profile
```

Baseline:

```text
main
```

Do not commit or push automatically.

Recommended commit:

```text
feat: add Epic FHIR integration profile
```

---

## Next step

Do not connect to Epic sandbox in Task 029.

The next planned task is:

```text
Task 030 — Oracle Health Integration Profile
```

After vendor-readiness tasks and capability discovery, a later phase will perform the real sandbox integrations manually and through controlled integration tests.
