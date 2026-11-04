# Microsoft Graph Connector Permissions V1

Estado: **perfil documental; dirección arquitectónica aceptada, compatibilidad operacional pendiente**, Enterprise Connector Authorization V1 — TASK 001. Consulta oficial: **2026-11-04, America/Lima**. Ninguna aplicación, consentimiento, token o llamada Microsoft Graph se creó/ejecutó. [ADR-097](../adr/ADR-097-enterprise-connector-authorization-boundaries.md) acepta solo dirección arquitectónica, no permisos/credenciales ni llamadas Graph. [Contrato local](enterprise-connector-authorization-v1.md) y [arquitectura](../design/enterprise-connector-authorization-v1.md) separan autoridad de plataforma y proveedor. Los permisos Graph solo participan en A (adquisición); no conceden B (entrega), C (modelo/destino) ni D (indexación/conservación, deshabilitado V1). TASK 004 propone el adaptador, TASK 005 integración LangGraph controlada, TASK 006 delegated y TASK 007 E2E; todas requieren autorización propia.

## Fuentes oficiales y alcance de la investigación

| ID | Microsoft Learn consultado | Uso / límite |
|---|---|---|
| M1 | [Permissions overview](https://learn.microsoft.com/en-us/graph/permissions-overview) | Delegated frente a application; intersección con usuario, consentimiento |
| M2 | [Selected overview](https://learn.microsoft.com/en-us/graph/permissions-selected-overview) | Granularidad, asignación, herencia y modalidades actuales |
| M3 | [Permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference) | Nombres exactos y AdminConsentRequired; no confundir permisos heredados |
| M4 | [Best practices](https://learn.microsoft.com/en-us/graph/best-practices-graph-permission) | Mínimo privilegio; artículo orientado a apps Teams, no prueba de soporte de endpoints SharePoint |
| M5 | [Entra OBO](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow) | Cadena delegada Entra compatible; no app-only ni intercambio genérico Keycloak |
| M6 | [Client Credentials](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow) | Credencial de aplicación, recurso y permisos consentidos; sin refresh token de usuario |
| M7 | [Authorization Code](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow) | Code + PKCE, redirect registrado y adquisición por librería reconocida |
| M8 | [Drive resource](https://learn.microsoft.com/en-us/graph/api/resources/drive?view=graph-rest-1.0) | OneDrive business, personal y biblioteca son tipos distintos |
| M9 | [Get driveItem](https://learn.microsoft.com/en-us/graph/api/driveitem-get?view=graph-rest-1.0) | Metadatos por identidad registrada; tabla de permisos por método |
| M10 | [List children](https://learn.microsoft.com/en-us/graph/api/driveitem-list-children?view=graph-rest-1.0) | Enumeración de una carpeta; paginación acotada, no crawling |
| M11 | [Get content](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0) | Descarga puede devolver 302 a URL preautenticada sensible |
| M12 | [Search sites](https://learn.microsoft.com/en-us/graph/api/site-search?view=graph-rest-1.0) | No admite Sites.Selected application; búsqueda global excluida |
| M13 | [Create site permission](https://learn.microsoft.com/en-us/graph/api/site-post-permissions?view=graph-rest-1.0) | Gestión administrativa distinta del lector; privilegios elevados, no incorporarlos al worker |
| M14 | [Access tokens](https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens) | El cliente trata el access token del recurso externo como credencial opaca |
| M15 | [Graph throttling](https://learn.microsoft.com/en-us/graph/throttling) | 429/Retry-After; no elevar permisos para recuperar disponibilidad |
| M16 | [Apps/service principals](https://learn.microsoft.com/en-us/entra/identity-platform/app-objects-and-service-principals) | Registro de aplicación y representación por tenant no son la misma entidad |
| M17 | [Entra B2B](https://learn.microsoft.com/en-us/entra/external-id/what-is-b2b) | Invitados y tenant de recurso; no prueba de acceso a cada archivo |

Las páginas públicas pudieron leerse aunque el chrome de Learn mostraba avisos de inicio de sesión. No se inició sesión ni se siguieron enlaces de Graph Explorer. Las fuentes son revisables: antes de cada futuro onboarding se debe volver a verificar el método v1.0, modalidad, cuenta, cloud y permiso efectivo. No se presupone cobertura beta, personal MSA, SharePoint Embedded ni nubes soberanas.

## Delegated y application no son intercambiables

Delegated actúa por una persona y queda limitado por sus derechos externos y el consentimiento de aplicación; application actúa sin persona presente y requiere autoridad propia de la aplicación. Para nuestro diseño se añade siempre la intersección con política local. Un consentimiento externo no crea un grant interno. M1 y M4 sustentan el mínimo privilegio; no obligan a usar un modo que no responda al caso de uso.

| Aspecto | Delegated | Application / app-only |
|---|---|---|
| Evidencia externa | Sesión/cuenta Entra vinculada explícitamente al principal humano interno | App/service principal y credencial del tenant/instancia aprobados |
| Adquisición futura | Code + PKCE; OBO solo bajo sus prerrequisitos | Client Credentials; preferencia por certificado o federación de workload compatible, sujeto a diseño de despliegue |
| Consentimiento | Según permiso y política del tenant; no asumir user consent disponible | Administrativo, con asignación de permisos aplicable |
| Autoridad | Usuario ∩ aplicación ∩ recurso ∩ política local | Aplicación ∩ recurso ∩ política local; nunca atribuir presencia humana |
| Renovación | Mediante caché protegida/librería y refresh cuando esté concedido; puede exigir interacción | Nuevo token mediante credencial vigente; no inventar refresh token de usuario |
| Cambio de modalidad | Requiere nueva aprobación/binding | Nunca fallback desde delegated rechazado |

## Matriz Selected comprobada documentalmente

M2 describe ambos modos para Selected. M3 distingue los requisitos de consentimiento; «No» no anula restricciones del tenant ni la asignación por recurso. Ningún nombre es por sí mismo un permiso de solo lectura: el **rol externo read** y la operación local aprobada deben restringirlo.

| Permiso exacto | Recurso seleccionado | Application / delegated | Admin consent en referencia: application / delegated | Aplicabilidad documental y gate |
|---|---|---|---|---|
| `Sites.Selected` | Site collection SharePoint | Ambos | Sí / No | SharePoint Online; no asumir equivalente a «solo un drive». Un OneDrive empresarial requiere identificar su recurso SharePoint y comprobar ese escenario; no declarar autorización de cualquier OneDrive |
| `Lists.SelectedOperations.Selected` | Lista concreta | Ambos | Sí / Sí | SharePoint Online; biblioteca/lista registrada, sin acceso automático al padre |
| `ListItems.SelectedOperations.Selected` | Ítem; también archivo/carpeta donde corresponda | Ambos | Sí / Sí | SharePoint; el tipo de destino y el grant importan, no solo el path Graph |
| `Files.SelectedOperations.Selected` | Archivo o carpeta de biblioteca con documentos | Ambos | Sí / Sí | La referencia incluye SharePoint Online y OneDrive; candidato granular para OneDrive for Business, condicionado a pruebas por método y grant |

**No equivalentes:** `Files.Read.Selected` y `Files.ReadWrite.Selected` son delegated heredados/preview de Office 365 file handlers v1.0, de duración limitada; M3 indica que no deben usarse para llamar directamente Graph. No se usarán como perfil de este conector. Tampoco `FileStorageContainer.Selected` de SharePoint Embedded es un alias de Files.SelectedOperations.Selected.

Para Selected se requieren conjuntamente consentimiento del permiso adecuado, asignación explícita a la aplicación sobre el recurso y token válido para la llamada. Consentir sin asignar no concede acceso. Asignar sin el permiso del token tampoco basta. En delegated se añade el derecho del usuario. Asignaciones debajo del site pueden romper herencia y consumir límites de permisos únicos; no desplegar grants por archivo masivamente. Otros permisos ya concedidos pueden abrir caminos adicionales: añadir Selected no restringe automáticamente permisos amplios coexistentes. Fuente: M2.

## Perfil externo recomendado, no aprovisionado

Preferir el Selected más estrecho compatible con **todas** las lecturas requeridas, rol read, recursos registrados y cuenta empresarial. Sites.Selected con read es una alternativa para un site dedicado aprobado cuando el menor alcance no cubra un método necesario; no se presume mínimo absoluto ni se sustituye automáticamente. `Sites.Read.All`/`Files.Read.All` quedan prohibidos por defecto: una excepción exige justificación de necesidad sin alternativa, evaluación del alcance efectivo, nueva aprobación del cliente/PO y revisión contractual. Nunca activar esa excepción ante un 403.

La administración de asignaciones Selected es control plane, no capacidad del lector. M13 exige `Sites.FullControl.All` para crear el permiso de site y condiciones adicionales en delegated; esa identidad administrativa debe estar separada del worker. No hay receta ejecutable ni autorización para obtenerla en TASK 001. Para listas/ítems/archivos se verificará el método administrativo específico y rol del operador; no copiar privilegios de bootstrap al data plane.

## Operación frente a endpoint: no promesa universal de soporte

| Capacidad futura | Rutas candidatas, no llamadas ejecutadas | Verificado / pendiente |
|---|---|---|
| Resolver recurso registrado | Lookup local; IDs externos provisionados por operador | No necesita búsqueda global Graph ni Graph directory permissions por defecto |
| Leer metadatos | GET v1.0 `/drives/{drive-id}/items/{item-id}` | M9 documenta método; compatibilidad Selected específica de cuenta/grant queda como gate operacional |
| Enumerar dentro del alcance | GET v1.0 `/drives/{drive-id}/items/{item-id}/children` | M10 documenta método; no inferir acceso a padres/hermanos ni raíz del tenant; comprobar cada resultado/página |
| Leer contenido | GET v1.0 `/drives/{drive-id}/items/{item-id}/content` | M11 documenta 302; habilitación pendiente de transporte seguro y prueba Selected del recurso real |
| Buscar todos los sites | `/sites?search=...` | M12 excluye Sites.Selected application; NO admitida en V1, sin ampliación automática |
| Resolver enlaces compartidos, remoteItem, `/shares` | Ninguna habilitada inicialmente | Excluidos; no redimir links ni adoptar otro tenant/drive automáticamente |

Las tablas genéricas de M9–M11 muestran Files.Read/Files.Read.All y otras alternativas y no siempre enumeran Selected. M2 documenta el modelo Selected por destino, pero eso no certifica cada combinación de endpoint, tenant y cuenta. Se registra esta discrepancia de detalle: **soporte documental del modelo; compatibilidad operacional pendiente**, no «Selected funciona en todas las APIs» ni «hay que solicitar Files.Read.All». Un método sin evidencia se mantiene deshabilitado.

OneDrive `business` y bibliotecas `documentLibrary` se consideran candidatos diferenciados (M8), no el OneDrive personal de una cuenta MSA. La matriz de aceptación futura separará SharePoint site/biblioteca y OneDrive for Business, delegated/app-only, metadatos/children/content y grant `read`. B2B/tenants compartidos se mantienen deshabilitados hasta contratos y pruebas específicos.

## OAuth, OBO y tokens

Code + PKCE requiere un flujo humano Entra y vínculo interno aprobados, state/nonce/redirect exactos y librería reconocida (M7); el login Keycloak de laboratorio no implementa ese vínculo. OBO requiere un access token **Entra** delegado para el API intermedio y una cadena/consentimiento compatibles; no usa ID tokens, no funciona con un workload app-only como si fuera una persona y no intercambia genéricamente un token Keycloak. Fuente M5. Federación de workload para credenciales de aplicación sería otro mecanismo explícito, no OBO.

Client Credentials pide el recurso Graph aprobado con el perfil de aplicación consentido; `https://graph.microsoft.com/.default` no es un permiso Selected ni un grant de lectura, sino el selector de permisos configurados del recurso (M6). No se solicita aquí. Para delegated se solicita solo el conjunto aprobado; `offline_access`, si fuese necesario, requiere revisión y protección del refresh token, no se agrega por costumbre.

El cliente no usará la decodificación de un token Graph para decidir permisos locales ni asumirá que todo token externo es JWT. El proveedor recurso valida su token; el broker usa metadatos de expiración/tenant/cuenta de la adquisición reconocida y registros confiables. Esto no cambia la validación JWT obligatoria de nuestras APIs receptoras. Fuente M14.

## Transporte, consentimiento y revocación

M11 permite una URL de descarga preautenticada sin Authorization. Para nosotros es una credencial efímera: nunca log, prompt, auditoría ni respuesta al agente. Nada de redirects automáticos: validar HTTPS/origen de descarga aprobado para ese perfil, DNS/IP/egress, cadena y vínculo al recurso; no reenviar Bearer Graph al host destino. Si no existe una política segura verificable, denegar contenido y conservar solo metadatos permitidos. Validar también nextLink; no aceptar URLs arbitrarias de documentos.

Microsoft puede denegar por consentimiento retirado, ACL, Conditional Access, tenant o disponibilidad. 401/403 no habilitan otra credencial/modalidad. La latencia de revocación externa no tiene SLA supuesto; un pre-check no conoce todos los permisos efectivos actuales. 429/Retry-After permite solo reintento acotado de la misma lectura autorizada, sin ampliar permisos (M15). La revocación local bloquea nuevas decisiones; no recupera bytes ya entregados.

## Decisiones pendientes y evidencia antes de habilitar

Pendientes: tenant de prueba autorizado, registro/app ownership, single-tenant frente a multitenant, alcance inicial site/lista/archivo, permisos de cada método, selección de librería/broker/vault, política de descarga, cuentas invitadas, clouds y controles de consentimiento/retirada. No son dependencias que el agente pueda resolver pidiendo credenciales ahora.

Evidencia requerida: consentimiento/rol read y grant registrados por administrador separado; aceptación dentro del alcance y denegación de recurso hermano/tenant ajeno; usuario delegado sin ACL denegado; token/modalidad incorrectos denegados; revocación local/externa y expiración; método no soportado deshabilitado sin elevación. Véase [plan](../design/enterprise-connector-authorization-implementation-plan-v1.md). La consulta de Learn es la única evidencia Microsoft de TASK 001.
