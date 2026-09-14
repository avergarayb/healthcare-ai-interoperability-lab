

# Task 075 — Autenticación servicio-a-servicio del Model Boundary Contract v1

## WHAT — Qué se implementa

Implementar autenticación real entre procesos para proteger el endpoint existente:

```http
GET /api/model-boundary/v1
```

El único consumidor externo autorizado será:

```text
services/ai-service
    └── GET http://localhost:8081/api/model-boundary/v1
```

La autenticación utilizará un **shared secret de laboratorio enviado mediante header HTTP estático**.

### Mecanismo fijado

Header obligatorio:

```http
X-Service-Token: <shared-secret>
```

Variables de entorno:

#### Java — `fhir-integration-service`

```env
MODEL_BOUNDARY_SERVICE_TOKEN=<valor-secreto>
```

#### Python — `services/ai-service`

```env
MODEL_BOUNDARY_SERVICE_TOKEN=<mismo-valor-secreto>
```

El valor debe ser proporcionado únicamente mediante variables de entorno. No se permite commitear `.env`, secretos, tokens reales ni valores sensibles en el repositorio.

---

## WHY — Por qué se implementa

En la Task 074, el `ai-service` consumió correctamente el Model Boundary Contract v1, pero el endpoint Java permanecía abierto.

Esta tarea cierra esa deuda introduciendo autenticación mínima entre servicios, sin introducir:

- OAuth de usuario.
- SMART nuevo.
- Login clínico.
- JWT de producto.
- IdP, Keycloak o Cognito.
- Cambios en el contrato v1.
- Nuevos endpoints clínicos.
- LLM o llamadas a modelos.

La autenticación demuestra la separación entre:

1. Identidad del proceso consumidor.
2. Autorización de acceso al endpoint.
3. Recepción del contrato v1.
4. Decisión futura de llamar o no a un modelo.

La autenticación válida no implica autorización para llamar a un LLM.

---

## HOW — Cómo debe funcionar

### 1. Protección en Java

El endpoint existente:

```http
GET /api/model-boundary/v1
```

debe exigir el header:

```http
X-Service-Token
```

Comportamiento requerido:

| Solicitud | Resultado |
|---|---|
| Header ausente | `401 Unauthorized` **antes** de `currentContract()`. Sin body del contrato v1. No dispara Oracle/Epic. |
| Header vacío | Igual que header ausente. |
| Token incorrecto | Igual que header ausente. |
| Token correcto | La solicitud **llega al controller actual**. El HTTP **no** es automáticamente 200. |

Un token válido solo significa que el request pasa el filtro de servicio. El HTTP status sigue determinado por `ModelBoundaryHttpStatuses`:

| `outcome` | HTTP |
|---|---:|
| `SNAPSHOT_COMPLETE` | `200` |
| `SNAPSHOT_PARTIAL` | `200` |
| `AUTHENTICATION_REQUIRED` | `401` |
| `PATIENT_CONTEXT_NOT_CONFIGURED` | `409` |
| `SNAPSHOT_UNAVAILABLE` | `502` |

La comparación del token debe realizarse contra la variable:

```env
MODEL_BOUNDARY_SERVICE_TOKEN
```

Si la variable no está configurada, Java **permanece levantado**. Solo `GET /api/model-boundary/v1` queda fail-closed y responde **siempre 401**. No tumbar Spring Boot. Las páginas `/lab/*` y los endpoints SMART siguen disponibles.

El mecanismo debe aplicarse únicamente al endpoint:

```http
GET /api/model-boundary/v1
```

No se debe ampliar el alcance hacia otros endpoints clínicos ni modificar la autenticación existente del producto.

#### Colisión de HTTP 401

Hay dos 401 distintos. No confundirlos:

1. **Servicio no autenticado.** Header `X-Service-Token` ausente, vacío o incorrecto, o `MODEL_BOUNDARY_SERVICE_TOKEN` no configurado en Java. Este 401 ocurre **antes** de `currentContract()`, **no incluye** el contrato v1 y no dispara Oracle/Epic.
2. **`AUTHENTICATION_REQUIRED` (SMART).** Token de servicio válido; el controller corre; el outcome funcional es SMART no autenticado. Este 401 **sí** puede incluir el contrato v1 y lo determina `ModelBoundaryHttpStatuses`.

Python puede devolver ambos como:

```json
{
  "status": "rejected",
  "modelCalled": false,
  "contractVersion": null,
  "outcome": null,
  "reason": "boundary_http_4xx"
}
```

porque la regla 074 trata cualquier `4xx` así. Eso no hace equivalentes las causas.

### 2. Respuesta Java con autenticación válida

Cuando el token sea válido, Java ejecuta el controller actual y devuelve el **mismo Model Boundary Contract v1**. El HTTP sigue `ModelBoundaryHttpStatuses`; no es 200 automático.

No se permite:

- Cambiar nombres de campos.
- Añadir `usable`.
- Añadir `requiresHumanReview`.
- Añadir `modelCallAuthorized`.
- Añadir `context`.
- Envolver el contrato en otro objeto.
- Cambiar `contractVersion`.
- Cambiar `outcome`.
- Cambiar las reglas de negocio sintéticas de las Tasks 065–073.

La autenticación solo protege el acceso. No modifica el contenido del contrato.

### 3. Consumo desde Python

El `ai-service` debe enviar el header:

```http
X-Service-Token: <valor-de-MODEL_BOUNDARY_SERVICE_TOKEN>
```

al llamar:

```http
GET http://localhost:8081/api/model-boundary/v1
```

El token no debe aparecer en logs, mensajes de error, respuestas HTTP ni documentación operativa con valores reales.

### 4. Resultado Python ante errores de autenticación

El endpoint Python existente:

```http
GET /internal/agent-context
```

debe conservar su respuesta cerrada y estable.

Cuando Java responda `401`, Python debe devolver:

```json
{
  "status": "rejected",
  "modelCalled": false,
  "contractVersion": null,
  "outcome": null,
  "reason": "boundary_http_4xx"
}
```

El reason `boundary_http_4xx` se mantiene como reason cerrado para cualquier respuesta HTTP `4xx` del boundary, incluyendo `401`.

No se debe interpretar ni transformar el body de error de Java como si fuera un contrato v1.

Para errores de autenticación:

- `status` debe ser `rejected`.
- `modelCalled` debe ser `false`.
- No se debe devolver información clínica.
- No se debe intentar una llamada alternativa sin autenticación.
- No se debe reintentar indefinidamente.
- No se debe ocultar el fallo devolviendo `received`.

### 5. Variables de entorno

El valor del token debe configurarse por entorno en ambos procesos:

```env
MODEL_BOUNDARY_SERVICE_TOKEN=<shared-secret>
```

Requisitos:

- No commitear `.env`.
- Mantener `.env.example` sin secretos reales, si el repositorio utiliza ese patrón.
- Documentar el nombre de la variable.
- Validar que ambos procesos utilicen exactamente el mismo valor en el entorno local de laboratorio.
- No imprimir el valor del token.
- Los tests existentes de `GET /api/model-boundary/v1` deben enviar `X-Service-Token`.
- Dummy versionado permitido en tests: `test-model-boundary-token`.
- No usar secretos reales en el repositorio.
- No exigir “cero tokens en fixtures”: eso rompe los tests actuales.

El shared secret es únicamente un mecanismo de laboratorio. No se presenta como solución definitiva para producción.

---

## CONCEPT — Conceptos y límites

### Shared secret

Un shared secret es un valor conocido por el servicio consumidor y el servicio protegido. El consumidor lo envía mediante un header y Java valida que coincida con el valor configurado.

En esta tarea:

```http
X-Service-Token: <shared-secret>
```

representa la identidad técnica mínima del proceso `ai-service`.

### Autenticación versus autorización

Esta tarea implementa autenticación básica del proceso:

> “¿La llamada presenta el secreto de servicio esperado?”

No implementa autorización fina:

> “¿Este servicio puede acceder a este paciente, clínica, recurso o tipo específico de contexto?”

La autorización fina queda explícitamente fuera del alcance.

### Contrato versus transporte

El Model Boundary Contract v1 es el contenido funcional devuelto por Java.

El header `X-Service-Token` pertenece al transporte y a la seguridad de la llamada. No forma parte del JSON del contrato v1 y no debe agregarse como campo de respuesta.

### No implica llamada a modelo

Aunque la llamada al boundary sea autenticada y el contrato sea recibido correctamente:

```json
{
  "status": "received",
  "modelCalled": false
}
```

La autenticación no autoriza ni ejecuta:

- OpenAI.
- Azure OpenAI.
- Azure AI Foundry.
- Prompts.
- Resúmenes clínicos.
- Inferencia.
- Agentes LLM.

---

## Fuera de alcance

No implementar ni modificar:

- LLM, OpenAI, Azure, Foundry o cualquier proveedor de modelos.
- Prompts o resúmenes clínicos.
- OAuth de usuario.
- SMART nuevo.
- Login clínico.
- JWT de producto.
- IdP, Keycloak o Cognito.
- Ampliación de la allowlist de la Task 042.
- Nuevos endpoints clínicos.
- Patient CRUD.
- Cinco herramientas.
- MCP.
- Kafka.
- LangGraph.
- Nuevos paquetes Java `aiconsumer*`.
- Cambios en los campos del contrato v1.
- Cambios en `requiresHumanReview`.
- `modelCallAuthorized=true`.
- Desactivación de controles deny-by-default de las Tasks 065–073.
- Integración live con Epic u Oracle como prerrequisito.
- Rediseño del Model Boundary Contract v1.

---

## Pruebas requeridas

Las pruebas deben cubrir como mínimo:

### Caso 1 — Llamada sin autenticación

Solicitud:

```http
GET /api/model-boundary/v1
```

Sin header `X-Service-Token`.

Resultado esperado:

```http
401 Unauthorized
```

Sin body del contrato v1. No se invoca `currentContract()`. No se llama a Oracle/Epic.

### Caso 2 — Llamada con token inválido

Solicitud:

```http
GET /api/model-boundary/v1
X-Service-Token: invalid-token
```

Resultado esperado:

```http
401 Unauthorized
```

Sin body del contrato v1. No se invoca `currentContract()`. No se llama a Oracle/Epic.

### Caso 3 — Llamada con token válido

Solicitud:

```http
GET /api/model-boundary/v1
X-Service-Token: test-model-boundary-token
```

El token válido solo abre el controller. El HTTP depende del `outcome`.

Los tests que esperan HTTP `200` **deben mockear** `SNAPSHOT_COMPLETE` (o `SNAPSHOT_PARTIAL`). No usar Oracle/Epic live como prerrequisito.

Resultado esperado con mock `SNAPSHOT_COMPLETE`:

```http
200 OK
```

El body debe ser exactamente compatible con el contrato v1 actual.

Un test adicional puede mockear `AUTHENTICATION_REQUIRED` y esperar HTTP `401` **con** contrato, para no confundirlo con el 401 de servicio (sin contrato).

### Caso 4 — Python sin credencial

Ejecutar `GET /internal/agent-context` con `MODEL_BOUNDARY_SERVICE_TOKEN` ausente o vacío.

Resultado esperado:

```json
{
  "status": "rejected",
  "modelCalled": false,
  "contractVersion": null,
  "outcome": null,
  "reason": "boundary_http_4xx"
}
```

Python **permanece levantado**. `/health` sigue respondiendo. Si `MODEL_BOUNDARY_SERVICE_TOKEN` está ausente o vacío, `/internal/agent-context` llama **sin** header; Java responde 401; Python devuelve el JSON anterior. No tumbar uvicorn. No debe quedar una llamada no autenticada funcionando silenciosamente como `received`.

### Caso 5 — Python con credencial inválida

Configurar un token diferente al token Java.

Resultado esperado:

```json
{
  "status": "rejected",
  "modelCalled": false,
  "contractVersion": null,
  "outcome": null,
  "reason": "boundary_http_4xx"
}
```

### Caso 6 — Python con credencial válida

Configurar el mismo token en Java y Python.

Resultado esperado:

- Java deja pasar el header y ejecuta el controller actual.
- Si el test mockea `SNAPSHOT_COMPLETE` con contexto retenido: Java `200`, Python `status=received`, `modelCalled=false`.
- Si el test mockea `AUTHENTICATION_REQUIRED`: Java `401` (SMART), Python `rejected` / `boundary_http_4xx`.
- No Oracle/Epic live como prerrequisito.
- El contrato v1 no se modifica.

### Modalidad de pruebas

Las pruebas pueden ejecutarse mediante:

- Tests unitarios con mocks.
- Tests de integración locales entre Java y Python.
- Test local con ambos procesos levantados.

No se requiere Epic ni Oracle live como prerrequisito.

---

## Criterios de aceptación

- [ ] `GET /api/model-boundary/v1` rechaza solicitudes sin `X-Service-Token`.
- [ ] `GET /api/model-boundary/v1` rechaza tokens inválidos con HTTP `401`.
- [ ] Una solicitud con token válido llega al controller; el HTTP sigue `ModelBoundaryHttpStatuses` (no es 200 automático).
- [ ] Un test con token válido y mock `SNAPSHOT_COMPLETE` recibe HTTP `200` y el contrato v1 existente.
- [ ] Python envía `X-Service-Token` al consumir Java.
- [ ] Python devuelve `rejected` ante respuestas `401` o cualquier `4xx` del boundary.
- [ ] Python conserva `modelCalled=false` en todos los casos.
- [ ] El token se configura exclusivamente mediante variables de entorno.
- [ ] No existen secretos reales en el repositorio.
- [ ] No se modifica Java clínico ni se reescribe el contrato v1.
- [ ] No se amplía la allowlist de la Task 042.
- [ ] No se agregan nuevos endpoints clínicos.
- [ ] Existen pruebas para llamada sin auth, auth inválida y auth válida.
- [ ] Las pruebas no dependen de Epic u Oracle live.
- [ ] Se documenta que la autenticación fina y el acceso a modelos siguen abiertos.
- [ ] La documentación no presenta el shared secret como mecanismo definitivo de producción.

---

## Documentación requerida

Actualizar o crear la documentación correspondiente a la Task 075 incluyendo:

1. El motivo de la deuda de seguridad existente en 074.
2. El mecanismo elegido:
   - Header `X-Service-Token`.
   - Variable `MODEL_BOUNDARY_SERVICE_TOKEN`.
3. El comportamiento HTTP `401`.
4. El comportamiento de Python ante `4xx`.
5. La configuración local sin commitear secretos.
6. Las pruebas ejecutadas.
7. Las limitaciones del mecanismo de laboratorio.
8. La deuda que permanece abierta:
   - Autorización fina entre servicios.
   - Rotación y gestión formal de secretos.
   - Identidad de servicio más robusta para producción.
   - LLM y decisión de model call.

---

## STOP explícito

Esta tarea termina cuando el acceso al Model Boundary Contract v1 está protegido por autenticación servicio-a-servicio básica y verificable.

El siguiente paso es la **Task 076 — integración controlada con LLM**.

La Task 076 no forma parte de esta implementación y no debe iniciarse dentro de la Task 075.

