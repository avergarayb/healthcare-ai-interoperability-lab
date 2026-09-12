# Model Boundary Contract v1

Task 055 records the shared contract guarantees after Oracle (042–045) and Epic (052–054). This is not a new contract version.

## Shared invariants

Oracle and Epic must produce the same `ModelBoundaryContract` shape:

| Field | Guarantee |
|---|---|
| `contractVersion` | `v1` |
| Patient | present on complete/partial; allowlist is `resourceType` plus technical `status` |
| Conditions | present on complete/partial; allowlist is `resourceType`, `clinicalStatusCode` |
| Observations | present on complete/partial; allowlist is `resourceType`, `status` |
| DiagnosticReports | present on complete/partial; allowlist is `resourceType`, `status` |
| received / retained / truncated | preserved from the controlled projection |
| `RetentionCeiling` | `N = 5` for included collections |
| `hasClinicalData` | stub-derived from retained counts, not clinical values |
| `AgentStub` | same consumer; no vendor branch |

The allowlist is exactly Task 042. Do not add fields so that Oracle and Epic “match”.

## Allowed differences

| Aspect | Epic | Oracle |
|---|---|---|
| `MedicationRequest` | absent (`null`) | may be present |
| Snapshot contents | `ClinicalSnapshotContents.withoutMedicationRequests()` | `ClinicalSnapshotContents.allCollections()` |
| Destination name | `epic-sandbox` | `oracle-health-sandbox` |
| Laboratory confirmation | `GET /epic/sandbox/fhir/clinical-projection` | `GET /oracle/sandbox/fhir/clinical-projection`, `GET /api/model-boundary/v1`, `GET /lab/agent-stub` |

Absence is not an empty collection. The stub accepts both `null` and a present MedicationRequest collection without `if Epic` or `if Oracle`.

## What the stub must not know

FHIR, HAPI, Epic, Oracle, SMART, tokens, Patient IDs, or EHR URLs. Vendor adapters choose `ClinicalSnapshotContents` before the contract.

## Tests

Shared assertions live in `ModelBoundaryContractAssertions`. `OracleEpicContractCompatibilityTest` runs the same v1 rules for both destinations.
