# FHIR notes

Local FHIR R4 server for this lab is HAPI FHIR, started from `infra/docker/docker-compose.yml`.

- Base URL: `http://localhost:8080/fhir`
- Capability Statement: `GET /metadata`

Persistence is PostgreSQL. HAPI configuration stays under `infra/docker/` and is not part of `fhir-integration-service`.

`fhir-integration-service` is a Java FHIR **client**. See [fhir-client.md](fhir-client.md) for `/metadata`, [fhir-search.md](fhir-search.md) for Patient read/search, [fhir-resources-and-references.md](fhir-resources-and-references.md) for Observation, Condition, and `Reference`, and [fhir-include-revinclude.md](fhir-include-revinclude.md) for `_include` and `_revinclude`.
