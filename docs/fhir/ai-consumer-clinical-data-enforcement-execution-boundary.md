# AI Consumer Clinical Data Enforcement Execution Boundary

Task 070 adds a deny-by-default clinical data-access enforcement-execution boundary after an enforcement decision. This file lives under `docs/fhir` only for laboratory documentation layout. Task 070 does not process FHIR and does not execute enforcement.

## Purpose

```text
AiConsumerClinicalDataEnforcementResult
        +
synthetic ClinicalDataEnforcementExecutionContext
        ↓
AiConsumerClinicalDataEnforcementExecutionBoundary
        ↓
NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS
  | EXECUTION_INPUT_NOT_AVAILABLE
  | EXECUTION_BLOCKED
  | EXECUTION_REQUIRES_ENFORCEMENT_DECISION
  | EXECUTION_REQUIRES_REAL_AUTHORIZATION
  | EXECUTION_REQUIRES_HUMAN_REVIEW
  | EXECUTION_NOT_AVAILABLE
```

An enforcement decision is not execution. Execution is not a grant. A grant is not a FHIR read.

## Relation to Task 069

Task 069 decides that enforcement is not applied. Task 070 consumes only that result and asks a narrower question:

> Is clinical-data enforcement execution available?

It does not ask whether clinical access is granted or applied.

## Distinctions

```text
decisión de enforcement ≠ ejecución de enforcement
frontera sintética ≠ permiso clínico efectivo
ejecución declarada ≠ ejecución realizada
```

Task 070 never produces `CLINICAL_DATA_ACCESS_GRANTED`, `CLINICAL_DATA_ACCESS_ENFORCED`, or `ENFORCEMENT_EXECUTED`.

## Input

The only permitted input is an `AiConsumerClinicalDataEnforcementResult` plus a synthetic `ClinicalDataEnforcementExecutionContext`.

The context may record a decision check, an authorization check, or a human-review check. Those values are untrusted. They do not trigger FHIR reads, tokens, or OAuth.

## Statuses

| Status | Meaning |
|---|---|
| `NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS` | the 069 result is not enforced; the default laboratory path |
| `EXECUTION_INPUT_NOT_AVAILABLE` | the 069 result is missing |
| `EXECUTION_BLOCKED` | missing tenant or untrusted true flag |
| `EXECUTION_REQUIRES_ENFORCEMENT_DECISION` | an enforcement-decision check was attempted without a real decision |
| `EXECUTION_REQUIRES_REAL_AUTHORIZATION` | an authorization check was attempted without a real provider |
| `EXECUTION_REQUIRES_HUMAN_REVIEW` | a human-review check remains required |
| `EXECUTION_NOT_AVAILABLE` | reserved deny state |

## Deny-by-default

```text
missing 069 result → input not available
untrusted true flag → block
missing tenant → block
decision check without decision → requires enforcement decision
authorization check without provider → requires real authorization
human-review check → requires human review
enforcement not executed → not executed
```

Query parameters and headers such as `?enforcementExecutionPerformed=true` do not change the verdict.

## Security invariants

Every result keeps:

```text
executionDecisionAvailable = false
executionDecisionEvaluated = false
enforcementExecutionAvailable = false
enforcementExecutionProviderConfigured = false
enforcementExecutionPerformed = false
clinicalDataAccessGranted = false
clinicalDataAccessAllowed = false
clinicalDataAccessEnforced = false
realAuthorizationRequired = true
requiresHumanReview = true
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
modelCallAuthorized = false
```

## Example (no clinical data)

```json
{
  "boundaryVersion": "v1",
  "status": "NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS",
  "executionDecisionAvailable": false,
  "executionDecisionEvaluated": false,
  "enforcementExecutionAvailable": false,
  "enforcementExecutionProviderConfigured": false,
  "enforcementExecutionPerformed": false,
  "clinicalDataAccessGranted": false,
  "clinicalDataAccessAllowed": false,
  "clinicalDataAccessEnforced": false,
  "requiresHumanReview": true
}
```

## Surfaces

- Lab HTML: `GET /lab/ai-consumer-clinical-data-enforcement-execution`
- Lab JSON: `GET /api/ai-consumer-clinical-data-enforcement-execution/v1`
- Epic confirmation: `GET /epic/sandbox/fhir/clinical-projection` adds `aiConsumerClinicalDataEnforcementExecution=NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS` without replacing the 066–069 lines

## Prohibited dependencies

The `aiconsumerenforcementexecution` core may import only `AiConsumerClinicalDataEnforcementResult` from Task 069. It must not import HAPI FHIR, vendors, HTTP clients, OAuth, JWT, SMART, LLM, RAG, LangGraph, or `ai-service`.

There is no real execution provider. There is no FHIR read.

## Limitations

- No real enforcement execution
- No real authorization provider
- No OAuth, JWT, or SMART change
- No FHIR read
- No handoff or dispatch
- No model execution

A later task may add a real enforcement provider. That work is not Task 070.

Task 071 adds a deny-by-default clinical data-access enforcement-execution verification boundary over this result. See [ai-consumer-clinical-data-enforcement-execution-verification-boundary.md](ai-consumer-clinical-data-enforcement-execution-verification-boundary.md). Execution remains not verified.
