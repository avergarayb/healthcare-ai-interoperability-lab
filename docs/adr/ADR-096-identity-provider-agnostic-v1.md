# ADR-096 — Provider-agnostic identity and access foundation

## Status

Accepted as the architectural direction for Identity & Access Foundation V1 — TASK 001 by the Product Owner, including the final session-lifecycle and token-audience clarifications. Documentation only; not evidence of deployed OIDC, enterprise IAM, SaaS multi-tenancy or clinical identity verification. TASK 002 runtime remains subject to separate authorization.

## Context

Security & Governance V1 is technically closed for its laboratory scope after TASK 007. It delivered bounded service authentication, development sessions/attribution and durable security decisions. Existing Clinical Read/Federation contracts, synthetic Human Review and deterministic workflows remain operational authorities. Real legacy HAPI compatibility remains separately pending.

Customers may use Entra ID, Auth0, Okta, corporate Keycloak or another compatible provider. Neither product unit nor agent protocols should depend on a customer's specific IdP layout. Laboratory Keycloak must remain optional for customer deployments. A login must not grant arbitrary access to organization data, source systems, tools or external cloud resources.

## Decision

1. Authenticate at each product unit's boundary using explicitly configured trust, then resolve a provider-independent [Principal Context v1](../contracts/identity-principal-context-v1.md). Do not add an identity microservice or user database in TASK 001.
2. Bind exact external `(issuer, subject)` identities to stable internal ids. Keep principal type, organization membership and local resource permissions under trusted application control. Do not link by email, accept unverified tenant claims or union permissions across organizations.
3. Adopt the [OIDC provider design contract](../contracts/oidc-provider-integration-v1.md): exact issuer/API audience, signature and token-purpose validation, approved discovery/JWKS, bounded rotation/cache policy and fail-closed behavior. Unknown providers/tenants never self-register. TASK 002 must configure and test effective Keycloak audiences, not infer them from two client registrations; a secure provider-specific profile is valid when RFC 9068 emission is unavailable.
4. Use code/PKCE for human authentication and appropriate OAuth Client Credentials for technical actors. Keep human session cookies, API access tokens, ID tokens and external connector credentials distinct. A local human session follows its own expiry, reauthentication and revocation contract rather than necessarily expiring with the initial ID token. Reusing it preserves authentication evidence; sensitive operations can demand reauthentication. Workload request contexts cannot outlive their access token or a stricter local limit. Provider-specific token adapters remain outside clinical and workflow logic.
5. Support SaaS and dedicated deployment through the same modules/configuration. A shared issuer/realm can serve several application organizations, but actual SaaS resource isolation requires separate future storage/query/policy work; this ADR does not implement it.
6. Preserve current endpoint authentication modes and contracts until each migration is authorized with tests. No OIDC-to-legacy fallback or simultaneous credential interpretation without an explicit policy. Session/attribution/audit allowlists need additive versioned changes before OIDC actors can use them.
7. Propose a separately owned, opt-in local Keycloak fixture in TASK 002, with an exact image version/digest, configurable loopback port and synthetic realm/clients. Do not start it in TASK 001. Clients need not install Keycloak to use their corporate provider.
8. Leave new enterprise credential delegation and cloud-resource authorization to Enterprise Connector Authorization, and per-tool control/execution to MCP Integration Foundation. Existing Java FHIR OAuth/SMART remains outbound integration, not Human Review login.

The full source inventory, trust diagram, authentication flows, threat matrix and TASK 002 acceptance are maintained once in [the design](../design/identity-access-foundation-v1.md), not duplicated here.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Keycloak-specific roles/realm ids inside every agent | Couples business rules to provider layout and prevents portable customer deployment |
| Trust JWT roles/tenant/sub directly as local authorization | Confuses authentication, identity namespace, membership and resource permissions |
| One generic credential accepted by browser, tools and APIs | Loses actor attribution, audience separation and purpose constraints |
| A new central identity service now | Adds runtime/persistence scope before identity and migration contracts are approved |
| Replace all shared-token and development-session paths at once | Disrupts working laboratory contracts and hides migration/regression risk |

## Consequences

Java and Python retain independent deployment and ingress policies while sharing contract semantics and test vectors. Clinical eligibility, Review outcomes, source grants and LangGraph behavior remain deterministic and provider-independent. Applications still need explicit binding/membership administration, resource authorization and deployment controls; OIDC alone supplies none of those.

There is no production multi-tenancy, RBAC implementation, session migration, cloud connector, token exchange or MCP runtime in this task. Existing migrations, HAPI infrastructure and external clinical services remain untouched. Product Owner acceptance of this ADR approves the design direction, not every later runtime/deployment step. TASK 002's tests will validate only its dedicated fixture/harness, not product OIDC verifiers.

## References

- [ADR-093: development session](ADR-093-human-review-session.md)
- [ADR-094: development attribution](ADR-094-human-attribution.md)
- [ADR-095: product and clinical normalization boundary](ADR-095-clinical-normalization-boundary.md)
- [Security & Governance closure](../ai-governance/security-governance-v1-closure.md)
- [Service hardening](../ai-governance/service-security-hardening-v1.md)
