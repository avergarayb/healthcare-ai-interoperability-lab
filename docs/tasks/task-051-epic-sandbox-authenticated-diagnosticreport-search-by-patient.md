# Task 051 — Epic Sandbox Authenticated DiagnosticReport Search by Patient

## WHAT

Implement un único `DiagnosticReport` search autenticado contra `epic-sandbox`, reutilizando la arquitectura genérica FHIR ya demostrada en Tasks 046–050.

Flujo obligatorio:

```text
vendor.epic
    ↓
RoutingService.searchDiagnosticReports(...)
    ↓
FhirService
    ↓
HAPI FHIR
    ↓
GET /DiagnosticReport?patient={id}&_count=5[&category=...]
    ↓
página ciega
```

Reutilizar:
- token SMART de Task 046;
- Patient context de Task 048;
- capability discovery de Task 047;
- `DiagnosticReport` + `SEARCH_TYPE`;
- patrones genéricos de Observation/Condition.

No implementar ninguna etapa posterior.

## WHY

Task 050 demostró que Epic puede ejecutar búsquedas clínicas autenticadas mediante:

```text
PatientContext + SMART token + runtime capability + RoutingService + FhirService + HAPI FHIR
```

Task 051 extiende exactamente ese patrón a `DiagnosticReport`.

Epic ya tiene habilitado `DiagnosticReport.Read/Search (Results)`.

La frontera debe continuar siendo:

```text
vendor.* → RoutingService → FhirService → HAPI
```

Snapshot, projection, model-boundary, agente y LLM permanecen fuera del alcance.

# HOW

## 1. Rama y commit

Rama:

```text
feature/epic-sandbox-diagnosticreport-search
```

Commit propuesto:

```text
feat: add Epic sandbox authenticated DiagnosticReport search by Patient
```

No commitear `.env`.

## 2. SMART authentication

Reutilizar el mecanismo de Task 046.

Para el live será necesario habilitar localmente el scope:

```text
user/DiagnosticReport.read
```

El valor se configura únicamente en `.env` y nunca se documenta, imprime, commitea ni expone.

No implementar nuevo flujo OAuth, confidential client, client secret, callback ni autenticación específica de DiagnosticReport.

## 3. Patient context

Reutilizar exactamente el Patient context de Task 048.

No crear nuevo environment variable, Patient search, Patient read ni mecanismo alternativo para descubrir el contexto.

Si el contexto no está configurado:

```text
PATIENT_CONTEXT_NOT_CONFIGURED
HTTP 409
```

con cero requests HTTP de `DiagnosticReport`.

El Patient ID nunca debe aparecer en código, tests, documentación, logs, respuestas del lab ni PR.

## 4. Capability check

Reutilizar `EpicSandboxCapabilityDiscoveryService` y `FhirServerCapabilities`.

Verificar antes del search clínico:

```java
capabilities.supports("DiagnosticReport", SEARCH_TYPE)
```

El capability discovery mantiene el patrón de Task 047: un `GET /metadata` con perfil temporal `FhirAuthenticationSettings.none()`.

No utilizar:

```java
RoutingService.discoverCapabilities("epic-sandbox")
```

No crear capability específico de Epic.

Si `DiagnosticReport SEARCH_TYPE` no está soportado:

```text
CAPABILITY_UNSUPPORTED
HTTP 409
```

y cero requests de `DiagnosticReport`.

## 5. RoutingService

Crear/reutilizar:

```java
RoutingService.searchDiagnosticReports(...)
```

siguiendo el patrón de `searchConditions(...)` y `searchObservations(...)`.

El routing debe pasar al `FhirService` la información necesaria para una búsqueda por Patient.

No introducir `if Epic` ni `if Oracle`.

La query debe ser común para Oracle y Epic.

## 6. FhirService

No crear un servicio FHIR específico de Epic.

La firma inicial debe seguir el patrón existente:

```java
searchDiagnosticReportsByPatientWithCount(String patientId, int pageSize)
```

Si durante el live se demuestra que `DiagnosticReport` requiere un filtro adicional, añadir únicamente entonces el overload genérico equivalente al patrón de Condition/Observation:

```java
searchDiagnosticReportsByPatientWithCount(
    String patientId,
    int pageSize,
    String category
)
```

No inventar un filtro adicional antes de comprobar la query genérica.

## 7. Query inicial

Primera query:

```text
patient + _count=5
```

Es decir:

```http
GET /DiagnosticReport?patient={id}&_count=5
Authorization: Bearer <token>
```

No añadir inicialmente código LOINC, código interno Epic ni filtro específico de Results.

`_count=5` es una petición al servidor, no un techo de resultados ni una regla de retención.

## 8. Si Epic exige un filtro adicional

Si el live demuestra que Epic rechaza la query genérica, la corrección debe ser genérica.

El parámetro deberá vivir en:

```text
RoutingService
        ↓
FhirService
```

y aplicarse a todos los destinos.

Nunca:

```java
if (epic)
```

Nunca en `vendor.epic`.

No crear `EpicDiagnosticReportClient` ni utilizar códigos internos de Epic para solucionar exclusivamente Epic.

Si se necesita un filtro, debe ser portable y formar parte de la query genérica.

## 9. vendor.epic

No modificar la lógica de `vendor.epic` para construir la query.

No crear:

```text
EpicDiagnosticReportClient
EpicDiagnosticReportSearch
EpicDiagnosticReportService
```

No hardcodear hosts Epic. En `vendor.epic`, `https://` continúa prohibido salvo la excepción ya existente `EpicSandboxEndpoints.FHIR_R4_BASE`.

No añadir `if Epic` en `FhirService`, timeout, query genérica ni manejo genérico FHIR.

## 10. Timeout

Mantener exactamente:

```java
FhirClientFactory.SOCKET_TIMEOUT_MS = 60_000
```

No crear timeout específico para Epic o DiagnosticReport.

## 11. Resultado

Reutilizar el patrón genérico existente.

Éxito:

```text
SUCCEEDED
HTTP 200
```

Bundle vacío sigue siendo éxito:

```text
hasEntries=false
```

No crear `EMPTY`.

## 12. Página ciega

Endpoint:

```http
GET /epic/sandbox/fhir/diagnostic-report-search
```

Puede mostrar únicamente información operacional segura, por ejemplo:

```text
status
httpStatus
destination
resourceType
hasEntries
```

Nunca mostrar Patient ID, token, Authorization header, Bundle FHIR, DiagnosticReport JSON, códigos, textos clínicos, fechas, resultados, referencias ni identificadores.

# TESTS

Añadir tests unitarios para:

1. `RoutingService.searchDiagnosticReports(...)` utiliza el `FhirService` genérico.
2. Se verifica `DiagnosticReport + SEARCH_TYPE` antes del HTTP clínico.
3. Capability unsupported produce `CAPABILITY_UNSUPPORTED` / 409 y cero requests.
4. Patient context ausente produce `PATIENT_CONTEXT_NOT_CONFIGURED` / 409 y cero requests.
5. Token ausente produce el resultado genérico de autenticación / 401 y cero requests.
6. La query inicial contiene `patient` y `_count=5`.
7. La query inicial no contiene filtros Epic-specific.
8. Empty Bundle produce `SUCCEEDED` con `hasEntries=false`.
9. No existe outcome `EMPTY`.
10. `vendor.epic` no contiene `if Epic` para la query.
11. `vendor.epic` no introduce hosts nuevos.
12. No se modifica el timeout.

Si posteriormente se añade el overload con filtro, probar que el filtro se incorpora genéricamente y no mediante lógica de vendor.

# LIVE TEST

El LiveIT debe ser opt-in:

```powershell
$env:EPIC_SANDBOX_LIVE_IT="true"
```

Sin esa variable: `SKIPPED`, sin acceso de red a Epic.

Para el live:

1. reutilizar SMART authentication;
2. utilizar Patient context existente;
3. verificar `DiagnosticReport SEARCH_TYPE`;
4. ejecutar un único DiagnosticReport search;
5. validar HTTP 200 + `SUCCEEDED`;
6. permitir `hasEntries=true` o `hasEntries=false`;
7. mantener salida ciega.

No imprimir Patient ID, token ni contenido clínico.

# CONCEPT

Task 051 demuestra:

```text
Epic SMART
    +
Patient context
    +
DiagnosticReport SEARCH capability
        ↓
RoutingService.searchDiagnosticReports(...)
        ↓
FhirService
        ↓
HAPI FHIR
        ↓
DiagnosticReport search
        ↓
blind lab
```

`DiagnosticReport` no introduce una arquitectura nueva. Si aparece una particularidad de búsqueda de Epic, se resuelve como regla genérica de query en `RoutingService`/`FhirService`, igual que Condition y Observation.

# STOP

Implementar y validar una sola búsqueda autenticada de `DiagnosticReport` por Patient.

Objetivo:

```text
HTTP 200
DiagnosticReport search
SUCCEEDED
```

o:

```text
HTTP 200
SUCCEEDED
hasEntries=false
```

**STOP ahí.**

No diseñar ni implementar Task 052.

No avanzar hacia snapshot, projection, model-boundary, agent, LLM, `ai-service` ni MedicationRequest.

La única meta de Task 051 es demostrar:

```text
Epic sandbox
    ↓
authenticated DiagnosticReport search
    ↓
generic RoutingService
    ↓
generic FhirService
    ↓
HAPI FHIR
```
