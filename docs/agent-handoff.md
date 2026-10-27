# Contexto compartido para Codex y Cursor

Este documento conserva contexto técnico estable entre herramientas. No sustituye la comprobación en vivo de Git: cada sesión debe verificar rama, referencias, status, staged/unstaged, no rastreados y stashes antes de editar. Nunca aplicar ni alterar un stash o un cambio preexistente sin autorización.

## Estado del proyecto

El repositorio contiene dos unidades desplegables e independientes:

- **Healthcare Interoperability:** Java 21/Spring Boot, cliente FHIR R4, SMART, perfiles sandbox Epic/Oracle, Clinical Read, Mini HIS/Mini LIS, intercambio de laboratorio y Clinical Federation.
- **Healthcare AI:** Python/FastAPI/LangGraph, protocolos deterministas de seguimiento, casos durables de Human Review, sesión y atribución de desarrollo, narrativas acotadas y asistencia explicativa opcional.

Java mantiene los conectores y la normalización. Python consume contratos normalizados y conserva la autoridad de workflow; no debe incorporar adaptadores propietarios de cada HIS. El modelo no posee elegibilidad, autorización, protocolo, resultado humano ni ejecución externa. HAPI local sigue siendo el origen predeterminado de Clinical Read y soporte de laboratorio.

Las modalidades de agentes son: clínico (flujos acotados ya implementados), empresarial (planificada) e híbrido (planificada y sin unión implícita de permisos). MCP permanece planificado y no está implementado.

## Última EPIC y TASK integradas

- **EPIC vigente:** Security & Governance V1.
- **Última TASK integrada en `main`:** TASK 005, endurecimiento de autenticación entre servicios, separación de secretos y cookies de handoff.

TASK 001–005 implementaron `SECURITY_AUDIT_V1` en Python y Java para los eventos contratados, decisiones de workflow y Human Review, atribución del principal sintético, auditoría de acceso a Clinical Federation y autenticación estricta entre servicios. TASK 006 valida esos controles, aísla los stores de auditoría del runner E2E y prepara el documento de cierre; permanece en revisión hasta que el Product Owner apruebe e integre su rama. El alcance continúa siendo de laboratorio: no es un registro inviolable, IAM/RBAC, identidad clínica verificada ni auditoría de producción.

## Próxima TASK prevista

No hay una TASK posterior autorizada. Identity & Access Foundation V1, Enterprise Connector Authorization V1 y MCP Integration Foundation V1 son dependencias futuras descritas en el cierre de Security & Governance V1, no implementaciones iniciadas. Solicitar siempre el enunciado aprobado del Product Owner antes de trabajar en cualquiera de ellas.

## Dependencias y riesgos

- Java 21 y Maven 3.9+ para Healthcare Interoperability; Python 3.11+ y el entorno de `services/ai-service` para Healthcare AI. Docker es necesario solo para pruebas/integraciones que lo declaran.
- El recorrido operativo real Mini HIS → Mini LIS → Clinical Federation → LangGraph → Human Review requiere Docker Engine para el PostgreSQL dedicado. Si Docker no está disponible, ejecutar la cobertura aislada y registrar el bloqueo; no sustituirlo iniciando HAPI.
- Los stores de revisión, checkpoint, sesión, conocimiento y auditoría son SQLite con límites de laboratorio y, donde se documenta, un único proceso escritor. No constituyen persistencia distribuida ni cifrado de aplicación.
- Producción aún carece de IAM/RBAC y multi-tenancy, identidad clínica verificada, assignment, secret management y arquitectura de red aprobadas, checkpoint distribuido y aprobación para datos clínicos reales.
- El default suite de Python conserva una prueba que consulta HAPI local sin flag opt-in. No iniciar ni modificar `local-hapi` para satisfacerla; reportar el prerrequisito o el fallo.
- En checkouts Windows con `core.autocrlf=true` y sin `.gitattributes`, tres pruebas de integridad fallan porque leen bytes CRLF de `app/migrations/001_follow_up_review.sql`. Son:
  - `test_followup_coordination_action.py::test_migration_001_remains_unchanged`
  - `test_followup_human_attribution_schema.py::test_migrations_001_and_002_do_not_define_attribution`
  - `test_human_session.py::test_review_migrations_and_http_routes_stay_untouched`
  La normalización en memoria a LF reproduce el contenido esperado. Las tres fallas representan una sola causa de finales de línea; no editar la migración histórica para ocultarla. La corrección requiere una tarea autorizada que preserve el contrato byte-for-byte.
- Hay documentación histórica o no rastreada que puede describir estados anteriores. Solo tratar como integrada la documentación versionada y contrastarla con el índice de arquitectura y los contratos actuales.

## Decisiones vigentes del Product Owner

- Codex es el ejecutor principal mientras tenga cuota; Cursor continúa cuando el Product Owner lo indique. Ambos trabajan en el mismo workspace y repositorio, sin handoff entre personas.
- Usar datos sintéticos en demostraciones. Proteger secretos y no incluir datos clínicos en este handoff.
- Seguridad y autorización son obligatorias; los contratos existentes se preservan.
- No tocar `local-hapi` sin autorización explícita.
- No hacer commit ni push sin autorización. Staging, cuando se solicite, debe ser por rutas explícitas y después de revisar el diff.
- No iniciar IAM, conectores empresariales o MCP sin una TASK posterior explícita.

## Documentos que deben consultarse

- [`../AGENTS.md`](../AGENTS.md): reglas operativas comunes.
- [`../README.md`](../README.md), [`PROJECT.md`](PROJECT.md), [`roadmap.md`](roadmap.md) y [`architecture/README.md`](architecture/README.md): producto, estado y autoridad arquitectónica.
- [`contracts/security-audit-v1.md`](contracts/security-audit-v1.md): alcance exacto de Security & Governance V1 — TASK 001.
- [`ai-governance/service-security-hardening-v1.md`](ai-governance/service-security-hardening-v1.md) y [`ai-governance/security-governance-v1-closure.md`](ai-governance/security-governance-v1-closure.md): endurecimiento de TASK 005 y evidencia/límites del cierre de TASK 006.
- [`contracts/clinical-read-v1.md`](contracts/clinical-read-v1.md), [`contracts/clinical-federation-v1.md`](contracts/clinical-federation-v1.md) y [`contracts/ai-clinical-federation-v1.md`](contracts/ai-clinical-federation-v1.md): fronteras Java/Python y federación.
- [`design/langgraph-workflow-orchestration-v1.md`](design/langgraph-workflow-orchestration-v1.md) y [`contracts/follow-up-review-workflow-v1.md`](contracts/follow-up-review-workflow-v1.md): orquestación y autoridad operacional.
- [`contracts/human-identity-v1.md`](contracts/human-identity-v1.md), [`contracts/human-attribution-v1.md`](contracts/human-attribution-v1.md), [`adr/ADR-088-server-rendered-human-review-demo.md`](adr/ADR-088-server-rendered-human-review-demo.md), [`adr/ADR-093-human-review-session.md`](adr/ADR-093-human-review-session.md) y [`adr/ADR-094-human-attribution.md`](adr/ADR-094-human-attribution.md): Human Review, sesión y atribución de desarrollo.

## Procedimiento de cambio entre Codex y Cursor

1. La herramienta que toma el turno lee `AGENTS.md`, este handoff y los contratos aplicables; no depende del chat anterior.
2. Verifica Git en vivo, incluida la relación con `origin/main`, sin actualizar, cambiar de rama, limpiar ni aplicar stash automáticamente.
3. Identifica y preserva archivos staged, modificados o no rastreados que ya existían. Excluye `local-hapi` y secretos.
4. Confirma la TASK autorizada, sus contratos y pruebas. Si falta alcance que cambiaría el diseño, se detiene y consulta al Product Owner.
5. Continúa sobre el mismo workspace; no duplica implementaciones ni crea un “handoff branch”. Mantiene un diff mínimo y reporta cada operación relevante.
6. Antes de entregar, ejecuta validaciones proporcionales, revisa el diff por rutas explícitas y vuelve a mostrar el estado Git.
7. Espera la revisión del Product Owner. Commit y push requieren autorización separada.
