# ADR-095 — Clinical normalization boundary and commercial composition

## Status

Accepted

## Date

2026-10-15

## Context

[ADR-084](ADR-084-product-identity-and-architectural-units.md) made Healthcare Interoperability (Java) and Healthcare AI (Python; commercial name Healthcare AI Agents) independently deployable units that may also be composed. It left multi-protocol connectors open. [ADR-085](ADR-085-python-follow-up-fhir-and-model-authority-boundary.md) accepts the bounded FHIR reads that Follow-up Review already performs. [ADR-083](ADR-083-product-and-local-fhir-packaging.md) keeps the HAPI Docker stack as local laboratory support, not the product EHR.

This decision records the commercial connectivity target. It does not add a connector, a simulator, or a runtime.

## Implemented today

- Java is a FHIR R4 client. It reaches Epic sandbox, Oracle Health sandbox, and `local-hapi`, and it can publish Model Boundary v1 for those destinations. Other configured destinations fail closed. There is no proprietary REST, SOAP, HL7 v2, or file connector, and no normalizer that runs without a FHIR server. There is no exchange route among organizations.
- Python consumes Model Boundary v1 through `GET /internal/agent-context`. Follow-up Review also reads Patient, Encounter, Observation, and Appointment directly from an authorized FHIR endpoint (ADR-085). Python has no client for a customer HIS protocol.
- HAPI FHIR in `infra/docker` is the laboratory FHIR repository. It is not a customer HIS and not the normalization engine.
- The Mini HIS Simulator is a separate local process with its own SQLite database and a proprietary REST API. Java does not read it. It is not this exchange platform.

## Target architecture

1. A customer HIS, EHR, or ERP may be integrated through FHIR, proprietary REST, SOAP, HL7 v2, or files.
2. Java owns those connectors and the transformation, validation, and normalization of clinical data to FHIR R4.
3. Python consumes that normalized clinical data. It does not take a dependency on the proprietary protocol of each HIS.
4. The Java normalization engine is not required to call a FHIR server. A FHIR server remains one possible source or destination, not a prerequisite of normalization.
5. HAPI FHIR Docker remains the laboratory repository. In the exchange target it is optional, not a mandatory hop.
6. The Mini HIS Simulator has its own persistence and synthetic data. Its interface is a proprietary REST API. Later versions may simulate the other ingress protocols. It is not HAPI, Java does not read it, and it is not part of this change.
7. Healthcare Interoperability and Healthcare AI Agents stay separately sellable. An integrated offer is optional composition of the two units, not a third runtime. Pricing and SKU names remain undecided (ADR-084).

### Bidirectional exchange platform

Healthcare Interoperability is, as a target, an independent platform for authorized exchange among healthcare organizations. Healthcare AI is an optional consumer of normalized clinical data. It is not a dependency of the exchange. A FHIR server, including HAPI, is an optional repository or endpoint, not a mandatory part of every hop.

The organizations in scope are clinics, hospitals, EPS, insurers, pharmacies, laboratories, and other systems that an agreement authorizes. Each integration is limited by that agreement, by the permissions granted, and by the technical capability of the remote system. The platform does not assume that every party offers the same protocol or the same operations.

The target connector set is FHIR, proprietary REST, SOAP, HL7 v2, and files. Java owns inbound and outbound transformation between those protocols, and FHIR R4 normalization when the clinical content is normalized. Not every technical acknowledgement or file hop has to be stored as a FHIR resource. The platform also owns routing, validation, traceability, audit, and authorization controls for those exchanges.

None of that broker is implemented. The implemented surface remains the FHIR client, Model Boundary v1, and the ADR-085 Python reads. `FhirService` write methods exist for integration tests; they are not an organizational write API. Tasks 057–073 remain the simulation surface in ADR-079, not exchange controls.

The ADR-085 follow-up reads stay the implemented acquisition path until a later increment moves that capability onto normalized input. This decision does not remove them and does not authorize a new Python protocol client. The gap between those reads and the current Java contracts is recorded in [the Python–HAPI decoupling assessment](../design/python-hapi-decoupling-assessment-v1.md). Model Boundary v1 does not close that gap.

## Consequences

Java is the only unit that grows a protocol matrix. Python can be sold against normalized clinical data without one adapter per HIS. The exchange platform does not require Healthcare AI. HAPI stays the laboratory store and is optional in the target exchange. Until the follow-up path moves, Healthcare AI still needs an authorized FHIR endpoint for that capability.

## Non-goals

No implementation. No change to Model Boundary v1, `X-Service-Token`, roadmap, fixtures, or deployment. No Auth0, tenancy, or claim that the exchange connectors already exist. The Mini HIS Simulator is a local stand-in, not a connector.

## Related decisions

- ADR-083 — HAPI remains the local FHIR support pack
- ADR-084 — separate or composed product units
- ADR-085 — current bounded Python FHIR reads
