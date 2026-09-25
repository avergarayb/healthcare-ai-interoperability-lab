# ai-service

Task 074 laboratory consumer for Product B. FastAPI reads the existing Java Model Boundary Contract v1 and stops. That path does not call a language model.

Task 076 adds a separate, disabled-by-default experimental Gemini summary that accepts only fixture `SYN-076-001`. It does not consume v1 or call Java, Epic, Oracle, or HAPI.

```text
Epic / Oracle sandbox
        ↓
fhir-integration-service (Java)
        ↓
GET /api/model-boundary/v1
        ↓
ai-service (Python)
        ↓
received | rejected  (modelCalled=false)
```

## What this service does

1. Receives `GET /internal/agent-context` with inbound `X-Service-Token`. Missing, wrong, or unconfigured token returns HTTP 401 and does not call Java.
2. After authentication, calls `GET {MODEL_BOUNDARY_BASE_URL}{MODEL_BOUNDARY_PATH}` with `X-Service-Token` when `MODEL_BOUNDARY_SERVICE_TOKEN` is set.
3. Validates HTTP, JSON, required v1 fields, and `outcome`.
4. Decides `received` or `rejected`.
5. Always returns `modelCalled=false`.

It consumes the Java contract as-is. It does not wrap it, copy `records`, or add `usable` / `requiresHumanReview` / `modelCallAuthorized`.

Task 076 is a second path. It does not change the v1 consumer.

## What this service does not do

- RAG, LangGraph, MCP, or a second LLM provider
- Direct Epic, Oracle, HAPI FHIR, or SMART access
- Patient CRUD or new Java clinical endpoints
- OAuth, production identity, or fine-grained clinical authorization
- Sending `ModelBoundaryContract` v1 or live EHR data to Gemini

Task 075 protects `GET /api/model-boundary/v1` with a laboratory shared secret. `GET /internal/agent-context`, `POST /internal/experimental-summary`, and `POST /internal/agent/follow-up` reuse the same inbound token on the Python side and stay fail-closed when the token is blank. Sharing the secret does not merge the paths.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Process liveness |
| `GET` | `/internal/agent-context` | Consume the Java v1 contract (`X-Service-Token` required) |
| `POST` | `/internal/experimental-summary` | Gated Gemini summary of fixture `SYN-076-001` |
| `POST` | `/internal/agent/follow-up` | Synthetic Follow-up Agent. Token required. Disabled unless `FOLLOWUP_AGENT_ENABLED=true` |

## Environment

Copy `.env.example`. Do not commit `.env`.

| Variable | Laboratory default | Notes |
|---|---|---|
| `MODEL_BOUNDARY_BASE_URL` | `http://localhost:8081` | Java service |
| `MODEL_BOUNDARY_PATH` | `/api/model-boundary/v1` | Existing contract surface |
| `MODEL_BOUNDARY_TIMEOUT_SECONDS` | `90` | Java snapshot can take ~60s per socket |
| `MODEL_BOUNDARY_SERVICE_TOKEN` | (empty) | Same value as Java. Empty is fail-closed for inbound 074/076 and for Java v1 |
| `AI_SERVICE_HOST` | `0.0.0.0` | |
| `AI_SERVICE_PORT` | `8090` | |
| `LLM_EXPERIMENTAL_ENABLED` | `false` | `true` required before the 076 Gemini summary. Does not enable the Follow-up Agent |
| `FOLLOWUP_AGENT_ENABLED` | `false` | `true` required before `POST /internal/agent/follow-up` runs the agent |
| `GEMINI_API_KEY` | (empty) | Python only. Never commit a real value |
| `GEMINI_MODEL` | `gemini-flash-latest` | Override only. No automatic fallback if Google returns 404 |
| `RUN_LIVE_GEMINI_TESTS` | `false` | Opt-in live pytest |

Use `5` seconds only in mocked tests.

## Output

Exactly these fields:

```json
{
  "status": "received",
  "modelCalled": false,
  "contractVersion": "v1",
  "outcome": "SNAPSHOT_COMPLETE",
  "reason": null
}
```

`status` is `received` or `rejected`. `reason` is `null` on `received`. Closed rejection reasons:

- `empty_context` — no collection has `retainedCount > 0` (same idea as `AgentStub.hasClinicalData`)
- `boundary_outcome_not_success` — HTTP 200 and `outcome` is `SNAPSHOT_UNAVAILABLE`, `PATIENT_CONTEXT_NOT_CONFIGURED`, or `AUTHENTICATION_REQUIRED`
- `boundary_http_4xx` / `boundary_http_5xx` — Java HTTP class wins; body is not treated as a usable contract
- `boundary_timeout` / `boundary_connection_error`
- `invalid_contract` — not JSON, missing required keys, unknown `outcome`, or `retainedCount` not safely readable

`medicationRequests: null` is valid. A missing `medicationRequests` key is `invalid_contract`.

`SNAPSHOT_PARTIAL` with retained context is `received`.

Logs include a correlation id, Java HTTP status, duration, and the consumer verdict. They never include Patient identifiers, tokens, FHIR JSON, clinical values, or the full contract.

## Local run

Java `fhir-integration-service` must already be listening on port 8081 if you want a live call. Default tests do not need it.

```bash
cd services/ai-service
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8090
```

```http
GET http://localhost:8090/internal/agent-context
X-Service-Token: <same MODEL_BOUNDARY_SERVICE_TOKEN>
```

Experimental Gemini (disabled unless `LLM_EXPERIMENTAL_ENABLED=true` and `GEMINI_API_KEY` is set):

```http
POST http://localhost:8090/internal/experimental-summary
X-Service-Token: <same MODEL_BOUNDARY_SERVICE_TOKEN>
```

The body must be exactly fixture `SYN-076-001` from `app/experimental_fixture.py`.

## Follow-up Agent

`POST /internal/agent/follow-up` is a third path. It runs the synthetic Follow-up Agent over local fixtures. It does not call Java, FHIR, or HAPI, and it does not change 074 or 076.

`FOLLOWUP_AGENT_ENABLED` defaults to `false` and is separate from `LLM_EXPERIMENTAL_ENABLED`. While it is false, a valid token receives HTTP 503:

```json
{"detail": "Follow-up agent is disabled"}
```

That response is returned after authentication and before request validation, provider resolution, and the runtime. A missing or wrong token is still HTTP 401 with an empty body, whether the flag is true or false. The Gemini provider is constructed only after the flag is on and the request body is valid.

To try it locally, set the flag in the same shell that starts uvicorn. Uvicorn does not load `.env` by itself.

```powershell
$env:FOLLOWUP_AGENT_ENABLED = "true"
$env:MODEL_BOUNDARY_SERVICE_TOKEN = "<local-token>"
```

A configured `GEMINI_API_KEY` is also required before a live model call. Default tests do not use one; they inject `FakeLLMProvider`. Without a provider, an enabled request returns HTTP 200 with application status `PROVIDER_ERROR` and does not call Gemini.

```http
POST http://localhost:8090/internal/agent/follow-up
X-Service-Token: <same MODEL_BOUNDARY_SERVICE_TOKEN>
Content-Type: application/json

{"caseId": "SYN-FOLLOWUP-001"}
```

When the flag is true, a valid request returns the existing Follow-up contract, including `runId`, `caseId`, `status`, `followUpRequired`, `modelCalled`, `requiresHumanReview`, `summary`, `reason`, `suggestedActions`, and `evidence`. Application statuses such as `COMPLETED` and `POLICY_DENIED` use HTTP 200. A malformed body returns HTTP 422 only after the flag is enabled.

```json
{
  "status": "COMPLETED",
  "runId": "<uuid>",
  "agent": "follow-up-agent",
  "agentVersion": "follow-up-agent-v1",
  "caseId": "SYN-FOLLOWUP-001",
  "followUpRequired": "true",
  "summary": "Synthetic follow-up summary.",
  "reason": "Synthetic reason.",
  "suggestedActions": [{"type": "review", "detail": "Synthetic review"}],
  "evidence": [],
  "modelCalled": true,
  "requiresHumanReview": true,
  "promptVersion": "follow-up-agent-v2"
}
```

This surface uses synthetic laboratory data only. It does not diagnose, prescribe, or write clinical records. Human review remains mandatory. `/health` stays open and does not read this flag.

## Agent Decision Contract

Prompt version `follow-up-agent-v2` replaces the short `follow-up-agent-v1` instructions. The model proposes `followUpRequired`, a brief reason, permitted suggested actions, and evidence. Tools supply observed data. The runtime orchestrates the loop. Policy validates the proposal. The application sets `requiresHumanReview` to true.

`true` means observed information supports considering follow-up. `false` means it does not show that need in the current scope. `unknown` means the observed information is insufficient or contradictory. An empty list is not treated as `false`. The prompt is guidance for the model. It is not a security boundary.

## Bounded recovery

`MAX_RECOVERY_ATTEMPTS` is 1. The runtime uses it only when the model message is invalid JSON, has an invalid message shape, or has a correctable final shape. The first parse still rejects Markdown fences. The recovery prompt asks for raw JSON and does not include the previous completion.

A denied tool and evidence that was not observed end the run immediately. Tool and timeout limits stay at 6 calls and 30 seconds. `PROMPT_VERSION` stays `follow-up-agent-v2`.

## Provider retry

A provider error is a failure of `generate_text()` before the runtime has model text it can parse. `retryable` means the failure looks transient: HTTP 429, HTTP 5xx including 503, a provider timeout, or a coarse `http_5xx` result with no status code. HTTP 400, 401, and 403 are not retried. Malformed or empty model text is not a provider retry.

`MAX_PROVIDER_RETRIES` is 1. Before that retry, the runtime waits a bounded exponential backoff plus jitter: `min(1.0 * 2^(attempt - 1), 4.0)` seconds, plus up to `0.25` seconds. The first retry therefore waits about 1.0–1.25 seconds. `LLM_RETRY_REQUESTED` records that wait as `backoffMs`. The retry calls `generate_text()` again on the same `runId`. It does not execute tools, change Policy, or count as a tool call. Recovery stays separate: `RECOVERY_REQUESTED` is only for invalid model output. If the retry is exhausted, the status stays `PROVIDER_ERROR`. Policy remains the authority for tools and finals.

## Execution trace

`FollowUpRuntime` keeps an in-memory trace on `runtime.trace` for the current run. It records run start, each `generate_text()` turn, a provider error, a provider retry, a recovery request, policy checks, tool execution or denial, final receipt, and completion, failure, or timeout. Every event uses that run's `runId`.

The trace is for development and tests. It is not returned by `POST /internal/agent/follow-up`. It does not store prompts, model completions, tokens, or tool payloads. Persistence and production observability are out of scope.

## Follow-up Agent evaluation

`followup_evaluation` checks scripted runs of the existing runtime against an explicit expected contract. It uses `FakeLLMProvider` and the synthetic fixtures `SYN-FOLLOWUP-001` through `SYN-FOLLOWUP-006`. Each case is deterministic and does not call Gemini.

The harness compares status, follow-up required, tool order, suggested actions, evidence, LLM turn bounds, and the in-memory trace. It also checks human review, the tool allowlist, and that evidence matches observed tool results. It does not change agent behavior.

## Tests

```bash
cd services/ai-service
py -3 -m pytest
```

The default suite stays deterministic. It does not call Epic, Oracle, or Gemini, and it does not need an API key.

`FakeLLMProvider` scripts the runtime with fixed turns. Those tests check ordering, policy, evidence, and traces exactly.

`GeminiProvider` tests stub `_invoke` and return fixed text through `generate_text()`. They cross the real provider class without a network call. Markdown fences stay invalid JSON. An empty response or an invalid final is not retried as a provider error. A transient provider failure may be retried once.

## Live Gemini Evaluation

Set `RUN_LIVE_GEMINI_TESTS=true` and provide `GEMINI_API_KEY` to run the opt-in cases. They are skipped when the variable is missing or false. They call real Gemini through `GeminiProvider` and `FollowUpRuntime`, and that use can incur API cost.

The cases are the synthetic fixtures `SYN-FOLLOWUP-001`, `SYN-FOLLOWUP-002`, and `SYN-FOLLOWUP-005`. Gemini may choose different tools. The test does not require one sequence. The runtime and policy stay authoritative. Fences stay invalid. Recovery stays one attempt. A transient provider failure may be retried once, separately from recovery.

Each run is classified as `CONTRACT_SUCCESS`, `CONTRACT_VALIDATION_FAILURE`, `POLICY_DENIAL`, `PROVIDER_ERROR`, or `TIMEOUT`. A contract miss is recorded as that category. It does not relax parsing, evidence, or human review. The trace stays off the HTTP response. The test checks one `runId`, ordered sequences, a terminal event, and that prompts, completions, keys, and tool payloads are absent.
