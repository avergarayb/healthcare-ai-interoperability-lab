# AI Consumer Clinical Data Enforcement Execution Verification Boundary

Task 071 adds a deny-by-default clinical data-access enforcement-execution verification boundary after an execution result. This file lives under `docs/fhir` only for laboratory documentation layout. Task 071 does not process FHIR and does not verify enforcement.

## Purpose

```text
AiConsumerClinicalDataEnforcementExecutionResult
        +
synthetic ClinicalDataEnforcementExecutionVerificationContext
        ↓
AiConsumerClinicalDataEnforcementExecutionVerificationBoundary
        ↓
NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS
  | VERIFICATION_INPUT_NOT_AVAILABLE
  | VERIFICATION_BLOCKED
  | VERIFICATION_REQUIRES_EXECUTION_RESULT
  | VERIFICATION_REQUIRES_EVIDENCE
  | VERIFICATION_REQUIRES_REAL_PROVIDER
  | VERIFICATION_REQUIRES_HUMAN_REVIEW
  | VERIFICATION_NOT_AVAILABLE
```

An enforcement execution is not verification. A claimed execution flag is not evidence. Verification is not a grant and is not a FHIR read.

## Relation to Task 070

Task 070 decides that enforcement is not executed. Task 071 consumes only that result and asks a narrower question:

> Can the claimed enforcement execution be verified?

It does not ask whether clinical access is granted, allowed, or enforced.

## Distinctions

```text
ejecución de enforcement ≠ verificación de esa ejecución
frontera sintética ≠ evidencia de permiso clínico efectivo
enforcementExecutionPerformed=true ≠ executionVerified=true
```

Task 071 never produces `CLINICAL_DATA_ACCESS_GRANTED`, `CLINICAL_DATA_ACCESS_ENFORCED`, `ENFORCEMENT_EXECUTED`, or `EXECUTION_VERIFIED`.

## Input

The only permitted input is an `AiConsumerClinicalDataEnforcementExecutionResult` plus a synthetic `ClinicalDataEnforcementExecutionVerificationContext`.

The context may record an execution-result check, an evidence check, a provider check, or a human-review check. Those values are untrusted. They do not trigger FHIR reads, tokens, or OAuth.

## Statuses

| Status | Meaning |
|---|---|
| `NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS` | the 070 result is not verified; the default laboratory path |
| `VERIFICATION_INPUT_NOT_AVAILABLE` | the 070 result is missing |
| `VERIFICATION_BLOCKED` | missing tenant or untrusted true flag |
| `VERIFICATION_REQUIRES_EXECUTION_RESULT` | an execution-result check was attempted without a real result |
| `VERIFICATION_REQUIRES_EVIDENCE` | an evidence check was attempted without a real evidence store |
| `VERIFICATION_REQUIRES_REAL_PROVIDER` | a provider check was attempted without a real verification provider |
| `VERIFICATION_REQUIRES_HUMAN_REVIEW` | a human-review check remains required |
| `VERIFICATION_NOT_AVAILABLE` | reserved deny state |

## Deny-by-default

```text
missing 070 result → input not available
untrusted true flag → block
missing tenant → block
execution-result check without result → requires execution result
evidence check without evidence → requires evidence
provider check without provider → requires real provider
human-review check → requires human review
execution not verified → not verified
```

Query parameters and headers such as `?executionVerified=true` do not change the verdict.

## Security invariants

Every result keeps:

```text
verificationDecisionAvailable = false
verificationDecisionEvaluated = false
executionEvidenceAvailable = false
executionEvidenceEvaluated = false
executionVerificationAvailable = false
executionVerificationProviderConfigured = false
executionVerified = false
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
  "status": "NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS",
  "verificationDecisionAvailable": false,
  "verificationDecisionEvaluated": false,
  "executionEvidenceAvailable": false,
  "executionEvidenceEvaluated": false,
  "executionVerificationAvailable": false,
  "executionVerificationProviderConfigured": false,
  "executionVerified": false,
  "clinicalDataAccessGranted": false,
  "clinicalDataAccessAllowed": false,
  "clinicalDataAccessEnforced": false,
  "requiresHumanReview": true
}
```

## Surfaces

- Lab HTML: `GET /lab/ai-consumer-clinical-data-enforcement-execution-verification`
- Lab JSON: `GET /api/ai-consumer-clinical-data-enforcement-execution-verification/v1`
- Epic confirmation: `GET /epic/sandbox/fhir/clinical-projection` adds `aiConsumerClinicalDataEnforcementExecutionVerification=NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS` without replacing the 066–070 lines

## Prohibited dependencies

The `aiconsumerenforcementverification` core may import only `AiConsumerClinicalDataEnforcementExecutionResult` from Task 070. It must not import HAPI FHIR, vendors, HTTP clients, OAuth, JWT, SMART, LLM, RAG, LangGraph, or `ai-service`.

There is no real verification provider. There is no evidence store. There is no FHIR read.

## Limitations

- No real enforcement verification
- No real evidence store
- No real authorization provider
- No OAuth, JWT, or SMART change
- No FHIR read
- No handoff or dispatch
- No model execution

A later task may add a real evidence or verification provider. That work is not Task 071.
