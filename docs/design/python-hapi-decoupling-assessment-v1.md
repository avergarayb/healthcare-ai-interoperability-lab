# PYTHON_HAPI_DECOUPLING_ASSESSMENT_V1

Assessment only. No code, configuration, fixture, or runtime change. ADR-085 remains the implemented follow-up read decision. ADR-095 remains the target that Python consumes normalized clinical data. Model Boundary v1 is not that clinical API.

## 1. Direct Python reads of HAPI

The only HTTP FHIR client is `HapiReadClient` in `services/ai-service/app/langgraph_fhir_hapi.py`. It sends `GET` with `Accept: application/fhir+json` to `FHIR_BASE_URL`, default `http://localhost:8080/fhir`. It retries transient HTTP failures. Search follows either a HAPI page link (`_getpages`, `_getpagesoffset`, `_count`, `_bundletype`) or a same-origin resource link (`page`, `token`). Bounds are 25 per page, 4 pages, and 100 unique resources of one type. Exact reads allow only `Encounter`, `Observation`, and `Appointment`. Python does not write FHIR.

`FollowUpFHIRAdapter` (`langgraph_fhir_followup.py`) and `ClinicalReviewContextService` (`clinical_review_context.py`) are the callers. `ClientFHIRTransport` (`langgraph_fhir_client.py`) is the adapter's transport. The case identifier system is `https://lab.local/followup-case`.

| Operational entry | Classes | FHIR reads |
|---|---|---|
| `POST /internal/agent/follow-up` | `run_followup_http` → `build_live_followup_workflow` → `FollowUpWorkflow` → `PostConsultationContextReader` / `FollowUpFHIRAdapter` → `HapiReadClient`. Narrative subflow: `build_gemini_fhir_followup` on the same client. | `POST_CONSULTATION_RESULT_REVIEW_V1`. Patient search `identifier={system}\|{caseId}&_count=2`; `Patient/{id}`; `Encounter?patient=&status=finished`; `Observation?subject=&status=final`; `Appointment?patient=`. Authorized tool reads may repeat Patient, Observation, and Appointment GETs. |
| `POST /internal/agent/missed-follow-up` | `run_missed_follow_up_http` → `FollowUpFHIRAdapter(HapiReadClient)` | `MISSED_FOLLOW_UP_REVIEW_V1`. Same Patient resolution and Patient read, then Appointment search. No Gemini call during protocol evaluation. |
| `GET /internal/follow-up-review-cases/{id}/clinical-context` | `get_clinical_review_context_http` → `ClinicalReviewContextService` → `HapiReadClient` | Patient search by the same case identifier. Exact `Encounter/{id}`, `Observation/{id}`, or `Appointment/{id}` from the stored matched reference. Appointment search for the resolved patient. HTTP 404 on an exact read is absence, not a transport failure. |
| Open review-case HTML | `human_review_client._load_context` → `clinical_context_service` | Same in-process read as the clinical-context endpoint. The browser does not call HAPI. |

`GET /internal/agent-context` does not call HAPI. `consumer.py` calls Java `GET /api/model-boundary/v1` with `X-Service-Token`.

## 2. Java reads that exist

`RoutingService` is the destination-aware FHIR client used by projections. It discovers capabilities and, with resilience and audit, reads one Patient by logical id and searches Condition (`problem-list-item`, count 5), Observation (`vital-signs`, count 5), DiagnosticReport (count 5), MedicationRequest (count 5), and Patient by name (count 1). It has no Encounter operation, no Appointment operation, no identifier search, and no exact read of Encounter, Observation, or Appointment.

`ClinicalProjectionAssembler` uses those RoutingService calls. `ModelBoundaryMapper` copies the Task 042 allowlist onto `GET /api/model-boundary/v1`: patient status and resource type; condition resource type and clinical status; observation resource type and status; diagnostic report resource type and status; medication request resource type, status, and intent. There is no resource id, identifier, name, value, encounter reference, issued time, or appointment. Epic omits MedicationRequest. `local-hapi` reads only when `LOCAL_HAPI_PATIENT_ID` is set. `epic-sandbox`, `oracle-health-sandbox`, and `local-hapi` are the destinations with a projection. Other configured destinations return v1 `SNAPSHOT_UNAVAILABLE` and do not read FHIR. Laboratory HTML pages still use the Oracle projection directly.

`FhirService` also contains broader in-process searches and Patient/Observation create, update, and delete. Controllers do not expose those writes. Integration tests call them. They are not a Python contract.

The Java packages from tasks 057–073 expose `/lab/*` and `/api/*/v1` simulations. ADR-079 keeps them as an architecture-test surface. They do not read the follow-up resources.

## 3. Contracts Python still needs from Java

Model Boundary v1 cannot replace the follow-up reads. A separate read-only clinical contract is required before `FHIR_BASE_URL` can leave the operational paths. It needs at least:

- Patient search by `https://lab.local/followup-case` plus the case id, preserving the zero, one, and more-than-one outcomes.
- Patient read by logical id, including the identifier and the display name the protocol keeps.
- Encounter search by patient and `status=finished`, with id, status, and subject reference.
- Observation search by subject and `status=final`, with id, status, subject, encounter reference, and issued time. The current Java `vital-signs` search of five rows is a different query.
- Appointment search by patient, with id, status, start, and the patient reference used to classify the schedule.
- Exact read of one Encounter, Observation, or Appointment, where not found is distinct from an unavailable server.
- An explicit complete, incomplete, or unavailable collection result. Silent truncation must not become a trusted empty list. The current bounds are 25, 4 pages, and 100 resources.
- Stable ids so an existing review case can still store `Encounter/{id}`, `Observation/{id}`, and `Appointment/{id}`.

No follow-up write contract is required. Review state stays in the Python SQLite database.

## 4. Incremental migration

Each step keeps `POST_CONSULTATION_RESULT_REVIEW_V1`, `MISSED_FOLLOW_UP_REVIEW_V1`, the synthetic HAPI cases, and the human review records. v1 and `X-Service-Token` stay as they are. The new contract is additive.

1. Add the read-only Java contract against the already authorized FHIR endpoint, starting with `local-hapi`. Do not change Model Boundary v1 or the Python endpoints.
2. Compare Java and `HapiReadClient` on the existing synthetic cases. Do not replace fixtures.
3. Point missed follow-up at Java. Its read set is Patient resolution, Patient read, and Appointment search.
4. Point post-consultation acquisition, including authorized tool reads on that same client, at Java.
5. Point clinical context and the open-case HTML reader at Java.
6. Remove `FHIR_BASE_URL` from those paths only after the same synthetic cases and open review cases still match.

## 5. Operational flows and historical experiments

Operational HAPI readers are the two follow-up endpoints, clinical context, and the open review-case page. Operational paths that do not read HAPI are `GET /internal/agent-context`, review queue and case read, close, coordination, institutional retrieval, and the development review session.

Historical or non-operational FHIR-adjacent code: `POST /internal/experimental-summary` (fixture `SYN-076-001`, no FHIR), Java tasks 057–073, sandbox HTML diagnosis pages, and `FhirService` write methods used by integration tests. Those are not the migration queue. The LangGraph loop inside `POST /internal/agent/follow-up` is operational: the application owns acquisition, and the model does not choose the protocol outcome.

## 6. What this assessment does not claim

Moving these reads to Java does not create the bidirectional exchange platform in ADR-095. It does not make Model Boundary v1 a clinical API. It does not authorize Python to call a proprietary HIS protocol.
