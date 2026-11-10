# Project Definition

## Product vision

Build the **Healthcare AI & Interoperability Platform** as a controlled foundation for healthcare-system connectivity and AI-assisted workflows.

The platform contains two independently deployable product units. They may be composed or eventually commercialized together or independently; final pricing, packaging and SKUs are not decided.

### Healthcare Interoperability

Java 21 / Spring Boot product unit responsible for healthcare-system connectivity and interoperability contracts.

Currently implemented:

- FHIR R4 client capabilities;
- local HAPI FHIR connectivity;
- SMART Authorization Code + PKCE foundations;
- Epic and Oracle sandbox profiles;
- routing, resilience, audit and bounded FHIR operations;
- controlled clinical snapshots and projections;
- Model Boundary Contract v1.

It is not currently a product FHIR server, customer EHR, SIHCE or RENHICE participant.

### Healthcare AI

Python / FastAPI / LangGraph product unit responsible for controlled AI workflows and application-owned AI decision boundaries.

Currently implemented:

- authenticated internal Model Boundary v1 consumption without model invocation;
- a separate gated synthetic Gemini summary endpoint;
- Clinical Follow-up Review through `POST /internal/agent/follow-up`;
- direct, stable but constrained FHIR reads for that authorized capability;
- deterministic `POST_CONSULTATION_RESULT_REVIEW_V1` authority outside the model;
- deterministic `MISSED_FOLLOW_UP_REVIEW_V1` for a past `noshow` without a confirmed future Appointment, without Gemini;
- durable operational follow-up review cases with bounded queue, provenance and closure APIs;
- a server-rendered synthetic review demo at `/review-cases` inside this process;
- an authorized legacy/narrative LangGraph/Gemini subflow;
- `INSTITUTIONAL_KNOWLEDGE_RETRIEVAL_V1`, a synthetic institutional-procedure index retrieved with Gemini embeddings;
- `AI_ASSISTED_REVIEW_V1`, an on-demand explanation for an open review case. It does not store the model output and does not choose the human outcome.
- `CONTROLLED_ACTION_V1`, one internal follow-up coordination request after a closed case whose outcome is follow-up coordination planned. Closing the case does not create it. Gemini does not authorize it.

### Enterprise laboratory path

This path is integrated for offline laboratory use. It does not share clinical authority, and it is not production Microsoft 365, a real LLM, RAG, MCP, or Gate D.

- Enterprise Connector Authorization V1 TASK 001–005 and DEMO-001 are integrated (PR #109–#114). A four-node LangGraph workflow reads registered synthetic documents through an offline Graph adapter. Connector gates A and B are read and delivery. The adapter is not a live Microsoft Graph connection.
- Enterprise AI Processing Authorization V1 DESIGN-001, TASK-C01, and TASK-C02 are integrated (PR #115–#117). C01 evaluates Gate C only: a complete grant and recognized synthetic evidence may return `ALLOW_PROCESSING`, which is not executable. C02 adds a Windows-only offline fake gateway, a separate SQLite ledger, one-time leases, reservations, phases T1–T4, durable audit, and `UNKNOWN`/`UNCERTAIN`. It does not deliver an answer to a user. The older connector workflow still denies its Gate C. Gate D stays disabled. C02 does not open that older path.
- Codex completed the integrated work through C02. Cursor is the laboratory executor from this documentation baseline. TASK-C03 is the next candidate and is not authorized. DEMO-002, TASK-C04, and a later PostgreSQL evaluation are also not authorized.

Codex recorded, before the C02 merge and not re-run for this documentation change: C02 224 passed, C01 192 passed, and connector TASK 002–005 plus DEMO-001 617 passed with 1 skipped. The historical total is 1,033 passed and one inherited skip.

The enterprise limits that remain are Windows offline only, POSIX unsupported, a pending Windows file symlink, uncoordinated writers outside the admission barrier, two SQLite stores without a distributed transaction, no guaranteed external revocation, no enterprise IAM, no Microsoft credentials, no real LLM, no final grounding, no human delivery, no enterprise RAG, embeddings, or MCP, no production readiness, and no guaranteed cryptographic erasure. M01, M02, and the C02 P2 findings remain.

Healthcare AI does not have arbitrary FHIR access. Current follow-up reads are case-bound, GET-only, resource-constrained, bounded, completeness-aware and fail-closed. See [ADR-085](adr/ADR-085-python-follow-up-fhir-and-model-authority-boundary.md) and the [V1 contract](contracts/post-consultation-result-review-v1.md).

## Composition

Healthcare Interoperability and Healthcare AI are not structurally dependent product processes. Java works without Python. Healthcare AI may use a configured authorized FHIR endpoint without requiring the Java process, and may separately consume Java Model Boundary v1 for the Task 074 path.

Optional composition does not merge their security perimeters or make every interoperability payload valid model input.

## Current authority boundaries

- Healthcare systems and configured FHIR endpoints remain sources of clinical facts.
- Applications authorize and bound data acquisition.
- `POST_CONSULTATION_RESULT_REVIEW_V1` and `MISSED_FOLLOW_UP_REVIEW_V1` own deterministic follow-up evaluation. Neither infers clinical meaning.
- Gemini does not control protocol, clinical assessment, human review or action.
- Durable review workflow state is operational authority separate from protocol projection and clinical facts.
- `CLINICAL_REVIEW_CONTEXT_V1` reads current FHIR for an open review case and does not change protocol or review authority.
- The human review demo is presentation only. It does not authenticate a person, and the browser does not receive `X-Service-Token`. Generate AI assistance is a separate signed POST. It is not a login and it does not close the case.
- `INSTITUTIONAL_KNOWLEDGE_RETRIEVAL_V1` retrieves repository-controlled synthetic procedures. It does not change protocol output, FHIR reads or review cases. Gemini embeddings support that retrieval.
- `AI_ASSISTED_REVIEW_V1` may call Gemini once for an explanation after explicit generation. Observation values and patient identity stay out of that model input. Retrieval with no relevant guidance, or an unavailable index, does not call Gemini. The explanation is not stored.
- `CONTROLLED_ACTION_V1` records one internal coordination request from the durable review case. It does not call Gemini, retrieval, or FHIR, and it does not authenticate a reviewer.
- FHIR-derived data may reach Gemini only through explicitly authorized contracts. Institutional retrieval does not embed FHIR or patient data.
- No current Clinical Follow-up Review path writes FHIR or executes an autonomous external action.

## Current limitations and non-goals

The repository does not establish:

- production IAM, RBAC or multi-tenancy;
- a production secret-management or network-isolation architecture;
- human assignment, claiming, verified reviewer identity or a multi-user case-management system;
- clinical assessment, diagnosis, severity, urgency or treatment decisions;
- autonomous messaging, prescribing or FHIR writes from Healthcare AI;
- production processing approval for real patient data;
- production SaaS, customer-hosted or hybrid packaging;
- regulatory compliance, certification, SIHCE accreditation or RENHICE authorization;
- production RAG, MCP, a second LLM provider or a model router. The synthetic institutional index and the on-demand explanation are separate non-production demo capabilities.

Potential future technologies in historical tasks or roadmap notes are not implemented merely because they are named.

## Repository independence

This repository is independent. It is not CareFlow and must not import or reuse CareFlow application code.

## Engineering rule

Each implementation increment must define objective, architecture impact, security and data-integrity boundaries, tests and acceptance criteria. Material changes to FHIR access, model input, decision authority, writes, identity or deployment require an explicit decision and contract update.

Historical task and result documents are preserved as evidence; they are not current architecture authority unless a current index says so.

## Related documents

- [Current architecture](architecture/README.md)
- [Current roadmap](roadmap.md)
- [AI governance](ai-governance/README.md)
- [Healthcare Interoperability documentation](fhir/README.md)
- [Healthcare AI runbook](../services/ai-service/README.md)
