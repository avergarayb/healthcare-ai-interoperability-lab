# AI Consumer Enforcement Verification Approval Boundary

Task 073 adds a deny-by-default enforcement verification-approval boundary after a verification decision. This file lives under `docs/fhir` only for laboratory documentation layout. Task 073 does not process FHIR and does not approve clinical access.

## Purpose

```text
AiConsumerVerificationDecisionResult
        +
synthetic ClinicalDataEnforcementVerificationApprovalContext
        ↓
AiConsumerEnforcementVerificationApprovalBoundary
        ↓
VERIFICATION_APPROVAL_NOT_AVAILABLE
  | BLOCKED
  | HUMAN_REVIEW_REQUIRED
  | NOT_ELIGIBLE_FOR_APPROVAL
```

A verification decision is not an approval. An approval is not a clinical grant and is not a FHIR read.

## Relation to Task 072

Task 072 decides that a verification decision is not available. Task 073 consumes only that result and asks:

> Can the verification decision be approved?

The live answer is no.

## Distinctions

```text
decisión de verificación ≠ aprobación de verificación
aprobación sintética ≠ acceso clínico concedido
claims sintéticos ≠ evidencia confiable
```

Task 073 never produces `APPROVED`, `GRANTED`, or `VERIFIED`.

## Deny-by-default

```text
missing 072 result → blocked
missing context → blocked
untrusted approval claim → human review required
decision-availability check → blocked
decision-evaluated check → blocked
human-review claim → human review required
evidence check → blocked
live laboratory path → approval not available
```

Query parameters and headers such as `?verificationApproved=true` do not change the verdict.

## Security invariants

```text
verificationApprovalAvailable = false
verificationApprovalEvaluated = false
verificationApproved = false
approvalEvidenceEvaluated = false
approvalPolicyEvaluated = false
approvalHumanReviewRequired = true
clinicalDataAccessGranted = false
executionVerified = false
requiresHumanReview = true
```

## Surfaces

- Lab HTML: `GET /lab/ai-consumer-enforcement-verification-approval`
- Lab JSON: `GET /api/ai-consumer-enforcement-verification-approval/v1`
- Epic confirmation: `GET /epic/sandbox/fhir/clinical-projection` adds `aiConsumerEnforcementVerificationApproval=VERIFICATION_APPROVAL_NOT_AVAILABLE`

## Limitations

There is no real policy engine, approval store, authorization provider, or FHIR read.

Task 073 is the last synthetic deny-by-default gate in this chain. The next work, if any, should be a real isolated integration, not another `*_NOT_AVAILABLE` boundary.
