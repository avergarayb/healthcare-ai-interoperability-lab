# TASK-C03 Phase B2-RUNTIME — frontera ejecutable

Estado: cierre P1 en `feature/enterprise-ai-processing-authorization-task-c03-b2-runtime`. No hay PR ni merge. El observador y el grounding no están iniciados.

Base: `56862e9d7f5ccd91c5b3a0e89cb220470959102d`, merge del PR #120. `main` local sigue en `138b748747f0e3d57f7da89c1fbc7c2b62cf5f8d`.

La propuesta aprobada es [enterprise-grounded-answer-task-c03-b2-runtime-boundary-proposal.md](enterprise-grounded-answer-task-c03-b2-runtime-boundary-proposal.md). La alternativa A quedó implementada. `gateway.py` no cambió.

## API

- `TrustedEnterpriseSourceBoundary.compose(service, *, ledger, executor)` construye la frontera y el único `EnterpriseModelGateway` vinculado a esa instancia. El caller no entrega un gateway.
- `read(context, request)` ejecuta una lectura pública. No acepta evidencia, resultado, documento, sobre, bytes ni lease, y no los devuelve.
- `admit()` reclama la preparación, llama `prepare` y devuelve `RuntimeAdmission` con `state`, `organization_id`, `operation_id`, `lease_id` y `reservation`. La `ProcessingLease` queda en la fachada.
- `close()` de una admisión `PREPARED` no ejecutada llama `gateway.close` de su gateway exclusivo. La fila queda `CANCELLED` y `RELEASED`. `UNCERTAIN` conserva `HELD` y no llama `reconcile`.
- `state` recorre `NEW`, `READING`, `SOURCE_RECOGNIZED`, `PREPARE_CLAIMED`, `PREPARED`, `DENIED`, `UNCERTAIN` y `CLOSED`. Un estado terminal no vuelve a `SOURCE_RECOGNIZED`.

La admisión válida es el hilo de `admit` junto con el token de esa reclamación. `authority` ata al owner solo en ese par. Otro hilo que llegue antes, aunque copie el token, no queda atado y no reserva. `recognizes_source` es verdadero solo en esa ventana y, ya en `PREPARED`, para el owner atado.

`_seal` de ese mismo owner sigue siendo válido hasta `close`. Una ejecución futura tiene que hacer su último `_seal` antes de cerrar la frontera. Este incremento no llama al modelo.

## Diferencia con B2-SRC

El emisor de `tests/enterprise_single_read_source.py` sigue igual. Su `prepare_once` depende de que el caller lo use. La fachada no entrega el recibo, así que la vía pública no puede elegir otro método. `content_revision` sigue siendo `document.version`. No es un eTag.

## Reservas

Una admisión positiva deja `run_state=INTENT` y `reservation_state=HELD`. El `close` normal de esa admisión, sin ejecución del modelo, usa el `close` público de C02 y escribe `CANCELLED` y `RELEASED`, más el evento `ai_processing_cancelled`. No escribe `COMPLETED`. Un commit ambiguo, cuando `reserve` ya confirmó y `prepare` no devolvió la lease, queda en `UNCERTAIN` con la fila `HELD`. Ese cierre no la libera y no llama `reconcile`. Si `gateway.close` lanza, la fachada permanece en `PREPARED` y la fila permanece `HELD`.

## Comandos y resultados

Intérprete: `services/ai-service/.venv/Scripts/python.exe`. Directorio: `services/ai-service`. No se usó `services/ai-service/.pytest-tmp`. No se contactó `local-hapi`, Docker, Keycloak, Graph live ni un proveedor real.

Estos recuentos son de esta ejecución. No sustituyen los históricos de Codex ni los de B2-SRC.

```text
python -m pytest tests/test_enterprise_ai_processing_source_boundary.py -q --basetemp C:\Temp\c03p1rt
40 passed in 4.39s

python -m pytest tests/test_enterprise_single_read_source.py -q --basetemp C:\Temp\c03p1b2
34 passed in 0.76s

python -m pytest tests/test_enterprise_ai_processing.py -q --basetemp C:\Temp\c03p1c01
192 passed in 0.33s

python -m pytest tests/test_enterprise_ai_processing_architecture.py tests/test_enterprise_ai_processing_privacy.py tests/test_enterprise_ai_processing_ledger.py tests/test_enterprise_ai_processing_ownership.py tests/test_enterprise_ai_processing_gateway.py tests/test_enterprise_ai_processing_concurrency.py tests/test_enterprise_ai_processing_schema.py -q --basetemp C:\Temp\c03p1c02
226 passed in 41.88s

python -m pytest tests/test_enterprise_ai_processing_derived_delivery.py -q --basetemp C:\Temp\c03p1b1
31 passed in 6.25s

python -m pytest tests/test_enterprise_connectors.py tests/test_enterprise_connector_control_plane.py tests/test_enterprise_connector_graph.py tests/test_enterprise_connector_workflow.py tests/test_enterprise_connector_demo.py -q --basetemp C:\Temp\c03p1ent
617 passed, 1 skipped in 381.59s
```

B2-RUNTIME pasa de 36 a 40 pruebas. Las cuatro nuevas cubren la carrera anterior a `authority` y el cierre: competidor con el contexto copiado, el mismo gateway, otro gateway y otro `operation_id`; cierre `PREPARED` con `CANCELLED`/`RELEASED`; fallo e interrupción de `gateway.close` sin marcar la fila liberada; cierre concurrente que no libera la reserva de la otra organización.

La suite C02 anterior tenía 224 pruebas. Las dos adicionales son controles negativos del inventario: `cursor.execute` y `service._event` quedan prohibidos en `source_boundary.py`. La única llamada `execute` admitida es `self._service.execute`.

El omitido es `test_symlinked_store_is_rejected_when_supported`: el sistema local no permitió crear el symlink sintético. No se cambió ninguna ACL.

## Residuo

- Un objeto reconocido dentro del proceso no impide que código del mismo proceso lea atributos privados.
- `document.version` no prueba que el remoto sea inmutable.
- `UNCERTAIN` puede dejar una fila `HELD`. La frontera no la concilia.
- Dos procesos sobre el mismo SQLite siguen sin una transacción común.
- No hay borrado criptográfico. M01 y M02 siguen abiertos.
- El siguiente incremento, el observador efímero, requiere autorización propia.
