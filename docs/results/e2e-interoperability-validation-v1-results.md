# E2E interoperability validation V1 — results

Record of the laboratory run on 2026-10-19. The procedure stays in [the design](../design/e2e-interoperability-validation-v1.md). This file does not change that design, any ADR, or any clinical contract.

HEAD at execution: `1fd497adb0c50a3118632f6c78094caf033e0ab6` on `feature/follow-up-agent`.

The statements below are taken from response bodies and logs saved outside the repository. A conclusion that is not a direct field in those files is marked as inferred.

## 1. Objective

Confirm the path Mini HIS proprietary REST, Java Clinical Read API v1, Python `ClinicalReadClient`, and `MISSED_FOLLOW_UP_REVIEW_V1` on the synthetic seed. Stages 1 and 2 of the design were executed. Stage 3 was not.

## 2. Architecture and services

Three temporary loopback processes were started for this run and stopped afterward:

| Process | Address used |
|---|---|
| Mini HIS Simulator | `127.0.0.1:18095` |
| Healthcare Interoperability | `127.0.0.1:18086` |
| Healthcare AI | `127.0.0.1:18090` |

Port 8080 was already listening and was left running. Ports 8081, 8090, and 8095 were free and were not used. HAPI, Docker, Gemini, Epic, and Oracle were not started.

## 3. Environment

- `clinical-read.source=mini-his`
- Java Mini HIS base URL `http://127.0.0.1:18095`
- Python `MODEL_BOUNDARY_BASE_URL=http://127.0.0.1:18086`
- `FOLLOWUP_AGENT_ENABLED=true`
- `MODEL_BOUNDARY_TIMEOUT_SECONDS=10`
- A disposable service token was set on Java and Python. The value is not recorded here.
- Mini HIS, review, human-session, and institutional-knowledge SQLite files were new files outside the repository. They were deleted after the run and are not part of the evidence.

Python startup logged `knowledge_index status=UNAVAILABLE reason=embedding_unavailable`.

## 4. Scenario matrix

| Id | Result | Observed |
|---|---|---|
| E2E-HTTP-01 | PASS | HTTP 200. `contractVersion` `clinical-read-v1`. `destination` `mini-his`. Patient `MHS-PAT-001`. |
| E2E-HTTP-02 | PASS | HTTP 200. One Patient `MHS-PAT-004`. Collection `complete`. Both the follow-up-case identifier `SYN-FOLLOWUP-013` and the Mini HIS patient identifier are present. |
| E2E-HTTP-03 | PASS | Encounter `MHS-CON-001` status `finished`, class `AMB`, display `ambulatory`, `period.start` `2026-09-01T15:00:00Z`. No `period.end`. Search `status=finished` is `complete` and contains that id. |
| E2E-HTTP-04 | PASS | Observations `MHS-RES-001`, `002`, and `003` are HTTP 200. Patient `MHS-PAT-001` final search is `complete` and contains `001` and `002`. `004` and `006` were also read and match the unknown-unit rule. |
| E2E-HTTP-05 | PASS | `MHS-APT-001` and `MHS-APT-003` are `noshow`. `MHS-APT-002` is `booked`. Every participant status is `needs-action`. Starts are `2025-09-15T12:00:00Z` and `2027-11-24T12:00:00Z`. `MHS-PAT-006` search is HTTP 200, `complete`, and empty. |
| E2E-HTTP-06 | PASS | Missing, empty, and wrong token: HTTP 401, body length 0. `MHS-RES-999`: HTTP 404 `{"error":"not_found"}`. `SYN-FOLLOWUP-001`: HTTP 200, `complete`, empty Patient array. |
| E2E-AGT-01 | PASS | `matched`. Reason `missed_follow_up_without_confirmed_replacement`. One open review case, version 1, matched resource `Appointment/MHS-APT-001`. |
| E2E-AGT-02 | PASS | `not_matched`. Reason `confirmed_future_follow_up_exists`. `reviewCases` is empty. Provenance `Appointment/MHS-APT-003` and `Appointment/MHS-APT-002`. |
| E2E-AGT-03 | PASS | `not_matched`. Reason `eligible_past_noshow_absent`. `reviewCases` is empty. |
| E2E-AGT-04 | PASS | HTTP 200. Schema `CLINICAL_REVIEW_CONTEXT_V1`. Trigger `Appointment/MHS-APT-001`, status `noshow`. Item classification `OTHER`. Appointment collection `complete`. |
| E2E-AGT-05 | PASS | After the temporary Java process was stopped: HTTP 200, `evaluationStatus` `unavailable`, reason `patient_resolution_unavailable`, `reviewCases` empty. The existing case stayed `open` version 1. |
| E2E-AGT-06 | BLOCKED | Not executed. The design excludes a live post-consultation call because that route enters the narrative engine. |

No scenario is FAIL. No executed scenario is NOT VERIFIED. The Mini HIS access log was empty while the processes were still running and was flushed when Mini HIS stopped. The flushed file is part of the evidence. See section 10.

## 5. FHIR R4 normalization

Observed on the saved resources:

- Encounter status `completed` from the seed is `finished` in FHIR.
- Encounter class is system `http://terminology.hl7.org/CodeSystem/v3-ActCode`, code `AMB`, display `ambulatory`.
- Observation status is `final`.
- Category `laboratory` stays `laboratory`. Category `vital_sign` is `vital-signs`. System `http://terminology.hl7.org/CodeSystem/observation-category`.
- Observation `code.text` is the seed label. No LOINC or SNOMED coding is present in the saved observations.
- Appointment `not_attended` is `noshow`. Appointment `confirmed` is `booked`.
- `participant.status` is `needs-action`.
- `meta.source` on these resources is `https://lab.local/mini-his`.

`MHS-CON-001` has `period.start` and no `period.end`. `MHS-RES-001` has `effectiveDateTime` and no `issued`.

## 6. UCUM and original values

| Resource | Observed quantity |
|---|---|
| `MHS-RES-001` | `value` 13.4, `unit` `g/dL`, `system` `http://unitsofmeasure.org`, `code` `g/dL`. No component. |
| `MHS-RES-002` | No `valueQuantity` on the parent. Systolic component value 120, diastolic component value 80. Both `unit` `mmHg`, `system` `http://unitsofmeasure.org`, `code` `mm[Hg]`. |
| `MHS-RES-003` | `value` 95, `unit` `mg/dL`. The quantity object has only `value` and `unit`. |

`MHS-RES-004` (`1/min`, 72) and `MHS-RES-006` (`C`, 36.6) were checked in the same HTTP-04 pass. Their saved bodies are in the evidence directory. The checker required `value` and `unit` and the absence of `system` and `code`.

## 7. Follow-up Agent

All three agent calls used `POST /internal/agent/missed-follow-up` and returned `protocolId` `MISSED_FOLLOW_UP_REVIEW_V1`.

- `SYN-FOLLOWUP-013` matched and created review case `22a941ac-1ae4-4085-91bf-d0da4dc3f7ce`.
- `SYN-FOLLOWUP-014` did not match because a future booked appointment exists.
- `SYN-FOLLOWUP-015` did not match because no past noshow exists.

The case list saved after 014 and 015 contains one item, and that item is the 013 case. Inferred from that list: 014 and 015 did not create a review row.

Clinical context retrieval status is `complete`, reason `current_context_complete`. The missed-follow-up context in this body has a trigger appointment and an appointment collection. It does not include an encounter or observation object.

## 8. Idempotence

The first and replay bodies for `SYN-FOLLOWUP-013` contain the same `reviewCaseId`, status `open`, and version 1. The case read after Java was stopped still has `createdAt` and `updatedAt` `2026-10-20T04:23:40.634385Z`, status `open`, version 1, and one transition of type `created`.

## 9. Java unavailable

The temporary Java listener on 18086 was stopped. Mini HIS and Python were still up. The next missed-follow-up POST for `SYN-FOLLOWUP-013` returned HTTP 200 with `evaluationStatus` `unavailable` and reason `patient_resolution_unavailable`. `reviewCases` was empty. The stored case did not change status or version.

The Python log line for that call is `missed_follow_up ... status=unavailable`. There is no completed `httpx` response line for that attempt. Inferred: the client did not receive an HTTP response from Java.

## 10. Decoupling

Observed in `python-httpx.txt`: 15 `httpx` lines. Every URL is `http://127.0.0.1:18086/api/clinical-read/v1/...` and every completed response is HTTP 200. The file contains no port 18095 and no port 8080.

Observed in the Java Tomcat access log: 78 request lines, each for `/api/clinical-read/v1`. The log pattern does not include a client name, so that file alone does not name Python.

Observed in the Mini HIS access log after the process stopped: 69 request lines. All are proprietary `GET` paths such as `/patients`, `/consultations`, `/results`, and `/appointments`. None contain `clinical-read` or port 8080. The log pattern does not include a client name.

Observed during the run, in the Java HTTP client log, and not copied in full into the evidence directory: outbound URLs were to `127.0.0.1:18095`, and a count of `8080/fhir` in that log was 0. Inferred from the three logs together: Java called Mini HIS, and the captured Python client did not. The empty-file reading taken before shutdown is superseded by the flushed log.

No `gemini_followup` line and no generative-language URL appear in the Python log excerpt that was kept. The narrative route was not called. Inferred from the absence of those lines, not from a packet capture: Gemini was not invoked.

## 11. Incidents

The first comparison of appointment `start` required the text `T12:00Z`. The service returned `T12:00:00Z`. The calendar day matches the UTC date of the run plus the seed offset (`-400` days for the past appointments, `+400` days for the booked appointment). The check was repeated by comparing the instant, and HTTP-05 then passed. No product code was changed.

## 12. Coverage limits

- AGT-06 was not run. Post-consultation `matched` is not claimed.
- The incomplete-collection cap of 100 resources was not exercised.
- Units outside the seed (`MMHG`, a blank unit) were not sent.
- Epic, Oracle, HAPI as the Clinical Read source, and Model Boundary v1 were not the system under test.
- `HapiReadClient` remains in the source tree. This run shows it was not used in the captured `httpx` log. It does not show that no other entry point can still call it.
- Evidence files live on one workstation temp directory. They are not in git.

## 13. Evidence location

`C:\Users\Abel Vergaray\AppData\Local\Temp\e2e-interop-evidence-v1`

Bodies use the suffix `.body.json`. Status lines use `.meta.txt`. Also present: `http-results.txt`, `agt-results-before-down.txt`, `agt-05-result.txt`, `python-httpx.txt`, `run-summary.txt`, `java-access\access.2026-10-19.log`, and `minihis-access\access.2026-10-19.log`. No service token and no SQLite copy are stored there.

## 14. Conclusion

The acceptance criteria in the design for HTTP-01 through HTTP-06 and AGT-01 through AGT-05 were met by the saved responses. AGT-06 stayed blocked by design. Python’s captured outbound calls for the agent scenarios went to Java Clinical Read. Java’s captured outbound calls went to Mini HIS. This is a laboratory result on synthetic data. It is not a production certification and it does not implement the bidirectional exchange in ADR-095.
