# HL7-002 hospital laboratory v1

Synthetic hospital order and result flow. This contract selects the laboratory profile already implemented in [hl7v2-laboratory-v1](hl7v2-laboratory-v1.md). It does not add a second integration engine, a second federation, or a third clinical agent.

## Selected messages

HL7 v2.5.1 over loopback MLLP, which this repository already requires for the optional Mini LIS connector. REST remains the default exchange protocol.

| Message | Use |
|---|---|
| `OML^O21` | New laboratory order. `ORC-1` is `NW` |
| `ORL^O22` | Application accept of that order. `AA` means the order was stored, or the same order was already stored. It does not mean the assay is complete |
| `ORU^R01` | One result after Mini LIS commits it |
| `ACK` | Rejection of an order, or the reply to an `ORU^R01` |

`ORM^O01` is not selected. The existing laboratory path already completes the order with `OML^O21`.

Required segments stay those of the existing profile: `MSH`, `PID`, `ORC`, `OBR`, and `OBX` on the result. `SPM` is not used. The profile does not put LOINC or UCUM in the HL7 message. FHIR projection adds UCUM only through the existing `mini-lis-ucum-v1` map. It does not invent LOINC.

## Identity

A message is not identified by `MSH-10` alone. The inbound key is:

- `MSH-3` sending application
- `MSH-4` sending facility
- `ORC-21-10` requesting organization
- `MSH-10` message control id

The same key and the same clinical order return the stored decision and do not create another order. The clinical order is the organization, patient identifier, placer order id, test code, description, and requested time. `MSH-7` is not part of that comparison. The same key with a different clinical order is `AE` `contradictory_message`. That rejection is not stored, so the original decision remains. A different organization may use the same control id. The listener still accepts only organizations on its allowlist, and the checked-in allowlist is `org-mini-his`.

`MSH-8` still authenticates the sending system together with `MSH-3` and `MSH-4`. An unauthenticated message is not stored.

## Correlation

The exchange store already links:

- Mini HIS order id
- HL7 message control id
- Mini LIS order id
- Mini LIS result id
- FHIR `ServiceRequest`, `Observation`, and `DiagnosticReport` ids

`Observation.basedOn` references the Mini LIS `ServiceRequest`. `DiagnosticReport.basedOn` references that same request, and `DiagnosticReport.result` references the observation. A report read before any result has an empty result list.

## What this increment does not retarget

Clinical Federation already reads Mini HIS and Mini LIS when the patient link exists. The summary agent `lab-result-summary-v1` still requires one final observation from each of those two sources, and its permit stays bound to `org-mini-his` and `MHS-PAT-001`. Peru and Spain keep their jurisdiction profiles. Those profiles do not speak HL7, and this contract does not point the summary permit at them. A second country on this hospital path needs its own process, organization, allowlist, and store. It is not a second row in the current Mini HIS organization.

Human Review of the summary cites the validated observation. The order correlation remains in the exchange store. This increment does not put the raw HL7 message or a patient name into the model context.

No real provider call is authorized. The path is not RENHICE, HCDSNS, or EHDS conformance.

## What was executed

HL7-002 demonstrated the hospital exchange with the existing synthetic organization `org-mini-his`. One isolated case created a Mini HIS order, sent `OML^O21` over loopback MLLP, persisted it in Mini LIS, returned `ORU^R01`, and projected `ServiceRequest`, `DiagnosticReport`, and `Observation`. Clinical Federation read that exchange, status `complete`, with UCUM on the hemoglobin already seeded in Mini HIS and on the glucose produced by Mini LIS. MCP delivered the minimized chart to the existing `lab-result-summary-v1` graph. `NeutralModelGateway` used one intercepted call. Human Review stored the pending summary and one later human decision. The raw HL7 message was not copied into the model context.

The receipt `ServiceRequest` keeps the Mini HIS order id. `DiagnosticReport` and the result `Observation` use the Mini LIS order and result ids. `Observation.basedOn` points at `ServiceRequest/{lisOrderId}`. The exchange store and the Mini LIS inbound row connect the HIS order, the `OML^O21` control id, and the `ORU^R01` control id.

MULTI-COUNTRY-001 demonstrates independent clinical configurations for Peru and Spain. Combining that configuration with this HL7 path for a concrete hospital requires that hospital's organization, connectors, and permits. This contract does not claim an HL7 end-to-end run for Peru or Spain.

Rows already stored with an empty payload digest keep the previous replay behavior. `MSH-8` and the MLLP listener stay on loopback.
