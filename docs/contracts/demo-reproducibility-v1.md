# DEMO_REPRODUCIBILITY_V1

## Status

Laboratory contract for a local, synthetic, repeatable demonstration of the two follow-up review protocols. The fixtures, preparation utility, reset utility, and automated tests are in the repository, and the operator walkthrough was completed in the laboratory. Not production-ready. Not a clinical diagnosis, recommendation, or treatment decision. Not verified clinical identity. Not clinician authorization. Not a security audit. Not IAM, SSO, or RBAC.

This contract does not change [POST_CONSULTATION_RESULT_REVIEW_V1](post-consultation-review-v1.md), [MISSED_FOLLOW_UP_REVIEW_V1](missed-follow-up-review-v1.md), [the operational review workflow](follow-up-review-workflow-v1.md), [CONTROLLED_ACTION_V1](controlled-action-v1.md), [HUMAN_IDENTITY_V1](human-identity-v1.md), [HUMAN_ATTRIBUTION_V1](human-attribution-v1.md), or [DEMO_EXPERIENCE_V1](demo-experience-v1.md). Those contracts stay in force. `FollowUpRequest`, the existing agent endpoints, protocol rules, outcomes, coordination policy, sessions, and attribution rules do not change.

## Purpose

A person can prepare two known synthetic cases, walk the current Human Review page through both operational outcomes and one internal coordination request, and later reset only that disposable review state. The next preparation starts from open cases again. Historical review rows stay unchanged.

The Healthcare AI service does not write FHIR, does not send a message, and does not schedule an appointment.

## Authority

| Source | Owns |
|---|---|
| Existing deterministic evaluators | Whether a synthetic read matches a protocol |
| `ensure_for_protocol` | Creating or reusing one durable review case for a matched trigger |
| Review SQLite, schema version 3 | Cases, events, coordination requests, and development attributions |
| Local HAPI | The synthetic Patient, Encounter, Observation, and Appointment resources named by this contract |
| This contract | Which case ids are disposable, which rows a reset may delete, and when preparation or reset must abort |
| Browser | Nothing about protocol, outcome, status, or principal |

Preparation does not call Gemini, institutional retrieval, or LangGraph. Reset does not call FHIR.

## Identifiers and isolation

Disposable case ids:

| Case id | Protocol | Role |
|---|---|---|
| `SYN-DEMO-101` | `POST_CONSULTATION_RESULT_REVIEW_V1` | One open post-consultation review |
| `SYN-DEMO-102` | `MISSED_FOLLOW_UP_REVIEW_V1` | One open missed-follow-up review |

These ids are not added to `FollowUpRequest`. `POST /internal/agent/follow-up` and `POST /internal/agent/missed-follow-up` continue to reject them. Preparation does not use those endpoints.

Protected historical case ids:

- `SYN-FOLLOWUP-006`
- `SYN-FOLLOWUP-008`
- `SYN-FOLLOWUP-012`

A row belongs to a disposable case only when its review case has `case_id` equal to `SYN-DEMO-101` or `SYN-DEMO-102` and `protocol_id` equal to the protocol in the table above. Child rows belong to that case only through `review_case_id` of such a case. Any other linkage is ambiguous and is not disposable.

The session database is a different file. Preparation and reset do not open it.

## FHIR fixtures

Versioned fixtures live in `scripts/demo-reproducibility/`. They are not placed in `scripts/fhir/`. `scripts/fhir/load-synthetic-patients.ps1` is not modified and is not the loader for this demonstration.

Each Patient uses identifier system `https://lab.local/followup-case`. The identifier value is the case id. The two cases use different Patient resources so one patient's appointments cannot satisfy the other protocol.

Allowed resource ids:

| Case | Resource id | Constraints |
|---|---|---|
| `SYN-DEMO-101` | `Patient/syn-demo-patient-101` | Identifier value `SYN-DEMO-101` |
| `SYN-DEMO-101` | `Encounter/syn-demo-enc-101` | `status` `finished`, subject is that Patient, `period.end` is a complete timestamp |
| `SYN-DEMO-101` | `Observation/syn-demo-obs-101` | `status` `final`, subject is that Patient, encounter is that Encounter, `issued` is greater than or equal to `period.end` |
| `SYN-DEMO-102` | `Patient/syn-demo-patient-102` | Identifier value `SYN-DEMO-102` |
| `SYN-DEMO-102` | `Appointment/syn-demo-noshow-102` | `status` `noshow`, participant is that Patient, `start` is a complete timestamp already before the evaluation instant |

`SYN-DEMO-101` has no Appointment. An unclassified appointment would make the current post-consultation rule insufficient, and a future booked appointment would make it not matched. `SYN-DEMO-102` has no booked appointment with a future start. Those choices follow the current rules. They do not change the rules.

Fixed laboratory instants are `2026-01-15T12:00:00Z` for the encounter end, `2026-01-15T12:30:00Z` for the observation `issued`, and `2026-01-01T00:00:00Z` for the missed appointment `start`.

Before a PUT, the utility reads the target resource:

- If it is absent, the PUT may create it.
- If it is present, every identifier, subject, encounter, and participant reference must already belong only to the same demo Patient and the same allowed resource ids. The utility may then replace that resource with the versioned fixture.
- If the resource id is one of the historical fixtures, or ownership cannot be shown from those references, the utility aborts and does not write.

No other FHIR id is written. After a review reset, these FHIR resources may remain so a later preparation can read them again.

## Deterministic preparation

Preparation runs only while Healthcare AI is stopped, under the abort conditions below. Local HAPI may be running.

For each disposable case the utility reads through the existing authorized FHIR acquisition, evaluates the existing pure protocol function, and calls `ensure_for_protocol` only when the evaluation is `matched`. It does not invoke Gemini, LangGraph, or institutional retrieval.

`ensure_for_protocol` stays idempotent:

- No review row: one open case is created, with one `created` event and version 1.
- An open row with the same review identity: that row is reused. No second case is created.
- A closed row: preparation stops without writing. The operator must run reset before preparing again. Closed cases are not reopened.

A post-consultation read that is not `matched`, or a missed-follow-up read that is not `matched`, does not create a review case. Preparation then aborts.

## Human walkthrough

After preparation, the operator starts the existing Healthcare AI process and opens the current review queue. No new page is added.

The queue shows `SYN-DEMO-101` and `SYN-DEMO-102` open. The operator then:

1. Closes one case with `follow_up_coordination_planned` and records one internal coordination request.
2. Closes the other case with `review_completed_no_operational_action`.

The stored coordination status remains `requested`. That record does not send a message, write FHIR, or schedule an appointment. The development principal recorded for those two UI operations follows [HUMAN_ATTRIBUTION_V1](human-attribution-v1.md). Internal close is not used for this walkthrough, because it does not record that attribution.

On `SYN-DEMO-102`, visual validation of [DEMO_EXPERIENCE_V1](demo-experience-v1.md) slice 2 is part of acceptance: the originating appointment is understandable once, as `Cita que originó el caso`, and the current appointment list points back to it instead of repeating it. `Estado operativo de la cita no clasificado` is visible for the current `OTHER` classification. `OTHER` and `noshow` remain in `Detalles técnicos`. `SYN-DEMO-101` does not show `Cita que originó el caso`.

## Controlled reset

Reset is a local utility. It is not an HTTP endpoint. It opens only the review database identified below. It does not open the session database and it does not call FHIR.

The utility sets `PRAGMA foreign_keys=ON` and aborts if enforcement is not active. It checks `PRAGMA user_version` is 3, `PRAGMA integrity_check` is `ok`, and `PRAGMA foreign_key_check` returns no rows. It then copies every historical row, and every child row of those historical cases, from:

- `follow_up_review_cases`
- `follow_up_review_case_events`
- `follow_up_coordination_requests`
- `follow_up_human_attributions`

Inside `BEGIN IMMEDIATE` it deletes only disposable rows, in this order, because the foreign keys are `ON DELETE RESTRICT`:

1. `follow_up_human_attributions` for the selected review case ids.
2. `follow_up_coordination_requests` for those ids.
3. `follow_up_review_case_events` for those ids.
4. `follow_up_review_cases` for `SYN-DEMO-101` and `SYN-DEMO-102` whose protocol matches the table above.

The transaction commits only when the historical copy still matches the database, `foreign_key_check` is still empty, and `user_version` is still 3. Otherwise it rolls back. A reset that finds no disposable rows commits only when that historical comparison succeeds. It does not delete SQLite `-wal` or `-shm` files. FHIR resources are left in place.

## Preconditions and abort conditions

Both utilities require an explicit absolute path to the review database. The path must be the configured local `AI_REVIEW_DB_PATH`, must already exist, and must be schema version 3. The utility aborts if that path is missing, is the session database, is the institutional-knowledge database, or cannot be resolved to one file.

Both utilities check that `127.0.0.1:8090` does not accept a connection. That check is necessary and is not sufficient. They also require the exclusive write lock from `BEGIN IMMEDIATE` within the existing busy timeout. If the port check fails, the check itself errors, the lock is not acquired, or any ownership or schema fact is uncertain, the utility aborts and leaves the database unchanged.

Preparation also requires an explicit FHIR base URL on loopback. It aborts when the URL is not loopback, when a required read is unavailable, when a PUT target fails the ownership test, or when protocol evaluation is not `matched`.

Reset aborts when any selected row is not tied to `SYN-DEMO-101` or `SYN-DEMO-102` by the rule in this contract, when a disposable case id carries a different protocol, when a protected case id appears in the delete set, or when the historical copy would change.

## Acceptance

Automated, against a temporary database and a scripted FHIR client:

- Preparation creates one open version-1 case for each disposable id and does not call Gemini.
- A second preparation reuses those open cases.
- Preparation against a closed disposable case does not write and does not reopen it.
- Reset deletes only disposable cases, their events, their coordination requests, and their attributions.
- Historical rows for `SYN-FOLLOWUP-006`, `SYN-FOLLOWUP-008`, and `SYN-FOLLOWUP-012`, including events, coordination requests, and attributions, are equal before and after reset.
- The session database is not opened.
- `FollowUpRequest` still rejects `SYN-DEMO-101` and `SYN-DEMO-102`.
- A PUT is refused when an existing resource is not owned by the demo Patient named for that id.

Manual:

- With Healthcare AI stopped, preparation leaves both cases open. After the process starts, the queue shows both.
- One case is closed with coordination planned and has one coordination request. The other is closed with no operational action.
- The request status is `requested` and the page still says that this does not send a message, write FHIR, or schedule an appointment.
- Slice 2 of DEMO_EXPERIENCE_V1 is visually confirmed on `SYN-DEMO-102`, and `SYN-DEMO-101` has no originating-appointment block.
- Reset, while the process is stopped, removes only the disposable review state. A following preparation creates open cases again. The three historical cases remain as they were.

## Implementation slices

Slice 1 is this contract.

Slice 2 is the versioned fixtures in `scripts/demo-reproducibility/`. It does not load HAPI and does not change `scripts/fhir/`.

Slice 3 is the preparation utility and the automated preparation tests. It uses a temporary review database and a scripted FHIR client.

Slice 4 is the reset utility and the isolation tests. Those tests compare historical rows before and after.

Slice 5 is the completed operator walkthrough. It does not change runtime product behavior. Visual confirmation of DEMO_EXPERIENCE_V1 slice 2 remains a separate presentation check.

## Out of scope

No new service, database, frontend, or HTTP delete endpoint. No change to protocol rules, outcome values, coordination policy, sessions, HMAC, or service-token authentication. No expansion of `FollowUpRequest`. No Gemini call on the preparation path. No use or edit of `scripts/fhir/load-synthetic-patients.ps1`. No retrospective change to historical cases. No FHIR write by the Healthcare AI service. No message and no scheduled appointment. No IAM, SSO, RBAC, or security-audit storage.
