# Python OIDC Workload Boundary v1

TASK 003 implementation contract under [ADR-096](../adr/ADR-096-identity-provider-agnostic-v1.md), [Principal Context v1](identity-principal-context-v1.md) and [OIDC provider integration v1](oidc-provider-integration-v1.md). Workloads only; no human login/session or clinical authority.

## Activation and HTTP boundary

`GET /iam-lab/v1/workload-context` is registered at application startup only when `OIDC_WORKLOAD_LAB_ENABLED=true`. Default false means no route or OpenAPI operation and no discovery, key or audit initialization. Existing `/internal/*`, cookies, Human Review, HMAC, graph and Java contracts are unchanged. Activation is a deployment action, not a query parameter.

`OIDC_WORKLOAD_TRUST_CONFIG_PATH` names a bounded, operator-owned JSON registration; no default issuer/provider. `OIDC_WORKLOAD_AUDIT_DB_PATH` explicitly names a separate file-backed database, distinct from existing review/session/knowledge/security-audit stores. Enabled but incomplete configuration makes only the new boundary unavailable. Startup never requires contacting the IdP.

Exactly one `Authorization: Bearer <compact-JWT>` is required. Scheme/spaces are exact; duplicates, commas, malformed/oversized JWTs, cookies and any `X-Service-Token` at this boundary deny. No credential fallback. Correlation is a canonical UUIDv4 or a fresh server UUID; it is not identity. Responses have `Cache-Control: no-store`. Authentication rejection is generic 401 with `WWW-Authenticate: Bearer`; authenticated policy denial is generic 403; missing trust, unavailable metadata/keys or mandatory audit gives generic 503. Denied audit persistence failure also yields 503.

The 200 response is a minimized projection: context version, internal principal id/type, organization, authentication method, audience, sorted local permissions, authentication/expiry timestamps and correlation id. It excludes external issuer/subject, JWTs, raw claims and secrets. This route invokes no graph, connector, Java service, model or business write. Audit append is the sole intended persistent side effect, including for denials.

## Trust and Keycloak profile

One immutable explicitly registered provider per boundary in this increment; token fields never select providers/URLs. The verifier/core is independent of business logic. The only initially approved profile is `keycloak-client-credentials-v1`; other profiles require explicit adapters and conformance tests. Configuration includes enabled provider id, exact issuer/discovery/JWKS, endpoint allowlist, `[healthcare-ai-api]` audiences, `[RS256]` algorithms, allowed organizations and registered workload bindings. HTTPS validates certificates; HTTP requires explicit `allow_http_loopback=true` and literal approved localhost/loopback host. No production localhost default, proxy inheritance, redirects, dynamic issuer or token key URLs.

The profile requires verified signed `typ=Bearer`, `iss`, `sub`, `aud`, `exp`, `iat`, `jti`, `azp`; approved JOSE type `JWT` or `at+jwt`. ID tokens, Java audience, excess audiences, missing claims, duplicate JSON keys, unsupported algorithms and incompatible/weak/private keys deny. The configured exact service-account subject **and** client binding classify app-only identity; `azp` or `sub` alone does not. Human subjects cannot inherit a workload binding.

Numeric policy follows TASK 001: metadata/keys timeout at most 2 seconds, response at most 1 MiB, refresh at most 300 seconds, hard TTL at most 900 seconds, unknown-key refresh interval at least 30 seconds, maximum token lifetime 300 seconds, clock tolerance 0–60 seconds. Context expiry never exceeds original `exp`; an actually expired context is never returned despite clock tolerance. `authenticated_at` records validation time, not a new human authentication.

Keys are cached within the immutable provider/issuer registration using monotonic time and a lock. One refresh is coalesced/throttled for unknown kids; misses use the shared bounded refresh window, not unbounded attacker-key storage. Known validated keys may survive transport failure only inside hard TTL. Initial/hard-expired keys fail closed. Successful rotation replaces the key set; removed keys are not retained. Invalid metadata/key material invalidates cached trust. HTTP cache hints cannot extend lifetime.

For explicitly approved HTTP `localhost` only, the transport binds its local address to `127.0.0.1`, avoiding a Windows IPv6 fallback delay. The request URI, Host and issuer are unchanged; HTTPS keeps normal certificate validation. The two-second network deadline begins after local client/TLS-context construction. Compressed metadata is refused and responses remain capped; local construction time is not a relaxed network timeout.

## Binding and PrincipalContext

Trusted config binds exact issuer (provider registration), client id, external subject, internal principal id/type `workload`, active binding/principal, audience, fixed organization, active membership and local permissions. Organization must also be allowed by the provider. Required permission is `iam.workload-context.read`. JWT groups, roles, tenant, organization and scopes cannot add grants. No membership union or automatic provisioning exists.

The immutable internal context implements all [PrincipalContext v1](identity-principal-context-v1.md) fields, method `oauth2_client_credentials`, and original token-bound expiry. Only its minimized projection is returned. It is not forwarded to Java, persisted in checkpoints, logged or used by clinical protocols.

Audit uses the additive [OIDC workload audit v1](oidc-workload-security-audit-v1.md); legacy audit allowlists and migrations remain untouched. This is optional laboratory resource-server foundation, not enterprise IAM/RBAC, clinical identity, SaaS tenancy, corporate IdP onboarding or external cloud authorization.
