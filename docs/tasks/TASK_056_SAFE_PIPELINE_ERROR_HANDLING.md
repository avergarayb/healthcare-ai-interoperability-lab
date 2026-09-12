# Task 056 — Manejo de errores parciales, estados y observabilidad segura del pipeline

## Metadata

- **Proyecto:** `healthcare-ai-interoperability-lab`
- **Servicio principal:** `fhir-integration-service`
- **Stack:** Java 21, Spring Boot 3.5.16, HAPI FHIR 8.10.0
- **Paquete base:** `lab.healthcare.fhir`
- **Puerto:** `8081`
- **Rama sugerida:** `feature/safe-pipeline-error-handling`
- **Commit sugerido:** `feat: improve partial error handling and safe pipeline observability`

---

## WHAT

Mejorar el manejo de errores parciales, los estados del pipeline y la observabilidad segura del flujo:

```text
EHR FHIR
  ↓
Vendor adapter / RoutingService
  ↓
FhirService
  ↓
ClinicalSnapshot
  ↓
Controlled Projection
  ↓
Model Boundary Contract v1
  ↓
AgentStub
```

La implementación debe distinguir claramente entre:

- Ejecución completada correctamente.
- Ejecución completada parcialmente.
- Ejecución fallida.
- Error de autenticación.
- Error del proveedor.
- Timeout.
- Error de validación del contrato.
- Error de proyección.
- Rechazo del `AgentStub`.
- Operación no solicitada o no disponible.

Los errores parciales no deben ocultarse ni convertirse artificialmente en `SUCCESS`.

---

## WHY

Una etapa del pipeline puede fallar mientras otras producen información válida.

Ejemplo:

- `Patient` se recupera correctamente.
- `Condition` y `Observation` se recuperan correctamente.
- `DiagnosticReport` produce un timeout.
- `MedicationRequest` no está disponible para un proveedor.

Sin estados explícitos, el sistema puede:

- Reportar éxito cuando existe información incompleta.
- Ocultar qué operación falló.
- Dificultar el diagnóstico de problemas con proveedores.
- Exponer mensajes técnicos o datos sensibles en logs.
- Impedir que el consumidor conozca la calidad real de la información.
- Hacer ambiguo el comportamiento del `AgentStub`.

El objetivo es que el pipeline sea auditable, predecible y seguro, sin romper las fronteras arquitectónicas existentes.

---

## HOW

### 1. Definir estados normalizados

Estados mínimos sugeridos:

- `SUCCESS`
- `PARTIAL`
- `FAILED`
- `NOT_REQUESTED`
- `NOT_AVAILABLE`
- `TIMEOUT`
- `AUTHENTICATION_FAILED`
- `PROVIDER_ERROR`
- `VALIDATION_FAILED`
- `REJECTED`

#### Reglas de agregación

- `SUCCESS`: todas las etapas requeridas finalizaron correctamente y el contrato cumple sus invariantes.
- `PARTIAL`: existe un resultado utilizable, pero una o más operaciones no críticas fallaron, expiraron o no estuvieron disponibles.
- `FAILED`: falló una etapa crítica y no existe un resultado utilizable.
- `NOT_REQUESTED`: la operación no formaba parte del alcance solicitado.
- `NOT_AVAILABLE`: la operación es conocida, pero el proveedor no la expone o no existe información disponible.
- `TIMEOUT`: la operación superó el límite configurado.
- `AUTHENTICATION_FAILED`: falló la autenticación o autorización.
- `PROVIDER_ERROR`: el proveedor devolvió un error o una respuesta no procesable.
- `VALIDATION_FAILED`: el resultado no cumple las reglas del contrato o de la proyección.
- `REJECTED`: un consumidor interno, como `AgentStub`, rechazó un contrato inválido o incompatible.

---

### 2. Diferenciar operaciones críticas y no críticas

#### Operaciones críticas sugeridas

- Obtención de `Patient`.
- Construcción válida de `ClinicalSnapshot`.
- Generación de la proyección controlada.
- Validación del `Model Boundary Contract v1`.

#### Operaciones no críticas sugeridas

- `Condition`.
- `Observation`.
- `DiagnosticReport`.
- `MedicationRequest`.
- Otras operaciones opcionales fuera del alcance de una ejecución.

Una falla no crítica puede producir `PARTIAL`, pero no debe invalidar automáticamente todo el pipeline.

Una falla crítica debe producir `FAILED` o `REJECTED`, según corresponda.

---

### 3. Preservar el detalle por etapa

Cada resultado de etapa debe poder expresar:

- Nombre lógico de la etapa.
- Estado normalizado.
- Categoría de error, si corresponde.
- Indicador de si el error es recuperable o reintentable.
- Duración, si ya existe soporte para medirla.
- Cantidad de recursos recibidos.
- Cantidad de recursos retenidos.
- Indicador de truncamiento.
- Mensaje seguro para diagnóstico.

No incluir:

- Tokens.
- Secretos.
- `client_secret`.
- `client_id` reales.
- Identificadores de pacientes.
- URLs con parámetros sensibles.
- Excepciones completas sin sanitizar.
- Respuestas FHIR crudas.
- Payloads completos del proveedor.

---

### 4. Implementar una taxonomía segura de errores

Crear una representación interna normalizada, por ejemplo:

```text
ErrorInfo
  - code
  - category
  - retryable
  - safeMessage
  - providerStatus
```

Los códigos deben ser estables y agnósticos del proveedor.

Ejemplos:

- `FHIR_TIMEOUT`
- `FHIR_AUTHENTICATION_FAILED`
- `FHIR_PROVIDER_ERROR`
- `FHIR_RESPONSE_INVALID`
- `PROJECTION_VALIDATION_FAILED`
- `MODEL_BOUNDARY_REJECTED`
- `AGENT_STUB_REJECTED`

Evitar códigos como:

- `EPIC_TIMEOUT`
- `ORACLE_AUTH_ERROR`

El proveedor puede aparecer como metadato lógico de observabilidad, pero no debe contaminar el contrato genérico ni generar ramas específicas en el código compartido.

---

### 5. Mantener la ausencia esperada separada del error

Distinguir entre:

- Colección no solicitada.
- Colección no disponible.
- Colección vacía.
- Colección truncada.
- Colección fallida.
- Colección con timeout.

La ausencia de una colección no siempre significa fallo técnico.

Ejemplo:

- Epic puede tener `MedicationRequest = null`.
- Oracle puede devolver `MedicationRequest`.

No convertir automáticamente una colección ausente o vacía en un error técnico.

---

### 6. Actualizar la observabilidad

Usar logs estructurados y seguros. Incluir, cuando corresponda:

- Etapa.
- Operación lógica.
- Proveedor lógico.
- Estado normalizado.
- Código de error.
- HTTP status, si es seguro y está disponible.
- Duración.
- Conteos de recursos.
- `received`, `retained` y `truncated`.
- Identificador de correlación generado por el servidor, si ya existe.

No registrar:

- Access tokens.
- Refresh tokens.
- Secretos.
- URLs completas con credenciales o parámetros sensibles.
- Patient IDs reales.
- JSON clínico completo.
- Excepciones sin sanitizar.

Si se registra una excepción, utilizar un mensaje normalizado y seguro; no propagar `exception.getMessage()` sin filtrar.

---

### 7. Mantener las fronteras arquitectónicas

No:

- Agregar `Bundle → LLM`.
- Permitir `agent → Epic/HAPI/Oracle`.
- Permitir que `FhirService` importe clases específicas de vendor, SMART, snapshot, projection, model boundary o agent stub.
- Crear `Epic*Client`.
- Crear clientes por recurso.
- Agregar `if Epic` o `if Oracle` en código genérico.
- Agregar caché.
- Ampliar allowlists.
- Introducir un agente real o llamadas a un LLM.
- Modificar el contrato `Model Boundary v1` sin justificarlo explícitamente.
- Registrar secretos en documentación, pruebas o logs.
- Modificar `.env` ni subirlo al repositorio.

---

### 8. Mantener los endpoints existentes

Conservar, como mínimo:

- `GET /epic/sandbox/fhir/clinical-snapshot`
- `GET /epic/sandbox/fhir/clinical-projection`
- `GET /api/model-boundary/v1`
- `GET /lab/agent-stub`

Si se requieren estados adicionales, incorporarlos de forma compatible y controlada, sin romper las respuestas existentes.

---

### 9. Pruebas requeridas

Agregar pruebas unitarias y/o de integración para verificar:

#### Estados

- Todas las operaciones exitosas producen `SUCCESS`.
- Una operación no crítica fallida produce `PARTIAL`.
- Un timeout no crítico produce `PARTIAL`.
- Una falla crítica produce `FAILED`.
- Un contrato inválido produce `VALIDATION_FAILED` o `REJECTED`.
- Una operación no solicitada produce `NOT_REQUESTED`.
- Una capacidad no disponible produce `NOT_AVAILABLE`.

#### Agregación

- La agregación es determinista.
- Los errores críticos tienen prioridad sobre los no críticos.
- `PARTIAL` no se transforma en `SUCCESS`.
- El resultado conserva las operaciones afectadas.

#### Compatibilidad

- Epic continúa funcionando con `MedicationRequest = null`.
- Oracle continúa funcionando cuando `MedicationRequest` está presente.
- El mismo `AgentStub` procesa contratos válidos de ambos proveedores.
- No existen ramas `if Epic` / `if Oracle` en el código genérico.

#### Observabilidad segura

- Los logs o DTOs no contienen tokens.
- Los logs o DTOs no contienen secretos.
- No se serializan respuestas FHIR crudas.
- No se exponen identificadores clínicos sensibles.
- Los mensajes son estables y sanitizados.

#### Regresión

Ejecutar:

```bash
mvn test
```

Verificar que no existan fallos ni regresiones en las tareas 046–055 y que el contrato `Model Boundary v1` conserve sus invariantes.

---

## CONCEPT

Separar tres conceptos:

### 1. Estado técnico

Describe qué ocurrió durante la ejecución:

- Éxito.
- Timeout.
- Error del proveedor.
- Error de autenticación.
- Validación fallida.

### 2. Estado de disponibilidad clínica

Describe qué información está disponible:

- Completa.
- Parcial.
- Vacía.
- No solicitada.
- No disponible.
- Truncada.

### 3. Estado del contrato

Describe si el resultado puede cruzar la frontera hacia el modelo o el `AgentStub`:

- Válido.
- Inválido.
- Rechazado.

Estos conceptos no deben mezclarse.

Ejemplo de contrato válido con información parcial:

```text
Estado técnico: PARTIAL
Disponibilidad clínica: parcial
Estado del contrato: válido
```

En este caso, el sistema puede entregar un contrato válido, pero debe declarar que la información es parcial.

Ejemplo de ejecución no utilizable:

```text
Estado técnico: FAILED
Disponibilidad clínica: no utilizable
Estado del contrato: rechazado
```

En este caso, el contrato no debe llegar al `AgentStub`.

La observabilidad segura debe permitir entender qué ocurrió sin revelar datos clínicos, credenciales ni identificadores sensibles.

---

## Definition of Done

- [x] Estados normalizados definidos y documentados.
- [x] Reglas de agregación implementadas.
- [x] Operaciones críticas y no críticas identificadas.
- [x] Errores normalizados y sanitizados.
- [x] Ausencia esperada diferenciada de error técnico.
- [x] Estados por etapa preservados.
- [x] Observabilidad estructurada y segura.
- [x] No se exponen tokens, secretos, IDs ni FHIR crudo.
- [x] No se agregan ramas específicas por proveedor en código genérico.
- [x] No se modifica la frontera `Model Boundary v1`.
- [x] No se agrega LLM ni agente real.
- [x] Pruebas unitarias/integración agregadas.
- [x] `mvn test` ejecutado correctamente.
- [x] Documentación actualizada.
- [x] `.env` no modificado ni versionado.
- [ ] Commit creado con Conventional Commits.
- [x] Rama `feature/*` utilizada.
- [ ] PR creado hacia `main`.

---

## Entregables esperados

1. Código de estados y agregación del pipeline.
2. Modelo normalizado de errores.
3. Manejo explícito de resultados parciales.
4. Observabilidad segura.
5. Pruebas automatizadas.
6. Documentación actualizada.
7. Pull Request hacia `main`.

---

## Fuera de alcance

- Implementar un agente real.
- Integrar un LLM.
- Agregar RAG.
- Agregar memoria conversacional.
- Agregar nuevos proveedores.
- Ampliar la allowlist de recursos.
- Cambiar el contrato `Model Boundary v1` sin una tarea específica.
- Implementar reintentos automáticos complejos.
- Agregar caché.
- Exponer datos clínicos reales en logs o respuestas.
