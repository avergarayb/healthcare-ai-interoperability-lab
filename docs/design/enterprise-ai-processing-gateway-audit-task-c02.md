# TASK-C02 Phase B — gateway offline, ledger y auditoría durable

Estado: **aceptada por el Product Owner exclusivamente para laboratorio offline Windows; commit/push de las 17 rutas autorizado tras revisión final satisfactoria**. Entrega en la rama feature/enterprise-ai-processing-authorization-task-c02, no integrada en main; verificar Git y remoto en cada sesión. Se resolvió la incompatibilidad AST C01 mediante la única excepción autorizada. POSIX no está validado y ahora se rechaza explícitamente antes de abrir el store; symlink físico de archivo Windows sigue pendiente. No PR/merge, C03, DEMO-002, C04, proveedores reales, PostgreSQL, Graph live, RAG, MCP, Gate D o entrega humana.

Autoridad: [Phase A preservada y decisiones posteriores](enterprise-ai-processing-gateway-audit-task-c02-proposal.md), [DESIGN-001](enterprise-ai-processing-authorization-v1.md), [contrato C/auditoría](../contracts/enterprise-ai-processing-authorization-v1.md), [amenazas](enterprise-ai-processing-threat-model-v1.md) y [plan](enterprise-ai-processing-implementation-plan-v1.md). Los cuatro documentos DESIGN-001 y ADR-097 no se modificaron.

## Componentes e inventario cerrado

| Archivo | Responsabilidad / límite |
|---|---|
| [execution_types.py](../../services/ai-service/app/enterprise_ai_processing/execution_types.py) | Owner efímero, lease no portable, resultados metadata-only y puertos mínimos de dominio; sin SQL ni emisor de identidad |
| [gateway.py](../../services/ai-service/app/enterprise_ai_processing/gateway.py) | prepare/invoke_once, C01 por grant completo, input sellado/medido, barrera y cleanup independiente; sin SQL, filesystem o candidato público |
| [fake_model.py](../../services/ai-service/app/enterprise_ai_processing/fake_model.py) | Entrada real al adaptador y extracción determinista acotada; sin SQL/SDK/red/workers |
| [sqlite_ledger.py](../../services/ai-service/app/enterprise_ai_processing/sqlite_ledger.py) | Propiedad OS, inicialización, CAS/estados/reservas/audit, consulta organizacional y reconciliación |
| [migración propia](../../services/ai-service/app/enterprise_ai_processing/migrations/001_processing_ledger.sql) | Cinco tablas STRICT y cinco índices del DDL aprobado; sin modificar migraciones históricas |
| [fixture C02](../../services/ai-service/tests/enterprise_ai_processing_execution_fixture.py) | Autoridad exclusivamente de test, fuentes sintéticas, proyección durable y mutadores coordinados; no IAM |
| [AST C02](../../services/ai-service/tests/test_enterprise_ai_processing_architecture.py) | Inventario explícito de tres módulos C01 y cuatro C02, allowlists por componente, ciclos y ausencia de wiring |

No wiring FastAPI, LangGraph, ConnectorService, EnterpriseDocumentWorkflow, IAM, Java o grafos clínicos. Gate C del recorrido anterior continúa DENY y D deshabilitado. C02 no requiere LangGraph; ningún LLM autoriza. El ledger recibe metadata cerrada, nunca documento/pregunta/input/candidato. No expone SQL, conexiones ni transacciones al gateway.

Cada grant completo se proyecta con la revisión actual y se evalúa por C01, sin unión de grants ni motor paralelo de scopes. approval_ref procede del grant/revisión propios. Revisión C global: un cambio en B puede invalidar conservadoramente A; no hay aislamiento de disponibilidad por organización.

## Corrección AST C01 expresamente autorizada

Antes: suite C01 histórica 191 PASS/1 FAIL. Se reprodujo el fallo de la prueba arquitectónica: recorría todos los .py del namespace mediante glob, con allowlist de módulos puros C01. El primer import rechazado era types; SQLite, sincronización e invoke también eran incompatibles con C02 autorizado. Se ejecutaron las restricciones originales sobre los tres módulos C01 antes de editar: ninguna dependencia prohibida real.

El PO autorizó únicamente la prueba implicada y su helper en [test_enterprise_ai_processing.py](../../services/ai-service/tests/test_enterprise_ai_processing.py). Ahora inspecciona explícitamente __init__.py, models.py y policy.py. Conserva allowlist de imports, prohibiciones de efectos/adquisición/helpers privados, ausencia de wiring raíz y los ocho campos exactos de AIProcessingDecision. Añade rechazo explícito de SQL, imports dinámicos y builtins peligrosos. No skip/xfail ni ocultación de imports. Comparación AST con HEAD: todos los nodos fuera de esa prueba/helper permanecen iguales; los tres módulos productivos C01 están intactos.

La suite arquitectónica C02 independiente exige inventario cerrado, imports exactos por módulo, SQL/filesystem exclusivamente en backend e invoke solo desde self.model.invoke en gateway. Rechaza SDKs externos, red, configuración clínica, Human Review/FHIR/LangGraph/MCP/RAG, endpoints, helpers _validate_delivery/_event, introspección de frames y wiring anterior. Verifica ciclos reales y controles negativos inertes. No sustituye ejecución ni guard de red.

Después de la corrección AST: C01 **192 PASS en 0,48 s** y C02 **210 PASS en 21,43 s**, evidencia histórica anterior a esta autorización de publicación. La revisión final Windows repite C01 **192 PASS en 0,39 s** y C02 **224 PASS en 68,84 s**, incluidas **42 pruebas arquitectónicas**; no sumar selecciones intermedias como evidencia adicional.

## Auditoría: atribución y hechos observados

Antes, toda denegación pre-reserva era anonymous. Una negativa nueva reprodujo que una identidad reconocida no obtenía su evento DENY organizacional.

Después, el gateway usa reconocimiento exacto del envelope/contexto, IdentityBoundary pública, validez temporal/audience/tipo y principal workload activo en snapshot fresco. Solo deriva actor y organización de esas autoridades, sin reevaluador paralelo de grants. La autoridad sintética del backend también debe reconocerse. Identidad no verificable queda anonymous, sin refs. A reconocida que intenta B produce actor A y ninguna referencia B; no cambia el audit visible de B. Pre-reserva omite recursos/grants/operaciones aún no resueltos. La consulta organizacional no expone secuencia global.

Fallos del sink producen UNAVAILABLE sin evento ficticio ni fallback en memoria. C02 usa enterprise-ai-processing-audit-v1 propio, separado de auditorías clínicas/IAM/conector. Diez eventos cerrados con parejas fase/outcome/reason; audit y estado comparten commit. Eventos de grounding/entrega C03 no se emiten.

## Estados, propiedad, barrera y recuperación

1. T1: INTENT/ISSUED/HELD y cuatro eventos previos, un commit. Sin confirmación no se entrega lease.
2. T2: consumo único por owner exacto, revisión/deadline y attempt_version CAS. Se revalida después del commit antes de invocar adaptador.
3. T3: el wrapper fake ya fue alcanzado; incrementa entrada, revalida y confirma observación antes del núcleo. Libera admisión; no conserva transacción durante extracción.
4. T4: vuelve a validar, mide uso real y confirma resultado metadata-only. Commit ambiguo suprime candidato, incluso si COMPLETED quedó durable.

Contadores de entrada y procesamiento son distintos: T3 fallido puede dejar entrada 1/núcleo 0, sin evento confirmado. No presentar T1/T2 como inferencia. Leases copiadas, serializadas, ID, otro gateway o reinicio no crean autoridad; nunca se reconstruyen desde SQLite. Terminales no vuelven a COMPLETED.

El slot es por organización/instancia/perfil. HELD y UNCERTAIN bloquean nuevas reservas, incluso tras TTL. UNKNOWN no libera incertidumbre mediante finish. Reconciliación requiere administrador reconocido de la organización, rechaza owner vivo y no procesa; liberación explícita convierte reserva en CHARGED, conserva UNKNOWN e historial. No reembolso/replay automático.

El coordinador mantiene processing.owner con lock kernel real de byte Windows. La revisión final retiró la rama flock no validada: toda plataforma distinta de nt se rechaza antes de paths/esquema/ownership, sin flags de habilitación. Se rechaza segundo proceso/handle. Cierre con owner vivo falla sin soltar lock; cierre durante fake no limpia owner ni libera propiedad. Los comandos comparten barrera antes de abrir conexión; close no libera OS lock a mitad de comando. Orden: barrera → comando/transacción; conexiones cerradas por comando; no locks SQL durante fake. process_epoch/PID/existencia de sidecar no sustituyen el lock.

Barrera compartida **solo** por mutadores de la composición offline. El writer coordinado no confirma durante admisión, sí durante fake usando otra conexión; su revocación suprime finalización. La contraprueba no coordinada confirma el límite: cambio tras último chequeo puede coexistir con entrada/núcleo 1; se detecta al terminar y no sale contenido. No garantía global frente a writers externos, Graph ni revocación hasta el último byte.

Ocho crashes reales de hijos test-owned cubren T1 antes/después, T2 después, T3 antes/después, durante fake y T4 antes/después. Reapertura conserva ausencia/INTENT/CONSUMED/ENTERED/COMPLETED según último commit; huérfanos se reconcilian UNKNOWN/UNCERTAIN. Fallos deterministas adicionales cubren ambos lados de T2/T3/T4 y sinks. Sin sink no se afirma que UNKNOWN esté escrito.

## Correcciones propias y negativas reproducidas

- Denegación reconocida: atribución desde autoridad, no parámetros del solicitante.
- close aceptaba liberar propiedad con owner vivo: ahora lo rechaza; fixture no cierra ledger si gateway no pudo cerrar.
- COMPLETED aceptaba código ERROR: ahora solo CANDIDATE/NO_EVIDENCE y uso real válido.
- Cuatro contadores de uso aceptaban bool: ahora tipos int exactos/rangos.
- Expiración durante commit T2 alcanzaba wrapper: nuevo recheck previo y terminal EXPIRED; igualdad temporal no se renueva.
- attempt_version textual podía pasar: metadata numérica estricta, sin depender de coerción SQLite.
- UNKNOWN podía finalizar RELEASED: ahora UNCERTAIN; reconciliación explícita conserva incertidumbre del resultado.
- Comandos y registro de owners comparten barrera con close; cambios de estado/audit son atómicos.

Las siete primeras negativas de estado/lifecycle fallaron antes de sus correcciones; dos negativas adicionales reprodujeron coerción y UNKNOWN/RELEASED. Dos fallos al construir nuevos tests no fueron defectos productivos: approval=required ya era rechazado por DDL aprobado (se prueba reemplazo válido de la exención); una fuente de 1025 bytes ya era rechazada por A/B antes de poder emitir evidencia C02. No se relajaron esos controles ni se fabricaron capacidades. Las correcciones anteriores de Phase B (sellado de input, medición real de output, exención durable, cleanup y cancelación primaria) permanecen.

Revisión previa a publicación: la antigua allowlist nt/posix permitía una implementación no validada. Se restringió a Windows, retirando flock/fcntl y su permiso AST; negativa de gate previa falló y después pasó. Es una prueba de rechazo con nombre de plataforma inyectado, **no ejecución o validación POSIX**. Junctions se prueban solo sobre Windows real, sin rama que pueda aprobar por el gate de otra plataforma.

Se reprodujo además un defecto P2 de validación del puerto administrativo interno: release_slot="false", 1 o None se aceptaban por truthiness; una cadena no vacía podía liberar el slot. Ahora exige bool exacto, después de reconocer autoridad y antes de modificar estado/audit. No había endpoint ni escalada de privilegios: seguía requiriendo administrador sintético reconocido; no cambia el modelo de reconciliación. Las tres negativas fallaron antes y pasan con estado anterior intacto. Se ampliaron códigos inválidos de COMPLETED y se probó HELD caducada: TTL no libera automáticamente; un aborto vivo comprobado sí puede pasarla a RELEASED. Sin defectos P0/P1 nuevos pendientes reproducidos ni refactorización masiva.

Perfil exclusivo fake-enterprise-extractive-v1/fake/versión 1/in-process-offline. Máximos: una fuente, 1024 bytes UTF-8 de documento, 256 de pregunta allowlisted, input completo 2048, output serializado 512 y 256 unidades fake, cinco segundos, un slot, cero retries. Overhead completo medido; no truncamiento ni confianza en contadores del doble. 1024 UTF-8 pasa en composición; 1025 se bloquea ya en A/B. Proveedor/modelo/versión/destino/retención/clasificación/tokenizer/pregunta no aprobados no se guardan ni habilitan fallback. Documento hostil y flags heredados de tracing no son autoridad.

## Matriz final C02-01 a C02-16

PASS significa evidencia del alcance offline Windows, no compatibilidad universal ni aceptación de C03. Las limitaciones explícitas no se convierten en PASS artificial.

| Grupo | Resultado | Evidencia positiva y negativa |
|---|---|---|
| C02-01 | PASS | intent→entrada→resultado, audit ordenado; DENY/UNAVAILABLE y fallos T1 sin procesamiento |
| C02-02 | PASS | lease exacta/CAS/dos consumidores; copias/ID/serialización/reinicio sin autoridad ni replay |
| C02-03 | PASS | fake exacto; ocho configuraciones no aprobadas rechazadas, flags no habilitan SDK/fallback |
| C02-04 | PASS | caps/+1, input con overhead, UTF-8 1024/1025, output real 256/257/513, contadores falsos/bool |
| C02-05 | PASS | slot único y A/B distintos; segunda reserva y UNKNOWN expirado bloqueados, reconciliación cruzada rechazada |
| C02-06 | PASS | commits/audit; fallos antes/después y confirmación ambigua sin resultado entregado/replay |
| C02-07 | PASS | bytes 20/37 cambian candidato; NO_EVIDENCE y salida inválida/oversize no se aceptan |
| C02-08 | PASS | núcleo normal; error, cancelación y deadlines wall/monotonic sin retries/workers |
| C02-09 | PASS | revisión vigente; revocar grant/perfil/exención/clasificación/permiso, expiración y cambio global B impiden o suprimen |
| C02-10 | PASS, alcance coordinado | segundo proceso bloqueado y writer coordinado ordenado; contraprueba reproduce ausencia de revocación global |
| C02-11 | PASS Windows parcial; BLOCKED POSIX/symlink de archivo | reapertura/crashes/DDL/checksum/FKs/audit, raíz relativa/inexistente, cinco hard links y junctions reales raíz/ancestro; gate rechaza no-Windows; POSIX y symlink físico de archivo no validados |
| C02-12 | PASS | consultas propias/paginación estricta; autoridad forjada/expirada/rol/cruce y anonymous sin refs ajenas |
| C02-13 | PASS, owners propios | canarios ausentes de SQLite/auxiliares/log/repr y frames propios retenidos; sin garantía de borrado del host/caller |
| C02-14 | PASS | ambas señales, cause/context/group, fallos retire/clear/finalización; A cancelado no limpia B, incluso con cleanup fallido |
| C02-15 | PASS offline | guard antes de colección, flags activos, inventario/imports/ciclos/wiring y negativas AST; no sandbox/firewall del host |
| C02-16 | PASS, una omisión heredada | C01 192 PASS; TASK 002–005/DEMO-001 617 PASS/1 SKIPPED; camino anterior C/D y endpoints sin cambios |

### Evidencia final y trazabilidad

C02 final previa a publicación: **224/224 en 68,84 s**. C01: **192/192 en 0,39 s**. Siete suites C02: [schema](../../services/ai-service/tests/test_enterprise_ai_processing_schema.py), [gateway](../../services/ai-service/tests/test_enterprise_ai_processing_gateway.py), [ownership](../../services/ai-service/tests/test_enterprise_ai_processing_ownership.py), [ledger](../../services/ai-service/tests/test_enterprise_ai_processing_ledger.py), [privacy](../../services/ai-service/tests/test_enterprise_ai_processing_privacy.py), [concurrency](../../services/ai-service/tests/test_enterprise_ai_processing_concurrency.py) y AST enlazada arriba. Las 14 adiciones netas cubren gate POSIX rechazado, import fcntl prohibido, siete códigos de finalización adicionales, tres argumentos administrativos inválidos, HELD caducada y privacidad del WAL vivo. Selección focalizada inicial ownership/AST: 65 PASS en 4,16 s, anterior al último fix, no sumada al total. Preflight histórico de esquema: 27 antes de la primera base persistente, no sumar de nuevo.

Regresión final previa a publicación TASK 002–005/DEMO-001: **617 PASS/1 SKIPPED en 539,47 s**: 145 TASK 002, 75 TASK 003, 158 TASK 004, 196 TASK 005 y 43 DEMO-001. La omisión es el symlink físico Windows heredado, no modificada ni convertida en PASS. Los tres procesos finales reportan cero intentos externos fuera de guards. Total actual: **1.033 PASS/1 SKIPPED**, sin sumar repeticiones. Esta es ejecución nueva, distinta de las 617 regresiones anteriores en 306,41 s y 363,37 s. Resultados intermedios C02 (117, 155, 170, 187, 210, 223) no son ejecuciones adicionales independientes ni evidencia final.

## Filesystem, privacidad y límites operacionales

Raíz absoluta existente/canónica test-owned, chequeo de padres, reparse/symlink, inode/dev y hard links; DB y sidecars -wal/-shm/-journal. No adopción/reparación de archivo desconocido. DDL/checksum/FKs/quick_check/continuidad de audit y estados cruzados verificados. Plataforma no soportada falla cerrado antes de crear paths. No cambios de ACL ni .pytest-tmp. Estas defensas no protegen frente a host/administrador malicioso ni eliminan carreras de sustitución del filesystem.

Windows: procesos distintos, muerte/cierre, junctions reales de raíz/ancestro y hard links probados. POSIX: **no soportado en este incremento, bloqueado al abrir backend**, sin ejecución real de flock/fork/aliases aquí; una futura habilitación requiere autorización y pruebas nativas. Symlink físico de archivo Windows pendiente (el skip heredado no se convierte en prueba C02). No instalar herramientas ni simular plataforma para declarar compatibilidad. El test de plataforma no soportada solo demuestra rechazo, no POSIX.

Owner explícito repr=False; aliases retirados en finally, cierre y limpieza independientes, fallback por slots. Sin frame.clear/f_locals/GC ni nueva introspección runtime. Diagnóstico estándar de tracebacks con locals solo en tests. Señales originales propagadas aunque fallen finalización/retire/clear; limpieza no cierra ledger/owner ajeno. El canario también se comprueba con WAL existente y no vacío, antes de su limpieza: un observador exclusivamente de test fija snapshot; no es una transacción del gateway durante fake. No eliminación criptográfica, ni garantía sobre copias deliberadas en caller, fixture de adquisición o host. Candidate nunca aparece en resultado público. No grounding, respuesta humana o comprobación de recepción.

## Mantenibilidad y evolución de persistencia

Revisión focalizada, sin refactorizar M01/M02, C01 ni componentes anteriores:

| Prioridad | Ubicación | Evidencia / recomendación |
|---|---|---|
| P2 | gateway.py, invoke_once | 61 líneas con admisión, ejecución, error y cleanup; pruebas separan hitos. Si se amplía en C03, extraer fases internas pequeñas sin mover autorización a LangGraph ni cambiar ownership |
| P2 | sqlite_ledger.py, _transaction / finish | 41/32 líneas; SQL, CAS y audit concentrados en backend, sin transacción durante núcleo. Mantener tabla de transiciones y pruebas de conformidad antes de otro backend |
| P2 | execution_types.py, ExecutionOwner.clear; gateway.py, _cleanup | Lista sensible repetida intencionalmente como fallback independiente. Toda nueva referencia exige actualizar ambos y tests de traceback; no scrub global |
| P2 | fixture C02, mint/populate | Reutiliza owners internos de fixture C01 y registros por identidad; es acoplamiento exclusivamente de test, no puerto productivo ni issuer IAM. Mantenerlo explícito y reevaluar al cambiar C01 |
| P3 | gateway.py, _attribution / _evaluate | Reconocimiento mínimo se repite para atribuir denegación sin convertirlo en autorización. Conservar separación y negativas anonymous/cross-org; no copiar lógica de grants C01 |

No P0/P1 nuevo reproducible sin resolver dentro del alcance; plataformas/amenazas excluidas permanecen riesgos, no garantías. No closures con contenido en runtime C02 ni manipulación de frames. El binding interno gateway→prólogo fake es fijo, no callback externo. Los Protocol son puertos mínimos de dominio, no repositorio genérico ni framework.

SQLite solo laboratorio offline. PostgreSQL objetivo **después de DEMO-002 y antes de un piloto con datos reales**. Revisar aislamiento, locks por fila/orden, CAS y revisiones globales/organizacionales, slots multiworker/fencing, commits ambiguos, tipos/DDL/migración/backup. Compartir A/B/C puede simplificar consistencia local solo con una transacción común aprobada; compartir servidor no basta ni hace atómica entrada Python/proveedor/entrega. Conservar UNKNOWN, no migrar leases como autoridad. WAL/STRICT/BEGIN IMMEDIATE se justifican exclusivamente en backend de archivo único. Sin ORM/adaptador PostgreSQL/servicios nuevos, ni cambios a stores clínicos/IAM/conector.

## Comandos y protección del workspace

Desde services/ai-service, venv existente, Python -B -X utf8, pytest.main con guards socket/DNS **antes de colección**, -q -x -p no:cacheprovider y basetemp absoluto nuevo bajo infra/iam-lab/.runtime con prefijos cortos c02-*. C02 selecciona las siete suites; C01 su archivo completo; regresiones las cinco suites test_enterprise_connectors.py, test_enterprise_connector_control_plane.py, test_enterprise_connector_graph.py, test_enterprise_connector_workflow.py y test_enterprise_connector_demo.py. Hijos test-owned usan -B y sin ventanas. Guards no habilitan servicios ni red.

Operaciones de revisión: git status --short --branch; git diff y diff --cached; git stash list/rev-parse; git fetch origin; comparación HEAD/origin/main/ancestría; rg; Get-Content UTF8; SHA-256; comparación AST contra git show HEAD; compilación en memoria; enlaces Markdown/patrones de secretos; git diff --check. Fetch no cambió archivos ni rama/main local. Publicación autorizada: git add -- con las 17 rutas exactas; revisión completa/diff --cached --check y escaneo de blobs staged; commit feat(ai): add offline model gateway and durable processing audit; push exclusivo de la rama C02. No PR ni merge.

Se preservaron los ocho ajenos y stash; 1.293 archivos preexistentes protegidos (excluidos handoff y excepción autorizada) conservan su digest. Advertencia preexistente de ACL al enumerar .pytest-tmp y avisos LF→CRLF: sin modificar permisos/EOL/migraciones. Sin operaciones contra local-hapi, Docker, Keycloak o proveedores. La selección general con HAPI y tres hashes CRLF históricos queda fuera de esta ejecución; no afirmar que se probó.

Antecedente Windows: una regresión anterior con basetemp largo falló al inicializar SQLite de DEMO-001; repetición corta pasó sin cambiar código/timeout/ACL. Longitud de path es inferencia compatible, no error crudo demostrado. Diagnóstico WMI anterior fue denegado; no se elevaron permisos ni cambiaron servicios.

Tras publicar la rama, esperar revisión del PO: **sin PR, merge, siguiente tarea ni documento de transición a Cursor**. C02 no se considera integrada en main antes de merge. La validación no es preparación de producción, multi-tenancy/IAM empresarial ni certificación regulatoria.
