# AI Consumer Clinical Data Enforcement Boundary

Task 069 adds a deny-by-default clinical data-access enforcement decision boundary after an access request. This file lives under `docs/fhir` only for laboratory documentation layout. Task 069 does not process FHIR and does not enforce clinical access.

## Purpose

```text
AiConsumerClinicalDataAccessResult
        +
synthetic ClinicalDataEnforcementContext
        ↓
AiConsumerClinicalDataEnforcementBoundary
        ↓
NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS
  | ENFORCEMENT_INPUT_NOT_AVAILABLE
  | ENFORCEMENT_BLOCKED
  | ENFORCEMENT_REQUIRES_ACCESS_DECISION
  | ENFORCEMENT_REQUIRES_REAL_AUTHORIZATION
  | ENFORCEMENT_REQUIRES_HUMAN_REVIEW
  | ENFORCEMENT_NOT_AVAILABLE
```

A request is not an enforcement decision. An enforcement decision is not a grant. A grant is not a FHIR read.

## Relation to Task 068

Task 068 decides that a declared access request is not granted. Task 069 consumes only that result and asks a narrower question:

> Is there a sufficient basis for a future real enforcement decision?

It does not ask whether clinical access is granted or applied.

## Distinctions

| Layer | Meaning |
|---|---|
| Access request | synthetic request metadata from Task 068 |
| Enforcement decision available | a trusted provider can decide; stays `false` |
| Enforcement decision evaluated | a trusted provider assessed the decision; stays `false` |
| Clinical data access granted | a trusted provider issued access; stays `false` |
| Clinical data access enforced | the verdict became a permission; stays `false` |

```text
solicitud de acceso ≠ decisión de enforcement
decisión sintética ≠ concesión de acceso
concesión de acceso ≠ lectura FHIR
enforcement sintético ≠ acceso clínico
```

Task 069 never produces `CLINICAL_DATA_ACCESS_GRANTED`, `CLINICAL_DATA_ACCESS_ENFORCED`, or `ENFORCEMENT_APPROVED`.

## Input

The only permitted input is an `AiConsumerClinicalDataAccessResult` plus a synthetic `ClinicalDataEnforcementContext`.

The context may record a pending request reference or an authorization-evaluation attempt. Those values are untrusted. They do not trigger FHIR reads, tokens, or OAuth.

The input never includes FHIR JSON, Bundles, Patient IDs, tokens, signatures, vendor DTOs, prompts, model output, or clinical values.

## Statuses

| Status | Meaning |
|---|---|
| `NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS` | the 068 access result is not granted; the default laboratory path |
| `ENFORCEMENT_INPUT_NOT_AVAILABLE` | the 068 result is missing |
| `ENFORCEMENT_BLOCKED` | missing tenant or untrusted true flag |
| `ENFORCEMENT_REQUIRES_ACCESS_DECISION` | a request exists without a real access decision |
| `ENFORCEMENT_REQUIRES_REAL_AUTHORIZATION` | an authorization check was attempted without a real provider |
| `ENFORCEMENT_REQUIRES_HUMAN_REVIEW` | reserved deny state |
| `ENFORCEMENT_NOT_AVAILABLE` | reserved deny state |

## Deny-by-default

```text
missing 068 result → input not available
untrusted true flag → block
missing tenant → block
pending request → requires access decision
authorization check without provider → requires real authorization
access not granted → not enforced
```

Query parameters and headers such as `?clinicalDataAccessEnforced=true` or `X-Enforcement-Approved` do not change the verdict.

## Security invariants

Every result keeps:

```text
enforcementDecisionAvailable = false
enforcementDecisionEvaluated = false
clinicalDataAccessEnforcementAvailable = false
clinicalDataAccessEnforcementProviderConfigured = false
clinicalDataAccessEnforcementExecuted = false
clinicalDataAccessGranted = false
clinicalDataAccessAllowed = false
clinicalDataAccessEnforced = false
realAuthorizationRequired = true
requiresHumanReview = true
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
```

## Example (no clinical data)

```json
{
  "boundaryVersion": "v1",
  "status": "NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS",
  "enforcementDecisionAvailable": false,
  "enforcementDecisionEvaluated": false,
  "realAuthorizationRequired": true,
  "clinicalDataAccessGranted": false,
  "clinicalDataAccessAllowed": false,
  "clinicalDataAccessEnforcementAvailable": false,
  "clinicalDataAccessEnforced": false,
  "clinicalDataAccessEnforcementProviderConfigured": false,
  "requiresHumanReview": true
}
```

## Surfaces

- Lab HTML: `GET /lab/ai-consumer-clinical-data-enforcement`
- Lab JSON: `GET /api/ai-consumer-clinical-data-enforcement/v1`
- Epic confirmation: `GET /epic/sandbox/fhir/clinical-projection` adds `aiConsumerClinicalDataEnforcement=NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS` without replacing the 066 `aiConsumerDataScope`, 067 `aiConsumerClinicalDataScope`, or 068 `aiConsumerClinicalDataAccess` lines

## Prohibited dependencies

The `aiconsumerenforcement` core may import only `AiConsumerClinicalDataAccessResult` from Task 068. It must not import HAPI FHIR, vendors, HTTP clients, OAuth, JWT, SMART, LLM, RAG, LangGraph, or `ai-service`.

There is no real enforcement provider. There is no FHIR read.

## Limitations

- No real enforcement provider
- No real authorization provider
- No OAuth, JWT, or SMART change
- No FHIR read
- No handoff or dispatch
- No model execution

A later task may add a real enforcement provider. That work is not Task 069.
