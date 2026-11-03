# Trusted Identity Registry v1

TASK 004 laboratory contract under [ADR-096](../adr/ADR-096-identity-provider-agnostic-v1.md), [Principal Context v1](identity-principal-context-v1.md) and the [Python workload boundary](python-oidc-workload-v1.md). Workloads only, local Python service only. Implementation and operational evidence approved by the Product Owner for laboratory scope; commit/push authorized, main integration pending. No enterprise administration, human directory, new service or clinical multi-tenancy is introduced.

Identity & Access Foundation V1 — TASK 004: trusted workload registry and local revocation validated for laboratory scope.

## Explicit adoption

`OIDC_WORKLOAD_LAB_ENABLED=false` still removes the route/OpenAPI operation without registry, audit or provider I/O. When enabled, `OIDC_WORKLOAD_POLICY_MODE` is exactly `static` (default) or `sqlite`. Unknown modes make this boundary unavailable, never select a fallback. No claim, request header or parameter selects the mode.

- `static`: TASK 003's immutable JSON bindings, fixed organization and local grants; changes require controlled restart. Its disabled principal/binding remains 403 for compatibility.
- `sqlite`: explicit `OIDC_WORKLOAD_REGISTRY_DB_PATH`, an absolute path to an already initialized dedicated database. Static JSON bindings are ignored, even if populated. Provider metadata, exact issuer/audience, profile, algorithms, allowed organizations and key cache remain in TASK 003's trusted configuration/verifier. There is no import from Keycloak and no duplicate cryptographic trust source.

The registry must not share a file with review, human session, knowledge, legacy audit, OIDC access audit or `agent-workflow.sqlite3`. Runtime rejects configured path aliases, symlinks/junctions and linked files; foreign schema is refused without adopting/migrating it. Paths must not be SQLite sidecar filenames. Administration requires an explicit absolute database path and exclusive initialization; an existing file is never overwritten. The local OS owner remains trusted; path checks are not an OS security boundary.

## Versioned model

Migration: [001_trusted_identity_registry.sql](../../services/ai-service/app/identity_registry_migrations/001_trusted_identity_registry.sql), independent of historical application migrations. `user_version=1`, dedicated SQLite application id and the expected complete DDL identify the schema; foreign tables, triggers, altered constraints, failed integrity/FK checks or missing change-audit revisions deny use.

| Responsibility | Stored authority |
|---|---|
| Registry metadata | Contract version, one configured provider id/exact issuer/API audience, monotonic committed policy revision |
| Principal | Stable internal id, literal `workload`, enabled, version, UTC update time |
| Organization | Registered internal id and enabled flag; not an IdP realm or clinical-source grant |
| ExternalCredentialBinding | Stable binding id, exact issuer + subject + client, internal principal FK, enabled/version/update time |
| Membership | Principal + organization composite key/FKs, enabled/version/update time |
| PermissionGrant | Principal + organization + permission composite key; FK to membership, enabled/version/update time |
| PolicyChangeAudit | Minimized change evidence in the same transaction as policy; see below |

Issuer/subject and issuer/client are independently unique. Client identity must match the verified TASK 003 workload profile; email is never an identity key. A principal may have multiple registered bindings and memberships, but no implicit linkage or grant union. The bounded, strict, duplicate-key-rejecting fixture is trusted offline operator input, not API input. See the [synthetic fixture](../../services/ai-service/trusted-identity-registry.example.json). Initial fixture data and its initialization event commit atomically. Failed exclusive initialization can leave an empty, unusable file; it is not automatically deleted or reused.

## Request resolution and organizational policy

After the unchanged JWT verifier returns its minimized verified subject/client/expiry, every request opens a fresh read-only SQLite connection and explicit consistent transaction. No principal, membership or permission cache survives that request. The registry's provider/issuer/audience must exactly agree with trusted configuration; the database cannot add a trusted IdP, URL or token profile.

`X-IAM-Lab-Organization` is an optional laboratory candidate: one value, 1–64 ASCII letters/digits/dots/hyphens beginning with a letter/digit. Duplicate, comma-combined, empty, padded, oversized or unknown selections deny. It proves no membership. After cryptographic authentication:

1. Resolve the exact external/client binding to an active workload principal.
2. With exactly one enabled membership in an enabled organization, omission selects that organization. With zero or multiple active memberships, omission denies; never take the first.
3. Explicit or implicit organization must have active membership, enabled registration and be allowed by the provider configuration.
4. Evaluate only enabled grants for that principal and selected organization. `iam.workload-context.read` is required; only that route permission is projected. JWT roles/groups/scopes/tenant/organization and arbitrary headers/body cannot add authority.

Grant B never authorizes A. Revoked membership blocks its existing grants; explicitly restoring membership reactivates still-enabled grants, not revoked permissions. Static mode accepts an optional candidate only if it equals its fixed registered organization, preserving no-header clients. This policy does not change Java Clinical Federation's separate caller/source organizations, grants or patient links.

## Lifecycle, errors and revocation guarantee

| Condition | Result |
|---|---|
| Active binding/principal + active selected membership + local grant | 200, minimized immutable request context |
| Unknown binding, disabled binding or disabled principal in SQLite mode | Generic 401, `WWW-Authenticate: Bearer` |
| Missing/ambiguous/unauthorized organization, inactive membership, absent/revoked permission | Generic 403 |
| Missing, inaccessible, corrupt, incompatible, locked/unreadable or trust-mismatched registry | Generic 503, no context, no static fallback |
| Mandatory access audit unavailable | Generic 503, no context even after a valid policy decision |

All existing credential, JWT, no-store, correlation and token-expiry rules remain. Policy/registry unavailability is not permission. Registry errors expose no SQLite message, file path, raw claim or principal detail. Missing credentials retain the existing 401 policy before registry access; a failed mandatory audit can override any response with 503.

CLI writes use `BEGIN IMMEDIATE`, bounded busy timeout, FKs and parameterized values. WAL permits a consistent already-open reader during a committed revocation. **New decisions whose SQLite snapshot is acquired after the revocation commit observe it**; old snapshots/in-flight authorized operations are not cancelled retroactively. The next HTTP request opens a fresh snapshot and cannot use stale positive grants. There is no global instantaneous revocation between independent databases/deployments, no IdP-side revocation and no change to signature, issuer, audience or provider token validity. Restoring authority requires a separate explicit operation.

The context stays immutable and cannot outlive its token; no context is put in sessions, audit rows or LangGraph checkpoints. A final post-audit expiry check still suppresses an expired response. Snapshot resolution and access-audit append are separate transactions: an allowed audit row may describe a decision begun before revocation or before token expiry, not guaranteed response delivery.

## Local CLI contract

From `services/ai-service`, explicitly invoke `.venv\Scripts\python.exe -B -m app.trusted_identity_registry_cli`. No HTTP administrative routes exist.

| Operation | Required arguments besides `--db ABSOLUTE_PATH` |
|---|---|
| `init` | `--fixture PATH`, optional `--operator-label ID`; exclusive creation only |
| `list` | None; sanitized ids/state/version, no issuer, subject, credentials or arbitrary metadata |
| `enable-principal`, `disable-principal` | `--target INTERNAL_PRINCIPAL_ID` |
| `enable-binding`, `disable-binding` | `--target BINDING_ID` |
| `grant-membership`, `revoke-membership` | `--target INTERNAL_PRINCIPAL_ID --organization ORGANIZATION_ID` |
| `grant-permission`, `revoke-permission` | Same plus `--permission APPLICATION_PERMISSION` |

Mutations optionally accept an id-shaped `--operator-label`; it is **unverified**, not an authenticated administrator or authorization credential. Use only synthetic non-sensitive labels. Unknown parents, invalid parameters, ambiguous targets and incompatible schemas fail without policy changes. Explicit membership/grant operations upsert their desired state under existing FKs; existing principals/bindings are toggled, not provisioned. Repeating a desired-state operation still creates a new revision/audit of that operator instruction. No delete/provision-human/provider-admin/token endpoint is added. No Keycloak administrator credential authorizes this CLI.

`list` fields are ordered row arrays: principals `[id,type,enabled,version]`, bindings `[binding_id,principal_id,enabled,version]`, memberships `[principal_id,organization_id,enabled,version]`, grants `[principal_id,organization_id,permission,enabled,version]`. Successful mutations report committed/revision/operation and `operator_verified=false`. Errors are closed sanitized codes and nonzero exit; no raw parser/fixture/SQLite error is printed.

## Separate change audit

`trusted-identity-registry-change-v1` lives only in `registry_policy_change_audit`: sequential revision, event UUID, contract, UTC time, closed operation, internal target id, optional internal organization/permission, desired enabled state, `operator_kind=local_operator_unverified`, nullable bounded operator label and literal `operator_verified=0`. Initialization is revision 1. No token/hash, secret, external subject/issuer, clinical data, arbitrary payload or legacy actor is recorded. A binding change references its internal binding id, never its external subject.

Every administrative change, record version/update time, global revision and change event commit atomically. Constraint/storage/audit failure rolls back all of them. Policy tables retain only current state; the change audit preserves minimized operator instructions. It is not tamper-proof against the local OS owner, encrypted at rest, a corporate administrative audit or a SIEM.

The independent [OIDC access audit](oidc-workload-security-audit-v1.md) remains mandatory before HTTP response and adds only the bounded `registry_unavailable` reason. Normal denials remain anonymous/null identity. There is **no distributed atomicity** between these two files, and no change to legacy audit producers, actors, schema or stores.

## Non-goals

Single-host laboratory SQLite and trusted local CLI only. No authenticated admin service, enterprise IAM/RBAC, human OIDC/session adoption, clinical data authorization/multi-tenancy, SaaS isolation, cloud resource permission, MCP, Keycloak synchronization, new agents or new deployable service. See [the runbook and evidence](../design/trusted-identity-registry-v1.md) for executed versus pending verification.
