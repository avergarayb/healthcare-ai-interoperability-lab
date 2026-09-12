# AI Consumer Policy

Task 062 adds a deterministic policy over AI Consumer Contract v1. It is not real authentication, not dispatch, and not model authorization.

## Purpose

```text
AiConsumerContract v1
        +
synthetic consumer metadata
        ↓
AiConsumerPolicy
        ↓
ALLOWED_FOR_FUTURE_CONSUMPTION | REJECTED | HUMAN_REVIEW_REQUIRED
```

`ALLOWED_FOR_FUTURE_CONSUMPTION` means a laboratory consumer may later be considered for a read of the contract. It does not send the contract and it does not authorize a model.

## Input

- An existing `AiConsumerContract`.
- Synthetic consumer metadata: `consumerId`, `consumerType`, `requestedContractVersion`, `requestedOperation`, `requestedScope`, `tenantContextPresent`, `authenticated`, `authorized`.

Those fields are laboratory values. They are not tokens, users, Patient IDs, or clinic identities.

The only allowed operation is `READ_CONTRACT`. The only allowed scope is `ai.contract.read`. The only compatible version is `v1`.

## Decisions

| Decision | Meaning |
|---|---|
| `ALLOWED_FOR_FUTURE_CONSUMPTION` | contract is `READY` and the synthetic consumer passed the checks |
| `REJECTED` | consumer or contract failed a check |
| `HUMAN_REVIEW_REQUIRED` | contract status is `REQUIRES_HUMAN_REVIEW` |

The policy never emits `EXECUTE`, `DISPATCHED`, or `MODEL_AUTHORIZED`.

The boolean `requiresHumanReview` stays `true` on every result. That flag is the standing human-review requirement from Tasks 057–061. Obligatory review that blocks future consumption is `contractStatus=REQUIRES_HUMAN_REVIEW`, not the boolean alone. Otherwise every 061 contract would be blocked and Caso A could never succeed.

## Precedence

1. Invalid input
2. Consumer not authenticated
3. Consumer not authorized
4. Scope missing or not `ai.contract.read`
5. Version not `v1`
6. Operation not allowed (`EXECUTE_MODEL`, write-back, clinical writes)
7. Tenant context missing
8. Contract blocked (`CONTRACT_NOT_CONSUMABLE`)
9. Contract not eligible
10. Premature `modelCallAuthorized=true`
11. Dispatch requested or already set (`DISPATCH_TO_AI_SERVICE` is classified here, not as a generic illegal operation)
12. Contract requires human review
13. Allowed for future consumption

## Reason codes

`CONSUMER_NOT_AUTHENTICATED`, `CONSUMER_NOT_AUTHORIZED`, `REQUIRED_SCOPE_MISSING`, `CONTRACT_VERSION_NOT_SUPPORTED`, `OPERATION_NOT_ALLOWED`, `TENANT_CONTEXT_REQUIRED`, `CONTRACT_NOT_CONSUMABLE`, `CONTRACT_REQUIRES_HUMAN_REVIEW`, `CONTRACT_NOT_ELIGIBLE`, `PREMATURE_MODEL_AUTHORIZATION`, `DISPATCH_NOT_SUPPORTED`, `INVALID_POLICY_INPUT`.

## What this task does not do

- Real OAuth2, OIDC, JWT, or SMART authentication
- HTTP calls to an `ai-service`
- Dispatch, webhooks, or queues
- Model execution
- Clinical output

The laboratory page uses a fixed synthetic consumer (`lab-consumer` / `LAB`) to exercise the policy. Knowing that identity is not a credential.

## Laboratory surfaces

- Confirmation: `GET /epic/sandbox/fhir/clinical-projection`
- Lab HTML: `GET /lab/ai-consumer-policy`
- Lab JSON: `GET /api/ai-consumer-policy/v1`

## Next steps outside this task

A later task may add real consumer registration, tokens, scopes, tenants, and schema checks. That work is not Task 062.
