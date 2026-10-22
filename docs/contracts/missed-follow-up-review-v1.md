# MISSED_FOLLOW_UP_REVIEW_V1

## 1. Purpose

`MISSED_FOLLOW_UP_REVIEW_V1` identifies a past Appointment recorded as `noshow` when no confirmed future Appointment is currently recorded for the same authorized Patient, and presents each missed Appointment for human review.

It is an internal Healthcare AI protocol. It is not a clinical assessment and it is not production-ready.

## 2. Endpoint

```http
POST /internal/agent/missed-follow-up
X-Service-Token: <MODEL_BOUNDARY_SERVICE_TOKEN>
```

```json
{"caseId": "SYN-FOLLOWUP-008"}
```

The caller supplies only `caseId`. Patient id, Appointment id, FHIR URLs and FHIR queries are not accepted.

Authentication and `FOLLOWUP_AGENT_ENABLED` follow the existing follow-up gate. A missing token is HTTP 401. A disabled flag is HTTP 503 `Follow-up agent is disabled`.

## 3. Acquisition

For one request the application runs this order:

1. Resolve one authorized Patient from `caseId`.
2. Read and validate that Patient resource.
3. Search `Appointment?patient=Patient/{id}` with the existing bounded search.
4. Evaluate `MISSED_FOLLOW_UP_REVIEW_V1`.
5. For each `MATCHED` trigger, ensure or reuse one durable Review Case.

It does not search Encounter or Observation for this protocol.

Page limits, continuation checks, duplicate handling, Patient association and `PARTIAL` / `COMPLETE` / `UNAVAILABLE` semantics are unchanged.

One evaluation instant is used for the whole evaluation. `start < instant` is past. `start >= instant` is current or future. There is no grace period.

## 4. Decision

| Condition | Status | Reason |
|---|---|---|
| Mandatory acquisition unavailable | `unavailable` | Existing acquisition reason |
| Mandatory acquisition partial | `insufficient` | Existing acquisition reason |
| Mandatory acquisition not read | `not_evaluated` | `required_collection_not_read` |
| Any `booked` Appointment with parseable `start >= instant` | `not_matched` | `confirmed_future_follow_up_exists` |
| A valid past `noshow` exists and a `booked` Appointment has a missing or unparseable start | `insufficient` | `appointment_start_missing_or_invalid` |
| No valid past `noshow` and a `noshow` has a missing or unparseable start | `insufficient` | `appointment_start_missing_or_invalid` |
| One or more valid past `noshow` Appointments, and absence of a confirmed future booking can be proven | `matched` | `missed_follow_up_without_confirmed_replacement` |
| Otherwise | `not_matched` | `eligible_past_noshow_absent` |

`cancelled` is not a trigger. `pending` and `proposed` are not confirmed future follow-up.

Matched triggers are ordered by `Appointment.start`, then Appointment id. Each trigger persists its own review case with matched resources exactly `Appointment/{id}`. The same `caseId`, protocol id and Appointment reuses the existing case, including a closed case. A different Appointment is a different case. Closed cases are not reopened.

`NOT_MATCHED` does not persist a review case. When a future booking blocks a match, provenance lists the eligible past `noshow` resources and the blocking `booked` resources in that order.

## 5. Response

The body contains `protocolId`, `caseId`, `evaluationStatus`, `reasonCodes`, `provenanceResources` and `reviewCases`. It does not contain a Gemini narrative, `followUpRequired`, a clinical interpretation, raw FHIR or `Patient.id`.

## 6. Current context

Opening a case does not re-run this protocol. `CLINICAL_REVIEW_CONTEXT_V1` exact-reads the trigger Appointment and searches current Appointments. A typed not-found trigger is reported as `provenance_appointment_not_found`. A foreign or integrity-invalid trigger fails closed. A booking that appears later is shown as current context and leaves the durable trigger unchanged.

## 7. Non-goals

No schema migration, new outcome, FHIR write, controlled action, Gemini, LangGraph, RAG, or explicit replacement link between a missed Appointment and a later booking.
