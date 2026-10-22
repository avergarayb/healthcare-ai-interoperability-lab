# CLINICAL_REVIEW_CONTEXT_V1

## 1. Purpose

`CLINICAL_REVIEW_CONTEXT_V1` is the versioned internal contract for a deterministic, case-bound projection of current FHIR facts for one open `FollowUpReviewCase`.

It is not a protocol evaluation, a clinical assessment, a Gemini summary, a FHIR proxy, or a stored snapshot.

## 2. Authority

- FHIR owns the current clinical facts.
- `POST_CONSULTATION_RESULT_REVIEW_V1` owns the original match decision.
- `FollowUpReviewCase` owns immutable trigger provenance and operational state.
- This contract owns only the response of one authorized read.
- Gemini is not called.

The read does not change review identity, protocol id, original evaluation status, reason codes, matched resources, creation time, transition history, or outcome.

## 3. Endpoint

```http
GET /internal/follow-up-review-cases/{reviewCaseId}/clinical-context
X-Service-Token: <MODEL_BOUNDARY_SERVICE_TOKEN>
```

Authentication runs before repository access and before any FHIR read. A missing or invalid token is HTTP 401 with an empty body and does not reveal whether the review case exists.

The caller cannot send a FHIR type, id, query, or resource reference. `reviewCaseId` is an operational UUID. It is never copied into a FHIR path or query.

## 4. Open-only access

| Case state when acquisition starts | Result |
|---|---|
| `open` | Acquisition may proceed. |
| `closed` | HTTP 409 `clinical_context_not_available_for_closed_case`. |
| Unknown id | HTTP 404. |
| Invalid id | HTTP 422. |

The case is not reopened. Operational detail and history stay on their existing routes.

Eligibility is point-in-time. `open` is checked once before the first FHIR call. The service does not keep a SQLite transaction open across FHIR and does not check `open` again at the end. A close that commits during acquisition does not fail the request that already passed the check.

## 5. Read sequence

1. Load the durable case.
2. Require `open`.
3. Require evaluation `matched` and provenance for the case protocol.
   - `POST_CONSULTATION_RESULT_REVIEW_V1`: exactly one canonical `Encounter/{id}` and one canonical `Observation/{id}`.
   - `MISSED_FOLLOW_UP_REVIEW_V1`: exactly one canonical `Appointment/{id}`.
4. Resolve one Patient from the persisted `caseId` with the existing bounded identifier search.
5. GET the exact provenance resources for that protocol. The missed-follow-up path does not read Encounter or Observation.
6. Search Appointment for the resolved Patient with the existing bounded search.
7. Validate identity and association, then project. Encounter and Observation sections are omitted when the protocol has no such provenance.

Absolute, query-bearing, fragment, history, foreign, and wrong-type references are rejected. Unsupported provenance returns HTTP 503 and does not call FHIR.

Patient resolution does not fall back to `Observation.subject` or `Encounter.subject`. If the case does not resolve to exactly one complete Patient, the response is HTTP 503.

## 6. Exact-read outcomes

A typed exact read distinguishes a genuine upstream HTTP 404 from transport failure and from a resource that has the wrong type or id.

| Condition | HTTP |
|---|---|
| Exact Encounter, Observation, or trigger Appointment returns 404 | 200, `availability=not_found` for that resource |
| Transport, malformed payload, wrong type, wrong id, or foreign association | 503, no clinical body |
| Patient resolution failure | 503 |
| Appointment search incomplete, failed, or containing a foreign resource | 503 |
| Current Encounter or Observation status differs from the original trigger | 200, literal current status |

`not_found` is not used for integrity failures. Current status is not a new protocol match and does not close or rewrite the review case.

## 7. Response

The body is a closed object. Unknown fields are rejected by the service models. The root contains:

- `schema`: `CLINICAL_REVIEW_CONTEXT_V1`
- `reviewCase`: `reviewCaseId`, `status=open`, `version`
- `triggerProvenance`: protocol id, `matched`, reason codes, matched resources, `createdAt`
- `retrieval`: `complete` or `provenance_resource_not_found`, `retrievedAt`, `source=fhir_current`, bounded reason codes
- `currentContext.patient`: `{ "resolution": "resolved" }` only
- `currentContext.encounter`: present for `POST_CONSULTATION_RESULT_REVIEW_V1`; reference, availability, and, when available, status and optional period start/end
- `currentContext.observation`: present for `POST_CONSULTATION_RESULT_REVIEW_V1`; reference, availability, and, when available, status, optional issued, encounter reference, code, and content
- `currentContext.triggerAppointment`: present for `MISSED_FOLLOW_UP_REVIEW_V1`; reference, availability, and, when available, status and optional start
- `currentContext.appointments`: `collectionStatus=complete`, classifications, and items with reference, status, optional start, and classification

Patient id, name, birth date, gender, address, telecom, identifiers, and raw FHIR are not returned.

Appointment classifications are exactly the existing set: `UPCOMING_CONFIRMED`, `UPCOMING_UNCONFIRMED`, `CANCELLED`, `PAST`, `OTHER`, and `NONE`. `NONE` is used only after a complete empty search.

Retrieval reason codes are exactly:

- `current_context_complete`
- `provenance_encounter_not_found`
- `provenance_observation_not_found`
- `provenance_appointment_not_found`

## 8. Observation projection

Code projection may include at most 10 `coding` entries with `system`, `code`, and `display`, plus optional `text`.

Content is a closed union with `status=available` and one kind:

- `quantity`
- `coded`
- `string`
- `boolean`
- `integer`
- `range`
- `components`

Component values use the same kinds except nested components. At most 25 components are accepted. String, display, text, unit, system, and code fields are limited to 512 characters.

If a value is unsupported, conflicting, malformed, empty, or over a projection bound, the service returns the observation metadata and `content.status=not_projected` or `code.status=not_projected`. It does not truncate, interpret, or emit raw JSON. A resource whose identity or patient/encounter association is wrong is HTTP 503 instead.

## 9. Failure details

HTTP 503 uses `Clinical review context unavailable` for acquisition and integrity failures. A review row that the store cannot load uses the existing persistence detail. Neither detail includes exception text, FHIR ids, or response bodies.

## 10. Privacy and persistence

Logs for this endpoint do not include Patient identifiers, names, observation values, encounter clinical fields, appointment ids, raw FHIR, bundle bodies, paging tokens, or the clinical-context response.

The projection is not inserted into SQLite and does not add review-case columns, a cache, or a snapshot. `retrievedAt` lives only in the response.

## 11. Authentication limitation

`X-Service-Token` remains a single internal service credential. This contract does not establish production IAM, RBAC, human identity, or legal compliance.
