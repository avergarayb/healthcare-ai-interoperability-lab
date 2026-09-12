# AI Consumer Readiness

Task 063 adds a deterministic readiness and handoff-boundary over the synthetic consumer policy. This file lives under `docs/fhir` only for laboratory documentation layout. Task 063 does not process FHIR.

## Purpose

```text
AiConsumerPolicyResult
        ↓
AiConsumerReadiness
        ↓
READY_FOR_FUTURE_HANDOFF | BLOCKED | HUMAN_REVIEW_REQUIRED | NOT_READY
```

`READY_FOR_FUTURE_HANDOFF` means the technical evidence is complete for a later integration step. It does not authorize sending the contract and it does not authorize a model.

## Difference from policy

| Layer | Meaning |
|---|---|
| `ALLOWED_FOR_FUTURE_CONSUMPTION` | the synthetic policy found no immediate block for a future read |
| `READY_FOR_FUTURE_HANDOFF` | readiness found the policy result technically complete |
| Handoff authorization | not implemented; `handoffAuthorized` stays `false` |
| Dispatch | not implemented; `dispatchPerformed` stays `false` |

`ALLOWED_FOR_FUTURE_CONSUMPTION` is not `HANDOFF_AUTHORIZED`. `READY_FOR_FUTURE_HANDOFF` is not `DISPATCHED`.

## Input

The only permitted input is an `AiConsumerPolicyResult`, or a readiness input copied from that result.

The input never includes FHIR JSON, Bundles, Patient IDs, tokens, vendor DTOs, prompts, model output, or clinical values.

Task 063 does not re-run the FHIR pipeline.

## Statuses

| Status | Meaning |
|---|---|
| `READY_FOR_FUTURE_HANDOFF` | policy is `ALLOWED_FOR_FUTURE_CONSUMPTION` and security flags are consistent |
| `BLOCKED` | policy rejected, version/operation/scope unsupported, or execution state inconsistent |
| `HUMAN_REVIEW_REQUIRED` | policy requires human review, or `requiresHumanReview` was turned off |
| `NOT_READY` | policy result is missing |

The layer never emits `HANDOFF_AUTHORIZED`, `DISPATCHED`, `MODEL_AUTHORIZED`, or `MODEL_EXECUTED`.

## Reason codes

`READY_FOR_FUTURE_HANDOFF`, `POLICY_REJECTED`, `POLICY_REQUIRES_HUMAN_REVIEW`, `POLICY_RESULT_MISSING`, `INCONSISTENT_EXECUTION_STATE`, `HUMAN_REVIEW_FLAG_MISSING`, `CONTRACT_VERSION_NOT_SUPPORTED`, `OPERATION_NOT_SUPPORTED_FOR_READINESS`, `SCOPE_NOT_SUPPORTED_FOR_READINESS`.

Inconsistent execution is detected, not corrected: `modelCallAuthorized=true`, `modelCalled=true`, `processingStatus != NOT_EXECUTED`, or `dispatchStatus != NOT_DISPATCHED` become `BLOCKED`.

`AiConsumerPolicyResult` itself cannot hold those inconsistent flags. Readiness still checks them on its own input so a later change cannot slip past this boundary.

## Security invariants

Every result keeps:

```text
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
requiresHumanReview = true
handoffAuthorized = false
dispatchPerformed = false
```

Those values stay false or not-executed even when the status is `READY_FOR_FUTURE_HANDOFF`.

## Architectural boundary

```text
aiconsumerreadiness → aiconsumerpolicy
aiconsumerreadiness → aiconsumer   (dispatch and contract-version types only)
```

Readiness does not import `FhirService`, routing, vendors, HAPI, SMART internals, snapshot, projection, pipeline, agent, agentstub, aiboundary, firstai component, or aigateway.

The laboratory controller may assemble the existing 057–062 chain and then hand the policy result to readiness. That assembly is not part of the readiness core.

`aiconsumer` and `aiconsumerpolicy` do not import readiness.

## What this task does not do

- Real OAuth2, OIDC, JWT, or SMART authentication
- Real consumer registration or tokens
- HTTP calls to an `ai-service`
- Handoff or dispatch
- Model execution
- Clinical output

## Laboratory surfaces

- Confirmation: `GET /epic/sandbox/fhir/clinical-projection`
- Lab HTML: `GET /lab/ai-consumer-readiness`
- Lab JSON: `GET /api/ai-consumer-readiness/v1`

Those routes are laboratory surfaces. They are not a public authorization API.

## Next steps outside this task

Task 064 adds a deny-by-default handoff authorization boundary over this readiness result. See [ai-handoff-authorization-boundary.md](ai-handoff-authorization-boundary.md). Ready for a future handoff is still not authorization and not dispatch.

Task 065 adds a deny-by-default consumer authentication and authorization boundary. See [ai-consumer-authorization-boundary.md](ai-consumer-authorization-boundary.md).

A later task may add real consumer authentication, authorized handoff, or dispatch. That work is not Task 063. `READY_FOR_FUTURE_HANDOFF` must not be treated as permission to do any of those things.
