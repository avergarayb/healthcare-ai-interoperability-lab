# TASK-C04 Phase A — frontera OpenAI, sin egress

Estado: Phase A y Phase B integradas por el PR #124, merge `a7e6739246db37ec90e21c2903ec3f8d1f019b99`. El commit funcional es `f39199392194a997fc72ceadde328054c7add508`. Phase C de OpenAI quedó en `feature/enterprise-ai-processing-authorization-task-c04-live-smoke`, fusionada por el PR #125. El transporte público de OpenAI y de Gemini sigue cerrado. Gemini consumió dos solicitudes reales; no queda autorización para una tercera.

Base de C03: `origin/main` anterior `47cb35a723754136bdca596ce062062422d19108`, merge del PR #123. El commit funcional de C03 E2E es `c7b83ed2af0e0abe60b38c0dfd46a05c277a9215`.

## Arquitectura

El paquete `app/enterprise_llm_providers/` queda fuera de `enterprise_ai_processing`. No modifica el gateway, el fake, el ledger ni el grafo. `EnterpriseModelGateway` sigue exigiendo `type(self.model) is FakeEnterpriseModel`.

El adaptador separa configuración, permiso remoto en memoria, construcción del payload, transporte, validación y precio. El transporte predeterminado sigue siendo `DisabledOpenAITransport`. `OpenAISDKTransport` existe y no envía.

`requirements.txt` fija `openai==3.49.0`. Esa distribución usa `httpx2`, distinto del `httpx` de la aplicación. La instalación en el venv solo añadió `jiter==0.19.0` y el SDK. Python del entorno: 3.13.14. El paquete declara compatibilidad con 3.13 y Windows. El único módulo de aplicación que importa `openai` es `enterprise_llm_providers/transport.py`. La llamada documentada por el SDK es `client.responses.create(...)`.

## Modelo y API

Modelo elegido: `gpt-6-luna`, documentado en https://developers.openai.com/api/docs/models/gpt-6-luna. La página lo identifica así, admite Responses y Structured Outputs, ventana de 1.050.000 tokens, máximo de salida 128.000 y `reasoning.effort` con valor `none`.

La guía de texto usa `gpt-6-astra` como ejemplo general. No se seleccionó: el Product Owner nombró Luna y no se copió un precio de Astra que esta lectura no verificó.

`store` en Responses tiene default `true`. Si se omite, la referencia dice que la respuesta se conserva al menos 30 días. El payload fija `store=false`, `service_tier=default`, `max_output_tokens` entre 16 y 256, y `reasoning.effort=none`. No envía `tools`. El mínimo 16 de `max_output_tokens` sale de la referencia de `responses.create`.

## Datos y retención

C03 autoriza un fake interno. No autoriza sacar el documento del proceso. El payload lleva las instrucciones fijas, `question_id=vacation-days-v1` y el texto sintético dentro de `<source>`. No lleva principal, organización, grants, credencial ni metadatos del conector. El documento va en `input`; las instrucciones declaran que ese contenido no puede cambiarlas.

`store=false` no es Zero Data Retention. La guía https://developers.openai.com/api/docs/guides/your-data dice que los logs de abuso pueden conservar contenido hasta 30 días, salvo aprobación de Zero Data Retention o Modified Abuse Monitoring. En Zero Data Retention, `store` se trata como `false` aunque el cliente pida `true`. `/v1/responses` figura como elegible, pero la elegibilidad no sustituye esa aprobación. Tampoco elimina otras retenciones que el proveedor documente para herramientas o estado de aplicación. Este adaptador no usa herramientas.

La clave `OPENAI_API_KEY` solo se acepta desde un mapping o, en el futuro, desde el entorno. No se escribe en el payload, en `repr`, en logs ni en archivos del repositorio. No se pidió ni se comprobó una clave real. Una suscripción de ChatGPT no se toma como crédito de API.

## Permiso remoto

La lectura, el procesamiento fake, el procesamiento remoto, el grounding y la entrega derivada siguen siendo autoridades distintas. El permiso remoto es `RemoteExecutionPermit`: organización, principal, instancia, recurso, propósito, clasificación `synthetic-internal`, proveedor `openai`, modelo `gpt-6-luna`, `vacation-days-v1`, revisión, vigencia y presupuesto. Vive en memoria. No hay fila SQLite.

El perfil `fake-enterprise-extractive-v1` no puede representar a OpenAI. La migración 001 fija `provider='fake'`, `model_id='fake-enterprise-extractive-v1'` y `destination='in-process-offline'`. Reutilizarlo sería eludir el esquema.

### Migración 003, solo diseño

Haría falta una tabla nueva, por ejemplo `aip_remote_execution_permit`, con esos campos y un destino distinto del fake. No se ampliaría el `CHECK` del perfil fake ni el de la auditoría V2. No se implementó y no se creó el archivo SQL.

## Esquema y grounding

Structured Outputs admite objeto, booleano, entero, cadena, enum y `anyOf`, con `additionalProperties: false`, `strict: true` y todos los campos en `required`. El esquema `vacation_clause_observation` usa ese subconjunto: `question_id`, `evidence_found`, `proposed_days`, `proposed_months`, `source_excerpt`, `evidence_start`, `evidence_end` y `refusal_or_insufficient`. Los enteros ausentes van por `anyOf` con `null`. La raíz no es `anyOf`.

Cumplir el esquema no acredita la cifra. El validador local exige UTF-8, offsets en frontera de carácter, fragmento idéntico a `source[start:end]`, una sola cláusula `VACACIONES: N dias tras M meses de servicio.` y números iguales a esa cláusula. Dos cifras distintas producen `contradictory_source`. Una cifra inventada, un fragmento distinto, un offset inválido, un rechazo, un JSON inválido o una salida incompleta fallan cerrados. El adaptador no construye la frase «Según el documento consultado…».

## Errores y reintentos

No hay reintento automático. El envío marca la invocación como gastada antes de llamar al transporte; un segundo `observe` devuelve `replay_denied`. Un fallo local anterior al envío no consume esa marca.

Códigos cerrados, sin cuerpo remoto: `remote_disabled`, `not_configured`, `credential_absent`, `model_denied`, `remote_not_authorized`, `budget_exceeded`, `invalid_input`, `timeout`, `rate_limited`, `remote_unavailable`, `incomplete_output`, `invalid_output`, `model_refusal`, `invalid_offset`, `excerpt_mismatch`, `candidate_rejected`, `contradictory_source`, `consumption_ambiguous`. Si la respuesta llega sin `input_tokens` y `output_tokens`, el resultado no se acepta.

## Precios

Fuente: la página del modelo, consultada para esta tarea. Texto estándar: entrada $0,10 / 1M, entrada cacheada $0,01 / 1M, escritura de caché $0,125 / 1M, salida $0,50 / 1M. Por encima de 272.000 tokens de entrada, la misma página aplica 2× a la entrada y 1,5× a la salida de toda la solicitud. Batch y Flex están a la mitad; Fast, al doble. La reserva del laboratorio usa la tarifa de escritura de caché, no el descuento de caché, y fija `service_tier=default`.

Estimación estándar, no confirmada por el proveedor:

| Entrada | Salida | Una llamada | 100 | 1.000 |
|---|---:|---:|---:|---:|
| 500 | 200 | $0,000150 | $0,015 | $0,150 |
| 2.000 | 500 | $0,000450 | $0,045 | $0,450 |
| 8.000 | 1.000 | $0,001300 | $0,130 | $1,300 |

Esos importes son `estimate_microusd` sin techo de caché: 150, 450 y 1.300 micro-USD. El techo por llamada que rechaza el adaptador es más alto. La propuesta para una futura prueba real es 1.000 micro-USD por llamada ($0,001) y 5.000.000 micro-USD de tope de laboratorio ($5), con 256 tokens de salida como máximo. El gasto confirmado solo existirá cuando el proveedor devuelva `usage` en una llamada que el Product Owner haya autorizado. Esta ejecución no tiene gasto confirmado.

Los límites publicados de `gpt-6-luna` en el tier Build son 5.000 RPM y 2.000.000 TPM. No se usaron.

## Qué impide sustituir el fake

El SDK y la excepción de arquitectura ya están acotados al transporte. Siguen haciendo falta la migración 003, un perfil nuevo, un camino de gateway distinto de `FakeEnterpriseModel` y una autorización expresa de una sola llamada real. Un cambio de configuración no puede saltarse esos contratos.

## Phase B

`OpenAI()` en 3.49.0 usa `max_retries=2` y un timeout de 600 segundos si no se cambian. `OpenAISDKTransport` construye el cliente con `max_retries=0` y `httpx2.Timeout(15.0)`. No acepta `base_url`, proxy ni `http_client` del caller. `live_egress_enabled` devuelve falso en código; ni `OPENAI_API_KEY` ni `enabled=true` lo cambian. `send` valida el payload y termina en `egress_blocked` sin llamar a `responses.create`.

`dispatch_responses` es la llamada real `client.responses.create`, con `store=false`, `service_tier=default`, `reasoning.effort=none`, `stream=false`, `background=false`, sin `tools` y sin `previous_response_id`. Las pruebas la ejecutan con `httpx2.MockTransport`: el SDK arma la URL `api.openai.com` y la respuesta no sale del proceso. Un HTTP 429, un 500, un timeout y un fallo de conexión producen un solo intento. El cuerpo del error no pasa a la excepción. Si `response.model` no es `gpt-6-luna`, el resultado es `model_denied`. Sin `usage`, no hay éxito.

El dry-run `dry_run_fixed_fixture` no recibe documento ni transporte. Usa solo `VACACIONES: 20 dias tras 12 meses de servicio.` y un transporte interno simulado. No imprime el prompt. El permiso en memoria no autoriza egress ni se persiste. La migración 003 sigue diferida. Zero Data Retention no es requisito para este fixture sintético. C03 sigue en `FakeEnterpriseModel`.

El tope de US$5 es un contador de proceso, no un control del proveedor. Antes de una prueba real hace falta un presupuesto y alertas en el proyecto de OpenAI. El gasto de esta fase es cero.

## Phase C

El ejecutor aislado es `scripts/c04-openai-live-smoke/run_smoke.py`. Sin argumentos, o con `dry-run`, no abre un socket. Reutiliza el payload, el precio, `dispatch_responses` y el validador. No cambia `live_egress_enabled` ni el transporte predeterminado. `OpenAISDKTransport.send` sigue en `egress_blocked`. La llamada live, cuando el Product Owner la autorice, pasa por `open_official_client` y después por `dispatch_responses`.

```text
.\.venv\Scripts\python.exe ..\..\scripts\c04-openai-live-smoke\run_smoke.py dry-run
.\.venv\Scripts\python.exe ..\..\scripts\c04-openai-live-smoke\run_smoke.py live-once
```

El segundo comando no está autorizado todavía. Exige una terminal interactiva y la frase exacta `CONFIRMO UNA SOLICITUD openai gpt-6-luna vacation-days-v1 MAXIMO USD 0.001 PRESUPUESTO PLANIFICADO USD 5`. No acepta otro documento, pregunta, modelo, `base_url` ni una confirmación por variable o argumento. Una clave ausente se rechaza antes del envío. La clave se lee de `OPENAI_API_KEY` en el entorno del proceso; no se escribe en el repositorio ni se imprime.

Antes de construir el cliente, el proceso se detiene si existen `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `OPENAI_BASE_URL` u `OPENAI_CUSTOM_HEADERS`. El SDK usaría `OPENAI_BASE_URL` cuando no recibe `base_url`, y `httpx2` confía en el entorno de proxy. Esas variables no estaban definidas en esta sesión y `OPENAI_API_KEY` tampoco.

La reserva de esta fixture fue 303 micro-USD, bajo el techo de 1.000. El tope de US$5 sigue siendo un contador de proceso. El reporte marca `project_billing=unverified` y `provider_charge=unconfirmed`. No se comprobó un proyecto OpenAI, la facturación API, la disponibilidad del modelo, un límite mensual ni las alertas.

`live-once` crea `vacation-days-v1.attempt` con `O_EXCL` bajo `%LOCALAPPDATA%\healthcare-ai-interoperability-lab\c04-live-smoke` inmediatamente antes del envío. El archivo no guarda la clave ni el documento. Si el envío agota el tiempo, falla o devuelve una observación inválida, la marca permanece y la siguiente ejecución es `replay_denied`. Borrar la marca, usar otro directorio o llamar `dispatch_responses` desde otro código elude esa protección. No es idempotencia distribuida.

Un código del mismo proceso con la clave puede invocar el SDK sin este ejecutor. La fase evita el egress accidental del camino confiable; no aísla criptográficamente un proceso hostil.

El dry-run de esta sesión devolvió `PASS`, `requests_sent=0`, grounding `encontrado`, días 20 y meses 12, sin texto de la cláusula ni credencial.

## Pruebas de Phase B

`tests/test_enterprise_llm_provider.py`: 20 PASS en 0,69 s, basetemp `C:\Temp\c04b2`. Incluye el SDK real contra `httpx2.MockTransport`, `max_retries=0`, el dry-run fijo y el fake de C03 intacto.

`tests/test_architecture.py`: 9 PASS en 0,57 s. `tests/test_enterprise_ai_processing_architecture.py`: 51 PASS en 0,37 s. E2E C03: 34 PASS en 28,10 s. B2-GRD: 37 PASS en 21,81 s. B2-RUNTIME: 40 PASS en 15,20 s. B2-SRC: 34 PASS en 0,80 s. C01: 192 PASS en 0,30 s. C02: 233 PASS en 65,41 s. B1: 31 PASS en 5,88 s. Suites empresariales de conectores: 617 PASS y 1 SKIPPED en 515,20 s, basetemp `C:\Temp\c04bent`.

No se contactó local-hapi, Docker, Keycloak, Graph ni `api.openai.com`.

## Pruebas de Phase C

`tests/test_enterprise_llm_provider_live_smoke.py` y la regresión C04/arquitectura: 89 PASS en 3,30 s, basetemp `C:\Temp\c04c2`. El ejecutor aporta 9 pruebas. E2E C03: 34 PASS en 27,52 s. B2-GRD: 37 PASS en 21,07 s. B2-RUNTIME: 40 PASS en 15,69 s. B2-SRC: 34 PASS en 0,91 s. C01: 192 PASS en 0,51 s. C02: 233 PASS en 67,73 s. B1: 31 PASS en 14,66 s. Las cinco suites de conectores, en `C:\Temp\c04cent`, terminaron 615 PASS, 1 SKIPPED y 2 ERROR de preparación: pytest no pudo borrar un SQLite todavía abierto (`WinError 32`). Esos dos casos, repetidos solos en `C:\Temp\c04cent2`, dieron 2 PASS en 0,52 s. No cambiaron los conectores.

No se contactó local-hapi, Docker, Keycloak, Graph ni `api.openai.com`. No hubo solicitud live.

## Gemini, sin egress

El adaptador OpenAI permanece. Gemini es un paquete aparte dentro de `enterprise_llm_providers` y no entra en `EnterpriseModelGateway`. El transporte predeterminado es `DisabledGeminiTransport`. `GeminiSDKTransport.send` termina en `egress_blocked`. En esa fase no había modo live.

Modelo verificado: `gemini-3.5-flash-lite`. La página del modelo lo admite con Structured Outputs, límite de entrada 1.048.576 y de salida 65.536. El SDK ya fijado es `google-genai==2.24.0`; está instalado, declara los campos usados y no se cambió el pin. Python del entorno: 3.13.14. Construir `genai.Client` no abre un socket. La llamada sería `client.models.generate_content`.

La tarifa Standard de la página de precios es entrada US$0,30 / 1M y salida US$2,50 / 1M, incluidos los tokens de pensamiento. Batch, Flex y Priority no se seleccionan. El techo por llamada sigue en 1.000 micro-USD. Para caber, `max_output_tokens` es 128, no 256. La reserva de esta fixture fue 657 micro-USD. El dry-run simulado, con 40 tokens de entrada y 20 de salida, estima 62 micro-USD. `provider_charge` queda `unconfirmed`. El tope de US$5 no está verificado en Google.

`HttpRetryOptions.attempts` vale 1. En este SDK, 0 o 1 significan cero reintentos; el default no especificado es 5. El timeout va en milisegundos: 15.000. `thinking_level` es `MINIMAL`. No se envían tools, búsqueda, mapas, caché ni `base_url`. El esquema compartido exige `additionalProperties=false`. El grounding local es el mismo validador. Solo se acepta el fixture sintético fijo.

En el tier de pago, la página dice que el contenido no se usa para mejorar productos. El tier gratuito sí. Los logs de abuso siguen existiendo hasta una aprobación de Zero Data Retention. Esta fase no usa Search ni Maps, que conservarían contenido 30 días. No hubo llamada ni se leyó una clave.

Diferencias con OpenAI: otro modelo y otra tarifa de salida, más alta; el SDK es `google-genai` y no `openai`; el reintento se apaga con `attempts=1` y no con `max_retries=0`; el timeout se expresa en milisegundos; el pensamiento se fija en `MINIMAL` porque su costo entra en la salida; el máximo de salida de esta prueba es 128 tokens.

El dry-run `scripts/c04-gemini-dry-run/run_dry_run.py` devolvió `PASS`, `requests_sent=0`, días 20 y meses 12.

## Bridges neutrales, sin egress

`OpenAISdkBridge` y `GeminiSdkBridge` delegan en los adaptadores ya construidos. El catálogo añade `openai-sdk-a` y `gemini-sdk-a`, sin endpoint. La reserva del payload fijo es 303 micro-USD para OpenAI y 657 para Gemini. `GatewayResult` no devuelve días, meses ni extracto. El SDK de Gemini 2.24.0 expone `model_version`; el normalizador lo acepta junto al atributo `model` de los sustitutos de prueba. `send()` de ambos transportes sigue en `egress_blocked`. C03 no importa este gateway. El resultado público rechaza una organización distinta y no incluye la observación. El adaptador privado es una simulación en proceso, no un modelo autoalojado. El grafo clínico de seguimiento sigue acoplado al SDK de Gemini y no se modificó. La migración 003 sigue fuera. Las dos solicitudes reales de Gemini están en la sección siguiente y no tuvieron grounding `PASS`.

## Ejecutor Gemini

`scripts/c04-gemini-live-smoke/run_smoke.py` usa el gateway neutral, el puente Gemini y el grounding ya existente. El transporte predeterminado permanece cerrado. El único despacho está en `FixtureTransport`, limitado al fixture `vacation-days-v1` y al documento sintético fijo. No acepta otro documento, otro modelo ni una URL.

El modo predeterminado es `dry-run`:

```powershell
.\.venv\Scripts\python.exe ..\..\scripts\c04-gemini-live-smoke\run_smoke.py
```

`run_smoke.py live-once` se ejecuta desde `services/ai-service`, después de `$env:GEMINI_API_KEY = Read-Host "GEMINI_API_KEY"`. El dry-run no pide `GEMINI_API_KEY`, no crea una marca y no envía nada. El intento 002 usa `max_output_tokens` 256 solo en este ejecutor. El catálogo sigue reservando el perfil de 128 tokens. La reserva recalculada del payload de 256 es 977 micro-USD, bajo el techo de 1.000. `attempts` es 1 y el timeout es 15.000 ms. No hay fallback.

`live-once` del intento 002 exige una terminal interactiva, una frase distinta de la del primer intento, `GEMINI_API_KEY` en el entorno del proceso, el cliente oficial sobre `https://generativelanguage.googleapis.com` y la marca nueva `%LOCALAPPDATA%\healthcare-ai-interoperability-lab\c04-gemini-live-smoke\vacation-days-v1.attempt-002`. La marca `vacation-days-v1.attempt` del intento 001 permanece y no se reutiliza. Un timeout, un 429, un 5xx, un rechazo o un usage ambiguo no se reintenta y no borra la marca. El reporte de un fallo puede incluir `finish_reason` y conteos de tokens. No incluye el documento, el fragmento ni el pensamiento.

Antes de una ejecución real, el operador debe confirmar en la consola el saldo, el proyecto, la clave de ese proyecto, la facturación API, la recarga automática apagada y la ausencia de cargos automáticos no deseados. El saldo prepago no es un tope transaccional estricto. La clave se introduce con `Read-Host` y se retira con `Remove-Item Env:GEMINI_API_KEY`.

## Dos solicitudes reales

Se ejecutaron dos llamadas `live-once` y no hay autorización para una tercera. Las marcas viven fuera del repositorio, en `%LOCALAPPDATA%\healthcare-ai-interoperability-lab\c04-gemini-live-smoke`, y no se incorporan, borran ni reinician:

- `vacation-days-v1.attempt`, 76 bytes, SHA-256 `7a6ff9a563c05ce91c3f70d1f732050b9896a43d7ec2b6d5136cf8e818181638`.
- `vacation-days-v1.attempt-002`, 89 bytes, SHA-256 `c6d09088b73183a07dddd9fe9ab6ec0a9611dc5af16bba55c33728934d7ed1eb`.

El intento 001 devolvió `incomplete_output`. El reporte conservado no trae conteos de tokens. No se recuperó el cuerpo de esa respuesta.

El intento 002 devolvió `finish_reason=STOP`, candidato y contenido presentes, usage presente, 92 tokens de entrada y 107 de candidatos. `thoughts_token_count` y `output_tokens` llegaron nulos. El normalizador de ese momento exigía el pensamiento como entero, así que el resultado fue `consumption_ambiguous` y el grounding quedó `FAIL`. Esa llamada real no tuvo grounding `PASS`. La reserva fue 977 micro-USD. `provider_charge` permanece `unconfirmed`: el cálculo local no es la factura de Google.

Un fallo anterior, `environment_redirect`, no consumió solicitud. La causa fue tratar `os.environ` como `dict`. El ejecutor acepta un mapping y sigue rechazando proxy, `GEMINI_BASE_URL` y un host distinto de `generativelanguage.googleapis.com`.

## Usage opcional

La corrección es offline y no reclasifica el intento 002. `prompt_token_count` es entrada. `candidates_token_count` es la salida visible y se conserva aunque el pensamiento falte. `thoughts_token_count` ausente permanece ausente; cero explícito es cero. Un entero negativo, un booleano o una cadena invalidan el usage y no borran los conteos válidos. `tool_use_prompt_token_count`, cuando está presente, se suma a la entrada.

Si `total_token_count` está presente, la suma conocida es prompt, candidatos, pensamiento y tool-use. Un único componente ausente se completa con el resto. Varios ausentes se completan con cero solo cuando el resto es cero. Un resto positivo repartible entre dos o más ausentes no se inventa. Un total menor que la suma conocida, o distinto cuando no falta ningún componente, es `consumption_ambiguous`.

Cada componente inferido lleva su marca: `prompt_inferred`, `visible_inferred`, `thoughts_inferred` o `tool_inferred`. El valor inferido no se presenta como un conteo reportado por el proveedor. `cost_exact` solo es verdadero cuando el pensamiento queda determinado, sea reportado o inferido de forma unívoca. Si falta ese dato, `estimated_microusd` queda vacío y la reserva no se publica como consumo medido. `provider_charge=unconfirmed` se mantiene en todos los reportes. Un usage utilizable continúa al validador; un JSON inválido, `MAX_TOKENS`, `SAFETY` o una cifra inventada siguen en grounding `FAIL`.

El mismo criterio recorre el SDK simulado, el normalizador, el adaptador, el bridge, `GatewayResult` y el ejecutor. `GatewayResult` no incluye el documento, el fragmento ni el texto del modelo. Su proyección pública solo lleva fase, motivo, organización y despliegue. C03 sigue exigiendo `FakeEnterpriseModel` y no importa este gateway.

## Cierre de esta rama

La simulación y la llamada real quedan separadas. El dry-run de esta revisión devolvió `PASS`, `requests_sent=0`, reserva 977 y estimado simulado 62. El dry-run de OpenAI devolvió `PASS`, `requests_sent=0` y reserva 303. Las pruebas focalizadas de Gemini, OpenAI, gateway, bridges y arquitectura dieron 164 PASS en `C:\Temp\c04close2`. Las regresiones ya reportadas de C03 E2E (34), B2-GRD (37), B2-RUNTIME/SRC (74), C01/C02/B1 (405) y conectores (617 PASS, 1 SKIPPED) no se repitieron: el cambio de esta auditoría añade marcas opcionales al contrato del gateway neutral y esas suites no lo importan.

No hay una autorización pendiente para otra llamada. La migración 003 sigue siendo el permiso durable que esta fase no crea. RAG, MCP, PostgreSQL, Graph live y la integración con C03 permanecen fuera.

## Decisiones pendientes

- Confirmar proyecto OpenAI, facturación API, disponibilidad de `gpt-6-luna`, límite mensual de US$5 con hard limit si existe, y alertas. Esta sesión no lo comprobó.
- Confirmar en Google el proyecto, la facturación API y el cargo real de las dos solicitudes ya consumidas. El saldo prepago no sustituye ese cargo.
- La migración 003, la integración con C03, RAG, MCP, PostgreSQL y Graph live siguen fuera de esta fase. No hay una tercera solicitud Gemini autorizada.
