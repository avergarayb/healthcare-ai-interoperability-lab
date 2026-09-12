# Task 065 — Real Consumer Authentication and Authorization Boundary

## 1. WHAT

Diseñar e implementar una frontera aislada posterior a `AiHandoffAuthorizationBoundary` que represente la **autenticación y autorización real de un consumidor futuro**, sin ejecutar ningún handoff, dispatch ni llamada a modelos.

La tarea debe establecer un contrato técnico explícito para distinguir:

```text
Identidad del consumidor
    ≠ autenticación validada
    ≠ autorización concedida
    ≠ handoff autorizado
    ≠ dispatch ejecutado
```

La implementación debe permanecer en modo **deny-by-default**.

### Nombre sugerido

`RealConsumerAuthorizationBoundary`

### Paquete sugerido

```text
lab.healthcare.fhir.aiconsumerauthorization
```

### Rama sugerida

```text
feature/ai-consumer-authorization-boundary
```

### Commit sugerido

```text
feat: add ai consumer authorization boundary
```

No realizar push automático.

---

## 2. WHY

La cadena actual llega hasta:

```text
AiHandoffAuthorizationBoundary
    → HANDOFF_NOT_AUTHORIZED
```

La siguiente frontera natural es definir cómo un consumidor futuro podría ser autenticado y autorizado de forma explícita.

Sin embargo, esta tarea no debe interpretar:

```text
READY_FOR_FUTURE_HANDOFF
HANDOFF_NOT_AUTHORIZED
```

como autorización real.

Tampoco debe introducir una falsa sensación de seguridad mediante:

- un booleano configurable;
- un query parameter;
- un header arbitrario;
- una identidad sintética aceptada automáticamente;
- una autorización simulada como si fuera OAuth2, JWT, SMART on FHIR o RBAC real.

La tarea debe dejar preparada una separación arquitectónica para una futura integración de seguridad, sin implementar todavía un proveedor de identidad ni permitir el consumo real de datos o servicios.

---

## 3. HOW

## 3.1. Alcance funcional

Crear un componente aislado que:

1. Reciba el resultado de `AiHandoffAuthorizationBoundary`.
2. Reciba un contexto de autenticación/autorización **sintético y explícitamente no confiable**.
3. Evalúe si existe evidencia suficiente para considerar que el consumidor está autenticado y autorizado.
4. Mantenga la decisión en estado denegado mientras no exista una implementación real.
5. Produzca un resultado auditable y determinístico.
6. No ejecute ninguna operación externa.
7. No cambie ningún campo clínico del contrato v1.
8. No permita que parámetros HTTP activen autorización.

La implementación debe demostrar la diferencia entre:

```text
Authentication context present
    ≠ authenticated
```

y:

```text
Authenticated
    ≠ authorized
```

y:

```text
Authorized
    ≠ handoff executed
```

---

## 3.2. Entrada principal

El componente debe consumir:

```text
AiHandoffAuthorizationResult
```

desde el paquete:

```text
lab.healthcare.fhir.aihandoffauthorization
```

No debe consumir directamente:

- `FhirService`;
- `Epic`;
- `Oracle`;
- `HAPI FHIR`;
- `Bundle`;
- `Patient`;
- `MedicationRequest`;
- `AiBoundaryResult`;
- `FirstAiResult`;
- `AiExecutionDecision`;
- `AiConsumerContract`;
- `AiConsumerPolicyResult`;
- `AiConsumerReadinessResult`.

La frontera debe depender únicamente del resultado inmediatamente anterior y de un contexto de seguridad sintético definido dentro del nuevo paquete.

---

## 3.3. Contexto de autenticación sintético

Crear un modelo interno similar a:

```text
ConsumerSecurityContext
```

El nombre puede variar, pero debe representar únicamente metadatos abstractos de seguridad.

Campos sugeridos:

```text
contextPresent
authenticationMechanism
authenticationVerified
consumerType
consumerIdentifierPresent
authorizationEvaluated
requestedOperation
requestedScope
tenantContextPresent
credentialMaterialPresent
realSecurityProviderConfigured
```

Restricciones:

- No incluir tokens reales.
- No incluir JWT completos.
- No incluir secretos.
- No incluir API keys.
- No incluir Patient IDs.
- No incluir FHIR JSON.
- No incluir headers HTTP crudos.
- No incluir credenciales en logs.
- No permitir que el consumidor proporcione directamente `authenticated=true` para obtener autorización.
- No permitir que el consumidor proporcione directamente `authorized=true`.
- No aceptar `?authenticated=true`, `?authorized=true` ni equivalentes.
- No usar valores enviados por el cliente como prueba suficiente de autenticación.

El contexto puede ser construido internamente con valores explícitamente sintéticos para demostrar los estados del contrato.

---

## 3.4. Estados del resultado

Crear un resultado nuevo, por ejemplo:

```text
AiConsumerAuthorizationResult
```

Estados mínimos sugeridos:

```text
AUTHORIZATION_NOT_IMPLEMENTED
BLOCKED
HUMAN_REVIEW_REQUIRED
NOT_AUTHENTICATED
NOT_AUTHORIZED
```

No crear ni devolver estados que impliquen ejecución, tales como:

```text
AUTHORIZED
HANDOFF_AUTHORIZED
DISPATCHED
MODEL_AUTHORIZED
MODEL_CALLED
```

Si se considera necesario diferenciar “autenticación ausente” de “autorización ausente”, hacerlo únicamente como diagnóstico interno, manteniendo la decisión final denegada.

---

## 3.5. Resultado obligatorio

En todas las rutas normales y de error controlado, el resultado debe conservar:

```text
handoffAuthorized=false
dispatchPerformed=false
externalAuthorizationAvailable=false
modelCallAuthorized=false
modelCalled=false
processingStatus=NOT_EXECUTED
dispatchStatus=NOT_DISPATCHED
requiresHumanReview=true
```

Además, el nuevo resultado debe incluir:

```text
authenticationVerified=false
authorizationGranted=false
realSecurityProviderConfigured=false
consumerAuthorizationAvailable=false
```

El campo `consumerAuthorizationAvailable` debe expresar disponibilidad de una autorización real implementada, no la existencia de un contexto sintético.

Debe permanecer en:

```text
false
```

---

## 3.6. Reglas determinísticas

### Regla A — Entrada inexistente

Si el resultado de `AiHandoffAuthorizationBoundary` es inexistente:

```text
status=BLOCKED
reason=MISSING_HANDOFF_AUTHORIZATION_RESULT
```

### Regla B — Handoff no autorizado

Si:

```text
handoffAuthorized=false
```

el resultado debe permanecer denegado:

```text
status=AUTHORIZATION_NOT_IMPLEMENTED
reason=HANDOFF_NOT_AUTHORIZED
```

No debe intentar corregir ni elevar el estado.

### Regla C — Handoff autorizado de forma inesperada

Si la entrada contiene:

```text
handoffAuthorized=true
```

la implementación debe tratarlo como una inconsistencia:

```text
status=BLOCKED
reason=UNEXPECTED_HANDOFF_AUTHORIZATION
```

No debe propagar el valor como autorización válida.

### Regla D — Contexto sintético presente

Si existe un contexto sintético, pero:

```text
realSecurityProviderConfigured=false
authenticationVerified=false
authorizationEvaluated=false
```

el resultado debe ser:

```text
status=AUTHORIZATION_NOT_IMPLEMENTED
reason=REAL_AUTHENTICATION_AUTHORIZATION_NOT_IMPLEMENTED
```

### Regla E — Identidad declarada sin verificación

Si existe un identificador de consumidor, pero no existe verificación criptográfica o validación mediante un proveedor real:

```text
status=NOT_AUTHENTICATED
reason=CONSUMER_IDENTITY_NOT_VERIFIED
```

Un identificador textual nunca debe considerarse autenticación.

### Regla F — Autenticación sintética marcada como válida

Si el contexto intenta declarar:

```text
authenticationVerified=true
```

sin un proveedor real configurado:

```text
status=BLOCKED
reason=UNTRUSTED_AUTHENTICATION_ASSERTION
```

No debe aceptar el valor.

### Regla G — Autorización sintética marcada como concedida

Si el contexto intenta declarar:

```text
authorizationGranted=true
```

sin una autorización real implementada:

```text
status=BLOCKED
reason=UNTRUSTED_AUTHORIZATION_ASSERTION
```

### Regla H — Scope conceptual

El scope conceptual esperado puede ser:

```text
ai.handoff.request
```

Pero el scope no debe considerarse concedido únicamente porque aparezca en el contexto.

Si el scope está presente sin autenticación y autorización verificadas:

```text
status=NOT_AUTHORIZED
reason=SCOPE_NOT_VERIFIED
```

### Regla I — Tenant ausente

Si el contexto no contiene un contexto de tenant verificable:

```text
status=BLOCKED
reason=MISSING_TENANT_CONTEXT
```

No utilizar valores de tenant sintéticos como autorización real.

### Regla J — Parámetros de activación

La autorización no debe cambiar por:

```text
?authorized=true
?authenticated=true
?allow=true
?dispatch=true
?handoff=true
```

Tampoco por headers arbitrarios como:

```text
X-Authorized
X-Authenticated
X-Allow-Handoff
X-Consumer-Scope
```

Si se implementa un endpoint de laboratorio, dichos valores deben ignorarse o producir una respuesta denegada.

---

## 3.7. Contrato de seguridad conceptual

Documentar la siguiente secuencia:

```text
Consumer identity claimed
    ↓
Authentication performed by trusted provider
    ↓
Authentication verified
    ↓
Tenant context verified
    ↓
Operation and scope evaluated
    ↓
Authorization granted
    ↓
Handoff authorization evaluated separately
    ↓
Dispatch remains a separate future boundary
```

La implementación de Task 065 debe cubrir únicamente la representación y validación de la frontera de autenticación/autorización.

No debe implementar:

- OAuth2;
- OpenID Connect;
- SMART on FHIR;
- JWT validation;
- JWKS;
- PKCE;
- client registration;
- token introspection;
- mTLS;
- API gateway security;
- identity provider;
- role mapping real;
- external policy engine.

---

## 3.8. Endpoint de laboratorio

Si se considera necesario agregar un endpoint, usar uno de estos nombres:

```text
GET /lab/ai-consumer-authorization
```

o:

```text
GET /api/ai-consumer-authorization/v1
```

El endpoint debe:

- ser exclusivamente de laboratorio;
- no ser público;
- no aceptar credenciales reales;
- no aceptar tokens;
- no aceptar Patient IDs;
- no aceptar FHIR JSON;
- no ejecutar handoff;
- no realizar llamadas externas;
- devolver únicamente el resultado sintético de la frontera.

La respuesta no debe incluir:

- tokens;
- secretos;
- headers completos;
- identificadores de pacientes;
- recursos FHIR;
- datos clínicos;
- payloads de Bundle.

---

## 3.9. Integración con la proyección clínica

Actualizar la proyección únicamente para exponer un resumen no sensible, por ejemplo:

```text
aiConsumerAuthentication=NOT_AUTHENTICATED
aiConsumerAuthorization=AUTHORIZATION_NOT_IMPLEMENTED
aiConsumerAuthorizationAvailable=false
```

No cambiar:

```text
modelBoundaryContract=v1
agentStub=SUCCEEDED
deterministicAgent=READY
aiBoundary=PREPARED
clinicalDataAvailable=true
modelCallAuthorized=false
aiModelCalled=false
medicationRequestsStatus=NOT_REQUESTED
firstAiComponent=PREPARED
aiProcessingStatus=NOT_EXECUTED
aiExecutionGate=ELIGIBLE_BUT_NOT_AUTHORIZED
aiConsumerContract=v1
aiConsumerStatus=READY
aiDispatchStatus=NOT_DISPATCHED
aiConsumerPolicy=ALLOWED_FOR_FUTURE_CONSUMPTION
aiConsumerReadiness=READY_FOR_FUTURE_HANDOFF
aiHandoffAuthorization=HANDOFF_NOT_AUTHORIZED
```

La nueva información debe agregarse sin sobrescribir ni reinterpretar los estados existentes.

---

## 3.10. Reglas de aislamiento

El paquete nuevo puede depender de:

```text
lab.healthcare.fhir.aihandoffauthorization
```

No debe depender directamente de:

```text
lab.healthcare.fhir
lab.healthcare.fhir.service
lab.healthcare.fhir.epic
lab.healthcare.fhir.oracle
lab.healthcare.fhir.pipeline
lab.healthcare.fhir.agent
lab.healthcare.fhir.aiboundary
lab.healthcare.fhir.firstai
lab.healthcare.fhir.aigateway
lab.healthcare.fhir.aiconsumer
lab.healthcare.fhir.aiconsumerpolicy
lab.healthcare.fhir.aiconsumerreadiness
```

Excepto la dependencia directa permitida hacia el resultado de Task 064.

No debe importar:

- clases de HAPI FHIR;
- `FhirContext`;
- recursos R4;
- clientes HTTP;
- `WebClient`;
- `RestClient`;
- `Feign`;
- RabbitMQ;
- SDKs de modelos;
- clases de Epic;
- clases de Oracle;
- clases de autenticación de infraestructura no existentes.

No debe ser importado por:

- `FhirService`;
- adaptadores Epic;
- adaptadores Oracle;
- pipeline clínico;
- `DeterministicAgent`;
- `AiBoundary`;
- `FirstAiComponent`;
- `AiExecutionGate`;
- `AiConsumerContract`;
- `AiConsumerPolicy`;
- `AiConsumerReadiness`.

La integración con la proyección debe hacerse mediante un adaptador o ensamblador explícito, sin introducir dependencias inversas.

---

## 3.11. Contrato de auditoría

El resultado debe incluir una razón estable y no sensible.

Campos sugeridos:

```text
status
reason
operation
requestedScope
authenticationVerified
authorizationGranted
realSecurityProviderConfigured
consumerAuthorizationAvailable
handoffAuthorized
dispatchPerformed
modelCallAuthorized
modelCalled
processingStatus
dispatchStatus
requiresHumanReview
```

No registrar:

- credenciales;
- tokens;
- valores de Authorization;
- Patient IDs;
- identificadores clínicos;
- Bundle;
- FHIR JSON;
- secretos;
- payloads completos.

Los logs, si existen, deben registrar únicamente:

```text
status
reason
operation
```

---

## 4. CONCEPT

## 4.1. Autenticación

La autenticación responde:

> ¿Quién es el consumidor?

Una identidad declarada no es suficiente. Debe existir una validación confiable realizada por un proveedor real.

En Task 065 no se implementará ese proveedor.

Por ello:

```text
consumerIdentifierPresent=true
```

no implica:

```text
authenticationVerified=true
```

---

## 4.2. Autorización

La autorización responde:

> ¿Qué puede hacer el consumidor autenticado?

Incluso si en el futuro existiera autenticación válida, todavía sería necesario evaluar:

- operación;
- scope;
- tenant;
- permisos;
- contexto de uso;
- política de acceso.

Task 065 no concede permisos reales.

---

## 4.3. Handoff

La autorización de consumidor no equivale a autorización de handoff.

La separación correcta es:

```text
Consumer authenticated
    ≠ Consumer authorized
    ≠ Handoff authorized
    ≠ Dispatch executed
```

Task 065 no debe producir:

```text
handoffAuthorized=true
```

---

## 4.4. Deny-by-default

El resultado por defecto debe ser denegado.

La ausencia de evidencia no debe interpretarse como permiso:

```text
missing authentication → deny
missing authorization → deny
missing tenant → deny
missing scope → deny
synthetic assertion → deny
unexpected true flag → block
```

---

## 4.5. Estado de preparación

La tarea prepara una frontera arquitectónica para una futura seguridad real.

No implementa todavía:

- seguridad de producción;
- identidad federada;
- OAuth;
- autorización por scopes real;
- consumo de datos;
- handoff;
- dispatch;
- inferencia.

El objetivo es que la siguiente etapa no tenga que mezclar autenticación, autorización, handoff y ejecución en un único componente.

---

## 5. Pruebas requeridas

Agregar pruebas unitarias y de integración aisladas.

### Prueba A — Entrada válida de Task 064, sin seguridad real

Esperado:

```text
status=AUTHORIZATION_NOT_IMPLEMENTED
authenticationVerified=false
authorizationGranted=false
consumerAuthorizationAvailable=false
```

### Prueba B — Entrada inexistente

Esperado:

```text
status=BLOCKED
reason=MISSING_HANDOFF_AUTHORIZATION_RESULT
```

### Prueba C — `handoffAuthorized=true` inesperado

Esperado:

```text
status=BLOCKED
reason=UNEXPECTED_HANDOFF_AUTHORIZATION
```

### Prueba D — Identidad declarada sin verificación

Esperado:

```text
status=NOT_AUTHENTICATED
reason=CONSUMER_IDENTITY_NOT_VERIFIED
```

### Prueba E — `authenticationVerified=true` sin proveedor real

Esperado:

```text
status=BLOCKED
reason=UNTRUSTED_AUTHENTICATION_ASSERTION
```

### Prueba F — `authorizationGranted=true` sin proveedor real

Esperado:

```text
status=BLOCKED
reason=UNTRUSTED_AUTHORIZATION_ASSERTION
```

### Prueba G — Scope conceptual presente, pero no verificado

Esperado:

```text
status=NOT_AUTHORIZED
reason=SCOPE_NOT_VERIFIED
```

### Prueba H — Tenant ausente

Esperado:

```text
status=BLOCKED
reason=MISSING_TENANT_CONTEXT
```

### Prueba I — Parámetros de activación

Verificar que ningún parámetro equivalente a:

```text
authorized=true
authenticated=true
allow=true
dispatch=true
handoff=true
```

cambie el resultado.

### Prueba J — Headers de activación

Verificar que headers arbitrarios no concedan autorización.

### Prueba K — Invariantes globales

Para todos los estados:

```text
handoffAuthorized=false
dispatchPerformed=false
externalAuthorizationAvailable=false
modelCallAuthorized=false
modelCalled=false
processingStatus=NOT_EXECUTED
dispatchStatus=NOT_DISPATCHED
requiresHumanReview=true
authenticationVerified=false
authorizationGranted=false
realSecurityProviderConfigured=false
consumerAuthorizationAvailable=false
```

### Prueba L — No regresión

Verificar que la cadena anterior continúe mostrando:

```text
aiHandoffAuthorization=HANDOFF_NOT_AUTHORIZED
```

y que no cambien los estados de Tasks 057–064.

### Prueba M — No dependencias prohibidas

Revisar imports y dependencias para confirmar que el nuevo paquete no incorpora:

- HAPI FHIR;
- HTTP clients;
- RabbitMQ;
- SDKs de modelos;
- Epic;
- Oracle;
- autenticación real.

### Prueba N — No datos sensibles

Verificar que la respuesta y los logs no incluyan:

- tokens;
- Patient IDs;
- FHIR JSON;
- Bundle;
- datos clínicos.

---

## 6. Documentación requerida

Crear:

```text
docs/fhir/ai-consumer-authorization-boundary.md
```

La documentación debe incluir:

1. objetivo;
2. alcance;
3. estados;
4. contrato de entrada;
5. contrato de salida;
6. reglas deny-by-default;
7. diferencia entre autenticación y autorización;
8. diferencia entre autorización de consumidor y handoff;
9. invariantes;
10. parámetros que no conceden autorización;
11. dependencias permitidas;
12. dependencias prohibidas;
13. ejemplos sintéticos sin datos sensibles;
14. limitaciones;
15. trabajo explícitamente fuera de alcance.

Actualizar `docs/progress/progress-log.md` con:

- fecha;
- Task 065;
- rama;
- commit;
- resumen;
- pruebas ejecutadas;
- resultado;
- invariantes verificadas.

No incluir tokens, secretos, Patient IDs ni FHIR JSON.

---

## 7. Definition of Done

Task 065 está terminada cuando:

- [ ] Existe el paquete aislado `aiconsumerauthorization`.
- [ ] Consume únicamente el resultado de Task 064.
- [ ] Define un contexto sintético de seguridad.
- [ ] No implementa autenticación real.
- [ ] No implementa autorización real.
- [ ] Mantiene deny-by-default.
- [ ] No concede `handoffAuthorized=true`.
- [ ] No concede `dispatchPerformed=true`.
- [ ] No concede `modelCallAuthorized=true`.
- [ ] No concede `externalAuthorizationAvailable=true`.
- [ ] Mantiene `modelCalled=false`.
- [ ] Mantiene `processingStatus=NOT_EXECUTED`.
- [ ] Mantiene `dispatchStatus=NOT_DISPATCHED`.
- [ ] Mantiene `requiresHumanReview=true`.
- [ ] No incorpora LLM ni `ai-service`.
- [ ] No incorpora HTTP clients.
- [ ] No incorpora RabbitMQ.
- [ ] No incorpora OAuth, JWT, SMART ni tokens.
- [ ] No modifica el contrato clínico v1.
- [ ] No amplía la allowlist 042.
- [ ] No agrega `MedicationRequest` en Epic.
- [ ] No registra datos sensibles.
- [ ] Tiene pruebas para entradas válidas, inválidas e inconsistentes.
- [ ] Tiene pruebas de no activación por query params y headers.
- [ ] Tiene documentación.
- [ ] Los tests existentes continúan pasando.
- [ ] Se ejecuta `mvn test` correctamente.
- [ ] Se verifica el endpoint live sin cambios clínicos.
- [ ] El commit usa Conventional Commits.
- [ ] No se realiza push automático.

---

## 8. Instrucción final para Cursor

Implementa únicamente **Task 065 — Real Consumer Authentication and Authorization Boundary**.

No implementes Task 066 ni ninguna etapa posterior.

No reescribas Tasks 057–064.

No introduzcas autenticación real, OAuth2, JWT, SMART on FHIR, tokens, proveedores de identidad, autorización de producción, handoff, dispatch, WebClient, Feign, RabbitMQ, LLM, OpenAI, Azure OpenAI, Gemini, Claude, RAG, LangGraph ni `ai-service`.

La implementación debe ser una frontera aislada, determinística y deny-by-default que represente la separación entre identidad declarada, autenticación verificada, autorización concedida y handoff.

Mantén obligatoriamente:

```text
modelCallAuthorized=false
modelCalled=false
processingStatus=NOT_EXECUTED
dispatchStatus=NOT_DISPATCHED
requiresHumanReview=true
handoffAuthorized=false
dispatchPerformed=false
externalAuthorizationAvailable=false
authenticationVerified=false
authorizationGranted=false
realSecurityProviderConfigured=false
consumerAuthorizationAvailable=false
```

No uses parámetros HTTP ni headers para activar autorización.

No registres tokens, secretos, Patient IDs, FHIR JSON, Bundle ni datos clínicos.

Ejecuta todas las pruebas existentes y las nuevas pruebas de Task 065. Actualiza la documentación y el progress log. Usa una rama `feature/*` y un commit Conventional Commit:

```text
feat: add ai consumer authorization boundary
```

No hagas push automático.
