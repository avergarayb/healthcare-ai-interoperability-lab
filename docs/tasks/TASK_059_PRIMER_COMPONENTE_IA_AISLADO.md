# Task 059 — Primer componente de IA aislado basado en `AiBoundaryResult`

## Identificación

- **Proyecto:** `healthcare-ai-interoperability-lab`
- **Servicio actual:** `fhir-integration-service`
- **Stack actual:** Java 21, Spring Boot 3.5.16, HAPI FHIR 8.10.0
- **Paquete actual:** `lab.healthcare.fhir`
- **Puerto actual:** `8081`
- **Rama base:** `feature/ai-boundary-preparation`
- **Commit base:** `a9a082e`
- **Mensaje del commit base:** `feat: prepare ai boundary after deterministic agent`
- **Rama sugerida:** `feature/first-ai-component`
- **Commit sugerido:** `feat: add isolated first ai component`

---

# WHAT

Implementar el primer componente de IA aislado que consuma exclusivamente `AiBoundaryResult`.

Esta tarea representa la primera aproximación arquitectónica a un futuro componente de Inteligencia Artificial, pero **no debe implementar todavía un LLM, RAG, LangGraph, memoria conversacional ni llamadas a proveedores de IA**.

El componente debe:

1. Estar aislado de la interoperabilidad FHIR.
2. Consumir únicamente `AiBoundaryResult`.
3. No acceder a Epic, Oracle Health, FHIR, HAPI ni proveedores externos.
4. No recibir Bundles FHIR ni DTOs de proveedores.
5. Respetar siempre `modelCallAuthorized=false`.
6. No generar diagnóstico, prescripción ni recomendaciones clínicas.
7. Emitir una salida segura y explícita que indique que el procesamiento de IA real todavía no fue ejecutado.

---

# WHY

Las tareas anteriores establecieron las siguientes capas:

```text
Epic / Oracle Health
        ↓
FHIR / HAPI / Snapshot
        ↓
Controlled Projection
        ↓
Model Boundary Contract v1
        ↓
PipelineDiagnosis
        ↓
DeterministicAgentResult
        ↓
AiBoundaryResult
```

La Tarea 059 debe agregar una nueva frontera:

```text
AiBoundaryResult
        ↓
First AI Component
        ↓
AiComponentResult
```

La finalidad es demostrar que un componente separado puede consumir el contrato de frontera sin conocer:

- El proveedor clínico.
- El proceso de autenticación.
- El cliente FHIR.
- La estructura del Bundle.
- La implementación del pipeline.
- La lógica del agente determinístico.
- Los detalles de Epic u Oracle Health.

El componente será una preparación arquitectónica para una futura implementación de IA real en tareas posteriores.

---

# HOW

## 1. Inspección inicial obligatoria

Antes de modificar código, inspeccionar:

1. La implementación real de `AiBoundaryResult`.
2. `AiBoundaryInput`.
3. `AiBoundaryDecision`.
4. `AiBoundaryMapper`.
5. `AiBoundaryService`.
6. Los endpoints existentes:
   - `GET /lab/ai-boundary`
   - `GET /api/ai-boundary/v1`
   - `GET /epic/sandbox/fhir/clinical-projection`
7. Los patrones actuales de:
   - DTOs.
   - Services.
   - Controllers.
   - Tests.
   - Manejo de errores.
   - Correlation ID.
   - Serialización JSON.
8. Las reglas de arquitectura y dependencias del proyecto.

No crear clases duplicadas si ya existe una abstracción equivalente.

---

## 2. Aislamiento arquitectónico

El primer componente debe estar fuera de `fhir-integration-service` desde el punto de vista de responsabilidades.

Preferencia de implementación:

### Opción preferida

Crear un paquete aislado dentro del proyecto únicamente si el repositorio todavía no tiene módulos separados:

```text
lab.healthcare.fhir.firstai
```

### Opción alternativa

Crear un módulo o servicio separado únicamente si la estructura actual del repositorio ya soporta modularización sin introducir complejidad innecesaria.

No crear todavía un servicio Python ni un proceso externo.

La implementación debe documentar cuál opción se eligió y por qué.

---

## 3. Dependencia permitida

El componente puede consumir:

```text
AiBoundaryResult
```

También puede consumir tipos estrictamente necesarios que formen parte del contrato público de `AiBoundaryResult`.

No debe importar ni depender directamente de:

```text
vendor.*
FhirService
RoutingService
HAPI FHIR
FHIR Resource
Bundle
Epic*Client
Oracle*Client
SMART
OAuth2
Snapshot
Controlled Projection
Model Boundary Contract
AgentStub
DeterministicAgent
Pipeline
```

La regla principal es:

> El primer componente de IA conoce el resultado de la frontera, no conoce cómo se obtuvo.

---

# CONCEPT

## 1. Primer componente de IA no significa LLM

En esta tarea, “primer componente de IA” significa una pieza aislada que representa el punto de entrada de una futura capacidad de IA.

Todavía no debe existir:

- Llamada a OpenAI.
- Llamada a Azure OpenAI.
- Llamada a Gemini.
- Llamada a Claude.
- SDK de IA.
- Prompt enviado a un modelo.
- Token de IA.
- Respuesta generada por un LLM.
- RAG.
- Embeddings.
- Vector database.
- LangChain.
- LangGraph.
- Memoria conversacional.
- Tool calling.

El componente puede producir una salida técnica como:

```text
AI_COMPONENT_PREPARED
```

o:

```text
AI_PROCESSING_NOT_EXECUTED
```

La salida debe dejar claro que todavía no existe procesamiento de modelo.

---

## 2. `READY` no autoriza IA

Debe mantenerse la distinción entre:

```text
agentDecision = READY
```

y:

```text
modelCallAuthorized = false
```

Incluso cuando `agentDecision=READY`, el componente debe devolver:

```text
modelCalled = false
modelCallAuthorized = false
requiresHumanReview = true
```

No se permite cambiar estos valores a `true`.

---

## 3. Componente de IA versus decisión clínica

El componente no debe:

- Diagnosticar.
- Prescribir.
- Recomendar medicamentos.
- Recomendar tratamientos.
- Priorizar pacientes clínicamente.
- Interpretar síntomas.
- Inferir enfermedades.
- Emitir recomendaciones médicas.
- Sustituir revisión humana.

Su responsabilidad se limita a verificar que recibió una entrada de frontera válida y devolver una salida técnica segura.

---

# DISEÑO SUGERIDO

Los nombres son sugeridos. Adaptarlos a los patrones reales del repositorio.

Paquete sugerido:

```text
lab.healthcare.fhir.firstai
```

Clases sugeridas:

```text
FirstAiComponent
FirstAiInput
FirstAiResult
FirstAiStatus
FirstAiService
FirstAiMapper
```

No crear todas las clases si una estructura más pequeña y coherente resulta suficiente.

---

## 1. `FirstAiInput`

Representa la entrada recibida desde `AiBoundaryResult`.

Debe contener únicamente:

- `AiBoundaryResult`.
- Los campos contractuales mínimos necesarios.
- Estado del pipeline.
- Disponibilidad de datos clínicos.
- Decisión del agente.
- Warnings.
- Códigos de razón.
- Estado de autorización del modelo.
- Identificador de correlación, si ya existe.

No debe contener:

- Bundle FHIR.
- Recursos FHIR crudos.
- DTOs de Epic.
- DTOs de Oracle Health.
- Tokens.
- Secretos.
- Headers de autenticación.
- URLs privadas.
- Objetos HAPI.
- Clientes HTTP.
- Datos no presentes en `AiBoundaryResult`.

---

## 2. `FirstAiResult`

Debe representar la salida del primer componente de IA.

Debe incluir, como mínimo:

- Estado del componente.
- Estado del pipeline recibido.
- Disponibilidad de datos clínicos.
- Decisión determinística recibida.
- `requiresHumanReview`.
- `modelCalled`.
- `modelCallAuthorized`.
- Códigos de razón.
- Warnings operacionales.
- Estado de procesamiento.
- Correlation ID, si corresponde.

Estados sugeridos:

```text
PREPARED
NOT_EXECUTED
BLOCKED
REQUIRES_HUMAN_REVIEW
```

La implementación debe evitar crear estados redundantes si el proyecto ya posee un enum o patrón equivalente.

Para una entrada válida con `agentDecision=READY`, la salida esperada debe ser conceptualmente:

```text
componentStatus = PREPARED
processingStatus = NOT_EXECUTED
agentDecision = READY
clinicalDataAvailable = true
requiresHumanReview = true
modelCalled = false
modelCallAuthorized = false
```

---

## 3. `FirstAiService`

Debe coordinar el procesamiento inicial de `AiBoundaryResult`.

Responsabilidades:

1. Validar que `AiBoundaryResult` exista.
2. Validar que los campos mínimos estén disponibles.
3. Conservar la decisión determinística.
4. Conservar los warnings.
5. Conservar los códigos de razón.
6. No consultar ningún proveedor externo.
7. No invocar FHIR ni HAPI.
8. No invocar un modelo.
9. No cambiar `modelCallAuthorized`.
10. No cambiar `requiresHumanReview`.
11. Emitir una salida técnica explícita.

El servicio no debe implementar reglas clínicas ni reglas duplicadas de la Tarea 057.

---

## 4. `FirstAiMapper`

Debe mapear `AiBoundaryResult` a `FirstAiResult`.

Responsabilidades:

- Copiar únicamente campos permitidos.
- Preservar la semántica de los campos.
- Preservar `MedicationRequest = NOT_REQUESTED`.
- Preservar warnings operacionales.
- Preservar códigos de razón.
- Preservar el estado del pipeline.
- Preservar `agentDecision`.
- Preservar `modelCallAuthorized=false`.
- Preservar `modelCalled=false`.
- Preservar `requiresHumanReview=true`.

No debe:

- Ejecutar `DeterministicAgent`.
- Ejecutar `AgentStub`.
- Revalidar todo el contrato desde cero.
- Consultar Epic.
- Consultar Oracle.
- Ejecutar llamadas FHIR.
- Construir un Bundle.
- Crear datos clínicos.
- Inventar resultados.

---

# REGLAS FUNCIONALES

## Regla 1 — Entrada válida y `READY`

Cuando `AiBoundaryResult` sea válido y contenga:

```text
agentDecision = READY
clinicalDataAvailable = true
modelCallAuthorized = false
```

El resultado debe:

```text
componentStatus = PREPARED
processingStatus = NOT_EXECUTED
modelCalled = false
modelCallAuthorized = false
requiresHumanReview = true
```

No debe generar contenido clínico.

---

## Regla 2 — Entrada `BLOCKED`

Cuando:

```text
agentDecision = BLOCKED
```

El componente debe:

- Mantener `BLOCKED`.
- No generar salida clínica.
- No convertir el resultado en `READY`.
- No llamar a un modelo.
- Mantener `modelCallAuthorized=false`.
- Mantener `requiresHumanReview=true`.
- Conservar los códigos de razón.

---

## Regla 3 — Entrada `REQUIRES_HUMAN_REVIEW`

Cuando:

```text
agentDecision = REQUIRES_HUMAN_REVIEW
```

El componente debe:

- Mantener la decisión.
- Marcar revisión humana.
- No generar diagnóstico.
- No generar recomendación clínica.
- No llamar a un modelo.
- Conservar warnings y razones.

---

## Regla 4 — `modelCallAuthorized=false`

Si la entrada contiene:

```text
modelCallAuthorized = false
```

El componente no debe ejecutar ningún procesamiento de modelo.

No se permite:

- Sobrescribir el valor.
- Interpretarlo como autorización implícita.
- Enviar datos a un proveedor.
- Generar un prompt externo.
- Crear una solicitud HTTP de IA.

---

## Regla 5 — Datos clínicos ausentes

Si:

```text
clinicalDataAvailable = false
```

El componente debe:

- Conservar la ausencia de datos.
- No inventar información.
- No inferir información clínica.
- Mantener revisión humana.
- No llamar a un modelo.
- Conservar warnings y códigos de razón.

---

## Regla 6 — Pipeline parcial

Si:

```text
pipelineStatus = PARTIAL
```

El componente debe:

- Conservar `PARTIAL`.
- Conservar warnings.
- No convertirlo en `SUCCESS`.
- No producir salida clínica.
- No llamar a un modelo.
- Mantener revisión humana.

---

## Regla 7 — Warnings operacionales

Conservar, como mínimo cuando estén presentes:

- Truncamiento.
- Recurso no solicitado.
- Datos no disponibles.
- Limitaciones del proveedor.
- `medicationRequestsStatus = NOT_REQUESTED`.

No convertir warnings en errores clínicos inventados.

---

## Regla 8 — MedicationRequest

Conservar la semántica existente:

```text
medicationRequestsStatus = NOT_REQUESTED
```

No implementar:

- `MedicationRequest`.
- Prescripción.
- Recomendaciones farmacológicas.
- Acciones de medicación.
- Integración adicional con Epic.
- Ampliación de la allowlist 042.

---

# SUPERFICIES CIEGAS

El primer componente debe ser ciego a las siguientes superficies:

```text
Epic
Oracle Health
FHIR
HAPI FHIR
SMART PKCE
OAuth2
Access tokens
Client IDs
Client secrets
Patient IDs
Bundles
Resources
Vendor DTOs
Snapshot
Controlled Projection
Routing
AgentStub
DeterministicAgent
Pipeline internals
```

Debe conocer únicamente:

```text
AiBoundaryResult
```

La implementación debe agregar pruebas o documentación que demuestren esta separación.

---

# ENDPOINT O SUPERFICIE DE PRUEBA

Inspeccionar primero las superficies existentes.

Si existe un endpoint adecuado para probar el flujo completo:

```text
AiBoundaryResult → FirstAiComponent → FirstAiResult
```

reutilizarlo.

No crear endpoints duplicados.

Si se necesita un endpoint de laboratorio, debe:

- Ser claramente de laboratorio.
- No representar una API de producción.
- No realizar llamadas externas.
- No aceptar FHIR crudo.
- No aceptar tokens.
- No aceptar DTOs de Epic u Oracle.
- Recibir o construir únicamente una entrada basada en `AiBoundaryResult`.
- Mantener la política de seguridad existente.
- Exponer únicamente datos contractuales no sensibles.

La documentación debe indicar:

- Qué endpoint se reutilizó.
- Qué endpoint se creó, si fue necesario.
- Por qué no se pudo reutilizar una superficie existente.

---

# CONTRATOS Y COMPATIBILIDAD

No modificar innecesariamente:

- `Model Boundary Contract v1`.
- `PipelineDiagnosis`.
- `DeterministicAgentResult`.
- `AiBoundaryResult`.
- Integración Epic.
- Integración Oracle.
- OAuth2.
- SMART PKCE.
- FHIR.
- HAPI.
- Allowlist 042.
- Campos de las tareas 053–058.
- `.env`.

Debe conservarse:

```text
status=SUCCESS
destination=epic-sandbox
clinicalSnapshot=SUCCEEDED
controlledProjection=SUCCEEDED
modelBoundaryContract=v1
modelBoundary=SUCCEEDED
agentStub=SUCCEEDED
hasClinicalData=true
pipelineStatus=SUCCESS
deterministicAgent=READY
agentReason=READY_FOR_BOUNDARY
requiresHumanReview=true
agentModelCalled=false
aiBoundary=PREPARED
clinicalDataAvailable=true
modelCallAuthorized=false
aiModelCalled=false
medicationRequestsStatus=NOT_REQUESTED
```

El componente puede agregar su propio estado técnico, pero no debe alterar los campos anteriores.

---

# SEGURIDAD

No registrar:

- Tokens.
- Client IDs.
- Client secrets.
- Authorization headers.
- Patient IDs.
- Bundles completos.
- FHIR JSON crudo.
- Payloads completos de proveedores.
- Datos clínicos completos.
- Información personal innecesaria.

Se puede registrar únicamente:

- Correlation ID.
- Estado del pipeline.
- Disponibilidad de datos clínicos.
- Decisión del agente.
- Estado del primer componente.
- Códigos de razón.
- Cantidad de warnings, si ya existe un patrón seguro.

---

# PRUEBAS OBLIGATORIAS

Agregar pruebas siguiendo el estilo existente.

## Caso A — `READY` con datos clínicos disponibles

Verificar:

```text
componentStatus = PREPARED
processingStatus = NOT_EXECUTED
agentDecision = READY
clinicalDataAvailable = true
requiresHumanReview = true
modelCalled = false
modelCallAuthorized = false
```

---

## Caso B — `BLOCKED`

Verificar:

- Se conserva `BLOCKED`.
- No se convierte en `READY`.
- No se genera salida clínica.
- `modelCalled=false`.
- `modelCallAuthorized=false`.
- `requiresHumanReview=true`.
- Se conservan los códigos de razón.

---

## Caso C — `REQUIRES_HUMAN_REVIEW`

Verificar:

- Se conserva la decisión.
- Se mantiene revisión humana.
- No se llama a un modelo.
- Se conservan warnings y razones.

---

## Caso D — Pipeline `PARTIAL`

Verificar:

- Se conserva `PARTIAL`.
- Se conservan warnings.
- No se genera salida clínica.
- No se autoriza modelo.

---

## Caso E — Datos clínicos ausentes

Verificar:

- No se inventan datos.
- Se conserva `clinicalDataAvailable=false`.
- Se mantiene revisión humana.
- No se llama a un modelo.

---

## Caso F — Warnings operacionales

Verificar la conservación de:

- Truncamiento.
- Recurso no solicitado.
- Datos no disponibles.
- `MedicationRequest=NOT_REQUESTED`.

---

## Caso G — No exposición de datos prohibidos

Verificar que la salida no contenga:

- Tokens.
- Secretos.
- Headers.
- Bundles.
- Recursos FHIR crudos.
- DTOs de proveedores.
- Patient IDs no autorizados.

---

## Caso H — No llamadas externas

Verificar que el componente no invoque:

- Epic.
- Oracle Health.
- FHIR.
- HAPI.
- OpenAI.
- Azure OpenAI.
- Gemini.
- Claude.
- Cualquier proveedor de LLM.
- Clientes HTTP externos.

---

## Caso I — Entrada nula o incompleta

Verificar que:

- Se aplique el patrón de error existente.
- No se genere una decisión clínica.
- No se autorice el modelo.
- No se expongan detalles sensibles.
- Se mantenga trazabilidad segura.

---

# DEFINITION OF DONE

La tarea está terminada cuando:

- [ ] Existe un primer componente de IA aislado.
- [ ] Consume únicamente `AiBoundaryResult`.
- [ ] No consume FHIR crudo.
- [ ] No consume Bundles.
- [ ] No consume DTOs de Epic u Oracle.
- [ ] No consume tokens ni secretos.
- [ ] No importa clientes de proveedores.
- [ ] No modifica `Model Boundary Contract v1`.
- [ ] No amplía la allowlist 042.
- [ ] No agrega `MedicationRequest` a Epic.
- [ ] No duplica la lógica de la Tarea 057.
- [ ] Conserva `pipelineStatus`.
- [ ] Conserva `clinicalDataAvailable`.
- [ ] Conserva `agentDecision`.
- [ ] Conserva `requiresHumanReview=true`.
- [ ] Conserva `modelCalled=false`.
- [ ] Conserva `modelCallAuthorized=false`.
- [ ] Conserva warnings y códigos de razón.
- [ ] Conserva `medicationRequestsStatus=NOT_REQUESTED`.
- [ ] No llama a ningún LLM.
- [ ] No agrega SDKs de IA.
- [ ] No agrega Python.
- [ ] No agrega RAG.
- [ ] No agrega embeddings.
- [ ] No agrega vector database.
- [ ] No agrega LangChain.
- [ ] No agrega LangGraph.
- [ ] No agrega memoria conversacional.
- [ ] No genera diagnóstico.
- [ ] No genera prescripción.
- [ ] No genera recomendaciones clínicas.
- [ ] Las pruebas nuevas pasan.
- [ ] `mvn test` completo pasa.
- [ ] `.env` permanece intacto.
- [ ] Se actualiza `docs/progress/progress-log.md`.
- [ ] Se documentan las fronteras arquitectónicas.
- [ ] Se documentan las superficies ciegas.
- [ ] Se documenta el endpoint reutilizado o creado.
- [ ] Se crea el commit Conventional Commits.
- [ ] Se informa la rama utilizada.
- [ ] Se informa el resultado de las pruebas.

---

# FUERA DE ALCANCE

No implementar en la Tarea 059:

- LLM real.
- OpenAI.
- Azure OpenAI.
- Gemini.
- Claude.
- Cualquier proveedor de IA.
- API keys de IA.
- Prompts reales.
- Servicio Python.
- Servicio externo de IA.
- RAG.
- Embeddings.
- Vector database.
- LangChain.
- LangGraph.
- Memoria conversacional.
- Agentes autónomos.
- Tool calling.
- Function calling.
- Diagnóstico clínico.
- Prescripción.
- Recomendaciones médicas.
- Decisiones clínicas automatizadas.
- Nuevos recursos FHIR.
- `MedicationRequest` para Epic.
- Cambios en OAuth2.
- Cambios en SMART PKCE.
- Cambios en Epic.
- Cambios en Oracle Health.
- Cambios en la allowlist 042.
- Modificación de `.env`.

---

# ENTREGABLES

Cursor debe entregar:

1. Código del primer componente de IA aislado.
2. DTOs o modelos estrictamente necesarios.
3. Servicio de procesamiento.
4. Mapper, si corresponde.
5. Endpoint de laboratorio, únicamente si es necesario.
6. Pruebas unitarias y/o de integración.
7. Documentación de las fronteras arquitectónicas.
8. Documentación de las superficies ciegas.
9. Actualización de `docs/progress/progress-log.md`.
10. Lista de archivos creados y modificados.
11. Resultado de `mvn test`.
12. Confirmación de que `.env` no fue modificado.
13. Rama utilizada.
14. Commit creado.
15. Resumen de decisiones técnicas y riesgos pendientes.

---

# INSTRUCCIÓN FINAL PARA CURSOR

Antes de implementar:

1. Inspecciona la Tarea 058 real.
2. Inspecciona `AiBoundaryResult` y sus dependencias.
3. Inspecciona los patrones actuales de servicios, DTOs, controladores y pruebas.
4. Determina el nivel mínimo de aislamiento necesario.
5. Evita crear clases o endpoints duplicados.
6. Implementa únicamente el primer componente técnico aislado.
7. No implementes LLM, RAG, LangGraph ni memoria.
8. No cambies `modelCallAuthorized=false`.
9. No cambies `requiresHumanReview=true`.
10. No generes salida clínica.
11. Ejecuta las pruebas existentes y las nuevas.
12. Actualiza la documentación y entrega el commit.

El resultado esperado de la Tarea 059 es:

```text
AiBoundaryResult
        ↓
FirstAiComponent
        ↓
FirstAiResult
```

con:

```text
modelCalled = false
modelCallAuthorized = false
requiresHumanReview = true
processingStatus = NOT_EXECUTED
```

La Tarea 059 debe dejar preparada una base aislada para que una futura tarea implemente el LLM real, sin mezclar Inteligencia Artificial con la interoperabilidad clínica Java.
