# Enterprise Connector Control Plane V1 — TASK 003

Implementación **aceptada funcionalmente por el Product Owner exclusivamente para laboratorio**. La revisión final autoriza corregir defectos bloqueantes reproducidos y staging/commit/push de las catorce rutas propias tras validar; no PR, merge ni TASK 004. TASK 002 está integrada mediante PR #110; su motor, modelos y límites se reutilizan, no se reemplaza el modo en memoria.

Este contrato de almacenamiento/control plane `enterprise-connector-control-plane-v1` es aditivo dentro del alcance autorizado. No cambia [ADR-097](../adr/ADR-097-enterprise-connector-authorization-boundaries.md), [autorización local](../contracts/enterprise-connector-authorization-v1.md), [perfil Graph](../contracts/microsoft-graph-connector-permissions-v1.md) ni auditorías IAM/clínicas. Contexto: [arquitectura](enterprise-connector-authorization-v1.md), [amenazas](enterprise-connector-threat-model-v1.md), [plan](enterprise-connector-authorization-implementation-plan-v1.md) y [fixture TASK 002](enterprise-connector-synthetic-fixture-v1.md). No hay Graph, Entra, vault, administración corporativa, documentos reales, LLM, RAG, MCP ni integración LangGraph productiva.

## Arquitectura e interfaces

| Componente | Responsabilidad |
|---|---|
| [control_types.py](../../services/ai-service/app/enterprise_connectors/control_types.py) | Contexto administrativo interno, estados, metadata de referencia y codec cerrado de los modelos existentes |
| [sqlite_store.py](../../services/ai-service/app/enterprise_connectors/sqlite_store.py) | SQLite dedicada, validación de ruta/esquema, conexiones acotadas, snapshots consistentes y guard transaccional de entrega |
| [control_plane.py](../../services/ai-service/app/enterprise_connectors/control_plane.py) | Inicialización explícita, administración sintética autorizada, onboarding, grants, aprobación, lifecycle, rotación y consultas minimizadas |
| [durable_audit.py](../../services/ai-service/app/enterprise_connectors/durable_audit.py) | Sink durable de decisiones de conector compatible con el puerto TASK 002 |
| [001_control_plane.sql](../../services/ai-service/app/enterprise_connectors/migrations/001_control_plane.sql) | Nueva migración propia; no usa ni modifica migraciones históricas |
| [fixture de tests](../../services/ai-service/tests/enterprise_connector_control_plane_fixture.py) | Autoridad administrativa y composición SQLite explícitas, solo tests |
| [suite TASK 003](../../services/ai-service/tests/test_enterprise_connector_control_plane.py) | Lifecycle, aislamiento, persistencia, fallos y carreras deterministas |

No hay nuevo proceso, servicio, endpoint, CLI, setting global ni auto-enablement. La composición interna opt-in requiere `SQLitePolicyStore(path, test_owned_root=..., clock=...)`, una `AdministrativeAuthority` explícita, `ControlPlane`, `SQLiteConnectorAudit` y los evaluadores/broker/adaptador TASK 002. No se adapta automáticamente una sesión, token o contexto IAM. La aplicación existente no importa ni configura este control plane.

Solo se añaden dos hooks mínimos al motor: `SyntheticPolicyStore.delivery_guard()` conserva el RLock de memoria y `ConnectorService` utiliza ese puerto para la entrega final. El store SQLite implementa el mismo puerto con una transacción propia. El modo original no abre bases y conserva sus 145 pruebas. El chequeo AST permite únicamente los imports estándar necesarios en los nuevos archivos; sigue prohibiendo red/SDK/modelos y primitivas de ejecución arbitraria.

## Persistencia y relaciones

Una sola base Enterprise dedicada contiene tablas de política y **dos auditorías distintas**. Compartir esta transacción local permite atomicidad de cambios; no comparte archivos ni tablas con Trusted Identity Registry, OIDC, Federation, Human Review, conocimiento o auditoría clínica.

| Tabla | Autoridad y restricciones |
|---|---|
| `eca_metadata` | Contrato, SHA-256 canónico de la migración y revisión global positiva |
| `eca_definition` | Definición existente, propietario organizacional, versión y payload de campos cerrados |
| `eca_principal` | Binding local mínimo de workload sintético; no directorio humano ni autenticación |
| `eca_instance` | Organización/definición, referencias de binding/credencial, estado, versión y versión aprobada |
| `eca_binding` | Un binding inicial por instancia, tenant/client/service principal/provider/cloud/application; FK organizacional |
| `eca_resource` | ID interno, organización/instancia, padre registrado, versión y recurso cualificado; FK de padre en el mismo ámbito |
| `eca_credential` | Referencia, binding, tipo/custodia sintéticos, revisión UTC, estado, versión y metadata sin material secreto |
| `eca_external_grant` | Recurso/instancia/organización, versión y grant externo local del modelo TASK 002 |
| `eca_principal_grant` | Mismo ámbito más principal propio; operaciones, gates A/B, clasificación, propósito y destinatario |
| `eca_admin_audit` | Actor sintético verificado o anónimo, operación, entidades, revisiones/versiones/estados, UUID/UTC y resultado |
| `eca_access_audit` | Autorización local, resultado externo simulado y decisión de entrega; actor workload/anónimo, refs mínimas |

Hay PK únicas, FKs compuestas organizacionales, constraints de estados/versiones/JSON y un índice único de revisión administrativa aceptada. Las relaciones instancia→binding/credencial son diferidas para permitir onboarding transaccional. Un DRAFT incompleto almacena referencias nulas; su proyección inactiva usa un marcador interno no autoritativo y nunca llega al broker. La activación exige referencias completas.

El payload JSON solo codifica dataclasses existentes: no es un blob de documentos ni identidad recibida del agente. Se rechazan campos desconocidos/duplicados y se reconstruyen enums, sets inmutables y fechas UTC. IDs/versiones/ámbito se cotejan con columnas relacionales. Definiciones pertenecen a una organización en SQL sin duplicar el modelo TASK 002. IDs externos repetidos y tenant compartido no fusionan organizaciones ni instancias.

## Inicialización y migraciones

`ControlPlane.initialize(context)` requiere autoridad sintética de administrador. Crea el archivo de forma exclusiva; nunca sobrescribe/adopta un archivo existente, vacío o ajeno. Aplica solo la nueva migración, metadata y evento de inicialización en una transacción. Un fallo puede dejar un archivo propio vacío/inutilizable; no se elimina ni reutiliza automáticamente.

`user_version=1`, application id propio, DDL completo esperado, checksum de migración, quick check, FKs y continuidad de auditorías/revisiones identifican el store. El checksum nuevo normaliza LF/CRLF; esto no altera ni corrige los tres tests históricos de hashes. Tabla/trigger extra, constraint distinta, metadata ausente, audit gap, versión incompatible o migración ausente provocan fallo cerrado. Las lecturas nunca migran ni crean una base ausente. No existe fallback a memoria ni a otro archivo.

Todos los valores se enlazan como parámetros SQL. Los nombres de tablas/columnas usados internamente proceden de allowlists fijas; no son entrada SQL libre. Los errores expuestos son motivos cerrados, sin SQL, rutas o excepciones SQLite originales.

## Frontera administrativa

`AdministrativeAuthority.recognizes(context)` es un puerto interno obligatorio, sin implementación corporativa. `AdministrativeTestAuthority` y su fábrica viven exclusivamente en tests. Solo reconocen los objetos exactos emitidos por su frontera sintética; una dataclass igual, JSON, prompt, roles JWT, argumentos de tool o contexto workload no son autoridad. Se comprueban registro de test, tipo/rol, organización, IDs y expiración UTC.

| Actor sintético | Facultades |
|---|---|
| Administrador | Onboarding, cambios de grants, aprobación/activación, lifecycle, rotación/offboarding y metadata propia |
| Operador | Metadata/auditoría propias y suspensión de instancia/credencial; no grants, aprobación, activación ni rotación |
| Workload lector | Ninguna facultad administrativa; solo data plane con contexto independiente y grants |
| No verificado/copia/JSON | Rechazado; no se copian sus campos a la auditoría |

Un operador verificado sin permiso queda atribuido como `synthetic_operator`, no como administrador ni identidad anónima inventada. Identidades no verificadas quedan anónimas. No se reutiliza el CLI IAM de operador no verificado. Esto no es RBAC empresarial, OAuth duplicado ni autenticación basada en objetos Python para producción.

`metadata` y `audit_events` consultan únicamente la organización autorizada, con columnas minimizadas. Conocer un ID de otra organización no permite leerlo o modificarlo. El store y sus conexiones son puertos internos de composición confiable, no herramientas entregables a agentes; no aíslan código malicioso dentro del mismo proceso.

## Onboarding y lifecycle de instancia

Operaciones internas explícitas: `register`, `create_instance`, `register_credential`, `transition`, `change_grant`, `transition_credential`, `rotate`, `metadata` y `audit_events`. Cada mutación exige revisión global esperada de tipo entero y autoridad adecuada.

Secuencia de test: definición/principal propios → instancia DRAFT → binding/recurso/grants/referencia PENDING → referencia ACTIVE → submit → approve → activate. Registrar un binding no lo consiente en Microsoft. El perfil externo de laboratorio es únicamente `synthetic-selected-read`, modalidad application; delegated, B2B, remoteItem y shared links continúan deshabilitados.

| Origen | Operación explícita | Destino/condición |
|---|---|---|
| DRAFT | submit | PENDING_APPROVAL |
| PENDING_APPROVAL | approve | Permanece pendiente; registra la versión aprobada tras comprobar completitud |
| PENDING_APPROVAL | activate | ACTIVE solo si aprobación corresponde a versión actual y la configuración sigue válida |
| ACTIVE | suspend | SUSPENDED; invalida aprobación previa |
| SUSPENDED | approve y luego activate | Revisión nueva y activación explícitas, sin recuperación automática |
| DRAFT/PENDING_APPROVAL/ACTIVE/SUSPENDED | revoke | REVOKED |
| REVOKED | offboard | OFFBOARDED, deshabilita bindings/recursos/grants/referencias relacionados |
| REVOKED/OFFBOARDED | activate/approve/submit | Rechazado; no reversión a activo |

Las transiciones no listadas se rechazan. Activar exige definición/binding/referencia válidos, grant completo del lector y grant externo local vigentes sobre recursos permitidos. Configuración cambiada antes de activar invalida aprobación. El binding inicial no puede reemplazarse silenciosamente ni cambiar tenant/modo; necesita otro onboarding autorizado. Offboarding conserva metadata mínima/tombstones y auditoría, no borra historia ni llama a un proveedor externo.

## Grants y referencias sintéticas

Registro y mutaciones comprueban organización, instancia, recurso, principal, modalidad, operaciones soportadas, fechas, scope y gates. Modificar un grant existente permite restricciones y retiro/restauración explícitos; no permite sustituir su ámbito/principal/modo ni ampliar sus operaciones. Para otro ámbito/capacidad se exige un nuevo grant revisado. No se restauran grants de instancias revocadas/offboarded, ni se unen grants parciales.

`CredentialMetadata` añade al `CredentialReference` existente binding, tipo literal `synthetic`, custodia no sensible con prefijo `synthetic-custody.`, revisión UTC y estado. Se cotejan tenant, app/client, service principal, proveedor/cloud, instancia, organización y modalidad. No admite campos de token, contraseña, client secret, certificado privado, API key o ciphertext recuperable.

| Estado de referencia | Transiciones admitidas |
|---|---|
| PENDING | ACTIVE, REVOKED o EXPIRED si venció |
| ACTIVE | SUSPENDED, REVOKED, EXPIRED si venció o rotación explícita |
| SUSPENDED | ACTIVE si vigente, REVOKED, EXPIRED si venció o rotación explícita |
| REVOKED/EXPIRED/REPLACED | Sin reactivación |

Rotar desde ACTIVE/SUSPENDED crea una referencia distinta con versión superior, marca la anterior REPLACED/deshabilitada y actualiza el puntero de instancia en la misma transacción. La auditoría enlaza referencias vieja/nueva mediante IDs internos, no valores de credencial. El retiro de instancias puede cerrar referencias relacionadas como REVOKED. Recuperar una referencia terminal no se implementa como toggle: requiere nuevo onboarding revisado, no fallback.

Expiración/revisión vencida deshabilita la proyección de acceso sin una escritura implícita; `expire_credential` registra explícitamente EXPIRED. El broker sigue siendo simulado, sin adquisición real ni acceso a Key Vault/Secrets Manager. Custodia, cifrado, rotación de claves reales y revocación Microsoft no están implementados.

## Auditoría administrativa atómica

`enterprise-connector-administration-audit-v1` usa vocabulario cerrado, UUID/UTC, actor sintético tipado, organización validada, operación y entidad propias, referencia relacionada cuando aplica, versiones/revisiones y estados anterior/nuevo, resultado y motivo controlado. No registra datos arbitrarios de solicitudes desconocidas.

Cada cambio aceptado y su auditoría se confirman con la nueva revisión dentro de **la misma transacción BEGIN IMMEDIATE**. Fallo tras escribir la entidad, al auditar o antes de commit provoca rollback completo; no se publica un `committed=true` antes del commit efectivo. CAS obsoleto no sobrescribe cambios. Denegaciones disponibles se registran separadamente sin incrementar la revisión de política; fallo de ese sink tampoco fabrica evidencia.

La continuidad de eventos aceptados debe coincidir con la revisión global. Esto detecta ciertas inconsistencias, no manipulación por el propietario del sistema. No es log inviolable, firma criptográfica, SIEM ni auditoría de producción.

## Auditoría de acceso y guard de entrega

`SQLiteConnectorAudit` conserva las fases/outcomes del contrato de conector: autorización local, resultado externo simulado y decisión de entrega, sin mezclarlas con cambios administrativos. La fase administrativa no se acepta en el sink de acceso. Actor workload/anónimo, IDs internos, operación, motivo, revisión y correlación son metadata mínima; no se guardan contexto IAM completo, documentos, tokens, URLs, prompts o cuerpos.

Auditoría previa fallida: cero broker/adaptador. Fallo externo/final: contenido suprimido. La sección de entrega SQLite mantiene una reserva de escritor y revalida recurso/hijos, permisos y vigencia antes/después de auditar. Auditoría final y su commit participan en esa sección; si el commit falla, no se devuelve contenido ni se inventa un evento persistido. Las fases previas ya confirmadas pueden permanecer como decisiones anteriores, no garantía de entrega.

No existe atomicidad distribuida SQLite/Graph. **No debe introducirse I/O de red dentro del guard**: hoy solo comprueba metadata y permisos del proveedor simulado. Un adaptador Graph posterior necesita su contrato de frescura/custodia/egress y nueva revisión; no basta con conectar un SDK a estas interfaces.

## Snapshots, revocación y concurrencia

Cada snapshot SQLite abre una transacción de lectura consistente y reconstruye `PolicySnapshot` con los modelos TASK 002. No se mezclan grants de revisiones distintas, ni se cachea autorización positiva persistente. Una nueva decisión cuyo snapshot empieza después de una revocación confirmada observa ese estado. La caché transitoria de TASK 002 vuelve a autorizar y se invalida por revisión; no hay contenido persistido.

Antes de adquisición, entre páginas/reintentos y antes de entregar se leen políticas actuales. Una rotación durante adquisición invalida la decisión vieja antes de leer; suspensión, retiro u offboarding durante lectura suprimen la entrega al detectarse. Una lectura ya realizada no se deshace.

La reserva de escritor del guard final ordena la última comprobación local con administradores de **instancias independientes del store sobre el mismo archivo**: un cambio confirmado antes del guard se ve; un escritor que llega durante el guard espera o falla con timeout acotado y no se considera confirmado. Administración reentrante no puede incorporarse a una transacción de data plane y anunciar un commit inexistente. El resultado queda autorizado en ese punto, no frente a cambios posteriores ni otros archivos/despliegues. No se promete revocación distribuida instantánea.

No hay conexión SQLite global entre threads. Las operaciones regulares usan conexión propia o la transacción explícita de entrega ligada al contexto; el pool admite hasta cuatro conexiones por instancia de store, adquisición acotada a 0,2 s y busy timeout de 100 ms. La inicialización exclusiva usa una conexión propia de setup y la verificación inicial del DDL una conexión transitoria en memoria, ambas cerradas al terminar. El snapshot admite hasta 1024 filas por tabla; exceso falla cerrado. Son límites de laboratorio, no sizing productivo. Events/barriers y reloj inyectado sincronizan tests, no sleeps arbitrarios.

## Rutas, recuperación y límites operacionales

Se exige ruta absoluta canónica `.sqlite3`, archivo directamente bajo el directorio test-owned explícito y rechazo de alias, symlinks/junctions, hard links y archivos prohibidos. Inicialización exclusiva y application id/esquema propios impiden adoptar una base IAM/clínica ajena. Deben proporcionarse también las rutas prohibidas relevantes al componer un entorno; no hay una configuración productiva automática.

El propietario del proceso/archivo sigue siendo confiable. No hay protección ante compromiso del host, cifrado de aplicación, modificación de ACL, backups/restauración, retención legal, HA o migración entre versiones operativa. La auditoría/metadata se conserva para este laboratorio; una política productiva de retención/borrado/recuperación queda pendiente. Datos corruptos, base ausente/bloqueada o incompatible producen UNAVAILABLE/fallo cerrado, sin políticas antiguas ni otro store como recuperación silenciosa.

## Gates y ausencia de capacidades externas

A/B continúan siendo lectura y entrega **sintéticas**. C sigue denegado y D permanece deshabilitado, incluso con persistencia habilitada. Persistir metadata y auditoría no concede almacenamiento de documentos/derivados. No hay embeddings, índices, checkpoints, nuevas herramientas LangGraph, RAG, MCP, HTTP ni Graph SDK. Los documentos hostiles siguen siendo datos y no obtienen facultades administrativas.

## Pruebas, ejecución y evidencia

Desde `services/ai-service`, con el venv existente y un `--basetemp` nuevo/test-owned, fuera de `.pytest-tmp`:

```powershell
$taskRoot = (Resolve-Path '..\..\infra\iam-lab\.runtime').Path
$taskBase = Join-Path $taskRoot ('eca3-tests-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $taskBase) { throw 'Directorio temporal ya existe' }
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $taskBase tests/test_enterprise_connector_control_plane.py tests/test_enterprise_connectors.py
.\.venv\Scripts\python.exe -m compileall -q app/enterprise_connectors tests/enterprise_connector_control_plane_fixture.py tests/test_enterprise_connector_control_plane.py
```

Evidencia inicial repetida antes de corregir: **73 pruebas nuevas y 320 regresiones aprobadas; una omitida**. La revisión final añadió dos negativas: resultado final **75 pruebas nuevas aprobadas y una omitida**, **145 TASK 002 aprobadas**, **175 regresiones aprobadas**; total seleccionado **395 aprobadas, una omitida**. Regresiones: `test_oidc_workload.py`, `test_trusted_identity_registry.py`, `test_service_auth.py`, `test_security_audit.py`, `test_workflow_security_audit.py` y `test_human_review_security_audit.py`. Seleccionadas por IAM, grants, autenticación legacy, auditorías y Human Review con dobles; no se ejecutó la suite completa que puede consultar HAPI ni los tres tests históricos CRLF.

Las suites nuevas bloquean sockets/DNS y verifican ausencia de intentos externos. La ejecución conjunta añade el guard ya documentado de Windows: permite exclusivamente `_fallback_socketpair` de biblioteca estándar hacia su par efímero interno para asyncio/TestClient; no habilita destinos externos. Se detectaron cero intentos externos. Se mantiene un DeprecationWarning de Starlette/AnyIO. No se instalaron dependencias ni arrancaron servicios.

La omisión corresponde a crear un symlink físico: Windows no concede el privilegio y no se modificaron ACL. La rama de rechazo se prueba además de forma determinista; hard links sí se verifican con archivo propio. Esto no equivale a validación completa de seguridad del filesystem de producción.

Durante desarrollo se corrigió el orden de consulta de eventos con reloj fijo: UUID aleatorio no define orden temporal; ahora se usa orden de inserción local. Se comprobó además rollback antes del commit final, rechazo de administración reentrante y checksum nuevo estable LF/CRLF. No se alteraron migraciones históricas ni controles para ocultar fallos.

### Revisión final de seguridad

Se reprodujeron dos fallos de contrato cerrado: rotación de referencias y reemplazo de grants aceptaban una subclase del modelo con campos adicionales y podían persistirlos mediante el codec genérico. No se utilizaron secretos: la reproducción incluyó únicamente un marcador sintético. Ahora la inserción de referencias y el reemplazo de grants exigen el tipo exacto registrado antes de serializar. `test_administrative_payload_subclasses_cannot_persist_extra_fields` verifica rechazo, snapshot sin cambios, ausencia del marcador en payloads/auditoría y continuidad de lectura legítima. Los dos casos fallaron antes y pasan después; no se amplió funcionalidad ni se alteraron contratos base.

El inventario publicable sigue siendo de catorce rutas: ocho nuevas y seis modificadas. El archivo adicional mostrado por la interfaz de edición es `infra/iam-lab/.runtime/eca3-baseline.json`, evidencia local de hashes creada para proteger el workspace, ignorada por Git y excluida del commit; no es un decimoquinto archivo de implementación.

## Trazabilidad T01–T24

Referencias a funciones de la [suite TASK 003](../../services/ai-service/tests/test_enterprise_connector_control_plane.py). PASS se limita al control sintético descrito. PARTIAL no se convierte en PASS por tener SQLite. La matriz base no se modifica.

| Threat | Control / test | Evidencia y límite | Status |
|---|---|---|---|
| T01 | FKs/scopes por organización; `test_org_a_cannot_read_or_mutate_org_b`, `test_shared_tenant_and_identical_external_ids_do_not_merge_organizations` | Lectura/mutación cruzada negadas, incluso con tenant compartido e IDs externos iguales; no SaaS productivo | PASS |
| T02 | Puerto administrativo separado; `test_non_administrator_cannot_create_grants_or_approve`, `test_unverified_admin_inputs_do_not_mutate` | Workload, copia y JSON no autorizan control plane; host/proceso no aislados | PASS |
| T03 | Grants explícitos y sin roles externos; `test_grant_modification_cannot_substitute_scope_or_add_unapproved_capability` | Scope/principal/modo/operación/indexación falsos rechazados; no nueva interpretación JWT | PASS |
| T04 | Solo referencias; `test_metadata_and_audit_contain_no_documents_contexts_or_secrets` | Robo/replay de token Graph y vault real no implementados | NOT IMPLEMENTED |
| T05 | Sin refresh/delegated; `test_rotation_cannot_change_credential_scope` | Lifecycle de metadata no implementa refresh token ni su custodia | NOT IMPLEMENTED |
| T06 | Binding inicial cerrado; `test_active_binding_cannot_be_silently_replaced`, `test_rotation_cannot_change_credential_scope` | Tenant/app/modo ajenos no sustituyen binding; sin onboarding Entra real | PASS |
| T07 | Revisión y recursos persistidos; `test_in_flight_change_from_independent_store_suppresses_delivery`, `test_sql_constraints_reject_cross_org_foreign_key` | Efectos fuera del snapshot vigente se suprimen; no recursos reales movidos | PASS |
| T08 | Scope/parentage TASK 002 más FKs; `test_grant_modification_cannot_substitute_scope_or_add_unapproved_capability` | Relaciones locales comprobadas; ACL/herencia SharePoint pendientes | PARTIAL |
| T09 | Perfil sintético fijo; `test_rotation_cannot_change_credential_scope` | No consentimiento Selected ni inventario efectivo Microsoft | PARTIAL |
| T10 | Reader separado del administrador; `test_non_administrator_cannot_create_grants_or_approve` | No permisos administrativos para lector; compromiso de host/app-only real pendiente | PARTIAL |
| T11 | No login/linking humano | Administración OIDC corporativa, PKCE y phishing no implementados | NOT IMPLEMENTED |
| T12 | CAS, snapshots nuevos y guard final; `test_new_reader_after_confirmed_revocation_never_acquires`, `test_final_delivery_transaction_orders_independent_writers` | Garantía local por archivo, no revocación distribuida ni cancelación retroactiva | PARTIAL |
| T13 | Revalidación local/externa simulada; `test_cache_reauthorizes_after_durable_revocation` | Cache no conserva autoridad local retirada; ACL Graph real no validada | PARTIAL |
| T14 | No fallback; `test_incompatible_or_corrupt_store_never_falls_back`, `test_rotation_during_acquisition_stops_old_reference_before_read` | Store incompatible/ref antigua no recuperan con memoria u otra credencial | PASS |
| T15 | Pool/timeout acotados; `test_connection_budget_is_bounded`, `test_locked_database_fails_closed_before_acquisition` | Presupuestos de laboratorio, no cuotas ni defensa DoS productiva | PARTIAL |
| T16 | No transporte; bloqueo de red en suites nuevas | Rechazo sintético heredado; sin TLS/egress/SSRF real | PARTIAL |
| T17 | Recursos/bindings fijos, sin remoteItem/B2B | Registro restringido y negativas heredadas TASK 002; no resolución de enlaces | PASS |
| T18 | Control plane no consume documentos ni prompts; `test_unverified_admin_inputs_do_not_mutate` | Datos hostiles no crean administrador; sin LLM/tool real | PASS |
| T19 | C denegado; `test_c_d_remain_disabled_with_sqlite` | Persistencia no autoriza modelo ni destino externo | PASS |
| T20 | D deshabilitado; `test_sqlite_never_stores_document_content`, `test_c_d_remain_disabled_with_sqlite` | No indexación ni documentos; extractor/antimalware real pendientes | PARTIAL |
| T21 | Snapshot coherente/cache reautorizada; `test_snapshot_is_consistent_and_does_not_merge_grants_across_revisions`, `test_cache_reauthorizes_after_durable_revocation` | Aislamiento local, no RAG/citas/retención empresarial implementados | PARTIAL |
| T22 | Cambios/audit atómicos; `test_admin_change_and_event_rollback_together`, `test_durable_access_audit_is_fail_closed`, `test_final_transaction_commit_failure_suppresses_content_and_rolls_back_event` | Durabilidad local y rollback, no tamper-proof ni atomicidad Graph | PARTIAL |
| T23 | Campos cerrados; `test_declined_admin_is_anonymous_without_attacker_text`, `test_metadata_and_audit_contain_no_documents_contexts_or_secrets` | Sin cuerpos/secretos en auditoría; no SDK/vault/tracing productivos | PARTIAL |
| T24 | Autoridad sintética, CAS y aprobaciones; `test_stale_admin_revision_and_two_concurrent_admins`, `test_approval_is_invalidated_by_pre_activation_configuration_change` | Cambios auditados por frontera de test; IAM/admin corporativo y protección de host pendientes | PARTIAL |

## Recomendación y dependencias de TASK 004

El PO acepta TASK 003 solo para laboratorio y autoriza commit/push de catorce rutas tras revisión final satisfactoria. PR y merge requieren decisión nueva; TASK 004 no se inicia por esta aceptación.

Antes de Graph real faltan autorización de tenant Microsoft y app/service principal test-owned, recursos SharePoint/OneDrive sintéticos, permisos mínimos aprobados y Selected por método/cuenta, administración autenticada y separación admin/worker, custodia empresarial aprobada, certificado/identidad de workload gestionados, retención/auditoría y recuperación, red/egress, seguridad de redirects/URLs preautenticadas y política de clasificación/descarga/entrega/frescura externa. Este control plane no satisface por sí solo esas condiciones; si faltan, TASK 004 no debe llamar Graph ni crear recursos Microsoft.
