# TASK-C03 Phase B2-RUNTIME — frontera ejecutable de evidencia

Estado: la alternativa A está implementada en `services/ai-service/app/enterprise_ai_processing/source_boundary.py`. No hay commit ni publicación. El emisor de B2-SRC sigue en `tests/`. `gateway.py` no cambió. El detalle de la ejecución está en el [runbook](enterprise-grounded-answer-task-c03-b2-runtime.md).

Documentos de partida: [propuesta B2-SRC](enterprise-grounded-answer-task-c03-b2-source-evidence-proposal.md), [runbook B2-SRC](enterprise-grounded-answer-task-c03-b2-src.md), [propuesta C03](enterprise-grounded-answer-task-c03-proposal.md), [runbook B1](enterprise-grounded-answer-task-c03-b1.md), [runbook C02](enterprise-ai-processing-gateway-audit-task-c02.md), [amenazas](enterprise-ai-processing-threat-model-v1.md), [ADR-097](../adr/ADR-097-enterprise-connector-authorization-boundaries.md) y [M01/M02](enterprise-connector-maintainability-demo-001.md).

## 1. Estado

El laboratorio ya tiene una lectura reconocida y una admisión C02 de esa misma lectura, ambas dentro de `tests/enterprise_single_read_source.py`. La vía que consume el recibo es `prepare_once`. El caller de ese módulo puede no usarla.

Esta fase define la frontera de producto que haría esa cadena inevitable para quien use la API pública. No la implementa. El observador, el grounding, el LangGraph nuevo y la entrega siguen fuera.

## 2. Merge B2-SRC verificado

`git fetch origin` dejó `origin/main` en `56862e9d7f5ccd91c5b3a0e89cb220470959102d`. El mensaje es `Merge pull request #120 from avergarayb/feature/enterprise-ai-processing-authorization-task-c03-b2`. Los padres son `c6dd2124713a4aad193dc9ddf7d66129c16d38d7` y el commit funcional `0e8cbdf2e64b251b3c36b897636690fe3086eff4` (`test(ai): add trusted single-read source evidence for C03 B2`).

Ese commit funcional es ancestro de `origin/main`. B1 sigue en el historial: PR #119, merge `c6dd2124713a4aad193dc9ddf7d66129c16d38d7`, commit funcional `393a42230551f7047fad205f3ee12e43ee9acab1`.

`main` local sigue en `138b748747f0e3d57f7da89c1fbc7c2b62cf5f8d` y no se actualizó. La rama de este diseño es `feature/enterprise-ai-processing-authorization-task-c03-b2-runtime`, creada desde `origin/main`. El upstream hacia `origin/main` se retiró al crearla.

## 3. Arquitectura actual

La cadena real, leída en el código de este HEAD, es esta.

`ConnectorService.execute` recibe un `ConnectorExecutionContext` que `IdentityBoundary.recognizes` acepta y un `OperationRequest`. Devuelve un `OperationResult`. La correlación nace dentro de la llamada. El documento es un `UntrustedDocument` con `text: str` y `version: int`. No trae bytes ni eTag.

`GateCPolicyEvaluator.evaluate` exige un `AIProcessingEnvelope` y un `SourceEvidence` que la frontera reconozca. `ALLOW_PROCESSING` no ejecuta.

`EnterpriseModelGateway.prepare` crea un `ExecutionOwner`, evalúa, llama `boundary.populate` dentro de `_assemble`, evalúa otra vez, arma metadatos y solo entonces `ledger.reserve`. Si todo eso termina, guarda la `ProcessingLease` y la devuelve. Si falla, limpia el owner y llama `ledger.deny`. `deny` escribe auditoría. No libera una reserva ya confirmada. `reconcile` es el camino administrativo existente para una fila `INTENT` que quedó abierta: la pasa a `UNKNOWN`.

`_seal` vuelve a evaluar y a llamar `populate`. Compara los bytes con `original_source`. `invoke_once` llama `_seal` antes de `consume`, otra vez después, y el adaptador vuelve a sellar al entrar. El fake solo corre dentro de `invoke_once`. B2-SRC no lo llama.

`DerivedGrantMatch` sale de `assess_derived_delivery`. No autoriza A, B, C ni la entrega.

El inventario AST cerrado de `enterprise_ai_processing` admite exactamente `__init__.py`, `models.py`, `policy.py`, `execution_types.py`, `gateway.py`, `fake_model.py` y `sqlite_ledger.py`. Un archivo nuevo bajo `app/` falla esa prueba hasta que la misma tarea futura lo incorpore a la lista y fije sus imports.

`ProcessingLaboratory.__init__` sigue llamando `issue()`, y esa llamada ejecuta `execute`. La frontera de producto no puede apoyarse en ese constructor.

## 4. Problema de promoción a producto

`prepare_once` marca el recibo antes de `gateway.prepare` y lo consume en `finally`. Eso cubre el fallo anterior a `populate` solo para quien llama ese método.

`populate` rechaza un owner nuevo cuando el recibo ya está consumido y la preparación no está abierta. Por eso un segundo `prepare` que llega a `populate` no reserva otra lease. Un `gateway.prepare` directo que falla en `_evaluate`, antes de `populate`, no pasa por ese `finally`. El recibo puede seguir utilizable.

El caller tampoco debería poder entregar un `OperationResult`, un `SourceEvidence` o un recibo fabricados. Hoy el emisor vive en `tests/` y `app/` no puede importarlo.

La frontera de producto tiene que imponer, para su API pública, esta cadena y ninguna otra:

una lectura autorizada, un resultado reconocido, una evidencia reconocida y como máximo una admisión C.

El caller no elige el método que consume el recibo, porque no recibe el recibo.

## 5. Alternativas comparadas

### A. Fachada dueña de la operación

Nombre de trabajo: `TrustedEnterpriseSourceBoundary`. Una sola operación pública lee, emite la evidencia y llama `gateway.prepare`. El recibo, el sobre y la evidencia no salen de la fachada.

Para cerrar el bypass, `recognizes_source` es verdadero solo mientras la fachada tiene reclamada esa preparación, o después, solo para la operación ya admitida. Un `gateway.prepare` directo, sin esa reclamación, falla en la primera evaluación y no reserva. El `finally` de la fachada consume el recibo en todo camino que ella abrió, incluido el fallo anterior a `populate`.

`gateway.py` no cambia. C01 sigue siendo `GateCPolicyEvaluator`. C02 sigue reservando y sellando. B1 no interviene. La concurrencia es el mismo candado corto de B2-SRC, soltado antes de SQLite. El owner de los bytes es la fachada. El owner de la lease es el gateway. El riesgo de bypass que queda es código del mismo proceso que manipula atributos privados: el modelo de amenazas ya trata ese host como confiable, y un objeto reconocido no es una autoridad criptográfica.

La API pública es pequeña. Las pruebas tienen que demostrar que la llamada directa no reserva y que el fallo de la vía pública sí consume.

### B. Gancho mínimo en el gateway

`prepare` avisaría a la frontera al terminar, también si falla antes de `populate`. El gancho tendría un nombre fijo y un significado fijo: esta admisión terminó. No sería un callback arbitrario.

Cierra el hueco aunque `recognizes_source` siga siendo verdadero durante toda la vida de la evidencia, que es el comportamiento del emisor de prueba actual. Obliga a editar `gateway.py` y a no romper `SyntheticProcessingBoundary` ni `ExecutionFixture`: el gancho tendría que ser opcional. Cada frontera futura quedaría acoplada a ese aviso. El gateway ya confía en la frontera para `populate`; el gancho no añade una confianza nueva, pero sí un cambio de producto y una superficie que hay que mantener en todos los caminos de `prepare`.

### C. Capacidad de admisión entregada al caller

El caller recibiría un objeto de un solo uso, lo consumiría y después llamaría al gateway. Si olvida el objeto y llama `gateway.prepare` con la evidencia, reaparece el hueco de B2-SRC. Si la evidencia solo se reconoce después de consumir la capacidad, el caller sigue siendo quien debe hacer las dos cosas en orden. Esa dependencia es el problema que esta fase tiene que eliminar. La variante segura de C es no entregar la capacidad y esconderla dentro de la fachada. Eso es la alternativa A.

| Criterio | A. Fachada | B. Gancho | C. Capacidad suelta |
| --- | --- | --- | --- |
| API pública | Una operación. Sin recibo retornable | `prepare` gana un aviso fijo | El caller coordina dos pasos |
| C01 | El mismo evaluador | El mismo evaluador | El mismo evaluador |
| C02 | `prepare`, `reserve`, `_seal` intactos | Cambia `prepare` | Depende de que el caller entre al gateway |
| B1 | Sin cambio | Sin cambio | Sin cambio |
| Concurrencia | Candado solo en la reclamación | Igual, más el aviso | Carrera si hay dos capacidades |
| Owner | Fachada posee bytes y recibo; gateway posee la lease | Igual, con aviso | El caller puede retener la capacidad |
| Bypass | La llamada directa no pasa la evaluación | La llamada directa también consume | La llamada directa puede saltarse la capacidad |
| Mantenimiento | Un módulo nuevo y el inventario AST | `gateway.py` y todas las fronteras | Fácil de usar mal |
| Pruebas | Vía pública, bypass, fallo antes de `populate` | Además, fronteras viejas sin el gancho | Además, caller que omite el paso |

## 6. Decisión recomendada

Se recomienda la alternativa A.

La alternativa C deja el orden en manos del caller. La alternativa B modifica `gateway.py` para cubrir un caso que la fachada puede impedir antes: si la evidencia no se reconoce fuera de la reclamación, `prepare` directo falla en `_evaluate` y no llega a `populate`. El hueco de B2-SRC existe porque el emisor de prueba reconoce la evidencia durante toda su vida y solo consume si alguien llama `prepare_once`. La frontera de producto cambia esa regla de reconocimiento. Con eso, el cambio de `gateway.py` no es necesario.

No se elige A por tocar menos archivos. Se elige porque el bypass público queda fuera de la API. El código hostil del mismo proceso que lea atributos privados queda fuera de la garantía, alineado con AI-T01. Si el Product Owner exige que `gateway.prepare` consuma el recibo aunque la frontera lo reconozca todo el tiempo, la decisión pasa a B y habría que autorizar el gancho por separado. Esta propuesta no lo implementa.

## 7. Contrato runtime

Nombre candidato: `TrustedEnterpriseSourceBoundary`.

Lo construye la composición de laboratorio en el mismo proceso. Recibe dependencias ya confiables: el `ConnectorService` con `cache_size == 0` y adaptador offline, la identidad que reconoce el contexto, el `PolicyEvaluator`, el reloj, el ledger C02 y el acceso ejecutor de esa organización, y un `EnterpriseModelGateway` ya construido con esta frontera como `boundary`. No se construye desde JSON, desde una petición HTTP ni desde un módulo de `tests/`.

La operación pública recibe el contexto reconocido y el `OperationRequest` que va a ejecutarse. No recibe `OperationResult`, `SourceEvidence`, recibo, bytes, sobre, `content_revision`, correlación ni lease.

La frontera emite el `SourceEvidence` y el sobre. Conserva los bytes canónicos. Administra el recibo y no lo devuelve. Ella llama `gateway.prepare`. El gateway crea y posee la `ProcessingLease` y el `ExecutionOwner`. La operación se cierra con `close` de la frontera, después de que el gateway ya no necesite revalidar. Un uso posterior ve el estado `CLOSED` y falla cerrado.

Reconocer un objeto no concede permiso para otra operación. La identidad de objeto ata la evidencia a la llamada. El permiso de preparar existe solo en la transición que la fachada reclama. Nada de eso cifra ni protege contra código que ya ejecuta dentro del proceso.

## 8. Máquina de estados

Estados: `NEW`, `READING`, `SOURCE_RECOGNIZED`, `PREPARE_CLAIMED`, `PREPARED`, `DENIED`, `UNCERTAIN`, `CLOSED`.

Transiciones permitidas:

- `NEW` a `READING` al empezar la única lectura.
- `READING` a `SOURCE_RECOGNIZED` si el resultado cumple el contrato de B2-SRC.
- `READING` a `DENIED` si la lectura no es admisible.
- `READING` a `CLOSED` si llega `CancelledError` o `KeyboardInterrupt` antes del registro.
- `SOURCE_RECOGNIZED` a `PREPARE_CLAIMED` por el CAS de la fachada.
- `PREPARE_CLAIMED` a `PREPARED` si `prepare` devuelve la lease.
- `PREPARE_CLAIMED` a `DENIED` si `prepare` rechaza con un error cerrado y no hay señal de reserva ambigua.
- `PREPARE_CLAIMED` a `UNCERTAIN` si el error es de disponibilidad, de auditoría o no permite saber si `reserve` confirmó.
- `PREPARED`, `DENIED` y `UNCERTAIN` a `CLOSED` por `close`.

Transiciones prohibidas: volver a `SOURCE_RECOGNIZED`, repetir `PREPARE_CLAIMED`, pasar de `DENIED` o `UNCERTAIN` a `PREPARED`, y salir de `CLOSED`.

## 9. Ciclo de vida del receipt

El recibo externo nace en `SOURCE_RECOGNIZED` y muere al entrar en `PREPARE_CLAIMED`. No vuelve a un estado utilizable.

`prepare` que devuelve `DENY` deja `DENIED`. Un fallo antes de `populate`, si lo provocó la fachada, también deja `DENIED` o `UNCERTAIN`, nunca `SOURCE_RECOGNIZED`. Un fallo después de `reserve` que no entrega la lease deja `UNCERTAIN`: `deny` no cancela la fila `HELD`, y esta frontera no llama `reconcile` ni reintenta. La cancelación durante `PREPARE_CLAIMED` propaga la señal y cierra en `UNCERTAIN`. Otro hilo encuentra el estado ya reclamado y no prepara. Otro proceso con el mismo archivo SQLite queda en la limitación ya aceptada de C02: no hay transacción distribuida.

`close` en `NEW` o `READING` no registra evidencia. En `SOURCE_RECOGNIZED` retira el recibo sin preparar. En `PREPARED`, cuando esta fachada no ejecutó el modelo, `close` llama el `close` público de su gateway exclusivo y deja la fila en `CANCELLED` y `RELEASED`. En `DENIED` retira referencias sin reserva. En `UNCERTAIN` deja la fila `HELD` y no llama `reconcile`. Un segundo `close` no repite la cancelación.

## 10. Vinculación C01

La evidencia la construye la frontera con el resultado de esa llamada y la evaluación pública del snapshot. `content_revision` es `document.version`. La procedencia sigue siendo `synthetic-documents-v1`. `GateCPolicyEvaluator` no se duplica ni se modifica.

`recognizes_envelope` y `recognizes_source` son verdaderos para esos objetos mientras el estado es `SOURCE_RECOGNIZED` solo para la evaluación previa que la propia fachada dispara, durante `PREPARE_CLAIMED`, y durante `PREPARED` para las revalidaciones de la misma operación. Una evidencia copiada, de otra organización o de otra lectura da falso.

## 11. Vinculación C02

La fachada llama `EnterpriseModelGateway.prepare`. No construye una `ProcessingLease`. No llama `reserve`, `consume` ni `finish` por su cuenta. `ALLOW_PROCESSING` sigue sin ejecutar. Los diez eventos de auditoría C02 no cambian.

La evidencia tiene que seguir siendo reconocible en cada `_seal`: el de `invoke_once` antes y después de `consume`, y el de la entrada al adaptador. Esa es la última comprobación que necesita el reconocimiento. `invoke_once` limpia el `ExecutionOwner` antes de retornar. La frontera suelta sus referencias en el `close` posterior a ese punto. El primer incremento de implementación puede detenerse al devolver la lease, sin llamar `invoke_once`, y mantener el estado `PREPARED` hasta el `close` de la prueba. No ejecuta el fake.

## 12. Relación con B1

`DerivedGrantMatch` acredita solo el permiso derivado. Esta frontera no lo consulta para leer ni para preparar, y no inserta `AUTHORIZED`.

Quedan separadas, y en este orden futuro: lectura autorizada, procedencia reconocida, procesamiento autorizado por C, resultado técnico de C02, evidencia de grounding, permiso de entrega derivada y entrega observada. Esta fase cubre el diseño de las tres primeras hasta la admisión. El grounding, el permiso de entrega y la entrega observada se conectan después, cada uno con su autorización, usando los bytes y el contexto de esta misma lectura. No reutilizan el recibo externo ni abren otra lectura.

## 13. Ownership y cleanup

La fachada posee el resultado, el documento, los bytes, el recibo, el sobre y la evidencia. El gateway posee el `ExecutionOwner` y la lease. Ninguno entra en el estado de LangGraph, en checkpoints, tracing, callbacks, logs, `repr` ni SQLite.

`close` anula esas referencias en `finally`. No usa `frame.clear` ni `f_locals`. No promete borrado criptográfico. Una excepción del cleanup no conserva el registro y no toca otra operación. M01 y M02 siguen abiertos en el workflow antiguo. Esta frontera no los usa y no añade otro consumidor de `_validate_delivery` ni de `_event`.

## 14. Concurrencia y locks

Un candado por frontera cubre solo el paso `SOURCE_RECOGNIZED` a `PREPARE_CLAIMED`. Se suelta antes de `gateway.prepare`. No se mantiene durante SQLite ni durante una inferencia futura.

Dos hilos sobre la misma operación obtienen como máximo una lease. El segundo ve `PREPARE_CLAIMED`, `PREPARED`, `DENIED` o `UNCERTAIN` y falla cerrado. Operaciones de organizaciones distintas no comparten el registro ni los bytes.

## 15. Revocaciones

Si la revisión del store cambia durante `execute`, no hay evidencia. Si cambia entre `SOURCE_RECOGNIZED` y la reclamación, la transición a `PREPARE_CLAIMED` se niega y el recibo queda `DENIED`. Si cambia durante `PREPARED`, `_seal` responde `policy_changed` por el contrato actual de C01 y C02. La frontera no renueva la operación ni hereda la correlación en una lectura nueva.

La expiración del sobre, del contexto o de la decisión C se manifiesta como `authorization_expired` en la evaluación o en `_seal`. No alarga la lease.

## 16. Fallos y estados inciertos

| Situación | Estado |
| --- | --- |
| Lectura denegada, vacía, parcial o con auditoría caída | `DENIED`, sin evidencia |
| Cancelación durante la lectura | `CLOSED`, señal propagada, sin evidencia |
| `prepare` rechaza con razón cerrada y devuelve error | `DENIED` |
| `prepare` falla antes de `populate` por la vía de la fachada | `DENIED` o `UNCERTAIN`, nunca reutilizable |
| `prepare` falla después de que `reserve` pudo confirmar y no hay lease | `UNCERTAIN`. Sin reintento automático |
| `deny` no puede escribir | `UNCERTAIN` |
| Otro proceso dejó una fila `HELD` | Sigue siendo trabajo de `reconcile`, no de esta frontera |

## 17. Privacidad

Los bytes canónicos son una sola codificación UTF-8 estricta del texto de esa lectura. No se normaliza Unicode. 1024 bytes puede ser elegible para C. 1025 se conserva en la evidencia de lectura y C lo rechaza por presupuesto. No se trunca. Un cambio local de esos bytes, con la misma `document.version`, falla el reconocimiento. Una modificación remota no observada que conserve la versión no se detecta: `document.version` no es un eTag.

El texto no entra en logs, traceback, `repr` ni SQLite. La limpieza borra las referencias de la frontera. No hay borrado criptográfico.

## 18. Amenazas

| Amenaza | Control | Vínculo |
| --- | --- | --- |
| Recibo o evidencia fabricados, o recibo deserializado | No son parámetros. `pickle` del recibo de prueba ya falla. La frontera de producto no ofrece reconstrucción | AI-T01, AI-T04 |
| `gateway.prepare` directo | Sin reclamación, `recognizes_source` es falso y no hay `reserve` | AI-T01, AI-T07 |
| Fallo antes de `populate` en la vía pública | El `finally` de la fachada no devuelve el recibo a `SOURCE_RECOGNIZED` | AI-T07, AI-T08 |
| Reutilización después de `DENY` o segunda lease | Estados terminales y un solo `PREPARE_CLAIMED` | AI-T07, AI-T11 |
| Dos hilos | Candado de reclamación. Como máximo una lease | AI-T11 |
| Otra organización | Contexto, petición y evidencia de la misma llamada | AI-T01, AI-T11, AI-T17 |
| Uso después de `close` | Estado `CLOSED` y referencias anuladas | AI-T10 |
| Revocación entre lectura y `prepare`, o durante `_seal` | Revisión y reloj reales. Sin renovar | AI-T07 |
| SQLite caído o commit incierto | `UNCERTAIN`. Sin reintento. `reconcile` sigue siendo el de C02 | AI-T08 |
| Texto en traceback, log o SQLite | `repr` apagado y metadatos sin contenido | AI-T09, AI-T10 |
| Callback arbitrario | No se añade un gancho libre en el gateway | AI-T05 |
| Owner compartido | Un registro por operación | AI-T10, AI-T11 |
| Confundir objeto reconocido con autoridad | La reclamación es un permiso distinto de la identidad del objeto | AI-T01, AI-T14 |
| Más de una ejecución | Esta fase no llama `invoke_once`. La lease C02 sigue siendo de un uso | AI-T12 |
| Bytes cambiados con versión estable | Se comparan los bytes canónicos, no solo `document.version` | AI-T04 |
| Instrucciones dentro del documento | El texto no es política ni recibo | AI-T02 |
| Entrega o grounding implícitos | No hay `AUTHORIZED`, ni validador, ni grafo | AI-T06, AI-T16, AI-T18 |

## 19. Matriz B2-RT

No se ejecuta en esta fase. Cada caso futuro necesita su negativa.

| Id | Caso | Resultado esperado |
| --- | --- | --- |
| B2-RT-01 | Construcción con dependencias confiables | Frontera en `NEW` |
| B2-RT-02 | Dependencia no reconocida | Rechazo. Sin lectura |
| B2-RT-03 | Una operación positiva | Una llamada pública a `execute` |
| B2-RT-04 | Sin la lectura de `ProcessingLaboratory.__init__` | El contador de la operación no incluye esa lectura |
| B2-RT-05 | Evidencia | Una `SourceEvidence` de ese resultado, reconocida por C01 |
| B2-RT-06 | Admisión | Como máximo una lease |
| B2-RT-07 | `prepare` exitoso | `PREPARED` y una fila `HELD` |
| B2-RT-08 | `prepare` en `DENY` | `DENIED`. Sin segunda admisión |
| B2-RT-09 | Fallo antes de `populate` por la vía pública | Recibo no reutilizable. Sin lease |
| B2-RT-10 | Fallo después de reservar, sin lease devuelta | `UNCERTAIN`. Sin reintento |
| B2-RT-11 | Commit ambiguo | `UNCERTAIN`. No se llama `reconcile` desde la frontera |
| B2-RT-12 | Dos hilos | Una lease. Cero llamadas al fake |
| B2-RT-13 | Segunda llamada secuencial | Rechazo |
| B2-RT-14 | `gateway.prepare` directo con la evidencia real | Sin `reserve` |
| B2-RT-15 | Otra organización | No reconocida y sin ids ajenos |
| B2-RT-16 | Revisión cambiada | Sin evidencia, o C en `policy_changed` |
| B2-RT-17 | Expiración | `authorization_expired` |
| B2-RT-18 | Bytes locales sustituidos, versión igual | No reconocida |
| B2-RT-19 | UTF-8 multibyte | La longitud cuenta bytes |
| B2-RT-20 | 1024 bytes | Puede ser elegible |
| B2-RT-21 | 1025 bytes | Sin truncar. C rechaza por presupuesto |
| B2-RT-22 | `CancelledError` | Señal conservada. Sin evidencia reutilizable |
| B2-RT-23 | `KeyboardInterrupt` | Igual que la cancelación |
| B2-RT-24 | Excepción durante `close` | Registro retirado. Otra operación intacta |
| B2-RT-25 | Logs, traceback y SQLite | Sin texto ni bytes |
| B2-RT-26 | Regresión C01 | El evaluador no cambia |
| B2-RT-27 | Regresión C02 | `prepare` e `invoke_once` no cambian de contrato |
| B2-RT-28 | Regresión B1 | `DerivedGrantMatch` no autoriza esta lectura |
| B2-RT-29 | Regresión B2-SRC | El emisor de `tests/` sigue pasando |
| B2-RT-30 | Regresiones empresariales | Conector, plano de control, Graph offline, workflow y DEMO-001 |
| B2-RT-31 | Red | Cero intentos de socket o DNS |

## 20. Cambios mínimos de código futuros

Solo después de otra autorización.

- Nuevo módulo `services/ai-service/app/enterprise_ai_processing/source_boundary.py`. No es un traslado del archivo de `tests/`. El emisor de prueba permanece para B2-SRC.
- El inventario AST incorpora ese archivo y una lista de imports mínima: biblioteca estándar necesaria, modelos C01, tipos C02, el gateway y los modelos del conector. Siguen prohibidos red, Graph live, un LLM real y paquetes clínicos.
- `compose` construye el gateway y lo ata a esta instancia. El caller no lo inyecta. La fachada no importa el fake por su cuenta y no ejecuta el modelo en este incremento.
- No se editan `gateway.py`, `policy.py`, `service.py`, el workflow, el ledger ni las migraciones.
- Los fixtures de C01 y C02 pueden seguir usando `SyntheticProcessingBoundary`. La frontera nueva no los sustituye de golpe.

## 21. Plan incremental

1. Este diseño. Sin código.
2. Si el Product Owner lo acepta, implementar solo la fachada, su estado y las pruebas B2-RT. Sin observador y sin `invoke_once`.
3. Después, y con autorización aparte, el observador efímero sobre la ejecución C02.
4. Después, el grounding determinista sobre los bytes de esta lectura.
5. Después, un LangGraph que solo transporte metadatos.
6. Después, la revalidación final y la entrega, que no reutilizan el recibo externo.
7. Al cierre de cada tramo, las regresiones que ese tramo exija.

El paso 3 no empieza hasta que el paso 2 demuestre una lectura, una evidencia y como máximo una admisión, también cuando alguien llama `gateway.prepare` por fuera.

## 22. Riesgos residuales

- El host que ya ejecuta en el proceso puede leer atributos privados. La fachada no lo impide.
- `document.version` no prueba inmutabilidad remota.
- `UNCERTAIN` puede dejar una fila `HELD`. La frontera no la concilia sola.
- Dos procesos sobre el mismo SQLite siguen sin una transacción común.
- M01 y M02 siguen abiertos.
- No hay borrado criptográfico.
- El fake, cuando un tramo posterior lo invoque, no prueba un LLM real.

## 23. Decisiones solicitadas al Product Owner

1. Aceptar la alternativa A y dejar `gateway.py` sin cambios en el incremento de implementación.
2. Aceptar que un `gateway.prepare` directo, sin la reclamación de la fachada, falla en la evaluación y no consume un recibo que la API pública nunca entregó.
3. Rechazar, para ese incremento, el gancho de la alternativa B. Reservarlo solo si más adelante se exige consumo dentro del propio `prepare` aunque la evidencia siga reconocida todo el tiempo.
4. Aceptar los estados `DENIED` y `UNCERTAIN` como terminales, sin reintento automático y sin llamada nueva a `reconcile` desde la frontera.
5. Autorizar expresamente la implementación de la fachada en `source_boundary.py` y la ampliación mínima del inventario AST antes de escribir ese código. Esta propuesta no la inicia.

## 24. Implementación de la alternativa A

El Product Owner autorizó el paso 2. Quedó así:

- `TrustedEnterpriseSourceBoundary.compose(service, *, ledger, executor)` crea el `EnterpriseModelGateway` con esta frontera como `boundary`. Rechaza caché distinta de cero, un adaptador que no sea el sintético de laboratorio, un ledger que no sea `SQLiteExecutionLedger` y un ejecutor no reconocido. No hay parámetro de gateway.
- `read(context, request)` hace una llamada pública a `ConnectorService.execute` y guarda el resultado, los bytes y la `SourceEvidence`. No devuelve nada de eso.
- `admit()` es la única transición `SOURCE_RECOGNIZED` a `PREPARE_CLAIMED`. Llama `gateway.prepare` y devuelve `RuntimeAdmission` con estado, organización, `operation_id`, `lease_id` y `HELD`. La `ProcessingLease` permanece en la fachada.
- `authority` ata un `ExecutionOwner` solo si el hilo es el de `admit` y el token de esa reclamación sigue activo. Llegar antes a `authority` no basta. Copiar el token a otro hilo tampoco. Después de `PREPARED`, `_seal` reconoce ese mismo owner. Un owner nuevo no abre otra operación.
- `close` de una admisión `PREPARED` no ejecutada llama `gateway.close`. La fila queda `CANCELLED` y `RELEASED`, con auditoría `ai_processing_cancelled`. No declara `COMPLETED` y no llama `reconcile`. `UNCERTAIN` conserva la fila `HELD`. Si `gateway.close` falla, la fachada sigue en `PREPARED` y la fila sigue `HELD`.
- La evidencia sigue reconocida en `PREPARED` hasta `close`. Una ejecución futura tiene que llamar el último `_seal` antes de ese `close`. Este incremento no llega a esa ejecución.

La revisión P1 detuvo la publicación hasta demostrar dos puntos. La carrera investigada es un `prepare` competidor después de `PREPARE_CLAIMED` y antes de que la llamada legítima entre en `authority`. El competidor, incluso con el contexto copiado, el mismo gateway, otro gateway u otro `operation_id`, no obtiene admisión ni reserva. Al reanudar, queda una sola lease y una sola fila `HELD` de la operación legítima. El cierre normal de esa admisión, sin ejecutar el modelo, libera la reserva por el `close` público de C02.

El paso 3, el observador, no está iniciado.
