# AI Consumer Contract v1

Task 061 prepares an internal payload a future `ai-service` could consume. It is not a public API, not a dispatch channel, and not model authorization.

## What the contract is

```text
AiExecutionDecision
        ↓
AiConsumerContract v1
        ↓
dispatchStatus = NOT_DISPATCHED
```

`contractStatus=READY` means the contract was prepared. It does not mean the contract was sent, and it does not mean a model may be called.

## Fields

The contract copies controlled metadata only:

- `contractVersion` (`v1`)
- `contractStatus` (`READY` / `BLOCKED` / `REQUIRES_HUMAN_REVIEW` / `NOT_ELIGIBLE`)
- `dispatchStatus` (`NOT_DISPATCHED` in this task)
- `pipelineStatus`
- `clinicalDataAvailable`
- `agentDecision`
- `componentStatus`
- `executionDecision`
- `requiresHumanReview`
- `modelCallAuthorized`
- `modelCalled`
- `processingStatus`
- `reasonCodes`
- `warnings`
- `medicationRequestsStatus`

It never carries Patient IDs, FHIR JSON, Bundles, tokens, vendor DTOs, prompts, or clinical values.

## Distinctions that must stay separate

| State | Meaning in Task 061 |
|---|---|
| `PREPARED` | first AI component received the boundary |
| `ELIGIBLE_BUT_NOT_AUTHORIZED` | execution gate found a technical candidate |
| `contractStatus=READY` | a consumer contract exists |
| `dispatchStatus=NOT_DISPATCHED` | nothing was sent |
| `modelCallAuthorized=false` | no model permission |
| `processingStatus=NOT_EXECUTED` | no model ran |

`ELIGIBLE_BUT_NOT_AUTHORIZED` is not authorization. A prepared contract is not a request.

Premature `modelCallAuthorized=true` is rejected with `PREMATURE_MODEL_AUTHORIZATION`. It is not normalized to `false`.

## Laboratory surfaces

- Confirmation: `GET /epic/sandbox/fhir/clinical-projection`
- Lab HTML: `GET /lab/ai-consumer-contract`
- Lab JSON: `GET /api/ai-consumer-contract/v1`

Those routes are laboratory surfaces. They are not a production consumer API. Knowing the path must not be enough for a future agent to consume the contract.

## Future consumer validation (not implemented)

A later `ai-service` must not accept this contract only because it can reach an endpoint. That work still needs:

1. Consumer registration
2. Service identity
3. Authentication
4. Token validation
5. Authorized scopes
6. Allowed tenant
7. Allowed operation
8. Contract version check
9. Schema validation
10. Data policy
11. Safe audit
12. Rate limiting if the surface is ever exposed outside the lab

Task 061 documents that list. It does not implement it, and it does not send the contract anywhere.

Task 062 adds a synthetic consumer policy over this contract. See [ai-consumer-policy.md](ai-consumer-policy.md). Allowed future consumption is still not dispatch and not model authorization.

Task 063 adds a readiness boundary over that policy. See [ai-consumer-readiness.md](ai-consumer-readiness.md). Ready for a future handoff is still not handoff authorization and not dispatch.
