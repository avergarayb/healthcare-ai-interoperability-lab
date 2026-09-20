# Regulatory Context & Product Applicability

**Healthcare AI & Interoperability Platform**

**Snapshot date:** 19 September 2026  
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

State, for the evolving **Healthcare AI & Interoperability Platform** (also: **Healthcare AI Platform**, **the product**):

- which Peruvian instruments are **relevant to consider** for a future commercial offering;
- which **technical controls already exist**;
- which topics remain **open** before production or before sending real clinical data to a model.

**In scope:** documentation of applicability. Interoperability (Java FHIR boundary) and the current experimental Gemini path.

**Out of scope:** changing architecture or code; creating Tasks 078+; inventing RAG, agents, MCP, LangGraph, memory, OpenAI, a second provider, fallback/router, frontend, RBAC, IAM, tenancy, operational HITL, CDS, or a FHIR→Gemini path.

**Rule:** a technical control is not legal compliance.

---

## 2. Product context

The repository is the foundation of a commercial Healthcare AI & Interoperability Platform. Target deployment models (not implemented as a production estate today):

1. SaaS operated by the product provider.
2. Customer-hosted software in infrastructure controlled by the healthcare organization.
3. Hybrid (some components in the customer environment, some externally managed).

The current implementation is **under development**. Sandbox EHR integrations and a gated experimental model call exist. There is **no** production tenant, **no** accredited SIHCE, and **no** flow of FHIR-derived clinical context into Gemini.

Two technical surfaces remain in the current codebase of this single product:

| Technical surface | Role today |
|---|---|
| Java interoperability surface (`fhir-integration-service`, port **8081**) | SMART + FHIR R4 client to Epic/Oracle sandboxes and HAPI; snapshot; allowlist; Model Boundary v1 |
| Python AI surface (`ai-service`, port **8090**) | Consumes v1 without calling a model; separately, experimental Gemini on a synthetic fixture |

`docs/PROJECT.md` lists strategy items (RAG, Kubernetes, Spring Security, etc.). Those are **not** evidence of current runtime.

---

## 3. Current technical baseline

Verified against the repository (19 September 2026).

### Interoperability path (does not call Gemini)

```text
EHR sandbox (Epic / Oracle / HAPI)
        → Java / FHIR R4 client
        → snapshot
        → Task 042 allowlist
        → RetentionCeiling N=5
        → Model Boundary Contract v1
        → GET /api/model-boundary/v1  (+ X-Service-Token)
        → GET /internal/agent-context   (modelCalled=false)
```

### Experimental AI path (does not read v1 or FHIR)

```text
SYN-076-001
        → POST /internal/experimental-summary
        → LLMProvider → GeminiProvider
        → Google Gemini API
```

```text
FHIR / EHR context
        → Java / FHIR boundary
        → Model Boundary v1
        → X
        → X ----> Gemini
```

`SYN-076-001` is **not** equivalent to FHIR-derived clinical context.

| Capability | Evidence |
|---|---|
| Java 21 / Spring Boot, port 8081 | `services/fhir-integration-service/src/main/resources/application.yml` |
| HAPI FHIR R4 client | `lab.healthcare.fhir.client` (not a FHIR server of the product) |
| SMART Authorization Code + PKCE | `SmartAuthorizationCoordinator`, `AuthorizationCodeClient`; Epic `PUBLIC_PKCE`; Oracle `PUBLIC_PKCE` |
| Snapshot + allowlist 042 | `ClinicalProjectionMapper`, `ClinicalProjectionAssembler`; spec `docs/tasks/Task_042_Clinical_Data_Minimization_and_Controlled_Projection_v2.md` |
| RetentionCeiling N=5 | `RetentionCeiling.DEFAULT_LIMIT`; `OracleEpicContractCompatibilityTest` |
| Model Boundary v1 | `ModelBoundaryContract`, `ModelBoundaryMapper`; `docs/fhir/model-boundary-contract-v1.md` |
| X-Service-Token on v1 | `ModelBoundaryServiceAuthFilter`, `ModelBoundaryServiceTokenSettings` |
| Python consumer (no model) | `app/consumer.py`, `GET /internal/agent-context` |
| Experimental Gemini | `app/experimental_service.py`, `app/gemini_provider.py`, `POST /internal/experimental-summary` |
| FakeLLMProvider | `app/fake_llm_provider.py`; default pytest |
| Fixture SYN-076-001 | `app/experimental_fixture.py` |
| Feature gate default off | `LLM_EXPERIMENTAL_ENABLED`; `Settings.llm_experimental_enabled` default `false` |
| Timeout 30s / summary ≤ 2000 | `PROVIDER_TIMEOUT_SECONDS`, `MAX_SUMMARY_CHARS` |
| `requiresHumanReview=true` | Java `AiBoundaryDecision`; Python `experimental_models.py` |
| Java `modelCalled` / `modelCallAuthorized` false | `AiBoundaryDecision` constructor rejects `true` |
| Minimized experimental logs | `emit_audit`; `test_logs_do_not_contain_secrets_or_prompt` |
| Gemini default after 077 | `gemini-flash-latest` in `config.py`, `experimental_models.DEFAULT_MODEL` |
| Threat model T1–T9 | `docs/ai-governance/llm-boundary-threats-and-controls.md` |

Tasks 057–073 implement **deny-by-default simulation gates** in Java. Their own docs state they do **not** implement a real IdP, real consent, or clinical access (for example `docs/fhir/ai-consumer-authorization-boundary.md`, `docs/fhir/ai-consumer-consent-boundary.md`).

---

## 4. Deployment models

None of the three models is implemented as a production platform. They are **future product considerations**. Customer-hosted does **not** remove all regulatory questions.

### 4.1 SaaS

Provider-operated infrastructure. If the product later processes customer healthcare data, parties must determine **controller / processor / joint-controller** roles by contract and fact. That determination is **not** in this repository.

Future considerations (not implemented): tenancy, enterprise IAM, production secret management, provider-side access to customer data, incident process, DPA with the product provider **and** with Google (if Gemini remains).

### 4.2 Customer-hosted

Software runs where the healthcare organization controls infrastructure. The organization may be closer to **controller** of clinical data; the product vendor may still process data (support, updates, telemetry) or introduce Gemini as a sub-processor. **Not implemented:** packaging, customer runbooks, or a determination that hosting location ends applicability of Peruvian instruments.

### 4.3 Hybrid

Some components inside the customer environment and some externally managed. The material question is **explicit data flow**: what crosses to the product provider and what crosses to Google Gemini. Today the only model path is the synthetic fixture; a future hybrid that sent v1 or FHIR to Gemini would be a **material product change** and would void this snapshot.

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

**Product applicability:** the commercial Healthcare AI Platform **may** fall within the national AI policy space if it offers AI in Peru. Whether a given release is an “AI system” under the law/regulation, and which duties apply to a private vendor versus a public body, is an **open regulatory question**.

Current Gemini use is a **gated experimental summary of synthetic input**. That fact does **not** by itself answer applicability for a future clinical AI feature.

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

- The only live model path accepts **SYN-076-001**, not EHR or v1 data.
- The prompt builder instructs: no diagnose, no treatment, no medication, no clinical decisions (`app/llm_provider.py` `build_experimental_prompt`). That is a **technical instruction**, not a legal classification.
- `summary` is not wired to write FHIR, execute tools, or drive care.
- Java keeps `modelCallAuthorized=false` and `modelCalled=false` on the interoperability path.

A **future** commercial use that influenced clinical decisions, access to care, or processing of HCE data **might** sit near the reglamento’s high-risk *use* descriptions. That requires a **formal production AI risk assessment** and legal determination. Healthcare product ≠ automatically high-risk AI.

---

## 7. Personal and health data

| Data class | Current evidence | Status |
|---|---|---|
| Real patient / production PHI | Not a product feature in repo | Open question / future consideration |
| EHR sandbox resources | Fetched by Java; then minimized by allowlist 042 | Implemented technical control on projection; legal character of sandbox data: open question |
| Model Boundary v1 fields | `resourceType` + limited status codes; no Patient id/name/birthDate/values (Task 042 blocklist) | Implemented technical control |
| SYN-076-001 | Fixed synthetic case in `experimental_fixture.py` | Not equivalent to sandbox or real data |
| Health data as sensitive data under 29733 | Theme of the personal-data framework | Requires legal/organizational determination when real data exists |

Purpose limitation, data-subject rights, incident notification, international transfers, and formal controller/processor roles: **not implemented** as product workflows. Minimization of the **projection** is not a completed 29733 assessment.

RetentionCeiling N=5 is an **application retain-at-most-N** after a Bundle. It is **not** a legal retention or erasure policy.

---

## 8. Interoperability and clinical information

The product’s interoperability value is a **controlled FHIR client** plus a vendor-neutral boundary.

Authorized purpose of any future clinical flow (care, operations, research, AI) is **not** encoded as a legal purpose register. Tasks 066–067 simulate consent/purpose/scope and document that verification is **not implemented**.

Disassociated data for research (Ley 31750 / DS 020-2025-SA) is **not implemented**.

Do not treat sandbox SMART success as authorization for production reuse of clinical information, including reuse as model input.

---

## 9. External AI provider

Current provider path: **Google Gemini API** via `google-genai==2.24.0` (`GeminiProvider`). Default model id after Task 077: `gemini-flash-latest`. `GEMINI_MODEL` may override. There is **no** fallback, router, or second provider.

| Topic | What the repo shows | What the repo does **not** show |
|---|---|---|
| Application does not log API key, prompt, or completion | `emit_audit`; architecture/comment in `config.py` | Provider-side logging |
| No application-level claim of “no training” | Prompt says synthetic / no diagnose | Google account type, paid vs free tier, training/product-improvement terms |
| Timeout / error normalization | 30s; 502/504; `modelCalled=true` if invocation started | SLA or residency |
| External processing | HTTPS call from `GeminiProvider._invoke` | Region, subprocessors, DPA, retention at Google |

**No model training use in application code ≠ zero data retention at the provider.**

Account, region, contractual terms, and subprocessors are **open regulatory questions**. Do not infer them from a local `.env` (gitignored; not evidence).

---

## 10. SaaS vs customer-hosted applicability

| Topic | SaaS (future) | Customer-hosted (future) | Hybrid (future) | Current repo |
|---|---|---|---|---|
| Who operates compute | Product provider | Customer | Split; must be explicit | Developer workstation / local processes |
| Who holds EHR credentials | Typically provider or customer-by-contract | Typically customer | Split | Operator `.env` (Java SMART) |
| Who holds `GEMINI_API_KEY` | Provider or customer | Customer or shared | Highest leakage risk if unclear | Local env; not a secret manager |
| 29733 roles | Requires legal/organizational determination | Does not vanish | Follow the data flow | Not determined |
| 31814 / DS 115 | Depends on offered AI use | Depends on offered AI use | Same | Experimental synthetic path only |
| SIHCE / RENHICE | Only if the offering becomes that system | Only if the customer uses it as SIHCE | Same | Not established |
| Gemini crossing a border | Likely if Google processes outside PE | Still possible | Must be drawn | Not documented |

Customer-hosted ≠ outside regulatory scope.

---

## 11. Technical controls already implemented

Verified. No extra controls invented.

| Control | Where | Notes |
|---|---|---|
| SMART Authorization Code + PKCE | `SmartAuthorizationCoordinator`, `AuthorizationCodeClient` | Sandbox clients; not enterprise IAM |
| FHIR R4 boundary (client only) | HAPI client; Python architecture test forbids FHIR clients | Python does not query Epic/Oracle/HAPI |
| Allowlist 042 | `ClinicalProjectionMapper`, `ModelBoundaryMapper` | Patient: `resourceType` only; see Task 042 §4 |
| RetentionCeiling N=5 | `RetentionCeiling` | Not a legal retention policy |
| Model Boundary v1 | `GET /api/model-boundary/v1` | Not model input |
| X-Service-Token (Java) | `ModelBoundaryServiceAuthFilter` | Fail-closed if unconfigured |
| Constant-time compare (Java only) | `ModelBoundaryServiceTokenSettings.matches` uses `MessageDigest.isEqual` | **Not** claimed for Python |
| No Java log of the token value | Filter logs `reason=unconfigured\|absent\|empty\|mismatch` only | |
| X-Service-Token (Python 074 and 076 inbound) | `app/service_auth.authenticate` | Fail-closed if blank. `GET /internal/agent-context` and `POST /internal/experimental-summary` require the header; 074 returns 401 and does not fetch Java when auth fails. Equality compare. **Not** a network boundary |
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
| No OpenAI / LangGraph / FHIR host in Python app | `tests/test_architecture.py` | |

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
- Production Gemini / provider assessment (account, region, terms, retention, subprocessors)
- v1 or FHIR → Gemini
- Second LLM provider; fallback; router
- Effective network boundary for Python `:8090` (ADR-082 layer 2). Inbound `X-Service-Token` on `GET /internal/agent-context` and `POST /internal/experimental-summary` is implemented (see §11). That authentication layer does **not** implement network isolation. Default `AI_SERVICE_HOST` remains `0.0.0.0`.

---

## 13. Evidence matrix

No scores. No compliant / non-compliant labels.

| Regulatory / governance area | Requirement / topic | Current product applicability | Existing technical evidence | Current status | Future consideration |
|---|---|---|---|---|---|
| AI governance | Risk classification (DS 115) | Depends on **use**, not on “healthcare software” | Synthetic-only Gemini path; no v1→model | Open regulatory question | Classify each commercial use before launch |
| AI governance | Transparency | Relevant if an AI feature is offered to users | `promptVersion`, provider/model in 076 response; no end-user UI | Partially addressed | User-facing disclosure if commercialized |
| AI governance | Human oversight | Relevant for future high-risk **clinical** AI | `requiresHumanReview` flag (Java + 076) | Partially addressed | Operational HITL if use requires it |
| AI governance | Progressive implementation | Possible private-sector timelines in DS 115 | None in product | Open regulatory question | Counsel + official text |
| Data protection | Minimization / proportionality | Relevant when personal/health data exist | Allowlist 042 + N=5 + v1 | Implemented technical control | Formal processing assessment |
| Data protection | Purpose limitation | Relevant for real clinical flows | Simulated in 066/067 docs as not verified | Partially addressed (simulation) / not implemented (real purpose) | Legal purpose register |
| Data protection | Security of processing | Relevant for any personal data | Token 075/076, gate, gitignore, minimized logs | Partially addressed | IAM, rotation, isolation, SIEM |
| Data protection | Controller / processor | Relevant for SaaS / Gemini | Not in repo | Requires legal/organizational determination | Contracts + facts |
| Data protection | International transfers | Relevant if Gemini or SaaS leaves PE | Not documented | Open regulatory question | Provider + hosting assessment |
| Data protection | Data-subject rights | Relevant if real data subjects exist | Not implemented | Not implemented | Workflow + roles |
| Data protection | Incidents | Relevant in production | Not implemented | Not implemented | Incident process |
| Healthcare | SIHCE accreditation | Not established | No SIHCE implementation | Open question | Assess if the offering becomes a SIHCE |
| Healthcare | RENHICE | Not established | FHIR client ≠ registry participation | Open question | Only if customer/product joins RENHICE |
| Healthcare | FHIR Perú / IPS | Not implemented as profile accreditation | HAPI R4 client to vendor sandboxes | Not applicable to current scope as accreditation | Profile work if MINSA exchange is sold |
| Healthcare | Disassociated research data | Ley 31750 / DS 020-2025-SA theme | Not implemented | Not implemented | Separate product decision |
| External AI | Provider processing | Relevant to any real-data model call | `GeminiProvider`; fixture only | Controlled current scope | Production provider assessment |
| External AI | Provider logging / retention / training | Relevant | App does not log prompt/key | Open regulatory question | Google terms for the chosen SKU |
| Deployment | SaaS / hosted / hybrid | Future product consideration | Local processes only | Not implemented | Choose model and draw data flows |
| Identity | Service authentication | Lab shared secret | `X-Service-Token` | Implemented technical control | ≠ enterprise IAM/RBAC |

---

## 14. Open regulatory questions

### Operator

- Who is the legal operator of the Healthcare AI Platform?
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
- Will v1 or any FHIR-derived context ever be sent to a model? (Today: no.)

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

1. Keep the **two paths** until a new contract explicitly allows a different input to a model.
2. Treat allowlist 042 and v1 as the maximum clinical projection **under the current governance baseline** — not as a license to expand for AI. A later expansion would require a new decision, contract, and governance assessment. That is not a permanent ban on product evolution.
3. Do not market FHIR R4 or sandbox SMART as SIHCE/RENHICE authorization or as clinical AI.
4. Do not market `requiresHumanReview` as operational human oversight.
5. Do not market `X-Service-Token` as IAM.
6. Do not market N=5 as a legal retention policy.
7. Do not market “we do not log prompts” as “the provider retains nothing.”
8. Before any commercial AI use, complete: use-case description, risk classification against official DS 115 text, data inventory, party roles, and provider assessment.
9. SaaS vs customer-hosted changes **who** must answer 29733/31814 questions; it does not delete the questions.
10. Historical Tasks 057–073 remain useful as **deny-by-default simulations**; they must not be sold as real consent, IAM, or clinical authorization.

---

## 16. Regulatory snapshot

**Date:** 19 September 2026.

This is a **regulatory snapshot** of applicability and evidence. It must be **revalidated** before:

- production deployment;
- processing of real patient data;
- connecting Model Boundary v1 or FHIR to any model;
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
