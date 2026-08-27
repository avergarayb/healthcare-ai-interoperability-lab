# Task 016 — FHIR Authentication / OAuth 2.0

## Objetivo

Evolucionar `fhir-integration-service` para soportar autenticación basada en OAuth 2.0 al consumir un FHIR Server protegido.

Esta tarea representa el siguiente paso de la Fase 2:

```text
Task 015
FHIR Server Configuration
        |
        v
Task 016
OAuth 2.0 Authentication
        |
        v
Task 017
SMART on FHIR
```

En Task 015 desacoplamos el cliente de una URL FHIR fija.

Ahora debemos resolver una segunda pregunta fundamental de una integración real:

```text
¿Quién soy y cómo demuestro al FHIR Server que estoy autorizado?
```

---

# 1. Contexto

Actualmente:

```text
FhirClientFactory
       |
       v
IGenericClient
       |
       v
FHIR Server
```

El cliente puede seleccionar:

```text
local-hapi
```

pero actualmente no existe autenticación.

Para un servidor FHIR público de laboratorio esto puede ser suficiente.

Para un FHIR Server empresarial normalmente se necesita autenticación.

El objetivo de esta tarea es aprender e implementar el patrón OAuth 2.0 de forma controlada, utilizando un servidor de autorización local/sintético para no depender de credenciales reales.

---

# 2. Objetivo arquitectónico

Evolucionar hacia:

```text
                    FHIR Integration Service
                              |
                       FHIR Client Factory
                              |
                       Authentication Layer
                              |
                         Access Token
                              |
                              v
                       FHIR HTTP Request
                              |
                              v
                         FHIR Server
```

La autenticación debe quedar separada de `FhirService`.

Conceptualmente:

```text
FhirService
     |
     v
IGenericClient
     |
     v
Authorization Interceptor
     |
     v
Bearer Access Token
     |
     v
FHIR Server
```

---

# 3. Alcance

Implementar:

1. Conceptos básicos de OAuth 2.0.
2. Authorization Server local/sintético.
3. Access Token.
4. Bearer token.
5. Configuración de autenticación por FHIR Server profile.
6. Obtención del token.
7. Inyección del token en requests FHIR.
8. Renovación/refresh según el flujo seleccionado.
9. Separación entre FHIR connectivity y authentication.
10. Tests unitarios.
11. Tests de integración.
12. Documentación.

---

# 4. No hacer todavía

Esta tarea NO debe implementar:

- SMART on FHIR completo.
- OpenID Connect.
- login interactivo de usuario.
- UI de login.
- autorización clínica.
- scopes SMART específicos.
- PKCE para aplicaciones públicas.
- refresh token si el flujo seleccionado no lo necesita.
- persistencia de credenciales.
- multi-tenancy de producción.
- API REST administrativa.
- secretos reales de clientes.
- integración con Epic, Cerner u otro proveedor real.

SMART on FHIR será una tarea posterior.

---

# 5. Concepto fundamental

Diferenciar:

```text
FHIR
  =
modelo y API de interoperabilidad

OAuth 2.0
  =
framework de autorización

Access Token
  =
credencial temporal utilizada para acceder al recurso protegido
```

FHIR y OAuth no son lo mismo.

Un FHIR Server puede existir sin OAuth.

OAuth puede proteger una API que no sea FHIR.

En una integración real pueden coexistir:

```text
FHIR API
   +
OAuth 2.0
```

---

# 6. Roles OAuth 2.0

Documentar los conceptos:

```text
Resource Owner
      |
      v
Client
      |
      v
Authorization Server
      |
      v
Access Token
      |
      v
Resource Server
```

En el contexto de esta tarea:

```text
FHIR Integration Service
        =
OAuth Client
```

```text
Authorization Server
        =
servidor que emite tokens
```

```text
FHIR Server
        =
Resource Server
```

---

# 7. Flujo seleccionado

Para el laboratorio se debe seleccionar explícitamente un flujo OAuth 2.0 adecuado para comunicación server-to-server.

La implementación debe evaluar:

```text
Client Credentials Grant
```

como primera opción para esta tarea.

Motivo:

```text
FHIR Integration Service
        |
        | client_id + client_secret
        v
Authorization Server
        |
        | access_token
        v
FHIR Server
```

No requiere interacción humana.

Esto representa mejor un backend de integración que consume otro sistema.

---

# 8. HTTP primero

Antes de implementar Java, documentar el flujo HTTP.

Conceptualmente:

```http
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id=...
&client_secret=...
```

Resultado conceptual:

```json
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

No utilizar credenciales reales.

Los valores deben ser sintéticos.

---

# 9. Bearer Token

Una vez obtenido el token, el cliente FHIR debe enviar:

```http
Authorization: Bearer <access_token>
```

Por ejemplo:

```http
GET /fhir/Patient/patient-001
Authorization: Bearer <access_token>
```

El FHIR Server protegido debe aceptar el token.

Sin token:

```text
401 Unauthorized
```

Con token válido:

```text
200 OK
```

---

# 10. Servidor protegido

Para que la prueba sea reproducible, utilizar un servidor local/sintético.

Arquitectura:

```text
                Docker Compose
                     |
          +----------+----------+
          |                     |
          v                     v
 Authorization Server      HAPI FHIR
          |                     |
          | token               | protected resource
          +----------+----------+
                     |
                     v
             Integration Service
```

La tecnología exacta del Authorization Server debe evaluarse antes de agregar dependencias.

No asumir una implementación sin comprobar primero las opciones disponibles.

---

# 11. FHIR Server y Authorization Server

Son componentes diferentes.

```text
Authorization Server
        |
        | emite token
        v
Access Token
        |
        v
FHIR Server
        |
        | valida token
        v
Patient / Observation / Condition
```

El Authorization Server no contiene necesariamente los recursos FHIR.

El FHIR Server no necesariamente emite los tokens.

---

# 12. Configuración

Extender los FHIR Server profiles de Task 015.

Conceptualmente:

```yaml
fhir:
  active-server: local-hapi

  servers:
    local-hapi:
      base-url: http://localhost:8080/fhir
      fhir-version: R4
      enabled: true

      authentication:
        type: NONE
```

Y para un servidor protegido:

```yaml
fhir:
  servers:
    secured-lab:
      base-url: http://localhost:8081/fhir
      fhir-version: R4
      enabled: false

      authentication:
        type: OAUTH2_CLIENT_CREDENTIALS
        token-url: http://localhost:9090/oauth/token
        client-id: lab-client
```

El `client-secret` NO debe almacenarse directamente en un archivo versionado.

---

# 13. Secrets

No subir secretos al repository.

Nunca hacer:

```yaml
client-secret: my-real-secret
```

en un archivo versionado.

Para el laboratorio puede utilizarse:

```text
environment variable
```

por ejemplo:

```text
FHIR_SECURED_LAB_CLIENT_SECRET
```

La documentación debe explicar que en producción se utilizaría un secret manager apropiado.

---

# 14. Authentication Configuration

Crear una abstracción clara.

Conceptualmente:

```text
FhirServerProfile
        |
        +-- baseUrl
        +-- fhirVersion
        +-- enabled
        |
        +-- authentication
                |
                +-- type
                +-- tokenUrl
                +-- clientId
                +-- secret reference
```

No mezclar la autenticación directamente dentro de `FhirService`.

---

# 15. Token Client

Introducir un componente dedicado.

Conceptualmente:

```text
OAuth2TokenClient
        |
        v
Authorization Server
        |
        v
Access Token
```

Responsabilidades:

- solicitar token;
- interpretar respuesta;
- controlar expiración;
- renovar token cuando corresponda;
- no exponer secretos innecesariamente.

El nombre exacto de la clase puede variar.

---

# 16. Token Provider

Evaluar separar:

```text
Token Client
```

de:

```text
Token Provider
```

Por ejemplo:

```text
OAuth2TokenClient
        |
        v
AccessTokenProvider
        |
        v
Authorization Interceptor
        |
        v
IGenericClient
```

La razón es que una solicitud FHIR no debería solicitar un token nuevo innecesariamente.

---

# 17. Token caching

El token debe reutilizarse mientras sea válido.

Incorrecto:

```text
FHIR request
    |
    v
request token
    |
    v
FHIR request
```

en cada operación.

Mejor:

```text
FHIR request 1
      |
      v
token válido
      |
      v
FHIR Server

FHIR request 2
      |
      v
mismo token
      |
      v
FHIR Server
```

Cuando expire:

```text
nuevo token
```

La implementación debe tener en cuenta `expires_in`.

No es necesario implementar una solución distribuida de cache en esta tarea.

---

# 18. HAPI interceptor

Investigar la API de HAPI FHIR para agregar headers automáticamente.

Conceptualmente:

```text
IGenericClient
      |
      v
Interceptor
      |
      v
Authorization: Bearer ...
```

El interceptor debe agregar el header solamente cuando el profile requiere OAuth.

Para:

```text
authentication.type = NONE
```

no debe agregarse Authorization.

---

# 19. Compatibilidad con Task 015

Task 015 ya permite:

```text
local-hapi
```

La nueva arquitectura debe conservar compatibilidad.

Por ejemplo:

```text
local-hapi
    authentication = NONE
```

debe continuar funcionando sin token.

Esto es importante:

```text
Authentication
      =
capacidad configurable
```

y no:

```text
Authentication
      =
requisito obligatorio para todo FHIR Server
```

---

# 20. HTTP verification

Probar explícitamente:

### Sin token

```http
GET /Patient/patient-001
```

Resultado esperado:

```text
401 Unauthorized
```

### Con token inválido

```http
Authorization: Bearer invalid-token
```

Resultado esperado:

```text
401 Unauthorized
```

### Con token válido

```http
Authorization: Bearer <valid-token>
```

Resultado esperado:

```text
200 OK
```

El comportamiento exacto del servidor debe documentarse según lo observado.

No asumir códigos HTTP sin verificar.

---

# 21. Java verification

Demostrar que:

```text
FhirService
```

continúa realizando operaciones como:

```java
readPatient("patient-001")
```

sin conocer:

- client secret;
- token URL;
- OAuth flow;
- token cache.

El servicio solamente utiliza:

```java
IGenericClient
```

La autenticación pertenece a la infraestructura del cliente.

---

# 22. Error handling

Definir comportamiento para:

```text
401 Unauthorized
```

```text
400 invalid_request
```

```text
400 invalid_client
```

```text
invalid_grant
```

si aplica al flujo seleccionado.

También:

```text
token endpoint unavailable
```

y:

```text
token expired
```

No ocultar errores.

El mensaje debe permitir diferenciar:

```text
FHIR request failed
```

de:

```text
OAuth token acquisition failed
```

---

# 23. Tests unitarios

Agregar tests para:

### OAuth Token Client

- token válido.
- respuesta sin access token.
- error del Authorization Server.
- token expirado.
- configuración inválida.

### Token Provider

- reutiliza token válido.
- solicita uno nuevo cuando expira.

### Authentication

- agrega `Authorization`.
- no agrega `Authorization` cuando `NONE`.

### FhirService

Los tests existentes deben continuar funcionando.

---

# 24. Integration tests

Crear una prueba end-to-end:

```text
FhirIntegrationService
        |
        v
Authorization Server
        |
        v
Access Token
        |
        v
FHIR Server
        |
        v
Patient/patient-001
```

Verificar:

1. obtención del token;
2. request autenticado;
3. respuesta FHIR válida.

También verificar:

```text
sin token -> rechazado
token inválido -> rechazado
token válido -> permitido
```

---

# 25. No usar sistemas externos

No utilizar todavía:

- Google OAuth;
- Azure AD;
- Okta;
- Auth0;
- Epic identity;
- Cerner identity;
- credenciales de terceros.

Todo debe ser reproducible localmente.

---

# 26. Conceptos de seguridad

Documentar claramente:

```text
Authentication
    =
¿Quién eres?

Authorization
    =
¿Qué puedes hacer?

Access Token
    =
credencial temporal

Client Secret
    =
credencial del cliente OAuth

Bearer Token
    =
token enviado en Authorization header
```

OAuth 2.0 se ocupa principalmente de autorización delegada, aunque comúnmente se utiliza como mecanismo para obtener tokens que permiten identificar/autorizan al cliente frente a una API.

No confundir OAuth con identidad de usuario.

---

# 27. Documentación

Crear:

```text
docs/fhir/fhir-oauth2-authentication.md
```

Debe explicar:

- OAuth 2.0;
- Authorization Server;
- Resource Server;
- OAuth Client;
- Client Credentials;
- Access Token;
- Bearer token;
- token endpoint;
- expiración;
- token caching;
- interceptor HAPI;
- configuración;
- secrets;
- errores;
- diferencia entre OAuth 2.0 y SMART on FHIR.

Actualizar:

```text
docs/fhir/README.md
docs/roadmap.md
```

---

# 28. Regla de implementación

Seguir este orden:

```text
1. Inspeccionar repository
        ↓
2. Revisar Task 015
        ↓
3. Inspeccionar HAPI API
        ↓
4. Investigar mecanismo OAuth local
        ↓
5. Levantar Authorization Server
        ↓
6. Verificar token HTTP
        ↓
7. Proteger FHIR Server
        ↓
8. Verificar HTTP 401/200
        ↓
9. Diseñar authentication layer
        ↓
10. Implementar Java
        ↓
11. Unit tests
        ↓
12. Integration tests
        ↓
13. Documentación
        ↓
14. Verificación final
```

---

# 29. Instrucción especial para Cursor

Durante toda la ejecución de esta tarea, Cursor debe comportarse como un profesor.

Después de cada paso debe explicar:

### Qué hizo

### Por qué lo hizo

### Qué archivo modificó

### Qué comando ejecutó

### Qué resultado obtuvo

### Qué concepto OAuth / FHIR / Java / Spring estamos aprendiendo

No realizar toda la tarea silenciosamente.

Si aparece un problema:

1. explicar el problema;
2. explicar la causa;
3. explicar las alternativas;
4. elegir una solución;
5. implementar;
6. ejecutar nuevamente;
7. mostrar el resultado.

No ocultar problemas ni convertir errores reales en resultados aparentemente exitosos.

---

# 30. Criterios de aceptación

La tarea estará terminada cuando:

- [ ] OAuth 2.0 esté documentado.
- [ ] Client Credentials haya sido evaluado y seleccionado para el laboratorio.
- [ ] Exista Authorization Server local/sintético.
- [ ] Exista un FHIR Server protegido para la prueba.
- [ ] Se pueda obtener un access token.
- [ ] El token tenga expiración.
- [ ] El cliente envíe `Authorization: Bearer`.
- [ ] Token válido permita acceder al FHIR Server.
- [ ] Token inválido sea rechazado.
- [ ] Request sin token sea rechazado.
- [ ] Token válido sea reutilizado mientras no expire.
- [ ] Token nuevo sea obtenido cuando sea necesario.
- [ ] `FhirService` no conozca detalles OAuth.
- [ ] `FhirClientFactory` continúe siendo responsable del cliente.
- [ ] `local-hapi` sin autenticación continúe funcionando.
- [ ] Los secretos no estén versionados.
- [ ] Existan unit tests.
- [ ] Existan integration tests.
- [ ] Todos los tests anteriores continúen pasando.
- [ ] La documentación esté actualizada.
- [ ] No se implemente SMART todavía.

---

# 31. Dependencias

No agregar dependencias nuevas sin justificarlo.

Antes de introducir una librería OAuth:

1. comprobar si Spring Security OAuth Client ya está disponible/transitivamente;
2. comprobar las capacidades actuales de Spring Boot;
3. comprobar si HAPI proporciona mecanismos suficientes para el interceptor;
4. elegir la solución mínima necesaria.

No agregar un framework de identidad completo solamente para resolver el laboratorio.

---

# 32. Git

Branch:

```bash
git checkout -b feature/fhir-oauth2-authentication
```

No trabajar directamente sobre `main`.

No realizar commit automáticamente.

Al terminar:

```bash
git status
git diff --stat
git diff
```

Verificar también:

```bash
git diff --cached
```

antes del commit.

---

# 33. Resultado esperado

Al finalizar:

```text
                    FHIR Integration Service
                              |
                     FhirClientFactory
                              |
                     Authentication Layer
                              |
                     +--------+--------+
                     |                 |
                   NONE             OAuth2
                     |                 |
                     |          Token Provider
                     |                 |
                     |          Access Token
                     |                 |
                     +--------+--------+
                              |
                         IGenericClient
                              |
                              v
                         FHIR Server
```

Para un servidor sin autenticación:

```text
local-hapi
    |
    v
FHIR Server
```

Para un servidor protegido:

```text
secured-lab
    |
    v
OAuth 2.0
    |
    v
Access Token
    |
    v
FHIR Server
```

---

# 34. Relación con el futuro producto

Esta tarea empieza a acercar el laboratorio a un componente que podría utilizarse en consultoría.

El objetivo final no es vender:

```text
"un cliente HAPI FHIR"
```

sino poder construir una capa de integración reutilizable:

```text
                    Healthcare Integration Layer
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
       FHIR R4             OAuth 2.0          SMART
          |                   |                   |
          +-------------------+-------------------+
                              |
                              v
                    Integration Services
                              |
               +--------------+--------------+
               |              |              |
               v              v              v
            Clinic A       Clinic B       Hospital C
```

Esto permite que, en un proyecto real, la conversación con un cliente pueda evolucionar hacia:

> Podemos integrar su sistema FHIR existente directamente o utilizar nuestra capa de interoperabilidad como acelerador.

La monetización, multi-tenancy, observabilidad, gestión de conexiones y demás capacidades de producto se dejarán para tareas posteriores.

---

# 35. Próximo paso

Después de completar Task 016:

```text
Task 015
FHIR Server Configuration
        ↓
Task 016
OAuth 2.0 Authentication
        ↓
Task 017
SMART on FHIR
        ↓
Task 018+
Production-grade interoperability capabilities
```

No implementar SMART on FHIR como parte de Task 016.
