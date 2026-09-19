# ADR-076 — Controlled Gemini integration

Status: Accepted for laboratory Task 076  
Date: 2026-09-19

This is the first ADR in `docs/adr/`. It records an experimental laboratory decision. It does not claim regulatory compliance.

## Decision

Add a fail-closed Gemini call only in Python `ai-service`, on a new internal endpoint, using one exact synthetic fixture. Do not send `ModelBoundaryContract` v1, live Epic/Oracle/HAPI data, or FHIR Bundles to Gemini.

## Objective

Prove that Product B can invoke one external model under an explicit feature gate, service authentication, closed schemas, and mandatory human review — without changing the Java FHIR boundary.

## Scope

- Provider: Google Gemini only
- Model: Task 076 specified `gemini-2.5-flash` (configurable). Task 077 sets the repository default to `gemini-flash-latest` after the 2026-09-19 live demo (`gemini-2.5-flash` and `gemini-2.0-flash` returned Google 404; `gemini-flash-latest` returned 503 then 200). `GEMINI_MODEL` remains an override. There is no model fallback.
- SDK: `google-genai==2.24.0`
- Surface: `POST /internal/experimental-summary`
- Input: exact fixture `SYN-076-001`
- Feature flag: `LLM_EXPERIMENTAL_ENABLED=false` by default
- Service auth: `X-Service-Token` / `MODEL_BOUNDARY_SERVICE_TOKEN`, fail-closed when blank
- HTTP JSON: camelCase (`modelCalled`, `requiresHumanReview`, `promptVersion`)
- Timeout: 30 seconds
- Summary maximum: 2000 characters; oversized output is rejected, not truncated
- Live tests: `RUN_LIVE_GEMINI_TESTS=false` by default

## Why two paths stay separate

Java remains the only FHIR/SMART client. `/internal/agent-context` continues to consume v1 and always returns `modelCalled=false`. The experimental endpoint does not read v1 and does not call Java.

```text
v1 path: EHR → Java → ModelBoundary v1 → /internal/agent-context
076 path: fixture SYN-076-001 → /internal/experimental-summary → Gemini
```

## Human review and modelCalled

`requiresHumanReview` is always `true` and is set by the application. There is no switch to disable it. Gemini cannot set this field.

`modelCalled` is `true` only after the provider invocation starts. A disabled flag, invalid fixture, missing API key, or 401 does not set it to `true`.

Java `AiBoundaryDecision` flags are unchanged (`modelCalled=false`, `modelCallAuthorized=false`).

## Logging

Audit lines may include `correlationId`, `useCase`, `promptVersion`, `provider`, `model`, `durationMs`, `status`, and `modelCalled`. They must not include the API key, service token, prompt, completion, fixture body, or FHIR.

## Test strategy

Default `pytest` uses `FakeLLMProvider`. It must pass without `GEMINI_API_KEY`. `test_architecture.py` allows only `google-genai` and still forbids OpenAI, LangChain/LangGraph, `google-generativeai`, and FHIR clients.

## Explicit non-goals

OpenAI, second providers, RAG, MCP, LangGraph, memory, clinical recommendations, diagnosis, treatment or medication advice, production PHI, Java Gemini code, v1 field changes, and changes to `/internal/agent-context`.

## Risks left open

The laboratory still has no product users, no operational human-review workflow, and no authorization to use real clinical data. Completing this ADR is not approval for clinical use or for sending live EHR context to a model.
