# Real-world SMART on FHIR readiness

This note prepares the SMART layer for a later real Authorization Server. Read it after [fhir-smart-on-fhir.md](fhir-smart-on-fhir.md). It does **not** connect Epic, Oracle Health, or any external sandbox.

Task 028 prepares the platform for real SMART providers, but it does **not** certify compatibility with Epic or Oracle Health.

There is still no `@RestController`, no Dynamic Client Registration, and no new OAuth grant.

## Three kinds of SMART information

| Kind | Source | Lifetime | Examples |
|---|---|---|---|
| Local profile config | `fhir.servers.<name>` YAML | months | FHIR `base-url`, `client-id`, `redirect-uri`, `scope`, `aud`, `smart-configuration-url` |
| Discovered metadata | `GET /.well-known/smart-configuration` | until the provider republishes it | `authorization_endpoint`, `token_endpoint`, optional `issuer`, `scopes_supported`, `grant_types_supported` |
| Session authorization | one authorize attempt | seconds | `state`, PKCE challenge, the concrete `aud` on that request |

```text
FhirServerProfile
        ↓
FhirAuthenticationSettings          (local config)
        ↓
SmartDiscoveryUrl.from(settings)    (explicit profile URL — no vendor host concat)
        ↓
SmartConfigurationClient            (HTTP discovery)
        ↓
SmartConfiguration                  (published metadata)
        ↓
SmartCapabilities                   (interpretation)
        ↓
SmartConfigurationValidator         (can we run Authorization Code + PKCE S256?)
        ↓
SmartAuthorizationRequest           (this session)
        ↓
AuthorizationCodeClient
        ↓
SmartTokenProvider
        ↓
BearerAccessTokenInterceptor
        ↓
FHIR Server
```

`FhirService` still does not import `smart`. `RoutingService` still selects a destination. Resilience still wraps the FHIR READ, not OAuth.

## Discovery URL

The discovery URL is **configured** on the SMART profile (`authentication.smart-configuration-url`). `SmartDiscoveryUrl.from(settings)` returns that value. Java does not append `/.well-known/smart-configuration` to Epic or Oracle hosts.

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

A later real profile would replace those values. The SMART types stay the same. Disabled destinations `epic-sandbox` and `oracle-health-sandbox` reuse these types without calling a vendor; see [vendors/epic.md](vendors/epic.md) and [vendors/oracle-health.md](vendors/oracle-health.md).

## Optional metadata vs incompatibility

`SmartConfiguration` stores optional fields when present and leaves them empty when absent. It does not invent clinical scopes or grant types.

| Metadata | If absent | If present and incompatible |
|---|---|---|
| `authorization_endpoint` | `SmartCompatibilityException` | — |
| `token_endpoint` | `SmartCompatibilityException` | — |
| `grant_types_supported` | accept (undeclared) | reject when the list exists and omits `authorization_code` |
| `code_challenge_methods_supported` | accept (undeclared) | reject when the list exists and omits `S256` |
| `scopes_supported` | accept (undeclared) | informational; requested scopes still come from the profile |
| `issuer` | accept (undeclared) | stored only; not used as `aud` |

`SmartCompatibilityException` is not `OAuth2TokenException`. Discovery HTTP failures stay token/discovery exceptions. Declared-incompatible metadata is a compatibility failure. Messages omit tokens, secrets, codes, and the PKCE verifier.

## `aud`

`aud` is the FHIR API audience (`http://localhost:8180/fhir` in this lab). It is not the issuer, not the authorize URL, and not the token URL.

It is copied from the profile onto `SmartAuthorizationRequest`. `SmartTokenProvider` does not build it by string manipulation.

## Requested vs advertised scopes

| | Meaning |
|---|---|
| Requested | `authentication.scope` on the profile — what this app asks for |
| Advertised | `scopes_supported` on discovery — what the server publishes, if it publishes anything |

Missing `scopes_supported` is not a reject. Requested capability is not the same as advertised capability.

## PKCE S256

The lab flow always sends `code_challenge_method=S256`. The verifier stays on `AuthorizationSession`. `SmartAuthorizationRequest` holds only the challenge.

If discovery lists challenge methods and `S256` is missing, validation fails. If the field is absent, validation does not assume incompatibility.

## What did not change

OAuth Client Credentials, the synthetic SMART lab, `FhirService`, routing, mapping, audit, metrics, retry, circuit breaker, rate limiting, and bulkhead keep their previous jobs. SMART remains authentication of the HAPI client, not part of the FHIR resilience pipeline.
