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

The caller is the participant token, not the body. Grants are configuration. Checked-in grants allow Mini HIS to read Mini HIS and Mini LIS, and Mini LIS to read only itself. Logs record the correlation id, caller, source key, outcome, and error code. They do not record names, result values, units, or tokens.

Tokens are environment variables and are blank in `application.yml`.

## Reproduce the laboratory demo

The automated proof is the flow test. It starts PostgreSQL 16 with Testcontainers, Mini LIS, and Mini HIS on ephemeral ports, submits one synthetic order through the exchange, records one Mini LIS result, and federates both systems. It does not use the live Clinical Read port, the live Mini HIS database, or `POST /synthetic/reset`. `clinical-read.source` stays `local-hapi` in that process.

```text
mvn -f services/fhir-integration-service/pom.xml "-Dtest=FederationFlowTest,FederationServiceTest,ClinicalReadServiceTest" test
```

Docker Desktop must be running. The flow test is the multi-system evidence. `FederationServiceTest` covers identity, deduplication, authorization, a missing connector, and a timeout with fakes. `ClinicalReadServiceTest` covers the previous single-source service.

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
