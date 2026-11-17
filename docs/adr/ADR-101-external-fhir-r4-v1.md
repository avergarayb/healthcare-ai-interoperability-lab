# ADR-101 — One opt-in external FHIR R4 reader

## Status

Accepted for this laboratory increment. It is not a certification and it is not interoperability with Epic or Oracle.

## Context

Clinical Federation already returns a closed envelope for Mini HIS and Mini LIS. The lab-summary permit, its MCP tool, and the two-operation ledger are also closed. A public SMART R4 sandbox can supply synthetic Patient, Observation, and DiagnosticReport resources, but its logical ids are not a local identity and its host must not be chosen by a model or a browser.

## Decision

1. `external-fhir.enabled` defaults to false. The checked-in grant list does not contain `smart-sandbox`.
2. When the switch is on, one allowlisted client reads `https://r4.smarthealthit.org` with GET, TLS validation, no redirects, and no retries. The federation envelope stays `clinical-federation-v1`.
3. A local patient reaches that origin only through an explicit link. The same identifier or the same name in another system is not a match. Omitting `sources` does not select the sandbox.
4. UCUM is verified in place. Units are not converted. An observation that fails the check remains available to the audit with `unit-not-verified` and is not a model fact.
5. The AI path is a separate operation, tool, and graph. It reuses the federation client and the pending-review row. It does not reuse `lab-result-summary-v1` or `vacation-days-v1`, and it does not open the provider SDK. NeutralModelGateway execution of this operation remains pending.
6. The external request audit records the collection path and the outcome. It does not record a logical id, a response body, or a name.

## Consequences

A sandbox reset can invalidate the destination id. The live test has to discover a patient again. Production onboarding of a hospital FHIR server needs another contract. The external review is pending until a person decides it.

## References

- [External FHIR R4 v1](../contracts/external-fhir-r4-v1.md)
- [Clinical Federation v1](../contracts/clinical-federation-v1.md)
- [ADR-100](ADR-100-lab-review-iam-v1.md)
