# AI governance

Governance index for the **Healthcare AI & Interoperability Platform**. These are engineering and product-governance artifacts, not legal advice, clinical policy, compliance certification or regulatory approval.

The platform contains two independently deployable product units:

- **Healthcare Interoperability** — Java / Spring Boot;
- **Healthcare AI** — Python / FastAPI / LangGraph.

## Current documents

1. [`service-security-hardening-v1.md`](service-security-hardening-v1.md) — TASK 005 service, session and federation control matrix, residual risks and MCP readiness gates.
2. [`security-governance-v1-closure.md`](security-governance-v1-closure.md) — TASK 006 validation evidence, coverage limits and pending operational full-stack validation.
3. [`product-governance-boundary.md`](product-governance-boundary.md) — current product, data-flow and model-authority boundary.
4. [`regulatory-context.md`](regulatory-context.md) — applicability questions and technical evidence; legal conclusions require revalidation.
5. [`../contracts/post-consultation-result-review-v1.md`](../contracts/post-consultation-result-review-v1.md) — authoritative internal Clinical Follow-up Review contract.

## Historical and experimental evidence

1. [`laboratory-state.md`](laboratory-state.md) — historical technical snapshot after Tasks 076/077.
2. [`llm-boundary-threats-and-controls.md`](llm-boundary-threats-and-controls.md) — threat model for the separate synthetic Task 076 endpoint, not for the current FHIR-backed follow-up workflow.

Historical statements remain valid evidence for their original date and scope. They do not override current accepted decisions.

## Related ADRs

- [`ADR-076`](../adr/ADR-076-controlled-gemini-integration.md) — accepted synthetic Gemini experiment
- [`ADR-077`](../adr/ADR-077-product-architectural-unit.md) — product identity superseded in part by ADR-084
- [`ADR-078`](../adr/ADR-078-fhir-and-ai-boundary.md) — FHIR/AI separation, superseded in part by ADR-085
- [`ADR-079`](../adr/ADR-079-role-of-057-073-architecture-surface.md) — role of Java 057–073 simulations
- [`ADR-080`](../adr/ADR-080-internal-ai-service-boundary.md) — historical internal-boundary state
- [`ADR-081`](../adr/ADR-081-runtime-packaging-boundary.md) — runtime and local-support distinction
- [`ADR-082`](../adr/ADR-082-inbound-ai-service-protection.md) — inbound protection requirement
- [`ADR-083`](../adr/ADR-083-product-and-local-fhir-packaging.md) — product versus Local-FHIR Support Pack
- [`ADR-084`](../adr/ADR-084-product-identity-and-architectural-units.md) — independent product units
- [`ADR-085`](../adr/ADR-085-python-follow-up-fhir-and-model-authority-boundary.md) — accepted bounded Python FHIR and model-authority decision
