# FHIR notes

Local FHIR R4 server for this lab is HAPI FHIR, started from `infra/docker/docker-compose.yml`.

- Base URL: `http://localhost:8080/fhir`
- Capability Statement: `GET /metadata`

Persistence is PostgreSQL. HAPI configuration stays under `infra/docker/` and is not part of `fhir-integration-service`.

`fhir-integration-service` is a Java FHIR **client**. See [fhir-client.md](fhir-client.md) for `/metadata`, [fhir-search.md](fhir-search.md) for Patient read/search, [fhir-resources-and-references.md](fhir-resources-and-references.md) for Observation, Condition, and `Reference`, [fhir-include-revinclude.md](fhir-include-revinclude.md) for `_include` and `_revinclude`, [fhir-crud-write-operations.md](fhir-crud-write-operations.md) for create, update, and delete, [fhir-advanced-search.md](fhir-advanced-search.md) for multiple parameters, modifiers, date prefixes, `_sort`, and `_count`, [fhir-search-chaining.md](fhir-search-chaining.md) for chained search and `_has`, [fhir-terminology-and-validation.md](fhir-terminology-and-validation.md) for CodeSystem, ValueSet, Coding, and `$validate-code`, [fhir-validation-and-profiles.md](fhir-validation-and-profiles.md) for `$validate`, StructureDefinition, and profiles, [fhir-bundles-transactions.md](fhir-bundles-transactions.md) for Bundle transaction and batch, and [fhir-pagination.md](fhir-pagination.md) for paged `searchset` results.
