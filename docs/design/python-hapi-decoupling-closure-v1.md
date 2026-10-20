# PYTHON_HAPI_DECOUPLING_CLOSURE_V1

Closure record for operational Python reads. HEAD at this revision: `5514ddb0bbd535fa9126d868773acfe8ea5e4429` on `feature/follow-up-agent`. Sections 1 to 10 are the assessment written at `df79a05ee0c2c23423ef17e6d11663bc24334585`. Sections 11 to 16 record what the later increments implemented. Where they disagree, sections 11 to 16 are the current statement.

This revision does not change code, tests, scripts, contracts, or ADR text. It does not authorize a push or a merge.

This document does not replace [python-hapi-decoupling-assessment-v1](python-hapi-decoupling-assessment-v1.md). That assessment records steps 3 to 5 as implemented and step 6 as open. The laboratory E2E in [e2e-interoperability-validation-v1-results](../results/e2e-interoperability-validation-v1-results.md) observed Python `httpx` calls to Clinical Read on the missed-follow-up path. It did not execute the narrative route, and it does not prove that every remaining Python entry point is free of HAPI.

Statements about source are from the files named below. A conclusion that is not a direct import or constructor is marked as inferred.

## 1. Current state

The three operational factories construct `ClinicalReadClient`:

| Factory | File | Client |
|---|---|---|
| `build_live_followup_workflow` | `services/ai-service/app/langgraph_followup_workflow.py` | `ClinicalReadClient.from_settings` |
| `_live_adapter` | `services/ai-service/app/missed_follow_up_service.py` | `ClinicalReadClient.from_settings` inside `FollowUpFHIRAdapter` |
| `_fhir_client` | `services/ai-service/app/clinical_review_context_http.py` | `ClinicalReadClient.from_settings`, unless `app.state.clinical_context_fhir_client` is set |

`app/main.py` registers `POST /internal/agent/follow-up`, `POST /internal/agent/missed-follow-up`, and `GET /internal/follow-up-review-cases/{review_case_id}/clinical-context`. The open-case HTML reader calls `clinical_context_service`, which uses the same `_fhir_client`. No production factory in `app/` constructs `HapiReadClient`.

`HapiReadClient` and `hapi_base_url()` remain in `services/ai-service/app/langgraph_fhir_hapi.py`. `hapi_base_url()` reads `FHIR_BASE_URL` and otherwise uses `http://localhost:8080/fhir`. At the assessment HEAD, `clinical_review_context.py` imported `ExactResourceNotFound` from that module. Increment A moved that import to `langgraph_fhir_client.py`, where the class is defined. The HAPI module still re-exports it. Deleting the HAPI file would still break laboratory imports. See section 11.

`GET /internal/agent-context` uses `MODEL_BOUNDARY_BASE_URL` and `MODEL_BOUNDARY_PATH` for Model Boundary v1. That is a different contract from Clinical Read. `ClinicalReadClient.from_settings` reuses the same base URL and service token. It does not call `/api/model-boundary/v1`.

Java `local-hapi` stays a Clinical Read destination in `services/fhir-integration-service`. Retiring the Python client does not retire that destination.

## 2. Reference inventory

Classification: (1) active production code, (2) unused legacy, (3) automated test, (4) laboratory script, (5) configuration, (6) historical documentation.

### `HapiReadClient` and `langgraph_fhir_hapi`

| Location | Class | What it does |
|---|---|---|
| `app/langgraph_fhir_hapi.py` | 1 | Defines `HapiReadClient`, `hapi_base_url`, `ACCEPT`, continuation rules, and retry. Reachable by import. Not constructed by the three factories. |
| `app/clinical_review_context.py` | 1 | Imports `ExactResourceNotFound` from `app.langgraph_fhir_client` after Increment A. Used by `_read_provenance` on the clinical-context path. |
| `app/langgraph_fhir_client.py` | 6 | Module comment says HTTP lives in `HapiReadClient`. The protocol and `ExactResourceNotFound` live here. `ClinicalReadClient` also performs HTTP. |
| `scripts/demo-reproducibility/prepare_demo_cases.py` | 4 | `LoopbackFhirGateway` imports `ACCEPT` and `HapiReadClient` from the HAPI module and constructs `HapiReadClient(self._base_url)` when no reader is injected. After Increment C3, `ExactResourceNotFound` comes from `langgraph_fhir_client`. `reset_demo_cases.py` loads this module and does not construct the gateway. |
| `tests/test_langgraph_fhir_hapi.py` | 3 | Unit coverage plus opt-in live HAPI tests behind `RUN_HAPI_INTEGRATION_TESTS`. |
| `tests/test_post_consultation_workflow.py`, `test_post_consultation_pagination.py` | 3 | Inject `HapiReadClient` against an in-process HTTP handler. |
| `tests/test_langgraph_followup_workflow.py`, `test_langgraph_gemini_fhir_followup.py` | 3 | Some cases inject `HapiReadClient`. Live cases call `hapi_base_url()`. `test_application_consumer_does_not_need_langgraph` asserts the workflow class source does not name `HapiReadClient`. |
| `tests/test_missed_follow_up_service.py` | 3 | One case sets `app.state.clinical_context_fhir_client` to a lambda that returns `HapiReadClient`. |
| `tests/test_clinical_review_context.py`, `test_human_review_client.py`, `test_ai_assisted_review.py`, `test_demo_reproducibility_prepare.py` | 3 | Import `ExactResourceNotFound` or `_EXACT_RESOURCE_TYPES` from the HAPI module. The context tests also set `FHIR_BASE_URL` empty to assert it is not leaked. |
| `tests/test_architecture.py` | 3 | Lists `langgraph_fhir_hapi.py` in `LESSON_MODULES` and reads the file. |
| `tests/test_clinical_read_client.py` | 3 | Asserts the two live factories and `ClinicalReadClient` source do not contain the string `HapiReadClient`. |
| `services/ai-service/README.md`, `.env.example` | 5 | Document `FHIR_BASE_URL` as the follow-up HAPI client. |
| `docs/design/python-hapi-decoupling-assessment-v1.md` | 6 | Original inventory still names `HapiReadClient` on the three routes. The reconciliation table at the top supersedes that inventory for the factories. |
| `docs/architecture/README.md`, `docs/roadmap.md`, `docs/adr/ADR-095-clinical-normalization-boundary.md` | 6 | Record that the client remains and that step 6 is open. |
| `docs/results/e2e-interoperability-validation-v1-results.md`, `docs/design/e2e-interoperability-validation-v1.md` | 6 | Record the residual client and the captured missed-follow-up log. |
| `services/ai-service/docs/consolidacion-arquitectura-followup.md` | 6 | Describes the pre-migration chain. |
| `docs/contracts/java-interoperability-readiness-v1.md` | 6 | Untracked and stale. It still says the follow-up routes use `HapiReadClient`. This closure does not edit it. |
| `docs/ai-governance/regulatory-context.md` | 6 | Names the bounded read client file. |

No dynamic `importlib` load of `langgraph_fhir_hapi` exists under `app/`. The demo test loads `prepare_demo_cases.py` by path. `reset_demo_cases.py` loads the same file by path. FastAPI route registration in `main.py` does not import the HAPI module. Inferred: a request to the three clinical routes does not construct `HapiReadClient` unless a test replaced `clinical_context_fhir_client`.

### `FHIR_BASE_URL`

| Location | Class | What it does |
|---|---|---|
| `app/langgraph_fhir_hapi.py` | 1 | Only runtime reader of the variable. |
| `services/ai-service/.env.example`, `services/ai-service/README.md` | 5 | Default `http://localhost:8080/fhir`. |
| Tests named above | 3 | Set or call it for the legacy client and for leak checks. |
| `docs/tasks/001-project-bootstrap.md`, `docs/tasks/task-034-oracle-health-real-capability-discovery.md` | 6 | Task text. `EPIC_FHIR_BASE_URL` in task 047 is a different name. |
| Java `application.yml`, `docs/fhir/*`, ADR-081, ADR-083 | 6 | Java destination `local-hapi`. Not the Python variable. |

### `ClinicalReadClient` and `MODEL_BOUNDARY_BASE_URL`

| Location | Class | What it does |
|---|---|---|
| `app/clinical_read_client.py` | 1 | Client. `from_settings` uses `Settings.model_boundary_base_url`, the service token, and `model_boundary_timeout_seconds`. |
| `app/config.py` | 5 | `MODEL_BOUNDARY_BASE_URL` default `http://localhost:8081`. `MODEL_BOUNDARY_SERVICE_TOKEN` default empty. |
| The three factories and `clinical_review_context_http.py` | 1 | Construct the client. |
| `app/consumer.py` path via `/internal/agent-context` | 1 | Uses the same base URL for Model Boundary v1, not for Clinical Read. |
| `tests/test_clinical_read_client.py`, `tests/test_clinical_review_java_context.py` | 3 | Handler-level coverage of the client and the context service. |
| `.env.example`, `services/ai-service/README.md` | 5 | Document the Model Boundary base URL. |
| Clinical Read contract, architecture README, E2E design and results | 6 | Describe the operational caller. |

### Direct FHIR URLs that are not `HapiReadClient`

`scripts/fhir/load-synthetic-patients.ps1` defaults to `http://localhost:8080/fhir` and does not import the Python client. `prepare_demo_cases.py` also `PUT`s FHIR with `httpx` and `GET`s two demo Patient ids with `httpx`. Those writes are outside Clinical Read. Docs under `docs/fhir/` and `docs/tasks/` name `http://localhost:8080/fhir` as the local server. Java keeps that URL as the `local-hapi` base.

## 3. Consumer graph

```text
POST /internal/agent/follow-up
  -> run_followup_http
  -> build_live_followup_workflow
  -> ClinicalReadClient
  -> FollowUpWorkflow
       -> PostConsultationContextReader.search / Patient GET by id
       -> GeminiFhirFollowUp on the same client
            -> tool cache on the protocol ledger
            -> fallback after Increment B: transport.search on the protocol path

POST /internal/agent/missed-follow-up
  -> _live_adapter
  -> ClinicalReadClient.search / Patient GET by id

GET clinical-context and open-case HTML
  -> clinical_context_service
  -> ClinicalReadClient.search / read_exact
  -> ExactResourceNotFound imported from langgraph_fhir_client

prepare_demo_cases.py / reset_demo_cases.py
  -> LoopbackFhirGateway
  -> HapiReadClient.read_exact
  -> httpx PUT and Patient GET to the FHIR base URL

Opt-in tests with RUN_HAPI_INTEGRATION_TESTS
  -> HapiReadClient(hapi_base_url())
  -> FHIR_BASE_URL or http://localhost:8080/fhir

Java Clinical Read source local-hapi
  -> application.yml base-url
  -> HAPI
  Python is not in this edge
```

| Consumer | Dependency | How it is built | Trigger | Reachable from the running app | Tests | Removal risk |
|---|---|---|---|---|---|---|
| `build_live_followup_workflow` | `ClinicalReadClient` direct | `from_settings(Settings.from_env())` | `POST /internal/agent/follow-up` | Yes, when `FOLLOWUP_AGENT_ENABLED=true` | `test_clinical_read_client.py` asserts the source. Workflow tests mostly inject another client. Narrative live call was not part of the E2E. | Low for HAPI. The route no longer constructs `HapiReadClient`. |
| `_live_adapter` | `ClinicalReadClient` direct | Same factory | `POST /internal/agent/missed-follow-up` | Yes | `test_clinical_read_client.py`, `test_missed_follow_up_service.py`. E2E stages AGT-01 through AGT-05 observed this path. | Low for HAPI. |
| `_fhir_client` | `ClinicalReadClient` direct | Same factory, or the state override | Clinical-context GET and `human_review_client` | Yes | `test_clinical_review_java_context.py`. AGT-04 observed the context body. | Low for the HTTP client. High if `langgraph_fhir_hapi.py` disappears while the exception import stays. |
| `ClinicalReviewContextService._read_provenance` | `ExactResourceNotFound` indirect | Import from the HAPI module | Same context routes, after an open matched case | Yes | Context and human-review tests import the same symbol | High for a file delete. The symbol can move to `langgraph_fhir_client` without changing behavior. |
| `LoopbackFhirGateway` | `HapiReadClient` direct, plus raw `httpx` writes | `HapiReadClient(base_url)` | CLI `prepare_demo_cases.py`; `reset_demo_cases.py` loads it | No HTTP route | `test_demo_reproducibility_prepare.py` | High for the demo CLI. Clinical Read has no write route, so the PUT cannot move there. |
| Opt-in HAPI tests | `HapiReadClient` direct | `hapi_base_url()` | `RUN_HAPI_INTEGRATION_TESTS=true` only | No | The tests themselves | Medium. They are the remaining Python process that calls HAPI when the flag is on. |
| In-memory workflow tests | `HapiReadClient` direct | Constructor with `httpx.Client` | pytest | No | Pagination, retry, and bundle behavior | Medium. Those tests encode HAPI continuation behavior that `ClinicalReadClient` does not implement. |
| Java `local-hapi` | Java FHIR client | `application.yml` | Clinical Read when source is `local-hapi` | Java process | Java Clinical Read tests, not this inventory | None for the Python deletion. This edge must stay. |

`FollowUpFHIRAdapter` is an indirect consumer. It calls whatever object `ClientFHIRTransport` holds. The live factories pass `ClinicalReadClient`. Tests can still pass `HapiReadClient`. The adapter does not import the HAPI module.

## 4. Compatibility

Both clients implement `get` and `search` and return `BoundedSearchResult` from `search`. That shared shape is not functional equivalence.

| Behavior | `HapiReadClient` | `ClinicalReadClient` |
|---|---|---|
| Wire | `GET {FHIR_BASE_URL}/{path}`, `Accept: application/fhir+json` | `GET {MODEL_BOUNDARY_BASE_URL}/api/clinical-read/v1/...`, `Accept: application/json`, header `X-Service-Token` |
| Auth | None | Empty token raises `ReadClientError` before the request. HTTP 401 is `clinical read unavailable`. |
| Resources | `get` accepts any path. `read_exact` allows Encounter, Observation, Appointment. | `get` allows only `Patient/{id}`, `Encounter/{id}`, `Observation/{id}`, `Appointment/{id}` with no query. `read_exact` allows the same three types as HAPI, not Patient. |
| Patient search | Returns a FHIR Bundle | `search` maps `identifier=system\|value` to `identifierSystem` and `identifierValue`, then returns resources from the envelope. |
| Encounter search | Any query the caller sends; the adapter sends `patient` and `status=finished` | Requires `patient` and `status`. `_count` is accepted and not forwarded. |
| Observation search | Adapter protocol path uses `subject` and `status=final` | Accepts `patient` or `subject`, not both, plus `status`. |
| Appointment search | Adapter sends `patient` | Requires `patient`. |
| `get` on a search path | Returns the Bundle. Used by `patient_id_for_case`, `get_observations`, and `get_patient_appointments`. | Rejects any query with `clinical read path is not authorized`. |
| Pagination | Walks a HAPI next link or a same-origin `page`/`token` link. Bounds 25, 4 pages, 100 ids. | Does not walk links. Maps Java `collectionStatus` `complete` or `incomplete`. Java applies 25/4/100 on `local-hapi` and `limit=100` on Mini HIS. |
| Incomplete | `INCOMPLETE_LIMIT` when the client stops inside its walk | `INCOMPLETE_LIMIT` only when the envelope says `incomplete`. |
| Exact 404 | Any HTTP 404 on `read_exact` is `ExactResourceNotFound` and is not retried | `ExactResourceNotFound` only when status is 404 and the body is `{"error":"not_found"}`. Any other 404 is unavailable. |
| Other errors | `ReadClientError` with `HTTP {status}` or `transport failed`. Search becomes `FAILED`. | One message, `clinical read unavailable`. Search becomes `FAILED`. |
| Retry | Three attempts for 408, 429, 500, 502, 503, 504 | No retry. |
| Timeout | Constructor default 5 seconds | `MODEL_BOUNDARY_TIMEOUT_SECONDS` through settings. |
| Redirects | A 3xx is an error | `follow_redirects=False` |
| Response | Raw JSON object | Exact read unwraps `resource`. Search unwraps `resources`. |
| Writes | None on this class. The demo script writes with `httpx`. | None. The contract has no write route. |

The protocol methods `resolve_patient_for_protocol`, `search_encounters_for_protocol`, `search_observations_for_protocol`, and `search_appointments_for_protocol` call `search`. `get_patient` calls `get("Patient/{id}")`. Clinical context calls `search` and `read_exact`. Those calls match the Clinical Read translator.

The tool fallbacks do not. `make_followup_tool` and `make_appointments_tool` reuse the protocol ledger when the matching collection is `COMPLETE`. If that cache does not apply, they call `patient_id_for_case`, `get_observations`, or `get_patient_appointments`, and those methods call `get` with a search path. `ClinicalReadClient.get` rejects that path. On the current workflow, an `UNAVAILABLE` protocol returns before `invoke`, and a `PARTIAL` observation or appointment collection makes the tool raise before `get`. Inferred from that control flow: the successful and the unavailable live runs do not need the search-shaped `get`. The methods remain on the object the narrative engine holds, and they are not equivalent. The E2E did not call `POST /internal/agent/follow-up`, so this fallback was not observed live.

`_count=2` on patient resolution and `_count=25` on the other protocol searches are not sent to Java. Uniqueness of the patient identifier search is enforced in Java for Mini HIS (more than one match is `invalid_source`). For `local-hapi`, the contract says a search returns the bounded collection; it does not say the server stops at two Patient matches. The adapter still rejects a patient search that is not exactly one authorized match when the collection is `complete`. A complete collection with two matches remains a protocol failure. An incomplete patient collection is also a failure. That difference is real and is not closed by this document.

## 5. Removal risks

Deleting `langgraph_fhir_hapi.py` and every `FHIR_BASE_URL` reference in one change breaks the current tree:

- `clinical_review_context.py` fails to import, so clinical context and the open-case page fail at import time.
- `prepare_demo_cases.py` and `reset_demo_cases.py` fail when the gateway is constructed.
- The tests listed in section 2 fail, including `test_architecture.py`, which requires the file to exist.
- Opt-in Python tests that seed HAPI with `httpx.put` lose their reader. Java can still read HAPI.
- README and `.env.example` would describe a client that no longer exists. That is a documentation fix, not a runtime break.

Leaving the module in place keeps a reachable direct FHIR client. Any future caller that imports `HapiReadClient` bypasses Clinical Read, the service token, and the Mini HIS normalizer. The E2E log cannot detect that future caller.

`ClinicalReadClient` is not a drop-in for `get` on a search URL, for HAPI page links, or for FHIR writes. Treating it as one would make the tool fallback and the demo loader fail.

Java `local-hapi` and `scripts/fhir/load-synthetic-patients.ps1` are independent of this deletion. Removing them is out of scope.

## 6. Alternatives

### A. Delete the legacy client and its references now

The three HTTP factories would keep working, because they already construct `ClinicalReadClient`. The delete itself does not compile: the exception import, the demo gateway, and the tests still name the module. A is safe only after those references move. It is not safe as the first edit.

### B. Keep the client only in isolated laboratory tools

This matches `prepare_demo_cases.py`, which must `PUT` FHIR and must read Encounter, Observation, and Appointment before those writes. Clinical Read cannot host that write. It also matches the opt-in `RUN_HAPI_INTEGRATION_TESTS` reader.

It does not match the production import in `clinical_review_context.py`. A laboratory-only module cannot stay on the import path of the request process. B is a placement rule for the demo writer, not a complete closure.

### C. Move the remaining consumers, then delete the operational client

Move the `ExactResourceNotFound` import to `langgraph_fhir_client.py`. Point the automated protocol and context tests at `ClinicalReadClient` or an in-memory `FHIRReadClient`. Keep a laboratory FHIR reader and writer for the demo script and for opt-in HAPI checks, outside the FastAPI import graph. Delete `HapiReadClient` from `app/` only after those imports are gone. Update README and `.env.example` in that same change so `FHIR_BASE_URL` is no longer described as the follow-up client.

C is the alternative that matches the code. A is the last step of C. B is the exception for the demo write path.

## 7. Recommended strategy

The assessment recommended C and said not to delete `langgraph_fhir_hapi.py` until the production import and the demo import no longer needed it. That deletion was not done. The isolation design chose its alternative B, and Increments C2 to C4 implemented that choice. See section 12.

Reason: the operational routes already read through Clinical Read. The E2E observed that for missed follow-up and clinical context. The obstacle to step 6 is the remaining import, the demo gateway, and the tests that still construct the legacy client, plus the search-shaped `get` that `ClinicalReadClient` does not implement. Deleting the file first would break clinical context at import time. Keeping it as the app's HTTP client would leave step 6 open.

Do not claim the narrative tool fallback was proven. Do not move demo `PUT`s onto Clinical Read. Do not remove Java's HAPI destination.

## 8. Implementation plan

No step below is authorized by this document.

1. Change `clinical_review_context.py` to import `ExactResourceNotFound` from `langgraph_fhir_client`. Update the tests that import it from the HAPI module. Behavior of the exception stays the same.
2. Re-home or replace tests that construct `HapiReadClient` for protocol behavior so they drive `ClinicalReadClient` with an `httpx` handler, or an in-memory client. Keep pagination and retry tests only where they still describe a client that exists.
3. Split the demo gateway's read of Encounter, Observation, and Appointment from `app.langgraph_fhir_hapi`. The `PUT` and the two Patient `GET`s can stay as direct loopback FHIR calls in the script. They must not be imported by `app/main.py`.
4. Decide whether opt-in `RUN_HAPI_INTEGRATION_TESTS` remain as a script-level check or move behind Java's `local-hapi` tests. They must not be required for the default pytest run.
5. Remove `langgraph_fhir_hapi.py` from `app/` and from `LESSON_MODULES` only when no `app/` or script import remains. Drop `FHIR_BASE_URL` from `.env.example` and from the follow-up section of `services/ai-service/README.md`.
6. Leave Java `application.yml`, Clinical Read, Model Boundary, and the load-synthetic-patients script in place.
7. Do not edit ADR-085, ADR-095, or `clinical-read-v1.md` as part of the deletion. A later documentation pass can record that step 6 closed.

The search-shaped `get` fallback does not have to grow a new Clinical Read feature if the narrative tools keep using the protocol ledger. A closure test should show that a complete protocol run does not call `get` with a query, and that a query `get` is still rejected. Adding Bundle search to `ClinicalReadClient.get` would be a new contract and is not part of this plan.

## 9. Regression tests

Use tests that already exist. Do not add a dependency.

| Guarantee | Existing test or evidence | Gap |
|---|---|---|
| Follow-up Agent missed path | `test_clinical_read_client.py` factory source check; `test_missed_follow_up_service.py`; E2E AGT-01 through AGT-05 | Narrative `POST /internal/agent/follow-up` was not executed live. |
| Clinical review context | `test_clinical_review_java_context.py`; E2E AGT-04 | Re-run after the exception import moves. |
| Model Boundary unchanged | `GET /internal/agent-context` still uses `consumer.py` and `MODEL_BOUNDARY_PATH`. No Clinical Read edit is required for that route. | Confirm the closure diff does not touch `consumer.py` or the Model Boundary Java controller. |
| Mini HIS | Unchanged Java normalizer. Python has no Mini HIS URL in `ClinicalReadClient`. | No new Mini HIS test is required for a Python import move. |
| Java can still read HAPI | Java Clinical Read source `local-hapi` and its tests. | Do not delete `application.yml` `base-url`. |
| Operational Python does not call HAPI | Factory source assertions in `test_clinical_read_client.py`. After deletion, `rg` over `app/` for `HapiReadClient`, `FHIR_BASE_URL`, and `langgraph_fhir_hapi` should be empty. | The E2E log is historical evidence for one run, not a standing test. |

Default pytest for this closure is the clinical-read, missed-follow-up, clinical-context, and architecture modules already in the tree. Opt-in live HAPI and live Gemini tests stay opt-in. A full suite is not required to decide this assessment.

## 10. Acceptance criteria

- `app/` does not import `HapiReadClient`, `hapi_base_url`, or `FHIR_BASE_URL`.
- `clinical_review_context.py` imports `ExactResourceNotFound` from `langgraph_fhir_client.py`.
- The three factories still construct `ClinicalReadClient` and no other FHIR HTTP client.
- `prepare_demo_cases.py` no longer imports `app.langgraph_fhir_hapi`. Its FHIR writes stay in that script.
- `POST /internal/agent/missed-follow-up` and clinical context still pass their current Clinical Read tests.
- `GET /internal/agent-context` still targets Model Boundary v1.
- Java `local-hapi` configuration remains.
- README and `.env.example` no longer tell the operator to set `FHIR_BASE_URL` for the follow-up agent.
- This closure does not by itself certify production, does not execute AGT-06, and does not implement the bidirectional exchange in ADR-095.

Section 10 is the assessment target list. Section 16 records which items this closure met.

## 11. Completed scope

### Increment A

`4f0a036899ee81f8f351b7f7641b569868b9782b`, `refactor(ai): decouple clinical context exception import from HAPI`.

`clinical_review_context.py` imports `ExactResourceNotFound` from `app.langgraph_fhir_client`. The class definition and the HAPI re-export stayed in place.

### Increment B

`a22068addd1839f1c298a0888e8fcebbc854a655`, `fix(ai): align narrative tools with clinical read search`.

`patient_id_for_case`, `get_observations`, and `get_patient_appointments` call `transport.search` through `_complete_search`. `get_observations` uses `protocol_observation_search_path`, which includes `status=final`. `_complete_search` returns resources only when the collection status is `COMPLETE`. `INCOMPLETE_LIMIT` raises `ReadClientError` and does not return the partial resources. `get_patient` stays `transport.get("Patient/{id}")`.

The same commit series includes `cd8d68e4f21a079d4b827966f20d78e731c74b68`, `test(ai): stabilize follow-up coordination tests`. That change is test-only. It stops the coordination suite from depending on the last HMAC hex digit and on UUID order when two events share a timestamp. It does not change Clinical Read.

### Increment C2

`66a9eafc6742185648a541214c37db0861492617`, `test(ai): enforce clinical read runtime boundary`.

`tests/test_architecture.py` parses every `app/*.py` except `langgraph_fhir_hapi.py`. It rejects an import of `langgraph_fhir_hapi`, a reference to `HapiReadClient` or `FHIR_BASE_URL`, and a configuration read of that variable. Comments, docstrings, and plain strings are not references. The same test requires `ClinicalReadClient.from_settings` in `build_live_followup_workflow`, `_live_adapter`, and `_fhir_client`.

### Increment C3

`6ecc464768bd6935905830816c0ab7ae89c3469f`, `refactor(ai): import ExactResourceNotFound from source module`.

Consumers that only needed the exception now import it from `langgraph_fhir_client`. `prepare_demo_cases.py` still imports `ACCEPT` and `HapiReadClient` from `langgraph_fhir_hapi` and still constructs that client when no reader is injected. `_EXACT_RESOURCE_TYPES` stays in the HAPI module.

### Increment C4

`5514ddb0bbd535fa9126d868773acfe8ea5e4429`, `docs(ai): clarify clinical read and laboratory HAPI configuration`.

`services/ai-service/README.md` and `.env.example` describe `MODEL_BOUNDARY_BASE_URL` and `MODEL_BOUNDARY_SERVICE_TOKEN` as the operational Java path, and `FHIR_BASE_URL` as the laboratory direct reader. Names and values of the example assignments were not changed. The README also records that `test_local_server_missing_patient_is_not_a_clinical_result` calls HAPI in the default suite and is not behind `RUN_HAPI_INTEGRATION_TESTS`.

## 12. Architectural decision

The approved isolation decision is alternative B in [python-hapi-legacy-isolation-v1](python-hapi-legacy-isolation-v1.md).

`HapiReadClient` remains in `app/langgraph_fhir_hapi.py`. The three operational factories do not construct it. They construct `ClinicalReadClient.from_settings`. The boundary is a test over source, not a separate package. A future `app/` module that imports the legacy client fails `test_operational_python_reaches_java_through_clinical_read`. Laboratory scripts and HAPI tests may still import the module. That test does not scan `scripts/`.

This is not alternative A of the isolation design, which would move the file out of `app/`. It is not alternative C of that design, which would replace the client and delete the module. It is also not alternative C of section 7 of this assessment. The file was not deleted.

Java `clinical-read.source` remains `local-hapi` in `application.yml`. The other implemented value is `mini-his`. Python does not choose that source.

## 13. Technical evidence

| Evidence | What it shows | What it does not show |
|---|---|---|
| `tests/test_architecture.py` | Operational `app/` modules do not name the legacy client, and the three factories call `ClinicalReadClient.from_settings`. Synthetic samples in that file show the scan rejects an import and a `FHIR_BASE_URL` read. | It does not execute HTTP. It does not scan scripts or tests. |
| `tests/test_clinical_read_client.py` | Clinical Read paths, factory source, and the narrative fallback against a mocked envelope: `status=final` on observations, empty complete collections, and `INCOMPLETE_LIMIT` as `ReadClientError`. | It does not call a live Java process. |
| Narrative workflow tests with `ScriptedModel` | The tool graph and the ledger cache without Gemini. | They do not prove a live narrative call. |
| Coordination tests in `tests/test_followup_coordination_workflow.py` | After `cd8d68e`, the default suite no longer depends on the last HMAC hex digit or on UUID sort order for the two fixed-clock events. The revalidation suite included them. | They do not read FHIR and they do not prove the HAPI boundary. |
| Full `services/ai-service` suite after C3, with HAPI answering `GET http://localhost:8080/fhir/metadata` | 974 passed, 13 skipped, 0 failed, 1 Starlette `anyio` warning. The 13 skips are opt-in live tests. | It does not certify production. |
| [E2E results](../results/e2e-interoperability-validation-v1-results.md) | HTTP-01 through HTTP-06 and AGT-01 through AGT-05 on synthetic data. Captured Python `httpx` calls for those scenarios went to Java Clinical Read. Captured Java calls went to Mini HIS. The Python log for that run had no port 8080. | AGT-06 was not run. The narrative route and Gemini were not called. HAPI was not the Clinical Read source under test. The log does not prove that no other entry point can construct `HapiReadClient`. |

## 14. Commit history

Verified with `git log` at HEAD `5514ddb0bbd535fa9126d868773acfe8ea5e4429`:

| Hash | Subject | Increment |
|---|---|---|
| `4f0a036899ee81f8f351b7f7641b569868b9782b` | `refactor(ai): decouple clinical context exception import from HAPI` | A |
| `cd8d68e4f21a079d4b827966f20d78e731c74b68` | `test(ai): stabilize follow-up coordination tests` | B, test stability |
| `a22068addd1839f1c298a0888e8fcebbc854a655` | `fix(ai): align narrative tools with clinical read search` | B |
| `66a9eafc6742185648a541214c37db0861492617` | `test(ai): enforce clinical read runtime boundary` | C2 |
| `6ecc464768bd6935905830816c0ab7ae89c3469f` | `refactor(ai): import ExactResourceNotFound from source module` | C3 |
| `5514ddb0bbd535fa9126d868773acfe8ea5e4429` | `docs(ai): clarify clinical read and laboratory HAPI configuration` | C4 |

## 15. Limitations and remaining work

- Live narrative Gemini was not validated end to end. AGT-06 stayed blocked. The narrative fallback was tested with a mocked Clinical Read envelope and with scripted models.
- The usual regression leaves opt-in integrations skipped: `RUN_HAPI_INTEGRATION_TESTS`, `RUN_LIVE_GEMINI_TESTS`, live embeddings, and live AI assistance.
- The default suite still requires a local HAPI for `test_local_server_missing_patient_is_not_a_clinical_result`. That test is not opt-in. Readiness is `GET http://localhost:8080/fhir/metadata`. A refused connection fails the test with `transport failed`.
- `HapiReadClient` was not deleted and was not moved out of `app/`.
- Java still has `local-hapi` as an available Clinical Read backend. The platform is not independent of HAPI.
- This branch was not pushed and was not merged. At this revision it is 34 commits ahead of `origin/feature/follow-up-agent`.

## 16. Closure criteria

### Local technical closure

Met for operational Python V1 when all of the following hold, and they hold at this HEAD:

- `clinical_review_context.py` imports `ExactResourceNotFound` from `langgraph_fhir_client.py`.
- The three factories construct `ClinicalReadClient.from_settings`.
- Narrative fallbacks call `transport.search`, request `status=final` for observations, and raise on an incomplete collection.
- `tests/test_architecture.py` fails if another operational module names the legacy client.
- Laboratory `prepare_demo_cases.py` still writes FHIR with `httpx` and still reads Encounter, Observation, and Appointment through `HapiReadClient`.
- README and `.env.example` describe `FHIR_BASE_URL` as the laboratory direct reader.

Not met, and not required for this local closure: deleting `langgraph_fhir_hapi.py`, removing the demo import of that module, or removing Java `local-hapi`.

### E2E validation already recorded

The laboratory run in the E2E results covers Mini HIS to Java Clinical Read to Python for the missed-follow-up scenarios AGT-01 through AGT-05 and the HTTP checks. It does not cover the narrative route.

### Remote publication

Pending. No push and no merge are part of this document.

### Later work

Out of scope here: moving or deleting `HapiReadClient`, gating the remaining default-suite HAPI call, changing Java's default source, executing AGT-06, and any production certification.
