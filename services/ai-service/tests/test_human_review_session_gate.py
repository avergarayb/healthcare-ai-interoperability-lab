"""Review routes require a live development session. Tests log in through HTTP."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.followup_review import FollowUpReviewCaseService, ReviewCaseStatus, ReviewOutcome
from app.human_development_auth import SESSION_COOKIE
from app.human_review_client import (
    MSG_ACTION_TOKEN_INVALID,
    MSG_ASSISTANCE_TOKEN_INVALID,
    MSG_FORM_INVALID,
    MSG_ORIGIN_INVALID,
    issue_assistance_token,
    issue_controlled_action_token,
    issue_form_token,
)
from app.main import app, get_settings
from tests import test_ai_assisted_review as assisted

ORIGIN = {"origin": "http://127.0.0.1"}
UNKNOWN = "10000000-0000-4000-8000-000000000077"


class MutableClock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment


class SpyRepository:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.calls: list[str] = []

    def __getattr__(self, name: str):
        self.calls.append(name)
        return getattr(self.inner, name)


class SpyFhir:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def search(self, *args, **kwargs):
        self.calls.append("search")
        raise AssertionError("fhir")

    def read_exact(self, *args, **kwargs):
        self.calls.append("read")
        raise AssertionError("fhir")


@pytest.fixture(autouse=True)
def _clean_state():
    app.dependency_overrides.clear()
    for name in (
        "followup_review_repository",
        "clinical_context_fhir_client",
        "institutional_knowledge",
        "ai_assistance_provider",
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
        "institutional_knowledge",
        "ai_assistance_provider",
        "human_session_repository",
        "human_session_clock",
    ):
        if hasattr(app.state, name):
            delattr(app.state, name)


def _bind(tmp_path, **overrides):
    repository = assisted._repository(tmp_path)
    case = assisted._create(repository)
    assisted._prepare_session(repository)
    app.state.followup_review_repository = repository
    app.dependency_overrides[get_settings] = lambda: assisted._settings(**overrides)
    return repository, case


def _anonymous() -> TestClient:
    return TestClient(app, base_url="http://127.0.0.1")


def _get(client: TestClient, path: str):
    return client.get(path, follow_redirects=False)


def _authenticated() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    assisted._login(client)
    return client


def _fields(html: str, names: tuple[str, ...]) -> dict[str, str]:
    fields = {}
    for name in names:
        marker = f'name="{name}" value="'
        start = html.index(marker) + len(marker)
        fields[name] = html[start:html.index('"', start)]
    return fields


def _post(client: TestClient, path: str, fields: dict[str, str], *, origin: str = "http://127.0.0.1"):
    return client.post(
        path,
        content=urlencode(fields),
        headers={"origin": origin, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


def _coordination_count(path) -> int:
    connection = sqlite3.connect(path)
    try:
        return int(connection.execute("SELECT COUNT(*) FROM follow_up_coordination_requests").fetchone()[0])
    finally:
        connection.close()


def test_anonymous_queue_redirects_to_login(tmp_path):
    repository, case = _bind(tmp_path)
    spy = SpyRepository(repository)
    app.state.followup_review_repository = spy
    response = _get(_anonymous(), "/review-cases")
    assert response.status_code == 303
    assert response.headers["location"] == "/review-login"
    assert response.headers["cache-control"] == "no-store"
    assert case.id not in response.text
    assert case.case_id not in response.text
    assert spy.calls == []


def test_anonymous_detail_for_existing_case_does_not_reveal_it(tmp_path):
    repository, case = _bind(tmp_path)
    spy = SpyRepository(repository)
    app.state.followup_review_repository = spy
    response = _get(_anonymous(), f"/review-cases/{case.id}")
    assert response.status_code == 303
    assert response.headers["location"] == "/review-login"
    assert case.id not in response.headers["location"]
    assert case.id not in response.text
    assert spy.calls == []


def test_anonymous_detail_for_unknown_case_matches_existing_case(tmp_path):
    repository, case = _bind(tmp_path)
    client = _anonymous()
    existing = _get(client, f"/review-cases/{case.id}")
    unknown = _get(client, f"/review-cases/{UNKNOWN}")
    assert existing.status_code == unknown.status_code == 303
    assert existing.headers["location"] == unknown.headers["location"] == "/review-login"
    assert existing.text == unknown.text
    assert case.id not in existing.text
    assert UNKNOWN not in unknown.text


def test_anonymous_close_does_not_mutate(tmp_path):
    repository, case = _bind(tmp_path)
    spy = SpyRepository(repository)
    app.state.followup_review_repository = spy
    response = _post(
        _anonymous(),
        f"/review-cases/{case.id}/close",
        {
            "outcome": "follow_up_coordination_planned",
            "expectedVersion": "1",
            "formToken": "ab" * 32,
            "formExpiry": "9999999999",
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/review-login"
    assert spy.calls == []
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN


def test_anonymous_assistance_does_not_call_the_provider(tmp_path):
    repository, case = _bind(tmp_path)
    provider = assisted.FakeProvider(text=assisted._valid_output())
    fhir = SpyFhir()
    app.state.clinical_context_fhir_client = lambda: fhir
    app.state.ai_assistance_provider = provider
    app.state.institutional_knowledge = assisted.FakeKnowledge(chunks=(assisted._chunk(),))
    response = _post(
        _anonymous(),
        f"/review-cases/{case.id}/ai-assistance",
        {"assistanceExpiry": "9999999999", "assistanceToken": "ab" * 32},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/review-login"
    assert provider.calls == []
    assert fhir.calls == []
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN


def test_anonymous_controlled_action_does_not_insert(tmp_path):
    repository, case = _bind(tmp_path)
    repository.close(case.id, expected_version=1, outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED)
    spy = SpyRepository(repository)
    app.state.followup_review_repository = spy
    response = _post(
        _anonymous(),
        f"/review-cases/{case.id}/controlled-action",
        {"actionExpiry": "9999999999", "actionToken": "ab" * 32},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/review-login"
    assert spy.calls == []
    assert _coordination_count(repository.database_path) == 0


def test_expired_session_is_rejected(tmp_path):
    _bind(tmp_path)
    clock = MutableClock(datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc))
    app.state.human_session_clock = clock
    client = _authenticated()
    clock.moment = clock.moment + timedelta(hours=9)
    response = _get(client, "/review-cases")
    assert response.status_code == 303
    assert response.headers["location"] == "/review-login"
    assert response.headers["cache-control"] == "no-store"


def test_revoked_session_is_rejected(tmp_path):
    _bind(tmp_path)
    client = _authenticated()
    token = client.cookies.get(SESSION_COOKIE)
    logged_out = client.post("/review-logout", headers=ORIGIN, follow_redirects=False)
    assert logged_out.status_code == 303
    client.cookies.set(SESSION_COOKIE, token)
    response = _get(client, "/review-cases")
    assert response.status_code == 303
    assert response.headers["location"] == "/review-login"
    assert token not in response.text


def test_invalid_cookie_is_rejected(tmp_path):
    _bind(tmp_path)
    client = _anonymous()
    client.cookies.set(SESSION_COOKIE, "not-a-session-token")
    response = _get(client, "/review-cases")
    assert response.status_code == 303
    assert response.headers["location"] == "/review-login"
    assert "not-a-session-token" not in response.text


def test_disabled_development_authenticator_fails_closed(tmp_path):
    repository, case = _bind(tmp_path, human_review_development_auth_enabled=False)
    client = _anonymous()
    queue = _get(client, "/review-cases")
    existing = _get(client, f"/review-cases/{case.id}")
    unknown = _get(client, f"/review-cases/{UNKNOWN}")
    assert queue.status_code == existing.status_code == unknown.status_code == 503
    assert existing.text == unknown.text
    assert "This demo is not available." in queue.text
    assert case.id not in existing.text
    assert "not found" not in existing.text.lower()
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN


def test_invalid_development_configuration_fails_closed(tmp_path):
    repository, case = _bind(tmp_path, host="0.0.0.0")
    response = _get(_anonymous(), f"/review-cases/{case.id}")
    assert response.status_code == 503
    assert "This demo is not available." in response.text
    assert case.id not in response.text
    assert "0.0.0.0" not in response.text
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN


def test_unavailable_session_store_fails_closed(tmp_path):
    repository, case = _bind(tmp_path)
    client = _authenticated()
    path = app.state.human_session_repository.database_path
    path.write_bytes(b"not a database")
    response = client.get(f"/review-cases/{case.id}")
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert "This demo is not available." in response.text
    assert case.id not in response.text
    assert "Traceback" not in response.text
    assert str(path) not in response.text
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN


def test_authenticated_queue_and_detail_render(tmp_path):
    _repository, case = _bind(tmp_path)
    fhir = assisted.ScriptedFhir()
    app.state.clinical_context_fhir_client = lambda: fhir
    client = _authenticated()
    queue = client.get("/review-cases")
    detail = client.get(f"/review-cases/{case.id}")
    assert queue.status_code == detail.status_code == 200
    assert queue.headers["cache-control"] == detail.headers["cache-control"] == "no-store"
    assert case.case_id in queue.text
    assert "Close review" in detail.text
    assert "These pages require a development session." in queue.text
    assert "not production identity" in detail.text
    assert "Anyone who can reach this demo" not in queue.text
    assert "This page is not a user login." not in detail.text
    assert assisted.DEV_SECRET not in detail.text
    assert client.cookies.get(SESSION_COOKIE) not in detail.text


def test_authenticated_close_succeeds(tmp_path):
    repository, case = _bind(tmp_path)
    client = _authenticated()
    page = client.get(f"/review-cases/{case.id}")
    fields = _fields(page.text, ("expectedVersion", "formToken", "formExpiry"))
    closed = _post(
        client,
        f"/review-cases/{case.id}/close",
        {**fields, "outcome": "follow_up_coordination_planned"},
    )
    assert closed.status_code == 303
    assert closed.headers["cache-control"] == "no-store"
    stored = repository.get(case.id)
    assert stored.status is ReviewCaseStatus.CLOSED
    assert stored.outcome is ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED


def test_authenticated_assistance_uses_the_test_double(tmp_path):
    repository, case = _bind(tmp_path)
    fhir = assisted.ScriptedFhir()
    provider = assisted.FakeProvider(text=assisted._valid_output())
    app.state.clinical_context_fhir_client = lambda: fhir
    app.state.institutional_knowledge = assisted.FakeKnowledge(chunks=(assisted._chunk(),))
    app.state.ai_assistance_provider = provider
    client = _authenticated()
    page = client.get(f"/review-cases/{case.id}")
    fields = _fields(page.text, ("assistanceExpiry", "assistanceToken"))
    posted = _post(client, f"/review-cases/{case.id}/ai-assistance", fields)
    assert posted.status_code == 303
    assert len(provider.calls) == 1
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN
    assert _coordination_count(repository.database_path) == 0


def test_authenticated_controlled_action_succeeds(tmp_path):
    repository, case = _bind(tmp_path)
    repository.close(case.id, expected_version=1, outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED)
    client = _authenticated()
    page = client.get(f"/review-cases/{case.id}")
    posted = _post(
        client,
        f"/review-cases/{case.id}/controlled-action",
        _fields(page.text, ("actionExpiry", "actionToken")),
    )
    assert posted.status_code == 303
    assert _coordination_count(repository.database_path) == 1


def test_hmac_from_another_session_is_rejected(tmp_path):
    repository, case = _bind(tmp_path)
    fhir = SpyFhir()
    provider = assisted.FakeProvider(text=assisted._valid_output())
    app.state.clinical_context_fhir_client = lambda: fhir
    app.state.ai_assistance_provider = provider
    first = _authenticated()
    second = _authenticated()
    page = first.get(f"/review-cases/{case.id}")
    fhir.calls.clear()
    fields = _fields(page.text, ("expectedVersion", "formToken", "formExpiry"))
    rejected = _post(
        second,
        f"/review-cases/{case.id}/close",
        {**fields, "outcome": "follow_up_coordination_planned"},
    )
    assert rejected.status_code == 400
    assert MSG_FORM_INVALID in rejected.text
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN
    assert provider.calls == []
    assert fhir.calls == []
    assert _coordination_count(repository.database_path) == 0


def test_hmac_from_previous_login_is_rejected_after_relogin(tmp_path):
    repository, case = _bind(tmp_path)
    client = _authenticated()
    page = client.get(f"/review-cases/{case.id}")
    fields = _fields(page.text, ("assistanceExpiry", "assistanceToken"))
    logged_out = client.post("/review-logout", headers=ORIGIN, follow_redirects=False)
    assert logged_out.status_code == 303
    assisted._login(client)
    rejected = _post(client, f"/review-cases/{case.id}/ai-assistance", fields)
    assert rejected.status_code == 400
    assert MSG_ASSISTANCE_TOKEN_INVALID in rejected.text
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN


def test_hmac_wrong_purpose_is_rejected(tmp_path):
    repository, case = _bind(tmp_path)
    provider = assisted.FakeProvider(text=assisted._valid_output())
    app.state.ai_assistance_provider = provider
    client = _authenticated()
    page = client.get(f"/review-cases/{case.id}")
    close_fields = _fields(page.text, ("formToken", "formExpiry"))
    rejected = _post(
        client,
        f"/review-cases/{case.id}/ai-assistance",
        {"assistanceExpiry": close_fields["formExpiry"], "assistanceToken": close_fields["formToken"]},
    )
    assert rejected.status_code == 400
    assert MSG_ASSISTANCE_TOKEN_INVALID in rejected.text
    assert provider.calls == []
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN


def test_hmac_expired_or_tampered_is_rejected(tmp_path):
    repository, case = _bind(tmp_path)
    client = _authenticated()
    session_id = assisted._session_id(client)
    expired = issue_form_token(
        secret=assisted.SIGNING_SECRET,
        review_case_id=case.id,
        expected_version=1,
        session_id=session_id,
        now=1,
    )
    assert expired is not None
    expired_response = _post(
        client,
        f"/review-cases/{case.id}/close",
        {
            "outcome": "follow_up_coordination_planned",
            "expectedVersion": "1",
            "formToken": expired[0],
            "formExpiry": str(expired[1]),
        },
    )
    page = client.get(f"/review-cases/{case.id}")
    fields = _fields(page.text, ("expectedVersion", "formToken", "formExpiry"))
    tampered = fields["formToken"][:-1] + ("0" if fields["formToken"][-1] != "0" else "1")
    tampered_response = _post(
        client,
        f"/review-cases/{case.id}/close",
        {**fields, "formToken": tampered, "outcome": "follow_up_coordination_planned"},
    )
    assert expired_response.status_code == tampered_response.status_code == 400
    assert MSG_FORM_INVALID in expired_response.text
    assert MSG_FORM_INVALID in tampered_response.text
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN


def test_invalid_origin_is_rejected(tmp_path):
    repository, case = _bind(tmp_path)
    client = _authenticated()
    page = client.get(f"/review-cases/{case.id}")
    fields = _fields(page.text, ("expectedVersion", "formToken", "formExpiry"))
    rejected = _post(
        client,
        f"/review-cases/{case.id}/close",
        {**fields, "outcome": "follow_up_coordination_planned"},
        origin="http://evil.example",
    )
    assert rejected.status_code == 400
    assert MSG_ORIGIN_INVALID in rejected.text
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN


def test_rejected_requests_have_no_external_side_effects(tmp_path):
    repository, case = _bind(tmp_path)
    fhir = SpyFhir()
    provider = assisted.FakeProvider(text=assisted._valid_output())
    app.state.clinical_context_fhir_client = lambda: fhir
    app.state.ai_assistance_provider = provider
    app.state.institutional_knowledge = assisted.FakeKnowledge(chunks=(assisted._chunk(),))
    anonymous = _anonymous()
    _post(
        anonymous,
        f"/review-cases/{case.id}/close",
        {
            "outcome": "follow_up_coordination_planned",
            "expectedVersion": "1",
            "formToken": "cd" * 32,
            "formExpiry": "9999999999",
        },
    )
    _post(
        anonymous,
        f"/review-cases/{case.id}/ai-assistance",
        {"assistanceExpiry": "9999999999", "assistanceToken": "cd" * 32},
    )
    _post(
        anonymous,
        f"/review-cases/{case.id}/controlled-action",
        {"actionExpiry": "9999999999", "actionToken": "cd" * 32},
    )
    client = _authenticated()
    session_id = assisted._session_id(client)
    foreign = issue_assistance_token(
        secret=assisted.SIGNING_SECRET,
        review_case_id=case.id,
        session_id="22222222-2222-4222-8222-222222222222",
        now=1_000_000_000,
    )
    action = issue_controlled_action_token(
        secret=assisted.SIGNING_SECRET,
        review_case_id=case.id,
        session_id="22222222-2222-4222-8222-222222222222",
        now=1_000_000_000,
    )
    assert foreign is not None and action is not None
    assistance = _post(
        client,
        f"/review-cases/{case.id}/ai-assistance",
        {"assistanceExpiry": str(foreign[1]), "assistanceToken": foreign[0]},
    )
    controlled = _post(
        client,
        f"/review-cases/{case.id}/controlled-action",
        {"actionExpiry": str(action[1]), "actionToken": action[0]},
    )
    assert assistance.status_code == 400
    assert MSG_ASSISTANCE_TOKEN_INVALID in assistance.text
    assert controlled.status_code == 400
    assert MSG_ACTION_TOKEN_INVALID in controlled.text
    assert provider.calls == []
    assert fhir.calls == []
    assert repository.get(case.id).status is ReviewCaseStatus.OPEN
    assert _coordination_count(repository.database_path) == 0
    assert FollowUpReviewCaseService(repository).events(case.id)[-1].event_type.value == "created"


def test_internal_service_token_boundary_is_unchanged(tmp_path):
    repository, _case = _bind(tmp_path)
    client = _authenticated()
    health = client.get("/health")
    denied = client.get("/internal/follow-up-review-cases")
    allowed = client.get(
        "/internal/follow-up-review-cases",
        headers={"X-Service-Token": "synthetic-service-token-a"},
    )
    anonymous = _anonymous().get(
        "/internal/follow-up-review-cases",
        headers={"X-Service-Token": "synthetic-service-token-a"},
    )
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert denied.status_code == 401
    assert denied.headers.get("location") != "/review-login"
    assert allowed.status_code == 200
    assert anonymous.status_code == 200
    assert allowed.json()["items"][0]["caseId"] == repository.get(allowed.json()["items"][0]["reviewCaseId"]).case_id


def test_no_route_keeps_an_anonymous_fallback(tmp_path):
    repository, case = _bind(tmp_path)
    repository.close(case.id, expected_version=1, outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED)
    routes = (
        ("get", "/review-cases", None),
        ("get", f"/review-cases/{case.id}", None),
        ("get", f"/review-cases/{UNKNOWN}", None),
        (
            "post",
            f"/review-cases/{case.id}/close",
            {
                "outcome": "review_completed_no_operational_action",
                "expectedVersion": "2",
                "formToken": "ab" * 32,
                "formExpiry": "9999999999",
            },
        ),
        (
            "post",
            f"/review-cases/{case.id}/ai-assistance",
            {"assistanceExpiry": "9999999999", "assistanceToken": "ab" * 32},
        ),
        (
            "post",
            f"/review-cases/{case.id}/controlled-action",
            {"actionExpiry": "9999999999", "actionToken": "ab" * 32},
        ),
    )
    enabled = _anonymous()
    for method, path, fields in routes:
        response = _get(enabled, path) if fields is None else _post(enabled, path, fields)
        assert response.status_code == 303
        assert response.headers["location"] == "/review-login"
        assert response.status_code != 200
    app.dependency_overrides[get_settings] = lambda: assisted._settings(
        human_review_development_auth_enabled=False
    )
    disabled = _anonymous()
    for method, path, fields in routes:
        response = _get(disabled, path) if fields is None else _post(disabled, path, fields)
        assert response.status_code == 503
        assert "This demo is not available." in response.text
        assert case.id not in response.text
    assert _coordination_count(repository.database_path) == 0
