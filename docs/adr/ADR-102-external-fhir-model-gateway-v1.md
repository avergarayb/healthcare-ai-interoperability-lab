# ADR-102 — External FHIR summary through the neutral gateway

## Status

Accepted for this laboratory increment. It does not authorize a live provider call.

## Context

INTEROP-001 reads one public synthetic SMART R4 sandbox and can queue a review from an injected transport. That transport is not a durable permit. `lab-result-summary-v1` and `vacation-days-v1` remain separate operations. A key in the process environment is not permission to send a chart.

## Decision

1. Ledger schema 7 accepts `external-fhir-lab-summary-v1` with `external-fhir-lab-summary-policy-v1`. Schema 6 is unchanged. A cross-pair is invalid.
2. `NeutralModelGateway.execute_external_summary` is the only model entry. The graph does not import a provider SDK. The call uses the existing Gemini adapter and deployment `gemini-sdk-a`. Another provider is not activated.
3. The organization is the constant `org-smart-sandbox`. The patient id does not select it. A partial envelope, a missing link, two patient references, or an unverified UCUM quantity does not reach the model.
4. One authorization has one reservation, one invocation, and no automatic retry. A failed send leaves the reservation held and blocks that authorization.
5. The receipt phase for this path is `intercepted`. Human Review shows that phase and does not present the text as a live Gemini response. The reviewer comes from the IAM binding for `org-smart-sandbox`.
6. `request_real_provider_send()` stays closed. A later single live request needs a new Product Owner authorization, as written in the external FHIR contract. This increment does not perform it.

## Consequences

An external summary can be audited with the same reservation and review controls as the clinical summary, without spending the clinical permit. A live Gemini or OpenAI call remains a separate decision. The historical clinical Gemini evidence is not reused.

## References

- [External FHIR R4 v1](../contracts/external-fhir-r4-v1.md)
- [ADR-101](ADR-101-external-fhir-r4-v1.md)
- [ADR-100](ADR-100-lab-review-iam-v1.md)
