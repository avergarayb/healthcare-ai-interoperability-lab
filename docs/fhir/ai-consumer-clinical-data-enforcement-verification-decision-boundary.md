# AI Consumer Clinical Data Enforcement Verification Decision Boundary

Task 072 adds a deny-by-default clinical data-access enforcement verification-decision boundary after a verification result. This file lives under `docs/fhir` only for laboratory documentation layout. Task 072 does not process FHIR and does not approve verification.

## Purpose

```text
AiConsumerClinicalDataEnforcementExecutionVerificationResult
        +
synthetic VerificationDecisionContext
        ↓
AiConsumerVerificationDecisionBoundary
        ↓
VERIFICATION_DECISION_NOT_AVAILABLE
  | DECISION_INPUT_NOT_AVAILABLE
  | DECISION_BLOCKED
  | DECISION_REQUIRES_VERIFICATION_RESULT
  | DECISION_REQUIRES_VERIFIED_EVIDENCE
  | DECISION_REQUIRES_REAL_POLICY_PROVIDER
  | DECISION_REQUIRES_REAL_AUTHORIZATION
  | DECISION_REQUIRES_HUMAN_REVIEW
```

A verification result is not a decision. A decision is not an approval. An approval is not a grant and is not a FHIR read.

## Relation to Task 071

Task 071 decides that enforcement execution is not verified. Task 072 consumes only that result and asks a narrower question:

> Is a verification decision available for future policy consideration?

It does not ask whether clinical access is granted, allowed, or enforced.

## Distinctions

```text
resultado de verificación ≠ decisión de verificación
decisión disponible ≠ verificación aprobada
verificación aprobada ≠ acceso clínico concedido
frontera sintética ≠ motor de política real
```

Task 072 never produces `VERIFICATION_APPROVED`, `CLINICAL_DATA_ACCESS_GRANTED`, or `EXECUTION_VERIFIED`.

## Input

The only permitted input is an `AiConsumerClinicalDataEnforcementExecutionVerificationResult` plus a synthetic `VerificationDecisionContext`.

The context may record a verification-result check, an evidence check, a policy-provider check, an authorization check, or a human-review check. Those values are untrusted. They do not trigger FHIR reads, tokens, or OAuth.

## Statuses

| Status | Meaning |
|---|---|
| `VERIFICATION_DECISION_NOT_AVAILABLE` | the 071 result has no decision; the default laboratory path |
| `DECISION_INPUT_NOT_AVAILABLE` | the 071 result is missing |
| `DECISION_BLOCKED` | missing tenant or untrusted true flag |
| `DECISION_REQUIRES_VERIFICATION_RESULT` | a verification-result check was attempted without a real result |
| `DECISION_REQUIRES_VERIFIED_EVIDENCE` | an evidence check was attempted without verified evidence |
| `DECISION_REQUIRES_REAL_POLICY_PROVIDER` | a policy-provider check was attempted without a real provider |
| `DECISION_REQUIRES_REAL_AUTHORIZATION` | an authorization check remains required |
| `DECISION_REQUIRES_HUMAN_REVIEW` | a human-review check remains required |

## Deny-by-default

```text
missing 071 result → input not available
untrusted true flag → block
missing tenant → block
verification-result check without result → requires verification result
evidence check without evidence → requires verified evidence
policy-provider check without provider → requires real policy provider
authorization check → requires real authorization
human-review check → requires human review
decision not available → not available
```

Query parameters and headers such as `?verificationApproved=true` do not change the verdict.

## Security invariants

Every result keeps:

```text
decisionAvailable = false
decisionEvaluated = false
verificationInputAccepted = false
verificationEvidenceAccepted = false
verificationDecisionAvailable = false
verificationDecisionProviderConfigured = false
verificationApproved = false
executionVerified = false
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
  "status": "VERIFICATION_DECISION_NOT_AVAILABLE",
  "decisionAvailable": false,
  "decisionEvaluated": false,
  "verificationInputAccepted": false,
  "verificationEvidenceAccepted": false,
  "verificationDecisionAvailable": false,
  "verificationDecisionProviderConfigured": false,
  "verificationApproved": false,
  "clinicalDataAccessGranted": false,
  "clinicalDataAccessAllowed": false,
  "clinicalDataAccessEnforced": false,
  "requiresHumanReview": true
}
```

## Surfaces

- Lab HTML: `GET /lab/ai-consumer-clinical-data-enforcement-verification-decision`
- Lab JSON: `GET /api/ai-consumer-clinical-data-enforcement-verification-decision/v1`
- Epic confirmation: `GET /epic/sandbox/fhir/clinical-projection` adds `aiConsumerClinicalDataEnforcementVerificationDecision=VERIFICATION_DECISION_NOT_AVAILABLE` without replacing the 066–071 lines

Epic 072 field names do not reuse the 071 `aiConsumerVerificationDecisionAvailable` line. The 072 decision flags use `aiConsumerDecisionAvailable` and `aiConsumerEnforcementVerificationDecisionAvailable`.

## Prohibited dependencies

The `aiconsumerenforcementverificationdecision` core may import only `AiConsumerClinicalDataEnforcementExecutionVerificationResult` from Task 071. It must not import HAPI FHIR, vendors, HTTP clients, OAuth, JWT, SMART, LLM, RAG, LangGraph, or `ai-service`.

There is no real policy provider. There is no evidence store. There is no FHIR read.

## Limitations

- No real verification decision
- No real policy engine
- No real authorization provider
- No OAuth, JWT, or SMART change
- No FHIR read
- No handoff or dispatch
- No model execution

A later task may add a real policy engine or explicit human approval. That work is not Task 072.
