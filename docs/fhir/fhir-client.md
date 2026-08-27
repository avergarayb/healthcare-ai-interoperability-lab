# FHIR Client in fhir-integration-service

This note explains the first FHIR client in the laboratory. Read it as a teaching document, not as a catalogue of every HAPI FHIR feature.

## Three different things named "HAPI"

Keep these separate:

| Piece | Role | Where it lives |
|---|---|---|
| `fhir-integration-service` | Our Spring Boot **application**. It is the healthcare integration layer. | `services/fhir-integration-service` |
| HAPI FHIR **client library** | A Java library we depend on. It speaks FHIR over HTTP. | Maven: `hapi-fhir-client` + `hapi-fhir-structures-r4` |
| HAPI FHIR **server** | The local FHIR R4 server. Infrastructure, not application code. | Docker Compose: `hapi-fhir` on `http://localhost:8080/fhir` |

The application is a FHIR **client**. The Docker container is a FHIR **server**. The Maven artifacts are the **SDK** that lets Java talk FHIR.

## What a FHIR client is

A FHIR client is software that consumes a FHIR REST API.

It does the same job as `curl http://localhost:8080/fhir/metadata`, but with typed Java objects instead of raw JSON.

The first client operation was:

```text
GET {base-url}/metadata
        ↓
CapabilityStatement
```

Patient **read** and **search** are documented in [fhir-search.md](fhir-search.md). There is still no public REST controller.

## Why these Maven dependencies

| Artifact | Version | Scope | Responsibility |
|---|---|---|---|
| `ca.uhn.hapi.fhir:hapi-fhir-structures-r4` | `8.10.0` | compile | R4 model classes such as `CapabilityStatement` |
| `ca.uhn.hapi.fhir:hapi-fhir-client` | `8.10.0` | compile | HTTP FHIR client (`IGenericClient`) |

`8.10.0` matches the local server image `hapiproject/hapi:v8.10.0-3`. The client and the server then speak the same HAPI generation.

We did **not** add `hapi-fhir-server`, JPA, or validation modules. Those belong to *running* a FHIR server, not to calling one.

## FhirContext

`FhirContext` is HAPI's parser/serializer factory. It knows which FHIR version to use (DSTU2, STU3, R4, R5, ...).

The active server profile supplies `fhir-version: R4`. The factory builds:

```java
FhirContext.forVersion(FhirVersionEnum.R4)
```

Only R4 is accepted in this lab. If the context were R5, the client would not match our R4 server.

`FhirContext` is expensive to build and is thread-safe. Spring holds a single bean for the life of the process.

## IGenericClient

`IGenericClient` is the fluent FHIR REST client.

```java
fhirContext.newRestfulGenericClient(baseUrl)
```

It turns Java calls into FHIR HTTP requests against the **active server profile** base URL.

`capabilities().ofType(CapabilityStatement.class).execute()` is HAPI's typed equivalent of `GET /metadata`.

Clients are cheap and thread-safe. We keep one Spring bean because the base URL is fixed for a given environment.

## Base URL configuration

The server address is not hard-coded in Java. Named **server profiles** live in Spring configuration. The active profile for this lab is `local-hapi` (`authentication.type = NONE`). OAuth 2.0 Client Credentials is optional on `secured-lab`. SMART Authorization Code + PKCE is optional on `smart-lab`. See [fhir-server-configuration.md](fhir-server-configuration.md), [fhir-oauth2-authentication.md](fhir-oauth2-authentication.md), and [fhir-smart-on-fhir.md](fhir-smart-on-fhir.md).

## CapabilityStatement

`CapabilityStatement` is the FHIR resource a server returns for `/metadata`.

It answers: which FHIR version the server implements, which resources it supports, and which interactions it allows. It is the server's "I can do this" document.

Our local HAPI server currently reports FHIR R4 `4.0.1`.

## How the code is structured

```text
lab.healthcare.fhir.client
├── FhirServersProperties      # binds fhir.active-server and fhir.servers
├── FhirServerProfile          # name, baseUrl, fhirVersion, enabled, authentication
├── FhirServerProfileRegistry  # selects and validates the active profile
├── FhirClientFactory          # FhirContext + IGenericClient from a profile
├── FhirClientConfiguration    # Spring beans
├── OAuth2TokenClient          # Client Credentials token POST (optional)
├── SmartConfigurationClient   # SMART well-known discovery (optional)
├── AuthorizationCodeClient    # PKCE authorize + token exchange (optional)
├── BearerAccessTokenInterceptor
├── FhirService                # metadata, Patient read, Patient search, …
└── FhirClientException        # wraps connection/server errors
```

The package is `client`, not a second nested `fhir`, so the name describes the responsibility.

There is no `@RestController` for this feature. The learning goal is outbound FHIR communication, not a new inbound API.

## Error handling

`FhirService` does not swallow failures.

- Connection problems become `FhirClientException` with a `FhirClientConnectionException` cause.
- HTTP/FHIR server errors become `FhirClientException` with a `BaseServerResponseException` cause.

There is no global exception handler yet. That can wait until we expose HTTP APIs.

## Run the local FHIR server

From the repository root:

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

Wait until HAPI is ready, then:

```bash
curl http://localhost:8080/fhir/metadata
```

You should receive a `CapabilityStatement` with `"fhirVersion": "4.0.1"`.

## Run unit tests

Unit tests do not need Docker. From `services/fhir-integration-service`:

```bash
mvn test
```

They verify:

- the Spring context and `/actuator/health`;
- that the configured client is R4 and uses the active server profile `base-url`;
- that `FhirService` returns a `CapabilityStatement` and does not hide client errors.

## Run the integration test

The integration test talks to `http://localhost:8080/fhir`. It is a Failsafe `*IT` class and is skipped during `mvn test`.

With HAPI FHIR running:

```bash
cd services/fhir-integration-service
mvn verify -Pintegration
```

This starts the Spring context (no web server), calls `FhirService.retrieveCapabilityStatement()`, and asserts FHIR R4 `4.0.1`.
