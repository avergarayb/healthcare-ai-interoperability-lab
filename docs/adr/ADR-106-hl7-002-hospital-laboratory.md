# ADR-106 — Hospital laboratory orders stay on the existing HL7 profile

## Status

Accepted for this laboratory increment. It does not authorize a new integration engine, a production hospital interface, a live model call, or a second clinical agent.

## Context

Mini HIS, FHIR Integration Service, and Mini LIS already exchange one laboratory order as HL7 v2.5.1 `OML^O21` and one result as `ORU^R01` over loopback MLLP. REST remains the default. The inbound table treated `MSH-10` as a global primary key, so a different message that reused that control id was answered as a duplicate.

The summary agent and the Peru and Spain jurisdiction profiles are separate permits. The hospital connector is registered as `mini-his` / `org-mini-his`.

## Decision

1. HL7-002 selects the existing profile. `ORM^O01` is not added. MLLP stays the HL7 transport because the repository already uses it. No Kafka broker is added.
2. An inbound order is stored under the sending application, sending facility, requesting organization, and message control id. An identical message replays the stored decision. A different message with that key is `contradictory_message` and does not replace the order.
3. An `ORU^R01` whose control id is already stored is a duplicate only when the observation body is the same. A different body is rejected.
4. FHIR projection, Clinical Federation, MCP, and the existing agents stay as they are. A country-specific hospital stack would be another process with its own organization and store. This increment does not create that stack and does not widen `lab-result-summary-v1`.

## Consequences

A repeated control id can no longer hide a changed order. Historical rows whose digest is empty keep the previous replay behavior. The checked-in allowlist remains `org-mini-his`.

The `org-mini-his` exchange was executed through Clinical Federation, MCP, the existing summary graph, one intercepted model call, and Human Review. MULTI-COUNTRY-001 remains the Peru and Spain demonstration. Those profiles were not run on this HL7 path. A concrete hospital in either country still needs its own organization, connectors, and permits.

## References

- [hl7-002-hospital-laboratory-v1](../contracts/hl7-002-hospital-laboratory-v1.md)
- [hl7v2-laboratory-v1](../contracts/hl7v2-laboratory-v1.md)
