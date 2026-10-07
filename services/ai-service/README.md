# Healthcare AI service

Python / FastAPI product unit of the **Healthcare AI & Interoperability Platform**.

The service currently contains three deliberately separate internal capabilities:

1. Model Boundary v1 consumption without model invocation.
2. A disabled-by-default synthetic Gemini summary experiment.
3. **Clinical Follow-up Review**, with application-owned FHIR acquisition, deterministic protocol authority and a legacy/narrative LangGraph/Gemini subflow.

The authoritative follow-up rules are in [`../../docs/contracts/post-consultation-result-review-v1.md`](../../docs/contracts/post-consultation-result-review-v1.md). The FHIR/model boundary decision is [ADR-085](../../docs/adr/ADR-085-python-follow-up-fhir-and-model-authority-boundary.md).

The separate durable operational workflow is defined by [`FOLLOW_UP_REVIEW_WORKFLOW_V1`](../../docs/contracts/follow-up-review-workflow-v1.md) and [ADR-086](../../docs/adr/ADR-086-persistent-follow-up-review-workflow-and-operational-authority-boundary.md).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Process liveness; no service token required. |
| `GET` | `/internal/agent-context` | Authenticated consumption of Java Model Boundary v1; always `modelCalled=false`. |
| `POST` | `/internal/experimental-summary` | Gated Gemini summary for exact fixture `SYN-076-001`. |
| `POST` | `/internal/agent/follow-up` | Gated Clinical Follow-up Review for an allowed `caseId`. |
| `GET` | `/internal/follow-up-review-cases` | Bounded operational review queue; defaults to open cases. |
| `GET` | `/internal/follow-up-review-cases/{reviewCaseId}` | Operational state, immutable trigger provenance and transition history. |
| `POST` | `/internal/follow-up-review-cases/{reviewCaseId}/close` | Idempotent terminal closure with an approved operational outcome. |

All `/internal/*` endpoints require `X-Service-Token` and fail closed when `MODEL_BOUNDARY_SERVICE_TOKEN` is empty, absent or different. Sharing the development token does not merge their contracts. This token authenticates an internal service caller; it does not establish human reviewer identity.

## Environment

Copy `.env.example` to a local untracked `.env` or export variables in the process environment. Uvicorn does not load `.env` automatically. Never commit real credentials.

| Variable | Default/example | Purpose |
|---|---|---|
| `MODEL_BOUNDARY_BASE_URL` | `http://localhost:8081` | Producer used by `/internal/agent-context`. |
| `MODEL_BOUNDARY_PATH` | `/api/model-boundary/v1` | Java v1 contract path. |
| `MODEL_BOUNDARY_TIMEOUT_SECONDS` | `90` | Timeout for the Java v1 consumer. |
| `MODEL_BOUNDARY_SERVICE_TOKEN` | empty | Shared development service token for `/internal/*`; blank is fail-closed. |
| `HUMAN_REVIEW_FORM_SIGNING_SECRET` | empty | Separate server-side secret for close-form and AI-assistance HMAC. The purposes differ. Blank disables both forms. Do not reuse the service token. |
| `AI_SERVICE_HOST` | `0.0.0.0` | Uvicorn bind value; not by itself a production network boundary. |
| `AI_SERVICE_PORT` | `8090` | Python service port. |
| `LLM_EXPERIMENTAL_ENABLED` | `false` | Enables only `/internal/experimental-summary`. |
| `FOLLOWUP_AGENT_ENABLED` | `false` | Existing configuration name that enables Clinical Follow-up Review. |
| `FHIR_BASE_URL` | `http://localhost:8080/fhir` | Authorized FHIR endpoint used by the follow-up HAPI read client. |
| `AI_REVIEW_DB_PATH` | `./data/follow-up-review.sqlite3` | Dedicated file-backed SQLite product store for operational review cases. |
| `INSTITUTIONAL_KNOWLEDGE_DB_PATH` | `./data/institutional-knowledge.sqlite3` | Separate SQLite index for synthetic institutional procedures. Not the review store. |
| `INSTITUTIONAL_KNOWLEDGE_EMBEDDING_MODEL` | `gemini-embedding-001` | Embedding model. Do not reuse `GEMINI_MODEL`. A failed call does not switch models. |
| `INSTITUTIONAL_KNOWLEDGE_MIN_SCORE` | `0.68` | Initial Demo Product V1 retrieval threshold from the first live embedding check. Provisional. Not clinical confidence and not production-calibrated. |
| `GEMINI_API_KEY` | empty | Gemini credential; required for live generation and for live embeddings. |
| `GEMINI_MODEL` | `gemini-flash-latest` | Configured Gemini generation model. |
| `RUN_HAPI_INTEGRATION_TESTS` | `false` | Test-only opt-in for local real-HAPI tests. |
| `RUN_LIVE_GEMINI_TESTS` | `false` | Test-only opt-in for live Gemini generation tests. |
| `RUN_LIVE_EMBEDDING_TESTS` | `false` | Test-only opt-in for live embedding tests. Independent of `RUN_LIVE_GEMINI_TESTS`. |
| `RUN_LIVE_AI_ASSISTANCE_TESTS` | `false` | Test-only opt-in for one live structured assistance call. Independent of the other live flags. |

`FHIR_BASE_URL` is read by the FHIR client rather than the `Settings` dataclass. The live-test flags are read by tests, not by application startup configuration.

`AI_REVIEW_DB_PATH` is not HAPI PostgreSQL. V1 supports one `ai-service` instance and one writer store. The operator owns durable-volume placement, file permissions, backup and storage protection. Standard SQLite does not itself encrypt data at rest; environments using real clinical data require separately approved protected storage. No retention duration or automatic purge is configured.

## Local run

Start local HAPI from the repository root if Clinical Follow-up Review needs it:

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

Then install and run the service:

```powershell
cd services/ai-service
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:MODEL_BOUNDARY_SERVICE_TOKEN = "<local-token>"
$env:FOLLOWUP_AGENT_ENABLED = "true"
$env:FHIR_BASE_URL = "http://localhost:8080/fhir"
$env:GEMINI_API_KEY = "<local-key>"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8090
```

Do not treat this local bind, shared token or local HAPI stack as a production deployment architecture.

## Model Boundary v1 consumer

`GET /internal/agent-context` authenticates the caller, fetches the configured Java `GET /api/model-boundary/v1`, validates the closed contract and returns `received` or `rejected`. It does not send the v1 payload to Gemini and always returns `modelCalled=false`.

This remains independent from Clinical Follow-up Review.

## Synthetic experimental summary

`POST /internal/experimental-summary` remains disabled unless `LLM_EXPERIMENTAL_ENABLED=true`. It accepts only the exact synthetic fixture `SYN-076-001` and uses `GeminiProvider.generate_summary()`.

It does not consume Model Boundary v1 or implement the follow-up protocol. Its historical scope is recorded by ADR-076.

## Clinical Follow-up Review

Request:

```http
POST http://localhost:8090/internal/agent/follow-up
X-Service-Token: <same MODEL_BOUNDARY_SERVICE_TOKEN>
Content-Type: application/json

{"caseId": "SYN-FOLLOWUP-001"}
```

`FOLLOWUP_AGENT_ENABLED` must be `true`. Authentication occurs before the feature gate and request validation:

- missing/wrong/unconfigured token: HTTP 401 with an empty body;
- valid token while disabled: HTTP 503 with `{"detail":"Follow-up agent is disabled"}`;
- invalid request after enablement: HTTP 422;
- unexpected workflow failure: HTTP 502 with `{"detail":"Follow-up workflow failed"}`;
- valid projected workflow result: HTTP 200.

The retained environment/error string uses “agent” for compatibility; the productive capability name is **Clinical Follow-up Review**.

### Mandatory acquisition and deterministic authority

For every accepted request, the application binds the authorized case and, before LangGraph, acquires:

- the unique Patient identified by `Patient.identifier` system `https://lab.local/followup-case` and value `caseId`;
- the Patient resource;
- finished Encounters for that Patient;
- final Observations for that Patient;
- Appointments for that Patient.

Collection searches use page size 25, at most 4 pages and at most 100 unique resources per type. Search completeness is recorded explicitly; partial traversal cannot prove absence.

The application evaluates `POST_CONSULTATION_RESULT_REVIEW_V1` over the authorized immutable snapshot. Gemini does not choose the mandatory reads and cannot set protocol, clinical-assessment, human-review or action fields.

### Missed follow-up review

`POST /internal/agent/missed-follow-up` uses the same authentication, feature flag and `{"caseId": "..."}` request. It resolves the authorized Patient and reads Appointments only. A past `noshow` without a confirmed future `booked` Appointment matches. Each matched Appointment reuses or creates one review case. `cancelled` is not a trigger. The response has no narrative and no `Patient.id`. See [MISSED_FOLLOW_UP_REVIEW_V1](../../docs/contracts/missed-follow-up-review-v1.md).

The shared `/review-cases` pages show this protocol as "Missed follow-up review" and keep the technical protocol id. Opening a case reads current Appointments and does not rewrite the original trigger. Those pages do not retrieve institutional knowledge.

### Narrative agent subflow

After deterministic evaluation, the existing LangGraph/Gemini subflow may run when the workflow is available. It retains two authorized read tools:

- `get_patient_followup_context`;
- `get_patient_appointments`.

The model may choose between these narrative tools, but cannot supply a Patient id or arbitrary FHIR query. Tool policy requires the already authorized `caseId`; unknown tools and `send_message` are denied and audited before `ToolNode` execution.

Tool results may contain FHIR-derived payloads only through these explicit contracts. This is not general permission to send arbitrary FHIR context to Gemini.

`MAX_MODEL_TURNS` is 4. Automatic function calling is disabled. When a final model message carries a valid structured `follow_up_required` value (`true`, `false` or `unknown`), that value is projected. After tool use, an unstructured response triggers one closing request for the structured object; if the final or closing response still omits a valid structured decision, legacy `followUpRequired="unknown"` remains possible. Free text is never parsed to infer the value, and this legacy field does not control deterministic protocol authority.

### Response

A matched example has this shape:

```json
{
  "runId": "<uuid>",
  "caseId": "SYN-FOLLOWUP-001",
  "status": "completed",
  "context": {"patient": "resolved", "observation": "with_resources"},
  "schedule": {"check": "checked", "classifications": ["NONE"]},
  "clinicalAssessment": {"status": "not_performed"},
  "humanReview": {
    "status": "required",
    "reason": "deterministic_post_consultation_protocol_match"
  },
  "action": {"status": "proposed", "type": "review_follow_up_case"},
  "protocol": {
    "id": "POST_CONSULTATION_RESULT_REVIEW_V1",
    "evaluationStatus": "matched",
    "reasonCodes": ["post_consultation_result_requires_review"],
    "matchedResources": ["Encounter/encounter-id", "Observation/observation-id"]
  },
  "reviewCase": {
    "reviewCaseId": "<uuid>",
    "status": "open",
    "version": 1
  },
  "followUpRequired": "unknown",
  "answer": "Narrative model output.",
  "evidence": []
}
```

Top-level `status` describes execution, not protocol evaluation. Internal execution statuses map as:

- `finish` -> `completed`;
- `denied` -> `denied`;
- `unavailable` -> `unavailable`;
- `limit` -> `limit`.

`clinicalAssessment.status` remains `not_performed`. When the protocol matches, `humanReview.status=required` remains the response-level protocol requirement. The separate `reviewCase` projection identifies the durable operational work item. `action.status=proposed` does not execute an external action.

The review case is created or reused after deterministic evaluation and committed before the narrative model runs. If matched-case persistence is unavailable, the endpoint returns HTTP 503 and does not invoke Gemini. Once committed, a later model failure cannot roll the case back. The same deterministic event reuses its case even when that case is already closed; consequently `humanReview.status=required` and `reviewCase.status=closed` can validly appear together.

`answer` and `followUpRequired` remain legacy model-owned output and do not control `protocol`, `clinicalAssessment`, `humanReview` or `action`.

`evidence` identifies resources returned through narrative tools. `protocol.matchedResources` identifies resources used by the deterministic rule. They are intentionally different provenance sets.

### Durable operational review workflow

Only a deterministic `MATCHED` result creates a case. Identity uses SHA-256 over versioned canonical JSON containing exact `caseId`, exact `protocolId` and sorted unique `matchedResources`. Run ids, reason codes, timestamps and model output do not participate. FHIR logical resource versions are not part of V1 identity, so the same logical resource references reuse the existing case after closure.

The lifecycle is exactly `open -> closed`. Closure outcomes are exactly:

- `follow_up_coordination_planned`;
- `review_completed_no_operational_action`.

These outcomes are operational and do not express clinical normality, urgency, necessity, diagnosis, treatment or recommendation.

Queue example:

```http
GET /internal/follow-up-review-cases?status=open&limit=25
X-Service-Token: <same MODEL_BOUNDARY_SERVICE_TOKEN>
```

The queue supports exact `caseId`, a maximum limit of 100 and an opaque keyset cursor. Ordering is oldest first by creation time and review-case id. Durable and cursor timestamps use exact `YYYY-MM-DDTHH:MM:SS.ffffffZ` form, and cursor JSON rejects duplicate member names. Operational detail returns minimized protocol provenance and `created`/`closed` transition history. It does not read live FHIR.

Current clinical inspection for an open case is a separate read:

```http
GET /internal/follow-up-review-cases/<review-case-uuid>/clinical-context
X-Service-Token: <same MODEL_BOUNDARY_SERVICE_TOKEN>
```

`CLINICAL_REVIEW_CONTEXT_V1` resolves the Patient again from the persisted `caseId`, rereads the exact provenance Encounter and Observation, and repeats the bounded Appointment search. It does not rerun the protocol, call Gemini, or store the projection. A closed case returns HTTP 409. The contract is [CLINICAL_REVIEW_CONTEXT_V1](../../docs/contracts/clinical-review-context-v1.md).

Synthetic review demo, same process and port:

```text
GET /review-cases
GET /review-cases/<review-case-uuid>
POST /review-cases/<review-case-uuid>/close
POST /review-cases/<review-case-uuid>/ai-assistance
```

These pages are HTML for a controlled synthetic demo. They are not a user login. Anyone who can reach the process can open them. `caseId` is an operational identifier, not a patient name or `Patient.id`. The service token stays on the server and is not rendered. `MODEL_BOUNDARY_SERVICE_TOKEN` protects internal service calls only. The close form and the AI-assistance form are signed with `HUMAN_REVIEW_FORM_SIGNING_SECRET`, a different server-side value, and with different HMAC purposes. A close token does not authorize generation, and a generation token does not authorize close. If that signing secret is missing or blank, neither form is issued and both POSTs are refused. The close HMAC binds the case id, expected version and expiry. The assistance HMAC binds purpose `ai-assistance`, the case id and expiry. Neither is authentication, authorization, single-use, or replay-proof. The review-case version check remains authoritative for close. Current clinical context is read while the case is open and is not stored. A closed case shows the operational record and history without a historical clinical snapshot and without a generate button. If the current context cannot be loaded, the operational close form remains available. Legacy Gemini narrative is not shown. Explicit AI assistance is a separate section and is not stored. This is not a production clinical application. See [ADR-088](../../docs/adr/ADR-088-server-rendered-human-review-demo.md) and [ADR-091](../../docs/adr/ADR-091-ai-assisted-review.md).

Closure example:

```http
POST /internal/follow-up-review-cases/<review-case-uuid>/close
X-Service-Token: <same MODEL_BOUNDARY_SERVICE_TOKEN>
Content-Type: application/json

{"expectedVersion":1,"outcome":"follow_up_coordination_planned"}
```

The state update and append-only `closed` event are atomic. Retrying the same outcome returns the existing case without a duplicate event. A stale open version or different outcome after closure returns HTTP 409.

### FHIR and HAPI behavior

The follow-up client performs GET-only reads. It retries transport loss and transient HTTP 408, 429, 500, 502, 503 and 504 up to three attempts including the first. Redirects are disabled.

An ordinary same-resource continuation must preserve the exact resource endpoint and every application-controlled initial query parameter, including Patient/subject, status and `_count` where present. Only the recognized `page` and `token` paging values may be added or changed.

Separately, the client supports the narrowly constrained HAPI 8.10 base-endpoint continuation shape. That branch preserves configured origin and base path, page size, traversal token and offset progression. The two continuation shapes cannot be mixed during one traversal. Unsafe, cyclic, malformed or cross-origin links fail closed. Opaque paging tokens are not logged and are not authorization.

See the [V1 contract](../../docs/contracts/post-consultation-result-review-v1.md) for exact completeness, reference, timestamp, appointment and failure semantics.

### Known limitations

- No FHIR writes or autonomous messages.
- No clinical interpretation, diagnosis, severity, urgency or treatment decision.
- No general LangGraph checkpoint or conversational memory; persistence is limited to operational review cases.
- No assignment, claiming, acknowledgement state or verified human reviewer identity.
- SQLite V1 is single-instance and does not provide multi-replica persistence.
- Standard SQLite storage is not encrypted at rest by this application.
- No enterprise IAM/RBAC or tenancy.
- No production network or secret-management architecture.
- No production authorization/governance conclusion for real clinical data sent to Gemini.
- Institutional retrieval is a synthetic demo/lab index. It is not production RAG, not clinically calibrated, and not connected to review or FHIR.

## Institutional knowledge retrieval

`POST /internal/knowledge/retrieve` returns bounded synthetic procedure chunks for `POST_CONSULTATION_RESULT_REVIEW_V1` or `MISSED_FOLLOW_UP_REVIEW_V1`. It uses the same `X-Service-Token` as the other internal routes. It is not linked from `/review-cases`.

The corpus is the repository directory `knowledge/institutional/`. Chunks are deterministic. Vectors are cached in `INSTITUTIONAL_KNOWLEDGE_DB_PATH`. Cosine comparison runs in process. There is no vector database and no retrieval framework.

Gemini is used only through `client.models.embed_content` and `INSTITUTIONAL_KNOWLEDGE_EMBEDDING_MODEL`. Indexing a chunk whose content hash or model is new requires the embedding provider. A semantic query also embeds `queryText`. If that query embedding is unavailable, the status is `UNAVAILABLE` and the HTTP status is 503. The service does not substitute a lexical search and call it a semantic result. `FOUND` and `NO_RELEVANT_GUIDANCE` are HTTP 200.

The default score cutoff `0.68` is the initial demonstration threshold selected from the first live embedding validation. It is provisional and must be reevaluated when the corpus grows, document versions change, the embedding model changes, or the retrieval evaluation set grows. It is not validated, calibrated, production-ready, or clinically meaningful. Retrieved text is institutional data, not an instruction and not a clinical conclusion. The retrieval endpoint does not generate an explanation. See [ADR-090](../../docs/adr/ADR-090-institutional-knowledge-rag.md) and the [V1 contract](../../docs/contracts/institutional-knowledge-retrieval-v1.md).

## AI-assisted review

`POST /review-cases/<review-case-uuid>/ai-assistance` asks for one explanation of an open review case. The button is `Generate AI assistance`. GET does not generate. The service reads Clinical Review Context and institutional retrieval in process. It does not call `/internal/knowledge/retrieve` over HTTP and it does not add an internal assistance route.

The server query is `post consultation result follow-up` or `missed follow-up appointment`. Observation values, `code.text`, resource ids, references, timestamps and patient identity are not sent to Gemini. `NO_RELEVANT_GUIDANCE` and retrieval `UNAVAILABLE` stop before Gemini. A successful call uses `GEMINI_MODEL` once, with JSON schema, `thinking_level=low` for the current Gemini 3.8 Flash alias, and a 1024-token output bound. `MAX_TOKENS` is discarded. Summary and each review point must cite retrieved chunks. The page shows server-projected title, version, section and source text apart from the generated prose. The score is not shown.

Nothing is stored in the review database. The generation POST returns 303 to the case page. One process-local ticket lets that next GET show the assistance once. Refresh and any later GET say `Not generated` and do not call Gemini again. Close behavior is unchanged. A blank signing secret hides the button and rejects the POST before FHIR, retrieval and Gemini. This is a synthetic demo. It is not validated clinical assistance and it is not production-ready. See [ADR-091](../../docs/adr/ADR-091-ai-assisted-review.md) and the [V1 contract](../../docs/contracts/ai-assisted-review-v1.md).

Startup initializes this index without blocking review-case startup. A failed corpus or a missing embedding credential leaves retrieval unavailable and leaves the follow-up routes operating under their own rules. The generated SQLite file is local and must not be committed.

## Tests and evaluation

### Deterministic suite

```bash
cd services/ai-service
py -3 -m pytest
```

The default suite uses fake/scripted providers and in-memory or mocked transports. It does not require Gemini, Epic, Oracle, a live API key or live HAPI. It protects closed HTTP contracts, authentication/gates, workflow ordering, model/tool policy, retry behavior, case isolation, protocol semantics and pagination validation.

Dedicated temporary-file SQLite tests additionally protect schema migration, restart durability, deterministic identity, unique creation, optimistic closure, concurrent races, queue pagination and data minimization.

### Focused protocol and workflow coverage

```powershell
py -3 -m pytest `
  tests/test_post_consultation_review.py `
  tests/test_post_consultation_pagination.py `
  tests/test_post_consultation_workflow.py `
  tests/test_langgraph_followup_workflow.py `
  tests/test_langgraph_gemini_fhir_followup.py
```

These tests protect mandatory acquisition, completeness/failure semantics, temporal and appointment rules, concurrency/case isolation, deterministic projection and independence from legacy model output.

### Deterministic evaluation harness

```bash
py -3 -m pytest tests/test_followup_evaluation.py
```

The harness runs the productive workflow with scripted model replies and in-memory FHIR data. It checks tool/policy behavior and expected deterministic protocol outcomes. It does not use another model as a judge and does not establish clinical effectiveness or safety.

### Real local HAPI

In PowerShell, with the local HAPI service running:

```powershell
$env:RUN_HAPI_INTEGRATION_TESTS = "true"
py -3 -m pytest tests/test_langgraph_fhir_hapi.py tests/test_langgraph_followup_workflow.py tests/test_langgraph_gemini_fhir_followup.py
```

This opt-in category exercises productive HAPI reads, including multipage traversal. It does not require live Gemini unless the Gemini opt-in is also enabled.

### Live Gemini

```powershell
$env:RUN_HAPI_INTEGRATION_TESTS = "true"
$env:RUN_LIVE_GEMINI_TESTS = "true"
py -3 -m pytest tests/test_langgraph_gemini_fhir_followup.py
```

Live follow-up coverage requires both flags and a configured key/model. The experimental-summary live test also uses `RUN_LIVE_GEMINI_TESTS`, but remains a separate endpoint and contract. Live Gemini is never part of the default deterministic suite.

### Live embeddings

`RUN_LIVE_EMBEDDING_TESTS` is separate from `RUN_LIVE_GEMINI_TESTS`. It checks `google-genai==2.24.0` against `INSTITUTIONAL_KNOWLEDGE_EMBEDDING_MODEL` and runs golden queries over the synthetic corpus. It does not load `.env` by itself and it does not belong to the default suite.

```powershell
$env:RUN_LIVE_EMBEDDING_TESTS = "true"
$env:RUN_LIVE_GEMINI_TESTS = "false"
py -3 -m pytest tests/test_live_institutional_embeddings.py -s
```

`GEMINI_API_KEY` must already be in the process environment. Exact floating-point scores are not a contract. Deterministic tests use a fake embedding provider and do not call Gemini.

### Live AI assistance

`RUN_LIVE_AI_ASSISTANCE_TESTS` is separate from `RUN_LIVE_GEMINI_TESTS` and `RUN_LIVE_EMBEDDING_TESTS`. It uses synthetic facts, the real institutional index and one real structured generation. It does not require HAPI, and it does not assert exact wording.

```powershell
$env:RUN_LIVE_AI_ASSISTANCE_TESTS = "true"
$env:RUN_LIVE_GEMINI_TESTS = "false"
$env:RUN_LIVE_EMBEDDING_TESTS = "false"
py -3 -m pytest tests/test_live_ai_assistance.py -s
```

### Institutional knowledge

```powershell
$env:RUN_LIVE_GEMINI_TESTS = "false"
$env:RUN_LIVE_EMBEDDING_TESTS = "false"
py -3 -m pytest tests/test_institutional_knowledge.py
```

Test counts are release evidence, not architectural requirements; the protected categories and invariants are the durable documentation.

## Logging and audit

The HTTP layer logs correlation id, method, path and bounded status without secrets. Tool-policy audit records `run_id`, `case_id`, tool name, decision, policy version, reason and timestamp. Durable review `created` and `closed` events are operational transition provenance; they are not security, clinical or verified-human audit.

Application logs must not contain service tokens, API keys, prompts, completions, thought signatures, FHIR payloads or raw HAPI paging tokens. Institutional retrieval logs may include correlation id, route, status, protocol id, document id, version, chunk id, result count and duration. They must not include `queryText`, document text, chunk text, vectors, the API key or the service token. AI-assistance logs may include correlation id, review-case id, protocol id, assistance status, retrieval status, citation count, whether the model was called, and duration. They must not include the prompt, model input, model output, summary, review points, limitations, query text, chunk text, observation values or patient facts. The current in-memory/development audit behavior is not a durable production audit system.
