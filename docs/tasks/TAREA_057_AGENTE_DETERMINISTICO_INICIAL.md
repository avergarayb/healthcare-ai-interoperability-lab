# Tarea 057 — Agente determinístico inicial y frontera hacia el agente de IA

## 1. Objetivo

Implementar un agente determinístico inicial dentro de `fhir-integration-service` para validar la frontera entre la interoperabilidad clínica y el futuro agente real basado en inteligencia artificial.

Esta tarea **no implementa todavía OpenAI, RAG, LangGraph ni memoria conversacional**. Su propósito es verificar que el sistema puede entregar información clínica controlada a un componente de agente sin exponer directamente los sistemas EHR, FHIR, HAPI FHIR, Epic u Oracle.

## 2. Contexto arquitectónico

Flujo actual:

```text
Epic / Oracle / FHIR
        ↓
Adaptadores de interoperabilidad
        ↓
FhirService
        ↓
ClinicalSnapshot
        ↓
Proyección clínica controlada
        ↓
Model Boundary Contract v1
```

Flujo incorporando la Tarea 057:

```text
Model Boundary Contract v1
        ↓
Agente determinístico inicial
        ↓
Resultado estructurado
```

El agente determinístico será una primera implementación interna en Java. En una etapa posterior podrá ser reemplazado o complementado por un `ai-service` independiente, posiblemente desarrollado en Python.

## 3. Alcance

### Incluido

- Crear el paquete de agente dentro del proyecto Java.
- Consumir únicamente `Model Boundary Contract v1`.
- Consumir, cuando corresponda, el resultado de `PipelineDiagnosis`.
- Evaluar reglas determinísticas.
- Generar una salida estructurada y reproducible.
- Indicar si el resultado está listo, bloqueado o requiere revisión humana.
- Mantener separación estricta entre interoperabilidad y agente.
- Preparar una frontera clara para el futuro servicio de IA.

### No incluido

- OpenAI.
- Otro proveedor LLM.
- RAG.
- Embeddings.
- Base de datos vectorial.
- LangChain.
- LangGraph.
- Memoria conversacional.
- Agentes autónomos reales.
- Orquestación multiagente.
- Acceso directo del agente a Epic, Oracle o FHIR.
- Envío de Bundles FHIR completos a un modelo.
- Diagnóstico médico automatizado.
- Recomendaciones clínicas autónomas.

## 4. Definición de agente determinístico

Un agente determinístico produce el mismo resultado cuando recibe la misma entrada y se aplican las mismas reglas.

Ejemplo conceptual:

```java
if (contractIsValid && pipelineStatusIsSuccessful) {
    return READY;
}

if (contractIsInvalid) {
    return BLOCKED;
}

return REQUIRES_HUMAN_REVIEW;
```

El agente no interpreta lenguaje natural ni genera respuestas creativas. Ejecuta reglas explícitas y controlables.

## 5. Responsabilidades del agente

El agente debe:

1. Recibir el contrato clínico autorizado.
2. Validar que la entrada cumpla las condiciones mínimas.
3. Revisar el estado del pipeline.
4. Detectar advertencias o inconsistencias.
5. Determinar si el procesamiento puede continuar.
6. Generar un resultado estructurado.
7. Indicar cuándo es obligatoria la revisión humana.
8. Evitar cualquier acceso directo a fuentes clínicas externas.

## 6. Paquete propuesto

Ubicación:

```text
src/main/java/lab/healthcare/fhir/agent
```

Clases sugeridas:

```text
agent/
├── DeterministicAgent.java
├── DeterministicAgentInput.java
├── DeterministicAgentResult.java
├── AgentDecision.java
└── AgentValidationException.java
```

Los nombres definitivos deben ajustarse a las convenciones existentes del repositorio y evitar duplicar clases ya implementadas.

## 7. Entrada del agente

La entrada debe provenir exclusivamente de los contratos internos autorizados.

Ejemplo conceptual:

```json
{
  "clinicalContext": {
    "conditions": [],
    "medications": [],
    "observations": []
  },
  "pipelineDiagnosis": {
    "status": "SUCCESS",
    "warnings": []
  }
}
```

El ejemplo es ilustrativo. Deben utilizarse las clases y contratos reales existentes en el repositorio.

El agente no debe recibir:

- `Bundle` FHIR completo.
- Recursos HAPI FHIR sin proyectar.
- Tokens OAuth.
- Client secrets.
- Identificadores de conexión.
- Datos de configuración de Epic u Oracle.
- Respuestas crudas de proveedores.

## 8. Salida del agente

La salida debe ser estructurada, estable y fácil de validar.

Ejemplo conceptual:

```json
{
  "decision": "READY",
  "findings": [],
  "warnings": [],
  "requiresHumanReview": true
}
```

Posibles decisiones:

```text
READY
BLOCKED
REQUIRES_HUMAN_REVIEW
```

Las decisiones definitivas deben corresponder a las convenciones del proyecto.

## 9. Reglas de seguridad y arquitectura

El agente:

- No debe importar clases de Epic.
- No debe importar clases de Oracle.
- No debe importar clases de HAPI FHIR.
- No debe invocar directamente `FhirService`.
- No debe realizar llamadas HTTP hacia EHR.
- No debe acceder a tokens ni secretos.
- No debe consultar bases de datos clínicas directamente.
- No debe modificar el `ClinicalSnapshot`.
- No debe ampliar el contrato clínico por iniciativa propia.
- No debe registrar datos clínicos sensibles en logs.
- Debe utilizar únicamente información previamente filtrada y autorizada.
- Debe mantener la revisión humana como requisito para decisiones clínicas.

## 10. Separación de responsabilidades

### Interoperabilidad Java

La capa de interoperabilidad seguirá siendo responsable de:

- Conectarse con Epic y Oracle.
- Consumir FHIR.
- Gestionar autenticación y autorización.
- Normalizar recursos.
- Construir `ClinicalSnapshot`.
- Aplicar proyecciones controladas.
- Generar `Model Boundary Contract v1`.
- Gestionar errores de integración.

### Agente determinístico Java

El agente de esta tarea será responsable de:

- Consumir el contrato.
- Aplicar reglas explícitas.
- Evaluar la calidad mínima de la entrada.
- Generar una decisión estructurada.
- Indicar bloqueos y necesidad de revisión.

### Futuro agente real de IA

En una etapa posterior podrá existir un servicio separado:

```text
Java interoperability-service
        ↓
Model Boundary Contract v1
        ↓
Python ai-service
        ├── OpenAI / LLM
        ├── RAG
        ├── LangGraph
        ├── Memoria conversacional
        └── Herramientas controladas
```

## 11. Criterios de aceptación

- [x] El agente está ubicado en un paquete separado de la interoperabilidad.
- [x] El agente recibe únicamente contratos autorizados.
- [x] No existe acceso directo a Epic, Oracle, FHIR o HAPI FHIR.
- [x] Las reglas son determinísticas y reproducibles.
- [x] La salida tiene una estructura estable.
- [x] Se identifican entradas inválidas.
- [x] Se identifican advertencias del pipeline.
- [x] Se marca cuándo se requiere revisión humana.
- [x] No se registran secretos ni datos clínicos sensibles.
- [x] Se agregan pruebas unitarias.
- [x] Se ejecuta `mvn test`.
- [x] Se verifica que no se modifican archivos `.env`.
- [x] Se actualiza la documentación de arquitectura si corresponde.

## 12. Pruebas mínimas

Se deben cubrir al menos estos escenarios:

### Caso 1 — Entrada válida

```text
Contrato válido
Pipeline SUCCESS
Sin advertencias críticas
Resultado esperado: READY
```

### Caso 2 — Contrato inválido

```text
Contrato inválido
Resultado esperado: BLOCKED
```

### Caso 3 — Pipeline con error

```text
Pipeline FAILED
Resultado esperado: BLOCKED o REQUIRES_HUMAN_REVIEW
```

La decisión exacta debe seguir las reglas existentes del proyecto.

### Caso 4 — Advertencias no críticas

```text
Contrato válido
Pipeline SUCCESS
Advertencias no críticas
Resultado esperado: READY con warnings
```

### Caso 5 — Información insuficiente

```text
Faltan campos obligatorios
Resultado esperado: REQUIRES_HUMAN_REVIEW o BLOCKED
```

## 13. Endpoint opcional

Solo si no existe una superficie adecuada para integrar el agente, se puede evaluar un endpoint de laboratorio:

```http
POST /lab/deterministic-agent
```

El endpoint debe ser:

- Exclusivamente de laboratorio.
- Claramente identificado.
- Sin exponer información clínica sensible.
- Sin reemplazar los contratos internos.
- Sin convertirse todavía en una API de producción.

Si ya existe un `AgentStub` o una superficie equivalente, debe preferirse su reutilización en lugar de crear un endpoint duplicado.

## 14. Relación con el agente real

La Tarea 057 no es el agente inteligente final. Es una validación inicial de la frontera arquitectónica.

La evolución esperada es:

```text
Etapa 1:
Java → agente determinístico

Etapa 2:
Java → servicio de IA → LLM

Etapa 3:
Java → servicio de IA → LLM + RAG

Etapa 4:
Java → servicio de IA → LangGraph + memoria + herramientas

Etapa 5:
Java → Python AI Service → agentes especializados supervisados
```

La interoperabilidad continuará en Java. Python podrá utilizarse posteriormente para el servicio de IA porque ofrece un ecosistema amplio para LLM, RAG, embeddings, LangGraph y evaluación de agentes.

## 15. Resultado esperado

Al finalizar la Tarea 057, el proyecto debe demostrar que:

```text
Datos clínicos interoperables
        ↓
Contrato clínico controlado
        ↓
Agente aislado y determinístico
        ↓
Resultado estructurado y auditable
```

Esto permitirá incorporar posteriormente un LLM real sin conectar el modelo directamente con los sistemas clínicos ni romper las fronteras de seguridad e interoperabilidad.
