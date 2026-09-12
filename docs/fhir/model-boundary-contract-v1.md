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

Task 056 may persist `TIMEOUT` on an existing collection `status`. That is an operational refinement of a failed search or read, not a new v1 clinical field and not an allowlist change.

Task 057 consumes this contract as-is. The deterministic agent does not add clinical fields or call a model.

Task 058 copies the authorized contract metadata and the 057 verdict onto an AI boundary payload. It does not add clinical fields, call a model, or treat `READY` as model authorization.

Task 059 consumes that boundary in an isolated first AI component. It does not add clinical fields, call a model, or change `modelCallAuthorized=false`.

Task 060 evaluates the first AI result with an execution gate. Eligibility is not model authorization and does not add clinical fields.

Task 061 copies that gate verdict onto an internal AI Consumer Contract v1. It does not add clinical fields, dispatch the contract, or change `modelCallAuthorized=false`. See [ai-consumer-contract-v1.md](ai-consumer-contract-v1.md).

Task 062 adds a synthetic consumer policy over that contract. It does not add clinical fields, dispatch, or authorize a model. See [ai-consumer-policy.md](ai-consumer-policy.md).

Task 063 adds a readiness boundary over that policy. It does not add clinical fields, authorize handoff, or dispatch. See [ai-consumer-readiness.md](ai-consumer-readiness.md).

Task 064 adds a deny-by-default handoff authorization boundary. It does not add clinical fields, authorize handoff, or dispatch. See [ai-handoff-authorization-boundary.md](ai-handoff-authorization-boundary.md).

Task 065 adds a deny-by-default consumer authentication and authorization boundary. It does not add clinical fields or implement a real identity provider. See [ai-consumer-authorization-boundary.md](ai-consumer-authorization-boundary.md).

Task 066 adds a deny-by-default consent and purpose boundary. It does not add clinical fields or implement a real consent provider. See [ai-consumer-consent-boundary.md](ai-consumer-consent-boundary.md).

Task 067 adds a deny-by-default clinical data-scope and minimization boundary. It does not add clinical fields or grant clinical access. See [ai-consumer-data-scope-boundary.md](ai-consumer-data-scope-boundary.md).

Task 068 adds a deny-by-default clinical data-access request boundary. It does not add clinical fields or grant clinical access. See [ai-consumer-clinical-data-access-boundary.md](ai-consumer-clinical-data-access-boundary.md).

## What the stub must not know

FHIR, HAPI, Epic, Oracle, SMART, tokens, Patient IDs, or EHR URLs. Vendor adapters choose `ClinicalSnapshotContents` before the contract.

## Tests

Shared assertions live in `ModelBoundaryContractAssertions`. `OracleEpicContractCompatibilityTest` runs the same v1 rules for both destinations.
