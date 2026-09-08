# Task 046 — Epic Sandbox SMART Authorization Code + PKCE

## Status

**Implementation**

Depends on Task 029 and the generic SMART coordinator from Task 033. Does not implement Patient read, `/metadata`, snapshot, or an agent.

## Objetivo

Conectar por primera vez `epic-sandbox` mediante SMART on FHIR usando **Authorization Code + PKCE S256**, cliente público y flujo standalone.

Es el equivalente funcional de la **Task 033**, pero para Epic Sandbox.

## WHAT

Implementar:

```text
GET /epic/sandbox/smart/start
        ↓
SMART/OAuth discovery
        ↓
state + PKCE S256
        ↓
Epic authorization endpoint
        ↓
login sandbox
        ↓
http://localhost:8081/smart/callback
        ↓
Authorization Code exchange
        ↓
access token en memoria
```

Esta task termina al demostrar que Epic emitió correctamente un token utilizable.

No incluye Patient read, `/metadata`, snapshot, proyección, contrato, agente ni IA.

---

## WHY

Oracle Health es el primer EHR real demostrado, pero no es el destino final.

```text
Oracle Health
Epic
otros EHR FHIR R4
        ↓
fhir-integration-service
        ↓
arquitectura vendor-neutral
```

La Task 046 demuestra que el mismo laboratorio puede autenticarse contra un segundo EHR real sin crear clientes FHIR específicos por vendor.

```text
Epic SMART authentication
        ≠
Patient context
        ≠
FHIR clinical authorization demostrada
```

---

## HOW

### 1. Perfil `epic-sandbox`

Reutilizar la infraestructura existente de perfiles de integración.

Características:

- destination: `epic-sandbox`
- cliente público
- standalone
- Authorization Code
- PKCE S256
- FHIR R4
- Sandbox / Non-Production

No Production.

No crear un segundo stack OAuth.

---

### 2. Variables de entorno

Completar en `.env` local:

```text
EPIC_SANDBOX_CLIENT_ID
EPIC_SANDBOX_REDIRECT_URI
EPIC_SANDBOX_SCOPE
EPIC_SANDBOX_SMART_CONFIGURATION_URL
```

#### Client ID

`EPIC_SANDBOX_CLIENT_ID` ya existe localmente.

Nunca copiarlo a:

- Java
- docs
- `.env.example`
- commits
- tests
- logs

#### Redirect URI

Usar:

```text
http://localhost:8081/smart/callback
```

Por tanto:

```text
EPIC_SANDBOX_REDIRECT_URI=http://localhost:8081/smart/callback
```

No pedir HTTPS de producción.

#### Scope

`EPIC_SANDBOX_SCOPE` debe configurarse explícitamente desde `.env`.

La implementación no debe inventar scopes en Java.

Los scopes deben ser consistentes entre:

1. el registro de la aplicación Epic;
2. `.env`;
3. la solicitud OAuth.

Después de cambiar scopes debe realizarse un nuevo login.

#### SMART configuration URL

`EPIC_SANDBOX_SMART_CONFIGURATION_URL` contiene la configuración externa SMART/OAuth del sandbox Epic.

El código no debe construir manualmente los endpoints OAuth.

No hardcodear hosts de Epic en `vendor.epic`.

---

### 3. SMART discovery

Reutilizar el mecanismo genérico existente.

Resolver desde la configuración externa, como mínimo:

- authorization endpoint;
- token endpoint;
- capacidades necesarias para el flujo público PKCE.

No hardcodear:

```text
fhir.epic.com
```

en `vendor.epic`.

---

### 4. Authorization Code + PKCE

Usar:

```text
code_challenge_method=S256
```

Flujo:

1. generar `state`;
2. generar `code_verifier`;
3. calcular `code_challenge`;
4. iniciar authorization request;
5. validar `state` en callback;
6. intercambiar authorization code usando `code_verifier`.

No usar:

- client secret;
- `client_secret_basic`;
- `private_key_jwt`;
- autenticación confidencial.

---

### 5. Endpoint de inicio

Exponer:

```text
GET /epic/sandbox/smart/start
```

Su responsabilidad es iniciar el flujo SMART.

No debe:

- leer Patient;
- llamar `/metadata`;
- buscar recursos clínicos;
- crear snapshot.

---

### 6. Callback

Reutilizar:

```text
/smart/callback
```

No crear:

```text
/epic/callback
```

El mecanismo genérico debe conservar la asociación entre la autorización iniciada y el destino correspondiente.

---

### 7. Token

Después de un callback exitoso:

```text
Authorization Code
        ↓
token exchange
        ↓
IssuedAccessTokenProvider
```

El token queda solamente en memoria.

No persistir:

- access token;
- refresh token;
- sesión OAuth;
- Patient ID;
- datos clínicos.

Nunca mostrar el valor del token.

El diagnóstico puede indicar:

```text
tokenIssued=true
hasAccessToken=true
expiresAt=<timestamp>
hasScope=<true|false>
hasPatient=<true|false>
```

pero nunca el token.

---

# Arquitectura

Preservar:

```text
vendor.epic
        ↓
RoutingService
        ↓
FhirService
        ↓
HAPI FHIR
```

La coordinación SMART reutiliza los componentes genéricos existentes.

## Prohibido

No crear:

```text
EpicClient
EpicSmartClient
EpicPatientClient
EpicOAuthClient
```

No introducir `if Epic` en:

- `FhirService`;
- timeout;
- HAPI client factory;
- routing genérico.

No hardcodear:

```text
https://...
fhir.epic.com
```

dentro de `vendor.epic`.

La URL del sandbox pertenece a configuración.

---

# Resultado esperado

Después del login:

```text
SMART token exchange succeeded
```

y:

```text
tokenIssued=true
hasAccessToken=true
```

`hasPatient` no debe asumirse.

Al ser standalone:

```text
hasPatient=false
```

es válido.

No convertir `fhirUser` en Patient ID.

Principio:

```text
OAuth identity
        ≠
Clinical Patient context
```

---

# Login sandbox

Usar las credenciales publicadas por Epic para su sandbox standalone provider.

No almacenar credenciales en:

- Java;
- `.env.example`;
- documentación del repo;
- tests;
- logs.

---

# Diagnóstico seguro

Puede mostrar:

- destino;
- resultado del authorization flow;
- token issued;
- expiración;
- presencia de scopes;
- presencia/ausencia de Patient context.

No puede mostrar:

- access token;
- refresh token;
- authorization code;
- PKCE verifier;
- client ID;
- Patient ID;
- datos clínicos.

---

# Fuera de alcance

## No Patient read

No implementar:

```text
GET /Patient/{id}
```

## No capability discovery

No implementar:

```text
GET /metadata
```

## No contexto clínico

No:

- configurar Patient ID;
- adivinar IDs;
- enumerar pacientes;
- convertir `fhirUser` en Patient.

## No recursos clínicos

No buscar:

- Condition;
- Observation;
- DiagnosticReport;
- MedicationRequest.

## No snapshot / proyección / contrato / agente

No tocar:

```text
clinical snapshot
projection
model boundary
agent stub
```

## No IA

No:

- LLM;
- prompts;
- OpenAI;
- Gemini;
- Anthropic;
- RAG;
- embeddings;
- vector DB;
- `ai-service`.

## No Production

Solo Epic Sandbox / Non-Production.

---

# Validación

## Unit tests

```bash
mvn clean test
```

Sin requerir:

- login Epic;
- red Epic;
- credenciales reales.

Cubrir:

- flujo Authorization Code;
- PKCE S256;
- state validation;
- token provider;
- token nunca expuesto;
- boundaries arquitectónicos.

## Integration tests

```bash
mvn clean verify -Pintegration
```

No deben depender del sandbox Epic vivo.

## Live validation opt-in

1. Completar variables Epic en `.env`.
2. Arrancar:

```bash
mvn spring-boot:run
```

3. Abrir:

```text
http://localhost:8081/epic/sandbox/smart/start
```

4. Completar login sandbox.
5. Volver al callback:

```text
http://localhost:8081/smart/callback
```

6. Verificar que se emitió un token sin mostrar su valor.

Maven no automatiza el login clínico del navegador.

---

# Criterios de aceptación

- [ ] `epic-sandbox` inicia SMART Authorization Code.
- [ ] Usa cliente público.
- [ ] Usa PKCE S256.
- [ ] Reutiliza `http://localhost:8081/smart/callback`.
- [ ] Obtiene configuración SMART desde URL externa configurada.
- [ ] No hardcodea hosts Epic en `vendor.epic`.
- [ ] No crea `EpicClient`.
- [ ] No añade `if Epic` en `FhirService`, routing o timeout.
- [ ] Un login sandbox real puede emitir access token.
- [ ] El token queda solo en memoria.
- [ ] El token nunca se muestra.
- [ ] No existe Patient read.
- [ ] No existe `/metadata`.
- [ ] No existe snapshot.
- [ ] No existe agente/LLM.
- [ ] `mvn clean test` pasa.
- [ ] `mvn clean verify -Pintegration` pasa sin depender de Epic vivo.

---

# WHAT / WHY / HOW / CONCEPT

## WHAT

Conectar `epic-sandbox` mediante SMART Authorization Code + PKCE S256 y obtener un access token real.

## WHY

Demostrar que el laboratorio puede autenticar contra un segundo EHR real manteniendo la arquitectura vendor-neutral.

## HOW

Configuración externa → SMART discovery → Authorization Code → PKCE → callback genérico → token en memoria.

## CONCEPT

```text
Oracle Health authentication
        ≠
arquitectura Oracle-only

Epic SMART authentication
        ≠
Patient context
        ≠
FHIR clinical access

Vendor authentication
        ↓
misma arquitectura genérica
        ↓
futuras operaciones FHIR vendor-neutral
```

---

# Commit propuesto

```text
feat: add Epic sandbox SMART PKCE authentication
```
