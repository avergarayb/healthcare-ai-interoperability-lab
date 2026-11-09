# Enterprise AI Processing Authorization V1 — contrato interno de diseño

Estado: **Approved — design only; DESIGN-001**. Contrato aditivo aprobado como arquitectura base, no implementado. Identificadores conceptuales `enterprise-ai-processing-authorization-v1` y `enterprise-ai-processing-audit-v1`; no son una API, clases existentes, DDL ni una autorización ejecutable. El PO autoriza revisión final y commit/push exclusivamente de los cuatro documentos propios tras controles; no PR, merge ni inicio de TASK-C01/C02/C03/C04. Solo una autorización futura de implementación permitirá una composición empresarial offline. El runtime actual sigue C DENY / D DISABLED.

[Arquitectura y compatibilidad](../design/enterprise-ai-processing-authorization-v1.md), [amenazas](../design/enterprise-ai-processing-threat-model-v1.md) y [plan](../design/enterprise-ai-processing-implementation-plan-v1.md). Preserva [ADR-097](../adr/ADR-097-enterprise-connector-authorization-boundaries.md), [contrato conector](enterprise-connector-authorization-v1.md) y [PrincipalContext](identity-principal-context-v1.md); no redefine identidad, autorización Graph, Human Review o auditorías existentes.

## 1. Reglas de autoridad

1. A/B, permisos Microsoft, sesión/token de plataforma y disponibilidad de una credencial de modelo no conceden C. C no concede B ni D. D permanece deshabilitado, también para embeddings, historial, salidas, logs y checkpoints de contenido.
2. Frontera confiable verifica principal/organización y fija instancia, fuente, operación, destinatario y propósitos. En el primer fixture es una autoridad sintética explícita, no login humano corporativo. Ni dataclass copiada, JSON, prompt, tool arguments, JWT roles/groups, checkpoint ni nombre de agente son autoridad C.
3. Solicitud pública futura mínima: referencia de recurso y pregunta acotada/ID de pregunta; no principal, organización, tenant, provider, modelo, región, credencial, política o aprobación. La frontera debe cotejar esos candidatos con su envelope, no adoptarlos.
4. Solo un grant C completo, vigente y del ámbito exacto puede autorizar; nunca reunir propósito de uno, modelo de otro y clasificación de un tercero. Ningún wildcard de organización/proveedor/destino ni descubrimiento desde contenido.
5. Clasificación, versión, procedencia y binding provienen de registros/evidencia confiables; una etiqueta en el texto no desclasifica. Pregunta/contexto/candidato de respuesta también son datos y quedan sujetos al mismo destino aprobado.

## 2. Entidades propuestas y procedencia de campos

Registros inmutables de campos cerrados, IDs internos canónicos acotados, timestamps UTC y revisiones enteras monótonas. Rechazar extras, duplicados, tipos ambiguos y subclases con payload adicional. Los IDs no son URLs ni capacidades portables. Campos faltantes o incoherentes deniegan; error al verificar política/almacenamiento es UNAVAILABLE sin fallback.

| Entidad | Campos mínimos / dueño |
|---|---|
| **AIProcessingEnvelope** | `operation_id` nuevo; contexto reconocido y vigencia; principal y organización verificados; `connector_instance_id`, `resource_id`, `resource_tenant_binding_id`, `read_operation`, `read_purpose`, `processing_operation`, `processing_purpose`, `recipient_ref`, `source_evidence_ref`, revisiones de identidad/conector/C/perfil, `expires_at`. Emitido/reconocido/retirado por frontera confiable independiente de la pregunta. |
| **AuthorizedSourceEvidence** | Organización/instancia/recurso/tenant exactos, operación de lectura, versión de registro, revisión documental del fixture o versión de contenido comprobada, clasificación, label no confiable, procedencia del adaptador, momento de lectura y correlación A/B. Vinculación a bytes concretos mediante digest privado efímero y owner; no acepta registros reconstruidos por el modelo. No contiene credencial Graph. |
| **AIProcessingGrant** | ID/versión, principal/tipo y organización, instancia y tenant documental, recurso exacto (solo un documento en MVP), operación `enterprise.document.answer`, propósitos de lectura/IA admitidos, clasificación permitida, perfil exacto de modelo, destinatario autorizado, límites, requisitos de aprobación, `enabled`, `valid_from`, `expires_at`, `review_due_at`. Administración de fixture explícita fuera de agentes. |
| **ModelProcessingProfile** | ID/versión/estado, organización, provider kind, model ID y versión/deployment cuando corresponda, referencia de destino aprobado, tenant/cuenta del proveedor si aplica, regiones/procesamiento/routing autorizados, clases y propósitos admitidos, retención, límites/tokenizer y referencia de credencial futura. No hay valor implícito de proveedor externo. |
| **ProcessingApproval** | Referencia, organización/principal/recurso/versión, propósito/perfil/destino, aprobador verificable según contrato futuro, alcance, fecha y expiración/retiro. Política puede declarar `not_required` explícito para fake sintético; ausencia de aprobación requerida deniega. Documento o LLM no pueden concederla. |
| **AIProcessingDecision** | ID/correlación/op nuevos, outcome/motivo cerrado, refs de envelope/fuente/grant/perfil/destino, revisiones exactas, límites aprobados, tiempo de decisión y expiración mínima. Solo metadata, sin contenido ni credenciales; la ref efímera de evidencia no expone su digest. Una fila ALLOW no es una capacidad recuperable. |
| **ProcessingLease / BudgetReservation** | Un uso, owner y ámbito exactos, decisión/bytes/fuente/pregunta/perfil ligados privadamente, revisión, reserva input/output/tiempo/concurrencia y vencimiento. Consumida en gateway, no serializable a prompt/estado, no recuperable por operation ID ni reutilizable tras reinicio. |
| **ModelRequest / ModelResult** | Request efímero: instrucciones de aplicación fijas/versionadas, pregunta aprobada, fragmento único etiquetado como dato, metadata mínima de citas y límites. Result: categoría cerrada, propuesta de evidencia/citas acotada y uso observado; nunca establece permisos, actor, gates, fuente confiable o éxito de entrega. Texto/valores sensibles fuera de repr. |
| **GroundedAnswer** | Estado, respuesta efímera autorizable, evidencia/citas verificadas de la fuente propia, versión/procedencia/clasificación heredadas, correlaciones técnicas. Sin links ejecutables, contexto IAM, prompts, trazas, credenciales o autoridades reutilizables. Solo sale después de B/C finales y commits. |

El tenant documental se valida contra el binding conector; no es el tenant de modelo, la organización ni el tenant hogar de una persona. `resource.version` actual es versión registrada: no llamarla eTag ni revisión de bytes Microsoft. El fixture futuro debe fijar revisión de texto y manifest de procedencia; sin esa evidencia no hay respuesta afirmativa fundamentada.

El digest vincula bytes solo dentro del owner reconocido; copiarlo, conocer su referencia o repetir un valor idéntico no emite evidencia ni autoridad portable. No es identificador público ni campo de auditoría. Cambiar fuente/bytes/versión/clasificación invalida las decisiones dependientes y exige evidencia nueva; no reparar una decisión vieja con datos del modelo o una etiqueta del documento. DESIGN-001 no implementa algoritmos criptográficos.

El inventario de entidades describe el diseño completo, no el scope de C01. TASK-C01 solo prevé los tipos mínimos de entrada/salida, envelope sintético reconocido, grant C completo, perfil fake fijo y evaluación pura con reloj inyectado. Emisión, consumo y eventual registro durable de leases de un uso, reservas transaccionales, gateway y auditoría persistente son de TASK-C02; modelos de respuesta/workflow corresponden a etapas posteriores. No crear todo el inventario por anticipación.

## 3. Evaluación C deny-by-default

Secuencia conceptual completa, sin efectos de proveedor antes de completarla. Los pasos 1–6 contienen las comprobaciones de política que C01 podría evaluar sin efectos, sobre evidencia/snapshots de test confiables y controles A/B de sus puertos públicos; el paso 7 pertenece a C02, no al evaluador puro:

1. Reconocer el envelope y el contexto, principal registrado activo y organización, expiraciones y propósito vinculado. Revalidar lectura/entrega por motor existente; no reinterpretar una operación AI como READ para conceder C.
2. Resolver instancia/tenant/recurso propios y evidencia de lectura satisfactoria con auditoría vigente; revalidar versión, clasificación y bytes del source owner. Una correlación conocida o un resultado B copiado no es evidencia autoritativa.
3. Encontrar un grant C **completo** del ámbito exacto. Resolver su perfil y destino registrados, habilitados, vigentes y aprobados para esa clasificación/propósito/retención. Ninguna recuperación por perfil «parecido».
4. Comprobar aprobación/consentimiento si corresponde, sin asumir que un rol administrativo o consentimiento Graph sustituye esa aprobación. Aprobación humana productiva es contrato futuro; no reutilizar el cierre de un caso clínico.
5. Validar entrada entera: documento + pregunta + instrucciones fijas + metadata que verá el modelo, no solo chars del documento. Presupuesto de entrada/salida, tamaño, tiempo y concurrencia: mínimo de límites del conector, grant, perfil y operación.
6. Fijar versión y expiración mínimas de identidad, envelope, grants, perfil, aprobaciones, revisión y deadline. No extender vigencia para compensar inferencia lenta; cambio de revisión invalida la lease, no auto-refresh.
7. Persistir evaluación y reserva/intent obligatorios; solo entonces emitir la lease de un uso. En gateway, volver a verificar versiones/expiraciones/bytes/perfil y consumirla antes de la transferencia.

`ALLOW_PROCESSING` es un resultado de política, **no una capacidad ejecutable por sí sola**. Intentar una inferencia concreta exige además la secuencia de auditoría/reserva/lease y consumo del gateway de C02; C01 no emite ni consume leases e invoca cero modelos, incluido el fake. No significa ejecución, calidad, salida válida ni entrega. Denegación antes de invocar exige contador de llamadas de modelo igual a cero; una lectura Graph autorizada ya realizada no se niega retrospectivamente en la auditoría.

## 4. Proveedor neutral, destino y retención

| Provider kind propuesto | Binding exigido / estado |
|---|---|
| `fake` | ID/version deterministas, ejecución local sin sockets, sin herramientas/credenciales/telemetría; único proveedor previsto para TASK-C02, previa autorización. C01 solo evalúa el perfil, sin invocarlo. |
| `openai` | Perfil explícito de API/cuenta/proyecto/modelo/versionado/destino/retención bajo evaluación futura. No se elige modelo ni se afirma disponibilidad, residencia o condiciones del proveedor en este diseño. Deshabilitado. |
| `azure_openai` | Perfil explícito de recurso/deployment/modelo/versión, tenant de procesamiento y rutas/regiones aprobadas; no confundir Selected con autorización de recursos Azure. Deshabilitado. |
| `local` | Modelo/artefacto/revisión, runtime y destino registrados; «local» no implica confiable, sin red o sin retención. Necesita autorización y validación propias. Deshabilitado. |

El destino es un descriptor administrado, no URL del prompt: protocolo, origen/cuenta/deployment, ruta de procesamiento y política de egress futura. Un redirect, alias mutable, cambio de versión, routing fuera de región, retención desconocida o funcionalidad no verificada no se acepta como equivalente. Perfil incapaz de satisfacer política se deniega; nunca fallback automático de modelo, región, proveedor, cuenta o privilegio. También se rechaza fallback al proveedor Gemini de otro flujo o activación por settings/keys heredados.

Perfil inicial propuesto: `fake-enterprise-extractive-v1`, versión fija, destino `in-process-offline`, clasificación exacta `synthetic-internal`, propósito IA `synthetic-policy-question-answering`, una fuente y una pregunta allowlisted, sin herramientas, retries, entrenamiento, caché de respuestas ni retención de inputs/outputs después de la llamada. Solo retiene auditoría mínima separada. Identificadores de ejemplo, no registros creados.

Retención futura exige descriptor aprobado que cubra almacenamiento, cachés de proveedor, observabilidad/abuso, subprocesadores, regiones, uso/entrenamiento y eliminación/limitaciones. `no_retention` solicitado no es garantía de ningún proveedor; sin evidencia/configuración compatible no habilitarlo. Un proceso local comprometido tampoco está aislado por un nombre de perfil.

Límites candidatos de fixture, pendientes de aceptación al implementar:

| Límite | Propuesta y comprobación |
|---|---|
| Fuente / pregunta | Una fuente completa UTF-8 text/plain, máximo efectivo 1024 bytes por límite conector; pregunta canónica allowlisted, máximo 256 bytes; no documentos/preguntas reales. |
| Input total / output | Máximo 2048 bytes entrada total; máximo 512 bytes output y 256 unidades del tokenizer fake, aplicando el menor límite. No truncar silenciosamente una evidencia/condición. |
| Tokens | Perfil exige tokenizer/versionado y presupuestos explícitos de input/output. El fake contará un byte UTF-8 por unidad (`fake-byte-v1`), 2048/256 unidades; no afirmar equivalencia con tokens de proveedores reales. Tokenización real desconocida o cómputo no acotado deniega en perfil futuro. |
| Tiempo / intentos | Deadline máximo 5 s y nunca posterior a la vigencia restante, reloj inyectado para tests; una llamada, cero retries de modelo, también ante timeout ambiguo. No reutilizar timeout clínico ni renovar identidad. |
| Concurrencia | Cuando se implemente C02, una reserva C activa por organización/instancia/perfil en el fixture, además de los límites A existentes. No duplicar una reserva por compilación/reintento del grafo; C01 solo comprueba el límite declarado. |

Reserva transaccional antes de procesar, sin mantener la conexión/lock durante inferencia. Cancelación/timeout tras inicio no devuelve automáticamente tokens/cuota como si no hubiera consumo. Estado ambiguo conserva reserva/consumo conservador hasta reconciliación administrativa de metadata; nunca reejecuta contenido. Son límites de laboratorio, no sizing o cuotas comerciales.

## 5. Respuesta fundamentada y entrega

MVP extractivo: fake recibe los bytes autorizados y devuelve selección acotada de evidencia para una pregunta conocida. Aplicación valida contra **esa misma fuente/versión** y construye la frase final con plantilla controlada; no confía en un JSON del fake como validación semántica. Cada afirmación/dato/condición debe tener un fragmento exacto y offsets verificados contra bytes canónicos UTF-8 del owner. Modelo no inventa IDs ni resuelve enlaces. Sin evidencia completa, responder `INSUFFICIENT_EVIDENCE` sin número ni afirmación sustantiva; no completar con conocimiento del modelo.

Referencia visible: ID/nombre ficticio aprobado por registro, organización propia, revisión documental, procedencia offline y fragmento autorizado acotado. Títulos devueltos por modelo y URLs externas no son fuentes. La respuesta hereda la clasificación más restrictiva de fuente/pregunta; no desclasificar por resumir. Citas y fragmentos también pasan B/C finales y límites de terminal; no devolverlos en error/denegación.

No existe prueba universal de grounding para texto libre. La garantía inicial solo abarca extracción/plantillas y preguntas pequeñas con validación determinista. Proveedor real y respuestas generativas precisan otra evaluación antes de autorizar. Documentos contradictorios: primer MVP rechaza varias fuentes; contradicción dentro de la fuente o sin condiciones suficientes produce `INSUFFICIENT_EVIDENCE`/conflicto, sin escoger una conclusión. La política no la cambia el LLM ni se abre Human Review clínico para resolverla.

Tras inferencia, validar C fresco y B sobre fuente/resultado/destinatario, incluyendo vigencia, revisión y evidencia externa simulada. La frontera final propuesta en [arquitectura](../design/enterprise-ai-processing-authorization-v1.md) no existe hoy y es gate de integración. No devolver candidato desde un nodo ni transmitir tokens antes de commits. Un evento final ALLOWED es decisión local, no confirmación de que una persona leyó la respuesta.

Aplicar íntegramente la secuencia y semántica temporal de arquitectura: guard C -> guard conector, chequeos/auditorías y comprobación local conjunta `T_auth`, commit conector, commit C y solo después entrega. ALLOW de un archivo no sustituye el otro. Fallo parcial de audit/commit suprime respuesta/citas aunque una decisión previa haya persistido; ningún commit aislado prueba entrega o transacción distribuida. La observación externa tiene punto propio `T_ext`, no se congela con guards SQLite. La carrera entre liberación del guard conector, commit C y salida, así como observaciones externas concurrentes, queda explícita y requiere protocolo aprobado y pruebas bloqueantes en C03. No extrapolar el punto local a revocación global/hasta el último byte; tampoco se promete revocación retroactiva tras entrega. Inferencia e I/O de proveedor siempre fuera de locks/transacciones SQLite.

## 6. Resultados y errores nuevos (sin extender enums base)

| Resultado de procesamiento | Contenido / significado |
|---|---|
| `DENY` | Sin inferencia si el rechazo es previo; sin documento, cita o enumeración ajena. |
| `UNAVAILABLE` | Dependencia/política/auditoría no verificable; diagnóstico fijo y cero salida documental. |
| `PROCESSING_AUTHORIZED` | Decisión/intent local; no demuestra que el modelo haya sido invocado. |
| `PROVIDER_COMPLETED` | Adaptador observó resultado del fake; no demuestra grounding, B ni recepción. |
| `INSUFFICIENT_EVIDENCE` | Mensaje fijo sin afirmación, número ni citas no autorizadas; no búsqueda adicional. |
| `ANSWER_REJECTED` | Esquema, evidencia, clasificación o límites inválidos; candidato suprimido. |
| `DELIVERY_ALLOWED` / `DELIVERY_SUPPRESSED` | Resultado final solo después de la frontera; supresión sin respuesta/citas. |
| Cancelación primaria | Propagar la misma señal/objeto, no convertir a resultado normal; cleanup y auditoría best-effort obligatoria cuando el sink esté disponible. |

Motivos propuestos cerrados: `identity_invalid`, `scope_mismatch`, `source_evidence_invalid`, `processing_not_granted`, `classification_denied`, `purpose_denied`, `profile_denied`, `destination_denied`, `retention_unverified`, `approval_required`, `policy_changed`, `authorization_expired`, `budget_exceeded`, `provider_unavailable`, `provider_result_invalid`, `evidence_missing`, `audit_unavailable`, `cancelled`, `internal_failure`. No copiar campos desconocidos/texto de errores al motivo ni exponer diferencias de recursos ajenos. No HTTP nuevo en DESIGN-001.

## 7. Auditoría aditiva propuesta

`enterprise-ai-processing-audit-v1` es independiente de `connector-security-audit-v1`, Security Audit, OIDC, Human Review y sus productores/tablas/allowlists. SQLite C dedicado, inicialización explícita test-owned, esquema cerrado y consulta organizacional. Cambios de perfiles/grants y revisión deben confirmarse con su auditoría administrativa propia en una transacción C. No modificar ni leer stores de ejecución existentes para simular estos eventos.

| Evento conceptual | Hecho y condición |
|---|---|
| `ai_processing_evaluated` | C ALLOW/DENY/UNAVAILABLE; decisión, motivo y revisiones; denegaciones atribuidas solo si identidad verificada. |
| `ai_processing_profile_selected` | Perfil/modelo/destino **registrados y aprobados** seleccionados; no implica llamada. Solo después de C ALLOW, sin input libre en campos. |
| `ai_processing_budget_approved` | Reserva/límites input-output-tiempo/concurrencia aprobados; no consumo real confirmado. |
| `ai_processing_authorized` | Intent durable ligado a lease de un uso; obligatorio antes de transferir cualquier contenido al fake. |
| `ai_provider_invocation_observed` | Gateway observó entrada al adaptador. No prueba aceptación remota ni ejecución completa; en fake es entrada a función controlada. |
| `ai_provider_result_observed` | Resultado observado, uso si medible, categoría cerrada; estado desconocido explícito para ambigüedad, no éxito inventado. |
| `ai_answer_evidence_validated` | Esquema/evidencia aceptados, rechazados o insuficientes; sin texto ni fragmentos. |
| `ai_processing_cancelled` / `ai_processing_error` | Cancelación o fallo realmente observados, sin raw exception; no garantiza detención remota. |
| `ai_processing_revocation_detected` | Retiro/cambio/caducidad detectados en fase cerrada; no afirma retractar bytes ya transferidos. |
| `ai_final_delivery_decided` | ALLOWED/SUPPRESSED, destinatario interno propio, B/C frescos y revisiones; no recepción humana. |
| `ai_processing_policy_changed` | Cambio C administrativo aprobado, versión/revisión anterior-nueva; nunca atribuir un operador sintético como administrador corporativo. |

Campos comunes: contract/event version, UUID evento/operación/decisión/correlación, instante UTC, secuencia local, fase cerrada, outcome/motivo, actor verificado/workload sintético o anonymous, organización validada, refs propias de instancia/recurso/versión/grant/perfil/destino/reserva, revisiones y contadores cuantitativos acotados. Perfil resuelve provider/modelo/versionado/región registrados, no strings de la respuesta. Una correlación opcional enlaza la lectura con procesamiento; no proclamar correlación global del laboratorio. Denegación cross-org solo registra refs propias resueltas o sentinel, nunca metadatos de B para A.

Prohibidos: documentos, preguntas/prompt/respuesta, fragmentos/citas textuales, digest de contenido, JWT/token/hash de token, API key, cookies, material de credencial, URL preautenticada, nombres personales, SQL/paths internos, texto arbitrario de errores o stack traces. Los IDs de proveedor externos solo se admitirían mediante normalización/mapeo aprobado; no volcar headers/cuerpos como request ID.

Fallo de evaluación/selección/reserva/intent durable: cero llamadas de modelo. Fallo después de transferir/retornar: suprimir respuesta y citas, conservar solo eventos realmente confirmados. Caída entre intent e invocación/resultado deja **UNKNOWN**, no «no invocado» ni «completado»; no replay automático tras reinicio. Un fallo del sink no genera un evento ficticio en ese sink. Diagnóstico fijo local, sin secreto/contenido, no sustituye auditoría persistente. Tests de storage failure deterministas no acreditan atomicidad remota ni resiliencia operacional.

## 8. Revocación, concurrencia y cancelación

Revalidaciones obligatorias: resolución/lectura por A/B existentes; C al evaluar; antes de la llamada al consumir lease; al recibir resultado; y conjuntamente con B al entregar. Cambios de política/grant/perfil/clasificación/fuente/identidad/aprobación/revisión observados por los chequeos exigidos invalidan, aunque el fake termine bien. Las revocaciones/revisiones de ambos stores confirmadas antes de `T_auth` deben detectarse conforme al protocolo local; permisos externos se observan en `T_ext`, sin garantía de detección instantánea posterior. Si no puede verificarse la política/frescura requerida, fallar cerrado. No tratar la lectura o decisión anterior como permiso permanente.

Cada owner retira únicamente sus leases/reservas/refs. El orden y límites de los dos stores están en arquitectura: sin lock SQLite durante inferencia, sin red dentro de guards y sin promesa de atomicidad entre archivos/proveedor/consumidor. Dos organizaciones con IDs externos/modelos iguales no comparten ámbito, respuesta, presupuesto o auditoría consultable.

Ctrl+C/CancelledError tienen prioridad sobre close/clear fallidos; sin entrega, sin cambio a éxito, limpieza en finally independiente y señal original preservada. No adjuntar excepciones secundarias que capturen contenido; usar notas fijas. Timeout no es prueba de que un worker/proveedor se detuvo. El fake inicial es síncrono, bounded y sin worker de fondo; cualquier async/executor real requerirá contrato de join/cancel y revisión propia.

## 9. Criterio de aceptación futuro

Cada requisito debe vincularse a un test positivo y negativo de [plan/DEMO-002](../design/enterprise-ai-processing-implementation-plan-v1.md) y a una amenaza complementaria. Medir ausencia de invocación no autorizada, no solo código de error. Conservar todas las regresiones existentes C/D denegados en TASK 002–005/DEMO-001, incluidos owners/tracebacks/cadenas/cancelación/concurrencia. El opt-in nuevo no habilita el camino anterior ni su configuración. Este documento no autoriza implementar ninguna de sus entidades o eventos.
