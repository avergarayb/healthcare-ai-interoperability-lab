# Enterprise Connector Authorization V1 — synthetic fixture

TASK 002 **aceptada por el Product Owner exclusivamente para laboratorio sintético**. La autorización de revisión final permite corregir defectos bloqueantes acotados y, tras validar, staging/commit/push de las trece rutas propias; no PR, merge ni TASK 003. TASK 001 está integrada mediante PR #109; [ADR-097](../adr/ADR-097-enterprise-connector-authorization-boundaries.md) sigue Accepted — architectural direction only. Esto no integra Microsoft Graph, Entra, SharePoint, LangGraph productivo, RAG ni MCP. Toda evidencia de esta tarea es **determinista y sintética**, no live Microsoft ni acreditación de seguridad productiva.

Autoridad: [contrato local](../contracts/enterprise-connector-authorization-v1.md), [perfil Graph](../contracts/microsoft-graph-connector-permissions-v1.md), [arquitectura](enterprise-connector-authorization-v1.md), [threat model T01–T24](enterprise-connector-threat-model-v1.md) y [plan de siete tareas](enterprise-connector-authorization-implementation-plan-v1.md). Los documentos de TASK 001 conservan la evidencia de su etapa; este runbook describe únicamente el incremento ejecutable sintético posterior.

## Arquitectura e inventario implementados

Módulo interno [app/enterprise_connectors](../../services/ai-service/app/enterprise_connectors/), sin wiring en `app.main`, configuración productiva, rutas HTTP o grafos. No requiere Java/FHIR y no incorpora protocolos HIS/LIS.

| Archivo | Responsabilidad |
|---|---|
| [models.py](../../services/ai-service/app/enterprise_connectors/models.py) | Dataclasses frozen/slots, operaciones/gates, resultados y vocabulario cerrado |
| [registry.py](../../services/ai-service/app/enterprise_connectors/registry.py) | Snapshot tipado inmutable de registros/grants; publicación CAS bajo RLock y revisión monótona |
| [policy.py](../../services/ai-service/app/enterprise_connectors/policy.py) | Evaluación deny-by-default, ámbito exact/subtree, vigencia, ledger de decisiones de un uso y ausencia de unión de grants |
| [audit.py](../../services/ai-service/app/enterprise_connectors/audit.py) | Sink in-memory independiente con fallos por fase; sin escribir stores existentes |
| [synthetic.py](../../services/ai-service/app/enterprise_connectors/synthetic.py) | Broker y proveedor documental simulados, contadores/hooks de test |
| [service.py](../../services/ai-service/app/enterprise_connectors/service.py) | Interfaz interna, secuencia autorización/auditoría/adquisición/lectura/entrega, budgets y caché transitoria opt-in |
| [enterprise_connector_fixture.py](../../services/ai-service/tests/enterprise_connector_fixture.py) | Solo tests: reloj, fábrica de identidad y registros/documentos ficticios |
| [test_enterprise_connectors.py](../../services/ai-service/tests/test_enterprise_connectors.py) | Pruebas parametrizadas, bloqueador de red, fallos inyectados y concurrencia controlada |

El paquete usa exclusivamente biblioteca estándar y referencias relativas a sus propios módulos. No añade dependencias ni importa OAuth, FastAPI, HTTP clients, LangGraph, modelos, SQLite o SDKs cloud. Las interfaces `IdentityBoundary`, `AuditSink`, `CredentialBroker` y `DocumentAdapter` son internas: reemplazarlas requiere otra TASK y pruebas, no basta con conectar un SDK.

## Modelos e interfaz de ejecución

Se implementan `ConnectorDefinition`, `ConnectorInstance`, `TenantConnectorBinding`, `ExternalResourceGrant`, `ConnectorPrincipalGrant`, `CredentialReference`, `ConnectorAccessDecision`, `ConnectorOperation`, `QualifiedExternalResource`, `ConnectorExecutionContext` y `ConnectorAuditEvent`. Complementos: `RegisteredPrincipal`, `PolicySnapshot`, `ExecutionLimits`, `OperationRequest`, `UntrustedDocument` y `OperationResult`.

Las filas son inmutables, las colecciones de política son tuples/frozensets y los identificadores registrados están acotados. Cada snapshot tiene revisión positiva; entidades relevantes tienen versión. Los recursos incluyen organización, instancia, proveedor/cloud, tenant, tipo, ID externo, padre, clasificación y versión. Los mismos IDs externos en ámbitos distintos no equivalen al mismo recurso. Nombres visibles, paths, URLs o texto del documento no seleccionan identidad, tenant o credencial.

Interfaz preparada para consumo interno futuro: `ConnectorService.execute(context, OperationRequest(...), gate=Gate.READ)`. El request contiene instancia/recurso registrados, operación explícita, propósito, destinatario y revisión esperada; no acepta principal/organización/permisos como tool arguments. La instancia se resuelve por ID en el snapshot confiable. Diccionarios, prompts y JSON no se deserializan como identidad o solicitudes autoritativas.

`OperationResult` devuelve status, razón cerrada, correlation ID nuevo del servidor, estados local/externo/entrega y documentos solo si B permite. Cada documento tiene referencia interna, organización/instancia, versión y etiqueta `untrusted_enterprise_document`; texto excluido de repr. No devuelve contextos IAM, decisiones reutilizables, CredentialReference, tokens, URLs o excepciones internas. `EXTERNAL_SUCCESS` observado no significa que su auditoría haya persistido ni que el contenido se haya entregado. Un cache hit no se etiqueta como nueva ejecución externa.

Resolución/procedencia registradas son locales y no llaman al broker/adaptador. Metadatos no entregan contenido del documento. Enumerar exige una carpeta; cada resultado se reautoriza como metadato en A y B y se verifica su padre, sin contenido ni acceso implícito a padre/hermano. B sobre la carpeta no concede B para todos sus hijos. La lectura de contenido exige recurso de tipo documento.

## Frontera de identidad exclusivamente de test

`TestIdentityFactory` vive en tests, no en `app`. Construye un análogo mínimo de PrincipalContext previamente verificado, sin JWT ni credenciales. La interfaz interna reconoce únicamente el objeto exacto emitido por esa fábrica; una copia igual, JSON, roles/groups, claims, prompt o ID conocido no es prueba de identidad. Además se verifica registro activo, organización, tipo workload, audiencia, versión de contexto y vigencia.

Esta es una **simulación de la frontera**, no autenticación criptográfica ni una segunda implementación OAuth. No consume `WorkloadBoundary` ni modifica Trusted Identity Registry. TASK 003 debe definir administración/custodia; la futura TASK 005 necesita una frontera realmente autenticada y autorizada y un envelope confiable. Identidad de objetos Python, campos frozen y RLock no aíslan frente a código malicioso dentro del mismo proceso/host. No hay adaptador humano: delegated se representa pero se deniega hasta binding humano autorizado en TASK 006. El endpoint IAM actual no autentica este módulo ni cualquier grafo.

## Datos y matriz organizacional

Todos los textos, actores y recursos son inventados. `ORG-A` y `ORG-B` tienen principal, instancia, tenant, cliente, service principal, referencia y grants independientes. Las carpetas raíces contienen tres documentos cada una:

| Ámbito | Documentos | Permiso inicial |
|---|---|---|
| ORG-A / instance-a / tenant-a | Manual de vacaciones, política de seguridad, procedimiento de compras | principal-a, propósito synthetic-demonstration, recipient-a, subtree root-a |
| ORG-B / instance-b / tenant-b | Manual de vacaciones, política de seguridad, documento confidencial ficticio | principal-b, mismo propósito, recipient-b, subtree root-b |
| Recurso outside de cada organización | Referencia registrada fuera del subtree | Denegado |
| ORG-A → recursos/instancia de B y viceversa | IDs conocidos o externos idénticos | Denegado antes del broker/adaptador |
| Tenant sintético compartido | Instancias, grants y credenciales organizacionales separados | Lectura propia permitida; cruce de organización denegado |
| B2B, remoteItem y shared links | Marcadores sintéticos de recurso | Deshabilitados |

Los IDs externos de documentos equivalentes se repiten deliberadamente entre organizaciones. La prueba de tenant compartido cambia bindings/recursos/referencias de forma explícita antes de operar, sin asumir que compartir tenant une permisos.

## Política, grants y límites

La política exige contexto válido; principal registrado y tipo permitido; organización; definición/instancia activas; operación soportada; recurso propio registrado; scope exact/subtree; grant completo del principal y grant externo local vigentes; binding exacto de proveedor/cloud/tenant/instancia/app/service principal/modo; referencia compatible; clasificación, propósito y destinatario; revisión actual; presupuestos válidos y capacidad concurrente disponible. Ningún rol/group externo crea grants. No unir operaciones, destinatarios o recursos de grants parciales.

Una decisión local solo se emite después de persistir el evento previo en memoria. Se reevalúa antes de adquirir, leer cada página/reintento y entregar. Fallo local produce DENY/UNAVAILABLE, **cero intentos de broker y cero lecturas simuladas**. Auditoría previa caída también produce cero efectos. Credencial/referencia inválida conocida en política se rechaza antes del broker; indisponibilidad sobrevenida del broker puede producir un intento autorizado, nunca una lectura ni fallback.

Scope exact/subtree verifica la cadena registrada completa, hasta 16 niveles, incluso después de encontrar la raíz autorizada. Rechaza ciclos, padres ausentes, padres no carpeta y parentesco entre ámbitos distintos. Alcanzar el scope no transforma una ascendencia inválida en válida. No descubre recursos globalmente. Revisión de request debe ser entero canónico y coincidir con el snapshot; no se actualiza automáticamente para recuperar una solicitud vieja.

Valores **solo de laboratorio**, no límites Graph ni recomendaciones productivas:

| Presupuesto | Valor inicial |
|---|---|
| Páginas / ítems | 3 / 8 |
| Bytes UTF-8 acumulados | 1024 |
| Intentos totales por operación, incluidos reintentos/páginas | 3 |
| Tiempo con reloj inyectado | 5 segundos |
| Operaciones concurrentes por organización/instancia | 2 |
| MIME / contenido activo / comprimido | text/plain; activo y comprimido rechazados sin ejecutar/descomprimir |
| Caché | Deshabilitada por defecto; opt-in de 0–8 entradas, vencimiento máximo de 5 segundos y nunca posterior a contexto/grants/credencial |

## Broker, adaptador y autoridad externa simulada

El broker consume por identidad una decisión interna emitida por el ledger, de un solo uso, aún vigente y de revisión actual. Revalida política, simula disponibilidad/expiración/revocación y entrega al adaptador un objeto transitorio sin secreto. El adaptador rechaza objetos copiados/forjados; el uso se libera al terminar, también en fallos. Contadores `attempts` y `acquisitions` distinguen intentos autorizados y adquisiciones satisfactorias. `adapter.calls` identifica organización/instancia/recurso/cursor de cada intento simulado.

El proveedor posee permisos independientes del grant local. Puede devolver 200, 401, 403, 404, 429, 5xx o timeout simulado. Un permiso externo no suple un grant local; LOCAL_ALLOW no garantiza éxito externo. 401/403 no se reintentan con otra identidad/perfil; 429/5xx/timeouts tienen intentos acotados sin sleeps ni cambio de credencial. No se simula backoff real ni Retry-After operacional.

Solo se admiten cursores enteros secuenciales y páginas acotadas, nunca nextLink/Location suministrado como URL ejecutable. URLs maliciosas, redirecciones a otro origen o infraestructura interna, MIME no aprobado, flags activo/comprimido y exceso de tamaño/ítems/tiempo se rechazan. No existe cliente HTTP, DNS, descarga, extractor, compresor ni motor de herramientas en este fixture: estas negativas prueban la política sintética, no hardening de transporte real.

## Auditoría obligatoria y fallos

Sink separado en memoria; contrato semántico `connector-security-audit-v1`, sin cambiar stores/allowlists IAM, Federation o Security Audit. Fases: `local_authorization`, `external_execution`, `delivery`, `grant_administration`. Outcomes y motivos son enums cerrados, con UUID/UTC, revisión y referencias propias resueltas; entradas desconocidas/ajenas no se copian al evento.

Secuencia positiva: LOCAL_ALLOW auditado → adquisición → EXTERNAL_SUCCESS auditado → evaluación B/local/externa simulada del recurso y cada hijo → DELIVERY_ALLOWED auditado → misma revalidación completa → resultado. El último evento representa **decisión de entrega**, no confirmación de recepción por red. Una revocación detectada después de esa decisión deja además una denegación/supresión, sin devolver contenido. El correlation ID es estable por operación, no correlación global distribuida. Eventos no contienen documentos, prompts, URLs, contextos completos, credenciales ni texto del atacante.

Fallo de auditoría previo: cero broker/adaptador. Fallo del sink de resultado o de entrega: resultado sin contenido y UNAVAILABLE; no se inventa una escritura persistida. La auditoría puede contener una decisión previa que luego no termina en entrega; las fases no deben confundirse. No hay durabilidad, integridad antimanipulación, protección frente a administrador de host, atomicidad distribuida ni operación SIEM.

## Revocación, concurrencia y caché

Cada mutación de test usa compare-and-swap sobre revisión, construye un nuevo snapshot, audita el cambio y publica bajo RLock. Fallo del sink de cambios deja el snapshot anterior; CAS viejo no sobrescribe la revocación. No es una API de administración autenticada: el operador se mantiene sin atribución humana corporativa, sin rutas y solo mediante composición de test.

Nuevas decisiones posteriores a retiro confirmado deniegan; restaurar requiere mutación explícita nueva. Instancia/binding deshabilitados, permiso/contexto/referencia vencidos, recurso movido o revisión cambiada se rechazan. Hooks tras la lectura y Events/ThreadPoolExecutor controlan carreras sin sleeps: una primera lectura ya realizada no se deshace, pero su entrega se suprime; una segunda petición posterior al retiro no adquiere ni lee. Otra prueba satura el límite concurrente sin adquirir para la segunda solicitud.

Caché opt-in únicamente transitoria: separada por principal, organización, instancia, recurso/versiones, operación, propósito, destinatario y revisión. No cachea ALLOW; reevalúa A/B en cada uso y vacía entradas al detectar revisión nueva. `authorize_delivery` verifica bajo un único lock el conjunto del recurso y todos los hijos frente al estado independiente **actual del proveedor simulado**, sin nueva lectura ni adquisición. Se aplica tanto a datos recién leídos como a cache hits, antes y después de la auditoría de entrega. El retiro externo simulado suprime entrega aunque la revisión local no cambie. Resolución/procedencia local no requieren esa consulta externa. La sección final mantiene el lock de política local; la garantía es hasta las últimas comprobaciones, no cancelación retroactiva ni revocación después de ellas. No es Gate D ni índice persistente. Esto no demuestra reconsulta ACL Microsoft, revocación distribuida, eliminación segura de memoria ni atomicidad con un proveedor real; el transporte y la política de frescura reales necesitan contrato/evidencia propios. No hay caché habilitada en producto.

## Gates A/B/C/D y contenido hostil

- A implementa lectura mediante el proveedor simulado; no concede B/C/D.
- B revalida destinatario y política y permite entrega sintética explícita. A puede tener éxito y B denegar sin devolver contenido.
- C se deniega incluso si la configuración intenta incluir ese gate. No hay procesador IA ni llamadas LLM.
- D permanece deshabilitado incluso ante un grant aparente. No hay almacenamiento de documentos/derivados en disco, embeddings, índices o checkpoints.

La política de seguridad sintética incluye instrucciones hostiles para cambiar organización, usar credenciales administrativas, enviar a servidor externo, activar otra herramienta o indexar todo. Solo se devuelve como `untrusted_enterprise_document` cuando A/B permiten: no se interpreta, no muta el snapshot ni genera llamadas adicionales. Esto no prueba defensa de un LLM real ni de una futura herramienta LangGraph, todavía inexistentes. No se usa un clasificador LLM como autoridad.

## Ejecución y resultados

Desde `services/ai-service`, usar el venv existente, sin instalar dependencias ni iniciar servicios:

```powershell
.\.venv\Scripts\python.exe -m compileall -q app/enterprise_connectors tests/enterprise_connector_fixture.py tests/test_enterprise_connectors.py
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_enterprise_connectors.py
```

Resultado actual: **145 pruebas nuevas aprobadas**. Los tests nuevos bloquean socket connect/connect_ex/create_connection/getaddrinfo y fallan si se intenta red, aunque la excepción fuese capturada. Análisis AST verifica imports estándar/locales y ausencia de primitivas de ejecución/escritura/rutas HTTP. No hay integración de producto activada.

Regresiones seleccionadas: `test_oidc_workload.py`, `test_trusted_identity_registry.py`, `test_service_auth.py`, `test_security_audit.py`, `test_workflow_security_audit.py`, `test_human_review_security_audit.py`: **175 aprobadas**, con un DeprecationWarning de Starlette/AnyIO existente. Selección por fronteras IAM, grants/revocación, autenticación legacy, auditoría y Human Review; usan dobles/ASGI y SQLite temporales propios, no HAPI/IdP/cloud. No se ejecutó indiscriminadamente la suite completa ni las tres pruebas históricas de hashes CRLF. No se corrigieron sus migraciones ni ACL.

Comando reproducible para esas regresiones offline seleccionadas, desde el mismo directorio:

```powershell
$taskTempRoot = (Resolve-Path '..\..\infra\iam-lab\.runtime').Path
$taskTestBase = Join-Path $taskTempRoot ('eca2-regressions-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $taskTestBase) { throw 'Usar una carpeta temporal nueva' }
$taskSuites = @('tests/test_oidc_workload.py', 'tests/test_trusted_identity_registry.py', 'tests/test_service_auth.py', 'tests/test_security_audit.py', 'tests/test_workflow_security_audit.py', 'tests/test_human_review_security_audit.py')
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $taskTestBase @taskSuites
```

Para repetir esas regresiones, proporcionar un `--basetemp` absoluto nuevo y test-owned fuera de `.pytest-tmp`; nunca usar una carpeta preexistente ajena. La validación actual usa una carpeta única bajo `infra/iam-lab/.runtime/` y bloquea conexiones externas durante la repetición. Git usa red únicamente para `fetch origin`; no se hicieron llamadas cloud/Microsoft. Total seleccionado: **320 pruebas**. Estos resultados no sustituyen evidencia operacional Graph.

Una repetición auxiliar con bloqueo indiscriminado de sockets se interrumpió porque también impedía `socket._fallback_socketpair` de Python/Windows, usado internamente por asyncio/TestClient. No fue evidencia de un defecto productivo ni de una conexión HAPI. El guard corregido permite solo ese call stack de biblioteca estándar hacia su par efímero de loopback y sigue bloqueando connect/create_connection/getaddrinfo externos. La repetición corregida comprobó cero intentos externos; el fixture nuevo conserva bloqueo total de sockets. No se modificó código existente para adaptar ese harness.

Durante refinamiento apareció una regresión nueva: se estaba aplicando la operación CHILDREN a documentos hijo al revalidar una enumeración. Se corrigió usando evaluación METADATA de cada hijo, manteniendo el requisito de carpeta para la solicitud original. La revisión posterior también hizo explícita la evaluación B por hijo, tanto en lectura como caché: permiso de entrega sobre la carpeta no autoriza automáticamente sus ítems. La suite final cubre ambos casos; no fueron fallos preexistentes de producto.

### Revisión final de seguridad autorizada

La evidencia inicial aceptada por el PO fue 134 pruebas del fixture y 175 regresiones (309 total). Las 134 pruebas originales del fixture se volvieron a ejecutar antes de corregir; las regresiones se repiten después de los ajustes. Se añadieron once casos, incluidos los parámetros nuevos, y se reprodujeron diez fallos que demostraron dos brechas acotadas:

- `in_scope` devolvía ALLOW al encontrar la raíz del grant, sin detectar un ciclo, padre inexistente o cruce de organización por encima de esa raíz. Ahora la ascendencia completa debe ser válida antes de admitir el scope; el rechazo ocurre sin broker/adaptador.
- La autorización externa por hijo se comprobaba en cache hits, pero no en listados frescos; además, después de la auditoría de entrega se revalidaba solo la política local del recurso principal. Ahora `_validate_delivery` reevalúa B para recurso/hijos y `authorize_delivery` comprueba los permisos externos sintéticos del conjunto antes y después de esa auditoría. Se prueban retiros antes de leer, después de leer y durante la auditoría, también desde caché.

La prueba de revocación local se amplió a una mutación confirmada durante la auditoría de entrega: la última revalidación suprime el contenido. Los diez casos que inicialmente fallaron pasan tras la corrección, junto con el resto. No se cambió ADR-097, contratos TASK 001, autenticación, servicios ni infraestructura. Las clasificaciones T01–T24 no se elevan: los controles adicionales siguen siendo sintéticos.

## Threat traceability T01–T24

Funciones referidas pertenecen a [test_enterprise_connectors.py](../../services/ai-service/tests/test_enterprise_connectors.py); sus parametrizaciones forman parte de las 145 pruebas aprobadas. **PASS significa únicamente el control sintético descrito**, no amenaza resuelta en producción. PARTIAL incluye prueba positiva de una parte y limitación explícita. NOT IMPLEMENTED no se transforma en PASS porque falte una capacidad.

| Threat | Control del fixture | Test | Evidencia / límite | Status |
|---|---|---|---|---|
| T01 | Ámbitos exactos, IDs cualificados, caché separada | `test_cross_organization_resource_and_instance`, `test_identical_external_ids_do_not_cross_org_even_in_shared_tenant`, `test_cached_delivery_has_finite_expiry_and_org_partition` | Cruces denegados; cero efectos para rechazo local; cada resultado conserva su organización | PASS |
| T02 | Contexto emitido por frontera de test, ledger de un uso | `test_equal_but_forged_context_is_not_boundary_identity`, `test_decision_replay_and_forgery_rejected` | Copia/contexto/decisión/uso forjados rechazados; no aislamiento de host | PASS |
| T03 | JSON/claims/roles/groups no crean grants | `test_json_claims_prompts_and_tool_arguments_are_not_identity`, `test_no_union_of_incomplete_principal_grants` | Cero adquisiciones/lecturas; no JWT nuevo ni mapeo de roles | PASS |
| T04 | No hay tokens reales ni vault | `test_new_package_has_no_network_llm_http_routes_or_production_imports` | Control de robo/replay de token Graph y host no implementado | NOT IMPLEMENTED |
| T05 | No hay refresh/delegated | `test_local_invariants_deny_before_broker_or_adapter` | Delegated se deniega; custodia/robo/rotación de refresh no implementados | NOT IMPLEMENTED |
| T06 | Binding exacto de tenant/client/service principal/cloud | `test_local_invariants_deny_before_broker_or_adapter`, `test_request_fields_are_candidates_not_authority` | Sustituciones de bindings/recursos sin broker/adaptador | PASS |
| T07 | Revalidación por recurso, padre y revisión | `test_in_flight_changes_suppress_delivery`, `test_listing_reauthorizes_every_child_and_never_leaks_foreign_results` | Move/version y resultados ajenos suprimen entrega | PASS |
| T08 | Exact/subtree explícitos, ascendencia válida y sin B implícito sobre hijos | `test_exact_subtree_parent_sibling_and_child`, `test_scope_root_does_not_hide_invalid_ancestry`, `test_gate_b_on_folder_does_not_deliver_children_without_their_own_gate_b` | Cadena completa comprobada aun al alcanzar la raíz del grant; ACL/herencia real SharePoint no validada | PARTIAL |
| T09 | Perfil externo fijo y sin ampliación por error | `test_external_profile_is_checked_independently`, `test_external_failures_are_not_local_allow_success` | Sin consentimiento real ni inventario de permisos Selected/All coexistentes | PARTIAL |
| T10 | Worker sin operaciones admin/share/índice, límites | `test_read_cannot_ai_index_share_or_exfiltrate`, `test_concurrent_budget_denies_second_read_without_another_acquisition` | No permisos reales app-only ni aislamiento de host comprometido | PARTIAL |
| T11 | Sin linking/consent/callback humano | `test_trusted_but_invalid_context_still_denied` | Phishing, PKCE y binding humano Entra no implementados | NOT IMPLEMENTED |
| T12 | CAS, revocación local, rechecks y TTL de caché | `test_controlled_concurrency_revocation_between_two_requests`, `test_revocation_between_pages`, `test_revocation_restore_and_stale_request` | Nuevos efectos locales bloqueados; lectura anterior no deshecha; ventana de proveedor real no validada | PARTIAL |
| T13 | Permiso externo simulado independiente por recurso/hijo, antes/después de audit | `test_fresh_delivery_rechecks_each_child_external_permission`, `test_cached_delivery_rechecks_external_permission_after_delivery_audit`, `test_missing_local_external_grant_despite_external_permission` | Retiro simulado suprime entrega fresca/cacheada sin nuevas adquisiciones; no ACL/consent Microsoft real | PARTIAL |
| T14 | No fallback de organización/modo/perfil | `test_broker_failure_never_falls_back`, `test_external_failures_are_not_local_allow_success` | Una adquisición como máximo; 401/403 no escalan ni reintentan | PASS |
| T15 | Bytes/páginas/ítems/tiempo/intentos/concurrencia acotados | `test_bounded_pagination_and_infinite_continuation`, `test_synthetic_transport_and_content_limits`, `test_time_budget_uses_clock_not_sleep` | Presupuestos sintéticos verificados; no cuotas Microsoft/backoff real ni control de avalancha productivo | PARTIAL |
| T16 | URLs/redirects/nextLink nunca ejecutados; red prohibida | `test_synthetic_transport_and_content_limits`, `test_new_package_has_no_network_llm_http_routes_or_production_imports` | Negativas sintéticas; sin DNS rebinding/TLS/egress/descarga reales | PARTIAL |
| T17 | B2B/shared_link/remoteItem deshabilitados | `test_local_invariants_deny_before_broker_or_adapter`, `test_request_fields_are_candidates_not_authority` | Marcadores/URLs denegados sin resolver enlaces | PASS |
| T18 | Documento es dato, no operación ni autoridad | `test_hostile_document_is_data_and_never_activates_tools` | Snapshot idéntico y una sola lectura; no LLM/tool real probado | PASS |
| T19 | Gate C y destinatarios no autorizados denegados | `test_gates_are_independent_and_c_d_disabled`, `test_c_d_disabled_even_if_configuration_attempts_to_grant_them` | Cero salida a modelo/destino; no motor de egress real | PASS |
| T20 | Gate D deshabilitado, formatos/tamaño rechazados | `test_read_cannot_ai_index_share_or_exfiltrate`, `test_synthetic_transport_and_content_limits` | Sin embeddings/índice; extractor aislado/antimalware no implementados | PARTIAL |
| T21 | Caché segregada, B reautorizado, listado filtrado | `test_cached_result_is_reauthorized_and_never_cache_allow`, `test_listing_reauthorizes_every_child_and_never_leaks_foreign_results` | Sin resultados cross-org en fixture; no RAG, chunks o generador de citas implementados | PARTIAL |
| T22 | Auditoría previa/externa/entrega fail-closed | `test_mandatory_audit_fail_closed_no_fabricated_events`, `test_policy_change_failure_is_atomic_and_snapshot_is_immutable` | Sin entregas ante fallo; no durabilidad/tamper evidence/atomicidad Graph | PARTIAL |
| T23 | Campos cerrados, refs propias, sin cuerpos/URLs/contextos | `test_unknown_attacker_text_never_reaches_audit`, `test_hostile_document_is_data_and_never_activates_tools` | Sanitización del fixture; SDK/tracing/secret management real no implementados | PARTIAL |
| T24 | Mutaciones de test CAS y auditadas, sin API de administración | `test_snapshot_compare_and_swap_rejects_lost_update`, `test_policy_change_failure_is_atomic_and_snapshot_is_immutable` | No administrador corporativo autenticado ni protección contra host comprometido | PARTIAL |

## Preparación para TASK 003 y cierre propuesto

Aceptación alcanzada para el fixture: acceso propio A/B, cruces/forjas/grants parciales denegados antes de efectos, autoridad externa separada, auditoría fail-closed, retiro/restauración y carreras deterministas, C/D deshabilitados y ausencia de wiring/red/dependencias nuevas. El PO acepta TASK 002 **solo para laboratorio sintético** y autoriza commit/push de las trece rutas tras revisión final satisfactoria. No se ejecutó TASK 003; PR/merge requieren decisión separada.

TASK 003 requiere alcance propio para onboarding/administración autenticada, persistencia y lifecycle aditivos, custodia aprobada, versiones de contratos, retención/recuperación y separación de operadores/workers. Cualquier entorno Microsoft necesita tenant y recursos test-owned autorizados, consentimiento mínimo y validación del perfil Graph por método/cuenta. Resolver política de frescura/revocación externa antes de habilitar caché real. Delegated permanece en TASK 006; LangGraph productivo en TASK 005. Aislamiento de procesos/host, vault, infraestructura cloud, IAM empresarial, RAG/MCP y producción siguen pendientes, no certificados por estas pruebas.
