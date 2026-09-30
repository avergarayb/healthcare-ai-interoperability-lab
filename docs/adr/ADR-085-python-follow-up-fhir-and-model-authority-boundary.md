# ADR-085 — Python Follow-up FHIR and Model Authority Boundary

## Status

Accepted

## Date

2026-09-29

## Context

The Healthcare AI & Interoperability Platform contains two independently deployable product units:

- **Healthcare Interoperability** — Java / Spring Boot;
- **Healthcare AI** — Python / FastAPI / LangGraph.

ADR-078 established Java as the exclusive FHIR boundary and prohibited Python from adding a HAPI, Epic, Oracle, or other FHIR client. ADR-084 established the independent product-unit direction but still described direct FHIR acquisition by Python as unimplemented and unauthorized.

The accepted Clinical Follow-up Review implementation now requires Healthcare AI to acquire a narrowly defined FHIR snapshot directly from an authorized endpoint. The implementation is already bounded by application-owned acquisition, case isolation, collection-completeness tracking, strict resource/reference validation, read limits, and fail-closed behavior. The deterministic protocol is evaluated before the LangGraph narrative subflow.

The prior absolute prohibition is therefore incompatible with the accepted architecture. Reconciliation must preserve the useful separation between interoperability responsibilities and AI/model authority without describing the implemented FHIR reads as arbitrary access.

## Decision

Healthcare AI may perform direct FHIR reads for an explicitly authorized product capability when the read contract is documented, bounded, case-scoped, and fail-closed.

For **Clinical Follow-up Review V1**, the authorized FHIR resource types are:

- `Patient`;
- `Encounter`;
- `Observation`;
- `Appointment`.

The reads are:

- application-owned;
- bound to the authorized `caseId` and resolved Patient;
- HTTP GET-only;
- limited to the resource types and search shapes defined by the V1 contract;
- bounded by page and unique-resource limits;
- completeness-aware;
- validated before use;
- fail-closed on transport, structural, identity, reference, pagination, or security failure.

This decision does not authorize arbitrary FHIR access, user- or model-supplied FHIR queries, unrestricted resource retrieval, FHIR writes, or direct access to every configured EHR destination.

## Acquisition and protocol authority

Mandatory acquisition for `POST_CONSULTATION_RESULT_REVIEW_V1` occurs before LangGraph. The application, not Gemini, chooses and executes the mandatory Patient, Encounter, Observation, and Appointment reads.

The protocol is deterministic and application-owned. Gemini is not authoritative for:

- protocol evaluation;
- `clinicalAssessment`;
- `humanReview`;
- `action`.

The separately authorized LangGraph/Gemini narrative subflow may continue to use its two existing read tools. FHIR-derived data may reach Gemini only through explicitly authorized tool or data contracts. The existence of a configured FHIR endpoint does not permit arbitrary clinical context to be sent to a model.

Legacy model output (`answer` and `followUpRequired`) remains independent from deterministic product authority.

## Security consequences

Every authorized FHIR capability must preserve these properties:

1. A workflow for case X must never issue a continuation request that changes the application-authorized semantic search to case Y. Any returned clinical resource that does not belong to the authorized case or Patient must fail validation and must not be accepted or exposed by the workflow; this returned-resource validation is defense in depth against an incorrect upstream response.
2. Patient identity must be resolved through the capability's case contract before resource paths are built.
3. FHIR IDs and canonical relative references must be validated before use.
4. Empty, incomplete, malformed, unavailable, and unauthorized results must remain distinguishable.
5. Pagination state is traversal state, not authorization.
6. Continuation URLs must remain within the configured origin and an explicit path/query contract. An ordinary same-resource continuation must preserve every application-controlled semantic search parameter exactly once and unchanged; only the recognized `page` and `token` paging fields may be added or changed. A HAPI base-endpoint continuation follows its separate constrained `_getpages` contract.
7. Redirects and unsafe path traversal are rejected.
8. Secrets, clinical payloads, and opaque paging tokens must not be logged as ordinary audit fields.

The authoritative V1 rules are in [`../contracts/post-consultation-result-review-v1.md`](../contracts/post-consultation-result-review-v1.md).

## Operational consequences

- Healthcare AI requires an authorized FHIR endpoint for this capability, configured independently from the Java Model Boundary v1 producer.
- A complete search may establish absence; a partial search may not.
- Ordinary same-resource pagination is accepted only on the exact resource endpoint, with the initial application-controlled search semantics unchanged and only the currently recognized `page`/`token` paging state added or changed.
- HAPI-specific base-endpoint continuation is supported only through the constrained V1 adapter behavior.
- `humanReview.status=required` is currently a response-level protocol projection, not a durable queue or assignment.
- `action.status=proposed` does not execute an external action.
- No FHIR resource is created, updated, patched, or deleted.

## Relationship to Healthcare Interoperability

Healthcare Interoperability remains the product unit for broader healthcare-system connectivity, SMART authorization, vendor integrations, transformations, routing, and interoperability contracts. This ADR does not move those general responsibilities into Healthcare AI.

Healthcare AI remains independently deployable. Clinical Follow-up Review must not require the Healthcare Interoperability process merely to obtain its FHIR context when an authorized FHIR endpoint is configured. The two product units may still be composed where a deployment requires both.

This ADR does not decide final pricing, packaging, commercial SKUs, or a production deployment topology.

## Supersession

This ADR supersedes only these portions of **ADR-078**:

- the absolute rule that only Java may initiate HAPI/FHIR traffic;
- the absolute prohibition on a Python HAPI/FHIR client;
- the absolute statement that no FHIR-derived payload may reach Gemini, replacing it with the explicit-contract rule above;
- the future-reconsideration condition that treated all Python FHIR ingress as unapproved.

ADR-078 remains valid for separation of the Task 074 and Task 076 paths, the fact that Model Boundary v1 is not automatically model input, the prohibition on accidental FHIR-to-model coupling, and the requirement for explicit governance before expanding model data access.

This ADR supersedes only these portions of **ADR-084**:

- the current-state statement that Python is not a FHIR client;
- the statement that Python-direct-FHIR is unimplemented or unauthorized;
- the integration-contract entry that deferred every Python FHIR ingress decision to the future.

ADR-084 remains valid for the umbrella platform, the two independently deployable product units, optional composition, Java independence, Python independence, and the absence of a decided final commercial packaging model.

ADR-076 remains the accepted historical decision for the separate synthetic experimental-summary endpoint.

## Non-goals

This decision does not introduce:

- FHIR writes;
- direct Epic or Oracle follow-up integration;
- unrestricted FHIR search;
- model-selected mandatory acquisition;
- clinical interpretation, diagnosis, severity, urgency, treatment, or prescribing;
- production IAM, RBAC, tenancy, or network isolation;
- a durable human-review workflow;
- a provider-neutral pagination contract;
- a regulatory or compliance conclusion.

## Related decisions and contracts

- [`ADR-078`](ADR-078-fhir-and-ai-boundary.md) — previous FHIR and AI boundary
- [`ADR-084`](ADR-084-product-identity-and-architectural-units.md) — product identity and architectural units
- [`POST_CONSULTATION_RESULT_REVIEW_V1`](../contracts/post-consultation-result-review-v1.md) — authoritative internal contract
