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

No FHIR Provenance resource. No probabilistic matching. The Java query stays sequential. Federated Protocol Evaluation v1 now runs the existing structural rules on a complete envelope. See [federated protocol evaluation v1](../contracts/federated-protocol-evaluation-v1.md). A partial envelope stays insufficient and is not a match. In federated mode the open-case JSON detail refuses Clinical Read instead of showing a single-source chart as the evaluation evidence. Single mode still uses that projection.

## Evidence

Unit coverage is in `test_clinical_federation_client.py`, `test_federated_clinical_context.py`, and `test_federated_langgraph_mode.py`. On 2026-10-22 those tests, the Clinical Read client tests, the workflow orchestration tests, and the architecture tests passed: 51 federation/architecture/workflow tests and 16 Clinical Read tests.

The integrated run is `tests/test_federated_clinical_context_live.py` with `RUN_FEDERATED_CONTEXT_LIVE=true`. It starts PostgreSQL 16, Mini LIS on `127.0.0.1:18196`, a temporary Mini HIS on `127.0.0.1:18195`, and FHIR Integration Service on `127.0.0.1:18181`. `clinical-read.source` stays the checked-in `local-hapi`. The 2026-10-22 context run proved both sources and stopped at `insufficient` because protocol evaluation was intentionally not implemented then. The protocol evaluation run uses the same laboratory path and expects `waiting_human` when the existing structural rule matches `MHS-CON-001` and a Mini HIS observation. Mini LIS evidence stays visible with its own `meta.source`. The view may contain the original quantities and must not contain the patient name. That run is a synthetic demonstration, not a validated clinical system.

A partial envelope, a failed envelope, HTTP 401/403, and a timeout are covered by the unit and graph tests. The live run was the complete two-source path, not a forced source outage.
