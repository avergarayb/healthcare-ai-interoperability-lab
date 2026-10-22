# Current Architecture

This is the concise architecture authority and index for the **Healthcare AI & Interoperability Platform**. Historical task files and dated snapshots are evidence, not current architecture authority.

## Product units

| Unit | Runtime | Current responsibility |
|---|---|---|
| **Healthcare Interoperability** | Java 21 / Spring Boot | Implemented: FHIR/SMART client, vendor profiles, routing, resilience, transformations, controlled projections, Model Boundary v1, and Clinical Read API v1. The default Clinical Read source is local HAPI. `mini-his` is an optional laboratory source. A laboratory REST path sends one Mini HIS order to Mini LIS and reads the result back through Java. Target, not implemented: independent bidirectional exchange and multi-system federation among authorized organizations. |
| **Healthcare AI** | Python / FastAPI / LangGraph | Controlled AI workflows, deterministic protocol authority, narrative model subflows, and a laboratory `StateGraph` that pauses a matched follow-up case for Human Review. Operational follow-up factories acquire Patient, Encounter, Observation, and Appointment through Clinical Read API v1. |

The units are independently deployable and may be sold separately or composed. Pricing and SKU names are not decided. The commercial connectivity target is [ADR-095](../adr/ADR-095-clinical-normalization-boundary.md).

## Current data flows

```text
Epic / Oracle sandbox / local HAPI
        -> Healthcare Interoperability
        -> controlled projection / Model Boundary v1
        -> Healthcare AI Task 074 consumer (modelCalled=false)
```

```text
local HAPI  (clinical-read.source=local-hapi, the default)
        -> Java Clinical Read API v1
        -> Python ClinicalReadClient
        -> POST_CONSULTATION_RESULT_REVIEW_V1 or MISSED_FOLLOW_UP_REVIEW_V1
        -> durable operational review case when MATCHED
        -> post-consultation narrative subflow only when that protocol allows it
```

```text
Mini LIS (own PostgreSQL, proprietary REST, organization org-mini-lis)
        -> Java reads it only when clinical-read.source=mini-lis
        -> Java normalizes Patient, ServiceRequest, Observation, and DiagnosticReport to FHIR R4
        -> same Clinical Read API v1 envelope, destination mini-lis
        -> Python is not switched onto this source by this increment
```

```text
Mini HIS Simulator (own SQLite, proprietary REST)
        -> Java reads it only when clinical-read.source=mini-his
        -> Java normalizes the payload to FHIR R4
        -> same Clinical Read API v1 envelope
        -> Python ClinicalReadClient and the same follow-up protocols
```

```text
Java Clinical Read API v1
        -> Python StateGraph
        -> clinical_read
        -> context_intelligence
        -> protocol_evaluation
        -> eligibility_router
        -> not_matched or insufficient: completion
        -> matched: narrative
        -> human_review
        -> await_human (interrupt, waiting_human)
        -> stored Human Review decision
        -> Command(resume)
        -> completion
```

Java owns the clinical read. The deterministic protocol owns eligibility. The narrative step may call Gemini and does not choose the protocol result. LangGraph orders those steps, suspends the matched case, and stores the checkpoint. Human Review owns the human decision. A resume continues only after that decision is already stored. The same SQLite checkpoint is what a restarted Python process reads. One process writes that file. This laboratory graph is not a production workflow engine.

Python does not call Mini HIS and does not choose the protocol outcome. `HapiReadClient` remains in the Python tree; the factories named above do not construct it. Clinical review context for an open case uses the same Java read. See [Clinical Read API v1](../contracts/clinical-read-v1.md) and [ADR-095](../adr/ADR-095-clinical-normalization-boundary.md).

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

```text
Closed review case, outcome follow-up coordination planned, explicit Create coordination request
        -> deterministic coordination policy
        -> one durable internal coordination request
```

The follow-up flows above obtain clinical facts through Java. Model Boundary v1, institutional retrieval, AI-assisted review, and the coordination request are separate flows. Retrieval, assistance, and coordination do not call Clinical Read. None of these flows authorize arbitrary FHIR access or writes. `MISSED_FOLLOW_UP_REVIEW_V1` does not call Gemini or LangGraph during protocol evaluation. Institutional retrieval uses Gemini embeddings only. AI-assisted review may then make one structured generation call. It does not use LangGraph. The coordination request does not call Gemini, retrieval, or FHIR. See [ADR-089](../adr/ADR-089-missed-follow-up-review.md), [ADR-090](../adr/ADR-090-institutional-knowledge-rag.md), [ADR-091](../adr/ADR-091-ai-assisted-review.md) and [ADR-092](../adr/ADR-092-controlled-action.md).

## Commercial connectivity target

[ADR-095](../adr/ADR-095-clinical-normalization-boundary.md) is the target, not a description of the flows above.

| | Implemented | Target |
|---|---|---|
| Exchange role | FHIR client for configured destinations, one laboratory Clinical Read path, and one laboratory order route from Mini HIS to Mini LIS through Java. No production route among organizations | Independent bidirectional platform. Clinics, hospitals, EPS, insurers, pharmacies, laboratories, and other authorized systems. Each hop is limited by agreement, permission, and remote capability |
| Connectors | FHIR R4 client: Epic sandbox, Oracle Health sandbox, and laboratory HAPI. Proprietary REST readers for the Mini HIS Simulator and Mini LIS, each used only when selected as the single Clinical Read source. A typed registry can declare another system before its connector exists | FHIR, proprietary REST, SOAP, HL7 v2, and files, inbound and outbound |
| Transformation | Java projects FHIR it has already read. For `mini-his` it also normalizes proprietary JSON to FHIR R4 without calling a FHIR server. Epic, Oracle, and HAPI reads still require a FHIR server | Protocol transformation in both directions. FHIR R4 normalization when the content is clinical. A FHIR server is not mandatory for that engine |
| Exchange controls | Destination routing, resilience, and FHIR-call audit inside the Java client. Tasks 057–073 are simulations, not authorization of an exchange | Routing, validation, traceability, audit, and authorization controls for organizational exchange |
| Python clinical input | Model Boundary v1, plus Clinical Read API v1 for the operational follow-up factories. v1 is not that clinical API. Python does not call Mini HIS | Normalized clinical data only. No dependency on each HIS protocol. Healthcare AI is an optional consumer, not a dependency of the exchange |
| FHIR repository | HAPI FHIR Docker is the laboratory repository and the default Clinical Read source | Optional repository or endpoint, not a mandatory hop |
| Mini HIS Simulator | Local proprietary REST process and its own SQLite database. Java reads it when `clinical-read.source=mini-his` | Laboratory stand-in for a proprietary source. Not the exchange platform |

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
- A closed review case with follow-up coordination planned can record one internal coordination request through a second explicit POST. That request is not a message, a FHIR write, or a scheduled appointment. Gemini and retrieval do not authorize it. See [ADR-092](../adr/ADR-092-controlled-action.md).

## Authoritative documents

- [Product scope](../PROJECT.md)
- [Clinical Follow-up Review V1 contract](../contracts/post-consultation-result-review-v1.md)
- [Missed follow-up review V1 contract](../contracts/missed-follow-up-review-v1.md)
- [Clinical review context V1 contract](../contracts/clinical-review-context-v1.md)
- [Clinical Read API v1 contract](../contracts/clinical-read-v1.md)
- [Mini HIS terminology and UCUM maps](../contracts/mini-his-terminology-v1.md)
- [Mini LIS proprietary REST](../contracts/mini-lis-rest-v1.md)
- [Mini LIS FHIR mapping](../contracts/mini-lis-fhir-v1.md)
- [Mini LIS design](../design/mini-lis-v1.md)
- [Institutional knowledge retrieval V1 contract](../contracts/institutional-knowledge-retrieval-v1.md)
- [AI-assisted review V1 contract](../contracts/ai-assisted-review-v1.md)
- [Controlled action V1 contract](../contracts/controlled-action-v1.md)
- [Human identity V1 contract](../contracts/human-identity-v1.md) — accepted laboratory contract. The review demo requires a development session. Not production identity.
- [Human attribution V1 contract](../contracts/human-attribution-v1.md) — accepted laboratory contract. The review UI records a synthetic development principal on close and on the first coordination request. Manual validation passed. Not production-ready. Not a security audit, not IAM or SSO, not RBAC, and not verified clinical identity. No retrospective attribution and no FHIR write.
- [Operational Follow-up Review Workflow V1 contract](../contracts/follow-up-review-workflow-v1.md)
- [LangGraph workflow orchestration v1](../design/langgraph-workflow-orchestration-v1.md) — laboratory `StateGraph`, interrupt, resume, and SQLite checkpoint. Not production checkpointing.
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
| [ADR-084](../adr/ADR-084-product-identity-and-architectural-units.md) | Establishes independent product units; Python-FHIR current-state portions superseded by ADR-085. Ingress target is ADR-095. |
| [ADR-085](../adr/ADR-085-python-follow-up-fhir-and-model-authority-boundary.md) | Accepted decision for the follow-up resource set and model authority. Operational factories now acquire those resources through Clinical Read API v1. The ADR text still describes the earlier direct FHIR read. |
| [ADR-086](../adr/ADR-086-persistent-follow-up-review-workflow-and-operational-authority-boundary.md) | Accepted current decision for durable operational follow-up review state and authority. Its exclusion of live clinical-detail projection is superseded only by ADR-087. |
| [ADR-087](../adr/ADR-087-case-bound-current-clinical-review-context.md) | Accepted current decision for bounded current clinical context of an open review case. |
| [ADR-088](../adr/ADR-088-server-rendered-human-review-demo.md) | Accepted current decision for the server-rendered synthetic review demo inside Healthcare AI. |
| [ADR-089](../adr/ADR-089-missed-follow-up-review.md) | Accepted current decision for missed follow-up review on the shared review case. |
| [ADR-090](../adr/ADR-090-institutional-knowledge-rag.md) | Accepted current decision for synthetic institutional procedure retrieval. Not production RAG. |
| [ADR-091](../adr/ADR-091-ai-assisted-review.md) | Accepted current decision for on-demand explanatory review assistance. Not production-ready and not clinically certified. |
| [ADR-092](../adr/ADR-092-controlled-action.md) | Accepted current decision for one internal follow-up coordination request after an explicit human POST. Not external execution and not authenticated approval. |
| [ADR-093](../adr/ADR-093-human-review-session.md) | Accepted current decision for a development-only human session. Not production identity, IAM, SSO or RBAC. |
| [ADR-094](../adr/ADR-094-human-attribution.md) | Accepted development attribution. The review UI records a synthetic development principal. Manual validation passed. Not production-ready. Not a security audit, not IAM or SSO, not RBAC, and not verified clinical identity. |
| [ADR-095](../adr/ADR-095-clinical-normalization-boundary.md) | Accepted target: Healthcare Interoperability is an independent bidirectional exchange platform. Laboratory increments now include Clinical Read API v1, Mini HIS normalization, a Mini LIS read normalized to FHIR R4, and one REST order and result path through Java. That path is not multi-system federation. The organizational broker, SOAP, HL7 v2 transport, and file connectors are not implemented. |

## Historical governance artifacts

- [Post-077 laboratory snapshot](../ai-governance/laboratory-state.md)
- [Task 076 experimental LLM threat model](../ai-governance/llm-boundary-threats-and-controls.md)
- `docs/tasks/` and `docs/progress/`

These files must not be read as later implementation state without their original scope and date.
