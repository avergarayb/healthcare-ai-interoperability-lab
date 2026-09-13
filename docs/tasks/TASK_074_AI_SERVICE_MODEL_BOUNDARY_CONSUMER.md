# Task 074 — Primer consumidor Python del Model Boundary Contract v1

## WHAT

Crear el primer consumidor externo del contrato clínico existente mediante un nuevo servicio Python `ai-service` con FastAPI.

El servicio consumirá:

```http
GET /api/model-boundary/v1
```

No incorporará todavía ningún modelo de lenguaje ni accederá directamente a sistemas clínicos.

## Ubicación

El servicio debe crearse dentro del mismo repositorio:

```text
healthcare-ai-interoperability-lab/
└── services/
    └── ai-service/
```

No debe crearse fuera del repositorio ni dentro de `fhir-integration-service`.

## WHY

Esta tarea inicia el Producto B —servicios de agentes de salud— sin reescribir el Producto A ni duplicar responsabilidades.

```text
Sistemas clínicos / sandboxes
        ↓
Producto A — Java
        ↓
Model Boundary Contract v1
        ↓
Producto B — Python ai-service
        ↓
Resultado del consumidor
```

El contrato Java existente será la única fuente de contexto clínico para este primer consumidor.

## HECHOS Y RESTRICCIONES

### Contrato existente

`GET /api/model-boundary/v1` devuelve directamente un `ModelBoundaryContract` versión 1 con:

- `contractVersion`
- `destination`
- `contextSource`
- `generatedAt`
- `outcome`
- `patient`
- `conditions`
- `observations`
- `diagnosticReports`
- `medicationRequests`

Cada colección clínica contiene:

- `status`
- `receivedCount`
- `retainedCount`
- `truncated`
- `records`

El contrato **no contiene**:

- `usable`
- `requiresHumanReview`
- `modelCallAuthorized`
- `context`

El consumidor Python no debe envolver el contrato en otro objeto ni modificar su estructura.

### Componentes existentes

`GET /api/agent-stub/v1` ya consume el contrato desde Java.

La Task 074 debe crear el primer consumidor externo en Python. No debe crear un segundo stub Java.

Las Tasks 065–073 ya están implementadas y testeadas. Sus controles son puertas sintéticas `deny-by-default`, no autorización OAuth ni autenticación real entre servicios.

El endpoint Java está actualmente abierto. Esto debe documentarse explícitamente como deuda conocida. La autenticación servicio-a-servicio corresponde a la Task 075.

## HOW

### 1. Crear el servicio Python

Crear el servicio en:

```text
services/ai-service
```

Usar FastAPI.

La estructura mínima debe permitir:

- iniciar el servicio localmente;
- exponer un endpoint HTTP de prueba;
- invocar el endpoint Java;
- validar la respuesta;
- devolver un resultado controlado;
- ejecutar pruebas automatizadas.

No agregar todavía dependencias de LLM, agentes, RAG, MCP, LangGraph ni proveedores de modelos.

### 2. Configuración

Usar variables de entorno para la configuración, sin commitear secretos.

Variables mínimas esperadas:

```text
MODEL_BOUNDARY_BASE_URL
MODEL_BOUNDARY_PATH
MODEL_BOUNDARY_TIMEOUT_SECONDS
AI_SERVICE_HOST
AI_SERVICE_PORT
```

Valores locales de referencia:

```text
MODEL_BOUNDARY_BASE_URL=http://localhost:8081
MODEL_BOUNDARY_PATH=/api/model-boundary/v1
MODEL_BOUNDARY_TIMEOUT_SECONDS=90
AI_SERVICE_HOST=0.0.0.0
AI_SERVICE_PORT=8090
```

El puerto `8090` es una propuesta. Si el repositorio ya tiene una convención distinta, respetarla y documentarla.

El valor de referencia para el laboratorio es `90` segundos porque la llamada Java puede tardar mientras genera el snapshot desde Oracle o Epic. El socket de origen puede tener un timeout de hasta aproximadamente `60` segundos.

El valor `5` segundos debe utilizarse únicamente en pruebas con mocks, no como timeout de laboratorio para la integración real.

No incluir credenciales ni secretos en archivos versionados.

### 3. Endpoint del ai-service

Crear un endpoint interno mínimo, por ejemplo:

```http
GET /internal/agent-context
```

La ruta exacta puede variar si existe una convención previa en el repositorio.

El endpoint debe:

1. Invocar:

   ```http
   GET {MODEL_BOUNDARY_BASE_URL}{MODEL_BOUNDARY_PATH}
   ```

2. Aplicar el timeout configurado.

3. Validar el código HTTP.

4. Validar que la respuesta sea JSON.

5. Validar los campos estructurales mínimos:

   - `contractVersion`
   - `outcome`
   - `patient`
   - `conditions`
   - `observations`
   - `diagnosticReports`
   - `medicationRequests`

6. Evaluar el valor de `outcome`.

7. Devolver un resultado propio del `ai-service`.

### 4. Resultado del ai-service

El resultado externo del consumidor debe ser propio del Producto B y no debe confundirse con el contrato Java.

El JSON de salida debe tener exactamente estos campos:

```json
{
  "status": "received | rejected",
  "modelCalled": false,
  "contractVersion": "v1",
  "outcome": "SNAPSHOT_COMPLETE | SNAPSHOT_PARTIAL | SNAPSHOT_UNAVAILABLE | PATIENT_CONTEXT_NOT_CONFIGURED | AUTHENTICATION_REQUIRED",
  "reason": null
}
```

Reglas obligatorias:

- `status` solo puede ser `received` o `rejected`.
- `modelCalled` siempre debe ser `false`.
- `contractVersion` debe proceder del contrato recibido.
- `outcome` debe proceder del contrato recibido cuando exista un contrato válido.
- `reason` debe ser `null` cuando `status=received`.
- `reason` debe utilizar únicamente uno de estos valores cerrados cuando `status=rejected`:

  - `empty_context`
  - `boundary_outcome_not_success`
  - `boundary_http_4xx`
  - `boundary_http_5xx`
  - `boundary_timeout`
  - `boundary_connection_error`
  - `invalid_contract`

Está prohibido devolver:

- `records`;
- `patient`;
- identificadores de pacientes;
- tokens;
- valores clínicos;
- el contrato Java completo;
- cualquier otro campo no definido en el JSON de salida.

### 5. Reglas de evaluación

#### Enumeración real de `ClinicalSnapshotOutcome`

No existe un outcome `SUCCESS`.

Los valores reales son:

- `SNAPSHOT_COMPLETE`
- `SNAPSHOT_PARTIAL`
- `SNAPSHOT_UNAVAILABLE`
- `PATIENT_CONTEXT_NOT_CONFIGURED`
- `AUTHENTICATION_REQUIRED`

#### Resultado `received`

El consumidor debe devolver `received` únicamente cuando:

1. Java responde HTTP 200;
2. el contrato es válido;
3. `outcome` es `SNAPSHOT_COMPLETE` o `SNAPSHOT_PARTIAL`;
4. existe contexto clínico retenido.

`SNAPSHOT_PARTIAL` se considera `received`: el límite de contexto funcionó, aunque una o más colecciones hayan presentado fallos.

Ejemplo:

```json
{
  "status": "received",
  "modelCalled": false,
  "contractVersion": "v1",
  "outcome": "SNAPSHOT_PARTIAL",
  "reason": null
}
```

#### Resultado `rejected`

El consumidor debe devolver `rejected` cuando:

- `outcome` sea `SNAPSHOT_UNAVAILABLE`;
- `outcome` sea `PATIENT_CONTEXT_NOT_CONFIGURED`;
- `outcome` sea `AUTHENTICATION_REQUIRED`;
- la respuesta HTTP no sea 200;
- el contrato sea inválido;
- el contrato no tenga contexto clínico retenido.

#### Regla de `empty_context`

`empty_context` se determina utilizando la misma regla conceptual que `AgentStub.hasClinicalData`:

> El contexto está vacío cuando ninguna colección clínica tiene `retainedCount > 0`.

No leer `records` ni valores clínicos para decidir si existe contexto.

La evaluación debe considerar las colecciones:

- `conditions`;
- `observations`;
- `diagnosticReports`;
- `medicationRequests`.

`medicationRequests: null` es válido, especialmente para respuestas de Epic.

La diferencia entre campo omitido y campo explícitamente `null` debe respetarse durante la validación. No asumir que ambos casos son idénticos sin documentarlo en el modelo de validación.

Si ningún `retainedCount` es mayor que cero:

```json
{
  "status": "rejected",
  "modelCalled": false,
  "contractVersion": "v1",
  "outcome": "SNAPSHOT_COMPLETE",
  "reason": "empty_context"
}
```

#### `outcome` no exitoso

Si el contrato es válido y `outcome` es uno de los siguientes:

- `SNAPSHOT_UNAVAILABLE`;
- `PATIENT_CONTEXT_NOT_CONFIGURED`;
- `AUTHENTICATION_REQUIRED`;

devolver:

```json
{
  "status": "rejected",
  "modelCalled": false,
  "contractVersion": "v1",
  "outcome": "SNAPSHOT_UNAVAILABLE",
  "reason": "boundary_outcome_not_success"
}
```

El valor real de `outcome` debe conservarse. No reemplazarlo por `SUCCESS` ni por otro valor inventado.

No se debe intentar recuperar datos directamente desde Epic, Oracle, FHIR, HAPI FHIR o SMART.

#### Error HTTP 4xx o 5xx

Si Java responde con error HTTP:

- HTTP 4xx → `boundary_http_4xx`;
- HTTP 5xx → `boundary_http_5xx`.

En estos casos no existe un contrato confiable que devolver, por lo que `contractVersion` y `outcome` deben ser `null`.

Ejemplo:

```json
{
  "status": "rejected",
  "modelCalled": false,
  "contractVersion": null,
  "outcome": null,
  "reason": "boundary_http_4xx"
}
```

No exponer el body completo de error ni información clínica.

#### Timeout o error de conexión

Si el endpoint Java no responde dentro del timeout o existe un error de conexión:

- timeout → `boundary_timeout`;
- error de conexión → `boundary_connection_error`.

En estos casos `contractVersion` y `outcome` deben ser `null`.

No realizar reintentos complejos ni circuit breaker en esta tarea, salvo que ya exista una convención obligatoria.

#### Contrato inválido

Usar `invalid_contract` cuando:

- el body no sea JSON válido;
- falte un campo estructural obligatorio;
- el tipo de un campo sea incompatible;
- `outcome` no pertenezca a la enumeración real;
- la estructura de una colección no permita evaluar `retainedCount` de forma segura.

En este caso, `contractVersion` y `outcome` deben ser `null`, salvo que puedan leerse de forma segura sin aceptar el contrato como válido.

Ejemplo:

```json
{
  "status": "rejected",
  "modelCalled": false,
  "contractVersion": null,
  "outcome": null,
  "reason": "invalid_contract"
}
```

### 6. Trazabilidad

Agregar trazabilidad técnica mínima:

- correlation ID por solicitud;
- método y ruta invocada;
- código HTTP recibido;
- duración de la llamada;
- resultado técnico final.

No registrar:

- Patient ID;
- tokens;
- headers sensibles;
- JSON completo;
- valores clínicos;
- body completo de errores.

Si el repositorio ya tiene una convención de correlation ID, reutilizarla.

### 7. Documentación

Documentar en el servicio:

- propósito del `ai-service`;
- dependencia de `GET /api/model-boundary/v1`;
- contrato consumido sin modificaciones;
- endpoint local del consumidor;
- variables de entorno;
- estados de salida;
- comportamiento ante contrato vacío, rechazo, error HTTP y timeout;
- ausencia de autenticación servicio-a-servicio como deuda conocida;
- `modelCalled=false` permanente en esta tarea.

La documentación debe dejar claro:

> El endpoint Java está abierto únicamente para fines de laboratorio. No debe considerarse una configuración apta para producción. La autenticación servicio-a-servicio será implementada en la Task 075.

## TESTS

Crear pruebas automatizadas para cubrir como mínimo:

1. Contrato válido con `outcome` exitoso.
2. Contrato válido pero vacío.
3. Contrato con `outcome` no exitoso.
4. Respuesta HTTP 4xx.
5. Respuesta HTTP 5xx.
6. JSON inválido.
7. Contrato con campos estructurales obligatorios ausentes.
8. Timeout.
9. Error de conexión.
10. Confirmación de que `modelCalled` siempre es `false`.
11. Confirmación de que no se realiza ninguna llamada a un LLM.
12. Confirmación de que no se realiza acceso directo a Epic, Oracle, HAPI FHIR ni SMART.

Las pruebas deben usar mocks o servidores HTTP de prueba. No depender de sistemas clínicos reales.

## FUERA DE ALCANCE

No implementar en esta tarea:

- LLM;
- OpenAI;
- Azure OpenAI;
- Azure AI Foundry;
- LangGraph;
- RAG;
- MCP;
- Kafka;
- agentes autónomos;
- memoria conversacional;
- prompts clínicos;
- generación de resúmenes;
- acceso directo a Epic;
- acceso directo a Oracle;
- acceso directo a HAPI FHIR;
- SMART on FHIR;
- OAuth nuevo;
- autenticación servicio-a-servicio;
- autorización real;
- endpoints clínicos nuevos en Java;
- CRUD de pacientes;
- `GET /api/patients/{id}`;
- cinco herramientas clínicas;
- modificación del `ModelBoundaryContract v1`;
- creación de un segundo contrato;
- creación de un segundo stub Java;
- ampliación de la allowlist de la Task 042;
- desactivación de `requiresHumanReview`;
- transformación de un Bundle FHIR directamente para el modelo;
- incorporación de campos `usable`, `requiresHumanReview` o `modelCallAuthorized` al contrato Java.

## CRITERIOS DE ACEPTACIÓN

La Task 074 se considera terminada cuando:

- existe `services/ai-service`;
- el servicio utiliza FastAPI;
- el servicio puede iniciarse localmente;
- el servicio consume `GET /api/model-boundary/v1`;
- consume el contrato v1 sin envolverlo ni modificarlo;
- valida HTTP, JSON, estructura mínima y `outcome`;
- distingue respuestas exitosas, vacías, rechazadas, errores HTTP, timeout y errores de conexión;
- devuelve únicamente los estados `received` o `rejected`;
- `modelCalled` es siempre `false`;
- no existe ninguna dependencia de LLM;
- no existe acceso directo a Epic, Oracle, HAPI FHIR ni SMART;
- existen pruebas automatizadas;
- los logs no exponen información clínica ni identificadores sensibles;
- la deuda de autenticación servicio-a-servicio está documentada;
- la documentación explica claramente el alcance y las limitaciones del laboratorio.

## STOP EXPLÍCITO

Detener la implementación al cumplir los criterios anteriores.

No continuar con:

- autenticación servicio-a-servicio;
- autorización real;
- integración con un LLM;
- generación de resúmenes;
- creación de herramientas clínicas;
- RAG;
- MCP;
- nuevos conectores;
- cambios en el contrato Java.

La autenticación servicio-a-servicio corresponde a la Task 075.

La incorporación del LLM corresponde a la Task 076.

## CONCEPT

La Task 074 no construye todavía un agente inteligente. Construye el primer consumidor externo y verificable del contexto clínico controlado.

El objetivo es demostrar esta separación:

```text
Producto A:
conectividad, FHIR, fuentes clínicas, políticas y Model Boundary

Producto B:
consumo del contrato y futura orquestación del agente
```

En esta fase, el servicio Python debe ser deliberadamente hueco y seguro: recibe el contrato, valida su estado, no llama a ningún modelo y no busca datos por fuera del límite definido por Java.
