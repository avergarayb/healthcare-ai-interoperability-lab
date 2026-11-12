# TASK-C03 Phase A — respuesta fundamentada y entrega final

Estado: **propuesta enmendada**. B1, B2-SRC, B2-RUNTIME y B2-GRD están integrados. La sección 26 registra el incremento E2E en el árbol de trabajo, sin commit. La sección 22 sigue siendo el contrato de la migración V2. No hay migración 003.

Esta propuesta compone capacidades ya integradas. No crea un segundo evaluador de Gate C, no duplica grants, no lee tablas SQLite desde LangGraph y no llama a `ConnectorService._validate_delivery` ni a `ConnectorService._event`.

## 1. Estado y alcance

Objetivo de diseño: una sola invocación offline, sintética y Windows que componga lectura autorizada, evidencia de origen, evaluación C01, procesamiento fake C02, validación determinista, respuesta fundamentada, revalidación B/C y entrega auditada al llamador de confianza de esa misma llamada.

Queda fuera: Graph live, modelo real, RAG, embeddings, MCP, Gate D, IAM productivo, PostgreSQL, DEMO-002, TASK-C04, endpoints HTTP, workflow clínico, Human Review y cualquier afirmación de preparación productiva. El Gate C del workflow de cuatro nodos permanece DENY. C02 no lo habilita y C03 tampoco.

El primer resultado positivo exige un fixture sintético nuevo, con la cláusula explícita que el fake ya sabe reconocer. El texto actual de DEMO-001 no contiene días de vacaciones. Con ese texto el único resultado correcto es evidencia insuficiente. Esta propuesta no inventa «20 días».

## 2. Git y contratos examinados

Lectura de código y documentos sobre `origin/main` en `f1edf52f5d8a46fbad1538ab866dd3ac3aa01b0a`, merge del PR **#118**. El mensaje es `Merge pull request #118 from avergarayb/docs/codex-to-cursor-transition-001`. Sus padres son `3c3fc67df9a1da647046595395b084c2aca12e62` y `25fc505d850b7f08523ac66306d363210facaab5`. El documento de transición está en ese árbol. El commit funcional C02 `36b8a75d867de69871a99ac37d175e88c8bff088` y el merge C02 `3c3fc67` son ancestros. `main` local sigue en `138b748747f0e3d57f7da89c1fbc7c2b62cf5f8d` y no se actualizó.

La rama de trabajo es `feature/enterprise-ai-processing-authorization-task-c03`, creada desde `origin/main`. El seguimiento inicial hacia `origin/main` se retiró para que un push sin refspec no publique `main`. No hay upstream.

Contratos y diseños leídos, sin modificarlos:

- [AGENTS.md](../../AGENTS.md), [handoff](../agent-handoff.md), [transición](../agent-transition-codex-to-cursor.md), [PROJECT.md](../PROJECT.md), [roadmap](../roadmap.md), [índice de arquitectura](../architecture/README.md).
- [DESIGN-001](enterprise-ai-processing-authorization-v1.md), [contrato C](../contracts/enterprise-ai-processing-authorization-v1.md), [amenazas AI-T01–AI-T18](enterprise-ai-processing-threat-model-v1.md), [plan C01–C04](enterprise-ai-processing-implementation-plan-v1.md).
- [Runbook C01](enterprise-ai-processing-policy-fixture-v1.md), [propuesta C02](enterprise-ai-processing-gateway-audit-task-c02-proposal.md), [runbook C02](enterprise-ai-processing-gateway-audit-task-c02.md).
- [ADR-097](../adr/ADR-097-enterprise-connector-authorization-boundaries.md). Sigue siendo dirección arquitectónica. Esta propuesta no lo enmienda.
- [TASK 004](microsoft-graph-app-only-adapter-v1.md), [TASK 005](langgraph-enterprise-connector-integration-v1.md), [DEMO-001](../demos/enterprise-connector-demo-001.md), [M01/M02](enterprise-connector-maintainability-demo-001.md).

Esos documentos conservan el estado de su momento, incluidas frases de «C03 no autorizada» y «runtime C DENY». Siguen siendo ciertas para el workflow antiguo y para cualquier ejecución no autorizada todavía.

## 3. Arquitectura actual verificada

Código inspeccionado en el árbol de `f1edf52`. `app/main.py` no importa módulos empresariales. No hay ruta HTTP empresarial.

| Pieza | Hecho verificado |
|---|---|
| [PolicyEvaluator.evaluate](../../services/ai-service/app/enterprise_connectors/policy.py) | API pública. `Gate.AI_PROCESS` y `Gate.INDEX` lanzan `Reason.DATA_USE`. Un grant de lectura exige operación, propósito, destinatario, clasificación y ámbito completos. No inspecciona bytes ni respuestas derivadas. |
| [ConnectorService.execute](../../services/ai-service/app/enterprise_connectors/service.py) | Única operación pública de lectura. Rechaza cualquier gate distinto de `Gate.READ` antes de adquirir datos. La entrega B del documento ocurre dentro de `execute` mediante helpers privados. |
| [ConnectorService._validate_delivery](../../services/ai-service/app/enterprise_connectors/service.py) y [_event](../../services/ai-service/app/enterprise_connectors/service.py) | Privados. Los usa [EnterpriseDocumentWorkflow](../../services/ai-service/app/enterprise_workflows/document_read.py) en `_deliver` y `_failure`. |
| [GraphReadAdapter](../../services/ai-service/app/enterprise_connectors/providers/microsoft_graph/adapter.py) | `read` y `authorize_delivery` son públicos. `authorize_delivery` resuelve identidades y llama al transporte simulado. El comentario del código dice que no es I/O de Graph. El workflow exige `transport.offline` y `credentials.offline`. |
| [EnterpriseDocumentWorkflow.invoke](../../services/ai-service/app/enterprise_workflows/document_read.py) | Cuatro nodos: `validate_request`, `resolve_registered_resource`, `invoke_authorized_connector`, `evaluate_result`. Estado: `operation_id`, `correlation_id`, `resource_id`, `operation`, `status`, `reason`, `steps`. Sin checkpointer, store ni cache. El documento vive en `_Invocation`, no en el estado. `invoke` devuelve `EnterpriseResult.documents`, con el texto, solo a esa llamada. |
| [GateCPolicyEvaluator.evaluate](../../services/ai-service/app/enterprise_ai_processing/policy.py) | API pública de C01. Reutiliza `PolicyEvaluator.evaluate` para `Gate.READ` y `Gate.DELIVERY`. `ALLOW_PROCESSING` significa `processing_eligible_not_executable`. No emite lease ni ejecuta. `SourceEvidence` no contiene texto ni digest. |
| [EnterpriseModelGateway](../../services/ai-service/app/enterprise_ai_processing/gateway.py) | `prepare` devuelve una `ProcessingLease` no portable. `invoke_once` devuelve `ExecutionResult(state, reason, entries, processing_started, input_units, output_units)`. No hay `get_result`. |
| [ExecutionOwner](../../services/ai-service/app/enterprise_ai_processing/execution_types.py) | Guarda envelope, evidencia, bytes de fuente, pregunta, input, candidato y copias originales. `clear` anula esas referencias. |
| [FakeEnterpriseModel](../../services/ai-service/app/enterprise_ai_processing/fake_model.py) | Busca en bytes el primer patrón `VACACIONES: `, dígitos, ` dias tras `, dígitos y ` meses de servicio.`. Escribe `candidate` y `CANDIDATE`, o `b""` y `NO_EVIDENCE`, solo en el owner. No decide permisos ni redacta la frase final. |
| [SQLiteExecutionLedger._validate](../../services/ai-service/app/enterprise_ai_processing/sqlite_ledger.py) | Exige `schema_ddl` idéntico al oráculo en memoria de la migración 001, `schema_version = 1`, contrato `enterprise-ai-processing-ledger-v1` y checksum SHA-256 del texto LF de ese archivo. Una tabla nueva rompe esa igualdad. `initialize` solo crea V1. |
| Migración [001_processing_ledger.sql](../../services/ai-service/app/enterprise_ai_processing/migrations/001_processing_ledger.sql) | `aip_store.schema_version` tiene `CHECK (schema_version = 1)`. No se puede marcar V2 con un `UPDATE`. El CHECK de `aip_audit.event` admite solo los diez eventos de C02. |

`ExecutionResult` de estado `COMPLETED` y `result_code` `CANDIDATE` acreditan que el fake produjo una categoría cerrada. No acreditan grounding, Gate B, Gate C fresco ni entrega.

## 4. Objetivos y no objetivos

Objetivos de una implementación futura, todavía no autorizada:

1. Reutilizar el reader público, el evaluador C01 y el gateway C02.
2. Validar el candidato contra los bytes del mismo owner y la misma revisión.
3. Construir la frase solo con una plantilla y los campos verificados.
4. Revalidar B y C inmediatamente antes de la salida.
5. Distinguir decisión de entrega, intento, observación local y estado desconocido.
6. Auditar solo metadata, en una migración nueva, sin alterar el CHECK de C02.

No objetivos: segunda política C, acceso SQL desde el grafo, extensión de los cuatro nodos actuales, habilitar el Gate C antiguo, A-only, varios documentos, pregunta libre, reintento automático, caché de respuestas, checkpoint con contenido y borrado criptográfico.

## 5. Diferencias C02 a C03

| C02, ya integrado | C03, solo propuesto |
|---|---|
| Evaluación, reserva, lease, fake y resultado técnico. | Añade grounding, frase plantilla y decisión de entrega. |
| El candidato muere en `invoke_once` antes del `return`. | Hace falta un observador de un solo uso, autorizado aparte, para ver el candidato en esa misma pila. |
| `COMPLETED` no entrega al usuario. | La entrega es el retorno de esta llamada, después de commits, y no es una recepción humana. |
| Diez eventos cerrados. | Dos hechos nuevos viven en otra tabla. No se insertan en `aip_audit`. |
| El workflow de cuatro nodos no participa. | Un grafo nuevo llama a `invoke` como caja negra. No se insertan nodos en el grafo viejo. |

## 6. Contrato GroundedAnswer propuesto

Los cuatro objetos son efímeros, de una invocación, con `repr=False` en todo campo que pueda reconstruir texto. `repr=False` no borra memoria. Ninguno se guarda en el estado de LangGraph, en SQLite ni en auditoría. Ningún identificador de estos objetos es una capacidad de lectura posterior.

### GroundedEvidence

Campos en memoria, durante la misma llamada: `operation_id`, `organization_id`, `instance_id`, `tenant_id`, `resource_id`, `recipient_id`, `registered_version`, `content_revision`, `connector_revision`, `processing_revision`, `read_correlation_id`, `question_id`, `span_start`, `span_end`, `span_length`. `span_length` es un entero, la cantidad de bytes del corte, no el contenido. Los offsets son de bytes UTF-8. `question_id` solo puede ser `vacation-days-v1`.

Invariantes: `span_end - span_start == span_length`; el corte se comprobó contra los bytes del owner de lectura, no contra un alias del owner C02; la revisión no cambió. Este objeto no contiene texto. Offsets y longitud no entran en LangGraph, SQLite ni auditoría: junto con el documento permitirían reconstruir el fragmento.

### GroundingDecision

Enumeración cerrada, sin texto:

| Veredicto | Cuándo |
|---|---|
| `EVIDENCE_FOUND` | El candidato coincide con el span y el patrón cerrado, sin contradicción en el mismo documento. |
| `EVIDENCE_INSUFFICIENT` | El fake devolvió `NO_EVIDENCE`, el patrón no está, falta una condición o hay dos cláusulas incompatibles. |
| `CANDIDATE_INVALID` | Offsets, codificación, fuente, owner o candidato no coinciden con los bytes reales. |
| `AUTHORIZATION_DENIED` | B o C responden denegación verificable. |
| `AUTHORIZATION_UNVERIFIABLE` | Política, revisión, sink o frontera no pueden comprobarse. |
| `REVOCATION_DETECTED` | Un chequeo exigido observa revocación, caducidad o cambio de revisión. |
| `TECHNICAL_FAILURE` | Error interno sin contenido en el diagnóstico. |

`EVIDENCE_FOUND` no es entrega. Los veredictos de denegación, insuficiencia e invalidez no incluyen dígitos ni citas.

### GroundedAnswer

Se construye en memoria solo si el veredicto es `EVIDENCE_FOUND`, el permiso derivado sigue vigente y la decisión durable ya confirmó `AUTHORIZED`. Campos de trabajo: metadata de la evidencia, `classification = synthetic-internal`, `provenance = synthetic-documents-v1`, `template_id` y dos enteros (días y meses). Esos enteros no se guardan en SQLite. La frase se arma en el valor de retorno, no antes del commit C. No hay `answer_id`. Si el solicitante no está autorizado, no recibe este objeto, ni cifras, ni el veredicto de insuficiencia.

### FinalDeliveryDecision

| Estado | Significado |
|---|---|
| `AUTHORIZED` | Fila durable en el store C, ya confirmada. Aún no se construye el valor de retorno. No prueba que el llamador haya recibido nada. |
| `ATTEMPTED` | Estado solo de memoria: el valor de retorno ya existe en esta pila y todavía no hay observación del llamador. |
| `OBSERVED` | Lo puede afirmar el llamador de confianza cuando recibe el resultado. El callee no lo escribe antes ni después. No es recepción humana ni fila durable. |
| `SUPPRESSED` | Fila durable. No hay frase. Una fila B documental del reader no cuenta como esta decisión. |
| `UNKNOWN` | Commit ambiguo, caída después de `AUTHORIZED`, o excepción cuando el valor de retorno pudo haber salido. No se reintenta. |

`OBSERVED` no tiene columna. Un reinicio que encuentra `AUTHORIZED` lo pasa a `RELEASE_UNCERTAIN` y no reenvía, porque el texto no está almacenado y el callee no puede saber si el proceso anterior llegó a retornar.

## 7. Transferencia efímera

Hecho de código: `invoke_once` confirma el ledger, construye `ExecutionResult` sin candidato y en el `finally` llama a `_cleanup`, que pone `candidate`, `source_bytes` y `question_bytes` a `None`. Si la limpieza falla, el retorno pasa a `UNAVAILABLE` / `internal_failure`. Guardar el atributo del owner C02 conservaría el mismo objeto `bytes`.

El contrato actual impide la transferencia segura. Phase A no modifica C02. El cambio mínimo futuro es un método sin callback de caller:

```text
invoke_once_observed(lease) -> ExecutionResult
```

`invoke_once(lease)` queda intacto: no busca observador y limpia antes de retornar.

Alternativas descartadas:

| Alternativa | Motivo de descarte |
|---|---|
| `invoke_once_observed(lease, observer)` con callback del caller | Un callable arbitrario no es una autoridad. El documento o el solicitante no pueden suministrar código. |
| Incluir el candidato en `ExecutionResult` | Serializa contenido y parece entrega. |
| `get_result(operation_id)` | Convierte el id en capacidad. |
| Reconstruir el owner o reusar la lease | La lease ya está consumida y no es portable. |
| Caché de respuestas | Retención y Gate D. |
| Leer `result_code` como texto | Solo guarda `CANDIDATE` o `NO_EVIDENCE`. |

### Autoridad del observador

Lo crea la composición de confianza de C03, dentro de la invocación, del mismo modo que hoy solo un `ExecutionBoundary` de test emite envelopes. `workflow.invoke` no acepta un observer en sus argumentos. El gateway no acepta un callable externo.

Antes de `prepare`, esa composición construye un único `DeterministicVacationGrounding` para esa operación. El boundary lo reconoce por identidad de objeto: `type(observer) is DeterministicVacationGrounding`, `recognizes_observer(observer, operation_id) is True`, y el gateway guarda `id(observer)` junto a la lease de esa operación. Otra instancia, aunque sea de la misma clase, no sirve. `__reduce_ex__` lanza. No hay registro global ni paso entre operaciones.

`invoke_once_observed` lo ejecuta una sola vez, después del commit `COMPLETED`, fuera de la transacción SQLite y antes de `_cleanup`. Marca `used` antes de entrar. Una segunda entrada no vuelve a leer bytes. El observador puede ver, solo como locales de esa llamada: bytes de fuente del owner C02, bytes de pregunta, candidato, `result_code` y las revisiones ya reconocidas. No recibe puerto de entrega, ledger, adaptador, red ni herramientas. No ejecuta texto del documento. Su veredicto no autoriza modelo ni destinatario.

Devuelve solo escalares: veredicto, `span_start`, `span_end`, `span_length`, dos enteros o ausencia de ellos, `content_revision`, `registered_version` y `question_id`. Cero `bytes` y cero texto de span. Al salir, el gateway anula sus locales, retira la entrada del registro y llama a `observer.clear()`. El `finally` de C02 limpia el owner C02 igual que hoy. Si el observador falla o la llamada se cancela, el `COMPLETED` técnico no se reescribe ni se reintenta; C03 no entrega y propaga la señal original si era una cancelación.

### bytes() no copia un bytes existente

En CPython, `bytes(valor)` cuando `valor` ya es `bytes` devuelve el mismo objeto. `valor[:]` completo también. La frase anterior que presentaba `bytes(...)` como copia independiente queda retirada.

La plantilla de vacaciones no necesita conservar el fragmento. Necesita dos enteros ya comprobados. El owner de respuesta no guarda el span.

Hace falta una copia independiente solo para el buffer del owner de lectura, creado antes de poblar C02, para poder recomprobar el patrón en `T_auth` después de que C02 anule sus atributos:

```text
temporal = bytearray(texto_autorizado.encode("utf-8"))
buffer_de_lectura = bytes(temporal)
temporal.clear()
```

`bytearray(...)` asigna un buffer nuevo. `bytes(temporal)` asigna otro. La prueba de canario exige `buffer_de_lectura is buffer_c02` falso y `buffer_de_lectura is candidato` falso. Después de `_cleanup`, el owner de respuesta y el observador no contienen atributos que apunten al owner C02 ni a sus buffers. No se usa `frame.clear`, `f_locals`, `gc` ni recorrido global.

Límites que Python no da: anular un atributo no borra otras referencias ni la memoria del asignador; una `str` devuelta al llamador queda fuera de estos owners; no hay borrado criptográfico.

### Revalidación C01 después del cleanup

`GateCPolicyEvaluator.evaluate` no recibe la lease ni los bytes. Recibe snapshot fresco, política C fresca, `AIProcessingEnvelope` y `SourceEvidence`. El envelope sí contiene la pregunta, que es sensible y permanece solo en el owner de invocación de C03, nunca en el estado del grafo.

Ese owner conserva sus propias referencias al envelope y a la evidencia desde antes de `prepare`. No son atributos del owner C02, así que sobreviven a `_cleanup`. La lease consumida no se presenta. La autoridad se vuelve a pedir al boundary con el mismo envelope reconocido; no se inventa otra identidad. El chequeo C01 posterior demuestra grant, perfil, vigencia y revisión. No demuestra el span. El span se vuelve a comparar con el buffer del owner de lectura, que C02 no posee. Si ese buffer ya se limpió, no hay forma honesta de recomprobar los bytes y la llamada se suprime. El orden queda fijado en la sección 12: la recomprobación ocurre antes de anular el buffer de lectura.

## 8. Grounding y validación de citas

El fake no decide si la respuesta está fundamentada. El validador corre dentro del observador, sobre los bytes del owner, no sobre un id ni un digest.

Reglas:

1. `result_code == NO_EVIDENCE` o candidato vacío produce `EVIDENCE_INSUFFICIENT`. El mensaje fijo sin cifras solo se muestra si el permiso derivado ya autorizó la salida. Si el solicitante no está autorizado, la respuesta visible es la denegación cerrada, no la insuficiencia.
2. El candidato debe ser igual a `source_bytes[start:end]` para un único par de offsets de bytes. Un índice Unicode o un offset que caiga dentro de un código UTF-8 es `CANDIDATE_INVALID`.
3. No hay normalización NFC/NFD ni recodificación. Se comparan los bytes recibidos.
4. El span debe cumplir el mismo patrón cerrado del fake, con las dos series de dígitos ASCII. Esos enteros son los únicos datos de la plantilla.
5. El documento se recorre completo. Si aparece una segunda cláusula del mismo patrón con otros números, el veredicto es `EVIDENCE_INSUFFICIENT`. No se elige la primera por conveniencia.
6. Una frase repetida e idéntica puede citarse una vez. No amplía el significado.
7. Instrucciones dentro del documento son datos. No cambian organización, modelo, auditoría ni destino. No se citan como fuente. La plantilla no concatena el texto circundante.
8. La pregunta tiene que ser la cadena allowlisted ya reconocida por C01 y el `question_id` de la operación. Otra pregunta no se responde con este span.
9. `content_revision`, `registered_version` y la longitud UTF-8 tienen que coincidir con la evidencia de la lectura y con los bytes todavía presentes. `registered_version` es la versión del registro sintético, no un eTag de Graph.
10. El texto de DEMO-001 no contiene el patrón. El veredicto exigido es insuficiencia. Un fixture nuevo, en una tarea posterior, puede añadir la cláusula explícita sin editar el fixture viejo.

La frase final es una plantilla fija del laboratorio con los dos enteros verificados. Si falta uno, no hay frase. El modelo no aporta la oración.

## 9. Diseño LangGraph

No se modifica el `StateGraph` de cuatro nodos ni su scrub de M01. El grafo nuevo se llama `offline_enterprise_grounded_answer` y se compila con `checkpointer=False`, sin store, sin cache, sin debug, callbacks vacíos y tracing deshabilitado. El contexto de runtime lleva solo `operation_id`. No hay `stream`, `astream`, resume ni consulta por id.

Estado permitido: `operation_id`, `read_correlation_id`, `resource_id`, `registered_version`, `content_revision`, `status`, `reason`, `steps`.

Prohibido en estado, config, checkpoints, callbacks y logs: texto documental, pregunta, prompt, fragmento, candidato, respuesta, credenciales, tokens, digest y cualquier objeto que permita reconstruirlos. La lease y los owners viven en el marco de la invocación, fuera de los canales.

Nodos mínimos, sin reintento de nodo:

1. `validate_request`. Abre la frontera reconocida. Comprueba la forma de los argumentos. La pregunta no viaja en el estado; la aporta el envelope ya reconocido.
2. `read_authorized_document`. Llama a `EnterpriseDocumentWorkflow.invoke`. Si el resultado no es `DELIVERY_ALLOWED`, termina sin fake. El owner de lectura se queda con el buffer creado por `bytearray` y `bytes`, no con un alias del resultado. El estado solo copia ids, versión y códigos.
3. `evaluate_and_prepare`. Llama a `gateway.prepare`, que ya usa `GateCPolicyEvaluator` y reserva la lease. El observador ya fue reconocido para esa operación y no viaja en el estado. La lease tampoco.
4. `invoke_approved_model`. Llama a `invoke_once_observed(lease)`, sin callback. El nodo solo publica el veredicto y el motivo. Los enteros quedan en el owner de respuesta.
5. Fin del grafo. No renderiza ni entrega.

La entrega queda fuera del grafo, como `_deliver` en el workflow actual, después de que el grafo haya vuelto. Cancelación y `KeyboardInterrupt` se propagan como la misma señal. No se convierten en éxito. El owner se crea vacío dentro del `try` exterior. `close` y `clear` son independientes. Los fallos secundarios añaden una nota fija, sin payload. No se inspeccionan `f_locals` ni frames ajenos. Si la retirada explícita de referencias no basta en las pruebas futuras, el incremento se detiene. No se extiende el scrub de M01.

`EnterpriseDocumentWorkflow.invoke` sí devuelve el documento original a su llamador, porque hoy no existe una lectura pública A-only. El llamador de C03 es código de confianza de la misma invocación. No reenvía esos documentos en el resultado de C03. Un modo que procese sin entregar el original necesita otro contrato; no se obtiene llamando a helpers privados.

## 10. Puerto público de entrega

`PolicyEvaluator`, con `Gate.DELIVERY`, exige un grant principal completo: el gate está en `gates`, el propósito en `purposes`, el destinatario en `recipients` y la clasificación en `classifications`, más un grant externo completo. `ConnectorService.execute` rechaza cualquier gate distinto de `Gate.READ` antes de adquirir datos. Ese contrato no tiene `content_kind` ni una operación de respuesta. Coincidir destinatario y propósito del documento no crea el permiso derivado. Extender el enum `Gate` o el esquema del conector sería un cambio del contrato histórico A/B y un segundo significado metido en el mismo grant. No es la opción pequeña.

La opción pequeña es una autoridad sintética aparte, en el store de procesamiento V2, administrada solo por el administrador de laboratorio que ya reconoce el ledger. El solicitante no inserta la fila ni aporta constantes que la sustituyan. El predicado es una función cerrada de una sola fila completa. No es otro `PolicyEvaluator` y no reimplementa ámbito, bindings ni Gate C.

La fila `aip_derived_delivery_grant` exige, todas a la vez:

- organización, principal, instancia, tenant, recurso y destinatario exactos;
- `content_kind = grounded_extractive_answer`;
- `delivery_operation = enterprise.answer.deliver`;
- propósito `synthetic-policy-question-answering`, distinto del propósito de lectura `synthetic-demonstration`;
- clasificación `synthetic-internal`;
- versión registrada del recurso;
- revisión de política del conector y revisión de procesamiento vigentes en el momento del chequeo;
- `grant_id` C habilitado al que esta fila apunta;
- vigencia `valid_from`, `expires_at` y `review_due_at`;
- `enabled = 1`.

Falta cualquiera de esas igualdades: denegación. No se suman filas parciales. Una fila de otra organización no se consulta para el solicitante. El predicado sigue exigiendo, por separado, `PolicyEvaluator` en `READ` y en `DELIVERY`, `authorize_delivery` offline del recurso de origen, y un `ALLOW_PROCESSING` fresco. El permiso derivado no sustituye B ni C. B y C no sustituyen el permiso derivado.

Firma conceptual, no implementada:

```text
authorize_derived_delivery(
    context,
    request,
    derived_grant_id,
) -> DerivedDeliveryDecision
```

`content_kind`, revisiones y destinatario salen de la fila y del contexto reconocido, no de argumentos libres del solicitante. El método no llama a `_validate_delivery` ni a `_event`, no escribe en el store del conector y no devuelve bytes.

Pruebas de esta autoridad, todavía no ejecutadas: fila completa más B más C permite la decisión; B válido sin fila deniega; fila válida sin B deniega; `enabled = 0` o revisión distinta deniega; los mismos ids en otra organización deniegan sin revelar la fila ajena; un argumento `content_kind` del caller sin fila deniega.

## 10.1 Migración 002, borrador sustituido

El DDL de este apartado queda sustituido por la sección 22 y por `services/ai-service/app/enterprise_ai_processing/migrations/002_processing_ledger.sql`. No se aplica. Se conserva para mostrar qué se rechazó: revisión derivada global, `release_count`, `derived_grant_id` obligatorio y `organization_id` obligatorio en toda auditoría.

`_validate` compara el `sqlite_master` ordenado con el oráculo de 001 y exige `schema_version = 1`. Añadir una tabla a un archivo V1 hace que el código C02 actual lo rechace. El `CHECK` de `aip_store` impide un `UPDATE` a versión 2. Por eso 002 reconstruye `aip_store` y agrega tablas nuevas. No altera el `CREATE` de `aip_profile`, `aip_grant`, `aip_execution` ni `aip_audit`. No se ejecuta aquí. No usa `ATTACH` hacia el store del conector. No se edita el archivo 001.

Contrato V2 propuesto: `enterprise-ai-processing-ledger-v2`. El checksum V2 es el SHA-256 del texto LF de 002. La columna `v1_checksum` conserva el SHA-256 de 001.

```text
CREATE TABLE aip_store_next (
    singleton INTEGER NOT NULL PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 2),
    contract TEXT NOT NULL CHECK (contract = 'enterprise-ai-processing-ledger-v2'),
    store_id TEXT NOT NULL UNIQUE CHECK (length(store_id) = 36),
    migration_checksum TEXT NOT NULL CHECK (length(migration_checksum) = 64),
    v1_checksum TEXT NOT NULL CHECK (length(v1_checksum) = 64),
    revision INTEGER NOT NULL CHECK (revision BETWEEN 1 AND 1000000),
    next_audit_seq INTEGER NOT NULL CHECK (next_audit_seq > 0),
    next_grounding_seq INTEGER NOT NULL CHECK (next_grounding_seq > 0)
) STRICT;

CREATE TABLE aip_derived_delivery_grant (
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    derived_grant_id TEXT NOT NULL CHECK (length(derived_grant_id) BETWEEN 1 AND 80),
    version INTEGER NOT NULL CHECK (version BETWEEN 1 AND 1000000),
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    principal_id TEXT NOT NULL CHECK (length(principal_id) BETWEEN 1 AND 80),
    instance_id TEXT NOT NULL CHECK (length(instance_id) BETWEEN 1 AND 80),
    tenant_id TEXT NOT NULL CHECK (length(tenant_id) BETWEEN 1 AND 80),
    resource_id TEXT NOT NULL CHECK (length(resource_id) BETWEEN 1 AND 80),
    recipient_id TEXT NOT NULL CHECK (length(recipient_id) BETWEEN 1 AND 80),
    content_kind TEXT NOT NULL CHECK (content_kind = 'grounded_extractive_answer'),
    delivery_operation TEXT NOT NULL CHECK (delivery_operation = 'enterprise.answer.deliver'),
    purpose TEXT NOT NULL CHECK (purpose = 'synthetic-policy-question-answering'),
    classification TEXT NOT NULL CHECK (classification = 'synthetic-internal'),
    registered_version INTEGER NOT NULL CHECK (registered_version BETWEEN 1 AND 1000000),
    connector_revision INTEGER NOT NULL CHECK (connector_revision BETWEEN 1 AND 1000000),
    processing_revision INTEGER NOT NULL CHECK (processing_revision BETWEEN 1 AND 1000000),
    processing_grant_id TEXT NOT NULL CHECK (length(processing_grant_id) BETWEEN 1 AND 80),
    valid_from_us INTEGER NOT NULL CHECK (valid_from_us >= 0),
    expires_at_us INTEGER NOT NULL,
    review_due_at_us INTEGER NOT NULL,
    PRIMARY KEY (organization_id, derived_grant_id),
    FOREIGN KEY (organization_id, processing_grant_id)
        REFERENCES aip_grant (organization_id, grant_id),
    CHECK (valid_from_us < expires_at_us AND valid_from_us < review_due_at_us)
) STRICT;

CREATE TABLE aip_grounding_audit (
    event_id TEXT NOT NULL PRIMARY KEY CHECK (length(event_id) = 36),
    audit_seq INTEGER NOT NULL UNIQUE CHECK (audit_seq > 0),
    contract TEXT NOT NULL CHECK (contract = 'enterprise-ai-processing-audit-v1'),
    timestamp_us INTEGER NOT NULL CHECK (timestamp_us >= 0),
    event TEXT NOT NULL CHECK (event IN (
        'ai_answer_evidence_validated',
        'ai_derived_delivery_decided',
        'ai_derived_delivery_revocation_detected',
        'derived_delivery_grant_changed')),
    outcome TEXT NOT NULL CHECK (outcome IN (
        'EVIDENCE_FOUND', 'EVIDENCE_INSUFFICIENT', 'CANDIDATE_INVALID',
        'TECHNICAL_FAILURE', 'AUTHORIZED', 'SUPPRESSED', 'UNKNOWN',
        'REVOKED', 'CHANGED')),
    reason TEXT NOT NULL CHECK (reason IN (
        'accepted', 'evidence_insufficient', 'citation_invalid',
        'derived_delivery_not_granted', 'authorization_expired',
        'policy_changed', 'authority_unverifiable', 'audit_unavailable',
        'internal_failure', 'execution_unknown')),
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    operation_id TEXT CHECK (length(operation_id) = 36),
    decision_ref TEXT CHECK (length(decision_ref) = 36),
    read_correlation_id TEXT CHECK (length(read_correlation_id) = 36),
    principal_id TEXT CHECK (length(principal_id) BETWEEN 1 AND 80),
    instance_id TEXT CHECK (length(instance_id) BETWEEN 1 AND 80),
    resource_id TEXT CHECK (length(resource_id) BETWEEN 1 AND 80),
    recipient_id TEXT CHECK (length(recipient_id) BETWEEN 1 AND 80),
    derived_grant_id TEXT CHECK (length(derived_grant_id) BETWEEN 1 AND 80),
    processing_grant_id TEXT CHECK (length(processing_grant_id) BETWEEN 1 AND 80),
    registered_version INTEGER CHECK (registered_version BETWEEN 1 AND 1000000),
    content_revision INTEGER CHECK (content_revision BETWEEN 1 AND 1000000),
    connector_revision INTEGER CHECK (connector_revision BETWEEN 1 AND 1000000),
    processing_revision INTEGER CHECK (processing_revision BETWEEN 1 AND 1000000),
    question_id TEXT CHECK (question_id = 'vacation-days-v1'),
    span_length INTEGER CHECK (span_length BETWEEN 0 AND 1024),
    previous_revision INTEGER NOT NULL CHECK (previous_revision BETWEEN 0 AND 1000000),
    revision INTEGER NOT NULL CHECK (revision BETWEEN 1 AND 1000000),
    CHECK (span_length IS NULL OR event = 'ai_answer_evidence_validated')
) STRICT;

CREATE TABLE aip_delivery_decision (
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    operation_id TEXT NOT NULL CHECK (length(operation_id) = 36),
    decision_ref TEXT NOT NULL UNIQUE CHECK (length(decision_ref) = 36),
    state TEXT NOT NULL CHECK (state IN ('SUPPRESSED', 'AUTHORIZED', 'RELEASE_UNCERTAIN')),
    derived_grant_id TEXT NOT NULL CHECK (length(derived_grant_id) BETWEEN 1 AND 80),
    processing_grant_id TEXT NOT NULL CHECK (length(processing_grant_id) BETWEEN 1 AND 80),
    recipient_id TEXT NOT NULL CHECK (length(recipient_id) BETWEEN 1 AND 80),
    content_revision INTEGER NOT NULL CHECK (content_revision BETWEEN 1 AND 1000000),
    connector_revision INTEGER NOT NULL CHECK (connector_revision BETWEEN 1 AND 1000000),
    processing_revision INTEGER NOT NULL CHECK (processing_revision BETWEEN 1 AND 1000000),
    decided_at_us INTEGER NOT NULL CHECK (decided_at_us >= 0),
    release_count INTEGER NOT NULL CHECK (release_count IN (0, 1)),
    PRIMARY KEY (organization_id, operation_id),
    FOREIGN KEY (organization_id, operation_id)
        REFERENCES aip_execution (organization_id, operation_id),
    FOREIGN KEY (organization_id, derived_grant_id)
        REFERENCES aip_derived_delivery_grant (organization_id, derived_grant_id),
    CHECK ((state = 'SUPPRESSED' AND release_count = 0)
        OR (state = 'AUTHORIZED' AND release_count = 0)
        OR (state = 'RELEASE_UNCERTAIN' AND release_count = 1))
) STRICT;

CREATE UNIQUE INDEX aip_one_derived_grant
    ON aip_derived_delivery_grant (organization_id, principal_id, resource_id, recipient_id)
    WHERE enabled = 1;
CREATE INDEX aip_grounding_audit_org
    ON aip_grounding_audit (organization_id, audit_seq);
CREATE UNIQUE INDEX aip_grounding_grant_revision
    ON aip_grounding_audit (revision)
    WHERE event = 'derived_delivery_grant_changed';
```

Prohibido en estas tablas: documento, pregunta, prompt, cita, respuesta, días, meses, offsets, digest, token y texto de excepción. `span_length` es el único dato de tamaño, y solo en el evento de evidencia.

Compatibilidad que el código futuro tendría que cumplir, sin cambiar los comandos C02:

1. V1 válido: versión 1, contrato v1, checksum de 001, `schema_ddl` igual al oráculo 001, `quick_check`, claves foráneas y las invariantes actuales de `aip_audit` y `aip_execution`.
2. `migrate_to_v2` es un comando explícito del administrador sintético. `initialize` y la apertura normal no migran.
3. La transacción hace `BEGIN IMMEDIATE`, vuelve a validar V1, copia `aip_store` a `aip_store_next` con versión 2, el mismo `store_id`, checksum de 002 y checksum de 001, elimina `aip_store`, renombra, crea las tres tablas y los índices, valida el oráculo V2 y confirma.
4. Si cualquier paso falla, `ROLLBACK`. El archivo sigue siendo V1. No hay reparación automática.
5. Un store cuyo `sqlite_master` no coincide ni con V1 ni con V2, o cuya versión no es 1 ni 2, se rechaza. No se adopta ni se migra por heurística.
6. Reabrir V2 válido no vuelve a ejecutar 002.
7. Las pruebas C02 siguen creando V1 con `initialize` y usando `policy`, `reserve`, `consume`, `observe_entry`, `finish` y `deny` sobre las tablas viejas. Esos SQL no cambian. En V1, los métodos nuevos responden no disponible.
8. No existe downgrade. El código nuevo no reaplica 001 sobre V2. El código C02 actual, si abre un V2, falla cerrado porque el oráculo 001 ya no coincide. Un archivo a medio borrar tampoco se acepta.
9. El commit de la migración usa el mismo par de fallos inyectables de antes y después del `commit`. Si el resultado es ambiguo, la siguiente apertura tiene que ver V1 completo o V2 completo. Cualquier otra forma queda rechazada y no se reintenta a ciegas.
10. Una decisión `AUTHORIZED` encontrada al reabrir, sin proceso vivo que haya retornado, pasa a `RELEASE_UNCERTAIN` en una transacción nueva que no contiene texto y no habilita otro envío.

`SQLiteExecutionLedger.__init__` calcularía un segundo oráculo aplicando 002 sobre una memoria que ya tiene 001. `_validate` bifurca por `schema_version`. Esa es la única ampliación interna. Los métodos C02 no ganan parámetros ni escriben las tablas nuevas.

## 11. M02 y dependencias

M02 sigue abierto en el workflow de cuatro nodos: ese código todavía llama a los helpers privados y mantiene dos decisiones B a propósito. No se resuelve reescribiendo TASK 005 dentro de C03.

M02 para el consumidor nuevo sí es un incremento interno explícito de C03, y es el primer tramo antes de componer el grafo. DESIGN-001 ya lo condiciona a la aparición de este segundo consumidor. No hace falta una EPIC aparte, ni un framework de entregas, ni retirar las dos fronteras B existentes.

M01 no se toca. El grafo nuevo usa owners y `finally`, no el scrub por frames.

También son dependencias de implementación, no de esta Phase A: el método `invoke_once_observed`, la migración nueva de auditoría y un fixture sintético adicional para el caso positivo. El fixture de DEMO-001 permanece como caso de insuficiencia.

## 12. Protocolo A/B/C

Seis autoridades, sin unirlas: identidad de plataforma, autorización local A/B, autorización externa simulada, autorización C, perfil del fake y autorización del destinatario de la respuesta. Una credencial de API no es ninguna de ellas. C no concede B. B documental no concede la respuesta derivada.

Secuencia de una llamada. Los puntos de inferencia están fuera de transacciones SQLite.

1. Frontera reconocida y argumentos cerrados.
2. Reader público: A, lectura offline, B documental y auditoría del conector. Si B falla, no hay bytes y no hay fake.
3. Evidencia de origen en el owner: organización, instancia, tenant, recurso, versión registrada, revisión de contenido, clasificación, correlación y longitud. Sin digest en auditoría.
4. C01 dentro de `prepare`: A y B públicos otra vez, grant C completo, perfil fake, pregunta allowlisted. `ALLOW_PROCESSING` todavía no ejecuta.
5. Reserva e intent durables. Solo entonces existe la lease.
6. Consumo, entrada al fake y `finish`. Durante el fake no hay transacción de ninguno de los dos archivos.
7. Observador: grounding contra los bytes aún vivos. Después, limpieza C02.
8. Si no hay evidencia, supresión. No se revalida para «salvar» una respuesta.
9. Fuera del grafo, con el buffer de lectura todavía vivo: se toma el `RLock` en proceso del store conector y la barrera del ledger C. Se lee un snapshot con la transacción de lectura ya existente (`snapshot`, `BEGIN`, sin `BEGIN IMMEDIATE`). No se entra a `delivery_guard`, porque esa salida confirma una transacción de escritura aunque no haya ninguna fila definida para esta operación.
10. Dentro de ese intervalo se revalida A, B documental, el permiso derivado, C01 con el envelope propio, el patrón sobre el buffer de lectura y el permiso externo simulado (`T_ext`). Eso es `T_auth` local: la última comprobación antes de escribir la decisión. Los writers en proceso del conector esperan el `RLock`. Un writer de otro proceso no lo toma. Esa diferencia queda dentro de la ventana residual que el Product Owner acepta solo para laboratorio offline.
11. La única escritura de esta fase es la del store C: una fila `SUPPRESSED` o `AUTHORIZED`, más la auditoría de evidencia y de decisión, en una transacción `BEGIN IMMEDIATE`. `release_count` queda en 0. No hay texto ni enteros de la plantilla. Se suelta el `RLock` del conector sin commit de aplicación. Después se confirma la transacción C. Si no confirma, no hay frase.
12. Solo si el commit C de `AUTHORIZED` quedó confirmado se anula el buffer de lectura, se renderiza la plantilla desde los dos enteros y el estado de memoria pasa a `ATTEMPTED`. El retorno entrega la frase al llamador. El callee no registra `OBSERVED`. Si la excepción ocurre cuando esa frase ya pudo escapar, el estado pasa a `UNKNOWN` y, si el proceso sigue vivo, una transacción posterior marca `RELEASE_UNCERTAIN` con `release_count = 1`. No hay segundo intento.

El store del conector, en la entrega derivada, no inicia escritura, no modifica tablas y no confirma un commit de aplicación. La fila B escrita antes por el reader sigue siendo entrega documental. La frase de DESIGN-001 que pedía «commit conector y luego commit C» no se cumple con un commit vacío: aquí el conector solo se lee, y el único commit de decisión es el de C. No hay atomicidad entre los dos archivos, el proceso y el llamador. No hay revocación global.

## 13. Línea temporal transaccional

| Punto | Qué puede dejar de ser válido | Efecto si se observa |
|---|---|---|
| Antes del reader | A o B ya revocados | Cero lectura y cero fake |
| Durante la lectura | B o permiso externo | El propio `execute` suprime documentos |
| Antes de `prepare` | C, perfil, revisión o bytes distintos de la evidencia | Cero lease |
| Durante el fake | B, C, revisión, destinatario o bytes | No se ve hasta el sello posterior. El fake puede haber corrido. No se deshace ese hecho. No se entrega |
| Después de `COMPLETED` y antes del observador | El candidato está a punto de borrarse | El observador tiene que correr antes de `_cleanup` |
| Durante grounding | Revisión o bytes distintos | `CANDIDATE_INVALID` o revocación, sin frase |
| Después de soltar el `RLock` y antes del commit C | Writer del conector, incluido otro proceso | Posterior a `T_auth`. El Product Owner acepta esta ventana solo en laboratorio offline. No es revocación global ni atomicidad |
| Después de `T_ext` | Permiso externo simulado | El snapshot SQLite no congela ese permiso |
| Commit C confirmado como `AUTHORIZED` y caída antes del retorno | El llamador pudo no recibir la frase | Reapertura: `RELEASE_UNCERTAIN`, sin reenvío |
| `ATTEMPTED` y excepción | La frase pudo salir de la pila | `UNKNOWN`, sin segundo intento |
| Después de que el llamador observa el retorno | Revocación tardía | No retracta la frase ya recibida. El callee no tenía una prueba anticipada de esa recepción |

## 14. Revocaciones y carreras

Cada transición de la tabla anterior se prueba con un writer independiente. Un snapshot tomado antes del guard no sirve para `T_auth`. Un cambio intentado mientras el guard está tomado no cuenta como confirmado.

Casos bloqueantes ya pedidos por el plan:

- revocación del permiso derivado, de C o del conector confirmada antes de `T_auth`;
- writer en proceso bloqueado por el `RLock` mientras dura el chequeo;
- snapshot de lectura del conector seguido de fallo del commit C, sin fila nueva en el conector;
- cambio del conector después de soltar el `RLock` y antes del commit C o del retorno;
- cambio externo después de `T_ext`;
- expiración durante el cierre;
- caída con `AUTHORIZED` ya confirmado y retorno no observable por el callee.

No hay bypass de autorización para ganar esas carreras. La ventana posterior a `T_auth` permanece aceptada solo como límite de laboratorio offline. No autoriza a describir revocación global ni una transacción distribuida. Un writer de otro proceso puede confirmar mientras el `RLock` local está tomado, porque ese lock no es un lock SQLite de escritura.

`UNKNOWN` y `UNCERTAIN` de C02 siguen sin ser éxito, sin liberar cuota incierta y sin reintento automático. `RELEASE_UNCERTAIN` de C03 tampoco se reintenta. La clave `(organization_id, operation_id)` impide una segunda fila. No hay API que devuelva la frase a partir de `decision_ref`. Una pregunta repetida es otra operación, con otra lease y otra fila.

## 15. Auditoría y persistencia

C02 ya persiste sus diez eventos en `aip_audit`. El DDL de la sección 10.1 no inserta ahí los eventos nuevos y no cambia ese CHECK. La tabla `aip_grounding_audit` lleva `ai_answer_evidence_validated`, `ai_derived_delivery_decided`, `ai_derived_delivery_revocation_detected` y `derived_delivery_grant_changed`. El nombre de revocación no reutiliza la fila de C02: si C02 ya escribió `ai_processing_revocation_detected`, esa fila sigue siendo el hecho de procesamiento. La fila nueva es solo la observación de C03.

`ai_derived_delivery_decided` confirma `AUTHORIZED`, `SUPPRESSED` o `UNKNOWN` en la misma transacción que `aip_delivery_decision`. Nunca confirma `OBSERVED`. `span_length` puede acompañar a la validación de evidencia. Offsets, días, meses y texto no entran.

Cada transacción C la inicia el ledger, con `BEGIN IMMEDIATE`, después de `_validate`. El commit es el de esa conexión. Si el fallo inyectado queda después del `commit` y no se puede saber si confirmó, la reapertura exige un V2 íntegro o rechaza el archivo. No se fabrica la fila en un sink caído. Si el sink no está disponible antes de `prepare`, no hay lease. Si falla después de un `COMPLETED` ya confirmado, no hay frase y se conservan solo las filas confirmadas.

El conector no escribe auditoría nueva en la entrega derivada. Su fila de entrega documental, anterior, no se lee como prueba de esta decisión.

## 16. Privacidad y ownership

Cuatro sitios, con dueños distintos:

| Sitio | Qué retiene | Hasta cuándo |
|---|---|---|
| Owner de lectura | Buffer propio creado con `bytearray` y `bytes`, más el resultado documental hasta retirarlo del marco | Hasta la recomprobación de `T_auth`. Después se anula, antes de renderizar |
| Owner del gateway C02 | Bytes de fuente, pregunta, input y candidato | Hasta `_cleanup`, que corre aunque el observador falle. C03 no guarda un alias después |
| Owner de respuesta C03 | Veredicto, offsets y dos enteros en memoria; envelope y `SourceEvidence` para revalidar C01 | Los enteros viven hasta construir el retorno. El envelope se anula en el `finally` |
| Llamador de confianza | La `str` de la frase, solo si el retorno ocurre | Fuera del callee. El callee no puede probar que llegó. No se persiste |

El estado del grafo no recibe owners, buffers, pregunta ni enteros. No hay checkpoint ni historial. No se usa `frame.clear`, `f_locals`, `gc` ni introspección global. Las pruebas de canario tienen que demostrar que la identidad del buffer de lectura no es la del buffer C02 y que, después del `finally`, ni el observador ni el owner de respuesta apuntan al owner C02.

Una denegación visible al solicitante es un solo código cerrado, el mismo para falta de permiso derivado, cruce de organización, revocación y B denegado. No incluye cifras, citas, ids ajenos ni un veredicto de insuficiencia. La insuficiencia, con su mensaje fijo y sin números, solo sale cuando el permiso derivado y B/C ya autorizaron una respuesta y el patrón no está. La diferencia fina queda en la auditoría de la propia organización.

POSIX sigue sin soporte. Writers no coordinados y los dos archivos sin atomicidad distribuida siguen como límites. El symlink físico de Windows pendiente no forma parte de esta fase.

## 17. Amenazas

Se reutilizan AI-T01 a AI-T18. Esta fase no las da por probadas. El fake determinista no es evidencia contra un LLM real.

| ID | Aplicación en esta propuesta |
|---|---|
| AI-T01 | El envelope reconocido fija organización y recurso. La pregunta no aporta principal ni permiso. |
| AI-T02 | Grants y perfil están fuera del documento. El texto hostil no cambia el snapshot. |
| AI-T03 | El único perfil ejecutable sigue siendo `fake-enterprise-extractive-v1` / `in-process-offline`. Sin fallback. |
| AI-T04 | Revisión, longitud y bytes del owner. Un documento sustituido invalida el span. |
| AI-T05 | Una fuente, sin herramientas, sin URL y sin credencial hacia el fake. |
| AI-T06 | El validador exige igualdad de bytes y patrón. Citas cruzadas y offsets falsos producen `CANDIDATE_INVALID`. |
| AI-T07 | Revalidación en `prepare`, al consumir, al observar el resultado y en `T_auth`. |
| AI-T08 | El único commit de la decisión derivada es el del store C. Un snapshot del conector no es esa decisión. `UNKNOWN` no se reintenta. |
| AI-T09 | Metadata en el grafo. Sin saver ni tracing heredado. |
| AI-T10 | Sin nuevo `frame.clear` global. Owners ajenos, incluido el de TASK 005, no se limpian desde C03. |
| AI-T11 | Claves por organización. Sin registro de respuestas. |
| AI-T12 | Límites ya fijados: 1024, 256, 2048, 512 bytes, 256 unidades `fake-byte-v1`, 5 segundos, 0 reintentos, 1 slot. |
| AI-T13 | El owner de respuesta no conserva el span. `bytes()` sobre un `bytes` no se usa como copia. La tabla nueva no guarda texto ni enteros de la plantilla. |
| AI-T14 | El fake no tiene credencial. Una key no sería un grant C. |
| AI-T15 | No se suman grants parciales ni se restaura una revisión vieja para entregar. |
| AI-T16 | Fixture sin la cláusula: insuficiencia. Segunda cláusula distinta: abstención. |
| AI-T17 | Denegación cross-org sin metadata del otro lado. |
| AI-T18 | Sin imports clínicos, sin Human Review, sin RAG y sin habilitar el Gate C del grafo viejo. |

La matriz de inyección de DESIGN-001 se conserva: las instrucciones del documento se prueban como datos, y el validador rechaza citas reescritas o condiciones omitidas.

## 18. Matriz de pruebas

Ningún caso se ejecuta en Phase A. Todos son offline, con fixtures sintéticos, basetemp propio y sin red. Cada fila crítica tiene negativa. Los identificadores no sustituyen los D02 del plan; DEMO-002 sigue sin autorizar.

| ID | Caso | Resultado exigido |
|---|---|---|
| C03-01 | Patrón único en fixture nuevo, A/B/C y permiso derivado vigentes | `EVIDENCE_FOUND`, commit `AUTHORIZED` y frase de plantilla. Una sola entrada al fake |
| C03-02 | Texto DEMO-001, sin días | `EVIDENCE_INSUFFICIENT`, mensaje fijo, cero cifras |
| C03-03 | Candidato distinto de `source_bytes[start:end]` | `CANDIDATE_INVALID`, cero entrega |
| C03-04 | Offset de carácter Unicode o corte UTF-8 inválido | `CANDIDATE_INVALID` |
| C03-05 | Bytes cambiados después de la evidencia | Supresión. La revisión vieja no se repara con el candidato |
| C03-06 | `source_ref` o recurso de otra organización | Cero fake si falla antes de `prepare`; si el cruce aparece después, supresión y sin cita ajena |
| C03-07 | Owner o lease de otra invocación | `lease_invalid` o fallo cerrado, sin leer el otro candidato |
| C03-08 | `recipient_id` distinto del request | El puerto deniega. Cero frase |
| C03-09 | Gate B DENY | Cero fake si ocurre en el reader o en `prepare`. Si ocurre en `T_auth`, fake ya contado y entrega suprimida |
| C03-10 | Gate C DENY y, por separado, UNAVAILABLE | Cero fake en el previo. UNAVAILABLE no se convierte en denegación silenciosa ni en respuesta |
| C03-11 | Revocación confirmada antes de la salida | `REVOCATION_DETECTED` o supresión, sin frase |
| C03-12 | Revocación durante el fake | Una entrada observada, cero entrega, sin deshacer el procesamiento |
| C03-13 | Snapshot de lectura del conector y fallo del commit C | Cero frase y cero fila nueva en el conector. La fila B documental previa no cuenta |
| C03-14 | Sink caído antes de `prepare` | Cero fake. Después de `COMPLETED`, supresión y solo filas confirmadas |
| C03-15 | Caída después de `AUTHORIZED` y antes del retorno | Reapertura en `RELEASE_UNCERTAIN`, sin reenvío |
| C03-16 | Segunda llamada con la misma lease o el mismo id de respuesta | Prohibida. No existe API de recuperación |
| C03-17 | `CancelledError` y `KeyboardInterrupt` antes, durante y después del fake, con fallo de close/clear | La señal original sigue. Cero entrega. El otro owner permanece |
| C03-18 | Dos organizaciones concurrentes | Aislamiento de owners, leases, auditorías y respuestas |
| C03-19 | Canarios en documento, pregunta y candidato | Ausentes del estado, de callbacks, de checkpoints, de logs y de ambas SQLite |
| C03-20 | Regresión de C01 y C02 | `invoke_once` sigue sin devolver candidato. `ALLOW_PROCESSING` sigue sin ejecutar por sí solo |
| C03-21 | Reader, control plane, Graph offline, workflow de cuatro nodos y DEMO-001 | El Gate C antiguo sigue en DENY. Gate D sigue DISABLED. Los helpers privados del workflow viejo siguen cubiertos por sus pruebas |
| C03-22 | Flags de red, Graph, Gemini u otro proveedor | Cero sockets nuevos y cero constructores de proveedor real |
| C03-23 | Sin fila `aip_derived_delivery_grant` | Denegación cerrada, aunque B documental sea válido. Cero cifras |
| C03-24 | B y propósito de lectura válidos, permiso derivado ausente o con el propósito de lectura | Denegación. El propósito `synthetic-demonstration` no alcanza |
| C03-25 | `enabled = 0` o revisión distinta del permiso derivado antes de `T_auth` | Supresión, sin frase |
| C03-26 | Observador de otra clase o de otra instancia | El gateway no lo ejecuta. Cero lectura del candidato |
| C03-27 | Segunda entrada del mismo observador | No vuelve a ver bytes |
| C03-28 | Observador reconocido en otra organización u otra operación | Rechazo. No cruza el candidato |
| C03-29 | Callable pasado en los argumentos de `invoke` | La firma no lo acepta. No hay ejecución de código del documento |
| C03-30 | Canario `bytes` compartido con C02 | `buffer_de_lectura is buffer_c02` es falso. Tras el `finally`, no queda alias al owner C02 |
| C03-31 | Store V1 válido y `migrate_to_v2` | Queda V2, mismo `store_id`, checksums de 001 y de 002, tablas C02 intactas en su `CREATE` |
| C03-32 | Fallo inyectado durante 002 | `ROLLBACK`. La reapertura sigue validando V1 y los comandos C02 |
| C03-33 | `sqlite_master` a medias o versión distinta de 1 y 2 | Apertura no disponible. No se adopta ni se repara solo |
| C03-34 | Intento de downgrade o apertura V2 con el oráculo 001 | Rechazo. No se reaplica 001 |
| C03-35 | Commit C ambiguo | Sin frase. La siguiente apertura no reintenta la migración ni la entrega |
| C03-36 | Fila `AUTHORIZED` y proceso muerto antes del retorno | Reapertura en `RELEASE_UNCERTAIN`. Cero reenvío |
| C03-37 | Nuevo `invoke` con el mismo `operation_id` o `decision_ref` | La clave única lo impide. No hay lectura de la frase |
| C03-38 | Revalidar C01 después de `_cleanup` | El mismo envelope y la misma evidencia, snapshot fresco, sin lease nueva y sin identidad nueva |
| C03-39 | Denegación, cruce de organización e insuficiencia no autorizada | El solicitante ve el mismo código cerrado, sin cifras ni ids ajenos. La insuficiencia solo aparece si la entrega derivada estaba autorizada |

La selección futura, cuando exista autorización de implementación, incluye la suite nueva y las suites de conector, control plane, Graph, workflow y demo. No se ejecutan en esta fase. No se usan para declarar C03 implementado.

## 19. Plan incremental

Solo después de aprobar esta propuesta y de autorizar cada tramo. Un tramo no abre el siguiente.

1. **Permiso derivado y puerto.** Tabla y predicado de una fila, más `authorize_derived_delivery`. Sin cambiar `PolicyEvaluator` ni el esquema del conector.
2. **Observador reconocido.** `invoke_once_observed(lease)` y la clase única. `invoke_once` no cambia.
3. **Validador determinista.** Escalares sobre el buffer de lectura. Fixture viejo en insuficiencia. Fixture nuevo solo para el positivo.
4. **Grafo nuevo.** Nodos de la sección 9. Sin tocar los cuatro nodos ni M01.
5. **Revalidación final.** `RLock` y snapshot de lectura, sin `delivery_guard`, más las carreras de la sección 14.
6. **Migración 002.** Comando explícito, oráculo V2 y preservación de las pruebas V1. Sin DDL sobre 001.
7. **Pruebas de composición.** C03-01 a C03-39 más las regresiones de conectores. Gate de publicación separado.

Módulos que una implementación futura tendría que tocar, y por qué: `service.py` para el puerto; `gateway.py` para el observador; un módulo nuevo de grounding y otro de workflow; una migración 002 nueva; fixtures y pruebas nuevas. No haría falta un microservicio, ni PostgreSQL, ni un proveedor real, ni DEMO-002.

`invoke_once` de C02, el evaluador C01, el grafo de TASK 005, las migraciones clínicas y el adaptador Graph no cambian su comportamiento actual en los tramos 4 a 7, salvo la llamada al método nuevo.

## 20. Riesgos residuales

- El `RLock` en proceso no detiene a un writer de otro proceso. Esa ventana, y la de `T_ext`, quedan aceptadas solo en laboratorio offline.
- Dos SQLite, el proceso y el llamador no son atómicos. El conector no confirma una escritura de entrega derivada.
- `AUTHORIZED` durable puede quedar sin retorno. La reapertura lo marca `RELEASE_UNCERTAIN` y no reenvía.
- `bytes()` sobre un `bytes` no copia. Anular atributos no borra otras referencias ni la `str` del llamador.
- Un store que no coincide con el oráculo V1 ni con el V2 se rechaza. No hay downgrade.
- M01 sigue dependiendo de la forma de los frames del workflow viejo.
- M02 sigue abierto para ese workflow.
- No hay IAM empresarial, Graph live, modelo real, RAG, MCP ni Gate D.
- Un fake que extrae un patrón no demuestra resistencia de un modelo generativo.

## 21. Decisiones que requiere el Product Owner

La dirección general ya fue aceptada. Phase B1 aplicó la fila y la migración con las correcciones de la sección 22. Siguen abiertas para fases posteriores:

1. Aprobar la fila `aip_derived_delivery_grant` como autoridad separada, sin extender el enum `Gate` ni el esquema del conector.
2. Aprobar `invoke_once_observed(lease)` sin callback de caller, con un solo observador reconocido por identidad de objeto.
3. El DDL de la sección 10.1 no se aplica. El DDL vigente es el archivo 002 descrito en la sección 22. 001 y los comandos C02 no cambian.
4. Aprobar que la entrega derivada no escribe en el store del conector y que el único commit de decisión es el de C.
5. Mantener la aceptación de la ventana posterior a `T_auth` solo para laboratorio offline, sin revocación global ni atomicidad distribuida.
6. Aprobar que `OBSERVED` lo afirma el llamador y que `AUTHORIZED` al reabrir pasa a `RELEASE_UNCERTAIN` sin reenvío.
7. Confirmar que la insuficiencia visible solo existe después de la autorización derivada y que el resto de denegaciones comparten un código cerrado.
8. Confirmar que el fixture DEMO-001 sigue siendo insuficiencia y que M01 no se rehace con introspección de frames.
9. Phase B1 quedó autorizada y está en el árbol de trabajo, sin commit. Siguen sin autorizar el observador, el grounding, el grafo, la entrega y Phase B2.

## 22. Cierre P1 y alcance real de Phase B1

Phase B1 persiste y administra el permiso derivado. No entrega contenido, no crea un endpoint y no modifica `ConnectorService` ni `EnterpriseDocumentWorkflow`.

### Revisión

`processing_revision` sigue siendo `aip_store.revision`. `change_policy` solo ejecuta `UPDATE aip_store SET revision=revision+1` y un evento `ai_processing_policy_changed`. No toca la revisión derivada.

`derived_delivery_revision` vive en `aip_derived_revision`, una fila por organización. La ausencia de fila significa 0. Los valores almacenados empiezan en 1.

`change_derived_grant` compara, dentro de `BEGIN IMMEDIATE`, la revisión C esperada con `aip_store.revision` y la revisión derivada esperada con la fila de la organización. Si alguna no coincide, la transacción termina en `revision_conflict` y no escribe. Si coinciden, la misma transacción guarda en el grant la revisión C vigente, sin incrementarla, y `derived_delivery_revision = esperada + 1`, actualiza el contador de la organización a ese mismo valor y agrega `derived_delivery_grant_changed` con `revision = previous_revision + 1`.

El grant recién escrito coincide con ambos contadores, así que su propia actualización no lo deja vencido. Un `change_policy` posterior, o una administración derivada que mueva el contador sin reescribir ese grant, deja la evaluación futura denegada. La auditoría guarda `policy_changed`. La revocación del propio grant lo deja deshabilitado en la revisión nueva y la auditoría guarda `derived_delivery_not_granted`. La fila histórica y su auditoría no se reescriben. Volver a habilitar el permiso exige una versión nueva.

Al reabrir, `_validate_v2` exige que, por organización, los eventos `derived_delivery_grant_changed` sean contiguos desde 1 y que su cantidad y su máximo coincidan con `aip_derived_revision`. No exige que cada grant habilitado tenga esa revisión: el predicado lo comprueba al evaluar. Un cambio C no vuelve el archivo ilegible.

El commit ambiguo se modela con el fallo posterior a `commit`. El archivo queda en V2 completo. El fallo anterior a `commit` revierte a V1. Una forma intermedia no se repara ni se adopta.

### Migración

`migrate_to_v2` es explícito y exige administrador sintético reconocido, Windows y el candado de propietario. `initialize` y la apertura no lo llaman. Antes de escribir exige que no haya leases vivos ni filas `HELD`, `UNCERTAIN`, `INTENT`, `CONSUMED` o `ENTERED`. Esas reservas no se liberan. La transacción valida V1, aplica 002, sustituye `aip_store`, crea las tablas nuevas, valida el oráculo V2, las claves foráneas y las secuencias, y confirma. Cualquier fallo previo revierte. Un V2 ya migrado responde `revision_conflict`. No hay downgrade ni `ATTACH`. El oráculo V2 es el `sqlite_master` obtenido al aplicar 002 sobre el oráculo V1, no el borrador de la sección 10.1.

### Denegaciones

Una denegación anterior a T1 no fabrica `aip_execution` ni `aip_derived_delivery_grant`. Solo escribe `ai_derived_delivery_denied` si la auditoría confirma. `aip_delivery_decision.derived_grant_id` admite NULL y su clave foránea no exige un grant para `SUPPRESSED`.

Una supresión posterior a T1 exige una ejecución de la misma organización. Copia el destinatario desde esa fila, deja `derived_grant_id` vacío, escribe `SUPPRESSED` con `uncertainty_recorded = 0` y audita `ai_derived_delivery_suppressed`. No crea una ejecución.

Una identidad no reconocida no aporta organización ni referencias. La fila anónima deja todos los identificadores en NULL, con resultado `UNAVAILABLE` y razón `authority_unverifiable`. Un auditor reconocido que intenta administrar o evaluar queda auditado en su propia organización, sin ids ajenos, y recibe `scope_mismatch` antes de consultar el permiso. Ese código distingue el rol, no la existencia de un grant. Un cruce de organización, un permiso ausente, uno revocado, una revisión obsoleta, un destinatario distinto y una vigencia vencida producen en `assess_derived_delivery` el mismo `processing_not_granted`. La razón fina queda solo en la auditoría de la organización del llamador, sin el recurso ni el destinatario de la consulta. Si el fallo ocurre antes del commit de esa auditoría, no queda denegación persistida.

`uncertainty_recorded` sustituye a `release_count`. Vale 0 en `SUPPRESSED` y `AUTHORIZED`, y 1 en `RELEASE_UNCERTAIN`. No afirma que el llamador recibió bytes. Phase B1 no inserta `AUTHORIZED` ni `RELEASE_UNCERTAIN`.

### Procedencia

Se elige la alternativa A para una fase posterior: una sola llamada pública a `ConnectorService.execute`, con un emisor sintético reconocido que vincule ese resultado, el contexto, la solicitud, el documento y la correlación. No se envuelve `EnterpriseDocumentWorkflow.invoke`, porque esa frontera ya se cerró y una segunda lectura no puede atribuirse a la primera. Phase B1 no crea ese emisor. Phase B2 permanece bloqueada hasta que exista y hasta que una lectura autorizada produzca un resultado original, una evidencia y una operación C de esa misma llamada.

### Comandos de esta fase

`change_derived_grant` administra el permiso. El ledger fija `content_kind`, la operación, el propósito y la clasificación; el caller no los aporta. El grant C de la misma organización tiene que existir, estar habilitado y coincidir en versión. `assess_derived_delivery` solo comprueba ese permiso sintético. Un acierto devuelve `DerivedGrantMatch` y no escribe decisión ni entrega bytes. Ese objeto no es autorización A/B/C, ni ejecución de modelo, ni entrega final. `suppress_derived_delivery` registra la supresión posterior a T1. `read_derived_audit` devuelve solo la organización del administrador o del auditor. Phase B2 no puede componer el flujo hasta que un emisor autorizado vincule una sola lectura pública con su evidencia.

## 25. B2-GRD implementado

`EnterpriseModelGateway.invoke_once` no cambia de contrato: no observa y no devuelve candidato. `invoke_once_observed(lease)` no acepta callback, resultado fabricado ni otro modelo. Antes de invocar exige que la frontera B2-RUNTIME reconozca al owner, la lease y el `DeterministicVacationGrounding` creado por `compose`. Si no lo reconoce, responde `DENY` y no llama al fake.

La observación ocurre después del commit `COMPLETED` y fuera de la transacción SQLite, mientras el candidato sigue en el `ExecutionOwner`. Después corre el mismo `_cleanup`. Un fallo del observador o de la limpieza no reescribe `COMPLETED`, no repite la invocación y no deja cifras utilizables. Una cancelación anterior al commit sigue el camino C02. Una cancelación posterior al commit no vuelve a cerrar la fila.

`TrustedEnterpriseSourceBoundary.run` devuelve `RuntimeExecution` con estado técnico, motivo, organización, operación, entradas y reserva. No devuelve texto, candidato ni enteros. Esos enteros, si el veredicto interno es `EVIDENCE_FOUND`, viven en `GroundingRecord` hasta `close`. El documento de laboratorio sin la cláusula queda en `EVIDENCE_INSUFFICIENT`. Dos cláusulas con números distintos también. No hay frase final, ni fila `AUTHORIZED` de entrega, ni LangGraph nuevo.

`close` de una admisión `PREPARED` sin ejecución sigue cancelando esa reserva. `close` después de `COMPLETED` no emite otro `CANCELLED`. `UNCERTAIN` no se concilia. El detalle y los conteos están en el [runbook B2-GRD](enterprise-grounded-answer-task-c03-b2-grd.md).

## 26. E2E con cierre de autoridad y sellado

La composición vive en `EnterpriseAnswerFlow`. El grafo `enterprise_answer_delivery` tiene siete nodos y no tiene checkpointer, store ni caché. Su estado solo lleva fase, motivo, organización, operación, entradas, reserva y decisión. El documento, la pregunta, la evidencia, la lease, el `GroundingRecord`, los enteros y la frase permanecen en la composición de esa invocación.

La frase permitida sale de la plantilla fija y de los enteros del grounding reconocido para `vacation-days-v1`. Si el veredicto es `EVIDENCE_INSUFFICIENT` y la conjunción A/B/C/B1 sigue vigente, la entrega es una abstención fija, sin cifras. Cualquier otro veredicto no construye frase.

`commit_final_delivery` inserta `AUTHORIZED` solo si el caller ya permitió la conjunción y el ledger vuelve a comprobar el grant derivado, la ejecución `COMPLETED`/`CHARGED`, el perfil fake y `question_id`. Si no, inserta `SUPPRESSED`. No altera la fila C02. La auditoría V2 no tiene un evento de autorización positiva; la fila de `aip_delivery_decision` es el registro durable.

La entrega es el `RecognizedDeliverySink` creado por `compose`. No lo aporta el caller. `LocalDelivery` no contiene la frase. `receive(context, request)` exige un contexto que la frontera de identidad reconoce, no vencido, del mismo principal y la misma organización, y una solicitud con el mismo destinatario, instancia, recurso, operación y propósito de la lectura autorizada. Conocer la cadena `recipient_id` no basta. `AUTHORIZED` es la decisión durable. `observed` es la aceptación local del sink y no demuestra que una persona haya leído la frase.

`seal_release_uncertain` deja `RELEASE_UNCERTAIN` solo si una lectura posterior confirma esa fila. Si el sellado o esa lectura fallan, la vista pública no inventa el estado: conserva `AUTHORIZED` cuando esa fue la última lectura confirmada, o no afirma decisión si la lectura durable también falló. La fase queda `UNCERTAIN`, no hay segundo `accept` y la misma invocación no vuelve a autorizar. Esa prohibición vive en el proceso. Una caída o un reinicio no demuestran que la frase no haya salido ni impiden una operación nueva con un permiso vigente. El detalle está en el [runbook E2E](enterprise-grounded-answer-task-c03-e2e.md).
