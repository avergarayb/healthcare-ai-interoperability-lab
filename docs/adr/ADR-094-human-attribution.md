# ADR-094 — Human review attribution

## Status

Accepted for development attribution. Manual validation passed. Not production-ready. Not verified clinical identity. Not a security audit. Not IAM, SSO or RBAC.

## Date

2026-10-07

## Context

[ADR-093](ADR-093-human-review-session.md) accepts a development session in front of the Human Review UI. The resolved session carries `principal_id`, `authenticator_id` and `session_id`. Close and coordination handlers use that session for access and for the HMAC, then call the review and coordination operations without it.

Operational history remains `created` and `closed` on `follow_up_review_case_events`. Coordination requests remain unattributed rows in `follow_up_coordination_requests`. [HUMAN_IDENTITY_V1](../contracts/human-identity-v1.md) left attribution and security audit as separate later decisions. A synthetic development principal is not a verified clinical identity.

The review database was at schema version 2 when this decision was proposed. Migrations `001` and `002` stay closed. Migration `003` raises the schema to version 3. The close and coordination transactions store an optional development-principal snapshot. The Human Review UI passes that snapshot from the resolved session and shows `principal_id` on the case detail. The internal close route still omits it. Existing rows receive no retrospective attribution. This service does not write FHIR. Session rows live in another SQLite file and are deleted after expiry plus the cleanup grace. The internal close route authenticates with `X-Service-Token` and has no human actor.

## Decision

`HUMAN_ATTRIBUTION_V1` is the accepted increment. Human security audit was deferred by this decision and was later added as a separate scope under [SECURITY_AUDIT_V1](../contracts/security-audit-v1.md). The attribution contract is [HUMAN_ATTRIBUTION_V1](../contracts/human-attribution-v1.md).

The review database gains `follow_up_human_attributions` through a new migration `003`. `user_version` becomes 3. Migrations `001` and `002` stay byte-for-byte unchanged. Existing operational tables are not altered. Rows already stored are not backfilled.

One row records one UI operation:

- `review_case_closed`, only in the transaction that first closes the case and appends the version 2 `closed` event;
- `coordination_request_created`, only in the transaction that first inserts that case's coordination request.

The row stores `principal_id`, `authenticator_id`, `session_id` and one UTC timestamp. It does not store `display_name`, the cookie, the session token, `token_hash`, secrets, FHIR payloads or model text. `session_id` is a copy. There is no foreign key to the session database.

Uniqueness is one row per review case and operation. A closure attribution references the existing `(review_case_id, case_version)` pair at version 2, which only the closed event can occupy. A coordination attribution references the coordination request id, and a trigger requires that request to belong to the same review case. Deletes of those business rows stay restricted while an attribution points at them.

The Human Review handler copies the snapshot from the `HumanSession` returned by `require_human_session`. Form fields cannot supply it. The internal close route keeps calling close without a snapshot. AI assistance, login, logout and rejected requests do not write this table.

If the attribution insert fails, that same review transaction rolls back. A repeated successful close or coordination POST does not insert another row and does not fill a missing historical row.

The case detail page shows `principal_id` beside the fixed statement that it is a synthetic development principal, not verified clinical identity. Absent rows say that development attribution was not recorded. They are not labeled anonymous. Review history does not gain an actor column. The queue does not show attribution.

This ADR does not accept production identity, clinician authorization, assignment, RBAC, OIDC, IAM, SSO, or a security audit. The SQLite file remains editable by whoever can write the file.

## Consequences

Local review databases at version 2 will apply `003` on the next approved startup and keep their current cases. Synthetic cases closed before that migration stay without an attribution row. The session file and the knowledge index are untouched.

The close and coordination operations gain an optional snapshot. Omitting it preserves today's unattributed write. The Human Review UI is the caller that must pass the server snapshot. A later product caller that forgets the snapshot creates a new unattributed operation. The page reports that gap as attribution not recorded.

Migration `003`, the optional snapshot, and the Human Review detail are implemented. Manual validation passed. The internal close still omits the snapshot. Security audit remains separate from attribution; `SECURITY_AUDIT_V1` subsequently covered security decisions for the Human Review UI close without changing migration `003`.
