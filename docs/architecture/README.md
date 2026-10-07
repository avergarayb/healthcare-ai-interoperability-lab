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
        -> durable operational review case when MATCHED
        -> authorized LangGraph/Gemini narrative subflow when allowed
        -> application-owned response projection
```

```text
Configured authorized FHIR endpoint
        -> Healthcare AI Patient resolution + bounded Appointment search
        -> deterministic MISSED_FOLLOW_UP_REVIEW_V1
        -> one durable review case per missed Appointment when MATCHED
        -> shared review queue and case page
```

```text
Repository institutional Markdown
        -> deterministic chunks
        -> Gemini embedding, cached in a separate SQLite index
        -> POST /internal/knowledge/retrieve
        -> bounded institutional chunks and provenance
```

```text
Open review case, explicit Generate AI assistance
        -> bounded Clinical Review Context projection
        -> server-owned institutional query
        -> one structured Gemini explanation
        -> trusted citation projection on the same HTML page
```

These flows do not require the Java process merely to obtain FHIR context when an authorized FHIR endpoint is configured. They do not authorize arbitrary FHIR access or writes. `MISSED_FOLLOW_UP_REVIEW_V1` does not call Gemini or LangGraph during protocol evaluation. Institutional retrieval uses Gemini embeddings only. AI-assisted review may then make one structured generation call. It does not use LangGraph. See [ADR-089](../adr/ADR-089-missed-follow-up-review.md), [ADR-090](../adr/ADR-090-institutional-knowledge-rag.md) and [ADR-091](../adr/ADR-091-ai-assisted-review.md).

## Authority boundaries

- The application chooses mandatory FHIR acquisition; the model does not.
- FHIR search completeness and resource/reference integrity are evaluated before absence is trusted.
- The deterministic protocol owns `protocol`, `clinicalAssessment`, `humanReview` and `action`.
- Legacy Gemini narrative owns `answer` and `followUpRequired`. AI-assisted review owns a separate explanatory JSON output and does not select the review outcome.
- FHIR-derived model input is allowed only through explicitly authorized tool/data contracts.
- `humanReview.status=required` remains a response-level protocol requirement. A separate `FollowUpReviewCase` is the durable operational work item.
- `action.status=proposed` is not external execution.
- Gemini cannot create, close or select the outcome of an operational review case.
- The synthetic review demo is server-rendered HTML inside Healthcare AI. It presents the existing review contracts and does not give the browser `X-Service-Token`. Close forms are signed with `HUMAN_REVIEW_FORM_SIGNING_SECRET`, not the service token. See [ADR-088](../adr/ADR-088-server-rendered-human-review-demo.md).
- Institutional retrieval returns procedure text and provenance. It does not own protocol evaluation or review-case state. Query embedding and new-chunk embedding both depend on the embedding provider. See [ADR-090](../adr/ADR-090-institutional-knowledge-rag.md).
- AI-assisted review explains an open case on demand. FHIR facts, the deterministic protocol and the human outcome stay authoritative. Observation values and patient identity are not sent to Gemini. `NO_RELEVANT_GUIDANCE` and retrieval `UNAVAILABLE` do not call Gemini. Output is not stored. See [ADR-091](../adr/ADR-091-ai-assisted-review.md).

## Authoritative documents

- [Product scope](../PROJECT.md)
- [Clinical Follow-up Review V1 contract](../contracts/post-consultation-result-review-v1.md)
- [Missed follow-up review V1 contract](../contracts/missed-follow-up-review-v1.md)
- [Institutional knowledge retrieval V1 contract](../contracts/institutional-knowledge-retrieval-v1.md)
- [AI-assisted review V1 contract](../contracts/ai-assisted-review-v1.md)
- [Operational Follow-up Review Workflow V1 contract](../contracts/follow-up-review-workflow-v1.md)
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
| [ADR-086](../adr/ADR-086-persistent-follow-up-review-workflow-and-operational-authority-boundary.md) | Accepted current decision for durable operational follow-up review state and authority. Its exclusion of live clinical-detail projection is superseded only by ADR-087. |
| [ADR-087](../adr/ADR-087-case-bound-current-clinical-review-context.md) | Accepted current decision for bounded current clinical context of an open review case. |
| [ADR-088](../adr/ADR-088-server-rendered-human-review-demo.md) | Accepted current decision for the server-rendered synthetic review demo inside Healthcare AI. |
| [ADR-089](../adr/ADR-089-missed-follow-up-review.md) | Accepted current decision for missed follow-up review on the shared review case. |
| [ADR-090](../adr/ADR-090-institutional-knowledge-rag.md) | Accepted current decision for synthetic institutional procedure retrieval. Not production RAG. |
| [ADR-091](../adr/ADR-091-ai-assisted-review.md) | Accepted current decision for on-demand explanatory review assistance. Not production-ready and not clinically certified. |

## Historical governance artifacts

- [Post-077 laboratory snapshot](../ai-governance/laboratory-state.md)
- [Task 076 experimental LLM threat model](../ai-governance/llm-boundary-threats-and-controls.md)
- `docs/tasks/` and `docs/progress/`

These files must not be read as later implementation state without their original scope and date.
