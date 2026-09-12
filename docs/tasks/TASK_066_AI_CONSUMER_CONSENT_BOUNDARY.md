# Task 066 — Consumer Authorization Decision and Consent Boundary

## 1. WHAT

Diseñar e implementar una frontera aislada posterior a `AiConsumerAuthorizationBoundary` que evalúe, de forma determinística y deny-by-default, si existe un **contexto de consentimiento y propósito de uso** suficiente para una futura operación de consumo.

Esta tarea no debe ejecutar:

- handoff;
- dispatch;
- llamadas HTTP;
- llamadas a modelos;
- acceso a datos clínicos;
- autorización real;
- integración con un proveedor de identidad;
- integración con un sistema de consentimiento externo.

La tarea debe separar explícitamente:

```text
Autenticación del consumidor
    ≠ autorización del consumidor
    ≠ consentimiento del paciente
    ≠ propósito de uso válido
    ≠ handoff autorizado
    ≠ dispatch ejecutado
```

### Nombre sugerido

`ConsumerConsentAndPurposeBoundary`

### Paquete sugerido

```text
lab.healthcare.fhir.aiconsumerconsent
```

### Rama sugerida

```text
feature/ai-consumer-consent-boundary
```

### Commit sugerido

```text
feat: add ai consumer consent boundary
```

No realizar push automático.

---

## 2. WHY

La cadena actual termina en:

```text
AiConsumerAuthorizationBoundary
    → AUTHORIZATION_NOT_IMPLEMENTED
```

La autenticación y autorización del consumidor no son suficientes para permitir el uso de información clínica.

Una futura operación de consumo debe considerar, como mínimo:

- propósito de uso;
- base o contexto de consentimiento;
- alcance de los datos;
- tenant;
- operación solicitada;
- restricciones de uso;
- revisión humana;
- separación entre autorización técnica y autorización clínica.

Task 066 debe preparar esta frontera conceptual sin fingir que existe consentimiento real.

No debe interpretar ningún resultado previo como permiso para:

- consumir datos clínicos;
- ejecutar un handoff;
- invocar un modelo;
- realizar una operación externa.

---

## 3. HOW

## 3.1. Alcance funcional

Crear un componente aislado que:

1. Consuma el resultado de `AiConsumerAuthorizationBoundary`.
2. Reciba un contexto sintético de consentimiento y propósito.
3. Evalúe si el contexto es suficiente para una futura revisión.
4. Mantenga el resultado en estado denegado o no implementado.
5. Produzca razones determinísticas.
6. No consulte sistemas externos.
7. No acceda a recursos FHIR.
8. No procese datos clínicos.
9. No modifique los contratos clínicos existentes.
10. No convierta un contexto sintético en consentimiento real.

La implementación debe distinguir entre:

```text
Consent context present
    ≠ consent verified
```

```text
Purpose declared
    ≠ purpose approved
```

```text
Authorization available
    ≠ clinical data access allowed
```

```text
Consent evaluated
    ≠ handoff authorized
```

---

## 3.2. Entrada principal

El componente debe consumir:

```text
AiConsumerAuthorizationResult
```

desde:

```text
lab.healthcare.fhir.aiconsumerauthorization
```

No debe consumir directamente:

- `FhirService`;
- Epic;
- Oracle;
- HAPI FHIR;
- `Bundle`;
- `Patient`;
- `MedicationRequest`;
- `AiBoundaryResult`;
- `FirstAiResult`;
- `AiExecutionDecision`;
- `AiConsumerContract`;
- `AiConsumerPolicyResult`;
- `AiConsumerReadinessResult`;
- `AiHandoffAuthorizationResult`.

La dependencia principal debe ser únicamente el resultado inmediato de Task 065.

---

## 3.3. Contexto sintético de consentimiento

Crear un modelo interno similar a:

```text
ConsumerConsentContext
```

El nombre puede variar, pero debe representar únicamente metadatos abstractos.

Campos sugeridos:

```text
contextPresent
consentReferencePresent
consentVerified
consentStatus
purposeDeclared
purposeApproved
requestedPurpose
requestedDataScope
dataScopeApproved
tenantContextPresent
consentProviderConfigured
consentSourceTrusted
humanReviewCompleted
```

Los valores deben ser tratados como sintéticos y no confiables.

### Restricciones

No incluir:

- consentimientos reales;
- documentos de consentimiento;
- firmas;
- tokens;
- JWT;
- Patient IDs;
- FHIR JSON;
- Bundle;
- recursos clínicos;
- nombres de pacientes;
- datos de salud;
- URLs privadas;
- secretos;
- credenciales.

No aceptar un campo como:

```text
consentVerified=true
```

como prueba suficiente si no existe un proveedor real configurado.

No aceptar:

```text
purposeApproved=true
```

como autorización real.

---

## 3.4. Resultado principal

Crear un resultado similar a:

```text
AiConsumerConsentResult
```

Estados mínimos sugeridos:

```text
CONSENT_NOT_IMPLEMENTED
PURPOSE_NOT_VERIFIED
DATA_SCOPE_NOT_VERIFIED
BLOCKED
HUMAN_REVIEW_REQUIRED
NOT_ELIGIBLE_FOR_CONSUMPTION
```

No crear estados que impliquen permiso efectivo, tales como:

```text
CONSENT_GRANTED
PURPOSE_APPROVED
DATA_ACCESS_ALLOWED
HANDOFF_AUTHORIZED
DISPATCHED
MODEL_AUTHORIZED
MODEL_CALLED
```

Si se requiere representar una evaluación positiva de forma conceptual, usar un estado no operativo como:

```text
READY_FOR_FUTURE_CONSENT_REVIEW
```

Este estado no debe habilitar consumo ni handoff.

---

## 3.5. Resultado obligatorio

En todas las rutas normales y de error controlado, conservar:

```text
modelCallAuthorized=false
modelCalled=false
processingStatus=NOT_EXECUTED
dispatchStatus=NOT_DISPATCHED
requiresHumanReview=true
handoffAuthorized=false
dispatchPerformed=false
externalAuthorizationAvailable=false
authenticationVerified=false
authorizationGranted=false
realSecurityProviderConfigured=false
consumerAuthorizationAvailable=false
```

Agregar como invariantes de Task 066:

```text
consentVerified=false
purposeApproved=false
dataScopeApproved=false
consentProviderConfigured=false
consentAvailable=false
clinicalDataAccessAllowed=false
```

Los nombres pueden variar, pero el significado debe permanecer.

---

## 3.6. Reglas determinísticas

### Regla A — Entrada de autorización inexistente

Si `AiConsumerAuthorizationResult` es inexistente:

```text
status=BLOCKED
reason=MISSING_CONSUMER_AUTHORIZATION_RESULT
```

### Regla B — Autorización previa no implementada

Si:

```text
consumerAuthorizationAvailable=false
```

el resultado debe permanecer denegado:

```text
status=CONSENT_NOT_IMPLEMENTED
reason=CONSUMER_AUTHORIZATION_NOT_AVAILABLE
```

### Regla C — Autorización concedida inesperadamente

Si la entrada contiene:

```text
authorizationGranted=true
```

o:

```text
consumerAuthorizationAvailable=true
```

sin un proveedor real:

```text
status=BLOCKED
reason=UNEXPECTED_CONSUMER_AUTHORIZATION
```

No propagar esos valores como autorización válida.

### Regla D — Contexto de consentimiento ausente

Si no existe contexto:

```text
status=CONSENT_NOT_IMPLEMENTED
reason=MISSING_CONSENT_CONTEXT
```

### Regla E — Referencia de consentimiento no verificada

Si existe una referencia sintética, pero no está verificada:

```text
status=CONSENT_NOT_IMPLEMENTED
reason=CONSENT_REFERENCE_NOT_VERIFIED
```

Una referencia textual no demuestra consentimiento válido.

### Regla F — Consentimiento declarado como verificado

Si el contexto declara:

```text
consentVerified=true
```

pero:

```text
consentProviderConfigured=false
```

el resultado debe ser:

```text
status=BLOCKED
reason=UNTRUSTED_CONSENT_ASSERTION
```

### Regla G — Propósito no declarado

Si no existe propósito:

```text
status=PURPOSE_NOT_VERIFIED
reason=MISSING_PURPOSE
```

### Regla H — Propósito declarado, pero no aprobado

Si existe propósito, pero no existe una evaluación confiable:

```text
status=PURPOSE_NOT_VERIFIED
reason=PURPOSE_NOT_APPROVED
```

### Regla I — Propósito aprobado sintéticamente

Si el contexto declara:

```text
purposeApproved=true
```

sin un proveedor o proceso real:

```text
status=BLOCKED
reason=UNTRUSTED_PURPOSE_ASSERTION
```

### Regla J — Alcance de datos ausente

Si no se declara alcance de datos:

```text
status=DATA_SCOPE_NOT_VERIFIED
reason=MISSING_DATA_SCOPE
```

### Regla K — Alcance de datos aprobado sintéticamente

Si:

```text
dataScopeApproved=true
```

sin verificación real:

```text
status=BLOCKED
reason=UNTRUSTED_DATA_SCOPE_ASSERTION
```

### Regla L — Tenant ausente

Si no existe contexto de tenant verificable:

```text
status=BLOCKED
reason=MISSING_TENANT_CONTEXT
```

### Regla M — Revisión humana no completada

Si la política requiere revisión humana y:

```text
humanReviewCompleted=false
```

el resultado debe ser:

```text
status=HUMAN_REVIEW_REQUIRED
reason=HUMAN_REVIEW_NOT_COMPLETED
```

Nunca apagar:

```text
requiresHumanReview=true
```

### Regla N — Parámetros de activación

El resultado no debe cambiar por query parameters como:

```text
?consent=true
?consentVerified=true
?purposeApproved=true
?dataScopeApproved=true
?allow=true
?dispatch=true
?handoff=true
```

Tampoco por headers arbitrarios como:

```text
X-Consent-Verified
X-Purpose-Approved
X-Data-Scope-Approved
X-Allow-Clinical-Access
```

Estos valores deben ignorarse o producir una decisión denegada.

---

## 3.7. Propósitos permitidos en el contrato conceptual

Definir una enumeración limitada para propósitos sintéticos, por ejemplo:

```text
FOLLOW_UP_SUPPORT
CLINICAL_SUMMARY_REVIEW
PATIENT_ENGAGEMENT_SUPPORT
RESEARCH
ADMINISTRATIVE_SUPPORT
UNKNOWN
```

Esta enumeración no concede permisos.

No implementar lógica clínica basada en el propósito.

No permitir que un propósito:

```text
RESEARCH
```

o:

```text
CLINICAL_SUMMARY_REVIEW
```

habilite automáticamente:

- acceso a pacientes;
- acceso a Bundle;
- acceso a MedicationRequest;
- invocación de modelos;
- handoff;
- dispatch.

Si el propósito es `UNKNOWN` o está ausente:

```text
status=PURPOSE_NOT_VERIFIED
reason=UNKNOWN_OR_MISSING_PURPOSE
```

---

## 3.8. Alcance de datos

El alcance debe ser abstracto y no clínico.

Ejemplos permitidos:

```text
SUMMARY_METADATA
NON_CLINICAL_STATUS
SYNTHETIC_DEMO_CONTEXT
```

No utilizar como datos de entrada:

- Patient IDs;
- recursos FHIR;
- diagnósticos;
- medicamentos;
- observaciones;
- nombres;
- fechas clínicas;
- identificadores reales.

El alcance sintético no debe interpretarse como permiso para consultar datos reales.

---

## 3.9. Endpoint de laboratorio

Si se agrega un endpoint, utilizar uno de estos nombres:

```text
GET /lab/ai-consumer-consent
```

o:

```text
GET /api/ai-consumer-consent/v1
```

Debe ser exclusivamente de laboratorio.

No debe:

- aceptar tokens;
- aceptar credenciales;
- aceptar Patient IDs;
- aceptar FHIR JSON;
- aceptar documentos de consentimiento;
- consultar Epic;
- consultar Oracle;
- consultar una base de datos clínica;
- ejecutar handoff;
- ejecutar dispatch;
- llamar a modelos;
- enviar mensajes;
- conceder consentimiento real.

La respuesta debe contener solamente estados sintéticos y razones no sensibles.

---

## 3.10. Integración con la proyección clínica

La proyección puede exponer un resumen no sensible como:

```text
aiConsumerConsent=CONSENT_NOT_IMPLEMENTED
aiConsumerPurpose=PURPOSE_NOT_VERIFIED
aiConsumerDataScope=DATA_SCOPE_NOT_VERIFIED
aiConsumerConsentAvailable=false
aiClinicalDataAccessAllowed=false
```

No cambiar ni reinterpretar los estados existentes:

```text
controlledProjection=SUCCEEDED
modelBoundaryContract=v1
agentStub=SUCCEEDED
deterministicAgent=READY
aiBoundary=PREPARED
clinicalDataAvailable=true
modelCallAuthorized=false
aiModelCalled=false
medicationRequestsStatus=NOT_REQUESTED
firstAiComponent=PREPARED
aiProcessingStatus=NOT_EXECUTED
aiExecutionGate=ELIGIBLE_BUT_NOT_AUTHORIZED
aiConsumerContract=v1
aiConsumerStatus=READY
aiDispatchStatus=NOT_DISPATCHED
aiConsumerPolicy=ALLOWED_FOR_FUTURE_CONSUMPTION
aiConsumerReadiness=READY_FOR_FUTURE_HANDOFF
aiHandoffAuthorization=HANDOFF_NOT_AUTHORIZED
aiConsumerAuthentication=NOT_AUTHENTICATED
aiConsumerAuthorization=AUTHORIZATION_NOT_IMPLEMENTED
aiConsumerAuthorizationAvailable=false
```

La nueva frontera debe agregarse sin sobrescribir campos previos.

---

## 3.11. Reglas de aislamiento

El paquete nuevo puede depender únicamente de:

```text
lab.healthcare.fhir.aiconsumerauthorization
```

No debe depender directamente de:

```text
lab.healthcare.fhir
lab.healthcare.fhir.service
lab.healthcare.fhir.epic
lab.healthcare.fhir.oracle
lab.healthcare.fhir.pipeline
lab.healthcare.fhir.agent
lab.healthcare.fhir.aiboundary
lab.healthcare.fhir.firstai
lab.healthcare.fhir.aigateway
lab.healthcare.fhir.aiconsumer
lab.healthcare.fhir.aiconsumerpolicy
lab.healthcare.fhir.aiconsumerreadiness
lab.healthcare.fhir.aihandoffauthorization
```

Excepto la dependencia directa permitida hacia Task 065.

No importar:

- HAPI FHIR;
- `FhirContext`;
- recursos R4;
- `Bundle`;
- `Patient`;
- `MedicationRequest`;
- clientes HTTP;
- `WebClient`;
- `RestClient`;
- Feign;
- RabbitMQ;
- SDKs de modelos;
- clases de Epic;
- clases de Oracle;
- proveedores de consentimiento reales;
- sistemas externos de autorización.

No debe ser importado por:

- `FhirService`;
- adaptadores Epic;
- adaptadores Oracle;
- pipeline clínico;
- `DeterministicAgent`;
- `AiBoundary`;
- `FirstAiComponent`;
- `AiExecutionGate`;
- `AiConsumerContract`;
- `AiConsumerPolicy`;
- `AiConsumerReadiness`;
- `AiHandoffAuthorizationBoundary`;
- `AiConsumerAuthorizationBoundary`.

La integración con la proyección debe realizarse mediante un adaptador o ensamblador explícito.

---

## 3.12. Contrato de auditoría

El resultado debe incluir campos no sensibles como:

```text
status
reason
operation
requestedPurpose
requestedDataScope
consentVerified
purposeApproved
dataScopeApproved
consentProviderConfigured
consentAvailable
clinicalDataAccessAllowed
humanReviewCompleted
handoffAuthorized
dispatchPerformed
modelCallAuthorized
modelCalled
processingStatus
dispatchStatus
requiresHumanReview
```

No registrar:

- consentimientos completos;
- firmas;
- tokens;
- credenciales;
- Patient IDs;
- nombres;
- diagnósticos;
- medicamentos;
- Bundle;
- FHIR JSON;
- payloads completos;
- secretos.

Los logs, si existen, deben registrar únicamente:

```text
status
reason
operation
```

---

## 4. CONCEPT

## 4.1. Consentimiento

El consentimiento representa una base de autorización relacionada con el uso de información.

En esta tarea no se verifica ningún consentimiento real.

Por ello:

```text
consentReferencePresent=true
```

no implica:

```text
consentVerified=true
```

y:

```text
consentVerified=true
```

no debe aceptarse sin un proveedor real.

---

## 4.2. Propósito de uso

El propósito responde:

> ¿Para qué se pretende utilizar la información?

Declarar un propósito no significa que esté aprobado.

La aprobación debe permanecer fuera del alcance de Task 066.

---

## 4.3. Alcance de datos

El alcance define qué tipo de información podría utilizarse en una futura operación.

Task 066 no permite acceder a datos clínicos reales.

El alcance sintético sirve únicamente para demostrar que:

```text
purpose
    ≠ data scope
    ≠ clinical access
```

---

## 4.4. Autorización técnica frente a autorización de uso

Aunque un consumidor estuviera autenticado y autorizado técnicamente, todavía sería necesario evaluar si el uso pretendido es válido.

La separación conceptual es:

```text
Consumer authenticated
    ≠ Consumer authorized
    ≠ Consent verified
    ≠ Purpose approved
    ≠ Data scope approved
    ≠ Clinical data access allowed
    ≠ Handoff authorized
    ≠ Dispatch executed
```

---

## 4.5. Deny-by-default

La ausencia de consentimiento verificable, propósito aprobado o alcance autorizado debe producir una decisión denegada o no implementada.

Nunca debe producir permiso implícito.

```text
missing consent → deny
missing purpose → deny
missing data scope → deny
synthetic assertion → block
missing tenant → block
human review pending → human review required
```

---

## 4.6. Revisión humana

La revisión humana continúa siendo obligatoria.

Task 066 no debe cambiar:

```text
requiresHumanReview=true
```

La existencia de un contexto de consentimiento sintético no elimina la necesidad de revisión.

---

## 4.7. Estado de preparación

Task 066 prepara una frontera para una futura evaluación de consentimiento y propósito.

No implementa:

- consentimiento real;
- proveedores de consentimiento;
- OAuth;
- JWT;
- SMART on FHIR;
- autorización clínica real;
- acceso a datos;
- handoff;
- dispatch;
- inferencia;
- recomendaciones;
- diagnóstico;
- prescripción.

---

## 5. Pruebas requeridas

Agregar pruebas unitarias y de integración aisladas.

### Prueba A — Entrada válida de Task 065 sin proveedor de consentimiento

Esperado:

```text
status=CONSENT_NOT_IMPLEMENTED
consentVerified=false
purposeApproved=false
dataScopeApproved=false
consentAvailable=false
clinicalDataAccessAllowed=false
```

### Prueba B — Resultado de autorización inexistente

Esperado:

```text
status=BLOCKED
reason=MISSING_CONSUMER_AUTHORIZATION_RESULT
```

### Prueba C — Autorización previa no disponible

Esperado:

```text
status=CONSENT_NOT_IMPLEMENTED
reason=CONSUMER_AUTHORIZATION_NOT_AVAILABLE
```

### Prueba D — Consentimiento ausente

Esperado:

```text
status=CONSENT_NOT_IMPLEMENTED
reason=MISSING_CONSENT_CONTEXT
```

### Prueba E — Consentimiento sintético marcado como verificado

Esperado:

```text
status=BLOCKED
reason=UNTRUSTED_CONSENT_ASSERTION
```

### Prueba F — Propósito ausente

Esperado:

```text
status=PURPOSE_NOT_VERIFIED
reason=MISSING_PURPOSE
```

### Prueba G — Propósito aprobado sintéticamente

Esperado:

```text
status=BLOCKED
reason=UNTRUSTED_PURPOSE_ASSERTION
```

### Prueba H — Alcance de datos ausente

Esperado:

```text
status=DATA_SCOPE_NOT_VERIFIED
reason=MISSING_DATA_SCOPE
```

### Prueba I — Alcance aprobado sintéticamente

Esperado:

```text
status=BLOCKED
reason=UNTRUSTED_DATA_SCOPE_ASSERTION
```

### Prueba J — Tenant ausente

Esperado:

```text
status=BLOCKED
reason=MISSING_TENANT_CONTEXT
```

### Prueba K — Revisión humana pendiente

Esperado:

```text
status=HUMAN_REVIEW_REQUIRED
reason=HUMAN_REVIEW_NOT_COMPLETED
requiresHumanReview=true
```

### Prueba L — Parámetros de activación

Verificar que los siguientes parámetros no cambien el resultado:

```text
consent=true
consentVerified=true
purposeApproved=true
dataScopeApproved=true
allow=true
dispatch=true
handoff=true
```

### Prueba M — Headers de activación

Verificar que headers arbitrarios no concedan consentimiento ni acceso.

### Prueba N — Invariantes globales

Para todos los estados:

```text
modelCallAuthorized=false
modelCalled=false
processingStatus=NOT_EXECUTED
dispatchStatus=NOT_DISPATCHED
requiresHumanReview=true
handoffAuthorized=false
dispatchPerformed=false
externalAuthorizationAvailable=false
authenticationVerified=false
authorizationGranted=false
realSecurityProviderConfigured=false
consumerAuthorizationAvailable=false
consentVerified=false
purposeApproved=false
dataScopeApproved=false
consentProviderConfigured=false
consentAvailable=false
clinicalDataAccessAllowed=false
```

### Prueba O — No regresión

Verificar que Tasks 057–065 mantengan sus estados actuales.

En particular:

```text
aiHandoffAuthorization=HANDOFF_NOT_AUTHORIZED
aiConsumerAuthentication=NOT_AUTHENTICATED
aiConsumerAuthorization=AUTHORIZATION_NOT_IMPLEMENTED
aiConsumerAuthorizationAvailable=false
```

### Prueba P — No dependencias prohibidas

Verificar que el nuevo paquete no importe:

- HAPI FHIR;
- Epic;
- Oracle;
- HTTP clients;
- RabbitMQ;
- SDKs de modelos;
- proveedores de consentimiento reales.

### Prueba Q — No datos sensibles

Verificar que respuestas y logs no incluyan:

- tokens;
- Patient IDs;
- FHIR JSON;
- Bundle;
- datos clínicos;
- documentos de consentimiento;
- firmas.

---

## 6. Documentación requerida

Crear:

```text
docs/fhir/ai-consumer-consent-boundary.md
```

La documentación debe incluir:

1. objetivo;
2. alcance;
3. estados;
4. contrato de entrada;
5. contrato de salida;
6. contexto sintético de consentimiento;
7. propósito de uso;
8. alcance de datos;
9. reglas deny-by-default;
10. diferencia entre autenticación, autorización y consentimiento;
11. invariantes;
12. parámetros que no conceden permiso;
13. dependencias permitidas;
14. dependencias prohibidas;
15. ejemplos sintéticos;
16. limitaciones;
17. trabajo fuera de alcance.

Actualizar:

```text
docs/progress/progress-log.md
```

Incluir:

- fecha;
- Task 066;
- rama;
- commit;
- resumen;
- pruebas ejecutadas;
- resultado;
- invariantes verificadas.

No incluir tokens, secretos, Patient IDs ni FHIR JSON.

---

## 7. Definition of Done

Task 066 está terminada cuando:

- [ ] Existe el paquete aislado `aiconsumerconsent`.
- [ ] Consume únicamente el resultado de Task 065.
- [ ] Define un contexto sintético de consentimiento.
- [ ] Define propósito de uso.
- [ ] Define alcance de datos abstracto.
- [ ] No implementa consentimiento real.
- [ ] No implementa proveedor externo.
- [ ] Mantiene deny-by-default.
- [ ] No concede `consentVerified=true`.
- [ ] No concede `purposeApproved=true`.
- [ ] No concede `dataScopeApproved=true`.
- [ ] No concede `clinicalDataAccessAllowed=true`.
- [ ] No concede `handoffAuthorized=true`.
- [ ] No concede `dispatchPerformed=true`.
- [ ] No concede `modelCallAuthorized=true`.
- [ ] Mantiene `modelCalled=false`.
- [ ] Mantiene `processingStatus=NOT_EXECUTED`.
- [ ] Mantiene `dispatchStatus=NOT_DISPATCHED`.
- [ ] Mantiene `requiresHumanReview=true`.
- [ ] No incorpora LLM ni `ai-service`.
- [ ] No incorpora HTTP clients.
- [ ] No incorpora RabbitMQ.
- [ ] No incorpora OAuth, JWT, SMART ni tokens.
- [ ] No modifica el contrato clínico v1.
- [ ] No amplía la allowlist 042.
- [ ] No agrega `MedicationRequest` en Epic.
- [ ] No registra datos sensibles.
- [ ] Tiene pruebas para entradas válidas, inválidas e inconsistentes.
- [ ] Tiene pruebas de no activación por query params y headers.
- [ ] Tiene pruebas de no regresión.
- [ ] Tiene documentación.
- [ ] Los tests existentes continúan pasando.
- [ ] Se ejecuta `mvn test` correctamente.
- [ ] Se verifica el endpoint live sin cambios clínicos.
- [ ] El commit usa Conventional Commits.
- [ ] No se realiza push automático.

---

## 8. Instrucción final para Cursor

Implementa únicamente **Task 066 — Consumer Authorization Decision and Consent Boundary**.

No implementes Task 067 ni ninguna etapa posterior.

No reescribas Tasks 057–065.

No introduzcas consentimiento real, proveedores externos, OAuth2, JWT, SMART on FHIR, tokens, identidad federada, autorización clínica real, acceso a datos, handoff, dispatch, WebClient, Feign, RabbitMQ, LLM, OpenAI, Azure OpenAI, Gemini, Claude, RAG, LangGraph ni `ai-service`.

La implementación debe ser una frontera aislada, determinística y deny-by-default que represente la separación entre autenticación, autorización, consentimiento, propósito de uso, alcance de datos, acceso clínico, handoff y dispatch.

Mantén obligatoriamente:

```text
modelCallAuthorized=false
modelCalled=false
processingStatus=NOT_EXECUTED
dispatchStatus=NOT_DISPATCHED
requiresHumanReview=true
handoffAuthorized=false
dispatchPerformed=false
externalAuthorizationAvailable=false
authenticationVerified=false
authorizationGranted=false
realSecurityProviderConfigured=false
consumerAuthorizationAvailable=false
consentVerified=false
purposeApproved=false
dataScopeApproved=false
consentProviderConfigured=false
consentAvailable=false
clinicalDataAccessAllowed=false
```

No uses parámetros HTTP ni headers para activar consentimiento, propósito aprobado, alcance autorizado o acceso clínico.

No registres tokens, secretos, Patient IDs, FHIR JSON, Bundle, datos clínicos ni documentos de consentimiento.

Ejecuta todas las pruebas existentes y las nuevas pruebas de Task 066. Actualiza la documentación y el progress log. Usa una rama `feature/*` y un commit Conventional Commit:

```text
feat: add ai consumer consent boundary
```

No hagas push automático.
