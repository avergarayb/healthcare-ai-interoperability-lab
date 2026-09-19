# Task 076 — Controlled LLM Integration via Google Gemini API

Task 076 specified `gemini-2.5-flash`. After the 2026-09-19 live demo, Task 077 sets the repository default to `gemini-flash-latest`. `GEMINI_MODEL` remains overridable. Historical examples below still show the 076-specified id.

**Status:** READY FOR IMPLEMENTATION — PRE-IMPLEMENTATION CONFLICTS CLOSED  
**Canonical implementation spec:** this file  
**Branch:** `feature/076-controlled-gemini-integration`  
**Depends on:** Task 075 — Model Boundary Service Auth  
**Scope:** Python `ai-service` only  
**Provider:** Google Gemini API  
**Model:** `gemini-2.5-flash`

---

## 1. Objective

Implement the first controlled external LLM integration in the Healthcare AI & Interoperability Lab using the **Google Gemini API**.

The purpose of this task is to demonstrate an end-to-end, fail-closed, governance-controlled LLM invocation without changing the existing FHIR boundary, `ModelBoundaryContract v1`, or `/internal/agent-context`.

This task is an **experimental laboratory integration**, not a clinical decision-support feature.

The implementation must use only a fixed synthetic fixture and must not send real patient data, PHI, live Epic/Oracle data, HAPI FHIR resources, or complete FHIR Bundles to Gemini.

---

## 2. Explicit Scope

### In scope

- Google Gemini API integration.
- Python `ai-service`.
- A closed experimental summary use case.
- `LLMProvider` abstraction.
- `GeminiProvider` real implementation.
- `FakeLLMProvider` for deterministic tests.
- A new internal experimental endpoint.
- Configuration gate disabled by default.
- API key supplied only to Python.
- Strict input/output schemas.
- Human-review invariant.
- Provider error handling.
- Structured technical logging without prompts, completions, PHI, or secrets.
- Unit/integration tests.
- Optional live Gemini E2E test.
- Documentation and ADR for the integration.

### Explicitly out of scope

- OpenAI integration.
- Any second LLM provider.
- Provider fallback.
- Multi-provider routing.
- RAG.
- MCP.
- LangGraph.
- Agent memory.
- Autonomous agent behavior.
- Clinical recommendations.
- Diagnosis.
- Treatment suggestions.
- Medication recommendations.
- Production PHI processing.
- Changes to Java FHIR integration.
- Changes to `/internal/agent-context`.
- Changes to `ModelBoundaryContract v1`.
- Changes to SMART authentication.
- Direct FHIR access from Python.
- Direct access to Epic, Oracle, or HAPI FHIR from Python.

If another LLM provider is considered in the future, it must be handled by a separate task and separate review.

---

## 3. Current Architecture Invariants

These invariants remain unchanged. **Task 076 does not feed `ModelBoundaryContract v1` or `/internal/agent-context` into Gemini.** Those flows continue independently and are not the input path for this experimental endpoint.

The Task 076 flow is strictly:

```text
Fixed synthetic fixture
        |
        v
POST /internal/experimental-summary
        |
        v
Input validation + synthetic fixture equality
        |
        v
ExperimentalSummaryService
        |
        v
LLMProvider
        |
        v
GeminiProvider
        |
        v
Google Gemini API
```

In parallel, the existing FHIR path remains unchanged:

```text
Epic / Oracle / HAPI FHIR
        |
        v
Java FHIR boundary
        |
        v
ModelBoundaryContract v1
        |
        v
/internal/agent-context
```

There is **no data path from the live v1 flow into the Task 076 Gemini request**.

The Python AI service must **not** become a FHIR client.

The Gemini API must never receive:

- complete FHIR Bundles;
- raw FHIR resources;
- patient identifiers;
- patient names;
- MRNs;
- access tokens;
- SMART credentials;
- OAuth tokens;
- raw narratives;
- unminimized clinical documents;
- unapproved PHI.

Task 076 accepts only the exact canonical synthetic fixture defined in Section 8.

---

## 4. Architectural Decision

### 4.1 Provider abstraction

Create a small provider abstraction:

```python
class LLMProvider(ABC):

    @abstractmethod
    def generate_summary(
        self,
        request: ExperimentalSummaryRequest,
    ) -> ExperimentalSummaryResult:
        ...
```

The abstraction exists to isolate provider-specific SDK/API details from the application service.

### 4.2 Providers implemented in Task 076

Only these two implementations are allowed:

```text
LLMProvider
    |
    +-- GeminiProvider       # real provider
    |
    +-- FakeLLMProvider      # tests
```

Do **not** implement `OpenAIProvider`.

Do **not** create provider-selection logic for OpenAI.

Do **not** create configuration such as:

```text
LLM_PROVIDER=openai
```

The real provider for this task is Gemini.

---

## 5. Gemini Configuration

The project and API key have already been created in Google AI Studio.

The API key must be supplied to `ai-service` as a secret environment variable:

```env
GEMINI_API_KEY=<secret>
```

Never commit the key.

Never place it in:

- source code;
- Git;
- Docker images;
- `.env` files committed to the repository;
- Java configuration;
- frontend code;
- logs;
- API responses;
- prompts.

The experimental feature must also be disabled by default:

```env
LLM_EXPERIMENTAL_ENABLED=false
```

Model configuration:

```env
GEMINI_MODEL=gemini-2.5-flash
RUN_LIVE_GEMINI_TESTS=false
```

The implementation must validate that the required Gemini configuration exists before attempting a provider call.

Missing API key or invalid provider configuration must fail closed.

---

## 6. Gemini SDK

Use Google's official Python GenAI SDK:

```text
google-genai
```

Do not implement a custom Gemini HTTP client unless there is a documented technical reason.

Pin the resolved dependency version in the project's normal dependency management mechanism.

Do not invent or leave an unbounded dependency version.

The implementation must follow the current official SDK API for the selected model.

### 6.1 Existing architecture-test exception

The repository currently has an architecture test that rejects model clients from `requirements.txt` and `app/`. Task 076 requires exactly one narrowly scoped exception:

- allow `google-genai`;
- continue prohibiting `google-generativeai`;
- continue prohibiting `openai`;
- continue prohibiting LangChain/LangGraph clients;
- continue prohibiting FHIR clients;
- continue prohibiting direct Epic/Oracle/clinical hosts.

Update `test_architecture.py` accordingly. Do not weaken the test beyond this single `google-genai` allowlist entry.

---

## 7. Experimental Use Case

### Use case

Generate a short **informational summary of a synthetic encounter context**.

The model must not:

- diagnose the patient;
- recommend treatment;
- recommend medications;
- determine urgency;
- make a clinical decision;
- replace a clinician;
- make an autonomous decision.

The purpose is to prove the technical path:

```text
Synthetic input
      |
      v
Input validation
      |
      v
Prompt construction
      |
      v
Gemini API
      |
      v
Closed output validation
      |
      v
Human-reviewed experimental result
```

---

## 8. Synthetic Fixture

Task 076 enforces synthetic-only input by accepting **only one exact canonical fixture**. The endpoint must not accept arbitrary bodies merely because they satisfy the Pydantic schema.

Canonical fixture:

```json
{
  "caseId": "SYN-076-001",
  "patientAgeRange": "50-59",
  "sex": "F",
  "encounterType": "outpatient",
  "observations": [
    {
      "code": "SYN-OBS-001",
      "display": "Synthetic observation A",
      "value": "Synthetic value",
      "unit": "unit"
    },
    {
      "code": "SYN-OBS-002",
      "display": "Synthetic observation B",
      "value": "Synthetic value",
      "unit": "unit"
    }
  ],
  "medications": [
    {
      "code": "SYN-MED-001",
      "display": "Synthetic medication"
    }
  ]
}
```

The implementation must compare the normalized request against this canonical fixture. Any difference must be rejected before Gemini is invoked.

Therefore: `caseId != SYN-076-001` is rejected, and changing any other field is also rejected.

This is intentionally stricter than a generic `SYN-*` allowlist because Task 076 is a controlled demo, not a general synthetic-data ingestion API.

Do not construct the experimental input from live Epic, Oracle, HAPI FHIR, or production data.

---

## 9. Experimental Input Contract

Create a dedicated Python contract for this task. Python may use snake_case internally, but the HTTP JSON contract **must use camelCase**, matching Task 074 conventions.

Example:

```python
class ExperimentalSummaryRequest(BaseModel):
    case_id: str = Field(alias="caseId")
    patient_age_range: str = Field(alias="patientAgeRange")
    sex: str
    encounter_type: str = Field(alias="encounterType")
    observations: list[Observation]
    medications: list[Medication]

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
```

Nested models must also reject unknown fields and use the repository's camelCase JSON convention.

The HTTP request must be exactly equal to the canonical fixture in Section 8 after normalizing through the contract. Schema validity alone is insufficient.

The contract must reject:

- FHIR `Bundle`;
- arbitrary dictionaries;
- access tokens;
- OAuth credentials;
- SMART tokens;
- patient identifiers;
- free-form patient narratives;
- unknown fields;
- any body that differs from the canonical fixture.

Do not reuse `ModelBoundaryContract v1` for this experimental request.

`ModelBoundaryContract v1` remains unchanged.

---

## 10. Experimental Endpoint

Add a new Python-only endpoint:

```http
POST /internal/experimental-summary
```

This endpoint is independent from:

```http
/internal/agent-context
```

Do not modify `/internal/agent-context`.

Do not change its response contract.

Do not route the experimental endpoint through the existing Java `ModelBoundaryDecision`.

### Authentication

The endpoint must be protected as an internal endpoint.

Reuse the existing model-boundary service token mechanism where practical:

```http
X-Service-Token: <MODEL_BOUNDARY_SERVICE_TOKEN>
```

Validate it before processing the request.

Missing, empty, or invalid token:

```http
401 Unauthorized
```

If the configured `MODEL_BOUNDARY_SERVICE_TOKEN` is missing or blank, the endpoint must also fail closed with `401`. This mirrors the fail-closed behavior established in Task 075.

Do not log the token.

---

## 11. Feature Gate

The endpoint must be disabled by default.

Configuration:

```env
LLM_EXPERIMENTAL_ENABLED=false
```

When disabled:

```http
503 Service Unavailable
```

with a machine-readable error indicating that the experimental LLM integration is disabled.

No provider call may occur.

Response body must use the complete `ExperimentalSummaryResponse` contract:

```json
{
  "status": "DISABLED",
  "summary": null,
  "provider": "GEMINI",
  "model": "gemini-2.5-flash",
  "promptVersion": "experimental-summary-v1",
  "modelCalled": false,
  "requiresHumanReview": true
}
```

No provider call may occur.

If the endpoint is disabled, `modelCalled` must remain `false`.

---

## 12. Request Processing Order

The processing order must be fail-closed:

```text
1. Authenticate internal caller
2. Check experimental feature flag
3. Validate request schema
4. Validate synthetic-only constraints
5. Validate Gemini configuration
6. Construct versioned prompt
7. Invoke GeminiProvider
8. Validate provider response
9. Build closed experimental result
10. Emit technical audit log
```

No provider call may occur before steps 1–5 succeed.

---

## 13. Prompt Version

Use a versioned prompt identifier:

```text
experimental-summary-v1
```

The prompt must explicitly instruct Gemini:

- this is synthetic laboratory data;
- produce an informational summary only;
- do not diagnose;
- do not recommend treatment;
- do not recommend medication;
- do not make clinical decisions;
- do not infer patient identity;
- do not invent information not present in the input;
- keep the response concise.

The prompt itself must not be logged.

Only the prompt version may be logged.

### 13.1 Provider timeout and output limit

The outbound Gemini call must have an application-enforced timeout of:

```text
30 seconds
```

If the timeout is exceeded after the provider invocation has started:

```text
HTTP 504 Gateway Timeout
modelCalled = true
requiresHumanReview = true
```

The returned `summary` must be limited to **2000 characters** after provider response normalization. A response exceeding this limit must be rejected as a provider response error; do not silently truncate model output.

---

## 14. GeminiProvider

`GeminiProvider` is responsible only for provider-specific behavior.

It must:

1. receive the validated experimental request;
2. construct the provider input;
3. call Gemini using the official SDK;
4. handle provider exceptions;
5. return a normalized provider result;
6. never log the prompt or completion;
7. never expose the API key.

The application service must not contain Gemini-specific SDK calls.

Bad:

```python
service -> google.genai.Client(...)
```

Good:

```text
ExperimentalSummaryService
          |
          v
     LLMProvider
          |
          v
    GeminiProvider
          |
          v
     Gemini SDK
```

---

## 15. Output Contract

The HTTP response must use the same camelCase JSON convention as Task 074. Python may use snake_case internally with Pydantic aliases.

Example:

```python
class ExperimentalSummaryResponse(BaseModel):
    status: Literal[
        "COMPLETED",
        "DISABLED",
        "VALIDATION_ERROR",
        "PROVIDER_ERROR"
    ]
    summary: str | None
    provider: str | None
    model: str | None
    prompt_version: str = Field(alias="promptVersion")
    model_called: bool = Field(alias="modelCalled")
    requires_human_review: bool = Field(alias="requiresHumanReview")

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
```

The serialized JSON must be exactly:

```json
{
  "status": "COMPLETED",
  "summary": "...",
  "provider": "GEMINI",
  "model": "gemini-2.5-flash",
  "promptVersion": "experimental-summary-v1",
  "modelCalled": true,
  "requiresHumanReview": true
}
```

Rules:

### Successful Gemini call

```text
status = COMPLETED
modelCalled = true
requiresHumanReview = true
provider = GEMINI
model = configured Gemini model
```

### No provider invocation

```text
modelCalled = false
requiresHumanReview = true
```

### Error responses

For `503`, `502`, and `504`, use the complete response contract with `summary=null`, `modelCalled` reflecting whether invocation started, and `requiresHumanReview=true`.

Example disabled response:

```json
{
  "status": "DISABLED",
  "summary": null,
  "provider": "GEMINI",
  "model": "gemini-2.5-flash",
  "promptVersion": "experimental-summary-v1",
  "modelCalled": false,
  "requiresHumanReview": true
}
```

Example provider error after invocation started:

```json
{
  "status": "PROVIDER_ERROR",
  "summary": null,
  "provider": "GEMINI",
  "model": "gemini-2.5-flash",
  "promptVersion": "experimental-summary-v1",
  "modelCalled": true,
  "requiresHumanReview": true
}
```

Do not expose raw provider errors, prompts, completions, API keys, or SDK details in the response.

### Human review

`requiresHumanReview` must always be:

```text
true
```

There is no configuration switch to disable this requirement. The application, not Gemini, owns this field.

The implementation must reject or prevent any path that produces:

```text
requiresHumanReview = false
```

---

## 16. Definition of `modelCalled`

`modelCalled` means that the application actually initiated an outbound invocation of the Gemini provider.

Therefore:

- validation failure → `false`;
- feature disabled → `false`;
- missing API key → `false`;
- invalid internal authentication → no response field required / request rejected;
- provider invocation started → `true`;
- provider timeout after invocation started → `true`;
- provider HTTP/API error after invocation started → `true`;
- malformed provider response after invocation started → `true`.

Do not define `modelCalled=true` merely because the endpoint was reached.

---

## 17. Error Handling

Use deterministic HTTP behavior.

### Authentication

```text
401 Unauthorized
```

for missing/invalid `X-Service-Token`.

### Disabled

```text
503 Service Unavailable
```

for `LLM_EXPERIMENTAL_ENABLED=false`.

### Invalid request

```text
422 Unprocessable Entity
```

for schema/validation failure.

No provider call.

### Missing configuration

```text
503 Service Unavailable
```

No provider call.

### Gemini/provider error

Normalize provider-side failures as:

```text
502 Bad Gateway
```

unless the project already has a stronger existing error convention.

### Gemini timeout

Use:

```text
504 Gateway Timeout
```

if the configured provider timeout is exceeded.

### Invalid/malformed provider response

```text
502 Bad Gateway
```

Do not return raw provider responses to the caller.

Do not expose provider API keys, internal SDK exceptions, or sensitive provider details.

---

## 18. Provider Response Validation

Never trust the external provider response blindly.

Validate:

- expected output type;
- non-empty summary;
- maximum response length;
- no unexpected structured fields if structured output is used;
- no prohibited control fields;
- no attempt to set `requiresHumanReview`;
- no attempt to change `modelCalled`.

The provider must not be able to control governance metadata.

Governance metadata is produced by our application, not by Gemini.

---

## 19. Logging and Audit

Allowed technical fields:

```text
correlationId
useCase
promptVersion
provider
model
durationMs
status
modelCalled
```

Do NOT log:

- API key;
- access tokens;
- OAuth tokens;
- complete request;
- complete prompt;
- complete Gemini response;
- patient identifiers;
- patient names;
- FHIR resources;
- FHIR Bundles;
- clinical narratives;
- raw PHI;
- arbitrary model output.

Example:

```text
experimental_llm_call
correlationId=...
useCase=experimental-summary
provider=GEMINI
model=gemini-2.5-flash
promptVersion=experimental-summary-v1
durationMs=...
status=COMPLETED
modelCalled=true
```

---

## 20. FakeLLMProvider

Implement:

```text
FakeLLMProvider
```

for deterministic tests.

It must allow tests to simulate:

- successful response;
- timeout;
- provider 4xx;
- provider 5xx;
- malformed response;
- empty response;
- unexpected provider output.

Tests must not require a live Gemini API key.

---

## 21. Live Gemini E2E Test

A real Gemini test may exist but must be explicitly opt-in.

Example:

```env
RUN_LIVE_GEMINI_TESTS=false
```

Default:

```text
false
```

When enabled, the test requires:

```env
GEMINI_API_KEY
```

The test must use only the fixed synthetic fixture.

Never run the live test automatically in CI unless the repository already has a secure secret-management mechanism explicitly intended for this purpose.

---

## 22. Tests Required

At minimum:

### Authentication

- missing service token → 401;
- invalid service token → 401;
- valid service token → request proceeds.

### Feature gate

- disabled → 503;
- provider not invoked;
- `modelCalled=false`.

### Request validation

- valid synthetic request;
- unknown field rejected;
- Bundle rejected;
- token-like input rejected;
- missing required field rejected.

### Configuration

- missing Gemini API key;
- invalid configuration;
- provider not invoked when configuration is invalid.

### Gemini provider

Using `FakeLLMProvider`:

- successful response;
- timeout;
- provider 4xx;
- provider 5xx;
- malformed response;
- empty response.

### Governance

- `requiresHumanReview` always true;
- no code path can return false;
- `modelCalled=false` before invocation;
- `modelCalled=true` once provider invocation starts;
- provider cannot override governance fields.

### Logging

- technical metadata is emitted;
- prompt is not logged;
- completion is not logged;
- API key is not logged;
- synthetic request is not dumped into logs.

### Regression

Existing tests must continue to pass.

The following must remain unchanged:

```text
ModelBoundaryContract v1
/internal/agent-context
SMART authentication
Java FHIR integration
Epic/Oracle adapters
existing Task 075 service authentication
```

---

## 23. No Java Changes

Task 076 must not modify Java behavior.

Do not:

- add Gemini code to Java;
- add Gemini API keys to Java;
- call Gemini from Java;
- modify Java FHIR services;
- modify `/internal/agent-context`;
- modify `ModelBoundaryContract v1`;
- change existing model authorization flags.

The Java service remains responsible for the FHIR/provider boundary.

---

## 24. Security Requirements

The implementation must follow deny-by-default behavior.

Secrets:

```text
GEMINI_API_KEY
MODEL_BOUNDARY_SERVICE_TOKEN
```

must be environment/configuration secrets.

Never hard-code secrets.

Never commit secrets.

Never print secrets.

Never return secrets through API responses.

The Gemini API key must exist only in the Python service runtime.

---

## 25. Data Processing Boundary

For Task 076:

```text
FHIR data                     ❌
Epic production data          ❌
Oracle production data        ❌
Real patient data             ❌
PHI                           ❌
Synthetic fixture             ✅
Gemini API                    ✅
```

The laboratory must not be described as HIPAA compliant, legally compliant, or approved for clinical PHI processing based solely on this task.

Any future use involving real PHI requires a separate data-processing, legal, security, privacy, and clinical-governance assessment.

---

## 26. Documentation

This file is the **canonical implementation specification for Task 076**. It supersedes the earlier generic `TASK_076_CONTROLLED_LLM_INTEGRATION.md` implementation draft. Do not merge the two specifications.

Required files:

```text
docs/tasks/TASK_076_CONTROLLED_LLM_INTEGRATION.md
docs/adr/ADR-076-controlled-gemini-integration.md
```

The generic earlier draft should be replaced by this Gemini-specific specification at the canonical task path above. Do not keep two competing Task 076 implementation specs.

The ADR path is fixed because the repository has no existing ADR convention. `docs/adr/` becomes the location of the first ADR for this task; do not invent additional architecture-document folders.

The ADR must record:

- objective;
- scope;
- Gemini as the sole real provider for this task;
- selected model;
- SDK;
- configuration;
- exact synthetic fixture rule;
- feature flag;
- service authentication;
- camelCase HTTP contracts;
- timeout and output-size limits;
- human-review invariant;
- logging restrictions;
- provider error handling;
- test strategy;
- explicit non-goals;
- statement that this is an experimental lab integration.

Do not claim regulatory compliance.

---

## 27. Acceptance Criteria

Task 076 is complete only when all of the following are true:

- [ ] `LLMProvider` exists.
- [ ] `GeminiProvider` exists.
- [ ] `FakeLLMProvider` exists.
- [ ] `google-genai` is pinned in project dependencies.
- [ ] `test_architecture.py` allows only `google-genai` as the model SDK exception and continues prohibiting other model clients.
- [ ] `GEMINI_API_KEY` is read only by Python.
- [ ] `GEMINI_MODEL=gemini-2.5-flash` is configurable.
- [ ] `RUN_LIVE_GEMINI_TESTS=false` is the default.
- [ ] `LLM_EXPERIMENTAL_ENABLED=false` is the default.
- [ ] `/internal/experimental-summary` exists.
- [ ] The endpoint requires internal service authentication.
- [ ] Synthetic-only input is enforced by exact equality with canonical fixture `SYN-076-001`.
- [ ] Unknown input fields are rejected.
- [ ] HTTP JSON contracts serialize in camelCase, matching Task 074.
- [ ] Complete FHIR Bundles are rejected.
- [ ] No provider call occurs before all gates pass.
- [ ] Gemini is the only real LLM provider implemented.
- [ ] No OpenAI integration exists in this task.
- [ ] `requiresHumanReview` is always true.
- [ ] `modelCalled` accurately represents provider invocation.
- [ ] Gemini errors are normalized.
- [ ] Gemini provider timeout is fixed at 30 seconds.
- [ ] Summary length is capped at 2000 characters and oversized output is rejected.
- [ ] Provider responses are validated.
- [ ] Prompts and completions are not logged.
- [ ] Secrets are not logged.
- [ ] Live Gemini tests are opt-in.
- [ ] Unit/integration tests pass without Gemini credentials.
- [ ] Existing project tests pass.
- [ ] Java behavior is unchanged.
- [ ] `ModelBoundaryContract v1` is unchanged.
- [ ] `/internal/agent-context` is unchanged.
- [ ] Documentation and ADR are updated at the exact paths defined in Section 26.
- [ ] No competing generic Task 076 implementation spec remains in the repository.
- [ ] A controlled end-to-end demo using synthetic data succeeds.

---

## 28. Demonstration Scenario

The final demo should show:

```text
1. Start AI Service
2. LLM_EXPERIMENTAL_ENABLED=true
3. Configure GEMINI_API_KEY securely
4. Submit fixed synthetic fixture
5. Authenticate internal request
6. Validate request
7. Build experimental-summary-v1 prompt
8. Call Gemini
9. Validate Gemini response
10. Return controlled response
11. Show technical audit log
12. Confirm:
       - modelCalled=true
       - requiresHumanReview=true
       - no FHIR Bundle sent
       - no PHI used
       - API key never exposed
```

The demo must also show the fail-closed behavior:

```text
LLM_EXPERIMENTAL_ENABLED=false
        |
        v
503
        |
        v
No Gemini call
```

and:

```text
Invalid service token
        |
        v
401
        |
        v
No Gemini call
```

and:

```text
Invalid synthetic request
        |
        v
422
        |
        v
No Gemini call
```

---

## 29. Implementation Rule for Cursor

Before modifying code, the implementation preflight is considered closed by this specification. The following repository conflicts have been explicitly resolved here:

- `test_architecture.py` is updated only to allow `google-genai`;
- the first ADR path is fixed to `docs/adr/ADR-076-controlled-gemini-integration.md`;
- HTTP JSON uses camelCase;
- synthetic-only is enforced by exact fixture equality;
- provider timeout is 30 seconds;
- summary maximum is 2000 characters;
- error responses use the closed response contract;
- this Gemini file is the canonical implementation specification;
- branch is `feature/076-controlled-gemini-integration`.

Before modifying code, also inspect:

1. Inspect the current Python project structure.
2. Confirm the working branch is `feature/076-controlled-gemini-integration`; do not rename unrelated branches.
3. Inspect existing configuration conventions.
4. Inspect existing authentication/service-token implementation.
5. Inspect existing test conventions.
6. Inspect current `ModelBoundaryContract v1`.
7. Inspect current `/internal/agent-context`.
8. Inspect `test_architecture.py` and apply only the explicit `google-genai` exception described in Section 6.1.
9. Do not change existing contracts unless this task explicitly requires it.
8. Implement only the scope defined in this document.
9. Run the full existing test suite.
10. Run the new Task 076 tests.
11. Do not perform unrelated refactoring.
12. Report every changed file.
13. Report every new dependency.
14. Report the exact test commands and results.
15. Do not expose or print `GEMINI_API_KEY`.

If an implementation detail conflicts with an existing repository convention, stop and report the conflict before making an architectural change.

---

## 30. Final Architectural State After Task 076

After successful completion, the lab has two deliberately separate paths:

```text
EXISTING FHIR PATH

Epic / Oracle / HAPI FHIR
        |
        v
Java FHIR Boundary
        |
        v
ModelBoundary v1
        |
        v
/internal/agent-context


EXPERIMENTAL GEMINI PATH

Fixed synthetic fixture
        |
        v
/internal/experimental-summary
        |
        v
ExperimentalSummaryService
        |
        v
LLMProvider
        |
        v
GeminiProvider
        |
        v
Google Gemini API
```

There is no live FHIR-to-Gemini path in Task 076.

The final state must remain:

```text
FHIR boundary             = Java
AI boundary               = Python
LLM provider              = Gemini only
Input                     = exact synthetic fixture SYN-076-001
Human review              = mandatory
LLM authorization         = experimental feature gate
Production PHI            = not allowed
OpenAI                    = not implemented
RAG                       = not implemented
MCP                       = not implemented
Memory                    = not implemented
Clinical recommendations  = not implemented
```

---

## 31. Task Completion Report

At the end of implementation, Cursor must provide a concise report containing:

### Files changed

List every modified/created file.

### Dependencies

List every new dependency and its pinned version.

### Configuration

List required environment variables without revealing secret values.

### Tests

Report:

```text
mvn test
pytest
live Gemini E2E (if explicitly executed)
```

with exact results.

### Security verification

Confirm:

- API key is not committed;
- API key is not logged;
- service token is not logged;
- no PHI is used;
- no complete FHIR Bundle reaches Gemini;
- Java was not modified;
- `ModelBoundaryContract v1` was not modified;
- `/internal/agent-context` was not modified.

### Demo verification

Confirm that only canonical fixture `SYN-076-001` is accepted and that the synthetic end-to-end Gemini call completed successfully and that:

```text
modelCalled=true
requiresHumanReview=true
```

were produced by the application rather than by the model.
