# Enterprise AI Processing V1 — incrementos propuestos y DEMO-002

Estado: **Approved — design only; DESIGN-001**. El Product Owner aprueba la arquitectura base y el roadmap C01–C04; autoriza revisión final, precisiones acotadas y commit/push exclusivamente de los cuatro documentos propios si pasan los controles. No PR ni merge. No autoriza implementar o iniciar TASK-C01/C02/C03/C04, Gate C, LLM real, nuevos endpoints, D/RAG/MCP o TASK 006/007. Toda etapa posterior necesita autorización de ejecución expresa. No sustituye el [plan de siete TASK de conectores](enterprise-connector-authorization-implementation-plan-v1.md).

Referencias: [arquitectura e inventario](enterprise-ai-processing-authorization-v1.md), [contrato C/auditoría](../contracts/enterprise-ai-processing-authorization-v1.md), [amenazas AI-T01–AI-T18](enterprise-ai-processing-threat-model-v1.md), [DEMO-001 integrada](../demos/enterprise-connector-demo-001.md), [mantenibilidad](enterprise-connector-maintainability-demo-001.md), [ADR-097 preservado](../adr/ADR-097-enterprise-connector-authorization-boundaries.md).

## Secuencia y gates de revisión

```text
DESIGN-001 (diseño aprobado, sin implementación)
  -> TASK-C01 (evaluación C pura + fixture)
  -> TASK-C02 (gateway fake + store/audit C)
  -> TASK-C03 (workflow + evidencia + entrega final)
  -> DEMO-002 (consola conversacional sintética)
  -> TASK-C04 (evaluación separada de proveedor real, sin activación implícita)
```

No tareas artificiales para cada dataclass/evento ni framework universal de proveedores. La separación responde a riesgos verificables: política antes de efectos; persistencia/auditoría antes de inferencia; ownership/B final antes de una consola. Fake obligatorio primero. Aceptar un gate o merge no autoriza el siguiente.

### DESIGN-001 — alcance actual

Salida: arquitectura/inventario real, contrato aditivo, amenazas y este plan con DEMO-002. Validación exclusivamente documental: enlaces, coherencia cruzada, vocabularios, requisitos/casos, whitespace, secretos e integridad Git. No se ejecutan suites funcionales/live por cambios solo documentales. No modificar ADR-097, contratos base, AGENTS, handoff, roadmap global ni runbooks históricos para presentarlos como aprobación de C.

El PO acepta como base de diseño C independiente, seis autoridades, contratos aditivos, fake inicial, evidencia de bytes/versiones, auditoría separada, revocación fail-closed, nuevo workflow por composición, B/C finales y quince escenarios de DEMO-002. La aprobación no valida implementación, carreras de dos stores o garantías productivas. El protocolo temporal/puerto público de C03, esquema C de C02 y alcance concreto de cada incremento conservan sus gates de revisión/aprobación específica.

### TASK-C01 — evaluación C mediante fixture (no autorizada)

Incremento mínimo: tipos cerrados de entrada/salida, envelope de procesamiento sintético reconocido ligado a identidad/fuente, grant C completo, perfil fake fijo registrado en el fixture, evaluador C puro y reloj inyectable. Comprobar organización/instancia/tenant/recurso/propósitos/clasificación/perfil/destino/retención/aprobación, vigencia y límites explícitos. Reutilizar controles A/B mediante sus puertos públicos, sin duplicar scopes, cambiar grants antiguos ni retirar el rechazo C/D de `PolicyEvaluator`/`ConnectorService.execute`. El registro del perfil es dato de test, no un servicio/administración nuevos; issuer de test no es IAM comercial.

**Fuera de C01:** base de datos C, auditoría persistente C, BudgetReservation transaccional, emisión/consumo/persistencia de leases de un uso, Model Gateway, invocación fake, workflow LangGraph nuevo, endpoints, interfaces administrativas, SDK de proveedor o procesamiento documental por modelos. Leases/reservas/gateway/auditoría durable pertenecen a C02. Solo crear las entidades mínimas que necesite la evaluación pura, no todo el inventario del contrato por anticipación.

Positiva demostrable: documento propio y perfil explícitos -> `ALLOW_PROCESSING` como evaluación de política, **cero inferencias y ninguna lease** en esta etapa. Negativas: identidad/contexto/copias, organización/tenant/recurso/versión/clasificación/propósito/perfil/destino/retención/budgets, approval faltante, expiración/revocación y grants parciales. Reglas por defecto incompletas -> DENY; política no verificable -> UNAVAILABLE. Probar mismos IDs externos en dos organizaciones y C denegado aunque A/B permitan. Los contadores/gateway futuros no son necesarios para ejecutar C01: verificar ausencia de esos efectos/dependencias. AI-T01–AI-T04/AI-T07/AI-T15 según el alcance puro, no las pruebas de inferencia de etapas posteriores. Gate PO: autorización específica de C01 y, al completar ese incremento, revisión de sus tests/regresiones.

### TASK-C02 — Model Gateway offline y auditoría (no autorizada)

Incremento mínimo: puerto empresarial pequeño con request/result propios, fake determinista puro y contadores; ledger de un uso/reservas con límites; store C SQLite propio con metadata/perfiles/grants y auditoría del contrato. Aprobar esquema, migración **nueva propia**, rutas test-owned y API administrativa sintética antes de crearlos. No modificar esquema/migraciones históricas conector/IAM/clínicos, enums `Phase` ni sink existente. El esquema exacto del conector no admite tablas arbitrarias: no añadir C allí como comodidad.

El gateway no usa `get_llm_provider`, `LLMProvider.generate_summary` ni Gemini settings. No depende de SDK, clave o red. Proveedor/destino/modelo solo desde perfil confiable; constructores de proveedores reales ausentes, no un flag secreto para activarlos.

Positiva: C aprobada + intent/reserva durables -> una invocación fake -> resultado observado, todavía sin entrega humana ni afirmar grounding. Negativas: lease copiada/replay, cambio de perfil/revisión antes de llamada, fallo audit en cada fase, timeout/resultado inválido/oversize, herencia de tracing/live/env, presupuesto/contención/concurrencia y caída entre intent/resultado -> UNKNOWN, sin auto-retry. Probar reapertura SQLite y ausencia de payloads, rollback de cambios C+audit, no fallback a memoria. Espera fake controlada por Event con writer independiente confirma que no hay transacción SQLite retenida durante inferencia. AI-T03/AI-T05/AI-T08/AI-T09/AI-T11–AI-T15/AI-T17. Gate PO: contrato de store/audit aprobado y durabilidad/contador/fallos demostrados.

### TASK-C03 — LangGraph, grounding y entrega derivada (no autorizada)

Incremento mínimo: workflow empresarial nuevo que compone el reader público existente, C y gateway fake; estado metadata-only y owner por invocación. Mantener cuatro nodos y contrato de TASK 005. Añadir evidencia de fuente/versión/bytes y validador extractivo/renderer determinista. Ningún modelo decide permisos ni responde al usuario directamente.

Antes de editar el dueño de ConnectorService, el PO debe aprobar el puerto público acotado de entrega derivada propuesto en arquitectura. Es el segundo consumidor que justifica esa extensión; no copiar `_validate_delivery`/`_event` ni exponerlos como tool. La firma/commit de auditorías y las regresiones son condición bloqueante, no trabajo implícitamente autorizado por DESIGN-001. No resolver M01/M02 mediante refactorización masiva ni retirar las dos decisiones B existentes.

Positiva demostrable: grafo real, una fuente/una pregunta, C previo, una llamada fake, evidencia verificada y respuesta después de B/C finales. Negativas: revocación en cada fase/auditoría/commit, citas/texto sin respaldo, versión/bytes cambiados, pregunta fuera de alcance, contradicción, documento hostil, CancelledError/KeyboardInterrupt y errores close/clear con tracebacks retenidos. Mantener owners ajenos intactos y cero configuración externa capaz de activar saver/callbacks/streaming. Dos stores: orden de guards y fallos de ambos commits, sin prometer atomicidad entre archivos ni I/O dentro del guard. AI-T02/AI-T04–AI-T11/AI-T16–AI-T18. Gate PO: todas las negativas críticas/retención y regresiones existentes pasan antes de una demo nueva; cualquier reproducción bloqueante detiene el avance.

Pruebas bloqueantes adicionales de la secuencia de arquitectura: writers independientes con revocación confirmada antes de `T_auth`; writers que solo intentan confirmar durante guards; commit conector confirmado seguido de fallo C; cambio conector tras liberar su guard y antes de commit C/salida; cambio externo tras `T_ext`; expiración durante finalización y caída con confirmación desconocida. Verificar ausencia de entrega antes de ambos commits y de transacciones durante inferencia/I/O de proveedor. No marcar como resuelta la ventana posterior a `T_auth` ni equipararla a frescura externa. Si una intercalación o exigencia de frescura no puede explicarse/probarse bajo el puerto específicamente aprobado, la integración queda pendiente y vuelve al PO, sin una afirmación de atomicidad distribuida.

### DEMO-002 — walkthrough conversacional (no autorizada)

Ejecutor independiente de laboratorio en `scripts/` propuesto después de C03, reutilizando el workflow/gateway reales del incremento, Graph offline y SQLite propios; no tabla de respuestas constantes del menú. No tocar DEMO-001. Solo biblioteca/dependencias existentes si son suficientes; no nuevo servicio/web/endpoint por anticipación.

Experiencia: seleccionar una identidad **sintética preautorizada** del escenario, formular una pregunta del conjunto pequeño aprobado y recibir respuesta más evidencia. No pedir login corporativo ni texto libre de organización/modelo/tenant/permisos. Cada turno es una nueva operación, sin historial, memoria compartida, cache de respuestas, embeddings o vector DB. El término «conversacional» describe pregunta/respuesta visible, no un agente autónomo con herramientas.

Ejemplo futuro, **no resultado del fixture actual**:

```text
Usuario: ¿Cuántos días de vacaciones establece la política?
Agente: Según la política ficticia autorizada, establece 20 días
        tras 12 meses de servicio, conforme al fragmento citado.
Fuente: Política ficticia ORG-A, revisión documental 1, Graph OFFLINE.
```

El fixture actual contiene «Documento ficticio vacation, organización ORG-A. Sin datos reales.», sin días ni condiciones. La primera implementación debe añadir un **fixture de texto propio** que diga explícitamente «20 días tras 12 meses de servicio», con versión/evidencia y límites aprobados, sin cambiar datos existentes. Sin ese texto el resultado correcto es insuficiencia, no 20 ni otro número. Fake extrae evidencia de los bytes realmente leídos; no responde por el ID de escenario. Contraprueba obligatoria: cambiar días/condición en el nuevo fixture cambia evidencia/respuesta o invalida la versión; un canned answer no pasa.

Preguntas iniciales propuestas: cantidad de días, condición de antigüedad y una fuera de contenido. Mapear texto a un conjunto exacto/versionado de preguntas; unknown -> mensaje de insuficiencia/rechazo sin inferencia adicional. No usar otro modelo para clasificar la pregunta. No truncar silenciosamente una condición relevante. Las pruebas inyectan mutaciones/fallos desde composición de test, no ofrecen un menú administrativo capaz de cambiar permisos arbitrarios.

### TASK-C04 — evaluación de proveedor real (no autorizada)

No equivale a «activar OpenAI». Empezar por una revisión separada con PO/seguridad: cuenta/proyecto/recurso y propiedad, proveedor/modelo/versionado/deployment, destinos/rutas/regiones/retención verificables, clasificación, tokenizer/budgets/coste, custodia/separación de credenciales, SDK/egress/TLS/redirects/telemetría, cancelación/worker cleanup, aprobaciones y datos sintéticos. Verificar documentación oficial vigente entonces; este diseño no certifica capacidades comerciales, residencia ni no-retención de ningún proveedor.

Entregable inicial de C04: decisión habilitable/bloqueada y matriz/contrato de adaptador específico. Provisión, adquisición de credenciales, pruebas reales y activación requieren autoridad explícita adicional dentro de ese alcance. Fake/local/OpenAI/Azure OpenAI no intercambiables; ninguna migración automática desde Gemini ni fallback entre proveedores. Las garantías actuales son offline, no defensas operacionales contra SSRF, prompt injection de LLM real o eliminación remota.

## Matriz de DEMO-002 y aceptación requerida

Todo lo siguiente está **PLANNED, no ejecutado**. Modelo/fuente fake con StateGraph y SQLite reales del futuro incremento; contadores/Events y reloj inyectado, sin sleeps, servidores, Docker, Keycloak, HAPI o LLM live. Cada fila tiene contraprueba para evitar validar solo un status prefabricado.

| ID | Escenario / resultado esperado | Evidencia y contraprueba | Amenazas |
|---|---|---|---|
| D02-01 | Pregunta propia -> DELIVERY_ALLOWED, dato/condición correctos | Grafo real, A/B/C, exactamente una llamada fake, fragmento/versionado propios; modificar texto evidencia evita respuesta constante | AI-T01/AI-T04/AI-T06/AI-T16 |
| D02-02 | Documento no autorizado/cross-org -> DENY | Cero broker/transporte/fake para recurso B, sin cita/nombre; mismo ID externo no autoriza | AI-T01/AI-T17 |
| D02-03 | Modelo/destino no autorizado -> DENY antes de inferencia | Lectura A/B puede existir; contador fake cero, ningún fallback ni perfil alterado | AI-T03/AI-T05 |
| D02-04 | Clasificación prohibida -> DENY | Label del texto que diga «público» no cambia registro; cero fake | AI-T02/AI-T04 |
| D02-05 | Revocación durante fake -> DELIVERY_SUPPRESSED | Una llamada ya observada, cero respuesta/citas; petición posterior no invoca, sin afirmar deshacer procesamiento | AI-T07 |
| D02-06 | Documento hostil -> solo dato, ninguna acción adicional | Política/perfil invariantes, una fuente/call, tools/red cero; cita o respuesta hostil no fundamentada se rechaza | AI-T02/AI-T05/AI-T06 |
| D02-07 | Pregunta fuera de fuente -> INSUFFICIENT_EVIDENCE | Sin cifra ni búsqueda de otra fuente; pregunta fuera de allowlist no invoca modelo | AI-T16/AI-T18 |
| D02-08 | Candidato sin evidencia/fuente inventada -> ANSWER_REJECTED | Una llamada fake, cero entrega/citas; IDs/offsets/versiones cruzados no pasan | AI-T06/AI-T17 |
| D02-09 | Modelo indisponible -> UNAVAILABLE | Sin respuesta, sin retry/fallback; audit diferencia intent, entrada y resultado desconocido | AI-T03/AI-T08/AI-T12 |
| D02-10 | Fallo de audit -> UNAVAILABLE/supresión | Antes de intent cero fake; después de invocar no retractar hecho, cero entrega; solo filas confirmadas | AI-T08/AI-T17 |
| D02-11 | Cancelación -> señal preservada, sin entrega | Menú/antes/durante/después de fake y fallo close/clear; owner/lease retirados y datos ausentes de trazas propias | AI-T09/AI-T10 |
| D02-12 | Dos organizaciones concurrentes -> aislamiento | Sources/answers/leases/reservas/correlaciones separadas; cancelar una no modifica la otra, audit org-scoped | AI-T01/AI-T10/AI-T11 |
| D02-13 | Límites, aprobación/retención o replay inválidos -> DENY/UNAVAILABLE | Límite y +1, aprobación ausente/vencida, suma de grants, lease copiada/reusada; cero inferencia no aprobada | AI-T12–AI-T15 |
| D02-14 | Persistencia/tracing/índice solicitados -> rechazados | Config heredada no activa saver/tools; estados/eventos/logs/SQLite sin canarios; D permanece apagado | AI-T09/AI-T13/AI-T18 |
| D02-15 | Caducidad/bytes cambiados/contradicción -> supresión o insuficiencia | Reloj, versión y evidencia frescos, sin renovar permiso ni escoger cláusula conveniente | AI-T04/AI-T07/AI-T16 |

Mostrar al PO: respuesta/cita permitidas, organización sintética, fuente/versión/procedencia, códigos A/B/C/D, contadores y resumen audit del turno propio. Nunca prompt completo, token, key, datos ajenos ni excepción interna. Decisión final no es confirmación de recepción humana. Salir/EOF/Ctrl+C cierra solo recursos temporales propios y sanitiza diagnósticos; proceso muerto puede dejar artefacto test-owned, sin limpieza masiva/ACL. Conservar sondeo IPv6 loopback inocuo documentado por DEMO-001 y distinguirlo de egress.

Gate PO DEMO-002: ejecutar personalmente los casos aprobados y revisar respuestas/fuentes/limitaciones. No contar entrada redirigida como prueba humana. Código de menú no autoriza proveedor real ni siguiente tarea.

## Regresión y mantenibilidad

Selección obligatoria futura proporcional: suite nueva C del incremento, `test_enterprise_connectors.py`, `test_enterprise_connector_control_plane.py`, `test_enterprise_connector_graph.py`, `test_enterprise_connector_workflow.py` y `test_enterprise_connector_demo.py`. Cuando se añada puerto de entrega, repetir especialmente A-only/no B, revocación real de frontera, sink/commit, resultados malformados, cancelación/owners/cause/context/groups y dos organizaciones. No eliminar tests porque el camino nuevo permite C: el camino antiguo debe seguir denegándolo. Añadir AST/imports para aislar módulos clínicos y proveedores reales, pruebas con flags de entorno activos y observación de canales LangGraph reales, no solo output final.

Usar basetemp nuevo/absoluto/test-owned, fuera de `.pytest-tmp`, con socket/DNS guard y canarios sintéticos. No pruebas indiscriminadas que contactan HAPI ni live sin permiso; no modificar pruebas IAM históricas, CRLF, ACL o migraciones para ocultar fallos. Resultados anteriores (incluidos 261 finales y 617 históricos DEMO-001) no son pruebas nuevas de C. Si se selecciona IAM en una autorización futura, conservar explícita la deuda de fechas al importar/orden, no reclamar independencia inexistente.

M01: gestión explícita de refs antes que nueva introspección; mantener todas las regresiones y detener si no se demuestra ownership. M02: un puerto público mínimo justificado por el segundo consumidor, no duplicar el servicio ni eliminar B. P2: funciones pequeñas de validación pura, efectos secuenciados visibles, snapshots medidos sin caché de ALLOW y sin transacciones durante inferencia. P3: presentación clara de códigos y composición de fixtures solo según necesidad; no UI/framework/inyección de dependencias genéricos por anticipación. Ninguna de estas recomendaciones se implementa en DESIGN-001.

## Revisión del diseño y límites vigentes

DESIGN-001 está aprobado exclusivamente como base arquitectónica; C01–C04 no están autorizadas para ejecución. Tras publicar estos cuatro documentos, esperar revisión del PO antes de PR o de cualquier incremento. Antes de C02/C03 revisar los riesgos nuevos de almacenamiento y ownership y aprobar específicamente esquema/protocolo/puerto; si una incompatibilidad exige modificar contrato base, presentar propuesta aditiva y esperar aprobación antes de tocarlo. No se crea un ADR nuevo como si estuviese aceptado ni se cambia ADR-097.

Persisten límites de laboratorio: identidad sintética, sin administración corporativa/custodia/aislamiento de host, revocación local no retroactiva, dos stores sin atomicidad distribuida, no garantías universales de grounding o borrado, Graph live/Selected/compatibilidad HAPI independientes pendientes y deuda de frames/callbacks/SQLite. Gate C continúa DENY, D DISABLED y MCP no implementado. Publicación permitida: revisión final y commit/push de estas cuatro rutas documentales tras controles satisfactorios; después esperar al PO, sin PR/merge ni implementación.
