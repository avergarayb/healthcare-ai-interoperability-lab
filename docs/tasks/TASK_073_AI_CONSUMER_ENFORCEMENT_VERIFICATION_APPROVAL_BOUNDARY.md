# TASK 073 — AI Consumer Clinical Data Enforcement Verification Approval Boundary

## 1. Informe de posición

### Estado actual

El repositorio `healthcare-ai-interoperability-lab` contiene una cadena sintética y deny-by-default desde la Task 057 hasta la Task 072.

La Task 072 introdujo la separación entre:

```text
verification result
    ≠
verification decision
```

y dejó explícitamente sin aprobar:

```text
verificationDecisionAvailable=false
verificationDecisionEvaluated=false
verificationApproved=false
clinicalDataAccessGranted=false
```

La siguiente frontera no debe ejecutar enforcement, conceder acceso clínico ni habilitar un consumidor real. Debe representar únicamente la **decisión sintética de aprobación o rechazo de una verificación de ejecución de enforcement**.

### Objetivo de la Task 073

Crear una frontera aislada que:

1. Consuma exclusivamente el resultado inmediato de la Task 072.
2. Reciba un contexto sintético no confiable que represente una posible decisión de aprobación.
3. Evalúe de forma determinística si existe evidencia suficiente para una decisión sintética.
4. Produzca un resultado explícito de aprobación, rechazo o revisión humana.
5. Mantenga todos los invariantes de seguridad y no ejecución.
6. No conceda acceso clínico.
7. No ejecute enforcement.
8. No llame FHIR, HAPI FHIR, Epic, Oracle, ningún modelo ni ningún servicio externo.

Esta Task continúa la cadena de fronteras de gobernanza, pero **no debe convertirse en una autorización clínica real**.

---

## 2. Alcance exacto

### Incluido

- Nuevo paquete aislado:
  `lab.healthcare.fhir.aiconsumerenforcementverificationapproval`
- Nuevo resultado:
  `AiConsumerEnforcementVerificationApprovalResult`
- Nuevo contexto sintético:
  `ClinicalDataEnforcementVerificationApprovalContext`
- Nueva frontera:
  `AiConsumerEnforcementVerificationApprovalBoundary`
- Integración en el controller `.web` que ensambla las Tasks 057–073.
- Exposición de la nueva información en:
  - superficie `/lab/...`;
  - superficie `/api/.../v1` respaldada por Oracle;
  - campos ciegos de `/epic/sandbox/fhir/clinical-projection`.
- Tests unitarios, de arquitectura, de controller y de no-regresión.
- Documentación técnica y actualización del progress log.

### Fuera de alcance

No implementar:

- LLM, RAG, LangGraph o `ai-service` real.
- Cliente HTTP hacia un modelo.
- Integración con OpenAI, Azure OpenAI, Bedrock, Vertex AI u otro proveedor.
- Lectura de FHIR.
- Lectura de Epic.
- Lectura de Oracle clínico.
- Bundle FHIR hacia un modelo.
- Ejecución de enforcement.
- Autorización clínica efectiva.
- Concesión de acceso a datos clínicos.
- Consentimiento real.
- Autenticación real.
- Autorización real.
- Persistencia de decisiones.
- Colas, mensajería o dispatch.
- Cambios en la allowlist de la Task 042.
- Inclusión de `MedicationRequest` en Epic.
- Cambios en `.env`.

---

## 3. Regla arquitectónica principal

La nueva frontera debe consumir únicamente:

```text
AiConsumerVerificationDecisionResult
+
ClinicalDataEnforcementVerificationApprovalContext
```

El núcleo de la Task 073 no debe importar ni invocar directamente:

- `AgentStub`;
- `DeterministicAgent`;
- `AiBoundary`;
- `FirstAi`;
- `AiExecutionGate`;
- `AiConsumerContract`;
- `AiConsumerPolicy`;
- `AiConsumerReadiness`;
- `AiHandoffAuthorization`;
- `AiConsumerAuthorization`;
- `AiConsumerConsent`;
- `AiConsumerDataScope`;
- `AiConsumerClinicalDataAccess`;
- `AiConsumerClinicalDataEnforcement`;
- `AiConsumerClinicalDataEnforcementExecution`;
- `AiConsumerClinicalDataEnforcementExecutionVerification`;
- controllers previos;
- clientes FHIR;
- clientes Epic;
- repositorios Oracle;
- proveedores de seguridad;
- proveedores de modelos.

La composición de la cadena completa debe permanecer exclusivamente en la capa `.web`.

---

## 4. Nombres obligatorios

Usar nombres cortos para evitar nuevamente problemas de Windows MAX_PATH.

### Paquete

```text
lab.healthcare.fhir.aiconsumerenforcementverificationapproval
```

### Clases principales

```text
AiConsumerEnforcementVerificationApprovalBoundary
AiConsumerEnforcementVerificationApprovalResult
ClinicalDataEnforcementVerificationApprovalContext
```

### Estado principal de la nueva frontera

```text
VERIFICATION_APPROVAL_NOT_AVAILABLE
```

No usar:

- `Evaluator`;
- `Executor`;
- `Enforcer`;
- `ClinicalDataAccessGranted`;
- `ModelAuthorization`;
- `RealApproval`.

La palabra `Approval` representa únicamente una decisión sintética de gobernanza, no una aprobación clínica efectiva.

---

## 5. Contrato de entrada

### 5.1 Resultado inmediato anterior

La frontera recibe un objeto `AiConsumerVerificationDecisionResult` producido por la Task 072.

Debe tratarlo como un resultado no confiable para efectos de la nueva decisión.

La Task 073 no puede asumir que un resultado previo implica aprobación.

Debe verificar explícitamente:

```text
verificationDecisionAvailable
verificationDecisionEvaluated
verificationApproved
requiresHumanReview
```

### 5.2 Contexto sintético

Crear `ClinicalDataEnforcementVerificationApprovalContext` con campos mínimos y explícitos:

```text
approvalDecisionDeclared
approvalDecisionEvaluated
approvalEvidenceReferencePresent
approvalEvidenceSufficient
approvalPolicyReferencePresent
approvalPolicySatisfied
approvalHumanReviewRequired
approvalProviderConfigured
approvalAvailable
```

Todos los campos deben ser sintéticos y no confiables.

No representar tokens, credenciales, JWT, secretos, identificadores reales de pacientes ni datos clínicos.

---

## 6. Reglas determinísticas

La frontera debe aplicar las siguientes reglas en orden.

### Regla A — Entrada ausente

Si el resultado de la Task 072 es `null`:

```text
status=BLOCKED
reason=VERIFICATION_DECISION_RESULT_MISSING
```

### Regla B — Contexto ausente

Si el contexto sintético es `null`:

```text
status=BLOCKED
reason=VERIFICATION_APPROVAL_CONTEXT_MISSING
```

### Regla C — Aprobación prematura

Si el contexto declara cualquiera de los siguientes valores en `true`:

```text
approvalDecisionDeclared
approvalDecisionEvaluated
approvalEvidenceReferencePresent
approvalEvidenceSufficient
approvalPolicyReferencePresent
approvalPolicySatisfied
approvalProviderConfigured
approvalAvailable
```

la frontera no debe convertir esos valores en hechos confiables.

El resultado debe permanecer bloqueado o requerir revisión humana, según la regla de precedencia definida en la implementación.

La opción recomendada es:

```text
status=HUMAN_REVIEW_REQUIRED
reason=SYNTHETIC_APPROVAL_CLAIMS_UNTRUSTED
```

### Regla D — Resultado previo no disponible

Si:

```text
verificationDecisionAvailable=false
```

entonces:

```text
status=BLOCKED
reason=VERIFICATION_DECISION_NOT_AVAILABLE
```

### Regla E — Resultado previo no evaluado

Si:

```text
verificationDecisionEvaluated=false
```

entonces:

```text
status=BLOCKED
reason=VERIFICATION_DECISION_NOT_EVALUATED
```

### Regla F — Revisión humana heredada

Si:

```text
requiresHumanReview=true
```

entonces:

```text
status=HUMAN_REVIEW_REQUIRED
reason=HUMAN_REVIEW_REQUIRED_BY_PREVIOUS_BOUNDARY
```

### Regla G — Sin evidencia suficiente

Si el resultado previo no contiene una decisión verificable y el contexto no aporta evidencia confiable:

```text
status=BLOCKED
reason=VERIFICATION_APPROVAL_EVIDENCE_NOT_AVAILABLE
```

### Regla H — Estado live esperado

Con los valores actuales de la cadena 057–072, la respuesta live debe ser:

```text
status=VERIFICATION_APPROVAL_NOT_AVAILABLE
verificationApprovalAvailable=false
verificationApprovalEvaluated=false
verificationApproved=false
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
requiresHumanReview=true
```

La frontera no debe producir un estado `APPROVED` en la configuración live.

---

## 7. Contrato de salida

Crear `AiConsumerEnforcementVerificationApprovalResult`.

### Campos mínimos

```text
status
reason
verificationApprovalAvailable
verificationApprovalEvaluated
verificationApproved
approvalEvidenceEvaluated
approvalPolicyEvaluated
approvalHumanReviewRequired
clinicalDataAccessGranted
clinicalDataAccessAllowed
clinicalDataAccessRequested
clinicalDataAccessEnforced
enforcementExecutionPerformed
executionVerified
requiresHumanReview
```

### Invariantes obligatorios

Siempre deben mantenerse:

```text
verificationApprovalAvailable=false
verificationApprovalEvaluated=false
verificationApproved=false
approvalEvidenceEvaluated=false
approvalPolicyEvaluated=false
approvalHumanReviewRequired=true
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessRequested=false
clinicalDataAccessEnforced=false
enforcementExecutionPerformed=false
executionVerified=false
requiresHumanReview=true
```

No agregar flags que puedan interpretarse como autorización efectiva.

### Constructor

El constructor debe rechazar cualquier intento de crear un resultado con:

```text
verificationApprovalAvailable=true
verificationApprovalEvaluated=true
verificationApproved=true
clinicalDataAccessGranted=true
clinicalDataAccessAllowed=true
clinicalDataAccessRequested=true
clinicalDataAccessEnforced=true
enforcementExecutionPerformed=true
executionVerified=true
```

La creación debe fallar de forma determinística mediante la misma estrategia de validación utilizada por las fronteras 065–072.

### Método `denied(...)`

Implementar un factory method equivalente al patrón existente:

```text
denied(...)
```

Debe producir un resultado seguro con:

```text
verificationApprovalAvailable=false
verificationApprovalEvaluated=false
verificationApproved=false
requiresHumanReview=true
```

---

## 8. Estados permitidos

Usar un conjunto pequeño y explícito:

```text
VERIFICATION_APPROVAL_NOT_AVAILABLE
BLOCKED
HUMAN_REVIEW_REQUIRED
NOT_ELIGIBLE_FOR_APPROVAL
```

No introducir:

```text
APPROVED
AUTHORIZED
GRANTED
EXECUTED
VERIFIED
READY_FOR_CLINICAL_ACCESS
```

La ausencia de un estado `APPROVED` es intencional: esta Task modela la frontera de decisión, no una autorización clínica.

---

## 9. Exposición HTTP

### 9.1 Superficie de laboratorio

Agregar una ruta bajo `/lab/...` siguiendo el patrón de las Tasks anteriores.

La ruta debe devolver únicamente información sintética y segura.

No aceptar:

- query params para alterar la decisión;
- headers para alterar la decisión;
- body controlable por el cliente;
- tokens;
- identificadores clínicos.

### 9.2 Superficie Oracle-backed

Agregar los campos de la Task 073 en la respuesta `/api/.../v1` correspondiente, siguiendo el patrón existente.

No modificar contratos anteriores de forma incompatible.

### 9.3 Superficie Epic sandbox

Agregar campos ciegos al resultado de:

```text
GET /epic/sandbox/fhir/clinical-projection
```

Campos esperados:

```text
aiConsumerEnforcementVerificationApproval
aiConsumerVerificationApprovalAvailable
aiConsumerVerificationApprovalEvaluated
aiConsumerVerificationApproved
aiConsumerApprovalEvidenceEvaluated
aiConsumerApprovalPolicyEvaluated
aiConsumerApprovalHumanReviewRequired
```

Los campos deben ser derivados de la cadena sintética, no de Epic ni de FHIR real.

No añadir recursos FHIR.

No añadir `MedicationRequest`.

No modificar la allowlist de la Task 042.

---

## 10. Tests obligatorios

### 10.1 Tests unitarios de la frontera

Cubrir como mínimo:

1. Resultado anterior `null`.
2. Contexto `null`.
3. Resultado previo con `verificationDecisionAvailable=false`.
4. Resultado previo con `verificationDecisionEvaluated=false`.
5. Resultado previo con `requiresHumanReview=true`.
6. Contexto con declaraciones sintéticas en `true`.
7. Contexto con evidencia sintética declarada.
8. Contexto con política sintética declarada.
9. Estado live seguro.
10. Constructor rechazando `verificationApproved=true`.
11. Constructor rechazando `clinicalDataAccessGranted=true`.
12. Constructor rechazando `executionVerified=true`.

### 10.2 Tests de arquitectura

Verificar que el paquete:

```text
aiconsumerenforcementverificationapproval
```

no depende directamente de:

- controllers;
- HAPI FHIR;
- Epic;
- Oracle;
- proveedores de autenticación;
- proveedores de autorización;
- proveedores de consentimiento;
- proveedores de modelos;
- `WebClient`;
- `RestClient`;
- `RestTemplate`;
- SDKs externos.

### 10.3 Tests de controller

Cubrir:

- respuesta HTTP 200;
- campos de aprobación presentes;
- estado `VERIFICATION_APPROVAL_NOT_AVAILABLE`;
- `verificationApproved=false`;
- `clinicalDataAccessGranted=false`;
- `requiresHumanReview=true`;
- query params ignorados;
- headers ignorados;
- ausencia de mutación por input externo.

### 10.4 No-regresión

Ejecutar el test existente:

```text
EpicSandboxClinicalProjectionControllerTest
```

y todos los tests del servicio.

No aceptar regresiones.

---

## 11. Evidencia live obligatoria

Antes del commit, ejecutar la aplicación y verificar:

```text
GET /epic/sandbox/fhir/clinical-projection
```

La evidencia debe demostrar, sin parámetros ni headers especiales:

```text
HTTP 200
```

y al menos:

```text
aiConsumerVerificationApprovalAvailable=false
aiConsumerVerificationApprovalEvaluated=false
aiConsumerVerificationApproved=false
aiConsumerApprovalEvidenceEvaluated=false
aiConsumerApprovalPolicyEvaluated=false
aiConsumerApprovalHumanReviewRequired=true
```

También debe demostrar que permanecen intactos:

```text
clinicalDataAccessGranted=false
clinicalDataAccessAllowed=false
clinicalDataAccessEnforced=false
enforcementExecutionPerformed=false
executionVerified=false
requiresHumanReview=true
```

No se debe considerar terminada la Task 073 si únicamente pasan los tests y no existe evidencia live ciega.

---

## 12. Documentación obligatoria

Crear:

```text
docs/fhir/ai-consumer-enforcement-verification-approval-boundary.md
```

Documentar:

- propósito;
- alcance;
- no objetivos;
- contrato de entrada;
- contexto sintético;
- estados;
- reglas determinísticas;
- invariantes;
- diferencia entre verificación y aprobación;
- diferencia entre aprobación sintética y acceso clínico;
- superficies HTTP;
- evidencia live;
- limitaciones;
- riesgos residuales;
- siguiente frontera posible.

Actualizar, según corresponda:

```text
docs/architecture/domain-boundaries.md
docs/architecture/service-ownership.md
docs/architecture/platform-diagram.md
docs/architecture/model-boundary.md
docs/epic/...
docs/oracle/...
docs/smart/...
docs/progress/progress-log.md
```

No reescribir retrospectivamente las Tasks 057–072.

---

## 13. Git

### Rama

```text
feature/ai-consumer-enforcement-verification-approval-boundary
```

### Commit

Usar Conventional Commits:

```text
feat: add ai consumer enforcement verification approval boundary
```

No hacer:

- push;
- creación de PR;
- merge;
- modificación de `.env`;
- incorporación de secretos.

---

## 14. Criterios de aceptación

La Task 073 se considera completa únicamente cuando:

- [ ] Existe un paquete aislado.
- [ ] Consume solo `AiConsumerVerificationDecisionResult` y contexto sintético.
- [ ] No importa capas anteriores desde el núcleo.
- [ ] No usa FHIR, HAPI FHIR, Epic, Oracle, modelos ni servicios externos.
- [ ] Implementa estados deny-by-default.
- [ ] El constructor rechaza flags peligrosos en `true`.
- [ ] `verificationApproved` permanece `false`.
- [ ] `clinicalDataAccessGranted` permanece `false`.
- [ ] `clinicalDataAccessAllowed` permanece `false`.
- [ ] `clinicalDataAccessEnforced` permanece `false`.
- [ ] `enforcementExecutionPerformed` permanece `false`.
- [ ] `executionVerified` permanece `false`.
- [ ] `requiresHumanReview` permanece `true`.
- [ ] Query params y headers son ignorados.
- [ ] La superficie Epic sandbox expone campos ciegos.
- [ ] No se modifica la allowlist 042.
- [ ] No se añade `MedicationRequest`.
- [ ] Todos los tests pasan sin regresiones.
- [ ] Existe evidencia live HTTP 200 sin parámetros ni headers especiales.
- [ ] La documentación está actualizada.
- [ ] Se realiza únicamente el commit local indicado.

---

## 15. Posición final

La Task 073 debe cerrar la separación entre:

```text
verification decision
    ≠
verification approval
```

Pero no debe convertir esa aprobación sintética en permiso clínico real.

Después de esta Task, la cadena habrá modelado:

```text
resultado de verificación
→ decisión de verificación
→ frontera de aprobación sintética
```

La siguiente decisión arquitectónica deberá ser deliberada: continuar con más fronteras sintéticas o detener la expansión y preparar una primera integración real aislada. Esta Task no debe implementar esa integración real.
