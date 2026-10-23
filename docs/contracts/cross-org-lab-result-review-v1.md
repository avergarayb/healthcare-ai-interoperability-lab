# Cross-organization laboratory result review v1

## Status

Laboratory protocol `CROSS_ORG_LAB_RESULT_REVIEW_V1`. The workflow type `cross_org_lab_result` selects it. `post_consultation` and `missed_follow_up` keep their existing rules.

This is a synthetic coordination demonstration. It is not a production-validated clinical system and it does not interpret laboratory values.

## Selection

The caller chooses the workflow type. Glucose, hemoglobin, and any other result value do not select the protocol. In `single` mode this protocol returns `insufficient` with `cross_org_requires_federated_context` and does not read Clinical Read. A match is possible only from a complete federation envelope.

## Required evidence

A match requires all of the following:

1. A finished Encounter in Mini HIS for the caller patient.
2. A submitted Mini HIS laboratory order for that patient. Its FHIR status is `active`. A recorded order stays `draft` and is `not_matched` with `order_not_submitted`.
3. A Mini LIS ServiceRequest whose identifier `https://lab.local/mini-lis/order` equals the Mini HIS order id. That value is the exchange `externalRequestId`. Two Mini LIS orders for the same HIS order stay `insufficient` with `order_correlation_ambiguous`.
4. The Mini LIS requester organization identifier equals both the Mini HIS entry `organizationId` and the envelope `requestingOrganizationId`. A mismatch stays `insufficient` with `organization_correlation_missing`.
5. The Mini LIS Patient carries `https://lab.local/mini-lis/organization/{organizationId}/patient` with the Mini HIS patient id.
6. A Mini LIS Observation with status `final`, the same Mini LIS patient, and `basedOn` the Mini LIS ServiceRequest. A preliminary observation is `not_matched` with `result_not_final`.

The stored evidence is the Encounter, the Mini HIS ServiceRequest, the Mini LIS ServiceRequest, and the final Observation. Mini LIS evidence is required. The older post-consultation rule can still match from Mini HIS alone; this protocol cannot.

## Identifiers

| Relationship | Where it is read |
|---|---|
| HIS patient | `Patient.id` on `callerSystem`, identifier `https://lab.local/mini-his/patient` |
| HIS organization | federation entry `organizationId` |
| HIS order | ServiceRequest id and `https://lab.local/mini-his/order` |
| Exchange request | LIS identifier `https://lab.local/mini-lis/order` equals the HIS order id |
| Exchange correlation | `https://lab.local/exchange/correlation` on the submitted HIS order |
| LIS order | ServiceRequest id, distinct from the HIS order id |
| LIS patient link | `https://lab.local/mini-lis/organization/{organizationId}/patient` |
| Final result | Observation id and `basedOn` the LIS ServiceRequest inside that source |

Two resources are not the same because they share `Type/id`. A reference is accepted only when its base URL matches the entry `fullUrl` base. Name, birth date, test code, value, and time proximity are not correlation keys.

## Outcomes

| Situation | Result |
|---|---|
| Complete envelope and every correlation above | `matched`, `cross_org_lab_result_requires_review`, then Human Review |
| Partial or truncated envelope | `insufficient`, `federated_context_partial` |
| Missing encounter, HIS order, patient link, order link, or final result | `insufficient` |
| Draft HIS order, preliminary result, or final result tied to another order | `not_matched` |
| Failed envelope, HTTP 401, HTTP 403, or timeout | workflow `failed`, no clinical match, no Clinical Read fallback |

A missing fact is not presented as a negative clinical finding. `not_matched` is used only when the complete evidence shows the condition itself fails.

## Reproduction

`tests/test_federated_clinical_context_live.py` with `RUN_FEDERATED_CONTEXT_LIVE=true` creates a Mini HIS order, submits it through the existing exchange, and runs `cross_org_lab_result` before and after the final Mini LIS result. Only the second run reaches `await_human`.

## Limits

Synthetic identifiers only. No master patient index. No new clinical code system beyond the proprietary codes already stored by Mini HIS and Mini LIS. The narrative quotes the evidence and does not interpret values. Human review remains required.
