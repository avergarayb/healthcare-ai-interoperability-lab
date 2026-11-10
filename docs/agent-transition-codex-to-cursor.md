# Healthcare AI & Interoperability Lab
## Transferencia de contexto y responsabilidad: Codex → Cursor

- **Fecha de corte:** 10 de noviembre de 2026
- **Estado:** Verificado por Cursor en TRANSITION-001 el 10 de noviembre de 2026. TRANSITION-002 lo deja en el árbol de trabajo de la rama documental, todavía sin commit ni publicación.
- **Ruta objetivo en el repositorio:** `docs/agent-transition-codex-to-cursor.md`
- **Nuevo ejecutor técnico:** agente de Cursor, **un solo agente y un mismo chat continuo**.
- **Product Owner:** conserva la aprobación del alcance, pruebas, publicación y secuencia de tareas.
- **Separación operativa:** Codex pasa al trabajo de CNL. No trasladar archivos, stashes ni contexto de CNL al laboratorio.

> **Advertencia de vigencia:** esta transferencia resume decisiones, código y evidencias conocidas al cierre de C02. El estado real de `main`, del workspace y de los tests se verifica con Git y la ejecución local. Ningún resumen o documento histórico concede permiso para implementar la siguiente tarea.

---

## 1. Registro Git confirmado y trazabilidad

Repositorio: `avergarayb/healthcare-ai-interoperability-lab`.

| Entregable | PR | Estado | Evidencia de referencia |
|---|---:|---|---|
| Enterprise Connector Authorization — TASK 001 | #109 | Integrada | Arquitectura, contratos y ADR-097 |
| Enterprise Connector Authorization — TASK 002 | #110 | Integrada | Política y fixture sintético |
| Enterprise Connector Authorization — TASK 003 | #111 | Integrada | Control plane SQLite A/B |
| Enterprise Connector Authorization — TASK 004 | #112 | Integrada | Graph app-only **offline** |
| Enterprise Connector Authorization — TASK 005 | #113 | Integrada | Workflow LangGraph offline de cuatro nodos |
| Enterprise Connector — DEMO-001 | #114 | Integrada | Demostración manual offline de lectura y auditoría |
| Enterprise AI Processing — DESIGN-001 | #115 | Integrada | Arquitectura Gate C y threat model |
| Enterprise AI Processing — TASK-C01 | #116 | Integrada | Evaluador puro Gate C |
| Enterprise AI Processing — TASK-C02 | **#117** | **Integrada el 10/11/2026** | Gateway fake, ledger y auditoría C |

- **C02, commit funcional:** `36b8a75d867de69871a99ac37d175e88c8bff088`
- **C02, commit de merge:** `3c3fc67df9a1da647046595395b084c2aca12e62`
- **C01, commit funcional:** `96d94bfadba6e87a0beb7d3c98d70b6395e22681`
- **C01, commit de merge:** `6dea63b149e14c85fa466dce4dca7df63abf67f5`
- **DESIGN-001, commit:** `a422862d4c7be0264569d5d5c572f8e8b0ec953b`
- **DESIGN-001, merge:** `6ab970ffee703991c9976a687a1c1533e63b207d`

URL PR C02: https://github.com/avergarayb/healthcare-ai-interoperability-lab/pull/117

La página de GitHub confirmó el PR #117 fusionado hacia `main` y su SHA de merge. **Eso no sustituye la comprobación de cada sesión.** TRANSITION-001, con `git fetch` y `merge-base --is-ancestor`, confirmó que `origin/main` contiene `36b8a75` y `3c3fc67`. `main` local puede seguir atrás; no se actualiza sin autorización.

### Comprobaciones de Git obligatorias (solo lectura)

Desde el repositorio, inspeccionar al menos:

```powershell
git status --short --branch
git branch --show-current
git rev-parse HEAD
git fetch origin
git rev-parse origin/main
git merge-base --is-ancestor 36b8a75d867de69871a99ac37d175e88c8bff088 origin/main
git merge-base --is-ancestor 3c3fc67df9a1da647046595395b084c2aca12e62 origin/main
git log --oneline --decorate -12 origin/main
git diff --name-status
git diff --cached --name-status
git ls-files --others --exclude-standard
git stash list
```

Confirmar el código de salida de `merge-base`; no inferir éxito por falta de salida. No actualizar destructivamente `main`, no hacer checkout si pudiera afectar cambios ajenos y no aplicar stashes. Verificar los SHA-256 de los ocho archivos no rastreados protegidos reportados antes de C02 **si aún existen**, sin asumir que el inventario local sigue igual. El stash anterior tenía OID `492986769807c0b749ad34de71f6588e25413f68`; verificar si sigue presente, sin abrirlo, aplicarlo, eliminarlo o sobrescribirlo.

---

## 2. Visión del producto y fronteras

El laboratorio explora **interoperabilidad sanitaria, orquestación de agentes y autorización empresarial de procesamiento de documentos**. No es una plataforma SaaS lista para clientes reales.

Arquitectura general, que debe contrastarse con el código actual:

- **Java 21 / Spring Boot / FHIR R4:** servicios clínicos, normalización e integración; Mini HIS, Mini LIS y flujos de federación clínica según sus contratos.
- **Python / FastAPI / LangGraph:** orquestación y flujos de IA; rutas clínicas existentes aisladas de la nueva funcionalidad empresarial.
- **Enterprise Connector Authorization:** frontera de lectura/autorización, auditoría y adaptador Microsoft Graph **simulado/offline**.
- **Enterprise AI Processing Authorization:** evaluación Gate C, gateway fake offline y auditoría de procesamiento C.
- **Persistencia actual de laboratorio:** varias SQLite con ámbitos separados; ninguna transacción distribuida entre ellas.
- **Destino empresarial propuesto:** PostgreSQL, sujeto a evaluación y migración independientes **después de DEMO-002 y antes de cualquier piloto con datos reales**.

No considerar como funcionalidad implementada: autenticación corporativa de personas, Graph live, modelo LLM empresarial real, RAG, embeddings, MCP, permisos delegated de Graph, indexación Gate D, producción multinodo, entrega final empresarial de respuestas.

### Autoridades que nunca deben fusionarse por conveniencia

1. Identidad de plataforma.
2. Autorización local del conector (Gate A/B).
3. Autorización externa del recurso.
4. Autorización para procesamiento con IA (Gate C).
5. Credenciales/perfil del proveedor del modelo.
6. Autorización del destinatario final.

Gate A permite consulta; B permite entrega bajo su contrato; C autoriza procesamiento para modelo/destino/política exactos; D cubre indexación/retención de derivados y permanece **DISABLED**. A/B no conceden C, C no concede B/D y una credencial API nunca concede autorización de datos. El flujo antiguo del conector conserva **Gate C DENY** y **Gate D DISABLED**.

---

## 3. Documentación de autoridad — lectura en este orden

La estructura relativa se refiere a la ruta objetivo de este archivo, dentro de `docs/`.

### 3.1 Instrucciones, producto, arquitectura

1. [`../AGENTS.md`](../AGENTS.md) — instrucciones operativas prevalentes del repositorio.
2. [`agent-handoff.md`](agent-handoff.md) — contexto compartido. **Contiene en algunos apartados estados históricos que quedaron obsoletos tras el PR #117**: verificar Git antes de repetirlos.
3. [`PROJECT.md`](PROJECT.md), [`roadmap.md`](roadmap.md) y [`architecture/README.md`](architecture/README.md).
4. [`adr/ADR-097-enterprise-connector-authorization-boundaries.md`](adr/ADR-097-enterprise-connector-authorization-boundaries.md).

### 3.2 Conectores y demostración previa

- [`contracts/enterprise-connector-authorization-v1.md`](contracts/enterprise-connector-authorization-v1.md).
- [`design/enterprise-connector-authorization-v1.md`](design/enterprise-connector-authorization-v1.md).
- [`design/enterprise-connector-threat-model-v1.md`](design/enterprise-connector-threat-model-v1.md).
- [`design/enterprise-connector-synthetic-fixture-v1.md`](design/enterprise-connector-synthetic-fixture-v1.md).
- [`design/enterprise-connector-control-plane-v1.md`](design/enterprise-connector-control-plane-v1.md).
- [`design/microsoft-graph-app-only-adapter-v1.md`](design/microsoft-graph-app-only-adapter-v1.md).
- [`design/langgraph-enterprise-connector-integration-v1.md`](design/langgraph-enterprise-connector-integration-v1.md).
- [`demos/enterprise-connector-demo-001.md`](demos/enterprise-connector-demo-001.md).
- [`design/enterprise-connector-maintainability-demo-001.md`](design/enterprise-connector-maintainability-demo-001.md) — deudas M01/M02.

### 3.3 Procesamiento empresarial con IA

- [`design/enterprise-ai-processing-authorization-v1.md`](design/enterprise-ai-processing-authorization-v1.md) — arquitectura de DESIGN-001.
- [`contracts/enterprise-ai-processing-authorization-v1.md`](contracts/enterprise-ai-processing-authorization-v1.md) — contratos C y auditoría.
- [`design/enterprise-ai-processing-threat-model-v1.md`](design/enterprise-ai-processing-threat-model-v1.md) — AI-T01 a AI-T18.
- [`design/enterprise-ai-processing-implementation-plan-v1.md`](design/enterprise-ai-processing-implementation-plan-v1.md) — roadmap.
- [`design/enterprise-ai-processing-policy-fixture-v1.md`](design/enterprise-ai-processing-policy-fixture-v1.md) — runbook C01.
- [`design/enterprise-ai-processing-gateway-audit-task-c02-proposal.md`](design/enterprise-ai-processing-gateway-audit-task-c02-proposal.md) — Phase A, DDL, fallos y decisiones del PO.
- [`design/enterprise-ai-processing-gateway-audit-task-c02.md`](design/enterprise-ai-processing-gateway-audit-task-c02.md) — implementación C02, pruebas y límites; **fuente principal del cierre técnico**.

Si una ruta cambia o falta, informar, no inventar reemplazos. No promover documentación histórica a una autorización nueva.

---

## 4. Componentes Python que debe reconocer Cursor

### Gate C puro, TASK-C01 — conservar sin cambios

- `services/ai-service/app/enterprise_ai_processing/__init__.py`
- `services/ai-service/app/enterprise_ai_processing/models.py`
- `services/ai-service/app/enterprise_ai_processing/policy.py`
- `services/ai-service/tests/enterprise_ai_processing_fixture.py`
- `services/ai-service/tests/test_enterprise_ai_processing.py`

**Contrato:** `ALLOW_PROCESSING` es únicamente elegibilidad metadata-only, no una lease ni permiso portable de ejecutar. `DENY` y `UNAVAILABLE` preservan sus significados. El issuer de autoridad es solo sintético/test-owned; se rechazan copias, reconstrucciones y permisos parciales combinados. La versión registrada del recurso NO es un eTag Graph verificado.

### Gateway y auditoría TASK-C02 — Windows offline

- `services/ai-service/app/enterprise_ai_processing/execution_types.py`
- `services/ai-service/app/enterprise_ai_processing/gateway.py`
- `services/ai-service/app/enterprise_ai_processing/fake_model.py`
- `services/ai-service/app/enterprise_ai_processing/sqlite_ledger.py`
- `services/ai-service/app/enterprise_ai_processing/migrations/001_processing_ledger.sql`
- `services/ai-service/tests/enterprise_ai_processing_execution_fixture.py`
- `services/ai-service/tests/test_enterprise_ai_processing_architecture.py`
- `services/ai-service/tests/test_enterprise_ai_processing_schema.py`
- `services/ai-service/tests/test_enterprise_ai_processing_gateway.py`
- `services/ai-service/tests/test_enterprise_ai_processing_ownership.py`
- `services/ai-service/tests/test_enterprise_ai_processing_ledger.py`
- `services/ai-service/tests/test_enterprise_ai_processing_privacy.py`
- `services/ai-service/tests/test_enterprise_ai_processing_concurrency.py`

La prueba AST original de C01 fue modificada **solo en su ámbito arquitectónico** para vigilar explícitamente los tres módulos puros. La nueva suite AST C02 aplica restricciones diferenciadas por componente. No debilitar ninguna al introducir C03.

---

## 5. Semántica de ejecución C02 y sus límites

Modelo admitido exclusivamente: `fake-enterprise-extractive-v1`; destino `in-process-offline`; sin SDK, red, herramientas, hilos de fondo, fallback, caching o proveedores reales. El fake produce un candidato técnico extraído de bytes sintéticos, **no una respuesta entregada a usuarios**.

### Persistencia C

Base SQLite independiente, solo metadata, con cinco tablas: `aip_store`, `aip_profile`, `aip_grant`, `aip_execution` y `aip_audit`. Cinco índices adicionales. Migración propia `001_processing_ledger.sql`. No unirlas por `ATTACH` al SQLite del conector. No persistir documentos, preguntas, prompts, candidatos, fragmentos, digests ni secretos.

### Fases transaccionales

| Hito | Hecho confirmado | Restricción |
|---|---|---|
| T1 | Reserva + INTENT + lease ISSUED + auditoría en commit | Ninguna lease antes de commit confirmado |
| T2 | Lease consumida mediante CAS, CONSUMED | Consumo único; no reemitir por UUID/reinicio |
| T3 | Entrada **realmente observada** al wrapper fake, ENTERED, audit en commit | Entrada no significa núcleo procesado ni respuesta entregada |
| T4 | Resultado técnico observado y finalización en commit | Fallo o commit ambiguo suprime candidato; no replay |

Estados relevantes: `INTENT`, `CONSUMED`, `ENTERED`, `COMPLETED`, `INVALID`, `FAILED`, `CANCELLED`, `TIMED_OUT`, `REVOKED`, `EXPIRED`, `UNKNOWN`. Reservas `HELD`, `RELEASED`, `CHARGED`, `UNCERTAIN`. `UNKNOWN/UNCERTAIN` no se convierten silenciosamente en éxito, no liberan cuota incierta y no habilitan reintentos automáticos. Reconciliación administrativa solo metadata.

### Límites sintéticos C02

- 1 fuente, máximo **1024 bytes UTF-8**.
- Pregunta allowlisted, máximo **256 bytes UTF-8**.
- Input completo, incluidas instrucciones/framing/metadata, máximo **2048 bytes**.
- Output máximo **512 bytes** y **256 unidades fake-byte-v1**, sujeto al menor límite.
- Deadline máximo cinco segundos, cero retries.
- Un slot activo por organización/instancia/perfil.

`fake-byte-v1` NO equivale a tokens comerciales.

### Autorización, concurrencia y ownership

El gateway reutiliza C01 por grant completo. Revalida A/B y C contra evidencias reconocidas y revisiones vigentes. La lease no es bearer token ni se recupera desde la DB. El coordinador exclusivo usa un lock de sistema operativo **probado en Windows**. El backend C02 **rechaza POSIX antes de abrir archivos**; no presentar Linux/macOS como operativamente soportados. La barrera de admisión solo controla writers **coordinados** del fixture. Writers externos independientes pueden revocar durante una ventana posterior al último chequeo antes de entrada física: C02 no garantiza revocación global. Ninguna transacción SQLite queda abierta durante el procesamiento fake.

### Privacidad/cancelación

Owner efímero por invocación; cleanup independiente; `CancelledError` y `KeyboardInterrupt` se preservan. Canarios revisados en tablas, WAL, logs, repr y tracebacks propios retenidos. No prometer borrado criptográfico, aislamiento frente a host comprometido ni ausencia de copias fuera del owner.

---

## 6. Evidencia final — números y alcance exactos

Resultados anteriores al merge C02, reportados en tres ejecuciones offline separadas, con guards de red/DNS activos antes de colección:

| Suite | Evidencia |
|---|---:|
| C02 | **224 PASS** |
| C01 | **192 PASS** |
| Conectores TASK 002 | 145 PASS |
| Conectores TASK 003 | 75 PASS |
| Conectores TASK 004 | 158 PASS |
| Conectores TASK 005 | 196 PASS |
| DEMO-001 | 43 PASS |
| **Total** | **1033 PASS, 1 SKIPPED heredado** |

La omisión histórica está relacionada con symlink físico Windows. La prueba física específica Windows de C02 también permanece pendiente: no convertirla en PASS. La documentación C02 declara 16 grupos de aceptación, con C02-10 acotado a writers coordinados y C02-11 parcialmente bloqueado por plataforma/filesystem.

Esas cifras son **evidencia del commit C02 al cierre**, NO afirmación de que Cursor acaba de ejecutar las pruebas. Cursor deberá preparar un plan de pruebas proporcionado a la tarea que el PO autorice.

---

## 7. Riesgos y deuda técnica que C03 debe respetar

### Bloqueantes arquitectónicos antes de la entrega final

1. **Dos stores independientes A/B y C:** no hay atomicidad distribuida. No afirmar que dos commits independientes dan garantía de revocación/entrega conjunta. Las ventanas `T_auth` y `T_ext` siguen abiertas y deben probarse con escrituras y contención reales cuando C03 se diseñe.
2. **Entrega final B/C:** revalidación del destinatario, permisos y revisiones justo antes de entregar; fallo parcial o autorización incierta suprime contenido. No inferir recepción humana de un evento de entrega.
3. **Evidencia documental confiable:** organización/tenant/instancia/recurso/clasificación, bytes originales, versión registrada y revisión de contenido deben permanecer ligados al owner y al contexto. Documento/pregunta/prompt no otorgan permisos.
4. **Grounding extractivo:** verificar offsets/fragmentos contra bytes y revisión de fuente; abstenerse cuando no exista evidencia suficiente. El modelo fake no prueba grounding genérico de un LLM.
5. **Cancelación y memoria:** no introducir nuevas capturas de contenido en LangGraph State, checkpointer, callbacks, logs, tracing o tracebacks. Mantener ownership aislado y señales primarias.
6. **Puerto de entrega derivada:** M02 exige una propuesta pública y acotada antes de llamar helpers privados (`_validate_delivery`, `_event`). Obtener autorización específica del PO para cualquier cambio en ConnectorService o el workflow anterior.
7. **Plataforma Windows:** el gateway C02 solo funciona en Windows offline; no activar C03 contra POSIX ni afirmar paridad.
8. **Exclusividad/revocación:** no extender la barrera coordinada a writers externos o Graph live por suposición.

### Deudas ya reconocidas, no refactorizar sin alcance

- **M01:** manejo de refs, frames y cleanup del workflow LangGraph empresarial previo; sensibilidad ante cambios de Python/LangGraph.
- **M02:** acoplamiento a métodos privados de ConnectorService para entrega; posible puerto público de entrega derivada.
- **P2 C02:** `gateway.invoke_once` (61 líneas), transiciones de ledger, lista de campos sensibles de cleanup repetida y acoplamiento del fixture a C01; conservar las pruebas y proponer mejora solo al justificar un cambio concreto.
- **Infraestructura:** POSIX no soportado, symlink físico de archivo Windows pendiente, dos stores, SQLite de laboratorio, no IAM empresarial ni custodias de credenciales productivas.
- **Documentación:** `docs/agent-handoff.md` contenía estados anteriores al PR #117. TRANSITION-002 actualiza el índice vigente y conserva el relato histórico. ADR-097, DESIGN-001, contratos, amenazas y runbooks de cierre no se reescriben.

---

## 8. Hoja de ruta y próximo incremento candidato

1. **Transferencia a Cursor:** TRANSITION-001 completó la inspección de solo lectura. TRANSITION-002 actualiza el índice vigente en la rama documental. Sigue sin implementar C03 y sin commit hasta la revisión del Product Owner.
2. **TASK-C03 (sujeta a nuevo prompt PO):** integrar flujo LangGraph empresarial con fuente reconocida, gateway C02, grounding/verificación y decisión final B/C, sin elevar permisos, preservando límites y auditoría. No abrir modelos reales, Graph live, RAG ni MCP.
3. **DEMO-002 (sujeta a aprobación):** pregunta/respuesta sobre documento **sintético** con días y antigüedad explícitos; ejecución interactiva, denegaciones, revocación, sin evidencia, auditoría y no entrega en fallos. El fixture antiguo de vacaciones de DEMO-001 no contiene número de días; no inventarlo.
4. **TASK-C04 (posterior, no autorizada):** evaluar proveedor real (seguridad, región, retención, credenciales, límites, coste y contratos). Ningún proveedor autorizado por el solo uso de ChatGPT.
5. **PG-EVAL/MIGRATION (posterior a DEMO-002 y antes de datos reales):** evaluar PostgreSQL y consolidación transaccional local A/B/C, multitenancy, CAS, revocación, migraciones y backups. No trasladar leases de laboratorio como autoridad.

Ninguno de los puntos 2–5 está autorizado por el mero merge C02.

---

## 9. Protocolo de trabajo para Cursor

- **Un agente, una conversación continua.** No repartir subtareas entre operadores ni asumir handoff humano adicional.
- Primero **leer** AGENTS, handoff, contrato, arquitectura, amenazas, plan y código real. Después verificar Git y emitir informe. No iniciar una TASK por iniciativa del agente.
- Cada prompt de implementación debe llevar título **EPIC** y nombre de TASK, alcance exacto, archivos autorizados, pruebas positivas/negativas y reporte paso a paso.
- Las tareas de código se ejecutan en rama específica nacida de `origin/main` integrado, siempre tras inspeccionar trabajo preexistente y aprobación PO. No modificar `main` local innecesariamente.
- Proteger ocho untracked ajenos si siguen presentes, stashes (OID histórico indicado), hashes y cambios de otro trabajo. No ejecutar `git reset`, `git clean`, `git add .`, `git add -A` ni force push. Staging por rutas explícitas tras autorización.
- No contactar ni modificar `local-hapi`. No iniciar Docker, Keycloak, Graph live ni servicios clínicos por defecto. No alterar `.pytest-tmp`, ACL, migraciones históricas ni worktrees ajenos.
- No modificar Java/FHIR, IAM, Model Boundary clínico, Human Review, gateways ni conexiones externas fuera de un alcance expresamente aprobado.
- No abrir permisos C/D desde variables, herramientas, documentos o prompts. Mantener los tests AST C01 y C02 y guards de socket/DNS.
- Reportar en **detalle** comandos ejecutados, paths, diffs, decisiones, resultados, skips/bloqueos, integridad, seguridad y riesgos. No afirmar PASS de validaciones no ejecutadas.
- **Secuencia Git:** implementar → revisión del PO → autorización separada de commit/push → revisión del PO → creación de PR autorizada → merge manual por el usuario → siguiente tarea. Para documentación de transferencia, también requerir permiso antes de staging/publicación.

## 10. Primer entregable del agente Cursor (solo lectura)

Antes de cualquier cambio, responder con un informe en español que incluya:

1. Ruta y rama del repositorio actual, HEAD, `origin/main`, merge #117 y estado Git.
2. Verificación de los commits C01/C02 y los documentos existentes.
3. Archivos ajenos y stashes preservados (sin inventar estado si han cambiado).
4. Resumen de componentes Java/Python, con foco en conectores empresariales y Gate C.
5. Mapa de autoridades A/B/C/D y qué rutas son solo offline.
6. Contratos, esquemas y puertos realmente implementados en C01/C02.
7. Estado de pruebas **histórico** frente a pruebas **ejecutadas por Cursor**.
8. Restricciones Windows, carreras, UNKNOWN, auditoría, privacidad y M01/M02/P2.
9. Discrepancias entre este documento, handoff histórico y código real.
10. Propuesta concreta de actualización documental mínima, sin editar todavía.
11. Boceto arquitectónico de C03 **sin implementar** y preguntas bloqueantes para el PO.
12. Confirmación de cero cambios, cero servicios live y cero publicación.

**Stop:** esperar validación del Product Owner. No crear rama de implementación C03 ni comenzar coding hasta nueva autorización.
