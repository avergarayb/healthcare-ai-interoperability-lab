# TASK-C03 Phase B1 — permiso derivado y base SQLite V2

Estado: evidencia de Phase B1 en la rama de trabajo. No está integrada en `main`. Phase B2 no está autorizada y C03 completa no está terminada.

Rama `feature/enterprise-ai-processing-authorization-task-c03`. La base de esta evidencia es `f1edf52f5d8a46fbad1538ab866dd3ac3aa01b0a`. `main` local sigue en `138b748747f0e3d57f7da89c1fbc7c2b62cf5f8d`.

## Qué queda implementado

- Migración explícita de un store C V1 válido a V2. La apertura y `initialize` no migran.
- Revisión derivada por organización, separada de `aip_store.revision`.
- Alta, revocación y consulta del permiso `grounded_extractive_answer` / `enterprise.answer.deliver`.
- Auditoría V2 de cambios administrativos, denegaciones atribuibles y la fila anónima de identidad no verificable.
- `assess_derived_delivery` devuelve `DerivedGrantMatch` solo cuando el permiso sintético coincide. No autoriza A/B/C, no ejecuta un modelo y no entrega bytes. Las denegaciones de permiso ausente, revocado, revisión obsoleta, organización ajena, destinatario distinto y vigencia vencida comparten el código público `processing_not_granted`.

No hay `invoke_once_observed`, grounding, LangGraph nuevo, entrega de respuestas ni cambios en `ConnectorService` o `EnterpriseDocumentWorkflow`.

El DDL aplicable es `services/ai-service/app/enterprise_ai_processing/migrations/002_processing_ledger.sql`. El borrador de la sección 10.1 de la propuesta no se aplica. Las decisiones están en la sección 22 de `enterprise-grounded-answer-task-c03-proposal.md`.

## Comandos y resultados

Intérprete: `services/ai-service/.venv/Scripts/python.exe`. Directorio: `services/ai-service`. Basetemp: `C:\Temp\c03b1r`. No se usó `services/ai-service/.pytest-tmp`. No se contactó `local-hapi`.

```text
python -m pytest tests/test_enterprise_ai_processing_derived_delivery.py -q --basetemp C:\Temp\c03b1r
31 passed in 6.55s

python -m pytest tests/test_enterprise_ai_processing.py -q --basetemp C:\Temp\c03b1r
192 passed in 0.30s

python -m pytest tests/test_enterprise_ai_processing_architecture.py tests/test_enterprise_ai_processing_privacy.py tests/test_enterprise_ai_processing_ledger.py tests/test_enterprise_ai_processing_ownership.py tests/test_enterprise_ai_processing_gateway.py tests/test_enterprise_ai_processing_concurrency.py tests/test_enterprise_ai_processing_schema.py -q --basetemp C:\Temp\c03b1r
224 passed in 61.15s

python -m pytest tests/test_enterprise_connectors.py tests/test_enterprise_connector_control_plane.py tests/test_enterprise_connector_graph.py tests/test_enterprise_connector_workflow.py tests/test_enterprise_connector_demo.py -q --basetemp C:\Temp\c03b1r
617 passed, 1 skipped in 466.31s
```

El omitido es `test_symlinked_store_is_rejected_when_supported`: el sistema local no permitió crear el symlink sintético. No se cambió ninguna ACL. Los recuentos por archivo, incluido ese caso, son 145, 76, 158, 196 y 43.

## Residuo

Phase B2 sigue bloqueada hasta existir un emisor que vincule una sola llamada pública a `ConnectorService.execute`. El candado de un proceso no cubre otro proceso. Dos archivos SQLite no forman una transacción distribuida. POSIX sigue fuera de alcance.
