# TASK-C03 Phase B2-SRC — evidencia de una lectura

Estado: emisor de prueba en `feature/enterprise-ai-processing-authorization-task-c03-b2`. No está en `main`. No hay PR ni merge. El observador y el grounding no están iniciados. La promoción a `app/` queda bloqueada.

Base: `c6dd2124713a4aad193dc9ddf7d66129c16d38d7`, merge del PR #119. `main` local sigue en `138b748747f0e3d57f7da89c1fbc7c2b62cf5f8d`.

La propuesta aprobada es [enterprise-grounded-answer-task-c03-b2-source-evidence-proposal.md](enterprise-grounded-answer-task-c03-b2-source-evidence-proposal.md). La alternativa A quedó implementada solo como emisor de prueba.

## Qué queda implementado

- `services/ai-service/tests/enterprise_single_read_source.py` compone una llamada pública a `ConnectorService.execute` y emite `TrustedSourceReadReceipt` junto con la `SourceEvidence` C01 de ese mismo resultado.
- El módulo es de prueba. No entra en `app/enterprise_ai_processing` y el inventario AST cerrado no se amplió.
- El recibo no se serializa, no se copia y no se recupera por `operation_id`. No es un permiso Gate C ni una lease.
- `content_revision` es `document.version`. No es un eTag. Los bytes canónicos son una codificación UTF-8 estricta del texto recibido, sin normalizar y sin truncar.
- C01 reconoce esa evidencia con `GateCPolicyEvaluator`. La vía aprobada es `prepare_once`: consume el recibo externo aunque `prepare` falle, admite como máximo una lease y deja la evidencia interna reconocible en `_seal`. El modelo no se ejecuta.
- Dos `prepare_once` simultáneos no crean una segunda reserva. El candado cubre solo la reclamación del recibo.
- Un `gateway.prepare` directo que falla antes de `populate` puede no consumir el recibo. No es una garantía general ni una preparación productiva. `gateway.py` no cambió.
- No se modificó `ConnectorService`, el workflow, los evaluadores A/B/C, el gateway, el fake, el ledger ni las migraciones. El inventario AST no se amplió.

`ProcessingLaboratory.__init__` sigue haciendo una lectura por `issue()`. Esta composición no la reutiliza. La operación positiva parte de un conector que todavía no ha leído.

## Comandos y resultados

Intérprete: `services/ai-service/.venv/Scripts/python.exe`. Directorio: `services/ai-service`. No se usó `services/ai-service/.pytest-tmp`. No se contactó `local-hapi`, Docker, Keycloak, Graph live ni un proveedor real.

Estos recuentos son de esta ejecución. No sustituyen los históricos de Codex ni los de la publicación de B1.

```text
python -m pytest tests/test_enterprise_single_read_source.py -q --basetemp C:\Temp\c03b2r
34 passed in 0.78s

python -m pytest tests/test_enterprise_ai_processing.py -q --basetemp C:\Temp\c03b2c01
192 passed in 0.38s

python -m pytest tests/test_enterprise_ai_processing_architecture.py tests/test_enterprise_ai_processing_privacy.py tests/test_enterprise_ai_processing_ledger.py tests/test_enterprise_ai_processing_ownership.py tests/test_enterprise_ai_processing_gateway.py tests/test_enterprise_ai_processing_concurrency.py tests/test_enterprise_ai_processing_schema.py -q --basetemp C:\Temp\c03b2c02
224 passed in 28.85s

python -m pytest tests/test_enterprise_ai_processing_derived_delivery.py -q --basetemp C:\Temp\c03b2b1
31 passed in 7.67s

python -m pytest tests/test_enterprise_connectors.py tests/test_enterprise_connector_control_plane.py tests/test_enterprise_connector_graph.py tests/test_enterprise_connector_workflow.py tests/test_enterprise_connector_demo.py -q --basetemp C:\Temp\c03b2ent
617 passed, 1 skipped in 202.08s
```

El omitido es `test_symlinked_store_is_rejected_when_supported`: el sistema local no permitió crear el symlink sintético. No se cambió ninguna ACL.

## Residuo

- La versión del documento no detecta un cambio remoto no observado que conserve el mismo número.
- El reconocimiento vale dentro del proceso.
- `prepare_once` es la garantía de consumo, incluido el fallo y la admisión concurrente. Un `prepare` directo que no llega a `populate` queda fuera de esa garantía.
- No hay borrado criptográfico. M01 y M02 del workflow antiguo siguen abiertos y esta fase no los usa.
