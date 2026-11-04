# ADR-097 — Enterprise connector authorization boundaries

## Status

**Accepted — architectural direction only.** The Product Owner accepts separation of authorities, the initial modular approach and conceptual controls/restrictions. Enterprise Connector Authorization V1 — TASK 001 is documentation only. Number 097 follows ADR-096; no duplicate ADR or implemented enterprise connector was found. Acceptance does not certify operational Microsoft Graph compatibility, approve real permissions or credentials, authorize Graph calls, implement enterprise credential custody, or automatically authorize subsequent tasks. No Entra provisioning or new service is authorized.

## Context

Identity & Access Foundation V1 TASK 001–006 are integrated; TASK 006 merged through PR #108. The foundation authenticates technical actors and computes local permissions at opt-in product boundaries. It neither authorizes Microsoft resources nor provides corporate human login, a production vault or enterprise administration. ADR-096 explicitly leaves these resource/credential decisions to Enterprise Connector Authorization.

SharePoint/OneDrive reading introduces an external credential boundary, tenant/resource bindings, permission administration, downloaded untrusted content and retention risks. Those are material new access/identity/data decisions, so an ADR is appropriate rather than treating an enterprise adapter as another clinical connector or harmless SDK dependency.

## Accepted architectural decision

1. Require independent Platform Identity, local Connector Authorization and External Resource Authorization. A platform JWT/local grant is not a Graph credential, and a Graph token is not local authority.
2. Use exact organization/instance/resource-tenant/app/mode bindings; delegated adds an explicitly linked human account. No linking by email, automatic B2B adoption, permission union, dynamic URL/provider selection or delegated-to-app-only fallback.
3. Start with registered, bounded read capabilities and the least Selected profile proven for each endpoint/account/mode, not global search or automatic broad-scope recovery. Separate administrative consent/resource assignments from the runtime reader.
4. Propose reusable modules inside existing product units, initially consumed by Healthcare AI enterprise workflows without requiring Java/FHIR. Preserve Java ownership of clinical acquisition/normalization and all existing contracts. Do not create another deployable service; extraction/credential isolation limitations remain explicit.
5. Place external credential use behind a broker/vault reference boundary, never in agents, prompts, logs, checkpoints or clinical stores. No vault is implemented by naming it.
6. Add a distinct proposed Connector Security Audit V1 for local decisions, external results and grant administration; do not relabel OIDC/Federation events or claim centralized/tamper-proof audit.
7. Treat documents, shared links and future tool/API responses as untrusted data. Reading does not authorize model disclosure, indexing, sending, tool activation or scope changes. Azure/AWS reuse local authorization semantics, not Graph scopes.
8. Require independent data-use gates: A external document acquisition, B delivery to an authorized user, C processing by a specific model at an approved destination, D indexing or retaining derivatives. A implies none of B/C/D; D is disabled in V1. Reauthorize cached delivery and deny unapproved model use, instruction injection, cross-organization disclosure, sharing and exfiltration.
9. Make controlled LangGraph integration a separately authorized future TASK 005, after the bounded adapter. Use a trusted execution envelope from an authenticated and authorized boundary, not PrincipalContext supplied by prompts, tool arguments, checkpoints or users. Reauthorize asynchronous continuations; keep Microsoft tokens outside the graph; require gates A/B/C/D, distinct audits and negative tests. No existing laboratory IAM endpoint authenticates arbitrary graph invocations and no generic enterprise-agent framework is assumed.

The versioned [local contract](../contracts/enterprise-connector-authorization-v1.md), [Graph permission profile](../contracts/microsoft-graph-connector-permissions-v1.md) and [architecture](../design/enterprise-connector-authorization-v1.md) define details once. Microsoft facts are sourced and dated in the profile; this ADR accepts application design direction, not live provider compatibility or implemented enforcement.

## Alternatives

| Alternative | Evaluation |
|---|---|
| Treat platform OIDC as enterprise-resource authorization | Reject: wrong audience/authority, no tenant/resource consent or credential binding |
| Put Graph access and credentials directly in an LLM/MCP tool | Reject: no trusted policy gate; prompt injection/confused deputy and secret disclosure |
| Default Files.Read.All/Sites.Read.All or app-only fallback | Reject: unnecessarily broad authority and invalid recovery semantics |
| New connector microservice immediately | Defer: isolation can justify it later, but adds deployment/security/actor-propagation contracts not present today |
| Internal module with typed policy/adapter/broker interfaces | Recommend for the first bounded increment; not process isolation or a production secret boundary by itself |

## Consequences and acceptance

New onboarding, grants, credential lifecycle and audit controls must precede a real Graph reader. Existing lab human sessions/unverified CLI operator labels cannot bootstrap corporate administration. Method-specific Selected support, download safety, external revocation timing and guest access require future authorized evidence. The [threat model](../design/enterprise-connector-threat-model-v1.md) and [implementation plan](../design/enterprise-connector-authorization-implementation-plan-v1.md) define those gates.

TASK 001 creates no runtime/schema/endpoint/secret/cloud resource and changes no productive Java/Python or clinical behavior. The seven-task plan proposes synthetic fixture (002), onboarding/custody/audit (003), Graph app-only (004), controlled LangGraph integration (005), delegated consent/human binding (006) and E2E (007); every later scope requires its own authorization. Acceptance is architectural only; no production readiness, formal enterprise EPIC closure or Microsoft certification is claimed.

## References

- [ADR-096](ADR-096-identity-provider-agnostic-v1.md), [PrincipalContext V1](../contracts/identity-principal-context-v1.md).
- [IAM laboratory validation](../design/identity-access-foundation-v1-final-validation.md).
- [RAG authority decision](ADR-090-institutional-knowledge-rag.md), [clinical normalization boundary](ADR-095-clinical-normalization-boundary.md).
