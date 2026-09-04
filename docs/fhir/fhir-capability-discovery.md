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

## Oracle Health live validation (Task 034)

The Oracle Code sandbox `GET /metadata` is **public**. Live validation used the configured `ORACLE_HEALTH_SANDBOX_BASE_URL`, not a hostname compiled into Java.

Do **not** call `RoutingService.discoverCapabilities("oracle-health-sandbox")` for this GET. That destination is `SMART_AUTHORIZATION_CODE`; routed clients attach a Bearer via `SmartTokenProvider.authorizeSynthetically`, which is the synthetic `lab-oauth` flow and fails against Oracle. `OracleSandboxCapabilityDiscoveryService` copies the configured base URL onto a temporary `FhirServerProfile` with `FhirAuthenticationSettings.none()` and reuses `FhirCapabilityDiscoveryService`.

Live result (Oracle Health Millennium FHIR R4 Code sandbox, no Authorization header):

| Observation | Value |
|---|---|
| HTTP | `200` |
| Auth required | No (Outcome A — public metadata) |
| `fhirVersion` | `4.0.1` |
| Software name | empty in the document |
| Publisher | Oracle Health |
| Resources declared | 44 types, including Patient and Observation; not every R4 resource (`Medication`, `Claim` absent) |
| Patient interactions | `read`, `search-type`, `create`, `patch` |
| Internal model | `patch` omitted (unknown `FhirInteraction`); `update` / `delete` not declared |
| Search / operations | Patient search params and operations (`health-cards-issue`, `export`) exist in the raw document; `FhirServerCapabilities` records `SEARCH_TYPE`, not param names or operations |

This is **not** Patient search (Task 035), Patient read (Task 036), Condition search (Task 037), Observation search (Task 038), DiagnosticReport search (Task 039), or MedicationRequest search (Task 040). Tokens are not fetched or persisted for `/metadata`.

## What this is not

- SMART `/.well-known/smart-configuration`
- A hardcoded catalog of every R4 resource
- A cache
- Proof that the application implements every declared interaction
- An Oracle-specific duplicate of `FhirServerCapabilities`
