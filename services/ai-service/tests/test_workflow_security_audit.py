"""Workflow access auditing without HAPI, Gemini, or external providers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.langgraph_workflow_orchestration as orchestration
from app.config import Settings
from app.followup_review import ReviewCaseStatus, ReviewOutcome
from app.main import app, get_settings
from app.security_audit import SecurityAuditEvent, SecurityAuditUnavailable, workflow_security_event
from app.security_audit_sqlite import SQLiteSecurityAuditRepository


TOKEN = "synthetic-workflow-service-token"
CASE_ID = "SYN-FOLLOWUP-016"
WORKFLOW_TYPE = "post_consultation"
REVIEW_ID = "11111111-1111-4111-8111-111111111111"
DECISION = ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION.value
CORRELATION_ALLOWED = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
CORRELATION_RETRY = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
CORRELATION_MISSING = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
CORRELATION_INVALID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
CORRELATION_TYPE = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"


class FakeSaver:
    def __init__(self, record: dict | None = None) -> None:
        self.record = record

    def index_get(self, workflow_id: str) -> dict | None:
        if self.record is None or self.record.get("workflowId") != workflow_id:
            return None
        return dict(self.record)


class ReviewRepository:
    def __init__(self) -> None:
        self.case = SimpleNamespace(
            status=ReviewCaseStatus.CLOSED,
            outcome=ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION,
        )

    def get(self, review_case_id: str):
        return self.case if review_case_id == REVIEW_ID else None


class DownAudit:
    def __init__(self) -> None:
        self.attempts = 0

    def append(self, event: SecurityAuditEvent) -> SecurityAuditEvent:
        self.attempts += 1
        raise SecurityAuditUnavailable("synthetic storage failure")


def _settings(tmp_path) -> Settings:
    return Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token=TOKEN,
        host="127.0.0.1",
        port=8090,
        followup_agent_enabled=True,
        ai_review_db_path=str(tmp_path / "review.sqlite3"),
        human_session_db_path=str(tmp_path / "human-session.sqlite3"),
        security_audit_db_path=str(tmp_path / "security-audit.sqlite3"),
    )


def _audit(tmp_path) -> SQLiteSecurityAuditRepository:
    repository = SQLiteSecurityAuditRepository(tmp_path / "security-audit.sqlite3")
    repository.initialize()
    return repository


def _audit_storage_bytes(tmp_path) -> bytes:
    return b"".join(
        path.read_bytes()
        for path in tmp_path.glob("security-audit.sqlite3*")
        if path.is_file()
    )


def _client(tmp_path, audit_repository: object, *, review_repository: object | None = None) -> TestClient:
    settings = _settings(tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.security_audit_repository = audit_repository
    app.state.followup_review_repository = review_repository or object()
    app.state.agent_workflow_ports = object()
    app.state.agent_workflow_saver = FakeSaver()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_app_state():
    names = (
        "security_audit_repository",
        "security_audit_clock",
        "followup_review_repository",
        "agent_workflow_ports",
        "agent_workflow_saver",
    )
    app.dependency_overrides.clear()
    for name in names:
        if hasattr(app.state, name):
            delattr(app.state, name)
    yield
    app.dependency_overrides.clear()
    for name in names:
        if hasattr(app.state, name):
            delattr(app.state, name)


def test_authorized_start_is_durable_minimized_and_idempotent(tmp_path, monkeypatch):
    audit = _audit(tmp_path)
    client = _client(tmp_path, audit)
    actions: set[str] = set()

    def fake_start(saver, ports, case_id: str, workflow_type: str) -> dict:
        del saver, ports
        workflow_id = orchestration.workflow_id_for(case_id, workflow_type)
        actions.add(workflow_id)
        return {"workflowId": workflow_id, "status": "waiting_human"}

    monkeypatch.setattr(orchestration, "start_workflow", fake_start)
    body = {
        "caseId": CASE_ID,
        "workflowType": WORKFLOW_TYPE,
        "clinicalPayload": {"patient": "SYNTHETIC-CLINICAL-MARKER"},
    }
    first = client.post(
        "/internal/workflows",
        headers={"X-Service-Token": TOKEN, "X-Correlation-ID": CORRELATION_ALLOWED},
        json=body,
    )
    second = client.post(
        "/internal/workflows",
        headers={"X-Service-Token": TOKEN, "X-Correlation-ID": CORRELATION_RETRY},
        json=body,
    )
    assert first.status_code == second.status_code == 200
    assert len(actions) == 1

    restarted = SQLiteSecurityAuditRepository(tmp_path / "security-audit.sqlite3")
    restarted.initialize()
    event = restarted.list_by_correlation(CORRELATION_ALLOWED)[0]
    assert (event.event_type, event.action, event.outcome, event.reason_code) == (
        "workflow_start",
        "start_workflow",
        "allowed",
        "access_granted",
    )
    assert event.actor_type == "service_client"
    assert event.actor_id == "internal-service"
    assert event.organization_id is None
    assert event.resource_reference == f"workflow/{first.json()['workflowId']}"
    assert dict(event.metadata) == {"route": "/internal/workflows", "workflow_type": WORKFLOW_TYPE}
    assert len(restarted.list_by_correlation(CORRELATION_RETRY)) == 1
    raw = _audit_storage_bytes(tmp_path)
    assert TOKEN.encode() not in raw
    assert CASE_ID.encode() not in raw
    assert b"SYNTHETIC-CLINICAL-MARKER" not in raw


def test_start_denials_are_audited_before_any_workflow_effect(tmp_path, monkeypatch):
    audit = _audit(tmp_path)
    client = _client(tmp_path, audit)
    starts = []

    def fake_start(*args, **kwargs):
        starts.append((args, kwargs))
        raise AssertionError("a rejected request must not start a workflow")

    monkeypatch.setattr(orchestration, "start_workflow", fake_start)
    missing = client.post(
        "/internal/workflows",
        headers={"X-Correlation-ID": CORRELATION_MISSING},
        json={"caseId": CASE_ID, "workflowType": WORKFLOW_TYPE},
    )
    invalid = client.post(
        "/internal/workflows",
        headers={"X-Service-Token": "wrong", "X-Correlation-ID": CORRELATION_INVALID},
        json={"caseId": CASE_ID, "workflowType": WORKFLOW_TYPE},
    )
    unsupported = client.post(
        "/internal/workflows",
        headers={"X-Service-Token": TOKEN, "X-Correlation-ID": CORRELATION_TYPE},
        json={"caseId": CASE_ID, "workflowType": "untrusted_external_workflow"},
    )
    assert (missing.status_code, invalid.status_code, unsupported.status_code) == (401, 401, 422)
    assert starts == []
    expected = {
        CORRELATION_MISSING: ("service_token_missing", "anonymous"),
        CORRELATION_INVALID: ("service_token_invalid", "anonymous"),
        CORRELATION_TYPE: ("workflow_type_not_allowed", "service_client"),
    }
    for correlation_id, (reason, actor_type) in expected.items():
        event = audit.list_by_correlation(correlation_id)[0]
        assert event.outcome == "denied"
        assert event.reason_code == reason
        assert event.actor_type == actor_type
        assert event.resource_reference is None
    raw = _audit_storage_bytes(tmp_path)
    assert TOKEN.encode() not in raw
    assert b"untrusted_external_workflow" not in raw


def test_start_fails_closed_when_audit_cannot_write(tmp_path, monkeypatch):
    down = DownAudit()
    client = _client(tmp_path, down)
    starts = []
    monkeypatch.setattr(orchestration, "start_workflow", lambda *args: starts.append(args))
    response = client.post(
        "/internal/workflows",
        headers={"X-Service-Token": TOKEN, "X-Correlation-ID": CORRELATION_ALLOWED},
        json={"caseId": CASE_ID, "workflowType": WORKFLOW_TYPE},
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "Security audit persistence unavailable"}
    assert down.attempts == 1
    assert starts == []
    assert b"synthetic storage failure" not in response.content


def test_invalid_correlation_is_replaced_and_supported_types_remain_valid(tmp_path, monkeypatch):
    audit = _audit(tmp_path)
    client = _client(tmp_path, audit)
    monkeypatch.setattr(
        orchestration,
        "start_workflow",
        lambda saver, ports, case_id, workflow_type: {
            "workflowId": orchestration.workflow_id_for(case_id, workflow_type),
            "status": "waiting_human",
        },
    )
    response = client.post(
        "/internal/workflows",
        headers={"X-Service-Token": TOKEN, "X-Correlation-ID": "not-a-canonical-uuid"},
        json={"caseId": CASE_ID, "workflowType": WORKFLOW_TYPE},
    )
    assert response.status_code == 200
    with audit._scope() as connection:
        generated = connection.execute("SELECT correlation_id FROM security_audit_events").fetchone()[0]
    assert generated != "not-a-canonical-uuid"
    assert len(generated) == 36 and generated[14] == "4"
    for workflow_type in ("post_consultation", "missed_follow_up", "cross_org_lab_result"):
        event = workflow_security_event(
            event_type="workflow_start",
            outcome="allowed",
            reason_code="access_granted",
            correlation_id=CORRELATION_ALLOWED,
            authenticated=True,
            workflow_type=workflow_type,
        )
        assert dict(event.metadata)["workflow_type"] == workflow_type


def test_execution_failure_remains_an_allowed_access_decision(tmp_path, monkeypatch):
    audit = _audit(tmp_path)
    client = _client(tmp_path, audit)
    workflow_id = orchestration.workflow_id_for(CASE_ID, WORKFLOW_TYPE)

    def failed_workflow(*args):
        del args
        return {"workflowId": workflow_id, "status": "failed", "errorCode": "clinical_read_failed"}

    monkeypatch.setattr(
        orchestration,
        "start_workflow",
        failed_workflow,
    )
    response = client.post(
        "/internal/workflows",
        headers={"X-Service-Token": TOKEN, "X-Correlation-ID": CORRELATION_ALLOWED},
        json={"caseId": CASE_ID, "workflowType": WORKFLOW_TYPE},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    events = audit.list_by_correlation(CORRELATION_ALLOWED)
    assert len(events) == 1
    assert (events[0].outcome, events[0].reason_code) == ("allowed", "access_granted")


def test_missing_workflow_is_not_an_authorization_denial(tmp_path):
    audit = _audit(tmp_path)
    client = _client(tmp_path, audit, review_repository=ReviewRepository())
    workflow_id = orchestration.workflow_id_for(CASE_ID, WORKFLOW_TYPE)
    response = client.post(
        f"/internal/workflows/{workflow_id}/resume",
        headers={"X-Service-Token": TOKEN, "X-Correlation-ID": CORRELATION_ALLOWED},
        json={"reviewCaseId": REVIEW_ID, "decision": DECISION},
    )
    assert response.status_code == 404
    assert audit.list_by_correlation(CORRELATION_ALLOWED) == ()


def test_resume_audits_access_decisions_without_repeating_action(tmp_path, monkeypatch):
    audit = _audit(tmp_path)
    review_repository = ReviewRepository()
    client = _client(tmp_path, audit, review_repository=review_repository)
    workflow_id = orchestration.workflow_id_for(CASE_ID, WORKFLOW_TYPE)
    saver = FakeSaver(
        {"workflowId": workflow_id, "workflowType": WORKFLOW_TYPE, "status": "waiting_human"}
    )
    app.state.agent_workflow_saver = saver
    actions = []

    def fake_resume(saver_arg, ports, requested_id, decision, **kwargs):
        del ports
        if saver_arg.record["status"] != "waiting_human":
            raise orchestration.WorkflowNotSuspended
        if decision != kwargs["stored_outcome"]:
            raise orchestration.WorkflowDecisionRejected
        kwargs["before_resume"]()
        actions.append(requested_id)
        saver_arg.record["status"] = "completed"
        return dict(saver_arg.record)

    monkeypatch.setattr(orchestration, "resume_workflow", fake_resume)
    allowed = client.post(
        f"/internal/workflows/{workflow_id}/resume",
        headers={"X-Service-Token": TOKEN, "X-Correlation-ID": CORRELATION_ALLOWED},
        json={"reviewCaseId": REVIEW_ID, "decision": DECISION},
    )
    repeated = client.post(
        f"/internal/workflows/{workflow_id}/resume",
        headers={"X-Service-Token": TOKEN, "X-Correlation-ID": CORRELATION_RETRY},
        json={"reviewCaseId": REVIEW_ID, "decision": DECISION},
    )
    assert (allowed.status_code, repeated.status_code) == (200, 409)
    assert actions == [workflow_id]
    allowed_event = audit.list_by_correlation(CORRELATION_ALLOWED)[0]
    assert (allowed_event.event_type, allowed_event.outcome, allowed_event.reason_code) == (
        "workflow_resume",
        "allowed",
        "access_granted",
    )
    assert audit.list_by_correlation(CORRELATION_RETRY) == ()

    saver.record["status"] = "waiting_human"
    rejected = client.post(
        f"/internal/workflows/{workflow_id}/resume",
        headers={"X-Service-Token": TOKEN, "X-Correlation-ID": CORRELATION_INVALID},
        json={
            "reviewCaseId": REVIEW_ID,
            "decision": ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED.value,
        },
    )
    assert rejected.status_code == 403
    assert actions == [workflow_id]
    assert audit.list_by_correlation(CORRELATION_INVALID)[0].reason_code == "human_review_decision_rejected"


def test_resume_audit_failure_preserves_checkpoint_and_retry_executes_once(tmp_path, monkeypatch):
    down = DownAudit()
    review_repository = ReviewRepository()
    client = _client(tmp_path, down, review_repository=review_repository)
    workflow_id = orchestration.workflow_id_for(CASE_ID, WORKFLOW_TYPE)
    saver = FakeSaver(
        {"workflowId": workflow_id, "workflowType": WORKFLOW_TYPE, "status": "waiting_human"}
    )
    app.state.agent_workflow_saver = saver
    actions = []

    def fake_resume(saver_arg, ports, requested_id, decision, **kwargs):
        del ports, decision
        kwargs["before_resume"]()
        actions.append(requested_id)
        saver_arg.record["status"] = "completed"
        return dict(saver_arg.record)

    monkeypatch.setattr(orchestration, "resume_workflow", fake_resume)
    request_body = {"reviewCaseId": REVIEW_ID, "decision": DECISION}
    failed = client.post(
        f"/internal/workflows/{workflow_id}/resume",
        headers={"X-Service-Token": TOKEN, "X-Correlation-ID": CORRELATION_ALLOWED},
        json=request_body,
    )
    assert failed.status_code == 503
    assert saver.record["status"] == "waiting_human"
    assert actions == []

    audit = _audit(tmp_path)
    app.state.security_audit_repository = audit
    retried = client.post(
        f"/internal/workflows/{workflow_id}/resume",
        headers={"X-Service-Token": TOKEN, "X-Correlation-ID": CORRELATION_RETRY},
        json=request_body,
    )
    assert retried.status_code == 200
    assert saver.record["status"] == "completed"
    assert actions == [workflow_id]
    assert audit.list_by_correlation(CORRELATION_RETRY)[0].outcome == "allowed"
