# Task 015 — FHIR Server Configuration & Client Profiles

## Objetivo

Evolucionar `fhir-integration-service` desde un cliente FHIR configurado contra un único servidor local hacia un cliente capaz de trabajar con diferentes FHIR Servers mediante configuración externa.

Esta tarea inicia la Fase 2 del proyecto.

La Fase 1 estuvo orientada principalmente al aprendizaje y dominio de FHIR R4.

La Fase 2 comienza a transformar ese conocimiento en una capa de interoperabilidad reutilizable que pueda evolucionar hacia:

- componente de consultoría;
- acelerador de proyectos de interoperabilidad;
- plataforma de integración;
- potencial producto SaaS.

---

## 1. Contexto actual

Actualmente el servicio utiliza una configuración similar a:

```yaml
fhir:
  server:
    base-url: http://localhost:8080/fhir
```

El `FhirService` utiliza el `IGenericClient` configurado contra ese servidor.

Arquitectura actual:

```text
fhir-integration-service
        |
        v
   FHIR Client
        |
        v
http://localhost:8080/fhir
        |
        v
    HAPI FHIR
```

Esto funciona para el laboratorio, pero no es suficiente para una capa de interoperabilidad reutilizable.

---

## 2. Objetivo arquitectónico

Evolucionar hacia:

```text
                FHIR Integration Service
                         |
                  Client Configuration
                         |
             +-----------+-----------+
             |           |           |
             v           v           v
          HAPI Lab    Server A    Server B
             |           |           |
           local       externo     externo
```

El código de negocio no debe depender de una URL fija.

La URL del FHIR Server debe ser una propiedad de configuración.

---

## 3. Alcance

La tarea debe implementar:

1. Configuración externa del FHIR Server.
2. Validación de la configuración.
3. Creación de `FhirContext` reutilizable.
4. Creación de `IGenericClient` a partir de configuración.
5. Separación entre configuración y lógica de negocio.
6. Soporte para diferentes perfiles/configuraciones de FHIR Server.
7. Mantener HAPI local como servidor de laboratorio.
8. Verificación mediante HTTP y tests.
9. Documentación del diseño.

---

## 4. No hacer todavía

Esta tarea NO debe implementar:

- OAuth 2.0.
- SMART on FHIR.
- JWT.
- Client Credentials.
- certificados.
- secretos.
- API Gateway.
- multi-tenancy de producción.
- persistencia de configuraciones.
- UI administrativa.
- `@RestController`.
- DTOs de negocio.

Esas capacidades serán abordadas posteriormente.

La prioridad es construir correctamente la **configuración de conectividad**.

---

## 5. Concepto principal

Separar:

```text
FHIR Server Configuration
        |
        v
FHIR Client
        |
        v
FHIR Service
        |
        v
FHIR operations
```

La configuración no debe estar mezclada con las operaciones FHIR.

Por ejemplo, `FhirService` no debería contener:

```java
String baseUrl = "http://localhost:8080/fhir";
```

La URL debe venir de configuración.

---

## 6. Configuración propuesta

Evaluar y documentar una estructura similar a:

```yaml
fhir:
  servers:
    local-hapi:
      base-url: http://localhost:8080/fhir
      fhir-version: R4
      enabled: true
```

El nombre exacto de la estructura puede modificarse si la implementación encuentra una alternativa mejor.

La configuración debe permitir agregar posteriormente:

```yaml
fhir:
  servers:
    local-hapi:
      base-url: http://localhost:8080/fhir
      fhir-version: R4
      enabled: true

    external-server:
      base-url: https://example.org/fhir
      fhir-version: R4
      enabled: false
```

No se deben agregar URLs reales de proveedores comerciales.

---

## 7. Client Profile

Introducir el concepto de:

```text
FHIR Server Profile
```

Un profile representa la configuración necesaria para conectarse a un FHIR Server.

Como mínimo:

```text
Profile
 |
 +-- name
 +-- baseUrl
 +-- fhirVersion
 +-- enabled
```

No incluir todavía:

```text
clientId
clientSecret
tokenUrl
authorizationUrl
```

porque pertenecen a las siguientes tareas de seguridad.

---

## 8. FHIR Version

La versión debe formar parte explícita de la configuración.

Ejemplo:

```yaml
fhir-version: R4
```

El objetivo es evitar que la versión FHIR quede implícita en el código.

Actualmente utilizamos:

```java
FhirContext.forR4()
```

La implementación debe analizar cómo convertir la configuración de versión en el `FhirContext` correspondiente.

En esta tarea solamente debe soportarse R4.

No implementar R5 todavía.

Si se considera útil diseñarlo extensible para futuras versiones, hacerlo sin agregar complejidad innecesaria.

---

## 9. FhirContext

Mantener el principio aprendido en Fase 1:

`FhirContext` es un objeto costoso y thread-safe.

Debe existir como bean reutilizable y no crearse en cada operación.

Incorrecto:

```java
public Patient readPatient(...) {
    FhirContext context = FhirContext.forR4();
    ...
}
```

Correcto conceptualmente:

```text
Spring Application
       |
       v
 FhirContext bean
       |
       v
IGenericClient
       |
       v
FhirService
```

---

## 10. IGenericClient

El cliente debe construirse a partir del profile seleccionado.

Conceptualmente:

```java
fhirContext.newRestfulGenericClient(baseUrl);
```

La URL debe provenir de la configuración.

No debe existir una URL FHIR hardcodeada dentro de `FhirService`.

---

## 11. Decisión sobre múltiples servidores

La tarea debe analizar dos conceptos:

### Opción A

Un único FHIR Server activo por instancia de la aplicación.

```text
Application
    |
    v
FHIR Server
```

### Opción B

Varios perfiles configurados.

```text
Application
    |
    +---- Profile A ----> FHIR Server A
    |
    +---- Profile B ----> FHIR Server B
```

Para esta tarea se debe implementar la capacidad de definir varios perfiles, pero sin introducir todavía un sistema complejo de routing.

El objetivo es preparar la arquitectura para futuras integraciones.

---

## 12. Selección de Profile

Implementar una forma clara de seleccionar un profile.

Por ejemplo:

```text
local-hapi
```

debe permitir obtener:

```text
baseUrl = http://localhost:8080/fhir
FHIR version = R4
```

La estrategia exacta puede ser:

- configuración de aplicación;
- nombre de profile;
- bean;
- factory;
- registry.

La decisión debe estar documentada en:

```text
docs/fhir/fhir-server-configuration.md
```

No implementar una API REST para seleccionar profiles.

---

## 13. Factory / Registry

Evaluar la introducción de un componente dedicado para construir clientes.

Conceptualmente:

```text
FhirServerProfile
        |
        v
FhirClientFactory
        |
        v
IGenericClient
```

La responsabilidad debe estar separada de `FhirService`.

Por ejemplo:

```text
FhirService
    |
    v
FhirClientFactory
    |
    v
IGenericClient
```

No es obligatorio utilizar exactamente esos nombres si otra estructura resulta más limpia.

---

## 14. CapabilityStatement

Reutilizar el conocimiento adquirido en Fase 1.

Para el profile `local-hapi`:

```http
GET /metadata
```

debe continuar funcionando.

La aplicación debe poder demostrar que el cliente creado desde configuración puede consultar:

```text
CapabilityStatement
```

y verificar:

```text
FHIR version = 4.0.1
```

No asumir que todos los servidores soportan exactamente las mismas operaciones.

---

## 15. HTTP primero

Antes de implementar Java, comprobar mediante HTTP:

```http
GET http://localhost:8080/fhir/metadata
```

Verificar:

- HTTP 200.
- `CapabilityStatement`.
- FHIR R4.
- URL base correcta.

Documentar qué parte corresponde al servidor y qué parte corresponde al cliente.

---

## 16. Java / HAPI después

Después de verificar HTTP, implementar el cliente.

El flujo esperado:

```text
application.yml
      |
      v
FhirServerProfile
      |
      v
FhirClientFactory
      |
      v
FhirContext
      |
      v
IGenericClient
      |
      v
FhirService
      |
      v
GET /metadata
```

No crear un nuevo `FhirContext` por request.

---

## 17. Tests unitarios

Agregar tests que verifiquen:

### Configuración

- profile existente.
- `baseUrl` correctamente cargada.
- versión R4 correctamente cargada.
- profile habilitado.
- configuración inválida rechazada.

### Factory

- crea cliente con la URL configurada.
- utiliza R4.
- no contiene URL hardcodeada.

### FhirService

Los tests existentes deben continuar funcionando.

No romper:

- Patient read.
- Patient search.
- Observation.
- Condition.
- `$everything`.
- pagination.
- history.
- validation.

---

## 18. Tests de integración

Mantener HAPI Docker como servidor real.

Verificar:

```text
local-hapi
    |
    v
http://localhost:8080/fhir
    |
    v
GET /metadata
```

Y posteriormente una operación existente, por ejemplo:

```text
GET /Patient/patient-001
```

El objetivo es demostrar que la operación funciona utilizando el profile configurado.

---

## 19. Configuración por ambiente

Preparar la estructura para:

```text
application.yml
application-local.yml
application-test.yml
application-staging.yml
```

No es necesario implementar todos los ambientes todavía.

Debe quedar claro que:

```text
local
staging
production
```

pueden utilizar diferentes URLs sin cambiar código Java.

---

## 20. Secrets

No agregar secretos.

No utilizar:

```yaml
client-secret:
password:
token:
```

todavía.

La siguiente fase de seguridad será responsable de introducir mecanismos apropiados para credenciales y tokens.

---

## 21. Documentación

Crear:

```text
docs/fhir/fhir-server-configuration.md
```

Debe explicar:

- qué es un FHIR Server profile;
- diferencia entre servidor y cliente;
- por qué la URL no debe estar hardcodeada;
- FhirContext;
- IGenericClient;
- configuración externa;
- múltiples profiles;
- FHIR version;
- CapabilityStatement;
- diferencias entre configuración y autenticación;
- qué queda fuera de esta tarea.

Actualizar:

```text
docs/fhir/README.md
docs/roadmap.md
```

---

## 22. Regla de implementación

La implementación debe seguir este orden:

```text
1. Inspeccionar repository
        ↓
2. Inspeccionar código actual
        ↓
3. Verificar API HAPI necesaria
        ↓
4. Verificar comportamiento HTTP
        ↓
5. Diseñar configuración
        ↓
6. Implementar
        ↓
7. Unit tests
        ↓
8. Integration tests
        ↓
9. Documentación
        ↓
10. Verificación final
```

---

## 23. Instrucción especial para Cursor

Durante toda la ejecución de esta tarea, Cursor debe comportarse como un profesor.

NO debe limitarse a entregar un resumen final.

Después de cada paso debe mostrar:

### Qué hizo

Ejemplo:

```text
Creé FhirServerProfile.java.
```

### Por qué lo hizo

Ejemplo:

```text
La configuración estaba mezclada con el cliente.
Separar el profile permite cambiar el servidor sin modificar FhirService.
```

### Qué archivo modificó

Ejemplo:

```text
services/fhir-integration-service/src/main/...
```

### Qué comando ejecutó

Ejemplo:

```bash
mvn test
```

### Qué resultado obtuvo

Ejemplo:

```text
BUILD SUCCESS
```

### Qué concepto FHIR/Java/Spring estamos aprendiendo

Ejemplo:

```text
Spring external configuration
FHIR Server vs FHIR Client
FhirContext vs IGenericClient
```

Debe mostrar estos pasos progresivamente y no realizar toda la tarea silenciosamente para después entregar solamente un resumen.

Si encuentra un problema:

1. explicar el problema;
2. explicar la causa;
3. mostrar la solución;
4. ejecutar nuevamente la verificación;
5. mostrar el resultado.

No ocultar problemas ni simplificarlos.

---

## 24. Criterios de aceptación

La tarea estará terminada cuando:

- [ ] La URL FHIR no esté hardcodeada en `FhirService`.
- [ ] Exista configuración externa para el FHIR Server.
- [ ] Exista al menos un profile `local-hapi`.
- [ ] El profile utilice FHIR R4.
- [ ] `FhirContext` sea reutilizable.
- [ ] `IGenericClient` sea construido desde configuración.
- [ ] Se pueda agregar un segundo profile sin modificar `FhirService`.
- [ ] HAPI local continúe funcionando.
- [ ] `GET /metadata` funcione.
- [ ] Patient read continúe funcionando.
- [ ] Los tests existentes continúen pasando.
- [ ] Existan unit tests para configuración/factory.
- [ ] Exista integration test contra HAPI.
- [ ] No se agregue OAuth todavía.
- [ ] No se agreguen secretos.
- [ ] No se agregue `@RestController`.
- [ ] No se agreguen DTOs.
- [ ] La documentación esté actualizada.
- [ ] El comportamiento esté verificado antes del commit.

---

## 25. Dependencias

No agregar dependencias nuevas salvo que sean estrictamente necesarias.

Reutilizar:

```text
Spring Boot
HAPI FHIR R4
hapi-fhir-client
```

---

## 26. Git

Branch:

```bash
git checkout -b feature/fhir-server-configuration
```

No trabajar directamente sobre `main`.

No realizar commit automáticamente.

Al terminar:

```bash
git status
git diff --stat
git diff
```

Debe mostrarse claramente qué cambió antes del commit.

---

## 27. Resultado esperado

Al finalizar la tarea tendremos:

```text
                Spring Boot
                    |
                    v
          FHIR Server Profiles
                    |
          +---------+---------+
          |                   |
          v                   v
      local-hapi          external-x
          |                   |
          v                   v
       HAPI FHIR          futuro FHIR
          |
          v
    FhirClientFactory
          |
          v
      IGenericClient
          |
          v
      FhirService
```

La aplicación todavía utilizará HAPI local, pero el código ya no estará conceptualmente acoplado a:

```text
http://localhost:8080/fhir
```

Ese desacoplamiento será la base para las siguientes tareas de la Fase 2.

---

## 28. Próximo paso

Después de completar esta tarea:

```text
Task 015
FHIR Server Configuration
        ↓
Task 016
Authentication / OAuth 2.0
        ↓
Task 017
SMART on FHIR
```

No implementar las siguientes tareas como parte de Task 015.
