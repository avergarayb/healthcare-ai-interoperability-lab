# TASK-C01 — Gate C Policy Evaluation & Trusted Synthetic Fixture

Estado: **implementación C01 de laboratorio; revisión final y commit/push de siete rutas autorizados por el Product Owner, condicionados a controles satisfactorios**. No PR ni merge. DESIGN-001 está integrada por PR #115. La autorización actual permite revisar/corregir exclusivamente C01, repetir sus pruebas/regresiones y publicar su rama, no C02/C03/C04 o DEMO-002. Una decisión `ALLOW_PROCESSING` significa elegibilidad de política; **no autoriza ejecutar ningún modelo**, ni siquiera fake. Gate C del servicio anterior sigue DENY y D DISABLED.

Autoridad: [arquitectura aprobada](enterprise-ai-processing-authorization-v1.md), [contrato C](../contracts/enterprise-ai-processing-authorization-v1.md), [amenazas](enterprise-ai-processing-threat-model-v1.md), [plan](enterprise-ai-processing-implementation-plan-v1.md), [ADR-097](../adr/ADR-097-enterprise-connector-authorization-boundaries.md), [contrato de conectores](../contracts/enterprise-connector-authorization-v1.md) y [deudas M01/M02](enterprise-connector-maintainability-demo-001.md). Sus permisos de publicación anteriores son históricos; la autorización expresa posterior del PO habilita únicamente esta revisión final/publicación C01. Los cuatro documentos DESIGN-001 y contratos base permanecen sin cambios.

## Objetivo y arquitectura mínima

Declarar elegible una solicitud exacta solo si satisface todos los controles C representables en este incremento. Módulo opt-in [app/enterprise_ai_processing](../../services/ai-service/app/enterprise_ai_processing/), sin wiring en `main.py`, settings, endpoints, LangGraph, Java o Model Boundary clínico. Solo biblioteca estándar y los tipos/puertos de política existentes. Sin nuevas dependencias ni framework de políticas/proveedores.

| Archivo | Responsabilidad |
|---|---|
| [models.py](../../services/ai-service/app/enterprise_ai_processing/models.py) | Records internos frozen/slots, perfil fijo, vocabulario cerrado y puerto de reconocimiento; no deserialización ni issuer productivo |
| [policy.py](../../services/ai-service/app/enterprise_ai_processing/policy.py) | Evaluación determinista sobre snapshots/evidencia ya capturados, sin efectos externos |
| [fixture](../../services/ai-service/tests/enterprise_ai_processing_fixture.py) | Solo tests: organización A/B, emisor por identidad de objetos, configuración reconocida, owner de recibo A/B y reloj existente |
| [suite C01](../../services/ai-service/tests/test_enterprise_ai_processing.py) | Positivas/negativas, aislamiento, límites, ausencia de efectos y preservación del servicio anterior |

Interfaz interna: `GateCPolicyEvaluator(existing_policy, trusted_boundary).evaluate(connector_snapshot, processing_policy, envelope, evidence)`. La aplicación que compone esos puertos es confiable; no se ofrece una API para que un usuario final suministre el evaluador, la fábrica o una configuración de autoridad. No hay registro global mutable, autenticación duplicada ni persistencia C.

## Contratos implementados y conceptuales

Implementados mínimamente: `AIProcessingEnvelope`, `AIProcessingGrant`, `ModelProcessingProfile`, `SourceEvidence`, `ProcessingLimits`, snapshot `AIProcessingPolicy`, `AIProcessingDecision` y puerto `ProcessingBoundary`. Envelope reutiliza `ConnectorExecutionContext` y `OperationRequest`, ligando principal/organización a través del contexto existente y lectura/propósito/destinatario mediante el request cerrado. Añade ID de operación, binding/tenant/fuente, versiones/revisiones, expiración, pregunta y presupuesto declarado.

El puerto reconoce envelope, snapshot de configuración y evidencia; **no sustituye IdentityBoundary**. La identidad sigue comprobándose por `PolicyEvaluator` existente. Copiar una dataclass, una correlación o un ID no concede autoridad. Tipos exactos, extras rechazados por constructores, IDs canónicos, UTC, bool/int diferenciados y registros cerrados se comprueban antes de permitir. Los constructores internos no son parsers de entrada HTTP.

No implementados: `ProcessingApproval` humano/productivo, leases, ledger de ejecución C, BudgetReservation, gateway, ModelRequest/ModelResult, tokenizer, respuesta/grounding, auditoría durable C, store C o transacciones entre stores. No crear un índice/recuperación por operation ID. C02/C03/C04 necesitan autorización propia; las carreras `T_auth`/`T_ext` siguen siendo condiciones futuras de integración, no garantías de C01.

## Frontera y evidencia de test

Cada fixture crea su propio laboratorio en memoria de TASK 002. Primero ejecuta **el puerto público `ConnectorService.execute`** para una lectura documental sintética satisfactoria A/B. Solo en ese setup obtiene un documento y sus eventos existentes in-memory; después captura fuente, correlación, bytes UTF-8, versión registrada y revisión de contenido de test en un owner privado. No usa helpers privados ni Graph real y no crea SQLite.

El issuer de test registra únicamente objetos exactos de su fixture. La evidencia debe corresponder al mismo contexto y request **por identidad**, operación de procesamiento, documento propio, revisión y correlación del recibo real. El owner frozen/slots se crea después del resultado A/B y queda ligado al `operation_id` emitido; reetiquetar el envelope con otro UUID o trasladar un recibo entre invocaciones no lo reasocia. No es una lease ni un contador: una evaluación puede repetirse dentro de su vigencia sin ejecutar nada. El owner comprueba el texto original y su conteo de bytes, sin digests criptográficos. Una fuente copiada, bytes sustituidos incluso con igual longitud, correlación inventada o recibo de B para A se rechazan. El app recibe metadata, no el texto del documento. `registered_version` no es eTag Graph; `content_revision` es revisión propia del fixture, no una versión Microsoft verificada.

ORG-A/ORG-B tienen contextos workload, grants, instancias y tenants propios; IDs externos documentales y nombre nominal del perfil se repiten deliberadamente sin unir ámbitos. No hay empleado humano autenticado, JWT, binding delegado o administración IAM. El owner y los helpers de emisión/configuración están solo en tests, no en la composición productiva. La identidad de objetos/frozen no protege de código malicioso con control del proceso; no es un sandbox.

## Reutilización A/B y evaluación C

El evaluador no adquiere ni lee: reutiliza `PolicyEvaluator.evaluate` público sobre el snapshot reconocido, primero con A (`Gate.READ`) y luego con B (`Gate.DELIVERY`). El motor existente resuelve identidad/organización/instancia/tenant/recurso/grants/scope/validez; C01 no copia ese algoritmo ni llama `_validate_delivery` o `_event`. La frontera de test revalida además el permiso externo **simulado** mediante el puerto público `SyntheticDocumentAdapter.authorize_delivery`: consulta de memoria sin red, nuevas lecturas, broker o auditoría. Así un retiro conocido en el doble invalida la evidencia. La evidencia reconocida acredita una lectura/decisión de entrega sintéticas anteriores; no recepción humana ni frescura externa Graph. Una revalidación A/B fallida no se sustituye por un grant C. Estos recognizers deben ser puros; no conectarlos incidentalmente a un adaptador live.

Después coteja bindings de evidencia y envelope; exige perfil fijo propio y un solo grant C completo que coincida en principal/tipo, organización/instancia/tenant/recurso, operación y propósito de lectura, operación/propósito IA, clasificación, perfil/versionado y destinatario. Ninguna unión de parciales. Revisión nueva, estado deshabilitado o expiración invalidan; no renueva envelope ni conserva ALLOW entre evaluaciones. No escribe registros, contadores, auditoría, archivos o snapshots durante `evaluate`.

Único perfil: `fake-enterprise-extractive-v1`, provider `fake`, modelo/versionado fijos, destino `in-process-offline`, clasificación `synthetic-internal`, propósito `synthetic-policy-question-answering`, retención `ephemeral-no-retention` y declaración futura `fake-byte-v1`. Son datos de configuración sintética reconocida, no una implementación fake ni garantías comerciales. Otro proveedor/modelo/región/destino/retención desconocida deniega; no fallback a settings o credenciales heredadas. Pregunta/documento no seleccionan ninguna autoridad.

La aprobación del grant debe declararse expresamente `not_required` para este fixture. No hay default implícito, exención por documento ni aprobación por ser administrador. Una aprobación requerida no satisfecha deniega; verificar aprobaciones reales requerirá contrato/implementación posterior.

## Límites y vigencia

Una fuente; máximo 1024 bytes UTF-8 de fuente y 256 de pregunta exacta allowlisted; presupuesto declarado máximo de input 2048 bytes, output 512 bytes y 256 unidades fake; hasta cinco segundos, cero retries y declaración de una operación concurrente por ámbito, sin reservarla. No truncar ni normalizar silenciosamente la pregunta. No se interpreta texto ni se generan respuestas.

Se mide la fuente en el owner de test y la pregunta en el evaluador. Se valida que el presupuesto de entrada cubra al menos esos bytes conocidos y no supere los límites declarados; no se ensambla un prompt ni se inventa su overhead/consumo de tokens. C02 tendrá que medir/validar la entrada total realmente preparada, incluidos instrucciones y metadata, antes de cualquier transferencia. `fake-byte-v1` sigue siendo un identificador, no tokenizer ejecutado ni equivalencia con tokens comerciales. Los límites efectivos futuros de output seguirán siendo el menor de bytes/unidades; C01 no produce output de modelo.

Límites solicitados deben estar dentro de los caps C fijos, perfil, un grant completo y los límites aplicables del conector. La expiración de la decisión es el mínimo de envelope/contexto, A/B, grant/revisión, perfil/revisión y deadline desde emisión. Usa el reloj ya inyectado en el `PolicyEvaluator` de la composición, no reloj real ni sleeps. Evaluar otro snapshot es una nueva decisión, sin atomicidad SQLite, reservas o garantía de ejecución futura. La composición confiable debe aportar y reconocer el snapshot vigente (`refresh_connector` en tests); el evaluador puro no consulta stores ni descubre revocaciones no observadas. Un snapshot retirado de esa frontera se rechaza por identidad. La frescura transaccional/global no se demuestra en C01.

## Resultados y tratamiento de fallos

| Outcome | Semántica |
|---|---|
| `ALLOW_PROCESSING` | Elegibilidad completa bajo los inputs reconocidos actuales; metadata propia y expiración, sin contenido ni capacidad de ejecución |
| `DENY` | Regla verificable incumplida: identidad/contexto/evidencia no reconocidos, ámbito/perfil/propósito/clase/retención/approval inválidos, revisión vieja, revocación o límites |
| `UNAVAILABLE` | Autoridad indispensable lanza error/devuelve prueba no booleana, configuración íntegra no verificable o fallo del puerto A/B; sin fallback |

Razones cerradas en `ProcessingReason`; ningún mensaje/objeto de excepción subyacente se devuelve. Denegaciones/indisponibilidades no copian IDs ni organización de inputs ajenos. El resultado positivo solo contiene outcome, razón, operación, organización/recurso propios, revisiones y expiración; no pregunta/documento/contexto/grant/token/API key/digest. No sirve como envelope ni como capacidad del broker anterior. No hay handler que ejecute una decisión.

## Pruebas y evidencia

Evidencia histórica de implementación: **174 PASS en 0,31 s**. Las repeticiones intermedias de 140/158/162/163/169/171/172 son subconjuntos históricos del desarrollo, no se suman. Incluye llamadas A/B observadas, fallos de esos puertos, rechazo de copias/subclases/configuración corrupta, grants parciales, fuente/tenant/perfil/clase/retención/approval, límites exactos/+1 y UTF-8, expiración/revisión/retiro, evaluaciones paralelas A/B, señales de configuración clínica ignoradas y C/D anteriores aún denegados. Las negativas distinguen UTF-8 inválido (DENY, no fallo de dependencia), observación del recibo alterada y revocación externa simulada conocida; no cambian módulos anteriores.

Revisión final de seguridad: **192 PASS en 0,41 s**, tras las correcciones descritas abajo, guard socket/DNS y cero intentos externos observados. Son 18 casos adicionales: operación/owner de recibos, tipos escalares/fechas del contexto, reconstrucciones manuales, request equivalente no original, correlación/código B ajenos, snapshots retirados y entradas maliciosas concurrentes con evaluaciones válidas A/B. No se suman las repeticiones intermedias.

Se reprodujeron dos defectos C01 mediante inyección explícita de registros de test confiables: recibo reasociable a otro UUID/otra invocación del mismo contexto y aceptación de subclases escalares en el contexto. La primera selección negativa dio **6 FAIL / 1 PASS**; una primera corrección parcial dejó un fallo porque los tipos del módulo anterior son anotaciones diferidas. Ahora el owner liga operación/request originales y el validador reconoce tipos primitivos tanto directos como diferidos, sin evaluar expresiones de anotación. No se modificó la fábrica de identidad ni la política anteriores. Los casos ya pasan, sin inferencia ni autoridad portable; no se reprodujo un P0 ni una fuga cross-org. Estas pruebas no simulan protección frente a un host/emisor comprometido.

Una prueba bloquea open/SQLite/servicio/broker/lectura/auditoría durante evaluación y compara contadores antes/después: cero efectos C01. Las pruebas AST/imports comprueban namespace aislado, sin dependencias de red/SDK/LLM/LangGraph/store ni wiring raíz. El setup previo sí ejecuta una lectura y auditoría **simuladas en memoria** del motor existente: no confundir esos efectos autorizados de fixture con efectos del evaluador.

Regresiones actuales de revisión final, repetidas después de los cambios de código: **617 PASS, 1 SKIPPED, en 193,23 s**, sin warnings nuevos y con cero intentos externos fuera de los guards. Desglose: 145 TASK 002, 75 TASK 003, 158 TASK 004, 196 TASK 005 y 43 DEMO-001. La omisión es el symlink físico Windows heredado de TASK 003, sin privilegio disponible; no se añadieron skips ni modificaron ACL. Son dos procesos separados: 192 C01 + 617 regresiones = **809 aprobaciones actuales y una omisión**, no una selección conjunta ejecutada de una vez. La ejecución previa de 617/1 en 487,29 s y las anteriores de DEMO-001 son históricas, no evidencia nueva ni aprobaciones adicionales.

Comando focalizado desde `services/ai-service`, con venv existente y nuevo basetemp test-owned:

```powershell
$taskBase = Join-Path (Resolve-Path '..\..\infra\iam-lab\.runtime').Path ('c01-tests-' + [guid]::NewGuid().ToString('N'))
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -B -X utf8 -m pytest -q -x -p no:cacheprovider --basetemp $taskBase tests/test_enterprise_ai_processing.py
```

Las ejecuciones registradas usan `pytest.main` con esos argumentos y guard externo adicional de connect/connect_ex/create_connection/getaddrinfo antes de colección, además del guard de cada suite. Regresiones seleccionadas: `test_enterprise_connector_demo.py`, `test_enterprise_connector_workflow.py`, `test_enterprise_connector_graph.py`, `test_enterprise_connector_control_plane.py`, `test_enterprise_connectors.py`, en proceso con basetemp nuevo `c01-regressions-*`. Solo esas regresiones crean SQLite temporales propias de pruebas existentes; ningún store C o base preexistente se crea/modifica. No ejecutar la suite indiscriminada que consulta HAPI, live, Docker, Keycloak, IAM histórico ni los tres hashes CRLF. No cambiar ACL, timeouts, warnings o skips heredados para obtener verde.

## Amenazas, mantenimiento y límites

Cobertura C01 de AI-T01/02/03/04/07/15: falsificación/cross-org, autoridad desde contenido, perfil y clasificación, evidencia/versión, revocación/tiempo y grants completos/aprobación explícita. Es evidencia de evaluación/fixture, no de inferencia, prompt injection de un LLM, custodia, auditoría C, atomicidad o revocación durante procesamiento. AI-T05/06/08–14/16–18 conservan controles de no activación y dependencias futuras; sus mitigaciones completas siguen pendientes de C02/C03/C04. No declarar los dieciocho riesgos resueltos.

M01/M02 intactas: no nueva introspección ni dependencia de privados del servicio. Funciones separadas para shape, scope/evidencia, perfil, budgets y grant completo; sin motor de scopes duplicado, factory productiva, framework o nuevas dependencias. El receipt owner guarda texto únicamente en tests y no lo exporta al evaluador. No se promete borrado criptográfico, protección ante host comprometido, OIDC humano, producción o garantías de proveedor real.

Mantenibilidad de C01: sin imports circulares ni closures/aliases de autoridad, estado global mutable o manipulación de frames. El acoplamiento nuevo se limita a tipos públicos, snapshots, reloj y evaluación A/B; no depende de LangGraph. Dos observaciones P2 no bloqueantes: `_closed_scalars`/`_ids` dependen de anotaciones y nombres de campos (conservar las pruebas negativas al evolucionar el esquema; una futura anotación no primitiva necesita validador explícito), y el registro por identidad vive durante el fixture (no portable entre procesos, ni emisor productivo ni lifecycle de leases). El predicado de `recognizes_source` centraliza invariantes de owner; cualquier extracción futura debe conservar la comprobación conjunta operación/contexto/request/bytes. No justifica un framework ni refactorización masiva. Las dos correcciones de revisión fueron bloqueantes P1 del contrato de fixture/tipos y quedaron cubiertas por regresión; no se atribuye una elevación productiva a una fábrica de test deliberadamente malformada.

Siguiente paso: revisión del Product Owner del alcance y evidencia C01 tras su publicación autorizada y condicionada a controles satisfactorios. No crear PR/merge ni iniciar C02, gateway, inferencia, DEMO-002, D/RAG/MCP o servicios live sin autorización nueva. Verificar Git en vivo; este documento no fija el estado de publicación como permanente.
