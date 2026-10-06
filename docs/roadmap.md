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

### Healthcare AI

- Python / FastAPI service.
- Authenticated Model Boundary v1 consumer without model invocation.
- Separate disabled-by-default synthetic Gemini endpoint.
- LangGraph narrative agent subflow with explicit tool policy.
- Clinical Follow-up Review endpoint.
- Mandatory application-owned Patient, Encounter, Observation and Appointment acquisition.
- Bounded, completeness-aware HAPI pagination and case isolation.
- Deterministic `POST_CONSULTATION_RESULT_REVIEW_V1` outside model authority.
- Response-level human-review requirement and proposed review action when the protocol matches.
- Durable SQLite-backed operational review cases with queue, provenance, bounded closure outcomes and transition history.
- Open-case `CLINICAL_REVIEW_CONTEXT_V1` current FHIR projection without protocol reevaluation or persistence.
- Server-rendered synthetic review queue, case page and operational close inside Healthcare AI.
- Deterministic, evaluation-harness and opt-in real-HAPI coverage.

## Current product gaps

The following capabilities are not established by the current repository:

- human-review assignment, claiming and verified reviewer identity;
- clinical assessment or clinical decision support;
- general workflow checkpointing beyond the operational review-case store;
- a multi-user product frontend and human authentication; the synthetic review demo is not that frontend;
- enterprise IAM/RBAC and multi-tenancy;
- durable audit storage and production operations;
- production secret management and enforced network architecture;
- autonomous actions or FHIR writes from Healthcare AI;
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
- retrieval, local models, MCP or additional providers;
- customer-facing applications and integrations.

Each candidate requires a separate product decision, security assessment and acceptance contract. Historical phase names under `docs/tasks/` remain development history rather than current sequencing authority.

## Current position

The repository has an implemented interoperability foundation and an implemented Healthcare AI workflow foundation. It is beyond the former “Phase 2–3” and “future AI/LangGraph” descriptions.

It remains a development baseline: local HAPI and vendor sandboxes are not production healthcare deployment, the SQLite review store is single-instance, and deterministic follow-up review is not clinical diagnosis.
