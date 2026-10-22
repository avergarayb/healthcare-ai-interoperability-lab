# AI_ASSISTED_REVIEW_V1

## Status

Accepted synthetic-demo contract. Not production-ready. Not a clinical safety certification.

## Authority

| Source | Owns |
|---|---|
| FHIR / Clinical Review Context | Current facts |
| Deterministic protocol | Why the review case exists |
| Institutional knowledge | Operational guidance text |
| Gemini | One explanatory synthesis |
| Human reviewer | Review outcome |

Gemini does not create a case, close a case, select an outcome, change `evaluationStatus`, `reasonCodes` or `matchedResources`, write FHIR, or execute an external action.

## When it runs

`POST /review-cases/{reviewCaseId}/ai-assistance` after `Generate AI assistance`.

It does not run on queue GET, detail GET, review-case creation, protocol evaluation or FHIR acquisition. Only an open case can generate. A closed POST is rejected before FHIR, retrieval and Gemini.

## Model facts

The server projection may include protocol id, supported reason codes and the single shared reason-explanation source, encounter availability and status, observation availability, status, code and display, trigger-appointment availability and status, bounded appointment classifications, count, `confirmedFutureFollowUpPresent`, and context availability.

The model does not receive observation values, `code.text`, FHIR ids or references, timestamps, patient name, MRN, date of birth, demographics, `caseId`, `reviewCaseId`, matched resources, raw FHIR or `evaluationStatus`. The human page may continue to show the existing bounded observation value.

An unsupported reason fails closed as `unavailable` / `invalid_case_context` before the model sees it.

## Retrieval

The server builds `queryText`:

- `POST_CONSULTATION_RESULT_REVIEW_V1` → `post consultation result follow-up`
- `MISSED_FOLLOW_UP_REVIEW_V1` → `missed follow-up appointment`

The browser and the model cannot supply that query. Retrieval is in process, with `topK` of at most 3 and the current `INSTITUTIONAL_KNOWLEDGE_MIN_SCORE` of 0.68. That threshold is unchanged by this contract.

`FOUND` continues to one Gemini call. `NO_RELEVANT_GUIDANCE` returns `unavailable` / `no_relevant_guidance` and does not call Gemini. `UNAVAILABLE` returns `unavailable` / `retrieval_unavailable` and does not call Gemini. Neither changes the review case, clinical context or close workflow.

Gemini receives `chunkId`, section, text and `contentRole=institutional_document_data` for each retrieved chunk. Institutional text is data. The retrieval score stays on the server.

## Output

The model returns only:

- `summary.text` of 1..600 characters and 1..3 unique `citedChunkIds`
- 1..4 `reviewPoints`, each with text of 1..240 characters and 1..3 unique `citedChunkIds`
- 0..3 limitations, each 1..240 characters

Extra fields are rejected. Every summary and review point must cite chunk ids from that request's retrieval result. Unknown, duplicate, malformed or non-retrieved citations discard the entire output as `invalid_output`. The server then adds title, version and section from the trusted retrieval result.

`status`, `assistanceType=explanatory`, `humanReviewRequired=true` and the disclaimer are server-owned. Coarse unavailable reasons are `context_unavailable`, `retrieval_unavailable`, `no_relevant_guidance`, `provider_unavailable`, `invalid_output`, `case_not_open`, `not_configured` and `invalid_case_context`.

A citation proves the model named a retrieved chunk. It does not prove that every generated sentence is entailed by that chunk. There is no second model, entailment judge or keyword clinical filter. Valid free text can still contain undesirable clinical wording.

## Persistence and browser

Prompt, model input, model output, summary, review points, citations and limitations are not stored in the review database. No review-case migration is added.

A completed generation POST returns `303 See Other` to `GET /review-cases/{reviewCaseId}`. The assistance for that one response is held only in the process, under a random ticket. An `HttpOnly` `SameSite=Strict` cookie, scoped to that case path, carries the ticket and not the text. The following GET renders the assistance once and deletes the ticket. Browser refresh repeats that GET: it does not call Gemini and shows `Not generated`. A queue navigation is the same clean GET. The ticket expires after 60 seconds, is bound to one review case, is not written to SQLite, and is gone after a process restart. This handoff is not durable AI storage.

The fixed disclaimer is: "Generated assistance based on available case facts and institutional guidance. Human review remains required."

The page shows summary, operational review points, institutional source metadata and text, and limitations when present. It does not show the retrieval score, embeddings, prompt or raw model response. Generated prose and the institutional source are separate. Model text is HTML-escaped and is not rendered as Markdown.

The POST uses same-origin validation and an HMAC bound to purpose `ai-assistance`, `reviewCaseId` and expiry. A close token is not an assistance token. A blank `HUMAN_REVIEW_FORM_SIGNING_SECRET` leaves GET working, hides the generate button, and rejects the POST before FHIR, retrieval and Gemini. `MODEL_BOUNDARY_SERVICE_TOKEN` and `GEMINI_API_KEY` are not sent to the browser.

The close form, expected version, outcome options, idempotency, concurrency and history are unchanged. Assistance does not preselect or submit an outcome.

## Provider

Generation uses the existing `GEMINI_API_KEY` and `GEMINI_MODEL` through `google-genai` structured JSON, with a 1024 output-token bound and no automatic retry. `gemini-flash-latest` currently resolves to Gemini 3.8 Flash. That model rejects `thinking_level=minimal`; structured generation sets `thinking_level=low`, the lowest level it accepts. An explicit Gemini 2.5 Flash model sets `thinking_budget=0`. The two thinking fields are never sent together. 1024 stays sufficient for the small JSON contract once thinking no longer consumes the output budget. A `MAX_TOKENS` finish reason is incomplete output: the partial text is discarded and the result is `invalid_output`, with no retry. Timeout or provider failure is `provider_unavailable`. Invalid JSON or schema mismatch is `invalid_output`. There is no fallback model, legacy summary or general-knowledge answer. LangGraph is not used.
