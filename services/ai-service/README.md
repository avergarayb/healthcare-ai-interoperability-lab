# ai-service

Task 074 laboratory consumer for Product B. FastAPI reads the existing Java Model Boundary Contract v1 and stops. It does not call a language model.

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

1. Receives `GET /internal/agent-context`.
2. Calls `GET {MODEL_BOUNDARY_BASE_URL}{MODEL_BOUNDARY_PATH}`.
3. Validates HTTP, JSON, required v1 fields, and `outcome`.
4. Decides `received` or `rejected`.
5. Always returns `modelCalled=false`.

It consumes the Java contract as-is. It does not wrap it, copy `records`, or add `usable` / `requiresHumanReview` / `modelCallAuthorized`.

## What this service does not do

- Language models, prompts, summaries, RAG, LangGraph, MCP
- Direct Epic, Oracle, HAPI FHIR, or SMART access
- Patient CRUD or new Java clinical endpoints
- Service-to-service authentication (documented debt; Task 075)

The Java endpoint is open for laboratory use only. That is not a production configuration.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Process liveness |
| `GET` | `/internal/agent-context` | Consume the Java v1 contract |

## Environment

Copy `.env.example`. Do not commit `.env`.

| Variable | Laboratory default | Notes |
|---|---|---|
| `MODEL_BOUNDARY_BASE_URL` | `http://localhost:8081` | Java service |
| `MODEL_BOUNDARY_PATH` | `/api/model-boundary/v1` | Existing contract surface |
| `MODEL_BOUNDARY_TIMEOUT_SECONDS` | `90` | Java snapshot can take ~60s per socket |
| `AI_SERVICE_HOST` | `0.0.0.0` | |
| `AI_SERVICE_PORT` | `8090` | |

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
```

## Tests

```bash
cd services/ai-service
py -3 -m pytest
```

Tests mock HTTP. They do not call Epic, Oracle, or a language model.
