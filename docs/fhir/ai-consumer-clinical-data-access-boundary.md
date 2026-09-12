# AI Consumer Clinical Data Access Boundary

Task 068 adds a deny-by-default clinical data-access request and enforcement boundary after data scope. This file lives under `docs/fhir` only for laboratory documentation layout. Task 068 does not process FHIR and does not grant clinical access.

## Purpose

```text
AiConsumerDataScopeResult
        +
synthetic ClinicalDataAccessRequestContext
        ↓
AiConsumerClinicalDataAccessBoundary
        ↓
NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS
  | ACCESS_REQUEST_NOT_DECLARED
  | ACCESS_REQUEST_DECLARED_NOT_EVALUATED
  | ACCESS_REQUEST_REQUIRES_SCOPE
  | ACCESS_REQUEST_REQUIRES_REAL_AUTHORIZATION
  | ACCESS_REQUEST_BLOCKED
  | ACCESS_REQUEST_REQUIRES_HUMAN_REVIEW
```

A declared request is not an evaluated request. An effective synthetic request is not a grant. A grant is not a FHIR read.

## Relation to Task 067

Task 067 decides that a declared scope is not ready for clinical data access. Task 068 consumes only that result and asks a narrower question:

> Is there a declared, sufficiently defined request for a future access evaluation?

It does not ask whether clinical access is granted.

## Distinctions

| Layer | Meaning |
|---|---|
| Access request declared | synthetic request metadata is present |
| Access request evaluated | a trusted provider assessed the request; stays `false` |
| Clinical data access requested | an effective request claim was recorded; still not a grant |
| Clinical data access granted | a trusted provider issued access; stays `false` |
| Clinical data access allowed | FHIR or clinical records may be read; stays `false` |
| Enforcement | the verdict became a permission; stays `false` |

```text
alcance declarado ≠ solicitud de acceso
solicitud declarada ≠ solicitud evaluada
solicitud efectiva ≠ acceso concedido
acceso concedido ≠ lectura FHIR
```

Task 068 never produces `CLINICAL_DATA_ACCESS_GRANTED`, `CLINICAL_DATA_ACCESS_ALLOWED`, or `FHIR_ACCESS_ENABLED`.

## Input

The only permitted input is an `AiConsumerDataScopeResult` plus a synthetic `ClinicalDataAccessRequestContext`.

The context may record a declared request or an effective synthetic request. Those values are untrusted. They do not trigger FHIR reads, tokens, or OAuth.

The input never includes FHIR JSON, Bundles, Patient IDs, tokens, signatures, vendor DTOs, prompts, model output, or clinical values.

## Statuses

| Status | Meaning |
|---|---|
| `NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS` | the 067 scope is not prepared; the default laboratory path |
| `ACCESS_REQUEST_NOT_DECLARED` | a request evaluation was attempted without a declaration |
| `ACCESS_REQUEST_DECLARED_NOT_EVALUATED` | a synthetic request exists and is not approved |
| `ACCESS_REQUEST_REQUIRES_SCOPE` | a request exists without a scope reference |
| `ACCESS_REQUEST_REQUIRES_REAL_AUTHORIZATION` | an effective synthetic request still needs a real provider |
| `ACCESS_REQUEST_BLOCKED` | missing input, missing tenant, or untrusted true flag |
| `ACCESS_REQUEST_REQUIRES_HUMAN_REVIEW` | reserved deny state when consent or purpose remain unverified |

## Deny-by-default

```text
missing 067 result → block
untrusted true flag → block
missing tenant → block
request without scope → requires scope
declared request → declared, not evaluated
effective synthetic request → requested, not granted
empty explicit declaration → not declared
scope not prepared → not granted
```

Query parameters and headers such as `?clinicalDataAccessAllowed=true`, `?clinicalDataAccessGranted=true`, or `X-Clinical-Data-Access` do not change the verdict.

## Security invariants

Every result keeps:

```text
accessRequestEvaluated = false
clinicalDataAccessGrantAvailable = false
clinicalDataAccessEnforced = false
clinicalDataAccessProviderConfigured = false
clinicalDataAccessAuthorizationAvailable = false
clinicalDataAccessGranted = false
clinicalDataAccessAllowed = false
realAuthorizationRequired = true
requiresHumanReview = true
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
```

The default laboratory path also keeps `clinicalDataAccessRequested=false`. A synthetic effective-request case may set that flag to `true` only to show that a request is still not a grant.

## Example (no clinical data)

```json
{
  "boundaryVersion": "v1",
  "status": "NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS",
  "accessRequestDeclared": false,
  "accessRequestEvaluated": false,
  "scopeReferencePresent": false,
  "realAuthorizationRequired": true,
  "clinicalDataAccessRequested": false,
  "clinicalDataAccessGranted": false,
  "clinicalDataAccessAllowed": false,
  "clinicalDataAccessGrantAvailable": false,
  "clinicalDataAccessEnforced": false,
  "requiresHumanReview": true
}
```

## Surfaces

- Lab HTML: `GET /lab/ai-consumer-clinical-data-access`
- Lab JSON: `GET /api/ai-consumer-clinical-data-access/v1`
- Epic confirmation: `GET /epic/sandbox/fhir/clinical-projection` adds `aiConsumerClinicalDataAccess=NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS` without replacing the 066 `aiConsumerDataScope` or 067 `aiConsumerClinicalDataScope` lines

## Prohibited dependencies

The `aiconsumeraccess` core may import only `AiConsumerDataScopeResult` from Task 067. It must not import HAPI FHIR, vendors, HTTP clients, OAuth, JWT, SMART, LLM, RAG, LangGraph, or `ai-service`.

There is no real clinical-access provider. There is no FHIR read.

## Limitations

- No real authorization provider
- No consent verification
- No OAuth, JWT, or SMART change
- No FHIR read
- No handoff or dispatch
- No model execution

A later task may add a real access provider. That work is not Task 068.
