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
- an authorized legacy/narrative LangGraph/Gemini subflow.

Healthcare AI does not have arbitrary FHIR access. Current follow-up reads are case-bound, GET-only, resource-constrained, bounded, completeness-aware and fail-closed. See [ADR-085](adr/ADR-085-python-follow-up-fhir-and-model-authority-boundary.md) and the [V1 contract](contracts/post-consultation-result-review-v1.md).

## Composition

Healthcare Interoperability and Healthcare AI are not structurally dependent product processes. Java works without Python. Healthcare AI may use a configured authorized FHIR endpoint without requiring the Java process, and may separately consume Java Model Boundary v1 for the Task 074 path.

Optional composition does not merge their security perimeters or make every interoperability payload valid model input.

## Current authority boundaries

- Healthcare systems and configured FHIR endpoints remain sources of clinical facts.
- Applications authorize and bound data acquisition.
- `POST_CONSULTATION_RESULT_REVIEW_V1` owns deterministic follow-up evaluation.
- Gemini does not control protocol, clinical assessment, human review or action.
- FHIR-derived data may reach Gemini only through explicitly authorized contracts.
- No current Clinical Follow-up Review path writes FHIR or executes an autonomous external action.

## Current limitations and non-goals

The repository does not establish:

- production IAM, RBAC or multi-tenancy;
- a production secret-management or network-isolation architecture;
- a durable human-review queue or case-management workflow;
- clinical assessment, diagnosis, severity, urgency or treatment decisions;
- autonomous messaging, prescribing or FHIR writes from Healthcare AI;
- production processing approval for real patient data;
- production SaaS, customer-hosted or hybrid packaging;
- regulatory compliance, certification, SIHCE accreditation or RENHICE authorization;
- RAG, MCP, a second LLM provider or a model router as current product capabilities.

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
