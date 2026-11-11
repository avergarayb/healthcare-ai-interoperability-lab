# TASK-C03 Phase B2 — frontera de evidencia de una sola lectura

Estado: diseño aprobado. B2-SRC lo implementó como emisor de laboratorio en `tests/`, no como código de producto. `TrustedSourceReadReceipt` existe solo en ese módulo. No hay puerto nuevo, observador, grounding, LangGraph nuevo ni entrega. La promoción a `app/` queda bloqueada.

Esta propuesta no modifica [la propuesta C03](enterprise-grounded-answer-task-c03-proposal.md), el [runbook B1](enterprise-grounded-answer-task-c03-b1.md), contratos, ADR ni código.

## 1. Estado y alcance

Objetivo: definir cómo una composición futura puede demostrar esta cadena, y ninguna otra.

Una llamada autorizada a `ConnectorService.execute` produce un resultado original. Un emisor reconocido de ese mismo proceso vincula una evidencia a ese resultado. Esa evidencia es la única que puede entrar en una operación Gate C.

Quedan fuera: `invoke_once_observed`, el validador determinista, el grafo nuevo, la frase final, el puerto de entrega, cambios de `ConnectorService`, `EnterpriseDocumentWorkflow`, C01, C02, B1, migraciones y cualquier módulo bajo `app/`. Gate D, RAG, embeddings, MCP, Graph live y un modelo real siguen apagados. Las pruebas de B2-SRC ejercen el emisor de `tests/` y no amplían el inventario AST.

## 2. Merge B1 verificado

`git fetch origin main` dejó `origin/main` en `c6dd2124713a4aad193dc9ddf7d66129c16d38d7`. El mensaje es `Merge pull request #119 from avergarayb/feature/enterprise-ai-processing-authorization-task-c03`. Los padres son `f1edf52f5d8a46fbad1538ab866dd3ac3aa01b0a` y el commit funcional B1 `393a42230551f7047fad205f3ee12e43ee9acab1`.

`main` local sigue en `138b748747f0e3d57f7da89c1fbc7c2b62cf5f8d` y no se actualizó. La rama de este diseño es `feature/enterprise-ai-processing-authorization-task-c03-b2`, creada desde `origin/main`, sin upstream.

## 3. Arquitectura existente

La lectura pública es [ConnectorService.execute](../../services/ai-service/app/enterprise_connectors/service.py). Devuelve `OperationResult`. No devuelve `EnterpriseResult`.

[EnterpriseDocumentWorkflow.invoke](../../services/ai-service/app/enterprise_workflows/document_read.py) llama a ese método una vez, cierra su `InvocationBoundary` y solo después construye `EnterpriseResult`. El documento que sale ya no tiene envelope ni request vivos.

C01 no lee durante `GateCPolicyEvaluator.evaluate`. El fixture de prueba llama a `execute` en `ProcessingLaboratory.issue` y registra `SourceEvidence` por identidad de objeto. Ese emisor es de test. `content_revision` lo aporta el argumento del fixture, no el resultado del conector.

C02 `prepare` recibe un envelope y una evidencia ya reconocidos. Reserva y solo entonces emite `ProcessingLease`. `ALLOW_PROCESSING` no ejecuta.

B1 `assess_derived_delivery` devuelve `DerivedGrantMatch` o `processing_not_granted`. No es autorización integral.

## 4. Contratos públicos actuales

| Pieza | Qué expone hoy | Qué no expone |
| --- | --- | --- |
| `OperationRequest` | `instance_id`, `resource_id`, `operation`, `purpose`, `recipient_id`, `policy_version` | principal, tenant, clasificación, bytes |
| `ConnectorExecutionContext` | `principal_id`, `organization_id`, vigencia | no se deserializa desde input |
| `IdentityBoundary.recognizes` | el contexto fue emitido por la frontera que lo reconoce | un id copiado no basta |
| `OperationResult` | `status`, `reason`, `correlation_id`, estados local/externo/entrega, `documents` | revisión de política, tenant, clasificación, eTag, principal |
| `UntrustedDocument` | `resource_id`, `organization_id`, `instance_id`, `version`, `text: str` | bytes, destinatario, propósito, correlación |
| `EnterpriseResult` | metadatos y los mismos documentos, después de cerrar el workflow | el `OperationResult` y el envelope |
| `SourceEvidence` | metadatos y `utf8_bytes`; el docstring dice que no lleva texto, digest ni eTag de Graph | el documento |
| `AIProcessingEnvelope` | operación C, contexto, request, versiones, pregunta | no es una lease |
| `DerivedGrantMatch` | organización, grant derivado y las dos revisiones que el caller ya presentó | no autoriza A/B/C ni entrega |
| `GraphReadAdapter.read` | termina en `SyntheticPage(text=str)` | el `eTag` se comprueba dentro del parser y no sale en la página |

`PolicyEvaluator.evaluate` sigue siendo el único evaluador A/B. Rechaza `Gate.AI_PROCESS` y `Gate.INDEX`. No se propone un segundo evaluador.

## 5. Problema de procedencia

`OperationResult` y `UntrustedDocument` son dataclasses construibles. Cualquier código puede copiar sus campos. La igualdad de `correlation_id`, versión o texto no prueba que ese objeto sea el retorno de una llamada concreta.

El workflow agrava el hueco. `invoke` cierra la frontera en `_close` y luego retorna los documentos. No queda un puerto para continuar desde esa misma operación. Tomar esos documentos y atribuirles una `SourceEvidence` creada con otra llamada a `execute` une dos lecturas.

El fixture C01 evita esa unión solo porque `issue` llama a `execute` y registra la evidencia en el mismo método. No es un puerto de producto. Además guarda `original_text` y compara el texto, no la identidad del `OperationResult`. El `content_revision` no sale del documento.

## 6. Alternativas

### A. Composición que llama una vez a `execute` y sella el recibo

Un emisor nuevo, en el mismo proceso, llama a `ConnectorService.execute`. El caller no entrega el resultado. Antes de devolver nada, el emisor registra un recibo no portable contra ese objeto resultado, ese documento, ese contexto y ese request. C01 sigue recibiendo la `SourceEvidence` que ese emisor crea en el mismo paso.

Cambios futuros: un módulo nuevo y el alta explícita en el inventario cerrado de arquitectura. No cambia `execute`, el workflow, C01 ni C02.

Falsificar el resultado exige entrar en el emisor o registrar un objeto que el emisor no creó. Una copia tiene otra identidad y no se reconoce. No aparece una segunda lectura si el emisor llama a `execute` una sola vez y exige `cache_size == 0`.

M01 no se toca: el emisor limpia sus propios atributos. M02 no se toca: no llama a `_validate_delivery` ni a `_event`. La revalidación A/B usa `PolicyEvaluator.evaluate`.

El hueco que A no cierra: `execute` no devuelve la revisión de política, el tenant ni la clasificación. Esos datos salen de una evaluación pública posterior, no de una segunda lectura. Si la revisión del store cambió durante la llamada, el emisor no adivina y no emite recibo.

### B. Puerto público nuevo del conector

Un método devolvería resultado y evidencia como una sola unidad. La procedencia nacería dentro de `execute`. Haría falta un tipo nuevo en el contrato del conector y una decisión sobre si `execute` sigue devolviendo documentos sueltos. El workflow y TASK 005 tendrían otro camino de lectura, con riesgo de usarlo como segunda lectura. M02 pide no abrir otro consumidor de la frontera privada; un puerto público nuevo es más amplio que el problema.

### C. Continuación del workflow

El workflow ya hizo la lectura única y tiene el `OperationResult` en `_Invocation`. Una continuación reconocida podría sellar el recibo antes de `_close`. También tendría que cambiar el ciclo de vida de TASK 005, convivir con `_scrub_owned_tracebacks` y seguir el protocolo privado de `_deliver`. Es el cambio más grande y el que más fácil reabre una frontera ya cerrada.

## 7. Decisión recomendada

Se recomienda la alternativa A.

A puede demostrar la pertenencia sin cambiar `ConnectorService`: la prueba no es la igualdad de campos, sino que el emisor reconocido es quien invocó `execute` y quien registró el recibo por identidad de objeto. Un resultado fabricado, copiado o proveniente del workflow no entra a ese registro.

B sería necesaria solo si el producto exigiera que el propio conector se niegue a entregar documentos sin un recibo. Hoy `execute` debe seguir sirviendo al workflow. Esa extensión no hace falta para la cadena de C03.

C queda descartada para este incremento.

## 8. TrustedSourceReadReceipt

Nombre candidato, no clase aprobada. Es un recibo de una lectura, reconocido dentro del proceso.

| Regla | Definición |
| --- | --- |
| Emisor | Un solo compositor de test o, en el futuro, el compositor de producto. Implementa el reconocimiento. `IdentityBoundary` reconoce el contexto; no emite este recibo |
| Operación | Una llamada a `execute` con `Gate.READ`, operación `READ`, `cache_size == 0`, adaptador offline y estado `DELIVERY_ALLOWED` con éxito externo y entrega permitida |
| Respaldo | El objeto `OperationResult` devuelto, su único `UntrustedDocument`, el `ConnectorExecutionContext` y el `OperationRequest` pasados a esa llamada, más la evaluación A/B del snapshot estable |
| Resultado | El recibo guarda la identidad de ese resultado. No se reconstruye desde ids |
| Ámbito | Organización, principal, instancia, tenant, recurso, destinatario, propósito y clasificación observados en esa llamada |
| Uso | Un solo paso hacia `prepare`. Cualquier intento, éxito o fallo, lo retira. Una revocación también lo retira |
| Expiración | No vive más que el contexto, el envelope C01 y el plazo corto que C01 ya impone al envelope |
| Validación | `recognizes(receipt)` es verdadera solo si el registro tiene ese objeto. `False` es no reconocido. Una excepción es autoridad no disponible |
| Copia | `replace` u otro constructor produce otro objeto. No queda registrado |
| Serialización | `__reduce_ex__` debe fallar. No hay pickle, JSON ni cruce de proceso |
| Reconstrucción | Un UUID, un digest o campos iguales no restauran el recibo |
| Cierre | `close` borra el registro, anula los atributos del owner y no deja un `get_document` |
| Bytes | El owner conserva el `bytes` canónico. Sustituir el `str` del documento no cambia ese buffer. La validación compara longitud y, en memoria, el buffer del owner |
| Varios documentos | Cero recibos. `READ` ya une las páginas en un documento. `CHILDREN` y `METADATA` no sirven para esta evidencia |
| Lectura parcial o fallo | Si el estado no es entrega permitida, si no hay exactamente un documento, si el texto está vacío o si la auditoría del conector falla, no hay recibo. La excepción no cuenta como evidencia |

No hay caché persistente ni credencial nueva.

## 9. Vínculo al resultado original

El compositor sigue este orden y no acepta atajos.

1. Exige `type(service) is ConnectorService`, `cache_size == 0` y adaptador offline, la misma condición que el constructor del workflow.
2. Lee la revisión del snapshot. Si no puede, se detiene.
3. Llama una vez a `execute(context, request)`.
4. Vuelve a leer la revisión. Si cambió, no emite recibo.
5. Exige `OperationResult` exacto, `DELIVERY_ALLOWED`, éxito externo, entrega permitida y un solo documento cuyo `organization_id`, `instance_id`, `resource_id` y `version` coincidan con el recurso resuelto por `PolicyEvaluator.evaluate` para ese mismo request.
6. Evalúa `Gate.READ` y `Gate.DELIVERY` con la API pública. No llama a `_validate_delivery` ni a `_event`.
7. Crea el recibo y la `SourceEvidence` y los registra juntos. El `read_correlation_id` es el `correlation_id` de ese resultado. El `operation_id` de C lo crea el compositor, no el caller.
8. Devuelve solo el recibo y el par reconocido. No devuelve el `OperationResult` para que otro código lo rellene.

`organization_id` y `principal_id` salen del contexto reconocido. `instance_id`, `resource_id`, `purpose` y `recipient_id` salen del request que viajó en la llamada. `tenant_id` y `classification` salen de la evaluación pública del snapshot estable. `registered_version` es `document.version`. `connector_revision` es esa revisión estable. `source identity` es la identidad del recibo en el registro del emisor.

No existe un eTag en `UntrustedDocument`, `OperationResult` ni `SourceEvidence`. El parser de Graph compara `ETag` y después devuelve solo texto. Esta propuesta no inventa un eTag.

## 10. Fuente y bytes canónicos

El conector entrega `str`. En la ruta Graph, `parser.content` exige `response.body` de tipo `bytes`, comprueba tamaño y `ETag`, y hace `decode("utf-8")`. El body no se conserva. `SyntheticPage.text` y `UntrustedDocument.text` son `str`.

La representación canónica de C03 es un único `document.text.encode("utf-8")`, hecho una vez, guardado en el owner del recibo. `encode` crea un buffer nuevo. `bytes(existing_bytes)` no crea una copia; el diseño no lo usa como copia.

Ese buffer demuestra la forma UTF-8 del `str` que el servicio aceptó. No demuestra conservar los bytes remotos previos a la decodificación, ni ausencia de normalización anterior al `str`. No se hace una segunda lectura para obtener bytes.

La longitud de C01 y C02 es `len(canonical)`, no el número de caracteres. Un carácter multibyte cuenta por sus bytes. El límite por defecto de C01 es 1024 bytes de fuente. 1024 puede seguir. 1025 conserva el recibo de lectura, pero no es elegible para C: no se trunca. El texto del documento no se normaliza.

El owner no publica el buffer por `repr`. Al cerrar, anula su atributo. Eso no borra otras copias ni promete borrado criptográfico.

## 11. SourceEvidence C01

`SourceEvidence` actual basta. No hace falta un puerto nuevo en `GateCPolicyEvaluator`. El emisor la construye desde el recibo, no desde campos sueltos del caller.

| Campo | Origen obligatorio |
| --- | --- |
| `source_ref` | Identificador creado por el emisor al registrar el recibo |
| `organization_id`, `instance_id`, `resource_id` | Documento de esa llamada, igual al contexto y al request |
| `tenant_id`, `classification` | Evaluación pública del snapshot estable |
| `registered_version` | `document.version` |
| `content_revision` | El mismo `document.version`. El conector no tiene otra revisión de contenido. El argumento `content_revision` del fixture no es autoridad |
| `provenance` | `synthetic-documents-v1`, como exige C01 hoy |
| `utf8_bytes` | Longitud del buffer canónico |
| `read_correlation_id` | `result.correlation_id` de esa llamada |
| `connector_revision` | Revisión estable de los pasos 2 y 4 |
| `observed_at` | Reloj del evaluador en el sellado, no una marca aportada |

`recognizes_source` sigue siendo la puerta de C01. Debe ser verdadera solo para la evidencia registrada con ese recibo, ese contexto y ese request. Una evidencia de otra operación, organización o instancia devuelve no reconocida. Después de `close` o de una revocación, también.

El fixture actual puede seguir en las pruebas viejas. El compositor nuevo no debe copiar su libertad para elegir `content_revision`.

## 12. Composición con C02

El recibo externo no es una lease. La vía aprobada de esta fase es `prepare_once` del emisor de prueba. El orden demostrado es:

1. El recibo reconocido permite construir el envelope y la `SourceEvidence`.
2. `GateCPolicyEvaluator.evaluate` puede devolver `ALLOW_PROCESSING`. Eso no ejecuta.
3. `prepare_once` reclama el recibo y llama a `EnterpriseModelGateway.prepare`. Si la preparación falla, el recibo externo queda consumido igual.
4. La evidencia interna sigue siendo reconocible en `_seal` de esa operación ya admitida.
5. Esa evidencia no abre otra operación C ni otra lease.
6. `invoke_once` sigue siendo el único consumo de la lease. Esta fase no lo llama.

Cinco autoridades permanecen separadas:

1. Recibo externo de lectura. Se consume en `prepare_once`.
2. Evidencia interna reconocida. Vale solo para la operación admitida mientras C02 la revalida.
3. Lease C02. Es independiente y de un solo uso.
4. Permiso derivado B1. `DerivedGrantMatch` no autoriza la lectura ni la entrega.
5. Autorización final B/C. No está implementada.

Ninguna se sustituye por un token reutilizable. `gateway.py` no recibe un gancho nuevo. `prepare_once` es la vía cuyo consumo está garantizado. Un `gateway.prepare` directo que falla antes de `populate` puede no consumir el recibo: es una limitación del emisor de laboratorio, no una garantía general ni una preparación productiva.

Dos llamadas simultáneas a `prepare_once` con el mismo recibo admiten como máximo una lease. El candado cubre solo esa reclamación. No se mantiene durante la reserva SQLite ni durante una inferencia.

## 13. Autoridad B1

`DerivedGrantMatch` acredita el permiso sintético `grounded_extractive_answer` / `enterprise.answer.deliver`. No sustituye A, B, C ni la evidencia.

Una entrega futura, fuera de este diseño, no puede exigir que el recibo externo siga sin consumir después de `prepare`. Tendría que usar el contexto reconocido y los bytes vigentes de la misma lectura. No reutiliza el recibo externo y no hace una segunda lectura. La conjunción pendiente sería:

- evidencia interna de esa lectura, con sus bytes vigentes;
- `Gate.READ` vigente;
- `Gate.DELIVERY` vigente para el documento;
- Gate C vigente, con el perfil fake exacto;
- `DerivedGrantMatch` vigente para el mismo principal, recurso, destinatario, propósito, clasificación y revisiones;
- destinatario y propósito ya ligados al request de la lectura;
- revisión C y revisión derivada actuales;
- la lease C02 de esa operación, de un solo uso.

Esa conjunción no se implementa ahora. B1 no inserta `AUTHORIZED`.

## 14. Ownership

| Objeto | Dueño | Sale de la frontera |
| --- | --- | --- |
| `OperationResult` | El compositor, hasta sellar | No se entrega suelto |
| Bytes canónicos | Owner del recibo | No |
| Recibo | Registro del emisor, por identidad | Solo la referencia no portable |
| Envelope C01 | Registro del emisor, como hoy `recognizes_envelope` | La referencia reconocida |
| `SourceEvidence` | El mismo registro, unida al recibo | La referencia reconocida, sin texto |
| `ExecutionOwner` C02 | El gateway, como hoy | Solo la `ProcessingLease` |
| Respuesta futura | Owner de C03, todavía no creado | Fuera de alcance |

Ninguno de esos objetos entra en el estado de LangGraph, checkpoints, tracing, callbacks, logs, `repr` ni SQLite. El estado del workflow actual ya se limita a metadatos. El compositor nuevo no crea un grafo.

La limpieza es un `finally` del compositor: anula resultado, documento, texto, bytes, contexto y request en su owner. No llama a `frame.clear`, no lee `f_locals` y no modifica el scrub M01. Una cancelación o `KeyboardInterrupt` durante el sellado no deja el recibo registrado. No se promete borrado criptográfico.

## 15. Revocaciones

El recibo prueba una lectura pasada. No congela A, B ni C.

Si la revisión del store cambia antes del sellado, no hay recibo. Si cambia después, C01 responde stale y el recibo se retira. Si el grant C o el permiso derivado cambian, la operación no continúa y el recibo tampoco se reutiliza. Hace falta una lectura nueva, con evidencia nueva. Esa lectura nueva no hereda la correlación anterior.

La ventana entre la última comprobación y otro proceso sigue siendo la ya aceptada en laboratorio. Dos SQLite no forman una transacción.

## 16. Manejo de errores

| Situación | Resultado |
| --- | --- |
| `execute` devuelve denegación, supresión, indisponibilidad o denegación externa | Sin recibo |
| Auditoría del conector no disponible | `execute` ya falla cerrado. Sin recibo y sin éxito |
| Cero documentos, más de uno, texto vacío o tipo distinto | Sin recibo |
| Revisión distinta antes y después | Sin recibo |
| Excepción antes de registrar | El registro no contiene el recibo |
| `CancelledError` o `KeyboardInterrupt` | Se propaga. El `finally` limpia. No hay recibo |
| Fallo al cerrar | No sustituye el error original. El recibo, si sigue registrado, se retira |

Un fallo no se convierte en evidencia ni en `ALLOW_PROCESSING`.

## 17. Amenazas

| Amenaza | Control de este diseño | Vínculo |
| --- | --- | --- |
| Resultado fabricado o copiado | El emisor no acepta un `OperationResult` externo | AI-T01, AI-T04 |
| Recibo fabricado, copiado o serializado | Reconocimiento por identidad y rechazo a reducirlo | AI-T01, AI-T04 |
| Recibo de otra operación, organización o destinatario | El registro ata contexto, request y documento de la misma llamada | AI-T01, AI-T11, AI-T17 |
| Recibo caducado o reutilizado | `prepare_once` lo consume una vez; la evidencia interna no abre otra operación | AI-T07 |
| Dos `prepare_once` simultáneos | Una sola lease. El candado no cubre la reserva ni el modelo | AI-T07, AI-T11 |
| Bytes o versión sustituidos | El buffer y `document.version` quedan en el owner; C01 compara la longitud | AI-T04 |
| Dos lecturas con distinto contenido | Una sola llamada; el workflow cerrado no es fuente | AI-T04, AI-T16 |
| Evidencia después de cerrar la frontera | No se sella desde `EnterpriseResult` | AI-T04, AI-T10 |
| Caller aporta `SourceEvidence` | C01 no la reconoce si el emisor no la registró | AI-T01 |
| Instrucciones dentro del documento | El texto no es política, grant ni recibo | AI-T02 |
| Revocación entre lectura y `prepare` | Reevaluación pública y retiro del recibo | AI-T07 |
| Auditoría caída | Sin recibo y sin éxito | AI-T08 |
| Owner cerrado con contenido retenido | `finally` propio; otras copias no se niegan | AI-T09, AI-T10, AI-T13 |
| Fuga por traceback, estado o log | Sin contenido en el grafo; `repr` apagado; sin scrub M01 | AI-T09, AI-T10 |
| Cancelación concurrente | Limpieza del owner de esta llamada, sin tocar otro | AI-T10, AI-T11 |

Las pruebas del fake no demuestran resistencia de un modelo generativo. AI-T06, AI-T16 y el proveedor real siguen fuera de esta fase.

## 18. Matriz B2-SRC

B2-SRC ejecutó esta matriz sobre el emisor de prueba. Cada caso conserva su negativa.

| Id | Caso | Resultado esperado |
| --- | --- | --- |
| B2-SRC-01 | Una lectura `READ` autorizada | Un recibo, una evidencia, una correlación |
| B2-SRC-02 | Dos llamadas | Dos correlaciones. La evidencia de la primera no acepta el documento de la segunda |
| B2-SRC-03 | `OperationResult` copiado | No reconocido |
| B2-SRC-04 | Resultado construido por el caller | No reconocido |
| B2-SRC-05 | Recibo no registrado | No reconocido |
| B2-SRC-06 | Segundo `prepare` con el mismo recibo | Retirado. Sin segunda lease |
| B2-SRC-07 | Otra organización | No reconocido y sin ids ajenos en la respuesta |
| B2-SRC-08 | Otro destinatario | No reconocido |
| B2-SRC-09 | Contexto o recibo vencido | No autorizado |
| B2-SRC-10 | Revisión cambiada entre la llamada y el sello, o antes de C | Sin recibo, o C stale |
| B2-SRC-11 | Bytes distintos del buffer del owner | No reconocido |
| B2-SRC-12 | Texto UTF-8 multibyte | La longitud cuenta bytes, no caracteres |
| B2-SRC-13 | 1024 bytes | Puede ser elegible para C si el resto coincide |
| B2-SRC-14 | 1025 bytes | Recibo de lectura posible. C lo rechaza por límite. Sin truncar |
| B2-SRC-15 | Falta permiso B | Sin recibo |
| B2-SRC-16 | Falta grant C | Sin lease. El recibo no procesa |
| B2-SRC-17 | Fallo del conector | Sin recibo |
| B2-SRC-18 | Auditoría no disponible | Sin recibo y sin éxito |
| B2-SRC-19 | `CancelledError` | Limpieza y señal conservada. Sin recibo |
| B2-SRC-20 | `KeyboardInterrupt` | Igual que la cancelación |
| B2-SRC-21 | Estado, logs, `repr` y traceback | Sin texto ni bytes |
| B2-SRC-22 | Regresión TASK 005 | El workflow sigue cerrando antes de retornar |
| B2-SRC-23 | Regresión C01 | El evaluador y `SourceEvidence` no cambian de contrato |
| B2-SRC-24 | Regresión C02 | `prepare` e `invoke_once` no cambian |
| B2-SRC-25 | Regresión B1 | `DerivedGrantMatch` no autoriza la lectura ni la entrega |
| B2-SRC-26 | Red | Guards de socket y DNS sin intentos |

## 19. Cambios mínimos de código futuros

Solo después de otra autorización. Esta propuesta no los hace.

- Un módulo nuevo del compositor y del recibo. El inventario cerrado de `enterprise_ai_processing` hoy no admite ese archivo: la tarea futura tiene que ampliarlo de forma explícita y probar el rechazo de imports prohibidos.
- El emisor de test deja de tratar `content_revision` como argumento libre cuando construye la evidencia de C03. Las pruebas viejas de C01 pueden conservar su fixture.
- No se edita `service.py`, `document_read.py`, `policy.py` de C01, `gateway.py`, `fake_model.py`, los modelos C01 ni las migraciones.
- No se añade `get_document`, caché, endpoint ni grafo.

## 20. Plan incremental

1. Esta propuesta. Sin código.
2. Si el Product Owner la acepta, implementar solo el emisor, el recibo no portable y las pruebas B2-SRC. Sin observador.
3. Después, y con autorización aparte, el observador interno y el validador determinista sobre el buffer del owner. El fake sigue siendo el único proveedor.
4. Más tarde, la frase, el puerto de entrega y el grafo. Siguen fuera.

El paso 3 no empieza hasta que el paso 2 demuestre una lectura, un resultado, una evidencia y una operación C de esa misma llamada.

## 21. Riesgos residuales

- El `str` no conserva el body remoto ni el eTag. La garantía es la decodificación estricta que el adaptador ya hizo, no una custodia de bytes originales.
- Si la política cambia durante `execute`, se pierde la lectura. Es preferible a atribuir una revisión equivocada.
- El reconocimiento por identidad vale dentro del proceso. No aísla un host comprometido.
- `prepare_once` es la vía de consumo garantizada. Un `gateway.prepare` directo que falla antes de `populate` puede dejar el recibo sin consumir. Esa diferencia es de laboratorio y bloquea mover el emisor a `app/` hasta rediseñarla.
- M01 y M02 siguen abiertos en el workflow antiguo. Este diseño no los usa y no los cierra.
- La revocación de otro proceso y la ausencia de transacción entre los dos SQLite no cambian.
- El fake no prueba un LLM real. Esta fase no lo invoca.

## 22. Decisiones requeridas al Product Owner

1. Aceptar la alternativa A y rechazar, para este incremento, un puerto nuevo del conector y una continuación del workflow.
2. Aceptar que `content_revision` de esta evidencia sea `document.version`, porque el resultado no trae otra revisión.
3. Aceptar que no habrá eTag en el recibo mientras el servicio solo entregue `str`.
4. Aceptar el fallo cerrado cuando la revisión del store cambie durante la llamada.
5. Aceptar que cualquier `prepare` retira el recibo, también si falla.
6. Autorizar expresamente la implementación del emisor antes de escribir código. Esta propuesta no la inicia.

La decisión 5 quedó acotada por la implementación: la vía aprobada es `prepare_once`. No se afirma que cualquier `gateway.prepare` directo consuma el recibo. El detalle está en la sección 23.

## 23. Decisiones demostradas en la implementación

El Product Owner aceptó la alternativa A y la implementación de laboratorio, exclusivamente en `tests/`. El emisor no se promueve a `app/`. La publicación de este incremento, cuando los controles pasan, es el push de `feature/enterprise-ai-processing-authorization-task-c03-b2`. No hay PR ni merge.

El emisor y el recibo viven en `services/ai-service/tests/enterprise_single_read_source.py`. Son de prueba. No se añadió un módulo al paquete `enterprise_ai_processing`, así que el inventario AST cerrado no se amplió. Un módulo de producto habría publicado una autoridad que este incremento mantiene sintética.

`ProcessingLaboratory.__init__` sigue llamando `issue()`, y esa llamada ejecuta `ConnectorService.execute`. El compositor no se apoya en ese laboratorio. La prueba del constructor cuenta esa lectura por separado. La operación positiva usa el laboratorio del conector, que no lee durante su construcción. El contador de la operación no se pone a cero después del montaje: la lectura válida hace una llamada pública y una lectura del adaptador.

La autoridad es la identidad de los objetos retenidos por el emisor: contexto, petición, resultado, documento, evidencia, sobre y recibo. Un UUID, un hash o campos iguales no reconstruyen el recibo. No hay búsqueda por `operation_id`. `pickle` y `copy` fallan. El recibo no es un permiso Gate C ni una lease.

`content_revision` es `document.version`. Esa versión es metadata del recurso. No es un eTag remoto y no prueba que el contenido remoto sea inmutable. El emisor acredita los bytes UTF-8 estrictos que recibió en esa llamada, sin normalizar Unicode y sin truncar. Si los bytes locales cambian antes de preparar y la versión registrada sigue igual, C01 responde `source_evidence_invalid`.

C01 reconoce la evidencia con `GateCPolicyEvaluator` y esta frontera. No se modificó el evaluador. `prepare_once` consume el recibo externo aunque la preparación falle. `_seal` vuelve a reconocer la evidencia de la operación ya admitida. Esa evidencia no reserva otra lease. Dos `prepare_once` simultáneos admiten una sola lease y no ejecutan el fake. No se modificó `gateway.py`.

Un `gateway.prepare` directo que falla antes de `populate` puede no consumir el recibo. Es una limitación aceptada del emisor de laboratorio. No es consumo universal, no es preparación productiva y mantiene bloqueada la promoción a `app/`.

Una llamada pública con dos páginas del adaptador no produce recibo. Si la revisión del store cambia entre el antes y el después de `execute`, no hay recibo. Si cambia después del sello, C01 responde `policy_changed` y no hay lease.

1024 bytes puede obtener `ALLOW_PROCESSING`. 1025 bytes se conservan enteros y C los rechaza por `budget_exceeded`. Para dejar pasar 1025 por el conector, esa prueba sube solo el límite del store sintético.

La limpieza anula las referencias del emisor en `finally` y propaga `CancelledError` y `KeyboardInterrupt`. No usa `frame.clear`, `f_locals` ni recolección global. No promete borrado criptográfico. El texto no aparece en `repr`, logs, traceback ni SQLite.

El paso 3, observador y grounding, no está iniciado.
