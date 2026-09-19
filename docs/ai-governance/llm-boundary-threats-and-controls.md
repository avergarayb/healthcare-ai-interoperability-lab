# Threat model y control baseline — boundary LLM experimental

**Fecha de corte:** 19 de septiembre de 2026  
**Fase:** B — seguridad de la integración LLM existente  
**Objeto:** `ai-service` puerto **8090** y su camino experimental Gemini (Tasks 076/077)  
**No es:** evaluación regulatoria, `risk-assessment.md`, ni declaración de cumplimiento.

Convención de estados (igual que [`laboratory-state.md`](laboratory-state.md)):

| Código | Significado |
|---|---|
| **A** | Implementado y comprobado en código (y, si se indica, en test o demo) |
| **B** | Documentado como decisión o límite; no es un control extra |
| **C** | Parcial: existe un control técnico, no un sistema completo |
| **D** | Fuera del recorte actual; no es backlog aprobado |
| **E** | No encontrado / fuera de alcance |

Esta fase **no cambia capacidades**. No hay Task de código. No hay rate limiting, rotación de secretos, IAM ni isolation de red nuevos.

---

## 1. Purpose

Hacer explícito qué amenazas cubre hoy el boundary Gemini, qué controles existen, qué riesgos residuales se aceptan en laboratorio, y qué no debe venderse como plataforma de seguridad.

Sirve para **aprendizaje** y para **consultoría honesta**: mostrar cómo se pone un LLM al lado de FHIR sin convertir el laboratorio local en un producto de seguridad de producción.

---

## 2. Scope

Dentro de alcance:

```text
Caller interno
     │
     │ X-Service-Token
     ▼
POST /internal/experimental-summary
     │
     ├── LLM_EXPERIMENTAL_ENABLED
     ├── SYN-076-001
     ├── validación de request
     └── metadata de gobernanza
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

Fuera del boundary LLM (permanecen fuera del camino de Gemini):

- FHIR / Epic / Oracle / HAPI FHIR
- `ModelBoundaryContract` v1
- `GET /api/model-boundary/v1`
- `GET /internal/agent-context`

El secret `MODEL_BOUNDARY_SERVICE_TOKEN` es el mismo que usa Java (Task 075). Eso no mete a Java en este threat model; solo registra que el token es compartido de laboratorio.

---

## 3. Assets

| Asset | Notas |
|---|---|
| Endpoint `POST /internal/experimental-summary` | Único camino LLM |
| Fixture `SYN-076-001` | Único input admitido |
| `MODEL_BOUNDARY_SERVICE_TOKEN` / `X-Service-Token` | Secret compartido de laboratorio |
| `GEMINI_API_KEY` | Clave del proveedor; no se loguea |
| `GEMINI_MODEL` | Default `gemini-flash-latest` (077); override, sin fallback |
| Cuota / coste Gemini | Recurso externo de pago o de cuota |
| Proceso `ai-service` | CPU, memoria, un worker local |
| Línea de log `experimental_llm_call` | Telemetría minimizada |
| Metadata `requiresHumanReview`, `modelCalled`, `status` | La pone la aplicación, no Gemini |

---

## 4. Trust boundaries

```text
[caller local] --token--> [ai-service :8090] --API key--> [Google Gemini API]
                                │
                                X  no hay camino a FHIR / v1 / Epic / Oracle / HAPI
```

Confianza actual (laboratorio, no producción):

1. Quien conoce el token y puede alcanzar `127.0.0.1:8090` se trata como caller de servicio.
2. El proceso confía en su propio fixture y en su propio schema de respuesta.
3. Gemini es un proveedor **no confiable** para metadata de gobernanza y para ejecutar acciones (no hay herramientas ni escritura FHIR).
4. El entorno (`.env` inyectado al proceso) es el almacén de secretos. Uvicorn **no** carga `.env` solo.

---

## 5. Existing controls

### 5.1 A — Implementado

| Control | Estado | Evidencia |
|---|---|---|
| Endpoint LLM único | A | `POST /internal/experimental-summary` |
| `X-Service-Token` | A | `authenticate()`; tests 401 |
| Fail-closed si el token configurado está vacío | A | `test_blank_configured_token_is_fail_closed` |
| `LLM_EXPERIMENTAL_ENABLED=false` por defecto | A | `config.py`; test 503 `DISABLED` |
| Fixture `SYN-076-001` exclusivo | A | igualdad canónica; `SYN-076-002` → 422 |
| Validación de request (campos extra, Bundle, token-like) | A | tests 422; Bundle no llega al proveedor |
| Timeout de proveedor 30 s | A | GeminiProvider; test timeout → 504 |
| `summary` ≤ 2000 caracteres | A | `MAX_SUMMARY_CHARS`; oversized → 502 |
| `LLMProvider` / `GeminiProvider` | A | aislamiento del SDK |
| `FakeLLMProvider` | A | tests |
| `requiresHumanReview=true` | A (flag) / C (HITL) | validador + test; Gemini no puede apagarlo |
| Semántica `modelCalled` | A | `true` solo si la invocación empezó |
| Logging técnico minimizado | A | allowlist de campos en `emit_audit` |
| API key y service token fuera de logs | A | `test_logs_do_not_contain_secrets_or_prompt` |
| Prompt y completion fuera de logs | A | mismo test |
| `GEMINI_MODEL` configurable | A | 077; sin fallback/router |
| Java / v1 fuera del camino LLM | A | architecture tests; 074 `modelCalled=false` |

Tests de 076 que **ya** consolidan estos controles (no se añaden tests en esta fase):

- token ausente / inválido / en blanco → 401, `provider.calls == 0`
- flag off → 503, no llama proveedor
- Bundle y `access_token` en body → 422
- timeout / 4xx / 5xx / malformado / vacío / oversized → `modelCalled=true`
- `FakeLLMProvider("unexpected")` no puede poner `requiresHumanReview=false`
- logs sin key, token, prompt ni summary

### 5.2 B — Documentado (límites, no controles nuevos)

- El endpoint es **experimental**.
- Solo se usa el fixture `SYN-076-001`.
- El secret compartido es de laboratorio, **no IAM**.
- `X-Service-Token` autentica al caller de servicio; **no** identifica usuarios.
- No hay RBAC, consentimiento real, HITL operativo ni autorización clínica.
- No hay aislamiento de red documentado como control.
- No hay rate limiting.
- El secret vive en `.env` y **no** hay rotación implementada.
- El entorno debe inyectarse al proceso (Uvicorn no carga `.env`).
- Gemini no recibe FHIR ni datos reales.

Estas frases son el material de consultoría: evitan vender el laboratorio como identidad, red o clínica.

---

## 6. C — Parcial

### C.1 Autenticación del endpoint

Existe `X-Service-Token` y fail-closed.  
**No** es IAM, identidad de usuario, RBAC, OAuth ni un directorio.

Cierre de fase: autenticación de servicio básica; identidad/autorización de usuario no existe. **B no las inventa.**

### C.2 Protección contra abuso

Barrera actual: token + feature flag + endpoint “internal” en host local.  
Falta: rate limiting y isolation de red como control documentado.

Cierre: hay autenticación; no hay capa específica contra abuso o agotamiento (cuota Gemini, CPU).

### C.3 Prompt injection

No hay usuario ni documento externo. El modelo recibe `SYN-076-001`, fijo en código.

El riesgo de *indirect prompt injection* por FHIR narrative, notas, docs o mensajes de usuario es **bajo en este recorte**. No está “resuelto en general”.

Cierre: la superficie actual está reducida por diseño. No se añade framework de sanitización ni RAG para un problema que este boundary no tiene.

### C.4 Output validation

Hay schema, tope de 2000 caracteres, rechazo si el texto intenta setear `requiresHumanReview` / `modelCalled`, y el flag lo pone la app.

No hay clasificador semántico del contenido de `summary`. Gemini puede escribir texto no deseado **dentro** de ese campo; ese texto **no** ejecuta acciones ni escribe FHIR.

Cierre: control estructural. Limitación documentable; no justifica código en B.

---

## 7. D — Planificado

No hay backlog en este documento.

Controles para datos no sintéticos, otra exposición de red o uso clínico exigirían una **revisión independiente** antes de ampliar el boundary. Eso no es una lista de Tasks.

---

## 8. E — No encontrado / fuera de alcance

Rate limiting; network isolation como control; secret rotation; secret manager; IAM; RBAC; usuario autenticado; consentimiento; HITL operativo; clasificación semántica de output; detector general de prompt injection; DLP; SIEM; WAF; API gateway delante del POST; segundo proveedor; OpenAI; fallback; router; retries.

Que falten **no** implica que B deba implementarlas.

---

## 9. Threats

### T1 — Abuso del POST `/internal/experimental-summary`

Un caller que conozca el token puede repetir el POST: cuota Gemini, coste, CPU, latencia, saturación del proceso.

| | |
|---|---|
| Controles | Token, feature flag, fixture fijo, timeout 30 s |
| Hueco | Sin rate limiting |
| Estado | C |
| Tratamiento | Documentar como riesgo residual. No implementar rate limit en B (cambiaría superficie). Reevaluar si el endpoint deja de ser local/interno. |

### T2 — Compromiso del service token

El token compartido abre el endpoint. Vive en `.env`. No hay rotación ni identidad por caller.

| | |
|---|---|
| Controles | Token obligatorio, fail-closed, vacío → rechazo, token no se loguea |
| Huecos | Rotación, secret manager, identidad individualizada |
| Estado | C |
| Tratamiento | Documentar. El token es autenticación de servicio de laboratorio, no gestión de identidad de producción. Sin código de rotación en B. |

### T3 — Exposición accidental del secret

`MODEL_BOUNDARY_SERVICE_TOKEN` o `GEMINI_API_KEY` en logs, Git, errores, entorno visible o fuente.

| | |
|---|---|
| Controles | Env vars; audit line sin secretos; `.env` no se commitea (gitignore) |
| Hueco | La gestión sigue dependiendo del entorno de ejecución |
| Estado | C |
| Tratamiento | Ya hay test de logs. No hay funcionalidad nueva. El operador no debe commitear `.env`. |

### T4 — Prompt injection

Para inyectar habría que alterar lo que se envía a Gemini. Hoy el fixture es fijo y no viene de Epic, Oracle, HAPI, FHIR, usuario ni documento.

| | |
|---|---|
| Riesgo actual | Bajo en este recorte |
| Control | Contenido controlado + sin fuentes externas |
| Estado | C (diseño, no framework general) |
| Tratamiento | Documentar. No añadir sanitización genérica ni “prompt injection framework”. |

### T5 — Output malicioso o no esperado

Gemini puede devolver texto inesperado. `summary` no ejecuta comandos, no llama herramientas, no modifica FHIR/Epic/Oracle, no toma decisiones. `requiresHumanReview=true` lo fija la app.

| | |
|---|---|
| Controles | Schema, tope de caracteres, rechazo de metadata inyectada, flag de la app |
| Estado | C (estructural, no semántico) |
| Tratamiento | Tests 076 ya cubren que un provider falso no cambia `requiresHumanReview` / `modelCalled` / `status` gobernado. Sin clasificador. |

### T6 — Timeout Gemini

Si la invocación empezó y vence el límite: HTTP 504, `status=PROVIDER_ERROR`, `modelCalled=true`.

| | |
|---|---|
| Control | Timeout 30 s + semántica de `modelCalled` |
| Estado | A |
| Tratamiento | Cubierto. `test_provider_timeout_is_504_and_model_called_true`. |

### T7 — Error del proveedor

HTTP 4xx/5xx, respuesta inválida, error de SDK, vacío, oversized. La app normaliza. **No hay fallback.** El 503 live del 19/09 (`gemini-flash-latest` por capacidad) no justifica retries.

| | |
|---|---|
| Control | `GeminiProvider` + `apply_provider_generation` |
| Estado | A |
| Tratamiento | Tests 076. No implementar retry/fallback. |

### T8 — Abuso económico

Separado de disponibilidad: una clave válida + token permiten N llamadas a Gemini. El fixture y el flag reducen el acceso accidental; no limitan cantidad.

| | |
|---|---|
| Controles | Token + flag + fixture |
| Hueco | Sin tope de llamadas / billing |
| Estado | E/C |
| Tratamiento | Riesgo residual de laboratorio. Sin lógica de billing en 076/077. |

### T9 — Fuga por logs

Registrar request, prompt, completion, API key o token.

| | |
|---|---|
| Control | Allowlist: `correlationId`, `useCase`, `promptVersion`, `provider`, `model`, `durationMs`, `status`, `modelCalled` |
| Estado | A (línea de audit) / C (depende de que nadie loguee por otro lado) |
| Tratamiento | `test_logs_do_not_contain_secrets_or_prompt`. Control útil en consultoría: minimización deliberada del telemetry boundary. |

---

## 10. Control mapping

| Amenaza | Control actual | Estado | Acción en B |
|---|---|---|---|
| T1 Abuso del POST | Token + flag | C | Documentar |
| T2 Token comprometido | Secret compartido | C | Documentar |
| T3 Exposición de secrets | Env + no logging | C | Documentar (tests 076) |
| T4 Prompt injection | Fixture fijo | C | Documentar |
| T5 Output inesperado | Schema + metadata | C | Tests 076 |
| T6 Timeout Gemini | 30 s | A | Mantener |
| T7 Error Gemini | Normalización, sin fallback | A | Tests 076 |
| T8 Cost abuse | Sin rate limit | E/C | Residual |
| T9 Fuga por logs | Allowlist de campos | A/C | Tests 076 |
| Isolation de red | No documentada como control | E | Ausencia |
| IAM / RBAC | No existe | E | Fuera de alcance |

---

## 11. Residual risks

Aceptados **deliberadamente** en este laboratorio:

1. Quien tenga el token y alcance el puerto puede disparar Gemini (T1, T8).
2. Un solo secret compartido, sin rotación (T2).
3. Secretos en el entorno del operador, no en un secret manager (T3).
4. Sin defensa general de prompt injection más allá del fixture fijo (T4).
5. El texto de `summary` no se clasifica semánticamente (T5).
6. Sin isolation de red formal: “internal” es convención de path + bind local, no un control de red.
7. Tasks 057–073 no son IAM ni consentimiento reales.

Si cambia cualquiera de estas premisas (exponer el puerto, datos no sintéticos, varios callers, uso clínico), este documento **deja de aplicar** y hay que reabrir el modelo.

---

## 12. A–E status (resumen)

Ver secciones 5–8. Compacto:

| Tema | Estado |
|---|---|
| Controles 076/077 listados en §5.1 | A |
| Límites honestos de laboratorio (§5.2) | B |
| Auth de servicio vs IAM | C |
| Abuso / coste / isolation | C o E |
| Prompt injection general / output semántico | C |
| Controles para datos reales o red distinta | D (revisión futura, no task) |
| Rate limit, rotación, IAM, WAF, segundo proveedor | E |

---

## 13. Explicit non-goals

B **no** introduce:

- rate limiting, secret rotation, IAM, RBAC, tenancy
- frontend, HITL operativo, consentimiento
- RAG, MCP, LangGraph, memoria, agentes, herramientas
- OpenAI u otro proveedor, fallback, router, retries
- más fixtures, v1 → Gemini, Bundle → Gemini
- ampliar allowlist 042, MedicationRequest en Epic
- cambiar campos clínicos de v1 o apagar `requiresHumanReview`
- `risk-assessment.md`, `regulatory-context.md`, ni afirmaciones de DS 115-2025-PCM, Ley 31814, HIPAA o GDPR

---

## 14. Conclusion

La fase B se cierra **solo con este documento**.

| Entregable | Decisión |
|---|---|
| Documentación | Sí — este archivo |
| Tests adicionales | No. Los de 076 ya cubren token, fixture, timeout, metadata y logs |
| Código nuevo | No |
| Task 078 de features | No |

El laboratorio no gana capacidad. Queda explícito cómo se protege el boundary Gemini, qué cubre y qué queda fuera a propósito.

Siguiente descongelación (fuera de B): solo si hay un problema nuevo que justifique código o un contrato distinto. No “aprovechar” Gemini para acercar FHIR al modelo.
