# Task 062 — AI Consumer Contract Validation and Consumer Policy

## 1. Identificación

- **Proyecto:** `healthcare-ai-interoperability-lab`
- **Servicio:** `fhir-integration-service`
- **Base branch:** `feature/ai-consumer-contract`
- **Base commit:** `58ef362`
- **Suggested branch:** `feature/ai-consumer-policy`
- **Suggested commit:** `feat: add ai consumer policy`

---

## 2. Objetivo

Implementar una política interna de validación para consumidores del contrato `AiConsumerContract v1`.

La tarea debe definir y validar, de forma determinística, bajo qué condiciones un consumidor interno puede ser considerado apto para consumir el contrato en el futuro.

La implementación debe permanecer aislada y no debe ejecutar ningún modelo de IA, realizar dispatch, llamar a servicios externos ni enviar datos clínicos.

---

## 3. Motivo

El contrato interno de consumo creado en la Task 061 establece una frontera entre el pipeline clínico y un futuro consumidor de IA.

Antes de permitir cualquier consumo real, se necesita distinguir claramente entre:

- Contrato técnicamente válido.
- Consumidor identificado.
- Consumidor autenticado.
- Consumidor autorizado.
- Scope permitido.
- Versión de contrato compatible.
- Operación solicitada.
- Contexto de tenant presente.
- Elegibilidad para consumo futuro.
- Autorización de ejecución de modelo.
- Dispatch efectivo.
- Ejecución real de IA.

Esta tarea implementa únicamente la política de validación. No implementa autenticación ni autorización reales.

---

## 4. Alcance funcional

La política debe recibir un `AiConsumerContract` y metadatos sintéticos del consumidor.

Debe producir una decisión determinística que indique si:

1. El consumidor puede ser considerado válido para consumo futuro.
2. El contrato debe ser rechazado.
3. La solicitud requiere revisión humana.

La política debe validar, como mínimo:

- Identidad sintética del consumidor.
- Tipo de consumidor.
- Autenticación sintética.
- Autorización sintética.
- Versión solicitada.
- Operación solicitada.
- Scope solicitado.
- Presencia del contexto de tenant.
- Estado del contrato de consumo.
- Ausencia de autorización prematura para ejecutar modelos.
- Ausencia de dispatch ya realizado.

---

## 5. Fuera de alcance

No implementar:

- Llamadas a `ai-service`.
- Clientes HTTP.
- REST clients.
- WebClient.
- Feign.
- SDKs de modelos.
- OpenAI, Azure OpenAI, Anthropic u otros proveedores.
- LLM.
- Prompting.
- RAG.
- Embeddings.
- Vector databases.
- LangChain.
- LangGraph.
- Memoria conversacional.
- OAuth2/OIDC real.
- SMART on FHIR.
- PKCE.
- JWT real para consumidores.
- Gestión real de tokens.
- Gestión de client secrets.
- Integración con Epic.
- Integración con Oracle Health.
- Integración con FHIR servers externos.
- Dispatch por RabbitMQ.
- Webhooks.
- Reintentos.
- Dead-letter queues.
- Ejecución de modelos.
- Generación de diagnóstico.
- Prescripción.
- Recomendaciones clínicas.
- Escritura de resultados en FHIR.
- Actualización de `Patient`.
- Creación de `MedicationRequest`.
- Datos clínicos reales.
- Patient IDs reales.
- URLs privadas.
- Modificación de `.env`.

---

## 6. Paquete sugerido

Crear un paquete aislado:

```text
lab.healthcare.fhir.aiconsumerpolicy
```

La implementación debe adaptarse a la estructura real del repositorio si el paquete o las convenciones existentes requieren otro nombre equivalente.

---

## 7. Clases sugeridas

Las siguientes clases son sugeridas y pueden ajustarse a las convenciones del proyecto:

```text
AiConsumerPolicy
AiConsumerPolicyInput
AiConsumerPolicyDecision
AiConsumerPolicyReasonCodes
AiConsumerPolicyValidator
AiConsumerPolicyMapper
```

No crear clases innecesarias si la lógica puede mantenerse simple, legible y determinística.

---

## 8. Entrada de la política

La política debe recibir:

### 8.1. Contrato

Un `AiConsumerContract` proveniente de la Task 061.

No duplicar el contrato ni crear una segunda versión incompatible.

### 8.2. Metadatos sintéticos del consumidor

Los metadatos pueden incluir:

```text
consumerId
consumerType
requestedContractVersion
requestedOperation
requestedScope
tenantContextPresent
authenticated
authorized
```

Estos valores son exclusivamente sintéticos para laboratorio.

No deben representar:

- Tokens reales.
- Identidades reales.
- Patient IDs.
- Identificadores de clínicas reales.
- Credenciales.
- Secrets.
- Claims reales.
- Datos de usuarios reales.

---

## 9. Operación permitida

La única operación permitida en esta tarea debe ser:

```text
READ_CONTRACT
```

La política debe rechazar explícitamente operaciones como:

```text
EXECUTE_MODEL
GENERATE_CLINICAL_OUTPUT
WRITE_BACK_TO_FHIR
UPDATE_PATIENT
CREATE_MEDICATION_REQUEST
DISPATCH_TO_AI_SERVICE
```

La política no debe convertir una solicitud de lectura del contrato en autorización para ejecutar un modelo.

---

## 10. Scope conceptual

El scope conceptual permitido para esta tarea es:

```text
ai.contract.read
```

La validación debe rechazar:

- Scope ausente.
- Scope vacío.
- Scope diferente al permitido.
- Scope que implique ejecución de modelo.
- Scope que implique escritura en FHIR.
- Scope que implique acciones clínicas.

No implementar un sistema real de scopes. Solo validar el valor sintético recibido.

---

## 11. Reglas de decisión

### 11.1. Consumidor válido

El consumidor puede considerarse válido para consumo futuro únicamente si:

- `consumerId` está presente.
- `consumerType` está presente.
- `authenticated == true`.
- `authorized == true`.
- `requestedContractVersion` es compatible con `v1`.
- `requestedOperation == READ_CONTRACT`.
- `requestedScope == ai.contract.read`.
- `tenantContextPresent == true`.
- El contrato no está bloqueado.
- El contrato no requiere revisión humana obligatoria.
- El contrato no está marcado como no elegible.
- `modelCallAuthorized == false`.
- `modelCalled == false`.
- `dispatchStatus == NOT_DISPATCHED`.
- `processingStatus == NOT_EXECUTED`.

La decisión resultante debe ser:

```text
ALLOWED_FOR_FUTURE_CONSUMPTION
```

Esta decisión no autoriza ejecución de modelo ni dispatch.

---

### 11.2. Consumidor no autenticado

Si:

```text
authenticated == false
```

La política debe rechazar la solicitud.

Código sugerido:

```text
CONSUMER_NOT_AUTHENTICATED
```

Decisión:

```text
REJECTED
```

---

### 11.3. Consumidor no autorizado

Si:

```text
authorized == false
```

La política debe rechazar la solicitud.

Código sugerido:

```text
CONSUMER_NOT_AUTHORIZED
```

Decisión:

```text
REJECTED
```

---

### 11.4. Scope faltante o incorrecto

Si el scope no es exactamente:

```text
ai.contract.read
```

La política debe rechazar la solicitud.

Código sugerido:

```text
REQUIRED_SCOPE_MISSING
```

Decisión:

```text
REJECTED
```

---

### 11.5. Versión incompatible

Si la versión solicitada no es compatible con:

```text
v1
```

La política debe rechazar la solicitud.

Código sugerido:

```text
CONTRACT_VERSION_NOT_SUPPORTED
```

Decisión:

```text
REJECTED
```

---

### 11.6. Operación no permitida

Si la operación no es:

```text
READ_CONTRACT
```

La política debe rechazarla.

Código sugerido:

```text
OPERATION_NOT_ALLOWED
```

Decisión:

```text
REJECTED
```

---

### 11.7. Tenant context ausente

Si:

```text
tenantContextPresent == false
```

La política debe rechazar la solicitud.

Código sugerido:

```text
TENANT_CONTEXT_REQUIRED
```

Decisión:

```text
REJECTED
```

---

### 11.8. Contrato bloqueado

Si el contrato está bloqueado o contiene un estado equivalente a bloqueo, la política debe rechazarlo.

Código sugerido:

```text
CONTRACT_NOT_CONSUMABLE
```

Decisión:

```text
REJECTED
```

---

### 11.9. Contrato que requiere revisión humana

Si el contrato tiene:

```text
requiresHumanReview == true
```

La política debe evitar cualquier autorización automática de consumo operativo.

La decisión debe ser:

```text
HUMAN_REVIEW_REQUIRED
```

Código sugerido:

```text
CONTRACT_REQUIRES_HUMAN_REVIEW
```

La política no debe eliminar ni sobrescribir el indicador de revisión humana.

---

### 11.10. Contrato no elegible

Si el contrato está marcado como no elegible para consumo futuro, la política debe rechazarlo.

Código sugerido:

```text
CONTRACT_NOT_ELIGIBLE
```

Decisión:

```text
REJECTED
```

---

### 11.11. Autorización prematura de modelo

Si el contrato contiene:

```text
modelCallAuthorized == true
```

pero no existe una autorización externa real implementada y validada, la política debe rechazar la solicitud o marcarla para revisión humana.

Código sugerido:

```text
PREMATURE_MODEL_AUTHORIZATION
```

La política no debe aceptar este campo como una autorización suficiente.

Debe mantenerse:

```text
modelCallAuthorized == false
```

---

### 11.12. Dispatch no soportado

Si el contrato indica que ya hubo dispatch o que se solicita dispatch, la política debe rechazar la operación.

Código sugerido:

```text
DISPATCH_NOT_SUPPORTED
```

Debe mantenerse:

```text
dispatchStatus == NOT_DISPATCHED
```

---

### 11.13. Entrada inválida

Si faltan datos esenciales o existen combinaciones inconsistentes, la política debe producir una decisión determinística.

Código sugerido:

```text
INVALID_POLICY_INPUT
```

Decisión:

```text
REJECTED
```

---

## 12. Decisiones posibles

Definir un conjunto cerrado de decisiones:

```text
ALLOWED_FOR_FUTURE_CONSUMPTION
REJECTED
HUMAN_REVIEW_REQUIRED
```

No utilizar una decisión como `EXECUTE`, `DISPATCHED`, `MODEL_AUTHORIZED` o equivalente.

---

## 13. Códigos de razón sugeridos

Definir códigos estables y legibles:

```text
CONSUMER_NOT_AUTHENTICATED
CONSUMER_NOT_AUTHORIZED
REQUIRED_SCOPE_MISSING
CONTRACT_VERSION_NOT_SUPPORTED
OPERATION_NOT_ALLOWED
TENANT_CONTEXT_REQUIRED
CONTRACT_NOT_CONSUMABLE
CONTRACT_REQUIRES_HUMAN_REVIEW
CONTRACT_NOT_ELIGIBLE
PREMATURE_MODEL_AUTHORIZATION
DISPATCH_NOT_SUPPORTED
INVALID_POLICY_INPUT
```

La decisión debe incluir al menos un código de razón cuando la solicitud sea rechazada o requiera revisión humana.

---

## 14. Reglas de precedencia

La política debe documentar y probar una precedencia estable.

Orden recomendado:

1. Entrada inválida.
2. Consumidor no autenticado.
3. Consumidor no autorizado.
4. Scope inválido.
5. Versión incompatible.
6. Operación no permitida.
7. Tenant context ausente.
8. Contrato bloqueado o no consumible.
9. Contrato no elegible.
10. Autorización prematura de modelo.
11. Dispatch no soportado.
12. Revisión humana requerida.
13. Consumidor permitido para consumo futuro.

La precedencia debe ser consistente y no depender del orden accidental de evaluación.

---

## 15. Resultado esperado

El resultado debe contener, como mínimo:

```text
decision
reasonCode
contractVersion
consumerType
requestedOperation
requestedScope
modelCallAuthorized
modelCalled
processingStatus
dispatchStatus
requiresHumanReview
```

Los campos deben reflejar el estado real de la evaluación.

La política no debe transformar una decisión de lectura en una autorización de ejecución.

---

## 16. Fronteras arquitectónicas

La dependencia conceptual debe ser:

```text
aiconsumerpolicy -> aiconsumer
```

Opcionalmente, si resulta necesario:

```text
aiconsumerpolicy -> aigateway
```

No se permite dependencia directa hacia:

```text
vendor.*
FhirService
RoutingService
HAPI FHIR
Epic
Oracle Health
SMART
OAuth internals
Bundle
FHIR resources
Snapshot
Projection
Pipeline
Agent
AgentStub
ModelBoundary
FirstAi
AiBoundary
DeterministicAgent
AI SDKs
HTTP clients
RabbitMQ
```

La política debe permanecer en la frontera interna de consumo.

---

## 17. Superficies que deben permanecer ciegas

La implementación no debe conocer ni recibir:

- Datos FHIR crudos.
- Bundles.
- Recursos `Patient`.
- Recursos `MedicationRequest`.
- Patient IDs.
- Identificadores clínicos.
- Tokens.
- Client secrets.
- URLs de proveedores.
- DTOs de Epic.
- DTOs de Oracle.
- Valores clínicos.
- Prompts.
- Respuestas de LLM.
- Resultados generados por IA.
- Credenciales de usuarios.
- Datos personales.

La política debe operar exclusivamente sobre el contrato y metadatos sintéticos.

---

## 18. Observabilidad segura

Si se agregan logs, deben registrar únicamente información técnica y no sensible, por ejemplo:

```text
policyDecision
reasonCode
contractVersion
consumerType
requestedOperation
requestedScope
authenticated
authorized
tenantContextPresent
```

No registrar:

- Tokens.
- Secrets.
- Patient IDs.
- Datos clínicos.
- Bundles.
- Prompts.
- Respuestas de modelos.
- URLs privadas.
- Credenciales.

---

## 19. Pruebas requeridas

Agregar pruebas unitarias determinísticas para, como mínimo:

### Caso A — Consumidor válido

Debe producir:

```text
ALLOWED_FOR_FUTURE_CONSUMPTION
```

### Caso B — Consumidor no autenticado

Debe producir:

```text
REJECTED
CONSUMER_NOT_AUTHENTICATED
```

### Caso C — Consumidor no autorizado

Debe producir:

```text
REJECTED
CONSUMER_NOT_AUTHORIZED
```

### Caso D — Scope incorrecto

Debe producir:

```text
REJECTED
REQUIRED_SCOPE_MISSING
```

### Caso E — Versión incompatible

Debe producir:

```text
REJECTED
CONTRACT_VERSION_NOT_SUPPORTED
```

### Caso F — Operación no permitida

Debe producir:

```text
REJECTED
OPERATION_NOT_ALLOWED
```

### Caso G — Tenant context ausente

Debe producir:

```text
REJECTED
TENANT_CONTEXT_REQUIRED
```

### Caso H — Contrato bloqueado

Debe producir:

```text
REJECTED
CONTRACT_NOT_CONSUMABLE
```

### Caso I — Revisión humana requerida

Debe producir:

```text
HUMAN_REVIEW_REQUIRED
CONTRACT_REQUIRES_HUMAN_REVIEW
```

### Caso J — Autorización prematura

Debe rechazar o enviar a revisión humana cuando:

```text
modelCallAuthorized == true
```

### Caso K — Dispatch no soportado

Debe producir:

```text
REJECTED
DISPATCH_NOT_SUPPORTED
```

### Caso L — Entrada inválida

Debe producir:

```text
REJECTED
INVALID_POLICY_INPUT
```

### Caso M — Ausencia de datos sensibles

Las pruebas y fixtures no deben incluir:

- FHIR crudo.
- Bundles.
- Patient IDs.
- Tokens.
- Secrets.
- Valores clínicos reales.

### Caso N — Compatibilidad con tareas anteriores

Verificar que la implementación no rompa los contratos y estados establecidos en las Tasks 053–061.

---

## 20. Compatibilidad y no regresión

La nueva política debe conservar los siguientes estados de seguridad:

```text
modelCallAuthorized = false
modelCalled = false
processingStatus = NOT_EXECUTED
dispatchStatus = NOT_DISPATCHED
requiresHumanReview = true
```

La Task 062 no debe cambiar estos estados a valores que impliquen ejecución o envío.

No modificar:

- Contratos existentes.
- Endpoints FHIR.
- Integraciones externas.
- Configuración de proveedores.
- Variables de entorno.
- Secretos.
- Flujos de autenticación existentes.
- Pipeline clínico.
- Agente determinístico.
- Contratos de las Tasks 057–061.

---

## 21. Documentación requerida

Crear o actualizar documentación técnica, por ejemplo:

```text
docs/fhir/ai-consumer-policy.md
```

La documentación debe explicar:

- Propósito de la política.
- Entrada y salida.
- Decisiones posibles.
- Códigos de razón.
- Reglas de validación.
- Precedencia.
- Diferencia entre consumo futuro y ejecución.
- Límites de seguridad.
- Ausencia de autenticación real.
- Ausencia de dispatch.
- Ausencia de ejecución de modelos.
- Próximos pasos fuera de esta tarea.

---

## 22. Definition of Done

La tarea se considera terminada cuando:

- Existe una política interna de consumidores.
- La política consume `AiConsumerContract`.
- La política valida identidad sintética.
- La política valida autenticación sintética.
- La política valida autorización sintética.
- La política valida scope.
- La política valida versión.
- La política valida operación.
- La política valida tenant context.
- La política valida el estado del contrato.
- La política distingue rechazo de revisión humana.
- La política no ejecuta modelos.
- La política no autoriza modelos prematuramente.
- La política no realiza dispatch.
- `dispatchStatus` permanece en `NOT_DISPATCHED`.
- `modelCallAuthorized` permanece en `false`.
- `modelCalled` permanece en `false`.
- `processingStatus` permanece en `NOT_EXECUTED`.
- `requiresHumanReview` permanece en `true`.
- No se incorporan tokens reales.
- No se incorporan secretos.
- No se incorporan datos clínicos.
- No se incorporan Patient IDs.
- No se incorporan llamadas HTTP.
- No se incorporan dependencias con Epic u Oracle.
- Las pruebas unitarias pasan.
- Las pruebas de regresión pasan.
- La documentación queda actualizada.
- `.env` permanece intacto.
- El diff contiene únicamente cambios relacionados con esta tarea.

---

## 23. Entregables

1. Implementación de la política de consumidores.
2. DTOs o records internos necesarios.
3. Códigos de razón.
4. Pruebas unitarias.
5. Documentación técnica.
6. Evidencia de ejecución de pruebas.
7. Resumen de archivos modificados.
8. Confirmación de que no se agregaron integraciones externas.
9. Confirmación de que no se modificó `.env`.

---

## 24. Instrucción final para Cursor

Implementa la Task 062 en el repositorio actual respetando estrictamente las fronteras arquitectónicas existentes.

Antes de modificar código:

1. Inspecciona la estructura real del repositorio.
2. Revisa `AiConsumerContract` y sus estados.
3. Revisa la documentación de la Task 061.
4. Revisa los contratos de las Tasks 057–060.
5. Identifica las convenciones de paquetes, records, enums y pruebas.
6. No inventes clases, métodos o campos que no existan sin justificar su incorporación.

Después de implementar:

1. Ejecuta las pruebas unitarias.
2. Ejecuta las pruebas completas del servicio.
3. Verifica que `.env` no haya cambiado.
4. Revisa el diff.
5. Confirma que no existen llamadas HTTP, SDKs de IA, tokens, secretos, FHIR crudo, Bundles ni datos clínicos.
6. Actualiza la documentación.
7. Entrega un resumen técnico con:
   - Archivos creados.
   - Archivos modificados.
   - Pruebas ejecutadas.
   - Resultado de las pruebas.
   - Commit sugerido.
   - Riesgos o decisiones pendientes.
