# FHIR server configuration and client profiles

This note starts Phase 2: the Java client can describe **more than one** FHIR server in configuration, and pick one without changing `FhirService`. Read it after [fhir-client.md](fhir-client.md).

There is still no SMART, REST controller, or secret store. OAuth 2.0 Client Credentials is documented in [fhir-oauth2-authentication.md](fhir-oauth2-authentication.md).

## Server vs client

| Piece | Role |
|---|---|
| FHIR **server** | Stores Resources. This lab’s server is HAPI in Docker at `http://localhost:8080/fhir`. |
| FHIR **client** | `fhir-integration-service`. It calls the server over HTTP. |
| **Server profile** | Named connectivity settings (URL, FHIR release, enabled). Not a StructureDefinition profile. |

Named profiles live in `lab.healthcare.fhir.server`. `FhirService` stays in `client`. See [fhir-architecture.md](fhir-architecture.md).

`FhirService` speaks FHIR operations (`read`, `search`, `$everything`, …). It must not own the server URL.

## Why the URL is not in Java

A reusable interoperability layer will talk to a lab HAPI today and to another R4 endpoint tomorrow. Changing code for each URL does not scale.

```text
application.yml
      |
      v
FhirServersProperties
      |
      v
FhirServerProfileRegistry   ← which profile is active
      |
      v
FhirClientFactory           ← FhirContext + IGenericClient
      |
      v
FhirService                 ← operations only
```

Local, staging, and production should differ by YAML (or env), not by a commit to `FhirService`.

## FHIR Server profile

```text
Profile
 |
 +-- name         local-hapi
 +-- baseUrl      http://localhost:8080/fhir
 +-- fhirVersion  R4
 +-- enabled      true
 +-- authentication
       +-- type   NONE
```

OAuth fields (`tokenUrl`, `clientId`, client secret via environment) belong to a **different** profile (`secured-lab`). See [fhir-oauth2-authentication.md](fhir-oauth2-authentication.md).

## External configuration

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

`example-org` is a **disabled placeholder**. It proves a second profile can exist without calling a real vendor. Do not put commercial EHR URLs here.

Active profile:

```text
fhir.active-server = local-hapi
        ↓
must exist in fhir.servers
        ↓
must be enabled
        ↓
base-url and fhir-version required
```

Invalid configuration fails at startup (`IllegalStateException`), not on the first Patient read.

Environment overlay (no Java change):

```text
application.yml              defaults
application-local.yml        --spring.profiles.active=local
```

`application-local.yml` only restates `active-server: local-hapi` as a teaching overlay.

## One active client per process

This task defines **many profiles**, and uses **one** of them as the Spring `IGenericClient` bean.

```text
Option A (implemented for runtime)
  Application → one active FHIR server

Option B (prepared in YAML)
  local-hapi + example-org (disabled)
```

There is no request-time router and no REST API to switch profiles. Change `fhir.active-server` and restart (or use a Spring profile).

## FHIR version

YAML `fhir-version: R4` is the **release family**.

HAPI:

```java
FhirContext.forVersion(FhirVersionEnum.valueOf("R4"))
```

Only **R4** is accepted. `R5` is rejected. That keeps the mapping explicit without implementing R5.

The **server** still reports publication version `4.0.1` in `CapabilityStatement.fhirVersion`. Those are related, not the same string.

`FhirContext` is created once as a Spring bean. It is not created inside `readPatient`.

## IGenericClient

```java
fhirContext.newRestfulGenericClient(profile.baseUrl())
```

The URL comes from the active `FhirServerProfile`. `FhirService` keeps constructor injection of `IGenericClient`.

## CapabilityStatement

Verified against local HAPI **before** the Java change:

```http
GET http://localhost:8080/fhir/metadata
```

HTTP `200`, `CapabilityStatement`, `fhirVersion: 4.0.1`, `implementation.url: http://localhost:8080/fhir`.

That response is **server** metadata. The **client** only chooses which base URL to call. After this task, that choice is `fhir.servers.local-hapi.base-url`.

`FhirService.retrieveCapabilityStatement()` is unchanged. The IT `FhirServerConfigurationIT` reads `/metadata` and `Patient/patient-001` through the configured profile.

## HTTP vs client

| Step | Who |
|---|---|
| Listen on `:8080`, persist Postgres | HAPI server (Compose) |
| `GET /metadata`, `GET /Patient/patient-001` | any HTTP client |
| Bind YAML, build `FhirContext` + `IGenericClient` | Spring / this service |
| `capabilities().execute()`, `read().resource(Patient.class)` | HAPI Java client |

## What this task does not do

- OAuth 2.0 Client Credentials is implemented for `secured-lab`; `local-hapi` stays `NONE`
- SMART, JWT login, client credentials against a real EHR
- Secrets committed in YAML
- Multi-tenant routing
- Persisting profiles in a database
- `@RestController` / business DTOs
- FHIR R5

Next planned lab task is SMART on FHIR. Not implemented here.
