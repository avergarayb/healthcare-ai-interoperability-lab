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

- RAG, MCP, or a second LLM provider on the 074 and 076 paths
- Direct Epic, Oracle, or SMART access. The follow-up path reads HAPI; 074 and 076 do not
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
| `POST` | `/internal/agent/follow-up` | `FollowUpWorkflow.run()`. Token required. Disabled unless `FOLLOWUP_AGENT_ENABLED=true` |

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

`POST /internal/agent/follow-up` calls `FollowUpWorkflow.run(case_id)`. That workflow is the LangGraph follow-up: Gemini tool calling, policy, audit, `ToolNode`, and the FHIR read chain. It does not change 074 or 076. `GeminiProvider.generate_summary()` still serves `POST /internal/experimental-summary`.

`FOLLOWUP_AGENT_ENABLED` defaults to `false` and is separate from `LLM_EXPERIMENTAL_ENABLED`. While it is false, a valid token receives HTTP 503 and the workflow does not run:

```json
{"detail": "Follow-up agent is disabled"}
```

That response is returned after authentication and before request validation. A missing or wrong token is still HTTP 401 with an empty body, whether the flag is true or false. A malformed body returns HTTP 422 only after the flag is enabled, and the workflow does not run.

To try it locally, set the flag in the same shell that starts uvicorn. Uvicorn does not load `.env` by itself.

```powershell
$env:FOLLOWUP_AGENT_ENABLED = "true"
$env:MODEL_BOUNDARY_SERVICE_TOKEN = "<local-token>"
$env:GEMINI_API_KEY = "<local-key>"
```

Gemini for this path uses `Settings.gemini_api_key` and `Settings.gemini_model`. Default tests inject a scripted workflow and do not call Gemini.

```http
POST http://localhost:8090/internal/agent/follow-up
X-Service-Token: <same MODEL_BOUNDARY_SERVICE_TOKEN>
Content-Type: application/json

{"caseId": "SYN-FOLLOWUP-001"}
```

A workflow result uses HTTP 200. Internal statuses map as `finish` → `completed`, `denied` → `denied`, `unavailable` → `unavailable`, and `limit` → `limit`.

```json
{
  "runId": "<uuid>",
  "caseId": "SYN-FOLLOWUP-001",
  "status": "completed",
  "followUpRequired": "unknown",
  "answer": "Synthetic answer.",
  "evidence": [
    {"tool": "get_patient_followup_context", "id": "Patient/SYN-PATIENT-001"},
    {"tool": "get_patient_followup_context", "id": "Observation/obs-synthetic-001"}
  ]
}
```

The application creates one `runId` and passes it into the workflow. Evidence lists FHIR references for `get_patient_followup_context`. The body does not include the patient, the observation, prompts, completions, or signatures. An unexpected workflow failure, including a Gemini or transport error the workflow does not map to `unavailable`, returns HTTP 502 `{"detail": "Follow-up workflow failed"}` and does not echo the exception.

This surface uses synthetic laboratory data only. It does not diagnose, prescribe, or write clinical records. `/health` stays open and does not read this flag.

The previous manual runtime, its JSON tool loop, fixture tools, and `FollowUpResponse` contract have been removed. They are not a second implementation.

## Tests

```bash
cd services/ai-service
py -3 -m pytest
```

The default suite stays deterministic. It does not call Epic, Oracle, or Gemini, and it does not need an API key.

Follow-up endpoint tests inject a scripted workflow. Experimental-summary tests use `FakeLLMProvider` and stub `GeminiProvider._invoke` for `generate_summary()`.

## Live Gemini

Set `RUN_LIVE_GEMINI_TESTS=true` together with `RUN_HAPI_INTEGRATION_TESTS=true` to run the opt-in follow-up case. It stays skipped otherwise. HAPI reads alone use `RUN_HAPI_INTEGRATION_TESTS=true`. The experimental summary has its own opt-in live test and still uses `GeminiProvider.generate_summary()`.

## Follow-up workflow

`POST /internal/agent/follow-up` calls `FollowUpWorkflow.run(case_id)`.

Incremental LangGraph laboratories (C16-A through C16-T) were used to prove the pieces. Those lesson modules are gone. One workflow remains:

```text
FollowUpWorkflow.run
        |
        v
LangGraph
        |
        +--> Gemini tool calling
        |
        +--> evaluate_tool_policy
        |
        +--> record_policy_audit
        |
        +--> ToolNode
                |
                v
        get_patient_followup_context
                |
                v
        FollowUpFHIRAdapter
                |
                v
        ClientFHIRTransport
                |
                v
        HapiReadClient
                |
                v
        HAPI FHIR
```

Policy and audit stay outside the graph. `evaluate_tool_policy` runs before `ToolNode`. `ToolNode` executes an allowed tool. It does not authorize. A denied or unknown tool is audited and does not reach `ToolNode`. `MAX_MODEL_TURNS` is 4. LangGraph `recursion_limit` is not the product limit.

Automatic function calling is disabled on both Gemini requests (`AutomaticFunctionCallingConfig(disable=True)`). The first request can propose `get_patient_followup_context`. The second request does not declare tools. It asks only for a JSON object with `answer` and `follow_up_required` (`true`, `false`, or `unknown`). The workflow copies that field. It does not read the answer text. `thought_signature` from the function-call part is sent back on the next request and is not logged or returned.

`record_policy_audit` writes one `followup_tool_policy_audit` line on the `ai-service` logger. That line uses the same `run_id` as the HTTP `runId` and the workflow, plus `case_id`, `tool_name`, `decision`, `policy_version`, and `reason`. It does not include prompts, signatures, Patient, or Observation.

The case id is not a `Patient.id`. The adapter searches `Patient.identifier` (`system` `https://lab.local/followup-case`, `value` equal to the case id), then reads that Patient and the Observations whose subject is that Patient. The laboratory Patient `SYN-PATIENT-001` carries this identifier for `SYN-FOLLOWUP-001`. A case with no matching identifier is `unavailable`. Other accepted case ids have no FHIR patient yet. This path only reads HAPI.

This follow-up has no persistent memory, RAG, checkpointing, or human-in-the-loop interrupt.

A live call for `SYN-FOLLOWUP-001` returned HTTP 200 with `status` `completed` and `followUpRequired` `unknown`. That run confirmed the two Gemini calls, the tool, the audit, and the HAPI reads. It did not inspect Gemini's internal structured payload, so `unknown` stays a valid result when that field is absent or was not observed. The service does not infer it from the answer text.

Gemini settings come from `Settings` (`GEMINI_API_KEY`, `GEMINI_MODEL`). `config.py` was not changed. `GeminiProvider` still serves the experimental summary.

`FollowUpWorkflowResult` is the internal result: `run_id`, `case_id`, `status` (`finish`, `denied`, `unavailable`, `limit`), `final_answer`, `follow_up_required`, and `evidence`. The HTTP body is `FollowUpEndpointResponse`.

HAPI reads are opt-in with `RUN_HAPI_INTEGRATION_TESTS=true`. Live Gemini stays opt-in with `RUN_LIVE_GEMINI_TESTS=true`.
