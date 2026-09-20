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

Task 075 protects `GET /api/model-boundary/v1` with a laboratory shared secret. `GET /internal/agent-context` and `POST /internal/experimental-summary` reuse the same inbound token on the Python side and stay fail-closed when the token is blank. Sharing the secret does not merge the two paths.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Process liveness |
| `GET` | `/internal/agent-context` | Consume the Java v1 contract (`X-Service-Token` required) |
| `POST` | `/internal/experimental-summary` | Gated Gemini summary of fixture `SYN-076-001` |

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
| `LLM_EXPERIMENTAL_ENABLED` | `false` | `true` required before any Gemini call |
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

## Tests

```bash
cd services/ai-service
py -3 -m pytest
```

Default tests mock HTTP and use `FakeLLMProvider`. They do not call Epic, Oracle, or Gemini. Live Gemini tests run only when `RUN_LIVE_GEMINI_TESTS=true`.
