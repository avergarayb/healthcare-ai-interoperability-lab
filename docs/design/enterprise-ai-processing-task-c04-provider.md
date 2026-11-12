# TASK-C04 Phase A — frontera OpenAI, sin egress

Estado: Phase A y Phase B en `feature/enterprise-ai-processing-authorization-task-c04-provider`. El transporte SDK existe y su envío está cerrado. No hay llamada real.

Base: `origin/main` `47cb35a723754136bdca596ce062062422d19108`, merge del PR #123. El commit funcional de C03 E2E es `c7b83ed2af0e0abe60b38c0dfd46a05c277a9215`.

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

## Pruebas de esta ejecución

`tests/test_enterprise_llm_provider.py`: 20 PASS en 0,69 s, basetemp `C:\Temp\c04b2`. Incluye el SDK real contra `httpx2.MockTransport`, `max_retries=0`, el dry-run fijo y el fake de C03 intacto.

`tests/test_architecture.py`: 9 PASS en 0,57 s. `tests/test_enterprise_ai_processing_architecture.py`: 51 PASS en 0,37 s. E2E C03: 34 PASS en 28,10 s. B2-GRD: 37 PASS en 21,81 s. B2-RUNTIME: 40 PASS en 15,20 s. B2-SRC: 34 PASS en 0,80 s. C01: 192 PASS en 0,30 s. C02: 233 PASS en 65,41 s. B1: 31 PASS en 5,88 s. Suites empresariales de conectores: 617 PASS y 1 SKIPPED en 515,20 s, basetemp `C:\Temp\c04bent`.

No se contactó local-hapi, Docker, Keycloak, Graph ni `api.openai.com`.

## Decisiones pendientes

- Implementar la migración 003 cuando el permiso remoto deba ser durable.
- Configurar presupuesto y alertas del proyecto OpenAI antes de cualquier envío.
- Autorizar, en otro incremento, una sola llamada real con el fixture fijo y sin integrar C03.
