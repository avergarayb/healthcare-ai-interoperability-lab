# DEMO-001 — Evaluación read-only de mantenibilidad

Alcance: TASK 002–005 integradas hasta PR #113; [demo funcional separada](../demos/enterprise-connector-demo-001.md). Informe revisado por el Product Owner al aprobar funcionalmente la demo offline; sus recomendaciones no están autorizadas para implementación. No se refactorizó código productivo, cambió un contrato ni inició TASK 006/007. Esta revisión no certifica seguridad productiva ni rendimiento. Clasificación: P0 bloqueante reproducido; P1 deuda importante; P2 mejora de mantenimiento; P3 opcional.

## Método y resultado general

Inspección de implementación, fixtures, runbooks, pruebas y dependencias AST de `app/enterprise_connectors` y `app/enterprise_workflows`: **19 módulos, 36 aristas internas de importación estática y cero ciclos detectados**. Esto no analiza todas las dependencias externas/imports dinámicos del proceso ni acredita su ausencia global. Medidas de longitud incluyen líneas físicas y funciones anidadas, no complejidad ciclomática ni una calificación automática de calidad.

Los límites actuales son reconocibles: modelos/registro, política/ledger, servicio, control plane/store/auditoría, adaptador de protocolo y workflow separado. Es una base modular acotada, no evidencia suficiente para llamarla «código espagueti». Las partes más delicadas son la limpieza de excepciones, la frontera final duplicada deliberadamente por capas y el coste/acoplamiento de snapshots SQLite. No se halló un P0 nuevo reproducido dentro de esta evaluación; los dos bloqueantes históricos de TASK 005 están documentados y tienen regresiones. La nueva DEMO falló inicialmente por su guard de importación, corregido solo en el script de laboratorio, no en TASK 002–005.

## Hallazgos

### M01 — P1: contrato implícito de ownership y limpieza de traceback

- **Archivo/ubicación:** [document_read.py](../../services/ai-service/app/enterprise_workflows/document_read.py), `_scrub_owned_tracebacks` línea 116 y `_invoke` línea 386.
- **Evidencia:** selección por globals exactos y `frame`/`self is owner`, lectura de f_locals, frame.clear sobre terminados y varios finally/notes. El nombre/estructura de locals/closures participa en el mecanismo. Históricamente dos bloqueantes requirieron probar retención y cadenas entre invocaciones; la corrección conserva excepción y stack pero elimina locales propios.
- **Riesgo:** renombrar helpers/capturas o actualizar Python/LangGraph puede invalidar la identificación o introducir un alias no inspeccionado. No es un problema de estilo aislado ni borrado seguro de memoria.
- **Recomendación:** tratar owner/aliases como invariante explícita de revisión; mantener pruebas de traceback retenido, grupos y aislamiento como gate de actualización. Preferir retirada explícita de aliases cuando baste; cualquier sustitución del scrub necesita una tarea autorizada y reproducción de negativas.
- **Impacto de modificarlo:** alto, afecta confidencialidad/cancelación/concurrencia. No hacer cambios cosméticos aquí; tampoco compartir/cachar grafos con closures sensibles para reducir construcción.

### M02 — P1: acoplamiento privado de la última frontera de entrega

- **Archivo/ubicación:** [document_read.py](../../services/ai-service/app/enterprise_workflows/document_read.py), `_failure` línea 191 y `_deliver` línea 330; [service.py](../../services/ai-service/app/enterprise_connectors/service.py), `_event` línea 36 y `_validate_delivery` línea 59.
- **Evidencia:** workflow llama helpers privados del servicio y debe conocer el orden revalidación/auditoría/commit. Existe una decisión B dentro del servicio y otra en la salida del workflow.
- **Riesgo:** cambios internos del servicio pueden romper el consumidor o desplazar la autorización fuera de la entrega real. Las dos decisiones B son intencionadas, no duplicación eliminable sin análisis.
- **Recomendación:** documentar/probar el protocolo interno de entrega; si aparece otro consumidor, evaluar un helper acotado de esa frontera con contrato explícito. No construir otro motor de políticas ni eliminar una frontera para simplificar.
- **Impacto:** medio–alto; exige negativas de revocación, audit/commit, resultado malformado y compatibilidad con TASK 002/004. Sin modificación durante DEMO-001.

### M03 — P2: funciones de orquestación densas

- **Archivo/ubicación:** [document_read.py](../../services/ai-service/app/enterprise_workflows/document_read.py) `_compile` 232–328 (97 líneas); [service.py](../../services/ai-service/app/enterprise_connectors/service.py) `execute` 73–154 (82); [policy.py](../../services/ai-service/app/enterprise_connectors/policy.py) `_evaluate` 60–136 (77); [control_plane.py](../../services/ai-service/app/enterprise_connectors/control_plane.py) `register` 135–204 (70); [adapter.py](../../services/ai-service/app/enterprise_connectors/providers/microsoft_graph/adapter.py) `read` 97–162 (66).
- **Evidencia:** varias fases/ramas y funciones anidadas en una misma función. No se deduce un defecto únicamente de su longitud.
- **Riesgo:** mayor carga de revisión y cambios que accidentalmente reordenen fases de seguridad o introduzcan captures sensibles.
- **Recomendación:** ante cambios funcionales futuros, separar validaciones/proyecciones puras claramente repetidas, conservando visible el orden de efectos y un owner por invocación. No dividir por métrica ni crear clases/estrategias sin un segundo caso real.
- **Impacto:** medio; el troceado del workflow necesita repetir todos los tests de retención/concurrencia, no solo outputs positivos.

### M04 — P2: validación y reconstrucción SQLite repetidas

- **Archivo/ubicación:** [sqlite_store.py](../../services/ai-service/app/enterprise_connectors/sqlite_store.py), `validate` 94, `connection` 110, `_snapshot` 153; [service.py](../../services/ai-service/app/enterprise_connectors/service.py), `_event` 36.
- **Evidencia:** cada conexión valida esquema, quick_check, FKs y continuidad de auditorías; snapshots reconstruyen tablas y el servicio solicita varios por operación. Pool acotado a cuatro y busy timeout 100 ms; guard final reserva escritor. Los context managers cierran/rollback por operación, no existe una conexión global persistente entre hilos.
- **Riesgo:** contención/coste creciente al aumentar filas o escritores. La revisión no midió un cuello de botella ni demuestra un SLA.
- **Recomendación:** medir conteo/coste de consultas con fixtures más grandes y registrar presupuestos antes de optimizar. Mantener autorización fresca y fail-closed; no ampliar timeouts ni cachear ALLOW para lograr tests verdes. Ningún I/O de red dentro del guard.
- **Impacto:** alto si se cambia transaccionalidad; requiere revisar revocación, escritores independientes, rollback y sink. No implica una recomendación automática de otro motor de base de datos.

### M05 — P2: duplicación parcial de traducción de fallos

- **Archivo/ubicación:** [service.py](../../services/ai-service/app/enterprise_connectors/service.py), `execute` 135–144; [document_read.py](../../services/ai-service/app/enterprise_workflows/document_read.py), `_failure` 191–215 y handlers de `_run`/nodos.
- **Evidencia:** ambos niveles proyectan outcome/reason y atribución con vocabulario cerrado; contienen comportamiento propio de su frontera, no copias equivalentes completas.
- **Riesgo:** deriva de motivos/semántica al ampliar resultados y dificultad de diagnosticar por mensajes deliberadamente minimizados.
- **Recomendación:** conservar pruebas de estados/fases por frontera; compartir solo una proyección pura si un cambio futuro demuestra repetición semántica real. No añadir stack traces/payloads al audit como atajo ni consolidar auditorías distintas.
- **Impacto:** medio; debe preservar supresión, atribución anónima, decisiones versus recepción y fallo de un sink sin evento ficticio.

### M06 — P2: fixtures y tests deliberadamente acoplados a internos

- **Archivo/ubicación:** [fixture Graph](../../services/ai-service/tests/enterprise_connector_graph_fixture.py), `TestGraphCredentials.release`, `graph_laboratory`; [fixture workflow](../../services/ai-service/tests/enterprise_connector_workflow_fixture.py), `TestInvocationBoundary`; [suite workflow](../../services/ai-service/tests/test_enterprise_connector_workflow.py), inspectores de owners y monkeypatch de fronteras; [consola](../../scripts/enterprise-connector-demo/run_demo.py), comprobación de liberación en `_execute`.
- **Evidencia:** uso de `_pages`, `_issued`, `_leases`, `_exchanges`, `_authorities`, captures y private helpers para comprobar limpieza/ausencia de efectos. La DEMO importa exclusivamente estas fábricas de test, sin pytest interactivo.
- **Riesgo:** refactors inocuos pueden romper fixtures; renombrar tests sin revisar su propiedad/inspección puede reducir cobertura. El guard de sockets es global dentro del proceso de laboratorio, no apropiado para alojarlo junto a otros servicios.
- **Recomendación:** mantener el proceso aislado y diferenciar pruebas de caja negra de regresiones internas de confidencialidad. Un pequeño helper de fixture para comprobar estado liberado solo se justificaría al cambiar esos fixtures, sin exponer authority en una API productiva.
- **Impacto:** bajo–medio para fixtures, alto si se debilitan inspectores. No convertir el issuer sintético en autenticador empresarial.

### M07 — P3: presentación y diagnósticos de operador

- **Archivo/ubicación:** [run_demo.py](../../scripts/enterprise-connector-demo/run_demo.py), `print_report`, `print_audit`, `main`.
- **Evidencia:** menú español, códigos cerrados técnicos, explicación humana específica de organization_mismatch, errores fijos y contador de red. Otras razones se presentan como códigos; no hay sistema de localización.
- **Riesgo:** comprensión limitada de fallos infrecuentes sin consultar el runbook; no es un defecto de autorización.
- **Recomendación:** añadir traducciones de razones cerradas únicamente según feedback manual del PO, sin imprimir errores subyacentes ni payloads. No hace falta framework de UI/localización para cuatro escenarios.
- **Impacto:** bajo, limitado a presentación y sus asserts.

### M08 — P3: simplificación de composición, sin extracción anticipada

- **Archivo/ubicación:** [run_demo.py](../../scripts/enterprise-connector-demo/run_demo.py), `DemoSession._execute` línea 178; [fixture workflow](../../services/ai-service/tests/enterprise_connector_workflow_fixture.py), `workflow_laboratory`.
- **Evidencia:** la consola construye `workflow_laboratory(directory, both=True)` en los cuatro escenarios, aunque solo el escenario 2 selecciona el recurso B. La separación actual de política, servicio y protocolo ya permite composición explícita; los namespaces continúan siendo sintéticos.
- **Riesgo:** preparación de fixtures innecesaria para escenarios de una organización y mayor superficie de comprensión. No se midió una mejora de rendimiento potencial ni se identificó un defecto de aislamiento.
- **Recomendación:** en una tarea posterior autorizada, evaluar preparar B solo para el escenario 2 y comprobar que no cambien política, contadores, aislamiento ni auditoría. Reutilizar límites y pruebas, no convertir el issuer de test en IAM, Selected en permiso universal ni añadir interfaces/microservicios anticipadamente.
- **Impacto:** bajo y localizado si se limita al fixture de consola; cualquier extracción productiva/custodia/tenancy sigue exigiendo contrato y autorización propios. Sin cambios durante DEMO-001.

## Prioridad y siguiente paso

Sin P0 nuevo reproducido; **dos P1, cuatro P2 y dos P3**. Prioridad: preservar regresiones de ownership y frontera final, después medir SQLite y simplificar de forma localizada cuando exista una necesidad de cambio. No hay evidencia que justifique una refactorización general, nueva capa IAM, microservicio o patrón adicional ahora. Las deudas OIDC/orden, CRLF y symlink/ACL están fuera de alcance y no fueron alteradas.

El runbook funcional conserva el comando y evidencia final de DEMO-001. Las recomendaciones son propuestas para revisión del Product Owner, no autorizaciones de implementación ni de TASK 006/007.
