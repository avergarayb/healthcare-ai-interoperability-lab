# Task 028 — Real-World SMART on FHIR Readiness

## Objetivo

Preparar la capa SMART on FHIR construida en las Tasks 016–018 para conectarse posteriormente a proveedores reales, sin introducir todavía una conexión obligatoria a Epic, Oracle Health u otro sandbox externo.

La Task 028 no añade una nueva operación FHIR ni un nuevo grant OAuth. Su objetivo es separar claramente:

- configuración conocida del laboratorio,
- descubrimiento SMART dinámico,
- requisitos de un Authorization Server real,
- parámetros específicos de una sesión SMART.

Al finalizar, la plataforma debe estar preparada para recibir la configuración de un proveedor real mediante perfiles y discovery, sin hardcodear endpoints dentro del flujo SMART.

---

# Contexto

Actualmente existe soporte para un flujo SMART on FHIR sintético:

FHIR Server Profile
        ↓
FhirAuthenticationSettings
        ↓
SmartTokenProvider
        ↓
SmartConfigurationClient
        ↓
PKCE + Authorization Code
        ↓
OAuth Token
        ↓
BearerAccessTokenInterceptor
        ↓
FHIR Server

Eso permitió demostrar el Authorization Code Flow en un laboratorio controlado.

Un proveedor real introduce información que no debe asumirse fija:

- authorization endpoint,
- token endpoint,
- scopes soportados,
- PKCE,
- audience (`aud`),
- issuer,
- capabilities declaradas por SMART.

La plataforma debe distinguir entre:

1. configuración local del cliente;
2. metadata descubierta del Authorization Server;
3. parámetros concretos de una autorización.

---

# Arquitectura objetivo

Caller / Application
        ↓
FhirServerProfile
        ↓
FhirAuthenticationSettings
        ↓
SmartConfigurationClient
        ↓
SMART Discovery
/.well-known/smart-configuration
        ↓
SmartConfiguration
        ↓
SmartAuthorizationRequest
        ↓
Authorization Code + PKCE
        ↓
AuthorizationCodeClient
        ↓
SmartTokenProvider
        ↓
AccessTokenProvider
        ↓
BearerAccessTokenInterceptor
        ↓
FHIR Server

`FhirService` no conoce SMART.

`RoutingService` sigue resolviendo el destino.

La capa `smart` sigue siendo responsable del flujo OAuth/SMART.

No se añade lógica de Epic u Oracle dentro de `client`, `routing` o `auth`.

---

# Nuevo modelo

Paquete:

`lab.healthcare.fhir.smart`

## 1. SmartAuthorizationRequest

Representa una solicitud concreta de autorización SMART.

Debe contener únicamente parámetros de sesión necesarios para construir la autorización:

- `authorizationEndpoint`
- `clientId`
- `redirectUri`
- `scope`
- `state`
- `aud`
- PKCE challenge

No contiene:

- `clientSecret`
- access token
- refresh token
- datos clínicos

### Concepto

La configuración del servidor no es lo mismo que una solicitud de autorización.

Una configuración puede vivir durante meses.

Un `state` y un PKCE verifier pertenecen a una sesión concreta.

---

## 2. SmartConfiguration

La metadata descubierta sigue representando la información publicada por:

`/.well-known/smart-configuration`

Debe modelar explícitamente los campos relevantes para el cliente.

Como mínimo, conservar:

- `authorization_endpoint`
- `token_endpoint`

Y añadir soporte para metadata útil de compatibilidad cuando esté disponible, sin obligar a que todos los servidores la publiquen.

Por ejemplo:

- `issuer`
- `scopes_supported`
- `code_challenge_methods_supported`
- `grant_types_supported`

Los campos opcionales deben seguir siendo opcionales.

No se inventan defaults clínicos.

---

## 3. SmartCapabilities

Crear un modelo pequeño que permita responder preguntas como:

- ¿declara Authorization Code?
- ¿declara PKCE S256?
- ¿qué scopes publica?
- ¿qué grant types declara?

Este modelo no sustituye a la metadata original.

Es una interpretación del discovery para que el resto de la aplicación no tenga que inspeccionar listas JSON directamente.

---

## 4. SmartConfigurationValidator

Responsable de validar que la metadata descubierta es compatible con el flujo que queremos ejecutar.

Ejemplos:

- falta `authorization_endpoint` → incompatible;
- falta `token_endpoint` → incompatible;
- PKCE requerido por nuestro flujo pero el servidor declara explícitamente métodos incompatibles → error;
- metadata opcional ausente → no necesariamente error.

No debe asumir que todos los servidores publican exactamente la misma metadata.

---

## 5. SmartCompatibilityException

Excepción específica para metadata SMART incompatible.

No reutilizar `OAuth2TokenException`.

Ejemplos:

- endpoint requerido ausente;
- capability declarada incompatible;
- flujo requerido no soportado.

El mensaje debe ser seguro:

- sin authorization code,
- sin PKCE verifier,
- sin tokens,
- sin secretos.

---

# `aud` — Audience

## WHAT

`aud` identifica el servidor FHIR al que está destinada la aplicación.

Ejemplo conceptual:

`aud=https://fhir.example.com`

## WHY

En un ecosistema real, el Authorization Server puede necesitar saber qué FHIR API está solicitando acceso la aplicación.

No debe confundirse con:

- issuer,
- authorization endpoint,
- token endpoint.

## HOW

El `aud` pertenece a la solicitud de autorización SMART, no al `FhirService`.

La fuente inicial será el perfil FHIR configurado.

No se construye mediante string manipulation dentro de `SmartTokenProvider`.

## CONCEPT

Authorization target ≠ OAuth endpoint.

---

# Scopes

La Task debe separar:

## Scopes solicitados

Lo que nuestra aplicación pide.

Ejemplo conceptual:

`launch/patient patient/Patient.read patient/Observation.read`

## Scopes soportados

Lo que el servidor declara en su metadata, si publica esa información.

La plataforma puede validar compatibilidad cuando exista metadata suficiente.

No debe rechazar automáticamente un servidor solo porque no publique `scopes_supported`.

### Concepto

Requested capability ≠ advertised capability.

---

# PKCE

El laboratorio ya utiliza PKCE.

La Task 028 debe hacer explícita la compatibilidad con:

`S256`

Flujo:

code_verifier
        ↓ SHA-256
code_challenge
        ↓
Authorization Request

La metadata puede declarar:

`code_challenge_methods_supported`

Reglas:

- si la metadata declara métodos y no incluye `S256` → incompatibilidad;
- si no declara el campo → no asumir incompatibilidad automáticamente;
- no registrar el verifier ni el challenge como secreto en logs.

---

# Discovery vs configuración local

## Configuración local

Pertenece al perfil:

- base FHIR URL;
- client ID;
- redirect URI;
- configuración necesaria para la aplicación.

## Discovery remoto

Pertenece al proveedor:

- authorization endpoint;
- token endpoint;
- capabilities;
- metadata SMART.

La URL de discovery debe derivarse de forma explícita y documentada a partir del destino SMART/FHIR configurado.

No hardcodear:

- Epic URLs;
- Oracle URLs;
- localhost URLs.

---

# Validación de compatibilidad

Añadir una operación explícita, conceptualmente:

`SmartConfigurationValidator.validate(configuration, requirements)`

La validación responde:

> ¿Puede nuestra plataforma ejecutar este flujo SMART contra esta metadata?

No ejecuta OAuth.

No abre navegador.

No obtiene tokens.

No llama a `FhirService`.

---

# Requisitos del flujo actual

La plataforma actual requiere:

1. Authorization Code Flow.
2. PKCE S256.
3. Authorization endpoint.
4. Token endpoint.

Las capacidades adicionales son informativas o validables cuando el proveedor las declara.

No añadir todavía:

- Dynamic Client Registration;
- Refresh Token flow nuevo;
- Backend Services;
- JWT client assertion;
- Epic-specific APIs;
- Oracle-specific APIs.

Eso pertenece a tareas posteriores.

---

# Integración con la arquitectura existente

## `client`

No cambia la responsabilidad.

`FhirService` sigue ejecutando operaciones FHIR.

No importa:

- `SmartCapabilities`;
- `SmartConfigurationValidator`;
- `SmartAuthorizationRequest`.

## `server`

El perfil sigue representando el destino.

No conoce reglas específicas de Epic u Oracle.

## `auth`

Sigue exponiendo:

`AccessTokenProvider`

SMART continúa implementando ese contrato.

## `smart`

Contiene:

- discovery;
- metadata;
- compatibility;
- PKCE;
- authorization request;
- authorization code;
- token provider.

## `routing`

Selecciona el destino.

No interpreta metadata SMART.

---

# Flujo completo

## Antes

Destination
    ↓
SmartTokenProvider
    ↓
Discovery
    ↓
Authorization Code
    ↓
Token

## Después

Destination
    ↓
Smart Configuration Discovery
    ↓
SmartCapabilities
    ↓
Compatibility Validation
    ↓
SmartAuthorizationRequest
    ↓
PKCE S256
    ↓
Authorization Code
    ↓
Token
    ↓
FHIR Request

---

# Qué NO cambia

Esta Task no debe romper:

- OAuth Client Credentials;
- SMART sintético existente;
- `FhirService`;
- routing;
- mapping;
- audit;
- metrics;
- retry;
- circuit breaker;
- rate limiting;
- bulkhead.

El pipeline de resiliencia sigue siendo:

Rate Limiter
    ↓
Bulkhead
    ↓
Circuit Breaker
    ↓
Retry
    ↓
FhirService

SMART pertenece a la construcción/autenticación del cliente, no al pipeline de resiliencia de una operación FHIR.

---

# Tests

Añadir tests unitarios para:

## SmartConfiguration

- endpoints obligatorios;
- metadata opcional;
- scopes;
- grant types;
- PKCE methods.

## SmartCapabilities

- Authorization Code declarado;
- S256 declarado;
- scopes disponibles;
- metadata ausente.

## SmartConfigurationValidator

### Debe aceptar

- authorization endpoint + token endpoint;
- Authorization Code compatible;
- S256 compatible.

### Debe rechazar

- authorization endpoint ausente;
- token endpoint ausente;
- PKCE metadata declarada sin S256;
- grant types declarados sin Authorization Code.

### No debe rechazar automáticamente

- scopes_supported ausente;
- grant_types_supported ausente;
- code_challenge_methods_supported ausente.

## SmartAuthorizationRequest

Verificar:

- `aud`;
- state;
- redirect URI;
- scopes;
- PKCE challenge.

Nunca imprimir secretos.

---

# Integration Test

Actualizar o añadir un IT contra el laboratorio SMART existente.

Debe demostrar:

1. discovery de SMART configuration;
2. construcción de `SmartCapabilities`;
3. validación de compatibilidad;
4. construcción de authorization request;
5. Authorization Code Flow existente;
6. token;
7. operación FHIR autenticada.

El laboratorio sintético sigue siendo válido como entorno controlado.

La Task no requiere internet.

La conexión a sandboxes reales se realizará después de completar la preparación vendor-aware.

---

# Explicaciones obligatorias para aprendizaje

Cursor debe explicar las porciones importantes implementadas usando este formato:

## WHAT
¿Qué hace el código?

## WHY
¿Por qué existe esta clase o decisión?

## HOW
¿Cómo funciona paso a paso?

## CONCEPT
¿Qué concepto de interoperabilidad, OAuth o arquitectura representa?

Explicar especialmente:

1. diferencia entre SMART discovery y configuración local;
2. `aud`;
3. requested scopes vs advertised scopes;
4. PKCE S256;
5. metadata opcional vs incompatibilidad;
6. `SmartCapabilities`;
7. `SmartConfigurationValidator`;
8. por qué `FhirService` no conoce SMART.

No explicar cada getter o constructor trivial.

---

# Documentación

Crear:

`docs/fhir/fhir-smart-real-world-readiness.md`

Actualizar cuando corresponda:

- `docs/fhir/README.md`
- `docs/fhir/fhir-smart-on-fhir.md`
- `docs/fhir/fhir-architecture.md`
- `docs/fhir/fhir-server-configuration.md`
- `docs/fhir/fhir-routing.md`
- `docs/roadmap.md`
- `README.md`

Documentar claramente:

> Task 028 prepara la plataforma para proveedores SMART reales, pero todavía no certifica compatibilidad con Epic ni Oracle Health.

---

# Criterios de aceptación

La Task está completa cuando:

1. La metadata SMART puede representar endpoints y capabilities relevantes.
2. La plataforma distingue metadata descubierta de parámetros de autorización.
3. `aud` forma parte explícita de la autorización SMART.
4. PKCE S256 puede validarse contra metadata declarada.
5. Metadata opcional ausente no produce falsos negativos.
6. Metadata explícitamente incompatible produce `SmartCompatibilityException`.
7. El flujo SMART sintético existente continúa funcionando.
8. `FhirService` no importa clases SMART.
9. No hay URLs hardcodeadas de vendors.
10. No se registran tokens, secrets, authorization codes ni PKCE verifier.
11. Tests unitarios e integration tests permanecen verdes.
12. Las capas de routing, observability y resilience no cambian de responsabilidad.

---

# Fuera de alcance

Esta Task NO incluye:

- conexión real a Epic;
- conexión real a Oracle Health;
- sandbox externo;
- Dynamic Client Registration;
- nuevos OAuth grants;
- refresh token management;
- vendor-specific code;
- AI Agent;
- base de datos.

---

# Git

Rama:

`feature/fhir-smart-real-world-readiness`

Baseline:

`main` después de la Task 027.

Mensaje recomendado:

`feat: prepare SMART on FHIR for real-world provider compatibility`
