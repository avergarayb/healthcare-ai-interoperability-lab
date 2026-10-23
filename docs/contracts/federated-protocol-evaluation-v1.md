# Federated protocol evaluation v1

## Status

Laboratory increment in `services/ai-service`. It runs the existing follow-up rules on a Clinical Federation envelope. It does not add a medical protocol, a clinical threshold, or an autonomous decision.

This is a synthetic demonstration. It is not a production-validated clinical system.

## Protocol selection

The caller selects the workflow. `post_consultation` stays `POST_CONSULTATION_RESULT_REVIEW_V1`. `missed_follow_up` stays `MISSED_FOLLOW_UP_REVIEW_V1`. Laboratory values do not select a protocol.

The synthetic association is explicit:

- workflow type `post_consultation`;
- patient system key `mini-his`;
- identifier system `https://lab.local/mini-his/patient`;
- identifier value `MHS-PAT-001`.

The follow-up identifier `https://lab.local/followup-case|{caseId}` is not required for this association. The workflow type is the protocol, and the configured identifier is the patient.

## What the existing rule matches

`POST_CONSULTATION_RESULT_REVIEW_V1` matches only when all of these are true:

- the caller patient is present;
- one finished Encounter belongs to that patient;
- one final Observation belongs to that patient and references that Encounter;
- `issued` is at or after `period.end`, and both timestamps are valid;
- no upcoming confirmed Appointment is present;
- no Appointment is unclassified.

The reason is `post_consultation_result_requires_review`. The result is a proposal. Human Review remains required. The rule does not interpret hemoglobin, glucose, or blood pressure.

Mini HIS seed `MHS-PAT-001` / `MHS-CON-001` / `MHS-RES-001` satisfies that structure. Mini LIS evidence is read and shown with its origin. The existing rule does not require a second source, so a glucose result is not turned into a second match and is not given a threshold.

## Evidence

For each resource kept in the workflow view:

- `sourceKey` and `meta.source`;
- resource type and id;
- code system and code only when the resource already has them;
- original value and unit, or the original string when there is no quantity;
- relevant instant;
- status;
- `fullUrl` as a locator inside the envelope.

`fullUrl` is not a FHIR server on Mini HIS or Mini LIS. The evaluator does not call it. Java rewrites relative references to the registry base URL. The evaluator copies a caller-source resource and restores `Type/id` only when that reference uses the same base as the entry `fullUrl`. A reference from another host stays unresolved. The stored match uses `Encounter/{id}` and `Observation/{id}` from `callerSystem`.

The rule snapshot contains only `callerSystem` resources. A Mini LIS observation is not paired with a Mini HIS Encounter when the local identifiers coincide. The same code and value stay two resources, each with its own `sourceKey`, `meta.source`, and `fullUrl`. Mini LIS evidence remains additional read context. It is not required for `matched`. No LOINC, SNOMED CT, or UCUM value is invented. Patient names are not copied into the view.

## Incomplete context

| Situation | Result |
|---|---|
| Every requested source is `complete` and the cap was not hit | The existing rule runs. A structural match can open Human Review. |
| One source responds and another fails, or the envelope is `truncated` | `insufficient`, including `federated_context_partial`. A visible pair does not match, because the missing source could change the rule. |
| One source is `identity_unresolved` | That source is not called. The envelope is partial. The result stays `insufficient`. The unresolved source is a warning, not a normal chart. |
| One source is `complete` with zero resources | That source is empty, not an identity miss and not a normal result. |
| The envelope is `failed` | Graph `failed`. No protocol match and no Clinical Read fallback. |
| HTTP 401 or 403, or a timeout | Graph `failed`. No clinical evaluation and no Clinical Read fallback. |

A partial context is never presented as a complete clinical review. The page keeps the sentence «Esta lectura no es una revisión clínica completa.»

## Narrative and Human Review

In federated mode the narrative is deterministic. It quotes the protocol, the rule status, the reasons, the matched references, and the other read resources with source, value, and unit. It does not call Gemini and cannot change the rule result.

A match stores the existing review case and pauses at `await_human`. The page shows the matched evidence with its source. The open-case JSON projection still returns HTTP 409 `federated_context_not_read_from_clinical_read` and does not explain a federated evaluation with a Clinical Read chart.

No review schema changed. Older cases stay readable.

## Reproduction

Set `RUN_FEDERATED_CONTEXT_LIVE=true` and run `tests/test_federated_clinical_context_live.py` from `services/ai-service`. The test starts PostgreSQL 16, Mini LIS, a temporary Mini HIS, and FHIR Integration Service on loopback ports `15433`, `18196`, `18195`, and `18181`. It creates one synthetic exchange order, stores one Mini LIS result, reads the federation envelope, and expects `waiting_human` with `POST_CONSULTATION_RESULT_REVIEW_V1`.

It does not use the live Mini HIS database, does not bind `8080`, `8081`, `8090`, `8095`, or `8096`, and does not reset synthetic data.

## Limits

The demonstration uses synthetic identifiers only. It does not validate a clinical protocol for care. It does not implement a master patient index. Mini HIS evidence determines a structural match. Mini LIS evidence adds context and does not satisfy the pair by sharing a local identifier. Single mode is unchanged.
