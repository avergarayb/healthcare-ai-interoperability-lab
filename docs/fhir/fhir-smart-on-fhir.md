# SMART on FHIR

This note adds a **synthetic SMART on FHIR** Authorization Code + PKCE flow to the Java FHIR client. Read it after [fhir-oauth2-authentication.md](fhir-oauth2-authentication.md). It is **not** Epic, Oracle Health, OpenID Connect, or a login UI.

There is still no `@RestController`, no real user identity, and no commercial EHR. Task 028 prepares discovery, capabilities, and authorization-request types for a later real provider; it does **not** certify Epic or Oracle Health. Vendor placeholders: [vendors/epic.md](vendors/epic.md), [vendors/oracle-health.md](vendors/oracle-health.md).

## OAuth 2.0 vs SMART

| | Task 016 | Task 017 |
|---|---|---|
| Profile | `secured-lab` | `smart-lab` |
| Grant | Client Credentials | Authorization Code + PKCE S256 |
| Who | application → system | application → user/context → FHIR |
| Token extras | `access_token`, `expires_in` | + `refresh_token`, `scope`, `patient` |
| Question answered | “is this client allowed?” | “which patient, and which resource types?” |

```text
OAuth 2.0
    =
authorization framework

SMART on FHIR
    =
OAuth 2.0 profile
  + FHIR-oriented scopes
  + launch / patient context
  + /.well-known/smart-configuration
```

SMART does not replace FHIR. It does not replace OAuth. It standardizes how a FHIR **app** obtains a token that a FHIR **server** can understand.

```text
patient  → this patient's compartment
user     → whatever the logged-in clinician may see
system   → backend, no end-user (Task 016)
```

`patient/Patient.read` does **not** grant `patient/Observation.read`. That is authorization, not authentication.

## Discovery (HTTP first)

SMART apps must not invent authorize/token URLs. They read:

```http
GET http://localhost:8180/fhir/.well-known/smart-configuration
```

The FHIR gateway proxies that path to the synthetic Authorization Server. Observed:

```json
{
  "authorization_endpoint": "http://localhost:9090/authorize",
  "token_endpoint": "http://localhost:9090/oauth/token",
  "grant_types_supported": ["authorization_code", "refresh_token", "client_credentials"],
  "response_types_supported": ["code"],
  "code_challenge_methods_supported": ["S256"],
  "scopes_supported": [
    "patient/Patient.read",
    "patient/Observation.read",
    "patient/Condition.read",
    "user/Patient.read",
    "system/Patient.read"
  ],
  "capabilities": [
    "launch-standalone",
    "client-public",
    "permission-patient",
    "context-standalone-patient"
  ]
}
```

`local-hapi` on `:8080` still has no SMART discovery. HAPI itself does not implement this file.

## Authorization Code + PKCE

Public SMART apps (no confidential `client_secret` in the app) use PKCE **S256**:

```text
code_verifier  → random
code_challenge → BASE64URL(SHA256(verifier))
state          → random, round-tripped, must match
aud            → FHIR base URL (http://localhost:8180/fhir)
```

```http
GET http://localhost:9090/authorize
  ?response_type=code
  &client_id=lab-smart-app
  &redirect_uri=http://127.0.0.1:8081/smart/callback
  &scope=patient/Patient.read%20patient/Observation.read
  &state=...
  &aud=http://localhost:8180/fhir
  &code_challenge=...
  &code_challenge_method=S256
```

This lab **auto-approves** (no browser, no login). Observed: HTTP **302** to `redirect_uri?code=...&state=...`. A mismatched `state` is rejected in Java (`OAuth2TokenException`) **before** the code is exchanged. A wrong `aud` is rejected by the Authorization Server (`400 invalid_request`). Authorization codes are single-use.

Token exchange:

```http
POST http://localhost:9090/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=...
&redirect_uri=http://127.0.0.1:8081/smart/callback
&client_id=lab-smart-app
&code_verifier=...
```

Observed:

```json
{
  "access_token": "smart-...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "refresh-...",
  "scope": "patient/Patient.read patient/Observation.read",
  "patient": "patient-001"
}
```

`patient` is SMART **context**, not a FHIR search parameter. The access token is still a Bearer credential.

## Refresh

```http
POST /oauth/token
grant_type=refresh_token
&refresh_token=...
&client_id=lab-smart-app
```

The lab **rotates** refresh tokens and issues a new access token. `SmartTokenProvider` reuses the cached access token until `expires_in` minus 30 seconds, then refreshes. It does not repeat `/authorize`.

## Gateway: authentication vs authorization

nginx `auth_request` asks the Authorization Server about each FHIR call.

| Request | Result (observed) |
|---|---|
| No `Authorization` | `401` `invalid_token` |
| Unknown Bearer | `401` |
| `patient/Patient.read` then `GET /fhir/Observation?patient=patient-001` | `403` `insufficient_scope` |
| `patient/Patient.read patient/Observation.read` then that Observation search | `200` |
| Task 016 `Bearer lab-access-token` | still `200` on Patient (system-style) |
| Unsecured `:8080` | still `200` without a token |

`.read` scopes allow **GET** only. Patient context `patient-001` rejects another Patient id.

## Java

SMART types live in `lab.healthcare.fhir.smart`. Generic tokens and the Bearer interceptor live in `lab.healthcare.fhir.auth`. See [fhir-architecture.md](fhir-architecture.md).

```text
FhirService
     │
     ▼
IGenericClient
     │
     ▼
BearerAccessTokenInterceptor
     │
     ▼
AccessTokenProvider
     ├── CachingAccessTokenProvider   (Client Credentials)
     └── SmartTokenProvider           (discovery → authorize → PKCE → refresh)
```

`FhirService` still only sees `IGenericClient`.

| Class | Job |
|---|---|
| `SmartConfigurationClient` | `GET` well-known JSON |
| `SmartConfiguration` | discovered endpoints plus optional issuer/scopes/grants/PKCE methods |
| `SmartCapabilities` | interpretation of that metadata (declared vs absent) |
| `SmartConfigurationValidator` | can this metadata run Authorization Code + PKCE S256? |
| `SmartAuthorizationRequest` | one session: `aud` from the profile, scopes, state, S256 challenge |
| `Pkce` | verifier, S256 challenge, `state` |
| `AuthorizationCodeClient` | authorize URL, state check, code exchange, refresh |
| `SmartTokenProvider` | cache + refresh for the SMART profile |

Profile `smart-lab` is **disabled** by default. It is a public client: no `client-secret` in YAML.

```yaml
smart-lab:
  base-url: http://localhost:8180/fhir
  authentication:
    type: SMART_AUTHORIZATION_CODE
    smart-configuration-url: http://localhost:8180/fhir/.well-known/smart-configuration
    client-id: lab-smart-app
    redirect-uri: http://127.0.0.1:8081/smart/callback
    scope: patient/Patient.read patient/Observation.read
    aud: http://localhost:8180/fhir
```

The callback path is **not** a Spring controller. Integration tests (and `SmartTokenProvider` in this lab) follow the `302` and read `code` + `state`.

## Lab limits

No EHR launch (`iss`/`launch`), no OIDC `id_token`, no real consent, no TLS, no Epic/Cerner scopes catalog. Tokens are opaque strings invented by `lab-oauth`.

## Run

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build
```

```bash
curl.exe -sS http://localhost:8180/fhir/.well-known/smart-configuration
```

Unit tests: `mvn test`. Integration: `mvn verify -Pintegration` (needs Compose on `:8080`, `:8180`, `:9090`).
