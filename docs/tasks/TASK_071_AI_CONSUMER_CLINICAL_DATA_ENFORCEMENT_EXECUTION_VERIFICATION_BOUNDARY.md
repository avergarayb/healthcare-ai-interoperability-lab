# TASK 071 — AI Consumer Clinical Data Enforcement Execution Verification Boundary

## 1. Position

**Task:** 071  
**Title:** AI Consumer Clinical Data Enforcement Execution Verification Boundary  
**Previous task:** 070 — AI Consumer Clinical Data Enforcement Execution Boundary  
**Suggested branch:** `feature/ai-consumer-clinical-data-enforcement-execution-verification-boundary`  
**Suggested commit:** `feat: add ai consumer clinical data enforcement execution verification boundary`  
**Service:** `fhir-integration-service`  
**Root package:** `lab.healthcare.fhir`  
**Suggested package:** `lab.healthcare.fhir.aiconsumerenforcementverification`

This task must implement **one isolated, synthetic, deny-by-default verification boundary** after Task 070.

It must not implement real clinical-data enforcement, real authorization, FHIR reads, model calls, dispatch, handoff, or any external integration.

---

## 2. Objective

Create a deterministic boundary that receives only the immediate result of Task 070:

```text
AiConsumerClinicalDataEnforcementExecutionResult
```

The boundary must produce a new result representing whether the claimed enforcement execution can be verified.

The expected live outcome is:

```text
NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS
```

The implementation must make the distinction explicit:

```text
enforcement execution
    ≠
enforcement execution verification
```

and:

```text
synthetic verification
    ≠
evidence of effective clinical-data permission
```

Task 071 is a verification boundary only. It must not perform, simulate, or authorize actual enforcement.

---

## 3. Scope

### Included

- A new isolated package.
- A result object for enforcement-execution verification status.
- A deterministic service or evaluator.
- A synthetic, untrusted verification context if required by the existing pattern.
- A controller/web adapter.
- Oracle-backed JSON surface.
- Blind fields on the existing Epic clinical projection endpoint.
- Unit, architecture, controller, and non-regression tests.
- Documentation and progress-log update.

### Excluded

- Real enforcement verification provider.
- Real authorization provider.
- Real audit/evidence store.
- OAuth, JWT, SMART, Epic, Oracle, or external identity integration.
- FHIR reads or writes.
- HAPI FHIR imports.
- LLM, RAG, LangGraph, `ai-service`, or model invocation.
- RabbitMQ, WebClient, Feign, RestClient, or external HTTP clients.
- Dispatch, handoff, or contract transmission.
- Changes to Tasks 057–070.
- Changes to the clinical contract v1.
- Changes to allowlist 042.
- Changes to `.env`.

---

## 4. Input contract

The core package may consume **only**:

```text
AiConsumerClinicalDataEnforcementExecutionResult
```

This is the immediate result of Task 070.

The core package must not import:

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

The web/controller layer may assemble the existing chain, following the established 065–070 pattern. The domain/core evaluator must remain isolated.

---

## 5. Suggested output contract

Create:

```text
AiConsumerClinicalDataEnforcementExecutionVerificationResult
```

Suggested fields:

```text
String status
boolean verificationDecisionAvailable
boolean verificationDecisionEvaluated
boolean executionEvidenceAvailable
boolean executionEvidenceEvaluated
boolean executionVerificationAvailable
boolean executionVerificationProviderConfigured
boolean executionVerified
boolean clinicalDataAccessEnforced
boolean clinicalDataAccessAllowed
boolean clinicalDataAccessGranted
boolean requiresHumanReview
```

The exact naming may follow the repository's existing conventions, but it must not overwrite or reuse the live names from Tasks 066–070.

Suggested status values:

```text
VERIFICATION_INPUT_NOT_AVAILABLE
VERIFICATION_BLOCKED
VERIFICATION_REQUIRES_EXECUTION_RESULT
VERIFICATION_REQUIRES_EVIDENCE
VERIFICATION_REQUIRES_REAL_PROVIDER
VERIFICATION_REQUIRES_HUMAN_REVIEW
VERIFICATION_NOT_AVAILABLE
NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS
```

The normal live result must be:

```text
status = NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS
verificationDecisionAvailable = false
verificationDecisionEvaluated = false
executionEvidenceAvailable = false
executionEvidenceEvaluated = false
executionVerificationAvailable = false
executionVerificationProviderConfigured = false
executionVerified = false
clinicalDataAccessEnforced = false
clinicalDataAccessAllowed = false
clinicalDataAccessGranted = false
requiresHumanReview = true
```

---

## 6. Deny-by-default rules

The evaluator must reject or block any input that attempts to represent verified execution.

If the input or synthetic context contains any of the following as `true`, the boundary must not promote the result:

```text
executionEvidenceAvailable
executionEvidenceEvaluated
executionVerificationAvailable
executionVerificationProviderConfigured
executionVerified
clinicalDataAccessEnforced
clinicalDataAccessAllowed
clinicalDataAccessGranted
verificationDecisionAvailable
verificationDecisionEvaluated
```

The result constructor/factory must normalize or reject unsafe positive values so that callers cannot manufacture verified clinical-data enforcement through the new boundary.

No positive synthetic context may enable:

```text
executionVerified
clinicalDataAccessEnforced
clinicalDataAccessAllowed
clinicalDataAccessGranted
modelCallAuthorized
handoffAuthorized
dispatchPerformed
modelCalled
```

A status or flag from Task 070 must never be treated as proof that enforcement actually occurred.

In particular:

```text
enforcementExecutionPerformed=true
    ≠
executionVerified=true
```

Task 071 must preserve the distinction between a claimed execution state and independently verified evidence.

---

## 7. Required invariants

Task 071 must preserve all existing invariants from Tasks 057–070.

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

### New Task 071 invariants

```text
verificationDecisionAvailable=false
verificationDecisionEvaluated=false
executionEvidenceAvailable=false
executionEvidenceEvaluated=false
executionVerificationAvailable=false
executionVerificationProviderConfigured=false
executionVerified=false
```

All applicable boolean fields must remain `false`, and:

```text
requiresHumanReview=true
```

---

## 8. Required behavior matrix

| Input condition | Expected result |
|---|---|
| Null input | `VERIFICATION_INPUT_NOT_AVAILABLE` |
| Missing Task 070 result | `VERIFICATION_INPUT_NOT_AVAILABLE` |
| Task 070 live deny-by-default result | `NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS` |
| Execution result unavailable | `VERIFICATION_REQUIRES_EXECUTION_RESULT` |
| Execution evidence unavailable | `VERIFICATION_REQUIRES_EVIDENCE` |
| Evidence not evaluated | `VERIFICATION_REQUIRES_EVIDENCE` |
| Real verification provider absent | `VERIFICATION_REQUIRES_REAL_PROVIDER` |
| Synthetic context claims execution is verified | Block or normalize to deny-by-default |
| Synthetic context claims access is enforced | Block or normalize to deny-by-default |
| Missing tenant/clinic context, if applicable | `VERIFICATION_BLOCKED` or equivalent deny state |
| Human review required | `VERIFICATION_REQUIRES_HUMAN_REVIEW` |
| Any positive verification flag | Never produce verified enforcement |
| Normal live request | `NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS` |

The implementation must be deterministic and side-effect free.

The evaluator must not infer evidence from:

- HTTP 200.
- Presence of a JSON field.
- A synthetic boolean.
- A Task 070 status string.
- A request header.
- A query parameter.
- A declared tenant or clinic identifier.
- A prior boundary's readiness state.

---

## 9. Suggested implementation structure

```text
lab.healthcare.fhir.aiconsumerenforcementverification
├── AiConsumerClinicalDataEnforcementExecutionVerificationResult
├── AiConsumerClinicalDataEnforcementExecutionVerificationEvaluator
├── AiConsumerClinicalDataEnforcementExecutionVerificationStatus
└── optional synthetic context/value objects
```

Do not introduce a generic framework or refactor previous boundaries.

The evaluator should:

1. Validate that the Task 070 result exists.
2. Inspect only the immediate Task 070 result.
3. Detect missing, inconsistent, or unsafe values.
4. Apply deny-by-default rules.
5. Produce the new verification result.
6. Preserve human review.
7. Avoid all external calls and side effects.
8. Never infer effective enforcement from a claimed execution flag.

---

## 10. Web/API surfaces

Follow the established 065–070 pattern.

### Lab surface

```http
GET /lab/ai-consumer-clinical-data-enforcement-execution-verification
```

### Oracle-backed JSON surface

```http
GET /api/ai-consumer-clinical-data-enforcement-execution-verification/v1
```

The Oracle-backed response must expose the new Task 071 fields and preserve the existing deny-by-default values.

### Epic blind projection fields

Extend the existing response from:

```http
GET /epic/sandbox/fhir/clinical-projection
```

only with blind, non-authorizing Task 071 fields.

Suggested fields:

```text
aiConsumerClinicalDataEnforcementExecutionVerification
aiConsumerVerificationDecisionAvailable
aiConsumerVerificationDecisionEvaluated
aiConsumerExecutionEvidenceAvailable
aiConsumerExecutionEvidenceEvaluated
aiConsumerExecutionVerificationAvailable
aiConsumerExecutionVerificationProviderConfigured
aiConsumerExecutionVerified
```

Expected values:

```text
aiConsumerClinicalDataEnforcementExecutionVerification=NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS
aiConsumerVerificationDecisionAvailable=false
aiConsumerVerificationDecisionEvaluated=false
aiConsumerExecutionEvidenceAvailable=false
aiConsumerExecutionEvidenceEvaluated=false
aiConsumerExecutionVerificationAvailable=false
aiConsumerExecutionVerificationProviderConfigured=false
aiConsumerExecutionVerified=false
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
- Not accept tokens, authorization values, tenant overrides, verification evidence, or execution flags from the request.
- Not perform external HTTP calls.
- Not invoke HAPI FHIR.
- Not invoke a model or agent.
- Not mutate shared state.

The endpoint must return the same deterministic result regardless of irrelevant query parameters or headers.

HTTP 200 must not be interpreted as evidence that enforcement was executed or verified.

---

## 12. Tests

### Boundary tests

Cover:

- Valid Task 070 input.
- Null input.
- Missing input.
- Task 070 deny-by-default input.
- Execution decision unavailable.
- Execution evidence unavailable.
- Execution evidence not evaluated.
- Real verification provider absent.
- Positive synthetic verification flags.
- Positive synthetic execution flags.
- Positive synthetic clinical-access flags.
- Missing tenant/clinic context, if context is introduced.
- Human review preservation.
- Deterministic repeated evaluation.
- No side effects.
- No inference from HTTP status or status strings.

### Constructor/factory safety tests

Verify that the result cannot be created with effective values for:

```text
verificationDecisionAvailable
verificationDecisionEvaluated
executionEvidenceAvailable
executionEvidenceEvaluated
executionVerificationAvailable
executionVerificationProviderConfigured
executionVerified
clinicalDataAccessEnforced
clinicalDataAccessAllowed
clinicalDataAccessGranted
```

### Architecture tests

Verify:

- Core package imports only `AiConsumerClinicalDataEnforcementExecutionResult` from the previous boundary.
- No imports from Tasks 057–069.
- No HAPI FHIR imports.
- No `FhirContext`.
- No `Patient`, `Bundle`, `Observation`, `Condition`, `Encounter`, or `MedicationRequest`.
- No HTTP client libraries.
- No RabbitMQ.
- No OAuth/JWT/SMART SDKs.
- No LLM, RAG, LangGraph, OpenAI, Azure, Gemini, Claude, or `ai-service`.
- No dependency on `.env`.

### Controller tests

Verify:

- Lab endpoint works.
- Oracle-backed JSON endpoint works.
- Query parameters do not alter the result.
- Headers do not alter the result.
- No request-supplied verification evidence can enable verification.
- No request-supplied execution flag can enable verification.
- No request-supplied authorization value can enable access.
- HTTP 200 does not change any verification flag.

### Epic non-regression

Update or add:

```text
EpicSandboxClinicalProjectionControllerTest
```

Verify:

- HTTP 200 remains unchanged.
- Existing clinical projection fields remain unchanged.
- Task 071 blind fields are present.
- All new verification flags remain false.
- No new FHIR resources are returned.
- No Task 071 field enables clinical access.
- No Task 071 field is treated as proof of enforcement.

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
docs/fhir/ai-consumer-clinical-data-enforcement-execution-verification-boundary.md
```

Document:

- Purpose.
- Position after Task 070.
- Input and output contracts.
- Status values.
- Deny-by-default behavior.
- Difference between execution and verification.
- Why a claimed execution flag is not evidence.
- Security and clinical-data limitations.
- Explicit non-goals.
- Endpoint surfaces.
- Test coverage.
- Why verification is not implemented by a real provider.

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
- Confirmation that no real verification provider, enforcement, FHIR read, model call, dispatch, or handoff was implemented.

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
- Add a real enforcement provider.
- Add a real evidence store.
- Add real authorization or consent.
- Add a model provider.
- Add LLM/RAG/LangGraph/`ai-service`.
- Send the contract.
- Perform dispatch.
- Perform handoff.
- Set `executionVerified=true`.
- Set `clinicalDataAccessGranted=true`.
- Set `clinicalDataAccessAllowed=true`.
- Set `clinicalDataAccessEnforced=true`.
- Set `modelCallAuthorized=true`.
- Set `handoffAuthorized=true`.
- Set `dispatchPerformed=true`.
- Set `modelCalled=true`.
- Disable or remove `requiresHumanReview`.
- Modify `.env`.
- Modify Tasks 057–070.
- Commit, push, or open a PR automatically.

---

## 15. Acceptance criteria

Task 071 is complete only when:

- A new isolated package exists.
- It consumes only `AiConsumerClinicalDataEnforcementExecutionResult`.
- It produces a dedicated verification-boundary result.
- The boundary is deterministic and deny-by-default.
- The live status is `NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS`.
- All new verification and evidence flags are false.
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

This task does **not** verify or authorize effective clinical-data enforcement.

The next future work may separately address a real evidence/verification provider or an explicit policy decision, but that is outside Task 071.

The current chain must end as:

```text
AiConsumerClinicalDataEnforcementExecution
  → AiConsumerClinicalDataEnforcementExecutionVerification
  → NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS
```

with:

```text
executionVerified=false
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessEnforced=false
enforcementExecutionPerformed=false
requiresHumanReview=true
```
