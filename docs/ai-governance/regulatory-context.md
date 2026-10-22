# Regulatory Context & Product Applicability

**Healthcare AI & Interoperability Platform**

**Technical baseline updated:** 29 September 2026

**Legal/regulatory snapshot retained from:** 19 September 2026
**Document type:** engineering / product-governance analysis  
**Not:** legal advice, legal opinion, compliance certification, privacy certification, or healthcare certification

This document describes **applicability questions** and **technical evidence already present in the repository**. It does **not** declare that the product complies with any statute.

Classifications used below:

| Label | Meaning |
|---|---|
| Implemented technical control | Present in code and, where cited, in tests |
| Documented control | Recorded as a design limit; not an extra runtime capability |
| Partially addressed | A technical fragment exists; the organizational/legal system does not |
| Not implemented | Absent in the repository |
| Not applicable to current scope | Does not arise on the current implementation path |
| Future product consideration | Relevant if the commercial product is deployed as described |
| Open regulatory question | Requires official-source and/or legal/organizational determination |
| Requires legal/organizational determination | Role, purpose, or obligation cannot be inferred from code |

Historical development notes remain in [`laboratory-state.md`](laboratory-state.md) and [`llm-boundary-threats-and-controls.md`](llm-boundary-threats-and-controls.md). Those files record the post-077 baseline. They are not rewritten here.

---

## 1. Purpose and scope

State, for the evolving **Healthcare AI & Interoperability Platform** (also: **the product**):

- which Peruvian instruments are **relevant to consider** for a future commercial offering;
- which **technical controls already exist**;
- which topics remain **open** before production or before sending real clinical data to a model.

**In scope:** documentation of applicability for Healthcare Interoperability, Healthcare AI, the synthetic Gemini experiment, and the implemented Clinical Follow-up Review data flow.

**Out of scope:** changing legal interpretations; declaring compliance; inventing RAG, MCP, memory, OpenAI, a second provider, fallback/router, frontend, RBAC, IAM, tenancy, operational HITL, CDS, or production authorization for real-data model processing.

**Rule:** a technical control is not legal compliance.

---

## 2. Product context

The repository is the foundation of a commercial **Healthcare AI & Interoperability Platform** with two independently deployable product units:

| Product unit | Role today |
|---|---|
| Healthcare Interoperability (`fhir-integration-service`, Java, port **8081**) | SMART + FHIR R4 connectivity to Epic/Oracle sandboxes and local HAPI; snapshots, controlled projections and Model Boundary v1. |
| Healthcare AI (`ai-service`, Python, port **8090**) | Model Boundary v1 consumption without a model; separate synthetic Gemini experiment; Clinical Follow-up Review with bounded FHIR reads, deterministic protocol authority and a narrative LangGraph/Gemini subflow. |

The units may be deployed together or independently. Final commercial packaging is not decided. Target SaaS, customer-hosted and hybrid models remain unimplemented production considerations.

The current implementation is **under development**. There is no production tenant, accredited SIHCE, RENHICE participation, enterprise IAM, durable human-review workflow or approved production flow of real patient data to Gemini.

Clinical Follow-up Review can technically provide FHIR-derived payloads to Gemini through two explicitly authorized narrative tool contracts. That fact invalidates the earlier synthetic-only technical baseline but does not establish legal authorization, production readiness or permission for arbitrary FHIR/model data flow.

---

## 3. Current technical baseline

Technical baseline verified against the repository on 29 September 2026. Legal interpretations in later sections were not independently changed by this update.

### Healthcare Interoperability and Model Boundary v1

```text
EHR sandbox / local HAPI
        -> Java FHIR R4 client
        -> controlled snapshot and projection
        -> Model Boundary Contract v1
        -> GET /internal/agent-context (modelCalled=false)
```

This path does not call Gemini and does not make v1 automatic model input.

### Synthetic experimental AI

```text
SYN-076-001
        -> POST /internal/experimental-summary
        -> GeminiProvider
        -> Google Gemini API
```

This path remains synthetic, gated and separate.

### Clinical Follow-up Review

```text
POST /internal/agent/follow-up
        -> authenticated case scope
        -> configured authorized FHIR endpoint
        -> mandatory Patient / Encounter / Observation / Appointment reads
        -> deterministic POST_CONSULTATION_RESULT_REVIEW_V1
        -> authorized LangGraph/Gemini narrative subflow when allowed
        -> application-owned protocol / review / action projection
```

The FHIR reads are application-owned, case-bound, GET-only, resource-constrained, bounded, completeness-aware and fail-closed. Mandatory acquisition occurs before LangGraph. Gemini is not authoritative for protocol evaluation, clinical assessment, human review or action.

FHIR-derived payloads may reach Gemini only through the two explicitly authorized narrative tools. The current repository does not establish production approval for using real clinical data in this flow.

| Capability | Evidence |
|---|---|
| Java FHIR/SMART and sandbox connectivity | `services/fhir-integration-service`; `docs/fhir/` |
| Controlled Java projection and Model Boundary v1 | `ClinicalProjectionMapper`, `ModelBoundaryContract` |
| Authenticated Python v1 consumer without model invocation | `app/consumer.py`, `GET /internal/agent-context` |
| Synthetic Gemini experiment | `app/experimental_service.py`, `POST /internal/experimental-summary` |
| Bounded Python FHIR read client | `app/langgraph_fhir_hapi.py`, `app/langgraph_fhir_followup.py` |
| Mandatory pre-LangGraph acquisition | `PostConsultationContextReader`, `FollowUpWorkflow.run` |
| Deterministic protocol authority | `app/post_consultation_review.py` |
| Closed follow-up HTTP projection | `app/followup_models.py`, `app/followup_service.py` |
| Model tool policy and audit | `app/langgraph_gemini_fhir_followup.py` |
| Authoritative internal contract | `docs/contracts/post-consultation-result-review-v1.md` |

Tasks 057–073 remain deny-by-default Java simulations, not real IAM, consent or clinical authorization.

---

## 4. Deployment models

None of the three models is implemented as a production platform. They are **future product considerations**. Customer-hosted does **not** remove all regulatory questions.

### 4.1 SaaS

Provider-operated infrastructure. If the product later processes customer healthcare data, parties must determine **controller / processor / joint-controller** roles by contract and fact. That determination is **not** in this repository.

Future considerations (not implemented): tenancy, enterprise IAM, production secret management, provider-side access to customer data, incident process, DPA with the product provider **and** with Google (if Gemini remains).

### 4.2 Customer-hosted

Software runs where the healthcare organization controls infrastructure. The organization may be closer to **controller** of clinical data; the product vendor may still process data (support, updates, telemetry) or introduce Gemini as a sub-processor. **Not implemented:** packaging, customer runbooks, or a determination that hosting location ends applicability of Peruvian instruments.

### 4.3 Hybrid

Some components inside the customer environment and some externally managed. The material question is **explicit data flow**: what crosses to the product provider and what crosses to Google Gemini. The repository now includes an explicitly authorized FHIR-derived narrative-tool path, but no production hybrid deployment or real-data approval. Any production use would require revalidation of this snapshot.

---

## 5. Regulatory framework

Instruments named here are **public Peruvian norms** identified as relevant **to consider**. This section is **not** a legal memorandum and **does not** apply articles to the product as if obligations were already triggered.

Official texts must be re-read before production. Publication references:

| Instrument | Public locator (snapshot) |
|---|---|
| Ley N.° 31814 | [gob.pe / Congreso](https://www.gob.pe/institucion/congreso-de-la-republica/normas-legales/4565760-31814); [El Peruano](https://busquedas.elperuano.pe/dispositivo/NL/2192926-1) |
| DS N.° 115-2025-PCM | [gob.pe / PCM](https://www.gob.pe/institucion/pcm/normas-legales/7133522-115-2025-pcm); [El Peruano](https://busquedas.elperuano.pe/dispositivo/NL/2436426-1) |
| Ley N.° 29733 | Ley de Protección de Datos Personales |
| DS N.° 016-2024-JUS | [ANPD / gob.pe](https://www.gob.pe/institucion/anpd/normas-legales/6554453-n-016-2024-jus) |
| Ley N.° 30024 | [MINSA](https://www.gob.pe/institucion/minsa/normas-legales/240527-30024) — crea RENHICE |
| Ley N.° 31750 | modifica arts. 2 y 4 de la Ley 30024 ([El Peruano](https://busquedas.elperuano.pe/dispositivo/NL/2180595-1)) |
| DS N.° 020-2025-SA | modifica el reglamento de la Ley 30024 (DS 009-2017-SA) |
| FHIR / IPS Perú (SIHCE–RENHICE) | [Guía FHIR PE / MINSA](https://dyaku.minsa.gob.pe/guides/index.html) |

HIPAA and GDPR are **not** analyzed here. If the product later serves other jurisdictions, that is a separate open question.

### 5.1 Ley N.° 31814

*Ley que promueve el uso de la inteligencia artificial en favor del desarrollo económico y social del país* (published 5 July 2023).

Public object: promote AI in digital transformation with an ethical, safe, transparent, and responsible environment; PCM / Secretaría de Gobierno y Transformación Digital as national technical authority.

**Product applicability:** the commercial Healthcare AI & Interoperability Platform **may** fall within the national AI policy space if it offers AI in Peru. Whether a given release is an “AI system” under the law/regulation, and which duties apply to a private vendor versus a public body, is an **open regulatory question**.

Current Gemini use has two separate paths: the gated experimental summary of synthetic input and the authorized Clinical Follow-up Review narrative subflow, which may receive FHIR-derived tool payloads under explicit contracts. This technical capability does not establish production real-clinical-data authorization or answer legal/regulatory applicability; provider, purpose, transfer, retention and risk questions require revalidation before such use.

### 5.2 Decreto Supremo N.° 115-2025-PCM

Reglamento of Ley 31814 (published 9 September 2025; six titles, 36 articles). Themes in the official text include: principles (including human supervision and transparency), risk classification (unacceptable / high / otherwise acceptable), progressive implementation, and distinct public- vs private-sector provisions.

**Do not** treat “healthcare software” as automatically high-risk. Classification depends on **actual use** (see §6).

Progressive implementation and sector timelines in the reglamento are **open regulatory questions** for counsel; they are not implemented as product features.

### 5.3 Ley N.° 29733

Ley de Protección de Datos Personales. Topics to confirm against the official text before any production assessment include purpose limitation, proportionality/minimization, security, data-subject rights, controller/processor, international transfers, incidents, and special treatment of **health data**. This list is not a determination that those duties already apply to the product.

**Product applicability:** sandbox EHR traffic and a synthetic fixture are **not** a substitute for a processing inventory of real patient data. If SaaS later processes health data of persons in Peru, 29733/016-2024-JUS become **future product considerations**. Role of the vendor: **requires legal/organizational determination**.

### 5.4 Decreto Supremo N.° 016-2024-JUS

Approves the current Reglamento of Ley 29733 (published 30 November 2024; derogates DS 003-2013-JUS). Develops obligations and procedures applicable to personal-data processing. The exact duties applicable to this product depend on the facts, roles, processing activities, and jurisdictions involved. Those duties are **not determined** in the repository.

### 5.5 Ley N.° 30024

Creates the **Registro Nacional de Historias Clínicas Electrónicas (RENHICE)**.

FHIR R4 **client capability** in this product is **not** RENHICE accreditation and **not** authorization to reuse clinical data for arbitrary purposes.

### 5.6 Ley N.° 31750

Amends Ley 30024 (arts. 2 and 4): interoperability of electronic health records and access to **disassociated** data for research. The official amendment text refers to Ley 29733. How that reference applies to this product is an **open regulatory question**.

The current product does **not** implement RENHICE research-access workflows or a dissociation pipeline for national research.

### 5.7 Decreto Supremo N.° 020-2025-SA

Modifies the Reglamento of Ley 30024 (DS 009-2017-SA) to align with Ley 31750 (research / disassociated data procedures).

**Not applicable to current scope** as an implemented integration. **Open question** if a customer is an IPRESS whose SIHCE must interoperate with RENHICE.

### 5.8 SIHCE / FHIR Perú

MINSA FHIR R4 guidance describes exchange among **SIHCE** in the framework of Ley 30024 / RENHICE (IPS Perú / Core PE).

| Distinction | Current product |
|---|---|
| FHIR R4 client to vendor sandboxes | Implemented technical control |
| Conformity to FHIR Perú / IPS Perú profiles | Not implemented as an accreditation or profile pack |
| SIHCE of an IPRESS | Not established |
| RENHICE participant | Not established |

FHIR interoperability ≠ SIHCE accreditation ≠ RENHICE authorization ≠ license to send clinical data to a model.

---

## 6. AI risk classification

DS 115-2025-PCM classifies **uses**, including (in the official reglamento text) **high-risk uses** such as managing critical health services, determining access to health services, or orienting screening / diagnostic suggestion / management / prognosis / prioritization that can significantly affect wellbeing, including evaluation of sensitive data in electronic health records.

**This snapshot does not classify the current product as high-risk.**

Reasons this document stays at **open regulatory question** rather than a label:

- The synthetic experimental-summary path remains limited to `SYN-076-001`.
- Clinical Follow-up Review may supply FHIR-derived data through explicitly authorized narrative tools, but its protocol is deterministic and does not assess diagnosis, severity, urgency, treatment, medication or clinical normality.
- `clinicalAssessment.status` remains `not_performed`; model output cannot control protocol, human review or action.
- The workflow performs no FHIR write or autonomous external action.
- Java Model Boundary v1 remains a separate non-model path.

A commercial use that processes real HCE data through an external model, influences clinical decisions or affects access to care **might** sit near the reglamento’s high-risk *use* descriptions. That requires a **formal production AI risk assessment** and legal determination. Healthcare product ≠ automatically high-risk AI.

The earlier synthetic-only rationale is no longer a sufficient basis for a legal conclusion. Existing applicability conclusions must be revalidated before production use of the FHIR-derived narrative path; this document does not silently change that legal conclusion.

---

## 7. Personal and health data

| Data class | Current evidence | Status |
|---|---|---|
| Real patient / production PHI | Not a product feature in repo | Open question / future consideration |
| EHR sandbox resources | Fetched by Java; then minimized by allowlist 042 | Implemented technical control on projection; legal character of sandbox data: open question |
| Model Boundary v1 fields | `resourceType` + limited status codes; no Patient id/name/birthDate/values (Task 042 blocklist) | Implemented technical control |
| SYN-076-001 | Fixed synthetic case in `experimental_fixture.py` | Not equivalent to sandbox or real data |
| Clinical Follow-up Review FHIR snapshot | Patient, Encounter, Observation and Appointment through a case-bound contract | Implemented development path; production use and legal roles unresolved |
| Narrative follow-up tool payloads | FHIR-derived payloads available only through authorized tools | Implemented technical boundary; real-data provider processing not approved or assessed here |
| Health data as sensitive data under 29733 | Theme of the personal-data framework | Requires legal/organizational determination when real data exists |

Purpose limitation, data-subject rights, incident notification, international transfers, and formal controller/processor roles: **not implemented** as product workflows. Minimization of the **projection** is not a completed 29733 assessment.

RetentionCeiling N=5 is an **application retain-at-most-N** after a Bundle. It is **not** a legal retention or erasure policy.

---

## 8. Interoperability and clinical information

The product’s interoperability value includes the Healthcare Interoperability FHIR client and vendor-neutral boundary. Healthcare AI also has a separate, capability-specific FHIR read contract for Clinical Follow-up Review. That contract is not a general interoperability or legal-purpose registry.

Authorized purpose of any future clinical flow (care, operations, research, AI) is **not** encoded as a legal purpose register. Tasks 066–067 simulate consent/purpose/scope and document that verification is **not implemented**.

Disassociated data for research (Ley 31750 / DS 020-2025-SA) is **not implemented**.

Do not treat sandbox SMART success, local HAPI success or a technically authorized tool as authorization for production reuse of clinical information, including reuse as model input.

---

## 9. External AI provider

Current provider: **Google Gemini API** via `google-genai==2.24.0`. Default model id: `gemini-flash-latest`; `GEMINI_MODEL` may override. There is no fallback, router or second provider.

Gemini is used by two separate paths:

- the exact synthetic fixture on `/internal/experimental-summary`;
- the Clinical Follow-up Review narrative subflow, where FHIR-derived payloads may be returned only through explicitly authorized tools.

The deterministic follow-up protocol and its review/action projection remain outside Gemini.

| Topic | What the repo shows | What the repo does **not** show |
|---|---|---|
| Application excludes API keys, prompts, completions and clinical payloads from ordinary audit fields | `emit_audit`, follow-up HTTP log and policy audit | Provider-side logging or retention |
| Model input is contract-bounded | Synthetic fixture contract or authorized follow-up tools | Legal purpose, production authorization or provider terms for real clinical data |
| Timeout/error normalization and bounded retry | Provider implementations and workflow tests | SLA or residency |
| External processing | HTTPS calls to Gemini | Region, subprocessors, DPA, retention or product-improvement use at Google |

**No model training use in application code ≠ zero data retention at the provider.**

Account, region, contractual terms, subprocessors and the treatment of real clinical prompts/tool payloads are **open regulatory questions**. Do not infer them from a local `.env` or from application-side logging controls.

---

## 10. SaaS vs customer-hosted applicability

| Topic | SaaS (future) | Customer-hosted (future) | Hybrid (future) | Current repo |
|---|---|---|---|---|
| Who operates compute | Product provider | Customer | Split; must be explicit | Developer workstation / local processes |
| Who holds EHR credentials | Typically provider or customer-by-contract | Typically customer | Split | Operator `.env` (Java SMART) |
| Who holds `GEMINI_API_KEY` | Provider or customer | Customer or shared | Highest leakage risk if unclear | Local env; not a secret manager |
| 29733 roles | Requires legal/organizational determination | Does not vanish | Follow the data flow | Not determined |
| 31814 / DS 115 | Depends on offered AI use | Depends on offered AI use | Same | Synthetic experiment plus deterministic follow-up and a gated narrative model path; legal classification unresolved |
| SIHCE / RENHICE | Only if the offering becomes that system | Only if the customer uses it as SIHCE | Same | Not established |
| Gemini crossing a border | Likely if Google processes outside PE | Still possible | Must be drawn | Not documented |

Customer-hosted ≠ outside regulatory scope.

---

## 11. Technical controls already implemented

Verified. No extra controls invented.

| Control | Where | Notes |
|---|---|---|
| SMART Authorization Code + PKCE | `SmartAuthorizationCoordinator`, `AuthorizationCodeClient` | Sandbox clients; not enterprise IAM |
| FHIR R4 boundaries | Java interoperability client plus constrained Python follow-up read client | Python access is case-bound, GET-only and limited by ADR-085; not arbitrary Epic/Oracle/HAPI access |
| Allowlist 042 | `ClinicalProjectionMapper`, `ModelBoundaryMapper` | Patient: `resourceType` only; see Task 042 §4 |
| RetentionCeiling N=5 | `RetentionCeiling` | Not a legal retention policy |
| Model Boundary v1 | `GET /api/model-boundary/v1` | Not model input |
| X-Service-Token (Java) | `ModelBoundaryServiceAuthFilter` | Fail-closed if unconfigured |
| Constant-time compare (Java only) | `ModelBoundaryServiceTokenSettings.matches` uses `MessageDigest.isEqual` | **Not** claimed for Python |
| No Java log of the token value | Filter logs `reason=unconfigured\|absent\|empty\|mismatch` only | |
| X-Service-Token (Python internal endpoints) | `app/service_auth.authenticate` | Fail-closed if blank on agent-context, experimental-summary and Clinical Follow-up Review. Equality compare. **Not** a network boundary |
| Feature gate | `LLM_EXPERIMENTAL_ENABLED` default false | 503 `DISABLED`, no provider call |
| Synthetic fixture only | `is_canonical_fixture`; Bundle → 422 | |
| Timeout 30s | `GeminiProvider` + `PROVIDER_TIMEOUT_SECONDS` | |
| Output size limit | `MAX_SUMMARY_CHARS = 2000`; oversized → 502 | |
| `requiresHumanReview=true` | App-owned; provider cannot unset | ≠ operational HITL |
| `modelCalled` semantics (076) | True only after provider invocation starts | |
| Java `modelCalled=false`, `modelCallAuthorized=false` | `AiBoundaryDecision` | Unchanged by 076/077 |
| correlationId | `X-Correlation-ID` or generated UUID on 074/076 | Java v1 surface does not use the same scheme |
| Minimized experimental logs | Allowlist of fields in `emit_audit` | ≠ provider-side LLM logs |
| Threat model T1–T9 | `llm-boundary-threats-and-controls.md` | Documented control / residual risks |
| Follow-up case isolation | `langgraph_fhir_followup.py`, protocol/pagination/concurrency tests | Applies to Patient association and every page |
| Bounded completeness-aware FHIR reads | `langgraph_fhir_hapi.py` | Page/resource limits; incomplete ≠ empty |
| HAPI continuation restrictions | `langgraph_fhir_hapi.py` | Same origin/base, strict query, stable traversal, no redirects |
| Deterministic protocol outside model authority | `post_consultation_review.py`, `followup_service.py` | Gemini cannot set protocol/review/action fields |
| Explicit narrative-tool contracts | `langgraph_gemini_fhir_followup.py` | FHIR-derived model input is limited to authorized tools |
| No follow-up FHIR writes | Read client and workflow architecture | Proposed action is not execution |

`.env` is gitignored (`.gitignore`). That is hygiene, not a secret manager.

---

## 12. Controls not implemented

Recorded as **governance/product questions**, not as Tasks in this change:

- Enterprise IAM / RBAC; tenancy
- Secret rotation; secret manager
- Rate limiting; network isolation as a control; WAF / API gateway
- SIEM; DLP; persistent clinical audit (Java `LoggingFhirAuditRecorder` is an in-memory lab buffer, max 100 events — not a production audit store)
- Operational HITL (reviewer, queue, approve/reject)
- Legal retention / erasure policy
- Data-subject rights workflow
- Formal DPA; controller/processor determination
- Formal production AI risk assessment
- Production clinical validation
- SIHCE applicability assessment; RENHICE applicability assessment
- Production Gemini / provider assessment (account, region, terms, retention, subprocessors and real-data use)
- Production authorization and governance for real clinical data supplied through the follow-up narrative tools
- Second LLM provider; fallback; router
- Effective network boundary for Python `:8090` (ADR-082 layer 2). Inbound `X-Service-Token` is implemented on the three internal endpoints (see §11). That authentication layer does **not** implement network isolation. Default `AI_SERVICE_HOST` remains `0.0.0.0`.
- Durable follow-up audit storage, queue, reviewer assignment, acknowledgement and disposition

---

## 13. Evidence matrix

No scores. No compliant / non-compliant labels.

| Regulatory / governance area | Requirement / topic | Current product applicability | Existing technical evidence | Current status | Future consideration |
|---|---|---|---|---|---|
| AI governance | Risk classification (DS 115) | Depends on **use**, not on “healthcare software” | Synthetic path plus deterministic follow-up and contract-bounded narrative model path | Open regulatory question; revalidate before production real-data use | Classify each commercial use before launch |
| AI governance | Transparency | Relevant if an AI feature is offered to users | `promptVersion`, provider/model in 076 response; no end-user UI | Partially addressed | User-facing disclosure if commercialized |
| AI governance | Human oversight | Relevant for future high-risk **clinical** AI | Follow-up `humanReview.status=required` is application-owned | Response-level projection only | Operational queue, roles and disposition if use requires it |
| AI governance | Progressive implementation | Possible private-sector timelines in DS 115 | None in product | Open regulatory question | Counsel + official text |
| Data protection | Minimization / proportionality | Relevant when personal/health data exist | Allowlist 042 + N=5 + v1 | Implemented technical control | Formal processing assessment |
| Data protection | Purpose limitation | Relevant for real clinical flows | Simulated in 066/067 docs as not verified | Partially addressed (simulation) / not implemented (real purpose) | Legal purpose register |
| Data protection | Security of processing | Relevant for any personal data | Service token, gates, case isolation, bounded reads, continuation validation, minimized logs | Partially addressed | IAM, rotation, isolation, SIEM and durable audit |
| Data protection | Controller / processor | Relevant for SaaS / Gemini | Not in repo | Requires legal/organizational determination | Contracts + facts |
| Data protection | International transfers | Relevant if Gemini or SaaS leaves PE | Not documented | Open regulatory question | Provider + hosting assessment |
| Data protection | Data-subject rights | Relevant if real data subjects exist | Not implemented | Not implemented | Workflow + roles |
| Data protection | Incidents | Relevant in production | Not implemented | Not implemented | Incident process |
| Healthcare | SIHCE accreditation | Not established | No SIHCE implementation | Open question | Assess if the offering becomes a SIHCE |
| Healthcare | RENHICE | Not established | FHIR client ≠ registry participation | Open question | Only if customer/product joins RENHICE |
| Healthcare | FHIR Perú / IPS | Not implemented as profile accreditation | HAPI R4 client to vendor sandboxes | Not applicable to current scope as accreditation | Profile work if MINSA exchange is sold |
| Healthcare | Disassociated research data | Ley 31750 / DS 020-2025-SA theme | Not implemented | Not implemented | Separate product decision |
| External AI | Provider processing | Relevant to any real-data model call | `GeminiProvider`; synthetic input and authorized follow-up tool contracts | Technical boundary implemented; production real-data conclusion unresolved | Production provider and legal assessment |
| External AI | Provider logging / retention / training | Relevant | App does not log prompt/key | Open regulatory question | Google terms for the chosen SKU |
| Deployment | SaaS / hosted / hybrid | Future product consideration | Local processes only | Not implemented | Choose model and draw data flows |
| Identity | Service authentication | Lab shared secret | `X-Service-Token` | Implemented technical control | ≠ enterprise IAM/RBAC |

---

## 14. Open regulatory questions

### Operator

- Who is the legal operator of the Healthcare AI & Interoperability Platform?
- In which country is the operator established?
- Which jurisdictions will the product serve?

### Data

- Will real patient data be processed?
- Which FHIR resources and which elements (beyond allowlist 042)?
- What is the minimum required dataset for each commercial use?
- How are sandbox data legally characterized versus production data?

### AI

- What exact AI use cases will be commercialized?
- Will outputs influence clinical decisions or access to care?
- Will human review be mandatory **as an operation**, not only as a flag?
- Which explicitly authorized FHIR-derived context may be sent to a model? Today the Clinical Follow-up Review narrative tools can supply contract-bounded payloads; production use with real clinical data remains unapproved and requires legal/regulatory/provider revalidation.

### Provider

- Which Google service/product will be used in production (API SKU, contract)?
- What terms apply (including training / product improvement)?
- What retention and provider-side logging apply?
- Where can data be processed, and which subprocessors apply?
- Is there a DPA?

### Deployment

- SaaS, customer-hosted, or hybrid?
- Who operates infrastructure and who manages secrets?
- Who can access production data (vendor support included)?

### Healthcare

- Is the customer an IPRESS?
- Is the platform part of a SIHCE?
- Does RENHICE integration apply?
- What authorized purpose governs the clinical data flow?

---

## 15. Product implications

Implications for **product design**, not a backlog of coding Tasks:

1. Keep each model input path explicit: the synthetic experiment, Model Boundary v1 non-model consumer, and authorized Clinical Follow-up Review narrative tools are separate contracts.
2. Treat allowlist 042, Model Boundary v1 and the follow-up tool contracts as bounded interfaces, not as general permission to expand model access. A new data category requires a new decision, contract and governance assessment.
3. Do not market FHIR R4 or sandbox SMART as SIHCE/RENHICE authorization or as clinical AI.
4. Do not market `requiresHumanReview` or follow-up `humanReview.status=required` as an operational queue, assignment or completed human oversight.
5. Do not market `X-Service-Token` as IAM.
6. Do not market N=5 as a legal retention policy.
7. Do not market “we do not log prompts” as “the provider retains nothing.”
8. Before commercial use with real clinical data, complete: use-case description, risk classification against official DS 115 text, data inventory, party roles, lawful purpose/authorization and provider assessment.
9. SaaS vs customer-hosted changes **who** must answer 29733/31814 questions; it does not delete the questions.
10. Historical Tasks 057–073 remain useful as **deny-by-default simulations**; they must not be sold as real consent, IAM, or clinical authorization.

---

## 16. Regulatory snapshot

**Date:** 19 September 2026.

The legal/regulatory analysis remains the 19 September 2026 snapshot; its technical baseline was reconciled on 29 September 2026. It must be **revalidated** before:

- production deployment;
- processing of real patient data;
- production use of FHIR-derived or other real clinical data with any model;
- materially expanding the authorized follow-up model-data contract;
- offering clinical decision support;
- claiming SIHCE/RENHICE participation;
- a material change of provider, deployment model, or jurisdiction.

Official instruments cited in §5 can be amended. Re-read the texts on [gob.pe](https://www.gob.pe) / El Peruano; do not rely on this file as the legal source.

---

## 17. Disclaimer and limitations

This document is an **engineering and product-governance analysis** prepared from the repository and from publicly identified Peruvian instruments.

It does **not** constitute:

- legal advice or a legal opinion;
- a declaration of compliance with Ley 31814, DS 115-2025-PCM, Ley 29733, DS 016-2024-JUS, Ley 30024, Ley 31750, DS 020-2025-SA, FHIR Perú, HIPAA, GDPR, or any other framework;
- privacy, security, clinical, or regulatory certification;
- accreditation as SIHCE or authorization to participate in RENHICE.

No statement in this file should be read as “the system complies with…”, “the product is compliant with…”, “the platform is certified…”, or “the platform satisfies all requirements…”.

Counsel and the product operator must determine roles, purposes, and obligations from **facts and official sources**, not from this snapshot alone.
