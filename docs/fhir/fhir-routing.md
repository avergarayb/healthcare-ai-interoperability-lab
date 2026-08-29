# FHIR routing foundation

This note adds **destination selection** in front of the FHIR client. Read it after [fhir-server-configuration.md](fhir-server-configuration.md) and [fhir-architecture.md](fhir-architecture.md). It does not replace [fhir-mapping.md](fhir-mapping.md) or OAuth/SMART.

There is still no `@RestController`, no routing database, and no message broker.

## Why routing exists

Task 015 already describes more than one FHIR server in YAML (`local-hapi`, `example-org`, `secured-lab`, `smart-lab`). The Spring bean `IGenericClient` talks to **one** of them: `fhir.active-server`.

A reusable integration component also needs to send a given Resource to a **named** destination without hard-coding `http://localhost:8080/fhir` in business code.

```text
RoutingRequest
      ↓
RoutingService
      ↓
FhirServerProfileRegistry   (existing YAML profiles)
      ↓
FhirClientFactory           (existing client construction)
      ↓
IGenericClient
      ↓
FhirService.readPatient     (existing FHIR operation)
```

Routing answers: **where** should this request go?

## RoutingRequest

```text
RoutingRequest
 ├── destination   profile name, e.g. local-hapi
 └── resource      HAPI R4 Resource (Patient with a logical id for a read)
```

The request does **not** contain `base-url`, `client-secret`, token URLs, or SMART settings. Those stay on the server profile.

Lab helper:

```java
RoutingRequest.readPatient("local-hapi", "patient-001")
```

## RoutingService

| Method | Job |
|---|---|
| `resolve` | enabled `FhirServerProfile` for the destination name |
| `client` | `FhirClientFactory` + token provider for that profile |
| `readPatient` | `GET Patient/{id}` on the selected client |

Unknown or disabled destinations throw `RoutingException`. There is no fallback to `local-hapi`.

`example.org` remains in YAML as a **disabled** second profile. Tests must not call it over the internet.

## Relationship with server profiles

`FhirServerProfileRegistry.enabledProfile(name)` is the lookup used by routing. It reuses the same YAML as Task 015:

```yaml
fhir:
  active-server: local-hapi
  servers:
    local-hapi:
      base-url: http://localhost:8080/fhir
      enabled: true
    example-org:
      base-url: https://example.org/fhir
      enabled: false
```

Routing does not invent a second configuration model.

## Relationship with FhirClientFactory

`RoutingService` does not call `newRestfulGenericClient`. `FhirClientFactory` still builds `FhirContext` and `IGenericClient`.

Authentication follows the profile:

```text
NONE                    → no Bearer interceptor
Client Credentials      → CachingAccessTokenProvider
SMART Authorization Code → SmartTokenProvider
```

`FhirAccessTokenProviders` (client package) is the shared composition used by the active-server bean and by routed clients. Task 020 does not add a new grant type.

## Mapping vs routing

| Layer | Question |
|---|---|
| Mapping | How do I turn external JSON into a FHIR Resource? |
| Routing | Which configured server should receive this request? |
| Authentication | How is that server authorized? |
| `FhirService` | How do I perform the FHIR interaction? |

`MappingService` does not import `routing`. `FhirService` has no `if (destination == …)` rules. A routed read constructs a short-lived `FhirService` with the destination client.

## Invalid destinations

| Destination | Result |
|---|---|
| `local-hapi` | enabled → client base `http://localhost:8080/fhir` |
| `does-not-exist` | `RoutingException` |
| `example-org` | `RoutingException` (disabled) |

## Why this is intentionally simple

No tenant rules, Kafka, load balancing, or clinical-data routing. The first operation is Patient read by logical id.

That is enough to prove:

```text
destination name → existing profile → existing factory → FHIR operation
```

Future routing can add tenant, environment, or resource-type rules **without** putting those rules in `FhirService`. Routed Patient reads also emit a structured audit event and increment bounded metrics; see [fhir-audit-observability.md](fhir-audit-observability.md) and [fhir-metrics-observability.md](fhir-metrics-observability.md). Routed READ also goes through retry and a per-destination circuit breaker; see [fhir-retry-resilience.md](fhir-retry-resilience.md) and [fhir-circuit-breaker.md](fhir-circuit-breaker.md).
