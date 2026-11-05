# Microsoft Graph App-only Read Adapter V1 — Offline-First

Enterprise Connector Authorization V1 — TASK 004, implementación de protocolo **aceptada funcionalmente exclusivamente para laboratorio offline**. El PO autoriza revisión final y staging/commit/push de exactamente doce rutas tras validación satisfactoria; no PR, merge, validación Microsoft live ni TASK 005. TASK 003 está integrada por PR #111; verificar Git en vivo.

Autoridad: [ADR-097](../adr/ADR-097-enterprise-connector-authorization-boundaries.md), [contrato local](../contracts/enterprise-connector-authorization-v1.md), [perfil Microsoft](../contracts/microsoft-graph-connector-permissions-v1.md), [arquitectura](enterprise-connector-authorization-v1.md), [amenazas](enterprise-connector-threat-model-v1.md), [plan](enterprise-connector-authorization-implementation-plan-v1.md), [TASK 002](enterprise-connector-synthetic-fixture-v1.md) y [TASK 003](enterprise-connector-control-plane-v1.md). Se preservan sus contratos; las notas de autorización de etapas anteriores son históricas.

## Alcance y arquitectura

Módulo interno [providers/microsoft_graph](../../services/ai-service/app/enterprise_connectors/providers/microsoft_graph/), sin cliente HTTP, SDK, proceso, endpoint, setting global, OAuth, credenciales Microsoft o integración LangGraph. Los puertos solo tienen implementaciones de test. Ninguna variable de entorno habilita live.

| Archivo | Responsabilidad |
|---|---|
| [types.py](../../services/ai-service/app/enterprise_connectors/providers/microsoft_graph/types.py) | Identidad canónica, perfil Selected/read, catálogo explícito, solicitudes/respuestas, metadata/procedencia y puertos offline |
| [requests.py](../../services/ai-service/app/enterprise_connectors/providers/microsoft_graph/requests.py) | Rutas GET fijas, encoding de segmentos, continuación y política de descarga ficticia |
| [responses.py](../../services/ai-service/app/enterprise_connectors/providers/microsoft_graph/responses.py) | JSON cerrado, identidad/facetas, tamaño/MIME/etag, contenido UTF-8 y mapeo de errores |
| [adapter.py](../../services/ai-service/app/enterprise_connectors/providers/microsoft_graph/adapter.py) | Adaptador compatible con `ConnectorService`, presupuestos y revalidación mediante puertos inyectados |
| [fixture](../../services/ai-service/tests/enterprise_connector_graph_fixture.py) | Únicas implementaciones de transporte y autoridad no secreta; onboarding SQLite autorizado sintético |
| [suite](../../services/ai-service/tests/test_enterprise_connector_graph.py) | Negativas/positivas de protocolo, auditoría, aislamiento, límites y revocación sin sockets |

Se reutilizan `PolicyEvaluator`, `PolicySnapshot`, `DecisionLedger`, `SyntheticBroker`, `SyntheticPage`, grants, instancias, referencias y `SQLiteConnectorAudit`. No hay otro evaluador ni control plane. El servicio y todos los archivos existentes de TASK 002/003 permanecen sin cambios.

### Límite contractual de la composición

TASK 003 admite exclusivamente provider/cloud `synthetic-documents`/`synthetic`, perfil `synthetic-selected-read` y referencias sintéticas. No se amplían esas allowlists ni se escriben filas por fuera del onboarding para simular un binding Graph real.

`GraphCatalog` añade, desde composición confiable de test, el mapeo de registros sintéticos a identidades de protocolo Graph. Distingue explícitamente provider/cloud de protocolo (`microsoft-graph`/`global`) del namespace de política sintético. Se cotejan organización, instancia, tenant, ID externo, padre, tipo y versión con el snapshot; una entrada de catálogo no crea recurso ni grant. El catálogo no es una API de administración ni un almacén corporativo.

**Parte live detenida por contrato:** registrar namespaces Graph, perfiles externos reales, drive/site mappings administrados/versionados y custodia efectiva requerirá propuesta/aprobación contractual aditiva. Este catálogo de test no sustituye ese onboarding. No se implementó esa extensión ni se presenta metadata sintética como consentimiento o credencial Microsoft.

## Contratos y secuencia

Contexto confiable de test → política actual → auditoría local durable → ledger/broker sintéticos → constructor Graph → transporte de test → parser → resultado lógico auditado → revalidación local → Gate B → auditoría de entrega → revalidación final → resultado.

`GraphCredentialProvider` valida el uso emitido por el broker existente; la fábrica de `OfflineTransportAuthority` vive solo en tests. Es un objeto sin bearer, JWT, client secret ni representación utilizable por Microsoft. Mantiene ámbito organizacional/instancia/tenant/referencia y no autoriza administración. Release del broker descarta también estados de paginación y autoridades transitorias, incluso ante fallos.

Una lectura de contenido usa metadata de control del mismo recurso antes de `/content` para comprobar identidad, MIME, tamaño y etag. No descubre otros recursos ni devuelve esa respuesta Graph al solicitante. Los wire requests de una operación comparten un único presupuesto y uso de credencial; no se adquiere otra identidad ante un error.

`OperationResult` conserva su contrato: documentos minimizados, refs internas/versiones y etiqueta `untrusted_enterprise_document`, sin JSON Graph, títulos, URLs o credenciales. `GraphMetadata`/`GraphProvenance` son proyecciones internas verificadas por el parser; no se amplía silenciosamente el modelo de salida para exponer nuevos campos. `resource.resolve_registered` y `resource.provenance.read` siguen siendo operaciones locales del servicio.

## Identidad y perfil

Identidad de protocolo: organización, instancia, tenant de recurso, provider/cloud, site opcional según tipo empresarial, drive, item, padre, tipo y versión registrados. Etags esperados pertenecen al catálogo de test. IDs repetidos, incluso con tenant/drive compartidos, nunca eliminan el namespace local de organización/instancia.

El perfil admite solo Graph v1.0/global, application, rol read y los cuatro Selected documentados. No acepta personal, beta, delegated, permisos All ni los antiguos Files.Read.Selected. No hay búsqueda, `/me`, `/shares`, Embedded, writes, sharing, permisos administrativos o fallback.

Revisión documental pública de Microsoft Learn: **2026-11-05, America/Lima**. [Selected](https://learn.microsoft.com/en-us/graph/permissions-selected-overview) describe ámbitos y asignaciones; las tablas de métodos [metadata](https://learn.microsoft.com/en-us/graph/api/driveitem-get?view=graph-rest-1.0), [children](https://learn.microsoft.com/en-us/graph/api/driveitem-list-children?view=graph-rest-1.0) y [content](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0) no prueban cada combinación Selected/cuenta/tenant. La compatibilidad operacional sigue pendiente; no se añade un permiso amplio para resolver esa diferencia documental. Consultar Learn no fue una llamada a Graph ni un acceso a Microsoft 365.

## Request builder y metadata

Solo construye GET en `https://graph.microsoft.com/v1.0/drives/{drive-id}/items/{item-id}`, con sufijo `/children` o `/content` según operación. Los segmentos son identificadores registrados validados y codificados, nunca URLs, nombres, rutas de usuario o texto recuperado. Metadata/children usan `$select` fijo; no `$expand` ni descubrimiento.

El parser acota bytes antes de JSON, rechaza duplicados, constantes no finitas, tipos inválidos, campos extra y respuestas incompletas. Comprueba item, drive, site/tipo empresarial, padre esperado, file/folder mutuamente excluyentes, size entero, etag y text/plain. `name` es dato ignorado, no autoridad. remoteItem, campos de descarga, facets incompatibles y sustituciones no se adoptan ni provocan búsquedas alternativas.

Es un subconjunto cerrado deliberado: metadata live con campos, anotaciones o formatos distintos requiere revisión, no aceptación permisiva. Para el parentReference se conserva el modelo documentado de [itemReference](https://learn.microsoft.com/en-us/graph/api/resources/itemreference?view=graph-rest-1.0); no se infiere tenant desde un hostname o email.

## Children, paginación y nextLink

Se requiere carpeta registrada y cada hijo se resuelve solo en el snapshot organizacional correspondiente. El parser verifica identidad/padre; el servicio existente comprueba A por hijo y B antes/después de auditar la entrega. Enumerar no autoriza contenido, padres, hermanos o recursos desconocidos.

Cada continuación exige HTTPS, host exacto sin userinfo/puerto/fragmento y ruta exacta del drive/item/children autorizado. Solo se admite `$skiptoken` acotado y, opcionalmente, el mismo `$select` fijo; encoding canónico, sin parámetros adicionales o duplicados. Esta es una gramática offline conservadora, no aceptación universal de tokens opacos live. Se rechazan cambios de host/drive/item, tenant en query, URLs anidadas, codificación ambigua, loops y elementos repetidos entre páginas. Una continuación no puede cambiar la operación original.

El servicio reautoriza cada página/reintento; el proveedor simulado vuelve a validar el uso antes de cada wire request. Errores o límites nunca entregan una colección parcial como completa.

## Status, errores y presupuestos

| Respuesta simulada | Efecto |
|---|---|
| 200 | Solo éxito si parsing, identidad y límites permiten |
| 302 | Solo flujo de contenido y una descarga ficticia explícitamente aprobada |
| 304 | Sin reutilización implícita de contenido ni autorización cacheada; fallo cerrado |
| 400 | Solicitud/respuesta no admitida, sin recuperación privilegiada |
| 401/403/404 | Denegación externa sanitizada, sin nueva credencial, búsqueda o ampliación de scope |
| 408 / timeout | Categoría de timeout sintético compatible con reintentos acotados del servicio |
| 429 | Retry-After entero acotado; solo espera virtual inyectada y reautorización antes de reintentar |
| 500/502/503/504 | Intentos acotados del mismo perfil; sin sleeps reales |
| Otro status, cuerpo/headers inválidos o excepción | Fallo fijo, sin cuerpo/URL/stack trace público |

El [contrato de throttling Microsoft](https://learn.microsoft.com/en-us/graph/throttling) no fija nuestros presupuestos de laboratorio. Retry-After ausente, no soportado o fuera del tiempo restante cierra la operación. No se implementa scheduler productivo ni parsing universal de HTTP-date.

Se conservan los límites TASK 002 de 3 páginas, 8 ítems, 1024 bytes de texto, 3 intentos y 5 segundos; también su concurrencia. El adaptador cuenta **cada wire request**, incluidos metadata, content y descarga dentro de esos tres intentos. Añade un límite por body de `min(8192, max_bytes*8)`, total wire `min(32768, max_bytes*16)` y hasta 128 intercambios locales vivos; release los elimina. El tiempo usa el reloj inyectado. Headers duplicados/control characters, Content-Length incoherente y contenido comprimido se rechazan.

## 302 y URLs preautenticadas

Microsoft documenta [302 hacia una URL temporal que no necesita Authorization](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0). Es material sensible: no se devuelve, audita, registra ni entrega al modelo. No se copiaron URLs preautenticadas reales.

La descarga está deshabilitada por defecto. La política de test solo admite hosts exactos reservados `.invalid`, paths `/synthetic/...` y el marcador ficticio `ticket=synthetic-only`; rechaza hosts reales, direcciones IP, loopback, redes privadas, HTTP, userinfo, puertos, fragmentos y redirecciones encadenadas. El salto de descarga recibe `authorization=None`, nunca la autoridad Graph. Solo text/plain UTF-8, etag y longitud exactos; sin PDF/Office ni extractor complejo.

El transporte registra método/operación/refs internas/tipo de salto y si hubo autoridad, no targets ni headers sensibles. Solicitudes/respuestas excluyen sus valores de repr. No hay DNS, TLS, streaming o egress real que validar: estas negativas **no acreditan defensa operacional SSRF/DNS rebinding**.

## Auditoría, SQLite y revocación

Se reutiliza la base test-owned creada por `ControlPlane.initialize` y onboarding normal. No hay otra migración, tabla o auditoría IAM/clínica. Un resultado lógico del adaptador puede involucrar varios wire requests, pero el contrato de auditoría sigue registrando fases lógicas del conector; no se inventan eventos HTTP o Graph live.

Sink previo fallido: cero broker/transporte. Fallo de resultado/entrega: cero contenido. Correlación por operación, sin contexto completo, documentos, títulos, tokens, URLs o errores libres. Metadata/procedencia Graph no se persiste en esas tablas.

La revocación local, suspensión, offboarding y rotación detectados antes de la siguiente llamada impiden nuevas continuaciones/adquisiciones; después de leer suprimen entrega. Se conserva reautorización de caché y permiso externo independiente simulado, antes/después de audit. No se cancela retroactivamente una lectura ni se promete revocación distribuida.

**No hay I/O de red en el guard SQLite.** El port de entrega del fixture solo consulta su conjunto de permisos en memoria. Todos los `send` comprueban que no hay transacción SQLite activa. Un adaptador live no puede reemplazarlo con llamadas HTTP dentro del guard: necesitará un contrato propio de frescura/evidencia y diseño de entrega sin mantener reserva de escritor durante I/O externo.

## Gates y datos hostiles

A adquiere datos simulados; B autoriza entrega independientemente por recurso/hijo/destinatario. C permanece denegado y D deshabilitado. Los textos hostiles solo salen etiquetados como datos, sin activar herramientas, cambiar política, llamar LLM, generar embeddings, integrar RAG/MCP o almacenar contenido en SQLite/checkpoints. No hay tool LangGraph productiva ni TASK 005 iniciada.

## Pruebas y ejecución

Ejecutar desde `services/ai-service` con el venv existente, `-p no:cacheprovider` y un `--basetemp` nuevo, absoluto y test-owned bajo el runtime ignorado, fuera de `.pytest-tmp`. No instalar dependencias ni arrancar servicios.

```powershell
$taskBase = Join-Path (Resolve-Path '..\..\infra\iam-lab\.runtime').Path ('eca4-tests-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $taskBase) { throw 'Usar directorio temporal nuevo' }
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $taskBase tests/test_enterprise_connector_graph.py
.\.venv\Scripts\python.exe -m compileall -q app/enterprise_connectors/providers tests/enterprise_connector_graph_fixture.py tests/test_enterprise_connector_graph.py
```

La suite Graph bloquea crear sockets, DNS y create_connection, y verifica que no hubo intentos aunque se capturara una excepción. La selección conjunta añade el guard ya documentado de Windows: únicamente socketpair interno de biblioteca estándar para asyncio/TestClient; no permite destinos externos. La consulta pública de Learn y `git fetch origin` son actividades separadas de estas pruebas offline.

Primera ejecución del adaptador: 145 aprobadas y cero intentos externos. Se añadieron negativas de revisión y tres positivas separadas de forma `business` (metadata/children/content), sin inferir compatibilidad Microsoft desde ellas. **Resultado conjunto final: 553 aprobadas, una omitida y cero intentos externos**: 158 nuevas TASK 004, 75 TASK 003, 145 TASK 002 y 175 regresiones IAM/legacy/auditoría/Human Review seleccionadas. La repetición intermedia anterior a los cuatro últimos casos obtuvo 549 aprobadas y una omitida. El symlink físico Windows conserva su clasificación omitida cuando falta privilegio; no se cambia ACL. No se ejecuta la suite completa que consulta HAPI ni los tres hashes históricos CRLF.

Selección final, pasada a `pytest.main` por el harness con bloqueo de red, en este orden: `test_oidc_workload.py`, `test_trusted_identity_registry.py`, `test_service_auth.py`, `test_security_audit.py`, `test_workflow_security_audit.py`, `test_human_review_security_audit.py`, `test_enterprise_connector_graph.py`, `test_enterprise_connector_control_plane.py` y `test_enterprise_connectors.py`. Se usa un basetemp nuevo por ejecución. El guard registró 124 socketpairs internos de biblioteca estándar en las regresiones ASGI y ningún intento externo; la suite Graph prohíbe incluso crear sockets. Compileall, imports y chequeos AST aprobados.

### Hallazgos durante la revisión

- Un caso nuevo reprodujo un loop de cursor: alternar el `$select` fijo hacía parecer distinta una continuación con el mismo `$skiptoken`. Se corrigió la comparación semántica del token después de validar la URL completa; `test_graph_repeated_cursor_with_select_variant_is_still_a_loop` falló antes y pasa después, sin una tercera llamada ni entrega.
- La primera selección conjunta (Graph antes de IAM) terminó con 381 aprobadas, una omitida y un fallo OIDC preexistente dependiente de tiempo. `test_rejected_tokens_are_audited_without_identity_or_claims` calcula sus parámetros temporales al importar el módulo; después de más de tres minutos de pruebas Graph, `nbf=collection_time+60` ya no estaba en el futuro. Sus 12 casos pasan en proceso nuevo. No se cambió IAM ni el test; la repetición conjunta ejecuta primero las seis regresiones seleccionadas y luego Graph/TASK 003/TASK 002. El defecto de determinismo del test necesita alcance propio; cambiar el orden evita caducar su fixture, no relaja la validación de tokens. Se conservan también el DeprecationWarning Starlette/AnyIO y las limitaciones CRLF/ACL históricas.

### Revisión final autorizada para publicación

Se inspeccionaron código, contratos e integración; no aparecieron nuevos defectos bloqueantes y no se modificaron implementación ni tests durante esta revisión. Se repitieron los 12 casos OIDC en proceso nuevo y la selección conjunta IAM-first: **553 aprobadas, una omitida, cero intentos externos**; no se añadieron skip/xfail. La suite conserva dependencia del orden por la deuda OIDC anterior, no se declara independiente de él.

Cuatro comprobaciones adicionales con fixtures nuevos y bloqueo total de sockets/DNS pasaron, sin incorporarlas al conteo pytest: esquema SQLite incompatible impide broker/transporte; fallo del commit final revierte el evento de entrega y suprime contenido Graph; offboarding confirmado impide nuevas adquisiciones/solicitudes; invocar el adaptador dentro del guard SQLite rechaza el wire port. Solo se manipularon bases temporales propias, no stores existentes ni migraciones. Se revisaron también inventario de doce rutas, hashes protegidos, imports/AST, compileall, enlaces, secretos y ausencia de artefactos runtime en la publicación.

## Threat traceability T01–T24

Los nombres corresponden a la [suite nueva](../../services/ai-service/tests/test_enterprise_connector_graph.py), salvo evidencia heredada expresamente identificada. PASS significa solo el control local/offline descrito. No eleva a PASS productivo, certifica Selected o acredita custodia/infraestructura real. Se conservan 9 PASS de laboratorio, 12 PARTIAL y 3 NOT IMPLEMENTED.

| Threat | Evidencia nueva / heredada | Límite residual | Status |
|---|---|---|---|
| T01 | `test_graph_cross_org_identical_ids_and_shared_tenant_remain_separate` | Aislamiento de fixtures, no tenant Microsoft probado | PASS |
| T02 | `test_graph_decision_replay_and_copied_credential_use_are_rejected` | Ledger existente; proceso/host confiables | PASS |
| T03 | `test_graph_local_denial_has_no_credential_or_transport_effect` | Claims/JSON no crean grants; no IAM nuevo | PASS |
| T04 | `test_graph_wrong_credential_scope_cannot_be_onboarded` | Sin tokens/vault reales; robo/replay Microsoft no implementado | NOT IMPLEMENTED |
| T05 | Perfil app-only y referencia sintética heredada | Refresh/delegated/custodia no implementados | NOT IMPLEMENTED |
| T06 | `test_graph_tenant_mismatch_in_catalog_never_selects_a_credential` | Catálogo de test, no onboarding corporativo | PASS |
| T07 | `test_graph_metadata_substitution_or_contradiction_suppresses_output` | Identidad/versión offline; moves live pendientes | PASS |
| T08 | `test_graph_child_requires_its_own_gate_b`, `test_graph_foreign_child_response_is_not_adopted` | Parentage local y metadata, no ACL/herencia SharePoint live | PARTIAL |
| T09 | `test_graph_profile_never_broadens_scope_or_changes_mode` | Selected/read objetivo; consentimiento efectivo y permisos coexistentes pendientes | PARTIAL |
| T10 | `test_graph_catalog_presence_does_not_grant_access` | Worker sin grants automáticos; aislamiento real pendiente | PARTIAL |
| T11 | Sin login/linking/consentimiento | Administración corporativa/PKCE/consent phishing no implementados | NOT IMPLEMENTED |
| T12 | `test_graph_confirmed_concurrent_revoke_suppresses_inflight_and_new_read`, `test_graph_revocation_between_pages_stops_continuation` | Orden local y detección; sin SLA distribuido/retroactividad | PARTIAL |
| T13 | `test_graph_cached_result_rechecks_external_permission_without_new_read` | Permisos externos simulados, no frescura ACL real | PARTIAL |
| T14 | `test_graph_http_errors_are_sanitized_and_retries_bounded` | Sin fallback de credencial/modo; no proveedor live | PASS |
| T15 | `test_graph_retry_after_cannot_exceed_budget`, `test_graph_enumeration_never_crawls_or_adopts_resources` | Budgets offline; cuotas/scheduler/streaming reales pendientes | PARTIAL |
| T16 | `test_graph_nextlink_cannot_become_arbitrary_http`, `test_graph_302_invalid_destinations_are_never_requested` | Validación sintáctica y red bloqueada; no SSRF/DNS/TLS operacional | PARTIAL |
| T17 | `test_graph_offline_identity_is_not_live_onboarding` | Personal/remoteItem excluidos; sin resolución de links | PASS |
| T18 | `test_graph_hostile_text_never_changes_policy_or_activates_other_gates` | Texto no ejecutado; LLM/tool real no probado | PASS |
| T19 | `test_graph_hostile_text_never_changes_policy_or_activates_other_gates` | C denegado, sin motor de egress real | PASS |
| T20 | `test_graph_document_or_download_url_never_reaches_sqlite` | D deshabilitado; extractor/antimalware reales pendientes | PARTIAL |
| T21 | `test_graph_cached_result_rechecks_external_permission_without_new_read` | Caché local reautorizada; no ACL-RAG/citas empresariales | PARTIAL |
| T22 | `test_graph_durable_audit_is_mandatory`; rollback/commit heredados TASK 003 | Fail-closed local; no atomicidad Graph ni log inviolable | PARTIAL |
| T23 | `test_graph_content_302_has_no_authority_forwarding_or_url_output`, `test_graph_timeout_and_arbitrary_exception_do_not_leak` | Canaries sintéticos, sin SDK/vault/tracing live | PARTIAL |
| T24 | Onboarding, CAS, roles, aprobación y auditoría heredados TASK 003 | Control plane intacto; sin administrador corporativo | PARTIAL |

## Requisitos de validación live — no ejecutados

- Autorización nueva del PO, tenant Microsoft y entorno/suscripción cuando aplique; recursos sintéticos y propietario comprobados.
- App registration/service principal test-owned, responsable administrativo y separación administrador/lector.
- Extensión contractual aprobada de namespace/bindings/perfiles Graph, catálogo administrado/versionado y frontera administrativa autenticada; no reutilizar el catálogo de test como configuración productiva.
- Consentimiento, Selected mínimo y asignación read explícita; inventario de permisos amplios coexistentes y matriz por método/recurso/cuenta.
- Positivas propias y negativas de hermano/padre/tenant, sin inferir OneDrive for Business de SharePoint ni universalidad desde una sola lectura.
- Custodia aprobada de certificado/workload identity, adquisición OAuth, expiración, rotación y revocación; no pedir secretos en chat.
- Transporte real revisado por separado: egress, DNS/IP, TLS, redirects, URLs preautenticadas sin Bearer, streaming, MIME, extracción y límites.
- Auditoría, retención, recuperación y política de frescura/entrega sin HTTP dentro de una transacción SQLite.
- Clasificación de documentos, recursos de prueba, pruebas de retirada y plan de cleanup/offboarding por propiedad.

Ningún requisito anterior queda satisfecho por HTTP simulado. La activación no es un flag; faltan componentes/contratos/autoridad y no se provisionó nada. Tampoco habilita TASK 005: su frontera autenticada, envelope, reautorización asíncrona, modelos/destinos y pruebas de integración necesitan autorización independiente.

TASK 004 se acepta como adaptador de protocolo offline reutilizable, no como conector Microsoft operacional ni cierre de la EPIC. Commit/push de doce rutas autorizados tras revisión final satisfactoria; esperar revisión del Product Owner antes de PR. No merge, Microsoft live ni otra tarea.
