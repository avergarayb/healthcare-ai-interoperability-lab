# Task 061 — AI Consumer Contract v1 y política de entrega segura

## Identificación

- **Proyecto:** `healthcare-ai-interoperability-lab`
- **Servicio actual:** `fhir-integration-service`
- **Stack:** Java 21, Spring Boot 3.5.16, HAPI FHIR 8.10.0
- **Paquete raíz:** `lab.healthcare.fhir`
- **Puerto:** `8081`
- **Rama base:** `feature/ai-execution-gate`
- **Commit base:** `2e62344`
- **Mensaje base:** `feat: add ai execution gate`
- **Rama sugerida:** `feature/ai-consumer-contract`
- **Commit sugerido:** `feat: add ai consumer contract`

---

# WHAT

Diseñar e implementar un **contrato interno de consumo para un futuro `ai-service`**, basado exclusivamente en los resultados controlados de las tareas 058–060.

La Tarea 061 no debe ejecutar IA, llamar a un modelo ni realizar conexiones externas.

Debe establecer una frontera explícita entre:

```text
AiExecutionDecision
        ↓
AI Consumer Contract v1
        ↓
Futuro ai-service
```

El contrato debe representar una **posible entrega futura**, no una autorización ni una ejecución real.

Valores obligatorios en esta fase:

```text
modelCalled=false
modelCallAuthorized=false
processingStatus=NOT_EXECUTED
requiresHumanReview=true
dispatchStatus=NOT_DISPATCHED
```

La implementación debe dejar claro que:

```text
ELIGIBLE_BUT_NOT_AUTHORIZED ≠ autorización
```

y que:

```text
contrato preparado ≠ solicitud enviada
```

---

# WHY

La Tarea 060 creó una puerta de ejecución que diferencia:

- Entrada preparada.
- Entrada técnicamente elegible.
- Autorización para IA.
- Ejecución real.

La Tarea 061 debe crear el contrato que un futuro `ai-service` podría consumir sin conocer:

- FHIR.
- HAPI FHIR.
- Epic.
- Oracle Health.
- Bundles.
- DTOs de proveedores.
- SMART PKCE.
- Tokens.
- Detalles internos del pipeline.
- Implementación del agente determinístico.

El contrato debe ser estable, mínimo y seguro.

No debe convertirse todavía en:

- Un endpoint público para cualquier agente.
- Un mecanismo de autenticación.
- Un canal de envío real.
- Una integración con OpenAI.
- Un contrato clínico de diagnóstico.

---

# CONCEPT

## 1. Contrato de consumo

El contrato define qué información mínima podría recibir un futuro componente de IA.

Debe contener únicamente metadatos y estados controlados, por ejemplo:

```text
contractVersion
contractStatus
correlationId, si ya existe
pipelineStatus
clinicalDataAvailable
agentDecision
firstAiComponentStatus
executionDecision
requiresHumanReview
modelCallAuthorized
modelCalled
processingStatus
dispatchStatus
reasonCodes
warnings
medicationRequestsStatus
```

Campos opcionales:

```text
createdAt
sourceComponent
```

Solo agregarlos si ya existe un patrón seguro y no generan datos sensibles.

No debe transportar:

- FHIR JSON.
- `Bundle`.
- Recursos clínicos completos.
- Valores de `Patient`.
- Valores de `Condition`.
- Valores de `Observation`.
- Valores de `DiagnosticReport`.
- Patient IDs.
- Tokens.
- Client IDs.
- Client secrets.
- Headers de autorización.
- DTOs de Epic u Oracle.
- Prompts.
- Respuestas de modelos.

---

## 2. Preparación no significa entrega

Deben distinguirse estos estados:

```text
PREPARED       = el componente aislado recibió la entrada
ELIGIBLE       = la puerta considera que la entrada es técnicamente candidata
CONTRACT_READY = existe un contrato controlado
DISPATCHED     = el contrato fue enviado a otro servicio
EXECUTED       = un modelo fue llamado
```

En la Tarea 061:

```text
CONTRACT_READY = posible
DISPATCHED     = false
EXECUTED       = false
```

No se debe implementar envío real a un `ai-service`.

---

## 3. Cualquier agente no puede consumir el contrato

La Tarea 061 no implementará todavía autenticación externa, pero debe documentar que el futuro consumo requerirá:

- Identidad del consumidor.
- Autenticación.
- Autorización.
- Scopes.
- Política de tenant.
- Operación permitida.
- Validación de contrato.
- Política de datos.
- Auditoría segura.

Por tanto, el contrato no debe exponerse como una API pública sin protección.

---

# HOW

## 1. Inspección inicial obligatoria

Antes de modificar código, Cursor debe inspeccionar:

1. `AiExecutionDecision`.
2. `AiExecutionInput`.
3. `AiExecutionStatus`.
4. `AiExecutionReasonCodes`.
5. `FirstAiResult`.
6. `AiBoundaryResult`.
7. Los endpoints existentes de las tareas 058–060.
8. Los DTOs y enums actuales.
9. Los patrones de validación.
10. Los patrones de serialización.
11. Los mecanismos existentes de correlation ID.
12. Las pruebas actuales.
13. La documentación arquitectónica.

No crear clases duplicadas si ya existe un contrato equivalente.

---

## 2. Paquete aislado

Paquete sugerido:

```text
lab.healthcare.fhir.aiconsumer
```

o un nombre equivalente coherente con la estructura real del repositorio.

Posible estructura:

```text
lab.healthcare.fhir.aiconsumer
├── AiConsumerContract
├── AiConsumerContractVersion
├── AiConsumerContractStatus
├── AiConsumerDispatchStatus
├── AiConsumerReasonCodes
├── AiConsumerContractMapper
└── AiConsumerContractService
```

Los nombres son orientativos. Reutilizar tipos existentes cuando sea seguro.

---

## 3. Entrada permitida

El componente debe aceptar únicamente:

```text
AiExecutionDecision
```

y, cuando sea estrictamente necesario:

```text
FirstAiResult
AiBoundaryResult
```

La entrada debe ser un objeto ya procesado por las capas anteriores.

No debe aceptar directamente:

- `Bundle`.
- `Patient`.
- `Condition`.
- `Observation`.
- `DiagnosticReport`.
- Recursos HAPI.
- DTOs de Epic.
- DTOs de Oracle.
- Tokens.
- Headers de autorización.
- Payloads FHIR.

---

## 4. Contrato sugerido

El contrato puede seguir una estructura similar a:

```text
AiConsumerContract v1
```

Campos conceptuales:

```text
contractVersion
contractStatus
pipelineStatus
clinicalDataAvailable
agentDecision
firstAiComponentStatus
executionDecision
requiresHumanReview
modelCallAuthorized
modelCalled
processingStatus
dispatchStatus
reasonCodes
warnings
medicationRequestsStatus
```

No agregar:

```text
patientId
resourceId
encounterId
fhirBundle
clinicalPayload
prompt
modelName
providerToken
```

---

# REGLAS FUNCIONALES

## Regla 1 — Entrada `ELIGIBLE_BUT_NOT_AUTHORIZED`

Cuando:

```text
executionDecision = ELIGIBLE_BUT_NOT_AUTHORIZED
modelCallAuthorized = false
processingStatus = NOT_EXECUTED
```

el contrato debe indicar:

```text
contractStatus = READY
dispatchStatus = NOT_DISPATCHED
modelCalled = false
modelCallAuthorized = false
requiresHumanReview = true
```

Debe quedar explícito que `READY` describe la preparación del contrato, no una autorización de modelo.

---

## Regla 2 — Entrada bloqueada

Cuando:

```text
executionDecision = BLOCKED
```

el contrato debe indicar:

```text
contractStatus = BLOCKED
dispatchStatus = NOT_DISPATCHED
modelCallAuthorized = false
modelCalled = false
requiresHumanReview = true
```

Debe conservar:

- Códigos de razón.
- Warnings.
- Estado del pipeline.
- Estado del agente.
- Estado del componente.

No debe producir salida clínica.

---

## Regla 3 — Revisión humana requerida

Cuando:

```text
executionDecision = REQUIRES_HUMAN_REVIEW
```

el contrato debe indicar:

```text
contractStatus = REQUIRES_HUMAN_REVIEW
dispatchStatus = NOT_DISPATCHED
modelCallAuthorized = false
modelCalled = false
requiresHumanReview = true
```

No se debe crear una recomendación ni un resumen clínico.

---

## Regla 4 — Entrada no elegible

Cuando:

```text
executionDecision = NOT_ELIGIBLE
```

el contrato debe indicar:

```text
contractStatus = NOT_ELIGIBLE
dispatchStatus = NOT_DISPATCHED
modelCallAuthorized = false
modelCalled = false
requiresHumanReview = true
```

Debe conservarse la razón de no elegibilidad.

---

## Regla 5 — Autorización prematura

Si la entrada contiene:

```text
modelCallAuthorized = true
```

la implementación debe rechazarla de acuerdo con el patrón de validación existente.

Debe producir una razón equivalente a:

```text
PREMATURE_MODEL_AUTHORIZATION
```

No se debe normalizar silenciosamente a `false`.

No se debe crear el contrato como listo.

No se debe realizar ninguna llamada externa.

---

## Regla 6 — Estado de procesamiento

En toda la Tarea 061:

```text
processingStatus = NOT_EXECUTED
modelCalled = false
```

No utilizar estados como:

```text
EXECUTED
COMPLETED
GENERATED
FAILED_MODEL_CALL
```

porque todavía no existe un modelo.

---

## Regla 7 — Estado de envío

En toda la Tarea 061:

```text
dispatchStatus = NOT_DISPATCHED
```

No implementar:

- HTTP client hacia `ai-service`.
- RabbitMQ para envío de IA.
- Webhooks.
- Retries.
- Dead-letter queues.
- Mensajería externa.
- Publicación real del contrato.

La Tarea 061 solo prepara y valida el contrato.

---

## Regla 8 — Datos clínicos ausentes

Cuando:

```text
clinicalDataAvailable = false
```

el contrato debe:

- Marcar la entrada como no elegible o bloqueada según las reglas existentes.
- Mantener revisión humana.
- Mantener `modelCallAuthorized=false`.
- Mantener `modelCalled=false`.
- No inventar datos clínicos.
- No generar un contrato que sugiera que hay información clínica disponible.

---

## Regla 9 — Pipeline parcial

Cuando:

```text
pipelineStatus = PARTIAL
```

el contrato debe:

- Conservar `PARTIAL`.
- Conservar warnings.
- Mantener `requiresHumanReview=true`.
- Mantener `modelCallAuthorized=false`.
- Mantener `modelCalled=false`.
- Mantener `dispatchStatus=NOT_DISPATCHED`.

No convertir `PARTIAL` en `SUCCESS`.

---

## Regla 10 — MedicationRequest

Conservar:

```text
medicationRequestsStatus = NOT_REQUESTED
```

No agregar:

- `MedicationRequest` a Epic.
- Prescripción.
- Sugerencias farmacológicas.
- Nuevos recursos FHIR.
- Campos clínicos adicionales al contrato v1.

---

# FRONTERAS ARQUITECTÓNICAS

## Dependencias permitidas

```text
aiconsumer → aigateway
aiconsumer → firstai
aiconsumer → aiboundary
```

Solo cuando sean necesarias y mediante tipos públicos.

## Dependencias prohibidas

`aiconsumer` no debe importar:

```text
vendor.*
FhirService
RoutingService
HAPI FHIR
Epic clients
Oracle clients
SMART PKCE
OAuth2 internals
snapshot
projection
modelboundary internals
agent internals
agentstub
FHIR resources
Bundle
```

Además, estos módulos no deben importar `aiconsumer` si eso crea una dependencia inversa:

```text
FhirService
snapshot
projection
pipeline
agent
agentstub
modelboundary
aiboundary
firstai
aigateway
```

---

# SUPERFICIES CIEGAS

El contrato y su mapper deben ser ciegos a:

```text
Epic
Oracle Health
FHIR
HAPI FHIR
Bundle
Patient IDs
Clinical resource IDs
OAuth tokens
Client IDs
Client secrets
SMART PKCE
Vendor DTOs
HTTP Authorization headers
Provider-specific URLs
Raw clinical values
Prompts
LLM responses
```

El contrato debe conocer únicamente estados y metadatos previamente controlados.

---

# SUPERFICIE DE PRUEBA

Inspeccionar los endpoints existentes.

Si ya existe una superficie adecuada para mostrar el resultado de `AiExecutionGate`, reutilizarla.

No crear endpoints duplicados.

Si se crea una superficie de laboratorio, debe:

- Ser claramente de laboratorio.
- No ser una API pública de producción.
- No aceptar FHIR crudo.
- No aceptar tokens.
- No aceptar Patient IDs.
- No aceptar DTOs de proveedores.
- No enviar el contrato a otro servicio.
- No ejecutar modelos.
- No exponer datos clínicos completos.
- Mantener las políticas de seguridad existentes.

El endpoint, si existe, debe mostrar únicamente:

```text
contractVersion
contractStatus
executionDecision
dispatchStatus
modelCallAuthorized
modelCalled
processingStatus
requiresHumanReview
reasonCodes
warnings
medicationRequestsStatus
```

---

# VALIDACIÓN FUTURA DEL CONSUMIDOR

La Tarea 061 debe documentar, pero no implementar todavía, que un futuro `ai-service` requerirá:

1. Registro del consumidor.
2. Identidad del servicio.
3. Autenticación.
4. Validación del token.
5. Scopes autorizados.
6. Tenant permitido.
7. Operación permitida.
8. Validación de versión del contrato.
9. Validación de esquema.
10. Política de datos.
11. Auditoría.
12. Rate limiting y protección contra abuso, si se expone externamente.

Un futuro agente no debe poder consumir el contrato únicamente por conocer el endpoint.

---

# SEGURIDAD Y OBSERVABILIDAD

No registrar:

- Tokens.
- Client IDs.
- Client secrets.
- Authorization headers.
- Patient IDs.
- FHIR JSON.
- Bundles.
- Valores clínicos.
- DTOs de Epic u Oracle.
- Prompts.
- Respuestas de modelos.

Se puede registrar:

- Correlation ID.
- Versión del contrato.
- Estado del pipeline.
- Decisión de ejecución.
- Estado del componente.
- Estado del contrato.
- Estado de envío.
- Código de razón.
- Cantidad de warnings.
- `modelCallAuthorized=false`.
- `modelCalled=false`.

---

# PRUEBAS OBLIGATORIAS

## Caso A — Entrada `ELIGIBLE_BUT_NOT_AUTHORIZED`

Verificar:

```text
contractStatus = READY
dispatchStatus = NOT_DISPATCHED
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
requiresHumanReview = true
```

## Caso B — Entrada `BLOCKED`

Verificar:

- Contrato bloqueado.
- No envío.
- No autorización.
- No ejecución.
- Conservación de razones.
- Conservación de warnings.

## Caso C — Entrada `REQUIRES_HUMAN_REVIEW`

Verificar:

- Contrato en revisión humana.
- `requiresHumanReview=true`.
- `modelCallAuthorized=false`.
- `modelCalled=false`.
- `dispatchStatus=NOT_DISPATCHED`.

## Caso D — Entrada `NOT_ELIGIBLE`

Verificar:

- Contrato no elegible.
- No envío.
- No autorización.
- No ejecución.
- Conservación de la razón.

## Caso E — Autorización prematura

Verificar que:

```text
modelCallAuthorized = true
```

produzca:

```text
PREMATURE_MODEL_AUTHORIZATION
```

y que:

- No cree contrato listo.
- No envíe información.
- No ejecute modelo.
- No exponga datos sensibles.

## Caso F — Datos clínicos ausentes

Verificar:

- No se inventan datos.
- El contrato no indica disponibilidad clínica.
- Se mantiene revisión humana.
- No se autoriza el modelo.
- No se realiza envío.

## Caso G — Pipeline parcial

Verificar:

- Se conserva `PARTIAL`.
- Se conservan warnings.
- No se transforma en `SUCCESS`.
- No se autoriza modelo.
- No se envía contrato.

## Caso H — `MedicationRequest`

Verificar:

```text
medicationRequestsStatus = NOT_REQUESTED
```

y que no se agreguen recursos ni campos nuevos.

## Caso I — Contrato sin datos sensibles

Verificar que la serialización no incluya:

- Patient IDs.
- FHIR JSON.
- Bundles.
- Tokens.
- Client IDs.
- Secretos.
- DTOs de proveedores.
- Valores clínicos.

## Caso J — No dependencias prohibidas

Verificar que el paquete no dependa de:

- `vendor.*`.
- `FhirService`.
- HAPI.
- Epic.
- Oracle.
- SMART PKCE.
- OAuth2 internals.
- `DeterministicAgent`.
- `AgentStub`.
- Clientes HTTP.
- SDKs de IA.

## Caso K — Compatibilidad con tareas anteriores

Verificar que los campos 053–060 continúen intactos:

```text
pipelineStatus
deterministicAgent
agentReason
aiBoundary
firstAiComponent
aiProcessingStatus
aiExecutionGate
modelCallAuthorized
aiModelCalled
requiresHumanReview
medicationRequestsStatus
```

---

# DEFINITION OF DONE

La tarea está terminada cuando:

- [ ] Existe un contrato interno `AI Consumer Contract v1`.
- [ ] El contrato consume únicamente resultados controlados de tareas anteriores.
- [ ] No acepta FHIR crudo.
- [ ] No acepta Bundles.
- [ ] No acepta DTOs de Epic u Oracle.
- [ ] No acepta tokens ni secretos.
- [ ] No implementa autenticación externa todavía.
- [ ] Documenta la futura validación de consumidores.
- [ ] Distingue preparación, elegibilidad, autorización, envío y ejecución.
- [ ] Mantiene `modelCallAuthorized=false`.
- [ ] Mantiene `modelCalled=false`.
- [ ] Mantiene `processingStatus=NOT_EXECUTED`.
- [ ] Mantiene `dispatchStatus=NOT_DISPATCHED`.
- [ ] Mantiene `requiresHumanReview=true`.
- [ ] Rechaza autorización prematura.
- [ ] Conserva warnings.
- [ ] Conserva códigos de razón.
- [ ] Conserva `medicationRequestsStatus=NOT_REQUESTED`.
- [ ] No amplía la allowlist 042.
- [ ] No modifica el contrato clínico v1.
- [ ] No agrega `MedicationRequest` a Epic.
- [ ] No ejecuta ningún modelo.
- [ ] No realiza llamadas externas.
- [ ] No crea un cliente HTTP para `ai-service`.
- [ ] No agrega OpenAI, Azure OpenAI, Gemini, Claude u otro proveedor.
- [ ] No agrega Python.
- [ ] No agrega RAG.
- [ ] No agrega embeddings.
- [ ] No agrega vector database.
- [ ] No agrega LangChain.
- [ ] No agrega LangGraph.
- [ ] No agrega memoria conversacional.
- [ ] No genera diagnóstico.
- [ ] No genera prescripción.
- [ ] No genera recomendaciones clínicas.
- [ ] Las pruebas nuevas pasan.
- [ ] `mvn test` completo pasa.
- [ ] `.env` permanece intacto.
- [ ] Se actualiza `docs/progress/progress-log.md`.
- [ ] Se documentan las fronteras arquitectónicas.
- [ ] Se documentan las superficies ciegas.
- [ ] Se documenta la validación futura de consumidores.
- [ ] Se documenta la ausencia de envío real.
- [ ] Se crea el commit Conventional Commits.
- [ ] Se informa la rama utilizada.
- [ ] Se informa el resultado de las pruebas.

---

# FUERA DE ALCANCE

No implementar en la Tarea 061:

- LLM real.
- OpenAI.
- Azure OpenAI.
- Gemini.
- Claude.
- Cualquier proveedor de IA.
- API keys.
- Prompts.
- Respuestas de modelos.
- Servicio Python.
- `ai-service` externo.
- Cliente HTTP hacia `ai-service`.
- RabbitMQ para envío de IA.
- Webhooks.
- Retries.
- Dead-letter queues.
- RAG.
- Embeddings.
- Vector database.
- LangChain.
- LangGraph.
- Memoria conversacional.
- Agentes autónomos.
- Tool calling.
- Function calling.
- Diagnóstico clínico.
- Prescripción.
- Recomendaciones médicas.
- Decisiones clínicas automatizadas.
- Nuevos recursos FHIR.
- `MedicationRequest` para Epic.
- Cambios en OAuth2.
- Cambios en SMART PKCE.
- Cambios en Epic.
- Cambios en Oracle Health.
- Cambios en la allowlist 042.
- Modificación de `.env`.

---

# ENTREGABLES

Cursor debe entregar:

1. Contrato interno `AI Consumer Contract v1`.
2. DTOs, enums o modelos estrictamente necesarios.
3. Mapper desde `AiExecutionDecision`.
4. Servicio de construcción y validación del contrato.
5. Validación contra autorización prematura.
6. Pruebas unitarias y/o de integración.
7. Documentación de fronteras arquitectónicas.
8. Documentación de superficies ciegas.
9. Documentación de la futura validación de consumidores.
10. Confirmación de que no existe envío real.
11. Actualización de `docs/progress/progress-log.md`.
12. Lista de archivos creados y modificados.
13. Resultado de `mvn test`.
14. Confirmación de que `.env` no fue modificado.
15. Rama utilizada.
16. Commit creado.
17. Resumen de decisiones técnicas y riesgos pendientes.

---

# INSTRUCCIÓN FINAL PARA CURSOR

Antes de implementar:

1. Inspecciona las tareas 058, 059 y 060.
2. Inspecciona `AiBoundaryResult`, `FirstAiResult` y `AiExecutionDecision`.
3. Reutiliza tipos y patrones existentes cuando sea posible.
4. No crees endpoints duplicados.
5. No agregues datos clínicos al contrato.
6. No agregues FHIR crudo, Bundles ni DTOs de proveedores.
7. No agregues tokens, Patient IDs ni secretos.
8. No implementes autenticación externa en esta tarea.
9. Documenta cómo se validará un futuro consumidor.
10. No realices envío real a un `ai-service`.
11. Mantén `dispatchStatus=NOT_DISPATCHED`.
12. Mantén `modelCallAuthorized=false`.
13. Mantén `modelCalled=false`.
14. Mantén `processingStatus=NOT_EXECUTED`.
15. Mantén `requiresHumanReview=true`.
16. No generes salida clínica.
17. Ejecuta todas las pruebas.
18. Actualiza la documentación.
19. Crea el commit indicado.

Resultado esperado:

```text
AiExecutionDecision
        ↓
AiConsumerContract v1
        ↓
dispatchStatus = NOT_DISPATCHED
```

con:

```text
contractStatus = READY
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
requiresHumanReview = true
dispatchStatus = NOT_DISPATCHED
```

La Tarea 061 debe preparar un contrato seguro y estable para un futuro `ai-service`, sin convertir todavía la interoperabilidad Java en un consumidor abierto ni ejecutar procesamiento de IA.
