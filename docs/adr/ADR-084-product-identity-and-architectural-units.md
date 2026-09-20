# ADR-084 — Product Identity and Architectural Units

## Status

Proposed

## Date

2026-09-20

## Context

ADR-077 (Proposed, 2026-09-20) defined the architectural unit as one **Healthcare AI & Interoperability Platform**: three logical boundaries on two technical surfaces (Java Interoperability Surface, Python AI Surface). It stated that Java and Python are **not** two commercial products, because they share `ModelBoundaryContract` v1, a laboratory `X-Service-Token`, and Phase B gates G0–G4.

Phase C9 reviewed that hypothesis against a different commercial/architectural goal: Java and Python must be able to exist and deploy independently; an integrated offering is optional composition, not a structural dependency. ADR-077 already listed this trigger under Future Reconsideration (“if the product is split into separately sold runtimes”).

This ADR records that change of **architectural unit**. It does not choose legal entities, pricing, SKUs, or a commercial catalog. It does not implement code, contracts, adapters, or network isolation.

The repository today still has two processes (`fhir-integration-service`, `ai-service`) and one implemented Java→Python hop (074 consumes v1). Independence is an architectural target. Feature completeness is not implied.

## Decision

The deployable architectural units are:

### Product A — Java Interoperability

An independent interoperability unit. It connects healthcare systems. It does not require Python.

**Conceptual responsibility:** external connectivity; FHIR interoperability; SMART/EHR connectivity; transformations; mappings; routing; adapters; bidirectional and system-to-system integration; possible future HL7 v2, SOAP, or proprietary APIs.

**Currently implemented:** FHIR R4 *client* (not a product FHIR server); SMART Authorization Code + PKCE; Epic and Oracle sandbox destinations; local HAPI as a configurable destination; snapshot; Task 042 allowlist; RetentionCeiling N=5; `ModelBoundaryContract` v1; in-process simulations 057–073 (`/lab/*`, ADR-079).

**Not implemented (evolution, not current capability):** HL7 v2; SOAP; proprietary insurer/pharmacy APIs; Clinic A ↔ Clinic B / Pharmacy / Insurer / Laboratory as a multi-protocol broker.

Java is not merely an adapter that exists to feed Python. It can expose v1 and still be useful with no AI process installed.

### Product B — Python Healthcare AI

An independent controlled-AI unit. It does not require Java as a universal architectural dependency.

**Conceptual responsibility:** controlled AI use cases; AI context; model-boundary consumption; LLM provider abstraction; gated model invocation; application-owned `requiresHumanReview` / `modelCalled`; AI-specific governance (G0 today).

**Currently implemented:** `GET /internal/agent-context` (074) consumes **v1** from a configured HTTP producer (default `http://localhost:8081`); `POST /internal/experimental-summary` (076) accepts only fixture `SYN-076-001` and may call Gemini; inbound `X-Service-Token` on both; Python is not a FHIR/EHR client (ADR-078).

**Not implemented / not decided here:** Python receiving FHIR resources or Bundles directly. This ADR does **not** authorize a Python FHIR client, Epic/Oracle/HAPI access, or FHIR → Gemini.

074 today depends on *a v1 producer*. That producer is Java in this repository. Another compatible v1 producer is an integration possibility, not an implemented third product.

### Integrated Solution — A + B

Optional composition of Product A and Product B. Not a third independent runtime.

```text
Product A (Java)
        │
        │ ModelBoundaryContract v1
        ▼
Product B (Python 074)     modelCalled=false
        X
        Gemini

SYN-076-001
        │
        ▼
Product B (Python 076)
        │
        ▼
Gemini   (experimental, gated)
```

A does not need B for interoperability. B does not need A for 076. B’s 074 path needs a v1 producer, which may be A.

## Current Implementation Boundary

| | |
|---|---|
| **Implemented today** | Two host processes; Java FHIR/SMART/EHR client path; v1; 074 consumer of v1; 076 synthetic Gemini; shared laboratory token; HAPI Compose support pack (not product EHR); 057–073 in the Java process |
| **Architectural target** | A deployable without B; B deployable without A for capabilities that do not need a v1 producer; Integrated Solution as optional A+B; Java not modeled as “FHIR adapter for Python” |
| **Future evolution** | Multi-protocol / system-to-system interop on A; whether B may ingest FHIR from a non-EHR-client contract; contract evolution beyond v1; packaging/SKU mechanics |

## Integration Contract

- **Java → Python (074), currently:** `ModelBoundaryContract` v1 on `GET /api/model-boundary/v1`. Not a FHIR Bundle. Not LLM input (ADR-078).
- **FHIR, currently:** interoperability contract between Java and EHR/FHIR destinations (Epic, Oracle, local HAPI). Not the Java→Python contract.
- **Python-direct-FHIR:** future decision. Not implemented. Not authorized by this ADR.
- **076:** unchanged. Fixture only. No FHIR. No v1.

Sharing v1 or `MODEL_BOUNDARY_SERVICE_TOKEN` does not merge A and B into one mandatory deployable, and does not merge 074 and 076.

## System-to-System Interoperability

System-to-system integration (including future Clinic ↔ Clinic / Pharmacy / Insurer / Laboratory, and possible HL7/API/SOAP/proprietary hops) belongs **conceptually** to Product A.

That capability is an **architectural direction**. It is **not implemented**. This ADR does not add HL7, SOAP, or those connectors.

## Independence

- **Java must work without Python.** Already true in process terms: Java does not call `:8090`.
- **Python is architecturally independent of Java** as a unit. 076 already runs without Java. 074 still requires a v1 HTTP producer; independence of 074 is a target, not current completeness.

## Integrated Solution

A+B is optional. Installing both does not create a third product process. Service-to-service use of v1 is the current integration hop.

## Network consequence (not decided here)

| Deploy | Consequence |
|---|---|
| A only | No Python listener; no AI-internal Z3 (C8) |
| B only | Python is the AI surface; 074/076 remain internal (ADR-080/082) |
| A+B | v1 hop is service-to-service; 074/076 stay non-public |

How reachability is enforced remains a later decision. This ADR does not choose bind, isolation, or cloud networking.

## Consequences

Positive: A can be adopted for interoperability without AI; B can be adopted for controlled AI when an input contract exists (today: 076, or 074+v1); Integrated Solution is explicit composition; Java is not reduced to a Python feeder.

Trade-offs: contracts and versioning between units; separate security perimeters; independent deploy concerns; Phase B “one product” wording and ADR-081/083 “Product Runtime = Java+Python” will need a later editorial/review pass (not done in this ADR). A future Python FHIR-ingress decision, if any, needs its own ADR and must not silently reuse 076 or violate ADR-078.

## Non-Goals

No implementation of: Python FHIR ingestion; HL7 v2; SOAP; proprietary adapters; network isolation; Kubernetes/cloud/installer/SaaS infrastructure; IAM; mTLS; Vault; API gateway; RAG; agents; MCP; second LLM provider; fallback/router; FHIR → Gemini; v1 → Gemini; changes to v1 fields; deletion of 057–073.

No legal, compliance, SIHCE, or RENHICE claims.

## Impact on ADR-077

ADR-084 **supersedes** ADR-077’s **product identity** decision: a single Healthcare AI & Interoperability Platform that is “not two commercial products,” and the pairing of Java+Python as one architectural unit *because* they share v1 and a token.

ADR-077 is **not deleted**. It remains the historical record.

**Superseded in ADR-077:** Decision paragraph on single product identity; the sentence that Java and Python “remain one product” / “are not two commercial products”; treating shared v1+token as proof of one commercial unit; Rationale/Alternatives framed only as one-platform options A–D.

**Not superseded (still valid as technical facts):** Current State inventory (two processes, Java owns FHIR client, Python owns 074/076, Compose is support, 057–073 in Java); three *logical* concerns (FHIR integration, v1/clinical projection, controlled AI) as descriptions of what exists; two *processes* so Python is not an EHR client and Gemini stays off the FHIR path (ADR-078); HAPI and `/lab/*` are not SIHCE/IAM; out-of-scope list (no K8s/IAM/RAG in that ADR); Future Reconsideration trigger that this ADR exercises.

## Impact on ADR-078–083

These files are **not modified** by C10.

| ADR | Remains valid | Future review (not in this change) |
|---|---|---|
| **078** | Java is the current FHIR/EHR client boundary; Python is not a FHIR/EHR client; v1 ≠ model input; 074 ≠ 076; no FHIR/v1 → Gemini | If Python-direct-FHIR is ever designed, a new ADR; must not turn Python into an Epic/Oracle/HAPI client |
| **079** | 057–073 stay a Java simulation/architecture-test surface, not Product B | Whether a Java-only deliverable includes `/lab/*` |
| **080** | Internal AI HTTP intention applies to Product B | Wording that assumes a single platform |
| **081** | HAPI stack is local support, not product EHR/DB/IAM/edge | “Product runtime = Java and Python” as the *only* commercial deploy unit |
| **082** | Inbound s2s + network *requirement* for 074/076; auth layer implemented; network layer still open | Perimeter described per A-only / B-only / A+B (C8), without choosing tools |
| **083** | Local-FHIR Support Pack remains optional and non-product | “One product” / single Product Runtime pair vs three deployable units |

ADR-076 remains Accepted for the experimental Gemini path. Its historical “Product B” label is not rewritten here.

`docs/ai-governance/product-governance-boundary.md` still says one product and two surfaces. That document is **not** updated in this change; it is a future governance editorial if this ADR is accepted.

## Open Decisions

- Python-direct-FHIR ingestion (whether, what contract, not a client to Epic/Oracle/HAPI)
- Evolution of the A↔B contract beyond v1
- HL7 v2 / SOAP / proprietary adapters on Product A
- Legal SKU / pricing / catalog names
- Network-boundary enforcement (C8 properties; no tool chosen)
- How Phase B gates G0–G4 apply when A and B are adopted separately
- Materialization of independent deliverables (images, installer, etc.)

## Related Decisions

- ADR-077 — prior unit (identity superseded; file retained)
- ADR-076 — controlled Gemini (do not modify)
- ADR-078 — FHIR and AI boundary
- ADR-079 — 057–073
- ADR-080 / ADR-082 — internal AI protection
- ADR-081 / ADR-083 — packaging vs Local-FHIR Support Pack
- Phase C9 — Product Architecture Boundary Review (chat artifact)

## Future Reconsideration

Revisit if A and B are legally packaged as one SKU again, if a new process owns FHIR or the model path, if 074’s v1 producer is specified as something other than Product A, or if a written decision authorizes Python FHIR ingress.
