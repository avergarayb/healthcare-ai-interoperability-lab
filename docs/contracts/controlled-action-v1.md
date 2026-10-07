# CONTROLLED_ACTION_V1

## Status

Accepted synthetic-demo contract. Not production-ready. Not authenticated human approval. Not a security audit.

## Authority

| Source | Owns |
|---|---|
| Durable Review Case | Status, outcome and protocol |
| `FOLLOW_UP_COORDINATION_ACTION_POLICY_V1` | Whether this action may be recorded |
| Repository insert | One internal coordination request |
| Human button | The explicit request to record it |

Gemini output, institutional retrieval, FHIR context and browser-supplied outcome, protocol or status do not authorize or execute the action. The action does not require AI assistance to have been generated.

## Action

The only action is `create_follow_up_coordination_request`.

It records an internal follow-up coordination request. It does not schedule an appointment, send a message, call a CRM, write FHIR, create a FHIR Task or Appointment, or interpret clinical information.

`requested` means that internal request was recorded. It does not mean contact was made or an appointment was scheduled.

## When it runs

`POST /review-cases/{reviewCaseId}/controlled-action` after `Create coordination request`.

Closing a review case does not run it. Queue GET, case GET, refresh and F5 do not run it. There is no internal action route and no generic action API.

The policy allows the action only when all of these are true on the durable review case:

- the case exists;
- `status` is `closed`;
- `outcome` is `follow_up_coordination_planned`;
- `protocol_id` is `POST_CONSULTATION_RESULT_REVIEW_V1` or `MISSED_FOLLOW_UP_REVIEW_V1`;
- the action is exactly `create_follow_up_coordination_request`.

Anything else is denied. Denial does not insert a row.

## HTTP

| Condition | Result |
|---|---|
| Allowed, first or repeated POST | `303 See Other` to `GET /review-cases/{reviewCaseId}` |
| Open case, other outcome, or unsupported protocol | 409, no row |
| Unknown case | 404 |
| Invalid link | 422 |
| Missing or malformed form, invalid Origin, bad, expired or cross-purpose HMAC | 400 |
| Blank signing secret | 400 before the action service runs |
| Persistence unavailable | 503 |

The successful GET shows `Coordination request created`, the request identifier, status `requested` and the creation timestamp. The button is absent once a row exists. Refresh repeats that GET and does not insert.

## Presentation protection

The POST uses same-origin validation and an HMAC over `controlled-action`, `reviewCaseId`, the fixed action type and expiry. TTL is 900 seconds. The same `HUMAN_REVIEW_FORM_SIGNING_SECRET` is used with a different purpose from close and from `ai-assistance`. Those tokens do not authorize this POST.

A blank secret leaves GET working, omits the button on an eligible case, and rejects the POST before the service. The service token and Gemini key are not sent to the browser.

This signature is not a login, not reviewer identity, and not single-use. A repeated valid POST for the same case returns the existing request.

## Persistence

The row lives in the review SQLite database, table `follow_up_coordination_requests`, not in the institutional knowledge database.

Migration `001` is unchanged. A new database applies `001` and then `002`. A database at `user_version` 1 applies `002` and becomes version 2. A future schema version fails closed. Existing review cases and their history are kept.

Stored fields are `id`, `action_identity`, `review_case_id`, `protocol_id`, `action_type`, `status` and `created_at`. There is no version column and no action-event table. `protocol_id` is copied from the review case inside the insert transaction.

`action_identity` is the SHA-256 hex of canonical JSON:

```json
{"actionType":"create_follow_up_coordination_request","identitySchema":"CONTROLLED_ACTION_IDENTITY_V1","reviewCaseId":"<review-case-uuid>"}
```

Keys are sorted. The same review case and action type produce the same identity. `UNIQUE(action_identity)` and `UNIQUE(review_case_id, action_type)` plus `BEGIN IMMEDIATE` and `ON CONFLICT DO NOTHING` yield one row for repeated and concurrent requests.

The review case status, outcome, version, timestamps, review identity, provenance and history are not modified. Review-case history remains the created and closed events.

The row does not contain raw FHIR, observation values, patient name, MRN, date of birth, demographics, clinical notes, diagnosis, treatment, Gemini output, prompts, or retrieval text.

## Non-goals

No CRM, messaging, email, scheduling, FHIR write, MCP, background worker, generic policy engine, generic tool registry, or external adapter. A future adapter may consume an already recorded request. It does not grant authorization, and this contract does not require the request row to be removed.
