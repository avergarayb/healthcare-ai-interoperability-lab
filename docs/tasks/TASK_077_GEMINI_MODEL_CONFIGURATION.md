# Task 077 — Gemini model configuration and lifecycle alignment

**Status:** READY FOR IMPLEMENTATION  
**Branch:** `feature/077-gemini-model-configuration`  
**Depends on:** Task 076 (merged or this branch stacked after 076)  
**Scope:** Python `ai-service` defaults + documentation only

This task does **not** add AI capability. It closes the gap between the Task 076 specified model and the model that actually succeeded in the 2026-09-19 live demo.

---

## 1. Fact to correct

Task 076 specified:

```text
GEMINI_MODEL=gemini-2.5-flash
```

The current **code default** is still `gemini-2.5-flash` (`Settings.gemini_model`, `DEFAULT_MODEL`, `.env.example`, README, ADR-076, progress-log, TASK_076 examples).

The live demo of 19 September 2026 showed:

| Model | Google HTTP | Result |
|---|---|---|
| `gemini-2.5-flash` | 404 | retired / not served |
| `gemini-2.0-flash` | 404 | retired (shutdown 1 June 2026) |
| `gemini-flash-latest` | 503 then 200 | `COMPLETED`, `modelCalled=true` |

`gemini-flash-latest` was set in the operator `.env`, **not** as the repository default. ChatGPT’s clause “if that is already the code default” is **false**. Task 077 must change the default.

Do not rewrite Task 076 history. 076 specified `gemini-2.5-flash`. 077 records the live outcome and aligns the default.

---

## 2. In scope

- Document that `GEMINI_MODEL` is an environment override.
- Change the repository default to `gemini-flash-latest`.
- Update 076-facing docs so they do not present `gemini-2.5-flash` as the **effective** default.
- Record the 404s and the successful `gemini-flash-latest` call (date 2026-09-19).
- Keep logging `provider=GEMINI` and the **configured** `model=` value (no hard-coded stale id in audit examples).
- Tests: default / unset `GEMINI_MODEL` must resolve to `gemini-flash-latest`. Tests that inject an explicit model may keep echoing that model.

## 3. Out of scope

- OpenAI or a second provider
- Automatic fallback between Gemini model ids
- Dynamic model selection / router
- Retry or resilience architecture for the transient Google 503
- RAG, MCP, LangGraph, memory
- Java, FHIR, v1, SMART, 075 token, `/internal/agent-context`
- Input/output contract changes
- Clinical use, new patient data
- `docs/ai-governance/` (after 077, not in 077)
- Task 078

A single Google 503 is not a reason to add retries.

---

## 4. Required code touchpoints

Change the default string `gemini-2.5-flash` → `gemini-flash-latest` in:

```text
services/ai-service/app/config.py
services/ai-service/app/experimental_models.py   (DEFAULT_MODEL)
services/ai-service/.env.example
```

`from_env()` must keep:

```text
os.getenv("GEMINI_MODEL", "gemini-flash-latest")
```

Empty `GEMINI_MODEL` after strip still falls back to `gemini-flash-latest`.

Do **not** add a list of models or a fallback chain. If Google later 404s `gemini-flash-latest`, the operator sets `GEMINI_MODEL` to another id. The application does not try a second id.

## 5. Tests

- A settings/default test: no `GEMINI_MODEL` → `gemini_model == "gemini-flash-latest"`.
- Existing experimental tests that set `gemini_model="gemini-2.5-flash"` may stay: they prove the **configured** id is echoed, not that 2.5 is the default.
- Tests that expect the default response `model` field when using `_settings()` without override must expect `gemini-flash-latest` if `_settings()` is updated to the new default.
- `test_architecture.py` stays as in 076 (only `google-genai` allowed).
- Do not add a live Gemini test. Do not require `GEMINI_API_KEY`.

## 6. Documentation

Update, do not invent new folders:

```text
docs/tasks/TASK_077_GEMINI_MODEL_CONFIGURATION.md   (this file)
docs/adr/ADR-076-controlled-gemini-integration.md   (note: default aligned in 077)
docs/progress/progress-log.md                       (Task 077 + 076 live model note)
services/ai-service/README.md
services/ai-service/.env.example
```

Optional one-line note at the top of `docs/tasks/TASK_076_CONTROLLED_LLM_INTEGRATION.md`:

```text
Task 076 specified gemini-2.5-flash. After the 2026-09-19 live demo, Task 077
sets the repository default to gemini-flash-latest. GEMINI_MODEL remains overridable.
```

Do not bulk-replace every 076 example JSON if that would falsify the original spec. Historical 076 examples may keep `gemini-2.5-flash` **as the 076-specified id**, with the 077 note above.

ADR-076 / progress-log / README / `.env.example` must state the **current** default is `gemini-flash-latest`.

Record explicitly (no Patient ids, tokens, or API keys):

```text
2026-09-19 live (synthetic fixture SYN-076-001, no Java):
- gemini-2.5-flash → Google 404
- gemini-2.0-flash → Google 404
- gemini-flash-latest → Google 503 then 200 COMPLETED
- modelCalled=true, requiresHumanReview=true
```

Do not claim regulatory compliance.

## 7. Acceptance

- [ ] Code default is `gemini-flash-latest`.
- [ ] `GEMINI_MODEL` still overrides the default.
- [ ] No model fallback or router.
- [ ] Java / v1 / 074 / 075 unchanged.
- [ ] Experimental request/response schemas unchanged.
- [ ] Docs no longer present `gemini-2.5-flash` as the current default.
- [ ] 076 historical specification of `gemini-2.5-flash` remains visible as history.
- [ ] Live 404/200 notes are in progress-log or ADR.
- [ ] `pytest` passes without a Gemini key.
- [ ] No `mvn` source changes; `mvn test` not required unless Java is touched by mistake.

## 8. Implementation rule

Inspect the files in section 4 before editing. Change only the default and the docs listed. Do not refactor the provider. Do not print `GEMINI_API_KEY`.
