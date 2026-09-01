# Task 031 — FHIR Capability Discovery

**Rama:** `feature/fhir-capability-discovery`  
**Baseline:** `main` después de completar y mergear la Task 030  
**Estado inicial:** No implementada

---

## Objetivo

La Task 031 añade descubrimiento de capacidades reales de un servidor FHIR mediante:

```text
GET /metadata
        ↓
CapabilityStatement
        ↓
FHIR Capability Discovery
        ↓
¿Qué soporta realmente este servidor?
```

Hasta ahora la plataforma conoce:

- configuración de nuestros destinos;
- perfiles de vendor (`GENERIC`, `EPIC`, `ORACLE_HEALTH`);
- configuración y discovery SMART;
- readiness de integración;
- routing y resiliencia.

Pero todavía no existe una capa que responda, en runtime:

> ¿Qué versión FHIR expone este servidor concreto?  
> ¿Soporta `Patient`?  
> ¿Permite `READ` sobre `Patient`?  
> ¿Permite `SEARCH`?  
> ¿Qué capacidades declara realmente su `CapabilityStatement`?

Esta task convierte `GET /metadata` en un contrato interno estable.

---

# Arquitectura

```text
Caller
   ↓
RoutingService
   ↓
Rate Limiter
   ↓
Bulkhead
   ↓
Circuit Breaker
   ↓
Retry
   ↓
FHIR Client
   ↓
GET /metadata
   ↓
CapabilityStatement
   ↓
FhirCapabilityDiscoveryService
   ↓
FhirServerCapabilities
```

La operación de discovery pertenece a la capa de interoperabilidad.

El resultado:

- no es metadata de vendor;
- no reemplaza SMART discovery;
- no inventa recursos;
- no supone que todo FHIR R4 está disponible.

---

# 1. CapabilityStatement

## WHAT

FHIR define `CapabilityStatement` como el recurso mediante el cual un servidor describe sus capacidades.

El endpoint habitual es:

```text
GET /metadata
Accept: application/fhir+json
```

Ejemplo conceptual:

```json
{
  "resourceType": "CapabilityStatement",
  "fhirVersion": "4.0.1",
  "software": {
    "name": "HAPI FHIR Server"
  },
  "rest": [
    {
      "resource": [
        {
          "type": "Patient",
          "interaction": [
            { "code": "read" },
            { "code": "search-type" }
          ]
        }
      ]
    }
  ]
}
```

## WHY

Un perfil YAML dice lo que configuramos.

Un perfil Epic u Oracle dice lo que conocemos del vendor.

Pero solo el servidor concreto puede declarar sus capacidades runtime.

## HOW

La nueva capa obtiene el `CapabilityStatement` mediante el cliente FHIR existente y lo transforma a un modelo interno.

## CONCEPT

**Configured capability ≠ vendor metadata ≠ runtime server capability.**

---

# 2. Modelo interno

Crear el paquete:

```text
lab.healthcare.fhir.capability
```

Modelo propuesto:

| Tipo | Rol |
|---|---|
| `FhirCapabilityDiscoveryService` | Descubre capacidades desde un servidor |
| `FhirServerCapabilities` | Snapshot estable de capacidades |
| `FhirResourceCapabilities` | Capacidades de un resource type |
| `FhirInteraction` | Interacciones soportadas |
| `FhirCapabilityException` | Fallo seguro de discovery |

El modelo interno no debe exponer HAPI por toda la aplicación.

---

# 3. `FhirServerCapabilities`

## WHAT

Representa una interpretación estable del `CapabilityStatement`.

Debe incluir como mínimo:

```text
fhirVersion
softwareName
implementationUrl
resource capabilities
```

Y permitir preguntas como:

```java
capabilities.supportsResource("Patient")
capabilities.supports("Patient", FhirInteraction.READ)
capabilities.supports("Patient", FhirInteraction.SEARCH_TYPE)
```

## WHY

El resto de la aplicación no debería recorrer:

```text
CapabilityStatement.rest()
    → resources
    → interactions
    → code
```

cada vez que necesite saber si una operación es posible.

## HOW

El discovery transforma la estructura FHIR externa a una representación semántica propia.

## CONCEPT

**External protocol model → internal capability model.**

---

# 4. Resource type vs interacción

## WHAT

Que un servidor declare:

```text
Patient
```

no significa automáticamente que soporte todas las operaciones.

Por ejemplo:

```text
Patient
   ├── READ
   └── SEARCH_TYPE
```

es diferente de:

```text
Patient
   ├── READ
   ├── SEARCH_TYPE
   ├── CREATE
   └── UPDATE
```

## WHY

FHIR no debe tratarse como:

> “Si existe Patient, puedo hacer cualquier cosa”.

Las capacidades deben respetar las interacciones declaradas.

## HOW

Crear:

```text
FhirInteraction
```

con las interacciones necesarias para el laboratorio.

Inicialmente:

```text
READ
SEARCH_TYPE
CREATE
UPDATE
DELETE
```

Solo representan códigos de CapabilityStatement; no significan que todas las operaciones estén implementadas en `FhirService`.

## CONCEPT

**Server capability ≠ application implementation.**

---

# 5. Capability declarada vs operación implementada

## WHAT

Un servidor puede declarar:

```text
Patient CREATE
```

aunque nuestro laboratorio solo implemente:

```java
readPatient(...)
```

## WHY

Discovery no debe inventar funcionalidades en nuestra aplicación.

## HOW

Debe existir una separación clara:

```text
Server supports CREATE
        ≠
Application currently executes CREATE
```

Task 031 descubre.

No añade automáticamente:

```text
createPatient()
updatePatient()
deletePatient()
```

## CONCEPT

**Capability discovery ≠ feature generation.**

---

# 6. FHIR version

## WHAT

El `CapabilityStatement` declara una versión FHIR.

Ejemplo:

```text
4.0.1
```

## WHY

Los perfiles actuales del laboratorio trabajan con R4.

No debemos asumir compatibilidad si un servidor declara una versión incompatible.

## HOW

`FhirServerCapabilities` conserva el valor descubierto.

La Task 031 valida que exista una versión.

La compatibilidad completa entre versiones puede evolucionar posteriormente; esta task no implementa un motor universal de conversión entre R4/R5.

## CONCEPT

**FHIR endpoint ≠ automáticamente FHIR R4 compatible.**

---

# 7. SMART Discovery vs Capability Discovery

## WHAT

Son dos descubrimientos diferentes.

### SMART discovery

```text
/.well-known/smart-configuration
```

Responde:

```text
¿Dónde está authorize?
¿Dónde está token?
¿Authorization Code?
¿PKCE S256?
```

### FHIR capability discovery

```text
GET /metadata
```

Responde:

```text
¿Qué recursos?
¿Qué interacciones?
¿Qué versión FHIR?
¿Qué servidor?
```

## WHY

OAuth y FHIR son capas diferentes.

## HOW

Task 028 permanece intacta.

Task 031 añade una capa paralela.

```text
SMART Discovery
      +
Capability Discovery
      ↓
Integration Compatibility
```

## CONCEPT

**Authentication capability ≠ FHIR API capability.**

---

# 8. Vendor profile vs CapabilityStatement

## WHAT

Epic y Oracle Health describen:

```text
qué sabemos/configuramos sobre la integración
```

El `CapabilityStatement` describe:

```text
qué declara este servidor concreto
```

## WHY

No debemos afirmar:

```text
vendor == EPIC
→ entonces Patient está disponible
```

Eso sería una suposición incorrecta.

## HOW

Task 031 no agrega:

```java
if (vendor == EPIC)
```

La misma discovery API funciona para:

```text
local-hapi
Epic
Oracle Health
otro servidor FHIR compatible
```

## CONCEPT

**Vendor identity ≠ runtime capability.**

---

# 9. Discovery por destino

## WHAT

Las capacidades pertenecen a un destino concreto.

Ejemplo:

```text
local-hapi
   → Patient READ = true

secured-lab
   → Patient READ = true

future-server
   → Patient READ = false
```

## WHY

Dos servidores del mismo vendor pueden tener configuraciones diferentes.

## HOW

El resultado debe conservar:

```text
destination/profile name
```

como contexto de discovery.

No debe usar:

- patient ID;
- correlation ID;
- token;
- valores clínicos.

## CONCEPT

**Capabilities are dependency-specific.**

---

# 10. Integración con Routing

El punto inicial recomendado es una operación explícita:

```text
RoutingService.discoverCapabilities(destination)
```

Flujo:

```text
Caller
   ↓
resolve destination
   ↓
resilience pipeline
   ↓
FhirCapabilityDiscoveryService
   ↓
CapabilityStatement
   ↓
FhirServerCapabilities
```

La resolución de destino ocurre antes de discovery.

Un destino inexistente sigue siendo:

```text
RoutingException
VALIDATION_ERROR
```

No se convierte en un error clínico FHIR.

---

# 11. Resiliencia

Capability discovery es una llamada a un dependency remoto.

Por eso debe respetar el pipeline existente:

```text
Rate Limiter
    ↓
Bulkhead
    ↓
Circuit Breaker
    ↓
Retry
    ↓
GET /metadata
```

## WHY

Si el servidor está caído, `/metadata` también puede:

- timeout;
- rechazar conexiones;
- devolver 5xx.

## HOW

La Task 031 reutiliza las capas existentes.

No crea:

```text
CapabilityRetryExecutor
CapabilityCircuitBreaker
```

## CONCEPT

**Una misma dependency policy debe proteger las llamadas al mismo servidor.**

---

# 12. Métricas y audit

Discovery debe producir observabilidad segura.

La operación puede identificarse inicialmente como:

```text
CAPABILITY_DISCOVERY
```

Por tanto, será necesario evaluar y extender el modelo de operación actual, que hasta ahora está deliberadamente acotado a `READ`.

El evento debe incluir:

```text
destination
operation
outcome
status
duration
```

No debe registrar:

- CapabilityStatement completo;
- Patient JSON;
- tokens;
- Authorization headers;
- client secrets.

## CONCEPT

**Observability tracks operations, not payloads.**

---

# 13. Error handling

Los errores HTTP y de conexión reutilizan la clasificación estructurada de la Task 023:

```text
TIMEOUT
CONNECTION_ERROR
SERVER_ERROR
AUTHENTICATION_ERROR
AUTHORIZATION_ERROR
NOT_FOUND
...
```

La discovery no debe crear un segundo sistema de clasificación.

Si el documento recibido no puede interpretarse como un `CapabilityStatement` válido, se utiliza:

```text
FhirCapabilityException
```

con un mensaje seguro.

## WHY

Hay diferencia entre:

```text
el servidor no responde
```

y:

```text
respondió algo incompatible con CapabilityStatement
```

## CONCEPT

**Transport failure ≠ protocol interpretation failure.**

---

# 14. No cache todavía

## WHAT

Task 031 descubre capacidades bajo demanda.

## WHY

Cache introduce decisiones adicionales:

- TTL;
- invalidación;
- refresh;
- cambios de CapabilityStatement;
- coherencia por destino.

No es necesario para aprender primero el contrato básico.

## HOW

No crear cache distribuido.

No Redis.

No base de datos.

Una futura task puede añadir caching explícitamente.

## CONCEPT

**Discovery first; caching later.**

---

# 15. Arquitectura propuesta

```text
                    ┌─────────────────────┐
                    │ RoutingService      │
                    └──────────┬──────────┘
                               │
                    destination resolution
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Resilience Pipeline │
                    │ Rate → Bulkhead     │
                    │ Circuit → Retry     │
                    └──────────┬──────────┘
                               │
                               ▼
             ┌────────────────────────────────┐
             │ FhirCapabilityDiscoveryService │
             └───────────────┬────────────────┘
                             │
                             ▼
                      GET /metadata
                             │
                             ▼
                    CapabilityStatement
                             │
                             ▼
                  FhirServerCapabilities
```

`FhirService` debe mantenerse enfocado en operaciones FHIR de negocio.

La discovery puede utilizar el mismo `IGenericClient`, pero no debe convertir `FhirService` en un objeto que conozca routing, vendor o políticas.

---

# 16. Explicaciones obligatorias para aprendizaje

Cursor debe explicar las porciones importantes usando exactamente:

## WHAT
¿Qué hace?

## WHY
¿Por qué existe?

## HOW
¿Cómo funciona técnicamente?

## CONCEPT
¿Qué concepto de interoperabilidad, arquitectura o diseño representa?

Las explicaciones mínimas deben cubrir:

1. `GET /metadata` y `CapabilityStatement`.
2. Conversión de modelo HAPI a modelo interno.
3. Resource type vs interaction.
4. `supportsResource()` y `supports()`.
5. SMART discovery vs FHIR capability discovery.
6. Vendor profile vs runtime capabilities.
7. Reutilización del pipeline de resiliencia.
8. Por qué discovery no crea CREATE/UPDATE automáticamente.
9. Errores de transporte vs documento CapabilityStatement inválido.
10. Por qué no se agrega cache todavía.

---

# Tests

## Unit tests

Cubrir como mínimo:

### `FhirServerCapabilitiesTest`

```text
supportsResource
supports interaction
resource inexistente
interaction inexistente
```

### `FhirCapabilityDiscoveryServiceTest`

```text
CapabilityStatement → internal model
FHIR version
software metadata
resources
interactions
```

### `FhirInteractionTest`

```text
FHIR interaction codes
unknown/unsupported handling
```

### Architecture boundary tests

Verificar:

```text
FhirService
Routing
Resilience
```

no contienen lógica específica de:

```text
EPIC
ORACLE_HEALTH
```

para capability discovery.

---

# Integration Tests

Crear:

```text
FhirCapabilityDiscoveryIT
```

contra:

```text
local-hapi
```

Escenario mínimo:

```text
GET /metadata
      ↓
CapabilityStatement
      ↓
discover capabilities
      ↓
FHIR version discovered
      ↓
Patient resource discovered
      ↓
READ capability verified
```

También probar un destino inexistente:

```text
does-not-exist
      ↓
RoutingException
VALIDATION_ERROR
```

Si es viable dentro de la arquitectura actual, probar un fallo de dependency para comprobar reutilización del pipeline de resiliencia.

---

# Criterios de aceptación

La Task 031 estará terminada cuando:

- `GET /metadata` funcione contra HAPI local;
- el resultado se transforme a un modelo interno;
- se pueda preguntar si un resource existe;
- se pueda preguntar si una interacción está soportada;
- SMART discovery siga separado;
- Epic y Oracle sigan siendo perfiles de vendor;
- no exista `if (vendor == ...)` en routing;
- resiliencia se reutilice;
- audit/metrics no registren payloads sensibles;
- no exista cache todavía;
- `FhirService` mantenga sus responsabilidades;
- Tasks 001–030 sigan verdes.

---

# Fuera de alcance

Esta task no implementa:

- conexión real a Epic;
- conexión real a Oracle Health;
- OAuth real;
- DCR;
- EHR Launch completo;
- cache de CapabilityStatement;
- generación automática de operaciones;
- soporte universal R4/R5;
- catálogo hardcodeado de todos los recursos FHIR;
- certificación de vendors.

---

# Resultado esperado

Al terminar la Task 031, la plataforma tendrá dos mecanismos de discovery complementarios:

```text
┌──────────────────────────────────────────┐
│ SMART Discovery                          │
│                                          │
│ /.well-known/smart-configuration         │
│                                          │
│ → authorize endpoint                     │
│ → token endpoint                         │
│ → grants                                 │
│ → PKCE                                   │
└──────────────────────────────────────────┘

                    +

┌──────────────────────────────────────────┐
│ FHIR Capability Discovery                │
│                                          │
│ GET /metadata                            │
│                                          │
│ → FHIR version                           │
│ → resources                              │
│ → interactions                           │
│ → server capabilities                    │
└──────────────────────────────────────────┘

                    ↓

        Integration Compatibility Layer
                    ↓

       Real-world Sandbox Integration
```

Esto deja al laboratorio preparado para la siguiente etapa:

```text
Real Sandbox Integration
        ↓
Epic sandbox
        ↓
Oracle Health environment
```

pero sin afirmar todavía que esos proveedores estén conectados.

---

## Git

**Rama:**

```text
feature/fhir-capability-discovery
```

**Baseline:**

```text
main después de Task 030
```

**Mensaje de commit recomendado:**

```text
feat: add FHIR capability discovery foundation
```
