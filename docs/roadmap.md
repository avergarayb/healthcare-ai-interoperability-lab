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
- Laboratory LangGraph `StateGraph` for follow-up workflows. Java Clinical Read supplies the clinical facts. The same two deterministic protocols decide eligibility. Gemini may prepare a narrative and does not decide that eligibility. A matched case opens Human Review. `interrupt` suspends the graph. The checkpoint is a SQLite file beside the review database. A stored human decision resumes the same workflow, including after the Python process restarts. This is laboratory orchestration. It is not a production workflow engine. Design: [LangGraph workflow orchestration v1](design/langgraph-workflow-orchestration-v1.md).
- Response-level human-review requirement and proposed review action when the protocol matches.
- Durable SQLite-backed operational review cases with queue, provenance, bounded closure outcomes and transition history.
- Open-case `CLINICAL_REVIEW_CONTEXT_V1` current FHIR projection without protocol reevaluation or persistence.
- Server-rendered synthetic review queue, case page and operational close inside Healthcare AI.
- Synthetic institutional procedure retrieval through `POST /internal/knowledge/retrieve`, with Gemini embeddings, a separate SQLite index and no generated explanation.
- On-demand AI-assisted review for an open follow-up case, with one structured Gemini explanation, claim-level citations and no stored model output.
- One explicit internal follow-up coordination request after a closed review case whose outcome is follow-up coordination planned. The request status `requested` records that internal request. It does not send a message, write FHIR, or schedule an appointment.
- Development authentication for the synthetic review pages: a server-side session, login and logout, and form signatures bound to that session. It is not production identity, verified reviewer identity, RBAC or institutional SSO.
- Development attribution for a new Human Review close and for the first coordination request from that UI. The stored principal is a synthetic development principal. Manual validation passed. It is not verified clinical identity, IAM, SSO, RBAC, or a security audit. Historical rows stay unattributed. This service does not write FHIR. Security audit remains a separate later decision.
- `DEMO_EXPERIENCE_V1` is done as presentation for the synthetic Human Review queue and case page. Implementation is complete: Spanish operational labels, readable UTC dates, one closed technical-details group, one rendering of the appointment that opened a missed-follow-up case, and the unclassified appointment label. Automated tests passed. Manual validation of slice 1 is complete. Visual validation of slice 2 is still pending. It does not change protocols, outcomes, coordination policy, sessions, or attribution. It is not production-ready and not a complete localization.
- Deterministic, evaluation-harness and opt-in real-HAPI coverage. Live embedding and live AI-assistance checks are separate opt-ins from live Gemini narrative tests.
- Laboratory stages 1 and 2 of Mini HIS to Java Clinical Read to the missed-follow-up agent were executed on 2026-10-19. The record is [E2E interoperability validation results](results/e2e-interoperability-validation-v1-results.md). The procedure remains [the design](design/e2e-interoperability-validation-v1.md). Post-consultation live execution was not run. This is not a production certification.

## Current product gaps

The following capabilities are not established by the current repository:

- human-review assignment, claiming and verified reviewer identity;
- clinical assessment or clinical decision support;
- production workflow checkpointing. The laboratory StateGraph checkpoint in SQLite is implemented for one writer process. It is not a production checkpoint store;
- a multi-user product frontend and production human identity; the synthetic review demo has a development session and is not that frontend;
- enterprise IAM/RBAC and multi-tenancy;
- durable audit storage and production operations;
- production secret management and enforced network architecture;
- autonomous actions or FHIR writes from Healthcare AI;
- retirement of `HapiReadClient` and `FHIR_BASE_URL`;
- UCUM beyond `g/dL` and `mmHg`, and a terminology server, ValueSet, or ConceptMap;
- SOAP, HL7 v2 message transport, file connectors, and a route among organizations. Mini LIS keeps one domain service so a later HL7 v2 adapter can submit the same orders and results. ORM/OML, ORU^R01, ACK, and MLLP are not implemented.
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

It remains a development baseline: local HAPI and vendor sandboxes are not production healthcare deployment, the SQLite review store is single-instance, and deterministic follow-up review is not clinical diagnosis. An internal coordination request after an explicit POST is recorded operational evidence. It is not external execution and it is not clinical diagnosis. The synthetic review pages now use the accepted demo presentation. Slice 2 of that presentation still awaits visual confirmation. Clinical Read and the Mini HIS source are laboratory increments in this repository. They are not the bidirectional exchange in ADR-095. Laboratory LangGraph orchestration is implemented for follow-up: Clinical Read, deterministic evaluation, a narrative proposal, Human Review `interrupt` and resume, and SQLite checkpoint recovery after a Python restart. That checkpoint is not production-ready. The 2026-10-19 laboratory E2E result is recorded separately and does not close the product gaps above.
