# FOLLOW_UP_REVIEW_WORKFLOW_V1

## 1. Purpose

`FOLLOW_UP_REVIEW_WORKFLOW_V1` is the versioned internal operational contract that turns a `POST_CONSULTATION_RESULT_REVIEW_V1` `MATCHED` result into a durable human-review work item.

It does not redefine the deterministic protocol's `humanReview`, `action` or `clinicalAssessment` fields. It provides operational persistence, discovery, provenance inspection and closure.

## 2. Authority boundaries

- FHIR remains the source of clinical facts.
- `POST_CONSULTATION_RESULT_REVIEW_V1` owns deterministic match semantics.
- This contract owns only durable operational review state, outcome and transition history.
- Gemini owns only its existing narrative output and cannot create, suppress, mutate or close a review case.
- `X-Service-Token` authenticates an internal service caller, not a human reviewer.

## 3. Creation sequence

```text
mandatory case-bound FHIR acquisition
  -> deterministic POST_CONSULTATION_RESULT_REVIEW_V1
  -> if MATCHED, create or reuse FollowUpReviewCase and commit
  -> narrative Gemini/LangGraph when applicable
  -> HTTP projection
```

`NOT_MATCHED`, `INSUFFICIENT`, `UNAVAILABLE` and `NOT_EVALUATED` do not create a review case.

If matched-case persistence fails, the follow-up request returns HTTP 503 and Gemini is not invoked. If Gemini fails after persistence, the case remains open and discoverable.

## 4. Review event identity

The identity schema is exactly:

```text
FOLLOW_UP_REVIEW_EVENT_IDENTITY_V1
```

Canonical JSON contains:

- exact `caseId`;
- exact `protocolId`;
- sorted, unique canonical `matchedResources`.

SHA-256 of the UTF-8 canonical JSON is stored as `reviewIdentity` and is unique. The identity excludes reason codes, run id, execution identity, timestamps and model output.

The exact identity reuses the existing case whether open or closed. A different matched-resource set or protocol id creates a new case. V1 does not include FHIR `meta.versionId`; the same logical resource references after closure reuse the closed case.

## 5. Persistent case

Persisted fields are:

| Field | Rule |
|---|---|
| `id` | UUID v4; projected as `reviewCaseId`. |
| `reviewIdentity` | Unique SHA-256 identity; not exposed by the API. |
| `caseId` | Exact authorized case value. |
| `protocolId` | Versioned deterministic protocol id. |
| `protocolEvaluationStatus` | Always `matched`. |
| `reasonCodes` | Immutable, bounded, canonical protocol provenance. |
| `matchedResources` | Immutable, canonical protocol provenance. |
| `status` | `open` or `closed`. |
| `outcome` | Absent while open; required when closed. |
| `version` | 1 at creation; 2 after the only V1 closure. |
| `createdAt`, `updatedAt` | Real UTC timestamps in exact `YYYY-MM-DDTHH:MM:SS.ffffffZ` form. |
| `closedAt` | Absent while open; closure timestamp when closed. |

## 6. Lifecycle and outcomes

The only transition is:

```text
open -> closed
```

Allowed outcomes are exactly:

- `follow_up_coordination_planned`: an operational workflow records that follow-up coordination is planned; no appointment or clinical recommendation is implied.
- `review_completed_no_operational_action`: the review closes without recording coordination in this workflow; this does not mean normal, clinically unnecessary or no action elsewhere.

There is no pending, in-review, resolved, dismissed, escalated or reopened state.

## 7. Transition history

Append-only events are:

- `created`: version 1, no from-status, to-status `open`;
- `closed`: version 2, from-status `open`, to-status `closed`, with outcome.

The case mutation and corresponding event are committed in one transaction. Idempotent closure does not append a second event. This is operational provenance, not verified-human, security or clinical audit.

## 8. Follow-up response projection

A successfully persisted or reused matched result includes a separate top-level object:

```json
{
  "reviewCase": {
    "reviewCaseId": "<uuid-v4>",
    "status": "open",
    "version": 1
  }
}
```

Non-matched responses omit `reviewCase`. A valid repeated response may contain `humanReview.status=required` while `reviewCase.status=closed`; the first is immutable protocol projection and the second is operational state.

## 9. Queue API

```http
GET /internal/follow-up-review-cases
```

Parameters:

- `status=open|closed`, default `open`;
- optional exact `caseId`;
- `limit`, default 25 and maximum 100;
- opaque bounded `cursor`.

Results are ordered oldest first by `(createdAt, reviewCaseId)`. Pagination is keyset-based; a cursor is bound to the status and case-id filters that created it. Unknown, duplicate, malformed, mismatched or unbounded parameters fail validation. Queue entries omit identity hash, reason codes and matched resources.

Decoded cursor JSON rejects duplicate object member names. Cursor timestamps use the exact durable timestamp form defined above.

## 10. Detail API

```http
GET /internal/follow-up-review-cases/{reviewCaseId}
```

Detail includes operational fields, immutable protocol id/status/reasons/matched-resource provenance and ordered transition history. It does not retrieve live FHIR or model output. Unknown ids return 404; malformed ids return bounded 422.

## 11. Closure API

```http
POST /internal/follow-up-review-cases/{reviewCaseId}/close
Content-Type: application/json

{
  "expectedVersion": 1,
  "outcome": "follow_up_coordination_planned"
}
```

The request is closed and forbids extra fields. There is no note, actor or arbitrary status.

| Condition | Result |
|---|---|
| Open, expected version matches | Close atomically, append event, return 200. |
| Closed, same outcome | Return existing case with 200; no new event. |
| Closed, different outcome | 409. |
| Open, stale version | 409. |
| Unknown case | 404. |
| Invalid body/outcome | 422. |
| Persistence unavailable | 503. |

## 12. Persistence and concurrency

V1 uses a dedicated SQLite file configured by `AI_REVIEW_DB_PATH`, separately from HAPI PostgreSQL. The supported topology is one `ai-service` instance and one writer boundary.

The schema is versioned and initialized at application startup. Connections are per operation, with foreign keys, WAL, bounded busy waiting and short transactions. A unique identity constraint resolves duplicate creation. Conditional status/version updates resolve competing closures. No transaction spans FHIR or Gemini calls.

## 13. Data minimization and storage limitations

The store contains potentially sensitive operational metadata. It does not store raw Patient, Encounter, Observation, Appointment or Bundle payloads; Patient id as a separate field; prompts, completions, answers or tool evidence; notes; human identifiers; or assignment.

Creation provenance remains immutable when source FHIR changes or disappears. Operational detail and history do not retrieve live FHIR. Current clinical inspection of an open case is the separate [CLINICAL_REVIEW_CONTEXT_V1](clinical-review-context-v1.md) contract. This workflow does not store that projection. No deletion, purge or retention duration is provided.

Standard SQLite is not encrypted at rest. Real-clinical-data environments require deployment-provided protected storage and an approved retention policy. This contract does not establish production real-data readiness.

## 14. Non-goals

Closing a case records the operational outcome only. It does not create a follow-up coordination request. That later explicit POST is [CONTROLLED_ACTION_V1](controlled-action-v1.md).

The contract does not provide clinical interpretation, urgency, diagnosis, treatment, FHIR writes, messaging, reviewer identity, assignment, claiming, reopen, escalation, frontend, multi-tenancy, production IAM/RBAC, multi-replica operation or durable security/LLM audit.
