# ADR-077 — Product Architectural Unit

## Status

Proposed

## Date

2026-09-20

## Context

Phase C2 asked how the existing codebase should be understood as a product: one commercial identity versus two products, and where HAPI/Compose and the Java 057–073 packages sit. `docs/PROJECT.md` still lists a broad strategy (RAG, Kubernetes, Spring Security). Phase A/B name a single **Healthcare AI & Interoperability Platform**. ADR-076 historically said “Product B” for Python. Those framings must not be silently merged.

Numbering note: **Task 077** (Gemini default `gemini-flash-latest`) is a completed implementation task, not this ADR. This file is the next *ADR* after ADR-076.

## Current State

Verified in the repository (Phase C1):

- One Java application: `fhir-integration-service` (Java 21, Spring Boot 3.5.16, port 8081).
- One Python application: `ai-service` (FastAPI, port 8090).
- Java owns FHIR/SMART/Epic/Oracle/local HAPI client usage (`FhirService`, vendor packages).
- Python owns `GET /internal/agent-context` (Task 074) and `POST /internal/experimental-summary` (Task 076).
- Compose (`infra/docker/docker-compose.yml`) runs HAPI, Postgres for HAPI, `lab-oauth`, nginx — not Java or Python.
- Packages `agent`, `agentstub`, `aiboundary`, `firstai`, `aigateway`, `aiconsumer*` implement Tasks 057–073 in the same Java process, with `/lab/*` HTML and `/api/*/v1` JSON. They do not call Gemini.

## Decision

The **product identity** is a single **Healthcare AI & Interoperability Platform**.

The **architectural unit** is three *logical* boundaries realized on two *technical* surfaces, plus two *non-product-runtime* surfaces:

| Kind | What |
|---|---|
| Logical boundary | FHIR integration (Java client, SMART, destinations) |
| Logical boundary | Clinical data / Model Boundary v1 (allowlist 042, RetentionCeiling N=5, `ModelBoundaryContract`) |
| Logical boundary | Controlled AI (Python experimental Gemini path) |
| Technical surface | Interoperability Surface — Java |
| Technical surface | AI Surface — Python |
| Experimental / simulation | In-process Java gates 057–073 and `/lab/*` (see ADR-079) |
| Temporary / support | Local HAPI FHIR, HAPI Postgres, lab-oauth, nginx (see ADR-081) |

Java and Python remain **one product** because they share a versioned contract (`GET /api/model-boundary/v1`), a laboratory service secret (`X-Service-Token` / `MODEL_BOUNDARY_SERVICE_TOKEN`), and a single governance baseline (Phase B gates G0–G4). They are **not** two commercial products.

They remain **two processes** so that the AI surface cannot become an EHR client and so that Gemini stays off the FHIR path (ADR-078).

This ADR does not choose pricing, packaging SKUs, or marketing slogans. “Interop-first” versus “AI platform” as *sales* language stays outside engineering.

## Rationale

Consistent with code: two deployable applications, one v1 hop, one experimental model hop, a large Java simulation ladder, and a Compose stack that is not the product EHR (C1/C2). Closest C2 options: **C** (three logical boundaries) for the core unit, **B** (AI as optional capability — 076 is gated and unused by 074), and **D** (simulations called out so they are not a third commercial product). Option **A** is only a naming overlay, not a different topology.

## Alternatives Considered

- **A — Healthcare Platform = Interoperability + AI.** Describes identity, not the v1 boundary or 057–073.
- **B — Interoperability Platform + AI capability.** Matches optional 076; understates the explicit Model Boundary as a first-class logical boundary.
- **C — FHIR + Clinical Data Boundary + Controlled AI.** Matches the code path EHR → projection → v1 → (074 \| 076). Does not by itself name simulations or HAPI.
- **D — Interop + in-process simulations + optional experimental AI.** Matches C1’s third mass (057–073) and Compose support. Alone it sounds like three products.

This ADR records the combination above rather than treating A–D as a scored contest.

## Consequences

Positive: one vocabulary for Phase B (U0–U4, G0–G4) and future ADRs; HAPI and `/lab/*` are not sold as SIHCE or IAM.

Negative / trade-off: three logical boundaries on two processes requires discipline in docs; ADR-076’s “Product B” wording remains historical and is not rewritten here.

## Boundaries

Out of scope: SaaS vs customer-hosted vs hybrid; Kubernetes; tenancy; IAM; RAG/agents/MCP; FHIR → Gemini; changing v1 fields; deleting 057–073; legal compliance claims.

## Related Decisions

- ADR-076 — Controlled Gemini integration (experimental path; do not modify).
- ADR-078 — FHIR and AI Boundary.
- ADR-079 — Role of 057–073.
- ADR-080 — Internal AI Service Boundary.
- ADR-081 — Runtime Packaging Boundary.
- `docs/ai-governance/product-governance-boundary.md`
- `docs/ai-governance/regulatory-context.md` (applicability only; not compliance).
- Phase C1 baseline; Phase C2 evolution analysis (chat artifacts, not files).

## Future Reconsideration

Revisit if the product is split into separately sold runtimes, if 057–073 are extracted or retired, or if a new process is introduced that owns FHIR or the model path.
