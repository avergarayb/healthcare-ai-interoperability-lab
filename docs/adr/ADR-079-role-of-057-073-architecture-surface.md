# ADR-079 — Role of 057–073 Architecture Surface

## Status

Proposed

## Date

2026-09-20

## Context

Java contains a long deny-by-default chain (Tasks 057–073) with HTML `/lab/*` pages and JSON `/api/*/v1` endpoints. Phase C1 treated this as a third mass of code in the same process as the FHIR client. C2 listed possible roles without choosing an implementation action. The risk is selling or evolving this surface as IAM, consent, an agent, or CDS.

## Current State

Packages under `lab.healthcare.fhir` include `agent`, `agentstub`, `aiboundary`, `firstai`, `aigateway`, and `aiconsumer*` (policy, readiness, handoff, authorization, consent, scope, access, enforcement, verification, approval). Controllers expose paired HTML and JSON (for example `AiBoundaryController`, `FirstAiController`, `AiConsumerConsentController`).

Their own docs (for example `docs/fhir/ai-consumer-authorization-boundary.md`, `docs/fhir/ai-consumer-consent-boundary.md`) state they do **not** implement a real IdP or real consent. Constructors such as `AiBoundaryDecision` reject `modelCalled=true` and `modelCallAuthorized=true`. `*ArchitectureBoundaryTest` classes lock those rules. This surface does not invoke Gemini (`google-genai` is Python-only).

## Decision

Architecturally, 057–073 are an **in-process simulation and architecture-test surface** (and a historical ladder toward 074). They are **not** a third commercial product and **not** the AI Surface.

They may remain in the Java application as:

- deny-by-default **simulations** for local demonstration (`/lab/*`);
- **automated guards** that `modelCallAuthorized` / `modelCalled` stay false on the interoperability process.

They are **not** interpreted as:

- enterprise IAM or RBAC;
- clinical consent or purpose approval;
- operational HITL;
- clinical decision support;
- an autonomous or tool-using agent;
- a second product;
- a Gemini or other model runtime.

This ADR does **not** delete, move, or refactor packages.

## Rationale

C1: same JVM as `FhirService`; no Gemini; docs deny real auth/consent. C2: roles “simulation/demo” and “internal architecture test” fit the evidence; “product capability” does not. Keeping the code while constraining its *meaning* avoids a silent rewrite.

## Alternatives Considered

- **Treat as product IAM/consent.** Contradicts the task docs and would be a false capability.
- **Treat as the real agent/CDS runtime.** No model, no tools, no write-back.
- **Extract or delete immediately.** Implementation; out of C3.
- **Ignore the surface in architecture.** Leaves a large HTTP/HTML area unexplained (C1 risk).

## Consequences

Positive: commercial and Phase B language stay honest; 074/076 remain the external AI-related paths.

Negative / trade-off: the JAR still ships a large `/lab/*` surface; operators can confuse it with the product runtime (ADR-081). Future packaging may hide or omit it — that is a later decision.

## Boundaries

No code movement; no new gates; no claim that simulations satisfy Ley 29733, Ley 31814, or SIHCE/RENHICE.

## Related Decisions

- ADR-077 — simulations are a non-commercial surface of the same product.
- ADR-078 — this surface does not create a FHIR → Gemini path.
- `docs/fhir/model-boundary-contract-v1.md` (Tasks 057–073 consume v1 as-is).
- `docs/ai-governance/laboratory-state.md` (historical 057–073 wording).
- `docs/ai-governance/product-governance-boundary.md` §8, §18.

## Future Reconsideration

Revisit if the product runtime is packaged without `/lab/*`, if a real identity or consent provider is introduced (a new ADR), or if any 057–073 type begins calling a model.
