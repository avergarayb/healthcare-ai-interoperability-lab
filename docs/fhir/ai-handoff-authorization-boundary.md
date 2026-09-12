# AI Handoff Authorization Boundary

Task 064 adds a deny-by-default authorization boundary after consumer readiness. This file lives under `docs/fhir` only for laboratory documentation layout. Task 064 does not process FHIR and does not implement real authorization.

## Purpose

```text
AiConsumerReadinessResult
        ↓
AiHandoffAuthorizationBoundary
        ↓
HANDOFF_NOT_AUTHORIZED | BLOCKED | HUMAN_REVIEW_REQUIRED | NOT_READY_FOR_AUTHORIZATION
```

`READY_FOR_FUTURE_HANDOFF` means the technical evidence is complete. It does not authorize sending the contract.

`HANDOFF_NOT_AUTHORIZED` is the only positive conclusion this task may emit. It means the structure exists and the real authorization step is still missing.

## Difference from readiness

| Layer | Meaning |
|---|---|
| `READY_FOR_FUTURE_HANDOFF` | readiness found the policy result technically complete |
| `HANDOFF_NOT_AUTHORIZED` | no effective permission to send the contract |
| Handoff authorization | not implemented; `handoffAuthorized` stays `false` |
| Dispatch | not implemented; `dispatchPerformed` stays `false` |
| Model execution | not implemented; `modelCallAuthorized` stays `false` |

```text
READY_FOR_FUTURE_HANDOFF ≠ HANDOFF_AUTHORIZED
HANDOFF_AUTHORIZED ≠ DISPATCHED
```

Task 064 never produces `HANDOFF_AUTHORIZED`.

## Input

The only permitted input is an `AiConsumerReadinessResult`, or an authorization input copied from that result.

The input never includes FHIR JSON, Bundles, Patient IDs, tokens, vendor DTOs, prompts, model output, or clinical values.

Task 064 does not re-run the FHIR pipeline.

A query parameter, header, or public boolean cannot activate authorization.

## Statuses

| Status | Meaning |
|---|---|
| `HANDOFF_NOT_AUTHORIZED` | readiness may be complete, but real authorization is not implemented |
| `BLOCKED` | readiness was blocked, or execution flags were inconsistent |
| `HUMAN_REVIEW_REQUIRED` | readiness requires human review, or `requiresHumanReview` was turned off |
| `NOT_READY_FOR_AUTHORIZATION` | readiness result is missing or incomplete |

The layer never emits `HANDOFF_AUTHORIZED`, `DISPATCHED`, `MODEL_AUTHORIZED`, or `MODEL_EXECUTED`.

## Reason codes

`REAL_AUTHORIZATION_NOT_IMPLEMENTED`, `READINESS_RESULT_MISSING`, `READINESS_BLOCKED`, `READINESS_REQUIRES_HUMAN_REVIEW`, `READINESS_NOT_COMPLETE`, `INCONSISTENT_EXECUTION_STATE`, `HUMAN_REVIEW_FLAG_MISSING`, `HANDOFF_SCOPE_NOT_GRANTED`.

Inconsistent execution is detected, not corrected: `modelCallAuthorized=true`, `modelCalled=true`, `processingStatus != NOT_EXECUTED`, `dispatchStatus != NOT_DISPATCHED`, `handoffAuthorized=true`, or `dispatchPerformed=true` become `BLOCKED`.

`AiConsumerReadinessResult` itself cannot hold those inconsistent flags. The authorization input still checks them so a later change cannot slip past this boundary.

## Future authorization contract

The result copies synthetic, non-sensitive flags that a later task may replace with real checks:

- `consumerIdentityPresent`
- `consumerAuthenticated`
- `consumerAuthorized`
- `tenantContextPresent`
- `externalAuthorizationAvailable`

Those flags never activate handoff. In this task:

```text
externalAuthorizationAvailable = false
handoffAuthorized = false
```

The only evaluation operation is `EVALUATE_HANDOFF_AUTHORIZATION`. There is no `AUTHORIZE_HANDOFF`, `DISPATCH_CONTRACT`, or `EXECUTE_MODEL`.

`ai.contract.read` is not handoff permission. A conceptual future scope `ai.handoff.request` may be recorded, but it is never granted.

## Security invariants

Every result keeps:

```text
externalAuthorizationAvailable = false
handoffAuthorized = false
dispatchPerformed = false
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
requiresHumanReview = true
```

Those values stay false or not-executed even when readiness is `READY_FOR_FUTURE_HANDOFF`.

## Architectural boundary

```text
aihandoffauthorization → aiconsumerreadiness
aihandoffauthorization → aiconsumerpolicy   (policy decision type)
aihandoffauthorization → aiconsumer         (dispatch status type)
```

The core does not import `FhirService`, routing, vendors, HAPI, SMART internals, snapshot, projection, pipeline, agent, agentstub, aiboundary, firstai component, or aigateway.

The laboratory controller may assemble the existing 057–063 chain and then hand the readiness result to this boundary. That assembly is not part of the authorization core.

`aiconsumer`, `aiconsumerpolicy`, and `aiconsumerreadiness` do not import this package.

## What this task does not do

- Real OAuth2, OIDC, JWT, or SMART authentication
- Real consumer registration or tokens
- HTTP calls to an `ai-service`
- Handoff or dispatch
- Model execution
- Clinical output

## Laboratory surfaces

- Confirmation: `GET /epic/sandbox/fhir/clinical-projection`
- Lab HTML: `GET /lab/ai-handoff-authorization`
- Lab JSON: `GET /api/ai-handoff-authorization/v1`

Those routes are laboratory surfaces. They are not a public authorization API. `?authorized=true` and similar headers do not change the verdict.

## Next steps outside this task

Task 065 adds a deny-by-default consumer authentication and authorization boundary over this result. See [ai-consumer-authorization-boundary.md](ai-consumer-authorization-boundary.md). Handoff remains unauthorized.

A later task may add a real identity provider, a granted handoff scope, or dispatch. That work is not Task 064. `HANDOFF_NOT_AUTHORIZED` must stay the default until those controls exist.
