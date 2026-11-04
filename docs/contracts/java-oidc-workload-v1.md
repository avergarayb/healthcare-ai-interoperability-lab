# Java OIDC Workload Boundary v1

Identity & Access Foundation V1 — TASK 005 laboratory contract under [ADR-096](../adr/ADR-096-identity-provider-agnostic-v1.md), [Principal Context](identity-principal-context-v1.md) and [provider integration](oidc-provider-integration-v1.md). The Product Owner approved the implementation, the final-review NumericDate correction and its revalidation, and authorized commit/push of the 24 TASK 005 paths after final integrity checks. PR, merge and TASK 006 remain unauthorized. This does not migrate any clinical or legacy endpoint.

## Activation and isolation

`GET /iam-lab/v1/workload-context` exists only when `iam.java.workload.lab.enabled=true` (environment `IAM_JAVA_WORKLOAD_LAB_ENABLED`). Default absent/false means no controller mapping, IAM filter, trust/key client or IAM audit initialization. There is no OpenAPI generator in this service; the actual MVC mapping is absent. Ordinary startup requires no IdP. No human session, Python call, FHIR/clinical read, Federation, exchange, Mini HIS/LIS, LLM or business write is executed by this route.

`IAM_JAVA_WORKLOAD_TRUST_CONFIG_PATH` names an explicit operator-owned JSON registration. `IAM_JAVA_WORKLOAD_AUDIT_DB_PATH` names a separate absolute file-backed SQLite audit. No default trusted provider or audit path is supplied. Missing/invalid registration makes only this boundary unavailable, not a permissive fallback. Provider enablement and route enablement are independent.

The new Spring `SecurityFilterChain` is a `DefaultSecurityFilterChain` with an exact GET/path matcher. A `FilterChainProxy` is registered by a Servlet `FilterRegistrationBean` only at this path, at `HIGHEST_PRECEDENCE + 10`. Existing Model Boundary, Clinical Read/catalogue, Federation and Exchange filters stay at `HIGHEST_PRECEDENCE` on their own URL patterns. There is no global `springSecurityFilterChain`, `@EnableWebSecurity`, HTTP Basic/form login or `anyRequest().permitAll`. Direct Resource Server/JOSE modules are used without the global starter/config module. Adding `spring-security-config` later is a material isolation change requiring new regression/design review.

## HTTP credential policy

One exact `Authorization: Bearer <compact-JWT>`, application JWT cap 16,384 characters. Duplicate values, comma-combined headers, malformed/padded/lowercase scheme and any accompanying `X-Service-Token` or `Cookie` deny; neither is fallback authentication. Servlet/container HTTP limits may reject oversized/invalid HTTP earlier, before this filter can audit it. Unsupported methods are not authenticated GET operations and cannot obtain context; normal MVC method handling or missing request context rejects them.

HEAD is intentionally unsupported in this increment: Spring MVC maps it implicitly, but the GET-only IAM matcher supplies no request context and the controller guard returns 401 with an empty HTTP body, even with a valid token. It does not validate that credential or create a GET access-decision event. POST/PUT/PATCH/DELETE return 405; OPTIONS returns only public protocol metadata (200, no body/context). This does not assert authentication/audit coverage for unsupported methods. Only canonical authenticated GET can return PrincipalContext. The real-container regression verifies these outcomes and the single REQUEST filter registration; no ASYNC/FORWARD/ERROR capability is implied.

Canonical single UUIDv4 correlation is preserved; malformed/duplicate correlation gets a new server UUID. Correlation carries no identity. Responses have `Cache-Control: no-store`; 401 also has `WWW-Authenticate: Bearer`. Errors are only `unauthorized`, `forbidden` or `unavailable`, never JWT/SQLite/transport details. Every normal decision reaching the IAM GET filter requires the [separate mandatory audit](java-oidc-security-audit-v1.md) before response.

| Decision | HTTP |
|---|---|
| Valid configured token, active binding/principal/membership and Java route grant | 200 |
| Invalid/missing/conflicting credential, wrong audience/purpose/issuer, unregistered/disabled workload binding/principal | 401 |
| Authenticated workload without active permitted organization or local permission | 403 |
| Incomplete/disabled trust, unavailable required keys/provider or mandatory audit | 503; no context |

## Trust registration

[Secret-free disabled example](../../services/fhir-integration-service/java-oidc-workload.example.json). Strict immutable `java-oidc-workload-v1` record, unknown/missing/duplicate JSON fields and scalar coercion rejected; file cap 64 KiB.

Required configuration: provider id/enabled, exact issuer, approved discovery and expected JWKS URI, finite exact endpoint allowlist, audience `healthcare-interop-api`, algorithm `RS256`, profile `keycloak-client-credentials-v1`, explicit HTTP-loopback exception, allowed organization ids and static workload bindings. No token/header/parameter can select a provider, URL, key source or mode.

HTTPS retains JVM certificate/host validation. HTTP requires `allow_http_loopback=true` and literal `localhost`, `127.0.0.1` or `::1`; no global TLS switch. Literal IP trust is deliberately narrower than Python: non-loopback literal IP endpoints are refused. Approved DNS endpoints remain operator responsibility, not a production DNS/network-isolation guarantee. URLs cannot contain credentials, query, fragment or control characters. No inherited proxy or redirects. Only configured discovery/JWKS are fetched; metadata issuer/JWKS must agree exactly and advertised authorization/token endpoints must belong to the allowlist.

Limits: skew 0–60 seconds, token lifetime 1–300 seconds, key refresh 30–300 seconds, hard TTL at least refresh and at most 900 seconds, unknown-kid refresh interval 30–300 seconds, network deadline/connect timeout at most 2,000 ms per fetch, response cap 1 KiB–1 MiB, maximum 32 keys. Limits cannot be relaxed by HTTP cache hints or token claims.

## JWT profile and keys

Spring `NimbusJwtDecoder` and `JwtAuthenticationProvider` perform recognized JWT/signature authentication, with explicit `OAuth2TokenValidator` policy. Nimbus owns signature verification and RSA public-key conversion. There is no manual signature implementation or arbitrary token introspection. The authentication converter creates no authorities from scopes/roles/groups.

Require signed RS256, approved JOSE `typ=JWT` or `at+jwt`, bounded known `kid`, compatible public RSA signing key (2,048–8,192 bits), exact issuer and exactly one Java API audience. Validate required integral `iat`/`exp`, optional integral `nbf`, skew and maximum lifetime. Actual expiry always denies despite skew. Duplicate JSON claims/headers, unsigned/HS tokens, token `jku/x5u/jwk/x5c/crit`, private JWKS parameters, duplicate kids, unusable key ops and malformed keys deny. No fallback to a key for another provider/algorithm.

Temporal admission also checks the original nonnegative integer NumericDates before Nimbus converts seconds to millisecond-based Date values: actual expiry, future iat/nbf, positive ordered lifetime and maximum lifetime. This prevents overflow wrapping a correctly signed out-of-range claim into a plausible current date. These unverified envelope checks can only reject; accepted credentials still require Nimbus signature verification and the signed Spring/profile validators. No claim is rewritten and no cryptography is implemented locally.

The named Keycloak profile requires signed payload `typ=Bearer`, nonempty bounded `sub`, `azp` and `jti`, plus exact registered service-account subject **and** authorized client. The reference client is `lab-python-to-java`, subject `00000000-0000-4000-8000-000000000202`. This is not a claim that Keycloak emits RFC 9068. An ID token, human subject, AI-audience token or merely signed realm token cannot become a registered Java workload.

The provider-scoped cache is synchronized and uses monotonic time. One coalesced refresh attempt is shared across misses, including failed attempts; there is no unbounded per-attacker-kid map. Known validated keys survive transport failure only within hard TTL. Initial/hard-expired trust fails closed. Invalid discovery/key material invalidates cached trust. Successful rotation replaces the set; removed keys are not retained. HTTP uses asynchronous bounded body consumption and a whole-fetch deadline, without unbounded buffering or redirects. Local HttpClient construction is outside the network deadline and does not contact the provider.

## Local identity, organization and permission

One immutable Java registration per process. Each binding supplies exact client/subject under the configured issuer, stable internal workload id/type, enabled binding/principal, fixed organization, enabled membership, own audience and local permissions. Client and subject bindings are unique, bounded and explicit; there is no automatic provisioning or import from Keycloak.

Required Java-only permission: `iam.java-workload-context.read`. Python's `iam.workload-context.read` grants nothing here. Effective permissions are computed locally and limited to this route; signed `roles`, `groups`, `scope`, `tenant`, organization and email cannot add authority.

Initial scope is one fixed organization per credential binding; no automatic permission union or first-membership selection. Optional single bounded `X-IAM-Lab-Organization` is only a candidate and must equal the trusted fixed membership. Duplicate, comma-combined, padded or different candidates deny. General multi-organization selection is future work, not inherited from Python's registry. These caller organizations do not change Java clinical-source grants/patient links or Federation participant identity.

The full immutable internal `JavaPrincipalContext` implements context version, principal id/type, verified organization, method `oauth2_client_credentials`, provider/verified issuer/subject, audience, locally effective permissions, authentication/expiry instants and correlation. Only a minimized projection is returned; issuer, subject and provider id are omitted. Full context and raw credentials are never stored, logged, sent to Python, clinical stores or checkpoints. Context expiry is bounded by token expiry and checked again after mandatory audit and before projection. An already committed allowed audit row describes the decision, not guaranteed delivery if the token expires before response.

Static binding/principal/permission/provider changes require controlled restart. No TASK 004 SQLite registry, shared Python database, distributed revocation or global identity service is introduced. See [architecture, tests and evidence](../design/java-oidc-resource-server-v1.md).
