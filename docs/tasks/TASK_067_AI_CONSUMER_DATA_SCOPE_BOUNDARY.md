# TASK 067 — Clinical Data Scope and Minimization Boundary

## 1. Informe de posición

### Estado de la plataforma

Task 066 está implementada, validada en vivo y commiteada en la rama:

- Rama: `feature/ai-consumer-consent-boundary`
- Commit: `b92a094` — `feat: add ai consumer consent boundary`
- Tests: `846/0`

La cadena actual llega hasta una frontera sintética de consentimiento, propósito y alcance de datos:

```text
AiConsumerAuthorizationBoundary
  → AiConsumerConsentBoundary
```

El estado actual continúa siendo deny-by-default:

```text
aiConsumerConsent=CONSENT_NOT_IMPLEMENTED
aiConsumerPurpose=PURPOSE_NOT_VERIFIED
aiConsumerDataScope=DATA_SCOPE_NOT_VERIFIED
aiConsumerConsentAvailable=false
aiClinicalDataAccessAllowed=false
```

### Posición para Task 067

Task 067 debe implementar únicamente una frontera aislada de **evaluación sintética de minimización, necesidad y alcance de datos clínicos**.

No debe conceder acceso clínico, no debe consultar FHIR, no debe leer recursos de pacientes y no debe autorizar un consumidor real. La tarea debe preparar una decisión explícita sobre si un futuro consumidor podría ser evaluado respecto de un alcance de datos, manteniendo todas las autorizaciones reales desactivadas.

La distinción central es:

```text
data scope declarado ≠ data scope aprobado
data minimization evaluada ≠ acceso clínico concedido
necesidad declarada ≠ necesidad verificada
alcance sintético ≠ lectura FHIR
```

---

## 2. WHAT

Diseñar e implementar una nueva frontera Java aislada que consuma exclusivamente el resultado de Task 066 y produzca una decisión sintética sobre:

1. si existe un alcance de datos declarado;
2. si el alcance está suficientemente definido para una evaluación futura;
3. si el alcance respeta principios sintéticos de minimización;
4. si el propósito declarado tiene una relación explícita con el alcance;
5. si el resultado debe permanecer bloqueado o requerir revisión humana;
6. si el consumidor queda preparado para una futura evaluación de acceso, sin concederla.

La frontera debe ser determinista, auditable y sin dependencias de proveedores externos.

### Nombre sugerido

`ClinicalDataScopeBoundary`

### Paquete sugerido

```text
lab.healthcare.fhir.aiconsumerscope
```

### Rama sugerida

```text
feature/ai-consumer-data-scope-boundary
```

### Commit sugerido

```text
feat: add ai consumer data scope boundary
```

No hacer push automático. No crear PR.

---

## 3. WHY

La plataforma ya separa:

- contrato de consumidor;
- política sintética;
- readiness;
- autorización de handoff;
- autenticación;
- autorización;
- consentimiento;
- propósito;
- alcance de datos.

La siguiente frontera debe evitar que el sistema interprete un alcance declarado como permiso para acceder a información clínica.

Un consumidor futuro podría declarar:

- propósito de uso;
- categorías de datos necesarias;
- recursos FHIR requeridos;
- límites de tenant;
- necesidad de minimización;
- restricciones de uso.

Pero esas declaraciones no constituyen autorización ni acceso.

Task 067 debe hacer visible esta separación:

```text
declaración de alcance
  ≠
alcance evaluado sintéticamente
  ≠
alcance aprobado por un proveedor real
  ≠
acceso clínico efectivo
```

La tarea también debe impedir que una futura integración convierta automáticamente:

```text
consentimiento declarado
  +
propósito declarado
  +
alcance declarado
```

en:

```text
clinicalDataAccessAllowed=true
```

---

## 4. CONCEPT

### 4.1. Conceptos nuevos

#### Data scope

Descripción de las categorías de datos que un futuro consumidor declara necesitar.

Ejemplos conceptuales permitidos únicamente como valores sintéticos:

- `PATIENT_DEMOGRAPHICS`
- `ENCOUNTER_SUMMARY`
- `CONDITION_SUMMARY`
- `MEDICATION_SUMMARY`

Estos valores no deben provocar consultas FHIR ni acceso a pacientes.

#### Data minimization

Evaluación sintética de si el alcance solicitado parece limitado al propósito declarado.

La evaluación no es una decisión legal, clínica ni de seguridad. Es una señal técnica preparatoria.

#### Purpose-scope alignment

Relación declarativa entre el propósito y el alcance solicitado.

La tarea puede determinar que la relación está:

- `NOT_DECLARED`
- `DECLARED`
- `NOT_EVALUATED`
- `REQUIRES_HUMAN_REVIEW`

No debe afirmar que el propósito fue aprobado por una autoridad real.

#### Clinical data access

Capacidad efectiva de leer o utilizar datos clínicos.

Task 067 no la implementa y debe mantenerla deshabilitada.

### 4.2. Estados sugeridos

Definir un enum o representación equivalente con estados explícitos:

```text
DATA_SCOPE_NOT_DECLARED
DATA_SCOPE_DECLARED_NOT_EVALUATED
MINIMIZATION_NOT_EVALUATED
PURPOSE_SCOPE_ALIGNMENT_NOT_VERIFIED
SCOPE_REQUIRES_HUMAN_REVIEW
SCOPE_BLOCKED
NOT_READY_FOR_CLINICAL_DATA_ACCESS
```

El estado normal esperado para la ruta live debe ser:

```text
NOT_READY_FOR_CLINICAL_DATA_ACCESS
```

No crear un estado que implique:

```text
DATA_SCOPE_APPROVED
CLINICAL_DATA_ACCESS_GRANTED
CLINICAL_DATA_ACCESS_ALLOWED
```

---

## 5. Alcance funcional

### 5.1. Entrada

Consumir únicamente:

```text
AiConsumerConsentResult
```

producido por Task 066.

No importar ni consumir directamente:

- `AiConsumerContract`;
- `AiConsumerPolicyResult`;
- `AiConsumerReadinessResult`;
- `AiHandoffAuthorizationResult`;
- `AiConsumerAuthorizationResult`;
- `FirstAiResult`;
- `AiBoundaryResult`;
- objetos del pipeline FHIR;
- recursos HAPI FHIR;
- entidades de Epic;
- entidades de Oracle.

Si el diseño necesita transportar datos adicionales, definir un contexto sintético local no confiable, por ejemplo:

```text
ConsumerDataScopeContext
```

Este contexto no debe representar una autorización real.

### 5.2. Salida

Crear un resultado explícito, por ejemplo:

```text
AiConsumerDataScopeResult
```

Debe incluir, como mínimo:

```text
status
scopeDeclared
scopeEvaluated
minimizationEvaluated
purposeScopeAlignmentEvaluated
clinicalDataAccessAllowed
requiresHumanReview
```

Campos recomendados:

```text
boundaryVersion
inputAvailable
scopeDeclarationSource
declaredDataCategories
declaredResourceTypes
declaredTenantScope
minimizationStatus
purposeScopeAlignmentStatus
decisionReason
```

Los campos de alcance deben contener únicamente metadatos sintéticos y no datos clínicos reales.

### 5.3. Resultado esperado

Con la entrada actual de Task 066, el resultado debe representar:

```text
scopeDeclared=false
scopeEvaluated=false
minimizationEvaluated=false
purposeScopeAlignmentEvaluated=false
clinicalDataAccessAllowed=false
requiresHumanReview=true
status=NOT_READY_FOR_CLINICAL_DATA_ACCESS
```

Si el contexto sintético contiene declaraciones, la frontera puede clasificarlas como declaradas o pendientes de evaluación, pero nunca como aprobadas por un proveedor real.

---

## 6. Reglas deterministas

Implementar reglas claras y testeables.

### Regla A — Input ausente

Si `AiConsumerConsentResult` es `null` o inválido:

```text
status=SCOPE_BLOCKED
requiresHumanReview=true
clinicalDataAccessAllowed=false
```

### Regla B — Consentimiento no implementado

Si el resultado de Task 066 indica:

```text
consentAvailable=false
consentVerified=false
```

la frontera no puede producir una aprobación de alcance.

Resultado mínimo:

```text
status=NOT_READY_FOR_CLINICAL_DATA_ACCESS
clinicalDataAccessAllowed=false
requiresHumanReview=true
```

### Regla C — Propósito no verificado

Si:

```text
purposeApproved=false
```

no puede existir una decisión positiva de minimización o alineamiento.

### Regla D — Alcance ausente

Si no hay categorías o recursos declarados:

```text
scopeDeclared=false
scopeEvaluated=false
minimizationEvaluated=false
status=DATA_SCOPE_NOT_DECLARED
```

El resultado general debe seguir siendo:

```text
clinicalDataAccessAllowed=false
```

### Regla E — Alcance declarado pero no verificado

Si existe un alcance sintético, pero no existe proveedor real que lo evalúe:

```text
scopeDeclared=true
scopeEvaluated=false
minimizationEvaluated=false
clinicalDataAccessAllowed=false
requiresHumanReview=true
```

### Regla F — Relación propósito-alcance

La frontera puede comprobar únicamente que ambos valores fueron declarados sintéticamente.

No puede afirmar que la relación fue aprobada.

Valores permitidos:

```text
NOT_DECLARED
DECLARED_NOT_VERIFIED
REQUIRES_HUMAN_REVIEW
```

### Regla G — Tenant

Si falta el tenant o el alcance de tenant no está definido:

```text
status=SCOPE_BLOCKED
clinicalDataAccessAllowed=false
requiresHumanReview=true
```

No utilizar el tenant como mecanismo de autorización real.

### Regla H — Deny by default

Ante cualquier ambigüedad:

```text
clinicalDataAccessAllowed=false
requiresHumanReview=true
```

### Regla I — No habilitar accesos indirectos

Ningún resultado de esta tarea puede:

- activar un cliente FHIR;
- permitir una consulta;
- habilitar un endpoint clínico;
- crear un token;
- modificar scopes OAuth;
- habilitar SMART;
- cambiar una bandera de autorización previa.

---

## 7. Invariantes obligatorios

Task 067 debe preservar siempre:

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

Invariantes nuevos:

```text
scopeEvaluated=false
minimizationEvaluated=false
purposeScopeAlignmentEvaluated=false
clinicalDataScopeProviderConfigured=false
clinicalDataScopeApprovalAvailable=false
clinicalDataAccessRequested=false
clinicalDataAccessGranted=false
```

Si alguno de estos campos no existe todavía, agregarlo únicamente en el resultado de Task 067 o en el contrato técnico estrictamente necesario. No cambiar campos clínicos existentes del contrato v1.

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
- proveedores de consentimiento;
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

El núcleo de `aiconsumerscope` no debe importar:

```text
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

Debe consumir únicamente el contrato de entrada de Task 066 mediante una dependencia explícita y mínima.

---

## 9. Superficies HTTP

Agregar una superficie local únicamente si el proyecto ya utiliza este patrón.

Ruta sugerida:

```text
GET /lab/ai-consumer-data-scope
```

Ruta API sugerida:

```text
GET /api/ai-consumer-data-scope/v1
```

Integrar en:

```text
GET /epic/sandbox/fhir/clinical-projection
```

solo como proyección de estado.

No crear endpoints que:

- acepten scopes por query parameters;
- acepten consentimiento por headers;
- acepten `clinicalDataAccessAllowed=true`;
- acepten categorías clínicas arbitrarias para activar acceso;
- acepten tokens;
- ejecuten consultas FHIR.

La respuesta HTTP debe ser JSON técnico, sin datos de pacientes, documentos de consentimiento ni tokens.

---

## 10. Contrato HTTP sugerido

Ejemplo conceptual:

```json
{
  "boundaryVersion": "v1",
  "status": "NOT_READY_FOR_CLINICAL_DATA_ACCESS",
  "scopeDeclared": false,
  "scopeEvaluated": false,
  "minimizationEvaluated": false,
  "purposeScopeAlignmentEvaluated": false,
  "clinicalDataScopeProviderConfigured": false,
  "clinicalDataScopeApprovalAvailable": false,
  "clinicalDataAccessRequested": false,
  "clinicalDataAccessGranted": false,
  "clinicalDataAccessAllowed": false,
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

Con el resultado realista de Task 066:

- el resultado es `NOT_READY_FOR_CLINICAL_DATA_ACCESS`;
- `clinicalDataAccessAllowed=false`;
- `requiresHumanReview=true`;
- no hay aprobación de alcance.

### B — Input ausente

Debe producir bloqueo seguro.

### C — Consentimiento no disponible

Debe impedir cualquier aprobación de alcance.

### D — Propósito no verificado

Debe impedir cualquier resultado positivo.

### E — Alcance no declarado

Debe producir `DATA_SCOPE_NOT_DECLARED`.

### F — Alcance declarado sintéticamente

Debe indicar que fue declarado, pero no evaluado ni aprobado.

### G — Minimización no evaluada

Debe mantener `minimizationEvaluated=false`.

### H — Alineamiento no verificado

Debe mantener `purposeScopeAlignmentEvaluated=false`.

### I — Tenant ausente

Debe producir bloqueo seguro.

### J — Tenant sintético declarado

Debe conservarlo como metadato no confiable y no conceder acceso.

### K — Contexto sintético manipulado

Aunque el contexto indique valores positivos, el resultado no debe activar:

```text
clinicalDataAccessAllowed=true
```

### L — Query parameters

Los parámetros como:

```text
?clinicalDataAccessAllowed=true
?scopeApproved=true
?minimizationApproved=true
```

no deben cambiar el resultado.

### M — Headers

Headers como:

```text
X-Clinical-Data-Access: true
X-Scope-Approved: true
X-Consent-Verified: true
```

no deben cambiar el resultado.

### N — Invariantes

Verificar todas las invariantes de las secciones 7 y 8.

### O — No regresión

Ejecutar la suite existente completa y verificar que no se alteran los resultados de Tasks 057–066.

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

---

## 12. Documentación requerida

Crear:

```text
docs/fhir/ai-consumer-data-scope-boundary.md
```

La documentación debe explicar:

1. objetivo de la frontera;
2. relación con Task 066;
3. diferencia entre alcance declarado y alcance aprobado;
4. diferencia entre minimización sintética y acceso clínico;
5. estados posibles;
6. invariantes;
7. dependencias prohibidas;
8. ausencia de proveedor real;
9. ausencia de acceso FHIR;
10. ejemplos de respuesta sin datos sensibles;
11. limitaciones explícitas.

Actualizar:

```text
docs/progress/progress-log.md
```

Registrar:

- Task 067;
- rama;
- commit;
- tests;
- estado live;
- confirmación de que no existe acceso clínico real.

No modificar retrospectivamente las tareas 057–066.

---

## 13. Criterios de aceptación

Task 067 está terminada únicamente si:

- existe una frontera aislada para alcance y minimización;
- consume solo el resultado de Task 066;
- no accede a FHIR;
- no usa HAPI FHIR;
- no usa proveedores reales;
- no usa OAuth, JWT ni SMART;
- no habilita acceso clínico;
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

- [ ] Revisar Task 066 implementada y sus contratos.
- [ ] Identificar el nombre exacto de `AiConsumerConsentResult`.
- [ ] Identificar el patrón de paquetes y endpoints existente.
- [ ] No modificar Tasks 057–066.

### Implementación

- [ ] Crear paquete `lab.healthcare.fhir.aiconsumerscope`.
- [ ] Crear contrato de entrada mínimo.
- [ ] Crear contexto sintético no confiable, si es necesario.
- [ ] Crear resultado `AiConsumerDataScopeResult`.
- [ ] Crear estados deterministas.
- [ ] Implementar deny-by-default.
- [ ] Mantener acceso clínico deshabilitado.
- [ ] No añadir dependencias externas.
- [ ] No modificar `.env`.

### Pruebas

- [ ] Tests unitarios.
- [ ] Tests de input ausente.
- [ ] Tests de consentimiento y propósito no verificados.
- [ ] Tests de alcance ausente y declarado.
- [ ] Tests de tenant.
- [ ] Tests de query params y headers.
- [ ] Tests de invariantes.
- [ ] Tests de no regresión.
- [ ] Tests de ausencia de side effects.
- [ ] Suite completa en verde.

### Documentación

- [ ] Crear `docs/fhir/ai-consumer-data-scope-boundary.md`.
- [ ] Actualizar `docs/progress/progress-log.md`.
- [ ] Registrar limitaciones.
- [ ] No incluir secretos ni datos clínicos.

### Cierre

- [ ] Verificar endpoint live.
- [ ] Verificar HTTP 200 si corresponde.
- [ ] Confirmar `clinicalDataAccessAllowed=false`.
- [ ] Confirmar `requiresHumanReview=true`.
- [ ] Crear commit:
  `feat: add ai consumer data scope boundary`
- [ ] No hacer push.
- [ ] No crear PR.
- [ ] Reportar rama, commit, tests y evidencia live.

---

## 15. Resultado live esperado

La proyección de Epic debe conservar todos los valores previos y añadir, como mínimo, un bloque equivalente a:

```text
aiConsumerDataScope=NOT_READY_FOR_CLINICAL_DATA_ACCESS
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

La evidencia live no debe mostrar:

```text
clinicalDataAccessAllowed=true
scopeApproved=true
minimizationApproved=true
dataScopeApproved=true
```

---

## 16. Fuera de alcance explícito

No diseñar ni implementar en Task 067:

- Task 068;
- proveedor real de consentimiento;
- autorización OAuth;
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

Implementa una frontera sintética de alcance y minimización de datos clínicos después de Task 066.

La frontera debe responder:

> “¿Existe un alcance de datos declarado y suficientemente definido para una evaluación futura?”

No debe responder:

> “¿Está autorizado el consumidor para leer datos clínicos?”

La respuesta de Task 067 debe permanecer en estado de preparación o bloqueo, con:

```text
clinicalDataAccessAllowed=false
clinicalDataAccessGranted=false
clinicalDataScopeApprovalAvailable=false
requiresHumanReview=true
```

El objetivo es hacer explícita la frontera entre:

```text
consentimiento y propósito declarados
  →
alcance de datos declarado
  →
evaluación sintética de minimización
  →
futura evaluación real de acceso
```

sin saltar a:

```text
acceso clínico
```
