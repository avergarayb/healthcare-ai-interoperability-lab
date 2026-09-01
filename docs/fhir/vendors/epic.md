# Epic integration profile

Task 029 prepares an Epic-specific integration profile. It does **not** yet perform the real Epic sandbox authorization flow.

Read this after [fhir-smart-real-world-readiness.md](../fhir-smart-real-world-readiness.md) and [fhir-server-configuration.md](../fhir-server-configuration.md).

## What this task is

Epic is a **vendor profile**, not a fork of `FhirService`. Generic FHIR operations stay vendor-neutral. Routing still selects a destination name (`epic-sandbox`). SMART types from Task 028 are reused.

```text
FhirServerProfile (epic-sandbox, disabled)
        ↓
FhirVendor = EPIC
        ↓
EpicIntegrationProfile
        ↓
EpicCapabilities + EpicReadinessState
        ↓
EpicProfileValidator
```

No login to [Epic on FHIR](https://fhir.epic.com/). No real client ID. No Patient read against Epic.

## Official sandbox identifiers

Epic's public developer documentation (see [fhir.epic.com/Documentation](https://fhir.epic.com/Documentation), [Developer](https://fhir.epic.com/Developer/), [SMART test](https://fhir.epic.com/test/smart)) publishes an Epic-hosted non-production R4 base:

```text
https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/
```

That URL is a **public sandbox identifier**, not a customer production endpoint. A later customer-specific Interconnect URL is configuration, not a Java constant. Treat current official Epic documentation as authoritative if the sandbox URL changes.

## YAML placeholder

Profile `epic-sandbox` is **disabled** by default. Local startup still uses `local-hapi`. Credentials come from the environment; Git has empty defaults.

```yaml
epic-sandbox:
  enabled: false
  vendor: EPIC
  base-url: https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/
  fhir-version: R4
  authentication:
    type: SMART_AUTHORIZATION_CODE
    client-id: ${EPIC_SANDBOX_CLIENT_ID:}
    redirect-uri: ${EPIC_SANDBOX_REDIRECT_URI:}
    scope: ${EPIC_SANDBOX_SCOPE:}
    aud: https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/
    smart-configuration-url: ${EPIC_SANDBOX_SMART_CONFIGURATION_URL:}
  vendor-integration:
    environment: SANDBOX
    launch-mode: STANDALONE
    user-context: PATIENT
    client-authentication: PUBLIC_PKCE
```

Discovery is **not** concatenated from `fhir.epic.com` in Java. If Epic's well-known URL differs from an assumed pattern, `smart-configuration-url` wins. Do not commit `EPIC_SANDBOX_CLIENT_SECRET` or private keys.

## Environments, launch, users, auth

| Concept | Values in this task | Runtime |
|---|---|---|
| Environment | `SANDBOX` (prepared), `PRODUCTION` (represented, unused) | No production customer connection |
| Launch | `STANDALONE`, `EHR_LAUNCH` | EHR launch is readiness (`iss` / `launch`), not Hyperspace |
| User context | `PATIENT`, `CLINICIAN_STAFF` | Metadata only; scopes and Epic app registration decide access |
| Client auth | `PUBLIC_PKCE`, `CLIENT_SECRET`, `PRIVATE_KEY_JWT` | Only `PUBLIC_PKCE` is implemented (Task 028) |

Epic documents `private_key_jwt` for some confidential / backend scenarios and persistent access / refresh for qualifying confidential clients. This lab **represents** those modes and marks them unsupported at runtime. It does not fake JWT assertion.

## Readiness is not certification

| State | Meaning |
|---|---|
| `NOT_CONFIGURED` | Public sandbox URL may be present; client ID / discovery still empty |
| `CONFIGURED` | Required fields present; auth mode may be unimplemented |
| `SMART_COMPATIBLE` | Authorization Code + PKCE S256 can be built from this profile |
| `READY_FOR_SANDBOX` | SMART-compatible sandbox configuration — **not** Epic-certified |

There is no `CERTIFIED`, `PRODUCTION_READY`, or `EPIC_APPROVED` state.

## Vendor-known APIs vs CapabilityStatement

Epic publishes a resource/API catalog rather than implying every FHIR R4 interaction. `EpicKnownApiSurface` is a placeholder: this lab does **not** hardcode that catalog. Runtime inspection of a server's `CapabilityStatement` is [fhir-capability-discovery.md](../fhir-capability-discovery.md). That API is vendor-neutral; Epic identity does not imply Patient is available.

## Architecture rules

- `FhirService` does not import `lab.healthcare.fhir.vendor.epic`.
- `RoutingService` does not contain Epic OAuth logic.
- SMART discovery / PKCE stay in `lab.healthcare.fhir.smart`.
- Disabled missing credentials must not break `fhir.active-server=local-hapi`.
- Oracle Health is a sibling vendor profile; see [oracle-health.md](oracle-health.md).
