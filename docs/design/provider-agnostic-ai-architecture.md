# Arquitectura de modelos agnóstica al proveedor

Estado: bridges OpenAI y Gemini sobre el gateway neutral, en `feature/enterprise-ai-processing-authorization-task-c04-live-smoke`, sin commit y sin egress. Los adaptadores y transportes existentes se reutilizan. El detalle de esos bordes está en el [runbook C04](enterprise-ai-processing-task-c04-provider.md).

## Arquitectura modular

El agente declara el caso de uso, las capacidades, el presupuesto y el contexto autorizado. `NeutralModelGateway` elige un despliegue del catálogo y llama a un adaptador. El adaptador traduce la petición y devuelve una respuesta normalizada. El grounding de `check_observation` corre después y no pertenece al proveedor.

`OpenAISdkBridge` y `GeminiSdkBridge` traducen la petición neutral al permiso y a la lectura que ya exigen los adaptadores existentes. Esos adaptadores conservan el parser, el validador y el transporte. El módulo del bridge no importa un SDK. El transporte predeterminado sigue deshabilitado. Las pruebas de integración construyen el cliente oficial con un transporte HTTP simulado: `httpx2.MockTransport` para OpenAI y `httpx.MockTransport` para Gemini. El SDK instalado publica `model_version`; el normalizador de Gemini acepta ese campo y también el atributo `model` de los sustitutos anteriores.

MCP sigue siendo la frontera de herramientas y RAG la de recuperación. Ninguno de los dos forma parte de este contrato ni depende de un SDK.

`GatewayResult` publica aceptación, motivo, despliegue, organización autorizada, tokens y reservas. No publica días, meses, extracto ni texto del proveedor. No hay `get_answer`, `get_candidate` ni `get_grounding`, ni una consulta por `operation_id`. `public_state` rechaza una organización distinta de la que autorizó la ejecución. La observación se comprueba dentro de la llamada y no se conserva. Esto no sustituye la autorización de entrega de C03. Los tokens no reconstruyen el documento.

## Interfaces comunes

El paquete `app/model_gateway` define `ModelIdentity`, `ModelDeployment`, `ModelCapabilities`, `ModelRequest`, `ModelResponse`, `UsageMetadata`, `ExecutionContext`, `ExecutionGrant`, `ExecutionPolicy` y `GatewayResult`. El error común es `ProviderError`: solo expone un código.

`ModelRequest` lleva el caso, la organización, el principal, el recurso y el texto fijo. No tiene endpoint, herramientas ni parámetros de un proveedor. Esas traducciones viven en el adaptador. `ExecutionGrant` repite principal y recurso para que la política los compare con el contexto. `ExecutionPolicy` fija una invocación, prohíbe el fallback y prohíbe el egress. No se puede construir una política que abra esas puertas.

Cada adaptador ofrece `capabilities`, `validate_request`, `estimate_cost`, `invoke_once` y `normalize_response`.

## Registry

`ProviderRegistry` nace con un catálogo fijo. `register` rechaza cualquier alta, incluida una URL. Un despliegue tiene `deployment_id`, proveedor, `model_id`, ubicación, capacidades, política de datos, reserva y organizaciones. El endpoint de todos los despliegues actuales es nulo.

La identidad lógica y el despliegue están separados. `private-vacation-extractor-v1` existe dos veces: `private-offline-a` para ORG-A y `private-offline-b` para ORG-B. El mismo modelo no comparte permiso. Los bridges usan `openai-sdk-a` y `gemini-sdk-a`, también sin endpoint y solo para ORG-A. El catálogo no admite un alta con datos del usuario.

## Capacidades

El catálogo conoce texto, salida estructurada, herramientas, streaming, visión, ventana de contexto, contabilidad de tokens, control de razonamiento y reporte de uso. Embeddings quedan fuera de este contrato y seguirían otro, como ya hace el borde clínico de embeddings.

El caso `vacation-days-v1` exige `structured_output` y `usage_report`. `text-only-offline-a` está registrado y solo ofrece texto, así que la operación termina en `capability_denied` antes de invocar. No hay un camino que acepte JSON no validado en su lugar.

## Políticas de selección y destino

La autorización compara organización, principal, recurso, propósito, clasificación, proveedor, despliegue, capacidades, presupuesto y revisión. El propósito y la clasificación son los sintéticos ya usados por el permiso remoto. Un grant de `openai` contra el despliegue Gemini es `remote_not_authorized`. Un modelo local también exige ese grant: estar en proceso no lo autoriza.

`execute` rechaza cualquier URL aportada por el caller, aunque coincida con un host conocido. Una resolución que cambia entre dos lecturas y un estado HTTP 301, 302, 303, 307 o 308 producen `destination_denied`. Esos controles no abren un socket. Un cliente live futuro tendría que fijar la dirección del despliegue registrado y repetirlos antes de enviar.

## Adapters

| Adaptador | Protocolo interno | SDK |
|---|---|---|
| `OpenAISdkBridge` sobre `OpenAIResponsesAdapter` | Responses, `gpt-6-luna`, `store=false`, `reasoning.effort=none` | Sí, envío cerrado. Despliegue `openai-sdk-a` |
| `GeminiSdkBridge` sobre `GeminiResponsesAdapter` | generateContent, `gemini-3.5-flash-lite`, salida 128, pensamiento `MINIMAL` | Sí, envío cerrado. Despliegue `gemini-sdk-a` |
| `OfflineResponsesAdapter` | `offline-responses-shape` | No |
| `OfflineGeminiAdapter` | `offline-generate-content-shape` | No |
| `PrivateCustomAdapter` | `custom-json-v1` | No |

`VacationClauseAgent` solo llama a `gateway.execute`. No conoce el protocolo privado ni los nombres de los SDK. Cambiar de adaptador no cambia el agente ni el grounding.

Anthropic, otros proveedores de nube y un endpoint compatible con OpenAI no están implementados. Un `deployment_id` ausente del catálogo es `model_unregistered`.

## Aislamiento y costo

Los despliegues offline reservan una cota de planificación: 191 micro-USD para OpenAI y 470 para Gemini. Los despliegues SDK reservan el payload fijo: 303 micro-USD para OpenAI y 657 para Gemini, ambos bajo el techo de 1.000. El protocolo privado reserva 1 micro-USD de contabilidad, no una factura de proveedor. El presupuesto del contexto tiene que cubrir la reserva del despliegue elegido. Por debajo, `budget_exceeded` ocurre antes de la invocación.

El costo estimado de la respuesta no se presenta como cargo confirmado. Si falta el usage, el resultado es `consumption_ambiguous` y el despliegue queda gastado: no hay segundo intento ni otro proveedor.

## Seguridad

No hay fallback. Un fallo de OpenAI no llama a Gemini. Un consumo ambiguo, un timeout, un 429 o un 5xx no se reenvían. El documento fijo no entra en `repr`, en el estado público ni en el código de error. Los despliegues tienen egress cerrado. `OpenAISDKTransport.send` y `GeminiSDKTransport.send` siguen bloqueados. La política de datos de laboratorio es `synthetic-only-no-retention-claim`: no afirma retención cero del proveedor.

El aislamiento de esta fase no es criptográfico. Otro código del mismo proceso puede construir un cliente SDK si posee la clave. El gateway impide que el agente y el caller elijan un destino; no impide una llamada directa hecha fuera de este camino.

El bridge conserva el cuerpo del proveedor en una sola referencia mientras normaliza. Al terminar, en éxito o en fallo, esa referencia se suelta. No es un borrado criptográfico de la memoria del proceso ni un cache.

`execute` solo devuelve `accepted` cuando el grounding pasa. Si falla, el caller recibe el código (`candidate_rejected`, `excerpt_mismatch`, `model_refusal` u otro) y no el documento ni las cifras. Con el fixture sintético fijo, ese código no revela un documento real. Antes de conectar el gateway a C03 o de admitir otro documento, hay que revisar si esos códigos pueden salir antes de la autorización de entrega.

## Conexión futura con C03 y otros agentes

C03 sigue exigiendo `FakeEnterpriseModel`. Este gateway no está importado por ese flujo ni cambia Gate C, el perfil fake ni la entrega. Conectarlo después exigiría un camino distinto del perfil fake, la migración 003 para un permiso durable por despliegue y auditoría propia. Esos cambios no están hechos.

El grafo clínico de seguimiento todavía importa el SDK de Gemini dentro del módulo de LangGraph y en su proveedor clínico. Esta base no lo migra. En el camino empresarial, `openai` solo se importa desde `enterprise_llm_providers/transport.py` y `google` solo desde `gemini_transport.py`. Las versiones declaradas son `openai==3.49.0` y `google-genai==2.24.0`.

`PrivateCustomAdapter` demuestra un protocolo distinto dentro del proceso. No abre un modelo autoalojado ni un endpoint privado.

Los permisos del gateway y de los bridges viven en memoria. No se persisten y no autorizan otra organización, otro principal ni otro proveedor. Una llamada live sigue exigiendo, aparte, confirmación de facturación, una sola ejecución y la frase interactiva del runbook C04. Este diseño no deja esa llamada hecha.

## Prueba de esta base

| Requisito | Prueba |
|---|---|
| Mismo caso, dos proveedores y protocolo privado | `test_two_offline_adapters_serve_the_same_use_case_without_a_sdk`, `test_both_sdk_bridges_answer_the_same_case_for_one_agent` |
| Registry cerrado, capacidad, grant cruzado, organización, principal, propósito, presupuesto | `test_registry_selection_fails_closed`, `test_a_shared_unapproved_purpose_is_denied` |
| Credencial o bridge reasignado no cruza el grant; metadata de otra organización | `test_credential_and_rewired_bridge_cannot_cross_the_grant` |
| Malformado, rechazo, usage, modelo, timeout, 429, 5xx, sin replay ni fallback | `test_openai_sdk_errors_send_once_and_do_not_fall_back`, `test_gemini_sdk_errors_send_once_and_do_not_fall_back` |
| Grounding negativo, UTF-8 y contradicción | `test_shared_grounding_rejects_the_same_bad_observation`, `test_utf8_boundary_and_contradiction_stay_in_the_shared_validator` |
| Versiones e imports | `test_requirements_have_no_language_model_or_clinical_clients`, `test_openai_import_is_limited_to_the_sdk_transport`, `test_c04_package_has_no_network_client_and_c03_fake_stays_bound` |
| Egress y live sin ejecutar | `test_default_sdk_bridges_do_not_send`, `test_live_edges_remain_blocked` |
| El cuerpo del proveedor no queda en el bridge | `test_provider_body_is_released_after_success_and_failure` |
| C03 en el fake | `test_results_logs_and_c03_do_not_carry_the_fixture` |
