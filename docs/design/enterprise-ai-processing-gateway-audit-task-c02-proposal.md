# TASK-C02 — Phase A: gateway offline, ledger y auditoría durable

## Decisión vigente del PO — revisión final y publicación Windows offline

El PO acepta funcionalmente C02 solo para laboratorio offline Windows y autoriza revisión final, correcciones reproducidas dentro de C02 y commit/push condicionado de las 17 rutas cerradas. No PR/merge, C03/DEMO-002/C04 ni traspaso a Cursor. C02 se entrega en feature/enterprise-ai-processing-authorization-task-c02, no integrada en main; verificar publicación/ancestría con Git en vivo. Las autorizaciones anteriores de no publicación que figuran abajo son históricas.

La revisión encontró que la rama POSIX no validada podía abrir el backend: se restringió explícitamente a nt antes de paths/esquema/ownership y se retiraron flock/fcntl. Prueba negativa de rechazo, no validación POSIX. Windows conserva pruebas reales de procesos independientes, muerte/cierre, hard links y junctions; symlink físico de archivo sigue pendiente, sin permisos elevados ni ACL modificadas.

Se corrigió un defecto P2 del puerto administrativo sintético: release_slot exige bool exacto para evitar interpretar la cadena "false" como liberación. Tres negativas reprodujeron aceptación indebida; ahora rechazan sin cambiar estado/audit. No escalada de autoridad, nuevo IAM ni cambio del protocolo de reconciliación. Códigos inválidos de COMPLETED y HELD caducada tienen negativas adicionales. Sin P0/P1 nuevo pendiente reproducido ni refactor de los P2 de mantenimiento.

Repetición actual posterior a estos ajustes: **224 PASS C02 en 68,84 s; 192 PASS C01 en 0,39 s; cinco regresiones 617 PASS/1 SKIPPED heredado en 539,47 s**, con cero intentos fuera de guards. Incluye comprobación de privacidad sobre WAL vivo no vacío con observador de test, sin transacción del gateway durante fake. Total actual 1.033 PASS/1 SKIPPED; detalles en el [runbook](enterprise-ai-processing-gateway-audit-task-c02.md). No sumar las 210 pruebas históricas ni las selecciones focalizadas al resultado actual. Persisten writers no coordinados, dos stores sin atomicidad distribuida, memoria externa al owner, M01/M02/P2, ausencia de entrega humana/LLM real y PostgreSQL futuro no implementado.

## Decisión histórica del PO — Phase B autorizada, sin publicación

La Phase A conservada abajo es la base histórica aprobada condicionalmente. El PO autoriza implementar exclusivamente C02, pruebas y documentación, sin staging/commit/push/PR y sin C03/DEMO-002/C04. Antes del flujo de ejecución se fijan estas tres decisiones:

1. Barrera de admisión por coordinador, únicamente de laboratorio. Todos los mutadores sintéticos C/A/B/fuente de la composición test-owned la respetan; el control plane A/B no cambia. Writers no coordinados, host comprometido y Graph live quedan fuera de la garantía, con contraprueba explícita.
2. Propiedad del archivo mediante lock real del sistema operativo en `processing.owner`, dentro de raíz test-owned y validado contra symlinks/reparse points/junctions/hard links/aliases. Segundo proceso rechazado; close/muerte liberan el lock, nunca reemiten leases. Plataforma sin mecanismo soportado falla cerrado. Ni existencia del sidecar, PID ni process_epoch constituyen propiedad.
3. `ai_provider_invocation_observed` significa entrada realmente alcanzada al adaptador interno confiable, no ejecución completa del núcleo extractivo. Su prólogo confirma T3 antes de procesamiento, sin SQL en el núcleo. Contadores separados de entrada y procesamiento; T1/T2 no anticipan T3. La barrera y conexiones se liberan antes de extraer. Las ventanas de crash conservan hechos durables/UNKNOWN, sin atomicidad COMMIT→Python supuesta.

Las modificaciones y evidencias posteriores de implementación se registrarán de forma aditiva aquí y en un runbook propio; no convierten el diseño histórico en pruebas ejecutadas.

### Decisión posterior: excepción AST autorizada y continuación C02

El PO autorizó expresamente modificar solo la prueba arquitectónica C01 y su helper indispensable en `tests/test_enterprise_ai_processing.py`. El diagnóstico previo reprodujo el rechazo de `types` por el glob del namespace completo; las restricciones originales sobre los tres módulos puros C01 pasaron antes de editar. Ahora esos tres módulos se inspeccionan explícitamente, sin cambiar producción C01 ni los demás tests; un inventario cerrado y controles AST C02 separados mantienen SQL/filesystem solo en backend, fake vía gateway, sin red/SDK/endpoint/wiring/ciclos ni helpers privados anteriores. No skip/xfail ni imports ocultos.

Resultado posterior: **C01 192 PASS en 0,48 s; C02 210 PASS en 21,43 s**, incluidos 41 controles arquitectónicos positivos/negativos. Cinco regresiones finales TASK 002–005/DEMO-001: **617 PASS/1 SKIPPED heredado en 306,41 s**. Cero intentos fuera de guards en los tres procesos. La matriz C02-01 a C02-16 y los límites se mantienen en el [runbook vigente](enterprise-ai-processing-gateway-audit-task-c02.md), sin reutilizar la evidencia histórica como ejecución nueva.

Denegaciones C02: identidad reconocida se atribuye al workload/organización derivados de autoridad confiable; no verificable queda anonymous sin refs; cruce A→B no incluye identificadores B en audit A. Negativas reproducidas corrigieron cierre con owner vivo, COMPLETED con ERROR, contadores bool, expiración durante T2, metadata numérica textual y UNKNOWN/RELEASED. No hubo cambios en C01 productivo, A/B, contratos anteriores, migraciones históricas ni SQL fuera del backend. La migración C02 conserva el DDL aprobado abajo.

Windows tiene pruebas reales de lock entre procesos, muerte/cierre, hard links y junctions raíz/ancestro. POSIX y symlinks físicos de archivo Windows permanecen sin validación operacional, no un PASS artificial. La barrera protege solo la composición cuyos mutadores la respetan: contraprueba no coordinada conserva el límite de revocación. PostgreSQL sigue como evaluación/migración posterior a DEMO-002 y antes de datos reales; no implementado. Sin C03, DEMO-002, C04, staging o publicación. Pendiente revisión del PO.

### Evidencia histórica de Phase B parcial y bloqueo de compatibilidad

Los siguientes párrafos registran el estado **anterior** a la autorización AST. El permiso requerido ya se concedió y aplicó de forma acotada según la sección precedente; no son instrucciones vigentes de detener por el mismo bloqueo resuelto.

Se implementaron cuatro módulos, migración propia idéntica al DDL base y fixture/suites C02. Prueba previa al primer archivo SQLite de ejecución: 27 casos aislados de esquema en memoria. Ejecución posterior completa propia: **117 PASS en 19,29 s**, con guard de red/DNS; incluye crashes reales de procesos hijos test-owned en T1–T4, lock entre procesos, cancelación/concurrencia y privacidad. No es evidencia de C03 ni aceptación final de C02.

Las tres condiciones tienen evidencia de laboratorio Windows: barrera compartida de la composición, exclusividad mediante lock de sistema operativo y entrada observada desde el adaptador realmente alcanzado. El núcleo no importa ni ejecuta SQLite. La contraprueba no coordinada reproduce un cambio tras el último chequeo y antes de extracción: procesamiento ya admitido, detección al finalizar y ninguna salida documental. No certifica revocación global. POSIX conserva una rama de implementación, no una validación operacional realizada en esta sesión Windows.

**Bloqueo reproducible:** la suite C01 sin modificar obtuvo **191 PASS / 1 FAIL**. Su prueba `test_package_is_not_wired_to_runtime_and_has_no_execution_primitives`, en `tests/test_enterprise_ai_processing.py` líneas 540–559, inspecciona `package.glob('*.py')`, no solo los tres archivos originales C01; prohíbe imports y llamadas que los cuatro nuevos módulos C02 necesitan expresamente. El primer fallo observado es el import `types`; también se excluyen SQLite, sincronización y `invoke`. Reubicar/ocultar imports o saltar esa prueba no es una corrección válida. Los modelos, política y tests C01 permanecen intactos; el flujo de implementación queda detenido ante la incompatibilidad de alcance.

Para continuar se necesita autorización específica del PO para evolucionar **únicamente** esa prueba arquitectónica: conservar íntegros sus controles sobre `__init__.py`, `models.py` y `policy.py` C01, mantener la ausencia de wiring raíz y agregar controles AST C02 propios (SQL solo en backend, núcleo sin persistencia/proveedores/red, sin endpoints/SDKs ni consumidores de helpers privados anteriores). No se ha aplicado ese cambio ni se considera aprobado. Toda aceptación C02 exige nuevas repeticiones completas después de resolverlo.

Detalle de implementación, correcciones, evidencia parcial, limitaciones y regresiones en el [runbook Phase B](enterprise-ai-processing-gateway-audit-task-c02.md). No staging, commit, push o PR. La propuesta Phase A original se conserva a continuación como evidencia histórica.

## Propuesta Phase A original — contenido histórico preservado

Estado: **propuesta técnica pendiente de aprobación del Product Owner; diseño solamente**. No implementación, DDL ejecutado, migración, base nueva, inferencia, staging, commit, push, PR o merge. La aprobación funcional y merge de C01 no autorizan implementar C02; el PO autoriza expresamente esta Phase A documental. Esta fase crea exclusivamente este documento; no actualiza el handoff, contratos ni runbooks anteriores.

Decisión adicional del PO: SQLite se conserva **solo para laboratorio offline**. PostgreSQL es el objetivo de una plataforma empresarial multiempresa futura, sujeto a evaluación/migración después de DEMO-002 y antes de cualquier piloto con datos reales. No se implementa PostgreSQL, ORM, adaptador alternativo ni servicio de base de datos ahora.

## 1. Autoridad, base e inventario inspeccionado

- [Arquitectura DESIGN-001](enterprise-ai-processing-authorization-v1.md), [contrato C/auditoría](../contracts/enterprise-ai-processing-authorization-v1.md), [amenazas](enterprise-ai-processing-threat-model-v1.md), [plan](enterprise-ai-processing-implementation-plan-v1.md), [ADR-097](../adr/ADR-097-enterprise-connector-authorization-boundaries.md), [contrato de conectores](../contracts/enterprise-connector-authorization-v1.md).
- [Runbook C01](enterprise-ai-processing-policy-fixture-v1.md), [modelos](../../services/ai-service/app/enterprise_ai_processing/models.py), [evaluador](../../services/ai-service/app/enterprise_ai_processing/policy.py), [fixture](../../services/ai-service/tests/enterprise_ai_processing_fixture.py) y [pruebas C01](../../services/ai-service/tests/test_enterprise_ai_processing.py).
- [SQLitePolicyStore](../../services/ai-service/app/enterprise_connectors/sqlite_store.py), [SQLiteConnectorAudit](../../services/ai-service/app/enterprise_connectors/durable_audit.py), [ControlPlane](../../services/ai-service/app/enterprise_connectors/control_plane.py), [migración existente](../../services/ai-service/app/enterprise_connectors/migrations/001_control_plane.sql), [ConnectorService](../../services/ai-service/app/enterprise_connectors/service.py) y [política A/B](../../services/ai-service/app/enterprise_connectors/policy.py).
- [Mantenibilidad M01/M02](enterprise-connector-maintainability-demo-001.md), [AGENTS](../../AGENTS.md), [handoff](../agent-handoff.md), [README](../../README.md), [producto](../PROJECT.md), [roadmap](../roadmap.md) e [índice de arquitectura](../architecture/README.md).

Verificación de esta revisión: Git confirma el commit funcional C01 aprobado como ancestro de `origin/main`, integrado por **PR #116**. Los SHA y el estado de ramas se consultan en cada sesión; no son configuración permanente del diseño. El handoff conserva una descripción histórica de C01 en revisión; se contrasta con Git, sin modificarlo en esta fase.

Hechos relevantes del código, no capacidades supuestas:

| Componente actual | Consecuencia para C02 |
|---|---|
| C01 es puro; `AIProcessingDecision` contiene ocho campos, sin grant seleccionado, lease ni texto | Reutilizarlo; no tratar el resultado ni su ID de operación como autoridad ejecutable |
| `ProcessingBoundary` reconoce objetos exactos de snapshots/envelope/evidencia; identidad sigue en A/B | La composición de test C02 debe reconocer sus objetos originales; filas reconstruidas no emiten identidad |
| El owner C01 liga operación/contexto/request exacto/bytes/correlación | No reasociar un recibo por UUID, longitud o coincidencia estructural; conservar las regresiones del fix C01 |
| C01 limita grants/perfiles a tuplas de hasta 32 y revisiones/versiones a 1..1.000.000 | El store nuevo debe producir esas proyecciones; no cargar ilimitadamente ni cambiar C01 para ampliar capacidad |
| SQLitePolicyStore valida DDL exacto, contrato/checksum, FKs y auditoría; writer `BEGIN IMMEDIATE`, WAL y timeout acotado | Añadir tablas C al archivo existente lo invalidaría; store C y migración independientes |
| SQLiteConnectorAudit admite solo fases del conector | No extender sus enums, tablas o productores con eventos C |
| ConnectorService devuelve documento después de B y audit; C/D siguen rechazados | Adquisición solo por su API pública; C02 no entrega al humano, no modifica servicio ni cuatro nodos LangGraph |

Los 192 C01 y 617 regresiones/una omisión son **evidencia histórica de C01**, no pruebas nuevas de C02. En esta fase no se ejecutan suites funcionales.

## 2. Arquitectura mínima y límites

```text
Fixture confiable y owner efímero
  -> gateway empresarial
       -> evaluador C01 + puertos A/B públicos + reconocimiento de fuente
       -> ledger C (snapshots, CAS, reserva, consumo y audit atómicos)
            -> implementación SQLite C propia, solo metadata
       -> fake fijo (entrada de un uso; procesamiento sin transacción)
       -> finalización durable y eliminación de referencias
  <- resultado técnico sin documento, pregunta, candidato ni respuesta humana
```

Se conservan seis autoridades separadas de DESIGN-001. Ningún SQL, conexión, cursor, PRAGMA, estado de SQLite o ORM llega al evaluador, fake, gateway ni futuro LangGraph. El gateway entiende operaciones de dominio con CAS, no `BEGIN`/`COMMIT`. No callback de proveedor/red dentro de una transacción; el adaptador SQLite no ve contenido.

Propuesta de **cuatro módulos Python nuevos** dentro de `app/enterprise_ai_processing`, una migración propia futura y un fixture/suites propios; son rutas candidatas, **no archivos creados**:

| Módulo candidato | Responsabilidad mínima |
|---|---|
| `execution_types.py` | Owner, lease opaca, metadata cerrada, estados/resultados técnicos y dos puertos pequeños |
| `gateway.py` | Preparación, invocación única, frontera de entrada y finalización/cleanup; sin SQL ni resolución de scopes |
| `fake_model.py` | Único fake admitido, síncrono y acotado; extracción dependiente de la entrada, sin herramientas ni persistencia |
| `sqlite_ledger.py` | Persistencia C, CAS, auditoría, inicialización explícita y administración sintética reconocida; no payloads |

No crear repositorio genérico por tabla, unit-of-work público, factory universal de modelos, bus de eventos, nuevo microservicio ni segundo evaluador. Inicialmente `ProcessingExecutionLedger` y `ProcessingAuditSink` son **un mismo backend transaccional**: separar sinks obligatorios rompería atomicidad reserva/intent/audit. Una consulta de auditoría es otro permiso del mismo ledger, no una segunda escritura asíncrona. Separar archivo administrativo solo si su tamaño/riesgo lo justifica al implementar, no por anticipación.

### Puertos de dominio candidatos

Firmas conceptuales, no código ejecutable:

| Operación | Entrada / salida / atomicidad |
|---|---|
| `load_policy(authority)` | Snapshot C01 completo y revisionado, leído consistentemente; DTO inmutable, sin conexión expuesta |
| `reserve(owner_metadata, selection, expected_revision)` | CAS de revisión/versiones + slot + fila de intento/lease + cuatro eventos previos, en una transacción; lease solo después de commit confirmado |
| `consume(consume_metadata, expected_attempt_version, expected_revision)` | Tras reconocimiento efímero del gateway, comparación durable exacta + CAS ISSUED→CONSUMED; commit antes de entrar al fake |
| `observe_entry` / `finish` / `abort_before_entry` | Transiciones cerradas y sus eventos en la misma transacción; ninguna acepta texto ni una excepción |
| `change_policy(admin, change, expected_revision)` | Cambio de perfil/grant/exención, incremento de revisión y audit administrativo atómicos |
| `read_audit(auditor, cursor, limit)` / `reconcile(admin, metadata)` | Solo ámbito reconocido; reconciliar no reemite leases ni devuelve resultados |

No métodos `get_result(operation_id)`, reanudar, ejecutar por ID, SQL arbitrario ni recuperación de capacidades. `owner_metadata`/`selection`/`consume_metadata` no son argumentos públicos: solo comandos cerrados emitidos por esta composición reconocida del gateway. Reconocer owner/lease es responsabilidad del gateway antes de emitirlos; el backend recibe únicamente metadata, nunca el owner con contenido ni objetos arbitrarios del solicitante. El permiso de invocar comandos del ledger también se fija en la composición confiable, no se obtiene con IDs conocidos. `StoreUnavailable`, `RevisionConflict`, `BudgetDenied` y `InvalidAuthority` serán categorías cerradas, sin SQL/path/error crudo hacia arriba.

## 3. Reutilizar C01 sin otra fuente de verdad

El store C es la única fuente durable nueva de perfiles/grants; objetos C01 son **proyecciones temporales**, no configuración paralela ni caché de ALLOW. No se importan helpers privados de C01 ni de ConnectorService.

Problema real: C01 no expone qué grant satisfizo la evaluación. Solución propuesta sin modificarlo: ordenar los candidatos propios por ID, construir para cada uno una proyección confiable `AIProcessingPolicy` con **un solo grant completo**, misma revisión y perfiles actuales, y llamar C01. La frontera de test reconoce temporalmente cada proyección original derivada de esa lectura; el solicitante no puede registrarla. El primer ALLOW fija ese grant/versionado y su expiración. No copiar sus filtros internos, combinar parciales ni inferir el grant a partir de una decisión global. Hasta 32 candidatos, sin consultas/modelos por candidato; retirar las proyecciones al terminar.

Antes de reservar/consumir: snapshots A/B frescos por sus puertos públicos, evidencia original reconocida y permiso externo **solo simulado**, revisión C actual y nueva evaluación C01. Si la revisión C cambia entre lectura y escritura, el CAS falla: no reconfigurar silenciosamente el envelope, no renovar vigencia y no reintentar inferencia. Un perfil/grant distinto requiere una operación nueva aprobada por frontera, no reparar una lease.

El grant C guarda referencias de principal/instancia/tenant/recurso ya existentes, **no nuevas identidades**. No existen FKs entre archivos SQLite: C01/A/B verifican esas referencias contra el snapshot del conector. C02 no cambia IdentityBoundary, modelos C01, store A/B, IAM ni esquema clínico.

## 4. Esquema SQLite V1 propuesto — cinco tablas

**DDL completo propuesto, no ejecutado.** Identificador de esquema nuevo `enterprise-ai-processing-ledger-v1`; eventos `enterprise-ai-processing-audit-v1`. Las tablas se alojarán exclusivamente en `processing.sqlite3` bajo un directorio absoluto nuevo creado por el fixture en un basetemp propio. Ni adjuntar con `ATTACH` ni inicializar sobre archivos existentes ajenos.

Convenciones: IDs internos `SAFE_ID` 1..80 o UUID v4 canónico según campo; validados estrictamente antes de escribir y después de leer. Tiempos `*_us`: enteros UTC de microsegundos desde epoch; conversión exacta sin floats, nunca timestamp local. C01 recibe `datetime` UTC, no enteros. Límites/versiones son `int` exacto, no bool/string/float; flags SQL 0/1 se convierten explícitamente a bool. Toda nulabilidad, PK, FK, UNIQUE y CHECK está en el DDL; índices adicionales debajo. No se usan JSON/payloads genéricos ni SQL generado desde identificadores externos.

`STRICT` es una elección SQLite **justificada** para evitar almacenamiento de tipos incompatibles; requiere SQLite >=3.37 y verificación explícita de versión al implementar. No sustituye los validadores de dominio ni impide coerciones de afinidad. No `AUTOINCREMENT`, `rowid` como identidad, triggers de negocio, JSON1, tablas virtuales o columnas de contenido. Secuencia audit explícita bajo la transacción, no una capacidad.

```sql
CREATE TABLE aip_store (
    singleton INTEGER NOT NULL PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    contract TEXT NOT NULL CHECK (contract = 'enterprise-ai-processing-ledger-v1'),
    store_id TEXT NOT NULL UNIQUE CHECK (length(store_id) = 36),
    migration_checksum TEXT NOT NULL CHECK (length(migration_checksum) = 64),
    revision INTEGER NOT NULL CHECK (revision BETWEEN 1 AND 1000000),
    next_audit_seq INTEGER NOT NULL CHECK (next_audit_seq > 0)
) STRICT;

CREATE TABLE aip_profile (
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    profile_id TEXT NOT NULL CHECK (profile_id = 'fake-enterprise-extractive-v1'),
    version INTEGER NOT NULL CHECK (version BETWEEN 1 AND 1000000),
    enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
    provider TEXT NOT NULL CHECK (provider = 'fake'),
    model_id TEXT NOT NULL CHECK (model_id = 'fake-enterprise-extractive-v1'),
    model_version TEXT NOT NULL CHECK (model_version = '1'),
    destination TEXT NOT NULL CHECK (destination = 'in-process-offline'),
    classification TEXT NOT NULL CHECK (classification = 'synthetic-internal'),
    processing_purpose TEXT NOT NULL CHECK (processing_purpose = 'synthetic-policy-question-answering'),
    retention TEXT NOT NULL CHECK (retention = 'ephemeral-no-retention'),
    tokenizer TEXT NOT NULL CHECK (tokenizer = 'fake-byte-v1'),
    question_set_id TEXT NOT NULL CHECK (question_set_id = 'vacation-question-v1'),
    valid_from_us INTEGER NOT NULL CHECK (valid_from_us >= 0),
    expires_at_us INTEGER NOT NULL,
    review_due_at_us INTEGER NOT NULL,
    max_sources INTEGER NOT NULL CHECK (max_sources = 1),
    max_source_bytes INTEGER NOT NULL CHECK (max_source_bytes BETWEEN 1 AND 1024),
    max_question_bytes INTEGER NOT NULL CHECK (max_question_bytes BETWEEN 1 AND 256),
    max_input_bytes INTEGER NOT NULL CHECK (max_input_bytes BETWEEN 1 AND 2048),
    max_output_bytes INTEGER NOT NULL CHECK (max_output_bytes BETWEEN 1 AND 512),
    max_output_units INTEGER NOT NULL CHECK (max_output_units BETWEEN 1 AND 256),
    max_seconds INTEGER NOT NULL CHECK (max_seconds BETWEEN 1 AND 5),
    max_retries INTEGER NOT NULL CHECK (max_retries = 0),
    max_concurrent INTEGER NOT NULL CHECK (max_concurrent = 1),
    PRIMARY KEY (organization_id, profile_id),
    CHECK (valid_from_us < expires_at_us AND valid_from_us < review_due_at_us)
) STRICT;

CREATE TABLE aip_grant (
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    grant_id TEXT NOT NULL CHECK (length(grant_id) BETWEEN 1 AND 80),
    version INTEGER NOT NULL CHECK (version BETWEEN 1 AND 1000000),
    enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
    principal_id TEXT NOT NULL CHECK (length(principal_id) BETWEEN 1 AND 80),
    principal_type TEXT NOT NULL CHECK (principal_type = 'workload'),
    instance_id TEXT NOT NULL CHECK (length(instance_id) BETWEEN 1 AND 80),
    tenant_id TEXT NOT NULL CHECK (length(tenant_id) BETWEEN 1 AND 80),
    resource_id TEXT NOT NULL CHECK (length(resource_id) BETWEEN 1 AND 80),
    recipient_id TEXT NOT NULL CHECK (length(recipient_id) BETWEEN 1 AND 80),
    read_operation TEXT NOT NULL CHECK (read_operation = 'document.content.read'),
    read_purpose TEXT NOT NULL CHECK (read_purpose = 'synthetic-demonstration'),
    processing_operation TEXT NOT NULL CHECK (processing_operation = 'enterprise.document.answer'),
    processing_purpose TEXT NOT NULL CHECK (processing_purpose = 'synthetic-policy-question-answering'),
    classification TEXT NOT NULL CHECK (classification = 'synthetic-internal'),
    profile_id TEXT NOT NULL,
    profile_version INTEGER NOT NULL CHECK (profile_version BETWEEN 1 AND 1000000),
    approval TEXT NOT NULL CHECK (approval = 'not_required'),
    approval_ref TEXT NOT NULL CHECK (length(approval_ref) BETWEEN 1 AND 80),
    valid_from_us INTEGER NOT NULL CHECK (valid_from_us >= 0),
    expires_at_us INTEGER NOT NULL,
    review_due_at_us INTEGER NOT NULL,
    max_sources INTEGER NOT NULL CHECK (max_sources = 1),
    max_source_bytes INTEGER NOT NULL CHECK (max_source_bytes BETWEEN 1 AND 1024),
    max_question_bytes INTEGER NOT NULL CHECK (max_question_bytes BETWEEN 1 AND 256),
    max_input_bytes INTEGER NOT NULL CHECK (max_input_bytes BETWEEN 1 AND 2048),
    max_output_bytes INTEGER NOT NULL CHECK (max_output_bytes BETWEEN 1 AND 512),
    max_output_units INTEGER NOT NULL CHECK (max_output_units BETWEEN 1 AND 256),
    max_seconds INTEGER NOT NULL CHECK (max_seconds BETWEEN 1 AND 5),
    max_retries INTEGER NOT NULL CHECK (max_retries = 0),
    max_concurrent INTEGER NOT NULL CHECK (max_concurrent = 1),
    PRIMARY KEY (organization_id, grant_id),
    UNIQUE (organization_id, grant_id, profile_id),
    FOREIGN KEY (organization_id, profile_id)
        REFERENCES aip_profile (organization_id, profile_id),
    CHECK (valid_from_us < expires_at_us AND valid_from_us < review_due_at_us)
) STRICT;

CREATE TABLE aip_execution (
    organization_id TEXT NOT NULL,
    operation_id TEXT NOT NULL CHECK (length(operation_id) = 36),
    attempt_version INTEGER NOT NULL CHECK (attempt_version BETWEEN 1 AND 1000000),
    owner_ref TEXT NOT NULL CHECK (length(owner_ref) = 36),
    process_epoch TEXT NOT NULL CHECK (length(process_epoch) = 36),
    lease_id TEXT NOT NULL UNIQUE CHECK (length(lease_id) = 36),
    decision_ref TEXT NOT NULL CHECK (length(decision_ref) = 36),
    principal_id TEXT NOT NULL,
    principal_type TEXT NOT NULL CHECK (principal_type = 'workload'),
    instance_id TEXT NOT NULL,
    binding_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    read_correlation_id TEXT NOT NULL CHECK (length(read_correlation_id) = 36),
    registered_version INTEGER NOT NULL CHECK (registered_version BETWEEN 1 AND 1000000),
    content_revision INTEGER NOT NULL CHECK (content_revision BETWEEN 1 AND 1000000),
    connector_revision INTEGER NOT NULL CHECK (connector_revision BETWEEN 1 AND 1000000),
    processing_revision INTEGER NOT NULL CHECK (processing_revision BETWEEN 1 AND 1000000),
    grant_id TEXT NOT NULL,
    grant_version INTEGER NOT NULL CHECK (grant_version BETWEEN 1 AND 1000000),
    approval_ref TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    profile_version INTEGER NOT NULL CHECK (profile_version BETWEEN 1 AND 1000000),
    destination TEXT NOT NULL CHECK (destination = 'in-process-offline'),
    classification TEXT NOT NULL CHECK (classification = 'synthetic-internal'),
    read_operation TEXT NOT NULL CHECK (read_operation = 'document.content.read'),
    read_purpose TEXT NOT NULL CHECK (read_purpose = 'synthetic-demonstration'),
    processing_operation TEXT NOT NULL CHECK (processing_operation = 'enterprise.document.answer'),
    processing_purpose TEXT NOT NULL CHECK (processing_purpose = 'synthetic-policy-question-answering'),
    question_id TEXT NOT NULL CHECK (question_id = 'vacation-days-v1'),
    source_bytes INTEGER NOT NULL CHECK (source_bytes BETWEEN 1 AND 1024),
    question_bytes INTEGER NOT NULL CHECK (question_bytes BETWEEN 1 AND 256),
    input_bytes INTEGER NOT NULL CHECK (input_bytes BETWEEN 1 AND 2048),
    reserved_output_bytes INTEGER NOT NULL CHECK (reserved_output_bytes BETWEEN 1 AND 512),
    reserved_output_units INTEGER NOT NULL CHECK (reserved_output_units BETWEEN 1 AND 256),
    max_seconds INTEGER NOT NULL CHECK (max_seconds BETWEEN 1 AND 5),
    authorized_at_us INTEGER NOT NULL CHECK (authorized_at_us >= 0),
    expires_at_us INTEGER NOT NULL,
    consumed_at_us INTEGER,
    entered_at_us INTEGER,
    finished_at_us INTEGER,
    lease_state TEXT NOT NULL CHECK (lease_state IN ('ISSUED','CONSUMED','EXPIRED','REVOKED','CLOSED')),
    run_state TEXT NOT NULL CHECK (run_state IN
        ('INTENT','CONSUMED','ENTERED','COMPLETED','INVALID','FAILED','CANCELLED','TIMED_OUT','REVOKED','EXPIRED','UNKNOWN')),
    reservation_state TEXT NOT NULL CHECK (reservation_state IN ('HELD','RELEASED','CHARGED','UNCERTAIN')),
    result_code TEXT CHECK (result_code IN ('CANDIDATE','NO_EVIDENCE','INVALID','ERROR','TIMEOUT','CANCELLED','UNKNOWN','REVOKED')),
    input_units_observed INTEGER CHECK (input_units_observed BETWEEN 0 AND 2048),
    output_bytes_observed INTEGER CHECK (output_bytes_observed BETWEEN 0 AND 1000000),
    output_units_observed INTEGER CHECK (output_units_observed BETWEEN 0 AND 1000000),
    elapsed_us INTEGER CHECK (elapsed_us >= 0),
    PRIMARY KEY (organization_id, operation_id),
    FOREIGN KEY (organization_id, grant_id, profile_id)
        REFERENCES aip_grant (organization_id, grant_id, profile_id),
    CHECK (input_bytes >= source_bytes + question_bytes),
    CHECK (expires_at_us > authorized_at_us
        AND expires_at_us <= authorized_at_us + max_seconds * 1000000),
    CHECK (consumed_at_us IS NULL OR consumed_at_us >= authorized_at_us),
    CHECK (entered_at_us IS NULL OR (consumed_at_us IS NOT NULL AND entered_at_us >= consumed_at_us)),
    CHECK (finished_at_us IS NULL OR finished_at_us >= authorized_at_us),
    CHECK ((run_state = 'INTENT' AND lease_state = 'ISSUED' AND consumed_at_us IS NULL AND reservation_state = 'HELD')
        OR (run_state = 'CONSUMED' AND lease_state = 'CONSUMED' AND consumed_at_us IS NOT NULL AND reservation_state = 'HELD')
        OR (run_state = 'ENTERED' AND lease_state = 'CONSUMED' AND entered_at_us IS NOT NULL AND reservation_state = 'HELD')
        OR (run_state IN ('COMPLETED','INVALID','FAILED','CANCELLED','TIMED_OUT','REVOKED','EXPIRED','UNKNOWN')
            AND lease_state IN ('CLOSED','REVOKED','EXPIRED') AND reservation_state <> 'HELD'))
) STRICT;

CREATE UNIQUE INDEX aip_one_active_scope
    ON aip_execution (organization_id, instance_id, profile_id)
    WHERE reservation_state IN ('HELD','UNCERTAIN');
CREATE INDEX aip_execution_recovery ON aip_execution (process_epoch, run_state);

CREATE TABLE aip_audit (
    event_id TEXT NOT NULL PRIMARY KEY CHECK (length(event_id) = 36),
    audit_seq INTEGER NOT NULL UNIQUE CHECK (audit_seq > 0),
    contract TEXT NOT NULL CHECK (contract = 'enterprise-ai-processing-audit-v1'),
    timestamp_us INTEGER NOT NULL CHECK (timestamp_us >= 0),
    event TEXT NOT NULL CHECK (event IN
        ('ai_processing_evaluated','ai_processing_profile_selected','ai_processing_budget_approved',
         'ai_processing_authorized','ai_provider_invocation_observed','ai_provider_result_observed',
         'ai_processing_cancelled','ai_processing_error','ai_processing_revocation_detected',
         'ai_processing_policy_changed')),
    phase TEXT NOT NULL CHECK (phase IN ('evaluation','preparation','entry','result','cleanup','administration')),
    outcome TEXT NOT NULL CHECK (outcome IN
        ('ALLOW','DENY','UNAVAILABLE','AUTHORIZED','OBSERVED','CANCELLED','ERROR','REVOKED','CHANGED','UNKNOWN')),
    reason TEXT NOT NULL CHECK (reason IN
        ('processing_eligible_not_executable','invalid_input','identity_invalid','scope_mismatch',
         'source_evidence_invalid','processing_not_granted','classification_denied','purpose_denied',
         'profile_denied','destination_denied','retention_unverified','approval_required',
         'policy_changed','authorization_expired','budget_exceeded','authority_unverifiable',
         'provider_unavailable','provider_result_invalid','audit_unavailable','cancelled','internal_failure',
         'accepted','lease_invalid','execution_unknown','deadline_exceeded','revision_conflict')),
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('anonymous','workload','synthetic_administrator')),
    actor_ref TEXT,
    organization_id TEXT,
    operation_id TEXT,
    decision_ref TEXT,
    read_correlation_id TEXT,
    instance_id TEXT,
    resource_id TEXT,
    grant_id TEXT,
    grant_version INTEGER CHECK (grant_version BETWEEN 1 AND 1000000),
    profile_id TEXT,
    profile_version INTEGER CHECK (profile_version BETWEEN 1 AND 1000000),
    connector_revision INTEGER CHECK (connector_revision BETWEEN 1 AND 1000000),
    previous_revision INTEGER NOT NULL CHECK (previous_revision BETWEEN 0 AND 1000000),
    revision INTEGER NOT NULL CHECK (revision BETWEEN 1 AND 1000000),
    attempt_version INTEGER CHECK (attempt_version BETWEEN 1 AND 1000000),
    lease_ref TEXT,
    input_units INTEGER CHECK (input_units BETWEEN 0 AND 2048),
    output_units INTEGER CHECK (output_units BETWEEN 0 AND 1000000),
    entity_kind TEXT CHECK (entity_kind IN ('store','profile','grant','execution')),
    entity_ref TEXT,
    CHECK ((actor_kind = 'anonymous' AND actor_ref IS NULL AND organization_id IS NULL
        AND operation_id IS NULL AND decision_ref IS NULL AND read_correlation_id IS NULL
        AND instance_id IS NULL AND resource_id IS NULL AND grant_id IS NULL AND grant_version IS NULL
        AND profile_id IS NULL AND profile_version IS NULL AND connector_revision IS NULL
        AND attempt_version IS NULL AND lease_ref IS NULL AND input_units IS NULL
        AND output_units IS NULL AND entity_kind IS NULL AND entity_ref IS NULL)
        OR (actor_kind <> 'anonymous' AND actor_ref IS NOT NULL AND organization_id IS NOT NULL)),
    CHECK ((event = 'ai_processing_policy_changed' AND outcome = 'CHANGED'
        AND actor_kind = 'synthetic_administrator' AND revision = previous_revision + 1)
        OR (event <> 'ai_processing_policy_changed' AND revision = previous_revision))
) STRICT;

CREATE INDEX aip_audit_org ON aip_audit (organization_id, audit_seq);
CREATE INDEX aip_audit_operation ON aip_audit (organization_id, operation_id, audit_seq);
CREATE UNIQUE INDEX aip_policy_change_revision ON aip_audit (revision)
    WHERE event = 'ai_processing_policy_changed';
```

### Integridad y responsabilidad por tabla

| Tabla | Revisión, ámbito, referencias y transacciones |
|---|---|
| `aip_store` | Una fila, revisión global coherente con C01; `next_audit_seq` avanza solo al append confirmado. Inicialización y cambios administrativos; no incrementar revisión C por consumo/audit, para no revocar operaciones por observación |
| `aip_profile` | PK organización/perfil; versión aumenta por CAS, nunca se borra/reasigna organización. Una pregunta canónica resuelta desde `question_set_id` estático; no texto de pregunta en DB. Solo administración con audit |
| `aip_grant` | Grant completo con FK de perfil en la misma organización; `profile_version` es pin comprobado por C01, no FK a una versión mutable. `approval_ref` identifica exención sintética incorporada al grant/versionado/vigencia, no aprobación humana ni entidad administrable independiente. Solo administración con audit |
| `aip_execution` | Una fila reúne reserva + lease + intento + resultado metadata; PK organización/operación, lease única y slot activo único. Versiones guardadas son evidencia histórica, no permisos actuales. No FK por versión a filas de política mutables. Reserva/consumo/entrada/finalización/reconciliación mediante CAS de `attempt_version` |
| `aip_audit` | Append-only por puerto; IDs ya resueltos del ámbito propio, sin FK a intentos porque también registra denegaciones previas a una reserva. No update/delete del audit en el puerto. Revisión administrativa única, secuencia serializada por backend y consultas por organización; no log inviolable |

No índices adicionales de grants: máximo 32 por proyección; medir antes de optimizar. Los índices parciales evitan una sexta tabla de slots y funcionan también como concepto en PostgreSQL, pero su comportamiento concurrente debe volver a probarse. No hard delete de política o intentos; revocar/deshabilitar conserva referencias históricas. `grant.profile_id` no se modifica una vez referenciado; otro perfil requeriría nuevo grant. No declarar borrado/archivo ni retención de audit productivos: requieren política futura.

Reglas cruzadas no expresables por CHECK local se validan en el ledger **antes de cada commit y al leer**: transiciones de la sección 7; `entered_at_us` nunca en INTENT/CONSUMED; terminal exige `finished_at_us`; COMPLETED exige observación de entrada, resultado válido y unidades conocidas; RELEASED solo si se prueba no entrada; CHARGED solo si terminó la llamada, UNCERTAIN en ambigüedad. Al admitir/consumir/entrar se exigen además límites medidos <= mínimo grant/perfil/envelope/conector, perfil/approval/versiones actuales exactos y expiración válida. Los pins históricos no se comparan con la versión vigente para declarar corrupto el historial: un cambio legítimo revoca trabajo nuevo/en curso observado, no reescribe los hechos anteriores. Fallo de integridad → UNAVAILABLE, no corregir filas silenciosamente. Las cifras observadas pueden superar el presupuesto al detectar un resultado inválido; nunca se convierten en autorización para ese tamaño.

**Datos prohibidos en las cinco tablas:** contenido, pregunta libre, prompt, respuesta, citas/fragmentos, digest de documento/pregunta, JWT/token/hash de token, keys, cookies, credenciales, URLs, nombres personales, errores/tracebacks o paths internos. `question_id`, owner/lease/decision refs son metadata de fixture, no prueba de posesión ni material secreto. Ni esos IDs ni una consulta audit reconstruyen bytes o autoridad.

### Inicialización y seguridad del archivo

Futura migración propia `enterprise_ai_processing/migrations/001_processing_ledger.sql`, no creada ahora. Inicializar solo con autoridad de fixture reconocida, creación exclusiva de archivo inexistente bajo raíz test-owned; rechazar rutas relativas/alias, symlinks/junctions/hard links y archivos clínicos/IAM/conector. Raíz y todos los componentes deben verificarse; no modificar ACL ni intentar reparar `.pytest-tmp`. No SQLite `:memory:` como fallback de durabilidad.

SQLite-specific justificado: WAL para lectores mientras un escritor corto confirma; `foreign_keys=ON` por conexión; `trusted_schema=OFF`; lectores `query_only`; `BEGIN IMMEDIATE` para serializar CAS/slot/audit y evitar upgrade tardío del writer; busy timeout inicial propuesto 100 ms y admisión de conexiones acotada (cuatro). Contención falla cerrado, sin ampliar timeout ni repetir ejecución. No copiar el `ContextVar` reentrante del store A/B: cada comando C posee su transacción, sin transacción ambiente pública ni administración reentrante. No `ATTACH` ni red en un guard.

Validar versión SQLite, contrato, DDL/tablas/índices exactos, checksum normalizado LF **de esta migración nueva**, FKs e integridad; no normalizar ni editar migraciones históricas. Inicialización y evento administrativo de revisión 1 en una transacción; si falla, no publicar store válido. Un archivo propio incompleto se pone fuera de servicio, no se adopta ni borra automáticamente. Reabrir un esquema exactamente válido es no-op de inicialización, no duplica eventos; desconocido/alterado falla cerrado. Proponer `application_id`/`user_version` solo como marcas redundantes del backend, nunca autoridad suficiente. No ejecutar PRAGMAs o DDL durante esta fase.

## 5. Administración sintética y políticas

Única composición habilitada: fixture aislado, un proceso coordinador por store C y emisor de test dueño de contextos administrativos/auditores por organización. Reconocer objeto exacto, tipo cerrado, rol, organización y expiración; constructor/copy/deepcopy/JSON/etiqueta CLI/JWT no conceden autoridad. No endpoints, CLI de administración ni bootstrap desde una sesión humana existente. Un auditor no modifica políticas ni reconcilia.

`change_policy` verifica autoridad fuera y dentro de su admisión local, carga revisión esperada, valida tipos C01 y ámbito completo, actualiza filas/versiones, incrementa revisión global una vez y escribe `ai_processing_policy_changed` en la misma transacción. El cambio de perfil no actualiza grants automáticamente: el pin antiguo deniega hasta revisión explícita del grant. No resetear revisiones al reiniciar; al alcanzar el límite C01, UNAVAILABLE y revisión del contrato, no wraparound.

La revisión global C01 implica invalidación conservadora: un cambio administrativo legítimo en B puede invalidar un envelope/lease A con revisión anterior, aunque no altere sus grants. No es mezcla de permisos/contenido; tampoco independencia de disponibilidad por organización. Mantener esa semántica en C02, probarla explícitamente y evaluar revisiones por organización en la etapa PostgreSQL con cambio de contrato aprobado, no ocultarla con auto-refresh.

Límite administrativo de laboratorio: 32 grants y 32 perfiles por snapshot, perfiles fake fijos, máximo una reserva activa por organización/instancia/perfil y caps de sección 8. No contador diario/mensual, dinero ni cuota comercial nueva. La exención `not_required` se administra con el grant; approval requerida/humana no está soportada y deniega, no se fabrica un aprobador. Cambios rechazados no incrementan revisión: evento de evaluación/error sanitizado en transacción separada solo si el sink funciona. Fallo del commit de cambio → nada se considera aplicado; confirmación ambigua → UNAVAILABLE y comprobación metadata por administrador, jamás éxito supuesto.

## 6. Lease y owner: autoridad que no sale del proceso

Una lease runtime opaca, no serializable y sin contenido en repr; registro **por instancia de gateway**, nunca global, con referencia fuerte al objeto exacto. Owner creado vacío dentro de `try` exterior y luego ligado a envelope/source originales, contexto reconocido y bytes/pregunta canónicos. La lease liga privadamente owner/operación/organización/principal, request A/B, fuente y ambas versiones, decisión C01 conservada, grant/versionado/exención, perfil/destino, pregunta exacta, límites, revisiones y expiración mínima. No confiar en dataclass frozen ni en digests/UUID conocidos como autoridad.

En DB solo metadata de esa vinculación; ni fila, ID, copia, token ni historial audit pueden emitir la lease. La pregunta se liga en memoria por sus bytes reales, no solo por `question_id`. El source se revalida contra owner y entrada preparada; cambiar bytes aun del mismo tamaño deniega. La decisión C01 retenida se compara con su envelope y revisión; `decision_ref` es una referencia nueva de trazabilidad, no un campo inventado dentro del objeto C01.

Consumo requiere **ambos controles**: objeto y owner exactos todavía registrados + CAS SQL `(organization_id, operation_id, attempt_version, lease_state=ISSUED, revisión vigente, no vencida)`. Un affected-row distinto de uno deniega/no disponible según causa, nunca invoca. La fila se modifica y confirma antes del fake; dos consumidores no pueden confirmar ese CAS sobre la misma versión. Tras consumir se retira el permiso de repetir, incluso si falla la invocación o el commit queda ambiguo.

Tras reinicio no existen los owners/leases reconocidos: reapertura permite consultar/reconciliar metadata pero **no reconstruir ni consumir capacidades**, tampoco para INTENT durable no consumido. Ninguna recuperación automática por operación, de fuente/pregunta o de resultado. UUID `process_epoch` identifica arranque para diagnóstico, no autentica al proceso.

## 7. Estados, reservas e incertidumbre

| Estado durable | Lease / reserva | Significado y transición permitida |
|---|---|---|
| INTENT | ISSUED / HELD | Autorización, reserva e intent confirmados; no demuestra entrada. Puede consumir, expirar o revocarse |
| CONSUMED | CONSUMED / HELD | Derecho a una entrada retirado; aún no se prueba ejecución. Nunca volver a ISSUED |
| ENTERED | CONSUMED / HELD | Observación durable de entrada real al fake; no resultado completo ni entrega |
| COMPLETED | CLOSED / CHARGED | Resultado técnico válido observado y finalización confirmada; no grounding ni respuesta humana |
| INVALID / FAILED | CLOSED / CHARGED o UNCERTAIN | Resultado rechazado o fallo; consumo conocido se conserva; duda de uso queda incierta |
| CANCELLED / TIMED_OUT | CLOSED / CHARGED o UNCERTAIN | Señal/deadline observados; no prueba universal de detención. Antes de entrada demostrable puede RELEASED |
| REVOKED / EXPIRED | REVOKED o EXPIRED / RELEASED, CHARGED o UNCERTAIN | Detectado antes de entrada: cero fake y liberar solo con prueba; después: no deshacer consumo |
| UNKNOWN | CLOSED / UNCERTAIN | Ventana de crash/commit no verificable; sin replay ni liberación por TTL |

Transiciones terminales no retornan a estados ejecutables. Reconciliación de UNKNOWN puede cerrar la reserva como CHARGED (peor caso) tras confirmar que ningún owner/worker de esa ejecución sigue vivo; conserva `run_state=UNKNOWN`, sin inventar resultado. Es una operación administrativa propia con audit, no reembolso automático. Una operación nueva de otro ID todavía requiere nueva autorización y presupuesto; no replay encubierto.

Reservar input medido y techos de salida antes de la entrada, un slot por `(organización, instancia, perfil)`. HELD y UNCERTAIN impiden otra reserva del mismo ámbito. No liberar automáticamente al vencer la lease si hubo entrada o posibilidad de ella. Sin entrada comprobada, abortar libera; con resultado observado conservar unidades medidas; desconocido conserva exposición máxima reservada y bloquea slot hasta reconciliación. CHARGED registra consumo histórico, no descuenta un saldo comercial inexistente. No hay préstamos de cuota entre organizaciones.

## 8. Gateway y fake propuestos

`prepare(owner)` devuelve solo la lease interna reconocida después de intent durable. `invoke_once(owner, lease)` produce metadata cerrada de finalización o propaga la cancelación primaria; no acepta provider/modelo/SQL ni una decisión aportada por el solicitante. No devuelve contenido ni candidato al usuario en C02. C03 tendrá que aprobar por separado el traspaso efímero y B/C finales; no exponer ahora una API de resultados para anticiparlo.

Única configuración: perfil/modelo `fake-enterprise-extractive-v1`, versión `1`, provider `fake`, destino `in-process-offline`; sin factories/SDK/keys/settings clínicos. Una fuente UTF-8 <=1024 bytes y pregunta exacta allowlisted <=256. Preparación posterior a C inicial, luego **segunda evaluación** y medición de la entrada entera antes de reservar: instrucciones fijas versionadas, delimitación/framing, pregunta y metadata realmente visibles, además del documento; máximo 2048 bytes/unidades `fake-byte-v1`. No truncar ni declarar overhead cero. El ID de pregunta es una proyección de la pregunta original reconocida, no sustitución de bytes en el presupuesto.

Salida total serializada <=512 bytes **y** <=256 unidades fake; se aplica el menor límite (un byte UTF-8 por unidad). Tiempo UTC absoluto nunca posterior a C01 y hasta cinco segundos desde emisión, más reloj monotónico inyectable para medir duración dentro del proceso; no persistir un monotonic timestamp para reutilizarlo tras reinicio. Cero retries. Todos los techos son el mínimo de envelope, grant único, perfil y límites aplicables del conector; nunca elevar caps para pasar una prueba.

Fake síncrono sin sockets/HTTP/DNS/herramientas/callbacks externos/training/cache/retención/streaming/threads de fondo. Contrato mínimo: recibe únicamente owner reconocido de entrada ya sellada, devuelve categoría CANDIDATE/NO_EVIDENCE y fragmento/offsets efímeros acotados **derivados de esos bytes**, no del nombre de escenario. Propuesta de extracción acotada de una cláusula sintética de vacaciones con días y antigüedad; sin cláusula completa, NO_EVIDENCE, no número inventado del documento actual. C03 decidirá grounding/plantilla final; C02 solo valida esquema/tamaño/uso. Modificar la cláusula debe cambiar el candidato o invalidar la versión. No afirmar robustez de un LLM real.

Contadores técnicos por owner/instancia de fake, sin payload y no globales: número real de entradas a la función (máximo uno), procesamiento iniciado, bytes/unidades reales de entrada y salida, inicio/fin monotónicos y categoría cerrada. Errores/oversize/timeout/cancelación mediante dobles test-owned y Events/reloj inyectado; esos hooks no son opciones del solicitante ni nuevas rutas. No enviar llamadas a otro fake/proveedor como fallback. Un timeout se detecta en checkpoints acotados antes/durante/después; no usar executor de fondo ni afirmar preempción de un thread bloqueado.

## 9. Orden transaccional y frontera de entrada

| Paso | Hecho / transacción |
|---|---|
| P0 | Reconocer owner, contexto y fuente originales; cargar snapshots; C01 por grant completo, sin side effects |
| P1 | Preparar/sellar input efímero completo y medirlo; C01 fresco; rechazos con audit minimizado, cero fake |
| T1 reserve | CAS C/versiones + slot + INTENT/ISSUED/HELD + eventos evaluación, perfil, presupuesto e intent, **un commit**. Solo después registrar lease runtime |
| P2 | Bajo admisión local coordinada: C01/A/B y permiso simulado frescos, bytes/pregunta/perfil/expiry iguales; ninguna renovación |
| T2 consume | CAS ISSUED→CONSUMED y versión de intento +1, revisión/tiempo actuales; confirmar; fallo/ambigüedad no entra al fake |
| P3 entrada | Último chequeo de vigencia/owner y admisión; la función fake cruza su frontera real, incrementa contador; no hay transacción abierta |
| T3 observe | **Después** de observar esa entrada: ENTERED + `ai_provider_invocation_observed`, commit corto. Se ejecuta en el prólogo confiable antes de procesamiento; fallo impide procesar y deja incertidumbre si no pudo persistir |
| P4 | Soltar barrera de admisión y toda conexión/lock SQLite antes de procesar; fake acotado procesa una vez |
| P5/T4 finish | Medir/validar resultado, C01/revisiones/expiry otra vez; resultado observado + finalización/reserva y eventos correspondientes en una transacción; suprimir todo payload al fallar |
| finally | Close y clear independientes; retirar lease, owner y aliases propios; nunca entrada alternativa ni recuperación automática |

**Corrección del flujo conceptual:** no registrar «invocación observada» antes de llamar. T2 es consumo durable, no entrada. T3 solo existe si el prólogo de la función realmente fue alcanzado; el fallo de T3 no produce un evento ficticio ni hace que el contador de entrada vuelva a cero. Puede haber contador 1 y ningún procesamiento realizado. El intent siempre antecede incluso a esa entrada.

### Punto de entrada y límite que requiere decisión del PO

No hay atomicidad automática entre commit T2, liberación del writer y llamada Python. Para el laboratorio se propone una **barrera de admisión de proceso, compartida por todos los mutadores autorizados de la composición**: C admin, invocaciones y cambios simulados A/B/fuente. Orden único barrera → comandos C → llamadas públicas A/B, sin adquisición inversa ni reentrada administrativa. El prólogo fijo del fake verifica el permiso de entrada, reloj y owner y completa T3; libera la barrera antes de procesar. Esta señal interna acotada no es callback externo ni herramienta/modelo administrable.

Un cambio autorizado confirmado antes de entrar debe preceder al chequeo bajo esa barrera y bloquear la llamada; después de entrar puede cambiar durante P4 y se detecta al finalizar. Writers usan conexiones independientes para demostrar commit durante P4, no durante la admisión. Si otro coordinador/proceso intenta abrir el store C para ejecución simultánea, **no está soportado**: la composición debe asegurar un único dueño por archivo; no confiar en `process_epoch` como lock de proceso.

Mecanismo candidato concreto, sujeto a aprobación: sidecar vacío `processing.owner` en la misma raíz test-owned, con lock exclusivo de sistema operativo mantenido por el coordinador toda su vida (implementación privada Windows/POSIX con biblioteca estándar). No basta crear un marcador o guardar un PID: otro proceso debe fallar al adquirir el lock; su liberación tras muerte permite reapertura administrativa, nunca replay. Validar alias/propiedad del sidecar igual que el archivo SQLite, no usar un path global ni modificar ACL. Este lock de propiedad no es una transacción ni congela writers que accedan por fuera del protocolo; el writer de prueba durante P4 usa otra conexión del coordinador autorizado. Sin exclusividad aprobada y pruebas de segundo proceso/muerte/cierre, no habilitar el gateway. No se crea sidecar ni lock en esta fase.

**Los puertos A/B existentes y SQLite no prueban que todos sus writers externos respeten esa barrera.** Revocación de un writer que la omite puede confirmar entre la última lectura y P3; un simple recheck no elimina esa carrera. Por ello la propuesta exige que el PO apruebe explícitamente este alcance de laboratorio coordinado o solicite otro protocolo antes de implementar. Pruebas de writers no coordinados deben reproducir/documentar el límite, no marcar garantía global PASS. No modificar control plane/IdentityBoundary ni añadir un bypass para simular atomicidad. Si se exige cubrir cualquier writer independiente antes de la entrada física, el protocolo queda **bloqueado** hasta diseño adicional aprobado.

Ninguna transacción SQLite durante procesamiento del fake; la pequeña T3 precede al procesamiento y no ejecuta extracción/modelo dentro del lock. No confundir «función alcanzada», «procesamiento iniciado» y «resultado completo». Las ventanas `T_auth`/`T_ext` y la entrega conjunta de C03 permanecen pendientes según DESIGN-001, no resueltas por esta barrera.

## 10. Auditoría durable y consultas

Vocabulario de diez eventos C02 del DDL, aditivo y separado de todos los sinks existentes. Parejas válidas, además de los CHECK: evaluación/evaluation con ALLOW-DENY-UNAVAILABLE; perfil y presupuesto/preparation con ALLOW; autorizado/preparation con AUTHORIZED; entrada/entry con OBSERVED; resultado/result con OBSERVED o UNKNOWN; cancelación/cleanup con CANCELLED; error/cleanup con ERROR o UNKNOWN; revocación/result o cleanup con REVOKED; cambio/administration con CHANGED. Validador de evento exige estas parejas exactas, tipos y refs del ámbito; no aceptar cualquier combinación del producto cartesiano SQL.

T1 persiste los cuatro eventos previos con la reserva; T3 entrada observada; T4 resultado y cualquier cancelación/error/revocación realmente observados, sin borrar el hecho previo. C01 se reevalúa antes de consumo y al terminar: registrar también esas evaluaciones mediante append transaccional en T2/T4, con la misma semántica. Si se rechaza antes de T1, transacción de audit sola; si falla, UNAVAILABLE sin modelo ni memoria fallback. Ningún log local sustituye un commit requerido.

La atribución se obtiene de una frontera confiable reconocida y registro propio, no del string `organization_id` del input. Si no puede demostrarse, anonymous sin refs. Para una identidad A reconocida que pide B: actor A y únicamente refs propias ya resueltas; omitir identificadores de B, incluso en denegaciones administrativas. No replicar `_event` privado del servicio: nuevo validador de atribución minimizado del fixture, no un evaluador de grants A/B. Sink caído: diagnóstico fijo, cero evento persistido inventado.

`read_audit` exige auditor sintético reconocido, organización fijada por su autoridad, cursor interno validado y limit 1..100; el solicitante no selecciona otra organización. Consultas SQL siempre parametrizadas. No endpoint ni dump global; audit anónimo queda para custodio del fixture, no visible a auditores de una organización. No exponer secuencia global/counters ajenos como mecanismo de enumeración. `ai_answer_evidence_validated` y `ai_final_delivery_decided` permanecen definidos por el contrato de diseño para C03, **no admitidos ni emitidos en este esquema C02 V1**; su incorporación exigirá una migración nueva aprobada.

## 11. Fallos y estados seguros

Regla para toda fila: ningún contenido vuelve al usuario en C02 y **ningún reintento automático de la operación**. Una transacción abortada no significa que deba ejecutarse otra inferencia. Sin acceso al sink no se puede afirmar que UNKNOWN ya se escribió: el registro puede quedar en su último estado confirmado y clasificarse como UNKNOWN al recuperar.

| Situación | Se sabe / no se sabe | Persistencia y reserva seguras |
|---|---|---|
| Caída antes de T1 | No intent durable bajo este protocolo; no entrada autorizada | Sin intento o solo denegación confirmada; cero fake permitido |
| Caída durante T1 | Commit puede no confirmarse al caller | Reabrir para inspección: ausencia o INTENT; ninguna lease reemitida; duda conservadora |
| Caída después de T1 | Intent existe; no observación de entrada | INTENT huérfano clasificado UNKNOWN al recuperar; HELD pasa UNCERTAIN, sin inferir «no ejecutado» |
| Caída después de T2 | Consumo confirmado, entrada todavía incierta | CONSUMED → UNKNOWN/UNCERTAIN; nunca ISSUED |
| Caída justo antes de P3 | Proceso vivo puede saber que no entró; reinicio no puede reconstruir ese conocimiento | Abort vivo probado libera; huérfano/ambigüedad conserva UNKNOWN |
| Caída en prólogo/T3 | Puede haberse alcanzado la función sin procesamiento | Última fila CONSUMED o ENTERED; UNKNOWN/UNCERTAIN, no inventar observación |
| Caída durante P4 | Entrada puede estar confirmada; resultado no | ENTERED huérfano → UNKNOWN/UNCERTAIN |
| Resultado obtenido, T4 no iniciado | Conocimiento solo volátil | Al perderlo no hay COMPLETED durable; UNKNOWN, candidato retirado |
| Fallo/commit ambiguo de T4 | Puede haber resultado confirmado o solo ENTERED | UNAVAILABLE al caller; inspección metadata posterior, no devolver ni recalcular resultado |
| Cancelación antes de entrada | Cero fake si el owner vivo lo prueba | CANCELLED/RELEASED + audit si sink funciona; misma señal primaria |
| Cancelación después de entrada | Hubo posible uso; detención solo si el fake síncrono confirma que salió | CANCELLED/CHARGED si conocido; de otro modo UNCERTAIN, nunca reembolso automático |
| Timeout | Deadline excedido no prueba detención de código arbitrario | TIMED_OUT/CHARGED o UNCERTAIN; cero workers adicionales |
| Contención SQLite | No se obtuvo commit requerido en tiempo acotado | UNAVAILABLE; preentrada cero procesamiento, posterior sin salida; no subir timeout |
| Error de integridad/esquema | Autoridad no verificable | UNAVAILABLE; no adoptar, resetear, reparar ni reemplazar store |

Reapertura primero valida esquema y luego reconcilia intentos de un proceso definitivamente terminado, sin reconstruir owners. La exclusividad del coordinador impide declarar huérfana una ejecución todavía viva. Reconciliación escribe eventos de error/UNKNOWN reales y conserva el historial; no genera eventos de resultado ni cambia UNKNOWN por COMPLETED sin evidencia durable.

## 12. Revocación, concurrencia y referencias sensibles

Retiro de grant/perfil/exención, revisión C/A/B, clasificación/revisión/bytes de fuente o expiración detectados antes de entrada: abortar, cero fake. Durante procesamiento: no retractar bytes ya vistos; registrar detección al terminar, descartar candidato y no permitir otro intento con la misma lease. No renovar contexto, pregunta o deadline. C02 no entrega respuestas y no implementa la supresión B/C del destinatario final de C03.

Events en tests sincronizan antes de T1, después de T1, antes de P3, durante P4 y antes de T4; reloj inyectado prueba igualdad exacta de expiración. Misma organización/instancia/perfil: segundo slot falla; ORG-A/ORG-B con IDs externos idénticos no comparten slot, fuente, lease o consulta audit. Cancelar A no cierra ni limpia owner B. Ledger CAS + índice único protegen reserva/consumo; no afirmar concurrencia distribuida por eso.

Contenido permanece solo en owner explícito `repr=False`, sin registro global, callbacks/tracing/config heredada ni LangGraph/checkpointer. Helpers sensibles reciben owner, no copias de payload por argumentos; aliases locales se retiran en `finally` y se evitan closures con inputs. Cierre de conexiones/recursos propios de cada comando y lease, y clear de datos, se intentan independientemente. Un owner no cierra el ledger compartido, barreras o lock de propiedad del coordinador, ni conexiones de B; el fixture los retira solo al terminar todas sus operaciones. `CancelledError`/`KeyboardInterrupt` originales se propagan aunque cleanup falle; notas secundarias fijas, sin errores que capturen payload. Sin `frame.clear`, `f_locals`, GC/introspección, limpieza cruzada o promesa de borrado criptográfico.

**Gate bloqueante de retención:** conservar tracebacks, cause/context/groups y excepciones primarias/secundarias; examinar que frames/owners propios ya no retienen canarios de input/candidato mientras otro owner sigue intacto. También fallos de store.close y clear, con cancelación concurrente. Python puede retener parámetros/temporales en frames de dependencias; `repr=False`/poner owner a None no lo soluciona por sí solo. Si la estrategia explícita no supera esas pruebas, detener implementación/publicación y volver al PO; no importar ni ampliar el scrub M01. Copias retenidas deliberadamente por el caller/host están fuera de esta garantía.

## 13. Matriz de aceptación futura — todo PLANNED

Ninguna fila siguiente es PASS ni prueba ejecutada en Phase A.

| ID | Positiva y contraprueba obligatorias | Evidencia esperada / amenazas |
|---|---|---|
| C02-01 | C válido + intent confirmado → exactamente una entrada y resultado; C DENY/UNAVAILABLE → cero | Contador real, secuencia audit, sin texto; AI-T03/08/15 |
| C02-02 | Lease/owner exactos consumen; copia/deepcopy/JSON/ID, otra operación, otra fuente o restart no | CAS, contador <=1, dos consumidores con Events; AI-T11/15 |
| C02-03 | Perfil fake exacto; modificar provider/modelo/destino/retención/key/env no habilita fallback | Cero invocación alternativa ni imports clínicos; AI-T03/05/13/14 |
| C02-04 | Input completo y output dentro de cada cap; límites exactos/+1, UTF-8 y overhead real | Medición sin campos declarados por caller, sin truncar; AI-T12 |
| C02-05 | Reserva única propia; segunda misma clave rechazada y otra organización independiente | Conexiones independientes, slots, consumo/reconciliación; AI-T11/12 |
| C02-06 | Commit/audit correctos; fallar cada append, T1/T2/T3/T4 y confirmaciones ambiguas | Cero fake antes de intent; hechos confirmados, UNKNOWN sin replay; AI-T08 |
| C02-07 | Fake usa bytes reales; documento cambiado modifica candidato o invalida evidencia | Nunca respuesta por escenario; resultado inválido/oversize/NO_EVIDENCE; AI-T03/12/13 |
| C02-08 | Fake normal; indisponible/error/timeout/cancelación no activa retries/threads/fallback | Contador, duración, estados y señal original; AI-T03/08/12 |
| C02-09 | C/AB/fuente vigentes; revocar en cada ventana, cambiar perfil/clasificación/revisión/expirar, incluyendo invalidación global por cambio en B | Writer coordinado bloquea preentrada, writer durante P4 confirma sin lock de inferencia; AI-T07/15 |
| C02-10 | Writer no coordinado en ventana T2→P3 y segundo coordinador | Demostrar límite/exclusividad, no llamar «revocación global»; condición PO de sección 9; AI-T07/11 |
| C02-11 | Reabrir DB/validar esquema; intentos huérfanos, manipulación, paths/aliases/ACL | Sin nueva capacidad, memoria fallback, reparación o reembolso; AI-T08/15 |
| C02-12 | Consultas A/B propias; cruzar rol/org/cursor e inputs hostiles | Nada de B en error/audit A; anonymous sin refs; AI-T11/17 |
| C02-13 | Metadata en DB/logs/repr; canarios en documento/pregunta/candidato/excepción | Ausencia en tablas, ficheros auxiliares, logging/tracing y tracebacks propios; AI-T09/13/14/17 |
| C02-14 | Cancelar A mientras B continúa, close/clear fallidos, cause/context/group retenidos | Owners separados, señal preservada, cero nueva introspección; AI-T09/11 |
| C02-15 | Socket/DNS guard, flags heredados activos, AST/imports | Cero conexiones externas, callbacks externos, SDKs o configuración clínica; AI-T05/09/14 |
| C02-16 | A/B/C/D existentes y cuatro nodos intactos | C01 + cinco suites anteriores, C/D denegados, sin nuevos endpoints; AI-T15/17 y compatibilidad |

Implementación futura: venv existente, basetemp absoluto nuevo test-owned fuera de `.pytest-tmp`, sin live, Docker, Keycloak o HAPI. Repetir suite C02 completa, `test_enterprise_ai_processing.py` y las cinco suites TASK 002–005/DEMO-001 listadas en el plan; mantener skip Windows/ACL/CRLF y deuda IAM fuera del alcance, no ocultarlos. Medir ausencia de efectos además de outcomes. Prueba de commit durante P4 con conexión independiente obligatoria: ninguna transacción del gateway permanece abierta durante extracción. No ejecutar estas suites por el cambio documental actual.

## 14. Evolución PostgreSQL sin abstracciones prematuras

Decisión vigente: futuro destino **PostgreSQL**, no opción intercambiable implementada. Las operaciones de dominio del ledger encapsulan persistencia y CAS; C01 sigue puro y futuro LangGraph solo orquesta. No exponer ORM, SQLAlchemy, sesiones SQLite, rutas o expresiones SQL en sus contratos; no implementar adaptador PostgreSQL ni feature flag de motor ahora.

| Aspecto | SQLite laboratorio propuesto | Evaluación requerida para PostgreSQL |
|---|---|---|
| Transacciones/locking | Writer de archivo con BEGIN IMMEDIATE, barrera local de admisión; no multi-worker | Locks de filas/orden de adquisición, aislamiento y snapshot de cada sentencia; no asumir que READ COMMITTED o una lectura anterior congela permisos |
| Revisiones/CAS | Revisión C global y `attempt_version`; límite C01 explícito | Revisiones por organización/ámbito si se aprueba cambiar contrato; CAS/locks atómicos y manejo de serialization/deadlock sin reejecutar efectos |
| Concurrencia/slots | Índice parcial único HELD/UNCERTAIN y coordinador único | Unicidad concurrente, filas de presupuesto/slots si hacen falta; procesos múltiples, fencing y prueba de consumo único; no confiar en objetos Python entre réplicas |
| Tipos/DDL | STRICT, enteros flags/UTC-us, CHECK y referencias compuestas | Tipos boolean/UUID/bigint/timestamptz elegidos explícitamente, conversiones UTC/precisión, restricciones y nombres versionados; no copiar STRICT/PRAGMAs |
| Integridad/migración | Archivo y DDL/checksum exactos, WAL/sidecars propios | Roles/privilegios, catálogo y migraciones transaccionales, backup/restore, cifrado/retención y validación de esquema, sin conexiones omnipotentes |
| Aislamiento empresarial | FKs y filtros por organización, autoridad sintética | Identidad/administración reales y permisos de DB; evaluar RLS como defensa adicional, no sustituto de políticas ni prueba automática de multi-tenancy |
| Fallos | Busy timeout corto, commit ambiguo → cerrado/UNKNOWN | Timeouts de lock/statement/pool, conexión perdida/commit incierto, failover y reconciliación; nunca retry automático de inferencia |
| Presupuesto/uso | Límites por llamada y slot, sin saldo comercial | Definir cuotas/ventanas/coste y contadores con transacciones y control de carreras antes de vender capacidad |
| SQL específico | WAL/BEGIN IMMEDIATE/STRICT/validación archivo justificados localmente | Backend privado reemplazable; pruebas de conformidad de comandos, no emulación de SQLite ni repositorio genérico |

### ¿Una misma base PostgreSQL para A/B y C?

**Sí podría simplificar consistencia transaccional local**, si ambos dominios usan la **misma transacción/conexión y protocolo aprobado**, mantienen sus grants/auditorías separados y ordenan de forma conjunta revisiones, reserva y decisión final. Solo compartir servidor, base o esquema con transacciones independientes no elimina la carrera ni garantiza snapshot coherente. Puede evitar el doble commit local de dos archivos y habilitar FKs aprobadas, pero requiere migrar A/B explícitamente, cambiar sus puertos bajo autorización y probar contención/rollback/aislamiento.

No vuelve atómicos DB + entrada Python/LLM + permisos externos + entrega humana; no congela Graph, no permite mantener transacciones durante inferencia, no elimina UNKNOWN ni implementa revocación hasta el último byte. Tampoco implica fusionar auditorías IAM/clínicas ni convertir la DB en identidad. Comparar dominio compartido con esquemas separados frente a bases independientes, roles, blast radius y carga. C02 no decide ni migra A/B.

Etapa propuesta **PG-EVAL/MIGRATION**, después de DEMO-002 aceptada y **antes de cualquier piloto empresarial con datos reales**, con autorización propia. Orden respecto de C04 a decidir por el PO; cualquier proveedor real conserva su gate independiente. Entregables: ADR/contratos revisados para autoridad multiempresa y consistencia A/B/C; benchmark y pruebas multi-writer; plan de transformación solo metadata y revisión/estados UNKNOWN; pruebas de migración/reconciliación/backup/restore/rollback; aislamiento organizacional y administración/secretos/operación aprobados. No migrar leases ni contenido; todos los owners de laboratorio expirarán sin replay. Aceptación PO obligatoria antes de piloto; «PostgreSQL elegido» no equivale a producción lista. Ninguna modificación a SQLite clínico, IAM, conector o almacenes existentes está autorizada aquí.

## 15. Mantenibilidad, riesgos y decisiones requeridas

Cuatro módulos, cinco tablas y un ledger de comandos de dominio bastan como propuesta inicial. C01 sigue intacto; no duplicación de scopes, búsqueda de grants propios delegada a C01 por candidato, una sola persistencia C y versiones visibles. Transacciones solo para reserva/intent, consumo, observación, finalización, cambio administrativo y reconciliación/audit. Texto/pregunta/candidato/decision original/owner/lease reconocida son efímeros. Sin necesidad de LangGraph para ninguna prueba C02; M01/M02 se conservan y no adquieren nuevos consumidores privados.

Riesgos no resueltos por aceptar este documento: punto de entrada frente a writers fuera de la barrera, exclusividad real del coordinador, retención de tracebacks propios, custodia/host comprometido, integridad no inviolable de SQLite y recuperación/commit ambiguo, límites de tipos/anotaciones C01, falta de administración humana y revocación global, grounding/B final/two-store races de C03. La barrera de proceso es alcance de fixture, no sustituto de transacción PostgreSQL distribuida ni aislamiento del host. No preparación comercial ni certificación de proveedor.

Solicitudes concretas al PO, **antes de código/tablas**:

1. Aprobar/revisar estos cinco esquemas, su DDL, mapping C01, versión/checksum y ruta exclusivamente test-owned; inicialización explícita y no adopción de archivos ajenos.
2. Aprobar cuatro módulos y ledger unido al audit transaccional, sin ORM ni cambios de C01/A/B/contratos existentes.
3. Aprobar exención `not_required` ligada al grant y autoridad administrativa/auditora solo de test, CAS y caps/slot; no cuotas comerciales ni IAM humano.
4. Decidir **alcance coordinado de laboratorio** para el punto de entrada y mecanismo verificable de exclusividad por archivo. Si exige cubrir writers no coordinados antes de entrada física, rechazar el protocolo actual y diseñar otro antes de implementar.
5. Aprobar semántica de T1–T4, UNKNOWN/UNCERTAIN, no replay ni reembolso automático, reconciliación solo metadata y contador de entrada distinto de procesamiento.
6. Aprobar contrato fake/entrada entera/uso, sin retorno de candidato al usuario ni afirmaciones de grounding en C02, y gates bloqueantes de retención/concurrencia/fallos.
7. Confirmar la etapa PostgreSQL posterior a DEMO-002 y previa a todo piloto con datos reales; aprobar solo la evaluación futura de base A/B/C compartida, no su implementación.

Esta fase **no concede** ninguno de esos permisos de implementación. Al aprobar el diseño, emitir una autorización C02 de Phase B con rutas exactas y criterios de aceptación. No C03, DEMO-002, C04, proveedores, RAG, MCP, Gate D, endpoints, staging/publicación ni servicios por inferencia del agente.
