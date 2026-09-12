# Task 053 — Proyección controlada de ClinicalSnapshot para Epic Sandbox

## Estado

**COMPLETED**

## Objetivo

Extender la proyección controlada existente —validada inicialmente con Oracle Health en la Task 042— para que pueda consumir el `ClinicalSnapshot` de Epic Sandbox y producir una salida segura, mínima y vendor-neutral.

La proyección debe mantener la frontera:

```text
Epic / Oracle FHIR
        ↓
ClinicalSnapshot
        ↓
Controlled Projection
        ↓
Model Boundary Contract v1
        ↓
Agente
```

La Task 053 no debe integrar LLM, agente real ni nuevos recursos FHIR.

---

## Contexto

Las Tasks 046–051 validaron autenticación SMART, capability discovery y búsquedas clínicas individuales en Epic Sandbox.

La Task 052 consolidó esos resultados en un `ClinicalSnapshot` genérico mediante:

- Patient read.
- Condition search.
- Observation search.
- DiagnosticReport search.

El snapshot de Epic no incluye `MedicationRequest`. Oracle mantiene su comportamiento actual, que incluye `MedicationRequest`.

La diferencia de contenido debe resolverse mediante el modelo genérico `ClinicalSnapshotContents`, no mediante condiciones `if Epic` o `if Oracle` dentro de la proyección.

---

## Alcance

Implementar la proyección controlada de un `ClinicalSnapshot` de Epic Sandbox usando exactamente la allowlist ya aprobada en la Task 042.

La proyección debe permitir que el contrato de salida sea consumido por el endpoint:

```text
/api/model-boundary/v1
```

o por el punto de entrada equivalente ya existente.

Antes de crear un endpoint nuevo, revisar y reutilizar el flujo actual.

---

## Allowlist autorizada

La proyección solo puede exponer los siguientes campos:

### Patient

- `resourceType`

### Condition

- `resourceType`
- `clinicalStatus.code`, mapeado como `clinicalStatusCode`

### Observation

- `resourceType`
- `status`

### DiagnosticReport

- `resourceType`
- `status`

No ampliar esta allowlist en esta tarea.

---

## Datos explícitamente prohibidos

La salida proyectada no debe incluir:

- Patient ID.
- Identificadores personales.
- Nombre.
- Apellido.
- Fecha de nacimiento.
- Teléfono.
- Dirección.
- Texto narrativo.
- `code.display`.
- Códigos clínicos no autorizados.
- Valores de Observation.
- Unidades de Observation.
- Texto de DiagnosticReport.
- Dosis.
- Medicamentos.
- Referencias de sujeto.
- JSON FHIR crudo.
- Access token.
- Refresh token.
- Client ID.
- Client secret.
- URLs privadas.
- Cualquier dato no incluido expresamente en la allowlist.

---

## Requisitos funcionales

### 1. Consumir el ClinicalSnapshot genérico

La proyección debe aceptar el `ClinicalSnapshot` producido por la Task 052 sin crear una implementación específica de Epic.

No crear:

- `EpicControlledProjection`.
- `EpicModelBoundaryService`.
- `EpicProjectionClient`.
- Clientes específicos por recurso.

Si existe una frontera vendor-specific, debe limitarse a adaptar el resultado al modelo genérico antes de la proyección.

### 2. Reutilizar la proyección Oracle

Identificar la implementación de la Task 042 y reutilizar:

- El mismo servicio de proyección.
- Los mismos DTOs, si son compatibles.
- La misma allowlist.
- Las mismas reglas de exclusión.
- El mismo contrato de salida.

La proyección debe funcionar con:

- Snapshot Oracle.
- Snapshot Epic.

Sin duplicar lógica por proveedor.

### 3. Manejar la ausencia de MedicationRequest

El snapshot Epic no contiene `MedicationRequest`.

La proyección debe:

- Aceptar correctamente la ausencia de ese grupo.
- No fallar por ausencia de `MedicationRequest`.
- No inventar una colección vacía si el contrato distingue entre ausencia y colección vacía, salvo que ese sea el comportamiento ya definido.
- Mantener compatibilidad con el snapshot Oracle.

No agregar `MedicationRequest` a Epic en esta tarea.

### 4. Generar el Model Boundary Contract v1

La salida debe ajustarse al contrato v1 existente.

Verificar:

- Estructura.
- Nombres de campos.
- Tipos.
- Estado de operación.
- Metadatos permitidos.
- Ausencia de datos sensibles.
- Compatibilidad con el agente stub existente.

No modificar el contrato v1 salvo que exista una incompatibilidad real y documentada.

Si se requiere modificarlo, detenerse y reportar la incompatibilidad antes de ampliar el alcance.

### 5. Endpoint y respuesta pública

Reutilizar el endpoint actual del model boundary.

La respuesta pública debe:

- Ser vendor-neutral.
- No exponer FHIR crudo.
- No exponer HAPI.
- No exponer Patient ID.
- No exponer tokens.
- No exponer datos clínicos fuera de la allowlist.
- No permitir que el consumidor elija arbitrariamente campos FHIR.
- No aceptar consultas libres hacia Epic u Oracle.

El agente debe consumir únicamente el contrato v1.

---

## Requisitos no funcionales

### Arquitectura

- Mantener la separación:
  - vendor adapter
  - RoutingService
  - FhirService
  - ClinicalSnapshot
  - Controlled Projection
  - Model Boundary Contract
  - Agent Stub
- No introducir `if Epic` o `if Oracle` en la proyección genérica.
- No modificar `FhirService` para resolver diferencias de proyección.
- No introducir nuevos clientes por recurso.
- No modificar el timeout genérico:
  - `FhirClientFactory.SOCKET_TIMEOUT_MS = 60_000`
- No agregar cache.
- No ampliar allowlists.
- No redescubrir capabilities dentro de la proyección.
- No modificar SMART.

### Seguridad

No incluir en código, logs, documentación, tests ni respuestas:

- Tokens.
- Client ID.
- Client secret.
- Patient ID real.
- Datos clínicos reales.
- URLs privadas.
- Identificadores personales.

`.env` no debe modificarse ni commitearse.

---

## Plan de implementación recomendado

### Paso 1 — Revisar la Task 042

Identificar:

- Servicio de proyección.
- DTO de salida.
- Allowlist actual.
- Reglas de filtrado.
- Tests existentes.
- Endpoint del model boundary.
- Integración con el agente stub.

No modificar código todavía.

### Paso 2 — Revisar la Task 052

Confirmar:

- Tipo real de `ClinicalSnapshot`.
- Tipo real de `ClinicalSnapshotContents`.
- Representación de grupos ausentes.
- Forma de transportar Patient, Condition, Observation y DiagnosticReport.
- Estado de operación y errores parciales.

### Paso 3 — Ejecutar la proyección con snapshot Epic

Usar el snapshot Epic de la Task 052 como entrada.

Comprobar que:

- La proyección no requiere `MedicationRequest`.
- La salida conserva únicamente la allowlist autorizada.
- El resultado es igual en estructura al resultado Oracle equivalente, salvo la ausencia de MedicationRequest cuando corresponda.

### Paso 4 — Validar el contrato

Validar el contrato v1 con:

- El consumidor/agente stub existente.
- Casos con datos.
- Casos sin `MedicationRequest`.
- Casos de error o snapshot incompleto, si el contrato los contempla.

### Paso 5 — Validación live

Ejecutar el flujo completo con Epic Sandbox:

```text
SMART token
    ↓
Patient read
    ↓
Condition search
    ↓
Observation search
    ↓
DiagnosticReport search
    ↓
ClinicalSnapshot
    ↓
Controlled Projection
    ↓
Model Boundary Contract v1
```

La evidencia visible debe ser ciega y limitada a:

- Estado general.
- Estado del contrato.
- Cantidades o presencia de grupos, si ya están permitidas.
- Confirmación de que el agente recibió el contrato.
- Confirmación de ausencia de campos prohibidos.

No mostrar contenido clínico ni identificadores.

---

## Criterios de aceptación

- [x] La proyección controlada acepta el `ClinicalSnapshot` de Epic.
- [x] Se reutiliza la implementación genérica de la Task 042.
- [x] No se crea una proyección específica de Epic.
- [x] No se agregan condiciones `if Epic` o `if Oracle` en la proyección.
- [x] La allowlist autorizada permanece sin ampliaciones.
- [x] `MedicationRequest` ausente en Epic no provoca error.
- [x] Oracle mantiene su comportamiento actual.
- [x] El contrato Model Boundary v1 permanece compatible.
- [x] El agente stub consume únicamente el contrato v1.
- [x] No se expone JSON FHIR crudo.
- [x] No se exponen tokens, Patient ID ni datos clínicos prohibidos.
- [x] La validación live de Epic es exitosa.
- [x] Los tests aplicables pasan.
- [x] La documentación de progreso queda actualizada.
- [x] `.env` no fue modificado ni commiteado.

---

## Evidencia requerida para el cierre

Registrar únicamente evidencia segura, ajustando los nombres a la implementación real:

```text
destination=epic-sandbox
clinicalSnapshot=SUCCEEDED
controlledProjection=SUCCEEDED
modelBoundaryContract=v1
modelBoundary=SUCCEEDED
agentStub=SUCCEEDED
sensitiveFieldsExposed=false
rawFhirExposed=false
```

No registrar:

- Patient ID.
- Tokens.
- Client ID.
- JSON FHIR.
- Nombres.
- Diagnósticos.
- Valores de Observation.
- Texto de DiagnosticReport.

---

## Entregables

1. Proyección controlada compatible con el snapshot Epic.
2. Reutilización de la allowlist de la Task 042.
3. Compatibilidad con Oracle.
4. Validación de ausencia de `MedicationRequest` en Epic.
5. Tests unitarios o de integración apropiados.
6. Validación live ciega.
7. Actualización de `docs/progress/progress-log.md`.
8. Actualización mínima de documentación relacionada, si corresponde.

---

## Restricciones de trabajo

Antes de implementar:

- Revisar la implementación real de las Tasks 042, 043, 044, 045 y 052.
- Confirmar nombres reales de clases, DTOs, endpoints y métodos.
- No asumir que el contrato descrito coincide exactamente con el código.
- No modificar código hasta identificar el punto correcto de integración.

Durante la implementación:

- No tocar `.env`.
- No crear una rama nueva sin autorización.
- No hacer commit.
- No hacer push.
- No abrir un PR.
- No modificar tareas anteriores.
- No ampliar la allowlist.
- No integrar LLM.
- No integrar un agente real.
- No agregar MedicationRequest a Epic.

Al finalizar, reportar:

1. Archivos modificados.
2. Servicio genérico reutilizado.
3. Compatibilidad Oracle/Epic.
4. Tratamiento de la ausencia de MedicationRequest.
5. Tests y validaciones ejecutadas.
6. Evidencia live segura.
7. Riesgos o decisiones pendientes.
8. Confirmación explícita de que no se tocaron `.env`, secretos ni datos clínicos reales.
