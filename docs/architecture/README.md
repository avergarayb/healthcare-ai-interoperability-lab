# Current Architecture

This is the concise architecture authority and index for the **Healthcare AI & Interoperability Platform**. Historical task files and dated snapshots are evidence, not current architecture authority.

## Product units

| Unit | Runtime | Current responsibility |
|---|---|---|
| **Healthcare Interoperability** | Java 21 / Spring Boot | FHIR/SMART connectivity, vendor profiles, routing, resilience, transformations, controlled projections and interoperability contracts. |
| **Healthcare AI** | Python / FastAPI / LangGraph | Controlled AI workflows, authorized bounded FHIR acquisition for explicit capabilities, deterministic protocol authority and narrative model subflows. |

The units are independently deployable and may be composed. Final commercial packaging is not decided.

## Current data flows

```text
Epic / Oracle sandbox / local HAPI
        -> Healthcare Interoperability
        -> controlled projection / Model Boundary v1
        -> Healthcare AI Task 074 consumer (modelCalled=false)
```

```text
Configured authorized FHIR endpoint
        -> Healthcare AI case-bound GET reads
        -> mandatory Patient + Encounter + Observation + Appointment snapshot
        -> deterministic POST_CONSULTATION_RESULT_REVIEW_V1
        -> authorized LangGraph/Gemini narrative subflow when allowed
        -> application-owned response projection
```

The second flow does not require the Java process merely to obtain FHIR context when an authorized FHIR endpoint is configured. It does not authorize arbitrary FHIR access or writes.

## Authority boundaries

- The application chooses mandatory FHIR acquisition; the model does not.
- FHIR search completeness and resource/reference integrity are evaluated before absence is trusted.
- The deterministic protocol owns `protocol`, `clinicalAssessment`, `humanReview` and `action`.
- Gemini owns only legacy narrative output such as `answer` and `followUpRequired`.
- FHIR-derived model input is allowed only through explicitly authorized tool/data contracts.
- `humanReview.status=required` is a response-level requirement, not a durable review work item.
- `action.status=proposed` is not external execution.

## Authoritative documents

- [Product scope](../PROJECT.md)
- [Clinical Follow-up Review V1 contract](../contracts/post-consultation-result-review-v1.md)
- [Healthcare Interoperability architecture](../fhir/fhir-architecture.md)
- [Healthcare AI runbook](../../services/ai-service/README.md)
- [AI governance](../ai-governance/README.md)

## ADR index

| ADR | Status in the current architecture |
|---|---|
| [ADR-076](../adr/ADR-076-controlled-gemini-integration.md) | Accepted historical decision for the separate synthetic Gemini endpoint. |
| [ADR-077](../adr/ADR-077-product-architectural-unit.md) | Product-identity portion superseded by ADR-084; retained as history. |
| [ADR-078](../adr/ADR-078-fhir-and-ai-boundary.md) | Absolute Python-FHIR prohibition superseded in part by ADR-085; remaining separation principles retained. |
| [ADR-079](../adr/ADR-079-role-of-057-073-architecture-surface.md) | Current classification of Java 057–073 as simulation/architecture surface. |
| [ADR-080](../adr/ADR-080-internal-ai-service-boundary.md) | Historical boundary state; inbound authentication was subsequently implemented. |
| [ADR-081](../adr/ADR-081-runtime-packaging-boundary.md) | Local support-stack distinction retained; product-unit framing refined by ADR-084. |
| [ADR-082](../adr/ADR-082-inbound-ai-service-protection.md) | Authentication requirement implemented; effective production network boundary remains unresolved. |
| [ADR-083](../adr/ADR-083-product-and-local-fhir-packaging.md) | Local-FHIR Support Pack distinction retained; single-runtime wording refined by ADR-084. |
| [ADR-084](../adr/ADR-084-product-identity-and-architectural-units.md) | Establishes independent product units; Python-FHIR current-state portions superseded by ADR-085. |
| [ADR-085](../adr/ADR-085-python-follow-up-fhir-and-model-authority-boundary.md) | Accepted current decision for bounded Python FHIR reads and model authority. |

## Historical governance artifacts

- [Post-077 laboratory snapshot](../ai-governance/laboratory-state.md)
- [Task 076 experimental LLM threat model](../ai-governance/llm-boundary-threats-and-controls.md)
- `docs/tasks/` and `docs/progress/`

These files must not be read as later implementation state without their original scope and date.
