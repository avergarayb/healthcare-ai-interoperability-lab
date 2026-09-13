# TASK 072 — AI Consumer Clinical Data Enforcement Verification Decision Boundary

## 1. Position

**Task:** 072  
**Title:** AI Consumer Clinical Data Enforcement Verification Decision Boundary  
**Previous task:** 071 — AI Consumer Clinical Data Enforcement Execution Verification Boundary  
**Suggested branch:** `feature/ai-consumer-clinical-data-enforcement-verification-decision-boundary`  
**Suggested commit:** `feat: add ai consumer clinical data enforcement verification decision boundary`  
**Service:** `fhir-integration-service`  
**Root package:** `lab.healthcare.fhir`  
**Suggested package:** `lab.healthcare.fhir.aiconsumerenforcementverificationdecision`

This task must implement **one isolated, synthetic, deny-by-default decision boundary** after Task 071.

It must not implement real verification, real authorization, FHIR reads, model calls, dispatch, handoff, or any external integration.

---

## 2. Objective

Create a deterministic boundary that receives only the immediate result of Task 071:

```text
AiConsumerClinicalDataEnforcementExecutionVerificationResult
```

The boundary must produce a new result representing whether a verification decision is available for future policy consideration.

The expected live outcome is:

```text
VERIFICATION_DECISION_NOT_AVAILABLE
```

The implementation must make the distinction explicit:

```text
verification result
    ≠
verification decision
```

and:

```text
synthetic decision boundary
    ≠
authorization to access clinical data
```

Task 072 must not convert an unavailable or unverified result into an approval.

---

## 3. Scope

### Included

- A new isolated package.
- A result object for verification-decision status.
- A deterministic `Boundary` component.
- A synthetic, untrusted decision context if required by the existing pattern.
- A controller/web adapter.
- Oracle-backed JSON surface.
- Blind fields on the existing Epic clinical projection endpoint.
- Unit, architecture, controller, and non-regression tests.
- Documentation and progress-log update.

### Excluded

- Real verification provider.
- Real evidence store.
- Real policy engine.
- Real authorization or consent provider.
- OAuth, JWT, SMART, Epic, Oracle, or external identity integration.
- FHIR reads or writes.
- HAPI FHIR imports.
- LLM, RAG, LangGraph, `ai-service`, or model invocation.
- RabbitMQ, WebClient, Feign, RestClient, or external HTTP clients.
- Dispatch, handoff, or contract transmission.
- Changes to Tasks 057–071.
- Changes to the clinical contract v1.
- Changes to allowlist 042.
- Changes to `.env`.

---

## 4. Input contract

The core package may consume **only**:

```text
AiConsumerClinicalDataEnforcementExecutionVerificationResult
```

This is the immediate result of Task 071.

The core package must not import:

- `AiConsumerClinicalDataEnforcementExecutionResult`
- `AiConsumerClinicalDataEnforcementResult`
- `AiConsumerClinicalDataAccessResult`
- `AiConsumerDataScopeResult`
- `AiConsumerConsentResult`
- `AiConsumerAuthorizationResult`
- `AiHandoffAuthorizationResult`
- `AiConsumerReadinessResult`
- `AiConsumerPolicyResult`
- `AiConsumerContract`
- `AiExecutionDecision`
- `FirstAiResult`
- `AiBoundaryResult`
- `DeterministicAgent`
- Model Boundary v1 classes

The web/controller layer may assemble the existing chain, following the established 065–071 pattern. The domain/core boundary must remain isolated.

---

## 5. Suggested output contract

Create:

```text
AiConsumerClinicalDataEnforcementVerificationDecisionResult
```

Suggested fields:

```text
String status
boolean decisionAvailable
boolean decisionEvaluated
boolean verificationInputAccepted
boolean verificationEvidenceAccepted
boolean verificationDecisionAvailable
boolean verificationDecisionProviderConfigured
boolean verificationApproved
boolean clinicalDataAccessEnforced
boolean clinicalDataAccessAllowed
boolean clinicalDataAccessGranted
boolean realAuthorizationRequired
boolean requiresHumanReview
```

The exact naming may follow repository conventions, but it must not overwrite or reuse live names from Tasks 066–071.

Suggested status values:

```text
DECISION_INPUT_NOT_AVAILABLE
DECISION_BLOCKED
DECISION_REQUIRES_VERIFICATION_RESULT
DECISION_REQUIRES_VERIFIED_EVIDENCE
DECISION_REQUIRES_REAL_POLICY_PROVIDER
DECISION_REQUIRES_REAL_AUTHORIZATION
DECISION_REQUIRES_HUMAN_REVIEW
VERIFICATION_DECISION_NOT_AVAILABLE
```

The normal live result must be:

```text
status = VERIFICATION_DECISION_NOT_AVAILABLE
decisionAvailable = false
decisionEvaluated = false
verificationInputAccepted = false
verificationEvidenceAccepted = false
verificationDecisionAvailable = false
verificationDecisionProviderConfigured = false
verificationApproved = false
clinicalDataAccessEnforced = false
clinicalDataAccessAllowed = false
clinicalDataAccessGranted = false
realAuthorizationRequired = true
requiresHumanReview = true
```

---

## 6. Deny-by-default rules

The boundary must reject or block any input that attempts to represent an approval.

If the input or synthetic context contains any of the following as `true`, the boundary must not promote the result:

```text
decisionAvailable
decisionEvaluated
verificationInputAccepted
verificationEvidenceAccepted
verificationDecisionAvailable
verificationDecisionProviderConfigured
verificationApproved
clinicalDataAccessEnforced
clinicalDataAccessAllowed
clinicalDataAccessGranted
```

The result constructor/factory must normalize or reject unsafe positive values so callers cannot manufacture a verification approval through the new boundary.

No positive synthetic context may enable:

```text
verificationApproved
clinicalDataAccessEnforced
clinicalDataAccessAllowed
clinicalDataAccessGranted
modelCallAuthorized
handoffAuthorized
dispatchPerformed
modelCalled
```

The boundary must not infer approval from:

- HTTP 200.
- Presence of a JSON field.
- A synthetic boolean.
- A Task 071 status string.
- A request header.
- A query parameter.
- A declared tenant or clinic identifier.
- A prior readiness or execution state.

The following distinction must remain explicit:

```text
verification decision available
    ≠
verification approved
```

and:

```text
verification approved
    ≠
clinical-data access granted
```

---

## 7. Required invariants

Task 072 must preserve all existing invariants from Tasks 057–071.

### Existing execution and delivery invariants

```text
modelCalled=false
modelCallAuthorized=false
processingStatus=NOT_EXECUTED
dispatchStatus=NOT_DISPATCHED
handoffAuthorized=false
dispatchPerformed=false
requiresHumanReview=true
```

### Existing security and consent invariants

```text
externalAuthorizationAvailable=false
authenticationVerified=false
authorizationGranted=false
realSecurityProviderConfigured=false
consumerAuthorizationAvailable=false

consentVerified=false
purposeApproved=false
dataScopeApproved=false
consentProviderConfigured=false
consentAvailable=false
```

### Existing scope and access invariants

```text
scopeEvaluated=false
minimizationEvaluated=false
purposeScopeAlignmentEvaluated=false
clinicalDataScopeProviderConfigured=false
clinicalDataScopeApprovalAvailable=false

accessRequestEvaluated=false
clinicalDataAccessRequested=false
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessGrantAvailable=false
clinicalDataAccessEnforced=false
clinicalDataAccessProviderConfigured=false
clinicalDataAccessAuthorizationAvailable=false
```

### Task 069 invariants

```text
enforcementDecisionAvailable=false
enforcementDecisionEvaluated=false
clinicalDataAccessEnforcementAvailable=false
clinicalDataAccessEnforcementProviderConfigured=false
clinicalDataAccessEnforcementExecuted=false
```

### Task 070 invariants

```text
executionDecisionAvailable=false
executionDecisionEvaluated=false
enforcementExecutionAvailable=false
enforcementExecutionProviderConfigured=false
enforcementExecutionPerformed=false
```

### Task 071 invariants

```text
verificationDecisionAvailable=false
verificationDecisionEvaluated=false
executionEvidenceAvailable=false
executionEvidenceEvaluated=false
executionVerificationAvailable=false
executionVerificationProviderConfigured=false
executionVerified=false
```

### New Task 072 invariants

```text
decisionAvailable=false
decisionEvaluated=false
verificationInputAccepted=false
verificationEvidenceAccepted=false
verificationDecisionAvailable=false
verificationDecisionProviderConfigured=false
verificationApproved=false
```

All applicable boolean fields must remain `false`, and:

```text
requiresHumanReview=true
```

---

## 8. Required behavior matrix

| Input condition | Expected result |
|---|---|
| Null input | `DECISION_INPUT_NOT_AVAILABLE` |
| Missing Task 071 result | `DECISION_INPUT_NOT_AVAILABLE` |
| Task 071 live deny-by-default result | `VERIFICATION_DECISION_NOT_AVAILABLE` |
| Verification result unavailable | `DECISION_REQUIRES_VERIFICATION_RESULT` |
| Execution verification unavailable | `DECISION_REQUIRES_VERIFIED_EVIDENCE` |
| Execution not verified | `DECISION_REQUIRES_VERIFIED_EVIDENCE` |
| Real policy provider absent | `DECISION_REQUIRES_REAL_POLICY_PROVIDER` |
| Real authorization still required | `DECISION_REQUIRES_REAL_AUTHORIZATION` |
| Synthetic context claims approval | Block or normalize to deny-by-default |
| Synthetic context claims clinical access | Block or normalize to deny-by-default |
| Missing tenant/clinic context, if applicable | `DECISION_BLOCKED` or equivalent deny state |
| Human review required | `DECISION_REQUIRES_HUMAN_REVIEW` |
| Any positive decision flag | Never produce approval |
| Normal live request | `VERIFICATION_DECISION_NOT_AVAILABLE` |

The implementation must be deterministic and side-effect free.

---

## 9. Suggested implementation structure

```text
lab.healthcare.fhir.aiconsumerenforcementverificationdecision
├── AiConsumerClinicalDataEnforcementVerificationDecisionResult
├── AiConsumerClinicalDataEnforcementVerificationDecisionBoundary
├── AiConsumerClinicalDataEnforcementVerificationDecisionStatus
└── optional synthetic context/value objects
```

Use `*Boundary`, not `*Evaluator`.

Do not introduce a generic framework or refactor previous boundaries.

The boundary should:

1. Validate that the Task 071 result exists.
2. Inspect only the immediate Task 071 result.
3. Detect missing, inconsistent, or unsafe values.
4. Apply deny-by-default rules.
5. Produce the new decision-boundary result.
6. Preserve human review.
7. Avoid all external calls and side effects.
8. Never convert synthetic verification into approval.

---

## 10. Web/API surfaces

Follow the established 065–071 pattern.

### Lab surface

```http
GET /lab/ai-consumer-clinical-data-enforcement-verification-decision
```

### Oracle-backed JSON surface

```http
GET /api/ai-consumer-clinical-data-enforcement-verification-decision/v1
```

The Oracle-backed response must expose the new Task 072 fields and preserve the existing deny-by-default values.

### Epic blind projection fields

Extend the existing response from:

```http
GET /epic/sandbox/fhir/clinical-projection
```

only with blind, non-authorizing Task 072 fields.

Suggested fields:

```text
aiConsumerClinicalDataEnforcementVerificationDecision
aiConsumerDecisionAvailable
aiConsumerDecisionEvaluated
aiConsumerVerificationInputAccepted
aiConsumerVerificationEvidenceAccepted
aiConsumerVerificationDecisionAvailable
aiConsumerVerificationDecisionProviderConfigured
aiConsumerVerificationApproved
```

Expected values:

```text
aiConsumerClinicalDataEnforcementVerificationDecision=VERIFICATION_DECISION_NOT_AVAILABLE
aiConsumerDecisionAvailable=false
aiConsumerDecisionEvaluated=false
aiConsumerVerificationInputAccepted=false
aiConsumerVerificationEvidenceAccepted=false
aiConsumerVerificationDecisionAvailable=false
aiConsumerVerificationDecisionProviderConfigured=false
aiConsumerVerificationApproved=false
```

Do not add clinical resources, FHIR fields, patient data, medication data, or new Epic allowlist entries.

---

## 11. Controller requirements

The controller must:

- Use the existing deterministic assembly pattern.
- Avoid `@RequestParam`.
- Avoid `@RequestHeader`.
- Ignore query parameters.
- Ignore arbitrary headers.
- Not accept tokens, authorization values, tenant overrides, verification evidence, approval flags, or policy decisions from the request.
- Not perform external HTTP calls.
- Not invoke HAPI FHIR.
- Not invoke a model or agent.
- Not mutate shared state.

The endpoint must return the same deterministic result regardless of irrelevant query parameters or headers.

HTTP 200 must not be interpreted as a verification decision or approval.

---

## 12. Tests

### Boundary tests

Cover:

- Valid Task 071 input.
- Null input.
- Missing input.
- Task 071 deny-by-default input.
- Verification result unavailable.
- Execution verification unavailable.
- Execution not verified.
- Real policy provider absent.
- Real authorization required.
- Positive synthetic decision flags.
- Positive synthetic verification flags.
- Positive synthetic clinical-access flags.
- Missing tenant/clinic context, if context is introduced.
- Human review preservation.
- Deterministic repeated evaluation.
- No side effects.
- No inference from HTTP status or status strings.

### Constructor/factory safety tests

Verify that the result cannot be created with effective values for:

```text
decisionAvailable
decisionEvaluated
verificationInputAccepted
verificationEvidenceAccepted
verificationDecisionAvailable
verificationDecisionProviderConfigured
verificationApproved
clinicalDataAccessEnforced
clinicalDataAccessAllowed
clinicalDataAccessGranted
```

### Architecture tests

Verify:

- Core package imports only `AiConsumerClinicalDataEnforcementExecutionVerificationResult` from the previous boundary.
- No imports from Tasks 057–070.
- No HAPI FHIR imports.
- No `FhirContext`.
- No `Patient`, `Bundle`, `Observation`, `Condition`, `Encounter`, or `MedicationRequest`.
- No HTTP client libraries.
- No RabbitMQ.
- No OAuth/JWT/SMART SDKs.
- No LLM, RAG, LangGraph, OpenAI, Azure, Gemini, Claude, or `ai-service`.
- No dependency on `.env`.
- Boundary class is named with `Boundary`, not `Evaluator`.

### Controller tests

Verify:

- Lab endpoint works.
- Oracle-backed JSON endpoint works.
- Query parameters do not alter the result.
- Headers do not alter the result.
- No request-supplied verification evidence can enable approval.
- No request-supplied decision flag can enable approval.
- No request-supplied authorization value can enable access.
- HTTP 200 does not change any decision or approval flag.

### Epic non-regression

Update or add:

```text
EpicSandboxClinicalProjectionControllerTest
```

Verify:

- HTTP 200 remains unchanged.
- Existing clinical projection fields remain unchanged.
- Task 072 blind fields are present.
- All new decision and approval flags remain false.
- No new FHIR resources are returned.
- No Task 072 field enables clinical access.
- No Task 072 field is treated as proof of verification or authorization.

### Expected test evidence

The implementation is acceptable only after:

```text
all tests pass
0 failures
```

Record the exact test count in the progress log after implementation. Do not invent the count in advance.

---

## 13. Documentation

Create:

```text
docs/fhir/ai-consumer-clinical-data-enforcement-verification-decision-boundary.md
```

Document:

- Purpose.
- Position after Task 071.
- Input and output contracts.
- Status values.
- Deny-by-default behavior.
- Difference between verification and decision.
- Difference between decision availability and approval.
- Why synthetic context cannot authorize access.
- Security and clinical-data limitations.
- Explicit non-goals.
- Endpoint surfaces.
- Test coverage.
- Why a real policy provider is not implemented.

Update:

```text
docs/progress/progress-log.md
```

Include:

- Task number and title.
- Branch.
- Commit.
- Test result.
- Live endpoint evidence.
- Final live status.
- Confirmation that no real policy provider, authorization, enforcement, FHIR read, model call, dispatch, or handoff was implemented.

Update architecture/endpoint documentation only if required by the repository's existing pattern. Do not rewrite prior task documentation.

---

## 14. Explicit prohibitions

Do not:

- Import HAPI FHIR.
- Read or write FHIR.
- Add `MedicationRequest` to Epic.
- Expand allowlist 042.
- Modify clinical contract v1.
- Call Epic or Oracle.
- Add OAuth, JWT, SMART, or token handling.
- Add a real verification provider.
- Add a real evidence store.
- Add a real policy engine.
- Add real authorization or consent.
- Add a model provider.
- Add LLM/RAG/LangGraph/`ai-service`.
- Send the contract.
- Perform dispatch.
- Perform handoff.
- Set `verificationApproved=true`.
- Set `clinicalDataAccessGranted=true`.
- Set `clinicalDataAccessAllowed=true`.
- Set `clinicalDataAccessEnforced=true`.
- Set `modelCallAuthorized=true`.
- Set `handoffAuthorized=true`.
- Set `dispatchPerformed=true`.
- Set `modelCalled=true`.
- Disable or remove `requiresHumanReview`.
- Modify `.env`.
- Modify Tasks 057–071.
- Commit, push, or open a PR automatically.

---

## 15. Acceptance criteria

Task 072 is complete only when:

- A new isolated package exists.
- It consumes only `AiConsumerClinicalDataEnforcementExecutionVerificationResult`.
- It produces a dedicated verification-decision-boundary result.
- The implementation uses a `Boundary` component.
- The boundary is deterministic and deny-by-default.
- The live status is `VERIFICATION_DECISION_NOT_AVAILABLE`.
- All new decision, evidence, provider, and approval flags are false.
- All previous invariants remain unchanged.
- Query parameters and headers are ignored.
- Epic clinical projection remains HTTP 200.
- No FHIR read or write is introduced.
- No external provider is introduced.
- No model, dispatch, or handoff is introduced.
- Boundary, architecture, controller, and Epic non-regression tests pass.
- Documentation and progress log are updated.
- The exact test evidence is recorded.
- No push or PR is performed automatically.

---

## 16. Handoff to the next future task

This task does **not** approve verification, authorize clinical-data access, or activate enforcement.

The next future work may separately address a real policy engine or explicit human approval workflow, but that is outside Task 072.

The current chain must end as:

```text
AiConsumerClinicalDataEnforcementExecutionVerification
  → AiConsumerClinicalDataEnforcementVerificationDecision
  → VERIFICATION_DECISION_NOT_AVAILABLE
```

with:

```text
verificationApproved=false
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessEnforced=false
enforcementExecutionPerformed=false
executionVerified=false
requiresHumanReview=true
```
