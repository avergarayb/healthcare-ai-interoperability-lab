# Task 060 — AI Execution Gate y contrato de preparación para procesamiento futuro

## Identificación

- **Proyecto:** `healthcare-ai-interoperability-lab`
- **Servicio actual:** `fhir-integration-service`
- **Stack actual:** Java 21, Spring Boot 3.5.16, HAPI FHIR 8.10.0
- **Paquete actual:** `lab.healthcare.fhir`
- **Puerto actual:** `8081`
- **Rama base:** `feature/first-ai-component`
- **Commit base:** `b385755`
- **Mensaje del commit base:** `feat: add isolated first ai component`
- **Rama sugerida:** `feature/ai-execution-gate`
- **Commit sugerido:** `feat: add ai execution gate`

---

# WHAT

Implementar una **puerta explícita de ejecución de IA** que determine si una entrada proveniente de `FirstAiResult` podría avanzar hacia un futuro procesamiento de IA.

La Tarea 060 no debe ejecutar ningún modelo ni realizar llamadas externas.

Su objetivo es separar claramente:

1. La preparación técnica de la entrada.
2. La decisión del agente determinístico.
3. La autorización para procesamiento de IA.
4. La ejecución real de IA.

Valores obligatorios:

```text
modelCalled = false
modelCallAuthorized = false
processingStatus = NOT_EXECUTED
requiresHumanReview = true
```

La Tarea 060 debe dejar preparada una interfaz estable para que una futura tarea pueda incorporar un proveedor de IA sin modificar las capas de interoperabilidad clínica.

---

# WHY

Las tareas anteriores ya implementaron:

```text
AiBoundaryResult
        ↓
FirstAiComponent
        ↓
FirstAiResult
```

Sin embargo, todavía no existe una separación explícita entre:

```text
entrada preparada
```

y:

```text
entrada autorizada para procesamiento de IA
```

La Tarea 060 debe crear esa separación.

El objetivo no es llamar a un LLM, sino evitar que una futura integración de IA interprete accidentalmente:

```text
agentDecision = READY
```

como:

```text
modelCallAuthorized = true
```

La autorización debe ser una decisión independiente, controlada y auditable.

---

# CONCEPT

## 1. Preparación no significa autorización

La siguiente distinción debe quedar explícita:

```text
PREPARED       = el componente recibió una entrada válida
READY          = la entrada fue considerada utilizable por el agente
AUTHORIZED     = existe permiso explícito para procesar con IA
EXECUTED       = un modelo fue llamado realmente
```

En la Tarea 060:

```text
PREPARED       = posible
AUTHORIZED     = false
EXECUTED       = false
```

No se debe crear una autorización implícita basada en:

- `agentDecision=READY`.
- `pipelineStatus=SUCCESS`.
- `clinicalDataAvailable=true`.
- `firstAiComponent=PREPARED`.

---

## 2. La puerta de ejecución no es un modelo

La puerta de ejecución será una decisión técnica local.

No debe:

- Crear prompts.
- Invocar LLM.
- Seleccionar modelos.
- Generar respuestas clínicas.
- Ejecutar RAG.
- Consultar una base vectorial.
- Crear memoria conversacional.
- Ejecutar herramientas externas.

Su responsabilidad será evaluar si las condiciones mínimas de la frontera están presentes y devolver una decisión de autorización.

En esta fase, aunque las condiciones técnicas sean favorables, la autorización efectiva debe permanecer deshabilitada.

---

# HOW

## 1. Inspección inicial obligatoria

Antes de modificar código, inspeccionar:

1. `AiBoundaryResult`.
2. `FirstAiInput`.
3. `FirstAiResult`.
4. `FirstAiComponent`.
5. `FirstAiComponentStatus`.
6. `FirstAiProcessingStatus`.
7. Los endpoints existentes:
   - `GET /lab/first-ai-component`
   - `GET /api/first-ai-component/v1`
   - `GET /epic/sandbox/fhir/clinical-projection`
8. Los patrones existentes de:
   - Services.
   - DTOs.
   - Mappers.
   - Enums.
   - Controllers.
   - Manejo de errores.
   - Tests.
   - Observabilidad.
9. Las dependencias reales entre paquetes.

No crear clases duplicadas si ya existe una abstracción equivalente.

---

## 2. Aislamiento arquitectónico

La implementación debe permanecer fuera de las responsabilidades de interoperabilidad FHIR.

Paquete sugerido:

```text
lab.healthcare.fhir.aigateway
```

o un nombre equivalente que respete la estructura real del repositorio.

No mezclar esta lógica con:

```text
FhirService
snapshot
projection
pipeline
agent
agentstub
modelboundary
vendor.*
```

La dependencia recomendada debe ser:

```text
firstai → aigateway
```

o, si el diseño real lo requiere:

```text
aiboundary → firstai → aigateway
```

No se debe crear una dependencia inversa desde interoperabilidad hacia la puerta de ejecución.

---

# DISEÑO SUGERIDO

Los nombres siguientes son orientativos. Adaptarlos a los patrones existentes.

```text
lab.healthcare.fhir.aigateway
├── AiExecutionGate
├── AiExecutionInput
├── AiExecutionDecision
├── AiExecutionStatus
├── AiExecutionReasonCode
└── AiExecutionMapper
```

No crear todas las clases si una solución más pequeña mantiene la separación de responsabilidades.

---

## 1. `AiExecutionInput`

Debe representar únicamente la información mínima necesaria para evaluar la puerta de ejecución.

La entrada puede derivarse de:

- `FirstAiResult`.
- `AiBoundaryResult`.

Debe contener únicamente:

- `agentDecision`.
- `pipelineStatus`.
- `clinicalDataAvailable`.
- `firstAiComponentStatus`.
- `aiProcessingStatus`.
- `requiresHumanReview`.
- `modelCalled`.
- `modelCallAuthorized`.
- Warnings.
- Códigos de razón.
- Correlation ID, si ya existe.

No debe contener:

- FHIR crudo.
- Bundles.
- Recursos HAPI.
- DTOs de Epic.
- DTOs de Oracle Health.
- Tokens.
- Client IDs.
- Client secrets.
- Headers.
- URLs privadas.
- Payloads clínicos completos.
- Patient IDs.
- Datos clínicos no incluidos en `FirstAiResult` o `AiBoundaryResult`.

---

## 2. `AiExecutionDecision`

Debe representar el resultado de evaluar la puerta de ejecución.

Debe distinguir entre:

- Entrada no preparada.
- Entrada bloqueada.
- Revisión humana requerida.
- Entrada técnicamente elegible.
- Autorización efectiva deshabilitada.

Estados sugeridos:

```text
NOT_ELIGIBLE
BLOCKED
REQUIRES_HUMAN_REVIEW
ELIGIBLE_BUT_NOT_AUTHORIZED
```

Si el repositorio ya tiene estados equivalentes, reutilizarlos.

Para el caso actual:

```text
agentDecision = READY
clinicalDataAvailable = true
firstAiComponentStatus = PREPARED
aiProcessingStatus = NOT_EXECUTED
modelCallAuthorized = false
```

El resultado esperado debe ser:

```text
executionDecision = ELIGIBLE_BUT_NOT_AUTHORIZED
modelCallAuthorized = false
modelCalled = false
requiresHumanReview = true
```

El término `ELIGIBLE` debe interpretarse como una evaluación técnica preliminar, no como permiso para llamar a un modelo.

---

## 3. `AiExecutionGate`

Debe evaluar la entrada y producir `AiExecutionDecision`.

Responsabilidades:

1. Validar que exista una entrada.
2. Validar que la entrada provenga de una frontera permitida.
3. Revisar el estado del agente determinístico.
4. Revisar la disponibilidad de datos clínicos.
5. Revisar el estado del componente `firstai`.
6. Revisar el estado de procesamiento.
7. Mantener `modelCallAuthorized=false`.
8. Mantener `modelCalled=false`.
9. Mantener `requiresHumanReview=true`.
10. Devolver razones técnicas claras.
11. No llamar a servicios externos.
12. No crear salida clínica.

No debe:

- Ejecutar `DeterministicAgent`.
- Ejecutar `AgentStub`.
- Consultar Epic.
- Consultar Oracle Health.
- Consultar FHIR.
- Usar HAPI.
- Crear un Bundle.
- Generar prompts.
- Invocar un LLM.
- Modificar `AiBoundaryResult`.
- Modificar `FirstAiResult`.

---

# REGLAS FUNCIONALES

## Regla 1 — Entrada `READY` y preparada

Cuando:

```text
agentDecision = READY
firstAiComponentStatus = PREPARED
aiProcessingStatus = NOT_EXECUTED
clinicalDataAvailable = true
```

El resultado debe ser:

```text
executionDecision = ELIGIBLE_BUT_NOT_AUTHORIZED
modelCallAuthorized = false
modelCalled = false
requiresHumanReview = true
```

No se debe producir contenido clínico.

---

## Regla 2 — Entrada `BLOCKED`

Cuando:

```text
agentDecision = BLOCKED
```

El resultado debe ser:

```text
executionDecision = BLOCKED
modelCallAuthorized = false
modelCalled = false
requiresHumanReview = true
```

Debe conservar:

- Códigos de razón.
- Warnings.
- Estado del pipeline.
- Estado del componente.

---

## Regla 3 — Revisión humana requerida

Cuando:

```text
agentDecision = REQUIRES_HUMAN_REVIEW
```

El resultado debe ser:

```text
executionDecision = REQUIRES_HUMAN_REVIEW
modelCallAuthorized = false
modelCalled = false
requiresHumanReview = true
```

No se deben generar diagnósticos ni recomendaciones.

---

## Regla 4 — Datos clínicos ausentes

Cuando:

```text
clinicalDataAvailable = false
```

El resultado debe:

- Bloquear el procesamiento.
- Mantener revisión humana.
- Mantener `modelCallAuthorized=false`.
- Mantener `modelCalled=false`.
- Conservar warnings y razones.
- No inventar datos.

---

## Regla 5 — Pipeline parcial

Cuando:

```text
pipelineStatus = PARTIAL
```

El resultado debe:

- Conservar `PARTIAL`.
- No convertirlo en `SUCCESS`.
- No autorizar el modelo.
- Mantener revisión humana.
- Conservar warnings operacionales.

---

## Regla 6 — Procesamiento todavía no ejecutado

Cuando:

```text
aiProcessingStatus = NOT_EXECUTED
```

El resultado debe mantener:

```text
modelCalled = false
```

No se debe cambiar el estado a:

- `EXECUTED`.
- `COMPLETED`.
- `SUCCESS`.
- `GENERATED`.

---

## Regla 7 — Autorización falsa

Cuando:

```text
modelCallAuthorized = false
```

La puerta debe rechazar cualquier intento de ejecución real.

No se debe interpretar como autorización:

- `READY`.
- `PREPARED`.
- `SUCCESS`.
- `clinicalDataAvailable=true`.

---

## Regla 8 — Intento de autorización prematura

Si una entrada intenta llegar con:

```text
modelCallAuthorized = true
```

la implementación debe aplicar el patrón de seguridad existente.

Opciones válidas:

- Rechazar la entrada.
- Normalizar el valor a `false`.
- Devolver una razón explícita de autorización no permitida.

La opción elegida debe documentarse y probarse.

En ningún caso se debe ejecutar un modelo.

---

## Regla 9 — MedicationRequest

Conservar:

```text
medicationRequestsStatus = NOT_REQUESTED
```

No implementar:

- `MedicationRequest`.
- Prescripción.
- Recomendaciones farmacológicas.
- Nuevos recursos FHIR.
- Ampliación de la allowlist 042.

---

# SUPERFICIES CIEGAS

La puerta de ejecución debe ser ciega a:

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
FHIR Resources
Vendor DTOs
Snapshot
Controlled Projection
FhirService
RoutingService
AgentStub
DeterministicAgent
Pipeline internals
```

Debe conocer únicamente:

```text
FirstAiResult
AiBoundaryResult
```

y los tipos mínimos necesarios para evaluar la autorización técnica.

---

# SUPERFICIE DE PRUEBA

Inspeccionar los endpoints existentes.

Si ya existe una superficie adecuada para mostrar el resultado de `FirstAiComponent`, reutilizarla.

No crear endpoints duplicados.

Si se requiere un endpoint de laboratorio, debe:

- Ser claramente de laboratorio.
- No representar una API de producción.
- No aceptar FHIR crudo.
- No aceptar tokens.
- No aceptar DTOs de Epic u Oracle.
- No ejecutar ningún modelo.
- Devolver únicamente la decisión de la puerta.
- No exponer datos clínicos completos.
- Mantener las políticas de seguridad existentes.

La documentación debe indicar:

- Endpoint reutilizado.
- Endpoint nuevo, si corresponde.
- Motivo técnico de la decisión.

---

# COMPATIBILIDAD

No modificar innecesariamente:

- `Model Boundary Contract v1`.
- `PipelineDiagnosis`.
- `DeterministicAgentResult`.
- `AiBoundaryResult`.
- `FirstAiResult`.
- Integración Epic.
- Integración Oracle Health.
- OAuth2.
- SMART PKCE.
- FHIR.
- HAPI.
- Allowlist 042.
- Campos de las tareas 053–059.
- `.env`.

Debe conservarse la evidencia existente:

```text
firstAiComponent=PREPARED
aiProcessingStatus=NOT_EXECUTED
modelCallAuthorized=false
aiModelCalled=false
requiresHumanReview=true
medicationRequestsStatus=NOT_REQUESTED
```

---

# SEGURIDAD Y OBSERVABILIDAD

No registrar:

- Tokens.
- Client IDs.
- Client secrets.
- Authorization headers.
- Patient IDs.
- Bundles.
- FHIR JSON.
- Payloads clínicos completos.
- DTOs de proveedores.
- Prompts.
- Respuestas de modelos.

Se puede registrar:

- Correlation ID.
- Estado del pipeline.
- Estado del agente.
- Estado de `firstai`.
- Decisión de la puerta.
- Código de razón.
- Cantidad de warnings.
- Estado de autorización.

---

# PRUEBAS OBLIGATORIAS

## Caso A — Entrada preparada y `READY`

Verificar:

```text
executionDecision = ELIGIBLE_BUT_NOT_AUTHORIZED
modelCallAuthorized = false
modelCalled = false
requiresHumanReview = true
```

---

## Caso B — Entrada `BLOCKED`

Verificar:

- Decisión `BLOCKED`.
- No autorización.
- No ejecución.
- Revisión humana.
- Conservación de razones.

---

## Caso C — Revisión humana requerida

Verificar:

- Decisión `REQUIRES_HUMAN_REVIEW`.
- `requiresHumanReview=true`.
- `modelCallAuthorized=false`.
- `modelCalled=false`.

---

## Caso D — Datos clínicos ausentes

Verificar:

- Bloqueo técnico.
- No invención de datos.
- No autorización.
- Conservación de warnings.

---

## Caso E — Pipeline parcial

Verificar:

- Se conserva `PARTIAL`.
- No se convierte en `SUCCESS`.
- No se autoriza modelo.
- Se conserva revisión humana.

---

## Caso F — `aiProcessingStatus=NOT_EXECUTED`

Verificar:

```text
modelCalled = false
modelCallAuthorized = false
```

---

## Caso G — Intento de autorización `true`

Verificar que:

- No se ejecute ningún modelo.
- Se rechace o normalice según la política documentada.
- Se emita un código de razón seguro.
- No se expongan datos sensibles.

---

## Caso H — Conservación de warnings

Verificar la conservación de:

- Truncamiento.
- Recurso no solicitado.
- Datos no disponibles.
- Limitaciones operacionales.
- `MedicationRequest=NOT_REQUESTED`.

---

## Caso I — No dependencias prohibidas

Verificar que la puerta no dependa de:

- `vendor.*`.
- `FhirService`.
- HAPI.
- Epic.
- Oracle.
- `DeterministicAgent`.
- `AgentStub`.
- Clientes HTTP externos.
- SDKs de IA.

---

## Caso J — Entrada nula o incompleta

Verificar:

- Aplicación del patrón de error existente.
- No autorización.
- No ejecución.
- No salida clínica.
- No exposición de información sensible.

---

# DEFINITION OF DONE

La tarea está terminada cuando:

- [ ] Existe una puerta explícita de ejecución de IA.
- [ ] Consume únicamente `FirstAiResult` o `AiBoundaryResult`.
- [ ] No consume FHIR crudo.
- [ ] No consume Bundles.
- [ ] No consume DTOs de Epic u Oracle.
- [ ] No consume tokens ni secretos.
- [ ] No importa clientes de proveedores.
- [ ] No ejecuta `DeterministicAgent`.
- [ ] No ejecuta `AgentStub`.
- [ ] No modifica `Model Boundary Contract v1`.
- [ ] No amplía la allowlist 042.
- [ ] No agrega `MedicationRequest` a Epic.
- [ ] Mantiene `modelCallAuthorized=false`.
- [ ] Mantiene `modelCalled=false`.
- [ ] Mantiene `processingStatus=NOT_EXECUTED`.
- [ ] Mantiene `requiresHumanReview=true`.
- [ ] Conserva `pipelineStatus`.
- [ ] Conserva `clinicalDataAvailable`.
- [ ] Conserva `agentDecision`.
- [ ] Conserva warnings y códigos de razón.
- [ ] Conserva `medicationRequestsStatus=NOT_REQUESTED`.
- [ ] No implementa ningún LLM.
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

No implementar en la Tarea 060:

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

1. Código de la puerta de ejecución de IA.
2. DTOs, enums o modelos estrictamente necesarios.
3. Servicio o componente de evaluación.
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

1. Inspecciona la implementación real de las tareas 058 y 059.
2. Inspecciona `AiBoundaryResult` y `FirstAiResult`.
3. Inspecciona los estados existentes.
4. Inspecciona los patrones actuales de services, DTOs, mappers, controllers y tests.
5. Determina si ya existe una puerta o política de autorización equivalente.
6. Evita crear clases o endpoints duplicados.
7. Implementa únicamente una decisión técnica de autorización.
8. No implementes ningún LLM.
9. No realices llamadas externas.
10. No cambies `modelCallAuthorized=false`.
11. No cambies `modelCalled=false`.
12. No cambies `processingStatus=NOT_EXECUTED`.
13. No cambies `requiresHumanReview=true`.
14. No generes salida clínica.
15. Ejecuta las pruebas existentes y las nuevas.
16. Actualiza la documentación y entrega el commit.

El resultado esperado de la Tarea 060 es:

```text
FirstAiResult
        ↓
AiExecutionGate
        ↓
AiExecutionDecision
```

con:

```text
executionDecision = ELIGIBLE_BUT_NOT_AUTHORIZED
modelCalled = false
modelCallAuthorized = false
processingStatus = NOT_EXECUTED
requiresHumanReview = true
```

La Tarea 060 debe dejar preparada una política de autorización explícita para que una futura tarea implemente el procesamiento de IA real sin mezclarlo con la interoperabilidad clínica Java.
