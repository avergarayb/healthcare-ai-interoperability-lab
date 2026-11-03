# Contexto compartido para Codex y Cursor

Este documento conserva contexto técnico estable entre herramientas. No sustituye la comprobación en vivo de Git: cada sesión debe verificar rama, referencias, status, staged/unstaged, no rastreados y stashes antes de editar. Nunca aplicar ni alterar un stash o un cambio preexistente sin autorización.

## Estado del proyecto

El repositorio contiene dos unidades desplegables e independientes:

- **Healthcare Interoperability:** Java 21/Spring Boot, cliente FHIR R4, SMART, perfiles sandbox Epic/Oracle, Clinical Read, Mini HIS/Mini LIS, intercambio de laboratorio y Clinical Federation.
- **Healthcare AI:** Python/FastAPI/LangGraph, protocolos deterministas de seguimiento, casos durables de Human Review, sesión y atribución de desarrollo, narrativas acotadas y asistencia explicativa opcional.

Java mantiene los conectores y la normalización. Python consume contratos normalizados y conserva la autoridad de workflow; no debe incorporar adaptadores propietarios de cada HIS. El modelo no posee elegibilidad, autorización, protocolo, resultado humano ni ejecución externa. HAPI local sigue siendo el origen predeterminado de Clinical Read y soporte de laboratorio.

Las modalidades de agentes son: clínico (flujos acotados ya implementados), empresarial (planificada) e híbrido (planificada y sin unión implícita de permisos). MCP permanece planificado y no está implementado.

## Última EPIC y TASK integradas

- **EPIC vigente:** Identity & Access Foundation V1.
- **Última TASK integrada en `main`:** Identity & Access Foundation V1 — TASK 003, frontera Python OIDC workload (PR #105). Verificar la referencia remota en cada sesión.

Security & Governance V1 TASK 001–007 están integradas y la EPIC está técnicamente cerrada para su alcance de laboratorio por decisión del Product Owner. Incluye `SECURITY_AUDIT_V1`, autenticación estricta en sus fronteras contratadas, atribución sintética, E2E operacional y federación aislada validada. La reejecución final de FederationFlowTest tras los ajustes de gates quedó diferida por Docker; el Product Owner autorizó el commit sin repetirla. HAPI legacy live sigue como validación independiente pendiente. No implica IAM empresarial, identidad clínica verificada ni preparación productiva.

Identity & Access Foundation V1 — TASK 001 define contratos provider-agnostic, PrincipalContext, límites de confianza y adopción incremental. El Product Owner aprobó ADR-096 y los ciclos de vida separados: la sesión humana tendrá su contrato de expiración/reautenticación/revocación; el contexto de un workload no superará la expiración efectiva de su access token. TASK 002 integra un [fixture Keycloak aislado](design/identity-keycloak-lab-v1.md) en `infra/iam-lab/`, aprobado para laboratorio. TASK 003 integra una [frontera OIDC Python opt-in](design/python-oidc-resource-server-v1.md), solo workloads y con auditoría aditiva propia. TASK 004 añade un [registro confiable SQLite opt-in](design/trusted-identity-registry-v1.md) exclusivamente para esa frontera, con implementación/evidencia aprobadas para laboratorio y commit/push autorizados; integración en main pendiente. No hay nueva base empresarial de usuarios ni migración de sesiones; las rutas existentes conservan su autenticación.

## Próxima TASK prevista

El Product Owner aprobó TASK 004 y su validación de laboratorio: modo estático predeterminado, SQLite explícito, CLI offline, membresías/grants por organización, auditoría de cambios atómica y revocación en cada nueva decisión. Autoriza revisión final y commit/push exclusivamente de las veintiuna rutas de TASK 004; PR, merge y TASK 005 requieren autorización posterior. El runbook conserva pruebas deterministas/live y límites. La ruta `GET /iam-lab/v1/workload-context` continúa deshabilitada por defecto; no migra `/internal/*`, Human Review, LangGraph ni Java. No reutilizar el ID token de TASK 002: no se persistió y expiró; TASK 003 conserva cobertura sintética de su rechazo sin afirmar nueva evidencia humana live. Enterprise Connector Authorization V1 y MCP Integration Foundation V1 continúan como EPICs futuras no autorizadas.

## Dependencias y riesgos

- Java 21 y Maven 3.9+ para Healthcare Interoperability; Python 3.11+ y el entorno de `services/ai-service` para Healthcare AI. Docker es necesario solo para pruebas/integraciones que lo declaran.
- El recorrido operativo real Mini HIS → Mini LIS → Clinical Federation → LangGraph → Human Review requiere Docker Engine para el PostgreSQL dedicado. Si Docker no está disponible, ejecutar la cobertura aislada y registrar el bloqueo; no sustituirlo iniciando HAPI.
- `FederationFlowTest` es autónomo y usa Mini HIS, Mini LIS y PostgreSQL propios de la ejecución. La compatibilidad Clinical Read con HAPI real está separada en `LegacyHapiClinicalReadCompatibilityLiveIT`: es opt-in, requiere un HAPI test-owned con `syn-demo-patient-102` y nunca debe apuntar al `local-hapi` preexistente.
- Los stores de revisión, checkpoint, sesión, conocimiento y auditoría son SQLite con límites de laboratorio y, donde se documenta, un único proceso escritor. No constituyen persistencia distribuida ni cifrado de aplicación.
- Sesión y atribución humanas actuales aceptan únicamente `DEVELOPMENT_AUTHENTICATOR_V1`; adoptar OIDC exige contratos/migraciones aditivos posteriores. Un token válido no aporta por sí mismo pertenencia organizacional, acceso a un caso ni grants de fuentes. Las allowlists de auditoría tampoco aceptan actores nuevos automáticamente.
- El registro TASK 004 es SQLite local de laboratorio, no directorio humano ni administración IAM autenticada. Las etiquetas CLI de operador son no verificadas. Cada decisión SQLite nueva consulta un snapshot fresco; las decisiones ya en curso no se cancelan retroactivamente. No hay caché positiva de permisos ni revocación global entre despliegues, y el modo estático sigue requiriendo reinicio. El registro y la auditoría de acceso separados no poseen atomicidad distribuida.
- Exchange Java conserva un filtro independiente con `getHeader` y trim del token. El hardening exacto/rechazo de duplicados de Security & Governance TASK 005 no cubrió esa superficie; queda como hardening futuro acotado, sin cambios Java ni apertura de otra TASK en esta intervención.
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
- El diseño IAM debe admitir Keycloak de laboratorio y proveedores corporativos OIDC sin acoplar agentes/protocolos al proveedor. TASK 001 es solo documental; no cambia los métodos de autenticación existentes ni habilita OIDC en endpoints.
- No tocar `local-hapi` sin autorización explícita.
- No hacer commit ni push sin autorización. Staging, cuando se solicite, debe ser por rutas explícitas y después de revisar el diff.
- TASK 003/004 autorizan solo la frontera técnica OIDC Python de workloads y el registro de política local de laboratorio. No ampliar OIDC a rutas existentes, sesiones, Java, conectores empresariales o MCP sin una TASK posterior explícita. La aprobación final de TASK 004 autoriza commit/push de sus veintiuna rutas, no PR, merge ni TASK 005.

## Documentos que deben consultarse

- [`../AGENTS.md`](../AGENTS.md): reglas operativas comunes.
- [`../README.md`](../README.md), [`PROJECT.md`](PROJECT.md), [`roadmap.md`](roadmap.md) y [`architecture/README.md`](architecture/README.md): producto, estado y autoridad arquitectónica.
- [`contracts/security-audit-v1.md`](contracts/security-audit-v1.md): alcance exacto de Security & Governance V1 — TASK 001.
- [`ai-governance/service-security-hardening-v1.md`](ai-governance/service-security-hardening-v1.md) y [`ai-governance/security-governance-v1-closure.md`](ai-governance/security-governance-v1-closure.md): endurecimiento de TASK 005 y evidencia/límites del cierre de TASK 006.
- [`contracts/clinical-read-v1.md`](contracts/clinical-read-v1.md), [`contracts/clinical-federation-v1.md`](contracts/clinical-federation-v1.md) y [`contracts/ai-clinical-federation-v1.md`](contracts/ai-clinical-federation-v1.md): fronteras Java/Python y federación.
- [`contracts/identity-principal-context-v1.md`](contracts/identity-principal-context-v1.md), [`contracts/oidc-provider-integration-v1.md`](contracts/oidc-provider-integration-v1.md), [`design/identity-access-foundation-v1.md`](design/identity-access-foundation-v1.md) y [`adr/ADR-096-identity-provider-agnostic-v1.md`](adr/ADR-096-identity-provider-agnostic-v1.md): arquitectura y contratos de diseño IAM TASK 001 aprobados, inventario real, límites de confianza y criterios para TASK 002; aún no son capacidades implementadas.
- [`design/identity-keycloak-lab-v1.md`](design/identity-keycloak-lab-v1.md): fixture TASK 002 opt-in, imagen fijada, operación y limpieza por propiedad, evidencia y pendientes; sus pruebas no validan OIDC de producto.
- [`contracts/python-oidc-workload-v1.md`](contracts/python-oidc-workload-v1.md), [`contracts/oidc-workload-security-audit-v1.md`](contracts/oidc-workload-security-audit-v1.md) y [`design/python-oidc-resource-server-v1.md`](design/python-oidc-resource-server-v1.md): TASK 003, activación explícita, perfil, bindings, auditoría propia y evidencia acotada; sin adopción humana ni clínica.
- [`contracts/trusted-identity-registry-v1.md`](contracts/trusted-identity-registry-v1.md) y [`design/trusted-identity-registry-v1.md`](design/trusted-identity-registry-v1.md): TASK 004, esquema/CLI, selección organizacional, revocación local, auditoría de cambios y evidencia determinista/live aprobadas para laboratorio; integración en main pendiente.
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
