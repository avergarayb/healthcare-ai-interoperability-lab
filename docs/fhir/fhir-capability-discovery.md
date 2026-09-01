# FHIR capability discovery

Task 031 turns `GET /metadata` into an internal capability model. Read this after [fhir-client.md](fhir-client.md) and [fhir-routing.md](fhir-routing.md). It does **not** replace SMART discovery ([fhir-smart-real-world-readiness.md](fhir-smart-real-world-readiness.md)) or vendor profiles ([vendors/epic.md](vendors/epic.md), [vendors/oracle-health.md](vendors/oracle-health.md)).

There is still no cache, no Redis, and no automatic `createPatient()`.

## What this task is

A named destination answers **where**. SMART answers **how to authorize**. A vendor profile answers **what we configured about Epic or Oracle Health**. Capability discovery answers **what this server declared at runtime**.

```text
GET /metadata
        ↓
CapabilityStatement
        ↓
FhirCapabilityDiscoveryService
        ↓
FhirServerCapabilities
        ↓
supportsResource("Patient")
supports("Patient", READ)
```

```http
GET http://localhost:8080/fhir/metadata
Accept: application/fhir+json
```

## Internal model

`lab.healthcare.fhir.capability` does not leak HAPI `CapabilityStatement` to the rest of the application.

| Type | Role |
|---|---|
| `FhirCapabilityDiscoveryService` | Fetch + interpret |
| `FhirServerCapabilities` | Snapshot: version, software, URL, resources |
| `FhirResourceCapabilities` | Interactions for one resource type |
| `FhirInteraction` | `READ`, `SEARCH_TYPE`, `CREATE`, `UPDATE`, `DELETE` |
| `FhirCapabilityException` | Invalid document (not a transport failure) |

Unknown FHIR interaction codes (`vread`, `history-instance`) are omitted. Declaring `Patient` does not imply every interaction. Declaring `CREATE` does not add a write method to `FhirService`.

## Routing and resilience

```text
RoutingService.discoverCapabilities(destination)
        ↓
Rate limiter → bulkhead → circuit → retry
        ↓
FhirService.retrieveCapabilityStatement()
        ↓
interpret CapabilityStatement
```

Unknown destinations remain `RoutingException` / `VALIDATION_ERROR`. The same per-destination pipeline protects `/metadata` as it protects `GET Patient/{id}`. There is no `CapabilityRetryExecutor`.

Audit operation is `CAPABILITY_DISCOVERY`. The event records destination, outcome, status, and duration. It does not log the CapabilityStatement JSON, Patient payloads, or tokens.

## What this is not

- SMART `/.well-known/smart-configuration`
- Epic or Oracle Health live sandbox
- A hardcoded catalog of every R4 resource
- A cache
- Proof that the application implements every declared interaction
