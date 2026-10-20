# ADR-095 — Clinical normalization boundary and commercial composition

## Status

Accepted

## Date

2026-10-15. Laboratory reconciliation recorded 2026-10-16. Status remains Accepted. The commercial target below is unchanged.

## Context

[ADR-084](ADR-084-product-identity-and-architectural-units.md) made Healthcare Interoperability (Java) and Healthcare AI (Python; commercial name Healthcare AI Agents) independently deployable units that may also be composed. It left multi-protocol connectors open. [ADR-085](ADR-085-python-follow-up-fhir-and-model-authority-boundary.md) accepts the bounded Patient, Encounter, Observation, and Appointment reads that Follow-up Review performs, and it keeps protocol authority in the application. [ADR-083](ADR-083-product-and-local-fhir-packaging.md) keeps the HAPI Docker stack as local laboratory support, not the product EHR.

This decision records the commercial connectivity target. The 2026-10-15 text did not add a connector. Later laboratory commits added a bounded Clinical Read path. Those commits do not implement the broker described in the target.

## Implemented today

Implemented means present in source. This ADR does not record a test execution.

- Java remains a FHIR R4 client for Epic sandbox, Oracle Health sandbox, and `local-hapi`. It publishes Model Boundary v1 for destinations that can build that contract. Other configured FHIR destinations fail closed for that contract. There is no SOAP, HL7 v2, or file connector, and no exchange route among organizations.
- Java exposes read-only [Clinical Read API v1](../contracts/clinical-read-v1.md), `GET /api/clinical-read/v1`, for Patient, Encounter, Observation, and Appointment. The same `X-Service-Token` used by Model Boundary v1 protects it. `clinical-read.source` defaults to `local-hapi`. HAPI in `infra/docker` remains an available local origin and the laboratory FHIR repository. It is not a customer HIS and not required for every read.
- When `clinical-read.source` is `mini-his`, Java reads the Mini HIS Simulator over proprietary REST and normalizes that JSON to FHIR R4 structures. The simulator is a separate process with its own SQLite database. It is not part of the HAPI Docker stack and it is not this exchange platform. The normalization contract is [mini-his-terminology-v1](../contracts/mini-his-terminology-v1.md): status, class, and category maps `mini-his-maps-v1`, plus UCUM maps `mini-his-ucum-v1` for `g/dL` and `mmHg` only.
- Python still consumes Model Boundary v1 through `GET /internal/agent-context`. Python has no client for a customer HIS protocol. The operational factories `build_live_followup_workflow`, the missed-follow-up service factory, and `clinical_review_context_http` (including the open-case page reader) acquire Patient, Encounter, Observation, and Appointment through `ClinicalReadClient` and Clinical Read API v1. `HapiReadClient` and `FHIR_BASE_URL` remain in the Python tree. That retirement is not closed. The resource set and the model boundary in ADR-085 stay in force.

## Target architecture

1. A customer HIS, EHR, or ERP may be integrated through FHIR, proprietary REST, SOAP, HL7 v2, or files.
2. Java owns those connectors and the transformation, validation, and normalization of clinical data to FHIR R4.
3. Python consumes that normalized clinical data. It does not take a dependency on the proprietary protocol of each HIS.
4. The Java normalization engine is not required to call a FHIR server. A FHIR server remains one possible source or destination, not a prerequisite of normalization.
5. HAPI FHIR Docker remains the laboratory repository. In the exchange target it is optional, not a mandatory hop.
6. The Mini HIS Simulator keeps its own persistence and synthetic data. Its interface is a proprietary REST API. Java may read that laboratory API and normalize it, as recorded above. Later versions may simulate the other ingress protocols. The simulator is not HAPI and it is not the exchange platform.
7. Healthcare Interoperability and Healthcare AI Agents stay separately sellable. An integrated offer is optional composition of the two units, not a third runtime. Pricing and SKU names remain undecided (ADR-084).

### Bidirectional exchange platform

Healthcare Interoperability is, as a target, an independent platform for authorized exchange among healthcare organizations. Healthcare AI is an optional consumer of normalized clinical data. It is not a dependency of the exchange. A FHIR server, including HAPI, is an optional repository or endpoint, not a mandatory part of every hop.

The organizations in scope are clinics, hospitals, EPS, insurers, pharmacies, laboratories, and other systems that an agreement authorizes. Each integration is limited by that agreement, by the permissions granted, and by the technical capability of the remote system. The platform does not assume that every party offers the same protocol or the same operations.

The target connector set is FHIR, proprietary REST, SOAP, HL7 v2, and files. Java owns inbound and outbound transformation between those protocols, and FHIR R4 normalization when the clinical content is normalized. Not every technical acknowledgement or file hop has to be stored as a FHIR resource. The platform also owns routing, validation, traceability, audit, and authorization controls for those exchanges.

None of that broker is implemented. The laboratory surface is the FHIR client, Model Boundary v1, Clinical Read API v1, and the Mini HIS normalizer behind one configured source. `FhirService` write methods exist for integration tests; they are not an organizational write API. Tasks 057–073 remain the simulation surface in ADR-079, not exchange controls.

ADR-085 still bounds which resources Follow-up Review may acquire and who owns the protocol decision. The operational factories now call Java for that acquisition instead of calling HAPI directly. This decision does not authorize a Python client for a proprietary HIS. What remains of `HapiReadClient` is recorded in [the Python–HAPI decoupling assessment](../design/python-hapi-decoupling-assessment-v1.md). Model Boundary v1 does not close that gap and is not Clinical Read API v1.

## Consequences

Java is the only unit that grows a protocol matrix. Python can be sold against normalized clinical data without one adapter per HIS. The exchange platform does not require Healthcare AI. HAPI stays the laboratory store and is optional in the target exchange. The operational follow-up factories depend on Clinical Read API v1. With the default source they still need the local HAPI endpoint behind Java. They do not need a direct Python FHIR URL.

## Non-goals

No Auth0, tenancy, or claim that SOAP, HL7 v2, file, or organizational exchange connectors exist. Model Boundary v1 and its `X-Service-Token` stay as they are; Clinical Read reuses that header and does not replace the v1 contract. The Mini HIS Simulator is a local stand-in. Reading it is not a customer connector and not the bidirectional broker.

## Related decisions

- ADR-083 — HAPI remains the local FHIR support pack
- ADR-084 — separate or composed product units
- ADR-085 — follow-up resource set and model authority; operational acquisition now goes through Clinical Read
