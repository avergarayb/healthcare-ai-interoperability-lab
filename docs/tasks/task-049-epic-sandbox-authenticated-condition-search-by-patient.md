# Task 049 — Epic Sandbox Authenticated Condition Search by Patient

## WHAT / WHY / HOW / CONCEPT

QUÉ DEBE DISEÑAR CHATGPT AHORA — TASK 049
==================================================

Epic sandbox authenticated Condition search by the configured Patient.

Espejo de Oracle Task 037. NO snapshot. NO Patient search. NO Observation todavía.

Flujo objetivo:

  token SMART en memoria (046)
        +
  EPIC_SANDBOX_PATIENT_ID (048; no nuevo env)
        +
  capability.supports("Condition", SEARCH_TYPE) usando discovery 047 (perfil NONE, un GET /metadata)
        ↓
  RoutingService.searchConditions("epic-sandbox", issuedTokenProvider, patientId)
        ↓
  FhirService.searchConditionsByPatientWithCount(...)
        ↓
  GET /Condition?patient={id}&...   Authorization: Bearer <token 046>
        ↓
  FhirConditionSearchResult
        ↓
  página ciega

REUSAR:
- PatientContext / CONFIGURED / EPIC_SANDBOX_PATIENT_ID de 048
- IssuedAccessTokenProvider de 046
- EpicSandboxCapabilityDiscoveryService de 047
- FhirConditionSearchOutcome / FhirConditionSearchResult / FhirConditionSearchResults
- RoutingService.searchConditions (ya existe; Oracle lo usa)
- Página ciega al estilo GET /oracle/sandbox/fhir/condition-search

NO CREAR:
- EpicConditionClient / EpicFhirService / EpicConditionSearch
- RoutingService.discoverCapabilities("epic-sandbox")
- Patient search / Patient read nuevo
- Observation / DiagnosticReport / MedicationRequest
- snapshot / proyección / contrato / agente / LLM / ai-service
- Production Epic / confidential client
- cache
- hardcoded Patient ID
- host fhir.epic.com nuevo
- if Epic en FhirService o timeout
- categoría Condition distinta hardcodeada “porque Epic”

Query: reusar la genérica ya viva en RoutingService (patient + _count=5 + category=problem-list-item).
_count es petición, no techo. Bundle vacío = SUCCESS con count=0 (no EMPTY).
Si Epic sandbox no acepta esa category, la spec debe decir cómo se diagnostica (capability / outcome), NO inventar if Epic.

Si falta token: AUTHENTICATION_REQUIRED, 401, CERO HTTP Condition.
Si falta Patient ID: PATIENT_CONTEXT_NOT_CONFIGURED, 409, CERO HTTP Condition.
Si capability no declara Condition SEARCH_TYPE: CAPABILITY_UNSUPPORTED, 409, CERO HTTP Condition.

Lab propuesto: GET /epic/sandbox/fhir/condition-search
Ciego: no token, no Patient ID, no Condition JSON, no códigos, no textos clínicos.
Puede mostrar outcome, httpStatus, destination, resourceType, count.

Tests default SIN red Epic. Live opt-in EPIC_SANDBOX_LIVE_IT=true.
LiveIT Maven no puede login browser: diagnostica AUTH / CONTEXT si falta sesión.

Rama propuesta: feature/epic-sandbox-condition-search
Commit propuesto: feat: add Epic sandbox authenticated Condition search by Patient

==================================================

## STOP CONDITION

Implement only one authenticated Condition search by the configured Patient against `epic-sandbox`.

Do not continue into Patient search, Condition read, Observation, DiagnosticReport, MedicationRequest, snapshot, projection, contract, agent, LLM, or `ai-service`.

## HARD BOUNDARIES

- Reuse `PatientContext`, `PatientContextSource.CONFIGURED`, `PatientContexts.fromConfigured(...)`, and `EPIC_SANDBOX_PATIENT_ID` from Task 048.
- Reuse `IssuedAccessTokenProvider` from Task 046.
- Reuse `EpicSandboxCapabilityDiscoveryService` from Task 047.
- Check `supports("Condition", SEARCH_TYPE)` before clinical HTTP.
- Reuse `RoutingService.searchConditions(...)`.
- Reuse `FhirService.searchConditionsByPatientWithCount(...)`.
- Reuse `FhirConditionSearchOutcome`, `FhirConditionSearchResult`, and `FhirConditionSearchResults`.
- Do not call `RoutingService.discoverCapabilities("epic-sandbox")`.
- Do not create `EpicConditionClient`, `EpicFhirService`, or Epic-specific Condition search logic.
- Do not add `if Epic` logic to `FhirService` or timeout handling.
- Reuse the generic query: `patient + _count=5 + category=problem-list-item`.
- `_count=5` is a request, not a retention ceiling.
- Empty Bundle is `SUCCESS` with `count=0`; do not introduce `EMPTY`.
- If Epic rejects the category/query, preserve the generic outcome/error path; do not invent an Epic-specific query workaround.
- Missing token → `AUTHENTICATION_REQUIRED`, HTTP 401, zero Condition HTTP.
- Missing Patient ID → `PATIENT_CONTEXT_NOT_CONFIGURED`, HTTP 409, zero Condition HTTP.
- Unsupported Condition SEARCH → `CAPABILITY_UNSUPPORTED`, HTTP 409, zero Condition HTTP.
- No Patient search fallback.
- No Condition read.
- No cache.
- No new Epic host hardcoding.
- No real Patient ID outside local `.env`.
- Lab: `GET /epic/sandbox/fhir/condition-search`.
- Lab is blind: no token, Patient ID, Condition JSON, codes, or clinical text.
- Default tests have no Epic network access.
- LiveIT is opt-in with `EPIC_SANDBOX_LIVE_IT=true`.
- PowerShell: no `&&`; use `curl.exe`.

## FIRST INSPECTION

Cursor must inspect first:

```text
RoutingService.searchConditions
FhirConditionSearchResult
FhirConditionSearchOutcome
FhirConditionSearchResults
OracleSandboxConditionSearchService
EpicSandboxPatientContextService
EpicSandboxCapabilityDiscoveryService
```

Also inspect the exact Oracle Task 037 implementation and its blind-lab/controller pattern.

## GIT

Branch:

```text
feature/epic-sandbox-condition-search
```

Commit:

```text
feat: add Epic sandbox authenticated Condition search by Patient
```

Never commit `.env`.

## ARCHITECTURE

```text
Epic sandbox
    │
    │ SMART Bearer token
    ▼
configured Patient context
    │
    ▼
EpicSandboxCapabilityDiscoveryService
    │
    ▼
FhirServerCapabilities.supports("Condition", SEARCH_TYPE)
    │
    ▼
RoutingService.searchConditions(...)
    │
    ▼
FhirService.searchConditionsByPatientWithCount(...)
    │
    ▼
HAPI FHIR
    │
    ▼
GET /Condition?patient=...&_count=5&category=problem-list-item
    │
    ▼
FhirConditionSearchResult
    │
    ▼
blind lab
```

The vendor boundary identifies the Epic destination and supplies authentication/context. The actual Condition search remains vendor-neutral.
