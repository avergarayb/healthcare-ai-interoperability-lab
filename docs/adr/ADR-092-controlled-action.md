# ADR-092 — Controlled follow-up coordination action

## Status

Accepted

## Date

2026-10-07

## Context

A closed follow-up review case can already record `follow_up_coordination_planned` or `review_completed_no_operational_action`. That outcome is the human operational decision. It is not itself an executed action. AI-assisted review may have explained the open case earlier. Gemini output, retrieved guidance and browser fields are not authorization to act.

The next demonstration had to show one explicit human request, a deterministic policy, and one durable internal result, without sending a message, writing FHIR, or scheduling an appointment.

## Decision

`CONTROLLED_ACTION_V1` adds one action, `create_follow_up_coordination_request`, for a review case that is already closed with `follow_up_coordination_planned` and one of `POST_CONSULTATION_RESULT_REVIEW_V1` or `MISSED_FOLLOW_UP_REVIEW_V1`.

The browser calls `POST /review-cases/{reviewCaseId}/controlled-action` only after the reviewer presses `Create coordination request`. Closing the case does not create the request. There is no internal service-token action route and no generic `POST /actions`.

`FollowUpCoordinationActionService` loads the durable review case and applies `FOLLOW_UP_COORDINATION_ACTION_POLICY_V1`. The policy reads status, outcome and protocol from that row. It does not read FHIR, Gemini output, retrieval text, or caller-supplied outcome, protocol or status. A denial does not insert a row. An allowance calls the repository once.

The repository remains persistence. `ensure_follow_up_coordination_request` copies `protocol_id` from the review case inside `BEGIN IMMEDIATE`, inserts one row, and does not apply the business policy. The product page does not call that method. A later in-process caller must use the service.

The durable result is one `follow_up_coordination_requests` row in the existing review SQLite file, added by migration `002` when `user_version` is 0 or 1. The row status is only `requested`. That means the internal request was recorded. It does not mean a person was contacted or an appointment was booked. The row is not removed when a future adapter exists. A later external step would consume this request. It would not replace the request, and it would not become the authorization decision.

Identity is the SHA-256 of canonical JSON for `CONTROLLED_ACTION_IDENTITY_V1`, the review case id and the action type. `UNIQUE(action_identity)` and `UNIQUE(review_case_id, action_type)`, with `INSERT ... ON CONFLICT DO NOTHING`, make repeated and concurrent requests return the same row. There is no action-event table. Review-case history stays the created and closed events. The action does not change the review case.

The POST reuses same-origin validation and `HUMAN_REVIEW_FORM_SIGNING_SECRET`, with purpose `controlled-action`, the review case id, the fixed action type and a 900-second expiry. A close token and an assistance token do not validate. A blank secret hides the button and rejects the POST before the service runs. The signature is presentation protection for this synthetic demo. It is not authenticated human approval, reviewer identity, or a security audit.

Gemini, institutional retrieval, LangGraph and FHIR writes have no role in authorization or execution.

## Consequences

The demonstration can show decision and execution as separate steps. A valid form is not clinician authorization. Access to the review pages is the development session in [ADR-093](ADR-093-human-review-session.md). That session is development authentication, not production identity. Direct use of the repository method still persists for an existing case without the policy, so new product code must call the service. A closed review case does not change outcome or protocol through the review service, so the policy read remains valid until the insert. This is not production authorization, clinical validation, HIPAA or GDPR compliance, or an external integration.
