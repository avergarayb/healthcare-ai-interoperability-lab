# Task 037 — Oracle Health Authenticated Condition Search by Patient

**Proyecto:** Healthcare AI Interoperability Lab  
**Stack:** Java 21, Spring Boot 3.5.16, HAPI FHIR 8.10.0  
**Servicio:** `fhir-integration-service`  
**Puerto:** `8081`

---

## 1. Objetivo

Implementar el primer acceso a un **recurso clínico relacionado con un Patient** mediante una búsqueda FHIR autenticada contra Oracle Health Millennium.

La operación objetivo será una búsqueda acotada de `Condition` asociada explícitamente al `PatientContext` configurado.

```text
Patient Context
      ↓
Capability check
      ↓
GET /Condition?patient={patientId}
      + Bearer
      ↓
FHIR Bundle
      ↓
Safe diagnostic result
```

---

# 2. WHAT / WHY / HOW / CONCEPT

## WHAT

Agregar una operación autenticada para consultar recursos `Condition` asociados a un Patient ID explícitamente configurado.

Esta task **no** construye todavía un resumen clínico ni procesa información mediante IA/LLM.

## WHY

Task 036 ya demostró:

```text
GET /Patient/{id} + Bearer → HTTP 200 Patient
```

Eso demuestra que:

- existe un Patient context explícito;
- el token SMART es válido;
- Oracle acepta una operación FHIR autenticada;
- el Patient configurado puede ser recuperado.

El siguiente paso lógico es demostrar acceso a **información clínica relacionada con ese Patient**.

`Condition` es un buen primer recurso porque permite validar la cadena:

```text
Patient context
      ↓
SMART authorization
      ↓
FHIR capability
      ↓
Clinical resource authorization
      ↓
Condition search
```

## HOW

```text
ORACLE_HEALTH_SANDBOX_PATIENT_ID
              ↓
       PatientContext
              ↓
Capability: Condition SEARCH_TYPE
              ↓
IssuedAccessTokenProvider
              ↓
RoutingService.searchConditions(...)
              ↓
FhirService
              ↓
GET /Condition?patient={id}
              ↓
FhirAuthenticatedClinicalSearchResult
```

## CONCEPT

```text
Patient context ≠ Clinical resource access
```

Tener un Patient ID válido **no garantiza** que el token pueda consultar `Condition`.

La operación depende simultáneamente de:

- Patient context explícito.
- Token SMART usable.
- Capability runtime declarada por Oracle.
- Scope/autorización efectiva del access token.
- Restricciones propias del servidor Oracle.

---

# 3. Alcance

## Incluido

- Búsqueda autenticada de `Condition` por Patient.
- Reutilización del `PatientContext` de Task 036.
- Validación previa de Patient context.
- Validación de token usable.
- Validación runtime de capability `Condition search-type`.
- Uso del `AccessTokenProvider` existente.
- Resultado diagnóstico seguro.
- Endpoint HTTP de laboratorio.
- Tests unitarios.
- Tests de integración.
- LiveIT opt-in.

## Fuera de alcance

- Crear `Condition`.
- Actualizar `Condition`.
- Eliminar `Condition`.
- Enumerar Conditions sin Patient context.
- Buscar pacientes para descubrir IDs.
- Mostrar JSON clínico.
- Clinical Snapshot.
- IA / LLM.
- `Observation`.
- `DiagnosticReport`.
- `MedicationRequest`.
- EHR launch.
- `client_secret_basic`.
- `private_key_jwt`.
- Persistencia de access tokens.

---

# 4. Operación FHIR

La operación objetivo debe ser conceptualmente:

```text
GET /Condition?patient={patientId}&_count={safeLimit}
```

El `patientId` debe provenir exclusivamente del `PatientContext` configurado.

## No implementar

```text
GET /Condition

GET /Condition?_count=...

GET /Patient ... para descubrir IDs
```

Tampoco debe existir:

- fallback search si no existe Patient context;
- enumeración clínica;
- adivinación de Patient IDs.

---

# 5. Patient Context

Se reutiliza el modelo introducido en Task 036:

```java
PatientContext {
    destination,
    patientId,
    source
}
```

Para Task 037, la fuente continúa siendo:

```text
CONFIGURED
```

No implementar todavía:

```text
SMART_LAUNCH
APPLICATION_SELECTED
```

Si:

```text
ORACLE_HEALTH_SANDBOX_PATIENT_ID=
```

está vacío, la operación debe terminar en:

```text
PATIENT_CONTEXT_NOT_CONFIGURED
```

y debe haber:

```text
CERO HTTP clínico
```

---

# 6. Capability Discovery

Task 034 ya demostró que Oracle Health declara una superficie real y limitada de FHIR R4.

Antes de realizar el HTTP contra `Condition`, verificar:

```java
capabilities.supports("Condition", SEARCH_TYPE)
```

No asumir:

```text
Permiso del portal
      ≠
Capability declarada por runtime
      ≠
Scope efectivo del token
```

Si Oracle no declara la interacción requerida:

```text
CAPABILITY_UNSUPPORTED
```

y no debe realizarse la búsqueda.

---

# 7. Arquitectura

```text
vendor.oracle
      ↓
OracleSandboxConditionSearchService
      ↓
PatientContext
      ↓
Capability validation
      ↓
RoutingService.searchConditions(...)
      ↓
FhirService
      ↓
HAPI FHIR
      ↓
Oracle Health Millennium
```

## Reglas arquitectónicas

- `FhirService` no importa `vendor.oracle`.
- `FhirService` no importa SMART.
- `FhirService` no conoce Oracle.
- No crear `OracleConditionClient`.
- No crear `OracleClinicalClient`.
- Oracle orquesta.
- La capa genérica ejecuta FHIR.
- Java en `vendor.oracle` no hardcodea hosts Oracle/Cerner.

Principio:

```text
vendor.oracle → routing → FhirService → HAPI
```

Nunca:

```text
FhirService → vendor.oracle
```

---

# 8. Resultado diagnóstico

La operación no debe devolver información clínica.

El resultado puede incluir metadata operacional segura:

- `destination`
- `resourceType`
- `responseType`
- `httpStatus`
- `hasEntries`
- `outcome`
- `detail` sanitizado

## No incluir

- Access token.
- Patient JSON.
- Condition JSON.
- Diagnósticos.
- Códigos clínicos.
- Nombres.
- Demografía.
- Identificadores clínicos.

---

# 9. Outcomes

| Outcome | Cuándo |
|---|---|
| `CONDITION_SEARCH_SUCCEEDED` | Oracle devolvió HTTP 200 y un Bundle |
| `PATIENT_CONTEXT_NOT_CONFIGURED` | No existe Patient context válido; cero HTTP clínico |
| `AUTHENTICATION_REQUIRED` | No existe access token usable |
| `AUTHENTICATION_REJECTED` | Oracle responde HTTP 401 |
| `AUTHORIZATION_DENIED` | Oracle responde HTTP 403 |
| `CAPABILITY_UNSUPPORTED` | `Condition search-type` no está declarado |
| `DEPENDENCY_FAILURE` | Timeout, conexión o fallo de dependencia según la taxonomía existente |

---

# 10. Endpoint de laboratorio

```text
GET /oracle/sandbox/fhir/condition-search
```

El endpoint debe:

- No aceptar un Patient ID arbitrario por query parameter.
- Usar exclusivamente el `PatientContext` configurado.
- No devolver Bundle clínico.
- Devolver únicamente el diagnóstico seguro.

---

# 11. Flujo de validación en vivo

## 1. Configurar `.env`

```env
ORACLE_HEALTH_SANDBOX_ENABLED=true

ORACLE_HEALTH_SANDBOX_PATIENT_ID=<patient-id-local>
```

El Patient ID real:

- permanece solamente en `.env`;
- no se commitea;
- no se copia a Java;
- no aparece en documentación pública.

## 2. Reiniciar

```bash
mvn spring-boot:run
```

## 3. Iniciar SMART

Abrir:

```text
http://localhost:8081/oracle/sandbox/smart/start
```

## 4. Login Oracle

Completar el login manual.

Resultado esperado:

```text
/smart/callback

hasAccessToken=true
```

## 5. Ejecutar Condition search

Abrir:

```text
http://localhost:8081/oracle/sandbox/fhir/condition-search
```

## 6. Revisar únicamente

- outcome
- HTTP status
- responseType
- hasEntries
- detail sanitizado

---

# 12. Resultado esperado

El resultado ideal será:

```text
outcome=CONDITION_SEARCH_SUCCEEDED
destination=oracle-health-sandbox
resourceType=Condition
responseType=Bundle
httpStatus=200
hasEntries=true|false
detail=Authenticated Condition search succeeded
```

Un Bundle vacío:

```text
hasEntries=false
```

sigue siendo una operación:

```text
autenticada
+
autorizada
+
FHIR técnicamente válida
```

---

# 13. Seguridad y privacidad

- `.env` nunca se commitea.
- Patient ID real permanece local.
- Access token nunca se imprime.
- Condition Bundle no se imprime.
- No logs con datos clínicos.
- No screenshots con información clínica real.
- LiveIT permanece opt-in.

---

# 14. Testing

Validar como mínimo:

## Unit tests

- Condition search exitoso.
- Patient context ausente → cero HTTP.
- Token ausente → `AUTHENTICATION_REQUIRED`.
- Capability ausente → `CAPABILITY_UNSUPPORTED`.
- HTTP 401 → `AUTHENTICATION_REJECTED`.
- HTTP 403 → `AUTHORIZATION_DENIED`.
- Timeout/5xx → `DEPENDENCY_FAILURE`.

## Architecture tests

- `FhirService` no importa `vendor.oracle`.
- `FhirService` no importa capability/SMART.
- `vendor.oracle` no contiene hosts hardcodeados.
- Oracle adapter no usa `IGenericClient` directamente.

## Integration

La integración estándar debe funcionar con Oracle disabled y sin red real.

## LiveIT

Debe ser explícitamente opt-in.

---

# 15. Comandos de validación

```bash
mvn clean test
```

```bash
mvn clean verify -Pintegration
```

Live validation:

```bash
mvn verify -Poracle-live
```

con:

```text
ORACLE_HEALTH_LIVE_IT=true
```

---

# 16. Criterios de aceptación

- [ ] Reutiliza `PatientContext` de Task 036.
- [ ] No enumera Conditions sin Patient.
- [ ] No adivina Patient IDs.
- [ ] Valida `Condition SEARCH_TYPE` antes del HTTP.
- [ ] Usa el token real emitido por SMART.
- [ ] `FhirService` permanece vendor-neutral.
- [ ] No se crea un Oracle-specific FHIR client.
- [ ] No se exponen datos clínicos.
- [ ] `.env` no se commitea.
- [ ] Tests estándar pasan sin Oracle real.
- [ ] Live validation es explícitamente opt-in.
- [ ] Se puede demostrar una operación real sobre un recurso clínico relacionado con el Patient.

---

# 17. Commit propuesto

```text
feat: add Oracle Health authenticated Condition search by Patient
```

---

# 18. Roadmap posterior

```text
033  SMART Authentication
034  Real Capability Discovery
035  Authenticated Patient Search
036  Controlled Patient Read
037  Condition Search by Patient
038  Observation Search by Patient
039  DiagnosticReport Search by Patient
040  MedicationRequest Search by Patient
041  Clinical Snapshot
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
Clinical resource authorization
      ≠
Clinical data availability
```

La Task 037 debe demostrar únicamente la siguiente frontera:

```text
Tenemos un Patient explícito
          +
Tenemos un token SMART real
          +
Oracle declara la capability
          ↓
Podemos ejecutar una operación clínica FHIR autenticada
```
