# Estado técnico del laboratorio — post Tasks 076 y 077

**Fecha de este recorte:** 19 de septiembre de 2026  
**Alcance:** capacidades y controles que existen en el código y en la demo live.  
**No es:** declaración de cumplimiento legal, producto clínico, ni sistema de producción.

Convención de estados:

| Código | Significado |
|---|---|
| **A** | Implementado y comprobado en código (y, si se indica, en demo) |
| **B** | Documentado como decisión o contrato, no es una capacidad extra |
| **C** | Parcial: existe un control técnico, no un sistema completo |
| **D** | Planificado solo si ya está fuera de alcance; no es backlog aprobado |
| **E** | No encontrado / fuera de alcance |

Cadena documentada (dos caminos, no una tubería única de datos):

```text
Java FHIR boundary
      ↓
ModelBoundaryContract v1
      ↓
Task 074 consumer
      ↓
Task 075 service authentication
      ↓
Task 076 Gemini experimental integration   ← camino distinto, no alimentado por v1
      ↓
Task 077 Gemini model default alignment
```

---

## Advertencia

Este documento describe el estado técnico del laboratorio. **No** constituye una declaración de cumplimiento legal, regulatorio, clínico, de privacidad, seguridad o certificación.

**No** se afirma cumplimiento de:

- Decreto Supremo N.° 115-2025-PCM
- Ley 31814
- HIPAA
- GDPR
- ni de cualquier otro marco

**No** se afirma que el laboratorio sea producto clínico, sistema de decisión clínica, plataforma hospitalaria o sistema de producción.

---

## 1. Propósito

Consolidar lo construido hasta 077 sin inventar frontend, IAM, HITL operativo, RAG ni uso clínico.

---

## 2. Alcance técnico

### Producto A — Java (`fhir-integration-service`) — A

- Java 21, Spring Boot, puerto **8081**
- Cliente HAPI FHIR **R4** (no es un servidor FHIR de la aplicación)
- SMART Authorization Code + PKCE
- Sandboxes Epic y Oracle Health
- Snapshot clínico + allowlist Task 042 + `RetentionCeiling` N=5
- `ModelBoundaryContract` v1
- `GET /api/model-boundary/v1`
- Task 075: cabecera `X-Service-Token` / `MODEL_BOUNDARY_SERVICE_TOKEN` (fail-closed si el secret está en blanco)

`PROJECT.md` lista Spring Security, HL7 v2, RAG, Kubernetes, etc. como **estrategia**. Eso no es evidencia de implementación (**D/E** en runtime).

### Producto B — Python (`ai-service`) — A

- FastAPI, puerto **8090**
- Task 074: `GET /internal/agent-context` consume v1; `modelCalled=false`
- Task 076: `POST /internal/experimental-summary` (Gemini, fixture sintético)
- Task 076 también exige `X-Service-Token` en ese POST (mismo secret de laboratorio; no es IAM)

---

## 3. A — Implementado

### A.1 FHIR boundary

Java es el único cliente de Epic sandbox, Oracle sandbox y HAPI FHIR R4. **Python no hace esas consultas.**

### A.2 Snapshot + allowlist 042

Existe. 076/077 **no** amplían la allowlist. No hay recursos clínicos nuevos por la integración LLM.

### A.3 RetentionCeiling N=5

Recorte de proyección hacia v1. **No** es política legal de retención ni obligación de supresión.

### A.4 ModelBoundaryContract v1

Sin cambios en 076/077. Delimita lo que puede cruzar al consumidor 074. **076 no conecta v1 a Gemini.**

### A.5 Task 074 — consumer

`GET /internal/agent-context` sigue separado del camino Gemini. No llama modelo.

### A.6 Task 075 — service authentication

`X-Service-Token` en `GET /api/model-boundary/v1`. Autenticación servicio-a-servicio de laboratorio. **No** es IAM, RBAC ni identidad empresarial.

### A.7 Task 076 — Gemini experimental

```text
POST /internal/experimental-summary
        ↓
LLMProvider
        ↓
GeminiProvider          (FakeLLMProvider en tests)
        ↓
Google Gemini API
```

Independiente de `/internal/agent-context`.

### A.8 Fixture sintético

Solo igualdad exacta con `SYN-076-001`. El modelo no recibe Bundle FHIR, v1, Epic, Oracle ni HAPI.

### A.9 Feature gate

`LLM_EXPERIMENTAL_ENABLED=false` por defecto. Sin flag no hay llamada al proveedor.

### A.10 Human review (flag)

`requiresHumanReview=true` lo pone la aplicación, no Gemini. Ver **C.1**.

### A.11 `modelCalled`

`true` solo si la invocación al proveedor **empezó**. Java permanece en `modelCalled=false` y `modelCallAuthorized=false`.

### A.12 Logging

Permitido: `correlationId`, `useCase`, `promptVersion`, `provider`, `model`, `durationMs`, `status`, `modelCalled`.  
No: prompt, completion, API key, service token.

### A.13 Task 077

Default de repositorio: `gemini-flash-latest`. `GEMINI_MODEL` es override; vacío → ese default. Sin fallback, router, segundo proveedor ni retries.

Demo live 2026-09-19 (sin Java, fixture sintético):

| Modelo | Resultado Google |
|---|---|
| `gemini-2.5-flash` | 404 |
| `gemini-2.0-flash` | 404 |
| `gemini-flash-latest` | 503 luego 200 `COMPLETED` |

076 **especificó** `gemini-2.5-flash`. 077 alineó el default. No reescribir la historia de 076.

---

## 4. B — Documentado

### B.1 Separación de boundaries

Java = frontera FHIR/proveedor EHR. Python = frontera AI/experimental.

### B.2 Dos caminos

| Superficie | Modelo |
|---|---|
| `GET /internal/agent-context` | no llama |
| `POST /internal/experimental-summary` | único LLM actual |

### B.3 Gobernanza experimental

Integración **experimental** de un proveedor LLM externo con datos **sintéticos**. No es solución clínica desplegada.

### B.4 Limitación del modelo

Gemini no recibe Bundle FHIR y no se conecta a Epic, Oracle ni HAPI.

---

## 5. C — Parcial

### C.1 Supervisión humana

Existe la invariante `requiresHumanReview=true`. **No** hay HITL operativo: ni UI, ni rol médico, ni cola, ni aprobación/rechazo, ni auditoría de un revisor humano.

### C.2 Integración LLM

Gemini es real, pero solo para `SYN-076-001`. No es una plataforma general de procesamiento clínico con LLM.

### C.3 Lifecycle de modelos

Hay override `GEMINI_MODEL`. No hay estrategia de routing, fallback ni catálogo de modelos.

---

## 6. D — Planificado

No hay backlog aprobado en este documento.

Puede anotarse, sin comprometer task: integraciones de **otros** proveedores LLM no están implementadas.

OpenAI **no** es una Task futura comprometida. Solo: **E** — no implementado.

---

## 7. E — No encontrado / fuera de alcance

Frontend clínico; RBAC; tenancy; workflow HITL operativo; servidor FHIR propio de la app; consentimiento clínico real; IAM empresarial; RAG; MCP; LangGraph; memoria de agente; segundo proveedor LLM; OpenAI; fallback/router de modelos Gemini; recomendaciones, diagnóstico o tratamiento automatizados; MedicationRequest en Epic; v1 → Gemini.

**Tasks 057–073:** simulaciones / gates de laboratorio. No son IAM, consentimiento, RBAC, autorización clínica ni infraestructura de producción.

---

## 8. Invariantes técnicas

1. No enviar Bundle FHIR a un modelo.  
2. Python no consulta Epic, Oracle ni HAPI.  
3. No ampliar allowlist 042 por la integración LLM.  
4. No añadir MedicationRequest a Epic.  
5. No modificar campos clínicos de v1.  
6. `requiresHumanReview` permanece `true`.  
7. Java: `modelCalled=false`, `modelCallAuthorized=false`.  
8. `/internal/agent-context` no llama modelo.  
9. `/internal/experimental-summary` es el único camino LLM.  
10. Ese camino usa solo `SYN-076-001`.  
11. `LLM_EXPERIMENTAL_ENABLED` es `false` por defecto.  
12. 057–073 no son IAM/consentimiento real.  
13. No hay RAG, LangGraph, MCP, memoria ni OpenAI.

---

## 9. Diagrama (caminos separados)

```text
                 PRODUCTO A
           Java / FHIR Boundary
                    │
     ┌──────────────┴──────────────┐
     │                             │
 Epic / Oracle / HAPI          Snapshot
     │                             │
     └──────────────┬──────────────┘
                    ▼
          ModelBoundaryContract v1
                    │
                    ▼
              Task 074 consumer
                    │
                    ▼
         Task 075  X-Service-Token
         GET /api/model-boundary/v1


                 PRODUCTO B
              Python ai-service
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
/internal/agent-context   /internal/experimental-summary
          │                   │
          ▼                   ▼
    No model call        SYN-076-001 only
                              │
                              ▼
                        LLMProvider
                              │
                              ▼
                        GeminiProvider
                              │
                              ▼
                      Google Gemini API
```

v1 **no** alimenta a Gemini.

---

## 10. Tabla resumen

| Componente | Estado |
|---|---|
| Java FHIR boundary | A |
| Cliente HAPI FHIR R4 | A |
| SMART Auth Code + PKCE | A |
| Snapshot / allowlist 042 | A |
| RetentionCeiling N=5 | A |
| ModelBoundaryContract v1 | A |
| Task 074 consumer | A |
| Task 075 service auth | A |
| Python ai-service | A |
| Endpoint Gemini experimental | A |
| GeminiProvider / FakeLLMProvider | A |
| Fixture sintético | A |
| Alineación default 077 | A |
| Flag `requiresHumanReview` | C |
| Workflow HITL operativo | E |
| Apoyo a decisión clínica | E |
| RAG / MCP / LangGraph / memoria | E |
| OpenAI / segundo proveedor | E |
| IAM / RBAC / consentimiento real | E |
| Cumplimiento legal/regulatorio | E (no evaluado, no declarado) |

---

## 11. Referencias de código y docs

- `docs/tasks/TASK_074_*`, `TASK_075_*`, `TASK_076_*`, `TASK_077_*`
- `docs/adr/ADR-076-controlled-gemini-integration.md`
- `docs/fhir/model-boundary-contract-v1.md`
- `docs/progress/progress-log.md`
- `docs/ai-governance/llm-boundary-threats-and-controls.md` (fase B; sin cambio de capacidad)
- `services/ai-service/app/config.py` (`gemini-flash-latest`)
- `services/ai-service/app/experimental_fixture.py` (`SYN-076-001`)
