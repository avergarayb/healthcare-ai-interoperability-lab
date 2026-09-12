# AI Consumer Authorization Boundary

Task 065 adds a deny-by-default consumer authentication and authorization boundary after handoff authorization. This file lives under `docs/fhir` only for laboratory documentation layout. Task 065 does not process FHIR and does not implement real authentication or authorization.

## Purpose

```text
AiHandoffAuthorizationResult
        +
synthetic ConsumerSecurityContext
        ↓
AiConsumerAuthorizationBoundary
        ↓
AUTHORIZATION_NOT_IMPLEMENTED | BLOCKED | HUMAN_REVIEW_REQUIRED | NOT_AUTHENTICATED | NOT_AUTHORIZED
```

A declared consumer identity is not authentication. Authentication is not authorization. Authorization is not handoff.

## Distinctions

| Layer | Meaning |
|---|---|
| Identity claimed | a synthetic identifier or type is present |
| Authentication verified | a trusted provider confirmed the consumer; not implemented |
| Authorization granted | an authenticated consumer may perform an operation; not implemented |
| Handoff authorized | permission to send the contract; stays `false` |
| Dispatch executed | the contract was sent; stays `false` |

```text
consumerIdentifierPresent ≠ authenticationVerified
authenticationVerified ≠ authorizationGranted
authorizationGranted ≠ handoffAuthorized
handoffAuthorized ≠ dispatchPerformed
```

Task 065 never produces `AUTHORIZED`, `HANDOFF_AUTHORIZED`, `DISPATCHED`, or `MODEL_AUTHORIZED`.

## Input

The only permitted input is an `AiHandoffAuthorizationResult` plus a synthetic `ConsumerSecurityContext`.

The context may record abstract flags such as `contextPresent`, `authenticationMechanism`, `authenticationVerified`, `consumerIdentifierPresent`, `requestedScope`, and `tenantContextPresent`. Those flags are untrusted. The consumer cannot supply `authenticated=true` or `authorized=true` to obtain permission.

The input never includes FHIR JSON, Bundles, Patient IDs, tokens, JWT, vendor DTOs, prompts, model output, or clinical values.

## Statuses

| Status | Meaning |
|---|---|
| `AUTHORIZATION_NOT_IMPLEMENTED` | no real provider exists; the default laboratory path |
| `BLOCKED` | missing input, unexpected true flag, untrusted assertion, or missing tenant |
| `HUMAN_REVIEW_REQUIRED` | the standing human-review flag was turned off |
| `NOT_AUTHENTICATED` | an identity was claimed without a trusted verification |
| `NOT_AUTHORIZED` | a scope was claimed without verified authorization |

## Reason codes

`MISSING_HANDOFF_AUTHORIZATION_RESULT`, `HANDOFF_NOT_AUTHORIZED`, `UNEXPECTED_HANDOFF_AUTHORIZATION`, `REAL_AUTHENTICATION_AUTHORIZATION_NOT_IMPLEMENTED`, `CONSUMER_IDENTITY_NOT_VERIFIED`, `UNTRUSTED_AUTHENTICATION_ASSERTION`, `UNTRUSTED_AUTHORIZATION_ASSERTION`, `SCOPE_NOT_VERIFIED`, `MISSING_TENANT_CONTEXT`, `HUMAN_REVIEW_FLAG_MISSING`.

`handoffAuthorized=true` on the input is blocked. It is not copied onto the result.

`authenticationVerified=true` or `authorizationGranted=true` without a real provider is blocked.

`ai.handoff.request` may appear as a conceptual scope. It is never granted.

## Deny-by-default

```text
missing authentication → deny
missing authorization → deny
missing tenant → deny
missing scope verification → deny
synthetic assertion → deny
unexpected true flag → block
```

Query parameters and headers such as `?authorized=true`, `X-Authorized`, or `X-Allow-Handoff` do not change the verdict.

## Security invariants

Every result keeps:

```text
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

`consumerAuthorizationAvailable` means a real authorization implementation exists. A synthetic context does not make it `true`.

## Architectural boundary

```text
aiconsumerauthorization → aihandoffauthorization
```

The core does not import `FhirService`, routing, vendors, HAPI, SMART internals, snapshot, projection, pipeline, agent, agentstub, aiboundary, firstai, aigateway, aiconsumer, aiconsumerpolicy, or aiconsumerreadiness.

The laboratory controller may assemble the existing 057–064 chain and then hand the 064 result to this boundary. That assembly is not part of the authorization core.

Those upstream packages do not import this package.

## What this task does not do

- OAuth2, OIDC, JWT, JWKS, SMART, PKCE, mTLS
- Identity providers, client registration, token introspection
- HTTP calls to an `ai-service`
- Handoff or dispatch
- Model execution
- Clinical output

## Laboratory surfaces

- Confirmation: `GET /epic/sandbox/fhir/clinical-projection`
- Lab HTML: `GET /lab/ai-consumer-authorization`
- Lab JSON: `GET /api/ai-consumer-authorization/v1`

Those routes are laboratory surfaces. They are not a public authentication API.

On the Epic page the added blind fields are:

```text
aiConsumerAuthentication=NOT_AUTHENTICATED
aiConsumerAuthorization=AUTHORIZATION_NOT_IMPLEMENTED
aiConsumerAuthorizationAvailable=false
```

## Next steps outside this task

Task 066 adds a deny-by-default consent and purpose boundary over this result. See [ai-consumer-consent-boundary.md](ai-consumer-consent-boundary.md). Consumer authorization remains unimplemented.

A later task may add a real identity provider, verified scopes, or a later handoff decision. That work is not Task 065. `AUTHORIZATION_NOT_IMPLEMENTED` must stay the default until those controls exist.
