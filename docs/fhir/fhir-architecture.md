# FHIR Integration Service architecture

This note is the package map after Tasks 001–017. It does **not** add a FHIR capability. Read it after [fhir-client.md](fhir-client.md). OAuth and SMART behavior is unchanged: see [fhir-oauth2-authentication.md](fhir-oauth2-authentication.md) and [fhir-smart-on-fhir.md](fhir-smart-on-fhir.md).

There is still no `@RestController`, no DTO layer, and no extra microservice.

## Previous architecture

After Task 017 every production class lived under one package:

```text
lab.healthcare.fhir.client
├── FhirService
├── FhirClientFactory
├── FhirClientConfiguration
├── FhirServerProfile / FhirServersProperties / FhirServerProfileRegistry
├── AccessToken / AccessTokenProvider / BearerAccessTokenInterceptor
├── OAuth2TokenClient
├── SmartConfigurationClient / AuthorizationCodeClient / Pkce / SmartTokenProvider
└── FhirClientException
```

That compiled and the tests passed. The package name `client` no longer described the contents.

## Why that structure does not scale

`client` mixed five different questions:

| Question | Example |
|---|---|
| Which FHIR operation? | `readPatient`, `$everything` |
| Which server? | `fhir.active-server`, `base-url` |
| How is the request authorized? | Bearer interceptor, token cache |
| How is a Client Credentials token obtained? | `POST /oauth/token` |
| How is SMART launched? | PKCE, well-known, authorization code |

A consulting or SaaS integration component will add Epic, Oracle Health, another grant type, or another FHIR operation. If all of those land in `client`, every change collides. The next developer cannot add an authentication mechanism without opening `FhirService`.

## New package structure

```text
lab.healthcare.fhir
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
├── auth
│   ├── AccessToken.java
│   ├── AccessTokenProvider.java
│   ├── BearerAccessTokenInterceptor.java
│   ├── CachingAccessTokenProvider.java
│   ├── FhirAuthenticationType.java
│   ├── FhirAuthenticationSettings.java
│   └── oauth2
│       ├── OAuth2TokenClient.java
│       ├── OAuth2TokenException.java
│       └── OAuth2TokenResponseParser.java
│
├── smart
│   ├── SmartConfiguration.java
│   ├── SmartConfigurationClient.java
│   ├── AuthorizationCodeClient.java
│   ├── AuthorizationSession.java
│   ├── SmartTokenProvider.java
│   └── Pkce.java
│
├── mapping
│   ├── MappingService.java
│   ├── MappingDefinition.java
│   ├── FieldMapping.java
│   └── MappingException.java
│
├── routing
│   ├── RoutingService.java
│   ├── RoutingRequest.java
│   └── RoutingException.java
│
├── observability
│   ├── FhirOperationContext.java
│   ├── FhirAuditEvent.java
│   ├── FhirAuditRecorder.java
│   ├── LoggingFhirAuditRecorder.java
│   ├── FhirMetricsRecorder.java
│   ├── InMemoryFhirMetricsRecorder.java
│   └── FhirMetricSnapshot.java
│
└── exception
    ├── FhirClientException.java
    ├── FhirErrorCategory.java
    ├── FhirErrorDetails.java
    └── FhirErrorClassifier.java
```

YAML keys (`fhir.active-server`, `fhir.servers`, nested `authentication`) are unchanged. Spring still scans from `lab.healthcare.fhir`.

## Package responsibilities

| Package | Owns | Does not own |
|---|---|---|
| `client` | HAPI `FhirContext` / `IGenericClient` construction, FHIR operations | token URLs, PKCE, profile YAML binding |
| `server` | named profiles, which server is active | how to obtain a token |
| `auth` | token value, provider SPI, Bearer interceptor, cache for Client Credentials | SMART discovery, FHIR search |
| `auth.oauth2` | Client Credentials HTTP token POST and JSON parse | SMART authorize URL, `FhirService` |
| `smart` | well-known, PKCE, authorization code, refresh | generic Client Credentials |
| `mapping` | external JSON → HAPI R4 Resource | FHIR HTTP, OAuth, terminology `$validate-code` |
| `routing` | destination profile name → enabled server + client | mapping, OAuth grant types, FHIR search logic |
| `observability` | correlation, outcome, duration, safe audit line, aggregated counters | FHIR payloads, tokens, destination lookup, Prometheus |
| `exception` | bounded failure category, safe details, `FhirClientException` | OAuth token POST (`OAuth2TokenException` stays in `auth.oauth2`), retry/circuit breaker |

`FhirAuthenticationSettings` lives in `auth` because it is the **runtime** authentication model. `FhirServersProperties.AuthenticationSettings` stays nested in `server` as the YAML binding DTO. The registry maps one to the other. That keeps Spring Boot record binding on a single canonical constructor in the properties type.

`OAuth2TokenResponseParser` is public so SMART's `AuthorizationCodeClient` can reuse the same JSON mapping as Client Credentials without becoming an OAuth class.

## Dependency direction

```text
FhirService
    │  uses IGenericClient only
    ▼
client (factory + Spring composition root)
    │
    ├──► server   (which profile)
    ├──► auth     (AccessTokenProvider)
    ├──► oauth2   (OAuth2TokenClient bean)
    └──► smart    (SmartTokenProvider bean)

server ──► auth   (FhirAuthenticationSettings on the profile)

auth ──► oauth2   (CachingAccessTokenProvider calls OAuth2TokenClient)
oauth2 ──► auth   (AccessToken, FhirAuthenticationSettings)

smart ──► auth
smart ──► oauth2  (token JSON parse + OAuth2TokenException)

mapping  (no imports of client / auth / smart)

routing ──► server   (profile lookup)
routing ──► client   (FhirClientFactory, FhirAccessTokenProviders, FhirService)
routing ──► observability (audit event + metrics after destination is known)
routing ──► exception     (RoutingException details; FhirClientException details)
```

Intended runtime chain for an authenticated FHIR call:

```text
FhirService
    → IGenericClient
        → BearerAccessTokenInterceptor
            → AccessTokenProvider
                → CachingAccessTokenProvider   (Client Credentials)
                → SmartTokenProvider           (Authorization Code + PKCE)
```

The interceptor does not know which grant produced the token.

### Cycles that must not exist

These are forbidden and are not present in production code:

```text
auth → smart → auth
smart → client → smart
server → smart → server
FhirService → OAuth2TokenClient / Pkce / AuthorizationCodeClient
```

`auth` and `auth.oauth2` import each other. That is a **namespace** cycle, not a SMART/client cycle. `AccessToken` stays in `auth` because SMART also uses it. `CachingAccessTokenProvider` stays in `auth` because it is the Client Credentials `AccessTokenProvider`, not a SMART type. No extra interface was added solely to split those two packages.

`FhirClientConfiguration` is the composition root: it may depend on every layer. That is wiring, not FHIR business logic.

## Why FhirService stays independent of OAuth and SMART

`FhirService` methods are FHIR operations (`readPatient`, `searchPatients`, `getPatientEverything`, …). Authorization is an HTTP header on the HAPI client. If `FhirService` imported `Pkce` or `OAuth2TokenClient`, every new grant type would touch the operation layer.

The preferred result is the one this refactoring keeps:

```text
FhirService imports FhirClientException and HAPI types only.
```

A future developer can add another `AccessTokenProvider` (or another `FhirServerProfile`) without editing `FhirService`.

## How the layers work together

```text
application.yml
      │
      ▼
FhirServersProperties          server (YAML)
      │
      ▼
FhirServerProfileRegistry      server → auth settings
      │
      ▼
FhirClientFactory              client
      │
      +-- NONE → IGenericClient
      +-- OAUTH2_CLIENT_CREDENTIALS → interceptor + CachingAccessTokenProvider
      +-- SMART_AUTHORIZATION_CODE  → interceptor + SmartTokenProvider
      │
      ▼
FhirService                    FHIR only
      │
      ▼
gateway / HAPI
```

Server selection answers “where”. Authentication answers “with what credential”. FHIR answers “which resource interaction”.

## Future EHR integrations

Clean boundaries make this shape possible without rewriting operations:

```text
FHIR Integration Service
│
├── FHIR operations     (client.FhirService)
├── Server profiles     (HAPI today; Epic / Oracle Health later)
├── Authentication      (NONE, Client Credentials, SMART; later other grants)
└── Exceptions          (FHIR vs token acquisition)
```

Task 018 does **not** implement those providers. It only stops accumulating unrelated classes in `client`.

Do not invent interfaces for a single implementation. `AccessTokenProvider` already exists because NONE, Client Credentials, and SMART are three behaviors behind one interceptor.

## Tests

Unit and feature tests follow the production packages where practical:

| Production | Tests |
|---|---|
| `auth` / `auth.oauth2` | interceptor, token cache, `OAuth2TokenClient`, `FhirOauth2AuthenticationIT` |
| `smart` | PKCE, discovery, code exchange, `FhirSmartOnFhirIT` |
| `server` | YAML binding, `FhirServerConfigurationIT` |
| `client` | `FhirService` unit tests and FHIR operation ITs (search, CRUD, bundles, …) |
| `mapping` | JSON → Patient/Observation unit tests, `FhirMappingIT` |
| `routing` | destination resolution unit tests, `FhirRoutingIT` |
| `observability` | audit event unit tests, `FhirAuditObservabilityIT`, metrics counters, `FhirMetricsObservabilityIT` |
| `exception` | classifier / details unit tests, `FhirErrorHandlingIT` |

Synthetic seed helpers stay next to the FHIR ITs in `client`.
