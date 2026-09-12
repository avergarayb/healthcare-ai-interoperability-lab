# Tarea 058 — Preparación del límite Java hacia un futuro AI Service

## 1. Identificación

- **Proyecto:** `healthcare-ai-interoperability-lab`
- **Servicio:** `fhir-integration-service`
- **Rama sugerida:** `feature/ai-boundary-preparation`
- **Commit sugerido:** `feat: prepare ai boundary after deterministic agent`
- **Stack existente:** Java 21, Spring Boot 3.5.16, HAPI FHIR 8.10.0
- **Paquete sugerido:** `lab.healthcare.fhir.aiboundary`

---

## 2. Objetivo

Preparar una frontera clara entre el servicio Java de interoperabilidad clínica y un futuro servicio de Inteligencia Artificial.

La implementación debe permitir que el futuro componente de IA consuma únicamente un contrato clínico controlado y seguro, sin acceder directamente a:

- Recursos FHIR crudos.
- Bundles completos.
- DTOs específicos de Epic u Oracle Health.
- Tokens OAuth2.
- Credenciales.
- Clientes HTTP de proveedores.
- HAPI FHIR.
- Servicios internos de interoperabilidad.
- Detalles de infraestructura.
- Datos no incluidos explícitamente en el contrato permitido.

Esta tarea **no implementa todavía un LLM ni un agente autónomo**. Su objetivo es preparar la frontera técnica y contractual para una futura integración con un `ai-service`.

---

## 3. Contexto funcional

La Tarea 057 implementó un agente determinístico inicial dentro del servicio Java.

El agente determinístico:

- Valida el `Model Boundary Contract v1`.
- Consume el `PipelineDiagnosis`.
- Reutiliza la validación existente de `AgentStub`.
- Emite una decisión determinística.
- No llama a Epic, Oracle Health, FHIR, HAPI ni a un modelo de IA.
- Mantiene separados:
  1. El estado del pipeline.
  2. La disponibilidad de datos clínicos.
  3. La decisión del agente.

La Tarea 058 debe reutilizar esa salida y preparar una representación explícita para un futuro componente de IA.

---

## 4. Resultado esperado

Crear una frontera de aplicación que represente el resultado clínico autorizado para ser considerado por un futuro servicio de IA.

La frontera debe:

1. Recibir únicamente datos contractuales ya normalizados.
2. Recibir la decisión del agente determinístico.
3. No volver a consultar proveedores externos.
4. No volver a interpretar recursos FHIR crudos.
5. No reimplementar las reglas de la Tarea 057.
6. No autorizar automáticamente una llamada a un modelo.
7. Mantener explícita la diferencia entre:
   - `READY`
   - disponibilidad de datos clínicos
   - autorización para llamar a un modelo
   - revisión humana requerida

---

## 5. Concepto central obligatorio

Debe quedar explícito en el código y en la documentación:

> `READY` no significa autorización para llamar a un modelo de IA.

La salida debe mantener, como mínimo, estos indicadores conceptualmente separados:

- `pipelineStatus`
- `clinicalDataAvailable`
- `agentDecision`
- `requiresHumanReview`
- `modelCalled`
- `modelCallAuthorized`

Valores esperados en esta fase:

- `modelCalled = false`
- `modelCallAuthorized = false`
- `requiresHumanReview = true`

La Tarea 058 no debe activar ninguna llamada real a OpenAI, otro LLM o cualquier proveedor de IA.

---

## 6. Diseño sugerido

Inspeccionar primero el código existente. No crear clases duplicadas si ya existe una implementación equivalente.

Paquete sugerido:

```text
lab.healthcare.fhir.aiboundary
```

Clases sugeridas, solo si no existe una alternativa adecuada:

```text
AiBoundaryInput
AiBoundaryDecision
AiBoundaryResult
AiBoundaryMapper
AiBoundaryService
```

Los nombres pueden adaptarse al estilo real del repositorio, siempre que se conserve la responsabilidad de cada componente.

---

## 7. Responsabilidades de los componentes

### 7.1. `AiBoundaryInput`

Representa la entrada controlada hacia la frontera de IA.

Debe contener únicamente información proveniente de:

- `Model Boundary Contract v1`.
- `PipelineDiagnosis`.
- `DeterministicAgentResult`.

No debe contener:

- `Bundle` FHIR crudo.
- `Resource` de HAPI.
- DTOs de Epic.
- DTOs de Oracle Health.
- Access tokens.
- Refresh tokens.
- Client secrets.
- URLs privadas de proveedores.
- Objetos de infraestructura.

Si el contrato actual ya contiene una estructura adecuada, reutilizarla en lugar de crear otra copia innecesaria.

---

### 7.2. `AiBoundaryDecision`

Representa la decisión de frontera, no una decisión clínica ni una autorización de ejecución de IA.

Debe permitir expresar, como mínimo:

- Estado del pipeline.
- Disponibilidad de datos clínicos.
- Decisión del agente determinístico.
- Si se requiere revisión humana.
- Si se llamó a un modelo.
- Si existe autorización para llamar a un modelo.
- Warnings operacionales.
- Códigos de razón.
- Identificador de correlación, si ya existe en el sistema.

Valores por defecto obligatorios para esta tarea:

```text
modelCalled = false
modelCallAuthorized = false
requiresHumanReview = true
```

No agregar una autorización implícita basada únicamente en `READY`.

---

### 7.3. `AiBoundaryResult`

Debe ser una salida estable y serializable para una futura integración.

Debe incluir:

- La decisión de frontera.
- Los campos contractuales necesarios.
- Warnings no sensibles.
- Códigos de razón.
- Información mínima de trazabilidad.

No debe exponer:

- Tokens.
- Secretos.
- Headers de autenticación.
- Recursos FHIR completos.
- Payloads completos de proveedores.
- Información innecesaria para el futuro servicio de IA.

---

### 7.4. `AiBoundaryMapper`

Debe transformar los resultados existentes hacia la frontera de IA.

Responsabilidades:

- Mapear `DeterministicAgentResult`.
- Conservar los campos relevantes de `Model Boundary Contract v1`.
- Conservar los datos de `PipelineDiagnosis`.
- Conservar los códigos de razón.
- Conservar warnings operacionales.
- No modificar la decisión determinística original.
- No agregar campos inventados.
- No eliminar información necesaria para auditoría.

No debe:

- Volver a consultar Epic.
- Volver a consultar Oracle Health.
- Ejecutar llamadas FHIR.
- Ejecutar lógica de negocio duplicada.
- Invocar un LLM.
- Crear un diagnóstico clínico.

---

### 7.5. `AiBoundaryService`

Debe coordinar la creación del resultado de frontera.

Flujo esperado:

```text
Model Boundary Contract v1
        +
PipelineDiagnosis
        +
DeterministicAgentResult
        ↓
AiBoundaryMapper
        ↓
AiBoundaryService
        ↓
AiBoundaryResult
```

El servicio debe:

- Validar que las entradas mínimas estén presentes.
- Reutilizar las validaciones existentes cuando sea posible.
- Mantener la decisión determinística.
- Marcar `modelCalled = false`.
- Marcar `modelCallAuthorized = false`.
- Mantener `requiresHumanReview = true`.
- Emitir warnings operacionales de forma segura.
- No ejecutar ninguna llamada externa de IA.

---

## 8. Reglas funcionales

### Regla 1 — No duplicar la lógica de la Tarea 057

La Tarea 058 debe consumir el resultado del agente determinístico.

No debe copiar ni reimplementar las reglas de:

- `READY`.
- `BLOCKED`.
- `REQUIRES_HUMAN_REVIEW`.
- Validación del contrato.
- Validación del pipeline.
- Disponibilidad de datos clínicos.

---

### Regla 2 — Mantener separados los tres juicios

Debe conservarse la separación entre:

1. Estado del pipeline.
2. Disponibilidad de datos clínicos.
3. Decisión del agente.

La frontera de IA no debe convertir esos tres conceptos en un único booleano ambiguo.

---

### Regla 3 — `READY` no autoriza el modelo

Incluso cuando el resultado determinístico sea `READY`:

```text
modelCalled = false
modelCallAuthorized = false
requiresHumanReview = true
```

---

### Regla 4 — Datos clínicos ausentes

Si no existen datos clínicos utilizables:

- Conservar la decisión del agente.
- No inventar datos.
- No completar información mediante inferencias.
- Mantener revisión humana.
- Agregar un código de razón o warning si corresponde.

---

### Regla 5 — Resultado parcial

Si el pipeline es `PARTIAL`:

- Conservar el estado parcial.
- Conservar warnings.
- No convertirlo en `READY`.
- No autorizar llamadas a modelos.
- Mantener revisión humana.

---

### Regla 6 — Truncamiento o recurso no solicitado

Si existen warnings como:

- Recurso no solicitado.
- Truncamiento.
- Datos no disponibles.
- Limitaciones operacionales.

Deben conservarse en la frontera de IA sin exponer información sensible.

---

### Regla 7 — MedicationRequest

Mantener la semántica actual:

```text
MedicationRequest = NOT_REQUESTED
```

Si existe un warning asociado, debe conservarse.

No implementar todavía:

- MedicationRequest.
- Prescripción.
- Recomendación farmacológica.
- Acciones clínicas.
- Generación de órdenes médicas.

---

## 9. Endpoint o superficie de integración

Inspeccionar primero los endpoints existentes.

Si ya existe una superficie adecuada para mostrar el resultado del agente determinístico, reutilizarla o ampliarla de forma compatible.

No crear endpoints duplicados sin necesidad.

Si se considera necesario agregar un endpoint de laboratorio, debe:

- Ser claramente de laboratorio.
- No simular una API de producción.
- No realizar llamadas externas de IA.
- Devolver únicamente `AiBoundaryResult`.
- Mantener la misma política de seguridad y trazabilidad existente.
- No exponer secretos ni tokens.

La implementación debe documentar qué endpoint se reutilizó o por qué fue necesario crear uno nuevo.

---

## 10. Compatibilidad y no regresión

La implementación debe conservar:

- Los campos de las tareas 053–056.
- La salida de la Tarea 057.
- `MedicationRequest = NOT_REQUESTED`.
- Warnings operacionales.
- Códigos de razón.
- `requiresHumanReview = true`.
- `modelCalled = false`.

No modificar innecesariamente:

- Integración Epic.
- Integración Oracle Health.
- OAuth2.
- Cliente FHIR.
- HAPI FHIR.
- Routing existente.
- Contratos previos.
- Datos de prueba existentes.

---

## 11. Observabilidad y seguridad

Agregar trazabilidad segura únicamente si el repositorio ya tiene un patrón establecido.

Se puede registrar:

- Correlation ID.
- Estado del pipeline.
- Decisión del agente.
- Disponibilidad de datos clínicos.
- Códigos de razón.
- Resultado de la frontera.

No registrar:

- Access tokens.
- Refresh tokens.
- Client secrets.
- Authorization headers.
- Bundles completos.
- Payloads clínicos completos.
- Datos personales innecesarios.
- Información sensible no requerida para depuración.

---

## 12. Pruebas obligatorias

Agregar o actualizar pruebas unitarias y de integración según el estilo existente.

Como mínimo, cubrir:

### Caso A — Resultado `READY`

Verificar:

```text
agentDecision = READY
modelCalled = false
modelCallAuthorized = false
requiresHumanReview = true
```

### Caso B — Resultado `BLOCKED`

Verificar:

- Se conserva `BLOCKED`.
- No se convierte en `READY`.
- No se autoriza el modelo.
- Se conservan códigos de razón.

### Caso C — Resultado `REQUIRES_HUMAN_REVIEW`

Verificar:

- Se conserva la decisión.
- `requiresHumanReview = true`.
- No se autoriza el modelo.

### Caso D — Pipeline `PARTIAL`

Verificar:

- Se conserva `PARTIAL`.
- Se conservan warnings.
- No se autoriza el modelo.

### Caso E — Sin datos clínicos

Verificar:

- No se inventan datos.
- Se conserva la ausencia de datos.
- Se requiere revisión humana.
- No se autoriza el modelo.

### Caso F — Warnings operacionales

Verificar que se conserven warnings de:

- Truncamiento.
- Recurso no solicitado.
- Datos no disponibles.
- `MedicationRequest = NOT_REQUESTED`.

### Caso G — Seguridad del contrato

Verificar que el resultado no exponga:

- Tokens.
- Secretos.
- Headers.
- Bundles FHIR completos.
- DTOs de proveedores.

### Caso H — No llamada a IA

Verificar que no exista ninguna invocación a:

- OpenAI.
- Otro proveedor LLM.
- SDK de IA.
- Cliente HTTP de IA.
- Servicio Python externo.

---

## 13. Criterios de aceptación

La tarea está terminada cuando:

- [x] Existe una frontera explícita entre Java y el futuro AI Service.
- [x] La frontera consume solo contratos controlados.
- [x] Se reutiliza `DeterministicAgentResult`.
- [x] No se duplica la lógica de la Tarea 057.
- [x] Se conserva la separación entre pipeline, datos clínicos y decisión del agente.
- [x] `READY` no autoriza llamadas a modelos.
- [x] `modelCalled = false`.
- [x] `modelCallAuthorized = false`.
- [x] `requiresHumanReview = true`.
- [x] Se conservan warnings y códigos de razón.
- [x] Se conserva `MedicationRequest = NOT_REQUESTED`.
- [x] No se agregan llamadas a Epic, Oracle Health o FHIR.
- [x] No se agregan SDKs de IA.
- [x] No se agregan componentes Python.
- [x] No se agregan LLM, RAG, embeddings, vector DB ni LangGraph.
- [x] Las pruebas nuevas pasan.
- [x] La suite completa de Maven pasa.
- [x] `.env` permanece intacto.
- [x] Se actualiza la documentación de progreso.
- [x] Se documenta el endpoint reutilizado o creado.
- [ ] Se crea commit y rama según el estándar del repositorio.

---

## 14. Fuera de alcance

No implementar en esta tarea:

- OpenAI API.
- Azure OpenAI.
- Gemini.
- Claude.
- Cualquier otro LLM.
- Servicio Python `ai-service`.
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
- Automatización de decisiones clínicas.
- Nuevos recursos FHIR no solicitados.
- `MedicationRequest`.
- Integración real con WhatsApp u otros canales.
- Cambios de infraestructura no necesarios.

---

## 15. Entregables

Cursor debe entregar:

1. Código de la frontera de IA.
2. Pruebas unitarias y/o de integración.
3. Documentación técnica breve.
4. Actualización de `docs/progress/progress-log.md`.
5. Registro de archivos modificados.
6. Resultado de `mvn test`.
7. Confirmación de que `.env` no fue modificado.
8. Commit creado.
9. Rama utilizada.
10. Resumen de riesgos o decisiones técnicas pendientes.

---

## 16. Instrucción final para Cursor

Antes de modificar código:

1. Inspecciona la implementación real de la Tarea 057.
2. Inspecciona los contratos existentes.
3. Inspecciona los endpoints actuales.
4. Inspecciona los patrones de DTO, mapper, service y test.
5. Determina si ya existe una frontera equivalente.
6. Evita duplicar clases o endpoints.
7. Implementa la mínima solución compatible con el diseño actual.
8. No avances hacia la implementación del agente LLM real.

La Tarea 058 debe dejar preparado el límite arquitectónico para que una futura Tarea 059 pueda implementar un componente de IA separado, sin mezclar responsabilidades con la interoperabilidad clínica Java.
