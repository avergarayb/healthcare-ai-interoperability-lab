# TASK 069 — Clinical Data Access Enforcement Decision Boundary

## 1. Informe de posición

### Estado de la plataforma

Task 068 está implementada, validada en vivo y commiteada:

- Rama: `feature/ai-consumer-clinical-data-access-boundary`
- Commit: `7fdd516` — `feat: add ai consumer clinical data access boundary`
- Tests: `881/0`

La cadena actual llega hasta una frontera sintética de solicitud de acceso clínico:

```text
AiConsumerDataScopeBoundary
  → AiConsumerClinicalDataAccessBoundary
```

El estado actual continúa siendo deny-by-default:

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

### Posición para Task 069

Task 069 debe implementar únicamente una frontera aislada de **decisión sintética de enforcement**, posterior a la solicitud de acceso clínico.

Esta tarea no debe conceder acceso, leer FHIR, llamar a un modelo, ejecutar handoff ni realizar dispatch. Su propósito es demostrar que una solicitud sintética, incluso cuando contiene señales positivas o aparenta estar preparada, no puede transformarse automáticamente en un permiso efectivo.

La frontera debe representar explícitamente la diferencia entre:

```text
solicitud de acceso
  ≠
decisión de enforcement
  ≠
concesión de acceso
  ≠
lectura FHIR
```

El resultado normal debe permanecer bloqueado o pendiente de revisión humana.

---

## 2. WHAT

Diseñar e implementar una frontera Java aislada que consuma exclusivamente:

```text
AiConsumerClinicalDataAccessResult
```

producido por Task 068.

La frontera debe producir una decisión sintética sobre si existe una base suficiente para una futura decisión de enforcement, sin ejecutar enforcement real.

Debe:

1. identificar si la entrada está disponible;
2. detectar solicitudes de acceso declaradas o efectivas;
3. verificar si el resultado previo sigue bloqueado;
4. comprobar si existe autorización real disponible;
5. impedir que cualquier flag sintético active acceso clínico;
6. representar que no existe una decisión de enforcement real;
7. mantener la revisión humana obligatoria;
8. impedir side effects y llamadas externas.

### Nombre sugerido

`ClinicalDataAccessEnforcementBoundary`

### Paquete sugerido

```text
lab.healthcare.fhir.aiconsumerenforcement
```

### Rama sugerida

```text
feature/ai-consumer-clinical-data-enforcement-boundary
```

### Commit sugerido

```text
feat: add ai consumer clinical data enforcement boundary
```

No hacer push automático. No crear PR.

---

## 3. WHY

Las tareas 057–068 construyeron progresivamente una cadena de preparación y controles sintéticos:

- contrato de consumidor;
- política;
- readiness;
- autorización de handoff;
- autenticación;
- autorización;
- consentimiento;
- propósito;
- alcance;
- minimización;
- solicitud de acceso.

El siguiente riesgo arquitectónico es que una capa posterior interprete la solicitud como autorización efectiva o active un mecanismo de enforcement sin proveedor real.

Task 069 debe cerrar explícitamente esa posibilidad.

La frontera debe dejar claro que:

```text
access request declared
  +
scope declared
  +
minimization evaluated
  +
consent declared
  +
purpose declared
```

no equivale a:

```text
clinical data access granted
```

Y tampoco equivale a:

```text
clinical data access enforced
```

La tarea prepara una futura decisión real, pero no la implementa.

---

## 4. CONCEPT

### 4.1. Enforcement decision

Decisión técnica que determina si un permiso previamente autorizado debe aplicarse a una operación.

Task 069 no implementa esa aplicación. Solo representa que la decisión real no está disponible.

### 4.2. Enforcement availability

Indica si existe un mecanismo real y configurado capaz de aplicar una decisión de acceso.

En esta tarea debe permanecer:

```text
clinicalDataAccessEnforcementAvailable=false
```

### 4.3. Enforcement executed

Indica si el sistema aplicó efectivamente una decisión de acceso.

En esta tarea debe permanecer:

```text
clinicalDataAccessEnforced=false
```

### 4.4. Decision versus grant

Una decisión sintética de “pendiente”, “bloqueada” o “requiere revisión” no es una concesión.

No crear estados positivos como:

```text
CLINICAL_DATA_ACCESS_GRANTED
CLINICAL_DATA_ACCESS_ENFORCED
ENFORCEMENT_APPROVED
```

### 4.5. Estados sugeridos

Definir un enum o representación equivalente:

```text
ENFORCEMENT_INPUT_NOT_AVAILABLE
ENFORCEMENT_BLOCKED
ENFORCEMENT_REQUIRES_ACCESS_DECISION
ENFORCEMENT_REQUIRES_REAL_AUTHORIZATION
ENFORCEMENT_REQUIRES_HUMAN_REVIEW
ENFORCEMENT_NOT_AVAILABLE
NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS
```

El estado live esperado debe ser:

```text
NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS
```

---

## 5. Alcance funcional

### 5.1. Entrada

Consumir únicamente:

```text
AiConsumerClinicalDataAccessResult
```

producido por Task 068.

No importar ni consumir directamente:

- `AiConsumerDataScopeResult`;
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

Si se necesita representar una decisión sintética, definir un contexto local no confiable, por ejemplo:

```text
ClinicalDataEnforcementContext
```

Este contexto no debe representar una autorización real ni un mecanismo de enforcement.

### 5.2. Salida

Crear un resultado explícito, por ejemplo:

```text
AiConsumerClinicalDataEnforcementResult
```

Debe incluir, como mínimo:

```text
status
enforcementDecisionAvailable
enforcementDecisionEvaluated
realAuthorizationRequired
clinicalDataAccessGranted
clinicalDataAccessAllowed
clinicalDataAccessEnforcementAvailable
clinicalDataAccessEnforced
requiresHumanReview
```

Campos recomendados:

```text
boundaryVersion
inputAvailable
accessRequestReferencePresent
authorizationDecisionReferencePresent
enforcementProviderConfigured
enforcementEvaluationStatus
decisionReason
```

Todos los valores deben ser metadatos técnicos sintéticos.

No incluir datos clínicos, identificadores de pacientes, tokens ni documentos.

### 5.3. Resultado esperado

Con la entrada actual de Task 068:

```text
status=NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS
enforcementDecisionAvailable=false
enforcementDecisionEvaluated=false
realAuthorizationRequired=true
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessEnforcementAvailable=false
clinicalDataAccessEnforced=false
requiresHumanReview=true
```

---

## 6. Reglas deterministas

### Regla A — Input ausente

Si `AiConsumerClinicalDataAccessResult` es `null` o inválido:

```text
status=ENFORCEMENT_INPUT_NOT_AVAILABLE
enforcementDecisionAvailable=false
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessEnforced=false
requiresHumanReview=true
```

### Regla B — Resultado previo bloqueado

Si Task 068 indica:

```text
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
```

la frontera no puede producir una decisión positiva.

Resultado mínimo:

```text
status=NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessEnforced=false
requiresHumanReview=true
```

### Regla C — Solicitud de acceso pendiente

Si existe una solicitud, pero no existe una decisión real de acceso:

```text
status=ENFORCEMENT_REQUIRES_ACCESS_DECISION
enforcementDecisionAvailable=false
clinicalDataAccessEnforced=false
requiresHumanReview=true
```

### Regla D — Autorización real ausente

Si:

```text
realAuthorizationRequired=true
```

o no existe proveedor real:

```text
status=ENFORCEMENT_REQUIRES_REAL_AUTHORIZATION
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessEnforced=false
requiresHumanReview=true
```

### Regla E — Contexto sintético positivo

Si el contexto sintético contiene flags positivos como:

```text
enforcementDecisionAvailable=true
clinicalDataAccessGranted=true
clinicalDataAccessAllowed=true
clinicalDataAccessEnforced=true
```

la frontera debe rechazarlos o neutralizarlos.

El resultado final debe mantener:

```text
enforcementDecisionAvailable=false
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessEnforced=false
requiresHumanReview=true
```

### Regla F — No activar enforcement

Ningún resultado de esta tarea puede:

- habilitar un filtro de autorización;
- activar un interceptor de acceso clínico;
- habilitar un endpoint FHIR;
- cambiar permisos;
- emitir tokens;
- modificar scopes OAuth;
- activar SMART;
- ejecutar una lectura;
- activar un consumidor real.

### Regla G — Tenant

Si falta el tenant o el contexto de tenant no está definido:

```text
status=ENFORCEMENT_BLOCKED
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessEnforced=false
requiresHumanReview=true
```

### Regla H — Deny by default

Ante cualquier ambigüedad:

```text
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessEnforced=false
requiresHumanReview=true
```

---

## 7. Invariantes obligatorios

Task 069 debe preservar siempre:

```text
modelCalled=false
modelCallAuthorized=false
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
scopeEvaluated=false
minimizationEvaluated=false
purposeScopeAlignmentEvaluated=false
clinicalDataScopeProviderConfigured=false
clinicalDataScopeApprovalAvailable=false
accessRequestEvaluated=false
clinicalDataAccessRequested=false
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessGrantAvailable=false
clinicalDataAccessEnforced=false
clinicalDataAccessProviderConfigured=false
clinicalDataAccessAuthorizationAvailable=false
```

Invariantes nuevos:

```text
enforcementDecisionAvailable=false
enforcementDecisionEvaluated=false
clinicalDataAccessEnforcementAvailable=false
clinicalDataAccessEnforcementProviderConfigured=false
clinicalDataAccessEnforcementExecuted=false
```

Si alguno de estos campos no existe, agregarlo únicamente al resultado de Task 069 o al contrato técnico estrictamente necesario.

No cambiar campos clínicos existentes del contrato v1.

---

## 8. Arquitectura y aislamiento

### 8.1. Dependencias permitidas

Permitido:

- Java 21;
- clases Java estándar;
- Spring Boot existente;
- records;
- enums;
- servicios puros;
- validación local;
- tests unitarios;
- integración con las superficies locales existentes para proyectar estado.

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
- proveedores reales de enforcement;
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

El núcleo de `aiconsumerenforcement` no debe importar:

```text
lab.healthcare.fhir.aiconsumeraccess
lab.healthcare.fhir.aiconsumerscope
lab.healthcare.fhir.aiconsumerconsent
lab.healthcare.fhir.aiconsumer
lab.healthcare.fhir.aiconsumerpolicy
lab.healthcare.fhir.aiconsumerreadiness
lab.healthcare.fhir.aihandoffauthorization
lab.healthcare.fhir.aiconsumerauthorization
lab.healthcare.fhir.firstai
lab.healthcare.fhir.aigateway
lab.healthcare.fhir.aiboundary
```

Tampoco debe importar paquetes de pipeline, vendor o HAPI FHIR.

Debe consumir únicamente el resultado inmediato de Task 068 mediante una dependencia explícita y mínima.

---

## 9. Superficies HTTP

Agregar una superficie local únicamente si el proyecto ya utiliza este patrón.

Ruta sugerida:

```text
GET /lab/ai-consumer-clinical-data-enforcement
```

Ruta API sugerida:

```text
GET /api/ai-consumer-clinical-data-enforcement/v1
```

Integrar en:

```text
GET /epic/sandbox/fhir/clinical-projection
```

solo como proyección de estado ciego.

No crear endpoints que:

- acepten `clinicalDataAccessGranted=true`;
- acepten `clinicalDataAccessAllowed=true`;
- acepten `clinicalDataAccessEnforced=true`;
- acepten `enforcementApproved=true`;
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
  "status": "NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS",
  "enforcementDecisionAvailable": false,
  "enforcementDecisionEvaluated": false,
  "realAuthorizationRequired": true,
  "clinicalDataAccessGranted": false,
  "clinicalDataAccessAllowed": false,
  "clinicalDataAccessEnforcementAvailable": false,
  "clinicalDataAccessEnforced": false,
  "clinicalDataAccessEnforcementProviderConfigured": false,
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

Con el resultado realista de Task 068:

- el resultado es `NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS`;
- `enforcementDecisionAvailable=false`;
- `enforcementDecisionEvaluated=false`;
- `clinicalDataAccessGranted=false`;
- `clinicalDataAccessAllowed=false`;
- `clinicalDataAccessEnforced=false`;
- `requiresHumanReview=true`.

### B — Input ausente

Debe producir bloqueo seguro.

### C — Acceso previo no concedido

Debe impedir cualquier enforcement.

### D — Solicitud pendiente

Debe producir `ENFORCEMENT_REQUIRES_ACCESS_DECISION`.

### E — Autorización real ausente

Debe producir `ENFORCEMENT_REQUIRES_REAL_AUTHORIZATION`.

### F — Contexto sintético positivo

Debe neutralizar todos los flags positivos y mantener deny-by-default.

### G — Tenant ausente

Debe producir bloqueo seguro.

### H — Query parameters

Los parámetros como:

```text
?clinicalDataAccessGranted=true
?clinicalDataAccessAllowed=true
?clinicalDataAccessEnforced=true
?enforcementApproved=true
```

no deben cambiar el resultado.

### I — Headers

Headers como:

```text
X-Clinical-Data-Access-Granted: true
X-Clinical-Data-Access-Allowed: true
X-Clinical-Data-Access-Enforced: true
X-Enforcement-Approved: true
```

no deben cambiar el resultado.

### J — Invariantes

Verificar todas las invariantes de las secciones 7 y 8.

### K — No regresión

Ejecutar la suite completa y verificar que no se alteran los resultados de Tasks 057–068.

### L — Dependencias prohibidas

Verificar mediante revisión de imports o regla automatizada que el núcleo no utiliza HAPI, vendors, HTTP clients, OAuth, JWT ni modelos.

### M — Datos sensibles

Verificar que no aparecen en logs, respuestas ni errores:

- tokens;
- Patient IDs;
- FHIR JSON;
- documentos de consentimiento;
- notas clínicas;
- identificadores clínicos reales.

### N — Determinismo

Para la misma entrada, el resultado debe ser idéntico.

### O — Sin side effects

La evaluación no debe escribir en bases de datos, publicar eventos ni ejecutar llamadas externas.

### P — No enforcement real

Verificar que no existe ningún componente que:

- active permisos;
- modifique scopes;
- habilite endpoints;
- emita tokens;
- ejecute consultas FHIR;
- active un consumidor real.

---

## 12. Documentación requerida

Crear:

```text
docs/fhir/ai-consumer-clinical-data-enforcement-boundary.md
```

La documentación debe explicar:

1. objetivo de la frontera;
2. relación con Task 068;
3. diferencia entre solicitud, decisión y enforcement;
4. diferencia entre enforcement sintético y acceso clínico;
5. estados posibles;
6. invariantes;
7. dependencias prohibidas;
8. ausencia de proveedor real;
9. ausencia de enforcement efectivo;
10. ejemplos de respuesta sin datos sensibles;
11. limitaciones explícitas.

Actualizar:

```text
docs/progress/progress-log.md
```

Registrar:

- Task 069;
- rama;
- commit;
- tests;
- estado live;
- confirmación de que no existe enforcement ni acceso clínico real.

Actualizar, si el patrón documental del repositorio lo exige:

```text
docs/architecture/
docs/fhir/
docs/epic/
docs/oracle/
docs/smart/
docs/model-boundary/
```

No modificar retrospectivamente las tareas 057–068.

---

## 13. Criterios de aceptación

Task 069 está terminada únicamente si:

- existe una frontera aislada de decisión sintética de enforcement;
- consume solo el resultado de Task 068;
- no accede a FHIR;
- no usa HAPI FHIR;
- no usa proveedores reales;
- no usa OAuth, JWT ni SMART;
- no habilita enforcement clínico;
- mantiene `clinicalDataAccessGranted=false`;
- mantiene `clinicalDataAccessAllowed=false`;
- mantiene `clinicalDataAccessEnforced=false`;
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

- [ ] Revisar Task 068 implementada y sus contratos.
- [ ] Identificar el nombre exacto de `AiConsumerClinicalDataAccessResult`.
- [ ] Identificar el patrón de paquetes y endpoints existente.
- [ ] No modificar Tasks 057–068.

### Implementación

- [ ] Crear paquete `lab.healthcare.fhir.aiconsumerenforcement`.
- [ ] Crear contrato de entrada mínimo.
- [ ] Crear contexto sintético no confiable, si es necesario.
- [ ] Crear resultado `AiConsumerClinicalDataEnforcementResult`.
- [ ] Crear estados deterministas.
- [ ] Implementar deny-by-default.
- [ ] Mantener enforcement clínico deshabilitado.
- [ ] No añadir dependencias externas.
- [ ] No modificar `.env`.

### Pruebas

- [ ] Tests unitarios.
- [ ] Tests de input ausente.
- [ ] Tests de acceso previo no concedido.
- [ ] Tests de solicitud pendiente.
- [ ] Tests de autorización real ausente.
- [ ] Tests de contexto sintético positivo.
- [ ] Tests de tenant.
- [ ] Tests de query params y headers.
- [ ] Tests de invariantes.
- [ ] Tests de no regresión.
- [ ] Tests de ausencia de side effects.
- [ ] Tests de ausencia de enforcement real.
- [ ] Suite completa en verde.

### Documentación

- [ ] Crear `docs/fhir/ai-consumer-clinical-data-enforcement-boundary.md`.
- [ ] Actualizar `docs/progress/progress-log.md`.
- [ ] Actualizar documentación arquitectónica relacionada, si corresponde.
- [ ] Registrar limitaciones.
- [ ] No incluir secretos ni datos clínicos.

### Cierre

- [ ] Verificar endpoint live.
- [ ] Verificar HTTP 200 si corresponde.
- [ ] Confirmar `clinicalDataAccessGranted=false`.
- [ ] Confirmar `clinicalDataAccessAllowed=false`.
- [ ] Confirmar `clinicalDataAccessEnforced=false`.
- [ ] Confirmar `requiresHumanReview=true`.
- [ ] Crear commit:
  `feat: add ai consumer clinical data enforcement boundary`
- [ ] No hacer push.
- [ ] No crear PR.
- [ ] Reportar rama, commit, tests y evidencia live.

---

## 15. Resultado live esperado

La proyección de Epic debe conservar todos los valores previos y añadir, como mínimo, un bloque equivalente a:

```text
aiConsumerClinicalDataEnforcement=NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS
aiConsumerEnforcementDecisionAvailable=false
aiConsumerEnforcementDecisionEvaluated=false
aiConsumerRealAuthorizationRequired=true
aiClinicalDataAccessGranted=false
aiClinicalDataAccessAllowed=false
aiClinicalDataAccessEnforcementAvailable=false
aiClinicalDataAccessEnforced=false
aiClinicalDataAccessEnforcementProviderConfigured=false
```

La evidencia live no debe mostrar:

```text
clinicalDataAccessGranted=true
clinicalDataAccessAllowed=true
clinicalDataAccessEnforcementAvailable=true
clinicalDataAccessEnforced=true
enforcementApproved=true
```

---

## 16. Fuera de alcance explícito

No diseñar ni implementar en Task 069:

- Task 070;
- proveedor real de enforcement;
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

Implementa una frontera sintética de decisión de enforcement después de Task 068.

La frontera debe responder:

> “¿Existe una base suficiente para una futura decisión real de enforcement?”

No debe responder:

> “¿Está concedido o aplicado el acceso clínico?”

La respuesta de Task 069 debe permanecer en estado de preparación o bloqueo, con:

```text
enforcementDecisionAvailable=false
enforcementDecisionEvaluated=false
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessEnforcementAvailable=false
clinicalDataAccessEnforced=false
requiresHumanReview=true
```

El objetivo es hacer explícita la frontera entre:

```text
solicitud de acceso
  →
decisión sintética
  →
futura autorización real
  →
futura concesión real
  →
futuro enforcement real
```

sin saltar a:

```text
acceso clínico o lectura FHIR
```
