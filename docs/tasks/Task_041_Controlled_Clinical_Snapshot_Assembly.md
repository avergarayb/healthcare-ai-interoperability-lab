# Task 041 — Controlled Clinical Snapshot Assembly

**Proyecto:** Healthcare AI Interoperability Lab  
**Servicio:** `fhir-integration-service`  
**Stack:** Java 21, Spring Boot 3.5.16, HAPI FHIR 8.10.0  
**Objetivo del repo:** interoperabilidad clínica + frontera segura hacia una futura capa de IA

---

# 1. Objetivo

Construir la primera capa de **agregación clínica controlada** sobre las operaciones FHIR ya demostradas en vivo contra Oracle Health Millennium.

Task 041 **no** agrega nuevos recursos clínicos.

Task 041 **no** introduce normalización clínica rica.

Task 041 **no** introduce IA.

Su responsabilidad es únicamente:

```text
Patient context explícito
        ↓
Token SMART usable
        ↓
Orquestación secuencial de recursos ya soportados
        ↓
Estado + conteos
        ↓
Controlled Clinical Snapshot
```

El snapshot debe ensamblar:

```text
Patient READ                1 recurso

Condition search            _count=5
Observation search          _count=5
DiagnosticReport search     _count=5
MedicationRequest search    _count=5
```

---

# 2. Contexto previo

Las siguientes tasks ya demostraron interoperabilidad real con Oracle Health:

| Task | Operación | Resultado en vivo |
|---|---|---|
| 033 | SMART Authorization Code + PKCE S256 | Access token real |
| 034 | `GET /metadata` | HTTP 200 |
| 035 | Patient search autenticado | HTTP 200 Bundle |
| 036 | `GET /Patient/{id}` | HTTP 200 Patient |
| 037 | `GET /Condition?patient=...` | HTTP 200 Bundle |
| 038 | `GET /Observation?patient=...` | HTTP 200 Bundle |
| 039 | `GET /DiagnosticReport?patient=...` | HTTP 200 Bundle |
| 040 | `GET /MedicationRequest?patient=...` | HTTP 200 Bundle |

Task 041 no debe duplicar estas operaciones ni crear clientes Oracle alternativos.

---

# 3. WHAT

Agregar una operación de snapshot controlado:

```text
GET /oracle/sandbox/fhir/clinical-snapshot
```

que ejecute secuencialmente:

```text
Patient
   ↓
Condition
   ↓
Observation
   ↓
DiagnosticReport
   ↓
MedicationRequest
```

y produzca únicamente:

- outcome global;
- status por recurso;
- count por colección;
- destination;
- Patient context source;
- `generatedAt` opcional.

No debe producir todavía un modelo clínico detallado.

---

# 4. WHY

Hasta Task 040, cada recurso se valida de forma independiente.

Eso demuestra interoperabilidad por recurso, pero todavía no existe una operación que represente:

```text
Un Patient explícito
        +
múltiples recursos clínicos
        +
una sola ejecución controlada
```

Task 041 debe resolver exactamente eso.

No debe resolver:

- interpretación clínica;
- timeline;
- AI prompt;
- RAG;
- agentes;
- recomendaciones;
- normalización clínica detallada.

---

# 5. HOW

Arquitectura objetivo:

```text
vendor.oracle
        ↓
OracleSandboxClinicalSnapshotService
        ↓
PatientContext
        ↓
IssuedAccessTokenProvider
        ↓
Capability validation
        ↓
RoutingService
        ↓
FhirService
        ↓
HAPI FHIR
        ↓
Oracle Health Millennium
```

La capa Oracle orquesta.

La capa genérica FHIR ejecuta las operaciones.

Nunca:

```text
FhirService → vendor.oracle
```

---

# 6. CONCEPT

La separación conceptual obligatoria es:

```text
FHIR Bundle
      ≠
Controlled Clinical Snapshot
      ≠
Clinical Normalization
      ≠
AI Context
      ≠
LLM Prompt
```

Task 041 termina en:

```text
Snapshot orchestration + status + counts
```

Nada más.

---

# 7. Recursos incluidos

## Patient

```text
GET /Patient/{id}
```

Máximo:

```text
1
```

## Condition

Usar exactamente la operación ya validada:

```text
GET /Condition?patient={id}&category=problem-list-item&_count=5
```

## Observation

```text
GET /Observation?patient={id}&_count=5
```

## DiagnosticReport

```text
GET /DiagnosticReport?patient={id}&_count=5
```

## MedicationRequest

```text
GET /MedicationRequest?patient={id}&_count=5
```

No agregar recursos nuevos en esta task.

---

# 8. Snapshot mínimo

Task 041 debe ser deliberadamente flaca.

No crear:

```text
SnapshotCondition
SnapshotObservation
SnapshotDiagnosticReport
SnapshotMedicationRequest
```

con:

- códigos;
- displays;
- fechas;
- valores;
- unidades;
- diagnósticos;
- medicamentos;
- dosis;
- texto clínico.

La minimización de campos clínicos pertenece a Task 042.

El snapshot puede ser conceptualmente:

```java
ClinicalSnapshotResult {
    outcome,
    destination,
    contextSource,
    generatedAt,

    patientStatus,

    conditionStatus,
    conditionCount,

    observationStatus,
    observationCount,

    diagnosticReportStatus,
    diagnosticReportCount,

    medicationRequestStatus,
    medicationRequestCount
}
```

El nombre final puede adaptarse a la arquitectura existente.

---

# 9. Status por recurso

Usar únicamente:

```text
SUCCESS
UNAVAILABLE
UNAUTHORIZED
FAILED
```

## SUCCESS

HTTP 200.

Un Bundle vacío:

```text
count=0
```

sigue siendo:

```text
SUCCESS
```

No crear un status separado `EMPTY`.

## UNAVAILABLE

La capability requerida no está declarada.

Debe ocurrir antes del HTTP clínico.

## UNAUTHORIZED

HTTP 403.

## FAILED

Ejemplos:

- timeout;
- HTTP 401;
- HTTP 5xx;
- error de red;
- fallo de transporte.

No mezclar failure de una colección con el outcome global completo.

---

# 10. Outcomes globales

## SNAPSHOT_COMPLETE

Cuando:

```text
Patient = SUCCESS
Condition = SUCCESS
Observation = SUCCESS
DiagnosticReport = SUCCESS
MedicationRequest = SUCCESS
```

Los Bundles vacíos siguen contando como SUCCESS.

## SNAPSHOT_PARTIAL

Cuando:

```text
Patient = SUCCESS
```

pero al menos una colección está en:

```text
UNAVAILABLE
UNAUTHORIZED
FAILED
```

## SNAPSHOT_UNAVAILABLE

Únicamente cuando falla el Patient read.

Sin Patient no existe sujeto clínico válido para el snapshot.

## PATIENT_CONTEXT_NOT_CONFIGURED

No existe Patient ID explícito.

Debe producir:

```text
CERO HTTP clínico
```

## AUTHENTICATION_REQUIRED

No existe token SMART usable.

Debe producir:

```text
CERO HTTP clínico
```

No inventar un outcome ambiguo como:

```text
NO_USEFUL_INFORMATION
```

---

# 11. Patient Context

Reutilizar exactamente el modelo de Task 036.

```text
PatientContext
```

Fuente actual:

```text
CONFIGURED
```

El Patient ID sale únicamente de:

```text
ORACLE_HEALTH_SANDBOX_PATIENT_ID
```

No:

- enumerar Patients;
- adivinar IDs;
- usar `fhirUser`;
- usar fallback search;
- extraer Patient de SMART launch.

EHR launch sigue fuera de alcance.

---

# 12. Capability validation

Antes de cada HTTP:

```text
Patient             → READ
Condition           → SEARCH_TYPE
Observation         → SEARCH_TYPE
DiagnosticReport    → SEARCH_TYPE
MedicationRequest   → SEARCH_TYPE
```

Si una capability no existe:

```text
resource status = UNAVAILABLE
```

y no debe ejecutarse el HTTP correspondiente.

La ausencia de capability de una colección no cancela las demás.

---

# 13. Token

Reutilizar:

```text
IssuedAccessTokenProvider
```

de la sesión SMART actual.

No crear:

```text
SnapshotTokenProvider
SnapshotOAuthClient
OracleSnapshotAuthClient
```

Si no hay token usable:

```text
AUTHENTICATION_REQUIRED
```

y:

```text
CERO HTTP clínico
```

---

# 14. Estrategia de ejecución

Task 041 v1 debe ser:

```text
SECUENCIAL
```

Orden:

```text
Patient
   ↓
Condition
   ↓
Observation
   ↓
DiagnosticReport
   ↓
MedicationRequest
```

## WHY

La primera versión debe priorizar:

- trazabilidad;
- debugging simple;
- comportamiento determinista;
- bajo riesgo de saturar Oracle;
- reutilización directa del pipeline existente.

No implementar todavía:

- paralelización;
- reactive orchestration;
- fan-out concurrente;
- background jobs.

---

# 15. Timeout

Reutilizar el timeout genérico existente:

```text
60 s por recurso
```

No agregar:

```text
if Oracle
```

No introducir un timeout global corto.

Una ejecución secuencial completa puede tardar varios minutos.

Esto debe documentarse.

No debe "arreglarse" bajando el timeout de transporte.

---

# 16. Fallos parciales

Cada recurso debe fallar de forma aislada.

Ejemplo:

```text
Patient             SUCCESS
Condition           SUCCESS
Observation         FAILED (TIMEOUT)
DiagnosticReport    SUCCESS
MedicationRequest   UNAUTHORIZED
```

Resultado:

```text
SNAPSHOT_PARTIAL
```

No cancelar ni borrar recursos exitosos por el fallo de otro recurso.

---

# 17. Endpoint de laboratorio

Agregar:

```text
GET /oracle/sandbox/fhir/clinical-snapshot
```

Respuesta segura conceptual:

```text
outcome=SNAPSHOT_COMPLETE
destination=oracle-health-sandbox
contextSource=CONFIGURED

patient=SUCCESS

conditions=SUCCESS
conditionCount=3

observations=SUCCESS
observationCount=5

diagnosticReports=SUCCESS
diagnosticReportCount=2

medicationRequests=SUCCESS
medicationRequestCount=4
```

No incluir Patient ID.

---

# 18. Prohibición de exposición clínica

El endpoint NO debe mostrar:

- Patient name;
- birth date;
- identifiers;
- diagnoses;
- Condition codes;
- Observation values;
- laboratory values;
- vital signs;
- DiagnosticReport text;
- MedicationRequest medication names;
- dosage;
- prescriber;
- raw FHIR JSON;
- raw Bundles.

Solamente:

```text
status + counts + operational metadata
```

---

# 19. Persistencia

Task 041 no persiste el snapshot.

No agregar:

- database;
- Redis;
- cache;
- snapshot history;
- files;
- serialized JSON snapshot.

El snapshot vive únicamente en memoria durante la operación.

---

# 20. Arquitectura obligatoria

Preservar:

```text
vendor.oracle
      ↓
snapshot orchestrator
      ↓
RoutingService
      ↓
FhirService
      ↓
HAPI FHIR
```

Prohibido:

```text
OraclePatientClient
OracleConditionClient
OracleObservationClient
OracleDiagnosticReportClient
OracleMedicationRequestClient
```

También prohibido:

```text
FhirService.searchEverything()
```

No meter orquestación de snapshot en `FhirService`.

---

# 21. Seguridad

Nunca exponer:

```text
Access Token
Authorization header
Authorization Code
PKCE verifier
Patient ID
Raw FHIR resource
```

No poner información clínica en:

- logs;
- exceptions;
- HTML diagnostics;
- `toString()`;
- audit payloads.

---

# 22. Tests

## Complete snapshot

```text
Patient             SUCCESS
Condition           SUCCESS
Observation         SUCCESS
DiagnosticReport    SUCCESS
MedicationRequest   SUCCESS

→ SNAPSHOT_COMPLETE
```

## Partial — timeout

```text
Observation = FAILED
others = SUCCESS

→ SNAPSHOT_PARTIAL
```

## Partial — unauthorized

```text
MedicationRequest = UNAUTHORIZED
others = SUCCESS

→ SNAPSHOT_PARTIAL
```

## Partial — capability unsupported

```text
DiagnosticReport = UNAVAILABLE
```

Verificar:

```text
no HTTP DiagnosticReport
```

Resultado:

```text
SNAPSHOT_PARTIAL
```

## Patient failure

Si Patient read falla:

```text
SNAPSHOT_UNAVAILABLE
```

No continuar a las colecciones.

## Missing Patient context

```text
PATIENT_CONTEXT_NOT_CONFIGURED
```

Verificar:

```text
zero clinical HTTP
```

## Missing token

```text
AUTHENTICATION_REQUIRED
```

Verificar:

```text
zero clinical HTTP
```

## Empty collections

Bundle HTTP 200 sin entries:

```text
SUCCESS
count=0
```

No usar status `EMPTY`.

---

# 23. Boundary tests

Mantener o añadir pruebas que garanticen:

```text
FhirService no importa vendor.oracle
```

```text
FhirService no importa SMART
```

```text
vendor.oracle no contiene hosts hardcodeados
```

```text
snapshot orchestrator no usa IGenericClient directamente
```

```text
no raw Bundle / Patient serialization en diagnostics
```

```text
no Patient ID en output seguro
```

---

# 24. Integration tests

Deben seguir pasando sin Oracle real:

```bash
mvn clean test
```

```bash
mvn clean verify -Pintegration
```

Oracle disabled debe producir cero llamadas externas.

---

# 25. Live validation

Live sigue siendo opt-in e interactiva.

Flujo:

```text
1. Configurar .env local

2. mvn spring-boot:run

3. GET /oracle/sandbox/smart/start

4. Login Oracle

5. Confirmar token emitido

6. GET /oracle/sandbox/fhir/clinical-snapshot

7. Revisar únicamente status y counts
```

Un resultado válido puede ser:

```text
SNAPSHOT_COMPLETE
```

o:

```text
SNAPSHOT_PARTIAL
```

dependiendo de las respuestas reales de Oracle.

---

# 26. Fuera de alcance

Task 041 NO implementa:

## Normalización clínica rica

No crear todavía modelos con:

- SNOMED;
- LOINC;
- displays;
- coding systems;
- clinical dates;
- medication dosage;
- interpretation flags.

Eso es Task 042.

## IA

No usar:

- OpenAI;
- Gemini;
- LLM;
- prompts;
- agents;
- RAG;
- embeddings;
- ML.

## Timeline

No construir timeline clínico.

## Interpretación

No producir:

- diagnosis;
- risk score;
- recommendations;
- summaries;
- insights.

## Infra avanzada

No agregar:

- parallel fetching;
- reactive execution;
- cache;
- persistence;
- background orchestration.

---

# 27. Acceptance criteria

Task 041 está completa cuando:

- [ ] Se construye un snapshot para un Patient explícito.
- [ ] Patient se lee exactamente una vez.
- [ ] Condition está limitado a `_count=5`.
- [ ] Observation está limitado a `_count=5`.
- [ ] DiagnosticReport está limitado a `_count=5`.
- [ ] MedicationRequest está limitado a `_count=5`.
- [ ] Cada recurso valida capability antes del HTTP.
- [ ] La ejecución v1 es secuencial.
- [ ] Los fallos de colecciones son aislados.
- [ ] Existe `SNAPSHOT_COMPLETE`.
- [ ] Existe `SNAPSHOT_PARTIAL`.
- [ ] `SNAPSHOT_UNAVAILABLE` ocurre únicamente cuando falla Patient.
- [ ] Missing context produce cero HTTP clínico.
- [ ] Missing token produce cero HTTP clínico.
- [ ] Bundle vacío = SUCCESS count=0.
- [ ] No existe status `EMPTY`.
- [ ] El snapshot contiene únicamente status/counts/metadata operacional.
- [ ] No se exponen datos clínicos.
- [ ] No se expone Patient ID.
- [ ] No se persiste el snapshot.
- [ ] No hay IA.
- [ ] No hay clientes Oracle específicos por recurso.
- [ ] `FhirService` permanece vendor-neutral.
- [ ] Unit tests pasan.
- [ ] Integration tests pasan.
- [ ] Live validation permanece opt-in.

---

# 28. Proposed branch

```text
feature/oracle-health-controlled-clinical-snapshot
```

# 29. Proposed commit

```text
feat: add controlled Oracle Health clinical snapshot
```

---

# 30. Siguiente frontera

Task 041:

```text
ensamblaje + status + counts
```

Task 042 debe definir:

```text
proyección clínica mínima
```

Es decir:

- qué campos pueden salir de los recursos FHIR;
- qué campos nunca deben salir;
- allowlist por recurso;
- minimización;
- modelo independiente de Oracle/HAPI.

Después podrá diseñarse una frontera explícita hacia un futuro `ai-service`.

No implementar esa frontera dentro de Task 041.
