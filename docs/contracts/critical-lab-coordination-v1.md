# Critical laboratory coordination v1

Laboratory contract for `critical-lab-coordination-v1`. It does not authorize a diagnosis, a treatment, an external message, or a production connection.

## Criticality

The simulation rule `sim-hemoglobin-low` version `1.0` matches LOINC `718-7` when the unit is `g/dL` and the numeric value is below `7.0`. Both the code and the unit already exist in this laboratory. Hemoglobin `13.4 g/dL` and glucose `90 mg/dL` do not match. The model never decides criticality. Mini LIS stores the event when a validated result is published, whether or not the agent is running.

## Specimen and result

Mini LIS keeps the order statuses `ORDERED`, `IN_PROGRESS`, `COMPLETED`, and `CANCELLED`. The bench adds a separate specimen case:

`ORDER_RECEIVED`, `SPECIMEN_REGISTERED`, `SPECIMEN_RECEIVED`, `PROCESSING`, `DRAFT`, `VALIDATED`, `PUBLISHED`.

A draft does not call the result writer and does not emit `ORU^R01`. Validation does not publish. Publication calls the existing result writer once. A second publication returns the same result. A correction adds another result and keeps the original event value.

## Agent

The first graph pass is `admit`, `validate_event`, `read_clinical_context`, `retrieve_protocol`, `assess_evidence`, `prepare_proposal`, `finish`. Human review and the single authorized task are later requests, so a pending proposal can be read again without a second model call. The default transport is blocked. `CRITICAL_LAB_MODEL_MODE=intercepted` returns one fixed sentence and is not a live provider.

The graph invokes `get_critical_event`, `get_lab_order`, `get_validated_lab_result`, `get_patient_encounter`, `search_clinical_protocol`, and `propose_critical_result_task` through the same in-process JSON-RPC session used by `read_federated_lab_chart`: `initialize`, `tools/list`, and `tools/call`. A direct Python function is not that session. Tool arguments cannot change the organization, the role, or the order. This contract does not add a network MCP server. A foreign organization, a missing event, or fewer than five cited protocols stores no proposal.

## Session

Mini HIS `/ward` and Mini LIS `/bench` use local laboratory sessions on loopback. They are not OIDC and they are not a second Keycloak realm. The agent accepts only the existing service token and a loopback coordinator URL. An unapproved proposal does not create the acknowledgement task. Rejection does not create it. A second apply returns the existing grant.

## Protocols

Retrieval scans the critical-lab index for the query `critical-result`. It keeps a document only when the organization matches, the status is `active`, and the system date is inside the document window. Each citation is `id@version#section` and can be checked against that file. On 2026-11-18, `org-mini-his` returns five citations. An empty query abstains. An expired text, a retired text, and another organization are not cited for that organization. Retrieved text is evidence, not a system instruction.
