# ADR-103 — Jurisdiction laboratory demonstration

## Status

Accepted for this laboratory increment. It does not authorize national conformance, a live provider call, or cross-border exchange.

## Context

Peru and Spain are the first demonstration jurisdictions. CorePE 0.1 is a draft and is not a valid NPM package version. HL7 Europe Base and Core 2.0.0 is an informative reference; the publisher's current version is 2.0.1. IPS 2.0.1 describes a document, not a laboratory-only observation set. No Spanish national FHIR profile is published in this repository. Epic remains the historical sandbox already in main.

## Decision

1. One Clinical Federation and one `JurisdictionLabGraph` serve the server-selected profile. The browser and the model do not choose the jurisdiction, the organization, or the policy.
2. The closed profiles are `pe-lab-demo-v1` and `es-lab-demo-v1`. A process enables at most one. A request that names both jurisdiction sources is `cross_border_denied`.
3. Validation class is `internal-demo-rules`. FHIR R4 structural checks are tagged `fhir-r4-checked`. Official profile validation is false. A resource that claims a CorePE, HL7 Europe, or IPS canonical is `profile_not_verified`.
4. Ledger schema 8 adds `jurisdiction-lab-summary-v1` with `pe-lab-demo-policy-v1` or `es-lab-demo-policy-v1`. Schema 7 does not accept those pairs. An external or clinical permit cannot spend this operation.
5. New reviews store cited observation evidence from the validated chart. The generated summary row stays immutable. Historical reviews stay readable when the evidence table is absent.
6. The model transport stays intercepted. `request_real_provider_send()` stays closed.

## Consequences

The same technical path can demonstrate Peru and Spain without a second gateway or a second agent. It does not implement RENHICE, HCDSNS, EHDS, ENS, or GDPR operations. Those obligations remain future work: legal basis, data-protection roles, retention, patient rights, national terminology services, and conformance certification.

## References

- [jurisdiction-lab-demo-v1](../contracts/jurisdiction-lab-demo-v1.md)
- CorePE 0.1 draft: https://dyaku.minsa.gob.pe/guides/index.html
- HL7 Europe Base and Core 2.0.0: https://hl7.eu/fhir/base/2.0.0/
- IPS 2.0.1: https://hl7.org/fhir/uv/ips/2.0.1/en/
