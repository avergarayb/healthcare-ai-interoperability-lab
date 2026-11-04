# Enterprise Connector Authorization V1

Estado: **dirección arquitectónica aprobada; controles pendientes de implementación**, TASK 001 documental. Versiones conceptuales `enterprise-connector-authorization-v1` y `connector-security-audit-v1`; no son endpoints, esquemas SQL/ORM ni capacidades ejecutables. [ADR-096](../adr/ADR-096-identity-provider-agnostic-v1.md), [PrincipalContext V1](identity-principal-context-v1.md) y [ADR-097 aceptado solo como dirección arquitectónica](../adr/ADR-097-enterprise-connector-authorization-boundaries.md) delimitan la autoridad. [Arquitectura](../design/enterprise-connector-authorization-v1.md), [perfil Microsoft](microsoft-graph-connector-permissions-v1.md) y [amenazas](../design/enterprise-connector-threat-model-v1.md) completan el contrato sin sustituir los existentes.

## Tres capas obligatorias

1. **Platform Identity:** la frontera receptora construye un contexto interno verificado y vigente. Un prompt, JSON enviado por el cliente, cabecera arbitraria o nombre de agente no es identidad.
2. **Connector Authorization:** política local determina principal, organización, instancia, modalidad, operación, recurso, clasificación y propósito permitidos.
3. **External Resource Authorization:** el proveedor decide si la credencial externa y, en delegated, la persona, tienen autoridad efectiva. La plataforma no conoce por anticipado todos esos permisos.

La entrega exige las tres capas satisfactorias, auditoría obligatoria y límites de datos. Un `LOCAL_ALLOW` solo autoriza intentar una operación acotada; no afirma autorización Microsoft ni garantiza entrega. Un token de `healthcare-ai-api`, un permiso local y un token Graph son tres objetos distintos. No se suman permisos entre capas, organizaciones, modos o proveedores.

## Estado real y frontera de identidad

Las APIs IAM Python/Java actuales solo verifican workloads en sus rutas técnicas opt-in. La [revocación SQLite Python](trusted-identity-registry-v1.md) no es un directorio empresarial ni administración corporativa; Java sigue estático. Sesiones humanas son de desarrollo, no OIDC humano productivo. Nada de esto otorga hoy acceso a un conector.

El diseño admite futuros principales humanos verificados y workloads registrados. Un agente actúa bajo un principal técnico con grants explícitos; el LLM no se convierte en principal ni posee credenciales. Un futuro flujo delegado requiere un binding humano externo adicional aprobado, no etiquetar un workload como persona. No crear ahora un Identity Service desplegable: es una responsabilidad lógica de la frontera IAM existente.

## Entidades conceptuales y campos mínimos

IDs internos opacos, acotados y no sensibles; versiones enteras monótonas; tiempos UTC. Las referencias deben resolver a registros confiables, no a URLs o secretos indicados por una solicitud. Los registros y sus transiciones exigen almacenamiento/administración versionados en una TASK posterior. No hay creación automática por el agente.

| Entidad | Campos/responsabilidades requeridos |
|---|---|
| **ConnectorDefinition** | `definition_id`, `connector_type`, `provider`, `version`, `supported_operations`, `required_external_permission_profiles`, `data_classification_constraints`, `enabled`; allowlists de operaciones/transportes y límites versionados |
| **ConnectorInstance** | `instance_id`, `organization_id`, `tenant_binding_id`, `definition_id/version`, `authorized_mode`, `lifecycle_status`, `credential_ref`, `policy_version`, `review_due_at`, `enabled`; propietario único, nada de secretos |
| **TenantConnectorBinding** | `binding_id`, `organization_id`, proveedor/cloud, `resource_tenant_id`, authority/issuer aprobados, app/client id y service-principal id esperados, endpoints permitidos, `mode`, `version`, estado, origen/aprobador/revisión; no inferidos del solicitante |
| **ExternalResourceGrant** | `resource_grant_id`, `connector_instance_id`, tipo de recurso externo, identidad canónica estable cualificada por tenant/cloud, `allowed_operations`, `external_grant_ref`, rol/perfil externo esperado, estado, `expires_at`/revisión, versión; registrar evidencia externa no equivale a saber la ACL vigente |
| **ConnectorPrincipalGrant** | `principal_grant_id`, principal interno/tipo, `organization_id`, `connector_instance_id`, operaciones, `allowed_resource_scope`, modalidad, propósito/clasificación, enabled, expiración y versión; no grants por texto del modelo |
| **DelegatedIdentityBinding** | Principal humano interno, tenant/issuer externo exactos, identificador de cuenta/objeto externo confiable, app/instancia/modo, estado/revisión, `credential_ref`; vinculación explícita, no por email |
| **CredentialReference** | Referencia opaca al broker/vault, organización/instancia/tenant/app/modo y cuenta delegada si corresponde, versión/estado/revocación; tipo compatible y perfil permitido. Nunca material secreto |
| **ConnectorAccessDecision** | `decision_id`, `correlation_id`, principal interno o anonymous, organización validada, instancia/definición, recurso interno resuelto, operación, modo/tipo de credencial permitido, resultado/motivo controlado, versión de política/bindings/grants, `decided_at`, `expires_at`, presupuesto y evidencia mínima; no credencial ni token portable |

### Invariantes de integridad

- Una instancia pertenece a una organización. Todas sus referencias, grants, credenciales y decisiones deben coincidir con esa organización y su binding externo; conocer un ID de B no da autoridad desde A.
- Una organización puede relacionarse con varios tenants y un tenant con varias organizaciones, pero cada asociación es explícita. La clave de caché/lookup incluye organización, instancia, tenant, app, modo y cuenta cuando exista. No resolver «primera coincidencia» ni reutilizar solo por client id.
- Application registration (app/client id) y service principal del tenant no son el mismo ID. Tenant de recurso, tenant hogar del usuario y organización SaaS tampoco. No inferir ninguno por email, hostname solicitado o claims no verificados.
- Modo delegado/app-only fijado en la instancia y grant. Una decisión no cambia de modo para recuperar un error. No grant union; dos permisos parciales de distintas organizaciones no forman uno suficiente.
- Estado `enabled` no basta: principal, membresía, binding, instancia, grant, credencial referenciada, revisión y política deben estar vigentes y coherentes.
- Expiraciones/revisiones son límites, no permisos. Falta de fecha/perfil obligatorio o revisión vencida deniega según política explícita; no interpretar null como «para siempre».
- El catálogo no permite operaciones no soportadas por el adaptador/proveedor. Un perfil externo no probado sigue deshabilitado aunque exista un grant local.
- La decisión es interna, de un solo uso y ligada a la operación/recurso/revisión/presupuesto. No se acepta desde HTTP, documentos, checkpoints o herramientas como una capacidad firmada reutilizable.

## Organizaciones, tenants y recursos

Cliente empresarial es la relación contractual; organización es nuestro ámbito interno de política/datos. Microsoft Entra tenant es el directorio externo; aplicación es su registro, service principal su representación local y usuario Microsoft una identidad dentro de un contexto de tenant. Site SharePoint, drive, biblioteca, carpeta y archivo son recursos, no identidades de plataforma. Modelo Microsoft documentado en el [perfil de permisos](microsoft-graph-connector-permissions-v1.md).

Representación canónica propuesta: `(provider, cloud, resource_tenant_id, resource_type, stable_resource_id, parent_scope)`; para Graph, preservar site/list/drive/item IDs separados y su correspondencia verificada. Biblioteca puede tener representación lista y drive, sin igualar sus identificadores. Nombre, ruta, URL compartida o email no son la clave de autorización. Un rename/move, cambio de padre, shortcut/remoteItem o migración exige revalidar pertenencia al alcance; no confiar en un prefijo de ruta ni en una copia antigua del árbol.

`allowed_resource_scope` admite solo recurso exacto o subtree registrado con semántica explícita de descendencia. Enumerar hijos no concede lectura de su contenido ni acceso a padres/hermanos. Cada ítem y continuación se valida contra el alcance; límites de páginas/items/bytes/tiempo no pueden convertirse en crawling. «Identificar recursos» significa resolver el catálogo autorizado, no buscar globalmente el tenant.

Recursos cross-tenant/B2B: deshabilitados por defecto para V1 inicial. Un invitado puede tener un objeto distinto en el tenant del recurso; no trasladar identidad/permisos del hogar. Una futura excepción requiere binding explícito de tenant de recurso, usuario invitado, app/service principal, recurso y consentimiento, más pruebas negativas. Nunca cambiar autoridad, redimir un enlace compartido o usar credenciales de B desde A automáticamente.

## Operaciones V1 propuestas

| Capacidad local | Límite |
|---|---|
| `resource.resolve_registered` | Catálogo local del ámbito autorizado; sin descubrimiento global externo |
| `resource.metadata.read` | Solo campos allowlisted de recurso registrado; minimizar títulos/rutas/nombres personales |
| `resource.children.list` | Una colección/carpeta autorizada con paginación acotada y scope validado por ítem |
| `document.content.read` | Gate A: adquisición acotada de un documento aprobado, MIME/tamaño/tiempo/límites de extracción; no concede entrega, uso por modelo ni conservación |
| `resource.provenance.read` | Identidad de recurso y versión/procedencia mínimas para el consumidor autorizado |

`connector.sharepoint.read` puede existir como nombre local futuro, pero no se traduce automáticamente a Sites.Selected ni al conjunto de operaciones anterior. La definición versionada debe mapear cada operación a un perfil externo probado. Las capacidades son namespaces de aplicación propuestos, no scopes Microsoft ni permisos implementados.

Fuera de V1: creación/modificación/eliminación, sharing, cambio de ACL, administración de sites/invitados, búsqueda global, descarga masiva, sincronización e índices RAG permanentes. Ni un GET externo ni una operación de «lectura» hacen inocua la extracción/exfiltración; también se autoriza propósito, volumen, clasificación y destino.

## Autorizaciones independientes de uso de datos

Además de las tres autoridades anteriores, cada efecto requiere una decisión local específica. Estos gates son requisitos conceptuales, no scopes Graph, endpoints ni mecanismos implementados en TASK 001.

| Gate | Efecto y autorización verificable requerida |
|---|---|
| A — consultar | Adquirir datos externos del recurso registrado; identidad/grants locales y autoridad externa vigentes, operación y presupuesto exactos |
| B — entregar | Entregar contenido al usuario autorizado identificado y destino aprobado; revalidar principal/organización/recurso, clasificación, propósito, minimización y vigencia antes de responder, también desde caché |
| C — procesar con IA | Enviar/procesar con un modelo concreto: política explícita de clasificación, proveedor/modelo/deployment, destino aprobado, propósito, minimización y uso/retención de datos; ausencia de aprobación deniega antes del envío |
| D — indexar o conservar derivados | **Deshabilitado en V1**: embeddings, índices permanentes, copias derivadas y retención de resultados/contenido en checkpoints; una futura habilitación requiere contrato/ADR, política y autorización propios |

**A no implica B, C ni D.** B no autoriza un modelo y C no autoriza entrega a un usuario, sharing ni conservación de derivados. Cada efecto aplicable necesita su propia evaluación; no son una cadena de permisos heredados. Los resultados transitorios de C quedan sujetos a minimización/purga y a B antes de entregarse; no habilitan retención persistente D ni prometen una política del proveedor que no se haya verificado. Auditoría mínima de decisiones/procedencia no es almacenamiento de documentos o derivados. Una caché transitoria acotada, si se autorizara, no da acceso permanente ni puede eludir B/C o el retiro de permisos.

Pruebas futuras obligatorias (TASK 002 con dobles, TASK 005 integración controlada, TASK 007 validación): A permitido pero C/modelo no autorizado denegado sin envío; documento hostil no activa herramientas ni cambia permisos; cache hit reautorizado antes de B; contenido de B nunca en respuestas, citas o resultados de A (organizaciones distintas); read no permite indexación, sharing ni exfiltración. Usar organizaciones sintéticas diferenciadas para no confundirlas con las letras de los gates. Nada de esto se ejecuta en TASK 001.

## Evaluación DENY-BY-DEFAULT

Antes de obtener credenciales o llamar al exterior, evaluar en una revisión consistente:

1. Principal autenticado, tipo y contexto íntegros, vigentes y aptos para la ruta; reautorización nueva si es trabajo diferido.
2. Organización activa válida y membresía/binding interno autorizados.
3. Definición e instancia habilitadas; instancia propiedad de esa organización.
4. Operación registrada, mínima y dentro del presupuesto de esa definición.
5. Recurso registrado y descendencia/identidad dentro del alcance explícito.
6. Grant del principal y ExternalResourceGrant locales vigentes, revisados y compatibles con la operación.
7. Modalidad delegated/application autorizada, con binding humano delegado si corresponde.
8. TenantConnectorBinding exacto y coherente con recurso, cloud, app y service principal.
9. CredentialReference del mismo ámbito, compatible con modo/perfil; broker no puede elegir una alternativa más poderosa.
10. Clasificación, propósito, destinatario y política de minimización/retención satisfechos.
11. Política/versiones actuales y dependencias disponibles; si no puede comprobarse, denegar/no disponible.
12. Auditoría previa obligatoria persistida antes de solicitar credencial o efectuar I/O externo.

Los pasos agrupan los trece controles del enunciado; no omiten membresía, instancia, recurso, grant, modo, tenant, credencial ni auditoría. Denegación local no contacta al proveedor ni al vault. Solo después el broker obtiene una credencial Graph del perfil/tenant/cuenta aprobados; Graph evalúa su propia autoridad en cada llamada. El broker valida metadatos de adquisición y no consume IDs/URLs de credenciales propuestos por el modelo.

Antes de cada página, reintento y entrega, revalidar la decisión/política/estado y expiraciones. Cambio concurrente invalida nuevas operaciones. Si se revoca durante un fetch, suprimir la entrega cuando se detecte; no prometer cancelar retroactivamente la llamada ni borrar bytes ya recibidos por un consumidor. El TTL de decisión será aprobado en implementación y nunca superará contexto, grants, credencial y límite local. No fijar un TTL de producción por analogía con los 30 segundos del fixture IAM.

| Resultado interno | Semántica, sin fijar un endpoint nuevo |
|---|---|
| `LOCAL_ALLOW` | Intento exacto permitido; no entrega/éxito externo todavía |
| `DENY` | Sin credencial ni I/O externo si es fallo local; error público genérico sin enumerar recursos ajenos |
| `UNAVAILABLE` | Config/política/vault/auditoría/proveedor requeridos no disponibles; sin fallback |
| `EXTERNAL_SUCCESS` | Proveedor permitió la operación; aún requiere auditoría final y revalidación para entregar |
| `EXTERNAL_DENIED` | 401/403 externos; no downgrade, token alternativo, ampliación o cambio de tenant |
| `DELIVERY_SUPPRESSED` | Contenido obtenido pero no entregable por revocación, caducidad, validación o fallo de auditoría |

Futuras rutas deberán contratar su HTTP por separado (incluidos auth 401, policy 403 y dependencia 503); no se modifican los HTTP IAM existentes. 404 externo no autoriza nada ni demuestra ausencia de todo el tenant. 429/5xx permite solo reintentos bounded del mismo perfil, si política sigue vigente; no cambio de credencial privilegiada. Respuestas parciales se declaran parciales o se rechazan, nunca completitud inventada.

## Credenciales y ciclo de vida

Instancia: `draft → pending_approval → active → suspended/revoked → offboarded`; reactivar exige revisión/versión explícitas, no recuperación automática. Grants/credenciales tienen enabled, revocación, expiración y revisión independientes. Un fallo de vault o proveedor no regresa a static/legacy ni delegated→application.

Toda credencial es propiedad de un ámbito de organización/instancia/tenant/app/modo; delegated añade cuenta externa ligada al principal humano. Solo el broker/vault puede materializarla de forma transitoria para un adaptador autorizado. Preferir certificado o federación compatible frente a client secrets largos, con custodia/rotación/revocación y permisos de uso separados; su disponibilidad no se presupone. No implementar vault ni solicitar secretos en TASK 001.

Tokens Graph, refresh tokens y claves privadas nunca van a prompts, checkpoints, chat, logs, auditoría, RAG o bases clínicas. Caché futura cifrada, limitada y segregada por todos los ámbitos; sin persistencia por defecto fuera de un vault/broker aprobado. Refresh delegado requiere consentimiento/perfil y puede exigir reautenticación; no reutilizar app-only para ocultarla. App-only renueva adquisición con credencial vigente, no mediante refresh token humano. Un refresh no renueva grants locales.

Offboarding: deshabilitar primero instancia/grants locales y nuevas decisiones, invalidar cachés y trabajo diferido, retirar referencias/bindings, pedir retirada externa por administrador autorizado y purgar temporales/cachés conforme a retención legal aprobada. Conservar auditoría mínima según política; no prometer eliminar datos sujetos a retención. Verificar todos los grants/rutas externas coexistentes; retirar uno no acredita revocación global. Fallos parciales dejan estado suspendido y evidencia, no reactivación silenciosa.

## Connector Security Audit V1 propuesto

Convenciones inspeccionadas: los contratos [Python OIDC](oidc-workload-security-audit-v1.md) y [Java OIDC](java-oidc-security-audit-v1.md) usan nombres cerrados, UUID/UTC, actor workload/anonymous, metadatos mínimos y append obligatorio. Security Audit legacy y Federation tienen vocabularios distintos. Se propone contrato **aditivo separado**, sin reutilizar sus tablas, actores ni productores ni añadir eventos allí en TASK 001.

| Evento propuesto | Fase y significado |
|---|---|
| `connector_access_allowed` | Autorización local previa: permite intentar; no afirma éxito Graph |
| `connector_access_denied` | Política local deniega |
| `connector_not_registered` | Definición/instancia no registrada, sin copiar input libre |
| `organization_mismatch` | Incoherencia de ámbito, sin revelar datos de otra organización |
| `resource_out_of_scope` | Recurso no registrado/permitido; input no confiable no se registra literalmente |
| `permission_revoked` | Decisión detecta grant local retirado; no afirma revocación Microsoft |
| `credential_unavailable` | Broker/referencia no disponible; no log de secreto/path |
| `credential_expired` | Adquisición/perfil expirado y no renovable dentro de la política |
| `external_access_denied` | Denegación Graph real; código/categoría controlados |
| `external_provider_unavailable` | Timeout/429/5xx o dependencia externa; sin cuerpo arbitrario |
| `connector_policy_error` | Política inconsistente/no verificable; fail-closed |

El contrato definitivo añadirá categorías de resultado externo satisfactorio, decisión/resultado de entrega, uso por modelo y administración, por ejemplo `connector_external_read_completed`, `connector_delivery_suppressed` y `connector_grant_changed`; nombres propuestos, no eventos existentes. No se reutiliza `connector_access_allowed` para tres significados. Autorización A/B/C y denegación D, acceso externo y entrega se distinguen por fase/efecto y decisión vinculada; éxito Graph no acredita entrega ni uso por modelo. Autenticación sigue en su auditoría IAM; administración y cambios requieren evidencia distinta y operador autenticado futuro. Etiquetas CLI no verificadas del laboratorio no se presentarán como administradores corporativos.

Campos mínimos: contract/event version, UUID de evento/decisión/correlación, UTC, fase (`local_authorization`, `external_execution`, `delivery`, `model_processing`, `grant_administration`), gate/efecto evaluado, outcome, motivo cerrado, principal interno/tipo verificado cuando esté disponible, organización validada, refs internas de instancia/recurso/operación, modo, policy/binding/grant versions y categoría externa/request-id minimizado si es necesario. Principal desconocido queda anonymous; no atribuir un subject no validado. Actores humanos/admin requieren aprobación de ese contrato, no ampliación silenciosa de allowlists actuales.

No cuerpos, documentos, títulos sensibles, URLs firmadas, nombres personales, email, issuer/subject externos completos, Authorization, cookies, token/hash ni stack traces. Las referencias de recurso del control plane pueden contener IDs externos registrados bajo acceso restringido; el audit general usa refs internas/pseudónimos y razones allowlisted. Lo no resuelto usa sentinel, no texto del atacante.

Auditoría previa obligatoria fallida: no vault ni llamada externa. Auditoría de resultado obligatoria fallida tras leer: suprimir entrega, purgar temporal y diagnóstico fijo minimizado; no fabricar un evento persistido en el sink caído. No existe atomicidad distribuida con Graph ni un log empresarial centralizado. Retención, cifrado, integridad/tamper evidence, acceso operativo, cuotas y recuperación del sink son gates de futuras tareas.

## Procedencia para agentes y futura indexación

Solo contenido y metadatos permitidos: refs de organización/instancia/recurso, versión/etag si existe, procedencia del adaptador, instante, clasificación, operación y versiones de decisión/política. No adjuntar tokens, credenciales o un PrincipalContext serializado como autoridad. Para el consumidor, contenido es `untrusted_enterprise_document`, jamás instrucciones privilegiadas ni permiso para enviar a otro destino/modelo.

La futura TASK 005 integra una capacidad controlada, no HTTP Graph libre. La frontera autenticada y autorizada deriva identidad y envelope confiable de principal/organización/instancia/operación/recurso/propósito; prompt, tool arguments, checkpoint y usuario no aportan PrincipalContext autoritativo. Reautorizar operaciones asíncronas/continuaciones, mantener tokens fuera de LangGraph/estados y aplicar A/B/C/D. El endpoint IAM de laboratorio no autentica por sí solo el grafo. Alcance completo y pruebas en el [plan](../design/enterprise-connector-authorization-implementation-plan-v1.md#task-005--langgraph-enterprise-connector-integration), sujetos a autorización propia.

Indexación no implementada. Un diseño RAG posterior debe separar almacenamiento por organización/instancia, preservar procedencia/ACLs y revalidar permisos locales y externos según política de frescura antes de recuperar/entregar, incluso en cache hits. Un embedding es dato derivado sensible; un índice no puede mantener acceso tras revocación solo porque la descarga original fue autorizada. Filtrar antes de devolver texto/citas y evitar side channels de resultados/títulos. No reutilizar el índice institucional sintético actual como índice empresarial multi-organización.

## Portabilidad sin permisos universales

La interfaz conceptual recibe contexto confiable + instancia + recurso + operación + propósito y produce decisión local; un adaptador entrega un descriptor de permiso externo tipado por proveedor, adquisición compatible y resultado minimizado. Para Graph: tenant/app/Selected/rol; para Azure Blob futuro: cuenta/contenedor/identidad y RBAC/data-plane/ACL aplicables; para S3 futuro: cuenta/rol/bucket/key y políticas IAM/resource/condiciones pertinentes. No existe un scope universal, no traducir Selected a Azure RBAC ni AWS IAM, ni asumir equivalencia de IDs/credenciales. La compatibilidad cloud específica necesita contrato y evidencia propios.
