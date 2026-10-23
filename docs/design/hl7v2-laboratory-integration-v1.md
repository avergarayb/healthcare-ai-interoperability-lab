# HL7 v2 laboratory integration v1

## Decision

HL7 v2.5.1 is a second protocol between FHIR Integration Service and Mini LIS. Mini HIS still submits the current JSON order. Java builds the canonical FHIR R4 ServiceRequest, then the selected connector turns that command into either the existing REST call or an `OML^O21`. The default protocol stays `rest`.

Mini LIS parses `OML^O21` and calls `LaboratoryRecordService`. It does not keep a second copy of the order rules and it does not gain a second database. An accepted order is answered with `ORL^O22`, which carries the LIS order id in `ORC-3` and the LIS patient id in `PID-3`. A rejection stays an `ACK`. A committed result publishes one `ORU^R01` over MLLP. Java checks the correlation, stores the result, and answers `ACK`. If that publication fails, the result remains in Mini LIS and can be sent again with the same message control id. The later Mini HIS read returns FHIR `Observation` and `DiagnosticReport` built with the same Mini LIS mapping used by REST. No LOINC or UCUM equivalence is invented.

The order exchange is synchronous. The result publication is synchronous at the moment the laboratory records the result, and it is asynchronous relative to the original order. Mini HIS does not receive an unsolicited HL7 message.

## What this version does not do

- It does not implement ORM, a broker, TLS, or a second HAPI FHIR server.
- It does not let Mini HIS speak HL7.
- It does not federate Clinical Read. Selecting `mini-lis` still replaces the single source.
- It does not make MLLP safe for an open network. The listener is loopback-only and the shared secret is not encrypted on that socket.
- `AA` confirms storage of the message. It does not confirm that the assay or a clinical review is complete.

## Extension

A later system adds a connector that implements `OrderDestination` and `ResultSource`. This profile's message builder can be reused. The domain write remains `LaboratoryRecordService`.

Contract: [hl7v2-laboratory-v1](../contracts/hl7v2-laboratory-v1.md).
