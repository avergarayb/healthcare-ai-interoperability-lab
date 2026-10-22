# E2E_INTEROPERABILITY_VALIDATION_V1

Design only. No test is executed by this document. No service, fixture, contract, or dependency changes.

HEAD at the time of writing: `1fd497adb0c50a3118632f6c78094caf033e0ab6` on `feature/follow-up-agent`.

## 1. Objective and scope

Prove, on a later execution, that one laboratory path works across three processes:

```text
Mini HIS proprietary REST
        -> Java Clinical Read API v1
        -> Python ClinicalReadClient
        -> Follow-up Agent
```

In scope:

- `clinical-read.source=mini-his` only.
- Synthetic rows already in `SyntheticSeed`.
- `MISSED_FOLLOW_UP_REVIEW_V1` through `POST /internal/agent/missed-follow-up`.
- The open review case that this protocol creates, then `GET /internal/follow-up-review-cases/{id}/clinical-context`.
- Normalization and UCUM behavior visible on the Java envelope.

Out of scope for a closed laboratory run:

- HAPI, Epic, Oracle, and Model Boundary v1 as the system under test.
- `POST /internal/agent/follow-up`. `FollowUpWorkflow.run` calls the narrative engine after protocol evaluation unless the status is `UNAVAILABLE`. That engine requires `GEMINI_API_KEY` when it loads a model (`langgraph_gemini_fhir_followup.py`). A missing key is an external dependency, not a Mini HIS result.
- Changing seed data to force a post-consultation match. The current normalizer emits `Encounter.period.start` and `Observation.effectiveDateTime`. It does not emit `Encounter.period.end` or `Observation.issued`. `evaluate_post_consultation_review` cannot reach `matched` on that shape.
- The untracked files `scripts/fhir/syn-*-012.json`, `docs/contracts/java-interoperability-readiness-v1.md`, and `docs/design/mini-his-simulator-v1.md`.

A unit test or a mock of `ClinicalReadClient` is not evidence for this design.

## 2. Architecture under test

| Process | Module | Default bind | Role in this design |
|---|---|---|---|
| Mini HIS Simulator | `services/mini-his-simulator` | `127.0.0.1:8095` | Proprietary JSON and its own SQLite file. No FHIR media type. |
| Healthcare Interoperability | `services/fhir-integration-service` | port `8081` | `GET /api/clinical-read/v1`. Header `X-Service-Token`. |
| Healthcare AI | `services/ai-service` | `AI_SERVICE_PORT` default `8090` | `ClinicalReadClient` uses `MODEL_BOUNDARY_BASE_URL` and the same token. |

`clinical-read.source` defaults to `local-hapi`. The Mini HIS branch in `ClinicalReadService` returns before `requireHapiSource`, so a down HAPI process is not part of this path. Python has no Mini HIS URL.

Contract version on every success body: `clinical-read-v1`. Destination for this source: `mini-his`.

Authentication: `ClinicalReadServiceAuthFilter` on `/api/clinical-read/v1/*`. The expected secret is `MODEL_BOUNDARY_SERVICE_TOKEN`. The source constant `ModelBoundaryServiceTokenSettings.TEST_DUMMY` is `test-model-boundary-token`. A blank token fails closed with HTTP 401 and an empty body. Python follow-up routes use the same header and return HTTP 401 with an empty body when `authenticate` fails. `FOLLOWUP_AGENT_ENABLED` must be `true`; otherwise those routes return HTTP 503 `Follow-up agent is disabled`.

## 3. Inventory of existing tests

These classes exist in the tree. This design does not claim that they were executed while the design was written.

| Level | Location | What it covers | What it does not cover |
|---|---|---|---|
| Unit / in-process HTTP | `MiniHisSimulatorTest`, `MiniHisSchemaMigrationTest` | Simulator schema and proprietary API | Java and Python |
| Unit / embedded HTTP | `MiniHisConnectorTest` | Java normalizer and connector against a local test server | A real Mini HIS process |
| Unit | `StaticTerminologyRegistryTest`, `StaticQuantityUnitRegistryTest` | The two map sets | A live observation |
| Unit | `ClinicalReadServiceTest`, `ClinicalReadControllerTest`, `ClinicalReadAuthUnconfiguredTest` | Envelope, errors, auth filter | Mini HIS process |
| Unit | `test_clinical_read_client.py`, `test_missed_follow_up_review.py`, `test_missed_follow_up_service.py` | Python client and protocol with stand-ins | Java and Mini HIS processes |
| Unit | `test_langgraph_followup_workflow.py` and the other `test_followup_*.py` files | Post-consultation and review persistence with stand-ins | The three-process path |

No committed end-to-end test starts Mini HIS, Java, and Python together.

## 4. Scenario matrix

Levels:

- **HTTP.** Mini HIS process and Java process. Python is not running.
- **E2E.** Those two plus the Python process and a temporary review SQLite file.

Shared preconditions for every HTTP and E2E row:

- A new SQLite file outside the repository, passed as `mini-his.sqlite-path`. `MiniHisStore.ensureReady` calls `insertSeed()` when patient, consultation, and clinical-result counts are all zero.
- Java started with `clinical-read.source=mini-his` and `clinical-read.mini-his.base-url` pointing at that Mini HIS.
- The same disposable token on Java `MODEL_BOUNDARY_SERVICE_TOKEN` and, for E2E rows, on Python.
- Ports that are free. The defaults are 8095, 8081, and 8090. If one is already listening, use another loopback port and point the next process at it. Do not stop a process that was already listening.
- HAPI is not started for these rows.

Appointment `start` is not a stored instant. `AppointmentStart.atOffset` resolves it at read time as the UTC date of the simulator clock plus the offset, at `12:00Z`. Past offset is `-400` days. Future offset is `400` days. Acceptance compares the returned instant with that rule on the clock used during the run. It does not expect a fixed calendar date.

### E2E-HTTP-01 Patient read

- Objective: one synthetic patient survives Mini HIS and the Java envelope.
- Data: `MHS-PAT-001`, family `Quispe`, given `Ana`, birth `1984-03-12`, sex `female`.
- Services: Mini HIS, Java.
- Command shape: `GET /api/clinical-read/v1/patients/MHS-PAT-001` with `X-Service-Token` and `Accept: application/json`.
- Expected: HTTP 200. `contractVersion` `clinical-read-v1`. `destination` `mini-his`. `resource.resourceType` `Patient`. `id` `MHS-PAT-001`. `gender` `female`. `birthDate` `1984-03-12`. `name[0].family` `Quispe`. `name[0].given[0]` `Ana`. Identifier system `https://lab.local/mini-his/patient` value `MHS-PAT-001`.
- Acceptance: those fields match the seed. No proprietary wrapper remains inside `resource`.
- Evidence: status line and the Patient JSON, token redacted.

### E2E-HTTP-02 Case identifier search

- Objective: the follow-up case id resolves to exactly one Mini HIS patient.
- Data: `PATIENT_IDENTIFIERS` row system `https://lab.local/followup-case`, value `SYN-FOLLOWUP-013`, patient `MHS-PAT-004`.
- Services: Mini HIS, Java.
- Command shape: `GET /api/clinical-read/v1/patients?identifierSystem=https://lab.local/followup-case&identifierValue=SYN-FOLLOWUP-013`.
- Expected: HTTP 200. `collectionStatus` `complete`. `resourceType` `Patient`. One resource, `id` `MHS-PAT-004`. That resource also carries the proprietary identifier `https://lab.local/mini-his/patient` / `MHS-PAT-004`. `MiniHisRestSource.searchPatients` rejects a truncated list or more than one row as `invalid_source`.
- Acceptance: one patient, both identifiers, collection complete.
- Evidence: the search envelope.

### E2E-HTTP-03 Encounter

- Objective: a consultation becomes one finished ambulatory Encounter.
- Data: `MHS-CON-001`, patient `MHS-PAT-001`, status `completed`, class `ambulatory`, instant `2026-09-01T15:00:00Z`.
- Services: Mini HIS, Java.
- Command shape: `GET /api/clinical-read/v1/encounters/MHS-CON-001` and `GET /api/clinical-read/v1/encounters?patient=MHS-PAT-001&status=finished`.
- Expected from `mini-his-maps-v1`: status `finished`. Class system `http://terminology.hl7.org/CodeSystem/v3-ActCode`, code `AMB`, display `ambulatory`. `subject.reference` `Patient/MHS-PAT-001`. `period.start` `2026-09-01T15:00:00Z`. No `period.end`. Search collection contains that encounter and is `complete` for this seed (one consultation for the patient, under the 100-row cap).
- Acceptance: status and class come from the map. The source words `completed` and `ambulatory` are not written as the FHIR status or class code. Display stays `ambulatory`.
- Evidence: exact read and search envelope.

### E2E-HTTP-04 Observations, UCUM, and original decimals

- Objective: cover results, both known UCUM units, structured blood pressure, and unknown units without a new fixture.
- Data: `MHS-RES-001` hemoglobin `13.4` `g/dL`. `MHS-RES-002` text `120/80` with components `120` and `80` `mmHg`. `MHS-RES-003` glucose `95` `mg/dL`. `MHS-RES-004` heart rate `72` `1/min`. `MHS-RES-006` temperature `36.6` `C`. All result status `final`. Categories `laboratory` or `vital_sign` as in the seed.
- Services: Mini HIS, Java.
- Command shape: exact `GET /api/clinical-read/v1/observations/{id}` for 001, 002, and 003. Search `GET /api/clinical-read/v1/observations?patient=MHS-PAT-001&status=final`.
- Expected:
  - Status `final`. Category system `http://terminology.hl7.org/CodeSystem/observation-category`. `laboratory` stays `laboratory`. `vital_sign` becomes `vital-signs`.
  - `code.text` is the seed display name. No LOINC or SNOMED coding.
  - `MHS-RES-001` `valueQuantity.value` compares equal to `13.4`, `unit` `g/dL`, `system` `http://unitsofmeasure.org`, `code` `g/dL`. No `component`.
  - `MHS-RES-002` has no `valueQuantity`. The text `120/80` is not parsed. Component 0: text `Presion sistolica`, value `120`, unit `mmHg`, system `http://unitsofmeasure.org`, code `mm[Hg]`. Component 1: text `Presion diastolica`, value `80`, same unit, system, and code.
  - `MHS-RES-003` `valueQuantity.value` compares equal to `95`, `unit` `mg/dL`. `system` and `code` are absent.
  - The same absence applies to `1/min` and `C` if 004 and 006 are read. Values stay `72` and `36.6`.
  - Subject `Patient/{patientId}`. Encounter `Encounter/{consultationId}`.
- Acceptance: known units gain UCUM. Unknown units stay text. Decimals are unchanged. Blood pressure stays two components.
- Evidence: the three exact observation documents. 004 and 006 are optional extra evidence for the same unknown-unit rule.

### E2E-HTTP-05 Appointments

- Objective: proprietary appointment status becomes FHIR status, and participant status stays outside the terminology map.
- Data: `MHS-APT-001` patient `MHS-PAT-004` `not_attended` offset `-400`. `MHS-APT-003` patient `MHS-PAT-005` `not_attended` offset `-400`. `MHS-APT-002` patient `MHS-PAT-005` `confirmed` offset `400`. `MHS-PAT-006` has no appointment.
- Services: Mini HIS, Java.
- Command shape: exact reads of the three ids, plus `GET /api/clinical-read/v1/appointments?patient=MHS-PAT-004`, `patient=MHS-PAT-005`, and `patient=MHS-PAT-006`.
- Expected: `not_attended` becomes `noshow`. `confirmed` becomes `booked`. `participant[0].status` is `needs-action`. `actor.reference` is `Patient/{patientId}`. `start` follows the offset rule above. PAT-004 search is one `complete` appointment. PAT-005 search is two, both present, `complete`. PAT-006 search is a `complete` empty `resources` array, not HTTP 404. `MiniHisRestSource.searchAppointments` returns 404 only when Mini HIS itself returns 404.
- Acceptance: both FHIR statuses, `needs-action` on every participant, and the empty collection for PAT-006.
- Evidence: three exact reads and three search envelopes.

### E2E-HTTP-06 Authentication and absence

- Objective: Java rejects a bad token and reports a missing Mini HIS row without a clinical body.
- Data: none beyond the running pair. Missing id `MHS-RES-999`, which is not in `SyntheticSeed`.
- Services: Mini HIS, Java.
- Command shape: repeat HTTP-01 without the header, with an empty header, and with a different token. Then `GET /api/clinical-read/v1/observations/MHS-RES-999` with the valid token. Then `GET /api/clinical-read/v1/patients?identifierSystem=https://lab.local/followup-case&identifierValue=SYN-FOLLOWUP-001` with the valid token.
- Expected: each bad token is HTTP 401 and the filter writes no body. `MHS-RES-999` is HTTP 404 `{"error":"not_found"}`. `SYN-FOLLOWUP-001` is not a Mini HIS identifier. Patient search treats a Mini HIS 404 as a `complete` empty Patient collection, not as `not_found`.
- Acceptance: 401 empty, 404 only for the missing result, empty complete collection for the unknown case id.
- Evidence: status codes and bodies. Do not record the valid token.

### E2E-AGT-01 Missed follow-up match and review case

- Objective: Python resolves `SYN-FOLLOWUP-013` through Java and the protocol matches.
- Data: patient `MHS-PAT-004`, only `MHS-APT-001`, past `noshow`, no `booked` appointment. Temporary review SQLite, empty at start.
- Preconditions: HTTP rows can be skipped only if this run repeats the Java reads it depends on. `FOLLOWUP_AGENT_ENABLED=true`. Python `MODEL_BOUNDARY_BASE_URL` is the Java base. Review, human-session, and institutional-knowledge SQLite paths point at a temporary directory outside the repository.
- Services: Mini HIS, Java, Python.
- Command shape: `POST /internal/agent/missed-follow-up` with header `X-Service-Token` and body `{"caseId":"SYN-FOLLOWUP-013"}`.
- Expected from `evaluate_missed_follow_up`: status `matched`, reason `missed_follow_up_without_confirmed_replacement`, provenance and trigger `Appointment/MHS-APT-001`. `_ensure_review_cases` creates a review case only because the status is `matched`. The case is open. A second POST for the same case id keeps that case. `missed_follow_up_service` does not call Gemini.
- Acceptance: one open case, one matched appointment, replay does not create a second case. No Encounter or Observation is required for this protocol.
- Evidence: both response bodies and a read of `GET /internal/follow-up-review-cases/{id}` showing status `open`. Redact the token.

### E2E-AGT-02 Future booked appointment

- Objective: a past `noshow` does not match when a future `booked` appointment exists.
- Data: `SYN-FOLLOWUP-014`, patient `MHS-PAT-005`, `MHS-APT-003` past `noshow` and `MHS-APT-002` future `booked`.
- Services: Mini HIS, Java, Python. Same temporary review database as AGT-01, or a fresh one. State which.
- Command shape: `POST /internal/agent/missed-follow-up` body `{"caseId":"SYN-FOLLOWUP-014"}`.
- Expected: `evaluate_missed_follow_up` checks `future_booked` before `past_noshow`. Status `not_matched`. Reason `confirmed_future_follow_up_exists`. Provenance includes `Appointment/MHS-APT-003` and `Appointment/MHS-APT-002`. `_ensure_review_cases` returns no case when status is not `matched`.
- Acceptance: `not_matched` and no new review row for 014.
- Evidence: response body and a case list that does not gain a 014 row.

### E2E-AGT-03 No past noshow

- Objective: a resolved patient with no appointments does not match.
- Data: `SYN-FOLLOWUP-015`, patient `MHS-PAT-006`, appointment search empty and complete.
- Services: Mini HIS, Java, Python.
- Command shape: `POST /internal/agent/missed-follow-up` body `{"caseId":"SYN-FOLLOWUP-015"}`.
- Expected: status `not_matched`, reason `eligible_past_noshow_absent`, no review case.
- Acceptance: that reason and no new row.
- Evidence: response body and the case list.

### E2E-AGT-04 Clinical context of the matched case

- Objective: the open case from AGT-01 reads the trigger through Java.
- Data: the review case id returned by AGT-01. Trigger `Appointment/MHS-APT-001`.
- Preconditions: AGT-01 has left the case `open`.
- Services: Mini HIS, Java, Python.
- Command shape: `GET /internal/follow-up-review-cases/{reviewCaseId}/clinical-context` with `X-Service-Token`.
- Expected: HTTP 200 for an open case. The missed-follow-up path does not require Encounter or Observation (`clinical-review-context-v1.md`). The trigger appointment is `noshow`. `appointment_classification` returns `OTHER` for `noshow`, because that status is not `cancelled`, `booked`, or in the past statuses `booked` and `fulfilled`. The appointment collection for PAT-004 is complete.
- Acceptance: context available, trigger id `MHS-APT-001`, classification `OTHER`, collection complete.
- Evidence: the context JSON.

### E2E-AGT-05 Java unavailable

- Objective: a stopped Java process does not create a review case.
- Data: `SYN-FOLLOWUP-013` after AGT-01, or a fresh review database. Record which, because an existing matched case must stay unchanged.
- Services: Mini HIS may stay up. Java is stopped. Python stays up.
- Command shape: the same POST as AGT-01.
- Expected: `ClinicalReadClient` turns a connection failure into a failed search. `evaluate_missed_follow_up` returns `UNAVAILABLE` when the patient or appointment collection is `UNAVAILABLE`. `_ensure_review_cases` does not insert on a non-match status. An existing open case from a previous match is not closed by this call.
- Acceptance: no new case. A case that already existed is still open and keeps its version.
- Evidence: the Python response and the case read before and after.

### E2E-AGT-06 Post-consultation, recorded limit

- Objective: state the outcome the current seed and normalizer can support, and stop before Gemini.
- Data: `SYN-FOLLOWUP-013` resolves to `MHS-PAT-004`, which has no consultation. `MHS-PAT-001` has consultations and final observations, but no `https://lab.local/followup-case` identifier, so the follow-up resolver does not select that patient.
- This row is not a closed-lab execution step.
- Derived protocol fact, not a claim that the HTTP route was run: for 013, encounter search `status=finished` is a complete empty collection, and `_evaluate_pairs` returns `finished_encounter_missing` with status insufficient. `ensure_review_case` returns no case unless the status value is `matched`.
- Even a future binding from a case id to `MHS-PAT-001` would still lack `period.end` and `Observation.issued`, so the pair evaluation would be insufficient (`encounter_end_missing_or_invalid` and `observation_issued_missing_or_invalid`) rather than `matched`.
- Acceptance for a later implementation: do not call `POST /internal/agent/follow-up` in the closed lab. Do not add a fixture to force `matched`.

## 5. Data and fixtures

Use `SyntheticSeed` only. Relevant rows:

| Id | Use |
|---|---|
| `MHS-PAT-001` .. `003` | Demographics, consultations, results. No follow-up case identifier. |
| `MHS-PAT-004` + `SYN-FOLLOWUP-013` + `MHS-APT-001` | Missed follow-up match. |
| `MHS-PAT-005` + `SYN-FOLLOWUP-014` + `MHS-APT-003` + `MHS-APT-002` | Future booked appointment blocks the match. |
| `MHS-PAT-006` + `SYN-FOLLOWUP-015` | Resolved patient, no appointment. |
| `MHS-RES-001`, `MHS-RES-002` | UCUM `g/dL` and `mm[Hg]`, decimals `13.4`, `120`, `80`. |
| `MHS-RES-003`, `004`, `006` | Unknown units `mg/dL`, `1/min`, `C`. |

`POST /synthetic/reset` reloads that seed. `MiniHisController` returns 403 `reset_not_local` unless both the remote and local addresses are loopback. A new empty file does not need reset. Do not point the simulator at `data/mini-his.sqlite` or at any review database under `services/ai-service/data`.

`scripts/fhir/syn-*-012.json` are not Mini HIS rows. `SYN-FOLLOWUP-001` through `012` are absent from `PATIENT_IDENTIFIERS`.

## 6. Execution procedure

Proposed commands are for a later run. They are not instructions that were executed for this design.

1. Create a temporary directory outside the repository. Put `mini-his.sqlite`, `review.sqlite3`, `human-session.sqlite3`, and `institutional-knowledge.sqlite3` there.
2. Start Mini HIS from `services/mini-his-simulator` with `server.address=127.0.0.1`, a free port, and `mini-his.sqlite-path` set to the new file. Spring maps `SERVER_ADDRESS`, `SERVER_PORT`, and `MINI_HIS_SQLITE_PATH`. Wait until the log says the application has started. `GET /health` on that port returns `{"status":"up"}`.
3. Start Java from `services/fhir-integration-service` with `SERVER_ADDRESS=127.0.0.1`, a free port, `CLINICAL_READ_SOURCE=mini-his`, `CLINICAL_READ_MINI_HIS_BASE_URL` equal to the Mini HIS base, and `MODEL_BOUNDARY_SERVICE_TOKEN` set to the disposable dummy. Do not start Docker or HAPI.
4. Run the HTTP scenarios with an HTTP client. Pass the token only as a header.
5. Start Python from `services/ai-service` with `AI_SERVICE_PORT` free, `FOLLOWUP_AGENT_ENABLED=true`, `MODEL_BOUNDARY_BASE_URL` equal to the Java base, the same token, `MODEL_BOUNDARY_TIMEOUT_SECONDS` greater than Java's Mini HIS read timeout of 5 seconds, and the three SQLite paths in the temporary directory. The existing interpreter is the one already used for this service. This design does not add a package.
6. Run AGT-01, then AGT-04, then AGT-02 and AGT-03. Run AGT-05 by stopping only the temporary Java process.
7. Stop only the three processes started in this procedure. Delete the temporary directory. Leave any pre-existing listener on 8080, 8081, 8090, or 8095 running.

`mvn -q spring-boot:run` is the existing Java and Mini HIS launcher. Python is the existing module `app.main`. No new plugin or image is required.

## 7. Acceptance criteria

The later run passes only when all of the following hold:

- HTTP-01 through HTTP-06 match the fields in section 4.
- AGT-01 creates one open review case for `SYN-FOLLOWUP-013` and replay keeps it.
- AGT-02 and AGT-03 add no review case.
- AGT-04 reads the trigger appointment through the context route and classifies `noshow` as `OTHER`.
- AGT-05 adds no case and does not close an existing one.
- AGT-06 is not executed as a live Gemini call.
- Python request URLs stay under `/api/clinical-read/v1`. No Python request uses the Mini HIS port.
- HAPI received no request in this run.
- No file inside the repository was written by the run.

## 8. Evidence to keep

Store evidence outside the repository. Suggested names:

- `http-01-patient.json` through `http-06-auth.txt`
- `agt-01-first.json`, `agt-01-replay.json`, `agt-01-case.json`
- `agt-02.json`, `agt-03.json`, `agt-04-context.json`, `agt-05-java-down.json`
- a short log list of process ports and the SQLite paths, without the token

Each file records the HTTP status and the JSON body. Strip `X-Service-Token`. Do not copy SQLite databases into the repository. Do not treat a mocked `ClinicalReadClient` test as a substitute for these files.

## 9. Risks and limitations

- Python coupled to Mini HIS: the check is the request log. `ClinicalReadClient` has no Mini HIS path. A test that calls `http://127.0.0.1:8095` from Python fails the acceptance rule.
- Residual HAPI client: `HapiReadClient` and `FHIR_BASE_URL` remain in the tree. The factories under test construct `ClinicalReadClient`. A run that still contacts port 8080 fails the acceptance rule.
- Normalization gaps: no `period.end`, no `Observation.issued`, observation `code` is text only, participant status is always `needs-action`. Those are current behavior, not defects to patch during the test.
- Clinical values: acceptance uses exact decimals from the seed. Any converted number fails.
- Authentication: an unset Java token makes every Clinical Read call 401. Python then reports the collection unavailable. That is AGT-05's neighbor, not a successful match.
- Persistence: review ids and versions come from the temporary SQLite file. Reusing `services/ai-service/data` would mix the run with existing cases. Appointment instants move with the clock; compare them to the offset rule.
- External services: Gemini, Epic, Oracle, and a shared HAPI are unnecessary for the closed set. `POST /internal/agent/follow-up` is the route that pulls Gemini back in.
- Unknown-unit coverage is only the units already seeded. The design does not add `MMHG` or a blank unit to the database.
- Collection caps: this seed is far below 100 rows. The run does not prove the incomplete-collection path.

## 10. Implementation stages

Stage 0. Leave the existing unit tests as they are. Do not rename them to E2E.

Stage 1. Execute section 6 steps 1–4 and keep the HTTP evidence. Stop there if Java cannot read the seed.

Stage 2. Execute AGT-01 through AGT-05. This is the first three-process evidence.

Stage 3. Decide separately whether post-consultation should grow `period.end` and `Observation.issued`, or whether the protocol should accept `effectiveDateTime`. That decision is not part of running this design. Until one of those exists, AGT-06 stays a documented limit.

No new dependency is justified for stages 1 and 2. The repository already has Maven, the Python environment used by `ai-service`, and an HTTP client on the host.
