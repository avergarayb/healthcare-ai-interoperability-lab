# ADR-087 — Case-bound Current Clinical Review Context

## Status

Accepted

## Date

2026-10-05

## Context

`FOLLOW_UP_REVIEW_WORKFLOW_V1` keeps immutable trigger provenance and operational state for a deterministic `POST_CONSULTATION_RESULT_REVIEW_V1` match. ADR-086 excluded live clinical-detail projection. A human inspecting an open review case still needs the current FHIR facts that belong to that case, without turning the review API into a FHIR proxy or giving Gemini a new role.

## Decision

Healthcare AI exposes `CLINICAL_REVIEW_CONTEXT_V1` at:

```text
GET /internal/follow-up-review-cases/{reviewCaseId}/clinical-context
```

The capability is a bounded, case-bound read of current FHIR for one open `FollowUpReviewCase`. It is not a new protocol evaluation, a clinical assessment, a model summary, or a historical snapshot.

Authority stays split:

- FHIR owns current clinical facts.
- `POST_CONSULTATION_RESULT_REVIEW_V1` owns the original deterministic trigger.
- `FollowUpReviewCase` owns immutable trigger provenance and the operational lifecycle.
- `CLINICAL_REVIEW_CONTEXT_V1` owns only the in-memory projection returned by this request.
- Gemini has no role.

This decision supersedes only ADR-086's non-goal that excluded live clinical-detail projection. ADR-086 otherwise remains in force. The projection does not mutate `reviewIdentity`, `protocolId`, the original evaluation status, reason codes, matched resources, `createdAt`, review history, or review outcome.

## Access and concurrency

The read is available only while the durable case is `open`. A closed case returns HTTP 409 with `clinical_context_not_available_for_closed_case`. The request does not reopen the case. Operational detail and history remain available through the existing review endpoints.

Eligibility is point-in-time. The service checks `open` once before FHIR acquisition starts. It does not hold a SQLite transaction or lock during FHIR calls, and it does not re-check `open` after the reads. If another request closes the case while acquisition is in progress, the already-started request may still complete. There is no distributed transaction across SQLite and FHIR.

## Authorized read scope

`reviewCaseId` is never a FHIR identifier or query selector. The caller cannot supply a resource type, resource id, FHIR query, or Patient, Encounter, Observation, or Appointment reference.

The application loads the durable case, requires `open`, and accepts only `POST_CONSULTATION_RESULT_REVIEW_V1` provenance that is exactly one canonical `Encounter/{id}` and one canonical `Observation/{id}`. It resolves the Patient again from the persisted `caseId` through the existing bounded identifier search. It then rereads those exact resources and repeats the existing bounded Appointment search for the resolved Patient. It does not search Encounter by `status=finished` or Observation by `status=final`, because the current status of the triggering resources may have changed.

Corrupt or unsupported provenance, incomplete Patient resolution, transport failure, a wrong or foreign resource, and an incomplete Appointment search fail the whole request with HTTP 503 and no clinical body. A genuine HTTP 404 from the exact Encounter or Observation read is a current-state fact: HTTP 200 with `availability=not_found` for that resource. That distinction is typed at the FHIR read boundary. It is not inferred by parsing exception text.

## Projection limits

The response separates `triggerProvenance` from `currentContext`. Patient exposure is only `resolution=resolved`. Encounter exposes reference, availability, status, and period start/end. Observation exposes reference, availability, status, issued, encounter reference, a bounded code, and a closed content union: quantity, coded, string, boolean, integer, range, or components. Appointments reuse the existing classifications and are returned only after a complete search.

Textual projection fields are limited to 512 characters. A code has at most 10 codings. An observation has at most 25 components. Oversized or unsupported observation content uses `content.status=not_projected` or `code.status=not_projected`. Values are not truncated and raw FHIR is not returned. Identity or association corruption remains HTTP 503.

The projection is not written to SQLite. `retrievedAt` exists only in the response. Authentication remains the existing `X-Service-Token`. It authenticates an internal service caller. This decision does not add human identity, production IAM, or RBAC.

## Consequences

An authenticated caller can inspect current, case-bound clinical facts for an open review case without rerunning the protocol or invoking a model. Closed cases and untrusted acquisitions do not receive that projection. The service still has one shared service token and no per-reviewer authorization.

## Non-goals

This decision does not add clinical interpretation, diagnosis, treatment, urgency, severity, medication, FHIR writes, messaging, assignment, reviewer identity, reopen, frontend, RAG, another model, a broker, Redis, another service, or multi-tenancy. It does not claim production IAM or legal compliance.

## Related decisions and contracts

- [ADR-086](ADR-086-persistent-follow-up-review-workflow-and-operational-authority-boundary.md)
- [CLINICAL_REVIEW_CONTEXT_V1](../contracts/clinical-review-context-v1.md)
- [FOLLOW_UP_REVIEW_WORKFLOW_V1](../contracts/follow-up-review-workflow-v1.md)
- [POST_CONSULTATION_RESULT_REVIEW_V1](../contracts/post-consultation-result-review-v1.md)
