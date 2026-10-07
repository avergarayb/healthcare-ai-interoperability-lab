from __future__ import annotations

import inspect
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.followup_coordination_action import FollowUpCoordinationRequest
from app.followup_review import FollowUpReviewCaseService, ReviewCaseStatus, ReviewOutcome
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.human_review_client import (
    MSG_ACTION_DENIED,
    MSG_ACTION_INVALID,
    MSG_ACTION_ORIGIN_INVALID,
    MSG_ACTION_TOKEN_INVALID,
    MSG_NOT_CONFIGURED,
    MSG_NOT_FOUND,
    assistance_token_is_valid,
    controlled_action_token_is_valid,
    issue_assistance_token,
    issue_controlled_action_token,
    issue_form_token,
    submit_controlled_action,
)
from app.main import app, get_settings
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)


SIGNING_SECRET = "synthetic-form-signing-secret-b"
ORIGIN = {"origin": "http://testserver"}
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
APP = Path(__file__).resolve().parents[1] / "app"


class Clock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self):
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def _settings(*, secret: str = SIGNING_SECRET) -> Settings:
    return Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token="synthetic-service-token-a",
        human_review_form_signing_secret=secret,
        host="127.0.0.1",
        port=8090,
        followup_agent_enabled=True,
        ai_review_db_path="unused-by-explicit-test-repository.sqlite3",
    )


def _protocol(
    *,
    protocol_id: str = POST_CONSULTATION_RESULT_REVIEW_V1,
    resources: tuple[str, ...] = ("Encounter/encounter-011", "Observation/observation-011"),
    reasons: tuple[str, ...] = ("post_consultation_result_requires_review",),
) -> ProtocolReviewResult:
    return ProtocolReviewResult(
        id=protocol_id,
        evaluation_status=ProtocolEvaluationStatus.MATCHED,
        reason_codes=reasons,
        matched_resources=resources,
        human_review_status="required",
        human_review_reason="deterministic_post_consultation_protocol_match",
        action_status="proposed",
        action_type="review_follow_up_case",
    )


def _repository(tmp_path, name="review.sqlite3"):
    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / name, clock=Clock())
    repository.initialize()
    return repository


def _create(repository, *, case_id: str, protocol=None):
    created = FollowUpReviewCaseService(repository).ensure_for_protocol(
        case_id,
        protocol or _protocol(),
    )
    assert created is not None
    return created


def _close(repository, case, outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED):
    return repository.close(case.id, expected_version=1, outcome=outcome)


def _client(repository, *, secret: str = SIGNING_SECRET) -> TestClient:
    app.state.followup_review_repository = repository
    app.dependency_overrides[get_settings] = lambda: _settings(secret=secret)
    return TestClient(app)


def _action_fields(html: str) -> dict[str, str]:
    fields = {}
    for name in ("actionExpiry", "actionToken"):
        marker = f'name="{name}" value="'
        start = html.index(marker) + len(marker)
        fields[name] = html[start:html.index('"', start)]
    return fields


def _post_action(client: TestClient, case_id: str, fields: dict[str, str], **overrides):
    payload = dict(fields)
    payload.update(overrides)
    return client.post(
        f"/review-cases/{case_id}/controlled-action",
        content=urlencode(payload),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


def _count_requests(path) -> int:
    connection = sqlite3.connect(path)
    try:
        return int(
            connection.execute("SELECT COUNT(*) FROM follow_up_coordination_requests").fetchone()[0]
        )
    finally:
        connection.close()


def _snapshot(path, review_case_id: str):
    connection = sqlite3.connect(path)
    try:
        case = connection.execute(
            "SELECT * FROM follow_up_review_cases WHERE id = ?",
            (review_case_id,),
        ).fetchone()
        events = connection.execute(
            """
            SELECT * FROM follow_up_review_case_events
            WHERE review_case_id = ?
            ORDER BY case_version ASC
            """,
            (review_case_id,),
        ).fetchall()
        return case, events
    finally:
        connection.close()


def _section(html: str) -> str:
    start = html.index("<h2>Controlled action</h2>")
    return html[start:]


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


@pytest.mark.parametrize(
    ("case_id", "protocol"),
    [
        ("SYN-FOLLOWUP-011", None),
        (
            "SYN-FOLLOWUP-012",
            _protocol(
                protocol_id=MISSED_FOLLOW_UP_REVIEW_V1,
                resources=("Appointment/noshow-012",),
                reasons=("missed_follow_up_without_confirmed_replacement",),
            ),
        ),
    ],
)
def test_eligible_closed_case_shows_the_action_button(tmp_path, case_id, protocol):
    repository = _repository(tmp_path)
    closed = _close(repository, _create(repository, case_id=case_id, protocol=protocol))
    page = _client(repository).get(f"/review-cases/{closed.id}")
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    form = _section(page.text)
    assert "Create an internal follow-up coordination request." in form
    assert "Create coordination request" in form
    assert f'action="/review-cases/{closed.id}/controlled-action"' in form
    assert 'name="actionExpiry"' in form
    assert 'name="actionToken"' in form
    assert "Patient" not in form
    assert "outcome" not in form
    assert "protocol" not in form
    assert SIGNING_SECRET not in page.text


def test_open_case_has_no_action_button(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository, case_id="SYN-FOLLOWUP-013")
    page = _client(repository).get(f"/review-cases/{created.id}")
    assert "Controlled action" not in page.text
    assert "Create coordination request" not in page.text


def test_no_action_closed_case_has_no_action_button(tmp_path):
    repository = _repository(tmp_path)
    closed = _close(
        repository,
        _create(repository, case_id="SYN-FOLLOWUP-014"),
        ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION,
    )
    page = _client(repository).get(f"/review-cases/{closed.id}")
    assert "Controlled action" not in page.text
    assert "Create coordination request" not in page.text


def test_unsupported_protocol_has_no_action_button(tmp_path):
    repository = _repository(tmp_path)
    closed = _close(
        repository,
        _create(
            repository,
            case_id="SYN-FOLLOWUP-003",
            protocol=_protocol(protocol_id="OTHER_PROTOCOL"),
        ),
    )
    page = _client(repository).get(f"/review-cases/{closed.id}")
    assert "Controlled action" not in page.text
    assert "Create coordination request" not in page.text


def test_missing_signing_secret_has_no_action_button(tmp_path):
    repository = _repository(tmp_path)
    closed = _close(repository, _create(repository, case_id="SYN-FOLLOWUP-015"))
    page = _client(repository, secret="").get(f"/review-cases/{closed.id}")
    assert "Create coordination request" not in page.text
    assert MSG_NOT_CONFIGURED in _section(page.text)


def test_valid_post_creates_request_and_get_reconstructs_it(tmp_path):
    repository = _repository(tmp_path)
    closed = _close(repository, _create(repository, case_id="SYN-FOLLOWUP-011"))
    client = _client(repository)
    page = client.get(f"/review-cases/{closed.id}")
    before = _snapshot(repository.database_path, closed.id)
    posted = _post_action(client, closed.id, _action_fields(page.text))
    assert posted.status_code == 303
    assert posted.headers["cache-control"] == "no-store"
    assert posted.headers["location"] == f"/review-cases/{closed.id}"
    shown = client.get(posted.headers["location"])
    assert shown.status_code == 200
    assert shown.headers["cache-control"] == "no-store"
    section = _section(shown.text)
    assert "Coordination request created." in section
    assert "Create coordination request" not in shown.text
    stored = repository.get_follow_up_coordination_request(closed.id)
    assert stored is not None
    assert stored.id in section
    assert ">requested<" in section
    assert stored.created_at in section
    assert _snapshot(repository.database_path, closed.id) == before
    assert repository.get(closed.id) == closed
    assert len(repository.events(closed.id)) == 2
    refreshed = client.get(f"/review-cases/{closed.id}")
    assert "Coordination request created." in refreshed.text
    assert _count_requests(repository.database_path) == 1


def test_repeated_post_reuses_the_request(tmp_path):
    repository = _repository(tmp_path)
    closed = _close(repository, _create(repository, case_id="SYN-FOLLOWUP-012"))
    client = _client(repository)
    fields = _action_fields(client.get(f"/review-cases/{closed.id}").text)
    first = _post_action(client, closed.id, fields)
    second = _post_action(client, closed.id, fields)
    assert first.status_code == second.status_code == 303
    stored = repository.get_follow_up_coordination_request(closed.id)
    assert stored is not None
    assert _count_requests(repository.database_path) == 1
    replay = client.get(second.headers["location"])
    assert stored.id in replay.text
    assert replay.text.count(stored.id) == 1


def test_concurrent_posts_create_one_request(tmp_path):
    repository = _repository(tmp_path)
    closed = _close(repository, _create(repository, case_id="SYN-FOLLOWUP-005"))
    client = _client(repository)
    fields = _action_fields(client.get(f"/review-cases/{closed.id}").text)
    workers = 8
    barrier = threading.Barrier(workers)

    def post(_index):
        barrier.wait(timeout=10)
        local = _client(repository)
        return _post_action(local, closed.id, fields)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(post, range(workers)))
    assert {result.status_code for result in results} == {303}
    assert _count_requests(repository.database_path) == 1
    assert len(repository.events(closed.id)) == 2


def test_cross_case_expired_close_and_assistance_tokens_are_rejected(tmp_path):
    repository = _repository(tmp_path)
    closed = _close(repository, _create(repository, case_id="SYN-FOLLOWUP-011"))
    other = "10000000-0000-4000-8000-000000000044"
    client = _client(repository)
    page_fields = _action_fields(client.get(f"/review-cases/{closed.id}").text)
    foreign = issue_controlled_action_token(secret=SIGNING_SECRET, review_case_id=other)
    expired = issue_controlled_action_token(secret=SIGNING_SECRET, review_case_id=closed.id, now=1)
    close = issue_form_token(
        secret=SIGNING_SECRET,
        review_case_id=closed.id,
        expected_version=2,
    )
    assistance = issue_assistance_token(secret=SIGNING_SECRET, review_case_id=closed.id)
    assert foreign is not None and expired is not None and close is not None and assistance is not None
    assert not controlled_action_token_is_valid(
        secret=SIGNING_SECRET,
        review_case_id=closed.id,
        expiry=close[1],
        token=close[0],
    )
    assert assistance_token_is_valid(
        secret=SIGNING_SECRET,
        review_case_id=closed.id,
        expiry=assistance[1],
        token=assistance[0],
    )
    rejected = [
        {"actionExpiry": str(foreign[1]), "actionToken": foreign[0]},
        {"actionExpiry": str(expired[1]), "actionToken": expired[0]},
        {"actionExpiry": str(close[1]), "actionToken": close[0]},
        {"actionExpiry": str(assistance[1]), "actionToken": assistance[0]},
        page_fields | {"actionToken": "0" * 64},
    ]
    for fields in rejected:
        response = _post_action(client, closed.id, fields)
        assert response.status_code == 400
        assert MSG_ACTION_TOKEN_INVALID in response.text
        assert response.headers["cache-control"] == "no-store"
        assert SIGNING_SECRET not in response.text
    assert _count_requests(repository.database_path) == 0


def test_invalid_origin_and_malformed_form_are_rejected(tmp_path):
    repository = _repository(tmp_path)
    closed = _close(repository, _create(repository, case_id="SYN-FOLLOWUP-013"))
    client = _client(repository)
    fields = _action_fields(client.get(f"/review-cases/{closed.id}").text)
    origin = client.post(
        f"/review-cases/{closed.id}/controlled-action",
        content=urlencode(fields),
        headers={"origin": "http://evil.test", "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    missing_origin = client.post(
        f"/review-cases/{closed.id}/controlled-action",
        content=urlencode(fields),
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    extra = _post_action(client, closed.id, fields, outcome="follow_up_coordination_planned")
    incomplete = client.post(
        f"/review-cases/{closed.id}/controlled-action",
        content=urlencode({"actionToken": fields["actionToken"]}),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert origin.status_code == missing_origin.status_code == 400
    assert MSG_ACTION_ORIGIN_INVALID in origin.text
    assert extra.status_code == incomplete.status_code == 400
    assert MSG_ACTION_INVALID in extra.text
    assert _count_requests(repository.database_path) == 0


def test_missing_secret_rejects_before_the_service(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    closed = _close(repository, _create(repository, case_id="SYN-FOLLOWUP-014"))

    class ServiceMustNotRun:
        def __init__(self, _repository) -> None:
            raise AssertionError("controlled action service was called")

    monkeypatch.setattr(
        "app.human_review_client.FollowUpCoordinationActionService",
        ServiceMustNotRun,
    )
    client = _client(repository, secret="")
    response = client.post(
        f"/review-cases/{closed.id}/controlled-action",
        content=urlencode({"actionExpiry": "1000", "actionToken": "not-a-signature"}),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert MSG_NOT_CONFIGURED in response.text
    assert _count_requests(repository.database_path) == 0


@pytest.mark.parametrize(
    ("case_id", "protocol", "outcome"),
    [
        ("SYN-FOLLOWUP-015", None, None),
        (
            "SYN-FOLLOWUP-004",
            None,
            ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION,
        ),
        (
            "SYN-FOLLOWUP-005",
            _protocol(protocol_id="OTHER_PROTOCOL"),
            ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
        ),
    ],
)
def test_direct_post_against_ineligible_case_fails(tmp_path, case_id, protocol, outcome):
    repository = _repository(tmp_path)
    created = _create(repository, case_id=case_id, protocol=protocol)
    case = created if outcome is None else _close(repository, created, outcome)
    issued = issue_controlled_action_token(secret=SIGNING_SECRET, review_case_id=case.id)
    assert issued is not None
    before = _snapshot(repository.database_path, case.id)
    response = _post_action(
        _client(repository),
        case.id,
        {"actionExpiry": str(issued[1]), "actionToken": issued[0]},
    )
    assert response.status_code == 409
    assert MSG_ACTION_DENIED in response.text
    assert SIGNING_SECRET not in response.text
    assert _count_requests(repository.database_path) == 0
    assert _snapshot(repository.database_path, case.id) == before


def test_unknown_case_returns_not_found(tmp_path):
    repository = _repository(tmp_path)
    missing = "10000000-0000-4000-8000-000000000099"
    issued = issue_controlled_action_token(secret=SIGNING_SECRET, review_case_id=missing)
    assert issued is not None
    response = _post_action(
        _client(repository),
        missing,
        {"actionExpiry": str(issued[1]), "actionToken": issued[0]},
    )
    assert response.status_code == 404
    assert MSG_NOT_FOUND in response.text
    assert _count_requests(repository.database_path) == 0


def test_created_metadata_is_escaped_and_not_stored_as_a_ticket(tmp_path):
    repository = _repository(tmp_path)
    closed = _close(repository, _create(repository, case_id="SYN-FOLLOWUP-011"))
    client = _client(repository)
    posted = _post_action(
        client,
        closed.id,
        _action_fields(client.get(f"/review-cases/{closed.id}").text),
    )
    assert posted.status_code == 303
    assert "set-cookie" not in {name.lower() for name in posted.headers}

    class MarkupRepository:
        def __init__(self, inner) -> None:
            self.inner = inner

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def get_follow_up_coordination_request(self, review_case_id: str):
            stored = self.inner.get_follow_up_coordination_request(review_case_id)
            assert stored is not None
            return replace(stored, created_at='2026-09-30T12:00:00.000000Z<script>alert(1)</script>')

    app.state.followup_review_repository = MarkupRepository(repository)
    page = client.get(f"/review-cases/{closed.id}")
    assert page.headers["cache-control"] == "no-store"
    assert "<script>" not in page.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page.text
    assert isinstance(repository.get_follow_up_coordination_request(closed.id), FollowUpCoordinationRequest)


def test_controlled_action_route_uses_the_service_and_not_a_generic_executor():
    handler = inspect.getsource(submit_controlled_action)
    assert "FollowUpCoordinationActionService" in handler
    assert "ensure_follow_up_coordination_request" in handler
    assert "repository.ensure" not in handler
    assert ".ensure(" not in handler
    assert "set_cookie" not in handler
    loader = inspect.getsource(
        __import__("app.human_review_client", fromlist=["_load_coordination_request"])._load_coordination_request
    )
    assert "get_follow_up_coordination_request" in loader
    assert "ensure" not in loader
    human = (APP / "human_review_client.py").read_text(encoding="utf-8").lower()
    main = (APP / "main.py").read_text(encoding="utf-8")
    for token in ("gemini", "langgraph", "toolnode", "hapi", "mcp", "react", "tool_registry"):
        assert token not in human
    assert '/review-cases/{review_case_id}/controlled-action' in main
    assert "POST /actions" not in main
    migrations = "\n".join(
        path.read_text(encoding="utf-8") for path in (APP / "migrations").glob("*.sql")
    )
    assert "follow_up_coordination_request_events" not in migrations
    assert "follow_up_coordination_request_events" not in human
