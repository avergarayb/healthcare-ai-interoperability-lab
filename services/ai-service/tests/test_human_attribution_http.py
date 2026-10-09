from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.clinical_review_context import ClinicalContextUnavailable
from app.config import Settings
from app.followup_coordination_action import FollowUpCoordinationActionService
from app.followup_review import FollowUpReviewCaseService, ReviewCaseStatus, ReviewOutcome
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.human_development_auth import SESSION_COOKIE
from app.human_review_client import (
    MSG_CLOSE_INVALID,
    MSG_FORM_INVALID,
    issue_controlled_action_token,
    issue_form_token,
)
from app.human_session import HumanSessionService, SESSION_TTL_SECONDS
from app.human_session_sqlite import SQLiteHumanSessionRepository
from app.main import app, get_settings
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)


SIGNING_SECRET = "synthetic-form-signing-secret-b"
DEV_SECRET = "development-secret-value-32chars-min"
SERVICE_TOKEN = "synthetic-service-token-a"
ORIGIN = {"origin": "http://127.0.0.1"}
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self) -> None:
        self.moment = NOW

    def __call__(self):
        return self.moment


def _settings(*, enabled: bool = True) -> Settings:
    return Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token=SERVICE_TOKEN,
        human_review_form_signing_secret=SIGNING_SECRET,
        host="127.0.0.1",
        port=8090,
        followup_agent_enabled=True,
        ai_review_db_path="unused-by-explicit-test-repository.sqlite3",
        human_session_db_path="unused-human-session-overridden-by-state.sqlite3",
        human_review_development_auth_enabled=enabled,
        human_review_development_auth_secret=DEV_SECRET,
        human_review_development_principal_id="lab-reviewer",
        human_review_development_principal_display_name="Lab reviewer",
    )


def _unavailable_fhir():
    raise ClinicalContextUnavailable("synthetic context is not loaded")


@pytest.fixture(autouse=True)
def _clean_state():
    app.dependency_overrides.clear()
    for name in (
        "followup_review_repository",
        "clinical_context_fhir_client",
        "human_session_repository",
        "human_session_clock",
    ):
        if hasattr(app.state, name):
            delattr(app.state, name)
    yield
    app.dependency_overrides.clear()
    for name in (
        "followup_review_repository",
        "clinical_context_fhir_client",
        "human_session_repository",
        "human_session_clock",
    ):
        if hasattr(app.state, name):
            delattr(app.state, name)


def _repository(tmp_path) -> SQLiteFollowUpReviewCaseRepository:
    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3", clock=lambda: NOW)
    repository.initialize()
    return repository


def _create(repository):
    created = FollowUpReviewCaseService(repository).ensure_for_protocol(
        "SYN-FOLLOWUP-001",
        ProtocolReviewResult(
            id=POST_CONSULTATION_RESULT_REVIEW_V1,
            evaluation_status=ProtocolEvaluationStatus.MATCHED,
            reason_codes=("post_consultation_result_requires_review",),
            matched_resources=("Encounter/encounter-001", "Observation/observation-001"),
            human_review_status="required",
            human_review_reason="deterministic_post_consultation_protocol_match",
            action_status="proposed",
            action_type="review_follow_up_case",
        ),
    )
    assert created is not None
    return created


def _bind(repository, *, enabled: bool = True, clock: Clock | None = None) -> TestClient:
    app.state.followup_review_repository = repository
    app.state.clinical_context_fhir_client = _unavailable_fhir
    store = SQLiteHumanSessionRepository(repository.database_path.parent / "human-session.sqlite3")
    store.initialize()
    app.state.human_session_repository = store
    if clock is not None:
        app.state.human_session_clock = clock
    app.dependency_overrides[get_settings] = lambda: _settings(enabled=enabled)
    return TestClient(app, base_url="http://127.0.0.1")


def _login(client: TestClient) -> None:
    response = client.post(
        "/review-login",
        content=urlencode({"developmentSecret": DEV_SECRET}),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _session(client: TestClient, clock: Clock | None = None):
    token = client.cookies.get(SESSION_COOKIE)
    assert token
    service = HumanSessionService(
        app.state.human_session_repository,
        clock=clock or (lambda: datetime.now(timezone.utc)),
    )
    return service.resolve(token)


def _hidden(html: str, name: str) -> str:
    marker = f'name="{name}" value="'
    start = html.index(marker) + len(marker)
    return html[start:html.index('"', start)]


def _post_form(client: TestClient, path: str, payload: dict[str, str]):
    return client.post(
        path,
        content=urlencode(payload),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


def _attributions(path):
    connection = sqlite3.connect(path)
    try:
        return connection.execute(
            """
            SELECT operation, principal_id, authenticator_id, session_id
            FROM follow_up_human_attributions
            ORDER BY operation
            """
        ).fetchall()
    finally:
        connection.close()


def test_http_close_records_the_server_session_principal(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    client = _bind(repository)
    _login(client)
    session = _session(client)
    page = client.get(f"/review-cases/{case.id}")
    assert "Cierre del caso: aún no está cerrado." in page.text
    assert "Solicitud interna de coordinación registrada." not in page.text
    assert "lab-reviewer" not in page.text
    assert session.session_id not in page.text
    closed = _post_form(
        client,
        f"/review-cases/{case.id}/close",
        {
            "outcome": "follow_up_coordination_planned",
            "expectedVersion": _hidden(page.text, "expectedVersion"),
            "formToken": _hidden(page.text, "formToken"),
            "formExpiry": _hidden(page.text, "formExpiry"),
        },
    )
    assert closed.status_code == 303
    detail = client.get(closed.headers["location"])
    assert "principal sintético de desarrollo lab-reviewer" in detail.text
    assert "Registrado " in detail.text
    assert "no una identidad clínica verificada" in detail.text
    assert session.session_id not in detail.text
    assert DEV_SECRET not in detail.text
    assert SIGNING_SECRET not in detail.text
    assert "anonymous" not in detail.text.lower()
    issued = issue_form_token(
        secret=SIGNING_SECRET,
        review_case_id=case.id,
        expected_version=2,
        session_id=session.session_id,
    )
    assert issued is not None
    token, expiry = issued
    repeated = _post_form(
        client,
        f"/review-cases/{case.id}/close",
        {
            "outcome": "follow_up_coordination_planned",
            "expectedVersion": "2",
            "formToken": token,
            "formExpiry": str(expiry),
        },
    )
    assert repeated.status_code == 303
    assert _attributions(repository.database_path) == [
        ("review_case_closed", "lab-reviewer", "DEVELOPMENT_AUTHENTICATOR_V1", session.session_id)
    ]


def test_forged_principal_is_rejected_and_a_later_valid_close_uses_the_session(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    client = _bind(repository)
    _login(client)
    page = client.get(f"/review-cases/{case.id}")
    payload = {
        "outcome": "follow_up_coordination_planned",
        "expectedVersion": _hidden(page.text, "expectedVersion"),
        "formToken": _hidden(page.text, "formToken"),
        "formExpiry": _hidden(page.text, "formExpiry"),
        "principal_id": "other-reviewer",
        "authenticator_id": "OIDC_AUTHENTICATOR_V1",
        "session_id": "00000000-0000-4000-8000-000000000099",
    }
    forged = _post_form(client, f"/review-cases/{case.id}/close", payload)
    assert forged.status_code == 400
    assert MSG_CLOSE_INVALID in forged.text
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN
    assert _attributions(repository.database_path) == []
    accepted = _post_form(client, f"/review-cases/{case.id}/close", {key: payload[key] for key in payload if key in {"outcome", "expectedVersion", "formToken", "formExpiry"}})
    assert accepted.status_code == 303
    assert _attributions(repository.database_path)[0][1] == "lab-reviewer"


def test_invalid_hmac_and_absent_session_do_not_write(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    client = _bind(repository)
    _login(client)
    page = client.get(f"/review-cases/{case.id}")
    bad = _post_form(
        client,
        f"/review-cases/{case.id}/close",
        {
            "outcome": "follow_up_coordination_planned",
            "expectedVersion": _hidden(page.text, "expectedVersion"),
            "formToken": "ab" * 32,
            "formExpiry": _hidden(page.text, "formExpiry"),
        },
    )
    assert bad.status_code == 400
    assert MSG_FORM_INVALID in bad.text
    client.cookies.clear()
    missing = _post_form(
        client,
        f"/review-cases/{case.id}/close",
        {
            "outcome": "follow_up_coordination_planned",
            "expectedVersion": _hidden(page.text, "expectedVersion"),
            "formToken": _hidden(page.text, "formToken"),
            "formExpiry": _hidden(page.text, "formExpiry"),
        },
    )
    assert missing.status_code == 303
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN
    assert _attributions(repository.database_path) == []


def test_revoked_and_expired_sessions_do_not_write(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    clock = Clock()
    client = _bind(repository, clock=clock)
    _login(client)
    page = client.get(f"/review-cases/{case.id}")
    payload = {
        "outcome": "follow_up_coordination_planned",
        "expectedVersion": _hidden(page.text, "expectedVersion"),
        "formToken": _hidden(page.text, "formToken"),
        "formExpiry": _hidden(page.text, "formExpiry"),
    }
    token = client.cookies.get(SESSION_COOKIE)
    logged_out = client.post("/review-logout", headers=ORIGIN, follow_redirects=False)
    assert logged_out.status_code == 303
    client.cookies.set(SESSION_COOKIE, token)
    revoked = _post_form(client, f"/review-cases/{case.id}/close", payload)
    assert revoked.status_code == 303
    assert revoked.headers["location"] == "/review-login"
    client.cookies.clear()
    _login(client)
    page = client.get(f"/review-cases/{case.id}", follow_redirects=False)
    assert page.status_code == 200
    payload["formToken"] = _hidden(page.text, "formToken")
    payload["formExpiry"] = _hidden(page.text, "formExpiry")
    clock.moment = NOW + timedelta(seconds=SESSION_TTL_SECONDS + 1)
    expired = _post_form(client, f"/review-cases/{case.id}/close", payload)
    assert expired.status_code == 303
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN
    assert _attributions(repository.database_path) == []


def test_http_coordination_records_one_attribution_and_repeat_does_not_duplicate(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    client = _bind(repository)
    _login(client)
    session = _session(client)
    page = client.get(f"/review-cases/{case.id}")
    closed = _post_form(
        client,
        f"/review-cases/{case.id}/close",
        {
            "outcome": "follow_up_coordination_planned",
            "expectedVersion": _hidden(page.text, "expectedVersion"),
            "formToken": _hidden(page.text, "formToken"),
            "formExpiry": _hidden(page.text, "formExpiry"),
        },
    )
    detail = client.get(closed.headers["location"])
    created = _post_form(
        client,
        f"/review-cases/{case.id}/controlled-action",
        {
            "actionExpiry": _hidden(detail.text, "actionExpiry"),
            "actionToken": _hidden(detail.text, "actionToken"),
        },
    )
    assert created.status_code == 303
    shown = client.get(created.headers["location"])
    assert shown.text.count(repository.get_follow_up_coordination_request(case.id).id) == 1
    assert "No se registró atribución de desarrollo para esta operación." not in shown.text
    assert "principal sintético de desarrollo lab-reviewer" in shown.text
    assert session.session_id not in shown.text
    issued = issue_controlled_action_token(
        secret=SIGNING_SECRET,
        review_case_id=case.id,
        session_id=session.session_id,
    )
    assert issued is not None
    token, expiry = issued
    repeated = _post_form(
        client,
        f"/review-cases/{case.id}/controlled-action",
        {"actionExpiry": str(expiry), "actionToken": token},
    )
    assert repeated.status_code == 303
    rows = _attributions(repository.database_path)
    assert [row[0] for row in rows] == ["coordination_request_created", "review_case_closed"]
    assert {row[3] for row in rows} == {session.session_id}


def test_internal_close_and_historical_rows_have_no_human_attribution(tmp_path):
    repository = _repository(tmp_path)
    internal_case = _create(repository)
    client = _bind(repository, enabled=False)
    response = client.post(
        f"/internal/follow-up-review-cases/{internal_case.id}/close",
        json={"expectedVersion": 1, "outcome": "review_completed_no_operational_action"},
        headers={"X-Service-Token": SERVICE_TOKEN},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "closed"
    assert _attributions(repository.database_path) == []

    historical = FollowUpReviewCaseService(repository).ensure_for_protocol(
        "SYN-FOLLOWUP-002",
        ProtocolReviewResult(
            id=POST_CONSULTATION_RESULT_REVIEW_V1,
            evaluation_status=ProtocolEvaluationStatus.MATCHED,
            reason_codes=("post_consultation_result_requires_review",),
            matched_resources=("Encounter/encounter-002", "Observation/observation-002"),
            human_review_status="required",
            human_review_reason="deterministic_post_consultation_protocol_match",
            action_status="proposed",
            action_type="review_follow_up_case",
        ),
    )
    assert historical is not None
    repository.close(
        historical.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    FollowUpCoordinationActionService(repository).ensure_follow_up_coordination_request(historical.id)
    app.dependency_overrides[get_settings] = lambda: _settings(enabled=True)
    browser = TestClient(app, base_url="http://127.0.0.1")
    _login(browser)
    page = browser.get(f"/review-cases/{historical.id}")
    assert "Cierre del caso: no se registró atribución de desarrollo." in page.text
    assert "No se registró atribución de desarrollo para esta operación." in page.text
    assert page.text.count("Solicitud interna de coordinación registrada.") == 1
    assert "Solicitud pendiente de registro." not in page.text
    assert "anonymous" not in page.text.lower()
    assert "lab-reviewer" not in page.text
    assert _attributions(repository.database_path) == []
