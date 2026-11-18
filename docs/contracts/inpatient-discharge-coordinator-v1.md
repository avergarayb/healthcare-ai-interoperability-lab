# Inpatient discharge coordinator v1

Synthetic preparation of a hospital discharge. The agent is `inpatient-discharge-coordinator-v1`. It does not diagnose, prescribe, or close the encounter.

HEALTH-004 is not on `origin/main`. This contract does not pretend that module exists. Mini HIS stays a proprietary laboratory simulator. The FHIR R4 collection is projected by the coordinator from the chart Mini HIS already stores.

## Sources

The coordinator reads one open episode of `org-mini-his` through a service token on loopback. The chart contains the episode, evolution notes, linked laboratory results, documented allergies, documented medication statements, and tasks. A note that contains an instruction-like phrase is withheld from the model context. The person still sees it in Mini HIS.

Contradictory medication statements stay in the chart and force an abstention. The coordinator does not invent a Condition or a MedicationRequest.

## Protocols

Five synthetic protocols are version `1.0`, valid for `org-mini-his` during 2026–2027: preparation, pending verification, continuity, follow-up coordination, and documentation review. Another organization and an expired text are not cited. Each citation names the protocol, the version, and the section `Human Authority`.

## Graph

LangGraph admits the organization and role, reads the chart through fixed tools, retrieves the protocols, and calls the model once. The tools are `read_episode`, `read_evolution`, `read_results`, `read_allergies`, `read_medications`, `read_tasks`, and `read_protocols`. The model does not choose the grant. The default transport is blocked. `DISCHARGE_MODEL_MODE=intercepted` uses a local draft and does not open a provider socket.

If the episode has no note, the case stays pending and the model is not called. An open ward task keeps `checklistComplete` false. `closesEncounter` is always false.

## Human authority

A clinician of `org-mini-his` may approve, reject, or request changes. The decision is stored against the proposal hash and the episode version. A second decision is `already_decided`. Approval marks the documentation accepted and leaves the episode open. Follow-up tasks are created only from the approved proposal, once. Closing the episode is a separate action in Mini HIS.

A new preparation uses a new authorization id. A consumed authorization is not reopened. Earlier proposals remain.

## Session

The ward session is a laboratory control for this simulator. It is not a second Keycloak realm and it does not replace the laboratory OIDC review used by the longitudinal demonstrations. An empty password fails closed. An auditor can read and cannot change the episode.
