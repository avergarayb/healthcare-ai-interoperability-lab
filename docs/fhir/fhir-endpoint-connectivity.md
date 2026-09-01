# FHIR endpoint connectivity

Task 032 adds a **transport-level** check for a FHIR base URL. Read this after [fhir-capability-discovery.md](fhir-capability-discovery.md) and [vendors/oracle-health.md](vendors/oracle-health.md).

It does **not** interpret `CapabilityStatement`, read Patient, or perform SMART login.

## What this is

```text
GET {fhir-base-url}/metadata
Accept: application/fhir+json
        ↓
HTTP status only (body discarded)
        ↓
FhirConnectivityStatus
```

A reachable result means the configured endpoint responded at the FHIR metadata boundary. It does not mean clinical access works.

## Package

`lab.healthcare.fhir.connectivity` is vendor-neutral. It does not import Oracle or Epic types, `FhirService`, or routing.

| Type | Role |
|---|---|
| `FhirEndpointConnectivityVerifier` | Builds `{base}/metadata` and probes it |
| `FhirConnectivityStatus` | `REACHABLE` / `UNREACHABLE` / `SKIPPED` |
| `FhirConnectivityOutcome` | Outcome enum |

Failures reuse Task 023 categories (`TIMEOUT`, `CONNECTION_ERROR`, `SERVER_ERROR`, `VALIDATION_ERROR`). Local URI mistakes are `VALIDATION_ERROR` and never become retries.

## Oracle sandbox readiness

Oracle-specific inspection lives in `vendor.oracle`:

```text
disabled → DISABLED (no HTTP)
invalid enabled config → INVALID_CONFIGURATION (no HTTP, VALIDATION_ERROR)
valid SANDBOX → READY_FOR_CONNECTIVITY_CHECK
PRODUCTION → CONFIGURED (out of sandbox connectivity scope)
```

`OracleSandboxReadinessService.checkConnectivity` validates **before** calling the generic verifier. Invalid configuration does not consume retry attempts or open a circuit.

## Opt-in live test

Default `mvn verify -Pintegration` excludes `*LiveIT.java`. A real Oracle probe requires:

```text
mvn verify -Poracle-live
ORACLE_HEALTH_LIVE_IT=true
```

plus the `ORACLE_HEALTH_SANDBOX_*` environment variables. See [`.env.example`](../../.env.example).
