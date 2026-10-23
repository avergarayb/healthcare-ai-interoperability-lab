# Roadmap

This document summarizes implemented foundations and visible product gaps for the **Healthcare AI & Interoperability Platform**. It does not select the next product increment or authorize speculative implementation.

Product scope lives in [PROJECT.md](PROJECT.md). Current authority boundaries live in the [architecture index](architecture/README.md).

## Implemented foundation

### Healthcare Interoperability

- Java 21 / Spring Boot FHIR R4 client.
- Local HAPI FHIR and PostgreSQL support stack.
- Named FHIR destinations and bounded routing/resilience behavior.
- SMART Authorization Code + PKCE foundations.
- Epic and Oracle sandbox integrations.
- Controlled snapshot, allowlist, retention ceiling and Model Boundary v1.
- Service-token protection for the v1 boundary.
- Laboratory Clinical Read API v1 for Patient, Encounter, Observation, and Appointment. The same service token protects it. The default source is local HAPI. Contract: [clinical-read-v1](contracts/clinical-read-v1.md). This line records source. It does not record a test run.
- Mini HIS Simulator as a separate process with its own SQLite database and a proprietary REST API. Java reads it only when `clinical-read.source=mini-his` and normalizes the payload to FHIR R4. It is not in the HAPI Docker stack and it is not an organizational exchange.
- Mini LIS as a separate Spring Boot process with its own PostgreSQL database and a proprietary REST API. Java reads it only when `clinical-read.source=mini-lis` and normalizes Patient, ServiceRequest, Observation, and DiagnosticReport to FHIR R4. The default Clinical Read source stays local HAPI. This read is not a bidirectional exchange. A typed source registry lists declared systems. A new system still needs its own connector. Contract: [mini-lis-rest-v1](contracts/mini-lis-rest-v1.md). Mapping: [mini-lis-fhir-v1](contracts/mini-lis-fhir-v1.md).
- Laboratory order exchange from Mini HIS to Mini LIS through FHIR Integration Service. Java builds a FHIR R4 ServiceRequest, submits the proprietary Mini LIS command, stores the HIS, FHIR, and LIS identifier correlation in its own SQLite file, and returns Observation and DiagnosticReport to Mini HIS. There is no direct Mini HIS to Mini LIS connection. Patient matching uses the identifier system, value, and requesting organization. A repeated request does not create a second order. A report before any result is empty. Clinical Read stays a single source. This route is not multi-system federation. The default connector is REST. An optional HL7 v2.5.1 connector sends `OML^O21` and receives `ORU^R01` over loopback MLLP. That connector is not production transport and it does not replace REST. Contract: [cross-org-lab-exchange-v1](contracts/cross-org-lab-exchange-v1.md). HL7 profile: [hl7v2-laboratory-v1](contracts/hl7v2-laboratory-v1.md).
- Clinical Federation v1, `POST /api/clinical-federation/v1/context`. A caller authorized as Mini HIS can read Mini HIS and, when an exchange patient link exists, Mini LIS in one response. Each entry keeps its source, organization, and `meta.source`. Resources are not merged because their code and value match. A missing link, a source error, a missing connector, and an unauthorized source stay distinct. The default Clinical Read source remains `local-hapi`. Python can consume that envelope when `AI_CLINICAL_CONTEXT_MODE=federated`. The default mode is `single` and does not call this endpoint. Contract: [clinical-federation-v1](contracts/clinical-federation-v1.md). AI consumer: [ai-clinical-federation-v1](contracts/ai-clinical-federation-v1.md). Design: [multi-source-clinical-federation-v1](design/multi-source-clinical-federation-v1.md) and [federated-clinical-context-ai-v1](design/federated-clinical-context-ai-v1.md).
- Static Mini HIS maps `mini-his-maps-v1` and UCUM maps `mini-his-ucum-v1` for `g/dL` and `mmHg`. No terminology server, no general LOINC or SNOMED, and no numeric unit conversion. Contract: [mini-his-terminology-v1](contracts/mini-his-terminology-v1.md).

### Healthcare AI

- Python / FastAPI service.
- Authenticated Model Boundary v1 consumer without model invocation.
- Separate disabled-by-default synthetic Gemini endpoint.
- LangGraph narrative agent subflow with explicit tool policy.
- Clinical Follow-up Review endpoint.
- Mandatory application-owned Patient, Encounter, Observation and Appointment acquisition.
- Bounded, completeness-aware collection handling and case isolation. The operational post-consultation, missed-follow-up, and clinical-context factories, including the open-case page reader, call Java through `ClinicalReadClient`. `HapiReadClient` and `FHIR_BASE_URL` remain in the repository. Python does not call Mini HIS.
- Deterministic `POST_CONSULTATION_RESULT_REVIEW_V1` outside model authority.
- Deterministic `MISSED_FOLLOW_UP_REVIEW_V1` from Patient and Appointment reads only, without Gemini, on the same review queue.
- Laboratory LangGraph `StateGraph` for follow-up workflows. The default source is Java Clinical Read. `AI_CLINICAL_CONTEXT_MODE=federated` reads the Clinical Federation envelope instead and does not fall back to Clinical Read. The same two deterministic protocols decide eligibility in single mode. In federated mode a patient that does not carry the follow-up case identifier stays `insufficient`; that is not a clinical match and not evidence of normality. Gemini may prepare a narrative and does not decide eligibility. A matched case opens Human Review. `interrupt` suspends the graph. The checkpoint is a SQLite file beside the review database. A stored human decision resumes the same workflow, including after the Python process restarts. This is laboratory orchestration. It is not a production workflow engine. Design: [LangGraph workflow orchestration v1](design/langgraph-workflow-orchestration-v1.md) and [federated clinical context](design/federated-clinical-context-ai-v1.md).
- Response-level human-review requirement and proposed review action when the protocol matches.
- Durable SQLite-backed operational review cases with queue, provenance, bounded closure outcomes and transition history.
- Open-case `CLINICAL_REVIEW_CONTEXT_V1` current FHIR projection without protocol reevaluation or persistence.
- Server-rendered synthetic review queue, case page and operational close inside Healthcare AI.
- Synthetic institutional procedure retrieval through `POST /internal/knowledge/retrieve`, with Gemini embeddings, a separate SQLite index and no generated explanation.
- On-demand AI-assisted review for an open follow-up case, with one structured Gemini explanation, claim-level citations and no stored model output.
- One explicit internal follow-up coordination request after a closed review case whose outcome is follow-up coordination planned. The request status `requested` records that internal request. It does not send a message, write FHIR, or schedule an appointment.
- Development authentication for the synthetic review pages: a server-side session, login and logout, and form signatures bound to that session. It is not production identity, verified reviewer identity, RBAC or institutional SSO.
- Development attribution for a new Human Review close and for the first coordination request from that UI. The stored principal is a synthetic development principal. Manual validation passed. It is not verified clinical identity, IAM, SSO, RBAC, or a security audit. Historical rows stay unattributed. This service does not write FHIR. Security audit remains a separate later decision.
- `DEMO_EXPERIENCE_V1`, including slice 2, is complete and validated in the laboratory as presentation for the synthetic Human Review queue and case page. Implementation covers Spanish operational labels, readable UTC dates, one closed technical-details group, one rendering of the appointment that opened a missed-follow-up case, and the unclassified appointment label. Automated tests passed. Manual validation of slice 1 is complete. Visual validation of slice 2 is complete: `SYN-DEMO-102` through Java Clinical Read against local HAPI, and `SYN-DEMO-101` in an isolated temporary review with an in-memory FHIR gateway. Java Clinical Read was used for `SYN-DEMO-102` only. It does not change protocols, outcomes, coordination policy, sessions, or attribution. It is not production-ready and not a complete localization.
- Deterministic, evaluation-harness and opt-in real-HAPI coverage. Live embedding and live AI-assistance checks are separate opt-ins from live Gemini narrative tests.
- Laboratory stages 1 and 2 of Mini HIS to Java Clinical Read to the missed-follow-up agent were executed on 2026-10-19. The record is [E2E interoperability validation results](results/e2e-interoperability-validation-v1-results.md). The procedure remains [the design](design/e2e-interoperability-validation-v1.md). Post-consultation live execution was not run. This is not a production certification.

## Current product gaps

The following capabilities are not established by the current repository:

- human-review assignment, claiming and verified reviewer identity;
- clinical assessment or clinical decision support;
- production workflow checkpointing. The laboratory StateGraph checkpoint in SQLite is implemented for one writer process. It is not a production checkpoint store;
- a multi-user product frontend and production human identity; the synthetic review demo has a development session and is not that frontend;
- enterprise IAM/RBAC and multi-tenancy;
- demographic or probabilistic patient matching. Federation uses an explicit identifier link only;
- a production master patient index or production clinical federation. The laboratory federated mode is opt-in, sequential, and limited to the granted Mini HIS and Mini LIS connectors. It does not emit a FHIR Provenance resource. It does not evaluate the follow-up protocols over the federated envelope. `federated_protocol_not_resolved` means the protocol was not resolved;
- durable audit storage and production operations;
- production secret management and enforced network architecture;
- autonomous actions or FHIR writes from Healthcare AI;
- retirement of `HapiReadClient` and `FHIR_BASE_URL`;
- UCUM beyond `g/dL` and `mmHg`, and a terminology server, ValueSet, or ConceptMap;
- SOAP and file connectors. HL7 v2.5.1 laboratory `OML^O21`, `ORU^R01`, `ACK`, and loopback MLLP are implemented as an optional Mini LIS connector. REST remains the default. ORM, TLS, and a production network are not implemented. The laboratory REST order route is not a production network. Mini LIS keeps one domain service for both protocols.
- protocol registry/lifecycle beyond the current versioned contract;
- production packaging for SaaS, customer-hosted or hybrid operation;
- completed governance and legal assessment for real clinical data sent to an external model.

This list is an inventory, not a priority order.

## Candidate future capabilities

Future product decisions may consider:

- reviewer assignment and identity-backed case management;
- additional explicitly authorized FHIR capabilities or adapters;
- broader interoperability mechanisms such as HL7 v2 or other designed adapters;
- production identity, tenancy, audit and deployment controls;
- production retrieval beyond the synthetic institutional index, local models, MCP or additional providers;
- customer-facing applications and integrations;
- an external adapter that consumes an already recorded internal coordination request. The coordination policy remains the authorization decision;
- production identity for human review, distinct from the accepted development session.
Each candidate requires a separate product decision, security assessment and acceptance contract. Historical phase names under `docs/tasks/` remain development history rather than current sequencing authority.

## Current position

The repository has an implemented interoperability foundation and an implemented Healthcare AI workflow foundation. It is beyond the former “Phase 2–3” and “future AI/LangGraph” descriptions.

It remains a development baseline: local HAPI and vendor sandboxes are not production healthcare deployment, the SQLite review store is single-instance, and deterministic follow-up review is not clinical diagnosis. An internal coordination request after an explicit POST is recorded operational evidence. It is not external execution and it is not clinical diagnosis. The synthetic review pages now use the accepted demo presentation. `DEMO_EXPERIENCE_V1`, including slice 2, is complete and validated in the laboratory. Clinical Read and the Mini HIS source are laboratory increments in this repository. They are not the bidirectional exchange in ADR-095. Laboratory LangGraph orchestration is implemented for follow-up: Clinical Read, deterministic evaluation, a narrative proposal, Human Review `interrupt` and resume, and SQLite checkpoint recovery after a Python restart. That checkpoint is not production-ready. The 2026-10-19 laboratory E2E result is recorded separately and does not close the product gaps above.
