# HL7 v2 laboratory profile v1

Synthetic laboratory messages only. Version HL7 v2.5.1. Transport is MLLP without TLS. This is not a production interface and it does not replace the REST exchange. The checked-in connector protocol remains `rest`.

## Messages

| Message | Direction | Meaning of ACK |
|---|---|---|
| `OML^O21` | FHIR Integration Service to Mini LIS | Accepted orders are answered with `ORL^O22`. `AA` means the order was stored, or the same placer order already existed. It does not mean the assay is complete |
| `ORU^R01` | Mini LIS to FHIR Integration Service, after a result commits | `AA` means the interoperability service stored that one result. It does not mean a clinician reviewed it |
| `ORL^O22` | Mini LIS to FHIR Integration Service, only for an accepted `OML^O21` | `ORC-3-1` is the LIS order id and `PID-3-1` is the LIS patient id. `MSA-3` is empty, or the text `duplicate` |
| `ACK` | Reply to a rejected order or to an `ORU^R01` | `AA` accept, `AE` application rejection, `AR` reject for authentication, structure, or an unsupported type |

One MLLP connection carries one message and one ACK. The order hop is synchronous: Mini HIS waits for Java, and Java waits for the ACK. The result hop is also a synchronous MLLP exchange, but it happens later, when Mini LIS records the result. Mini HIS still reads the stored FHIR report afterwards.

## OML^O21

Required:

- `MSH-3` `FHIR-EXCHANGE`, `MSH-4` `fhir-integration-service`
- `MSH-5` `MINI-LIS`, `MSH-6` `org-mini-lis`
- `MSH-8` shared secret. A blank secret is rejected
- `MSH-9` `OML^O21`, `MSH-10` message control id, `MSH-11` `P`, `MSH-12` `2.5.1`
- `PID-3-1` patient identifier, `PID-3-4` requesting organization
- `PID-5` name, `PID-7` date of birth, `PID-8` `F`, `M`, or `U`
- `ORC-1` `NW`, `ORC-2-1` placer order id, `ORC-21-10` requesting organization identifier
- `OBR-4-1` test code, `OBR-4-2` description, `OBR-4-3` local test system, `OBR-7` requested time

`MSH-4` authenticates the sending system only together with `MSH-3` and `MSH-8`. The requesting organization is `ORC-21-10`, and it must be on the listener allowlist and equal `PID-3-4`. The patient match is organization plus identifier. The name is stored only when the patient is created.

Not supported: `ORM`, specimens, `SPM`, ordering provider, LOINC, and UCUM. A code system containing `loinc` or `ucum` is rejected. Extra segments are ignored only when the required fields above are present and valid.

An accepted order returns `ORL^O22`, not a structured string in `MSA-3`. `ORC-1` is `OK`, `ORC-2-1` repeats the placer order id, `ORC-3-1` is the LIS order id, and `PID-3-1` is the LIS patient id. `MSA-3` is empty, or the text `duplicate`. On `AE` or `AR` the reply stays `ACK` and `MSA-3` is an error code, not a clinical value.

## ORU^R01

One result per message. `MSH-10` is the Mini LIS result id, so a retry keeps the same control id.

- `ORC-1` `RE`
- `ORC-2-1` placer order id, `ORC-3-1` filler order id
- `ORC-5` order status: `SC` ordered, `IP` in progress, `CM` completed, `CA` cancelled
- `ORC-21-10` requesting organization identifier
- `OBR-4-3` `https://lab.local/mini-lis/test`
- `OBX-2` `NM` or `ST`, `OBX-3-1` test code, `OBX-3-3` the same local system
- `OBX-4` external result id, `OBX-5` original value, `OBX-6-1` original unit text with no unit system
- `OBX-7` reference range text, `OBX-11` `P`, `F`, or `X`, `OBX-14` resulted time

Java accepts the ORU only when the secret and the sending system match and the placer, filler, organization, patient identifier, and test code match the stored correlation. The name is not a match key. The value is not written to the log.

## Idempotency

The same `MSH-10` returns the stored response and does not create another order or observation. A new control id with the same placer order returns `ORL^O22`, `MSA-3` `duplicate`, and the original LIS order id in `ORC-3-1`. If the response is lost after Mini LIS commits, the retry is safe. If the ACK is lost after Java stores an ORU, the same result id returns `duplicate=true`.

The clinical result status stays `PRELIMINARY`, `FINAL`, or `CANCELLED` in Mini LIS. A failed ORU publication does not change that status and does not remove the result. The technical outcome is the publication response: `AA`, or `destination_unavailable` when the Java listener does not answer. `POST /hl7/results/{resultId}/publication` sends the same `MSH-10` again. A second acceptance does not create another observation.

## Local conventions

These uses are explicit restrictions of this profile. They are not a claim that the base standard defines them this way.

- `ORC-21-10` carries the organization id. `ORC-21-1` is the organization name in the `XON` type and stays empty.
- `PID-3-4` is the assigning authority of the patient identifier. In this profile that authority is the requesting organization.
- `ORC-5` maps the existing order enum onto table 0038: `ORDERED` `SC`, `IN_PROGRESS` `IP`, `COMPLETED` `CM`, `CANCELLED` `CA`. `SC` is the table's scheduled code for an order that has not started.
- `OBX-11` and `OBR-25` use `P`, `F`, and `X` for preliminary, final, and cancelled. Those three codes exist in both table 0085 and table 0123.
- `OBX-6-1` carries the original unit text. `OBX-6-3` stays empty because this profile does not invent a UCUM code.
- `OBX-4` carries the external result id. In the base standard `OBX-4` is the observation sub-id. v2.5.1 has no observation-instance identifier; `OBX-21` is reserved. This profile sends one `OBX` per message.
- `MSA-3` on a rejection is a profile error code. On an accepted order it is empty or the text `duplicate`. Identifiers travel in `ORC` and `PID`.

## MLLP

Both listeners bind to loopback. The HL7 listener refuses a non-loopback socket even when HTTP allows an external bind. Docker Compose publishes Mini LIS on port 8096 and does not publish 2575 or 2576. HL7 stays disabled unless `MINI_LIS_HL7_ENABLED` is set. MLLP has no TLS in this version. The shared secret travels in `MSH-8` and is visible on the local socket. Production use needs network isolation or a later TLS wrapper, a secret outside the repository, and a distinct secret per environment. The checked-in secret is blank, so an unset variable rejects every message.

Configuration:

- Mini LIS: `MINI_LIS_HL7_ENABLED`, `MINI_LIS_HL7_PORT`, `MINI_LIS_HL7_SHARED_SECRET`, `MINI_LIS_HL7_OUTBOUND_PORT`
- Java: `EXCHANGE_MINI_LIS_PROTOCOL=hl7v2`, `EXCHANGE_MINI_LIS_HL7_HOST`, `EXCHANGE_MINI_LIS_HL7_PORT`, `EXCHANGE_MINI_LIS_HL7_SECRET`, `EXCHANGE_HL7_LISTEN_PORT`

`PUT /hl7/result-peer` points the result publication at the Java listener. It requires the Mini LIS service token and a loopback address.
