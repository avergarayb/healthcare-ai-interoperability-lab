# ADR-095 — Clinical normalization boundary and commercial composition

## Status

Accepted

## Date

2026-10-15

## Context

[ADR-084](ADR-084-product-identity-and-architectural-units.md) made Healthcare Interoperability (Java) and Healthcare AI (Python; commercial name Healthcare AI Agents) independently deployable units that may also be composed. It left multi-protocol connectors open. [ADR-085](ADR-085-python-follow-up-fhir-and-model-authority-boundary.md) accepts the bounded FHIR reads that Follow-up Review already performs. [ADR-083](ADR-083-product-and-local-fhir-packaging.md) keeps the HAPI Docker stack as local laboratory support, not the product EHR.

This decision records the commercial connectivity target. It does not add a connector, a simulator, or a runtime.

## Implemented today

- Java is a FHIR R4 client. It reaches Epic sandbox, Oracle Health sandbox, and `local-hapi`, and it can publish Model Boundary v1 for those destinations. Other configured destinations fail closed. There is no proprietary REST, SOAP, HL7 v2, or file connector, and no normalizer that runs without a FHIR server.
- Python consumes Model Boundary v1 through `GET /internal/agent-context`. Follow-up Review also reads Patient, Encounter, Observation, and Appointment directly from an authorized FHIR endpoint (ADR-085). Python has no client for a customer HIS protocol.
- HAPI FHIR in `infra/docker` is the laboratory FHIR repository. It is not a customer HIS and not the normalization engine.
- No Mini HIS Simulator exists in this repository.

## Target architecture

1. A customer HIS, EHR, or ERP may be integrated through FHIR, proprietary REST, SOAP, HL7 v2, or files.
2. Java owns those connectors and the transformation, validation, and normalization of clinical data to FHIR R4.
3. Python consumes that normalized clinical data. It does not take a dependency on the proprietary protocol of each HIS.
4. The Java normalization engine is not required to call a FHIR server. A FHIR server remains one possible source or destination, not a prerequisite of normalization.
5. HAPI FHIR Docker remains the laboratory repository.
6. A future Mini HIS Simulator has its own persistence and synthetic data. Its first interface is a proprietary REST API. Later versions may simulate the other ingress protocols. It is not HAPI and it is not part of this change.
7. Healthcare Interoperability and Healthcare AI Agents stay separately sellable. An integrated offer is optional composition of the two units, not a third runtime. Pricing and SKU names remain undecided (ADR-084).

The ADR-085 follow-up reads stay the implemented acquisition path until a later increment moves that capability onto normalized input. This decision does not remove them and does not authorize a new Python protocol client.

## Consequences

Java is the only unit that grows a protocol matrix. Python can be sold against normalized clinical data without one adapter per HIS. HAPI stays a laboratory store. Until the follow-up path moves, Healthcare AI still needs an authorized FHIR endpoint for that capability.

## Non-goals

No implementation. No change to Model Boundary v1, `X-Service-Token`, roadmap, fixtures, or deployment. No Auth0, tenancy, or claim that the connectors or the Mini HIS Simulator already exist.

## Related decisions

- ADR-083 — HAPI remains the local FHIR support pack
- ADR-084 — separate or composed product units
- ADR-085 — current bounded Python FHIR reads
