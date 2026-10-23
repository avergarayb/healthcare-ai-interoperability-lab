# Federated clinical context for AI v1

## Decision

LangGraph keeps the nodes `clinical_read`, `context_intelligence`, `protocol_evaluation`, `eligibility_router`, `narrative`, `human_review`, `await_human`, `completion`, and `failure`.

`build_live_ports` still constructs `ClinicalReadClient`. It constructs `ClinicalFederationClient` only when `AI_CLINICAL_CONTEXT_MODE=federated`. Single mode never calls the federation endpoint.

Federated mode does not call Mini HIS or Mini LIS from Python. Java remains the only component that calls those connectors.

## Partial and failed reads

| Situation | Agent effect |
|---|---|
| Every authorized source is `complete` | Context `complete`. The follow-up protocol is still `insufficient` unless a later single-mode match applies. Absence of a resource is not normality. |
| At least one source is `complete` and another is not | Context `partial`. Reason `federated_context_partial`. The review page says the read is not a complete clinical review. |
| A source cannot resolve identity | Warning `identity_unresolved:<source>`. That connector is not called by Java and Python does not replace it. |
| A source is `complete` with zero resources | Warning `no_resources:<source>`. The query can still be `complete`. |
| The envelope is `failed`, or Java returns 401 or 403 | Graph `failed`. No clinical evaluation is shown as valid. Clinical Read is not used as a substitute. |
| The client times out or the body is not the federation envelope | Graph `failed` with `federation_timeout` or `federation_unavailable`. |

A partial federated read does not open Human Review by itself, because the deterministic protocol did not match. The warnings are in `clinicalContext.federation` and the review page renders them when that view is shown. A protocol result of `matched` still interrupts at `await_human`.

## Security

Tokens come from the environment. The client rejects a blank token, a blank organization, or a source list taken from anywhere except settings. Logs record the correlation id, the envelope status, and the source count. They do not record the token, the patient name, or the resource body.

## Pending

No FHIR Provenance resource. No probabilistic matching. The Java query stays sequential. Federated mode does not evaluate `POST_CONSULTATION_RESULT_REVIEW_V1` or `MISSED_FOLLOW_UP_REVIEW_V1` from the envelope, so a Mini HIS patient such as `MHS-PAT-001` stays `insufficient` with `federated_protocol_not_resolved`. That is not evidence that a federated protocol matched. In federated mode the open-case JSON detail refuses Clinical Read instead of showing a single-source chart as the evaluation evidence. Single mode still uses that projection.

## Evidence

Unit coverage is in `test_clinical_federation_client.py`, `test_federated_clinical_context.py`, and `test_federated_langgraph_mode.py`. On 2026-10-22 those tests, the Clinical Read client tests, the workflow orchestration tests, and the architecture tests passed: 51 federation/architecture/workflow tests and 16 Clinical Read tests.

The integrated run is `tests/test_federated_clinical_context_live.py` with `RUN_FEDERATED_CONTEXT_LIVE=true`. On 2026-10-22 it passed, and the closure validation passed again in 26.36 seconds. It started PostgreSQL 16, Mini LIS on `127.0.0.1:18196`, a temporary Mini HIS on `127.0.0.1:18195`, and FHIR Integration Service on `127.0.0.1:18181`. `clinical-read.source` stayed the checked-in `local-hapi`. Java accepted one synthetic exchange order, Mini LIS stored one glucose result, and the Python client read both sources as `complete`. The in-memory timeline kept the Mini HIS and Mini LIS observations separate, including `meta.source` `https://lab.local/mini-his` and `https://lab.local/mini-lis`. The workflow finished `completed` / `insufficient` / `federated_protocol_not_resolved`. It did not call Clinical Read. `human_review` stayed in the graph and was not opened for this patient. The technical view did not contain the patient name or the observation quantities.

A partial envelope, a failed envelope, HTTP 401/403, and a timeout are covered by the unit and graph tests. The live run was the complete two-source path, not a forced source outage.
