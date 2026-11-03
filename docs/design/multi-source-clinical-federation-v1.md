# Multi-source clinical federation v1

Laboratory design for one read endpoint. It is not a master patient index and it is not a production federation platform.

## Decision

Clinical Read stays a single-source query selected by `clinical-read.source`. The default remains `local-hapi`. Federation is `POST /api/clinical-federation/v1/context`, implemented in Java, package `lab.healthcare.fhir.federation`.

The readers are the existing Mini HIS and Mini LIS connectors. Federation does not start another FHIR server and does not move connector logic into the AI Service.

## Identity

The match key is the caller system, the identifier system, and the identifier value.

- The caller source is searched with that exact identifier.
- Another source is read only when `exchange_patient_link` already maps that key to a destination logical id. The laboratory exchange writes the link when Mini HIS submits an order that Mini LIS accepts.
- No link means `identity_unresolved`. The other connector is not called, including its external-id search.
- Name, birth date, and sex are not accepted on the federation request and are not used as a fallback.

`identity_unresolved` and `complete` with `resourceCount` 0 are different. The first means the patient was not correlated. The second means the patient was correlated and the source returned no resources of the requested types.

## Provenance

The response entry carries `sourceKey`, `organizationId`, and `fullUrl`. The HTTP body is a federation envelope, not a FHIR `Bundle`. `fullUrl` uses the registry base URL so `Observation/1` from two organizations cannot be treated as one resource. `meta.source` already set by a normalizer is preserved. Relative FHIR references are rewritten to that same base URL so references inside one source stay coherent after aggregation.

A FHIR `Provenance` resource is a later increment. It is not required to tell which organization produced an entry in this version.

## Partial failure

Authorization is decided before any connector call. A source outside the caller grant fails the whole request with HTTP 403 and no clinical entries.

After authorization, one source can fail without discarding the others:

| Situation | Outcome | Query status when another source succeeded |
|---|---|---|
| Connector error or budget exhausted | `unavailable` | `partial` |
| No patient correspondence | `identity_unresolved` | `partial` |
| Patient found, no resources | `complete` | `complete` if every source completed |
| Registered, no connector | `connector_unavailable` | `partial` |
| No requested capability | `capability_unsupported` | `partial` |

If every source fails, `status` is `failed`, `entries` is empty, and HTTP status is still 200. The per-source outcomes explain the failure. HTTP 403 remains reserved for authorization.

## Security

The caller is the participant token, not the body. Grants are configuration. Checked-in grants allow Mini HIS to read Mini HIS and Mini LIS, and Mini LIS to read only itself. Operational logs record a server-trusted correlation id, caller, source key, outcome, and error code. They do not record names, result values, units, or tokens.

Security decisions use a separate `clinical_federation_access` event. Authentication is audited in the filter. Organization, caller-system, source-grant denials, and the single allowed decision are audited in `FederationService`, after validation and before connectors. The controller does not create a second audit event. Source errors and federation `partial`/`failed` results are execution outcomes, not access denials.

The event is appended to the Java-owned SQLite security-audit file before the protected operation proceeds. A failed append returns 503 and no connector is called. The file is durable across a normal single-host process restart, but it is editable by its owner, unreplicated, and not a production SIEM or immutable audit ledger. It is separate from the exchange-correlation database, Mini HIS, Mini LIS, local HAPI, and the AI Service databases.

The default file under `java.io.tmpdir` assumes one laboratory service instance and may be removed by operating-system cleanup. Concurrent service instances must use distinct configured paths; clients of one instance intentionally share that instance's audit ledger. Tests that write audit events use temporary per-test stores, and the federation flow configures its own path.

The Python federation client creates a canonical `FED-` correlation for this HTTP call. Java preserves it in the decision event, operational logs, and response, and Python logs it after a successful response. It is hop-level traceability only: the value is not inherited from the outer LangGraph workflow, checkpoint, or Human Review request.

Tokens are environment variables and are blank in `application.yml`.

## Reproduce the laboratory demo

The automated proof is the flow test. It starts PostgreSQL 16 with Testcontainers, Mini LIS, and Mini HIS on ephemeral ports, submits one synthetic order through the exchange, records one Mini LIS result, and federates both systems. Its Spring test context selects `clinical-read.source=mini-his` and assigns the unused local-HAPI URL to an inaccessible loopback port. It does not call Clinical Read, use `syn-demo-patient-102`, reuse an operator database, or contact local HAPI.

```text
mvn -f services/fhir-integration-service/pom.xml "-Dtest=FederationFlowTest,FederationServiceTest,ClinicalReadServiceTest" test
```

Docker Desktop must be running. The flow test is the multi-system evidence. `FederationServiceTest` covers identity, deduplication, authorization, a missing connector, and a timeout with fakes. `ClinicalReadServiceTest` covers the single-source service without claiming live HAPI compatibility.

### Coverage split

| Original assertion group | Responsibility | Executing test | Dependency | Expected evidence |
|---|---|---|---|---|
| Federation contract, caller and complete source outcomes | Clinical Federation | `FederationFlowTest` | Isolated Mini HIS, Mini LIS and PostgreSQL Testcontainers | `clinical-federation-v1`, `complete`, both sources complete |
| Patient, Observation and ServiceRequest counts; values and units | Normalization | `FederationFlowTest` | Synthetic per-run fixtures | Both source payloads, preserved units, no invented LOINC |
| Unique `fullUrl`, `meta.source`, rewritten references and strict parsing | Provenance and FHIR validity | `FederationFlowTest` | Ephemeral source URLs | Source-qualified entries and valid R4 resources |
| Unlinked patient and unavailable registered connector | Partial federation | `FederationFlowTest` | Isolated exchange link and unreachable synthetic registry entry | `identity_unresolved` and `connector_unavailable` without leakage |
| Valid participant, source grant, organization, caller system and anonymous request | Authentication and authorization | `FederationFlowTest` | Test-only participant tokens and per-run audit SQLite | Allowed requests plus 401/403 denials and seven ordered audit decisions |
| Clinical Read remains distinct from Federation | Contract regression | `ClinicalReadServiceTest` and controller tests | Deterministic unit/MockMvc fixtures | `clinical-read-v1` without a federation envelope |
| Default source is `local-hapi` and exact read of `syn-demo-patient-102` | Legacy HAPI compatibility | `LegacyHapiClinicalReadCompatibilityLiveIT` | Explicit, test-owned HAPI R4 server seeded by the operator of that test | Exact Patient read through `clinical-read.source=local-hapi` |

### Legacy HAPI compatibility boundary

The legacy exact-read assertion is explicitly excluded by Surefire and the default Failsafe configuration. JUnit also requires the dedicated `hapi-legacy-live` profile marker, `-Dhapi.legacy.testOwnedConfirmed=true` on the invocation and the environment opt-ins below. Other live profiles leave the HAPI profile marker false. Inherited HAPI environment variables alone cannot activate this test, even with the dedicated profile, because ownership confirmation defaults to false.

Before supplying the command-line ownership confirmation, the operator must verify that the URL and port belong to an independently managed HAPI R4 server dedicated to this test, with its own storage and the synthetic Patient `syn-demo-patient-102`. Loopback and boolean flags do not establish infrastructure ownership. Never point this test to the repository's preexisting `local-hapi` containers or any operator-owned server. The class only reads: it does not provision, seed, delete or modify HAPI resources.

```powershell
$env:HAPI_LEGACY_LIVE_IT='true'
$env:HAPI_LEGACY_TEST_OWNED='true'
$env:HAPI_LEGACY_BASE_URL='http://127.0.0.1:<dedicated-port>/fhir'
mvn -f services/fhir-integration-service/pom.xml verify -Phapi-legacy-live "-Dhapi.legacy.testOwnedConfirmed=true"
```

Leave the test omitted when those ownership, fixture and isolation requirements are not met. It checks the existing Clinical Read adapter against a real HAPI endpoint; a stub would prove only HTTP/contract behavior. A later task may provision a dedicated HAPI Testcontainers fixture, but image choice, readiness, seeding and cleanup are outside this increment.

A manual call, after the tokens and both simulators are running and an exchange order has created the patient link:

```text
POST /api/clinical-federation/v1/context
X-Service-Token: <FEDERATION_MINI_HIS_TOKEN>
```

Use the request in [the contract](../contracts/clinical-federation-v1.md). Do not put the token in the repository.

## Later AI integration

LangGraph and `ClinicalReadClient` continue to call Clinical Read v1. A later client can post to this endpoint with the organization participant token and branch on `status`. That client is not part of this increment.

## Not implemented

A general master patient index, reverse resolution from an arbitrary Mini LIS id to Mini HIS unless that direction was stored, parallel fan-out, FHIR `Provenance` resources, pagination beyond the entry cap, and federation reads from a registry row that has no connector.
