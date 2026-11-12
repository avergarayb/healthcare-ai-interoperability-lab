# TASK-C03 E2E — LangGraph, autorización final y entrega local

Estado: cierre de seguridad en `feature/enterprise-ai-processing-authorization-task-c03-e2e`. No hay PR ni merge.

Base: `d26d10c7a699bd4470f3ff08422657b641cf3b86`, merge del PR #122. El commit funcional de B2-GRD es `158433b081cbc7548e6e7bac6cc3c626cf6370cf`. `main` local no se movió.

La decisión queda en la sección 26 de [enterprise-grounded-answer-task-c03-proposal.md](enterprise-grounded-answer-task-c03-proposal.md).

## Flujo

`EnterpriseAnswerFlow.compose` construye la frontera B2-RUNTIME, el sink y el grafo. El caller aporta el contexto, la solicitud de lectura y la consulta del permiso derivado. No aporta sink, frase ni cifras.

Nodos, en orden:

1. `read_recognized_source`
2. `admit_gate_c`
3. `execute_and_ground`
4. `authorize_final`
5. `prepare_answer`
6. `deliver_local`
7. `finish`

Una fase `DENIED`, `FAILED` o `UNCERTAIN` salta a `finish`. No hay reintento de nodo. `checkpointer`, `store` y `cache` quedan en falso. El tracing de la invocación queda apagado.

Tiempos de laboratorio: `T_read` en el nodo de lectura, `T_process` en la admisión, `T_ground` después del `COMPLETED` de C02, `T_auth` dentro del `delivery_guard` del conector y de la transacción del ledger, `T_delivery_attempt` al entrar al sink y `T_delivery_observed` solo si `accept` confirma. El lock de SQLite no se sostiene durante el fake. El lock del conector no envuelve la escritura del ledger. No hay transacción distribuida entre los dos almacenes.

## Authorities

La entrega exige la conjunción, no la suma, de:

- Gate A y Gate B, revalidados con `PolicyEvaluator` sobre el snapshot vigente, sin segunda lectura.
- Gate C, con el mismo `GateCPolicyEvaluator`, mientras la frontera sigue reconociendo la evidencia en estado `EXECUTED`.
- Perfil `fake-enterprise-extractive-v1` y `question_id = vacation-days-v1`.
- Grant derivado `grounded_extractive_answer` / `enterprise.answer.deliver`, recomprobado dentro de `commit_final_delivery`.
- Grounding reconocido de esa misma operación: mismo objeto, mismo veredicto y, si hay evidencia, los mismos enteros.

`ALLOW_PROCESSING` no entrega. `DerivedGrantMatch` tampoco. El caller no puede sustituir el `GroundingRecord`.

## Ownership

El documento y la evidencia siguen en la frontera hasta `close`, que ocurre al terminar la invocación. El `GroundingRecord` no sale de esa frontera. La frase vive en `EphemeralAnswer` solo entre la autorización confirmada y el sink; después se anula. El sink conserva la frase detrás de un testigo que solo posee el flujo. El estado del grafo no la contiene.

## Destinatario

`receive(context, request)` distingue cuatro cosas. El `recipient_id` de la consulta es el destinatario configurado. La identidad efectiva es el objeto de contexto que `IdentityBoundary.recognizes` devolvió al emitirlo. La autoridad para leer exige, además, que ese contexto no esté vencido, que principal y organización coincidan con la ejecución y que la solicitud repita destinatario, instancia, recurso, operación y propósito. La confirmación del sink es `observed`. La lectura posterior no es una segunda entrega.

Una cadena igual a `recipient-a`, un contexto copiado campo a campo, un principal de otra organización, un recurso u operación distintos, un contexto vencido, una llamada antes de `run` y una llamada con un sink o una frase fabricados por el caller no devuelven la frase. Después de `SUPPRESSED` o de un fallo anterior a copiar el texto, tampoco. Después de `close`, el contexto reconocido y vigente puede leer la frase ya observada; la cadena sola no puede.

## Incertidumbre y replay

`AUTHORIZED` solo no habilita otro `accept`. El flujo marca la entrega como gastada antes de aceptar. Un segundo `run` de la misma instancia falla. Un segundo `accept` del sink falla. `seal_release_uncertain` es un `UPDATE` de una fila `AUTHORIZED`. La vista pública usa `RELEASE_UNCERTAIN` únicamente después de releer esa fila. Si el `UPDATE` falla, la última decisión confirmada sigue siendo `AUTHORIZED`, la fase es `UNCERTAIN` y `observed` permanece en falso. Si el commit fue ambiguo y la lectura de la fila también falla, la vista no nombra `RELEASE_UNCERTAIN` ni `AUTHORIZED`. La fila que SQLite haya confirmado no se borra y C02 permanece `COMPLETED` / `CHARGED`.

Dentro del proceso no hay segunda entrega ni una autorización positiva regenerada para esa invocación. La frase no está en SQLite, así que el ledger no puede repetirla. Esa garantía no sobrevive a una caída o a un reinicio: el protocolo no reserva la entrega fuera del proceso. Una ejecución posterior, con un `operation_id` nuevo y un permiso vigente, puede volver a leer. No se añadió la migración 003.

## Entrega y auditoría

`AUTHORIZED` es la fila durable en `aip_delivery_decision`. No afirma que alguien recibió la frase. `observed` solo pasa a verdadero cuando el sink confirma; esa confirmación es una entrega local observada y no demuestra que una persona haya leído la respuesta. `SUPPRESSED` reutiliza el evento `ai_derived_delivery_suppressed`. `RELEASE_UNCERTAIN` se afirma solo cuando `seal_release_uncertain` quedó confirmado por una lectura posterior. No demuestra entrega ni no-entrega. No hay segunda entrega.

La tabla de auditoría V2 no admite un evento de autorización positiva. No se añadió una migración 003. La fila `AUTHORIZED` es el registro durable de esa decisión. `result_code` C02 sigue siendo `CANDIDATE` o `NO_EVIDENCE` para un lector privilegiado del ledger.

## Casos

| ID | Qué cubre | Resultado |
|---|---|---|
| 01–09 | Cláusula 20/12, una lectura, una admisión, un fake real, grounding, grant vigente, un destinatario | PASS |
| 10–11 | DEMO-001 y documento sin cláusula: abstención autorizada | PASS |
| 12 | Cláusulas contradictorias, sin elegir una cifra | PASS |
| 13–14 | Revocación de Gate A y de Gate B | PASS |
| 15 | Revocación de Gate C, sin cancelar el cobro | PASS |
| 16 | Permiso B1 deshabilitado | PASS |
| 17 | Grant derivado ausente | PASS |
| 18 | Grant derivado expirado | PASS |
| 19 | Otra organización | PASS |
| 20 | Otro destinatario | PASS |
| 21 | Otro propósito de procesamiento: el esquema lo rechaza y no hay entrega | PASS |
| 22 | Revisión de procesamiento cambiada | PASS |
| 23 | Revisión derivada cambiada | PASS |
| 24 | Fallo del ledger antes de autorizar | PASS |
| 25 | Fallo del ledger después de `AUTHORIZED`: `RELEASE_UNCERTAIN` | PASS |
| 26 | Sink antes de aceptar | PASS |
| 27 | Sink después de aceptar y antes de confirmar | PASS |
| 28 | El mismo estado `RELEASE_UNCERTAIN`, cubierto por 25–27 | PASS |
| 29 | Reintento prohibido, cubierto por 01, 25 y 26 | PASS |
| 30 | Dos `run` concurrentes, un fake | PASS |
| 31 | `close` durante la ejecución | PASS |
| 32 | Expiración durante el flujo | PASS |
| 33 | Error del observador | PASS |
| 34 | Error de grounding | PASS |
| 35–36 | `CancelledError` y `KeyboardInterrupt` | PASS |
| 37 | Instrucciones hostiles sintéticas | PASS |
| 38–41 | State, checkpoint, SQLite/WAL, logs y excepciones | PASS |
| 42 | Regresión C01 | 192 PASS |
| 43 | Regresión C02 | 233 PASS |
| 44 | Regresión B1 | 31 PASS |
| 45 | Regresión B2-SRC | 34 PASS |
| 46 | Regresión B2-RUNTIME | 40 PASS |
| 47 | Regresión B2-GRD | 37 PASS |
| 48 | Cinco suites de conectores | 617 PASS, 1 SKIPPED |
| 49–50 | Cero red y solo `FakeEnterpriseModel` | PASS |
| P1-A | Cadena, contexto copiado, otra organización, otra operación, vencido, sink fabricado | PASS |
| P1-B | Sellado fallido, frase copiada sin confirmación, lectura durable fallida, sin replay en proceso | PASS |

La frase positiva es exactamente: «Según el documento consultado, corresponden 20 días de vacaciones tras 12 meses de servicio.» La abstención no contiene cifras. Una denegación de Gate A sobre un documento válido y sobre uno contradictorio publica la misma proyección pública.

## Comandos

Desde `services/ai-service`, con el venv existente y basetemp corto:

```text
pytest tests/test_enterprise_ai_processing_e2e.py --basetemp C:\Temp\c03p1e2e3
pytest tests/test_enterprise_ai_processing_grounding.py --basetemp C:\Temp\c03p1grd
pytest tests/test_enterprise_ai_processing_source_boundary.py --basetemp C:\Temp\c03p1rt
pytest tests/test_enterprise_single_read_source.py --basetemp C:\Temp\c03p1src
pytest tests/test_enterprise_ai_processing.py --basetemp C:\Temp\c03p1c01
pytest tests/test_enterprise_ai_processing_privacy.py tests/test_enterprise_ai_processing_ledger.py tests/test_enterprise_ai_processing_ownership.py tests/test_enterprise_ai_processing_gateway.py tests/test_enterprise_ai_processing_concurrency.py tests/test_enterprise_ai_processing_schema.py tests/test_enterprise_ai_processing_architecture.py --basetemp C:\Temp\c03p1c02
pytest tests/test_enterprise_ai_processing_derived_delivery.py --basetemp C:\Temp\c03p1b1
pytest tests/test_enterprise_connectors.py tests/test_enterprise_connector_control_plane.py tests/test_enterprise_connector_graph.py tests/test_enterprise_connector_workflow.py tests/test_enterprise_connector_demo.py --basetemp C:\Temp\c03p1ent
```

Resultado de esta ejecución: E2E 34 PASS en 17,31 s; B2-GRD 37 PASS en 18,96 s; B2-RUNTIME 40 PASS en 14,53 s; B2-SRC 34 PASS en 1,08 s; C01 192 PASS en 0,56 s; C02 233 PASS en 62,95 s; B1 31 PASS en 12,67 s; conectores 617 PASS y 1 SKIPPED en 378,94 s. El SKIPPED sigue siendo el enlace simbólico que Windows no puede crear. No se contactó local-hapi, Docker, Keycloak, Graph live ni un LLM real.

## Riesgos residuales

- El reconocimiento es identidad de objeto dentro del proceso. No es IAM ni una credencial externa.
- La prohibición de repetir `accept` no sobrevive a una caída o a un reinicio. No hay reserva durable adicional ni migración 003.
- `aip_grounding_audit` no puede nombrar la autorización positiva sin cambiar el `CHECK` de la migración 002.
- `result_code` histórico sigue visible para quien lee el ledger.
- El sobre de C02 expira a los cinco segundos. Una autorización demorada por contención puede denegar por expiración.
- Dos SQLite y el proceso no son una transacción. Una revocación de otro proceso dentro de esa ventana queda fuera de la garantía.
- Si el sink copió la frase y luego falló, ni `AUTHORIZED` ni un sellado fallido prueban que el destinatario no la tenga.
- La aceptación confirmada del sink no demuestra una lectura humana.
- No hay borrado criptográfico.
