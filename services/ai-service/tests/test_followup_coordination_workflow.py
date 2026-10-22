"""Coordination request queue, detail, and the two internal transitions."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.followup_coordination_action import (
    CoordinationRequestStatus,
    FollowUpCoordinationActionService,
    build_coordination_action_identity,
)
from app.followup_coordination_workflow import CoordinationTransitionRejected
from app.followup_review import (
    FollowUpReviewCaseService,
    FollowUpReviewTrigger,
    ReviewOutcome,
    ReviewPersistenceUnavailable,
    build_review_identity,
)
from app.followup_review_sqlite import SCHEMA_VERSION, SQLiteFollowUpReviewCaseRepository
from app.human_attribution import DEVELOPMENT_AUTHENTICATOR_V1, DevelopmentPrincipalSnapshot
from app.human_development_auth import SESSION_COOKIE
from app.human_review_client import (
    MSG_ACTION_TOKEN_INVALID,
    MSG_TRANSITION_REJECTED,
    issue_coordination_transition_token,
)
from app.human_session import HumanSessionService
from app.human_session_sqlite import SQLiteHumanSessionRepository
from app.main import app, get_settings
from app.post_consultation_review import POST_CONSULTATION_RESULT_REVIEW_V1


SIGNING_SECRET = "synthetic-form-signing-secret-b"
DEV_SECRET = "development-secret-value-32chars-min"
SERVICE_TOKEN = "synthetic-service-token-a"
ORIGIN = {"origin": "http://127.0.0.1"}
NOW = datetime(2026, 10, 14, 16, 0, tzinfo=timezone.utc)
APP = Path(__file__).resolve().parents[1] / "app"
REPO_ROOT = Path(__file__).resolve().parents[3]
OBSERVATION = "Observation/syn-secret-observation"


def _settings() -> Settings:
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
        human_review_development_auth_enabled=True,
        human_review_development_auth_secret=DEV_SECRET,
        human_review_development_principal_id="lab-reviewer",
        human_review_development_principal_display_name="Lab reviewer",
    )


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


def _principal(session_id: str | None = None) -> DevelopmentPrincipalSnapshot:
    return DevelopmentPrincipalSnapshot(
        principal_id="lab-reviewer",
        authenticator_id=DEVELOPMENT_AUTHENTICATOR_V1,
        session_id=session_id or str(uuid.uuid4()),
    )


def _requested(repository, case_id: str = "SYN-FOLLOWUP-030"):
    created = repository.ensure(
        FollowUpReviewTrigger(
            case_id=case_id,
            protocol_id=POST_CONSULTATION_RESULT_REVIEW_V1,
            protocol_evaluation_status="matched",
            reason_codes=("post_consultation_result_requires_review",),
            matched_resources=("Encounter/syn-demo-enc-101", OBSERVATION),
            review_identity=build_review_identity(
                case_id,
                POST_CONSULTATION_RESULT_REVIEW_V1,
                ("Encounter/syn-demo-enc-101", OBSERVATION),
            ),
        )
    )
    closed = FollowUpReviewCaseService(repository).close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
        attribution=_principal(),
    )
    request = FollowUpCoordinationActionService(repository).ensure_follow_up_coordination_request(
        closed.id,
        attribution=_principal(),
    )
    return closed, request


def _bind(repository) -> TestClient:
    app.state.followup_review_repository = repository
    app.state.clinical_context_fhir_client = lambda: (_ for _ in ()).throw(AssertionError("fhir"))
    store = SQLiteHumanSessionRepository(repository.database_path.parent / "human-session.sqlite3")
    store.initialize()
    app.state.human_session_repository = store
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app, base_url="http://127.0.0.1")


def _login(client: TestClient) -> None:
    response = client.post(
        "/review-login",
        content=urlencode({"developmentSecret": DEV_SECRET}),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _session(client: TestClient):
    token = client.cookies.get(SESSION_COOKIE)
    assert token
    return HumanSessionService(
        app.state.human_session_repository,
        clock=lambda: datetime.now(timezone.utc),
    ).resolve(token)


def _hidden(html: str, name: str) -> str:
    marker = f'name="{name}" value="'
    start = html.index(marker) + len(marker)
    return html[start:html.index('"', start)]


def _post_form(client: TestClient, path: str, payload: dict[str, str], *, origin: bool = True):
    headers = {"content-type": "application/x-www-form-urlencoded"}
    if origin:
        headers.update(ORIGIN)
    return client.post(
        path,
        content=urlencode(payload),
        headers=headers,
        follow_redirects=False,
    )


def _events(path: Path, request_id: str):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return list(
            connection.execute(
                """
                SELECT from_status, to_status, principal_id, authenticator_id, session_id, occurred_at
                FROM follow_up_coordination_request_events
                WHERE coordination_request_id = ?
                ORDER BY occurred_at, event_id
                """,
                (request_id,),
            )
        )
    finally:
        connection.close()


def test_queue_lists_identifier_case_protocol_status_and_detail_link(tmp_path):
    repository = _repository(tmp_path)
    _case, request = _requested(repository, "SYN-FOLLOWUP-030")
    client = _bind(repository)
    _login(client)
    page = client.get("/review-coordination-requests")
    assert page.status_code == 200
    assert request.id in page.text
    assert "SYN-FOLLOWUP-030" in page.text
    assert POST_CONSULTATION_RESULT_REVIEW_V1 in page.text
    assert "Solicitada" in page.text
    assert "requested" in page.text
    assert "14 de octubre de 2026, 16:00:00 UTC" in page.text
    assert f'href="/review-coordination-requests/{request.id}"' in page.text
    assert ">Detalle</a>" in page.text
    assert OBSERVATION not in page.text
    review = client.get("/review-cases")
    assert 'href="/review-coordination-requests"' in review.text


def test_empty_queue_is_explicit(tmp_path):
    client = _bind(_repository(tmp_path))
    _login(client)
    page = client.get("/review-coordination-requests")
    assert page.status_code == 200
    assert "No hay solicitudes de coordinación interna." in page.text


def test_anonymous_queue_detail_and_transition_redirect_to_login(tmp_path):
    repository = _repository(tmp_path)
    _case, request = _requested(repository)
    client = _bind(repository)
    queue = client.get("/review-coordination-requests", follow_redirects=False)
    detail = client.get(f"/review-coordination-requests/{request.id}", follow_redirects=False)
    posted = _post_form(
        client,
        f"/review-coordination-requests/{request.id}/transition",
        {
            "expectedStatus": "requested",
            "targetStatus": "in_progress",
            "transitionExpiry": "1",
            "transitionToken": "nope",
        },
    )
    assert queue.status_code == detail.status_code == posted.status_code == 303
    assert queue.headers["location"] == detail.headers["location"] == posted.headers["location"] == "/review-login"
    assert _events(repository.database_path, request.id) == []


def test_detail_links_the_review_case_without_clinical_content(tmp_path):
    repository = _repository(tmp_path)
    case, request = _requested(repository)
    client = _bind(repository)
    _login(client)
    session = _session(client)
    page = client.get(f"/review-coordination-requests/{request.id}")
    assert page.status_code == 200
    assert request.id in page.text
    assert f'href="/review-cases/{case.id}"' in page.text
    assert "SYN-FOLLOWUP-030" in page.text
    assert "Cerrado" in page.text
    assert "Todavía no hay transiciones." in page.text
    assert "Pasar la solicitud a en curso" in page.text
    assert OBSERVATION not in page.text
    assert "valueString" not in page.text
    assert session.session_id not in page.text
    assert DEV_SECRET not in page.text
    case_page = client.get(f"/review-cases/{case.id}")
    visible = case_page.text.split("<details>", 1)[0]
    assert f'href="/review-cases/{case.id}/coordination-request"' in visible
    assert request.id not in visible
    opened = client.get(f"/review-cases/{case.id}/coordination-request", follow_redirects=False)
    assert opened.status_code == 303
    assert opened.headers["location"] == f"/review-coordination-requests/{request.id}"


def test_requested_then_completed_records_actor_once_per_step(tmp_path):
    repository = _repository(tmp_path)
    _case, request = _requested(repository)
    client = _bind(repository)
    _login(client)
    session = _session(client)
    detail = client.get(f"/review-coordination-requests/{request.id}")
    started = _post_form(
        client,
        f"/review-coordination-requests/{request.id}/transition",
        {
            "expectedStatus": _hidden(detail.text, "expectedStatus"),
            "targetStatus": _hidden(detail.text, "targetStatus"),
            "transitionExpiry": _hidden(detail.text, "transitionExpiry"),
            "transitionToken": _hidden(detail.text, "transitionToken"),
        },
    )
    assert started.status_code == 303
    progressed = client.get(started.headers["location"])
    assert "En curso" in progressed.text
    assert "in_progress" in progressed.text
    assert "lab-reviewer" in progressed.text
    assert session.session_id not in progressed.text
    finished = _post_form(
        client,
        f"/review-coordination-requests/{request.id}/transition",
        {
            "expectedStatus": _hidden(progressed.text, "expectedStatus"),
            "targetStatus": _hidden(progressed.text, "targetStatus"),
            "transitionExpiry": _hidden(progressed.text, "transitionExpiry"),
            "transitionToken": _hidden(progressed.text, "transitionToken"),
        },
    )
    assert finished.status_code == 303
    done = client.get(finished.headers["location"])
    assert "La solicitud está completada." in done.text
    assert "Marcar la solicitud como completada" not in done.text
    rows = _events(repository.database_path, request.id)
    assert len(rows) == 2
    assert {(row["from_status"], row["to_status"]) for row in rows} == {
        ("requested", "in_progress"),
        ("in_progress", "completed"),
    }
    assert {row["principal_id"] for row in rows} == {"lab-reviewer"}
    assert {row["authenticator_id"] for row in rows} == {DEVELOPMENT_AUTHENTICATOR_V1}
    assert {row["session_id"] for row in rows} == {session.session_id}
    assert {row["occurred_at"] for row in rows} == {"2026-10-14T16:00:00.000000Z"}


def test_resubmit_does_not_append_another_event(tmp_path):
    repository = _repository(tmp_path)
    _case, request = _requested(repository)
    client = _bind(repository)
    _login(client)
    detail = client.get(f"/review-coordination-requests/{request.id}")
    payload = {
        "expectedStatus": _hidden(detail.text, "expectedStatus"),
        "targetStatus": _hidden(detail.text, "targetStatus"),
        "transitionExpiry": _hidden(detail.text, "transitionExpiry"),
        "transitionToken": _hidden(detail.text, "transitionToken"),
    }
    first = _post_form(client, f"/review-coordination-requests/{request.id}/transition", payload)
    second = _post_form(client, f"/review-coordination-requests/{request.id}/transition", payload)
    assert first.status_code == second.status_code == 303
    rows = _events(repository.database_path, request.id)
    assert len(rows) == 1
    assert rows[0]["to_status"] == "in_progress"


def test_invalid_transitions_tokens_and_origin_do_not_write(tmp_path):
    repository = _repository(tmp_path)
    _case, request = _requested(repository)
    with pytest.raises(CoordinationTransitionRejected):
        repository.transition_follow_up_coordination_request(
            request.id,
            expected_status=CoordinationRequestStatus.REQUESTED,
            target_status=CoordinationRequestStatus.COMPLETED,
            attribution=_principal(),
        )
    assert _events(repository.database_path, request.id) == []
    client = _bind(repository)
    _login(client)
    session = _session(client)
    detail = client.get(f"/review-coordination-requests/{request.id}")
    token = _hidden(detail.text, "transitionToken")
    forged_token = token[:-1] + ("1" if token[-1] == "0" else "0")
    forged = _post_form(
        client,
        f"/review-coordination-requests/{request.id}/transition",
        {
            "expectedStatus": "requested",
            "targetStatus": "in_progress",
            "transitionExpiry": _hidden(detail.text, "transitionExpiry"),
            "transitionToken": forged_token,
        },
    )
    assert forged.status_code == 400
    assert MSG_ACTION_TOKEN_INVALID in forged.text
    other = _principal()
    issued = issue_coordination_transition_token(
        secret=SIGNING_SECRET,
        request_id=request.id,
        expected_status="requested",
        target_status="in_progress",
        session_id=other.session_id,
    )
    assert issued is not None
    token, expiry = issued
    foreign = _post_form(
        client,
        f"/review-coordination-requests/{request.id}/transition",
        {
            "expectedStatus": "requested",
            "targetStatus": "in_progress",
            "transitionExpiry": str(expiry),
            "transitionToken": token,
        },
    )
    assert foreign.status_code == 400
    assert session.session_id != other.session_id
    cross = _post_form(
        client,
        f"/review-coordination-requests/{request.id}/transition",
        {
            "expectedStatus": _hidden(detail.text, "expectedStatus"),
            "targetStatus": _hidden(detail.text, "targetStatus"),
            "transitionExpiry": _hidden(detail.text, "transitionExpiry"),
            "transitionToken": _hidden(detail.text, "transitionToken"),
        },
        origin=False,
    )
    assert cross.status_code == 400
    assert _events(repository.database_path, request.id) == []
    repository.transition_follow_up_coordination_request(
        request.id,
        expected_status=CoordinationRequestStatus.REQUESTED,
        target_status=CoordinationRequestStatus.IN_PROGRESS,
        attribution=_principal(session.session_id),
    )
    repeated = _post_form(
        client,
        f"/review-coordination-requests/{request.id}/transition",
        {
            "expectedStatus": _hidden(detail.text, "expectedStatus"),
            "targetStatus": _hidden(detail.text, "targetStatus"),
            "transitionExpiry": _hidden(detail.text, "transitionExpiry"),
            "transitionToken": _hidden(detail.text, "transitionToken"),
        },
    )
    assert repeated.status_code == 303
    skipped = issue_coordination_transition_token(
        secret=SIGNING_SECRET,
        request_id=request.id,
        expected_status="requested",
        target_status="completed",
        session_id=session.session_id,
    )
    assert skipped is not None
    skip_token, skip_expiry = skipped
    rejected = _post_form(
        client,
        f"/review-coordination-requests/{request.id}/transition",
        {
            "expectedStatus": "requested",
            "targetStatus": "completed",
            "transitionExpiry": str(skip_expiry),
            "transitionToken": skip_token,
        },
    )
    assert rejected.status_code == 409
    assert MSG_TRANSITION_REJECTED in rejected.text
    assert [row["to_status"] for row in _events(repository.database_path, request.id)] == ["in_progress"]


def test_failed_event_insert_leaves_the_request_requested(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    _case, request = _requested(repository)
    real_connect = sqlite3.connect

    class _Guard:
        def __init__(self, inner):
            object.__setattr__(self, "_inner", inner)

        def execute(self, sql, *args, **kwargs):
            if isinstance(sql, str) and "INSERT INTO follow_up_coordination_request_events" in sql:
                raise sqlite3.IntegrityError("forced")
            return self._inner.execute(sql, *args, **kwargs)

        def __enter__(self):
            self._inner.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            return self._inner.__exit__(exc_type, exc, tb)

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def __setattr__(self, name, value):
            setattr(self._inner, name, value)

    monkeypatch.setattr(
        "app.followup_review_sqlite.sqlite3.connect",
        lambda *args, **kwargs: _Guard(real_connect(*args, **kwargs)),
    )
    with pytest.raises(ReviewPersistenceUnavailable):
        repository.transition_follow_up_coordination_request(
            request.id,
            expected_status=CoordinationRequestStatus.REQUESTED,
            target_status=CoordinationRequestStatus.IN_PROGRESS,
            attribution=_principal(),
        )
    monkeypatch.undo()
    stored = repository.get_follow_up_coordination_request(request.review_case_id)
    assert stored is not None
    assert stored.status is CoordinationRequestStatus.REQUESTED
    assert _events(repository.database_path, request.id) == []


def test_version_three_upgrade_keeps_requested_rows(tmp_path):
    path = tmp_path / "review.sqlite3"
    connection = sqlite3.connect(path)
    try:
        for name in (
            "001_follow_up_review.sql",
            "002_follow_up_coordination_request.sql",
            "003_follow_up_human_attribution.sql",
        ):
            connection.executescript((APP / "migrations" / name).read_text(encoding="utf-8"))
        review_case_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        identity = build_review_identity(
            "SYN-FOLLOWUP-031",
            POST_CONSULTATION_RESULT_REVIEW_V1,
            ("Encounter/syn-demo-enc-101",),
        )
        action_identity = build_coordination_action_identity(review_case_id)
        created_at = "2026-10-14T16:00:00.000000Z"
        connection.execute(
            """
            INSERT INTO follow_up_review_cases (
                id, review_identity, case_id, protocol_id, protocol_evaluation_status,
                reason_codes_json, matched_resources_json, status, outcome, version,
                created_at, updated_at, closed_at
            ) VALUES (?, ?, 'SYN-FOLLOWUP-031', ?, 'matched', '[]', '[]',
                      'closed', 'follow_up_coordination_planned', 2, ?, ?, ?)
            """,
            (
                review_case_id,
                identity,
                POST_CONSULTATION_RESULT_REVIEW_V1,
                created_at,
                created_at,
                created_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO follow_up_coordination_requests (
                id, action_identity, review_case_id, protocol_id, action_type, status, created_at
            ) VALUES (?, ?, ?, ?, 'create_follow_up_coordination_request', 'requested', ?)
            """,
            (
                request_id,
                action_identity,
                review_case_id,
                POST_CONSULTATION_RESULT_REVIEW_V1,
                created_at,
            ),
        )
        connection.commit()
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
    finally:
        connection.close()
    repository = SQLiteFollowUpReviewCaseRepository(path, clock=lambda: NOW)
    repository.initialize()
    with sqlite3.connect(path) as upgraded:
        assert upgraded.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 5
        status = upgraded.execute(
            "SELECT status, created_at FROM follow_up_coordination_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        assert tuple(status) == ("requested", created_at)
        assert (
            upgraded.execute("SELECT COUNT(*) FROM follow_up_coordination_request_events").fetchone()[0]
            == 0
        )
    moved = repository.transition_follow_up_coordination_request(
        request_id,
        expected_status=CoordinationRequestStatus.REQUESTED,
        target_status=CoordinationRequestStatus.IN_PROGRESS,
        attribution=_principal(),
    )
    assert moved.applied is True
    assert moved.request.status is CoordinationRequestStatus.IN_PROGRESS


def test_event_history_rejects_updates(tmp_path):
    repository = _repository(tmp_path)
    _case, request = _requested(repository)
    repository.transition_follow_up_coordination_request(
        request.id,
        expected_status=CoordinationRequestStatus.REQUESTED,
        target_status=CoordinationRequestStatus.IN_PROGRESS,
        attribution=_principal(),
    )
    connection = sqlite3.connect(repository.database_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE follow_up_coordination_request_events SET principal_id = 'other-reviewer'"
            )
    finally:
        connection.close()
    assert _events(repository.database_path, request.id)[0]["principal_id"] == "lab-reviewer"


def test_reset_still_removes_a_transitioned_demo_request(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "reset_demo_cases_workflow",
        REPO_ROOT / "scripts" / "demo-reproducibility" / "reset_demo_cases.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    review = tmp_path / "follow-up-review.sqlite3"
    repository = SQLiteFollowUpReviewCaseRepository(review, clock=lambda: NOW)
    repository.initialize()
    _case, request = _requested(repository, "SYN-DEMO-101")
    repository.transition_follow_up_coordination_request(
        request.id,
        expected_status=CoordinationRequestStatus.REQUESTED,
        target_status=CoordinationRequestStatus.IN_PROGRESS,
        attribution=_principal(),
    )
    session = tmp_path / "human-session.sqlite3"
    knowledge = tmp_path / "institutional-knowledge.sqlite3"
    session.write_bytes(b"")
    knowledge.write_bytes(b"")
    report = module.reset_demo_review(
        review_db_path=str(review.resolve()),
        configured_review_db_path=str(review.resolve()),
        session_db_path=str(session.resolve()),
        knowledge_db_path=str(knowledge.resolve()),
        service_accepts_connections=lambda: False,
    )
    assert report.removed_coordination_requests == 1
    with sqlite3.connect(review) as connection:
        assert connection.execute("SELECT COUNT(*) FROM follow_up_coordination_requests").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM follow_up_coordination_request_events").fetchone()[0] == 0
        assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
