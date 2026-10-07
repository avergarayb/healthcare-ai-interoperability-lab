# ADR-091 — AI-assisted review

## Status

Accepted

## Date

2026-10-07

## Context

An open follow-up review case already has authoritative FHIR facts, a deterministic reason, and a human close action. Institutional retrieval can return synthetic operational guidance. A reviewer may want a short explanation of that guidance without giving the model authority over the case.

## Decision

`AI_ASSISTED_REVIEW_V1` is one horizontal, on-demand explanation for `POST_CONSULTATION_RESULT_REVIEW_V1` and `MISSED_FOLLOW_UP_REVIEW_V1`. It is not a separate assistant per protocol, not an agent, and not production-ready.

The browser calls `POST /review-cases/{reviewCaseId}/ai-assistance`. The page calls the assistance service in process. There is no internal service-token assistance route and no HTTP call to `/internal/knowledge/retrieve`.

Generation runs only when the reviewer submits `Generate AI assistance`. Queue reads, case reads, review-case creation, protocol evaluation and FHIR acquisition do not generate it. Assistance is available only for an open case. A closed case has no button, and the POST stops before FHIR, retrieval and Gemini.

The model input is a bounded projection. It may include protocol id, supported reason codes, the shared server-owned reason explanations, encounter availability and status, observation availability, status, code and display, missed-follow-up trigger appointment availability and status, appointment classification labels, appointment count, `confirmedFutureFollowUpPresent`, and context availability. It does not include observation values, `code.text`, resource ids, references, timestamps, patient identity, `caseId`, `reviewCaseId`, matched resources or `evaluationStatus`. The human page may still show the existing bounded observation value.

The retrieval query is chosen by the server: `post consultation result follow-up` or `missed follow-up appointment`. `topK` stays at most 3 and the configured threshold stays 0.68. `NO_RELEVANT_GUIDANCE` and `UNAVAILABLE` do not call Gemini. Retrieved chunk text is data. The model receives `chunkId`, section, text and `contentRole=institutional_document_data`. It does not receive the retrieval score.

Gemini is called once through the existing `GEMINI_API_KEY` and `GEMINI_MODEL`, using `application/json`, `response_json_schema` and at most 1024 output tokens. Structured generation sets the lowest thinking mode the configured family accepts: `thinking_level=low` for the Gemini 3.8 Flash model behind `gemini-flash-latest`, and `thinking_budget=0` for an explicit Gemini 2.5 Flash model. A `MAX_TOKENS` finish is discarded as incomplete output. There is no tool, no LangGraph loop, no retry and no fallback to `generate_summary`. Summary and each review point must cite retrieved chunk ids. The server discards the whole output when validation fails, then projects title, version, section and source text from the retrieval result. Citation membership does not prove that every sentence is entailed by the source.

The server owns assistance status, `assistanceType=explanatory`, `humanReviewRequired=true` and the disclaimer. Nothing from the generation is stored. A later GET shows `Not generated`. The close form, outcome choices, version check and history stay independent.

The POST reuses same-origin validation and `HUMAN_REVIEW_FORM_SIGNING_SECRET`, with a distinct `ai-assistance` HMAC purpose. A close token and an assistance token do not validate as each other. A blank signing secret still allows GET and omits the generate button. The service token and Gemini key are not sent to the browser.

## Consequences

Review-case state, protocol evaluation and FHIR writes do not change when assistance succeeds or fails. A valid model string can still contain undesirable clinical wording; the schema rejects extra clinical fields but there is no keyword safety filter. Human review remains required. This is a synthetic demo boundary, not a clinical safety certification, HIPAA or GDPR claim, diagnostic capability, or production deployment.
