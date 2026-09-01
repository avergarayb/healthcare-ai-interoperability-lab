# Oracle Health integration profile

Task 030 prepares an Oracle Health-specific integration profile. It does **not** connect to a real Oracle Health sandbox, register an application, or read Patient data.

Read this after [epic.md](epic.md) and [fhir-smart-real-world-readiness.md](../fhir-smart-real-world-readiness.md).

## What this task is

Oracle Health is a **vendor profile**, not a fork of `FhirService`. Generic FHIR operations stay vendor-neutral. Routing still selects a destination name (`oracle-health-sandbox`). SMART types from Task 028 are reused. Epic from Task 029 stays unchanged.

```text
Generic FHIR Layer
        │
        ▼
Vendor Integration Layer
        │
   ┌────┴─────┐
   │          │
 Epic     Oracle Health
```

```text
FhirServerProfile (oracle-health-sandbox, disabled)
        ↓
FhirVendor = ORACLE_HEALTH
        ↓
OracleHealthIntegrationProfile
        ↓
OracleHealthCapabilities + OracleHealthReadinessState
        ↓
OracleHealthProfileValidator
```

Java does **not** concatenate Oracle/Cerner hostnames into a FHIR base URL. A later customer endpoint is configuration.

## YAML placeholder

Profile `oracle-health-sandbox` is **disabled** by default. Local startup still uses `local-hapi`. All registration values come from the environment; Git has empty defaults.

```yaml
oracle-health-sandbox:
  enabled: false
  vendor: ORACLE_HEALTH
  fhir-version: R4
  base-url: ${ORACLE_HEALTH_SANDBOX_BASE_URL:}
  authentication:
    type: SMART_AUTHORIZATION_CODE
    client-id: ${ORACLE_HEALTH_SANDBOX_CLIENT_ID:}
    redirect-uri: ${ORACLE_HEALTH_SANDBOX_REDIRECT_URI:}
    scope: ${ORACLE_HEALTH_SANDBOX_SCOPE:}
    aud: ${ORACLE_HEALTH_SANDBOX_AUD:}
    smart-configuration-url: ${ORACLE_HEALTH_SANDBOX_SMART_CONFIGURATION_URL:}
  vendor-integration:
    environment: SANDBOX
    launch-mode: STANDALONE
    user-context: PATIENT
    client-authentication: PUBLIC_PKCE
```

Do not commit client secrets, private keys, access tokens, or authorization codes.

## Environments, launch, auth

| Concept | Values | Runtime |
|---|---|---|
| Environment | `SANDBOX` (prepared), `PRODUCTION` (represented) | No customer production connection; production URLs are not manufactured in Java |
| Launch | `STANDALONE`, `EHR_LAUNCH` | EHR launch is readiness (`iss` / `launch`), not implemented |
| User context | `PATIENT`, `CLINICIAN_STAFF` | Metadata only |
| Client auth | `PUBLIC_PKCE`, `CLIENT_SECRET`, `PRIVATE_KEY_JWT` | Only `PUBLIC_PKCE` is implemented (Task 028) |

Unsupported modes fail with `OracleHealthProfileException` when selected for runtime use. The lab does not fake JWT assertion.

## Readiness is not certification

| State | Meaning |
|---|---|
| `NOT_CONFIGURED` | Disabled; registration values empty |
| `CONFIGURED` | Required fields present; auth mode may be unimplemented |
| `SMART_COMPATIBLE` | Authorization Code + PKCE S256 can be built from this profile |
| `READY_FOR_SANDBOX` | SMART-compatible sandbox configuration — **not** Oracle-approved |

There is no `CERTIFIED`, `PRODUCTION_READY`, or `ORACLE_APPROVED` state.

## Vendor-known APIs vs CapabilityStatement

`OracleHealthKnownApiSurface.assumesEveryR4Resource()` is `false`. Runtime inspection of a server's `CapabilityStatement` (`GET /metadata`) is [fhir-capability-discovery.md](../fhir-capability-discovery.md). That API is vendor-neutral; Oracle Health identity does not imply Patient is available.

## Architecture rules

- `FhirService` does not import `lab.healthcare.fhir.vendor.oracle`.
- Routing and resilience do not contain `if (vendor == ORACLE_HEALTH)`.
- There is no `OracleSmartConfigurationClient`, `OraclePkce`, or `OracleTokenProvider`.
- Disabled missing credentials must not break `fhir.active-server=local-hapi`.
