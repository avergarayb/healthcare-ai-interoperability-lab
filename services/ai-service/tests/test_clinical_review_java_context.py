"""Clinical review context reads through the Java clinical read client."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import pytest
from fastapi.testclient import TestClient

from app.clinical_read_client import ClinicalReadClient
from app.clinical_review_context import ClinicalContextUnavailable, ClinicalReviewContextService
from app.config import Settings
from app.followup_review import FollowUpReviewCaseService
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.human_development_auth import SESSION_COOKIE
from app.human_review_client import MSG_CONTEXT_UNAVAILABLE
from app.human_session import HumanSessionService
from app.human_session_sqlite import SQLiteHumanSessionRepository
from app.institutional_knowledge import RetrievalResult, RetrievedChunk
from app.langgraph_fhir_client import CASE_IDENTIFIER_SYSTEM
from app.llm_provider import ProviderGeneration
from app.main import app, get_settings
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)


TOKEN = "test-model-boundary-token"
SIGNING_SECRET = "synthetic-form-signing-secret-b"
DEV_SECRET = "development-secret-value-32chars-min"
ORIGIN = {"origin": "http://127.0.0.1"}
CASE = "SYN-FOLLOWUP-008"
MISSED_CASE = "SYN-FOLLOWUP-009"
PATIENT = "SYN-PATIENT-008"
ENCOUNTER = "encounter-008"
OBSERVATION = "observation-008"
APPOINTMENT = "appointment-008"
TRIGGER = "noshow-008"
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
CHUNK = "a" * 64


class Clock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self):
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def _settings() -> Settings:
    return Settings(
        model_boundary_base_url="http://interop.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token=TOKEN,
        human_review_form_signing_secret=SIGNING_SECRET,
        host="127.0.0.1",
        port=8090,
        followup_agent_enabled=True,
        ai_review_db_path="unused-by-explicit-test-repository.sqlite3",
        human_session_db_path="unused-human-session-overridden-by-state.sqlite3",
        human_review_development_auth_enabled=True,
        human_review_development_auth_secret=DEV_SECRET,
        human_review_development_principal_id="lab-reviewer",
        human_review_development_principal_display_name="Lab reviewer",
    )


def _post_protocol() -> ProtocolReviewResult:
    return ProtocolReviewResult(
        id=POST_CONSULTATION_RESULT_REVIEW_V1,
        evaluation_status=ProtocolEvaluationStatus.MATCHED,
        reason_codes=("post_consultation_result_requires_review",),
        matched_resources=(f"Encounter/{ENCOUNTER}", f"Observation/{OBSERVATION}"),
        human_review_status="required",
        human_review_reason="deterministic_post_consultation_protocol_match",
        action_status="proposed",
        action_type="review_follow_up_case",
    )


def _missed_protocol() -> ProtocolReviewResult:
    return ProtocolReviewResult(
        id=MISSED_FOLLOW_UP_REVIEW_V1,
        evaluation_status=ProtocolEvaluationStatus.MATCHED,
        reason_codes=("missed_follow_up_without_confirmed_replacement",),
        matched_resources=(f"Appointment/{TRIGGER}",),
        human_review_status="required",
        human_review_reason="deterministic_missed_follow_up_protocol_match",
        action_status="proposed",
        action_type="review_follow_up_case",
    )


def _patient(case_id: str) -> dict:
    return {
        "resourceType": "Patient",
        "id": PATIENT,
        "identifier": [{"system": CASE_IDENTIFIER_SYSTEM, "value": case_id}],
    }


def _encounter() -> dict:
    return {
        "resourceType": "Encounter",
        "id": ENCOUNTER,
        "status": "finished",
        "subject": {"reference": f"Patient/{PATIENT}"},
        "period": {"end": "2026-09-30T11:30:00Z"},
    }


def _observation() -> dict:
    return {
        "resourceType": "Observation",
        "id": OBSERVATION,
        "status": "final",
        "subject": {"reference": f"Patient/{PATIENT}"},
        "encounter": {"reference": f"Encounter/{ENCOUNTER}"},
        "issued": "2026-09-30T11:40:00Z",
        "code": {"text": "Synthetic result"},
        "valueString": "synthetic-result",
    }


def _appointment(appointment_id: str, status: str, start: str) -> dict:
    return {
        "resourceType": "Appointment",
        "id": appointment_id,
        "status": status,
        "start": start,
        "participant": [{"actor": {"reference": f"Patient/{PATIENT}"}, "status": "accepted"}],
    }


def _envelope(kind: str, payload: dict, collection_status: str = "complete") -> dict:
    if kind == "read":
        return {"contractVersion": "clinical-read-v1", "destination": "local-hapi", "resource": payload}
    return {
        "contractVersion": "clinical-read-v1",
        "destination": "local-hapi",
        "collectionStatus": collection_status,
        "resourceType": payload["resourceType"],
        "resources": payload["resources"],
    }


def _java_client(mode: str) -> tuple[ClinicalReadClient, httpx.Client]:
    upcoming = _appointment(APPOINTMENT, "booked", "2099-01-01T00:00:00Z")
    trigger = _appointment(TRIGGER, "noshow", "2026-01-01T00:00:00Z")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "interop.test"
        assert request.url.path.startswith("/api/clinical-read/v1/")
        assert "8080" not in str(request.url)
        assert request.headers["X-Service-Token"] == TOKEN
        path = request.url.path
        if mode == "down" and path.endswith("/patients"):
            return httpx.Response(503, json={"error": "unavailable"})
        if mode == "conflict" and path.endswith(f"/encounters/{ENCOUNTER}"):
            return httpx.Response(409, json={"error": "operation_not_supported"})
        if mode == "invalid" and path.endswith(f"/observations/{OBSERVATION}"):
            return httpx.Response(422, json={"error": "invalid_source"})
        if mode == "missing" and path.endswith(f"/encounters/{ENCOUNTER}"):
            return httpx.Response(404, json={"error": "not_found"})
        if mode == "incomplete" and path.endswith("/appointments") and "patient" in request.url.params:
            return httpx.Response(
                200,
                json=_envelope("search", {"resourceType": "Appointment", "resources": [upcoming]}, "incomplete"),
            )
        if path.endswith("/patients") and "identifierValue" in request.url.params:
            case_id = request.url.params["identifierValue"]
            return httpx.Response(200, json=_envelope("search", {"resourceType": "Patient", "resources": [_patient(case_id)]}))
        if path.endswith(f"/encounters/{ENCOUNTER}"):
            return httpx.Response(200, json=_envelope("read", _encounter()))
        if path.endswith(f"/observations/{OBSERVATION}"):
            return httpx.Response(200, json=_envelope("read", _observation()))
        if path.endswith(f"/appointments/{TRIGGER}"):
            return httpx.Response(200, json=_envelope("read", trigger))
        if path.endswith("/appointments"):
            resources = [trigger] if request.url.params.get("patient") == PATIENT and mode == "missed" else [upcoming]
            return httpx.Response(200, json=_envelope("search", {"resourceType": "Appointment", "resources": resources}))
        raise AssertionError(str(request.url))

    http = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    client = ClinicalReadClient("http://interop.test", TOKEN, timeout_seconds=5, http_client=http)
    return client, http


def _repository(tmp_path):
    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3", clock=Clock())
    repository.initialize()
    return repository


def _service(repository, client: ClinicalReadClient) -> ClinicalReviewContextService:
    return ClinicalReviewContextService(repository, client, clock=lambda: NOW)


@pytest.fixture(autouse=True)
def _clean_state():
    app.dependency_overrides.clear()
    for name in (
        "followup_review_repository",
        "clinical_context_fhir_client",
        "human_session_repository",
        "institutional_knowledge",
        "ai_assistance_provider",
    ):
        if hasattr(app.state, name):
            delattr(app.state, name)
    yield
    app.dependency_overrides.clear()
    for name in (
        "followup_review_repository",
        "clinical_context_fhir_client",
        "human_session_repository",
        "institutional_knowledge",
        "ai_assistance_provider",
    ):
        if hasattr(app.state, name):
            delattr(app.state, name)


def test_open_cases_keep_context_and_errors_stay_inconclusive(tmp_path):
    repository = _repository(tmp_path)
    post = FollowUpReviewCaseService(repository).ensure_for_protocol(CASE, _post_protocol())
    missed = FollowUpReviewCaseService(repository).ensure_for_protocol(MISSED_CASE, _missed_protocol())
    assert post is not None and missed is not None
    complete, complete_http = _java_client("ok")
    missed_client, missed_http = _java_client("missed")
    missing, missing_http = _java_client("missing")
    conflict, conflict_http = _java_client("conflict")
    invalid, invalid_http = _java_client("invalid")
    down, down_http = _java_client("down")
    incomplete, incomplete_http = _java_client("incomplete")
    try:
        body = _service(repository, complete).read(post.id)
        missed_body = _service(repository, missed_client).read(missed.id)
        hidden = _service(repository, missing).read(post.id)
        with pytest.raises(ClinicalContextUnavailable):
            _service(repository, conflict).read(post.id)
        with pytest.raises(ClinicalContextUnavailable):
            _service(repository, invalid).read(post.id)
        with pytest.raises(ClinicalContextUnavailable):
            _service(repository, down).read(post.id)
        with pytest.raises(ClinicalContextUnavailable):
            _service(repository, incomplete).read(post.id)
    finally:
        for http in (complete_http, missed_http, missing_http, conflict_http, invalid_http, down_http, incomplete_http):
            http.close()

    assert body.retrieval.status == "complete"
    assert body.current_context.encounter.reference == f"Encounter/{ENCOUNTER}"
    assert body.current_context.encounter.status == "finished"
    assert body.current_context.observation.reference == f"Observation/{OBSERVATION}"
    assert body.current_context.appointments.collection_status == "complete"
    assert body.current_context.appointments.classifications == ["UPCOMING_CONFIRMED"]
    assert missed_body.trigger_provenance.protocol_id == MISSED_FOLLOW_UP_REVIEW_V1
    assert missed_body.current_context.trigger_appointment.reference == f"Appointment/{TRIGGER}"
    assert missed_body.current_context.trigger_appointment.availability == "available"
    assert missed_body.current_context.trigger_appointment.status == "noshow"
    assert hidden.retrieval.status == "provenance_resource_not_found"
    assert hidden.current_context.encounter.availability == "not_found"
    assert hidden.retrieval.reason_codes == ["provenance_encounter_not_found"]


def test_factory_serves_context_review_page_and_assistance(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    case = FollowUpReviewCaseService(repository).ensure_for_protocol(CASE, _post_protocol())
    assert case is not None
    client, http = _java_client("ok")
    built: list[Settings] = []

    def from_settings(settings: Settings, *, http_client=None):
        built.append(settings)
        return client

    monkeypatch.setenv("MODEL_BOUNDARY_BASE_URL", "http://interop.test")
    monkeypatch.setenv("MODEL_BOUNDARY_SERVICE_TOKEN", TOKEN)
    monkeypatch.setenv("MODEL_BOUNDARY_TIMEOUT_SECONDS", "5")
    monkeypatch.setattr(ClinicalReadClient, "from_settings", classmethod(lambda cls, settings, http_client=None: from_settings(settings, http_client=http_client)))
    store = SQLiteHumanSessionRepository(tmp_path / "human-session.sqlite3")
    store.initialize()
    app.state.followup_review_repository = repository
    app.state.human_session_repository = store
    app.state.institutional_knowledge = _Knowledge()
    app.state.ai_assistance_provider = _Provider()
    app.dependency_overrides[get_settings] = _settings
    browser = TestClient(app, base_url="http://127.0.0.1")
    try:
        context = browser.get(
            f"/internal/follow-up-review-cases/{case.id}/clinical-context",
            headers={"X-Service-Token": TOKEN},
        )
        login = browser.post(
            "/review-login",
            content=urlencode({"developmentSecret": DEV_SECRET}),
            headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )
        page = browser.get(f"/review-cases/{case.id}")
        fields = {}
        for name in ("assistanceExpiry", "assistanceToken"):
            marker = f'name="{name}" value="'
            start = page.text.index(marker) + len(marker)
            fields[name] = page.text[start:page.text.index('"', start)]
        posted = browser.post(
            f"/review-cases/{case.id}/ai-assistance",
            content=urlencode(fields),
            headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )
        shown = browser.get(posted.headers["location"])
    finally:
        http.close()

    assert context.status_code == 200
    assert context.json()["retrieval"]["status"] == "complete"
    assert context.json()["currentContext"]["encounter"]["reference"] == f"Encounter/{ENCOUNTER}"
    assert login.status_code == 303
    assert browser.cookies.get(SESSION_COOKIE)
    assert page.status_code == 200
    assert "<h2>Contexto clínico actual</h2>" in page.text
    assert "finished" in page.text
    assert "Próxima y confirmada" in page.text
    assert PATIENT not in page.text
    assert posted.status_code == 303
    assert "JAVA-CONTEXT-SUMMARY" in shown.text
    assert built
    assert built[0].model_boundary_base_url == "http://interop.test"
    assert built[0].model_boundary_service_token == TOKEN
    assert built[0].model_boundary_timeout_seconds == 5
    assert not hasattr(app.state, "clinical_context_fhir_client")
    assert HumanSessionService(
        store,
        clock=lambda: datetime.now(timezone.utc),
    ).resolve(browser.cookies.get(SESSION_COOKIE)).session_id


def test_factory_error_does_not_render_a_complete_context(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    case = FollowUpReviewCaseService(repository).ensure_for_protocol(CASE, _post_protocol())
    assert case is not None
    client, http = _java_client("conflict")
    monkeypatch.setattr(
        ClinicalReadClient,
        "from_settings",
        classmethod(lambda cls, settings, http_client=None: client),
    )
    store = SQLiteHumanSessionRepository(tmp_path / "human-session.sqlite3")
    store.initialize()
    app.state.followup_review_repository = repository
    app.state.human_session_repository = store
    app.dependency_overrides[get_settings] = _settings
    browser = TestClient(app, base_url="http://127.0.0.1")
    try:
        context = browser.get(
            f"/internal/follow-up-review-cases/{case.id}/clinical-context",
            headers={"X-Service-Token": TOKEN},
        )
        browser.post(
            "/review-login",
            content=urlencode({"developmentSecret": DEV_SECRET}),
            headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )
        page = browser.get(f"/review-cases/{case.id}")
    finally:
        http.close()

    assert context.status_code == 503
    assert context.json() == {"detail": "Clinical review context unavailable"}
    assert "finished" not in context.text
    assert page.status_code == 200
    assert MSG_CONTEXT_UNAVAILABLE in page.text
    assert "Próxima y confirmada" not in page.text


class _Knowledge:
    def retrieve(self, request):
        return RetrievalResult(
            status="FOUND",
            protocol_id=request.protocolId,
            chunks=(
                RetrievedChunk(
                    document_id="DOC",
                    title="Procedure",
                    version="1.0",
                    document_status="active",
                    section="Purpose",
                    ordinal=1,
                    chunk_id=CHUNK,
                    content_hash="c" * 64,
                    language="en",
                    synthetic=True,
                    score=0.9,
                    text="Institutional procedure text.",
                ),
            ),
        )


class _Provider:
    def generate_structured(self, *, system_instruction, contents, response_json_schema, max_output_tokens):
        return ProviderGeneration(
            invocation_started=True,
            text=json.dumps(
                {
                    "summary": {"text": "JAVA-CONTEXT-SUMMARY", "citedChunkIds": [CHUNK]},
                    "reviewPoints": [{"text": "Confirm the recorded operational status.", "citedChunkIds": [CHUNK]}],
                    "limitations": [],
                }
            ),
        )
