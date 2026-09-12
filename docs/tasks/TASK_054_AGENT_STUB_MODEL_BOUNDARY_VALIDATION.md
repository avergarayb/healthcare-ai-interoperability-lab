# TASK 054 — Validación del consumo del Model Boundary Contract v1 por el Agent Stub

## Estado

**COMPLETED**

## WHAT

Validar que el `AgentStub` consuma correctamente el `Model Boundary Contract v1` generado desde la proyección controlada de Epic Sandbox, sin romper el flujo existente de Oracle.

La tarea debe mantenerse limitada a:

- Epic Sandbox.
- Oracle existente.
- `Model Boundary Contract v1`.
- `AgentStub`.
- Sin LLM.
- Sin agente real.
- Sin ampliar la allowlist.
- Sin agregar `MedicationRequest` a Epic.

### Alcance funcional

Se debe confirmar que:

1. El contrato v1 generado por Epic tiene la estructura esperada.
2. El `AgentStub` consume únicamente el contrato v1.
3. Epic y Oracle pueden utilizar el mismo contrato genérico.
4. La ausencia de `MedicationRequest` en Epic no provoca errores.
5. El flujo Oracle existente permanece compatible.
6. El agente no tiene acceso directo a FHIR, HAPI, SMART, tokens ni proveedores.

---

## WHY

La Task 053 confirmó que Epic puede producir una proyección controlada y que el `AgentStub` puede observarla dentro de la página específica de Epic.

Sin embargo, todavía falta validar formalmente la frontera de entrada del agente:

- La versión del contrato debe ser `v1`.
- La estructura debe ser válida.
- Los grupos y conteos deben ser interpretados correctamente.
- Los indicadores de truncamiento deben conservarse.
- Epic y Oracle deben ser consumibles por el mismo stub.
- La ausencia de `MedicationRequest` en Epic debe representarse como `null`.
- El stub no debe intentar recuperar información desde FHIR cuando el contrato sea inválido.

Esta tarea prepara la base técnica para futuros agentes, pero **no construye todavía un agente inteligente**.

---

## HOW

### 1. Revisar el contrato v1 existente

Identificar el contrato producido por `ModelBoundaryMapper` y verificar que mantenga la estructura genérica definida en la Task 042.

Validar, como mínimo:

- Versión del contrato: `v1`.
- Presencia de las secciones esperadas.
- Estructura de:
  - Patient.
  - Conditions.
  - Observations.
  - DiagnosticReports.
- Campos permitidos por la allowlist 042.
- Conteos recibidos y retenidos.
- Indicadores de truncamiento.
- Estado de disponibilidad de datos clínicos.

No ampliar el contrato ni agregar nuevos campos clínicos.

### 2. Validar el consumo por el Agent Stub

El `AgentStub` debe recibir el contrato v1 como única entrada funcional.

Debe poder:

- Aceptar un contrato válido.
- Confirmar que la versión es `v1`.
- Leer los grupos permitidos.
- Reportar conteos recibidos y retenidos.
- Identificar si existen datos clínicos.
- Identificar condiciones de truncamiento.
- Devolver un resultado técnico y determinista.

El stub no debe:

- Leer recursos FHIR directamente.
- Invocar `FhirService`.
- Invocar `RoutingService`.
- Conocer Epic u Oracle.
- Leer tokens SMART.
- Resolver Patient IDs.
- Acceder a URLs de EHR.
- Generar diagnósticos.
- Generar recomendaciones clínicas.
- Invocar un LLM.

### 3. Validar Epic Sandbox

Usar el flujo implementado en la Task 053:

```text
EpicSandboxClinicalProjectionService
        ↓
ClinicalProjectionAssembler
        ↓
allowlist 042 + RetentionCeiling N=5
        ↓
ModelBoundaryMapper
        ↓
Model Boundary Contract v1
        ↓
AgentStub.observe
```

La página de laboratorio esperada es:

```text
GET /epic/sandbox/fhir/clinical-projection
```

La evidencia debe ser ciega y confirmar, como mínimo:

```text
status=SUCCESS
destination=epic-sandbox
controlledProjection=SUCCEEDED
modelBoundaryContract=v1
modelBoundary=SUCCEEDED
agentStub=SUCCEEDED
sensitiveFieldsExposed=false
rawFhirExposed=false
hasClinicalData=true
```

También se debe comprobar:

```text
MedicationRequest = null
```

La ausencia debe representarse como `null`, no como una colección vacía.

### 4. Validar Oracle

Ejecutar la ruta existente de Oracle que utiliza el mismo contrato v1 y confirmar que no se rompe el comportamiento actual.

Oracle debe continuar utilizando:

```text
ClinicalSnapshotContents.allCollections()
```

Por lo tanto, Oracle conserva el soporte para `MedicationRequest`.

Validar que:

- Oracle sigue produciendo el contrato v1.
- El stub continúa observando el contrato Oracle.
- La presencia de `MedicationRequest` en Oracle no modifica la allowlist.
- No se agrega lógica específica del proveedor dentro del stub.
- No se modifica el overload de cuatro argumentos utilizado por Oracle.

### 5. Agregar o ajustar pruebas automatizadas

#### Contrato válido

Comprobar que:

- El stub acepta un contrato v1 válido.
- El resultado es exitoso.
- Los conteos se reportan correctamente.
- Los indicadores de truncamiento se conservan.
- `hasClinicalData` se interpreta correctamente.

#### Contrato inválido

Comprobar el rechazo determinista de:

- Versión ausente.
- Versión diferente de `v1`.
- Sección obligatoria ausente.
- Estructura incompatible.
- Campos fuera de la allowlist.

El stub no debe intentar recuperar datos desde FHIR ante un contrato inválido.

#### Epic sin MedicationRequest

Comprobar que:

- `MedicationRequest` permanece como `null`.
- El contrato Epic sigue siendo válido.
- El stub procesa el contrato sin errores.

#### Oracle con MedicationRequest

Comprobar que:

- El contrato Oracle sigue siendo válido.
- El stub lo consume sin lógica específica para Oracle.
- No existe una rama `if Oracle` ni `if Epic` dentro del agente.

### 6. Validar seguridad de salida

La respuesta del laboratorio debe ser ciega y no debe mostrar:

- Tokens.
- Client IDs.
- Patient IDs.
- Nombres de pacientes.
- Identificadores clínicos.
- JSON FHIR.
- Narrativas.
- Valores de observaciones.
- Texto de informes.
- Diagnósticos.
- Dosis.
- URLs internas o de proveedores.

Debe mostrar solamente estados técnicos, conteos y flags de seguridad.

### 7. Validar límites arquitectónicos

Confirmar que el código del `AgentStub` no importe ni dependa directamente de:

```text
FhirService
RoutingService
Epic*
Oracle*
SMART*
HAPI FHIR
```

La dependencia permitida debe ser únicamente el contrato v1 o los DTOs genéricos que lo representan.

No crear:

- `EpicAgentStub`.
- `OracleAgentStub`.
- `EpicModelBoundaryClient`.
- `OracleModelBoundaryClient`.
- `EpicAgentService`.
- `OracleAgentService`.

### 8. Validar compatibilidad de endpoints existentes

No cambiar innecesariamente los endpoints públicos existentes.

La Task 054 debe validar principalmente el flujo Epic de la Task 053 y la compatibilidad del flujo Oracle.

No se debe convertir todavía:

```text
GET /api/model-boundary/v1
GET /lab/agent-stub
```

en endpoints multi-proveedor, salvo que sea estrictamente necesario para cumplir esta tarea y se documente explícitamente.

No crear nuevos endpoints de agente real.

### 9. Ejecutar validaciones

Ejecutar, como mínimo:

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
- Pruebas nuevas o modificadas.
- Resultado de compilación.

Realizar también validación live ciega de Epic y Oracle, sin solicitar ni registrar:

- Patient IDs.
- Tokens.
- Client IDs.
- JSON clínico.
- Datos clínicos identificables.

### 10. Documentar el resultado

Actualizar:

- `docs/progress/progress-log.md`.
- La documentación específica de la Task 054, si corresponde.
- Cualquier ADR solamente si se modifica una decisión arquitectónica existente.

La documentación debe registrar:

- Qué se validó.
- Qué archivos se modificaron.
- Qué pruebas se ejecutaron.
- Evidencia live ciega.
- Riesgos o limitaciones.
- Confirmación de que no se utilizó LLM.
- Confirmación de que no se creó un agente real.
- Confirmación de que no se amplió la allowlist.
- Confirmación de que Epic no incorpora `MedicationRequest`.

No registrar secretos ni identificadores sensibles.

---

## CONCEPT

La Task 054 valida la **frontera de entrada del agente**, no la inteligencia del agente.

La arquitectura debe permanecer así:

```text
EHR / Vendor
    ↓
FHIR Integration
    ↓
ClinicalSnapshot
    ↓
Controlled Projection
    ↓
Model Boundary Contract v1
    ↓
AgentStub
```

El `AgentStub` debe ser agnóstico al proveedor:

```text
AgentStub
    ├── conoce el contrato v1
    ├── valida la estructura
    ├── conoce los estados y conteos permitidos
    ├── identifica truncamientos
    └── produce una respuesta técnica determinista
```

El `AgentStub` no debe conocer:

```text
Epic
Oracle
FHIR
HAPI
SMART
OAuth
Patient ID
Tokens
EHR URLs
```

La diferencia entre Epic y Oracle debe resolverse antes de la frontera del agente:

```text
Epic   → ClinicalSnapshotContents.withoutMedicationRequests()
Oracle → ClinicalSnapshotContents.allCollections()
```

Después del `Model Boundary Contract v1`, ambos flujos deben ser indistinguibles para el stub.

### Resultado esperado

La Task 054 estará completa cuando se demuestre que:

> Epic y Oracle pueden entregar contratos v1 compatibles a un mismo Agent Stub genérico, sin LLM, sin agente real, sin ampliar la allowlist y sin permitir que el agente acceda directamente a FHIR o a los proveedores.

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
- Integración directa con OpenAI u otro proveedor de modelos.
- Nuevos proveedores EHR.
- Tasks 055–060.
