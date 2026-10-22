# Product & Governance Boundary

**Healthcare AI & Interoperability Platform**

**Snapshot date:** 29 September 2026
**Document type:** product / engineering governance boundary

This document is not legal advice, regulatory or compliance certification, clinical validation, SIHCE accreditation or RENHICE authorization. Technical controls do not by themselves establish legal authorization or production readiness.

## 1. Purpose

This document defines the current product units, implemented data paths, model authority, human-review meaning and change-control boundary.

The authoritative Clinical Follow-up Review rules are in [`../contracts/post-consultation-result-review-v1.md`](../contracts/post-consultation-result-review-v1.md). Architecture decisions are indexed in [`../architecture/README.md`](../architecture/README.md).

## 2. Product identity

The umbrella product direction is **Healthcare AI & Interoperability Platform**. It contains two product/deployment units:

1. **Healthcare Interoperability** — Java / Spring Boot.
2. **Healthcare AI** — Python / FastAPI / LangGraph.

They are independently deployable and may be composed or eventually commercialized together or independently. Pricing, packaging and final commercial SKUs have not been decided.

“Product A” and “Product B” are optional architectural shorthand, not settled commercial names.

## 3. Current product state

### 3.1 Healthcare Interoperability

Implemented development capabilities include:

- Java 21 / Spring Boot;
- FHIR R4 client behavior;
- local HAPI FHIR connectivity;
- SMART Authorization Code + PKCE foundations;
- Epic and Oracle sandbox profiles;
- bounded routing, resilience, audit and observability;
- controlled snapshots, allowlists and projections;
- Model Boundary Contract v1 and service-token protection.

This unit is not a product FHIR server, customer EHR, SIHCE or RENHICE participant.

### 3.2 Healthcare AI

Implemented development capabilities include:

- FastAPI internal endpoints on the Python service;
- authenticated Model Boundary v1 consumption without model invocation;
- a separate gated Gemini summary restricted to fixture `SYN-076-001`;
- Clinical Follow-up Review through `POST /internal/agent/follow-up`;
- application-owned, case-bound, GET-only FHIR acquisition for Patient, Encounter, Observation and Appointment;
- bounded and completeness-aware search traversal;
- deterministic `POST_CONSULTATION_RESULT_REVIEW_V1` evaluation before LangGraph;
- a separately authorized LangGraph/Gemini narrative subflow;
- response-level human-review and proposed-action projection.

Direct FHIR acquisition is an intentional stable capability for explicitly authorized contracts. It is not permission for arbitrary FHIR access.

## 4. Current data flows

### 4.1 Model Boundary v1 consumer

```text
FHIR destination
        -> Healthcare Interoperability
        -> controlled projection / Model Boundary v1
        -> GET /internal/agent-context
        -> modelCalled=false
```

This path does not call Gemini and does not automatically authorize v1 as model input.

### 4.2 Synthetic experimental summary

```text
SYN-076-001
        -> POST /internal/experimental-summary
        -> GeminiProvider
        -> Google Gemini API
```

This historical experiment remains disabled by default and separate from Clinical Follow-up Review.

### 4.3 Clinical Follow-up Review

```text
POST /internal/agent/follow-up
        -> service authentication and feature gate
        -> authorized case scope
        -> configured authorized FHIR endpoint
        -> mandatory Patient / Encounter / Observation / Appointment reads
        -> deterministic POST_CONSULTATION_RESULT_REVIEW_V1
        -> authorized narrative LangGraph/Gemini subflow when allowed
        -> application-owned HTTP projection
```

FHIR-derived payloads may reach Gemini only through the explicitly authorized narrative tool/data contracts. A FHIR endpoint, Patient match or paging token is not general authorization to expose other resources or context to the model.

## 5. Decision and model authority

The application owns:

- mandatory acquisition;
- case scope and resource validation;
- collection completeness;
- protocol evaluation and reason codes;
- `clinicalAssessment`;
- `humanReview`;
- `action`.

Gemini may own legacy narrative output:

- `answer`;
- `followUpRequired`.

Legacy model output does not control or override deterministic product authority. `followUpRequired` is not the protocol decision.

The protocol does not interpret normality, diagnosis, severity, urgency or treatment. `clinicalAssessment.status` remains `not_performed`.

## 6. Human review and actions

For a protocol match:

- `humanReview.status=required` means the case should be presented for human review;
- `action.status=proposed` with `type=review_follow_up_case` is a proposal.

Neither field proves a durable queue, assignment, acknowledgement, disposition or external execution. The current capability performs no FHIR write, autonomous message, prescription or treatment action.

## 7. Data classification boundary

The repository distinguishes:

- **synthetic fixture data** — generated test/experimental data such as `SYN-076-001`;
- **local or sandbox FHIR data** — used to validate integration and workflow behavior;
- **real production patient data** — not established as an approved production processing capability.

Synthetic, sandbox and real patient data are not interchangeable governance categories. Technical ability to process FHIR-derived context does not authorize production use or external-model processing of real clinical data.

Before a deployment sends real clinical data to an external model, the responsible parties must resolve purpose, minimization, authorization, provider terms, logging/retention, security, human oversight, deployment model and regulatory applicability.

## 8. Current governance controls

| Control | Current status |
|---|---|
| Service-token authentication on internal product endpoints | Implemented development control; not enterprise IAM |
| Follow-up feature gate | Implemented; disabled by default |
| Authorized case binding | Implemented |
| Patient uniqueness and path-safe FHIR ids | Implemented |
| Resource/reference case isolation | Implemented |
| Bounded, completeness-aware collection reads | Implemented |
| HAPI continuation validation and redirects disabled | Implemented |
| Mandatory acquisition before LangGraph | Implemented |
| Deterministic protocol outside model authority | Implemented |
| Model tool allowlist and policy audit | Implemented |
| No FHIR writes from Clinical Follow-up Review | Implemented |
| Operational human-review workflow | Not implemented |
| Enterprise IAM/RBAC, tenancy and durable audit | Not implemented |
| Production network and secret-management architecture | Not implemented |
| Production real-data external-model approval | Not established |

Application logging restrictions do not establish provider-side retention, training, location or contractual behavior.

## 9. Use-case and risk boundary

| Level | Meaning | Current position |
|---|---|---|
| Interoperability | Retrieve, validate, transform and exchange healthcare data without requiring a model. | Implemented development capabilities in Healthcare Interoperability. |
| Deterministic healthcare workflow | Application-owned rules over authorized healthcare facts, without clinical interpretation. | Clinical Follow-up Review V1 implemented. |
| Narrative AI assistance | Model-generated text or legacy structured narrative output under explicit contracts. | Implemented in controlled development paths. |
| AI with real clinical context | External model receives real patient-specific clinical information. | Production authorization/governance not established. |
| Clinical decision support | Output may influence diagnosis, treatment, medication, prognosis, prioritization or access to care. | Not implemented or authorized. |

The existence of a deterministic follow-up rule or human-review projection must not be marketed as clinical decision support or operational human oversight.

## 10. Deployment boundary

Potential SaaS, customer-hosted and hybrid deployments remain future product choices. The current repository does not provide a production estate for any of them.

Healthcare Interoperability and Healthcare AI have separate runtime and security concerns. Local HAPI, its PostgreSQL database, `lab-oauth` and the local gateway are a support stack rather than mandatory product infrastructure.

Customer-hosted deployment would not automatically remove privacy, security, contractual or regulatory obligations. In every model, the material question is which data crosses each trust boundary.

## 11. Capabilities not established

Do not represent the repository as providing:

- production EHR or production patient-data processing;
- production clinical AI or clinical decision support;
- autonomous clinical decisions or actions;
- SIHCE accreditation, RENHICE participation or regulatory certification;
- enterprise IAM/RBAC, tenant isolation, DLP or SIEM;
- a durable human-review system;
- legal retention/erasure or data-subject-rights workflows;
- provider-side no-training/no-retention guarantees;
- arbitrary FHIR-to-Gemini access;
- a provider-neutral continuation contract;
- finalized commercial packaging.

## 12. Change-control gates

A new assessment and explicit contract/decision are required before:

- adding a FHIR resource type or materially broader query;
- sending a new category of FHIR-derived data to a model;
- using real production clinical data with an external model;
- adding writes, messages or external action execution;
- changing the protocol's clinical or temporal meaning;
- treating model output as deterministic authority;
- introducing a production deployment, tenant or identity model;
- positioning the product as clinical decision support.

Technical capability alone is not authorization to cross a governance gate.

## 13. Historical scope

`laboratory-state.md`, `llm-boundary-threats-and-controls.md`, ADR-076 through ADR-084 and `docs/tasks/` retain their original wording and dates. Current decisions supersede only the portions explicitly identified by later ADRs; history is not rewritten.

## 14. Related documents

- [`regulatory-context.md`](regulatory-context.md)
- [`../architecture/README.md`](../architecture/README.md)
- [`../adr/ADR-085-python-follow-up-fhir-and-model-authority-boundary.md`](../adr/ADR-085-python-follow-up-fhir-and-model-authority-boundary.md)
- [`../contracts/post-consultation-result-review-v1.md`](../contracts/post-consultation-result-review-v1.md)
- [`../../services/ai-service/README.md`](../../services/ai-service/README.md)
