# OIDC Provider Integration v1

## Status

Approved architectural design contract for Identity & Access Foundation V1 — TASK 001, following Product Owner review and the audience/profile clarifications below. This is a provider integration and validation design, not a verifier, deployed IdP or claim that Entra ID, Auth0, Okta or corporate Keycloak has been tested. [Principal Context v1](identity-principal-context-v1.md) owns the internal identity and lifecycle; [the architecture](../design/identity-access-foundation-v1.md) owns migration and resource-policy boundaries.

Later implementation: TASK 002 supplies the isolated laboratory provider; [TASK 003](python-oidc-workload-v1.md), approved by the Product Owner for laboratory scope and pending main integration, implements the Python workload-only boundary and its Keycloak profile. Other profiles, Java verification and human/session adoption remain separate future work. The original TASK 001 design below is not evidence that those capabilities exist.

OIDC authenticates humans. OAuth access tokens authenticate API callers under an explicit resource-server profile. OIDC compatibility alone does not guarantee JWT access tokens or app-only token semantics. Each provider onboarding must demonstrate the specific token profiles below without changing clinical or agent logic. Opaque access tokens require a separately approved introspection adapter; silently treating one as a JWT is forbidden.

## Trusted configuration contract

Configuration is provisioned by the deployment operator, validated before activation, and never accepted from login fields, token URLs, documents or API results. Enabling a provider does not enable an endpoint's OIDC policy automatically.

| Setting | Requirement |
|---|---|
| `provider_id` | Unique stable local identifier; alias changes do not change an external identity |
| `enabled` | Explicit boolean, false by default; disabled providers cannot authenticate |
| `issuer` | One exact allowed issuer string, including path and trailing-slash semantics; no wildcard or issuer template acceptance |
| `discovery_url` | Operator-approved exact metadata URL for that issuer |
| `expected_jwks_uri` | Exact, preapproved public-key URL; discovery must agree before keys are accepted |
| `endpoint_allowlist` | Exact allowed authorization, token and JWKS endpoints; another host/CDN needs explicit approval |
| `allowed_organization_ids` | Nonempty list of existing application organizations this provider may serve; membership is separately required |
| `human_clients` | Enabled client ids with exact redirect URI allowlists, code/PKCE policy and server-side secret references if confidential |
| `resource_servers` | Separate API definitions for `healthcare-ai-api` and `healthcare-interop-api`; each declares accepted audience(s), access-token profile and allowed caller client bindings |
| `id_token_algorithms`, `access_token_algorithms` | Separate nonempty asymmetric allowlists; initial lab policy `RS256`; adding `ES256` requires explicit compatibility tests |
| `access_token_profile` | Explicit reviewed profile defining token purpose, required signed claims, client identity and human/workload classification; no generic accept-any-JWT mode |
| `clock_skew_seconds` | Explicit bounded tolerance, at most 60 seconds in the proposed lab policy |
| `max_access_token_lifetime_seconds` | Explicit bound, proposed 300 seconds for the lab; longer customer policy requires review |
| `jwks_refresh_seconds`, `jwks_hard_ttl_seconds` | Bounded cache policy, proposed 300 and 900 seconds; HTTP cache hints cannot extend the hard limit |
| `unknown_kid_refresh_min_interval_seconds` | Proposed minimum 30 seconds per provider, with request coalescing and a negative cache |
| `http_timeout_seconds`, `metadata_max_bytes` | Proposed 2-second timeout and 1 MiB response cap for discovery/JWKS |
| `credential_refs` | Secret-manager/environment references only; no literal administrative, client or signing secrets |

These numeric bounds are proposed application laboratory policy, not OIDC defaults. Production operator policy, ownership and deployment review remain necessary. No new environment variable or configuration loader implements these names in TASK 001.

Synthetic shape, deliberately disabled and using reserved example domains:

```yaml
contract_version: oidc-provider-integration-v1
provider_id: corporate-example
enabled: false
issuer: https://identity.example.invalid/tenant-a/v2.0
discovery_url: https://identity.example.invalid/tenant-a/v2.0/.well-known/openid-configuration
expected_jwks_uri: https://identity.example.invalid/tenant-a/keys
allowed_organization_ids: [org-lab-a, org-lab-b]
id_token_algorithms: [RS256]
access_token_algorithms: [RS256]
resource_servers:
  healthcare-ai-api:
    accepted_audiences: [healthcare-ai-api]
    access_token_profile: explicitly-reviewed-provider-profile
  healthcare-interop-api:
    accepted_audiences: [healthcare-interop-api]
    access_token_profile: explicitly-reviewed-provider-profile
```

This excerpt is not runnable configuration; the other required settings and membership/client bindings must be supplied by a future implementation.

## Token-purpose rules

| Boundary | Acceptable evidence | Must reject |
|---|---|---|
| Human browser callback | Code redeemed by the registered application; validated ID token plus state, nonce and PKCE transaction | API access token as login proof; wrong client, redirect, transaction, issuer or nonce |
| Human browser request after login | Live application-owned opaque session tied to the verified internal human binding | ID/access tokens in form fields; service credential as human session |
| API request | Access token with the receiving API's audience and the configured access-token profile | ID token, refresh token, token for another API, malformed/duplicate Authorization headers |
| Workload API request | API access token plus an enabled server-side binding of issuer, client identity, principal type and organization | Assuming any valid `sub`, scope or provider role proves app-only identity |

An ID token's audience is the interactive client's id; an API access token's audience must match that API. Keep those identifiers separate. RFC 9068 tokens require the corresponding access-token media type (`at+jwt` or `application/at+jwt`). Other vendors' JWT access tokens need a named, tested token-purpose profile; a JOSE `typ=JWT` alone is insufficient. Entra-specific signed client/tenant claims and Keycloak-specific token fields are interpreted only inside that profile, never in the clinical domain.

TASK 002 must configure the effective Keycloak audiences through explicit audience mappers/client scopes and issuance policy, then inspect and validate the actual issued tokens in its fixture harness. Creating two clients alone does not establish audience separation. Each workload must obtain a token for its intended resource without an unintended second product API audience. Any default scopes/mappers that broaden those audiences must be constrained and verified.

The selected Keycloak version is not required to emit an RFC 9068-compatible access token. If it does not, define and test a Keycloak-specific access-token profile, including its signed token-purpose evidence, permitted client identity, signature algorithms and API audience rules. Do not pretend a generic JWT is RFC 9068-compliant or weaken signature, purpose or audience checks to accommodate the fixture.

For human clients use Authorization Code with PKCE `S256`, exact registered redirects, single-use expiring `state`, nonce and code verifier bound to the initiating browser transaction and expected issuer. Validate callback state and issuer binding before redeeming the code at the configured token endpoint. Validate the returned ID token cryptographically, its client audience, authorized-party rules where applicable, nonce and temporal claims. A code or token is never put in application logs. Local session creation and rotation happen only after internal binding and required audit succeed.

After login, the local human session follows its own future expiry, reauthentication and revocation contract; it is not necessarily capped by the initial ID token's expiry. Reusing a valid session does not establish fresh authentication. Workload and other API bearer request contexts remain bounded by the validated access token and stricter local policy. [Principal Context lifecycle](identity-principal-context-v1.md#transport-lifetime-and-minimization) defines these separate rules.

For workloads use Client Credentials only for registered technical clients where appropriate. It is OAuth application identity, not OIDC human authentication. Human delegation is a separate future flow. Resource Owner Password Credentials and implicit grants are outside this design. Administrative bootstrap credentials must never authenticate agents or product APIs.

## Validation order and fail-closed behavior

1. Resolve the permitted provider set from the route and trusted deployment policy. Treat an unverified issuer only as a lookup hint into that finite set; it cannot introduce a provider or URL. Bound token/header sizes and reject ambiguous credentials.
2. Require enabled, coherent configuration. Fetch metadata only from the configured URL. Compare metadata issuer exactly and require approved endpoints/JWKS. Reject TLS failures, redirects outside policy, unexpected hosts, oversized documents and inconsistent issuer/key metadata. Never discover from an email domain, request URL, JOSE `jku`/`x5u` or arbitrary `iss`.
3. Parse under bounded limits, reject duplicate/conflicting security claims and unsupported critical JOSE headers. Select a compatible verification key only from that provider's JWKS cache. Require signature verification with an allowed asymmetric algorithm, compatible key type and strength; reject `none`, unexpected symmetric algorithms, unusable encryption and token-supplied embedded trust keys.
4. Validate exact issuer, nonempty subject, API/client audience as appropriate, token purpose, authorized client binding and required temporal claims. Require `exp` and `iat`; enforce `nbf` when present, bounded skew, no future issuance beyond skew and maximum accepted lifetime. Do not infer human authentication time from a workload `iat`. Require `auth_time`/fresh authentication when a future step-up policy needs it.
5. Resolve the existing internal binding, registered principal type, enabled membership and one active organization. Compute effective permissions locally, then perform resource authorization. No external role, group, tenant or tool result independently grants a resource permission.

A resource token with invalid credentials yields a generic authentication rejection; an authenticated but ungranted operation is forbidden. Missing trusted configuration, required metadata/keys/policy or mandatory audit is unavailable and executes no protected work. Detailed reason codes are server-controlled and minimized; raw tokens, external subjects and discovered response bodies are excluded from ordinary logs. Existing endpoints retain their current response and audit contracts until migrated explicitly.

## Discovery, keys, rotation and outages

HTTPS and certificate validation are mandatory outside an explicit laboratory loopback exception. TASK 002 may use HTTP only to its own local Keycloak on an approved loopback host and port; this is a deployment-specific exception, not a token-selected switch. Never disable TLS globally or permit arbitrary private/metadata-service URLs through discovery. Container and browser views must share one exact issuer; do not rewrite issuer strings to compensate for networking differences.

Cache metadata and keys per provider/issuer and key identifier, never globally by `kid`. Validate key `use`, compatible algorithm and verification key operations where supplied, and minimum RSA strength of 2048 bits for the proposed RS256 profile. No private keys belong in JWKS responses consumed by the application.

- Known keys may be used only while the validated cache remains within its hard lifetime and the token passes every check. A network failure does not turn signature verification off.
- An unknown `kid` permits at most one coalesced refresh subject to the per-provider throttle. If still unknown, reject. Rate-limit misses; do not fetch once per attacker-controlled id or try unrelated issuers/algorithms.
- Validated rotation updates replace the active set; a removed key is no longer trusted after that update. Retaining overlapping old keys is the provider's responsibility, not an indefinite application fallback.
- At hard expiry or initial discovery/key failure, authentication needing those keys fails closed. Do not fall back to a static shared token or switch providers because a verifier is unavailable.
- Emergency provider disablement and key invalidation require an operator-controlled action. JWT expiry and cached verification imply a bounded revocation window; immediate global logout/revocation is not delivered by JWT validation alone.

## Multiple organizations and provider portability

One issuer can serve multiple application organizations. Use one trusted provider registration with explicit allowed organizations, distinct memberships and client bindings; a separate Keycloak realm per customer is optional, not a requirement. A tenant id in a valid token may constrain an approved binding, but cannot select arbitrary application tenants. The same Microsoft tenant may correspond to several product organizations, and those relationships remain server-managed.

For Entra onboarding register each concrete permitted issuer/tenant. Do not accept `/common`, `/organizations`, arbitrary Microsoft tenants or issuer templates as automatic trust. Auth0, Okta and corporate Keycloak onboarding likewise requires exact metadata, audience, signature/profile and membership tests. Replacing the provider must not alter LangGraph protocols, Java source grants or business rules. Unavailable provider features cause onboarding failure or an explicit adapter proposal, not weaker validation.

## Required future conformance evidence

Both language implementations must run the same synthetic token vectors for unknown/wrong issuer, wrong audience, wrong token kind, tampered signature, expired/future token, missing claims, unsupported algorithm, unknown `kid`, rotation and hard-expired cache. Include discovery SSRF, redirect, timeout and issuer/JWKS mismatch tests; shared-issuer multi-organization denial; client-credentials principal classification; and unavailable mandatory audit with zero protected side effects.

TASK 002's harness must independently demonstrate at least these fixture checks:

| Fixture input/check | Required result |
|---|---|
| AI API access token under the configured AI profile | Accepted by the fixture's validation harness |
| AI API access token under the Interoperability API profile | Rejected for the wrong resource audience |
| Interoperability API access token under the AI API profile | Rejected for the wrong resource audience |
| Interoperability API access token under its own profile | Accepted by the fixture's validation harness |
| Human ID token presented as an API access token | Rejected by the access-token profile |
| Unregistered workload, even with a valid provider signature | Rejected by the fixture's explicit client/principal binding |
| Discovery issuer and configured JWKS | Exact issuer/URI consistency and cryptographic verification with the approved public key; wrong issuer or unapproved key source rejected |

These checks are exclusive to the test-owned provider fixture and its harness. They do not exercise or validate product OIDC verifiers, which do not exist yet, and must not send those tokens to current product endpoints. Product conformance tests are a later authorized adoption step.

Successful OIDC login must not create an anonymous bypass, reinterpret a synthetic session or automatically authorize Clinical Read/Federation. See the endpoint migration matrix in [the design](../design/identity-access-foundation-v1.md).

## Primary references

- [OIDC Core 1.0](https://openid.net/specs/openid-connect-core-1_0.html): ID tokens, issuer-scoped subject identity and callback validation.
- [OIDC Discovery 1.0](https://openid.net/specs/openid-connect-discovery-1_0.html): metadata, issuer consistency and key discovery.
- [RFC 8725](https://www.rfc-editor.org/rfc/rfc8725.html): algorithm/key validation and token substitution defenses.
- [RFC 9068](https://www.rfc-editor.org/rfc/rfc9068.html): a specific JWT access-token profile, not an assumption about every OIDC provider.
- [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html): OAuth security practices, PKCE and grant restrictions.
