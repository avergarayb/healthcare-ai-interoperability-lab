# DEMO-001 — Consola empresarial interactiva offline

Demostración **de laboratorio y datos ficticios**, autorizada separadamente de las siete TASK de Enterprise Connector Authorization V1. TASK 005 está integrada mediante PR #113. El Product Owner aprobó funcionalmente DEMO-001 tras su validación manual y autorizó commit/push de sus cinco archivos propios después de los controles finales. No autoriza PR, merge, TASK 006/007 ni Graph live y no constituye una aplicación empresarial productiva.

## Objetivo y requisitos

Permitir al PO explorar autorización, revocación, contenido hostil y auditoría desde PowerShell. El resultado lo produce un LangGraph real; no es una tabla de respuestas prefabricadas. Se muestran solo documentos sintéticos autorizados y metadata de decisión minimizada.

Requisitos: Windows/PowerShell, checkout del repositorio y venv existente `services/ai-service/.venv` con las dependencias ya instaladas del AI Service (incluido LangGraph 1.2.12). El script usa biblioteca estándar y fixtures Python existentes, sin nuevas dependencias. **No necesita sesión de pytest**, servicios Java, HAPI, Docker, Keycloak, Microsoft 365, credenciales ni conexión de red.

## Inicio: un comando desde la raíz del repositorio

```powershell
.\services\ai-service\.venv\Scripts\python.exe -X utf8 .\scripts\enterprise-connector-demo\run_demo.py
```

Comando ejecutado y validado con entradas de consola redirigidas, incluidos los cuatro escenarios, auditoría, repetición y salida. `-X utf8` es una opción del intérprete para conservar acentos en Windows, no un flag de transporte. Separadamente, el PO ejecutó personalmente las cinco opciones en PowerShell y confirmó lectura permitida, cruce organizacional denegado sin broker/transporte, revocación suprimida, contenido hostil etiquetado sin acciones adicionales y auditoría del último escenario. Informó cero intentos de red externa bloqueados, un sondeo IPv6 local sin conexión y cierre normal. Esta aceptación humana no se deduce de las pruebas automatizadas ni acredita Graph live.

El ejecutor no acepta argumentos CLI ni configuración libre de principal, organización, tenant, credenciales, grants, endpoints o URLs. `--live` se rechaza. No hay una variable de entorno que sustituya el transporte offline por HTTP.

## Menú y pasos manuales

```text
1. Consultar documento autorizado.
2. Intentar acceder a un documento de otra organización.
3. Revocar permiso durante una lectura.
4. Consultar documento con instrucciones hostiles.
5. Visualizar resumen de auditoría.
0. Salir.
```

1. Seleccionar **1**. Revisar `DELIVERY_ALLOWED`, ORG-A, nombre descriptivo ficticio, vista de contenido, procedencia, operación, correlación y decisiones local/externa/B.
2. Seleccionar **5**. Revisar los cuatro eventos del último escenario, todos de ORG-A y con la misma correlación.
3. Seleccionar **2**. Comprobar `DENY / organization_mismatch`, explicación sanitizada, cero adquisiciones, cero solicitudes simuladas y cero documentos. No se muestra el contenido de ORG-B.
4. Seleccionar **3**. Comprobar `DELIVERY_SUPPRESSED / policy_revision_changed`, sin documentos. Un hook síncrono del transporte retira el grant tras leer y antes de entregar; un Event confirma ese punto. No hay sleeps, carreras temporales ni restauración automática.
5. Seleccionar **4**. Ver el texto hostil ficticio como **dato**, etiquetado `untrusted_enterprise_document`. La política permanece igual, el solicitante sigue siendo ORG-A y se ejecutan únicamente los cuatro nodos y dos solicitudes simuladas previstas. No se interpretan las instrucciones ni se envían datos a sus destinos.
6. Seleccionar **1** otra vez. La lectura positiva usa otro fixture/grants/decisiones y correlación; no restaura el permiso revocado del escenario anterior.
7. Seleccionar **0** para salir. EOF también cierra normalmente. Ctrl+C interrumpe y devuelve código 130 después del cleanup; un fallo o intento de red devuelve 1. Una opción CLI adicional devuelve 2.

Las opciones inválidas no ejecutan un workflow ni se reflejan literalmente en el diagnóstico. No se solicita entrada libre de identidad o de configuración.

## Resultados observados

| Escenario | Resultado | Intentos broker / adquisiciones | Wire simuladas | Documentos | Eventos de acceso |
|---|---|---|---|---|---|
| 1: documento propio | DELIVERY_ALLOWED | 1 / 1 | 2 | 1 | 4 |
| 2: ORG-A intenta recurso B | DENY | 0 / 0 | 0 | 0 | 1 |
| 3: revocación durante lectura | DELIVERY_SUPPRESSED | 1 / 1 | 2 | 0 | 3 |
| 4: documento hostil propio | DELIVERY_ALLOWED, dato no confiable | 1 / 1 | 2 | 1 | 4 |

Son contadores reales del fixture ejecutado, no resultados constantes del menú. El nombre visible es una etiqueta descriptiva de la demo, no un título Graph obtenido ni un identificador de autoridad. La vista documental se limita a 320 caracteres más indicador de truncado; se neutralizan escapes de terminal y controles no imprimibles. La procedencia muestra adaptador offline, organización, versión y etiqueta, sin tenant, referencia de credencial o contexto IAM.

## Qué hace LangGraph y dónde se autoriza

[Ejecutor](../../scripts/enterprise-connector-demo/run_demo.py), exclusivamente en `scripts/`, compone los [fixtures de test](../../services/ai-service/tests/enterprise_connector_workflow_fixture.py) existentes, no fábricas productivas. LangGraph ordena cuatro pasos: validar petición → resolver recurso registrado → invocar conector autorizado → evaluar resultado. Fuera del grafo, la frontera final vuelve a autorizar/auditar antes de devolver contenido. La consola muestra los nombres de nodos realmente ejecutados; una denegación temprana no ejecuta los cuatro.

Se reutilizan sin modificar `EnterpriseDocumentWorkflow`, `ConnectorService`, `PolicyEvaluator`, `SQLitePolicyStore`, `SQLiteConnectorAudit` y `GraphReadAdapter` offline. Las decisiones no se calculan en la consola. La única fábrica de identidad es `TestInvocationBoundary`; ni un ID conocido ni el texto del documento conceden autoridad. No hay autenticación humana corporativa para esta terminal: el operador local y el host son confiables en el laboratorio.

Gates: **A** lectura sintética; **B** entrega revalidada; **C DENY** para IA; **D DISABLED** para índices/derivados. No hay LLM, embeddings, RAG, MCP, API FastAPI, UI web, herramientas globales, checkpoints empresariales ni recuperación por operation ID. Ver los runbooks [TASK 002](../design/enterprise-connector-synthetic-fixture-v1.md), [TASK 003](../design/enterprise-connector-control-plane-v1.md), [TASK 004](../design/microsoft-graph-app-only-adapter-v1.md) y [TASK 005](../design/langgraph-enterprise-connector-integration-v1.md).

## Auditoría: opción 5

Se consulta el puerto existente `ControlPlane.audit_events(admin_a, "access")`, limitado a ORG-A, y se proyectan únicamente fase, decisión, razón cerrada, correlación y organización. No existe selector organizacional ni consulta SQL libre. La administración también es sintética, no una identidad corporativa.

La opción 5 conserva **solo la proyección minimizada del último escenario en memoria**. No conserva documentos, contextos, permisos, handles ni una base abierta. Los eventos fueron persistidos y leídos de SQLite durante el escenario; su archivo temporal ya se eliminó al terminarlo. No es auditoría durable entre sesiones ni una API de consulta por ID.

Los dos eventos B positivos son decisiones de las fronteras servicio/workflow; **no confirman recepción humana**. Revocación conserva autorización y resultado externo anteriores, más la supresión. No se inventan eventos ni se apaga el sink para facilitar la demo.

## Aislamiento, temporales y salida

Cada sesión crea únicamente un directorio nuevo `infra/iam-lab/.runtime/eca-demo-001-<aleatorio>/`. Cada opción 1–4 crea dentro otro `scenario-<aleatorio>/` con su propia `connectors.sqlite3`. No se adopta ni sobrescribe una base existente. No se modifican archivos hermanos del runtime ni recursos Docker/servicios.

Las conexiones/guards SQLite existentes cierran y hacen rollback en finally cuando corresponde. El directorio de cada escenario se elimina antes de mostrar el resultado; salir elimina el de sesión mediante TemporaryDirectory sobre la ruta recién creada. Las pruebas comprueban que los directorios desaparecen en Windows y que un archivo ajeno permanece intacto. El consumidor puede mostrar el preview autorizado; no se promete borrado criptográfico de memoria Python.

Si se mata el proceso o falla el filesystem, puede quedar un directorio propio. La consola informa fallo sin imprimir excepción, contenido o traceback; no ejecuta limpieza masiva ni altera ACL. Para inspeccionar posibles restos, sin eliminarlos:

```powershell
Get-ChildItem -LiteralPath .\infra\iam-lab\.runtime -Directory -Filter 'eca-demo-001-*'
```

No eliminar carpetas activas, preexistentes o de otras demos. Cualquier limpieza manual posterior debe identificar la carpeta exacta de la ejecución ya detenida. Los basetemp de pytest `demo001-tests-*`/`demo001-regressions-*`/`demo001-closure-tests-*`/`demo001-final-tests-*` son artefactos de pruebas propios, ignorados y separados; no son sesiones de la consola ni se borran automáticamente como tales. La revisión final comprobó cero directorios de sesión `eca-demo-001-*` después de las pruebas; el basetemp final se conserva ignorado, fuera del commit.

## Seguridad offline y problemas conocidos

Un guard local al proceso bloquea connect/connect_ex, envío TCP/UDP, escucha, DNS y helpers de conexión. Está activo antes de importar/componer los fixtures. Un intento capturado por una capa inferior también invalida la ejecución antes de mostrar el resultado; no hay fallback. Se restaura el monkeypatch al salir del proceso/control de pruebas, sin cambiar servicios.

La primera ejecución en frío falló porque el guard rechazaba también el sondeo de capacidad IPv6 de urllib3 durante su importación. La única excepción actual permite `bind(('::1', 0))` sobre AF_INET6: loopback efímero, **sin listen, connect, envío ni DNS**. Se cuenta aparte como sondeo local, no conexión externa. Una prueba verifica que listen sigue bloqueado después de ese bind. No se permite loopback de servicios como HAPI ni puertos prefijados. No es un firewall/sandbox del sistema ni impide primitivas nativas de código malicioso en un host comprometido.

Los errores se presentan mediante mensajes fijos, nunca repr, payloads o tracebacks. La excepción de texto visible está acotada a contenido ficticio autorizado solicitado por el PO. Los flags de tracing heredados se aíslan por TASK 005; hay cobertura en proceso nuevo con flags true y transporte solicitado como live, sin activarlo. No se instala software ni se consulta infraestructura externa.

Permanecen las deudas documentadas OIDC/orden, CRLF, symlink/ACL, SQLite de laboratorio y Graph/Selected no validado live. Esta demo no las corrige ni modifica los contratos, ADR-097, IAM o protocolos clínicos.

## Pruebas y revisión

[Suite DEMO-001](../../services/ai-service/tests/test_enterprise_connector_demo.py): menú, negativos, repeticiones, cuatro escenarios reales, auditoría org-scoped, Ctrl+C inyectado en menú/lectura/entrega, EOF, cleanup y errores, guard/HTTP/DNS, preview, imports y subprocess con el comando raíz. No requiere interacción con pytest. La prueba del grafo observa `CompiledStateGraph.invoke`, los nodos, Runtime y la ausencia de checkpoint/store.

Ejecución inicial: 35 PASS y un fallo al comprobar el proceso nuevo, debido al sondeo IPv6 citado; no fue acceso externo. Tras acotar ese sondeo, la suite inicial aprobó 38/38. Después se añadieron cinco negativas adicionales. **Evidencia conjunta histórica: 617 PASS, 1 SKIPPED, en 530,27 s**, sin warnings nuevos: 43 DEMO-001, 196 TASK 005, 158 TASK 004, 75 TASK 003 y 145 TASK 002. La omisión es el symlink físico Windows heredado; no se añadieron skips ni se alteraron ACL. La revisión read-only posterior repitió únicamente DEMO-001: 43/43 en 31,53 s, con cero intentos fuera de sus guards; no fue una repetición de las 617.

**Revisión final autorizada: 261 PASS, sin omisiones ni warnings, en 251,76 s**: las 43 DEMO-001, las 196 TASK 005 y 22 casos focalizados de TASK 003/004. Estos últimos verifican operaciones propias Graph, auditoría durable obligatoria, revocación antes de descargar, documento hostil, ausencia de contenido/URL en SQLite, persistencia tras reapertura, gates C/D deshabilitados y fallo de commit final con rollback/supresión. Se usó `-q -x -p no:cacheprovider --basetemp <directorio nuevo absoluto>` bajo `infra/iam-lab/.runtime/demo001-final-tests-<aleatorio>`, sin alterar `.pytest-tmp` ni ACL. Guard adicional de socket/DNS: cero intentos fuera de los guards internos. Esta selección no repitió las suites completas TASK 002–004, IAM/clínica o infraestructura live; sus 617 anteriores permanecen evidencia histórica.

Selección histórica real pasada a `pytest.main` desde el venv, con `-q -x -p no:cacheprovider --basetemp <directorio nuevo absoluto>`: `test_enterprise_connector_demo.py`, `test_enterprise_connector_workflow.py`, `test_enterprise_connector_graph.py`, `test_enterprise_connector_control_plane.py`, `test_enterprise_connectors.py`. Se ejecutó con un guard externo adicional de socket/DNS: **cero intentos fuera de los guards de la demo, cero socketpairs**. Las negativas nuevas provocan intentos deliberados que el guard interno rechaza antes de tráfico; no se describen como conexiones exitosas ni se suman como ausencia de intentos. Las ejecuciones positivas de consola registraron cero intentos, con un sondeo IPv6 local sin conexión en el proceso nuevo.

También aprobaron AST/imports, compileall, validación de enlaces/whitespace y escaneo de patrones de secretos. Las pruebas de Ctrl+C son inyecciones deterministas de KeyboardInterrupt en menú/lectura/entrega, no una afirmación de prueba humana del teclado. La salida normal, EOF, fallo de backend, cleanup y argumentos CLI tienen cobertura. La aceptación manual del PO corresponde a las cinco opciones y salida informadas arriba, no a inyección humana de todos los fallos.

No es necesario repetir indiscriminadamente IAM/clínica/Java: no se modifican componentes productivos ni configuración. La selección histórica incluyó íntegramente las cuatro suites empresariales reutilizadas; la revisión final usa la selección focalizada indicada en su evidencia. No se ejecutan HAPI, Docker, Keycloak o LLM live ni las pruebas históricas CRLF.

Evaluación read-only separada y revisada por el PO: [informe de mantenibilidad](../design/enterprise-connector-maintainability-demo-001.md). La autorización final permite staging explícito, commit y push exclusivamente del ejecutor, su suite, este runbook, el informe y el handoff tras controles satisfactorios. Siguiente paso después de publicar la rama: revisión del PO; no crear PR, merge ni implementar las recomendaciones sin nueva autorización.
