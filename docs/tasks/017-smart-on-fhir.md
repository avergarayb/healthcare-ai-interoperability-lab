# Task 017 — SMART on FHIR

## Objective

Extender `fhir-integration-service` para comprender y ejecutar un flujo básico de **SMART on FHIR** sobre un entorno local sintético.

La tarea parte de lo construido en Task 016:

- configuración de múltiples servidores FHIR;
- OAuth 2.0 Client Credentials;
- access token;
- Bearer authentication;
- `IGenericClient`;
- separación entre `FhirService` y la autenticación.

El objetivo es educativo y arquitectónico: entender qué agrega SMART on FHIR sobre OAuth 2.0 y FHIR, y preparar el `fhir-integration-service` para integraciones reales con EHRs que soporten SMART.

No se integra todavía con Epic, Oracle Health/Cerner ni otro EHR comercial.

---

## Scope

### In scope

- SMART on FHIR discovery.
- `/.well-known/smart-configuration`.
- Authorization endpoint.
- Token endpoint.
- SMART scopes.
- OAuth 2.0 Authorization Code.
- PKCE.
- `aud` como FHIR server audience.
- Access token.
- Refresh token.
- Patient/user context sintético.
- FHIR access después de autenticación.
- Separación entre Client Credentials, Authorization Code y SMART context.
- Tests unitarios e integration tests.
- Documentación.

### Out of scope

No implementar todavía:

- Epic real.
- Oracle Health/Cerner real.
- EHR comercial.
- OpenID Connect completo.
- login real de usuario.
- identity provider externo.
- launch desde un EHR real.
- `launch` embebido real.
- `openid` / `fhirUser` como identidad real.
- scopes administrativos reales.
- certificados TLS de producción.
- autorización clínica real.
- multiusuario real.
- consentimiento real del paciente.

---

# Step 1 — Branch

Crear:

```text
feature/fhir-smart-on-fhir
```

Partir desde `main`.

No trabajar directamente sobre `main`.

---

# Step 2 — SMART Discovery

Antes de implementar Java, verificar mediante HTTP:

```http
GET /.well-known/smart-configuration
```

Documentar al menos:

```text
authorization_endpoint
token_endpoint
scopes_supported
response_types_supported
code_challenge_methods_supported
capabilities
```

El cliente no debe inventar endpoints antes de verificar el discovery.

---

# Step 3 — SMART vs OAuth 2.0

Documentar la diferencia:

```text
OAuth 2.0
    ↓
mecanismo de autorización

SMART on FHIR
    ↓
perfil de OAuth 2.0
    +
scopes definidos para FHIR
    +
FHIR context
    +
discovery
```

Comparar con Task 016:

```text
Task 016

Client
  ↓
Client Credentials
  ↓
Access Token
  ↓
FHIR Server
```

versus:

```text
Task 017

FHIR App
  ↓
Authorization Code
  ↓
Authorization Server
  ↓
Authorization Code
  ↓
Token Endpoint
  ↓
Access Token
  +
Refresh Token
  +
FHIR context
  ↓
FHIR Server
```

---

# Step 4 — Authorization Code + PKCE

Implementar un flujo local sintético de Authorization Code.

La aplicación debe generar:

```text
code_verifier
code_challenge
state
```

Usar:

```text
S256
```

para PKCE.

Flujo:

```text
1. Application genera code_verifier
2. Application calcula code_challenge
3. Application genera state
4. Application construye authorization URL
5. Usuario/autorizador sintético autoriza
6. Authorization Server devuelve authorization code
7. Application intercambia code + code_verifier
8. Authorization Server devuelve tokens
```

No guardar `client_secret` en código.

---

# Step 5 — SMART scopes

Implementar y demostrar scopes SMART básicos.

Ejemplo:

```text
patient/Patient.read
patient/Observation.read
patient/Condition.read
```

También documentar la diferencia entre:

```text
patient
user
system
```

No asumir que un scope concede automáticamente todos los recursos.

El laboratorio debe demostrar al menos:

```text
patient/Patient.read
patient/Observation.read
```

---

# Step 6 — Patient Context

El Authorization Server sintético debe devolver un contexto de paciente.

Ejemplo:

```text
patient = patient-001
```

Documentar:

```text
FHIR authorization
        +
patient context
```

El objetivo es entender que SMART puede proporcionar contexto, no solamente un token válido.

---

# Step 7 — `aud`

El authorization request debe utilizar:

```text
aud
```

apuntando al FHIR server.

Ejemplo conceptual:

```text
aud=http://localhost:8180/fhir
```

El Authorization Server debe validar que la audiencia corresponde al servidor FHIR permitido.

No aceptar arbitrariamente cualquier `aud`.

---

# Step 8 — Token response

El token endpoint debe devolver una respuesta compatible con OAuth 2.0.

Ejemplo:

```json
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "...",
  "scope": "patient/Patient.read patient/Observation.read",
  "patient": "patient-001"
}
```

Los tokens son sintéticos.

Documentar:

```text
access_token
refresh_token
expires_in
scope
patient
```

No utilizar tokens reales.

---

# Step 9 — Refresh Token

Implementar un refresh token sintético.

Flujo:

```text
Access Token
    ↓
expira
    ↓
Refresh Token
    ↓
Token Endpoint
    ↓
nuevo Access Token
```

El cliente debe poder renovar el access token sin repetir todo el authorization flow.

Reutilizar la arquitectura de caching de Task 016.

---

# Step 10 — FHIR Authorization

El FHIR server/gateway debe rechazar requests sin autorización.

Ejemplos:

```http
GET /Patient/patient-001
```

sin token:

```text
401 Unauthorized
```

Token inválido:

```text
401 Unauthorized
```

Token válido con scope insuficiente:

```text
403 Forbidden
```

Token válido con scope suficiente:

```text
200 OK
```

Comprobar primero mediante HTTP.

---

# Step 11 — Java architecture

Mantener `FhirService` independiente de SMART.

Arquitectura esperada:

```text
                    FhirService
                         │
                         ▼
                   IGenericClient
                         │
                         ▼
             BearerAccessTokenInterceptor
                         │
                         ▼
                AccessTokenProvider
                         │
              ┌──────────┴──────────┐
              │                     │
       Client Credentials     SMART Authorization
              │                     │
              │              AuthorizationCodeClient
              │                     │
              │              SmartTokenProvider
              │                     │
              └──────────┬──────────┘
                         ▼
                  FHIR Gateway
                         │
                         ▼
                     HAPI FHIR
```

`FhirService` no debe contener:

```text
OAuth URLs
client secrets
authorization codes
PKCE
token parsing
```

---

# Step 12 — Suggested packages

Evaluar una estructura por responsabilidad:

```text
lab.healthcare.fhir
│
├── auth
│   ├── AccessToken
│   ├── AccessTokenProvider
│   ├── CachingAccessTokenProvider
│   ├── OAuth2TokenClient
│   ├── AuthorizationCodeClient
│   ├── SmartTokenProvider
│   └── BearerAccessTokenInterceptor
│
├── client
│   ├── FhirClientConfiguration
│   ├── FhirClientFactory
│   └── FhirService
│
├── config
│   ├── FhirServerProfile
│   ├── FhirServersProperties
│   └── FhirServerProfileRegistry
│
└── exception
    ├── FhirClientException
    └── OAuth2TokenException
```

No mover clases de Task 016 únicamente por estética.

Si se reorganizan paquetes, debe hacerse como refactoring controlado y todos los tests deben continuar funcionando.

---

# Step 13 — SMART discovery Java

Agregar un cliente para:

```http
GET /.well-known/smart-configuration
```

Representar al menos:

```text
authorizationEndpoint
tokenEndpoint
scopesSupported
responseTypesSupported
codeChallengeMethodsSupported
```

El cliente no debe hardcodear los endpoints SMART cuando el discovery esté disponible.

Flujo:

```text
FHIR Server URL
       ↓
/.well-known/smart-configuration
       ↓
SmartConfiguration
       ↓
AuthorizationCodeClient
```

---

# Step 14 — Authorization URL

Implementar construcción segura de la URL de autorización.

Debe incluir como mínimo:

```text
response_type=code
client_id=...
redirect_uri=...
scope=...
state=...
aud=...
code_challenge=...
code_challenge_method=S256
```

Usar URL encoding correcto.

El `state` debe generarse por autorización.

El `code_verifier` debe permanecer del lado de la aplicación.

---

# Step 15 — Callback

Implementar la recepción de:

```text
code
state
```

Comprobar:

```text
state recibido == state esperado
```

Si no coincide:

```text
OAuth2TokenException
```

No intercambiar el authorization code cuando el `state` sea inválido.

---

# Step 16 — Authorization Code Exchange

Enviar al token endpoint:

```text
grant_type=authorization_code
code=...
redirect_uri=...
client_id=...
code_verifier=...
```

Validar:

```text
access_token
token_type
expires_in
scope
patient
refresh_token
```

Los errores de OAuth deben diferenciarse de los errores FHIR.

---

# Step 17 — SMART-protected FHIR call

Una vez obtenido el token:

```text
SmartTokenProvider
       ↓
BearerAccessTokenInterceptor
       ↓
IGenericClient
       ↓
GET /Patient/patient-001
```

La llamada debe funcionar sin que `FhirService` conozca SMART.

Demostrar:

```text
readPatient("patient-001")
```

y búsqueda de Observations por paciente cuando el scope lo permita.

---

# Step 18 — Scope enforcement

Demostrar autorización insuficiente.

Ejemplo:

```text
Token:
patient/Patient.read
```

Request:

```http
GET /Observation?patient=patient-001
```

Resultado:

```text
403 Forbidden
```

Después obtener:

```text
patient/Patient.read
patient/Observation.read
```

y repetir la solicitud.

Resultado:

```text
200 OK
```

Esto demuestra la diferencia entre:

```text
authentication
```

y:

```text
authorization
```

---

# Step 19 — HTTP verification

Verificar:

### Discovery

```http
GET /.well-known/smart-configuration
```

### Authorization

```text
GET /authorize?...
```

### Token

```text
POST /oauth/token
```

### FHIR sin token

```http
GET /fhir/Patient/patient-001
```

→ `401`

### FHIR token insuficiente

```http
GET /fhir/Observation?patient=patient-001
```

→ `403`

### FHIR token correcto

```http
GET /fhir/Observation?patient=patient-001
```

→ `200`

---

# Step 20 — Tests

## Unit tests

Probar:

- SMART discovery parsing.
- authorization URL.
- URL encoding.
- PKCE verifier/challenge.
- state generation/validation.
- token parsing.
- refresh token.
- scope parsing.
- patient context.
- invalid state.
- invalid token response.
- expired token.
- missing access token.

## Integration tests

Crear:

```text
FhirSmartOnFhirIT
```

Debe comprobar:

1. SMART discovery.
2. Authorization flow.
3. Authorization code.
4. PKCE.
5. Token exchange.
6. Patient context.
7. FHIR access con token.
8. Scope insuficiente → 403.
9. Scope suficiente → 200.
10. Refresh token.
11. Nuevo access token.
12. FHIR access después del refresh.

---

# Step 21 — Existing tests

Ejecutar:

```bash
mvn clean test
```

y:

```bash
mvn clean verify -Pintegration
```

Todos los tests anteriores deben continuar pasando:

- Patient read/search.
- Observation/Condition.
- include/revinclude.
- CRUD.
- advanced search.
- chaining.
- terminology validation.
- resource validation.
- pagination.
- history/versioning.
- `$everything`.
- server configuration.
- OAuth 2.0 Client Credentials.

No aceptar regresiones silenciosas.

---

# Step 22 — Documentation

Crear:

```text
docs/fhir/fhir-smart-on-fhir.md
```

Documentar:

- SMART on FHIR.
- OAuth 2.0 vs SMART.
- discovery.
- Authorization Code.
- PKCE.
- scopes.
- patient context.
- `aud`.
- access token.
- refresh token.
- authorization vs authentication.
- FHIR access.
- arquitectura Java.
- diferencias con Task 016.
- limitaciones del laboratorio sintético.

Actualizar:

```text
docs/fhir/README.md
docs/fhir/fhir-oauth2-authentication.md
docs/roadmap.md
README.md
```

---

# Synthetic infrastructure

Mantener el laboratorio local.

Conceptualmente:

```text
                 ┌─────────────────────┐
                 │   SMART App         │
                 │ fhir-integration-   │
                 │ service             │
                 └──────────┬──────────┘
                            │
                            │ OAuth 2.0
                            ▼
                 ┌─────────────────────┐
                 │  SMART Auth Server  │
                 │       :9090         │
                 └──────────┬──────────┘
                            │
                            │ Bearer
                            ▼
                 ┌─────────────────────┐
                 │   FHIR Gateway      │
                 │       :8180         │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │     HAPI FHIR       │
                 │       :8080         │
                 └─────────────────────┘
```

No introducir Keycloak ni un IdP externo en esta tarea.

El Authorization Server continúa siendo sintético y exclusivamente de laboratorio.

---

# Security requirements

Nunca:

- almacenar client secrets en Git;
- imprimir access tokens en logs;
- imprimir refresh tokens en logs;
- aceptar cualquier `aud`;
- saltarse validación de `state`;
- reutilizar un authorization code;
- tratar un token expirado como válido;
- asumir que HTTP 200 significa autorización correcta;
- implementar autorización clínica real con lógica ad-hoc.

Utilizar variables de entorno para secretos.

---

# Important distinction

La evolución debe quedar clara:

```text
Task 015
Configuración
```

↓

```text
Task 016
OAuth 2.0 Client Credentials

"Aplicación → sistema FHIR"
```

↓

```text
Task 017
SMART on FHIR

"Aplicación → usuario/contexto → FHIR"
```

SMART no reemplaza FHIR.

SMART tampoco reemplaza OAuth 2.0.

SMART define cómo utilizar OAuth 2.0 de manera interoperable para aplicaciones relacionadas con FHIR.

---

# Expected result

Al terminar la tarea debe ser posible demostrar:

```text
1. Descubro cómo soporta SMART el servidor.

2. Construyo una autorización con:
   - client_id
   - redirect_uri
   - scope
   - aud
   - state
   - PKCE

3. Obtengo authorization code.

4. Intercambio el code.

5. Obtengo:
   - access token
   - refresh token
   - scope
   - patient context

6. Uso el access token contra FHIR.

7. El servidor valida scopes.

8. Renuevo el token cuando expira.

9. FhirService permanece independiente
   de esta lógica.
```

---

# Acceptance criteria

- [ ] Rama `feature/fhir-smart-on-fhir`.
- [ ] SMART discovery implementado.
- [ ] `/.well-known/smart-configuration` verificado por HTTP.
- [ ] Authorization Code implementado.
- [ ] PKCE S256 implementado.
- [ ] `state` validado.
- [ ] `aud` validado.
- [ ] SMART scopes implementados.
- [ ] Patient context sintético implementado.
- [ ] Access token implementado.
- [ ] Refresh token implementado.
- [ ] FHIR protegido con scopes.
- [ ] Token insuficiente → 403.
- [ ] Token válido → acceso FHIR.
- [ ] `FhirService` no conoce OAuth/SMART.
- [ ] `mvn clean test` → BUILD SUCCESS.
- [ ] `mvn clean verify -Pintegration` → BUILD SUCCESS.
- [ ] Documentación creada.
- [ ] No secrets en Git.
- [ ] No EHR comercial utilizado.
- [ ] No SMART real de Epic/Oracle Health utilizado.

---

# Deliverables

```text
docs/tasks/017-smart-on-fhir.md

docs/fhir/fhir-smart-on-fhir.md

FhirSmartOnFhirIT.java

SmartConfiguration.java
AuthorizationCodeClient.java
SmartTokenProvider.java
...
```

Los nombres finales pueden variar si la arquitectura mantiene las responsabilidades descritas.

---

# Git

No realizar commit ni push automáticamente.

Al finalizar:

```bash
git status
git diff --stat
git diff
```

Reportar:

- archivos creados;
- archivos modificados;
- archivos eliminados;
- tests ejecutados;
- resultados;
- comportamiento HTTP observado;
- problemas encontrados;
- decisiones de diseño.

El commit se realizará posteriormente de forma explícita.

---

# Next step

Después de completar Task 017:

```text
Task 018
```

será definida según lo aprendido en SMART on FHIR.

No implementar Task 018 como parte de esta tarea.
