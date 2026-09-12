# Task 064 — AI Consumer Handoff Authorization Boundary

## 1. Identificación

- **Proyecto:** `healthcare-ai-interoperability-lab`
- **Servicio actual:** `fhir-integration-service`
- **Stack:** Java 21, Spring Boot 3.5.16, HAPI FHIR 8.10.0
- **Paquete raíz:** `lab.healthcare.fhir`
- **Puerto:** `8081`
- **Base branch:** `feature/ai-consumer-readiness`
- **Base commit:** `f51baca`
- **Base message:** `feat: add ai consumer readiness`
- **Suggested branch:** `feature/ai-handoff-authorization-boundary`
- **Suggested commit:** `feat: add ai handoff authorization boundary`

---

# WHAT

Implementar una frontera interna de **autorización de handoff**, posterior a la Task 063.

Esta frontera debe evaluar si existe una autorización suficiente para permitir un futuro handoff del contrato hacia un consumidor externo o un futuro `ai-service`.

La implementación debe ser **deny-by-default**.

Aunque la Task 063 produzca:

```text
READY_FOR_FUTURE_HANDOFF
```

la Task 064 debe producir una decisión separada que indique que el handoff real todavía no está autorizado.

La tarea no debe:

- Enviar el contrato.
- Ejecutar HTTP.
- Invocar un modelo.
- Realizar dispatch.
- Crear credenciales reales.
- Implementar OAuth2/OIDC.
- Implementar JWT real.
- Integrarse con Epic u Oracle.
- Incorporar un `ai-service`.

La Task 064 debe formalizar el contrato y la frontera de autorización futura, manteniendo la autorización efectiva en `false`.

---

# WHY

Actualmente existe la siguiente cadena:

```text
AiConsumerPolicy
        ↓
ALLOWED_FOR_FUTURE_CONSUMPTION
        ↓
AiConsumerReadiness
        ↓
READY_FOR_FUTURE_HANDOFF
```

Sin embargo, todavía no existe una separación explícita entre:

- Consumidor sintéticamente válido.
- Contrato técnicamente preparado.
- Handoff autorizado.
- Handoff ejecutado.
- Modelo autorizado.
- Modelo ejecutado.

La Task 064 debe crear esa separación.

La regla central es:

```text
READY_FOR_FUTURE_HANDOFF
    ≠
HANDOFF_AUTHORIZED
```

y:

```text
HANDOFF_AUTHORIZED
    ≠
DISPATCHED
```

En esta etapa, incluso cuando todos los requisitos sintéticos estén presentes, la autorización efectiva debe permanecer:

```text
handoffAuthorized = false
```

La tarea prepara la frontera para una futura implementación de autenticación, registro y autorización real, pero no adelanta esa etapa.

---

# CONCEPT

## 1. Nueva cadena

```text
AiConsumerContract v1
        ↓
AiConsumerPolicy
        ↓
AiConsumerReadiness
        ↓
AiHandoffAuthorizationBoundary
        ↓
Futura autenticación y autorización real
        ↓
Futuro handoff
        ↓
Futuro ai-service
        ↓
Futuro modelo
```

La Task 064 implementa únicamente:

```text
AiConsumerReadiness
        ↓
AiHandoffAuthorizationBoundary
```

---

## 2. Diferencias obligatorias

| Estado | Significado |
|---|---|
| `ALLOWED_FOR_FUTURE_CONSUMPTION` | La política sintética permite considerar el contrato para consumo futuro |
| `READY_FOR_FUTURE_HANDOFF` | El contrato está técnicamente preparado para una futura frontera de handoff |
| `HANDOFF_NOT_AUTHORIZED` | No existe autorización efectiva para enviar el contrato |
| `HANDOFF_AUTHORIZED` | No debe producirse en la Task 064 |
| `DISPATCHED` | No debe producirse en la Task 064 |
| `MODEL_CALL_AUTHORIZED` | Debe permanecer en `false` |
| `MODEL_CALLED` | Debe permanecer en `false` |

---

## 3. Decisión de diseño

La Task 064 debe implementar una frontera de autorización **preparada, pero no habilitada**.

Esto significa:

- La estructura de autorización existe.
- Los requisitos futuros están documentados.
- La evaluación es determinística.
- La decisión final efectiva es siempre no autorizada.
- No existe envío.
- No existe dispatch.
- No existe llamada a modelo.

No se debe simular una autorización real mediante un booleano configurable desde un endpoint.

No se debe agregar un parámetro público como:

```text
?authorized=true
```

ni aceptar headers arbitrarios para activar el handoff.

---

# HOW

## 1. Inspección inicial obligatoria

Antes de modificar código, Cursor debe inspeccionar:

- `AiConsumerReadinessResult`.
- `AiConsumerReadinessStatus`.
- `AiConsumerPolicyResult`.
- `AiConsumerContract`.
- `AiExecutionDecision`.
- Documentación de las Tasks 060–063.
- Endpoints de laboratorio existentes.
- Convenciones de records, enums, servicios y pruebas.
- Dependencias actuales entre paquetes.

No asumir nombres de campos. Adaptar la implementación a los contratos reales existentes.

---

## 2. Paquete sugerido

Crear un paquete separado:

```text
lab.healthcare.fhir.aihandoffauthorization
```

La implementación no debe ubicarse dentro de:

```text
fhir
vendor
epic
oracle
pipeline
agent
aiboundary
firstai
aigateway
aiconsumer
aiconsumerpolicy
aiconsumerreadiness
```

El paquete debe depender únicamente de contratos internos apropiados.

---

## 3. Clases sugeridas

Las siguientes clases son sugeridas:

```text
AiHandoffAuthorizationBoundary
AiHandoffAuthorizationInput
AiHandoffAuthorizationResult
AiHandoffAuthorizationStatus
AiHandoffAuthorizationReasonCodes
AiHandoffAuthorizationValidator
AiHandoffAuthorizationMapper
```

No es obligatorio crear todas las clases si el diseño real puede resolverse con menos componentes.

La implementación debe evitar una jerarquía innecesaria.

---

# 4. Entrada permitida

La entrada principal debe ser:

```text
AiConsumerReadinessResult
```

Opcionalmente puede incluirse información de:

```text
AiConsumerContract
```

solo si es necesaria para verificar invariantes.

La entrada no debe incluir:

- FHIR crudo.
- `Bundle`.
- `Patient`.
- `Condition`.
- `Observation`.
- `DiagnosticReport`.
- `MedicationRequest`.
- Patient IDs.
- Tokens.
- Secrets.
- Client IDs reales.
- DTOs de Epic.
- DTOs de Oracle.
- Prompts.
- Respuestas de modelos.
- Valores clínicos.

La Task 064 no debe volver a ejecutar el pipeline ni reconstruir el contrato desde recursos FHIR.

---

# 5. Estados de autorización

Definir un conjunto cerrado de estados:

```text
HANDOFF_NOT_AUTHORIZED
BLOCKED
HUMAN_REVIEW_REQUIRED
NOT_READY_FOR_AUTHORIZATION
```

No agregar estados efectivos de ejecución como:

```text
HANDOFF_AUTHORIZED
DISPATCHED
MODEL_AUTHORIZED
MODEL_EXECUTED
CLINICAL_OUTPUT_GENERATED
```

`HANDOFF_AUTHORIZED` puede existir únicamente como concepto documentado de una futura etapa, pero no debe ser producido por la implementación de la Task 064.

---

# 6. Resultado obligatorio de esta etapa

Para cualquier entrada válida, el resultado efectivo debe conservar:

```text
handoffAuthorized = false
dispatchPerformed = false
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
requiresHumanReview = true
```

Incluso si la entrada es:

```text
readinessStatus = READY_FOR_FUTURE_HANDOFF
```

el resultado debe indicar:

```text
authorizationStatus = HANDOFF_NOT_AUTHORIZED
```

Código sugerido:

```text
REAL_AUTHORIZATION_NOT_IMPLEMENTED
```

La Task 064 no debe convertir la preparación técnica en autorización efectiva.

---

# 7. Reglas de evaluación

## 7.1. Readiness no disponible

Si:

```text
readinessResult == null
```

o el resultado es inválido, producir:

```text
NOT_READY_FOR_AUTHORIZATION
```

Código sugerido:

```text
READINESS_RESULT_MISSING
```

---

## 7.2. Readiness bloqueado

Si:

```text
readinessStatus == BLOCKED
```

producir:

```text
BLOCKED
```

Código sugerido:

```text
READINESS_BLOCKED
```

No se debe generar ninguna autorización futura ni salida clínica.

---

## 7.3. Revisión humana requerida

Si:

```text
readinessStatus == HUMAN_REVIEW_REQUIRED
```

producir:

```text
HUMAN_REVIEW_REQUIRED
```

Código sugerido:

```text
READINESS_REQUIRES_HUMAN_REVIEW
```

La revisión humana no debe transformarse automáticamente en autorización.

---

## 7.4. Readiness incompleto

Si:

```text
readinessStatus == NOT_READY
```

producir:

```text
NOT_READY_FOR_AUTHORIZATION
```

Código sugerido:

```text
READINESS_NOT_COMPLETE
```

---

## 7.5. Readiness preparado

Si:

```text
readinessStatus == READY_FOR_FUTURE_HANDOFF
```

la Task 064 debe verificar todas las invariantes.

Si las invariantes son correctas, producir:

```text
HANDOFF_NOT_AUTHORIZED
```

Código sugerido:

```text
REAL_AUTHORIZATION_NOT_IMPLEMENTED
```

El resultado debe explicar que:

- El contrato está preparado.
- La política sintética fue favorable.
- La autorización real todavía no existe.
- No se permite handoff.
- No se permite dispatch.
- No se permite ejecución de modelo.

---

## 7.6. Estado de ejecución inconsistente

Si alguno de estos valores no coincide con el estado seguro esperado:

```text
modelCallAuthorized != false
modelCalled != false
processingStatus != NOT_EXECUTED
dispatchStatus != NOT_DISPATCHED
handoffAuthorized != false
dispatchPerformed != false
```

producir:

```text
BLOCKED
```

Código sugerido:

```text
INCONSISTENT_EXECUTION_STATE
```

La Task 064 no debe corregir silenciosamente estos valores.

---

## 7.7. Revisión humana desactivada

Si:

```text
requiresHumanReview == false
```

producir:

```text
HUMAN_REVIEW_REQUIRED
```

Código sugerido:

```text
HUMAN_REVIEW_FLAG_MISSING
```

La Task 064 no puede apagar ni modificar el indicador de revisión humana.

---

## 7.8. Autorización externa simulada

La implementación no debe aceptar como autorización válida:

- Un booleano recibido desde un endpoint.
- Un header libre.
- Un query parameter.
- Un campo de texto no validado.
- Un valor hardcodeado que represente credenciales.
- Un `consumerId` sintético por sí solo.
- Un `scope` por sí solo.
- Un resultado `READY_FOR_FUTURE_HANDOFF` por sí solo.

No implementar una falsa autenticación ni una falsa autorización real.

---

# 8. Contrato de autorización futura

La Task 064 puede definir un contrato interno que documente los requisitos de una futura autorización real.

Los atributos conceptuales pueden incluir:

```text
consumerIdentityPresent
consumerAuthenticated
consumerAuthorized
requiredScopePresent
tenantContextPresent
contractVersionSupported
operationSupported
humanReviewSatisfied
handoffChannelConfigured
externalAuthorizationAvailable
```

Estos campos deben ser:

- Sintéticos.
- Internos.
- No sensibles.
- No vinculados a credenciales reales.
- No usados para activar el handoff.

En esta tarea, el resultado efectivo debe continuar siendo:

```text
externalAuthorizationAvailable = false
handoffAuthorized = false
```

Si los nombres reales del proyecto difieren, respetar las convenciones existentes.

---

# 9. Operación permitida

La operación conceptual de esta tarea debe ser:

```text
EVALUATE_HANDOFF_AUTHORIZATION
```

Esta operación significa únicamente evaluar si la frontera está preparada para una futura autorización.

No debe existir una operación ejecutable como:

```text
AUTHORIZE_HANDOFF
DISPATCH_CONTRACT
SEND_TO_AI_SERVICE
EXECUTE_MODEL
GENERATE_CLINICAL_OUTPUT
WRITE_BACK_TO_FHIR
```

---

# 10. Scope conceptual

El scope de lectura de la Task 062:

```text
ai.contract.read
```

no debe interpretarse como autorización para handoff.

La Task 064 debe mantener esa distinción.

Si se documenta un scope futuro, utilizar un valor conceptual no operativo, por ejemplo:

```text
ai.handoff.request
```

pero:

- No debe autorizarse.
- No debe enviarse.
- No debe incorporarse a una allowlist real.
- No debe activar ninguna integración.
- No debe aparecer como scope concedido.

El resultado efectivo debe indicar que el scope de handoff real todavía no está disponible.

Código sugerido:

```text
HANDOFF_SCOPE_NOT_GRANTED
```

---

# 11. Resultado esperado

El resultado debe incluir, como mínimo:

```text
authorizationStatus
reasonCode
readinessStatus
policyDecision
contractVersion
requestedOperation
requestedScope
consumerType
consumerIdentityPresent
consumerAuthenticated
consumerAuthorized
tenantContextPresent
externalAuthorizationAvailable
handoffAuthorized
dispatchPerformed
modelCallAuthorized
modelCalled
processingStatus
dispatchStatus
requiresHumanReview
```

Los campos efectivos deben conservar:

```text
externalAuthorizationAvailable = false
handoffAuthorized = false
dispatchPerformed = false
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
requiresHumanReview = true
```

---

# 12. Invariantes de seguridad

La implementación debe garantizar siempre:

```text
handoffAuthorized = false
dispatchPerformed = false
externalAuthorizationAvailable = false
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
requiresHumanReview = true
```

Estas invariantes deben mantenerse incluso cuando:

```text
readinessStatus = READY_FOR_FUTURE_HANDOFF
```

La única conclusión positiva permitida en esta etapa es:

```text
HANDOFF_NOT_AUTHORIZED
```

acompañada de una razón que indique que la autorización real aún no está implementada.

---

# 13. API de laboratorio

Se puede agregar un endpoint de laboratorio únicamente si sigue el patrón de las Tasks 061–063.

Endpoint sugerido:

```text
GET /lab/ai-handoff-authorization
```

o:

```text
GET /api/ai-handoff-authorization/v1
```

El endpoint debe:

- Utilizar únicamente datos sintéticos.
- Consumir `AiConsumerReadinessResult`.
- Mostrar la decisión de autorización no efectiva.
- No aceptar tokens.
- No aceptar Patient IDs.
- No aceptar FHIR JSON.
- No aceptar parámetros para activar autorización.
- No realizar HTTP externo.
- No realizar dispatch.
- No invocar Epic.
- No invocar Oracle.
- No invocar HAPI FHIR.
- No invocar un modelo.

El endpoint no debe presentarse como una API de autorización real.

Si no aporta valor respecto a los endpoints existentes, puede omitirse y exponer únicamente el componente interno con pruebas.

---

# 14. Observabilidad segura

Los logs, si se agregan, solo pueden incluir:

```text
authorizationStatus
reasonCode
readinessStatus
policyDecision
contractVersion
requestedOperation
requestedScope
consumerType
consumerIdentityPresent
consumerAuthenticated
consumerAuthorized
tenantContextPresent
externalAuthorizationAvailable
handoffAuthorized
dispatchPerformed
modelCallAuthorized
modelCalled
processingStatus
dispatchStatus
requiresHumanReview
```

No registrar:

- Tokens.
- Secrets.
- Client IDs reales.
- Patient IDs.
- FHIR crudo.
- Bundles.
- Datos clínicos.
- Prompts.
- Respuestas de modelos.
- URLs privadas.
- Credenciales.
- Headers completos.
- Claims reales.

---

# 15. Fronteras arquitectónicas

La dependencia permitida debe ser:

```text
aihandoffauthorization -> aiconsumerreadiness
```

Opcionalmente:

```text
aihandoffauthorization -> aiconsumerpolicy
aihandoffauthorization -> aiconsumer
```

No debe existir dependencia hacia:

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
Epic*
Oracle*
pipeline
agent
aiboundary
firstai
aigateway
aiconsumer
aiconsumerpolicy
```

La Task 064 debe ser una frontera de control interno, no parte de la interoperabilidad FHIR.

---

# 16. Superficies ciegas

La implementación debe permanecer ciega a:

- Epic.
- Oracle Health.
- SMART.
- OAuth.
- JWT.
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

No implementar:

```text
if Epic
if Oracle
if Patient
if MedicationRequest
if FHIR resourceType
```

---

# 17. Documentación requerida

Crear o actualizar:

```text
docs/fhir/ai-handoff-authorization-boundary.md
```

La documentación debe aclarar que la Task 064 no implementa autorización real.

Debe explicar:

- Propósito de la frontera.
- Diferencia entre readiness y autorización.
- Diferencia entre autorización y dispatch.
- Diferencia entre autorización y ejecución de modelo.
- Estados posibles.
- Códigos de razón.
- Invariantes de seguridad.
- Reglas deny-by-default.
- Requisitos conceptuales para una futura autorización real.
- Ausencia de OAuth2/OIDC.
- Ausencia de JWT real.
- Ausencia de tokens.
- Ausencia de clientes HTTP.
- Ausencia de handoff.
- Ausencia de modelo.
- Próximas etapas posibles, sin diseñar su implementación.

---

# 18. Pruebas requeridas

Crear pruebas unitarias determinísticas.

## Caso A — Readiness preparado

Entrada:

```text
readinessStatus = READY_FOR_FUTURE_HANDOFF
```

Con invariantes correctas.

Resultado esperado:

```text
authorizationStatus = HANDOFF_NOT_AUTHORIZED
reasonCode = REAL_AUTHORIZATION_NOT_IMPLEMENTED
handoffAuthorized = false
dispatchPerformed = false
```

---

## Caso B — Readiness bloqueado

Entrada:

```text
readinessStatus = BLOCKED
```

Resultado esperado:

```text
authorizationStatus = BLOCKED
reasonCode = READINESS_BLOCKED
```

---

## Caso C — Revisión humana requerida

Entrada:

```text
readinessStatus = HUMAN_REVIEW_REQUIRED
```

Resultado esperado:

```text
authorizationStatus = HUMAN_REVIEW_REQUIRED
```

---

## Caso D — Readiness no disponible

Entrada:

```text
readinessResult = null
```

Resultado esperado:

```text
authorizationStatus = NOT_READY_FOR_AUTHORIZATION
reasonCode = READINESS_RESULT_MISSING
```

---

## Caso E — Autorización de modelo prematura

Entrada:

```text
modelCallAuthorized = true
```

Resultado esperado:

```text
authorizationStatus = BLOCKED
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
authorizationStatus = BLOCKED
```

---

## Caso G — Dispatch realizado

Entrada:

```text
dispatchStatus = DISPATCHED
```

Resultado esperado:

```text
authorizationStatus = BLOCKED
```

---

## Caso H — Handoff marcado como autorizado

Entrada:

```text
handoffAuthorized = true
```

Resultado esperado:

```text
authorizationStatus = BLOCKED
```

La implementación no debe aceptar ni propagar esa autorización.

---

## Caso I — Revisión humana desactivada

Entrada:

```text
requiresHumanReview = false
```

Resultado esperado:

```text
authorizationStatus = HUMAN_REVIEW_REQUIRED
reasonCode = HUMAN_REVIEW_FLAG_MISSING
```

---

## Caso J — Scope de handoff no concedido

Entrada con scope conceptual de handoff no concedido.

Resultado esperado:

```text
authorizationStatus = HANDOFF_NOT_AUTHORIZED
reasonCode = HANDOFF_SCOPE_NOT_GRANTED
```

---

## Caso K — Autorización externa no disponible

Entrada:

```text
externalAuthorizationAvailable = false
```

Resultado esperado:

```text
authorizationStatus = HANDOFF_NOT_AUTHORIZED
reasonCode = REAL_AUTHORIZATION_NOT_IMPLEMENTED
```

---

## Caso L — Parámetro de activación no permitido

Verificar que no exista una forma de activar autorización mediante:

- Query parameter.
- Header libre.
- Campo booleano público.
- Valor hardcodeado modificable desde laboratorio.

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

- Tasks 054–063.
- `AiConsumerContract`.
- `AiConsumerPolicy`.
- `AiConsumerReadiness`.
- `AiExecutionDecision`.
- Endpoints de laboratorio existentes.
- Estados de seguridad actuales.

---

# 19. Compatibilidad con el estado actual

La Task 064 debe conservar:

```text
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
requiresHumanReview = true
handoffAuthorized = false
dispatchPerformed = false
```

La evidencia live puede continuar mostrando:

```text
aiConsumerReadiness = READY_FOR_FUTURE_HANDOFF
```

y adicionalmente, si se expone la nueva frontera:

```text
aiHandoffAuthorization = HANDOFF_NOT_AUTHORIZED
```

No debe aparecer:

```text
aiHandoffAuthorization = HANDOFF_AUTHORIZED
```

ni:

```text
dispatchStatus = DISPATCHED
```

---

# 20. Fuera de alcance

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
- RabbitMQ.
- Webhooks.
- Retries.
- DLQ.
- Dispatch.
- Handoff real.
- OAuth2.
- OIDC.
- JWT real.
- SMART.
- PKCE.
- Tokens.
- Client IDs reales.
- Client secrets.
- Registro real de consumidores.
- Autenticación real.
- Autorización real.
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
- Ampliación de allowlist 042.
- Incorporación de `MedicationRequest` para Epic.
- Cambios en campos clínicos del contrato v1.
- Modificación de `.env`.
- Registro de tokens, Patient IDs o FHIR crudo.

---

# 21. Definition of Done

La Task 064 se considera terminada cuando:

- Existe una frontera aislada de autorización de handoff.
- Consume `AiConsumerReadinessResult`.
- No consume FHIR crudo.
- No consume Bundles.
- No consume DTOs vendor-specific.
- No consume tokens reales.
- No consume Patient IDs.
- Distingue readiness de autorización.
- Implementa una política deny-by-default.
- La autorización efectiva permanece en `false`.
- `externalAuthorizationAvailable` permanece en `false`.
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
- No realiza dispatch.
- No implementa OAuth2/OIDC/JWT real.
- No incorpora Epic.
- No incorpora Oracle.
- No modifica `FhirService`.
- No amplía la allowlist 042.
- No cambia los campos clínicos del contrato v1.
- Las pruebas unitarias pasan.
- Las pruebas de regresión pasan.
- La documentación queda actualizada.
- `.env` permanece intacto.
- El diff contiene únicamente cambios de la Task 064.

---

# 22. Entregables

1. Implementación de `aihandoffauthorization`.
2. DTOs, records o enums internos necesarios.
3. Estados de autorización.
4. Códigos de razón.
5. Validaciones de invariantes.
6. Pruebas unitarias.
7. Endpoint de laboratorio opcional, si sigue el patrón existente.
8. Documentación técnica.
9. Evidencia de ejecución de `mvn test`.
10. Resumen de archivos creados y modificados.
11. Confirmación de que no se agregaron integraciones externas.
12. Confirmación de que `.env` no se modificó.

---

# 23. Commit y rama sugeridos

```text
Branch:
feature/ai-handoff-authorization-boundary
```

```text
Commit:
feat: add ai handoff authorization boundary
```

No realizar push automáticamente.

---

# 24. Instrucción final para Cursor

Implementa la Task 064 en el repositorio actual respetando estrictamente las fronteras arquitectónicas existentes.

Antes de modificar código:

1. Inspecciona `AiConsumerReadinessResult`.
2. Revisa `AiConsumerPolicyResult`.
3. Revisa `AiConsumerContract`.
4. Revisa las Tasks 060–063.
5. Identifica las convenciones reales de paquetes, records, enums y pruebas.
6. No inventes campos incompatibles.
7. No modifiques el pipeline FHIR.
8. No modifiques `FhirService`.
9. No agregues proveedores ni clientes externos.

Durante la implementación:

1. Mantén la lógica determinística.
2. Consume únicamente el resultado de readiness o el contrato interno.
3. Implementa una frontera deny-by-default.
4. No implementes autenticación real.
5. No implementes autorización real.
6. No aceptes parámetros para activar el handoff.
7. No proceses FHIR crudo.
8. No uses Patient IDs.
9. No uses tokens ni secrets.
10. No ejecutes modelos.
11. No realices dispatch.
12. Mantén `handoffAuthorized=false`.
13. Mantén `dispatchPerformed=false`.
14. Mantén `requiresHumanReview=true`.
15. Mantén todos los estados de ejecución en valores no ejecutados.

Después de implementar:

1. Ejecuta pruebas unitarias.
2. Ejecuta `mvn test`.
3. Verifica la ausencia de llamadas HTTP.
4. Verifica la ausencia de SDKs de IA.
5. Verifica la ausencia de OAuth2/OIDC/JWT real.
6. Verifica la ausencia de tokens y secretos.
7. Verifica que `.env` no cambió.
8. Revisa el diff.
9. Actualiza `docs/fhir/ai-handoff-authorization-boundary.md`.
10. Confirma que no se amplió la allowlist 042.
11. Entrega:
   - Archivos creados.
   - Archivos modificados.
   - Pruebas ejecutadas.
   - Resultado de pruebas.
   - Estados de autorización.
   - Invariantes verificadas.
   - Commit sugerido.
   - Riesgos o decisiones pendientes para etapas posteriores.
