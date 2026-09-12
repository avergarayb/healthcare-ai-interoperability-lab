# Task 052 — Consolidar Clinical Snapshot para Epic Sandbox

## Estado

**PLANNED**

## Objetivo

Consolidar los resultados clínicos obtenidos desde Epic Sandbox en un `ClinicalSnapshot` genérico, reutilizando las abstracciones existentes del laboratorio y manteniendo la separación estricta entre:

```text
Vendor-specific adapter
        ↓
RoutingService
        ↓
FhirService
        ↓
ClinicalSnapshot
        ↓
Controlled Projection
        ↓
Model Boundary Contract v1
```

La tarea debe permitir que Epic utilice el mismo flujo de snapshot que Oracle Health, sin introducir lógica específica de Epic en componentes genéricos.

## Alcance

Implementar la obtención de un snapshot clínico controlado para el perfil `epic-sandbox`.

El snapshot debe consolidar, como mínimo:

- `Patient`
- `Condition`
- `Observation`
- `DiagnosticReport`

Reutilizar las búsquedas validadas en las Tasks 048–051:

- Patient read por contexto configurado.
- Condition search por Patient.
- Observation search por Patient y categoría `vital-signs`.
- DiagnosticReport search por Patient.

No agregar todavía:

- `MedicationRequest`.
- Nuevos recursos FHIR.
- Proyección adicional.
- Integración con un LLM.
- Integración con un agente real.
- Persistencia.
- Cache.
- Procesamiento clínico o interpretación médica.

## Motivación

Las búsquedas individuales de Epic ya funcionan de forma autenticada. El siguiente paso es demostrar que esos resultados pueden integrarse en un snapshot clínico común, independiente del proveedor.

Esto valida que el laboratorio no depende de contratos específicos de Epic y que el futuro flujo de IA podrá recibir una estructura controlada sin conocer:

- El proveedor FHIR.
- La URL del servidor.
- El mecanismo SMART utilizado.
- Los detalles de HAPI FHIR.
- Los identificadores internos del paciente.
- El JSON FHIR crudo.

## Requisitos funcionales

### 1. Reutilizar las abstracciones existentes

Reutilizar las abstracciones genéricas actuales, especialmente:

- `FhirService`
- `RoutingService`
- El modelo o servicio de `ClinicalSnapshot` ya existente.
- Los contratos actuales de autenticación y capacidades.

No crear:

- `EpicPatientClient`
- `EpicConditionClient`
- `EpicObservationClient`
- `EpicDiagnosticReportClient`
- Clientes específicos por recurso.

No crear un servicio específico de Epic si el flujo genérico existente puede parametrizarse mediante el destino lógico.

### 2. Resolver el contexto del paciente

Utilizar el mecanismo de contexto ya implementado para Epic:

- Fuente: contexto configurado.
- Patient ID únicamente desde configuración local.
- Nunca incluir el Patient ID en logs, documentación, tests o respuestas visibles.
- No realizar búsqueda alternativa de Patient.
- No modificar el flujo SMART existente.

### 3. Ejecutar las búsquedas clínicas

#### Patient

- Read controlado por Patient ID configurado.
- Validar previamente la capacidad `Patient READ`.

#### Condition

- Search por Patient.
- Reutilizar la consulta genérica existente.
- Mantener el filtro actual de `problem-list-item`, si forma parte de la implementación validada.

#### Observation

- Search por Patient.
- Mantener la categoría `vital-signs`, requerida por Epic para la búsqueda validada.
- Mantener `_count=5` como cantidad solicitada, no como límite clínico ni garantía de exhaustividad.

#### DiagnosticReport

- Search por Patient.
- Reutilizar la consulta genérica existente:
  - `patient`
  - `_count=5`
- No agregar filtros específicos de Epic sin evidencia técnica.

### 4. Construir el ClinicalSnapshot

El snapshot debe contener únicamente la información necesaria para representar que los recursos fueron obtenidos y están disponibles para el siguiente paso del pipeline.

Debe conservar una estructura genérica y no depender de clases específicas de Epic.

Como mínimo, evaluar si el modelo existente permite representar:

- Identificación técnica del destino lógico, sin incluir secretos.
- Estado de la operación.
- Presencia o ausencia de cada grupo de recursos.
- Colecciones de recursos FHIR obtenidos, si ese es el contrato interno actual.
- Metadatos técnicos estrictamente necesarios.

No agregar al snapshot:

- Access tokens.
- Refresh tokens.
- Client ID.
- Patient ID en respuestas públicas o logs.
- Nombres.
- Fecha de nacimiento.
- Identificadores personales.
- Texto narrativo.
- Diagnósticos legibles.
- Valores clínicos.
- Dosis.
- Texto de informes.
- JSON crudo expuesto al modelo.

Si el `ClinicalSnapshot` actual transporta recursos FHIR completos internamente, estos deben permanecer dentro de la frontera interna y no enviarse directamente al modelo ni al agente.

### 5. Manejo de errores

Definir un comportamiento consistente cuando una búsqueda falla:

- No ocultar silenciosamente el error.
- No inventar resultados.
- No convertir un error de autenticación en un snapshot exitoso.
- No ejecutar búsquedas alternativas no autorizadas.
- Mantener el estado de cada componente del snapshot, si el modelo actual lo permite.
- Evitar que un fallo parcial produzca una afirmación de completitud clínica.

El comportamiento exacto debe alinearse con los contratos existentes. Si no está definido, documentar la decisión antes de implementarla.

### 6. Endpoint o punto de entrada

Reutilizar el patrón de endpoint existente para el snapshot de Oracle, si existe.

Si se requiere un endpoint específico para validar Epic, debe:

- Mantener una forma genérica y coherente.
- No exponer tokens ni Patient ID.
- No devolver JSON FHIR crudo como contrato público.
- No introducir una API pública específica de negocio para Epic.

Antes de crear un endpoint nuevo, revisar si el flujo actual puede parametrizarse mediante el destino lógico `epic-sandbox`.

No utilizar:

```java
RoutingService.discoverCapabilities("epic-sandbox")
```

La capacidad de Epic ya fue validada en la Task 047 y no debe redescubrirse innecesariamente dentro de esta tarea.

## Requisitos no funcionales

### Arquitectura

- Mantener la separación vendor-specific / genérico.
- No introducir `if (Epic)` ni `if (Oracle)` en `FhirService`.
- No introducir hosts hardcodeados en código vendor-specific.
- No modificar el timeout genérico actual.
- No agregar cache.
- No ampliar allowlists.
- No cambiar el mecanismo SMART existente.
- No modificar el flujo de Oracle que ya funciona.

### Seguridad

Nunca incluir en código, logs, documentación, tests o respuestas:

- Access token.
- Refresh token.
- Client ID.
- Client secret.
- Patient ID real.
- Identificadores de pacientes.
- Datos clínicos reales.
- URLs privadas con parámetros sensibles.

Los valores de configuración deben permanecer en `.env`, sin commit.

### Datos clínicos

El snapshot es una estructura técnica de integración, no un diagnóstico ni una recomendación médica.

No realizar:

- Inferencia clínica.
- Clasificación de riesgo.
- Resumen médico.
- Priorización clínica.
- Generación de recomendaciones.
- Interpretación de resultados.

## Plan de implementación recomendado

### Paso 1 — Revisar el flujo Oracle existente

Identificar:

- Servicio que construye el snapshot.
- Modelo `ClinicalSnapshot`.
- DTOs relacionados.
- Endpoint de validación.
- Manejo de errores.
- Límites actuales.
- Dependencias entre `RoutingService` y `FhirService`.

No modificar código todavía.

### Paso 2 — Comparar con el flujo Epic

Verificar que Epic pueda utilizar:

- El mismo modelo.
- Las mismas abstracciones.
- Los mismos métodos genéricos.
- El mismo contrato de salida.

Registrar cualquier diferencia real de Epic únicamente en el adapter o frontera vendor-specific correspondiente.

### Paso 3 — Implementar la consolidación

Construir el snapshot a partir de los resultados existentes:

1. Patient read.
2. Condition search.
3. Observation search.
4. DiagnosticReport search.

Evitar repetir autenticación o crear llamadas HTTP paralelas fuera de las abstracciones existentes.

### Paso 4 — Validar el contrato

Comprobar que el resultado:

- Es genérico.
- No expone datos sensibles.
- No expone JSON FHIR crudo públicamente.
- No contiene tokens.
- No depende de clases específicas de Epic.
- Puede ser consumido por el siguiente paso de proyección controlada.

### Paso 5 — Validación live

Realizar una validación contra Epic Sandbox usando la configuración local existente.

La evidencia visible debe limitarse a:

- Estado general del snapshot.
- Estado de cada grupo de recursos.
- HTTP status, si corresponde.
- Presencia de resultados, sin mostrar contenido clínico.
- Ausencia de secretos e identificadores.

No mostrar:

- Patient ID.
- Tokens.
- JSON FHIR.
- Nombres.
- Diagnósticos.
- Valores de Observation.
- Texto de DiagnosticReport.

## Criterios de aceptación

La Task 052 se considera completada únicamente si:

- [ ] Epic Sandbox puede construir un `ClinicalSnapshot` utilizando el flujo genérico.
- [ ] Se reutiliza el Patient read ya validado.
- [ ] Se reutiliza Condition search ya validado.
- [ ] Se reutiliza Observation search con `vital-signs`.
- [ ] Se reutiliza DiagnosticReport search ya validado.
- [ ] No se crean clientes específicos por recurso.
- [ ] No se agregan condiciones `if Epic` o `if Oracle` en componentes genéricos.
- [ ] No se modifica innecesariamente el flujo de Oracle.
- [ ] No se realiza un nuevo discovery de capacidades dentro del snapshot.
- [ ] No se agregan tokens, Patient ID ni datos clínicos a logs o documentación.
- [ ] El resultado no expone JSON FHIR crudo como contrato público.
- [ ] El snapshot puede continuar hacia la proyección controlada existente.
- [ ] La validación live en Epic Sandbox es exitosa.
- [ ] La documentación de progreso queda actualizada.
- [ ] La implementación pasa las validaciones y tests aplicables.

## Evidencia requerida para el cierre

Registrar únicamente evidencia segura, ajustando los nombres de campos a la implementación real:

```text
destination=epic-sandbox
clinicalSnapshot=SUCCEEDED
patientRead=SUCCEEDED
conditionSearch=SUCCEEDED
observationSearch=SUCCEEDED
diagnosticReportSearch=SUCCEEDED
hasClinicalData=true
```

No inventar campos si el endpoint actual utiliza otros nombres.

No registrar:

- Patient ID.
- Tokens.
- Client ID.
- Datos clínicos.
- JSON FHIR completo.
- URLs privadas.

## Entregables

1. Implementación del snapshot clínico genérico para Epic Sandbox.
2. Reutilización documentada de las búsquedas de las Tasks 048–051.
3. Tests unitarios o de integración apropiados, sin secretos ni datos reales.
4. Evidencia live segura.
5. Actualización de `docs/progress/progress-log.md`.
6. Actualización mínima de documentación relacionada, únicamente si es necesario.

## Restricciones de trabajo

Antes de implementar:

- Revisar el código actual.
- Identificar el flujo Oracle existente.
- Identificar el modelo real de `ClinicalSnapshot`.
- Confirmar qué partes ya están implementadas.
- No asumir nombres de clases, endpoints o métodos que no existan.

Durante la implementación:

- No tocar `.env`.
- No crear una rama nueva sin autorización.
- No hacer commit.
- No hacer push.
- No abrir un PR.
- No modificar tareas anteriores.
- No ampliar el alcance.

Al finalizar, reportar:

1. Archivos modificados.
2. Flujo implementado.
3. Reutilización de abstracciones.
4. Tests o validaciones ejecutadas.
5. Evidencia live segura.
6. Riesgos o decisiones pendientes.
7. Confirmación explícita de que no se tocaron `.env`, secretos ni datos clínicos reales.
