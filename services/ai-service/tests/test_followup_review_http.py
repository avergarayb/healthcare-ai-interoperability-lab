from __future__ import annotations

import base64
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.config import Settings
from app.followup_review import (
    FollowUpReviewCaseService,
    ReviewCaseStatus,
    ReviewOutcome,
    ReviewPersistenceUnavailable,
)
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.langgraph_fhir_client import InMemoryAuditSink, PreparedReadClient
from app.langgraph_followup_workflow import FollowUpWorkflow
from app.main import app, get_settings
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)


CASE = "SYN-FOLLOWUP-008"
TOKEN = "test-model-boundary-token"
AUTH = {"X-Service-Token": TOKEN}
BASE_TIME = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


class AdvancingClock:
    def __init__(self) -> None:
        self.value = BASE_TIME

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


def _protocol(resource_suffix: str = "008") -> ProtocolReviewResult:
    return ProtocolReviewResult(
        id=POST_CONSULTATION_RESULT_REVIEW_V1,
        evaluation_status=ProtocolEvaluationStatus.MATCHED,
        reason_codes=("post_consultation_result_requires_review",),
        matched_resources=(
            f"Encounter/encounter-{resource_suffix}",
            f"Observation/observation-{resource_suffix}",
        ),
        human_review_status="required",
        human_review_reason="deterministic_post_consultation_protocol_match",
        action_status="proposed",
        action_type="review_follow_up_case",
    )


def _repository(tmp_path, *, clock=None):
    repository = SQLiteFollowUpReviewCaseRepository(
        tmp_path / "review.sqlite3",
        clock=clock or AdvancingClock(),
    )
    repository.initialize()
    return repository


def _create(repository, *, case_id=CASE, resource_suffix="008"):
    case = FollowUpReviewCaseService(repository).ensure_for_protocol(
        case_id,
        _protocol(resource_suffix),
    )
    assert case is not None
    return case


def _raw_cursor(payload: str) -> str:
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def _execute_direct(path, sql, parameters=()):
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(sql, parameters)
        connection.commit()
    finally:
        connection.close()


@pytest.fixture(autouse=True)
def _clean_application_state():
    app.dependency_overrides.clear()
    if hasattr(app.state, "followup_review_repository"):
        del app.state.followup_review_repository
    yield
    app.dependency_overrides.clear()
    if hasattr(app.state, "followup_review_repository"):
        del app.state.followup_review_repository


def _client(repository) -> TestClient:
    app.state.followup_review_repository = repository
    app.dependency_overrides[get_settings] = lambda: _settings()
    return TestClient(app)


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/internal/follow-up-review-cases", None),
        ("get", "/internal/follow-up-review-cases/00000000-0000-4000-8000-000000000000", None),
        (
            "post",
            "/internal/follow-up-review-cases/00000000-0000-4000-8000-000000000000/close",
            {"expectedVersion": 1, "outcome": "follow_up_coordination_planned"},
        ),
    ],
)
def test_all_review_endpoints_require_service_authentication(tmp_path, method, path, body):
    client = _client(_repository(tmp_path))
    response = getattr(client, method)(path, json=body) if body is not None else getattr(client, method)(path)
    assert response.status_code == 401
    assert response.content == b""


def test_queue_defaults_open_and_returns_minimized_fields(tmp_path):
    repository = _repository(tmp_path)
    open_case = _create(repository)
    closed_case = _create(repository, resource_suffix="009")
    repository.close(
        closed_case.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    response = _client(repository).get("/internal/follow-up-review-cases", headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "reviewCaseId": open_case.id,
                "caseId": CASE,
                "protocolId": POST_CONSULTATION_RESULT_REVIEW_V1,
                "status": "open",
                "version": 1,
                "createdAt": open_case.created_at,
                "updatedAt": open_case.updated_at,
            }
        ]
    }
    assert "matchedResources" not in response.text
    assert "reviewIdentity" not in response.text


def test_queue_closed_filter_and_exact_case_filter(tmp_path):
    repository = _repository(tmp_path)
    first = _create(repository, case_id=CASE, resource_suffix="008")
    second = _create(repository, case_id="SYN-FOLLOWUP-009", resource_suffix="009")
    for case in (first, second):
        repository.close(
            case.id,
            expected_version=1,
            outcome=ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION,
        )
    response = _client(repository).get(
        "/internal/follow-up-review-cases",
        params={"status": "closed", "caseId": "SYN-FOLLOWUP-009"},
        headers=AUTH,
    )
    assert response.status_code == 200
    assert [item["reviewCaseId"] for item in response.json()["items"]] == [second.id]
    assert response.json()["items"][0]["outcome"] == "review_completed_no_operational_action"


def test_queue_uses_stable_oldest_first_cursor_pagination(tmp_path):
    repository = _repository(tmp_path)
    cases = [_create(repository, resource_suffix=str(index)) for index in range(3)]
    client = _client(repository)
    first = client.get("/internal/follow-up-review-cases", params={"limit": 2}, headers=AUTH)
    assert first.status_code == 200
    assert [item["reviewCaseId"] for item in first.json()["items"]] == [cases[0].id, cases[1].id]
    cursor = first.json()["nextCursor"]
    second = client.get(
        "/internal/follow-up-review-cases",
        params={"limit": 2, "cursor": cursor},
        headers=AUTH,
    )
    assert second.status_code == 200
    assert [item["reviewCaseId"] for item in second.json()["items"]] == [cases[2].id]
    assert "nextCursor" not in second.json()


def test_queue_cursor_paginates_same_timestamp_by_review_case_id(tmp_path):
    repository = _repository(tmp_path, clock=lambda: BASE_TIME)
    cases = [_create(repository, resource_suffix=str(index)) for index in range(5)]
    client = _client(repository)
    returned_ids = []
    cursor = None

    while True:
        params = {"limit": 2}
        if cursor is not None:
            params["cursor"] = cursor
        response = client.get(
            "/internal/follow-up-review-cases",
            params=params,
            headers=AUTH,
        )
        assert response.status_code == 200
        body = response.json()
        returned_ids.extend(item["reviewCaseId"] for item in body["items"])
        cursor = body.get("nextCursor")
        if cursor is None:
            break

    assert returned_ids == sorted(case.id for case in cases)
    assert len(returned_ids) == len(set(returned_ids)) == len(cases)


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"cursor": "not valid!"},
        {"unexpected": "value"},
    ],
)
def test_queue_rejects_invalid_or_unbounded_queries(tmp_path, params):
    response = _client(_repository(tmp_path)).get(
        "/internal/follow-up-review-cases", params=params, headers=AUTH
    )
    assert response.status_code == 422


@pytest.mark.parametrize("duplicate_key", ["status", "caseId", "createdAt", "id"])
def test_queue_rejects_cursor_with_duplicate_top_level_key(tmp_path, duplicate_key):
    repository = _repository(tmp_path)
    case = _create(repository)
    fields = [
        ('"v"', "1"),
        ('"status"', '"open"'),
        ('"caseId"', "null"),
        ('"createdAt"', json.dumps(case.created_at)),
        ('"id"', json.dumps(case.id)),
    ]
    duplicate_value = dict(fields)[json.dumps(duplicate_key)]
    raw = "{" + ",".join(f"{key}:{value}" for key, value in fields) + (
        f",{json.dumps(duplicate_key)}:{duplicate_value}" + "}"
    )

    response = _client(repository).get(
        "/internal/follow-up-review-cases",
        params={"cursor": _raw_cursor(raw)},
        headers=AUTH,
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid review case cursor"}


def test_queue_rejects_base64_cursor_with_invalid_json(tmp_path):
    response = _client(_repository(tmp_path)).get(
        "/internal/follow-up-review-cases",
        params={"cursor": _raw_cursor('{"v":1')},
        headers=AUTH,
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid review case cursor"}


@pytest.mark.parametrize(
    "created_at",
    [
        "2026-09-30Z",
        "2026-09-30T12Z",
        "2026-09-30 12:00:00.000000Z",
        "2026-09-30T12:00:00+00:00",
        "2026-09-30T12:00:00.123Z",
        "2026-09-30T12:00:00.000000Ztrailing",
    ],
)
def test_queue_rejects_cursor_with_noncanonical_timestamp(tmp_path, created_at):
    repository = _repository(tmp_path)
    case = _create(repository)
    cursor = _raw_cursor(
        json.dumps(
            {
                "v": 1,
                "status": "open",
                "caseId": None,
                "createdAt": created_at,
                "id": case.id,
            },
            separators=(",", ":"),
        )
    )

    response = _client(repository).get(
        "/internal/follow-up-review-cases",
        params={"cursor": cursor},
        headers=AUTH,
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid review case cursor"}


def test_cursor_cannot_be_reused_with_different_filters(tmp_path):
    repository = _repository(tmp_path)
    _create(repository, resource_suffix="1")
    _create(repository, resource_suffix="2")
    client = _client(repository)
    cursor = client.get(
        "/internal/follow-up-review-cases", params={"limit": 1}, headers=AUTH
    ).json()["nextCursor"]
    response = client.get(
        "/internal/follow-up-review-cases",
        params={"status": "closed", "limit": 1, "cursor": cursor},
        headers=AUTH,
    )
    assert response.status_code == 422


def test_detail_returns_provenance_and_transition_history_without_clinical_payload(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    response = _client(repository).get(
        f"/internal/follow-up-review-cases/{case.id}", headers=AUTH
    )
    assert response.status_code == 200
    body = response.json()
    assert body["protocolEvaluationStatus"] == "matched"
    assert body["reasonCodes"] == ["post_consultation_result_requires_review"]
    assert body["matchedResources"] == sorted(_protocol().matched_resources)
    assert body["transitions"][0]["eventType"] == "created"
    for forbidden in ("patient", "bundle", "answer", "evidence", "prompt", "reviewer"):
        assert forbidden not in response.text.lower()


def test_detail_returns_404_and_invalid_id_is_bounded_422(tmp_path):
    client = _client(_repository(tmp_path))
    missing = client.get(
        "/internal/follow-up-review-cases/00000000-0000-4000-8000-000000000000",
        headers=AUTH,
    )
    invalid = client.get("/internal/follow-up-review-cases/not-a-uuid", headers=AUTH)
    assert missing.status_code == 404
    assert invalid.status_code == 422
    assert invalid.json() == {"detail": "Invalid review case id"}


def test_close_success_and_same_outcome_retry_are_idempotent(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    client = _client(repository)
    request = {"expectedVersion": 1, "outcome": "follow_up_coordination_planned"}
    first = client.post(f"/internal/follow-up-review-cases/{case.id}/close", json=request, headers=AUTH)
    second = client.post(f"/internal/follow-up-review-cases/{case.id}/close", json=request, headers=AUTH)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["status"] == "closed"
    assert first.json()["version"] == 2
    assert [event["eventType"] for event in first.json()["transitions"]] == ["created", "closed"]


def test_close_conflict_not_found_and_validation_responses(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    client = _client(repository)
    stale = client.post(
        f"/internal/follow-up-review-cases/{case.id}/close",
        json={"expectedVersion": 2, "outcome": "follow_up_coordination_planned"},
        headers=AUTH,
    )
    assert stale.status_code == 409
    client.post(
        f"/internal/follow-up-review-cases/{case.id}/close",
        json={"expectedVersion": 1, "outcome": "follow_up_coordination_planned"},
        headers=AUTH,
    )
    different = client.post(
        f"/internal/follow-up-review-cases/{case.id}/close",
        json={"expectedVersion": 2, "outcome": "review_completed_no_operational_action"},
        headers=AUTH,
    )
    assert different.status_code == 409
    missing = client.post(
        "/internal/follow-up-review-cases/00000000-0000-4000-8000-000000000000/close",
        json={"expectedVersion": 1, "outcome": "follow_up_coordination_planned"},
        headers=AUTH,
    )
    assert missing.status_code == 404
    for body in (
        {"expectedVersion": 1, "outcome": "dismissed"},
        {"expectedVersion": 1, "outcome": "follow_up_coordination_planned", "note": "no"},
    ):
        assert client.post(
            f"/internal/follow-up-review-cases/{case.id}/close", json=body, headers=AUTH
        ).status_code == 422


def test_repository_unavailable_maps_to_generic_503(tmp_path):
    class Unavailable:
        def list_cases(self, **_kwargs):
            raise ReviewPersistenceUnavailable("database path and sql must stay hidden")

    response = _client(Unavailable()).get("/internal/follow-up-review-cases", headers=AUTH)
    assert response.status_code == 503
    assert response.json() == {"detail": "Follow-up review persistence unavailable"}
    assert "path" not in response.text
    assert "sql" not in response.text.lower()


def test_corrupt_persisted_case_maps_to_generic_503(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    _execute_direct(
        repository.database_path,
        "UPDATE follow_up_review_cases SET version = 2 WHERE id = ?",
        (case.id,),
    )

    response = _client(repository).get(
        f"/internal/follow-up-review-cases/{case.id}",
        headers=AUTH,
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Follow-up review persistence unavailable"}
    assert "version" not in response.text.lower()


def test_corrupt_persisted_history_maps_to_generic_503(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    closed = repository.close(
        case.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    _execute_direct(
        repository.database_path,
        """
        UPDATE follow_up_review_case_events
        SET outcome = 'review_completed_no_operational_action'
        WHERE review_case_id = ? AND event_type = 'closed'
        """,
        (closed.id,),
    )

    response = _client(repository).get(
        f"/internal/follow-up-review-cases/{closed.id}",
        headers=AUTH,
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Follow-up review persistence unavailable"}
    assert closed.id not in response.text


def test_detail_and_close_repository_failures_map_to_generic_503(tmp_path):
    class Unavailable:
        def get_detail(self, _review_case_id):
            raise ReviewPersistenceUnavailable

        def close(self, *_args, **_kwargs):
            raise ReviewPersistenceUnavailable

    client = _client(Unavailable())
    review_case_id = "00000000-0000-4000-8000-000000000000"
    detail = client.get(f"/internal/follow-up-review-cases/{review_case_id}", headers=AUTH)
    close = client.post(
        f"/internal/follow-up-review-cases/{review_case_id}/close",
        json={"expectedVersion": 1, "outcome": "follow_up_coordination_planned"},
        headers=AUTH,
    )
    assert detail.status_code == close.status_code == 503
    assert detail.json() == close.json() == {"detail": "Follow-up review persistence unavailable"}


def _matched_workflow_factory(repository, monkeypatch, model, *, observation_id="observation-008"):
    def factory(run_id: str):
        return FollowUpWorkflow(
            model=model,
            sink=InMemoryAuditSink(),
            fhir_client=PreparedReadClient(
                case_id=CASE,
                patient_id="patient-008",
                observation_id=observation_id,
                appointments=[],
            ),
            clock=lambda: "2026-09-30T12:00:00Z",
            run_id=run_id,
            now=lambda: BASE_TIME,
        )

    monkeypatch.setattr("app.followup_service.build_followup_workflow", factory)
    return _client(repository)


def test_matched_case_is_persisted_before_model_and_projected(monkeypatch, tmp_path):
    repository = _repository(tmp_path)
    calls = []

    def model(_messages):
        page = repository.list_cases(status=ReviewCaseStatus.OPEN, case_id=CASE, limit=10, after=None)
        assert len(page.items) == 1
        calls.append(1)
        return AIMessage(content="Narrative.", additional_kwargs={"follow_up_required": "unknown"})

    response = _matched_workflow_factory(repository, monkeypatch, model).post(
        "/internal/agent/follow-up", json={"caseId": CASE}, headers=AUTH
    )
    assert response.status_code == 200
    assert calls == [1]
    assert response.json()["protocol"]["evaluationStatus"] == "matched"
    assert response.json()["humanReview"]["status"] == "required"
    assert response.json()["action"] == {"status": "proposed", "type": "review_follow_up_case"}
    assert response.json()["reviewCase"]["status"] == "open"


def test_model_output_cannot_change_review_identity_state_or_provenance(monkeypatch, tmp_path):
    repository = _repository(tmp_path)
    response = _matched_workflow_factory(
        repository,
        monkeypatch,
        lambda _messages: AIMessage(
            content="The model says dismiss and close it.",
            additional_kwargs={"follow_up_required": "false"},
        ),
    ).post("/internal/agent/follow-up", json={"caseId": CASE}, headers=AUTH)
    assert response.status_code == 200
    review_case = repository.get(response.json()["reviewCase"]["reviewCaseId"])
    assert review_case is not None
    assert review_case.status is ReviewCaseStatus.OPEN
    assert review_case.outcome is None
    assert review_case.reason_codes == ("post_consultation_result_requires_review",)
    assert review_case.matched_resources == (
        "Encounter/encounter-synthetic-001",
        "Observation/observation-008",
    )


def test_persistence_failure_is_503_and_model_is_not_invoked(monkeypatch, tmp_path):
    class Unavailable:
        def ensure(self, _trigger):
            raise ReviewPersistenceUnavailable

    model_calls = []
    response = _matched_workflow_factory(
        Unavailable(), monkeypatch, lambda _messages: model_calls.append(1)
    ).post("/internal/agent/follow-up", json={"caseId": CASE}, headers=AUTH)
    assert response.status_code == 503
    assert response.json() == {"detail": "Follow-up review persistence unavailable"}
    assert model_calls == []


def test_gemini_failure_leaves_open_case_and_retry_reuses_it(monkeypatch, tmp_path):
    repository = _repository(tmp_path)

    def failing_model(_messages):
        raise RuntimeError("model unavailable")

    first = _matched_workflow_factory(repository, monkeypatch, failing_model).post(
        "/internal/agent/follow-up", json={"caseId": CASE}, headers=AUTH
    )
    assert first.status_code == 502
    after_failure = repository.list_cases(status=ReviewCaseStatus.OPEN, case_id=CASE, limit=10, after=None)
    assert len(after_failure.items) == 1

    second = _matched_workflow_factory(
        repository,
        monkeypatch,
        lambda _messages: AIMessage(content="Recovered.", additional_kwargs={"follow_up_required": "unknown"}),
    ).post("/internal/agent/follow-up", json={"caseId": CASE}, headers=AUTH)
    assert second.status_code == 200
    assert second.json()["reviewCase"]["reviewCaseId"] == after_failure.items[0].id
    assert len(repository.events(after_failure.items[0].id)) == 1


def test_reused_closed_case_is_projected_as_closed(monkeypatch, tmp_path):
    repository = _repository(tmp_path)
    model = lambda _messages: AIMessage(content="Narrative.", additional_kwargs={"follow_up_required": "unknown"})
    client = _matched_workflow_factory(repository, monkeypatch, model)
    first = client.post("/internal/agent/follow-up", json={"caseId": CASE}, headers=AUTH)
    review_case_id = first.json()["reviewCase"]["reviewCaseId"]
    client.post(
        f"/internal/follow-up-review-cases/{review_case_id}/close",
        json={"expectedVersion": 1, "outcome": "follow_up_coordination_planned"},
        headers=AUTH,
    )
    second = client.post("/internal/agent/follow-up", json={"caseId": CASE}, headers=AUTH)
    assert second.status_code == 200
    assert second.json()["humanReview"]["status"] == "required"
    assert second.json()["reviewCase"] == {
        "reviewCaseId": review_case_id,
        "status": "closed",
        "version": 2,
    }


def test_different_matched_observation_creates_another_review_case(monkeypatch, tmp_path):
    repository = _repository(tmp_path)
    model = lambda _messages: AIMessage(content="Narrative.", additional_kwargs={"follow_up_required": "unknown"})
    first = _matched_workflow_factory(repository, monkeypatch, model, observation_id="observation-a").post(
        "/internal/agent/follow-up", json={"caseId": CASE}, headers=AUTH
    )
    second = _matched_workflow_factory(repository, monkeypatch, model, observation_id="observation-b").post(
        "/internal/agent/follow-up", json={"caseId": CASE}, headers=AUTH
    )
    assert first.json()["reviewCase"]["reviewCaseId"] != second.json()["reviewCase"]["reviewCaseId"]


@pytest.mark.parametrize(
    "client_kwargs",
    [
        {},
        {"observations": [], "appointments": []},
        {"fail_observation_read": True, "appointments": []},
    ],
)
def test_non_matched_insufficient_and_unavailable_create_no_case(
    monkeypatch, tmp_path, client_kwargs
):
    repository = _repository(tmp_path)

    def factory(run_id: str):
        return FollowUpWorkflow(
            model=lambda _messages: AIMessage(
                content="Narrative.", additional_kwargs={"follow_up_required": "unknown"}
            ),
            sink=InMemoryAuditSink(),
            fhir_client=PreparedReadClient(case_id=CASE, patient_id="patient-008", **client_kwargs),
            clock=lambda: "2026-09-30T12:00:00Z",
            run_id=run_id,
            now=lambda: BASE_TIME,
        )

    monkeypatch.setattr("app.followup_service.build_followup_workflow", factory)
    response = _client(repository).post(
        "/internal/agent/follow-up", json={"caseId": CASE}, headers=AUTH
    )
    assert response.status_code == 200
    assert "reviewCase" not in response.json()
    page = repository.list_cases(status=ReviewCaseStatus.OPEN, case_id=None, limit=10, after=None)
    assert page.items == ()


def test_lifespan_initializes_and_reopens_configured_store(monkeypatch, tmp_path):
    path = tmp_path / "lifespan.sqlite3"
    monkeypatch.setenv("AI_REVIEW_DB_PATH", str(path))
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            assert path.exists()
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
    finally:
        get_settings.cache_clear()


def test_lifespan_rejects_future_schema(monkeypatch, tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=99")
    monkeypatch.setenv("AI_REVIEW_DB_PATH", str(path))
    get_settings.cache_clear()
    try:
        with pytest.raises(Exception, match="schema version is unsupported"):
            with TestClient(app):
                pass
    finally:
        get_settings.cache_clear()
