"""MISSED_FOLLOW_UP_REVIEW_V1 acquisition, review cases, and internal HTTP."""

from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.followup_review import ReviewOutcome, build_review_identity
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.langgraph_fhir_client import (
    CASE_IDENTIFIER_SYSTEM,
    BoundedSearchResult,
    BoundedSearchStatus,
    PreparedReadClient,
    synthetic_appointment,
)
from app.langgraph_fhir_hapi import HapiReadClient, hapi_base_url
from app.langgraph_fhir_followup import FollowUpFHIRAdapter
from app.main import app, get_settings
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1
from app.post_consultation_review import POST_CONSULTATION_RESULT_REVIEW_V1


CASE = "SYN-FOLLOWUP-008"
PATIENT = "SYN-PATIENT-008"
TOKEN = "test-model-boundary-token"
AUTH = {"X-Service-Token": TOKEN}
INSTANT = datetime(2026, 9, 29, tzinfo=timezone.utc)


class Clock:
    def __init__(self) -> None:
        self.value = INSTANT

    def __call__(self):
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def _settings(**overrides) -> Settings:
    values = {
        "model_boundary_base_url": "http://model-boundary.test",
        "model_boundary_path": "/api/model-boundary/v1",
        "model_boundary_timeout_seconds": 5,
        "model_boundary_service_token": TOKEN,
        "host": "127.0.0.1",
        "port": 8090,
        "followup_agent_enabled": True,
        "ai_review_db_path": "unused-by-explicit-test-repository.sqlite3",
    }
    values.update(overrides)
    return Settings(**values)


def _appointment(appointment_id: str, status: str, start: str | None) -> dict:
    return synthetic_appointment(
        appointment_id=appointment_id,
        status=status,
        start=start,
        patient_id=PATIENT,
    )


def _client(monkeypatch, prepared: PreparedReadClient, repository, *, enabled: bool = True):
    def factory(instant: datetime) -> FollowUpFHIRAdapter:
        assert instant == INSTANT
        return FollowUpFHIRAdapter(prepared, now=lambda: instant)

    monkeypatch.setattr("app.missed_follow_up_service._utc_now", lambda: INSTANT)
    monkeypatch.setattr("app.missed_follow_up_service._live_adapter", factory)
    app.state.followup_review_repository = repository
    app.dependency_overrides[get_settings] = lambda: _settings(followup_agent_enabled=enabled)
    return TestClient(app)


def _repository(tmp_path: Path) -> SQLiteFollowUpReviewCaseRepository:
    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3", clock=Clock())
    repository.initialize()
    return repository


def _post(client: TestClient, case_id: str = CASE):
    return client.post("/internal/agent/missed-follow-up", headers=AUTH, json={"caseId": case_id})


def _count(path: Path) -> int:
    connection = sqlite3.connect(path)
    try:
        return int(connection.execute("SELECT COUNT(*) FROM follow_up_review_cases").fetchone()[0])
    finally:
        connection.close()


@pytest.fixture(autouse=True)
def _clean_state():
    app.dependency_overrides.clear()
    if hasattr(app.state, "followup_review_repository"):
        delattr(app.state, "followup_review_repository")
    yield
    app.dependency_overrides.clear()
    if hasattr(app.state, "followup_review_repository"):
        delattr(app.state, "followup_review_repository")


def test_past_noshow_creates_one_review_case(tmp_path, monkeypatch):
    prepared = PreparedReadClient(
        case_id=CASE,
        patient_id=PATIENT,
        appointments=[_appointment("noshow-1", "noshow", "2026-01-01T00:00:00Z")],
    )
    repository = _repository(tmp_path)
    response = _post(_client(monkeypatch, prepared, repository))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["protocolId"] == MISSED_FOLLOW_UP_REVIEW_V1
    assert body["evaluationStatus"] == "matched"
    assert body["reasonCodes"] == ["missed_follow_up_without_confirmed_replacement"]
    assert body["provenanceResources"] == ["Appointment/noshow-1"]
    assert body["reviewCases"][0]["matchedResources"] == ["Appointment/noshow-1"]
    assert body["reviewCases"][0]["status"] == "open"
    assert PATIENT not in response.text
    assert "resourceType" not in response.text
    assert all("Encounter" not in call and "Observation" not in call for call in prepared.calls)
    assert any(call.startswith("Appointment?") for call in prepared.calls)


def test_future_booked_does_not_create_a_review_case(tmp_path, monkeypatch):
    prepared = PreparedReadClient(
        case_id=CASE,
        patient_id=PATIENT,
        appointments=[
            _appointment("noshow-1", "noshow", "2026-01-01T00:00:00Z"),
            _appointment("booked-1", "booked", "2099-01-01T00:00:00Z"),
        ],
    )
    repository = _repository(tmp_path)
    response = _post(_client(monkeypatch, prepared, repository))
    body = response.json()
    assert body["evaluationStatus"] == "not_matched"
    assert body["reasonCodes"] == ["confirmed_future_follow_up_exists"]
    assert body["reviewCases"] == []
    assert body["provenanceResources"] == ["Appointment/noshow-1", "Appointment/booked-1"]
    assert _count(tmp_path / "review.sqlite3") == 0


def test_cancelled_and_proposed_do_not_match(tmp_path, monkeypatch):
    cancelled = PreparedReadClient(
        case_id=CASE,
        patient_id=PATIENT,
        appointments=[_appointment("cancelled-1", "cancelled", "2026-01-01T00:00:00Z")],
    )
    repository = _repository(tmp_path)
    cancelled_body = _post(_client(monkeypatch, cancelled, repository)).json()
    proposed = PreparedReadClient(
        case_id=CASE,
        patient_id=PATIENT,
        appointments=[_appointment("proposed-1", "proposed", "2099-01-01T00:00:00Z")],
    )
    proposed_body = _post(_client(monkeypatch, proposed, repository)).json()
    assert cancelled_body["reasonCodes"] == ["eligible_past_noshow_absent"]
    assert proposed_body["reasonCodes"] == ["eligible_past_noshow_absent"]
    assert _count(tmp_path / "review.sqlite3") == 0


def test_invalid_noshow_start_and_incomplete_search_do_not_create_cases(tmp_path, monkeypatch):
    invalid = PreparedReadClient(
        case_id=CASE,
        patient_id=PATIENT,
        appointments=[_appointment("noshow-1", "noshow", None)],
    )
    repository = _repository(tmp_path)
    invalid_body = _post(_client(monkeypatch, invalid, repository)).json()
    assert invalid_body["evaluationStatus"] == "insufficient"
    assert invalid_body["reasonCodes"] == ["appointment_start_missing_or_invalid"]
    assert invalid_body["reviewCases"] == []

    class Incomplete(PreparedReadClient):
        def search(self, path: str, expected_resource_type: str) -> BoundedSearchResult:
            result = super().search(path, expected_resource_type)
            if expected_resource_type == "Appointment":
                return BoundedSearchResult(BoundedSearchStatus.INCOMPLETE_LIMIT, result.resources)
            return result

    incomplete = Incomplete(
        case_id=CASE,
        patient_id=PATIENT,
        appointments=[_appointment("noshow-1", "noshow", "2026-01-01T00:00:00Z")],
    )
    incomplete_body = _post(_client(monkeypatch, incomplete, repository)).json()
    assert incomplete_body["evaluationStatus"] == "insufficient"
    assert incomplete_body["reasonCodes"] == ["appointment_search_incomplete"]
    assert incomplete_body["reviewCases"] == []
    assert _count(tmp_path / "review.sqlite3") == 0


def test_unavailable_foreign_and_conflicting_appointments_create_no_case(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    unavailable = PreparedReadClient(
        case_id=CASE,
        patient_id=PATIENT,
        appointments=[],
        fail_appointment_read=True,
    )
    unavailable_body = _post(_client(monkeypatch, unavailable, repository)).json()
    assert unavailable_body["evaluationStatus"] == "unavailable"
    assert unavailable_body["reviewCases"] == []

    foreign = dict(_appointment("foreign-1", "noshow", "2026-01-01T00:00:00Z"))
    foreign["participant"] = [{"actor": {"reference": "Patient/other-patient"}, "status": "accepted"}]
    foreign_client = PreparedReadClient(case_id=CASE, patient_id=PATIENT, appointments=[foreign])
    foreign_body = _post(_client(monkeypatch, foreign_client, repository)).json()
    assert foreign_body["evaluationStatus"] == "unavailable"
    assert foreign_body["reasonCodes"] == ["appointment_integrity_failure"]

    first = _appointment("same-id", "noshow", "2026-01-01T00:00:00Z")
    second = _appointment("same-id", "booked", "2099-01-01T00:00:00Z")
    conflict = PreparedReadClient(case_id=CASE, patient_id=PATIENT, appointments=[first, second])
    conflict_body = _post(_client(monkeypatch, conflict, repository)).json()
    assert conflict_body["evaluationStatus"] == "unavailable"
    assert _count(tmp_path / "review.sqlite3") == 0


def test_two_noshow_cases_are_reused_and_a_later_booking_does_not_rewrite_them(tmp_path, monkeypatch):
    appointments = [
        _appointment("noshow-later", "noshow", "2026-06-01T00:00:00Z"),
        _appointment("noshow-earlier", "noshow", "2026-01-01T00:00:00Z"),
    ]
    prepared = PreparedReadClient(case_id=CASE, patient_id=PATIENT, appointments=appointments)
    repository = _repository(tmp_path)
    client = _client(monkeypatch, prepared, repository)
    first = _post(client).json()
    assert [item["matchedResources"] for item in first["reviewCases"]] == [
        ["Appointment/noshow-earlier"],
        ["Appointment/noshow-later"],
    ]
    ids = [item["reviewCaseId"] for item in first["reviewCases"]]
    second = _post(client).json()
    assert [item["reviewCaseId"] for item in second["reviewCases"]] == ids
    assert _count(tmp_path / "review.sqlite3") == 2
    repository.close(ids[0], expected_version=1, outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED)
    third = _post(client).json()
    assert third["reviewCases"][0]["status"] == "closed"
    assert third["reviewCases"][0]["version"] == 2
    assert third["reviewCases"][1]["status"] == "open"
    assert third["reviewCases"][1]["version"] == 1
    prepared.appointments.append(_appointment("booked-later", "booked", "2099-01-01T00:00:00Z"))
    blocked = _post(client).json()
    assert blocked["evaluationStatus"] == "not_matched"
    assert blocked["reasonCodes"] == ["confirmed_future_follow_up_exists"]
    assert blocked["reviewCases"] == []
    stored = repository.get(ids[1])
    assert stored is not None
    assert stored.status.value == "open"
    assert stored.matched_resources == ("Appointment/noshow-later",)
    assert stored.protocol_id == MISSED_FOLLOW_UP_REVIEW_V1


def test_review_identity_separates_protocol_and_appointment():
    missed = build_review_identity(CASE, MISSED_FOLLOW_UP_REVIEW_V1, ["Appointment/noshow-1"])
    repeated = build_review_identity(CASE, MISSED_FOLLOW_UP_REVIEW_V1, ["Appointment/noshow-1"])
    other_appointment = build_review_identity(CASE, MISSED_FOLLOW_UP_REVIEW_V1, ["Appointment/noshow-2"])
    other_protocol = build_review_identity(CASE, POST_CONSULTATION_RESULT_REVIEW_V1, ["Appointment/noshow-1"])
    assert missed == repeated
    assert missed != other_appointment
    assert missed != other_protocol


def test_endpoint_auth_flag_and_validation(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    prepared = PreparedReadClient(case_id=CASE, patient_id=PATIENT, appointments=[])
    client = _client(monkeypatch, prepared, repository)
    denied = client.post("/internal/agent/missed-follow-up", json={"caseId": CASE})
    assert denied.status_code == 401
    assert denied.content == b""
    invalid = client.post(
        "/internal/agent/missed-follow-up",
        headers=AUTH,
        json={"caseId": CASE, "appointmentId": "caller-supplied"},
    )
    assert invalid.status_code == 422
    assert PATIENT not in invalid.text
    assert "Appointment?" not in invalid.text
    disabled = _client(monkeypatch, prepared, repository, enabled=False)
    blocked = disabled.post("/internal/agent/missed-follow-up", headers=AUTH, json={"caseId": CASE})
    assert blocked.status_code == 503
    assert blocked.json()["detail"] == "Follow-up agent is disabled"


def test_matched_without_a_repository_is_a_fixed_persistence_error(tmp_path, monkeypatch):
    del tmp_path
    prepared = PreparedReadClient(
        case_id=CASE,
        patient_id=PATIENT,
        appointments=[_appointment("noshow-1", "noshow", "2026-01-01T00:00:00Z")],
    )

    def factory(instant: datetime) -> FollowUpFHIRAdapter:
        return FollowUpFHIRAdapter(prepared, now=lambda: instant)

    monkeypatch.setattr("app.missed_follow_up_service._utc_now", lambda: INSTANT)
    monkeypatch.setattr("app.missed_follow_up_service._live_adapter", factory)
    app.dependency_overrides[get_settings] = lambda: _settings()
    response = TestClient(app).post("/internal/agent/missed-follow-up", headers=AUTH, json={"caseId": CASE})
    assert response.status_code == 503
    assert response.json()["detail"] == "Follow-up review persistence unavailable"
    assert "Traceback" not in response.text


def _wait_for_indexed_appointment(base: str, patient_id: str, appointment_id: str) -> None:
    path = f"{base}/Appointment?patient=Patient/{patient_id}&_count=25"
    for _ in range(20):
        response = httpx.get(path, headers={"Accept": "application/fhir+json"}, timeout=5.0)
        payload = response.json()
        identifiers = [
            (entry.get("resource") or {}).get("id")
            for entry in payload.get("entry") or []
            if isinstance(entry, dict)
        ]
        if appointment_id in identifiers:
            return
        time.sleep(0.5)
    raise AssertionError("local appointment search did not include the seeded appointment")


def _hapi_enabled() -> bool:
    return os.getenv("RUN_HAPI_INTEGRATION_TESTS", "false").strip().lower() == "true"


def _store(base: str, path: str, body: dict) -> None:
    response = httpx.put(
        f"{base}/{path}",
        json=body,
        headers={"Accept": "application/fhir+json", "Content-Type": "application/fhir+json"},
        timeout=5.0,
    )
    if response.status_code not in {200, 201}:
        raise AssertionError(f"seed failed with HTTP {response.status_code}")


@pytest.mark.skipif(not _hapi_enabled(), reason="set RUN_HAPI_INTEGRATION_TESTS=true to call the local server")
def test_local_hapi_noshow_case_survives_a_later_booking(tmp_path):
    base = hapi_base_url()
    httpx.delete(f"{base}/Appointment/missed-fu-booked-014", timeout=5.0)
    patient_id = "missed-fu-patient-014"
    case_id = "SYN-FOLLOWUP-014"
    _store(
        base,
        f"Patient/{patient_id}",
        {
            "resourceType": "Patient",
            "id": patient_id,
            "identifier": [{"system": CASE_IDENTIFIER_SYSTEM, "value": case_id}],
        },
    )
    _store(
        base,
        "Appointment/missed-fu-noshow-014",
        {
            "resourceType": "Appointment",
            "id": "missed-fu-noshow-014",
            "status": "noshow",
            "start": "2020-01-01T00:00:00Z",
            "participant": [{"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"}],
        },
    )
    repository = _repository(tmp_path)
    app.state.followup_review_repository = repository
    app.state.clinical_context_fhir_client = lambda: HapiReadClient(base)
    app.dependency_overrides[get_settings] = lambda: _settings()
    client = TestClient(app)
    try:
        _assert_local_hapi_case(client, repository, base, case_id, patient_id)
    finally:
        if hasattr(app.state, "clinical_context_fhir_client"):
            delattr(app.state, "clinical_context_fhir_client")


def _assert_local_hapi_case(client: TestClient, repository, base: str, case_id: str, patient_id: str) -> None:
    _wait_for_indexed_appointment(base, patient_id, "missed-fu-noshow-014")
    matched = client.post("/internal/agent/missed-follow-up", headers=AUTH, json={"caseId": case_id})
    assert matched.status_code == 200, matched.text
    matched_body = matched.json()
    assert matched_body["evaluationStatus"] == "matched"
    assert matched_body["reviewCases"][0]["matchedResources"] == ["Appointment/missed-fu-noshow-014"]
    review_case_id = matched_body["reviewCases"][0]["reviewCaseId"]
    _store(
        base,
        "Appointment/missed-fu-booked-014",
        {
            "resourceType": "Appointment",
            "id": "missed-fu-booked-014",
            "status": "booked",
            "start": "2099-01-01T00:00:00Z",
            "participant": [{"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"}],
        },
    )
    _wait_for_indexed_appointment(base, patient_id, "missed-fu-booked-014")
    blocked = client.post("/internal/agent/missed-follow-up", headers=AUTH, json={"caseId": case_id})
    assert blocked.status_code == 200, blocked.text
    blocked_body = blocked.json()
    assert blocked_body["evaluationStatus"] == "not_matched"
    assert blocked_body["reasonCodes"] == ["confirmed_future_follow_up_exists"]
    assert blocked_body["reviewCases"] == []
    context = client.get(
        f"/internal/follow-up-review-cases/{review_case_id}/clinical-context",
        headers=AUTH,
    )
    assert context.status_code == 200, context.text
    body = context.json()
    assert body["triggerProvenance"]["matchedResources"] == ["Appointment/missed-fu-noshow-014"]
    assert "encounter" not in body["currentContext"]
    assert "observation" not in body["currentContext"]
    references = {item["reference"] for item in body["currentContext"]["appointments"]["items"]}
    assert "Appointment/missed-fu-booked-014" in references
    assert patient_id not in context.text
    stored = repository.get(review_case_id)
    assert stored is not None
    assert stored.status.value == "open"
    assert stored.matched_resources == ("Appointment/missed-fu-noshow-014",)


def test_protocol_path_does_not_invoke_the_narrative_workflow():
    root = Path(__file__).resolve().parents[1] / "app"
    sources = "\n".join(
        (root / name).read_text(encoding="utf-8").lower()
        for name in ("missed_follow_up_review.py", "missed_follow_up_service.py")
    )
    for token in (
        "gemini",
        "toolnode",
        "followupworkflow",
        "search_encounters_for_protocol",
        "search_observations_for_protocol",
        "followup_required",
    ):
        assert token not in sources
