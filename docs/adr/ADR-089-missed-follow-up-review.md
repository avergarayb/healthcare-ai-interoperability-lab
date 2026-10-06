# ADR-089 — Missed follow-up review

## Status

Accepted

## Date

2026-10-06

## Context

`POST_CONSULTATION_RESULT_REVIEW_V1` detects a post-consultation result without a confirmed future appointment. A past `Appointment` recorded as `noshow`, with no confirmed future `Appointment` for the same authorized Patient, is a separate operational review. The durable review case, queue, closure outcomes and server-rendered demo already exist.

## Decision

`MISSED_FOLLOW_UP_REVIEW_V1` is a second deterministic protocol inside Healthcare AI.

It reads only the authorized Patient and that Patient's Appointments, using the existing case resolution and bounded Appointment search. It does not read Encounter, Observation, Condition, MedicationRequest, DiagnosticReport or ServiceRequest. It does not call Gemini or LangGraph.

A trigger is `Appointment.status=noshow` with a parseable `start` before the single evaluation instant. `cancelled` is not a trigger. A `booked` Appointment with a parseable `start` at or after that instant blocks `MATCHED`. The protocol does not claim that the future appointment replaces a particular missed appointment.

Each eligible past `noshow` creates or reuses one `FollowUpReviewCase` whose matched resource is exactly `Appointment/{id}`. Review identity stays `FOLLOW_UP_REVIEW_EVENT_IDENTITY_V1`. There is no schema migration and no new outcome.

`POST /internal/agent/missed-follow-up` accepts only `caseId`, behind the existing service token and `FOLLOWUP_AGENT_ENABLED` gate. It is not a browser route.

`CLINICAL_REVIEW_CONTEXT_V1` also accepts this protocol. The response still uses that schema. Encounter and Observation are omitted when they are not this case's provenance. A missing trigger Appointment is `provenance_appointment_not_found` and does not delete or rewrite the case. Current appointments are read when the case is opened and do not change the original match.

The shared review queue and case page show this protocol with the label "Missed follow-up review".

## Consequences

Human review remains the operational authority. The protocol does not infer risk, urgency, severity, diagnosis, treatment, medical necessity or non-compliance. A later booked appointment does not close or reopen a case. This decision does not establish production readiness, IAM or clinical decision support.
