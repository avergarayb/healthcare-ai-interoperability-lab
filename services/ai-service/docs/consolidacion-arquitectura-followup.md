# Auditoría de convergencia del follow-up

Estado productivo: `POST /internal/agent/follow-up` llama a `FollowUpWorkflow.run()`. El runtime, el prompt, la traza, la evaluación, las tools, los fixtures y la policy del follow-up antiguo ya no están en el árbol. `GeminiProvider.generate_summary()` sigue en el resumen experimental.

El texto desde la sección A es el diagnóstico histórico, anterior a esa eliminación. No describe el código actual.

La versión instalada es `langgraph==1.2.12`.

## A. Arquitectura actual

```text
POST /internal/agent/follow-up          POST /internal/experimental-summary
        |                                          |
        v                                          v
followup_service                            LLMProvider.generate_summary
        |                                          |
        v                                          v
FollowUpRuntime.run                         GeminiProvider
  while True
  followup_prompt + parse_agent_message
  followup_policy + followup_tools (fixtures)
  followup_trace
        |
        v
FollowUpResponse

FollowUpWorkflow.run                 no está conectado al endpoint
        |
        v
GeminiFhirFollowUp (StateGraph)
  agent -> gemini_followup_message
  route_after_agent llama evaluate_tool_policy y record_policy_audit
  ToolNode -> get_patient_followup_context
        -> FollowUpFHIRAdapter -> ClientFHIRTransport -> HapiReadClient -> HAPI
        |
        v
FollowUpWorkflowResult

select_laboratory_response -> adapter -> FollowUpResponse
  no lo usa main.py
```

El workflow vivo importa `langgraph_followup_workflow.py`, `langgraph_gemini_fhir_followup.py`, `langgraph_fhir_followup.py` (adapter y tool), `langgraph_fhir_client.py` (policy, audit, transport), `langgraph_fhir_hapi.py` y tres símbolos de `langgraph_gemini_tool_calling.py`. El resto de módulos `langgraph_*.py` no entra en esa cadena.

## LangGraph 1.2.12 frente a la aplicación

Comprobado en el paquete instalado:

| Capacidad de la librería | Dónde está | Qué hace este repositorio | Quién debe poseerla |
| --- | --- | --- | --- |
| Estado y ejecución del grafo | `StateGraph` | `GeminiFollowUpState` y `invoke` | LangGraph |
| Routing condicional | aristas condicionales | `route_after_agent` | LangGraph ejecuta la rama. La aplicación decide allowed o denied antes de elegirla |
| Ejecución de tools | `ToolNode` | Una tool, después de la rama `tools` | LangGraph ejecuta. La aplicación autoriza |
| Ciclos | arista de vuelta al agente | tool result -> agente | LangGraph |
| Tope del grafo | `RunnableConfig.recursion_limit`, default 25; si se agota, `GraphRecursionError` | C16 no pasa `recursion_limit`. Corta en `MAX_MODEL_TURNS = 4` dentro del nodo agente | El 25 es un fusible del motor. El 4 es regla de aplicación. No son el mismo límite |
| Errores | la excepción sale de `invoke` | Lectura FHIR -> `unavailable`, salvo `transport failed`. Error de Gemini se propaga. No hay reintento | LangGraph propaga. La aplicación clasifica |
| Checkpoints | `compile(checkpointer=...)` | Ningún grafo lo usa | No hace falta para una petición síncrona de solo lectura |
| Interrupción | `interrupt_before` / `interrupt_after` | No se usa | No es `requiresHumanReview` |
| Callbacks | config de runnable | No se usan | No mover la autorización a un callback |

`ToolNode.__init__` acepta `wrap_tool_call`. Eso puede envolver la ejecución. No es el lugar de la policy. La policy sigue en `evaluate_tool_policy()`, llamada desde el routing, fuera del grafo como nodo.

## Gemini

`google.genai` hace la llamada HTTP, declara funciones y adjunta `thought_signature` al `Part`. El puente `gemini_followup_message` elige el modelo, arma `contents`, guarda la firma en `AIMessage.additional_kwargs` y la devuelve en el siguiente `Part`. Esa pieza sí tiene una razón: el SDK no habla el estado de LangGraph.

`GeminiProvider.generate_text()` no tiene esa razón para el follow-up. Llama a `generate_content` con un string, sin tools y sin firma. Existe porque C15 implementaba el ciclo a mano. `generate_summary()` es otra ruta, la del resumen experimental, y ahí el provider sigue teniendo trabajo.

## B. Responsabilidades duplicadas

| Responsabilidad | C15 | C16 | Decisión |
| --- | --- | --- | --- |
| Orquestación agente / tool / agente | `FollowUpRuntime.run` | `GeminiFhirFollowUp` | MIGRATE el endpoint al workflow. DELETE_LATER el `while` |
| Segundo grafo sin Gemini | — | clase `FollowUpWorkflow` en `langgraph_fhir_followup.py` | DELETE_LATER esa clase. KEEP el adapter del mismo archivo |
| Tool calling | JSON `tool_call` / `final` en texto | `AIMessage.tool_calls` y function calling | DELETE_LATER el protocolo de texto |
| Control de vueltas | reloj de 30 s y máximo de 6 tools | `MAX_MODEL_TURNS = 4` en el nodo. El fusible 25 de LangGraph no se configura | MIGRATE la regla de producto al límite de 4. DEPRECATE el reloj y el máximo de 6. No sustituir el 4 por `recursion_limit` |
| Policy de tools | `followup_policy` sobre seis tools de fixture | `evaluate_tool_policy` sobre la tool de lectura HAPI | MIGRATE la autorización viva. DELETE_LATER la allowlist de fixtures y las copias de `langgraph_policy_boundary.py` y `langgraph_policy_audit.py` |
| Validación de salida clínica | `validate_output` exige acciones, evidencia C15 y revisión humana | No existe | DEPRECATE. No portarla al grafo |
| Auditoría de autorización | eventos `POLICY_CHECK` dentro de `followup_trace` | `record_policy_audit` / `PolicyAuditEvent` | KEEP la auditoría C16. No es una traza de producto |
| Traza del bucle | `AgentEvent` en memoria | no hay equivalente | DELETE_LATER con el runtime. La línea de log HTTP se conserva |
| Provider de texto | `GeminiProvider.generate_text` | `gemini_followup_message` | DELETE_LATER el uso desde el follow-up. KEEP `generate_summary` |
| Configuración Gemini | `Settings` | `_gemini_config()` lee otra vez el entorno | MIGRATE el workflow a `Settings` |
| Contrato de salida | `FollowUpResponse` | `FollowUpWorkflowResult` más un adapter que rellena huecos | KEEP el resultado del workflow. DEPRECATE el adapter. El HTTP cambia de contrato en la migración |
| Errores de proveedor | un reintento con backoff y `PROVIDER_ERROR` | la excepción sale. No hay reintento | DELETE_LATER el backoff del follow-up. No está demostrado en el camino HAPI |
| Lectura clínica | seis tools sobre fixtures | Patient y Observation en HAPI | MIGRATE esas dos. DELETE_LATER encounters, conditions, medications y appointments: no hay implementación real que las reemplace |
| Lecciones C16 sueltas | — | módulos que el workflow no importa | DELETE_LATER |

## C. Código candidato a eliminar

Cada pieza se va cuando el reemplazo ya está en el camino único. No antes.

| Pieza | Qué la reemplaza |
| --- | --- |
| `FollowUpRuntime`, `parse_agent_message`, recuperación de JSON | `GeminiFhirFollowUp` y `ToolNode` |
| `followup_prompt.py` | `SYSTEM_INSTRUCTION` más la declaración de la función. El prompt JSON no se porta |
| `followup_trace.py` y `followup_evaluation.py` | Nada de C16 los reemplaza como traza. Se van porque describen el bucle que desaparece. La auditoría de policy no los sustituye |
| `followup_tools.py`, `followup_fixtures.py` | `make_followup_tool` y HAPI para Patient y Observation. Las otras cuatro lecturas no tienen reemplazo; se eliminan como alcance no demostrado, no como migración |
| Allowlist y `validate_output` de `followup_policy.py` | `evaluate_tool_policy()` para autorizar. La validación de salida no se reemplaza: se retira |
| `GeminiProvider.generate_text` usado por el follow-up | `gemini_followup_message` |
| Clase grafo `FollowUpWorkflow` en `langgraph_fhir_followup.py` | `FollowUpWorkflow` de `langgraph_followup_workflow.py` |
| Grafo `FHIRBoundary` en `langgraph_fhir_client.py` | `GeminiFhirFollowUp` |
| `langgraph_basics.py`, `langgraph_loop_prototype.py`, `langgraph_agent_loop.py`, `langgraph_tools.py`, `langgraph_structured_state.py`, `langgraph_architecture_comparison.py`, `langgraph_architecture_decision.py`, `langgraph_policy_boundary.py`, `langgraph_policy_audit.py`, `langgraph_clinical_tool.py`, `langgraph_fhir_adapter.py`, `langgraph_fhir_transport.py` | El camino vivo. No aportan una responsabilidad que ese camino no tenga ya |
| Grafo de lección dentro de `langgraph_gemini_tool_calling.py` | `gemini_followup_message`. Se conservan `MAX_MODEL_TURNS`, `_gemini_config` y `_tool_payload` hasta moverlos |
| `langgraph_followup_response_adapter.py` | No debe reemplazarse por otro adapter. Sobrevive el resultado del workflow y, después, un cuerpo HTTP más chico |

## D. Código que debemos conservar

| Pieza | Motivo |
| --- | --- |
| `main.py` | Procesos HTTP que no son el bucle: salud, contexto, resumen experimental y el follow-up |
| `followup_service.py` | Auth, flag, `FollowUpRequest`, 401, 422, 503 y el log de una línea. Cambia la llamada interna en la fase 2; el borde se queda |
| `config.py` | Una sola configuración del proceso |
| `FollowUpRequest` | Entrada cerrada del endpoint |
| `LLMProvider.generate_summary` y `GeminiProvider` para el resumen experimental | C16 no cubre `POST /internal/experimental-summary` |
| `FollowUpWorkflow.run` y `FollowUpWorkflowResult` | Única fachada de aplicación del grafo. Oculta mensajes y `ToolNode` |
| `GeminiFhirFollowUp` y `gemini_followup_message` | Orquestación y puente con `thought_signature` |
| `evaluate_tool_policy`, `record_policy_audit`, `PolicyAuditEvent` | Autorización y su registro. Siguen fuera del grafo |
| `FollowUpFHIRAdapter`, `make_followup_tool`, `ClientFHIRTransport`, `HapiReadClient` | Lectura real. HTTP y FHIR no entran al grafo |
| `service_auth.py` | Auth del servicio. No es parte del workflow |

`patient`, `observations`, `tools_used` y `turns` pueden seguir en el resultado de laboratorio hasta la fase 2. No entran al contrato HTTP. `tools_used` y `turns` son metadata de ejecución. El paciente y las observaciones son contexto clínico interno, no el cuerpo de la respuesta.

## E. Código que debe migrarse

| Desde | Hacia |
| --- | --- |
| Llamada `run_followup_agent` en `followup_service.py` | `FollowUpWorkflow.run` |
| Lectura Gemini del workflow | `Settings.gemini_api_key` y `Settings.gemini_model` |
| `run_id` creado con `uuid` dentro de `FollowUpRuntime` | El mismo id que la aplicación ya puede inyectar. Un solo id por ejecución, compartido con la auditoría |
| Estado `finish` / `denied` / `unavailable` / `limit` | Esos cuatro valores en el cuerpo HTTP. No traducir `unavailable` ni `limit` a `PROVIDER_ERROR` |
| `final_answer` | Un solo campo de texto en la respuesta |
| Token `follow_up_required` | El mismo token, o `unknown` si el modelo no lo emitió |
| Evidencia `{tool, resources}` | Referencias, sin renombrar `get_patient_followup_context` a una tool de C15 |
| Conteos de llamadas al modelo, si el HTTP todavía los publica | Un contador real en el resultado. Hoy `model_calls` vive en el motor y no en `FollowUpWorkflowResult` |

## F. Contrato de aplicación recomendado

No adaptar C16 hacia el `FollowUpResponse` actual. Ese modelo describe el agente de texto: identidad de prompt, acciones sugeridas, evidencia contra tools de fixture y `requiresHumanReview` forzado a `true`. El adapter ya inventa parte de eso para que Pydantic construya el objeto. Convergir significa que C15 deje ese cuerpo, no que el workflow lo imite.

Contrato interno, el que ya existe y debe quedar:

```text
FollowUpWorkflowResult
  run_id
  case_id
  status                  finish | denied | unavailable | limit
  final_answer
  follow_up_required      true | false | unknown
  evidence                tool + referencias
```

Contrato HTTP después de la migración:

```text
runId
caseId
status                  completed | denied | unavailable | limit
followUpRequired        true | false | unknown
answer
evidence                [{ tool, reference }]
```

| Campo actual | Destino |
| --- | --- |
| `runId` | Aplicación lo crea, el workflow lo repite, el HTTP lo publica |
| `caseId` | Petición y workflow |
| `status` | Workflow, con el vocabulario de arriba. `DISABLED` ya no viaja en el cuerpo: el servicio responde 503. `VALIDATION_ERROR` de JSON y `PROVIDER_ERROR` de reintento se retiran con el runtime |
| `followUpRequired` | Workflow, solo desde metadata estructurada |
| `summary` y `reason` | Se funden en `answer`. El partido actual es una adaptación al contrato viejo |
| `evidence` | Workflow. Cambia la forma. No se finge compatibilidad con la allowlist C15 |
| `modelCalled` | Observabilidad. Sale del cuerpo hasta que el resultado guarde un conteo real |
| `agent`, `agentVersion`, `promptVersion` | Dejan de existir en la respuesta. Son constantes del diseño viejo |
| `suggestedActions` | Deja de existir. No hay fuente estructurada |
| `requiresHumanReview` | Deja de existir como campo. La regla de revisión humana, si el producto la mantiene, se documenta fuera del payload |

`FollowUpRequest` se conserva.

## G. Plan de depuración

### Fase 1 — Consolidar

Sin cambiar `main.py` ni el cuerpo HTTP. Un solo camino de laboratorio, todavía desconectado.

Archivos:

- `app/langgraph_followup_workflow.py`
- `app/langgraph_gemini_fhir_followup.py`
- `app/langgraph_fhir_followup.py`
- `app/langgraph_fhir_client.py`
- `app/langgraph_fhir_hapi.py`
- `app/langgraph_gemini_tool_calling.py`
- `app/config.py`
- `app/langgraph_followup_response_adapter.py` solo para dejar de derivar campos; si no aporta, se deja de usar
- tests del camino vivo: `test_langgraph_followup_workflow.py`, `test_langgraph_gemini_fhir_followup.py`, `test_langgraph_fhir_hapi.py`

Trabajo: el workflow lee `Settings`; el resultado no gana campos de C15; policy y audit siguen como funciones; no se crea otro módulo de orquestación.

### Fase 2 — Migrar C15

El endpoint llama al workflow. El cuerpo HTTP pasa al contrato de la sección F.

Archivos:

- `app/followup_service.py`
- `app/followup_models.py` para el contrato nuevo, sin rellenar el viejo
- `app/main.py` solo si el follow-up deja de pedir `GeminiProvider`
- `tests/test_followup_service.py`
- `tests/test_followup_models.py`

Auth, flag, 401, 422 y 503 se quedan. No se reescribe `FollowUpRuntime` para que use LangGraph por dentro.

### Fase 3 — Eliminar legado

Archivos de producción C15:

- `app/followup_runtime.py`
- `app/followup_prompt.py`
- `app/followup_trace.py`
- `app/followup_evaluation.py`
- `app/followup_tools.py`
- `app/followup_fixtures.py`
- `app/followup_policy.py`

Tests C15 que protegen ese bucle:

- `test_followup_runtime.py`
- `test_followup_recovery.py`
- `test_followup_prompt.py`
- `test_followup_trace.py`
- `test_followup_evaluation.py`
- `test_followup_tools.py`
- `test_followup_fixtures.py`
- `test_followup_policy.py`
- `test_followup_provider_backoff.py`
- `test_followup_provider_retry.py`
- `test_followup_provider_lifecycle.py`
- `test_followup_gemini_boundary.py`
- `test_followup_live.py`

Lecciones y sus tests, más `app/langgraph_followup_response_adapter.py` y `tests/test_langgraph_followup_response_adapter.py`.

`gemini_provider.py` y `llm_provider.py` se quedan por el resumen experimental. `fake_llm_provider.py` se queda si ese resumen lo usa.

## Tests que protegen la arquitectura final

Deben quedar, concentrados en el camino único:

- auth, flag, petición inválida y 503, hoy en `test_followup_service.py`;
- una ejecución de `FollowUpWorkflow` con modelo scripted: denied no ejecuta la tool, la tool autorizada lee, el límite de 4 no llama otra vez al modelo, el id inyectado sale en el resultado y en la auditoría;
- la firma de pensamiento se conserva entre dos llamadas, hoy en `test_langgraph_gemini_fhir_followup.py`;
- HAPI, detrás del flag que ya existe, en `test_langgraph_fhir_hapi.py`;
- el resumen experimental y su provider, fuera de este workflow.

Obsoletos después de migrar: los de la fase 3. Duplicados de laboratorio: un test por lección que vuelve a demostrar estado, routing o policy con datos sintéticos distintos. No hace falta conservarlos para proteger el producto.

No se añaden tests en este diagnóstico.
