# FHIR OAuth 2.0 authentication

This note adds **OAuth 2.0 Client Credentials** to the Java FHIR client. Read it after [fhir-server-configuration.md](fhir-server-configuration.md). It is **not** SMART on FHIR.

There is still no login UI, OpenID Connect, `@RestController`, or vendor identity provider.

## FHIR vs OAuth

| Term | Meaning here |
|---|---|
| FHIR | Resource model and REST API (`Patient`, `GET /fhir/Patient/{id}`). |
| OAuth 2.0 | Authorization framework that issues a temporary **access token**. |
| Access token | Credential the client presents to a protected API. |
| Bearer token | That credential sent as `Authorization: Bearer …`. |

A FHIR server can exist without OAuth (`local-hapi` on `:8080`). OAuth can protect an API that is not FHIR. In this lab they coexist only for the **`secured-lab`** profile.

## Roles

```text
Resource Owner     (not used: there is no human login)
      |
Client             fhir-integration-service
      |
Authorization Server   lab-oauth  :9090
      |
Access Token
      |
Resource Server    fhir-gateway :8180  →  HAPI :8080
```

| Role | Lab component |
|---|---|
| OAuth **client** | `fhir-integration-service` (`client_id` = `lab-client`) |
| **Authorization Server** | Synthetic Python token endpoint `POST /oauth/token` |
| **Resource Server** | nginx gateway in front of HAPI. HAPI itself does not validate OAuth. |

HAPI `hapiproject/hapi:v8.10.0-3` does not enforce `Authorization`. A reverse proxy is the local Resource Server. The unsecured HAPI listener stays on `:8080` so Task 015 (`local-hapi`, `authentication.type = NONE`) keeps working.

Port **8081** is the Spring Boot app, not a FHIR base URL. The protected FHIR base is `http://localhost:8180/fhir`.

## Why Client Credentials

Server-to-server integration has no browser and no user:

```text
fhir-integration-service
        |  grant_type=client_credentials
        |  client_id + client_secret
        v
Authorization Server
        |  access_token, token_type=Bearer, expires_in
        v
FHIR HTTP request
        |  Authorization: Bearer …
        v
Protected FHIR gateway
```

Authorization Code, PKCE, and SMART launch context belong to [fhir-smart-on-fhir.md](fhir-smart-on-fhir.md).

HAPI ships `BearerTokenAuthInterceptor(String)` for a **fixed** token. Tokens expire (`expires_in`), so this lab uses a custom `IClientInterceptor` that asks an `AccessTokenProvider` on each request. The provider caches until expiry minus 30 seconds.

No extra Maven OAuth library: JDK `HttpClient` posts the token request; Jackson (already on the classpath via Spring Web) parses JSON; HAPI `registerInterceptor` adds the header.

## HTTP first

Token (synthetic values only):

```http
POST http://localhost:9090/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id=lab-client
&client_secret=lab-secret
```

```json
{
  "access_token": "lab-access-token",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

Protected Patient:

```http
GET http://localhost:8180/fhir/Patient/patient-001
Authorization: Bearer lab-access-token
```

Observed against this lab stack:

| Request | Result |
|---|---|
| No `Authorization` | `401` JSON `{"error":"invalid_token"}` |
| `Authorization: Bearer invalid-token` | `401` same body |
| `Authorization: Bearer lab-access-token` | `200` FHIR `Patient` (proxied to HAPI) |
| Wrong `client_secret` on `/oauth/token` | `401` `{"error":"invalid_client"}` |
| `grant_type` other than `client_credentials` / `authorization_code` / `refresh_token` | `400` `{"error":"unsupported_grant_type"}` |
| Unsecured `GET http://localhost:8080/fhir/Patient/patient-001` | still `200` (NONE) |

## Compose services

```text
docker compose
 ├── hapi-fhir-postgres
 ├── hapi-fhir          :8080   FHIR, no OAuth
 ├── lab-oauth          :9090   token endpoint
 └── fhir-gateway       :8180   Bearer check, then proxy to HAPI
```

`lab-oauth` is a small Python `http.server`. It is not Keycloak, Spring Authorization Server, or Azure AD.

The gateway asks the Authorization Server (`auth_request`) whether the Bearer token may access the FHIR path. Client Credentials still uses the synthetic value `lab-access-token` (system-style). SMART tokens carry scopes; see [fhir-smart-on-fhir.md](fhir-smart-on-fhir.md). The gateway strips `Authorization` before proxying so HAPI never sees it.

## Configuration vs connectivity

Task 015 profiles still hold URL and FHIR version. Authentication is nested, optional, and **not** required for every server:

```yaml
fhir:
  active-server: local-hapi
  servers:
    local-hapi:
      base-url: http://localhost:8080/fhir
      fhir-version: R4
      enabled: true
      authentication:
        type: NONE
    secured-lab:
      base-url: http://localhost:8180/fhir
      fhir-version: R4
      enabled: false
      authentication:
        type: OAUTH2_CLIENT_CREDENTIALS
        token-url: http://localhost:9090/oauth/token
        client-id: lab-client
        client-secret: ${FHIR_SECURED_LAB_CLIENT_SECRET:}
```

`secured-lab` stays **disabled** by default. Empty secret is allowed while disabled. Enabling it without `FHIR_SECURED_LAB_CLIENT_SECRET` fails at startup.

Copy `infra/docker/.env.example` to `.env` (gitignored). Do not commit real secrets. Production would use a secret manager, not YAML.

## Java layout

```text
FhirServersProperties
      |
      v
FhirServerProfile (+ FhirAuthenticationSettings)
      |
      v
FhirClientFactory
      |
      +-- NONE  → IGenericClient (no Authorization)
      |
      +-- OAUTH2_CLIENT_CREDENTIALS
              |
              v
        CachingAccessTokenProvider  ← OAuth2TokenClient
              |
              v
        BearerAccessTokenInterceptor
              |
              v
        IGenericClient → FHIR HTTP
              |
              v
        FhirService   (unchanged: still only IGenericClient)
```

Client Credentials types live in `lab.healthcare.fhir.auth` / `auth.oauth2`. See [fhir-architecture.md](fhir-architecture.md).

| Class | Job |
|---|---|
| `OAuth2TokenClient` | `POST` token URL; map JSON; throw `OAuth2TokenException` |
| `CachingAccessTokenProvider` | reuse token until `expires_in` minus 30s skew |
| `BearerAccessTokenInterceptor` | `Authorization: Bearer` on each HAPI request |
| `OAuth2TokenException` | token acquisition failed (distinct from `FhirClientException`) |

`FhirService.readPatient("patient-001")` does not know `token-url`, `client_secret`, or cache.

## Errors

| Situation | Type | Message contains |
|---|---|---|
| Token HTTP 400/401 | `OAuth2TokenException` | `OAuth token acquisition failed` + `invalid_request` / `invalid_client` / … |
| Token endpoint down | `OAuth2TokenException` | `OAuth token endpoint unavailable` |
| Response without `access_token` | `OAuth2TokenException` | `no access_token` |
| FHIR 401 after a token was sent | `FhirClientException` | FHIR/HAPI error (gateway 401 is a FHIR HTTP failure, not a token POST failure) |

Do not treat those as the same exception.

Expired tokens are not a FHIR error: the provider fetches a new one before the interceptor writes the header.

## OAuth 2.0 is not SMART on FHIR

Client Credentials proves **application → system**. SMART adds discovery, Authorization Code, PKCE, scopes, and patient context. See [fhir-smart-on-fhir.md](fhir-smart-on-fhir.md). Do not configure Epic/Cerner/Azure AD here.

## Run locally

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

Token and 401/200 probes (PowerShell: `curl.exe`):

```bash
curl.exe -sS -X POST http://localhost:9090/oauth/token -H "Content-Type: application/x-www-form-urlencoded" --data "grant_type=client_credentials&client_id=lab-client&client_secret=lab-secret"
curl.exe -sS -i http://localhost:8180/fhir/Patient/patient-001
curl.exe -sS -i http://localhost:8180/fhir/Patient/patient-001 -H "Authorization: Bearer invalid-token"
curl.exe -sS -i http://localhost:8180/fhir/Patient/patient-001 -H "Authorization: Bearer lab-access-token"
```

Unit tests: `mvn test`. Integration: `mvn verify -Pintegration` (needs Compose, including `:9090` and `:8180`).
