# HUMAN_ATTRIBUTION_V1

## Status

Accepted laboratory contract for development attribution. The Human Review UI stores a development-principal snapshot on a real close and on the first coordination request, and the case detail shows it. Manual validation and deterministic regression passed. Not production-ready. The stored principal is a synthetic development principal, not verified clinical identity. Not clinician authorization. Not a security audit. Not IAM, SSO or RBAC. No retrospective attribution. No FHIR write from this service.

This contract records which synthetic development principal initiated a real Review Case closure or the first follow-up coordination request from the Human Review UI. It does not revise [HUMAN_IDENTITY_V1](human-identity-v1.md), [CONTROLLED_ACTION_V1](controlled-action-v1.md) or [the operational review workflow](follow-up-review-workflow-v1.md). Those contracts stay in force.

## Authority

| Source | Owns |
|---|---|
| Resolved `HumanSession` | `principal_id`, `authenticator_id` and `session_id` copied into one attribution row |
| Human Review close POST | Whether this closure is a UI closure |
| Human Review controlled-action POST | Whether this coordination insert is a UI insert |
| Review SQLite transaction | Case, operational event, coordination row and attribution commit or roll back together |
| Existing review and coordination services | Whether the operation itself is allowed |

A stored `principal_id` means the server copied the development principal from the live session that submitted that POST. It does not mean a clinician was verified, a case was assigned, or a named person approved the action.

The browser, Gemini, institutional retrieval and FHIR context do not supply the principal. `POST /internal/follow-up-review-cases/{reviewCaseId}/close` does not create an attribution row. A service token is not a human principal.

## What is attributed

Exactly two operations, and only when that operation first succeeds from the Human Review UI:

| `operation` | Business row that must exist in the same transaction |
|---|---|
| `review_case_closed` | The operational `closed` event at case version 2 |
| `coordination_request_created` | The first `follow_up_coordination_requests` row for that review case |

Not attributed:

- Review Case creation and the operational `created` event.
- A repeated close of an already closed case, including the same outcome.
- A repeated coordination POST that returns the existing request.
- Any row already stored before this migration. Those rows are not backfilled.
- AI assistance, including a successful Gemini explanation.
- Login, logout, an incorrect development secret, an invalid HMAC, an invalid Origin, and a missing session.
- `POST /internal/follow-up-review-cases/{reviewCaseId}/close`.
- A direct repository call that does not receive an attribution snapshot.

The operational history table stays `created` and `closed` only. Coordination rows keep the fields defined by migration `002`. Attribution is a third table in the same review database.

## Snapshot

The HTTP handler builds the snapshot after `require_human_session` returns a `HumanSession`. The snapshot contains only:

| Field | Source |
|---|---|
| `principal_id` | `HumanSession.principal_id` |
| `authenticator_id` | `HumanSession.authenticator_id` |
| `session_id` | `HumanSession.session_id`, the session row UUID |

It does not contain the cookie, the raw token, `token_hash`, the development secret, the form signing secret, `display_name`, or any clinical value.

Form and query parsers stay exact. Close still allows only `outcome`, `expectedVersion`, `formToken` and `formExpiry`. Controlled action still allows only `actionExpiry` and `actionToken`. A body that adds `principal_id`, `authenticator_id`, `session_id` or any other field is rejected by the existing parser before a review write. The internal close JSON body still forbids extra fields and still has no actor.

`session_id` is copied so the row remains readable after session expiry and after session cleanup deletes the session row. There is no foreign key to `human_sessions`. The review database is not opened to resolve a session, and the session database is not opened to write attribution.

Application validation, before `BEGIN IMMEDIATE` on the review database, uses the existing development principal pattern and `DEVELOPMENT_AUTHENTICATOR_V1`. `session_id` must be a canonical UUID string. A snapshot that fails those checks writes nothing and returns the existing generic unavailable page. It does not close the case and does not insert a coordination request.

## Schema 003

The review database moves from `user_version` 2 to 3. Migrations `001_follow_up_review.sql` and `002_follow_up_coordination_request.sql` are not edited. `003_follow_up_human_attribution.sql` is:

```sql
BEGIN IMMEDIATE;

CREATE TABLE follow_up_human_attributions (
    attribution_id TEXT PRIMARY KEY,
    review_case_id TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (
        operation IN ('review_case_closed', 'coordination_request_created')
    ),
    subject_version INTEGER CHECK (subject_version IS NULL OR subject_version = 2),
    coordination_request_id TEXT,
    principal_id TEXT NOT NULL CHECK (
        length(principal_id) BETWEEN 1 AND 64
        AND principal_id NOT GLOB '*[^a-z0-9-]*'
        AND principal_id NOT GLOB '-*'
        AND principal_id NOT GLOB '*-'
    ),
    authenticator_id TEXT NOT NULL CHECK (
        authenticator_id = 'DEVELOPMENT_AUTHENTICATOR_V1'
    ),
    session_id TEXT NOT NULL CHECK (
        length(session_id) = 36
        AND session_id NOT GLOB '*[^0-9a-fA-F-]*'
    ),
    occurred_at TEXT NOT NULL CHECK (substr(occurred_at, -1) = 'Z'),
    UNIQUE (review_case_id, operation),
    CHECK (
        (
            operation = 'review_case_closed'
            AND subject_version = 2
            AND coordination_request_id IS NULL
        )
        OR
        (
            operation = 'coordination_request_created'
            AND subject_version IS NULL
            AND coordination_request_id IS NOT NULL
        )
    ),
    FOREIGN KEY (review_case_id) REFERENCES follow_up_review_cases(id) ON DELETE RESTRICT,
    FOREIGN KEY (review_case_id, subject_version)
        REFERENCES follow_up_review_case_events(review_case_id, case_version)
        ON DELETE RESTRICT,
    FOREIGN KEY (coordination_request_id)
        REFERENCES follow_up_coordination_requests(id) ON DELETE RESTRICT
);

CREATE TRIGGER follow_up_human_attributions_coordination_case
BEFORE INSERT ON follow_up_human_attributions
WHEN NEW.operation = 'coordination_request_created'
BEGIN
    SELECT RAISE(ABORT, 'attribution coordination case mismatch')
    WHERE NOT EXISTS (
        SELECT 1 FROM follow_up_coordination_requests
        WHERE id = NEW.coordination_request_id
          AND review_case_id = NEW.review_case_id
    );
END;

PRAGMA user_version = 3;

COMMIT;
```

`UNIQUE (review_case_id, case_version)` already exists on `follow_up_review_case_events`. Version 2 of that table is the closed event only, so the composite foreign key can point only at that event. A `created` event cannot satisfy `subject_version = 2`. SQLite does not enforce a foreign key when `subject_version` or `coordination_request_id` is null, so each operation uses only the key that applies to it.

The trigger rejects a coordination attribution whose request id belongs to another review case. Product code has no `UPDATE` or `DELETE` for this table. `ON DELETE RESTRICT` keeps a case, a closed event or a coordination request from disappearing while an attribution points at it.

Startup follows the current chain:

| Current `user_version` | Action |
|---|---|
| 0 | Apply `001`, then `002`, then `003` |
| 1 | Apply `002`, then `003` |
| 2 | Apply `003` |
| 3 | Open only when the schema contract matches this chain |
| Greater than 3 | Fail closed |

A failed `003` rolls back and leaves the review store unavailable. Existing cases, events and coordination requests are kept. No attribution row is inserted for them during migration. The session database and the institutional knowledge database are not migrated. The supported topology remains one `ai-service` process and one review writer.

The schema contract comparison executes `001`, `002` and `003` in memory. `SCHEMA_VERSION` is 3. The Human Review UI passes a snapshot from the resolved session. Callers that omit the snapshot still insert no attribution row. Migration does not add attribution to rows that already existed.

## Atomicity

Both writes stay inside the existing `BEGIN IMMEDIATE` on the review connection. The attribution `INSERT` happens before `COMMIT`. There is no second connection and no write after commit.

Closure, when the case is open and `expected_version` matches:

1. Update the case to `closed` at version 2.
2. Insert the operational `closed` event.
3. When the caller passed a snapshot, insert one `review_case_closed` attribution.
4. Commit.

`occurred_at` on that attribution is the same timestamp stored on the closed event. The UI path always passes the snapshot. The internal close path and any other current caller omit it, and step 3 does not run.

When the case is already closed with the same outcome, the transaction commits the current row and returns it. It does not insert an event or an attribution, including when the historical closure has no attribution row.

Coordination, when `INSERT ... ON CONFLICT DO NOTHING` reports one new row:

1. Insert the coordination request, copying `protocol_id` from the case.
2. When the caller passed a snapshot, insert one `coordination_request_created` attribution for that new request id.
3. Commit.

`occurred_at` is the same timestamp stored on the new coordination row. When the insert conflicts, the transaction returns the existing request and does not insert an attribution.

If the attribution `INSERT` fails, the connection context rolls the transaction back. The case status, the operational event and the coordination row from that attempt are not kept. The HTTP response is the existing generic persistence failure. It does not include SQL, the trigger text, the path or the principal. A later successful POST may try again.

Concurrent closes keep the current conditional update. Only the transaction whose update changes one row inserts the event and the attribution. Concurrent coordination inserts keep `ON CONFLICT DO NOTHING`. Only the transaction that inserts the request inserts the attribution.

## HTTP

`POST /review-cases/{reviewCaseId}/close` and `POST /review-cases/{reviewCaseId}/controlled-action` still require a live session, same-origin and the purpose-separated HMAC before any review write. An invalid HMAC writes no case change, no coordination row and no attribution row.

The handler copies the snapshot from the resolved session only. It does not read principal fields from the form.

`POST /internal/follow-up-review-cases/{reviewCaseId}/close` stays authenticated only by `X-Service-Token`. It calls the same close operation without a snapshot. A human session cookie on that route remains ignored.

AI assistance, login and logout do not gain an attribution write.

## Detail page

The case detail page gains one section, separate from Review history. Review history does not gain an actor column. The queue does not show attribution.

The section always includes this sentence:

`Shown principal ids are synthetic development principals, not verified clinical identity.`

| Durable state | Line |
|---|---|
| Case open | `Case closure: not closed.` |
| Case closed, no `review_case_closed` row | `Case closure: no development attribution was recorded.` |
| Case closed, attribution present | `Case closure: synthetic development principal <principal_id>.` |
| No coordination row | `Coordination request: none.` |
| Coordination row, no `coordination_request_created` row | `Coordination request: no development attribution was recorded.` |
| Coordination row and attribution present | `Coordination request: synthetic development principal <principal_id>.` |

`<principal_id>` is HTML-escaped. The page does not show `display_name`, `session_id`, the cookie or the token hash. Missing attribution is not labeled anonymous and is not given a placeholder principal.

`GET /internal/follow-up-review-cases/{reviewCaseId}` stays the operational detail defined by the workflow contract. It does not add an actor field in this increment.

## Tests the implementation must include

Deterministic tests, synthetic fixtures only. No live Gemini and no live HAPI.

| Case | Expected result |
|---|---|
| UI close of an open case | Case version 2, one `closed` event and one `review_case_closed` row commit together. `principal_id` and `session_id` match the server session. `occurred_at` matches the event. |
| Attribution insert aborted after the case update | Case stays open, version 1, one `created` event, zero attribution rows. |
| Same-outcome close repeated | Still one closed event and one attribution row. |
| UI coordination on an eligible closed case | One coordination row and one `coordination_request_created` row commit together. The review case version does not change. |
| Attribution insert aborted after the coordination insert | Zero coordination rows and zero attribution rows. |
| Coordination POST repeated | Still one coordination row and one attribution row. |
| Invalid or cross-session HMAC | No case change, no coordination row, no attribution row. |
| Form field `principal_id`, `authenticator_id` or `session_id` | Existing 400. No write. The stored principal, when a later valid POST writes one, is the configured session principal. |
| Internal close with `X-Service-Token` | Case closes with a `closed` event and zero attribution rows. |
| Case and coordination rows created before `003` | They remain after migration, with zero attribution rows, and the detail page says attribution was not recorded. |
| Open case detail | Says the case is not closed. It does not show a principal. |
| Review database and session database | Attribution rows exist only in the review file. The session file gains no business table. Session cleanup can delete the session row while the attribution row remains. |
| Direct repository close without a snapshot | Operational close only. No attribution row. |

Schema tests must reject `user_version` greater than 3, a version 3 file that does not match the chain, a second attribution for the same case and operation, an attribution aimed at the `created` event, and a coordination attribution whose request belongs to another case.

## Implementation slices

Slices 1 through 4 are implemented. Manual validation passed. The internal close still omits the snapshot.

| Slice | Work | Result |
|---|---|---|
| 1 | This contract and ADR-094 | Accepted laboratory contract |
| 2 | Migration `003`, schema version 3, fail-closed validation | Present. Existing rows stay unattributed |
| 3 | Optional snapshot on the review close and coordination transactions, with rollback | Present. Callers that omit the snapshot stay unattributed |
| 4 | Human Review UI passes the server snapshot and renders the detail section | Present. Internal close still omits the snapshot |

Slice 4 is the product boundary. A repository that can store a snapshot is not, by itself, the Human Review behavior.

## Non-goals

The attribution table is not a security-audit table and does not store login, logout, HMAC failure, AI assistance, or model text. The separate [SECURITY_AUDIT_V1](security-audit-v1.md) later added bounded login and Human Review close security events without changing this attribution schema. No RBAC, assignment, OIDC, SMART login, IAM, SSO, multi-tenancy, MCP, Kafka, or another service. No FHIR write from this service. No hash chain and no claim that either SQLite file is tamper-proof. No retrospective attribution. No production identity claim, no verified clinical identity, and no HIPAA or GDPR claim.

## Acceptance matrix

| Criterion | Pass |
|---|---|
| Real UI closure | One attribution row in the same commit as the closed case and the `closed` event |
| First UI coordination request | One attribution row in the same commit as the new coordination row |
| Failed attribution insert | That attempt leaves no case change and no coordination row |
| Idempotent repeat | No second attribution row |
| Invalid HMAC | No attribution row and no business write |
| Internal service-token close | Closed case, no attribution row |
| Historical rows | No attribution row, and the page does not call them anonymous or attributed |
| Client-supplied principal | Rejected. The snapshot comes from the resolved session |
| Session file | Unchanged schema. No foreign key from attribution to sessions |
| Operational tables | Migrations `001` and `002` byte-for-byte unchanged. History still has only `created` and `closed` |
| Label | Detail page calls the value a synthetic development principal |

## Risks

The SQLite file owner can still change or delete rows. This table has no update API. That is not tamper evidence.

Every browser that knows the development secret shares one configured `principal_id`. `session_id` separates sessions. It does not verify a person.

A future UI caller that closes through the repository without a snapshot produces a new unattributed closure. The page then shows that attribution was not recorded. The internal route is the accepted case of that gap. Other product code must pass the snapshot only from a resolved session.

The trigger abort text must not be copied into an HTTP response.

Applying `003` on the local review file keeps current synthetic cases and does not invent principals for them. Implementation must not delete or rebuild that file to make the migration look populated.
