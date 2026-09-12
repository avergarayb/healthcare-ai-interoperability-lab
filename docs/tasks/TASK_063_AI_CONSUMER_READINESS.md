# Task 063 — AI Consumer Readiness Evidence and Handoff Boundary

## 1. Identificación

- **Proyecto:** `healthcare-ai-interoperability-lab`
- **Servicio actual:** `fhir-integration-service`
- **Stack:** Java 21, Spring Boot 3.5.16, HAPI FHIR 8.10.0
- **Paquete raíz:** `lab.healthcare.fhir`
- **Puerto:** `8081`
- **Base branch:** `feature/ai-consumer-policy`
- **Base commit:** `4354b7d`
- **Base message:** `feat: add ai consumer policy`
- **Suggested branch:** `feature/ai-consumer-readiness`
- **Suggested commit:** `feat: add ai consumer readiness`

---

# WHAT

Implementar una nueva frontera interna de **readiness y handoff controlado** después de la política sintética de consumidores de la Task 062.

La tarea debe transformar el resultado de la política de consumidor en una evidencia técnica explícita que indique si el contrato está:

- Listo únicamente para una futura integración.
- Bloqueado.
- Pendiente de revisión humana.
- No apto para handoff.

La implementación debe permanecer completamente determinística y aislada.

**No debe llamar a un modelo, enviar el contrato, ejecutar dispatch ni comunicarse con un futuro `ai-service`.**

La Task 063 no implementa autenticación real, autorización real ni ejecución de IA. Solo formaliza la última frontera de preparación antes de una futura etapa de integración.

---

# WHY

La Task 062 produce:

```text
ALLOWED_FOR_FUTURE_CONSUMPTION
REJECTED
HUMAN_REVIEW_REQUIRED
```

Sin embargo, `ALLOWED_FOR_FUTURE_CONSUMPTION` no significa que el contrato pueda enviarse o que un modelo pueda ejecutarse.

Se necesita una capa explícita que distinga:

1. Política sintética favorable.
2. Readiness técnico.
3. Handoff autorizado.
4. Dispatch real.
5. Ejecución del modelo.

La Task 063 debe dejar documentado y observable que:

```text
ALLOWED_FOR_FUTURE_CONSUMPTION
    ≠
HANDOFF_AUTHORIZED
```

y que:

```text
READY_FOR_FUTURE_HANDOFF
    ≠
DISPATCHED
```

La tarea también debe evitar que una futura implementación confunda la preparación técnica con autorización de ejecución clínica o de modelos.

---

# CONCEPT

## 1. Cadena de estados

La cadena conceptual debe quedar así:

```text
FHIR / interoperabilidad
        ↓
Clinical Snapshot
        ↓
Controlled Projection
        ↓
Model Boundary
        ↓
AgentStub
        ↓
Deterministic Agent
        ↓
AI Boundary
        ↓
First AI Component
        ↓
AI Execution Gate
        ↓
AI Consumer Contract
        ↓
AI Consumer Policy
        ↓
AI Consumer Readiness
        ↓
Futura autenticación/autorización real
        ↓
Futuro handoff real
        ↓
Futuro modelo
```

La Task 063 implementa únicamente:

```text
AiConsumerPolicyResult
        ↓
AiConsumerReadiness
```

---

## 2. Diferencias obligatorias

| Concepto | Significado |
|---|---|
| `ALLOWED_FOR_FUTURE_CONSUMPTION` | La política sintética no encontró un bloqueo inmediato para lectura futura |
| `READY_FOR_FUTURE_HANDOFF` | La evidencia técnica está completa para una futura etapa, sin autorizar envío |
| `HANDOFF_AUTHORIZED` | No debe existir en esta tarea |
| `DISPATCHED` | No debe existir en esta tarea |
| `MODEL_CALL_AUTHORIZED` | Debe permanecer en `false` |
| `MODEL_CALLED` | Debe permanecer en `false` |
| `REQUIRES_HUMAN_REVIEW` | Debe permanecer en `true` |
| `NOT_EXECUTED` | Debe permanecer sin cambios |
| `NOT_DISPATCHED` | Debe permanecer sin cambios |

---

# HOW

## 1. Inspección inicial obligatoria

Antes de modificar código, Cursor debe inspeccionar:

- `AiConsumerPolicyResult`.
- `AiConsumerPolicyDecision`.
- `AiConsumerPolicy`.
- `AiConsumerContract`.
- `AiExecutionDecision`.
- `FirstAiResult`.
- `AiBoundaryResult`.
- Documentación de las Tasks 060, 061 y 062.
- Convenciones actuales de paquetes, records, enums y pruebas.
- Endpoints de laboratorio existentes.

No asumir nombres de campos que no existan. Adaptar la implementación a las clases reales del repositorio.

---

## 2. Paquete sugerido

Crear un paquete separado:

```text
lab.healthcare.fhir.aiconsumerreadiness
```

La implementación no debe ubicarse en:

```text
lab.healthcare.fhir
```

directamente ni dentro de:

```text
fhir
vendor
epic
oracle
agent
pipeline
aiboundary
firstai
aigateway
aiconsumer
aiconsumerpolicy
```

El nombre puede ajustarse a las convenciones reales del proyecto, pero debe conservar una frontera arquitectónica clara.

---

## 3. Clases sugeridas

Las siguientes clases son sugeridas:

```text
AiConsumerReadiness
AiConsumerReadinessInput
AiConsumerReadinessResult
AiConsumerReadinessStatus
AiConsumerReadinessReasonCodes
AiConsumerReadinessValidator
AiConsumerReadinessMapper
```

No crear todas las clases si una estructura más simple resulta suficiente.

La lógica debe ser clara, pequeña y determinística.

---

# 4. Entrada permitida

La entrada principal debe ser:

```text
AiConsumerPolicyResult
```

Opcionalmente puede recibirse también:

```text
AiConsumerContract
```

pero únicamente si resulta estrictamente necesario para verificar estados de seguridad.

La entrada nunca debe incluir:

- FHIR crudo.
- `Bundle`.
- Recursos clínicos.
- `Patient`.
- `Condition`.
- `Observation`.
- `DiagnosticReport`.
- `MedicationRequest`.
- Tokens.
- Secrets.
- Patient IDs.
- DTOs de Epic.
- DTOs de Oracle.
- Prompts.
- Respuestas de LLM.
- Valores clínicos.

La Task 063 no debe volver a procesar datos clínicos ni volver a ejecutar el pipeline.

---

# 5. Readiness status

Definir un conjunto cerrado de estados:

```text
READY_FOR_FUTURE_HANDOFF
BLOCKED
HUMAN_REVIEW_REQUIRED
NOT_READY
```

No agregar estados que impliquen envío o ejecución, como:

```text
HANDOFF_AUTHORIZED
DISPATCHED
MODEL_AUTHORIZED
MODEL_EXECUTED
CLINICAL_OUTPUT_GENERATED
```

---

# 6. Reglas de evaluación

## 6.1. Readiness permitido

La entrada puede producir:

```text
READY_FOR_FUTURE_HANDOFF
```

únicamente si se cumplen todas las condiciones:

- El resultado de la política existe.
- La decisión de política es exactamente:

  ```text
  ALLOWED_FOR_FUTURE_CONSUMPTION
  ```

- El contrato es `v1`.
- La operación es `READ_CONTRACT`.
- El scope es `ai.contract.read`.
- El consumidor sintético está autenticado.
- El consumidor sintético está autorizado.
- El contexto de tenant está presente.
- El contrato no está bloqueado.
- El contrato no está marcado como no elegible.
- No existe autorización prematura de modelo.
- `modelCallAuthorized == false`.
- `modelCalled == false`.
- `processingStatus == NOT_EXECUTED`.
- `dispatchStatus == NOT_DISPATCHED`.
- `requiresHumanReview == true`.

La decisión de readiness debe aclarar que se trata de una preparación futura y no de una autorización operativa.

---

## 6.2. Política rechazada

Si la política devuelve:

```text
REJECTED
```

el readiness debe ser:

```text
BLOCKED
```

Código sugerido:

```text
POLICY_REJECTED
```

No se debe crear ningún resultado clínico ni ejecutar ningún modelo.

---

## 6.3. Revisión humana requerida

Si la política devuelve:

```text
HUMAN_REVIEW_REQUIRED
```

el readiness debe ser:

```text
HUMAN_REVIEW_REQUIRED
```

Código sugerido:

```text
POLICY_REQUIRES_HUMAN_REVIEW
```

No se debe convertir la revisión humana en un estado `READY_FOR_FUTURE_HANDOFF`.

---

## 6.4. Resultado de política ausente

Si el resultado de la política es `null`, vacío o inválido, producir:

```text
NOT_READY
```

Código sugerido:

```text
POLICY_RESULT_MISSING
```

---

## 6.5. Estado inconsistente

Si la política indica:

```text
ALLOWED_FOR_FUTURE_CONSUMPTION
```

pero alguno de los estados de seguridad indica:

```text
modelCallAuthorized == true
modelCalled == true
processingStatus != NOT_EXECUTED
dispatchStatus != NOT_DISPATCHED
```

el resultado debe ser:

```text
BLOCKED
```

Código sugerido:

```text
INCONSISTENT_EXECUTION_STATE
```

La Task 063 no debe corregir silenciosamente estos estados. Debe detectarlos y bloquear el readiness.

---

## 6.6. Revisión humana apagada

Si:

```text
requiresHumanReview == false
```

el resultado no debe ser `READY_FOR_FUTURE_HANDOFF`.

Debe producir:

```text
HUMAN_REVIEW_REQUIRED
```

Código sugerido:

```text
HUMAN_REVIEW_FLAG_MISSING
```

La Task 063 no puede apagar ni modificar el indicador de revisión humana.

---

## 6.7. Contrato incompatible

Si la versión del contrato no es:

```text
v1
```

producir:

```text
BLOCKED
```

Código sugerido:

```text
CONTRACT_VERSION_NOT_SUPPORTED
```

---

## 6.8. Operación incompatible

Si la operación no es:

```text
READ_CONTRACT
```

producir:

```text
BLOCKED
```

Código sugerido:

```text
OPERATION_NOT_SUPPORTED_FOR_READINESS
```

---

## 6.9. Scope incompatible

Si el scope no es:

```text
ai.contract.read
```

producir:

```text
BLOCKED
```

Código sugerido:

```text
SCOPE_NOT_SUPPORTED_FOR_READINESS
```

---

# 7. Resultado esperado

El resultado de readiness debe incluir, como mínimo:

```text
readinessStatus
reasonCode
policyDecision
contractVersion
requestedOperation
requestedScope
consumerType
modelCallAuthorized
modelCalled
processingStatus
dispatchStatus
requiresHumanReview
handoffAuthorized
dispatchPerformed
```

Los dos últimos campos deben representar explícitamente:

```text
handoffAuthorized = false
dispatchPerformed = false
```

Estos campos no deben poder cambiar a `true` dentro de la Task 063.

Si el repositorio utiliza otros nombres, conservar las convenciones existentes, pero mantener el mismo significado.

---

# 8. Invariantes de seguridad

La implementación debe garantizar siempre:

```text
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
requiresHumanReview = true
handoffAuthorized = false
dispatchPerformed = false
```

Estas invariantes deben mantenerse incluso cuando:

```text
readinessStatus = READY_FOR_FUTURE_HANDOFF
```

El estado permitido significa únicamente:

> La información técnica está preparada para una futura etapa de integración, pero no existe autorización real, envío ni ejecución.

---

# 9. API de laboratorio

Se puede agregar un endpoint de laboratorio únicamente si sigue las convenciones existentes.

Endpoint sugerido:

```text
GET /lab/ai-consumer-readiness
```

o:

```text
GET /api/ai-consumer-readiness/v1
```

El endpoint debe:

- Usar únicamente datos sintéticos.
- Consumir la política sintética existente.
- No recibir Patient IDs.
- No recibir tokens.
- No recibir FHIR JSON.
- No invocar Epic.
- No invocar Oracle.
- No invocar HAPI FHIR.
- No ejecutar modelos.
- No realizar dispatch.

El endpoint no debe presentarse como una API pública de autorización.

Si el repositorio ya dispone de endpoints de laboratorio para Tasks 061–062, reutilizar el patrón existente sin duplicar lógica innecesariamente.

---

# 10. Observabilidad segura

Los logs, si se agregan, solo pueden incluir:

```text
readinessStatus
reasonCode
policyDecision
contractVersion
requestedOperation
requestedScope
consumerType
modelCallAuthorized
modelCalled
processingStatus
dispatchStatus
requiresHumanReview
handoffAuthorized
dispatchPerformed
```

No registrar:

- Tokens.
- Secrets.
- Patient IDs.
- FHIR crudo.
- Bundles.
- Datos clínicos.
- Prompts.
- Respuestas de modelos.
- URLs privadas.
- Credenciales.
- Identificadores reales de consumidores.

---

# 11. Fronteras arquitectónicas

La dependencia permitida debe ser:

```text
aiconsumerreadiness -> aiconsumerpolicy
```

Opcionalmente:

```text
aiconsumerreadiness -> aiconsumer
```

No debe existir dependencia desde `aiconsumerreadiness` hacia:

```text
FhirService
RoutingService
vendor.*
Epic
Oracle
HAPI FHIR
SMART
OAuth internals
Bundle
FHIR resources
ClinicalSnapshot
ControlledProjection
Pipeline
AgentStub
DeterministicAgent
AiBoundary
FirstAi
AiExecutionGate
HTTP clients
RabbitMQ
AI SDKs
```

La nueva frontera no debe ser importada por:

```text
FhirService
vendor.*
Epic*
Oracle*
pipeline
agent
aiboundary
firstai
aigateway
```

La Task 063 debe ser consumidora de la política, no parte del pipeline clínico.

---

# 12. Superficies ciegas

La implementación debe permanecer ciega a:

- Proveedores FHIR.
- Epic.
- Oracle Health.
- SMART.
- OAuth.
- Tokens.
- Client IDs.
- Client secrets.
- Patient IDs.
- Recursos clínicos.
- Bundles.
- URLs de sandbox.
- DTOs vendor-specific.
- Valores clínicos.
- Prompts.
- Respuestas de LLM.
- Diagnósticos.
- Prescripciones.
- Recomendaciones clínicas.

No implementar condicionales:

```text
if Epic
if Oracle
if Patient
if MedicationRequest
if FHIR resourceType
```

---

# 13. Documentación requerida

Crear o actualizar:

```text
docs/fhir/ai-consumer-readiness.md
```

Aunque la ruta esté dentro de `docs/fhir`, el contenido debe aclarar que la Task 063 no procesa FHIR y que la ubicación es únicamente por organización documental del laboratorio.

La documentación debe explicar:

- Propósito de readiness.
- Diferencia entre policy y readiness.
- Diferencia entre readiness y autorización.
- Diferencia entre readiness y dispatch.
- Estados posibles.
- Códigos de razón.
- Invariantes de seguridad.
- Entrada permitida.
- Datos que no deben entrar.
- Fronteras arquitectónicas.
- Ausencia de autenticación real.
- Ausencia de autorización real.
- Ausencia de handoff real.
- Ausencia de modelo.
- Próximos pasos previstos para Tasks 064+.

---

# 14. Pruebas requeridas

Crear pruebas unitarias determinísticas.

## Caso A — Política permitida

Entrada:

```text
policyDecision = ALLOWED_FOR_FUTURE_CONSUMPTION
```

Con todos los estados de seguridad correctos.

Resultado esperado:

```text
readinessStatus = READY_FOR_FUTURE_HANDOFF
handoffAuthorized = false
dispatchPerformed = false
```

---

## Caso B — Política rechazada

Entrada:

```text
policyDecision = REJECTED
```

Resultado esperado:

```text
readinessStatus = BLOCKED
reasonCode = POLICY_REJECTED
```

---

## Caso C — Revisión humana requerida

Entrada:

```text
policyDecision = HUMAN_REVIEW_REQUIRED
```

Resultado esperado:

```text
readinessStatus = HUMAN_REVIEW_REQUIRED
```

---

## Caso D — Resultado de política ausente

Entrada:

```text
policyResult = null
```

Resultado esperado:

```text
readinessStatus = NOT_READY
reasonCode = POLICY_RESULT_MISSING
```

---

## Caso E — Autorización prematura

Entrada:

```text
modelCallAuthorized = true
```

Resultado esperado:

```text
readinessStatus = BLOCKED
reasonCode = INCONSISTENT_EXECUTION_STATE
```

---

## Caso F — Modelo ejecutado

Entrada:

```text
modelCalled = true
```

Resultado esperado:

```text
readinessStatus = BLOCKED
```

---

## Caso G — Processing status incorrecto

Entrada:

```text
processingStatus != NOT_EXECUTED
```

Resultado esperado:

```text
readinessStatus = BLOCKED
```

---

## Caso H — Dispatch realizado

Entrada:

```text
dispatchStatus = DISPATCHED
```

Resultado esperado:

```text
readinessStatus = BLOCKED
```

---

## Caso I — Revisión humana desactivada

Entrada:

```text
requiresHumanReview = false
```

Resultado esperado:

```text
readinessStatus = HUMAN_REVIEW_REQUIRED
reasonCode = HUMAN_REVIEW_FLAG_MISSING
```

---

## Caso J — Versión incompatible

Entrada:

```text
contractVersion != v1
```

Resultado esperado:

```text
readinessStatus = BLOCKED
reasonCode = CONTRACT_VERSION_NOT_SUPPORTED
```

---

## Caso K — Operación incompatible

Entrada:

```text
requestedOperation != READ_CONTRACT
```

Resultado esperado:

```text
readinessStatus = BLOCKED
```

---

## Caso L — Scope incompatible

Entrada:

```text
requestedScope != ai.contract.read
```

Resultado esperado:

```text
readinessStatus = BLOCKED
```

---

## Caso M — No se generan datos clínicos

Las pruebas no deben incluir:

- FHIR JSON.
- Bundles.
- Patient IDs.
- Valores clínicos.
- Tokens.
- Secrets.
- Prompts.
- Respuestas de LLM.

---

## Caso N — No regresión

Verificar que la implementación no rompa:

- Tasks 054–062.
- `AiConsumerContract`.
- `AiConsumerPolicy`.
- `AiExecutionDecision`.
- Endpoints de laboratorio existentes.
- Contratos de estados de seguridad.

---

# 15. Compatibilidad con el estado actual

La Task 063 debe conservar estos valores:

```text
aiConsumerPolicy = ALLOWED_FOR_FUTURE_CONSUMPTION
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
requiresHumanReview = true
```

Cuando la política sea favorable, el nuevo resultado podrá mostrar:

```text
readinessStatus = READY_FOR_FUTURE_HANDOFF
```

pero nunca:

```text
handoffAuthorized = true
dispatchPerformed = true
```

---

# 16. Fuera de alcance

No implementar:

- LLM real.
- OpenAI.
- Azure OpenAI.
- Gemini.
- Claude.
- Otro proveedor de modelos.
- `ai-service` Python.
- Cliente HTTP.
- WebClient.
- Feign.
- OAuth2/OIDC real.
- JWT real.
- SMART.
- PKCE.
- Registro real de consumidores.
- Gestión de tokens.
- RAG.
- Embeddings.
- Vector DB.
- LangChain.
- LangGraph.
- Memoria conversacional.
- Diagnóstico.
- Prescripción.
- Recomendaciones clínicas.
- Escritura en FHIR.
- Actualización de `Patient`.
- Creación de `MedicationRequest`.
- Epic.
- Oracle Health.
- HAPI FHIR.
- RabbitMQ.
- Webhooks.
- Retries.
- DLQ.
- Dispatch.
- Handoff real.
- Ampliación de allowlist 042.
- Incorporación de `MedicationRequest` para Epic.
- Cambios en campos clínicos de `AiConsumerContract v1`.
- Modificación de `.env`.
- Registro de tokens, Patient IDs o FHIR crudo.

---

# 17. Definition of Done

La Task 063 se considera terminada cuando:

- Existe una frontera de readiness separada.
- Consume `AiConsumerPolicyResult` o `AiConsumerContract`.
- No consume FHIR crudo.
- No consume Bundles.
- No consume DTOs vendor-specific.
- No consume tokens reales.
- No consume Patient IDs.
- Distingue política permitida, rechazo y revisión humana.
- Produce estados de readiness cerrados.
- Diferencia readiness de autorización.
- Diferencia readiness de dispatch.
- `handoffAuthorized` permanece en `false`.
- `dispatchPerformed` permanece en `false`.
- `modelCallAuthorized` permanece en `false`.
- `modelCalled` permanece en `false`.
- `processingStatus` permanece en `NOT_EXECUTED`.
- `dispatchStatus` permanece en `NOT_DISPATCHED`.
- `requiresHumanReview` permanece en `true`.
- Detecta estados inconsistentes.
- Bloquea autorización prematura.
- No ejecuta modelos.
- No realiza llamadas HTTP.
- No incorpora Epic.
- No incorpora Oracle.
- No modifica `FhirService`.
- No amplía la allowlist 042.
- Las pruebas unitarias pasan.
- Las pruebas de regresión pasan.
- La documentación queda actualizada.
- `.env` permanece intacto.
- El diff contiene únicamente cambios de la Task 063.

---

# 18. Entregables

1. Implementación de la frontera `aiconsumerreadiness`.
2. DTOs, records o enums internos necesarios.
3. Estados de readiness.
4. Códigos de razón.
5. Validaciones de invariantes.
6. Pruebas unitarias.
7. Endpoint de laboratorio opcional, si sigue el patrón existente.
8. Documentación técnica.
9. Evidencia de `mvn test`.
10. Resumen de archivos creados y modificados.
11. Confirmación de que no se agregaron integraciones externas.
12. Confirmación de que `.env` no se modificó.

---

# 19. Commit y rama sugeridos

```text
Branch:
feature/ai-consumer-readiness
```

```text
Commit:
feat: add ai consumer readiness
```

No realizar push automáticamente.

---

# 20. Instrucción final para Cursor

Implementa la Task 063 en el repositorio actual, respetando estrictamente las fronteras arquitectónicas existentes.

Antes de modificar código:

1. Inspecciona `AiConsumerPolicyResult`.
2. Revisa `AiConsumerContract`.
3. Revisa las Tasks 060, 061 y 062.
4. Identifica los estados reales utilizados por el proyecto.
5. Identifica las convenciones de paquetes, records, enums, servicios y pruebas.
6. No inventes campos ni contratos incompatibles.
7. No modifiques el pipeline FHIR.
8. No modifiques `FhirService`.
9. No agregues proveedores ni clientes externos.

Durante la implementación:

1. Mantén la lógica determinística.
2. Consume únicamente el resultado de la política o el contrato interno.
3. No proceses FHIR crudo.
4. No uses Patient IDs.
5. No uses tokens ni secrets.
6. No ejecutes modelos.
7. No realices dispatch.
8. No autorices handoff real.
9. Mantén `requiresHumanReview=true`.
10. Mantén todos los estados de ejecución en valores no ejecutados.

Después de implementar:

1. Ejecuta pruebas unitarias.
2. Ejecuta `mvn test`.
3. Verifica la ausencia de llamadas HTTP.
4. Verifica la ausencia de SDKs de IA.
5. Verifica la ausencia de tokens y secretos.
6. Verifica que `.env` no cambió.
7. Revisa el diff.
8. Actualiza `docs/fhir/ai-consumer-readiness.md`.
9. Confirma que no se amplió la allowlist 042.
10. Entrega:
   - Archivos creados.
   - Archivos modificados.
   - Pruebas ejecutadas.
   - Resultado de pruebas.
   - Estados de readiness.
   - Invariantes verificadas.
   - Commit sugerido.
   - Riesgos o decisiones pendientes para la Task 064+.
