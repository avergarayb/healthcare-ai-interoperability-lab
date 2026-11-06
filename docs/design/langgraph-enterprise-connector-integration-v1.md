# LangGraph Enterprise Connector Integration V1 — TASK 005

Implementación interna **offline de laboratorio, en revisión final de seguridad**. TASK 004 está integrada mediante PR #112. El PO aceptó la corrección inicial de retención para laboratorio y autorizó revisión, corrección de bloqueantes y commit/push de las ocho rutas solo tras controles satisfactorios. El segundo hallazgo de sanitización entre invocaciones se reportó deteniendo publicación; su corrección y nueva evidencia se detallan abajo. No habilita Graph live, agente conversacional productivo, endpoints, LLM, RAG ni MCP. Sin PR, merge ni TASK 006/007; publicar no equivale a integración o cierre productivo.

Autoridad: [ADR-097](../adr/ADR-097-enterprise-connector-authorization-boundaries.md), [contrato local](../contracts/enterprise-connector-authorization-v1.md), [perfil Graph](../contracts/microsoft-graph-connector-permissions-v1.md), [arquitectura](enterprise-connector-authorization-v1.md), [amenazas](enterprise-connector-threat-model-v1.md), [plan](enterprise-connector-authorization-implementation-plan-v1.md), [TASK 002](enterprise-connector-synthetic-fixture-v1.md), [TASK 003](enterprise-connector-control-plane-v1.md) y [TASK 004](microsoft-graph-app-only-adapter-v1.md). No se modifican ADR/contratos aprobados; sus estados de etapas anteriores son históricos.

## Inventario previo y punto de extensión

El AI Service conserva dos caminos clínicos: `langgraph_gemini_fhir_followup.py` compila StateGraph con mensajes/tools y modelo narrativo; `langgraph_workflow_orchestration.py` compila el workflow clínico con lectura Java, protocolos deterministas, Human Review, interrupt/resume y `SqliteCheckpointSaver`. `langgraph_followup_workflow.py` mantiene el límite de aplicación del subflujo narrativo. Configuración, herramientas FHIR, protocolos, Model Boundary, Human Review, conocimiento institucional y checkpoints pertenecen a esas capacidades, no a este incremento.

No existía un runtime genérico empresarial compatible. Se reutiliza el patrón de construir/compilar un StateGraph, no el estado, saver, herramientas ni factories clínicos. El LangGraph instalado/fijado es **1.2.12**; se verificaron localmente StateGraph, compile y Runtime/context_schema. No se instala ni actualiza ninguna dependencia. El uso de `langsmith.tracing_context` es exclusivamente para desactivar tracing heredado, no para habilitar observabilidad externa.

Extensión: [enterprise_workflows/document_read.py](../../services/ai-service/app/enterprise_workflows/document_read.py), namespace separado del motor estándar de autorización y de los módulos clínicos raíz. Su `__init__.py` no registra nada. Respeta las comprobaciones arquitectónicas existentes y añade comprobaciones AST específicas del módulo nuevo, sin ampliar allowlists clínicas. Reutiliza [ConnectorService](../../services/ai-service/app/enterprise_connectors/service.py), PolicyEvaluator, modelos, SQLitePolicyStore, auditorías y adaptador Graph sin modificarlos. No hay otro AI Service, IAM, control plane o autorizador. Java/FHIR no son dependencia de este workflow empresarial.

## Arquitectura, nodos y transiciones

```text
Frontera interna confiable de laboratorio
  -> invoke(argumentos cerrados)
  -> START -> validate_request -> resolve_registered_resource
           -> invoke_authorized_connector -> evaluate_result -> END
  -> frontera final de entrega: revalidación + auditoría + commit SQLite
  -> respuesta solo de esta invocación
```

| Nodo | Responsabilidad |
|---|---|
| validate_request | Abrir envelope por puerto confiable; rechazar JSON de identidad, argumentos extra, operaciones/propósito/recurso distintos de los preautorizados |
| resolve_registered_resource | PolicyEvaluator vigente resuelve registro y grants; catálogo Graph coteja identidad registrada; sin búsqueda ni grants nuevos |
| invoke_authorized_connector | ConnectorService real ejecuta A, broker/adaptador offline, parsing, auditoría y B; resultado sensible queda solo en la closure privada |
| evaluate_result | Interpretación cerrada de resultados; LOCAL_ALLOW/EXTERNAL_SUCCESS aislados nunca equivalen a contenido entregado |

Fallo de validación/resolución termina directamente en END. Tras ejecutar el conector se interpreta su resultado cerrado y termina. Sin retry policy de nodos ni bucles de agente: los únicos reintentos son los presupuestos existentes del servicio/adaptador. La última frontera de entrega, fuera del grafo y sin streaming, vuelve a verificar A/B, destinatario y vigencia. El estado del grafo puede reflejar una decisión anterior; solo EnterpriseResult después de esa frontera representa la respuesta final.

## Contrato de entrada y herramienta controlada

Capacidad interna `enterprise_document_read`, registrada únicamente mediante construcción explícita de `EnterpriseDocumentWorkflow(service, boundary)` en el fixture offline. No es BaseTool global ni herramienta ofrecida a un LLM. `invoke(arguments)` no admite config, callbacks, contexto, thread, checkpoint, resume o destino por kwargs.

```json
{"resource_id":"vacation-a","operation":"document.content.read","purpose":"synthetic-demonstration"}
```

Diccionario exacto de tres campos string acotados, sin campos extra; referencia interna canónica, no URL. Operaciones admitidas: `resource.metadata.read`, `resource.children.list`, `document.content.read`. Los tres valores deben coincidir con el envelope preautorizado por la frontera, no lo definen. Instancia, organización, principal, tenant, modalidad, destinatario, grants, credencial, modelo y auditoría nunca son argumentos. Ningún texto documental participa en routing o decisiones.

## Identidad y execution envelope

`InvocationBoundary.open()` obtiene un VerifiedInvocation nuevo desde composición confiable, independientemente de argumentos de herramienta; `recognizes()` revalida y `close()` retira su uso. El valor interno liga contexto verificado, instancia, recurso, operación, propósito, destinatario, revisión y expiración, con modalidad enterprise/application. Construir/copiar una dataclass no es autoridad. También se exige que la frontera de identidad del evaluador reconozca el contexto exacto, y la política existente comprueba principal, organización, audiencia, tipo, grants y vigencia.

La **única fábrica es TestInvocationBoundary en tests**, apoyada en TestIdentityFactory de TASK 002/003. No es autenticación criptográfica ni un adaptador a usuarios corporativos. La ruta IAM no autentica este workflow; no se implementan JWT, login, linking por email o traducción de roles a grants. Un proveedor productivo de este puerto requerirá contrato/autoridad y revisión propios, no sustituir el fixture con JSON.

El contexto reconocido por el servicio no puede vencer después del envelope: se rechaza esa composición antes del broker. El fixture emite contextos acotados a cinco segundos usando la fábrica existente solo en tests; no copia ni reescribe contextos IAM productivos. Así la revalidación interna existente también detecta expiración entre metadata/content, no solo al terminar un nodo. El presupuesto de operación conserva su límite independiente de cinco segundos.

## Estado, Runtime context y contenido efímero

EnterpriseState contiene solo operation_id, correlation_id, resource_id, operation, status, reason y pasos cerrados. Runtime.context es RunInfo con **solo operation_id**, no envelope, contexto IAM, principal, destinatario, credenciales, store o contenido. Cada invocación compila su propio grafo; los nodos cierran sobre un frame privado limitado a esa ejecución. No existe registro global de resultados ni ID de recuperación.

El resultado sensible de ConnectorService permanece en ese frame, nunca se devuelve desde un nodo ni se añade a canales. Un finally exterior retira referencias en todas las salidas del ciclo protegido, incluidas cancelación y fallo de close; detalles y alcance de traceback en la sección de corrección del blocker. La respuesta autorizada incluye documentos etiquetados, refs internas, organización/instancia y versión, con texto excluido de repr. Recibir un operation_id/correlation_id no autoriza consultar resultados, reanudar ni reutilizar un contexto. El consumidor interno es responsable de su respuesta al destinatario fijado; no se presenta como transporte humano autenticado productivo.

No se promete borrado criptográfico de strings Python ni aislamiento ante código malicioso del mismo proceso. Los objetos privados/puertos son composición confiable, no un sandbox.

## Checkpoints, memoria, trazas y streaming

El grafo compila con `checkpointer=False`, `store=None`, `cache=None`, debug deshabilitado. No necesita interrupt/resume y deliberadamente no usa el saver clínico: conservar contenido/autoridad o aceptar un checkpoint como permiso violaría el alcance. No se admite configuración externa que los active.

`Context().run` aísla la configuración/callbacks heredados de LangChain; `tracing_context(enabled=False, parent=False)` deshabilita LangSmith incluso con flags de entorno activos, y callbacks está vacío. No existe API pública stream/astream/ainvoke/get_result. Las pruebas observan los updates reales de los cuatro nodos: sin documentos, identidades, referencias de credenciales o URLs. Ningún nodo escribe streams custom ni logs. Las comprobaciones son de esta composición offline, no certificación de toda telemetría futura del host.

## ConnectorService, Graph offline y SQLite

Se requiere servicio exacto compuesto con SQLitePolicyStore y GraphReadAdapter offline, sin caché de contenido (`cache_size=0`). El módulo no importa fábricas de test, clients HTTP, SDKs ni código clínico. Usa los puertos aprobados y, para la frontera final, los helpers internos existentes `_validate_delivery`/`_event`; ese acoplamiento está explícito y requerirá revisar pruebas si cambia el servicio, no crear otra implementación de política.

Onboarding, grants, Selected simulado, catálogo, broker, GET v1.0, parser, nextLink, budgets, status y 302 conservan TASK 003/004. La descarga ficticia usa `.invalid` y nunca reenvía autoridad Graph. No existe transporte real activable por flag. Se prueba business/documentLibrary en TASK 004; estas pruebas no acreditan permisos Selected ni compatibilidad Microsoft operacional.

Solo el fixture inicializa su base dedicada/test-owned. El workflow no crea tablas/migraciones ni abre bases clínicas/IAM. Se conservan guard transaccional, snapshots consistentes y fallos cerrados. No hay llamadas de transporte dentro del guard: el permiso externo de entrega es una consulta del doble en memoria.

## Auditoría y revocación

Secuencia positiva ordinaria: autorización local → resultado externo → decisión B del servicio → decisión B de la frontera final. Las cuatro fases/eventos mínimos comparten correlation_id; paginación/reintentos pueden añadir resultados externos. Las dos decisiones B son deliberadas: la primera no confirma recepción ni sustituye la última revalidación. Se usa el contrato/eventos existentes, sin eventos ficticios o cambios en IAM/Security Audit. La auditoría administrativa sigue separada.

Fallos locales se auditan con atribución verificada o anónima, refs resueltas y razones cerradas; nunca argumentos/raw errors. Sink previo fallido: cero broker/transporte. Fallo posterior o del commit final SQLite: cero contenido, sin inventar persistencia en el sink fallido. Un fallo de cleanup de frontera también suprime la respuesta.

Se revalida el envelope entre fases y al entregar; revisiones/expiraciones no se actualizan para rescatar solicitudes viejas. Retiro, suspensión, rotación, offboarding o permiso externo simulado retirado antes de las últimas comprobaciones suprimen contenido. El guard conserva orden local por archivo con escritores independientes. No promete cancelar lecturas ya realizadas, retirar bytes ya entregados, frescura ACL Microsoft ni revocación distribuida instantánea.

## Gates y errores

A obtiene datos sintéticos; B verifica destinatario, organización, recurso y grants independientemente. A sin B produce entrega suprimida. C permanece DENY y D DISABLED: no modelos, embeddings, chunks, índices, RAG institucional o MCP. Una API key de otro flujo no habilita nada aquí.

Resultados finales cerrados: DENY, UNAVAILABLE, EXTERNAL_DENIED, DELIVERY_SUPPRESSED o DELIVERY_ALLOWED. LOCAL_ALLOW/EXTERNAL_SUCCESS solos se rechazan como resultado final. Sin URLs, cuerpos externos, SQL, paths, excepciones ni contextos internos en la salida. Se conservan categorías/reintentos de TASK 004, nunca fallback privilegiado.

## Concurrencia y aislamiento

Estado/envelope/contenido son propios de cada invocación; tampoco se reutilizan entre llamadas paralelas del mismo objeto workflow. El servicio conserva su presupuesto de dos operaciones por organización/instancia. El fixture de identidad tiene leases separadas: cerrar una invocación no retira otra. Events/Barrier y reloj inyectado prueban carreras, sin sleeps arbitrarios.

No hay threads persistentes ni checkpoint empresarial. IDs repetidos y tenant compartido no unen grants de ORG-A/ORG-B. Las APIs de lectura de auditoría respetan la organización del solicitante; no consultar siempre la auditoría A cuando el actor pertenece a B.

## Demostración E2E offline reproducible

Desde `services/ai-service`, con venv existente y basetemp nuevo/test-owned fuera de `.pytest-tmp`:

```powershell
$taskBase = Join-Path (Resolve-Path '..\..\infra\iam-lab\.runtime').Path ('eca5-e2e-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $taskBase) { throw 'Usar una carpeta nueva' }
.\.venv\Scripts\python.exe -m pytest -q -s -p no:cacheprovider --basetemp $taskBase tests/test_enterprise_connector_workflow.py -k offline_e2e_scenario
```

La prueba usa grafo compilado, onboarding real del fixture SQLite y transporte Graph simulado; bloquea sockets/DNS. Imprime solo contadores y códigos, nunca contenido/secretos. Repetición tras la corrección: **8/8 escenarios aprobados, cero intentos externos**, lease cerrada/frame sanitizado y cero referencias sensibles propias identificadas por el inspector en cada caso.

| Escenario | Recorrido / resultado | Adquisiciones / wire / documentos / eventos |
|---|---|---|
| Positivo ORG-A | Cuatro nodos, A/B, entrega propia autorizada | 1 / 2 / 1 / 4 |
| ORG-A → recurso B | Validación y resolución, DENY organization_mismatch | 0 / 0 / 0 / 1 |
| Revocación durante lectura | Cuatro nodos, DELIVERY_SUPPRESSED policy_revision_changed | 1 / 2 / 0 / 3 |
| Hostil | Cuatro nodos; texto etiquetado, política intacta, ninguna herramienta/modelo extra | 1 / 2 / 1 / 4 |
| CancelledError con traceback retenido | Se propaga la misma excepción, sin respuesta normal | 1 / 2 / 0 / 3 |
| KeyboardInterrupt con traceback retenido | Se propaga la misma excepción, sin respuesta normal | 1 / 2 / 0 / 3 |
| Fallo ordinario de close | UNAVAILABLE; no documento | 1 / 2 / 0 / 5 |
| Cancelación y fallo de close | CancelledError original más nota fija de cleanup; sin respuesta | 1 / 2 / 0 / 3 |

Los conteos de esta tabla son **totales persistidos para la correlación**. En el fallo de close, la vista administrativa ORG-A muestra cuatro de los cinco: el fallo posterior al retiro de lease se atribuye anónimamente, sin inventar un principal. El quinto es un fallo real, no recepción ni éxito ficticio. Las dos decisiones B anteriores no confirman recepción. La consulta de conteo global ocurre solo en el test sobre su base propia, nunca como una API empresarial o ampliación de acceso administrativo.

Todos tienen cero llamadas LLM, embeddings, MCP o conexiones externas. Son pruebas deterministas de integración LangGraph **offline**, no E2E operacional Microsoft.

## Pruebas y regresiones

[Fixture](../../services/ai-service/tests/enterprise_connector_workflow_fixture.py) y [suite TASK 005](../../services/ai-service/tests/test_enterprise_connector_workflow.py) ejecutan grafos compilados reales. Cubren contrato cerrado, suplantaciones, lifecycle, SQLite/auditoría, metadatos/hijos/texto, paginación/nextLink, 401/403/429/5xx/timeout/302, revocación entre fases y entrega final, concurrencia, estado/streaming/trazas y contenido hostil. Se conserva la etiqueta y procedencia mínima sin estado sensible.

La ejecución conjunta usa IAM primero por la deuda OIDC existente de fechas calculadas al importar; no se modifica IAM ni se afirma independencia del orden. Continúan el symlink Windows omitido sin privilegio, warning Starlette/AnyIO y deuda histórica CRLF. No se ejecuta la suite indiscriminada que puede contactar HAPI ni pruebas live opt-in.

Durante desarrollo se corrigió el cleanup del fixture que retiraba otro envelope paralelo y se repitió la selección focalizada (16 aprobadas). Una selección conjunta alcanzó 285 aprobadas y falló al exigir dos commits SQLite simultáneos sin contención: el timeout de auditoría cerró correctamente una respuesta. La prueba positiva ahora mantiene dos lecturas en vuelo y ordena commits con Events; otra prueba fuerza el escritor independiente y exige UNAVAILABLE sin contenido (3 focalizadas aprobadas). No se amplió el timeout ni se relajaron controles. El E2E negativo se alineó a principal A→recurso B para consultar la auditoría del solicitante; no era una ausencia de auditoría ni un bypass. Se eliminó durability sin efecto al no haber checkpointer. El módulo se situó en namespace empresarial separado tras inspeccionar los límites de imports de los módulos raíz; las repeticiones interrumpidas no se contabilizan como selecciones completas. Ningún arreglo modifica el servicio, IAM o grafos clínicos.

Otra selección alcanzó 299 aprobadas y detectó un error del setup nuevo de Gate B: `change_grant` no admite el parámetro gates. Se corrigió utilizando retiro del grant y registro explícito del nuevo grant A-only, sin ampliar la API del control plane. Después aprobaron las 132 pruebas nuevas; se añadieron tres negativas de resultado de servicio malformado, incluidas en la selección final. Los fallos de construcción/prueba anteriores no se ocultan ni se suman como aprobaciones finales.

**Evidencia histórica anterior al blocker: 804 aprobadas, 6 omitidas, un warning preexistente, en 346,53 s.** Desglose anterior: 137 TASK 005; 158 TASK 004; 75 TASK 003; 145 TASK 002; 175 IAM/legacy/auditoría/Human Review; 114 clínicas/arquitectónicas offline. No se usa esa ejecución para afirmar que el cleanup estaba resuelto. Las omisiones son el symlink físico Windows y cinco tests live HAPI/Gemini opt-in. Cero intentos externos; 136 socketpairs internos de biblioteca estándar Windows, no conexiones a servicios. También incluía negativas de vigencia, no las nuevas de cancelación/retención.

Orden real pasado a `pytest.main` desde el harness con guard de red, `-q -x -p no:cacheprovider` y basetemp absoluto nuevo: `test_oidc_workload.py`, `test_trusted_identity_registry.py`, `test_service_auth.py`, `test_security_audit.py`, `test_workflow_security_audit.py`, `test_human_review_security_audit.py`, `test_enterprise_connector_workflow.py`, `test_enterprise_connector_graph.py`, `test_enterprise_connector_control_plane.py`, `test_enterprise_connectors.py`, `test_langgraph_workflow_orchestration.py`, `test_federated_langgraph_mode.py`, `test_langgraph_followup_workflow.py`, `test_langgraph_gemini_fhir_followup.py`, `test_architecture.py`. Los flags live se fijaron a false solo en el proceso de pruebas, sin alterar entorno persistente ni archivos de configuración. Compileall del módulo/fixtures y comprobaciones AST/imports aprobados. No se ejecutaron los tres hashes CRLF ni HAPI live.

## Corrección del blocker: cancellation-safe sensitive frame cleanup

### Causa y reproducción previa

El `_invoke` anterior tenía dos secciones try/finally consecutivas: la primera cerraba la lease y la segunda limpiaba el frame. CancelledError/KeyboardInterrupt, o una interrupción durante close, podían abandonar la primera sin alcanzar la segunda. Dos reproducciones con grafo real confirmaron lease retirada, ausencia de respuesta/conexiones externas y documentos/envelope/solicitud/argumentos retenidos en el frame accesible desde el traceback. La regresión nueva falló antes de corregir con diagnóstico fijo, sin imprimir el sentinel. Es retención sensible, no exfiltración demostrada.

La investigación incluyó aliases locales de OperationResult, envelope, contexto, evaluación y argumentos en helpers y closures. Limpiar un atributo no basta si un frame de traceback conserva otra referencia. No se modificaron ConnectorService, política, SQLite, auditorías previas, Graph, IAM ni código clínico para resolverlo.

### Estrategia y orden de cleanup

1. Crear el frame inicialmente vacío dentro de la región protegida; solo después asociar argumentos. Una interrupción en construcción no recibe contenido/autoridad.
2. Ejecutar el grafo real y la entrega actual, conservando estados/gates/auditoría.
3. Cerrar la lease antes de retirar su envelope; close sigue siendo responsable de retirar su lease incluso si informa un fallo. El fixture conserva su finally y leases independientes.
4. Solo en la salida normal autorizada, construir EnterpriseResult sin conservar un alias local al OperationResult sensible. No mutar el documento/resultado ya entregado legítimamente.
5. Finally exterior: clear idempotente y, en un finally adicional, limpieza directa de los slots privados result/envelope/request/arguments/interruption. Si un paso custom/interrumpido falla, la ruta directa todavía visita los demás slots. No depende de llegar a una segunda sección.
6. Los helpers eliminan sus aliases en finally; se eliminaron los aliases de resultado/envelope de la entrega. Después del cleanup local, `_invoke` sanitiza frames **ya terminados, del módulo exacto y ligados por identidad al owner de esta invocación** en su traceback, cause/context y grupos, conservando la excepción y ubicaciones de stack. Pertenecer solo al módulo no basta. Los frames activos y el facade limpian sus variables en su propio finally. No se limpia memoria global ni frames de otras invocaciones o bibliotecas.

La frontera conserva una señal de interrupción privada y transitoria cuando se cancela un nodo. No entra en EnterpriseState, Runtime.context, eventos o excepciones como un payload nuevo, y también se retira al terminar. Las pruebas detectaron que, sin esa comprobación al volver del runtime y en sus handlers, una cancelación de tarea podía terminar convertida en UNAVAILABLE. Ahora se relanza la señal original antes de cualquier entrega/continuación, sin modificar LangGraph.

### Prioridad de excepciones

| Situación | Comportamiento |
|---|---|
| Interrupción primaria | Se propaga el mismo objeto CancelledError/KeyboardInterrupt; ninguna respuesta normal o fallback |
| Primaria más close fallido | Gana la primaria; nota fija enterprise_lease_cleanup_failed, sin adjuntar cuerpo/objeto del fallo secundario |
| Primaria más clear fallido | Gana la primaria; nota fija enterprise_frame_cleanup_failed, con limpieza directa de respaldo |
| Ambas limpiezas fallan durante interrupción | Se preserva la primaria y ambas notas; no se ocultan como éxito |
| Close ordinario falla sin primaria | UNAVAILABLE sin contenido, usando vocabulario de auditoría existente |
| Close lanza BaseException sin primaria | Propaga esa interrupción y limpia el frame |
| Clear falla sin primaria | Propaga el fallo, no retorna el resultado que estaba preparado; limpieza directa en finally |

No se usa BaseException para devolver éxito. Se cubren explícitamente asyncio.CancelledError, KeyboardInterrupt y un BaseExceptionGroup con ambos. No hay API async/generador/resume empresarial; otros consumidores o cancelaciones futuras requieren su cobertura propia. No se fabrican eventos de cancelación/recepción ni persistencia en un sink caído.

### Salidas reconstruidas A–O

| Ruta | Resolución / garantía propia |
|---|---|
| A: DELIVERY_ALLOWED | Resultado legítimo preservado; frame limpio |
| B: DENY | Sin contenido; cierre/clear exterior |
| C: UNAVAILABLE | Sin contenido; cierre/clear exterior |
| D: EXTERNAL_DENIED | Sin contenido; cierre/clear exterior |
| E: DELIVERY_SUPPRESSED | Sin contenido; cierre/clear exterior |
| F: validación rechazada | Sin broker/transporte; frame limpio |
| G: error en graph.invoke | Error ordinario fail-closed; señal de interrupción propagada |
| H: fallo de auditoría final | Sin contenido; solo decisiones/fallos realmente persistidos |
| I: fallo de commit | Rollback, sin contenido ni evento de éxito inventado |
| J: CancelledError | Mismo objeto propagado; lease/frame/aliases retirados |
| K: KeyboardInterrupt | Mismo objeto propagado; lease/frame/aliases retirados |
| L: fallo de close | Política de prioridad anterior; clear no omitido |
| M: fallo en clear | Los otros slots aún se limpian; fallo observable |
| N: interrupción antes del grafo/construcción | Sin adquisición/lectura; owner inicialmente vacío |
| O: interrupción tras recuperar documento | Sin respuesta ni entrega posterior; traceback propio sanitizado |

### Evidencia y alcance de retención

Pruebas añadidas: `test_retained_tracebacks_cancel_cleanup`, `test_cancellation_priority_over_close_error`, `test_cleanup_step_failure_still_clears_other_slots`, `test_all_terminal_paths_clear_owned_frames`, `test_cancelled_parallel_invocation_does_not_retire_other_lease`, `test_cancel_during_frame_construction_has_no_sensitive_owner` y `test_base_exception_group_is_propagated_without_frame_retention`; E2E ampliado a ocho casos. Se retiene deliberadamente la excepción y su traceback, se usan sentinels únicos y el inspector de test solo lee referencias: no las limpia para conseguir PASS. Examina slots, variables propias, estructuras, dataclasses y celdas de closures; distingue los puertos/fixtures/consumidores externos que legítimamente conservan sus datos.

Se verifican dos lecturas paralelas con Events: la cancelada pierde su lease/frame sin retirar la lease de la otra, que entrega solo su documento. Sin sleeps ni ampliación del timeout SQLite. Una negativa de auditoría selectiva conserva cuatro eventos (el cuarto es UNAVAILABLE); no confundirla con sink totalmente caído/commit fallido que impide esa escritura. El primer assert del test se corrigió para exigir esa distinción, sin cambiar el productor de auditoría.

Selección intermedia de la corrección: 846 PASS, 6 SKIPPED, un warning preexistente, en 335,31 s, con 179 TASK 005. Después se añadió una negativa de cancelación de un solo disparo dentro del handler de auditoría de denegación: reprodujo una conversión a respuesta normal porque ese handler quedaba fuera de la captura de señal. El wrapper ahora cubre acción, handlers y proyección; `test_one_shot_cancellation_in_denial_audit_is_not_retried` exige excepción original, un único intento de auditoría y cero broker/transporte. Sus dos variantes y las doce cancelaciones anteriores aprobaron (14 focalizadas). Ningún cambio en productores de auditoría ni política; se repite la selección completa tras esta última corrección.

**Evidencia histórica del primer blocker: 848 PASS, 6 SKIPPED y un warning preexistente, en 227,28 s.** Incluye 181 TASK 005 (137 anteriores más 44 casos netos nuevos), 158 TASK 004, 75 TASK 003, 145 TASK 002, 175 IAM/legacy/auditoría/Human Review y 114 clínicas/arquitectónicas offline. Cero intentos externos; 136 socketpairs internos de biblioteca estándar Windows/ASGI. No cubría el segundo hallazgo de aislamiento entre cadenas de invocaciones.

Los ocho E2E también aprobaron en esa selección, incluida la comprobación del conteo total frente a la vista ORG-A. Aprobaron además 43 focalizadas de cleanup/E2E, tres de construcción/grupo y catorce de cancelación/auditoría; son subconjuntos solapados, no se suman al total. Aquella revisión no publicó; la nueva autorización permite commit/push únicamente después de revisar y validar la corrección adicional.

**Límites:** no borrado criptográfico, sandbox de Python ni promesa de eliminar copias externas o referencias legítimas del fixture, consumidor o librerías ajenas. El scrub acotado sacrifica locales de debugging del traceback propio, no los sitios de stack ni la identidad de la excepción. No modifica tracing clínico, infraestructura o contratos. No certifica toda observabilidad del host; el resultado autorizado del consumidor se conserva intencionalmente.

### Segundo hallazgo: pertenencia de frames por invocación

La revisión final reprodujo una limpieza cruzada: al cancelar B dentro del handler de cancelación de A, Python enlaza ambas excepciones por `__context__`. El scrub anterior filtraba solo por nombre de módulo y limpiaba también el frame terminado del facade de A. Ambas leases se cerraban, no había documentos devueltos ni intentos externos, y las excepciones originales se preservaban, pero se modificaba evidencia de otra invocación. No es una exfiltración ni un bypass de autorización demostrado. La publicación se detuvo y el hallazgo se reportó antes de continuar; una regresión nueva falló antes de corregir.

La corrección no introduce un registro global o thread-local de owners. El try exterior de `_invoke` conserva el owner concreto hasta completar cierre/clear y pasa esa identidad al scrub. Se exige `f_globals is globals()` y que el local/closure `frame`, o el `self` de un método del owner, sea **ese mismo objeto**, nunca solo el mismo workflow, organización o operation_id. Un owner ausente por construcción interrumpida no habilita scrub; se construye inicialmente sin argumentos sensibles. Los frames del facade no se seleccionan por su `self` workflow y retiran argumentos explícitamente en finally.

Se mantienen cadenas/grupos e identidad de excepciones; recorrer una causa no concede permiso para modificar sus frames. `test_chained_invocations_preserve_foreign_traceback_frames` retiene e inspecciona sin limpiar los frames de A y de su callback externo, y exige que sus locales mantengan las mismas referencias después de B. Son doce variantes: CancelledError/KeyboardInterrupt, context/cause/group, mismo workflow o workflows de organizaciones distintas. Los doce casos aprobaron tras reproducir el fallo inicial.

La prueba paralela de cancelación ahora cubre además fallo de close, fallo parcial de clear y ambos: cuatro variantes con Events, leases independientes y entrega correcta de la otra organización. Son **15 casos netos adicionales** respecto a 848. La suite TASK 005 completa aprobó **196/196**, en 89,64 s, con cero intentos externos.

**Selección conjunta final después de la corrección de pertenencia: 863 PASS, 6 SKIPPED y un warning preexistente, en 197,66 s.** Desglose: 196 TASK 005, 158 TASK 004, 75 TASK 003, 145 TASK 002, 175 IAM/legacy/auditoría/Human Review y 114 clínicas/arquitectónicas offline. IAM primero, basetemp nuevo/test-owned y guard de red: **cero intentos externos**, 136 socketpairs internos stdlib Windows/ASGI. Las omisiones siguen siendo el symlink Windows y cinco live opt-in; el warning es Starlette/AnyIO. No se modificaron ACL, timeouts, IAM ni pruebas históricas. Los ocho E2E aprobaron además por separado en 6,00 s, con los resultados y contadores de la tabla anterior. No se suman estas repeticiones al total conjunto. Compileall del paquete/fixture/tests, imports y AST aprobados.

**Punto de mantenimiento explícito:** el módulo usa objetos traceback, lectura de `f_locals` para comprobar pertenencia y `frame.clear()` únicamente para frames propios terminados. No escribe el diccionario de locales, no usa `sys._getframe()`, GC ni introspección global de objetos. El runtime rechaza limpiar un frame ejecutándose; ese RuntimeError no reemplaza la excepción y la retirada explícita de referencias sigue en finally. No se modifican frames LangGraph, terceros o owners distintos. Es necesario para retirar aliases conservados por tracebacks de helpers terminados, no para borrar memoria arbitraria. El cambio sacrifica locales de depuración propios, no evidencia de otros owners; su alcance y comportamiento deben revalidarse al cambiar Python, LangGraph o la estructura de helpers/closures. Esto no constituye un sandbox ni garantiza eliminar copias que retenga un consumidor o una biblioteca externa.

## Evidencia T01–T24 y límites

Se mantienen **9 PASS de laboratorio, 12 PARTIAL, 3 NOT IMPLEMENTED**. No se edita la matriz base ni se eleva una amenaza a PASS productivo por ejecutar LangGraph offline.

| Threat | Evidencia TASK 005 / heredada | Límite residual | Status |
|---|---|---|---|
| T01 | test_real_graph_owned_operations_and_trusted_recipient; test_forged_or_inconsistent_boundary_values_are_not_permissions | Fixtures, no SaaS Microsoft real | PASS |
| T02 | test_tool_arguments_never_select_authority; test_input_is_a_closed_request_not_prompt_or_resume | Frontera de test, proceso confiable | PASS |
| T03 | test_tool_arguments_never_select_authority | Roles/grants no son argumentos; IAM intacto | PASS |
| T04 | Puertos sin credenciales reales | Vault/robo de token Microsoft no implementados | NOT IMPLEMENTED |
| T05 | Sin refresh/delegated | Custodia delegada no implementada | NOT IMPLEMENTED |
| T06 | test_forged_or_inconsistent_boundary_values_are_not_permissions | Binding sintético, no linking externo | PASS |
| T07 | test_registration_and_lifecycle_fail_before_wire; test_invalid_parent_reference_never_delivers | Moves/identidad offline, no cambios Microsoft reales | PASS |
| T08 | test_gate_a_does_not_imply_gate_b; cobertura por hijo TASK 004 | ACL/herencia SharePoint pendientes | PARTIAL |
| T09 | Perfil Selected/read heredado TASK 004 | Sin consentimiento/permiso efectivo Microsoft | PARTIAL |
| T10 | Contrato cerrado de operaciones; AST de imports | No aislamiento de host/app-only real | PARTIAL |
| T11 | Sin consentimiento/linking humano | TASK 006 no iniciada | NOT IMPLEMENTED |
| T12 | test_revocation_revalidates_at_actual_delivery_boundary; test_inflight_revocation_uses_events_not_sleep | Orden por archivo, no SLA distribuido | PARTIAL |
| T13 | test_external_revoke_during_final_boundary_audit_suppresses_delivery | Permiso externo solo simulado | PARTIAL |
| T14 | test_graph_error_categories_and_bounded_retries | Sin fallback; no proveedor live | PASS |
| T15 | test_children_pagination_and_hostile_nextlink_through_graph; budgets heredados | Sin cuotas/scheduler productivos | PARTIAL |
| T16 | test_timeout_and_302_run_through_real_graph_without_url_escape | Sin red real/SSRF/DNS/TLS operativo | PARTIAL |
| T17 | test_resource_substitution_is_denied_before_broker | Links/remoteItem excluidos, no discovery | PASS |
| T18 | test_hostile_documents_are_delivered_only_as_untrusted_data | Workflow real sin LLM, no defensa universal de modelos | PASS |
| T19 | test_only_the_prebound_read_operation_is_available | C denegado, no egress productivo | PASS |
| T20 | test_integration_imports_no_clinical_llm_embedding_mcp_or_http_code | D deshabilitado; sin extractor/antimalware productivo | PARTIAL |
| T21 | test_two_orgs_parallel_have_distinct_invocations_no_thread_state; test_parallel_same_workflow_has_invocation_local_content | Sin ACL-RAG/retención empresarial | PARTIAL |
| T22 | test_audit_failures_are_fail_closed_through_graph; test_failure_after_graph_before_final_return_suppresses_content | SQLite local, no log inviolable/atomicidad Graph | PARTIAL |
| T23 | test_real_compiled_graph_has_only_safe_state_events_no_checkpoint_or_store; test_parent_callbacks_and_environment_tracing_cannot_capture_document | Canaries de composición offline, no telemetría futura del host | PARTIAL |
| T24 | Control plane TASK 003 sin cambios | Administrador corporativo/host no implementados | PARTIAL |

Las nuevas pruebas de traceback/cleanup añaden evidencia a T12/T21/T23 y la concurrencia mantiene T01/T02; no cambian la clasificación ni convierten observabilidad, Graph, IAM o vault en controles productivos.

## Limitaciones y preparación TASK 006/007

Solo laboratorio sintético. Faltan frontera humana corporativa, administración autenticada, custodia, Graph live/Selected por método, transporte seguro, frescura externa, HA y retención/auditoría productivas. No hay login humano, IAM empresarial ni aislamiento frente al host. No se conecta al endpoint IAM ni al grafo clínico por inferencia.

TASK 006 requiere autorización independiente y contratos de vinculación humana, consentimiento y custodia delegada; no reutilizar un workload como humano ni sustituir el puerto por claims libres. TASK 007 requerirá matriz E2E y clasificación de evidencia aprobadas. Ni esta implementación ni sus tests autorizan esas tareas, RAG, MCP o una activación live. La autorización actual permite commit/push de las ocho rutas si pasan todos los controles; después corresponde revisión del Product Owner. No crear PR ni hacer merge sin autorización nueva.
