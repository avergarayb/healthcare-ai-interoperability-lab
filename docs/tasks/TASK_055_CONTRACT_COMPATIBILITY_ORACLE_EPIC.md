# TASK 055 — Comparación formal de los flujos Oracle y Epic mediante pruebas de contrato y compatibilidad

## Estado

**IMPLEMENTED** (pending live)

## WHAT

Comparar formalmente los flujos Oracle y Epic para confirmar que ambos producen un `Model Boundary Contract v1` compatible con el mismo `AgentStub` genérico.

La tarea debe mantener el alcance limitado a:

- Oracle.
- Epic Sandbox.
- `ClinicalSnapshot`.
- Proyección controlada.
- `Model Boundary Contract v1`.
- `AgentStub`.
- Pruebas de contrato y compatibilidad.
- Sin LLM.
- Sin agente real.
- Sin ampliar la allowlist.
- Sin agregar `MedicationRequest` a Epic.

El objetivo es demostrar que las diferencias entre proveedores se resuelven antes de la frontera del agente y no dentro del contrato ni del `AgentStub`.

---

## WHY

Las Tasks 053 y 054 demostraron individualmente que:

- Epic puede generar una proyección controlada.
- El `AgentStub` puede consumir el contrato v1 de Epic.
- Oracle mantiene su flujo existente.
- `MedicationRequest` permanece ausente en Epic y disponible en Oracle.

Ahora es necesario demostrar formalmente que ambos proveedores respetan la misma frontera contractual.

La diferencia entre proveedores debe resolverse antes del `Model Boundary Contract`:

```text
Epic   → ClinicalSnapshotContents.withoutMedicationRequests()
Oracle → ClinicalSnapshotContents.allCollections()
```

Después de esa etapa, el contrato debe ser genérico y el `AgentStub` no debe distinguir si los datos provienen de Epic u Oracle.

Esta tarea debe prevenir:

- DTOs específicos por proveedor.
- Ramas `if Epic` o `if Oracle`.
- Allowlist diferente por proveedor.
- Contratos incompatibles.
- Dependencia del agente con FHIR o con el EHR.
- Manejo incorrecto de colecciones ausentes.
- Expansión accidental del contrato antes de incorporar un agente real.

---

## HOW

### 1. Definir las invariantes comunes del contrato v1

Identificar y documentar las propiedades que deben ser iguales para Oracle y Epic:

- `contractVersion = v1`.
- Estructura general del contrato.
- Sección Patient.
- Sección Conditions.
- Sección Observations.
- Sección DiagnosticReports.
- Conteos recibidos.
- Conteos retenidos.
- Indicadores `truncated`.
- Indicador `hasClinicalData`.
- Estados técnicos de procesamiento.
- Allowlist 042.

La comparación debe centrarse en la estructura y en las garantías del contrato, no en valores clínicos reales.

### 2. Documentar las diferencias permitidas

Documentar explícitamente las diferencias válidas:

| Aspecto | Epic | Oracle |
|---|---|---|
| `MedicationRequest` | Ausente, representado como `null` | Puede estar presente |
| Contenido del snapshot | `withoutMedicationRequests()` | `allCollections()` |
| Proveedor de origen | `epic-sandbox` | Oracle |
| Endpoint de laboratorio | `/epic/sandbox/fhir/clinical-projection` | Endpoints Oracle existentes |

Estas diferencias no deben modificar:

- La versión del contrato.
- La allowlist.
- La estructura de los grupos comunes.
- El comportamiento genérico del `AgentStub`.

### 3. Crear pruebas de contrato compartidas

Crear pruebas reutilizables que validen el mismo conjunto de reglas para ambos proveedores.

Las pruebas deben comprobar:

#### Versión

- Oracle produce `contractVersion = v1`.
- Epic produce `contractVersion = v1`.
- Versiones ausentes o distintas son rechazadas.

#### Estructura

- Patient presente.
- Conditions presente cuando corresponda.
- Observations presente cuando corresponda.
- DiagnosticReports presente cuando corresponda.
- La estructura es aceptada por el mismo `AgentStub`.

#### Allowlist

Confirmar que los campos permitidos siguen siendo únicamente:

```text
Patient:
  resourceType

Condition:
  resourceType
  clinicalStatus.code → clinicalStatusCode

Observation:
  resourceType
  status

DiagnosticReport:
  resourceType
  status
```

No agregar campos para hacer que Oracle y Epic “coincidan”.

#### Retention Ceiling

Validar que el techo `N=5` se mantenga para las colecciones aplicables.

Comprobar por separado:

- Conteo recibido.
- Conteo retenido.
- Indicador `truncated`.

El techo de retención no debe interpretarse como límite de consulta FHIR ni como límite de datos existentes.

### 4. Validar `MedicationRequest`

Comprobar formalmente:

#### Epic

```text
MedicationRequest = null
```

Debe permanecer ausente y no debe convertirse en una colección vacía.

#### Oracle

`MedicationRequest` puede estar presente debido a:

```text
ClinicalSnapshotContents.allCollections()
```

El `AgentStub` debe aceptar ambas situaciones sin lógica específica del proveedor.

No se debe:

- Agregar `MedicationRequest` a Epic.
- Eliminar `MedicationRequest` de Oracle.
- Ampliar la allowlist 042.
- Crear un tratamiento especial dentro del agente.

### 5. Validar el AgentStub como consumidor común

Confirmar que el mismo `AgentStub` procesa contratos de Oracle y Epic.

Debe:

- Aceptar contratos v1 válidos de ambos proveedores.
- Reportar los mismos indicadores técnicos.
- Interpretar correctamente conteos y truncamientos.
- Aceptar `MedicationRequest = null` en Epic.
- Aceptar `MedicationRequest` presente en Oracle.
- Rechazar contratos inválidos.
- No consultar FHIR ante errores contractuales.

No crear:

- `EpicAgentStub`.
- `OracleAgentStub`.
- `EpicContractConsumer`.
- `OracleContractConsumer`.
- `EpicModelBoundaryClient`.
- `OracleModelBoundaryClient`.

### 6. Validar endpoints existentes

Mantener las superficies actuales.

#### Epic

```text
GET /epic/sandbox/fhir/clinical-projection
```

#### Oracle

```text
GET /api/model-boundary/v1
GET /lab/agent-stub
```

Los endpoints Oracle continúan Oracle-backed.

No convertirlos en endpoints multi-proveedor salvo que sea estrictamente necesario para cumplir la validación y se documente explícitamente el motivo.

No crear nuevos endpoints de agente real.

### 7. Validar aislamiento arquitectónico

Confirmar que el código del contrato y del `AgentStub` no dependa directamente de:

```text
Epic*
Oracle*
FhirService
RoutingService
HAPI FHIR
SMART
OAuth
tokens
URLs de EHR
```

Las dependencias deben limitarse a:

- DTOs genéricos.
- Contrato v1.
- Servicios de validación o consumo genéricos.

No debe existir lógica como:

```java
if (provider.equals("epic")) {
    ...
}

if (provider.equals("oracle")) {
    ...
}
```

dentro del `AgentStub`, del mapper o del consumidor del contrato.

### 8. Ejecutar pruebas automatizadas

Ejecutar:

```text
mvn test
```

en:

```text
fhir-integration-service
```

Registrar:

- Cantidad total de pruebas.
- Fallos.
- Errores.
- Pruebas de contrato agregadas o modificadas.
- Resultado de compilación.
- Compatibilidad con las pruebas existentes de Oracle y Epic.

La validación debe incluir casos positivos y negativos:

- Contrato Oracle válido.
- Contrato Epic válido.
- Contrato con versión inválida.
- Patient ausente.
- Colección obligatoria ausente.
- Campo fuera de la allowlist.
- Epic con `MedicationRequest = null`.
- Oracle con `MedicationRequest` presente.
- Conteos y truncamiento válidos.
- Contrato parcial inválido.

### 9. Realizar validación live ciega

Validar Epic mediante:

```text
GET /epic/sandbox/fhir/clinical-projection
```

Confirmar únicamente estados técnicos:

```text
status=SUCCESS
destination=epic-sandbox
controlledProjection=SUCCEEDED
modelBoundaryContract=v1
modelBoundary=SUCCEEDED
agentStub=SUCCEEDED
sensitiveFieldsExposed=false
rawFhirExposed=false
```

Para Oracle, utilizar la evidencia disponible y, si es posible, ejecutar:

```text
GET /lab/agent-stub
```

o:

```text
GET /api/model-boundary/v1
```

La evidencia debe permanecer ciega y no debe incluir:

- Patient IDs.
- Tokens.
- Client IDs.
- JSON FHIR.
- Nombres.
- Diagnósticos.
- Valores clínicos.
- URLs privadas.
- Datos identificables.

Si no se realiza una sesión live Oracle, documentarlo explícitamente. No presentar la validación por tests como evidencia live.

### 10. Documentar el resultado

Actualizar:

- `docs/progress/progress-log.md`.
- Documentación específica de la Task 055.
- ADR únicamente si se modifica una decisión arquitectónica.

Registrar:

- Invariantes comunes del contrato.
- Diferencias permitidas entre Epic y Oracle.
- Pruebas de contrato.
- Resultado de `mvn test`.
- Evidencia live disponible.
- Confirmación de compatibilidad del mismo `AgentStub`.
- Confirmación de que no se amplió la allowlist.
- Confirmación de que `MedicationRequest` no se agregó a Epic.
- Riesgos o limitaciones pendientes.

No registrar secretos ni información clínica identificable.

---

## CONCEPT

La Task 055 establece que el `Model Boundary Contract v1` es el límite común entre la integración clínica y cualquier agente futuro.

La arquitectura debe quedar así:

```text
                    ┌─────────────────────┐
                    │     Epic Sandbox    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ ClinicalSnapshot    │
                    │ without Medication  │
                    │ Requests             │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Controlled          │
                    │ Projection          │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Model Boundary      │
                    │ Contract v1         │
                    └──────────┬──────────┘
                               │
                               ▼
                         AgentStub
```

```text
                    ┌─────────────────────┐
                    │       Oracle        │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ ClinicalSnapshot    │
                    │ allCollections()    │
                    └──────────┬──────────┘
                               │
                               ▼
                    Controlled Projection
                               │
                               ▼
                    Model Boundary Contract v1
                               │
                               ▼
                         AgentStub
```

Ambos flujos deben converger en el mismo consumidor:

```text
Epic Contract v1 ─────┐
                      ├──► AgentStub genérico
Oracle Contract v1 ──┘
```

El `AgentStub` debe observar únicamente:

```text
contractVersion
Patient
Conditions
Observations
DiagnosticReports
MedicationRequest opcional
counts
retention
truncated
hasClinicalData
technical status
```

No debe observar ni conocer:

```text
Epic
Oracle
FHIR
HAPI
SMART
OAuth
Patient ID
tokens
EHR URLs
```

### Resultado esperado

La Task 055 estará completa cuando se demuestre que:

> Oracle y Epic producen contratos `Model Boundary Contract v1` compatibles con el mismo `AgentStub`, manteniendo únicamente las diferencias permitidas de contenido y sin introducir lógica específica por proveedor, ampliar la allowlist ni incorporar un agente real.

### Fuera de alcance

No implementar todavía:

- Agente determinista avanzado.
- Agente basado en LLM.
- `ai-service`.
- Diagnóstico clínico.
- Recomendaciones médicas.
- Razonamiento clínico.
- Memoria de pacientes.
- RAG clínico.
- Integración con OpenAI u otro proveedor de modelos.
- Nuevos proveedores EHR.
- Tasks 056–060.
