# AI Consumer Consent Boundary

Task 066 adds a deny-by-default consent and purpose-of-use boundary after consumer authorization. This file lives under `docs/fhir` only for laboratory documentation layout. Task 066 does not process FHIR and does not implement real consent.

## Purpose

```text
AiConsumerAuthorizationResult
        +
synthetic ConsumerConsentContext
        ↓
AiConsumerConsentBoundary
        ↓
CONSENT_NOT_IMPLEMENTED | PURPOSE_NOT_VERIFIED | DATA_SCOPE_NOT_VERIFIED | BLOCKED | HUMAN_REVIEW_REQUIRED | NOT_ELIGIBLE_FOR_CONSUMPTION
```

Consumer authentication is not authorization. Authorization is not consent. Consent is not purpose approval. Purpose is not clinical access.

## Distinctions

| Layer | Meaning |
|---|---|
| Consent context present | a synthetic envelope exists |
| Consent verified | a trusted provider confirmed consent; not implemented |
| Purpose declared | a conceptual use is named |
| Purpose approved | that use was accepted; not implemented |
| Data scope approved | an abstract scope was accepted; not implemented |
| Clinical data access allowed | FHIR or clinical records may be read; stays `false` |
| Handoff authorized | permission to send the contract; stays `false` |

```text
consentReferencePresent ≠ consentVerified
purposeDeclared ≠ purposeApproved
authorization available ≠ clinical data access allowed
consent evaluated ≠ handoff authorized
```

Task 066 never produces `CONSENT_GRANTED`, `PURPOSE_APPROVED`, `DATA_ACCESS_ALLOWED`, `HANDOFF_AUTHORIZED`, `DISPATCHED`, or `MODEL_AUTHORIZED`.

## Input

The only permitted input is an `AiConsumerAuthorizationResult` plus a synthetic `ConsumerConsentContext`.

The context may record abstract flags such as `contextPresent`, `consentReferencePresent`, `consentVerified`, `requestedPurpose`, `requestedDataScope`, and `tenantContextPresent`. Those flags are untrusted. The consumer cannot supply `consentVerified=true` or `purposeApproved=true` to obtain permission.

The input never includes FHIR JSON, Bundles, Patient IDs, tokens, signatures, consent documents, vendor DTOs, prompts, model output, or clinical values.

## Statuses

| Status | Meaning |
|---|---|
| `CONSENT_NOT_IMPLEMENTED` | no real consent provider exists; the default laboratory path |
| `PURPOSE_NOT_VERIFIED` | a purpose is missing or not approved |
| `DATA_SCOPE_NOT_VERIFIED` | an abstract data scope is missing |
| `BLOCKED` | missing input, unexpected true flag, untrusted assertion, or missing tenant |
| `HUMAN_REVIEW_REQUIRED` | the consent review step is not completed |
| `NOT_ELIGIBLE_FOR_CONSUMPTION` | reserved deny state; not used as permission |

## Reason codes

`MISSING_CONSUMER_AUTHORIZATION_RESULT`, `CONSUMER_AUTHORIZATION_NOT_AVAILABLE`, `UNEXPECTED_CONSUMER_AUTHORIZATION`, `MISSING_CONSENT_CONTEXT`, `CONSENT_REFERENCE_NOT_VERIFIED`, `UNTRUSTED_CONSENT_ASSERTION`, `MISSING_PURPOSE`, `PURPOSE_NOT_APPROVED`, `UNKNOWN_OR_MISSING_PURPOSE`, `UNTRUSTED_PURPOSE_ASSERTION`, `MISSING_DATA_SCOPE`, `UNTRUSTED_DATA_SCOPE_ASSERTION`, `MISSING_TENANT_CONTEXT`, `HUMAN_REVIEW_NOT_COMPLETED`.

`authorizationGranted=true` or `consumerAuthorizationAvailable=true` on the input is blocked. Those values are not copied onto the result.

`consentVerified=true`, `purposeApproved=true`, or `dataScopeApproved=true` without a real provider is blocked.

Conceptual purposes (`FOLLOW_UP_SUPPORT`, `CLINICAL_SUMMARY_REVIEW`, `RESEARCH`, and the rest) never grant access.

Abstract data scopes (`SUMMARY_METADATA`, `NON_CLINICAL_STATUS`, `SYNTHETIC_DEMO_CONTEXT`) never grant a FHIR read.

## Deny-by-default

```text
missing consent → deny
missing purpose → deny
missing data scope → deny
synthetic assertion → block
missing tenant → block
human review pending → human review required
```

Query parameters and headers such as `?consent=true`, `X-Consent-Verified`, or `X-Allow-Clinical-Access` do not change the verdict.

## Security invariants

Every result keeps:

```text
consentVerified = false
purposeApproved = false
dataScopeApproved = false
consentProviderConfigured = false
consentAvailable = false
clinicalDataAccessAllowed = false
authenticationVerified = false
authorizationGranted = false
realSecurityProviderConfigured = false
consumerAuthorizationAvailable = false
handoffAuthorized = false
dispatchPerformed = false
externalAuthorizationAvailable = false
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
requiresHumanReview = true
```

`consentAvailable` means a real consent implementation exists. A synthetic context does not make it `true`.

## Architectural boundary

```text
aiconsumerconsent → aiconsumerauthorization
```

The core does not import `FhirService`, routing, vendors, HAPI, SMART internals, snapshot, projection, pipeline, agent, agentstub, aiboundary, firstai, aigateway, aiconsumer, aiconsumerpolicy, aiconsumerreadiness, or aihandoffauthorization.

The laboratory controller may assemble the existing 057–065 chain and then hand the 065 result to this boundary. That assembly is not part of the consent core.

Those upstream packages do not import this package.

## What this task does not do

- Real consent, consent documents, signatures
- External consent providers
- OAuth2, OIDC, JWT, SMART
- HTTP calls to an `ai-service`
- Handoff or dispatch
- Model execution
- Clinical output

## Laboratory surfaces

- Confirmation: `GET /epic/sandbox/fhir/clinical-projection`
- Lab HTML: `GET /lab/ai-consumer-consent`
- Lab JSON: `GET /api/ai-consumer-consent/v1`

Those routes are laboratory surfaces. They are not a public consent API.

On the Epic page the added blind fields are:

```text
aiConsumerConsent=CONSENT_NOT_IMPLEMENTED
aiConsumerPurpose=PURPOSE_NOT_VERIFIED
aiConsumerDataScope=DATA_SCOPE_NOT_VERIFIED
aiConsumerConsentAvailable=false
aiClinicalDataAccessAllowed=false
```

## Next steps outside this task

A later task may add a real consent provider or a later use-decision. That work is not Task 066. `CONSENT_NOT_IMPLEMENTED` must stay the default until those controls exist.
