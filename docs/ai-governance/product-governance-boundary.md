# Product & Governance Boundary

**Healthcare AI & Interoperability Platform**

**Snapshot date:** 20 September 2026

**Document type:** product / engineering governance boundary

**Related documents:**

- `docs/ai-governance/regulatory-context.md`
- `docs/ai-governance/laboratory-state.md`
- `docs/ai-governance/llm-boundary-threats-and-controls.md`
- `docs/adr/ADR-076-controlled-gemini-integration.md`
- `docs/fhir/model-boundary-contract-v1.md`

---

## 1. Purpose

This document defines the current product and governance boundary for the **Healthcare AI & Interoperability Platform**.

Its purpose is to establish:

- what the product is;
- what capabilities currently exist;
- what data paths currently exist;
- what the current AI boundary is;
- what capabilities are explicitly outside the current scope;
- how future commercial scenarios should be evaluated before becoming part of the product;
- and which transitions require a new product, technical, governance, or regulatory assessment.

This document is a product and engineering governance artifact.

It does not constitute:

- legal advice;
- legal opinion;
- regulatory certification;
- compliance certification;
- healthcare certification;
- SIHCE accreditation;
- RENHICE authorization;
- clinical validation.

A technical capability described here must not be interpreted as legal authorization or regulatory compliance.

---

## 2. Product identity

The product is:

**Healthcare AI & Interoperability Platform**

It is **one product** with **two technical surfaces**:

1. **Java interoperability surface**
2. **Python AI surface**

These surfaces are intentionally separated in the current architecture. They are not two commercial products.

The product is intended to evolve toward controlled integration between healthcare information systems, interoperability standards, and AI capabilities.

The current implementation is a **development baseline**. It is not a production healthcare platform.

Historical wording in `laboratory-state.md` records the post-077 technical baseline. It does not override this product identity.

---

## 3. Product objective

The long-term product objective is to provide a controlled technical platform through which healthcare organizations can integrate:

- healthcare information systems;
- FHIR-based interoperability;
- controlled clinical-data projections;
- AI capabilities;
- governance controls;
- and, where appropriate, human oversight.

The product should not assume that every AI capability requires access to clinical data.

The current architecture therefore treats:

**interoperability data access**

and

**AI model invocation**

as separate capabilities.

A future product decision may connect them only after an explicit new assessment.

---

## 4. Current product state

### 4.1 Java interoperability surface

Current role (verified in `services/fhir-integration-service`):

- Java 21 / Spring Boot (`pom.xml` `java.version` 21; `application.yml` port **8081**);
- FHIR R4 client (HAPI; the application is not a FHIR server);
- SMART Authorization Code + PKCE (`SmartAuthorizationCoordinator`, `AuthorizationCodeClient`);
- Epic sandbox integration;
- Oracle sandbox integration;
- HAPI FHIR interaction in the local development/sandbox environment, where applicable;
- clinical snapshot;
- Task 042 allowlist (`ClinicalProjectionMapper`);
- RetentionCeiling N=5 (`RetentionCeiling.DEFAULT_LIMIT`);
- Model Boundary Contract v1 (`ModelBoundaryContract`, `ModelBoundaryMapper`);
- service authentication on `GET /api/model-boundary/v1` (`X-Service-Token`, `ModelBoundaryServiceAuthFilter`).

The Java surface is currently the FHIR boundary.

Python does not directly query Epic, Oracle, or HAPI FHIR.

### 4.2 Python AI surface

Current role (verified in `services/ai-service`):

- FastAPI service (port **8090**);
- consumer of Model Boundary v1 without model invocation (`app/consumer.py`, `GET /internal/agent-context`, `modelCalled=false`);
- controlled experimental Gemini endpoint (`app/experimental_service.py`, `POST /internal/experimental-summary`);
- `LLMProvider` / `GeminiProvider` / `FakeLLMProvider`;
- synthetic fixture `SYN-076-001` (`app/experimental_fixture.py`);
- feature gate `LLM_EXPERIMENTAL_ENABLED` default `false`;
- default model `gemini-flash-latest` (Task 077; override via `GEMINI_MODEL`; no fallback);
- timeout 30 s (`PROVIDER_TIMEOUT_SECONDS`);
- summary limit `MAX_SUMMARY_CHARS` = 2000;
- `requiresHumanReview=true` (application-owned);
- `modelCalled` true only after provider invocation starts;
- minimized application audit logging (`emit_audit`).

The Python AI surface does not currently receive FHIR-derived context as model input.

---

## 5. Current data-flow boundary

### 5.1 Interoperability path

```text
EHR / FHIR sandbox
(Epic / Oracle / local HAPI FHIR)
        |
        v
Java FHIR client
        |
        v
Clinical snapshot
        |
        v
Task 042 allowlist
        |
        v
RetentionCeiling N=5
        |
        v
Model Boundary Contract v1
        |
        v
GET /api/model-boundary/v1
        |
        v
Python consumer
GET /internal/agent-context
        |
        v
modelCalled=false
```

This path does not currently invoke Gemini.

### 5.2 Experimental AI path

```text
SYN-076-001
(synthetic fixture)
        |
        v
POST /internal/experimental-summary
        |
        v
LLMProvider
        |
        v
GeminiProvider
        |
        v
Google Gemini API
```

This path does not currently read Model Boundary v1, FHIR resources, Epic data, Oracle data, or HAPI FHIR data.

### 5.3 Explicit separation

```text
FHIR / EHR
     |
     v
Java interoperability boundary
     |
     v
Model Boundary v1
     |
     X
     |
     X-----> Gemini


Synthetic fixture
     |
     v
Experimental AI endpoint
     |
     v
Gemini
```

The absence of a FHIR-to-Gemini path is a **current governance boundary**, not merely an accidental implementation detail.

---

## 6. Current AI boundary

The only current model invocation path is the experimental Gemini integration.

Its current input is restricted to the canonical synthetic fixture `SYN-076-001`.

The current experimental prompt (`app/llm_provider.py` `build_experimental_prompt`) instructs: informational summary only; do not diagnose; do not recommend treatment or medication; do not make clinical decisions.

These application-level restrictions are **technical controls**. They do not constitute a legal classification of the system or its future use.

The current AI path therefore represents **controlled AI experimentation with synthetic input**, not clinical AI using production patient data.

---

## 7. Current capabilities

These describe the current repository. They do not imply production readiness or regulatory authorization.

| Capability | Current status | Evidence |
|---|---|---|
| FHIR R4 client | Implemented | Java HAPI client |
| SMART Authorization Code + PKCE | Implemented for sandbox integrations | `SmartAuthorizationCoordinator` |
| Epic sandbox interaction | Implemented | Epic vendor packages |
| Oracle sandbox interaction | Implemented | Oracle vendor packages |
| Clinical projection | Implemented | `ClinicalProjectionAssembler` / mapper |
| Task 042 allowlist | Implemented | `ClinicalProjectionMapper`; Task 042 spec |
| RetentionCeiling N=5 | Implemented | `RetentionCeiling.DEFAULT_LIMIT` |
| Model Boundary v1 | Implemented | `ModelBoundaryContract` |
| X-Service-Token on v1 | Implemented | `ModelBoundaryServiceAuthFilter` |
| Python Model Boundary consumer | Implemented | `GET /internal/agent-context` |
| Experimental Gemini provider | Implemented | `GeminiProvider` |
| Synthetic fixture restriction | Implemented | `SYN-076-001` exact equality |
| LLM feature gate | Implemented | default `false` |
| 30-second provider timeout | Implemented | `PROVIDER_TIMEOUT_SECONDS` |
| Summary output limit | Implemented | `MAX_SUMMARY_CHARS` = 2000 |
| `requiresHumanReview=true` | Implemented as application control | Java `AiBoundaryDecision`; Python validators |
| `modelCalled` semantics | Implemented | 074 always false; 076 true only after invoke starts |
| Minimized experimental logs | Implemented | `emit_audit` |
| Threat model T1–T9 | Documented | `llm-boundary-threats-and-controls.md` |

---

## 8. Capabilities explicitly not established

The following are **not** current product capabilities and must not be represented externally as if they were:

- production EHR integration;
- production patient-data processing;
- production clinical AI;
- clinical decision support;
- autonomous clinical decision making;
- SIHCE accreditation;
- RENHICE participation;
- FHIR Perú profile accreditation;
- operational human-in-the-loop workflow;
- enterprise IAM;
- enterprise RBAC;
- production tenancy;
- production DLP;
- production SIEM;
- production clinical audit infrastructure;
- legal retention/erasure workflow;
- production provider contractual assessment;
- FHIR-derived context sent to Gemini.

---

## 9. Data classification boundary

The product currently distinguishes three materially different data situations.

**synthetic ≠ sandbox ≠ real patient data**

**sandbox SMART success ≠ authorization for production clinical-data reuse**

### 9.1 Synthetic data

Example: `SYN-076-001`.

Generated for controlled experimentation. Canonical experimental fixture. Current Gemini input. This is the current AI experimentation boundary.

### 9.2 Sandbox EHR data

Examples: Epic sandbox; Oracle sandbox.

Accessed through the Java interoperability surface. Used to validate SMART/FHIR integration. Subject to the current projection and allowlist controls.

Sandbox data must not automatically be treated as equivalent to production patient data.

### 9.3 Real patient data

Not currently established as a production product capability.

Introducing real patient data would be a **material product evolution** requiring a new assessment of: data inventory; purpose; roles; security; retention; access; deployment model; provider relationships; regulatory applicability; operational governance.

---

## 10. AI data boundary

Current AI boundary:

```text
Synthetic data
      |
      v
AI experimentation
```

Explicitly **not** part of the current baseline:

```text
FHIR
  |
  v
Model Boundary v1
  |
  v
Gemini
```

Any future decision to introduce such a path must be treated as a **material product change**. It must not be enabled merely by modifying an endpoint or changing the prompt.

That decision would require a new evaluation of: data minimization; purpose; authorization; privacy; security; provider processing; model risk; human oversight; deployment model; operational controls; and applicable regulatory requirements (see `regulatory-context.md` — applicability questions, not a compliance result).

---

## 11. Product deployment models

The long-term product **may** support three models. They are **future product considerations**. None is implemented as a production estate.

### 11.1 SaaS

The product provider operates the platform. Potential future characteristics: provider-managed infrastructure; customer data processed by the service; multi-tenant or isolated customer environments; external AI provider integration where applicable.

None of these production characteristics are currently implemented.

### 11.2 Customer-hosted

The healthcare organization operates the software in infrastructure under its control. Potential future characteristics: customer-managed infrastructure, credentials, and network; possibly a customer-controlled AI provider account.

Customer-hosted deployment does **not** automatically eliminate regulatory or contractual responsibilities.

### 11.3 Hybrid

Some components operate in the customer environment and others are externally managed.

The defining governance question is: **what data crosses each trust boundary?**

```text
Customer environment
        |
        | data crossing
        v
Product provider
        |
        | data crossing
        v
External AI provider
```

The current repository does not implement a production hybrid deployment.

---

## 12. Use-case boundary

Progressively more sensitive use cases. These are **not** Tasks.

| Level | Name | Meaning |
|---|---|---|
| **U0** | Interoperability | Retrieve FHIR resources; normalize; project controlled fields; exchange between systems. No AI model invocation is inherently required. |
| **U1** | Healthcare data processing | Transformation; controlled projection; validation; synchronization; operational workflows. Healthcare data does not automatically mean an AI system is involved. |
| **U2** | AI assistance | Summarization; administrative or document assistance; non-clinical workflow support. Actual data and purpose determine applicable governance. |
| **U3** | Clinical-context AI | AI receives information derived from clinical records or other patient-specific healthcare information. Material increase in sensitivity. The current synthetic Gemini path must not simply be replaced with FHIR-derived context. **Not implemented.** |
| **U4** | Clinical decision support | Output may influence diagnosis, treatment, medication, prognosis, prioritization, screening, access to healthcare, or other clinically consequential decisions. Different product category. Requires a new formal assessment before implementation or commercialization. **Not implemented.** |

---

## 13. Governance gates

| Gate | State | Status |
|---|---|---|
| **G0** — Synthetic AI experimentation | Synthetic fixture; controlled model endpoint; feature gate; output controls; minimized logs; experimental status | **AVAILABLE** (development) |
| **G1** — Sandbox interoperability | FHIR client; SMART + PKCE; sandbox credentials; projection; v1; explicit separation from the model path | **AVAILABLE IN DEVELOPMENT / SANDBOX** |
| **G2** — Real clinical data | Future. Requires data categories, purpose, roles, access, security, retention, audit, deployment, providers, regulatory applicability, operations | **NOT ENTERED** |
| **G3** — AI with clinical context | Future. Model receives information derived from real clinical context. Requires use case, input, minimization, purpose, provider processing/retention/logging, security, model governance, human oversight, output handling, risk classification | **NOT ENTERED** |
| **G4** — Clinical decision support | Future. Outputs that may materially influence clinical decisions or healthcare access. New product, technical, governance, and regulatory assessment | **NOT ENTERED** |

G0 and G1 describe the current development baseline. G2–G4 are future.

---

## 14. Gate transition principle

A gate must not be crossed simply because the underlying technical capability exists.

```text
FHIR client works
        X
        ↓
therefore send FHIR to Gemini
```

```text
Gemini summary works with synthetic data
        X
        ↓
therefore use it with patient records
```

These are **not** acceptable governance transitions.

A transition must be evaluated as a **product change**.

---

## 15. Current commercial boundary

The current product can be positioned as a developing **Healthcare AI & Interoperability Platform** with demonstrated technical capabilities in:

- FHIR interoperability;
- SMART sandbox integration;
- controlled clinical-data projection;
- model-boundary design;
- AI provider integration using synthetic data;
- AI governance controls.

The product must **not** currently be represented as:

- a certified SIHCE;
- a RENHICE participant;
- a clinically validated AI system;
- a clinical decision-support system;
- a production patient-data AI platform;
- a regulatory-compliant platform under any framework solely because these technical controls exist.

Commercial positioning must reflect the actual implementation state.

---

## 16. Future commercial evolution

```text
Healthcare interoperability
        |
        +----> Healthcare data services
        |
        +----> AI-assisted workflows
        |
        +----> Clinical-context AI
        |
        +----> Clinical decision support
```

Each branch is a **separate** product-evolution decision.

The current baseline does **not** commit the product to any specific future branch.

The purpose of this document is to prevent accidental capability expansion without an explicit decision.

---

## 17. Reusable technical boundaries

Architectural concepts that may remain reusable as the product evolves:

- explicit interoperability boundary;
- controlled data projection;
- model boundary;
- provider abstraction;
- feature gating;
- model invocation semantics;
- output constraints;
- human-review flag;
- correlation identifiers;
- minimized application audit events;
- threat-model documentation.

Reusability does **not** imply that the same controls are sufficient for every future deployment or clinical use.

Each material change must be evaluated against the new context.

These concepts are **not** a general-purpose agent framework.

---

## 18. Explicitly out of scope for this phase

This document does not authorize or initiate implementation of:

- RAG;
- agents;
- MCP;
- LangGraph;
- memory;
- OpenAI;
- a second model provider;
- fallback;
- router;
- frontend;
- enterprise IAM;
- RBAC;
- tenancy;
- operational HITL;
- WAF;
- SIEM;
- DLP;
- FHIR server;
- FHIR → Gemini;
- additional clinical resources;
- MedicationRequest integration into Epic;
- production EHR credentials;
- production patient data;
- clinical decision support.

These may be considered in future product phases only after explicit product and governance decisions.

---

## 19. Relationship with regulatory-context.md

`regulatory-context.md` answers: **which regulatory and applicability questions are relevant?**

This document answers: **what product boundary are we applying those questions to?**

```text
regulatory-context.md
        |
        v
Regulatory applicability
        |
        v
product-governance-boundary.md
        |
        v
Product scope / gates
        |
        v
Future architecture decisions
        |
        v
Implementation
```

Neither document is a substitute for legal advice or formal regulatory assessment.

This phase does not reopen the Phase A legal inventory.

---

## 20. Relationship with the technical governance baseline

The current technical governance baseline remains documented in:

- `laboratory-state.md` — historical development baseline after Tasks 076/077;
- `llm-boundary-threats-and-controls.md` — threat model T1–T9;
- `ADR-076-controlled-gemini-integration.md`;
- `docs/fhir/model-boundary-contract-v1.md`.

Those documents describe technical history, controls, decisions, and threat considerations.

This document adds the **product-level** boundary.

Historical terminology in `laboratory-state.md` should not override the current product identity: **Healthcare AI & Interoperability Platform**.

---

## 21. Change-control principle

Any of the following should trigger a new product/governance review:

- production patient data;
- FHIR-derived data sent to an AI model;
- new clinical AI use case;
- clinical decision support;
- new external AI provider;
- material provider change;
- new deployment model;
- SIHCE positioning;
- RENHICE integration;
- material expansion of the clinical projection;
- new jurisdiction;
- customer-hosted production deployment;
- hybrid deployment involving clinical data.

The existence of a technical implementation does not by itself authorize the change.

---

## 22. Current boundary summary

As of 20 September 2026:

```text
                    HEALTHCARE AI &
                INTEROPERABILITY PLATFORM
                           |
             +-------------+-------------+
             |                           |
             v                           v
       INTEROPERABILITY              AI SURFACE
             |                           |
        FHIR / SMART                Gemini
             |                           |
        Epic/Oracle                  Synthetic
         sandboxes                  fixture only
             |                           |
       Controlled                    Experimental
       projection                     summary
             |                           |
             +------------X--------------+
                          |
                 No FHIR → Gemini
```

Current boundary: FHIR/interoperability and experimental AI remain separate.

The product may evolve beyond this boundary, but every material expansion requires an explicit product and governance decision.

---

## 23. Final principle

The platform should evolve by **explicit contracts and gates** rather than by accidental capability expansion.

In particular:

- A technical path that is possible is not automatically a product capability.
- A product capability is not automatically a legal authorization.

The current governance baseline therefore favors explicit separation between:

- interoperability;
- healthcare data processing;
- AI experimentation;
- clinical-context AI;
- and clinical decision support.

This boundary remains valid until a future product decision explicitly changes it and the corresponding technical, governance, and regulatory assessments are completed.
