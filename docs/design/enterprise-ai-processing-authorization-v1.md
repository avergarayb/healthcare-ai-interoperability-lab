# Enterprise AI Processing Authorization V1 — arquitectura de diseño

Estado: **Approved — design only; DESIGN-001**. El Product Owner aprueba esta arquitectura base para una futura implementación offline. Autoriza revisión final, precisiones documentales y commit/push exclusivamente de los cuatro documentos propios si los controles pasan; no PR ni merge. No autoriza iniciar TASK-C01/C02/C03/C04, implementar Gate C, gateway, persistencia, autenticación o DEMO-002. En el runtime existente C continúa DENY y D DISABLED. Datos exclusivamente sintéticos, sin proveedores reales, Graph live, RAG o MCP.

La base inspeccionada integra Enterprise Connector TASK 001–005 y DEMO-001 (PR #114). Los estados de autorización anteriores en runbooks/handoff son evidencia histórica; la autorización documental vigente es la indicada arriba. [ADR-097](../adr/ADR-097-enterprise-connector-authorization-boundaries.md) y el [contrato de conectores](../contracts/enterprise-connector-authorization-v1.md) se preservan. Este diseño desarrolla su gate C sin convertir A, B, Selected o una API key en autoridad de procesamiento.

Documentos de esta propuesta: [contrato y auditoría](../contracts/enterprise-ai-processing-authorization-v1.md), [amenazas complementarias](enterprise-ai-processing-threat-model-v1.md), [incrementos y DEMO-002](enterprise-ai-processing-implementation-plan-v1.md). El contrato define campos/vocabularios una sola vez; este documento define composición y límites.

## Inventario contrastado con código

R = reutilizable dentro del laboratorio; A = requiere adaptación explícita aprobada; I = mantener aislado. Ninguna fila acredita identidad humana corporativa o compatibilidad cloud.

| Componente / evidencia | Capacidad real y decisión de reutilización |
|---|---|
| [EnterpriseDocumentWorkflow](../../services/ai-service/app/enterprise_workflows/document_read.py), `invoke`, `_compile`, `_deliver` | R: cuatro nodos reales, lectura acotada A/B y entrega final. Requiere SQLite/Graph offline exactos, sin caché. Consumir su entrada/salida pública, no sus helpers privados; no insertar nodos ni habilitar C en ese grafo. |
| [ConnectorService](../../services/ai-service/app/enterprise_connectors/service.py), `execute` | R: política, broker, lectura, revalidación, auditoría, B y cleanup. El resultado documental solo sale si B permite. No es un puerto de adquisición A-only ni model gateway. A: frontera pública de entrega derivada, propuesta más abajo. |
| [PolicyEvaluator](../../services/ai-service/app/enterprise_connectors/policy.py), `_evaluate`, `in_scope` | R: identidad reconocida, registro, ámbitos, vigencia, grants completos sin unión y revisión. C/D se rechazan expresamente, aunque un grant intente incluirlos. Añadir un permiso a un fixture no habilita C. A: evaluador C aditivo que consume comprobaciones A/B existentes sin duplicar su resolución. |
| [IdentityBoundary y modelos](../../services/ai-service/app/enterprise_connectors/models.py) | R: puerto `recognizes`, contexto interno y documento con texto fuera de repr. Emisor real actual solo de tests; reconoce objetos exactos, no JWT ni humanos corporativos. `UntrustedDocument.version` es versión del recurso registrado, no garantía de eTag Graph ni hash del contenido. |
| [InvocationBoundary](../../services/ai-service/app/enterprise_workflows/document_read.py), `VerifiedInvocation` | R: envelope de lectura ligado a principal, organización, recurso, propósito, destinatario y caducidad. A: envelope de procesamiento separado y vinculado al de lectura; no extender/cambiar silenciosamente el existente. No aceptar autoridad desde preguntas o JSON. |
| [SQLitePolicyStore](../../services/ai-service/app/enterprise_connectors/sqlite_store.py) y [ControlPlane](../../services/ai-service/app/enterprise_connectors/control_plane.py) | R: snapshots, CAS, guard de entrega local, lifecycle y consultas organizacionales. I: esquema cerrado y migración histórica; añadir tablas inesperadas lo invalida. No alojar aquí tablas C sin cambio versionado y aprobación separada. Administración actual es sintética, no productiva. |
| [SQLiteConnectorAudit](../../services/ai-service/app/enterprise_connectors/durable_audit.py) | R: auditoría durable A/externa/B, fail-closed y vocabulario cerrado. I: no admite fases nuevas de modelo; no ampliar `Phase`, tablas ni actores existentes incidentalmente. Auditoría C aditiva propia. |
| [GraphReadAdapter](../../services/ai-service/app/enterprise_connectors/providers/microsoft_graph/adapter.py) | R: protocolo offline, catálogo, validación y permisos externos simulados. No hay OAuth/HTTP live. A: evidencia documental confiable para vincular bytes/versión/clasificación; no dar al modelo URLs, credenciales ni catálogo completo. |
| [DEMO-001](../demos/enterprise-connector-demo-001.md), [consola](../../scripts/enterprise-connector-demo/run_demo.py) | R: proceso offline, fixtures, aislamiento por escenario, audit minimizado y guard de sockets. No es chat ni autenticador humano. Mantener demo existente independiente. |
| [Model Boundary v1](../fhir/model-boundary-contract-v1.md), [consumer](../../services/ai-service/app/consumer.py) | I: contrato Java de proyección clínica allowlisted; Python valida/consume con `modelCalled=false`. No es una API genérica de inferencia ni licencia para enviar documentos. Reutilizar principios de allowlists/fallo cerrado, no payloads, endpoints o tokens. |
| [LLMProvider](../../services/ai-service/app/llm_provider.py), [FakeLLMProvider](../../services/ai-service/app/fake_llm_provider.py), [GeminiProvider](../../services/ai-service/app/gemini_provider.py) | I: `generate_summary` recibe `ExperimentalSummaryRequest` clínico/sintético. `ProviderGeneration` inspira un resultado cerrado, no es prueba de autorización. `generate_structured` y errores acotados son precedentes; no reutilizar prompt, factory clínica, threads/SDK o credenciales. A: puerto empresarial pequeño propio, fake determinista primero. |
| [Settings](../../services/ai-service/app/config.py), `main.get_llm_provider` | I: configuración clínica/experimental selecciona Gemini según settings. Ningún flag/key heredado debe activar el nuevo camino. No leer archivos de secretos ni modificar settings durante diseño. |
| [Orquestación clínica](../../services/ai-service/app/langgraph_workflow_orchestration.py), [contrato Human Review](../contracts/follow-up-review-workflow-v1.md) | I: protocolos, persistencia, `interrupt`/resume, cierre humano y saver SQLite clínicos. Reutilizar solo patrón StateGraph y separación de autoridad. No usar un caso clínico como aprobación de C ni crear/cerrar Human Review empresarial por analogía. |

## Seis autoridades, no una unión de permisos

| Autoridad | Dueño / decisión | No concede |
|---|---|---|
| Platform Identity | Frontera verificada, organización activa y vigencia; en MVP emisor explícitamente de test | Grant Graph, C, identidad humana corporativa |
| Connector Authorization | Motor local existente, principal/instancia/recurso/operación/propósito y A/B | Procesamiento por modelo |
| External Resource Authorization | Proveedor de documentos; en MVP permiso independiente simulado | Derecho a divulgar a un modelo o a otro destinatario |
| AI Processing Authorization | Grant C completo + perfil de modelo/destino/retención/budgets vigentes | Leer otro documento, dar herramientas o entregar al humano |
| Model Provider Credentials | Solo adaptador futuro y referencia confiable ligada al perfil; fake no tiene secretos | Autoridad C ni permiso de recursos Graph |
| Final Recipient Authorization | B fresco sobre fuente y destinatario más validación/clasificación de respuesta derivada | Envío previo al modelo, recepción humana confirmada o conservación D |

La pregunta es entrada no confiable, no identidad. ORG-A/ORG-B, tenant documental y tenant/cuenta del proveedor del modelo son bindings separados, incluso si sus identificadores coinciden. Un modelo no es principal, administrador ni revisor. No hay unión de grants parciales ni fallback entre autoridades.

El «usuario sintético» de DEMO-002 es el operador del laboratorio bajo un principal técnico de test preautorizado y un recipient sintético, no una nueva identidad humana. Conservar `principal_type=workload` del fixture actual; no renombrarlo como humano ni implementar linking/delegated por esta propuesta. Un login humano verificado futuro necesitaría contrato propio.

## Composición mínima propuesta

Un incremento interno de Healthcare AI, sin dependencia Java/FHIR, nuevo servicio desplegable, framework de agentes ni registro global de herramientas:

```text
Frontera sintética confiable -> envelope de procesamiento + pregunta acotada
  -> workflow nuevo, metadata-only
       ValidateRequest
       ResolveAuthorizedResource
       ReadAuthorizedDocument -> EnterpriseDocumentWorkflow.invoke (cuatro nodos intactos)
       EvaluateGateC          -> decisión independiente, grant completo
       PrepareBoundedModelContext
       InvokeApprovedModel   -> gateway local -> fake puro, sin red/herramientas
       ValidateGroundedAnswer
  -> fuera del grafo: FinalDeliveryAuthorization -> respuesta de esta llamada
```

Todos los fallos terminan sin respuesta documental; no agent loop, retry de nodos, streaming ni continuación automática. Resolver/revalidar no busca recursos globales. El reader actual comprueba A/B y devuelve su resultado al consumidor confiable; la nueva aplicación lo guarda transitoriamente, no lo imprime por defecto. Ese B previo autoriza la entrega documental contratada, **no transferencia al modelo**. Esta composición deliberadamente exige B también para leer: el primer MVP no admite procesar documentos cuyo solicitante no puede recibir. Un futuro A-only necesitaría otro contrato y revisión, no sortear B.

Antes de cualquier exposición al modelo se requiere C sobre la fuente exacta, pregunta permitida y perfil completo. Preparar contexto incluye cualquier contenido de pregunta; no solo el documento. Selección/serialización sensible queda después de C. El gateway revalida y consume una lease interna de un uso inmediatamente antes de llamar al fake. Registrar intención no significa que el adaptador o un proveedor la haya recibido.

Al volver: comprobar caducidad/revocación, validar salida y fuentes; la frontera externa al grafo vuelve a comprobar identidad, A/B, C, clasificación y versiones, audita y confirma commits antes de devolver. C no concede B. Decisiones B anteriores del reader/servicio se conservan; no se borran por parecer duplicadas.

## Extensión explícita, no segundo motor de conectores

El evaluador C aplica solo restricciones nuevas de procesamiento sobre evidencia confiable y las comprobaciones A/B públicas existentes. No reimplementa `in_scope`, resolución de bindings, external grants, identidad o lifecycle. El envelope distingue propósito de lectura autorizado y propósito IA aprobado: no reescribe uno para satisfacer el otro.

Para no añadir consumidores de `_validate_delivery`/`_event`, TASK-C03 propondría **un único puerto público de entrega derivada en el dueño del servicio**. La implementación futura debe reutilizar sus comprobaciones actuales y preservar las dos fronteras B, admitir metadata de fuente/resultado acotada y ejecutar el callback de auditoría propia dentro del guard. No acepta texto arbitrario como permiso. Este puerto aún no existe; su firma y pruebas deben aprobarse antes de modificar código. No copiar el algoritmo de entrega al nuevo workflow ni importar privados como atajo. No es una refactorización general de TASK 005.

El mismo principio aplica a `AuthorizedSourceEvidence`: adaptador/composición confiables vinculan organización, instancia, tenant, recurso, versión registrada, clasificación y bytes recibidos. La evidencia actual no basta para declarar una versión de contenido Microsoft verificada. El MVP usa revisión del nuevo fixture y digest **solo efímero**, nunca auditado ni expuesto como identificador de contenido sensible. Copiar el digest o la referencia no crea autoridad portable ni un owner reconocido. Modificar fuente, bytes, versión o clasificación invalida las decisiones dependientes y las citas; no reconstruir evidencia desde una respuesta del fake ni permitir que el documento cambie su clasificación.

## Persistencia, revocación y puntos de orden

Propuesta: store SQLite C **separado y test-owned**, con grants/perfiles/versiones, reservas de presupuesto y auditoría C propia. No tablas de contenido, preguntas, respuestas, historial o checkpoints. Reduce el riesgo de alterar el esquema estricto del conector o stores IAM/clínicos. Tiene coste: referencias entre archivos no tienen FK ni atomicidad distribuida. Su contrato de esquema/inicialización/consulta necesitará aprobación en TASK-C02; no crear una base en DESIGN-001.

Revalidar C y A/B antes de reservar y antes de transferencia; liberar toda transacción mientras el fake procesa. Revocar/deshabilitar grant/perfil, cambiar clasificación/versión, vencer identidad/lease o retirar permiso fuente durante inferencia suprime el resultado al observarlo en las comprobaciones exigidas; política/frescura requerida no verificable falla cerrado. La semántica temporal local y externa se distingue abajo, sin detección instantánea global. No reiniciar ni renovar la autorización para rescatarlo. No se pueden retirar bytes que un proveedor futuro ya recibió; timeout/cancelación remotos pueden dejar ejecución desconocida.

Para la decisión final local, secuencia propuesta: **guard C -> guard conector -> revalidación de ambos ámbitos y permiso externo simulado -> auditorías respectivas -> última comprobación conjunta local -> commit conector -> commit C -> entrega**. Un ALLOW de un store no sustituye el chequeo del otro. Ninguna respuesta, cita o fragmento puede salir antes de completar satisfactoriamente todos los chequeos y commits exigidos. Nada de I/O de proveedor, espera de modelo o renderer dentro de los guards; tampoco transacciones o locks SQLite durante inferencia. No se implementa locking en DESIGN-001.

`T_auth` designa la última comprobación conjunta **local**, después de preparar las auditorías y mientras ambos guards siguen vigentes. El protocolo futuro debe demostrar que observa cualquier revocación/revisión de esos dos archivos confirmada antes de `T_auth`, y que la identidad/deadline siguen vigentes hasta permitir la salida. Si falta el chequeo, la vigencia o el commit de cualquiera de los stores, se suprime. Los commits en secuencia no son una transacción distribuida: uno puede quedar confirmado y el otro fallar. No se afirma atomicidad con entrega, proveedor ni observaciones de permisos fuera de SQLite.

| Intercalación relevante | Semántica exigida / condición de integración |
|---|---|
| Revocación C o conector confirmada antes de `T_auth` | Snapshot/chequeo correspondiente debe observarla y suprimir; un ALLOW anterior no la supera. Probar writers independientes, sin snapshots antiguos reutilizados. |
| Writer local intenta cambiar mientras su guard está vigente | No considerar su cambio confirmado por haberlo intentado; puede esperar o fallar por contención. No simular confirmación ni ampliar timeouts para ocultar carreras. |
| Conector confirma; después falla audit/commit C | No entregar nada. Puede permanecer una decisión B ya persistida, no evidencia de recepción ni una transacción global exitosa. Registrar fallo solo si el sink está disponible. |
| Writer del conector confirma tras liberarse su guard y antes de commit C o salida | Es posterior a `T_auth`; el orden propuesto no garantiza detectarlo. Ventana explícita pendiente de pruebas/revisión en C03; no anunciar protección «hasta el último byte». Si el requisito exige cubrirla, detener integración y aprobar un protocolo revisado antes de continuar. |
| Permiso externo simulado cambia entre su última consulta `T_ext` y `T_auth`/salida | Los guards SQLite no congelan ese permiso. La observación externa tiene su propio punto `T_ext`; retiro detectado suprime, pero no se garantiza detección instantánea posterior a esa consulta. C03 debe probar/definir el protocolo del doble y su ventana; ninguna equivalencia con frescura Graph live. |
| Caída o confirmación de commit no verificable | Sin entrega desde la llamada fallida; conservar UNKNOWN donde no pueda demostrarse el hecho. No fabricar rollback de otro archivo, recepción o evento persistido en un sink caído. |

Estas carreras, ambos fallos de commit y el orden de guards son **pruebas bloqueantes de TASK-C03**, no garantías verificadas por aprobar el diseño. El puerto público y su protocolo requieren aprobación específica antes de esa tarea; si no explican una intercalación/observación necesaria, queda pendiente de integración y se vuelve al PO. Cambios posteriores al punto aplicable no se cancelan retroactivamente, y nunca se promete revocación después de completar la entrega ni retractar bytes procesados/recibidos.

Reservas C se confirman antes de inferencia; nunca se mantiene un escritor SQLite durante ella. Contención falla cerrado con timeout acotado, no ampliar el timeout para hacer pasar concurrencia. Una ejecución/lease por operación y aislamiento organizacional en todas las claves; no compartir prompts, owners, grafos con captures sensibles ni respuestas. Reintento de pregunta es operación nueva, no resume por ID.

## Contenido efímero y dos P1 existentes

Se preservan los hallazgos [M01/M02](enterprise-connector-maintainability-demo-001.md): ownership de tracebacks y acoplamiento privado. No modificar su scrub, nombres/closures, excepciones o pruebas por efecto colateral.

Propuesta sencilla para lo nuevo: owner explícito por invocación, construido vacío dentro del try exterior, con refs de fuente/pregunta/contexto/candidato/leases fuera de canales. Nodos devuelven únicamente códigos y refs internas; helpers sensibles retiran aliases en finally; close y clear son independientes e idempotentes, con prioridad de cancelación original y diagnóstico fijo. No closure global, thread-local de resultados, caché de grafos con owner, `gc`, escritura de `f_locals` ni nuevo `frame.clear()`/inspección global. No reutilizar privados de limpieza TASK 005 desde otro módulo.

No basta poner `repr=False` o asignar un atributo a None. Retener tracebacks, cause/context/groups y cancelar mientras otro owner trabaja debe formar parte del gate de aceptación. El fake/controladores nuevos no propagarán errores ordinarios con inputs adjuntos; no se promete eliminar referencias que conserven bibliotecas/consumidores externos, ni borrado criptográfico Python. Si la retirada explícita no satisface las pruebas propias, detener el incremento y proponer aislamiento/revisión específica, no extender introspección a frames ajenos. Adaptadores reales necesitan decidir cancelación/threads/cierre y riesgo de copias antes de autorización; no copiar ciegamente el executor Gemini existente.

Graph: `checkpointer=False`, store/cache ausentes, callbacks vacíos, contexto nuevo y tracing deshabilitado aunque existan flags heredados. Runtime solo operation ID; ningún documento, prompt, pregunta libre, identidad, credencial, respuesta, excepción original o digest en estados, config, eventos LangGraph o checkpoints. Sin API stream/astream/resume/get-result. No historial conversacional persistido: cada turno vuelve a autorizar.

## Compatibilidad y propuestas que necesitan aprobación posterior

| Diferencia detectada | Propuesta separada, no cambio realizado |
|---|---|
| C/D y operación AI se rechazan expresamente en política/servicio actuales | Mantener ese camino igual; nuevo contrato C y composición opt-in separada. No ampliar gates de los grants de lectura ni eliminar el rechazo global. |
| Modelo y auditoría de conector no contienen fases C | Contrato de auditoría C en el documento nuevo y store propio; no nuevos enums/eventos en auditorías base. |
| Última entrega usa helpers privados | Puerto público acotado en TASK-C03 bajo aprobación explícita, con regresiones TASK 002–005 intactas. Bloqueante para integrar si no se aprueba. |
| Documento actual no acredita clasificación/versión de bytes para IA | Evidencia aditiva del reader/adaptador y fixture, sin reinterpretar `UntrustedDocument.version` como eTag ni cambiar el contrato base aquí. |
| Fixture de vacaciones no contiene días ni condiciones | Añadir un documento de test propio en un incremento autorizado; no editar los documentos existentes ni fabricar una respuesta. |
| Model Boundary, proveedores y Human Review son clínicos/experimentales | Mantenerlos aislados. Puerto empresarial mínimo propio; no extender modelos clínicos ni su autorización. |

El PO aprueba DESIGN-001 como base arquitectónica compatible con los límites A/B/C/D de ADR-097, no como operación de datos habilitada, implementación segura ya probada o aceptación de todos los riesgos de integración. Los alcances de C01–C04, esquema C y puerto público de C03 necesitan autorizaciones propias. Esta publicación solo registra el diseño aprobado y sus condiciones; no modifica ADR-097, contratos base, AGENTS, roadmap global, handoff ni runbooks históricos.
