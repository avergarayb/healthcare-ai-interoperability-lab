# TASK 070 — AI Consumer Clinical Data Enforcement Execution Boundary

## 1. Position

**Task:** 070  
**Title:** AI Consumer Clinical Data Enforcement Execution Boundary  
**Previous task:** 069 — AI Consumer Clinical Data Enforcement Boundary  
**Suggested branch:** `feature/ai-consumer-clinical-data-enforcement-execution-boundary`  
**Suggested commit:** `feat: add ai consumer clinical data enforcement execution boundary`  
**Service:** `fhir-integration-service`  
**Root package:** `lab.healthcare.fhir`  
**Suggested package:** `lab.healthcare.fhir.aiconsumerenforcementexecution`

This task must implement **one isolated, synthetic, deny-by-default boundary** after Task 069.

It must not implement real clinical-data enforcement, real authorization, FHIR reads, model calls, dispatch, handoff, or any external integration.

---

## 2. Objective

Create a deterministic boundary that receives only the immediate result of Task 069:

```text
AiConsumerClinicalDataEnforcementResult
```

The boundary must produce a new result representing whether clinical-data enforcement execution is available.

The expected live outcome is:

```text
NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS
```

The implementation must make the distinction explicit:

```text
enforcement decision
    ≠
enforcement execution
```

and:

```text
synthetic enforcement boundary
    ≠
effective clinical-data permission
```

---

## 3. Scope

### Included

- A new isolated package.
- A result object for enforcement-execution status.
- A deterministic service or evaluator.
- A synthetic, untrusted context if required by the existing pattern.
- A controller/web adapter.
- Oracle-backed JSON surface.
- Blind fields on the existing Epic clinical projection endpoint.
- Unit, architecture, controller, and non-regression tests.
- Documentation and progress-log update.

### Excluded

- Real enforcement provider.
- Real authorization provider.
- OAuth, JWT, SMART, Epic, Oracle, or external identity integration.
- FHIR reads or writes.
- HAPI FHIR imports.
- LLM, RAG, LangGraph, `ai-service`, or model invocation.
- RabbitMQ, WebClient, Feign, RestClient, or external HTTP clients.
- Dispatch, handoff, or contract transmission.
- Changes to Tasks 057–069.
- Changes to the clinical contract v1.
- Changes to allowlist 042.
- Changes to `.env`.

---

## 4. Input contract

The core package may consume **only**:

```text
AiConsumerClinicalDataEnforcementResult
```

This is the immediate result of Task 069.

The core package must not import:

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

The web/controller layer may assemble the existing chain, following the established 065–069 pattern. The domain/core evaluator must remain isolated.

---

## 5. Suggested output contract

Create:

```text
AiConsumerClinicalDataEnforcementExecutionResult
```

Suggested fields:

```text
String status
boolean executionDecisionAvailable
boolean executionDecisionEvaluated
boolean enforcementExecutionAvailable
boolean enforcementExecutionProviderConfigured
boolean enforcementExecutionPerformed
boolean clinicalDataAccessEnforced
boolean clinicalDataAccessAllowed
boolean clinicalDataAccessGranted
boolean realAuthorizationRequired
boolean requiresHumanReview
```

The exact naming may follow the repository's existing conventions, but it must not overwrite or reuse the live names from Tasks 066–069.

Suggested status values:

```text
EXECUTION_INPUT_NOT_AVAILABLE
EXECUTION_BLOCKED
EXECUTION_REQUIRES_ENFORCEMENT_DECISION
EXECUTION_REQUIRES_REAL_AUTHORIZATION
EXECUTION_REQUIRES_HUMAN_REVIEW
EXECUTION_NOT_AVAILABLE
NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS
```

The normal live result must be:

```text
status = NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS
executionDecisionAvailable = false
executionDecisionEvaluated = false
enforcementExecutionAvailable = false
enforcementExecutionProviderConfigured = false
enforcementExecutionPerformed = false
clinicalDataAccessEnforced = false
clinicalDataAccessAllowed = false
clinicalDataAccessGranted = false
realAuthorizationRequired = true
requiresHumanReview = true
```

---

## 6. Deny-by-default rules

The evaluator must reject or block any input that attempts to represent effective execution.

If the input or synthetic context contains any of the following as `true`, the boundary must not promote the result:

```text
enforcementExecutionAvailable
enforcementExecutionProviderConfigured
enforcementExecutionPerformed
clinicalDataAccessEnforced
clinicalDataAccessAllowed
clinicalDataAccessGranted
executionDecisionAvailable
executionDecisionEvaluated
```

The result constructor/factory must normalize or reject unsafe positive values so that callers cannot manufacture an effective clinical-data permission through the new boundary.

No positive synthetic context may enable:

```text
clinicalDataAccessEnforced
clinicalDataAccessAllowed
clinicalDataAccessGranted
modelCallAuthorized
handoffAuthorized
dispatchPerformed
modelCalled
```

---

## 7. Required invariants

Task 070 must preserve all existing invariants from Tasks 057–069.

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

### New Task 070 invariants

```text
executionDecisionAvailable=false
executionDecisionEvaluated=false
enforcementExecutionAvailable=false
enforcementExecutionProviderConfigured=false
enforcementExecutionPerformed=false
```

All applicable boolean fields must remain `false`, and:

```text
requiresHumanReview=true
```

---

## 8. Required behavior matrix

| Input condition | Expected result |
|---|---|
| Null input | `EXECUTION_INPUT_NOT_AVAILABLE` |
| Missing Task 069 result | `EXECUTION_INPUT_NOT_AVAILABLE` |
| Task 069 live deny-by-default result | `NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS` |
| Enforcement decision unavailable | `EXECUTION_REQUIRES_ENFORCEMENT_DECISION` |
| Enforcement decision not evaluated | `EXECUTION_REQUIRES_ENFORCEMENT_DECISION` |
| Real authorization still required | `EXECUTION_REQUIRES_REAL_AUTHORIZATION` |
| Synthetic context claims execution is available | Block or normalize to deny-by-default |
| Synthetic context claims access is granted | Block or normalize to deny-by-default |
| Tenant/clinic context absent | `EXECUTION_BLOCKED` or equivalent deny state |
| Human review required | `EXECUTION_REQUIRES_HUMAN_REVIEW` |
| Any positive execution flag | Never produce effective enforcement |
| Normal live request | `NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS` |

The implementation must be deterministic and side-effect free.

---

## 9. Suggested implementation structure

```text
lab.healthcare.fhir.aiconsumerenforcementexecution
├── AiConsumerClinicalDataEnforcementExecutionResult
├── AiConsumerClinicalDataEnforcementExecutionEvaluator
├── AiConsumerClinicalDataEnforcementExecutionStatus
└── optional synthetic context/value objects
```

Do not introduce a generic framework or refactor previous boundaries.

The evaluator should:

1. Validate that the Task 069 result exists.
2. Inspect only the immediate Task 069 result.
3. Detect missing, inconsistent, or unsafe values.
4. Apply deny-by-default rules.
5. Produce the new result.
6. Preserve human review.
7. Avoid all external calls and side effects.

---

## 10. Web/API surfaces

Follow the established 065–069 pattern.

### Lab surface

```http
GET /lab/ai-consumer-clinical-data-enforcement-execution
```

### Oracle-backed JSON surface

```http
GET /api/ai-consumer-clinical-data-enforcement-execution/v1
```

The Oracle-backed response must expose the new Task 070 fields and preserve the existing deny-by-default values.

### Epic blind projection fields

Extend the existing response from:

```http
GET /epic/sandbox/fhir/clinical-projection
```

only with blind, non-authorizing Task 070 fields.

Suggested fields:

```text
aiConsumerClinicalDataEnforcementExecution
aiConsumerExecutionDecisionAvailable
aiConsumerExecutionDecisionEvaluated
aiConsumerEnforcementExecutionAvailable
aiConsumerEnforcementExecutionProviderConfigured
aiConsumerEnforcementExecutionPerformed
```

Expected values:

```text
aiConsumerClinicalDataEnforcementExecution=NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS
aiConsumerExecutionDecisionAvailable=false
aiConsumerExecutionDecisionEvaluated=false
aiConsumerEnforcementExecutionAvailable=false
aiConsumerEnforcementExecutionProviderConfigured=false
aiConsumerEnforcementExecutionPerformed=false
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
- Not accept tokens, authorization values, tenant overrides, or execution flags from the request.
- Not perform external HTTP calls.
- Not invoke HAPI FHIR.
- Not invoke a model or agent.
- Not mutate shared state.

The endpoint must return the same deterministic result regardless of irrelevant query parameters or headers.

---

## 12. Tests

### Boundary tests

Cover:

- Valid Task 069 input.
- Null input.
- Missing input.
- Task 069 deny-by-default input.
- Decision unavailable.
- Decision not evaluated.
- Real authorization required.
- Positive synthetic execution flags.
- Positive synthetic access flags.
- Missing tenant/clinic context, if context is introduced.
- Human review preservation.
- Deterministic repeated evaluation.
- No side effects.

### Constructor/factory safety tests

Verify that the result cannot be created with effective values for:

```text
enforcementExecutionAvailable
enforcementExecutionProviderConfigured
enforcementExecutionPerformed
clinicalDataAccessEnforced
clinicalDataAccessAllowed
clinicalDataAccessGranted
```

### Architecture tests

Verify:

- Core package imports only `AiConsumerClinicalDataEnforcementResult` from the previous boundary.
- No imports from Tasks 057–068.
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
- No request-supplied execution flag can enable enforcement.
- No request-supplied authorization value can enable access.

### Epic non-regression

Update or add:

```text
EpicSandboxClinicalProjectionControllerTest
```

Verify:

- HTTP 200 remains unchanged.
- Existing clinical projection fields remain unchanged.
- Task 070 blind fields are present.
- All new execution/enforcement flags remain false.
- No new FHIR resources are returned.
- No Task 070 field enables clinical access.

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
docs/fhir/ai-consumer-clinical-data-enforcement-execution-boundary.md
```

Document:

- Purpose.
- Position after Task 069.
- Input and output contracts.
- Status values.
- Deny-by-default behavior.
- Security and clinical-data limitations.
- Explicit non-goals.
- Endpoint surfaces.
- Test coverage.
- Why execution is not implemented.

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
- Confirmation that no real enforcement, FHIR read, model call, dispatch, or handoff was implemented.

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
- Add real authorization or consent.
- Add a model provider.
- Add LLM/RAG/LangGraph/`ai-service`.
- Send the contract.
- Perform dispatch.
- Perform handoff.
- Set `clinicalDataAccessGranted=true`.
- Set `clinicalDataAccessAllowed=true`.
- Set `clinicalDataAccessEnforced=true`.
- Set `modelCallAuthorized=true`.
- Set `handoffAuthorized=true`.
- Set `dispatchPerformed=true`.
- Set `modelCalled=true`.
- Disable or remove `requiresHumanReview`.
- Modify `.env`.
- Modify Tasks 057–069.
- Commit, push, or open a PR automatically.

---

## 15. Acceptance criteria

Task 070 is complete only when:

- A new isolated package exists.
- It consumes only `AiConsumerClinicalDataEnforcementResult`.
- It produces a dedicated execution-boundary result.
- The boundary is deterministic and deny-by-default.
- The live status is `NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS`.
- All new execution/enforcement flags are false.
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

This task does **not** authorize or execute clinical-data enforcement.

The next future work may separately address a real enforcement provider or an explicit policy decision, but that is outside Task 070.

The current chain must end as:

```text
AiConsumerClinicalDataEnforcement
  → AiConsumerClinicalDataEnforcementExecution
  → NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS
```

with:

```text
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessEnforced=false
enforcementExecutionPerformed=false
requiresHumanReview=true
```
