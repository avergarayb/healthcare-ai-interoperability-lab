# AI Consumer Data Scope Boundary

Task 067 adds a deny-by-default clinical data-scope and minimization boundary after consent. This file lives under `docs/fhir` only for laboratory documentation layout. Task 067 does not process FHIR and does not grant clinical access.

## Purpose

```text
AiConsumerConsentResult
        +
synthetic ConsumerDataScopeContext
        ↓
AiConsumerDataScopeBoundary
        ↓
NOT_READY_FOR_CLINICAL_DATA_ACCESS | DATA_SCOPE_NOT_DECLARED | DATA_SCOPE_DECLARED_NOT_EVALUATED | SCOPE_BLOCKED
```

A declared scope is not an evaluated scope. Synthetic minimization is not clinical access. Purpose-scope alignment declared is not approved.

## Distinctions

| Layer | Meaning |
|---|---|
| Scope declared | synthetic categories or resource-type names are present |
| Scope evaluated | a trusted provider assessed the scope; stays `false` |
| Minimization evaluated | the scope was checked against the purpose; stays `false` |
| Alignment evaluated | purpose and scope were verified together; stays `false` |
| Clinical data access allowed | FHIR or clinical records may be read; stays `false` |

```text
data scope declared ≠ data scope approved
data minimization evaluated ≠ clinical access granted
necesidad declarada ≠ necesidad verificada
alcance sintético ≠ lectura FHIR
```

Task 067 never produces `DATA_SCOPE_APPROVED`, `CLINICAL_DATA_ACCESS_GRANTED`, or `CLINICAL_DATA_ACCESS_ALLOWED`.

## Input

The only permitted input is an `AiConsumerConsentResult` plus a synthetic `ConsumerDataScopeContext`.

The context may record abstract categories such as `CONDITION_SUMMARY` or `ENCOUNTER_SUMMARY`. Those values are untrusted. They do not trigger FHIR reads.

The input never includes FHIR JSON, Bundles, Patient IDs, tokens, signatures, vendor DTOs, prompts, model output, or clinical values.

## Statuses

| Status | Meaning |
|---|---|
| `NOT_READY_FOR_CLINICAL_DATA_ACCESS` | consent is unimplemented; the default laboratory path |
| `DATA_SCOPE_NOT_DECLARED` | a scope evaluation was attempted without categories |
| `DATA_SCOPE_DECLARED_NOT_EVALUATED` | synthetic categories exist and are not approved |
| `SCOPE_BLOCKED` | missing input, missing tenant, or untrusted true flag |
| `PURPOSE_SCOPE_ALIGNMENT_NOT_VERIFIED` | purpose remains unapproved |
| `MINIMIZATION_NOT_EVALUATED` | reserved; minimization never completes |
| `SCOPE_REQUIRES_HUMAN_REVIEW` | reserved deny state |

## Deny-by-default

```text
missing consent result → block
consent unavailable → not ready
missing tenant → block
empty explicit declaration → not declared
synthetic categories → declared, not evaluated
untrusted true flag → block
```

Query parameters and headers such as `?clinicalDataAccessAllowed=true` or `X-Scope-Approved` do not change the verdict.

## Security invariants

Every result keeps:

```text
scopeEvaluated = false
minimizationEvaluated = false
purposeScopeAlignmentEvaluated = false
clinicalDataScopeProviderConfigured = false
clinicalDataScopeApprovalAvailable = false
clinicalDataAccessRequested = false
clinicalDataAccessGranted = false
clinicalDataAccessAllowed = false
consentVerified = false
purposeApproved = false
dataScopeApproved = false
consentAvailable = false
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
requiresHumanReview = true
```

## Architectural boundary

```text
aiconsumerscope → aiconsumerconsent
```

The core does not import `FhirService`, routing, vendors, HAPI, SMART internals, snapshot, projection, pipeline, agent, aiboundary, firstai, aigateway, aiconsumer, aiconsumerpolicy, aiconsumerreadiness, aihandoffauthorization, or aiconsumerauthorization.

The laboratory controller may assemble the existing 057–066 chain and then hand the 066 result to this boundary.

## Laboratory surfaces

- Confirmation: `GET /epic/sandbox/fhir/clinical-projection`
- Lab HTML: `GET /lab/ai-consumer-data-scope`
- Lab JSON: `GET /api/ai-consumer-data-scope/v1`

On the Epic page the added blind fields are:

```text
aiConsumerClinicalDataScope=NOT_READY_FOR_CLINICAL_DATA_ACCESS
aiConsumerScopeDeclared=false
aiConsumerScopeEvaluated=false
aiConsumerMinimizationEvaluated=false
aiConsumerPurposeScopeAlignmentEvaluated=false
aiClinicalDataScopeProviderConfigured=false
aiClinicalDataScopeApprovalAvailable=false
aiClinicalDataAccessRequested=false
aiClinicalDataAccessGranted=false
aiClinicalDataAccessAllowed=false
```

The 066 line `aiConsumerDataScope=DATA_SCOPE_NOT_VERIFIED` stays. It is the consent-layer abstract scope, not this clinical-scope boundary.

## What this task does not do

- Real minimization or legal review
- FHIR reads
- OAuth, JWT, SMART
- Handoff or dispatch
- Model execution

A later task may add a real scope provider. That work is not Task 067.
