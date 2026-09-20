# ADR-078 — FHIR and AI Boundary

## Status

Proposed

## Date

2026-09-20

## Context

The platform has a working FHIR client path and a working Gemini path. The main architectural risk is treating those as one pipeline. Phase B (G0–G4) and ADR-076 already separate them. This ADR states the boundary as a standing product rule, not a temporary gap.

## Current State

```text
EHR / FHIR sandbox (Epic, Oracle, local HAPI)
        ↓
Java FhirService (HAPI R4 client)
        ↓
Snapshot → ClinicalProjectionMapper (Task 042) → RetentionCeiling N=5
        ↓
ModelBoundaryContract v1
        ↓
GET /api/model-boundary/v1
        ↓
GET /internal/agent-context   (modelCalled=false)
        X
        ↓
Gemini
```

```text
SYN-076-001
        ↓
POST /internal/experimental-summary
        ↓
LLMProvider → GeminiProvider → Google Gemini API
```

Evidence: `ClinicalProjectionMapper`, `RetentionCeiling`, `ModelBoundaryMapper`, `app/consumer.py` (evaluates v1; does not call a model), `app/experimental_service.py` (does not call Java/FHIR), `app/llm_provider.py` `build_experimental_prompt` (fixture fields only), `tests/test_architecture.py` (no FHIR/OpenAI/LangGraph clients in the Python app). Java `AiBoundaryDecision` rejects `modelCalled=true` and `modelCallAuthorized=true`.

## Decision

1. **Java is the FHIR interoperability boundary.** Only the Interoperability Surface initiates Epic, Oracle, or HAPI FHIR traffic.
2. **Python is not a FHIR/EHR client** and must not add Epic, Oracle, or HAPI clients.
3. **`ModelBoundaryContract` v1 is not model input.** Task 074 may *consume* v1 and must keep `modelCalled=false`.
4. **Gemini does not receive FHIR Bundles, v1 records, or live EHR payloads.** Task 076 accepts only exact fixture `SYN-076-001`.
5. **074 and 076 are different paths.** Sharing a process or a service token does not merge them.
6. **G0 (synthetic AI) does not authorize G2/G3.** Crossing to real clinical data or clinical-context AI requires a **new explicit contract** and a product/governance review (Phase B §21). This ADR does **not** design that contract or any new allowlist fields.

Allowlist 042 and RetentionCeiling N=5 remain the **current governance baseline** for projection. They are not a permanent ban on all future projection change; expansion for AI is not licensed by this ADR.

## Rationale

C1 verified there is no FHIR → Gemini hop in code. C2 treated that hop as a stable boundary: a working FHIR client plus a working Gemini call is not a product capability to join them. ADR-076 already forbade sending v1 or Bundles to Gemini.

## Alternatives Considered

- **Treat 076 as the natural sink for v1.** Would collapse G0 into G3 without a contract.
- **Move FHIR calls into Python “for the AI service”.** Would make the AI surface an EHR client.
- **Send Bundles to Gemini “because they are already in Java memory”.** Violates minimization and ADR-076.
- **Keep the split only in documentation.** Insufficient; C1 showed the split is implemented and test-enforced.

## Consequences

Positive: evolution (packaging, secrets, auth on 074) can proceed without moving the X.

Negative / trade-off: “full demo” (EHR context summarized by Gemini) is not available on this boundary; a later G3 is a new decision, not a flag flip.

## Boundaries

Out of scope: designing a future clinical-to-model contract; choosing fields; expanding Task 042; MedicationRequest on Epic; second provider; fallback/router; RAG; CDS; claiming legal compliance or SIHCE/RENHICE status.

## Related Decisions

- ADR-076 — synthetic-only Gemini, two paths.
- ADR-077 — one product, two surfaces, three logical boundaries.
- ADR-080 — how 074/076 are exposed as HTTP.
- `docs/fhir/model-boundary-contract-v1.md`
- `docs/ai-governance/product-governance-boundary.md` (G0–G4, U0–U4)
- `docs/ai-governance/llm-boundary-threats-and-controls.md`

## Future Reconsideration

Revisit only if a written product decision authorizes a **new** AI input contract (not silent reuse of 076) after the assessments listed in Phase B. Until then, connecting v1 or FHIR to Gemini is out of scope.
