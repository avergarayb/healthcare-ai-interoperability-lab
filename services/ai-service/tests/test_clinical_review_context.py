"""CLINICAL_REVIEW_CONTEXT_V1. Current FHIR projection for one open review case."""

from __future__ import annotations

import inspect
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.clinical_review_context import (
    ClinicalReviewContextService,
    project_observation_code,
    project_observation_content,
)
from app.clinical_review_context_http import get_clinical_review_context_http
from app.config import Settings
from app.followup_review import (
    FollowUpReviewCaseService,
    ReviewOutcome,
    build_review_identity,
    canonical_matched_resources,
)
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.langgraph_fhir_client import BoundedSearchResult, BoundedSearchStatus, CASE_IDENTIFIER_SYSTEM
from app.main import app, get_settings
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)


CASE = "SYN-FOLLOWUP-008"
OTHER_CASE = "SYN-FOLLOWUP-009"
TOKEN = "test-model-boundary-token"
AUTH = {"X-Service-Token": TOKEN}
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
PATIENT = "SYN-PATIENT-008"
OTHER_PATIENT = "SYN-PATIENT-009"
ENCOUNTER = "encounter-008"
OBSERVATION = "observation-008"
APPOINTMENT = "appointment-008"


class Clock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self):
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def _settings() -> Settings:
    return Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token=TOKEN,
        host="127.0.0.1",
        port=8090,
        followup_agent_enabled=True,
        ai_review_db_path="unused-by-explicit-test-repository.sqlite3",
    )


def _protocol(suffix: str = "008") -> ProtocolReviewResult:
    return ProtocolReviewResult(
        id=POST_CONSULTATION_RESULT_REVIEW_V1,
        evaluation_status=ProtocolEvaluationStatus.MATCHED,
        reason_codes=("post_consultation_result_requires_review",),
        matched_resources=(f"Encounter/encounter-{suffix}", f"Observation/observation-{suffix}"),
        human_review_status="required",
        human_review_reason="deterministic_post_consultation_protocol_match",
        action_status="proposed",
        action_type="review_follow_up_case",
    )


def _repository(tmp_path):
    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3", clock=Clock())
    repository.initialize()
    return repository


def _create(repository, *, case_id=CASE, suffix="008"):
    case = FollowUpReviewCaseService(repository).ensure_for_protocol(case_id, _protocol(suffix))
    assert case is not None
    return case


class ScriptedFhir:
    def __init__(self, *, case_id=CASE, patient_id=PATIENT, encounter_id=ENCOUNTER, observation_id=OBSERVATION):
        self.case_id = case_id
        self.patient_id = patient_id
        self.encounter_id = encounter_id
        self.observation_id = observation_id
        self.calls: list[tuple] = []
        self.encounter = _encounter(encounter_id, patient_id)
        self.observation = _observation(observation_id, encounter_id, patient_id)
        self.appointments: list[dict] = [_appointment(APPOINTMENT, patient_id)]
        self.patient_status = BoundedSearchStatus.COMPLETE
        self.appointment_status = BoundedSearchStatus.COMPLETE
        self.missing: set[str] = set()
        self.patients = {
            case_id: _patient(patient_id, case_id),
        }

    def search(self, path: str, expected_resource_type: str):
        self.calls.append(("search", expected_resource_type, path))
        if expected_resource_type == "Patient":
            patient = None
            for case_id, resource in self.patients.items():
                if case_id in path:
                    patient = resource
            resources = () if patient is None else (patient,)
            return BoundedSearchResult(self.patient_status, resources)
        resources = tuple(self.appointments)
        return BoundedSearchResult(self.appointment_status, resources)

    def read_exact(self, resource_type: str, resource_id: str) -> dict:
        self.calls.append(("exact", resource_type, resource_id))
        if resource_type in self.missing or resource_id in self.missing:
            from app.langgraph_fhir_hapi import ExactResourceNotFound

            raise ExactResourceNotFound()
        if resource_type == "Encounter":
            return dict(self.encounter)
        if resource_type == "Observation":
            return dict(self.observation)
        if resource_type == "Appointment":
            for item in self.appointments:
                if item.get("id") == resource_id:
                    return dict(item)
            from app.langgraph_fhir_hapi import ExactResourceNotFound

            raise ExactResourceNotFound()
        raise AssertionError(resource_type)


def _patient(patient_id: str, case_id: str) -> dict:
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "identifier": [{"system": CASE_IDENTIFIER_SYSTEM, "value": case_id}],
    }


def _encounter(encounter_id: str, patient_id: str, *, status: str = "finished") -> dict:
    return {
        "resourceType": "Encounter",
        "id": encounter_id,
        "status": status,
        "subject": {"reference": f"Patient/{patient_id}"},
        "period": {"start": "2026-09-30T11:00:00Z", "end": "2026-09-30T11:30:00Z"},
    }


def _observation(
    observation_id: str,
    encounter_id: str,
    patient_id: str,
    *,
    status: str = "final",
    value: dict | None = None,
    code: dict | None = None,
) -> dict:
    resource = {
        "resourceType": "Observation",
        "id": observation_id,
        "status": status,
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": f"Encounter/{encounter_id}"},
        "issued": "2026-09-30T11:20:00Z",
        "code": code
        or {
            "coding": [{"system": "http://loinc.org", "code": "1234-5", "display": "Synthetic"}],
            "text": "Synthetic result",
        },
    }
    resource.update({"valueString": "synthetic-result"} if value is None else value)
    return resource


def _appointment(appointment_id: str, patient_id: str, *, status: str = "booked", start: str = "2027-03-15T15:00:00Z") -> dict:
    return {
        "resourceType": "Appointment",
        "id": appointment_id,
        "status": status,
        "start": start,
        "participant": [{"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"}],
    }


@pytest.fixture(autouse=True)
def _clean_state():
    app.dependency_overrides.clear()
    for name in ("followup_review_repository", "clinical_context_fhir_client"):
        if hasattr(app.state, name):
            delattr(app.state, name)
    yield
    app.dependency_overrides.clear()
    for name in ("followup_review_repository", "clinical_context_fhir_client"):
        if hasattr(app.state, name):
            delattr(app.state, name)


def _http(repository, fhir: ScriptedFhir) -> TestClient:
    app.state.followup_review_repository = repository
    app.state.clinical_context_fhir_client = lambda: fhir
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def _body(repository, fhir, case_id: str) -> dict:
    response = _http(repository, fhir).get(
        f"/internal/follow-up-review-cases/{case_id}/clinical-context",
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_open_case_returns_current_context_without_patient_identity(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    body = _body(repository, fhir, case.id)
    assert body["schema"] == "CLINICAL_REVIEW_CONTEXT_V1"
    assert body["reviewCase"] == {"reviewCaseId": case.id, "status": "open", "version": 1}
    assert body["triggerProvenance"]["protocolId"] == POST_CONSULTATION_RESULT_REVIEW_V1
    assert body["triggerProvenance"]["evaluationStatus"] == "matched"
    assert body["triggerProvenance"]["matchedResources"] == [
        f"Encounter/{ENCOUNTER}",
        f"Observation/{OBSERVATION}",
    ]
    assert body["retrieval"]["status"] == "complete"
    assert body["retrieval"]["source"] == "fhir_current"
    assert body["retrieval"]["reasonCodes"] == ["current_context_complete"]
    assert body["currentContext"]["patient"] == {"resolution": "resolved"}
    assert "triggerAppointment" not in body["currentContext"]
    assert body["currentContext"]["encounter"]["availability"] == "available"
    assert body["currentContext"]["encounter"]["status"] == "finished"
    assert body["currentContext"]["encounter"]["reference"] == f"Encounter/{ENCOUNTER}"
    assert body["currentContext"]["observation"]["content"] == {
        "status": "available",
        "kind": "string",
        "value": "synthetic-result",
    }
    assert body["currentContext"]["appointments"]["collectionStatus"] == "complete"
    assert body["currentContext"]["appointments"]["classifications"] == ["UPCOMING_CONFIRMED"]
    rendered = json.dumps(body)
    for secret in (PATIENT, "Synthetic Patient", "birthDate", "resourceType", "participant"):
        assert secret not in rendered
    assert all(call[0] != "exact" or call[1] != "Patient" for call in fhir.calls)
    assert not any(case.id in json.dumps(call) for call in fhir.calls)


def test_closed_case_does_not_read_fhir(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    repository.close(case.id, expected_version=1, outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED)
    fhir = ScriptedFhir()
    response = _http(repository, fhir).get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "clinical_context_not_available_for_closed_case"}
    assert fhir.calls == []
    detail = _http(repository, fhir).get(f"/internal/follow-up-review-cases/{case.id}", headers=AUTH)
    assert detail.status_code == 200
    assert detail.json()["status"] == "closed"


def test_authentication_precedes_repository_and_fhir(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    response = _http(repository, fhir).get(f"/internal/follow-up-review-cases/{case.id}/clinical-context")
    assert response.status_code == 401
    assert response.content == b""
    assert fhir.calls == []


def test_missing_and_invalid_review_case(tmp_path):
    repository = _repository(tmp_path)
    fhir = ScriptedFhir()
    client = _http(repository, fhir)
    missing = client.get(
        "/internal/follow-up-review-cases/00000000-0000-4000-8000-000000000000/clinical-context",
        headers=AUTH,
    )
    invalid = client.get("/internal/follow-up-review-cases/not-a-uuid/clinical-context", headers=AUTH)
    assert missing.status_code == 404
    assert invalid.status_code == 422
    assert fhir.calls == []


def test_case_isolation_uses_only_persisted_provenance(tmp_path):
    repository = _repository(tmp_path)
    first = _create(repository, case_id=CASE, suffix="008")
    second = _create(repository, case_id=OTHER_CASE, suffix="009")
    fhir = ScriptedFhir()
    fhir.patients[OTHER_CASE] = _patient(OTHER_PATIENT, OTHER_CASE)
    body = _body(repository, fhir, first.id)
    injected = _http(repository, fhir).get(
        f"/internal/follow-up-review-cases/{first.id}/clinical-context",
        headers=AUTH,
        params={"patient": OTHER_PATIENT, "encounter": "encounter-009", "observation": "observation-009"},
    )
    assert injected.status_code == 200
    assert body["currentContext"]["encounter"]["reference"] == f"Encounter/{ENCOUNTER}"
    assert injected.json()["currentContext"]["encounter"]["reference"] == f"Encounter/{ENCOUNTER}"
    assert all("encounter-009" not in json.dumps(call) for call in fhir.calls)
    assert all(second.id not in json.dumps(call) for call in fhir.calls)
    other = ScriptedFhir(case_id=OTHER_CASE, patient_id=OTHER_PATIENT, encounter_id="encounter-009", observation_id="observation-009")
    other.patients = {OTHER_CASE: _patient(OTHER_PATIENT, OTHER_CASE)}
    other.appointments = []
    other_body = _body(repository, other, second.id)
    assert other_body["currentContext"]["encounter"]["reference"] == "Encounter/encounter-009"
    assert PATIENT not in json.dumps(other_body)


@pytest.mark.parametrize(
    ("resources", "expected_detail"),
    [
        (
            ["http://example.test/Encounter/encounter-008", "Observation/observation-008"],
            "Follow-up review persistence unavailable",
        ),
        (
            ["Encounter/encounter-008?subject=Patient/other", "Observation/observation-008"],
            "Follow-up review persistence unavailable",
        ),
        (
            ["Encounter/encounter-008/_history/1", "Observation/observation-008"],
            "Follow-up review persistence unavailable",
        ),
        (
            ["Patient/SYN-PATIENT-008", "Observation/observation-008"],
            "Follow-up review persistence unavailable",
        ),
        (
            ["Encounter/../observation-008", "Observation/observation-008"],
            "Follow-up review persistence unavailable",
        ),
        (
            ["Encounter/encounter-008", "Encounter/encounter-009"],
            "Clinical review context unavailable",
        ),
        (
            ["Observation/observation-008"],
            "Clinical review context unavailable",
        ),
        (
            ["Observation/observation-008", "Patient/SYN-PATIENT-008"],
            "Clinical review context unavailable",
        ),
    ],
)
def test_tampered_provenance_is_rejected_before_fhir(tmp_path, resources, expected_detail):
    repository = _repository(tmp_path)
    case = _create(repository)
    raw = json.dumps(resources, ensure_ascii=False, separators=(",", ":"))
    identity = None
    try:
        canonical = canonical_matched_resources(resources)
    except ValueError:
        canonical = None
    if canonical is not None and list(canonical) == resources:
        identity = build_review_identity(CASE, POST_CONSULTATION_RESULT_REVIEW_V1, canonical)
    connection = sqlite3.connect(tmp_path / "review.sqlite3")
    if identity is None:
        connection.execute(
            "UPDATE follow_up_review_cases SET matched_resources_json = ? WHERE id = ?",
            (raw, case.id),
        )
    else:
        connection.execute(
            "UPDATE follow_up_review_cases SET matched_resources_json = ?, review_identity = ? WHERE id = ?",
            (raw, identity, case.id),
        )
    connection.commit()
    connection.close()
    fhir = ScriptedFhir()
    response = _http(repository, fhir).get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    )
    assert response.status_code == 503
    assert response.json() == {"detail": expected_detail}
    assert fhir.calls == []
    assert "example.test" not in response.text
    assert "_history" not in response.text
    assert "SYN-PATIENT-008" not in response.text


def test_wrong_identity_and_foreign_association_fail_closed(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    fhir.encounter = _encounter(ENCOUNTER, PATIENT)
    fhir.encounter["id"] = "other-encounter"
    response = _http(repository, fhir).get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Clinical review context unavailable"
    assert not any(call[1] == "Appointment" for call in fhir.calls)
    fhir = ScriptedFhir()
    fhir.encounter["resourceType"] = "Patient"
    assert _http(repository, fhir).get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    ).status_code == 503
    fhir = ScriptedFhir()
    fhir.encounter["subject"] = {"reference": f"Patient/{OTHER_PATIENT}"}
    assert _http(repository, fhir).get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    ).status_code == 503
    fhir = ScriptedFhir()
    fhir.observation["encounter"] = {"reference": "Encounter/other-encounter"}
    failed = _http(repository, fhir).get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    )
    assert failed.status_code == 503
    assert "synthetic-result" not in failed.text
    fhir = ScriptedFhir()
    fhir.patient_status = BoundedSearchStatus.FAILED
    unresolved = _http(repository, fhir).get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    )
    assert unresolved.status_code == 503
    assert all(call[0] == "search" for call in fhir.calls)


def test_genuine_exact_not_found_stays_in_the_current_context(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    before = repository.get(case.id)
    fhir = ScriptedFhir()
    fhir.missing.add("Encounter")
    body = _body(repository, fhir, case.id)
    assert body["currentContext"]["encounter"] == {
        "reference": f"Encounter/{ENCOUNTER}",
        "availability": "not_found",
    }
    assert body["retrieval"]["status"] == "provenance_resource_not_found"
    assert body["retrieval"]["reasonCodes"] == ["provenance_encounter_not_found"]
    assert body["currentContext"]["observation"]["availability"] == "available"
    fhir = ScriptedFhir()
    fhir.missing.update({"Encounter", "Observation"})
    both = _body(repository, fhir, case.id)
    assert both["currentContext"]["encounter"]["availability"] == "not_found"
    assert both["currentContext"]["observation"] == {
        "reference": f"Observation/{OBSERVATION}",
        "availability": "not_found",
    }
    assert both["retrieval"]["reasonCodes"] == [
        "provenance_encounter_not_found",
        "provenance_observation_not_found",
    ]
    after = repository.get(case.id)
    assert after == before


def test_current_status_and_appointments_do_not_mutate_the_case(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    fhir.encounter["status"] = "cancelled"
    fhir.observation["status"] = "amended"
    fhir.appointments = [_appointment(APPOINTMENT, PATIENT)]
    body = _body(repository, fhir, case.id)
    assert body["currentContext"]["encounter"]["status"] == "cancelled"
    assert body["currentContext"]["observation"]["status"] == "amended"
    assert "currentMatch" not in body
    assert "stillMatched" not in body
    assert body["triggerProvenance"]["evaluationStatus"] == "matched"
    empty = ScriptedFhir()
    empty.appointments = []
    none_body = _body(repository, empty, case.id)
    assert none_body["currentContext"]["appointments"]["classifications"] == ["NONE"]
    assert none_body["currentContext"]["appointments"]["items"] == []
    other = ScriptedFhir()
    other.appointments = [_appointment(APPOINTMENT, PATIENT, status="arrived", start="2020-01-01T00:00:00Z")]
    assert _body(repository, other, case.id)["currentContext"]["appointments"]["classifications"] == ["OTHER"]
    incomplete = ScriptedFhir()
    incomplete.appointment_status = BoundedSearchStatus.INCOMPLETE_LIMIT
    failed = _http(repository, incomplete).get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    )
    assert failed.status_code == 503
    assert "NONE" not in failed.text
    assert repository.get(case.id).status.value == "open"
    assert repository.get(case.id).version == 1
    assert repository.get(case.id).matched_resources == case.matched_resources


def test_foreign_and_incomplete_appointments_fail_closed(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    fhir.appointments = [_appointment(APPOINTMENT, OTHER_PATIENT)]
    response = _http(repository, fhir).get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    )
    assert response.status_code == 503
    assert APPOINTMENT not in response.text
    malformed = ScriptedFhir()
    malformed.appointment_status = BoundedSearchStatus.FAILED
    assert _http(repository, malformed).get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    ).status_code == 503


@pytest.mark.parametrize(
    ("value", "kind"),
    [
        ({"valueQuantity": {"value": 1.5, "unit": "mg", "system": "http://unitsofmeasure.org", "code": "mg"}}, "quantity"),
        ({"valueCodeableConcept": {"coding": [{"system": "http://snomed.info/sct", "code": "1", "display": "Synthetic"}], "text": "Synthetic"}}, "coded"),
        ({"valueString": "synthetic"}, "string"),
        ({"valueBoolean": False}, "boolean"),
        ({"valueInteger": 0}, "integer"),
        ({"valueRange": {"low": {"value": 1, "unit": "mg"}, "high": {"value": 2, "unit": "mg"}}}, "range"),
    ],
)
def test_supported_observation_values_project_without_extra_fields(value, kind):
    content = project_observation_content(value)
    rendered = content.model_dump(exclude_none=True)
    assert rendered["status"] == "available"
    assert rendered["kind"] == kind
    assert "interpretation" not in rendered
    assert "resourceType" not in rendered


def test_components_project_only_closed_values():
    content = project_observation_content(
        {
            "component": [
                {
                    "code": {"coding": [{"code": "a"}]},
                    "valueInteger": 2,
                },
                {
                    "code": {"text": "Synthetic"},
                    "valueBoolean": True,
                },
            ]
        }
    )
    rendered = content.model_dump(exclude_none=True)
    assert rendered["kind"] == "components"
    assert rendered["components"][0]["value"]["kind"] == "integer"
    assert rendered["components"][1]["value"]["value"] is True


@pytest.mark.parametrize(
    "resource",
    [
        {"valueDateTime": "2026-09-30T00:00:00Z"},
        {"valueString": "one", "valueInteger": 1},
        {"component": [{"code": {"coding": [{"code": "a"}]}, "valueString": "x"} for _ in range(26)]},
        {"valueCodeableConcept": {"coding": [{"code": str(index)} for index in range(11)]}},
        {"valueString": "x" * 513},
        {"valueQuantity": {"unit": "mg"}},
        {"valueRange": {"low": {"unit": "mg"}}},
        {"code": {"coding": "not-a-list"}},
        {},
    ],
)
def test_unsupported_observation_content_is_not_projected(resource):
    if "code" in resource and "valueString" not in resource and "component" not in resource and not any(
        key.startswith("value") for key in resource
    ):
        projected = project_observation_code(resource["code"])
        rendered = projected.model_dump(exclude_none=True)
    else:
        rendered = project_observation_content(resource).model_dump(exclude_none=True)
    assert rendered == {"status": "not_projected"}
    assert "x" * 513 not in json.dumps(rendered)
    assert "valueDateTime" not in json.dumps(rendered)


def test_code_bounds_do_not_truncate():
    exact = project_observation_code({"text": "y" * 512, "coding": [{"display": "z" * 512, "code": "1"}]})
    assert exact.status == "available"
    assert exact.text == "y" * 512
    oversized = project_observation_code({"text": "y" * 513, "coding": [{"code": "secret-code"}]})
    assert oversized.model_dump(exclude_none=True) == {"status": "not_projected"}
    assert "secret-code" not in oversized.model_dump_json()


def test_open_close_race_keeps_the_started_projection(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    entered = threading.Event()
    release = threading.Event()
    original = fhir.search

    def blocking_search(path: str, expected_resource_type: str):
        if expected_resource_type == "Patient":
            entered.set()
            assert release.wait(2)
        return original(path, expected_resource_type)

    fhir.search = blocking_search
    outcome: dict = {}

    def run() -> None:
        outcome["body"] = ClinicalReviewContextService(repository, fhir, clock=lambda: NOW).read(case.id)

    worker = threading.Thread(target=run)
    worker.start()
    assert entered.wait(2)
    repository.close(case.id, expected_version=1, outcome=ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION)
    release.set()
    worker.join(2)
    assert not worker.is_alive()
    assert outcome["body"].review_case.status == "open"
    assert repository.get(case.id).status.value == "closed"
    assert repository.get(case.id).version == 2


def test_concurrent_cases_do_not_share_read_results(tmp_path):
    repository = _repository(tmp_path)
    first = _create(repository, case_id=CASE, suffix="008")
    second = _create(repository, case_id=OTHER_CASE, suffix="009")
    barrier = threading.Barrier(2)
    results: dict[str, str] = {}

    def run(review_case_id: str, case_id: str, patient_id: str, suffix: str) -> None:
        fhir = ScriptedFhir(
            case_id=case_id,
            patient_id=patient_id,
            encounter_id=f"encounter-{suffix}",
            observation_id=f"observation-{suffix}",
        )
        fhir.patients = {case_id: _patient(patient_id, case_id)}
        fhir.appointments = []
        barrier.wait(2)
        body = ClinicalReviewContextService(repository, fhir, clock=lambda: NOW).read(review_case_id)
        results[review_case_id] = body.current_context.encounter.reference

    threads = [
        threading.Thread(target=run, args=(first.id, CASE, PATIENT, "008")),
        threading.Thread(target=run, args=(second.id, OTHER_CASE, OTHER_PATIENT, "009")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(2)
    assert results[first.id] == f"Encounter/{ENCOUNTER}"
    assert results[second.id] == "Encounter/encounter-009"


@pytest.mark.parametrize("base_url", ["", "not-a-url"])
def test_invalid_fhir_base_url_is_generic_503(tmp_path, monkeypatch, base_url):
    monkeypatch.setenv("FHIR_BASE_URL", base_url)
    repository = _repository(tmp_path)
    case = _create(repository)
    app.state.followup_review_repository = repository
    app.dependency_overrides[get_settings] = _settings
    response = TestClient(app).get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "Clinical review context unavailable"}
    rendered = response.text
    assert base_url not in rendered or base_url == ""
    for leaked in ("FHIR_BASE_URL", "is empty", "not a safe HTTP origin", "Internal Server Error"):
        assert leaked not in rendered


def test_unauthenticated_request_does_not_construct_the_fhir_client(tmp_path, monkeypatch):
    monkeypatch.setenv("FHIR_BASE_URL", "")
    repository = _repository(tmp_path)
    case = _create(repository)
    constructed = {"count": 0}

    def factory():
        constructed["count"] += 1
        raise AssertionError("FHIR client constructed")

    app.state.followup_review_repository = repository
    app.state.clinical_context_fhir_client = factory
    app.dependency_overrides[get_settings] = _settings
    response = TestClient(app).get(f"/internal/follow-up-review-cases/{case.id}/clinical-context")
    assert response.status_code == 401
    assert response.content == b""
    assert constructed["count"] == 0


def test_missing_case_and_closed_case_precede_fhir_client_construction(tmp_path, monkeypatch):
    monkeypatch.setenv("FHIR_BASE_URL", "")
    repository = _repository(tmp_path)
    case = _create(repository)
    repository.close(case.id, expected_version=1, outcome=ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION)
    app.state.followup_review_repository = repository
    app.dependency_overrides[get_settings] = _settings
    client = TestClient(app)
    missing = client.get(
        "/internal/follow-up-review-cases/00000000-0000-4000-8000-000000000000/clinical-context",
        headers=AUTH,
    )
    closed = client.get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    )
    assert missing.status_code == 404
    assert closed.status_code == 409
    assert "FHIR_BASE_URL" not in missing.text
    assert "FHIR_BASE_URL" not in closed.text


def test_fhir_factory_programming_error_is_not_mapped_to_clinical_503(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)

    def factory():
        raise RuntimeError("programming failure sentinel")

    app.state.followup_review_repository = repository
    app.state.clinical_context_fhir_client = factory
    app.dependency_overrides[get_settings] = _settings
    response = TestClient(app, raise_server_exceptions=False).get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    )
    assert response.status_code == 500
    assert "Clinical review context unavailable" not in response.text
    assert "programming failure sentinel" not in response.text


def test_malformed_quantity_comparator_stays_not_projected_on_http(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    fhir.observation = _observation(
        OBSERVATION,
        ENCOUNTER,
        PATIENT,
        value={"valueQuantity": {"value": 1, "comparator": []}},
    )
    body = _body(repository, fhir, case.id)
    assert body["currentContext"]["observation"]["content"] == {"status": "not_projected"}
    assert "comparator" not in json.dumps(body["currentContext"]["observation"]["content"])


@pytest.mark.parametrize("comparator", [[], {}, 1, True, "~"])
def test_unusable_quantity_comparator_is_not_projected(comparator):
    content = project_observation_content({"valueQuantity": {"value": 1, "comparator": comparator}})
    assert content.model_dump(exclude_none=True) == {"status": "not_projected"}


def test_supported_quantity_comparator_is_projected():
    content = project_observation_content({"valueQuantity": {"value": 1, "comparator": "<="}})
    rendered = content.model_dump(exclude_none=True)
    assert rendered["status"] == "available"
    assert rendered["comparator"] == "<="


@pytest.mark.parametrize(
    "resource",
    [
        {"valueRange": {"low": {"value": 1, "comparator": []}, "high": {"value": 2}}},
        {"valueRange": {"low": {"value": 1}, "high": {"value": 2, "comparator": {}}}},
        {
            "component": [
                {"code": {"coding": [{"code": "a"}]}, "valueQuantity": {"value": 1, "comparator": []}}
            ]
        },
        {
            "component": [
                {
                    "code": {"coding": [{"code": "a"}]},
                    "valueRange": {"low": {"value": 1, "comparator": True}},
                }
            ]
        },
    ],
)
def test_malformed_comparator_in_range_and_components_is_not_projected(resource):
    rendered = project_observation_content(resource).model_dump(exclude_none=True)
    assert rendered == {"status": "not_projected"}


@pytest.mark.parametrize(
    "concept",
    [
        {},
        {"text": ""},
        {"text": "   "},
        {"coding": []},
        {"coding": [], "text": ""},
    ],
)
def test_empty_codeable_concept_is_not_projected(concept):
    assert project_observation_code(concept).model_dump(exclude_none=True) == {"status": "not_projected"}
    content = project_observation_content({"valueCodeableConcept": concept})
    assert content.model_dump(exclude_none=True) == {"status": "not_projected"}


def test_meaningful_coded_values_remain_projected():
    coding_only = project_observation_content(
        {"valueCodeableConcept": {"coding": [{"system": "http://loinc.org", "code": "1234-5"}]}}
    )
    rendered = coding_only.model_dump(exclude_none=True)
    assert rendered["status"] == "available"
    assert rendered["kind"] == "coded"
    assert rendered["coding"] == [{"system": "http://loinc.org", "code": "1234-5"}]
    assert "text" not in rendered
    text_only = project_observation_content({"valueCodeableConcept": {"text": "  Synthetic result  "}})
    text_rendered = text_only.model_dump(exclude_none=True)
    assert text_rendered["status"] == "available"
    assert text_rendered["text"] == "  Synthetic result  "
    assert text_rendered["coding"] == []


def test_empty_observation_and_component_codes_are_not_projected():
    assert project_observation_code({}).model_dump(exclude_none=True) == {"status": "not_projected"}
    assert project_observation_code({"text": " \t "}).model_dump(exclude_none=True) == {"status": "not_projected"}
    empty_component = project_observation_content(
        {"component": [{"code": {"text": ""}, "valueInteger": 1}]}
    )
    whitespace_component = project_observation_content(
        {"component": [{"code": {"text": "   ", "coding": []}, "valueString": "kept"}]}
    )
    assert empty_component.model_dump(exclude_none=True) == {"status": "not_projected"}
    assert whitespace_component.model_dump(exclude_none=True) == {"status": "not_projected"}
    assert "kept" not in whitespace_component.model_dump_json()


def test_endpoint_does_not_call_a_model_or_persist_context():
    source = (
        inspect.getsource(ClinicalReviewContextService) + inspect.getsource(get_clinical_review_context_http)
    ).lower()
    for token in ("gemini", "chatgoogle", "system_instruction", "graph.invoke", "followupworkflow"):
        assert token not in source
    assert "sqlite" not in inspect.getsource(ClinicalReviewContextService).lower()
    assert "insert" not in inspect.getsource(ClinicalReviewContextService).lower()


def _missed_protocol(appointment_id: str = "noshow-008") -> ProtocolReviewResult:
    return ProtocolReviewResult(
        id=MISSED_FOLLOW_UP_REVIEW_V1,
        evaluation_status=ProtocolEvaluationStatus.MATCHED,
        reason_codes=("missed_follow_up_without_confirmed_replacement",),
        matched_resources=(f"Appointment/{appointment_id}",),
        human_review_status="required",
        human_review_reason="deterministic_missed_follow_up_protocol_match",
        action_status="proposed",
        action_type="review_follow_up_case",
    )


def test_missed_follow_up_context_reads_the_trigger_and_current_appointments(tmp_path):
    repository = _repository(tmp_path)
    case = FollowUpReviewCaseService(repository).ensure_for_protocol(CASE, _missed_protocol())
    assert case is not None
    fhir = ScriptedFhir()
    fhir.appointments = [
        _appointment("noshow-008", PATIENT, status="noshow", start="2026-01-01T00:00:00Z"),
        _appointment(APPOINTMENT, PATIENT, status="booked", start="2027-03-15T15:00:00Z"),
    ]
    body = _body(repository, fhir, case.id)
    assert body["schema"] == "CLINICAL_REVIEW_CONTEXT_V1"
    assert body["triggerProvenance"]["protocolId"] == MISSED_FOLLOW_UP_REVIEW_V1
    assert body["triggerProvenance"]["matchedResources"] == ["Appointment/noshow-008"]
    assert "encounter" not in body["currentContext"]
    assert "observation" not in body["currentContext"]
    assert body["currentContext"]["triggerAppointment"]["availability"] == "available"
    assert body["currentContext"]["triggerAppointment"]["status"] == "noshow"
    assert body["currentContext"]["appointments"]["classifications"] == ["UPCOMING_CONFIRMED", "OTHER"]
    assert {item["reference"] for item in body["currentContext"]["appointments"]["items"]} == {
        "Appointment/noshow-008",
        f"Appointment/{APPOINTMENT}",
    }
    rendered = json.dumps(body)
    assert PATIENT not in rendered
    assert "resourceType" not in rendered
    exact_types = [call[1] for call in fhir.calls if call[0] == "exact"]
    assert exact_types == ["Appointment"]
    stored = repository.get(case.id)
    assert stored is not None
    assert stored.status.value == "open"
    assert stored.matched_resources == ("Appointment/noshow-008",)


def test_missing_trigger_appointment_keeps_the_case_and_current_search(tmp_path):
    repository = _repository(tmp_path)
    case = FollowUpReviewCaseService(repository).ensure_for_protocol(CASE, _missed_protocol())
    assert case is not None
    fhir = ScriptedFhir()
    fhir.appointments = [_appointment(APPOINTMENT, PATIENT)]
    fhir.missing.add("noshow-008")
    body = _body(repository, fhir, case.id)
    assert body["retrieval"]["status"] == "provenance_resource_not_found"
    assert body["retrieval"]["reasonCodes"] == ["provenance_appointment_not_found"]
    assert body["currentContext"]["triggerAppointment"] == {
        "reference": "Appointment/noshow-008",
        "availability": "not_found",
    }
    assert body["currentContext"]["appointments"]["items"][0]["reference"] == f"Appointment/{APPOINTMENT}"
    assert repository.get(case.id).matched_resources == ("Appointment/noshow-008",)


def test_foreign_trigger_appointment_fails_closed(tmp_path):
    repository = _repository(tmp_path)
    case = FollowUpReviewCaseService(repository).ensure_for_protocol(CASE, _missed_protocol())
    assert case is not None
    fhir = ScriptedFhir()
    fhir.appointments = [_appointment("noshow-008", OTHER_PATIENT, status="noshow", start="2026-01-01T00:00:00Z")]
    response = _http(repository, fhir).get(
        f"/internal/follow-up-review-cases/{case.id}/clinical-context",
        headers=AUTH,
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Clinical review context unavailable"
    assert "noshow-008" not in response.text
    assert repository.get(case.id).matched_resources == ("Appointment/noshow-008",)
