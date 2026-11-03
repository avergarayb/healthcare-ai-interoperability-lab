# Identity Principal Context v1

## Status and authority

Approved architectural design contract for Identity & Access Foundation V1 — TASK 001, following Product Owner review and the lifecycle clarifications below. TASK 001 itself introduced no runtime resolver, registry, database, verifier or endpoint. It does not supersede [Human identity v1](human-identity-v1.md), [Human attribution v1](human-attribution-v1.md), [Security audit v1](security-audit-v1.md) or [Clinical Federation v1](clinical-federation-v1.md).

Implementation status after TASK 001: [TASK 003](python-oidc-workload-v1.md), approved by the Product Owner for laboratory scope and pending main integration, implements only the Python workload adapter on a new opt-in boundary. Human/session/legacy adapters remain unimplemented; the original design semantics below are unchanged.

`identity-principal-context-v1` describes a request-local, immutable application identity after authentication. It is not an incoming JSON credential, an access token, a JWT claim set or a clinical identity certificate. Only the receiving service's trusted authentication and policy boundary may construct it. Java and Python implement the same semantics independently when later authorized; neither requires the other process to authenticate its own requests.

## Fields

All keys below are present. Nullable fields use JSON `null`, never an empty string or a fabricated identity. The JSON example is a design fixture, not a new wire API.

| Field | Required value | Trusted origin |
|---|---|---|
| `context_version` | Exactly `identity-principal-context-v1` | Application constant |
| `internal_principal_id` | Nonempty opaque application-assigned identifier, at most 64 ASCII letters, digits, dots or hyphens | Active internal principal registration; never raw `sub`, email or a request header |
| `principal_type` | `human`, `workload`, `federation_participant` or `development_synthetic` | Explicit principal registration and credential binding |
| `organization_id` | Verified active application organization identifier, or `null` before organization selection | Enabled principal membership and organization registry |
| `authentication_method` | `oidc_code_pkce`, `oauth2_access_token`, `oauth2_client_credentials`, `legacy_service_token`, `legacy_federation_token` or `development_secret` | The one successful authentication method selected by endpoint policy |
| `provider_id` | Registered provider identifier for OIDC/OAuth identity; otherwise `null` | Approved provider configuration |
| `external_issuer` | Exact validated issuer for an external identity; otherwise `null` | Cryptographically validated token and registered issuer |
| `external_subject` | Exact nonempty subject from the validated external assertion; otherwise `null` | Validated provider profile plus existing external-identity binding |
| `effective_permissions` | Deduplicated, sorted array of application permission names; empty means none | Receiving service's current policy evaluation for this principal, organization and audience |
| `audience` | Exactly the receiving application's configured resource identifier | Route policy after access-token audience validation, or equivalent legacy binding |
| `authenticated_at` | UTC RFC 3339 instant of the corresponding authentication evidence; preserved when a human session is reused | Verified login/session evidence for humans, or credential validation evidence for token-authenticated requests; never a fabricated fresh human authentication |
| `expires_at` | UTC upper bound for this request context, following the lifecycle rules below | Human session contract and current policy, or validated access-token expiry and any stricter local limit |
| `correlation_id` | Canonical UUIDv4 for this request | Server generation or validation of a bounded incoming correlation; not an authority claim |

Permission identifiers use an application-owned namespace, for example `review.case.read`; such names are illustrative and grant nothing today. Organization identifiers must match the application's registered identifier vocabulary. Limits for issuer and subject follow the selected provider validation profile, with bounded parsing; they are not copied into the short internal-id field.

`provider_id`, `external_issuer` and `external_subject` are populated together for externally authenticated identities and are all null for legacy/development identities. API bearer validation uses `oauth2_access_token` unless an approved app-only profile and registered client binding justify `oauth2_client_credentials`; an API cannot infer the original interactive grant from a JWT alone. `oidc_code_pkce` describes the verified browser login transaction and its server-resolved session, not any arbitrary token containing a human subject. Principal type still comes from registration. A development identity cannot become `human`, and a workload/federation participant cannot acquire human authority by changing a claimed method.

```json
{
  "context_version": "identity-principal-context-v1",
  "internal_principal_id": "principal-lab-reviewer-a",
  "principal_type": "human",
  "organization_id": "org-lab-a",
  "authentication_method": "oidc_code_pkce",
  "provider_id": "lab-oidc",
  "external_issuer": "https://identity.example.invalid/realms/lab",
  "external_subject": "synthetic-subject-a",
  "effective_permissions": [],
  "audience": "healthcare-ai-api",
  "authenticated_at": "2026-11-02T12:00:00Z",
  "expires_at": "2026-11-02T12:05:00Z",
  "correlation_id": "00000000-0000-4000-8000-000000000001"
}
```

## Principal and binding model

The planned logical records are `Principal`, `ExternalIdentityBinding`, `CredentialBinding`, `OrganizationMembership` and `EndpointPolicy`. These are responsibilities, not tables introduced by TASK 001. A later laboratory implementation may use explicit, validated synthetic configuration; production storage, provisioning, administration and revocation need their own authorized work.

- `Principal` owns a stable internal id, one registered type and enabled state. A human is not a workload; an LLM is not a credential-bearing actor. A federation participant is a technical application identity bound to a registered system, not a clinician.
- `ExternalIdentityBinding` maps the exact `(external_issuer, external_subject)` pair to one internal principal. That pair is unique in the installation. Provider aliases or organization memberships cannot create a second interpretation of the same pair. Unknown, disabled or ambiguous bindings fail closed; no automatic account creation or email-based linking.
- A principal can have several explicitly approved external bindings during a provider migration. Removing a provider does not change the internal id. Linking requires a trusted administrative procedure, not proof of matching email, display name or unverified claims. Pairwise subjects may differ between clients; never infer that they belong to one person.
- `CredentialBinding` associates a registered service client, legacy credential reference or federation system with an internal principal and permitted audiences. Secret values are outside this context. An OAuth workload's registered client identity must also match the selected issuer profile; `sub` alone does not prove a client-credentials flow.
- `OrganizationMembership` associates an internal principal with enabled application organizations. A token's `tenant`, `tid`, `groups`, `roles`, `organization` or similar claims cannot create membership. Approved signed claim mappings can constrain an existing membership, never expand it without a registry decision.

Legacy adapters are future, explicit mappings. The current shared Python credential still identifies only generic `service_client` / `internal-service`; it does not become a uniquely verified workload by adopting a new name. A future adapter must classify the existing development principal as `development_synthetic`, with no external issuer/subject; that new type field is not implemented today. Neither mapping silently changes existing audit actors.

## Resolution and authorization

1. Select one authentication policy for the route from trusted configuration. Reject ambiguous credentials, unsupported methods and duplicate credential headers before business work.
2. Validate the credential using [OIDC provider integration v1](oidc-provider-integration-v1.md) or the unchanged legacy mechanism; then resolve an active internal principal and its registered type.
3. Resolve the requested application organization against trusted memberships and provider-organization bindings. A route or selection parameter is only a candidate. With several memberships require explicit selection and revalidation; never choose the first or union all memberships. Dedicated installations still perform this check.
4. A context with `organization_id=null` may only access explicitly defined organization-selection/session operations and has no domain permissions. TASK 001 adds no such routes. Missing or ambiguous organization on a domain operation denies access.
5. Compute permissions from local policy for the selected organization, credential client, audience and operation. Any external scopes/roles are at most additional constraints under an approved mapping. Effective permission is bounded by all applicable restrictions, not their union.
6. The resource owner still evaluates object ownership, case state, source grants, allowed purpose, patient link and other domain checks. A permission name or successful login does not itself permit closing a case or reading a clinical source. Deny before connector calls, model calls, graph transitions or business writes when a required decision cannot be made.

Cross-organization federation is an explicit exception to same-organization resource access: the active caller organization must be verified, while source organizations may differ only under the existing Java source grants and patient links. This contract does not collapse clinical-source organizations into the caller's tenant or relax that contract.

## Transport, lifetime and minimization

The context is recomputed at each receiving service boundary. Do not trust browser fields, `X-Principal-*`, `X-Organization-*`, forwarded context JSON, prompts, clinical documents, API payloads or future MCP responses as proof of identity or permissions. There is no context-signing service or shared context token in this task.

Three lifecycles must remain distinct:

| Boundary | Authentication evidence and context lifetime |
|---|---|
| Human OIDC Code + PKCE callback | Validate the code transaction and ID token, including its signature, issuer, client audience, nonce and expiry, before accepting the login. The ID token is evidence at that authentication boundary, not an API credential or the application's session cookie. |
| Later human request using an application session | Resolve a live server-owned session and preserve its original `authenticated_at`. Bound the request context by the local session contract, security policy, reauthentication requirements and revocation state. Session expiry may outlive the initial ID token's expiry; there is no automatic minimum with that old token's `exp`, and the expired token is not reused as a credential. |
| Workload request using an access token | Validate that token under the receiving API's profile. Context expiry cannot exceed the access token's effective expiry or any stricter local policy limit. It cannot be extended by an unrelated human session, token refresh or provider SSO session. |

The access-token bound also applies to human API bearer requests that do not use a local application session. A context must be unexpired when used; generating it after a request starts does not renew the underlying credential or session. No request-local context is a reusable session or a new token.

For a human session, retain the source of the original authentication timestamp: validated provider `auth_time` when available, or the server-recorded acceptance of the validated login under an explicit future session contract. The latter is not proof of a fresh provider challenge. Session reads, cookie rotation, access-token refresh and workflow resume must not reset that evidence to simulate fresh human presence. For workloads, authentication evidence concerns the validated technical credential; it never implies a human authenticated at that time.

Sensitive operations may require reauthentication even while the local session remains valid. The future operation/session policy must define its freshness threshold, request the appropriate provider challenge and verify returned freshness evidence before allowing the operation. If the provider cannot supply the required evidence, deny the sensitive operation rather than updating `authenticated_at` locally. Revocation must invalidate the local session under its own contract; provider-wide logout/revocation remains a separately specified integration.

These are future adoption rules, not an implementation of OIDC sessions or a change to the existing eight-hour development-session contract.

A Python-to-Java call uses a Java-audience application credential. It does not forward an ID token, cookie or arbitrary serialized human context. Java reauthenticates and reapplies its policies. Any future on-behalf-of flow must separately define delegation, actor chain, audience, organization and authorization; it is not implicit in this design.

Reevaluate membership and policy on protected requests, not just at login. Cache expiry must bound the revocation window; failure to obtain required fresh policy denies the operation. A queued/resumed workflow must not reuse a stale context as current authorization. Preserve initiating attribution separately and reauthorize external effects when they occur.

Never place raw credentials, token hashes, the entire context or external issuer/subject in ordinary logs, model prompts, MCP payloads or LangGraph checkpoints. Only explicitly contracted attribution fields may be stored. The new UUID correlation does not replace existing `FED-` hop identifiers or establish global correlation; any bridge needs a separate propagation contract.

## Compatibility and acceptance requirements

The current Python session validator and SQLite schema only accept `DEVELOPMENT_AUTHENTICATOR_V1`; current attribution has the same restriction. Existing security-audit actors and metadata are also closed allowlists. Passing a new OIDC principal into them is not supported. Later adoption needs additive versioned session/attribution/audit contracts, migrations and regression tests; preserve historical rows without fabricated attribution.

Required future deterministic cases include: same subject from two issuers resolves to different principals; unknown mapping rejected; disabled binding denied; explicit linking preserves an internal id; workload cannot become human; multi-membership never unions permissions; organization spoof rejected; stale/revoked membership denied; malformed context inputs ignored as authority; resource authorization runs before protected work; source grants still govern cross-organization reads. No test claim is made by this document.

## References

- [Identity architecture and migration](../design/identity-access-foundation-v1.md)
- [ADR-096](../adr/ADR-096-identity-provider-agnostic-v1.md)
- [OIDC Core subject identifiers](https://openid.net/specs/openid-connect-core-1_0.html#SubjectIDTypes): external identity is issuer-scoped and may be pairwise; the internal binding and membership policy above are application decisions.
