# TASK 068 — Clinical Data Access Request and Enforcement Boundary

## 1. Informe de posición

### Estado de la plataforma

Task 067 está implementada, validada en vivo y commiteada:

- Rama: `feature/ai-consumer-data-scope-boundary`
- Commit: `1af857a` — `feat: add ai consumer data scope boundary`
- Tests: `863/0`

La cadena actual llega hasta una frontera sintética de alcance y minimización:

```text
AiConsumerConsentBoundary
  → AiConsumerDataScopeBoundary
```

El estado actual continúa siendo deny-by-default:

```text
aiConsumerClinicalDataScope=NOT_READY_FOR_CLINICAL_DATA_ACCESS
aiConsumerScopeDeclared=false
aiConsumerScopeEvaluated=false
aiConsumerMinimizationEvaluated=false
aiConsumerPurposeScopeAlignmentEvaluated=false
aiClinicalDataScopeProviderConfigured=false
aiClinicalDataScopeApprovalAvailable=false
aiClinicalDataAccessRequested=false
aiClinicalDataAccessGranted=false
aiClinicalDataAccessAllowed=false
```

### Posición para Task 068

Task 068 debe implementar únicamente una frontera aislada de **solicitud y aplicación sintética de acceso a datos clínicos**.

La tarea debe representar que un futuro consumidor podría solicitar acceso a un alcance de datos previamente declarado, pero debe impedir que esa solicitud se convierta en acceso real.

No debe consultar FHIR, no debe leer recursos clínicos, no debe emitir tokens, no debe invocar proveedores externos y no debe autorizar acceso clínico.

La distinción central es:

```text
acceso solicitado ≠ acceso aprobado
acceso aprobado ≠ acceso concedido
acceso concedido ≠ lectura FHIR
```

---

## 2. WHAT

Diseñar e implementar una frontera Java aislada que consuma exclusivamente el resultado de Task 067 y produzca una decisión sintética sobre una posible solicitud de acceso clínico.

La frontera debe:

1. identificar si existe una solicitud sintética de acceso;
2. comprobar si la solicitud está relacionada con un alcance declarado;
3. comprobar si existe una decisión sintética previa de preparación;
4. mantener el acceso clínico bloqueado cuando no existe un proveedor real;
5. representar explícitamente que la solicitud no ha sido concedida;
6. impedir cualquier acceso indirecto a recursos FHIR;
7. mantener la revisión humana obligatoria.

### Nombre sugerido

`ClinicalDataAccessRequestBoundary`

### Paquete sugerido

```text
lab.healthcare.fhir.aiconsumeraccess
```

### Rama sugerida

```text
feature/ai-consumer-clinical-data-access-boundary
```

### Commit sugerido

```text
feat: add ai consumer clinical data access boundary
```

No hacer push automático. No crear PR.

---

## 3. WHY

Las tareas anteriores ya separan:

- contrato de consumidor;
- política sintética;
- readiness;
- autorización de handoff;
- autenticación;
- autorización;
- consentimiento;
- propósito;
- alcance de datos;
- minimización.

La siguiente frontera debe impedir que una solicitud de acceso sea interpretada como una concesión.

Un futuro consumidor podría declarar:

- que necesita datos clínicos;
- qué categorías requiere;
- para qué propósito;
- dentro de qué tenant;
- con qué límites de minimización.

Sin embargo, una solicitud no representa una autorización.

Task 068 debe hacer visible esta separación:

```text
alcance declarado
  →
solicitud de acceso
  →
evaluación futura
  →
aprobación real
  →
concesión real
  →
lectura clínica
```

Task 068 solo puede representar los primeros pasos de forma sintética. No debe implementar los pasos reales.

---

## 4. CONCEPT

### 4.1. Conceptos nuevos

#### Clinical data access request

Solicitud declarativa de un futuro consumidor para utilizar un alcance de datos clínicos.

La solicitud es únicamente un metadato sintético. No activa consultas, permisos, tokens ni acceso.

#### Access request evaluation

Evaluación local y determinista de si la solicitud está suficientemente definida para una futura revisión.

No es una decisión de autorización.

#### Access grant

Concesión efectiva de acceso clínico.

Task 068 no la implementa y debe mantenerla deshabilitada.

#### Enforcement boundary

Frontera que impide que un estado sintético de solicitud o preparación active acceso real.

### 4.2. Estados sugeridos

Definir un enum o representación equivalente con estados explícitos:

```text
ACCESS_REQUEST_NOT_DECLARED
ACCESS_REQUEST_DECLARED_NOT_EVALUATED
ACCESS_REQUEST_REQUIRES_SCOPE
ACCESS_REQUEST_REQUIRES_REAL_AUTHORIZATION
ACCESS_REQUEST_BLOCKED
ACCESS_REQUEST_REQUIRES_HUMAN_REVIEW
NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS
```

El estado normal esperado para la ruta live debe ser:

```text
NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS
```

No crear un estado que implique:

```text
CLINICAL_DATA_ACCESS_GRANTED
CLINICAL_DATA_ACCESS_ALLOWED
FHIR_ACCESS_ENABLED
```

---

## 5. Alcance funcional

### 5.1. Entrada

Consumir únicamente:

```text
AiConsumerDataScopeResult
```

producido por Task 067.

No importar ni consumir directamente:

- `AiConsumerConsentResult`;
- `AiConsumerAuthorizationResult`;
- `AiHandoffAuthorizationResult`;
- `AiConsumerReadinessResult`;
- `AiConsumerPolicyResult`;
- `AiConsumerContract`;
- `FirstAiResult`;
- `AiBoundaryResult`;
- objetos del pipeline FHIR;
- recursos HAPI FHIR;
- entidades de Epic;
- entidades de Oracle.

Si el diseño necesita transportar una solicitud sintética, definir un contexto local no confiable, por ejemplo:

```text
ClinicalDataAccessRequestContext
```

Este contexto no debe representar una autorización real.

### 5.2. Salida

Crear un resultado explícito, por ejemplo:

```text
AiConsumerClinicalDataAccessResult
```

Debe incluir, como mínimo:

```text
status
accessRequestDeclared
accessRequestEvaluated
scopeReferencePresent
realAuthorizationRequired
clinicalDataAccessRequested
clinicalDataAccessGranted
clinicalDataAccessAllowed
requiresHumanReview
```

Campos recomendados:

```text
boundaryVersion
inputAvailable
requestSource
requestedDataCategories
requestedResourceTypes
requestedTenantScope
requestEvaluationStatus
enforcementStatus
decisionReason
```

Los campos deben contener únicamente metadatos sintéticos y no datos clínicos reales.

### 5.3. Resultado esperado

Con la entrada actual de Task 067, el resultado debe representar:

```text
accessRequestDeclared=false
accessRequestEvaluated=false
scopeReferencePresent=false
realAuthorizationRequired=true
clinicalDataAccessRequested=false
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
requiresHumanReview=true
status=NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS
```

Si el contexto sintético contiene una solicitud, la frontera puede clasificarla como declarada o pendiente de evaluación, pero nunca como concedida.

---

## 6. Reglas deterministas

### Regla A — Input ausente

Si `AiConsumerDataScopeResult` es `null` o inválido:

```text
status=ACCESS_REQUEST_BLOCKED
requiresHumanReview=true
clinicalDataAccessRequested=false
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
```

### Regla B — Alcance no preparado

Si:

```text
scopeEvaluated=false
```

o:

```text
clinicalDataScopeApprovalAvailable=false
```

no puede existir una concesión de acceso.

Resultado mínimo:

```text
status=NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
requiresHumanReview=true
```

### Regla C — Acceso solicitado sin alcance

Si existe una solicitud sintética, pero no existe referencia a un alcance:

```text
status=ACCESS_REQUEST_REQUIRES_SCOPE
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
requiresHumanReview=true
```

### Regla D — Solicitud declarada

Si existe una solicitud sintética:

```text
accessRequestDeclared=true
accessRequestEvaluated=false
```

La frontera debe mantener:

```text
clinicalDataAccessRequested=false
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
```

La declaración no debe convertirse automáticamente en una solicitud efectiva.

### Regla E — Solicitud efectiva sintética

Si el diseño representa una solicitud efectiva dentro de un contexto local, debe registrarse como metadato no confiable:

```text
clinicalDataAccessRequested=true
```

pero siempre:

```text
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
requiresHumanReview=true
```

Este caso solo es válido para demostrar la separación entre solicitar y conceder. No debe producir efectos externos.

### Regla F — Autorización real ausente

Si no existe proveedor real de autorización:

```text
realAuthorizationRequired=true
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
```

No crear un proveedor simulado que devuelva autorización positiva.

### Regla G — Consentimiento o propósito no verificados

Si el resultado previo mantiene:

```text
consentVerified=false
purposeApproved=false
```

la solicitud debe permanecer bloqueada o pendiente de revisión humana.

### Regla H — Tenant ausente

Si falta el tenant o el alcance de tenant no está definido:

```text
status=ACCESS_REQUEST_BLOCKED
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
requiresHumanReview=true
```

### Regla I — Deny by default

Ante cualquier ambigüedad:

```text
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
requiresHumanReview=true
```

### Regla J — No enforcement clínico real

Ningún resultado de esta tarea puede:

- activar un cliente FHIR;
- permitir una consulta;
- habilitar un endpoint clínico;
- crear un token;
- modificar scopes OAuth;
- activar SMART;
- modificar permisos de usuario;
- abrir acceso a un tenant;
- leer un recurso clínico.

---

## 7. Invariantes obligatorios

Task 068 debe preservar siempre:

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
scopeEvaluated=false
minimizationEvaluated=false
purposeScopeAlignmentEvaluated=false
clinicalDataScopeProviderConfigured=false
clinicalDataScopeApprovalAvailable=false
clinicalDataAccessRequested=false
clinicalDataAccessGranted=false
```

Invariantes nuevos:

```text
accessRequestEvaluated=false
clinicalDataAccessGrantAvailable=false
clinicalDataAccessEnforced=false
clinicalDataAccessProviderConfigured=false
clinicalDataAccessAuthorizationAvailable=false
```

Si alguno de estos campos no existe todavía, agregarlo únicamente en el resultado de Task 068 o en el contrato técnico estrictamente necesario. No cambiar campos clínicos existentes del contrato v1.

---

## 8. Arquitectura y aislamiento

### 8.1. Dependencias permitidas

Permitido:

- Java 21;
- clases Java estándar;
- Spring Boot existente;
- records, enums y servicios puros;
- validación local;
- tests unitarios;
- integración con las superficies locales ya existentes, si se requiere mostrar el estado.

### 8.2. Dependencias prohibidas

No usar:

- HAPI FHIR;
- `FhirContext`;
- `Patient`;
- `Bundle`;
- `MedicationRequest`;
- `Observation`;
- `Condition`;
- `Encounter`;
- clientes HTTP;
- WebClient;
- Feign;
- RestClient;
- RabbitMQ;
- OAuth;
- JWT;
- SMART on FHIR;
- tokens;
- SDKs de Epic;
- SDKs de Oracle;
- proveedores reales de autorización;
- bases de datos nuevas;
- LLM;
- OpenAI;
- Azure OpenAI;
- Gemini;
- Claude;
- RAG;
- LangGraph;
- `ai-service`.

### 8.3. Imports prohibidos en el núcleo

El núcleo de `aiconsumeraccess` no debe importar:

```text
lab.healthcare.fhir.aiconsumerscope
lab.healthcare.fhir.aiconsumer
lab.healthcare.fhir.aiconsumerpolicy
lab.healthcare.fhir.aiconsumerreadiness
lab.healthcare.fhir.aihandoffauthorization
lab.healthcare.fhir.aiconsumerauthorization
lab.healthcare.fhir.aiconsumerconsent
lab.healthcare.fhir.firstai
lab.healthcare.fhir.aigateway
lab.healthcare.fhir.aiboundary
```

Tampoco debe importar paquetes de pipeline, vendor o HAPI FHIR.

Debe consumir únicamente el contrato de entrada de Task 067 mediante una dependencia explícita y mínima.

---

## 9. Superficies HTTP

Agregar una superficie local únicamente si el proyecto ya utiliza este patrón.

Ruta sugerida:

```text
GET /lab/ai-consumer-clinical-data-access
```

Ruta API sugerida:

```text
GET /api/ai-consumer-clinical-data-access/v1
```

Integrar en:

```text
GET /epic/sandbox/fhir/clinical-projection
```

solo como proyección de estado.

No crear endpoints que:

- acepten `clinicalDataAccessAllowed=true`;
- acepten `clinicalDataAccessGranted=true`;
- acepten `scopeApproved=true`;
- acepten autorización por query parameters;
- acepten autorización por headers;
- acepten tokens;
- ejecuten consultas FHIR.

La respuesta HTTP debe ser JSON técnico, sin datos de pacientes, documentos de consentimiento ni tokens.

---

## 10. Contrato HTTP sugerido

Ejemplo conceptual:

```json
{
  "boundaryVersion": "v1",
  "status": "NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS",
  "accessRequestDeclared": false,
  "accessRequestEvaluated": false,
  "scopeReferencePresent": false,
  "realAuthorizationRequired": true,
  "clinicalDataAccessRequested": false,
  "clinicalDataAccessGranted": false,
  "clinicalDataAccessAllowed": false,
  "clinicalDataAccessGrantAvailable": false,
  "clinicalDataAccessEnforced": false,
  "requiresHumanReview": true
}
```

El ejemplo es ilustrativo. Adaptar nombres al estilo real del proyecto sin inventar campos incompatibles con contratos existentes.

No incluir:

```text
patientId
patientIds
FHIR JSON
Bundle
clinical notes
consent document
access token
refresh token
authorization code
```

---

## 11. Pruebas obligatorias

Crear pruebas unitarias y, si corresponde, pruebas de integración para la superficie local.

### A — Entrada válida actual

Con el resultado realista de Task 067:

- el resultado es `NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS`;
- `clinicalDataAccessRequested=false`;
- `clinicalDataAccessGranted=false`;
- `clinicalDataAccessAllowed=false`;
- `requiresHumanReview=true`.

### B — Input ausente

Debe producir bloqueo seguro.

### C — Alcance no evaluado

Debe impedir cualquier concesión.

### D — Alcance no aprobado

Debe mantener el acceso bloqueado.

### E — Solicitud ausente

Debe producir `ACCESS_REQUEST_NOT_DECLARED`.

### F — Solicitud declarada sintéticamente

Debe indicar que fue declarada, pero no evaluada ni concedida.

### G — Solicitud sin alcance

Debe producir `ACCESS_REQUEST_REQUIRES_SCOPE`.

### H — Solicitud efectiva sintética

Si se modela, debe mantener:

```text
clinicalDataAccessRequested=true
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
```

sin side effects.

### I — Autorización real ausente

Debe mantener `realAuthorizationRequired=true`.

### J — Tenant ausente

Debe producir bloqueo seguro.

### K — Contexto sintético manipulado

Aunque el contexto indique valores positivos, el resultado no debe activar:

```text
clinicalDataAccessGranted=true
clinicalDataAccessAllowed=true
```

### L — Query parameters

Los parámetros como:

```text
?clinicalDataAccessAllowed=true
?clinicalDataAccessGranted=true
?scopeApproved=true
```

no deben cambiar el resultado.

### M — Headers

Headers como:

```text
X-Clinical-Data-Access: true
X-Clinical-Data-Granted: true
X-Scope-Approved: true
```

no deben cambiar el resultado.

### N — Invariantes

Verificar todas las invariantes de las secciones 7 y 8.

### O — No regresión

Ejecutar la suite existente completa y verificar que no se alteran los resultados de Tasks 057–067.

### P — Dependencias prohibidas

Verificar mediante revisión de imports o regla automatizada que el núcleo no utiliza HAPI, vendors, HTTP clients, OAuth, JWT ni modelos.

### Q — Datos sensibles

Verificar que no aparecen en logs, respuestas ni errores:

- tokens;
- Patient IDs;
- FHIR JSON;
- documentos de consentimiento;
- notas clínicas;
- identificadores clínicos reales.

### R — Determinismo

Para la misma entrada, el resultado debe ser idéntico.

### S — Sin side effects

La evaluación no debe escribir en bases de datos, publicar eventos ni ejecutar llamadas externas.

### T — No enforcement

Verificar que no existe ningún componente que traduzca el resultado en permisos efectivos, scopes OAuth, tokens o acceso a recursos FHIR.

---

## 12. Documentación requerida

Crear:

```text
docs/fhir/ai-consumer-clinical-data-access-boundary.md
```

La documentación debe explicar:

1. objetivo de la frontera;
2. relación con Task 067;
3. diferencia entre solicitud y concesión;
4. diferencia entre concesión y lectura FHIR;
5. estados posibles;
6. invariantes;
7. dependencias prohibidas;
8. ausencia de proveedor real;
9. ausencia de acceso clínico;
10. ejemplos de respuesta sin datos sensibles;
11. limitaciones explícitas.

Actualizar:

```text
docs/progress/progress-log.md
```

Registrar:

- Task 068;
- rama;
- commit;
- tests;
- estado live;
- confirmación de que no existe acceso clínico real.

No modificar retrospectivamente las tareas 057–067.

---

## 13. Criterios de aceptación

Task 068 está terminada únicamente si:

- existe una frontera aislada para solicitudes de acceso clínico;
- consume solo el resultado de Task 067;
- no accede a FHIR;
- no usa HAPI FHIR;
- no usa proveedores reales;
- no usa OAuth, JWT ni SMART;
- no habilita acceso clínico;
- mantiene `clinicalDataAccessGranted=false`;
- mantiene `clinicalDataAccessAllowed=false`;
- mantiene `requiresHumanReview=true`;
- mantiene todas las invariantes previas;
- no activa nada mediante query params o headers;
- no utiliza datos clínicos reales;
- cuenta con pruebas deterministas;
- la suite completa no presenta regresiones;
- la documentación está actualizada;
- se ejecuta una verificación live;
- el commit usa Conventional Commits;
- no se realiza push automático;
- no se crea PR automáticamente.

---

## 14. Checklist para Cursor

### Preparación

- [ ] Revisar Task 067 implementada y sus contratos.
- [ ] Identificar el nombre exacto de `AiConsumerDataScopeResult`.
- [ ] Identificar el patrón de paquetes y endpoints existente.
- [ ] No modificar Tasks 057–067.

### Implementación

- [ ] Crear paquete `lab.healthcare.fhir.aiconsumeraccess`.
- [ ] Crear contrato de entrada mínimo.
- [ ] Crear contexto sintético no confiable, si es necesario.
- [ ] Crear resultado `AiConsumerClinicalDataAccessResult`.
- [ ] Crear estados deterministas.
- [ ] Implementar deny-by-default.
- [ ] Mantener acceso clínico deshabilitado.
- [ ] No añadir dependencias externas.
- [ ] No modificar `.env`.

### Pruebas

- [ ] Tests unitarios.
- [ ] Tests de input ausente.
- [ ] Tests de alcance no evaluado o no aprobado.
- [ ] Tests de solicitud ausente y declarada.
- [ ] Tests de solicitud sin alcance.
- [ ] Tests de solicitud efectiva sintética.
- [ ] Tests de tenant.
- [ ] Tests de query params y headers.
- [ ] Tests de invariantes.
- [ ] Tests de no regresión.
- [ ] Tests de ausencia de side effects.
- [ ] Tests de no enforcement clínico.
- [ ] Suite completa en verde.

### Documentación

- [ ] Crear `docs/fhir/ai-consumer-clinical-data-access-boundary.md`.
- [ ] Actualizar `docs/progress/progress-log.md`.
- [ ] Registrar limitaciones.
- [ ] No incluir secretos ni datos clínicos.

### Cierre

- [ ] Verificar endpoint live.
- [ ] Verificar HTTP 200 si corresponde.
- [ ] Confirmar `clinicalDataAccessGranted=false`.
- [ ] Confirmar `clinicalDataAccessAllowed=false`.
- [ ] Confirmar `requiresHumanReview=true`.
- [ ] Crear commit:
  `feat: add ai consumer clinical data access boundary`
- [ ] No hacer push.
- [ ] No crear PR.
- [ ] Reportar rama, commit, tests y evidencia live.

---

## 15. Resultado live esperado

La proyección de Epic debe conservar todos los valores previos y añadir, como mínimo, un bloque equivalente a:

```text
aiConsumerClinicalDataAccess=NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS
aiConsumerAccessRequestDeclared=false
aiConsumerAccessRequestEvaluated=false
aiConsumerScopeReferencePresent=false
aiConsumerRealAuthorizationRequired=true
aiClinicalDataAccessRequested=false
aiClinicalDataAccessGranted=false
aiClinicalDataAccessAllowed=false
aiClinicalDataAccessGrantAvailable=false
aiClinicalDataAccessEnforced=false
```

La evidencia live no debe mostrar:

```text
clinicalDataAccessGranted=true
clinicalDataAccessAllowed=true
clinicalDataAccessGrantAvailable=true
clinicalDataAccessEnforced=true
```

---

## 16. Fuera de alcance explícito

No diseñar ni implementar en Task 068:

- Task 069;
- proveedor real de autorización;
- proveedor real de consentimiento;
- OAuth;
- JWT;
- SMART on FHIR;
- acceso a Epic;
- acceso a Oracle;
- lectura de `Patient`;
- lectura de `MedicationRequest`;
- lectura de `Observation`;
- lectura de `Condition`;
- lectura de `Encounter`;
- consulta de Bundle;
- cliente HTTP;
- dispatch;
- handoff;
- ejecución de modelo;
- RAG;
- agente autónomo;
- auditoría regulatoria real;
- aprobación legal;
- decisión clínica;
- cambios al contrato clínico v1;
- ampliación de allowlist 042;
- modificación de `.env`.

---

## 17. Resumen ejecutivo para el implementador

Implementa una frontera sintética de solicitud de acceso a datos clínicos después de Task 067.

La frontera debe responder:

> “¿Existe una solicitud declarada y suficientemente definida para una futura evaluación de acceso?”

No debe responder:

> “¿Está concedido el acceso clínico?”

La respuesta de Task 068 debe permanecer en estado de preparación o bloqueo, con:

```text
clinicalDataAccessRequested=false
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessGrantAvailable=false
clinicalDataAccessEnforced=false
requiresHumanReview=true
```

El objetivo es hacer explícita la frontera entre:

```text
alcance y minimización declarados
  →
solicitud de acceso declarada
  →
evaluación futura
  →
autorización real
  →
concesión real
```

sin saltar a:

```text
lectura de datos clínicos
```
