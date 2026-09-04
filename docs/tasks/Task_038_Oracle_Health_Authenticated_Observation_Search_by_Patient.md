# Task 038 — Oracle Health Authenticated Observation Search by Patient

**Proyecto:** Healthcare AI Interoperability Lab  
**Servicio:** `fhir-integration-service`  
**Stack:** Java 21, Spring Boot 3.5.16, HAPI FHIR 8.10.0  
**Puerto:** `8081`

---

## 1. Objetivo

Implementar una búsqueda FHIR autenticada de recursos **Observation** asociados exclusivamente al `PatientContext` explícito validado en Task 036.

Operación objetivo:

```text
GET /Observation?patient={patientId}&_count=5
```

con un Bearer token real emitido mediante SMART Authorization Code + PKCE.

---

# 2. WHAT / WHY / HOW / CONCEPT

## WHAT

Agregar una operación autenticada para buscar `Observation` relacionadas con el Patient configurado.

El laboratorio debe demostrar acceso clínico FHIR real sin exponer el Bundle ni datos clínicos.

## WHY

Task 037 demostró:

```text
GET /Condition?patient={id}&category=problem-list-item&_count=5
```

→ HTTP 200  
→ Bundle  
→ `CONDITION_SEARCH_SUCCEEDED`

`Observation` abre otra categoría fundamental de información clínica:

- resultados de laboratorio;
- signos vitales;
- mediciones;
- resultados cuantitativos;
- observaciones clínicas codificadas.

Antes de construir un Clinical Snapshot o cualquier procesamiento con IA, debemos demostrar acceso controlado a distintos recursos clínicos.

## HOW

```text
ORACLE_HEALTH_SANDBOX_PATIENT_ID
              ↓
       PatientContext
              ↓
Capability: Observation SEARCH_TYPE
              ↓
IssuedAccessTokenProvider
              ↓
RoutingService.searchObservations(...)
              ↓
FhirService
              ↓
GET /Observation?patient={id}&_count=5
              ↓
FHIR Bundle
              ↓
Safe diagnostic result
```

## CONCEPT

```text
Patient access ≠ Observation access
```

Aunque el Patient pueda leerse y Condition pueda consultarse, debemos demostrar independientemente que `Observation` puede ser consultado con el mismo contexto y autorización.

---

# 3. Contexto previo obligatorio

La Task 038 asume cerradas y mergeadas:

```text
033 — Oracle Health secure sandbox SMART authentication
034 — Oracle Health real capability discovery
035 — Oracle Health authenticated FHIR read
036 — Oracle Health controlled Patient context read
037 — Oracle Health authenticated Condition search by Patient
```

Cadena:

```text
033  Token SMART real
034  CapabilityStatement real
035  Patient search autenticado
036  GET /Patient/{id}
037  Condition search por Patient
038  Observation search por Patient
```

No modificar ni duplicar la infraestructura SMART existente.

---

# 4. Alcance

## Incluido

- Búsqueda autenticada de `Observation` por Patient.
- Reutilización de `PatientContext`.
- Reutilización del token real SMART.
- Validación previa de capability runtime.
- Uso de `RoutingService`.
- Uso de `FhirService`.
- Resultado diagnóstico seguro.
- Endpoint HTTP de laboratorio.
- Tests unitarios, integración y LiveIT opt-in.
- Reutilización de la política genérica de timeout existente.

## Fuera de alcance

- Crear, actualizar o eliminar Observation.
- Enumerar Observations globalmente.
- Buscar Patients para descubrir IDs.
- Mostrar JSON clínico.
- Interpretar resultados clínicos.
- Calcular tendencias.
- Normalizar códigos clínicos o LOINC.
- Clinical Snapshot.
- AI / LLM.
- DiagnosticReport.
- MedicationRequest.
- EHR launch.
- Persistencia de tokens.

---

# 5. Operación FHIR

La búsqueda debe estar acotada al Patient context:

```text
GET /Observation?patient={patientId}&_count=5
```

El `patientId` debe provenir exclusivamente de:

```text
PatientContext
```

## Prohibido

```text
GET /Observation
GET /Observation?_count=...
```

sin Patient context.

No debe existir:

- enumeración clínica global;
- adivinación de Patient IDs;
- fallback automático a otro Patient;
- búsqueda de Patient para descubrir contexto.

---

# 6. Safe Limit

Usar un límite explícito y pequeño:

```text
_count=5
```

El objetivo es demostrar conectividad y autorización, no descargar un historial clínico completo.

Principio:

```text
Minimum necessary clinical access
```

Si Oracle requiere parámetros adicionales para aceptar la búsqueda, investigar y documentar el comportamiento antes de introducir lógica vendor-specific.

---

# 7. Patient Context

Reutilizar:

```java
PatientContext {
    destination,
    patientId,
    source
}
```

Fuente actual:

```text
CONFIGURED
```

Si no existe contexto:

```text
PATIENT_CONTEXT_NOT_CONFIGURED
```

y debe haber:

```text
CERO HTTP Observation
```

No implementar todavía:

```text
SMART_LAUNCH
APPLICATION_SELECTED
```

---

# 8. Capability Discovery

Antes del HTTP:

```java
capabilities.supports("Observation", SEARCH_TYPE)
```

Si no está declarado:

```text
CAPABILITY_UNSUPPORTED
```

y no se realiza la llamada FHIR.

Principio:

```text
Capability runtime
      ≠
OAuth scope
      ≠
Successful operation
```

---

# 9. Arquitectura

```text
vendor.oracle
      ↓
OracleSandboxObservationSearchService
      ↓
PatientContext
      ↓
Capability validation
      ↓
RoutingService.searchObservations(...)
      ↓
FhirService
      ↓
HAPI FHIR
      ↓
Oracle Health Millennium
```

## Reglas obligatorias

- No crear `OracleObservationClient`.
- No crear un cliente clínico específico de Oracle.
- `FhirService` permanece vendor-neutral.
- `FhirService` no importa `vendor.oracle`.
- `FhirService` no importa SMART.
- Oracle solamente orquesta.
- La operación FHIR pertenece a la arquitectura genérica.

```text
vendor.oracle → routing → FhirService → HAPI
```

Nunca:

```text
FhirService → vendor.oracle
```

---

# 10. Resultado diagnóstico seguro

El endpoint no debe devolver datos clínicos.

Puede devolver:

- `outcome`
- `destination`
- `resourceType`
- `responseType`
- `httpStatus`
- `contextSource`
- `hasPatientContext`
- `hasEntries`
- `detail` sanitizado

## No devolver

- Access token.
- Patient JSON.
- Observation JSON.
- Valores de laboratorio.
- Signos vitales.
- Nombres.
- Diagnósticos.
- Códigos clínicos.
- Fechas clínicas.
- Identificadores clínicos.

`hasEntries=true` solamente indica que Oracle devolvió un Bundle no vacío.

---

# 11. Outcomes

| Outcome | Cuándo |
|---|---|
| `OBSERVATION_SEARCH_SUCCEEDED` | Oracle devuelve HTTP 200 y Bundle |
| `PATIENT_CONTEXT_NOT_CONFIGURED` | No existe contexto; cero HTTP clínico |
| `AUTHENTICATION_REQUIRED` | No existe token usable |
| `AUTHENTICATION_REJECTED` | Oracle responde HTTP 401 |
| `AUTHORIZATION_DENIED` | Oracle responde HTTP 403 |
| `CAPABILITY_UNSUPPORTED` | Observation SEARCH_TYPE no está declarado |
| `DEPENDENCY_FAILURE` | Timeout, conexión o fallo de dependencia |

---

# 12. Timeout y rendimiento

Task 037 demostró:

```text
FHIR operation válida
        ≠
FHIR operation rápida
```

Condition search tardó aproximadamente:

```text
32–35 segundos
```

El timeout anterior de 30 segundos podía clasificar un resultado tardío como:

```text
DEPENDENCY_FAILURE
```

Task 038 debe reutilizar la política genérica ya corregida.

## No implementar

```text
if Oracle then timeout = ...
```

El timeout debe seguir siendo una política de transporte genérica y configurable.

---

# 13. Endpoint de laboratorio

Agregar:

```text
GET /oracle/sandbox/fhir/observation-search
```

El endpoint:

- no recibe un Patient ID arbitrario;
- usa `PatientContext`;
- no devuelve Bundle;
- no imprime información clínica;
- devuelve únicamente diagnóstico seguro.

---

# 14. Flujo de validación

## Paso 1 — Configuración

`.env` local:

```env
ORACLE_HEALTH_SANDBOX_ENABLED=true
ORACLE_HEALTH_SANDBOX_PATIENT_ID=<local-only>
```

Nunca commitear el Patient ID real.

## Paso 2 — Reiniciar

```bash
mvn spring-boot:run
```

## Paso 3 — SMART

Abrir:

```text
http://localhost:8081/oracle/sandbox/smart/start
```

Completar login Oracle y verificar:

```text
hasAccessToken=true
```

## Paso 4 — Observation search

Abrir:

```text
http://localhost:8081/oracle/sandbox/fhir/observation-search
```

---

# 15. Resultado esperado

```text
outcome=OBSERVATION_SEARCH_SUCCEEDED
destination=oracle-health-sandbox
resourceType=Observation
responseType=Bundle
httpStatus=200
contextSource=CONFIGURED
hasPatientContext=true
hasEntries=true|false
detail=Authenticated Observation search succeeded
```

Un Bundle vacío sigue demostrando:

```text
Authentication
      +
Authorization
      +
FHIR operation
```

---

# 16. Testing

## Unit tests

- Observation search exitoso.
- Patient context ausente → cero HTTP.
- Token ausente → `AUTHENTICATION_REQUIRED`.
- Capability ausente → `CAPABILITY_UNSUPPORTED`.
- HTTP 401 → `AUTHENTICATION_REJECTED`.
- HTTP 403 → `AUTHORIZATION_DENIED`.
- Timeout → `DEPENDENCY_FAILURE`.
- Fallos de dependencia según taxonomía existente.

## Architecture tests

- `FhirService` no importa Oracle.
- `FhirService` no importa SMART.
- No hay hosts hardcodeados en `vendor.oracle`.
- Oracle adapter no usa `IGenericClient` directamente.

## Integration tests

```bash
mvn clean verify -Pintegration
```

Debe funcionar con Oracle disabled, sin red y sin tokens reales.

## LiveIT

```bash
mvn verify -Poracle-live
```

con:

```text
ORACLE_HEALTH_LIVE_IT=true
```

Maven no debe fabricar credenciales ni tokens interactivos.

---

# 17. Criterios de aceptación

- [ ] Reutiliza `PatientContext`.
- [ ] Reutiliza el token SMART real existente.
- [ ] No acepta Patient ID arbitrario.
- [ ] No enumera Observations globalmente.
- [ ] Valida `Observation SEARCH_TYPE`.
- [ ] Usa `RoutingService`.
- [ ] Usa `FhirService`.
- [ ] No crea Oracle-specific FHIR client.
- [ ] No expone Bundle clínico.
- [ ] No expone token.
- [ ] Respeta la política genérica de timeout.
- [ ] Tests estándar funcionan sin Oracle real.
- [ ] Live validation es opt-in.
- [ ] Se demuestra una operación clínica FHIR real contra Oracle.

---

# 18. Commit propuesto

```text
feat: add Oracle Health authenticated Observation search by Patient
```

---

# 19. Roadmap

```text
033  SMART Authentication
034  Real Capability Discovery
035  Authenticated Patient Search
036  Controlled Patient Read
037  Condition Search by Patient
038  Observation Search by Patient
039  DiagnosticReport Search by Patient
040  MedicationRequest Search by Patient
041  Controlled Clinical Snapshot
042  Clinical Data Normalization
043  AI / LLM Clinical Summary
```

---

# Principio arquitectónico

```text
OAuth identity
      ≠
Patient context
      ≠
Resource capability
      ≠
Clinical authorization
      ≠
Clinical data availability
      ≠
Clinical interpretation
```

Task 038 debe demostrar únicamente:

```text
Patient explícito
      +
Token SMART real
      +
Observation SEARCH_TYPE
      +
Autorización efectiva
      ↓
Observation Bundle autenticado
```

Sin convertir todavía los datos clínicos en un Clinical Snapshot ni enviarlos a un modelo de IA.
