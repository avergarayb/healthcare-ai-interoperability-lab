# TASK-C03 Phase B2-GRD — observador efímero y grounding determinista

Estado: cierre P1 en `feature/enterprise-ai-processing-authorization-task-c03-b2-grd`. No hay PR ni merge. No hay LangGraph nuevo ni entrega final.

Base: `deff2c7a3e26abad0a76c08eff1ad503f3527ba0`, merge del PR #121. El commit funcional de B2-RUNTIME es `1d9d63c2be1adbb0277b943a8dfd8d09d0ec0867`. `main` local sigue en `138b748747f0e3d57f7da89c1fbc7c2b62cf5f8d`.

La decisión queda registrada en la sección 25 de [enterprise-grounded-answer-task-c03-proposal.md](enterprise-grounded-answer-task-c03-proposal.md).

## API

- `invoke_once(lease)` conserva el contrato C02. No busca observador y no devuelve el candidato.
- `invoke_once_observed(lease)` no recibe callback ni resultado. La frontera tiene que reconocer el owner, la lease y el observador creado por `compose`. Si no, la respuesta es `DENY` y el fake no corre.
- `TrustedEnterpriseSourceBoundary.run()` ejecuta esa llamada una sola vez y devuelve `RuntimeExecution`: estado, motivo, organización, operación, entradas y reserva. No devuelve texto, fragmento, candidato ni cifras.
- Una cláusula válida, un documento sin cláusula y dos cláusulas contradictorias que terminan `COMPLETED` publican la misma proyección: `COMPLETED`, `accepted`, una entrada y `CHARGED`. El veredicto queda solo en `GroundingRecord`. `close` durante `run` responde `lease_invalid` y no borra los bytes que `_seal` y el observador todavía usan. El lock de la fachada no se sostiene durante el fake.
- El veredicto interno usa las categorías de la propuesta: `EVIDENCE_FOUND`, `EVIDENCE_INSUFFICIENT`, `CANDIDATE_INVALID`, `AUTHORIZATION_DENIED`, `AUTHORIZATION_UNVERIFIABLE`, `REVOCATION_DETECTED` y `TECHNICAL_FAILURE`.
- Los enteros solo existen en `GroundingRecord` cuando el veredicto es `EVIDENCE_FOUND`. `close` los anula. No entran en SQLite, auditoría, logs ni `repr`.

## Orden

1. `read` hace una lectura pública y conserva una copia de bytes obtenida con `bytearray` y `bytes`.
2. `admit` reserva una lease. Los `_seal` de C02 siguen viendo la evidencia y esos bytes.
3. El fake escribe el candidato en el `ExecutionOwner`.
4. El ledger confirma `COMPLETED` y `CHARGED`. La transacción ya está cerrada.
5. El observador compara el candidato con la copia de la lectura. El patrón es `VACACIONES: [días] dias tras [meses] meses de servicio.` Los offsets son de bytes UTF-8. No hay normalización Unicode.
6. `_cleanup` borra el candidato y el resto de buffers del owner C02.
7. `close` de una ejecución ya cobrada no emite `CANCELLED`. `close` de una admisión sin ejecución sí cancela la reserva `HELD`. Una fila `UNCERTAIN` no se concilia. Mientras `run` está abierto, `close` no cambia la fila.

Dos cláusulas con números distintos producen `EVIDENCE_INSUFFICIENT`. Dos cláusulas idénticas producen un solo hallazgo. El texto de instrucciones dentro del documento no cambia el veredicto ni se copia al resultado. El documento de laboratorio sin la cláusula, el que usa DEMO-001, queda en `EVIDENCE_INSUFFICIENT`. DEMO-001 no se modificó.

## Matriz

| ID | Prueba | Variantes | Resultado de esta ejecución |
|---|---|---|---|
| 01–06 | `test_b2_grd_01_through_06_one_real_fake_execution_grounds_internally` | Lectura, evidencia, lease, fake real, candidato, grounding | PASS |
| 07 | `test_b2_grd_07_laboratory_document_without_clause_is_insufficient` | Documento de laboratorio sin cláusula | PASS |
| 08 | `test_b2_grd_08_candidate_that_is_not_the_fragment_is_invalid` | Candidato distinto | PASS |
| 09 | `test_b2_grd_09_utf8_offset_inside_a_codepoint_is_invalid` | Offset dentro de un codepoint | PASS |
| 10 | `test_b2_grd_10_multibyte_document_keeps_ascii_digits` | Documento multibyte | PASS |
| 11 | `test_b2_grd_11_contradictory_clauses_do_not_choose_one` | Cláusulas contradictorias | PASS |
| 12 | `test_b2_grd_12_repeated_identical_clause_is_one_finding` | Cláusulas idénticas | PASS |
| 13 | `test_b2_grd_13_hostile_instructions_stay_data` | Instrucciones hostiles | PASS |
| 14 | `test_b2_grd_14_swapped_reading_bytes_are_not_evidence` | Fuente sustituida | PASS |
| 15 | `test_b2_grd_15_other_organization_keeps_its_own_reservation` | Otra organización | PASS |
| 16 | `test_b2_grd_16_foreign_owner_is_not_observed` | Owner ajeno | PASS |
| 17 | `test_b2_grd_17_other_lease_does_not_run_the_fake` | Otra lease | PASS |
| 18 y 25 | `test_b2_grd_18_replaced_observer_cannot_watch` | Observador no reconocido | PASS |
| 19 | `test_b2_grd_19_observer_is_single_use` | Segundo uso | PASS |
| 20 | `test_b2_grd_20_same_lease_does_not_execute_twice` | Segunda ejecución | PASS |
| 21 | `test_b2_grd_21_missing_gate_b_does_not_process` | Sin Gate B | PASS |
| 22 | `test_b2_grd_22_missing_gate_c_stops_before_the_fake` | Sin Gate C | PASS |
| 23–24 | `test_b2_grd_23_24_revision_change_after_admission_is_revocation` | Revocación y cambio de revisión | PASS |
| 26 | `test_b2_grd_26_audit_failure_on_read_creates_no_execution` | Fallo de auditoría de lectura | PASS |
| 27 | `test_b2_grd_27_ambiguous_finish_does_not_retry` | Commit ambiguo | PASS |
| 28 | `test_b2_grd_28_observer_failure_after_completed_is_not_grounded` | Fallo del observador | PASS |
| 29 | `test_b2_grd_29_cancelled_error_during_the_model_is_uncertain` | CancelledError | PASS |
| 30 | `test_b2_grd_30_keyboard_interrupt_during_the_model_propagates` | KeyboardInterrupt | PASS |
| 31 | `test_b2_grd_31_cleanup_failure_is_not_success` | Cleanup fallido | PASS |
| 32 | `test_b2_grd_32_canary_is_absent_from_repr_logs_and_sqlite` | Canario | PASS |
| 33 | `test_b2_grd_33_public_result_has_no_candidate_channel` | Sin canal de candidato | PASS |
| 34 | `test_b2_grd_34_unexecuted_close_still_cancels_and_executed_close_does_not` | Cierre sin ejecución y con ejecución | PASS |
| 35 | `test_b2_grd_35_no_derived_delivery_row` | Sin entrega AUTHORIZED | PASS |
| 36 | `test_b2_grd_36_positive_path_makes_no_network_attempt` | Sin red | PASS |
| 37 | `test_b2_grd_37_historical_invoke_once_does_not_observe` | `invoke_once` histórico | PASS |
| Comparación pública | `test_b2_grd_public_metadata_does_not_reveal_grounding` | Válida, ausente y contradictoria | PASS |
| Carrera | `test_b2_grd_close_during_run_is_rejected_until_completion` | Antes de consume, durante el fake, antes del observador y durante grounding | PASS |
| Dos `run` | `test_b2_grd_two_runs_on_one_admission_invoke_the_fake_once` | Misma admisión | PASS |
| Aislamiento | `test_b2_grd_concurrent_runs_do_not_cross_figures` | Dos organizaciones | PASS |

El `result_code` durable de C02 sigue siendo `CANDIDATE` o `NO_EVIDENCE`. No es el veredicto de grounding y no sale en `RuntimeExecution`. Las categorías `EVIDENCE_*` no aparecen en SQLite.

## Comandos y resultados

Intérprete: `services/ai-service/.venv/Scripts/python.exe`. Directorio: `services/ai-service`. No se usó `services/ai-service/.pytest-tmp`. No se contactó `local-hapi`, Docker, Keycloak, Graph live ni un proveedor real.

```text
python -m pytest tests/test_enterprise_ai_processing_grounding.py -q --basetemp C:\Temp\c03p1grd
37 passed in 10.32s

python -m pytest tests/test_enterprise_ai_processing_source_boundary.py -q --basetemp C:\Temp\c03p1rt
40 passed in 8.54s

python -m pytest tests/test_enterprise_single_read_source.py -q --basetemp C:\Temp\c03p1b2
34 passed in 1.07s

python -m pytest tests/test_enterprise_ai_processing.py -q --basetemp C:\Temp\c03p1c01
192 passed in 0.63s

python -m pytest tests/test_enterprise_ai_processing_architecture.py tests/test_enterprise_ai_processing_privacy.py tests/test_enterprise_ai_processing_ledger.py tests/test_enterprise_ai_processing_ownership.py tests/test_enterprise_ai_processing_gateway.py tests/test_enterprise_ai_processing_concurrency.py tests/test_enterprise_ai_processing_schema.py -q --basetemp C:\Temp\c03p1c02
227 passed in 33.41s

python -m pytest tests/test_enterprise_ai_processing_derived_delivery.py -q --basetemp C:\Temp\c03p1b1
31 passed in 10.07s

python -m pytest tests/test_enterprise_connectors.py tests/test_enterprise_connector_control_plane.py tests/test_enterprise_connector_graph.py tests/test_enterprise_connector_workflow.py tests/test_enterprise_connector_demo.py -q --basetemp C:\Temp\c03p1ent
617 passed, 1 skipped in 286.69s
```

La suite C02 suma una prueba: `grounding.py` queda en el inventario y `cursor.execute` sigue prohibido ahí. `invoke_once` histórico sigue completando sin observador.

El caso positivo usa `FakeEnterpriseModel`. No se sustituye la extracción por un mock.

## Residuo

- La identidad de objeto cubre este proceso. No es una autoridad criptográfica.
- `invoke_once` sigue disponible para C02 y no expone el candidato. No es el camino de B2-GRD.
- Una fila `UNCERTAIN` sigue esperando `reconcile` administrativo.
- Los enteros no salen de este incremento. La frase de plantilla y la entrega derivada requieren otra autorización.
- No hay borrado criptográfico.
