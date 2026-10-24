"""Human Review security audit without HAPI, Gemini, or external services."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.clinical_review_context import ClinicalContextUnavailable
from app.config import Settings
from app.followup_review import (
    FollowUpReviewCaseService,
    ReviewCaseStatus,
    ReviewOutcome,
)
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.human_attribution import DEVELOPMENT_AUTHENTICATOR_V1, DevelopmentPrincipalSnapshot
from app.human_development_auth import SESSION_COOKIE
from app.human_review_client import issue_form_token
from app.human_session import HumanSessionService
from app.human_session_sqlite import SQLiteHumanSessionRepository
from app.main import app, get_settings
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)
from app.security_audit import (
    SecurityAuditEvent,
    SecurityAuditRejected,
    SecurityAuditUnavailable,
    authentication_event,
    human_review_decision_event,
    validate_security_audit_event,
)
from app.security_audit_sqlite import SQLiteSecurityAuditRepository


DEV_SECRET = "development-secret-value-32chars-min"
SERVICE_TOKEN = "synthetic-service-token-a"
SIGNING_SECRET = "synthetic-form-signing-secret-b"
ORIGIN = "http://127.0.0.1"
FORM_HEADERS = {
    "origin": ORIGIN,
    "content-type": "application/x-www-form-urlencoded",
}
NOW = datetime(2026, 10, 23, 18, 0, tzinfo=timezone.utc)


class Clock:
    def __call__(self) -> datetime:
        return NOW


class DownAudit:
    def __init__(self) -> None:
        self.attempts = 0

    def append(self, event: SecurityAuditEvent) -> SecurityAuditEvent:
        del event
        self.attempts += 1
        raise SecurityAuditUnavailable("synthetic audit write failure")


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token=SERVICE_TOKEN,
        human_review_form_signing_secret=SIGNING_SECRET,
        host="127.0.0.1",
        port=8090,
        followup_agent_enabled=True,
        ai_review_db_path=str(tmp_path / "review.sqlite3"),
        institutional_knowledge_db_path=str(tmp_path / "knowledge.sqlite3"),
        human_session_db_path=str(tmp_path / "human-session.sqlite3"),
        human_review_development_auth_enabled=True,
        human_review_development_auth_secret=DEV_SECRET,
        human_review_development_principal_id="lab-reviewer",
        human_review_development_principal_display_name="Lab reviewer",
        security_audit_db_path=str(tmp_path / "security-audit.sqlite3"),
    )


@pytest.fixture(autouse=True)
def _clean_app_state():
    names = (
        "followup_review_repository",
        "clinical_context_fhir_client",
        "human_session_repository",
        "human_session_clock",
        "security_audit_repository",
        "security_audit_clock",
        "agent_workflow_saver",
        "agent_workflow_ports",
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


def _review_repository(tmp_path: Path) -> SQLiteFollowUpReviewCaseRepository:
    repository = SQLiteFollowUpReviewCaseRepository(
        tmp_path / "review.sqlite3", clock=Clock()
    )
    repository.initialize()
    return repository


def _audit_repository(tmp_path: Path) -> SQLiteSecurityAuditRepository:
    repository = SQLiteSecurityAuditRepository(tmp_path / "security-audit.sqlite3")
    repository.initialize()
    return repository


def _create_case(
    repository: SQLiteFollowUpReviewCaseRepository,
    *,
    case_id: str = "SYN-AUDIT-REVIEW-001",
    suffix: str = "001",
):
    created = FollowUpReviewCaseService(repository).ensure_for_protocol(
        case_id,
        ProtocolReviewResult(
            id=POST_CONSULTATION_RESULT_REVIEW_V1,
            evaluation_status=ProtocolEvaluationStatus.MATCHED,
            reason_codes=("post_consultation_result_requires_review",),
            matched_resources=(
                f"Encounter/synthetic-secret-encounter-{suffix}",
                f"Observation/synthetic-secret-observation-{suffix}",
            ),
            human_review_status="required",
            human_review_reason="deterministic_post_consultation_protocol_match",
            action_status="proposed",
            action_type="review_follow_up_case",
        ),
    )
    assert created is not None
    return created


def _unavailable_fhir():
    raise ClinicalContextUnavailable("synthetic context unavailable")


def _client(
    tmp_path: Path,
    review: SQLiteFollowUpReviewCaseRepository,
    audit: object,
) -> TestClient:
    settings = _settings(tmp_path)
    sessions = SQLiteHumanSessionRepository(tmp_path / "human-session.sqlite3")
    sessions.initialize()
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.followup_review_repository = review
    app.state.clinical_context_fhir_client = _unavailable_fhir
    app.state.human_session_repository = sessions
    app.state.human_session_clock = Clock()
    app.state.security_audit_clock = Clock()
    app.state.security_audit_repository = audit
    return TestClient(app, base_url=ORIGIN)


def _login(client: TestClient) -> None:
    response = client.post(
        "/review-login",
        content=urlencode({"developmentSecret": DEV_SECRET}),
        headers=FORM_HEADERS,
        follow_redirects=False,
    )
    assert response.status_code == 303


def _session_id(client: TestClient) -> str:
    token = client.cookies.get(SESSION_COOKIE)
    assert token
    return HumanSessionService(
        app.state.human_session_repository, clock=Clock()
    ).resolve(token).session_id


def _hidden(html: str, name: str) -> str:
    marker = f'name="{name}" value="'
    start = html.index(marker) + len(marker)
    return html[start : html.index('"', start)]


def _page_payload(client: TestClient, review_case_id: str, outcome: str) -> dict[str, str]:
    page = client.get(f"/review-cases/{review_case_id}")
    assert page.status_code == 200
    return {
        "outcome": outcome,
        "expectedVersion": _hidden(page.text, "expectedVersion"),
        "formToken": _hidden(page.text, "formToken"),
        "formExpiry": _hidden(page.text, "formExpiry"),
    }


def _signed_payload(
    client: TestClient,
    review_case_id: str,
    *,
    version: int,
    outcome: str,
) -> dict[str, str]:
    issued = issue_form_token(
        secret=SIGNING_SECRET,
        review_case_id=review_case_id,
        expected_version=version,
        session_id=_session_id(client),
    )
    assert issued is not None
    token, expiry = issued
    return {
        "outcome": outcome,
        "expectedVersion": str(version),
        "formToken": token,
        "formExpiry": str(expiry),
    }


def _post_close(
    client: TestClient,
    review_case_id: str,
    payload: dict[str, str],
    correlation_id: str,
    *,
    origin: str | None = ORIGIN,
):
    headers = {"content-type": "application/x-www-form-urlencoded", "X-Correlation-ID": correlation_id}
    if origin is not None:
        headers["origin"] = origin
    return client.post(
        f"/review-cases/{review_case_id}/close",
        content=urlencode(payload),
        headers=headers,
        follow_redirects=False,
    )


def _correlation() -> str:
    return str(uuid.uuid4())


def _human_events(audit: SQLiteSecurityAuditRepository, correlation_id: str):
    return tuple(
        event
        for event in audit.list_by_correlation(correlation_id)
        if event.event_type == "human_review_decision"
    )


def test_authorized_close_is_audited_and_attributed_to_the_resolved_principal(tmp_path):
    review = _review_repository(tmp_path)
    case = _create_case(review)
    audit = _audit_repository(tmp_path)
    client = _client(tmp_path, review, audit)
    _login(client)
    session_id = _session_id(client)
    correlation_id = _correlation()

    response = _post_close(
        client,
        case.id,
        _page_payload(client, case.id, "follow_up_coordination_planned"),
        correlation_id,
    )

    assert response.status_code == 303
    stored = review.get(case.id)
    assert stored is not None and stored.status is ReviewCaseStatus.CLOSED and stored.version == 2
    attributions = review.list_human_attributions(case.id)
    assert len(attributions) == 1
    assert attributions[0].principal_id == "lab-reviewer"
    with sqlite3.connect(review.database_path) as connection:
        stored_session_id = connection.execute(
            "SELECT session_id FROM follow_up_human_attributions WHERE review_case_id = ?",
            (case.id,),
        ).fetchone()[0]
    assert stored_session_id == session_id
    event = _human_events(audit, correlation_id)[0]
    assert (
        event.actor_type,
        event.actor_id,
        event.action,
        event.outcome,
        event.reason_code,
    ) == (
        "development_principal",
        "lab-reviewer",
        "close_review_case",
        "allowed",
        "access_granted",
    )
    assert event.organization_id is None
    assert event.resource_reference == f"review-case/{case.id}"
    assert dict(event.metadata) == {
        "case_version": "1",
        "human_decision": "follow_up_coordination_planned",
        "route": "/review-cases/:reviewCaseId/close",
    }


def test_missing_and_invalid_sessions_are_distinct_denials_without_a_case_write(tmp_path):
    review = _review_repository(tmp_path)
    case = _create_case(review)
    audit = _audit_repository(tmp_path)
    client = _client(tmp_path, review, audit)
    missing_id = _correlation()
    invalid_id = _correlation()

    missing = _post_close(client, case.id, {}, missing_id)
    client.cookies.set(SESSION_COOKIE, "invalid-session-cookie")
    invalid = _post_close(client, case.id, {}, invalid_id)

    assert (missing.status_code, invalid.status_code) == (303, 303)
    assert _human_events(audit, missing_id)[0].reason_code == "human_session_missing"
    assert _human_events(audit, invalid_id)[0].reason_code == "human_session_invalid"
    for event in (*_human_events(audit, missing_id), *_human_events(audit, invalid_id)):
        assert event.actor_type == event.actor_id == "anonymous"
        assert event.resource_reference is None
    assert review.get(case.id).status is ReviewCaseStatus.OPEN
    assert review.list_human_attributions(case.id) == ()


def test_origin_and_form_signature_rejections_are_authenticated_security_denials(tmp_path):
    review = _review_repository(tmp_path)
    case = _create_case(review)
    audit = _audit_repository(tmp_path)
    client = _client(tmp_path, review, audit)
    _login(client)
    payload = _page_payload(client, case.id, "review_completed_no_operational_action")
    origin_id = _correlation()
    signature_id = _correlation()

    wrong_origin = _post_close(client, case.id, payload, origin_id, origin="http://evil.test")
    forged = _post_close(
        client,
        case.id,
        {**payload, "formToken": "ab" * 32},
        signature_id,
    )

    assert (wrong_origin.status_code, forged.status_code) == (400, 400)
    assert _human_events(audit, origin_id)[0].reason_code == "same_origin_rejected"
    assert _human_events(audit, signature_id)[0].reason_code == "form_signature_rejected"
    for event in (*_human_events(audit, origin_id), *_human_events(audit, signature_id)):
        assert (event.actor_type, event.actor_id) == (
            "development_principal",
            "lab-reviewer",
        )
        assert event.resource_reference == f"review-case/{case.id}"
        assert dict(event.metadata) == {"route": "/review-cases/:reviewCaseId/close"}
    assert review.get(case.id).status is ReviewCaseStatus.OPEN


def test_business_and_request_errors_are_not_mislabeled_as_security_denials(tmp_path):
    review = _review_repository(tmp_path)
    audit = _audit_repository(tmp_path)
    client = _client(tmp_path, review, audit)
    _login(client)
    outcome = "review_completed_no_operational_action"

    missing_case_id = "00000000-0000-4000-8000-000000000000"
    missing_correlation = _correlation()
    missing = _post_close(
        client,
        missing_case_id,
        _signed_payload(client, missing_case_id, version=1, outcome=outcome),
        missing_correlation,
    )

    closed_case = _create_case(review, case_id="SYN-AUDIT-REVIEW-002", suffix="002")
    first_id = _correlation()
    first = _post_close(
        client,
        closed_case.id,
        _page_payload(client, closed_case.id, outcome),
        first_id,
    )
    repeated_id = _correlation()
    repeated = _post_close(
        client,
        closed_case.id,
        _signed_payload(client, closed_case.id, version=2, outcome=outcome),
        repeated_id,
    )

    stale_case = _create_case(review, case_id="SYN-AUDIT-REVIEW-003", suffix="003")
    stale_id = _correlation()
    stale = _post_close(
        client,
        stale_case.id,
        _signed_payload(client, stale_case.id, version=2, outcome=outcome),
        stale_id,
    )
    invalid_id = _correlation()
    invalid_payload = _page_payload(client, stale_case.id, outcome)
    invalid_payload["outcome"] = "diagnosis_not_allowed"
    invalid = _post_close(client, stale_case.id, invalid_payload, invalid_id)

    assert (missing.status_code, first.status_code, repeated.status_code, stale.status_code) == (
        404,
        303,
        303,
        303,
    )
    assert invalid.status_code == 400
    assert len(_human_events(audit, first_id)) == 1
    for correlation_id in (missing_correlation, repeated_id, stale_id, invalid_id):
        assert _human_events(audit, correlation_id) == ()
    assert review.get(stale_case.id).status is ReviewCaseStatus.OPEN


def test_audit_failure_rolls_back_close_then_retry_closes_and_resumes_once(
    tmp_path, monkeypatch
):
    review = _review_repository(tmp_path)
    case = _create_case(review)
    audit = _audit_repository(tmp_path)
    down = DownAudit()
    client = _client(tmp_path, review, audit)
    _login(client)
    payload = _page_payload(client, case.id, "follow_up_coordination_planned")
    workflow = {"status": "waiting_human", "executions": 0}

    def resume_once(settings, repository, review_case_id, outcome):
        del settings, repository, review_case_id, outcome
        if workflow["status"] != "waiting_human":
            return None
        workflow["status"] = "completed"
        workflow["executions"] += 1
        return dict(workflow)

    monkeypatch.setattr("app.followup_service.resume_after_human_decision", resume_once)
    app.state.security_audit_repository = down
    failed_id = _correlation()
    failed = _post_close(client, case.id, payload, failed_id)

    assert failed.status_code == 503
    assert down.attempts == 1
    assert review.get(case.id).status is ReviewCaseStatus.OPEN
    assert [event.event_type.value for event in review.events(case.id)] == ["created"]
    assert review.list_human_attributions(case.id) == ()
    assert workflow == {"status": "waiting_human", "executions": 0}

    app.state.security_audit_repository = audit
    retry_id = _correlation()
    retried = _post_close(client, case.id, payload, retry_id)
    repeat_id = _correlation()
    repeated = _post_close(
        client,
        case.id,
        _signed_payload(
            client,
            case.id,
            version=2,
            outcome="follow_up_coordination_planned",
        ),
        repeat_id,
    )

    assert (retried.status_code, repeated.status_code) == (303, 303)
    assert workflow == {"status": "completed", "executions": 1}
    assert len(_human_events(audit, retry_id)) == 1
    assert _human_events(audit, repeat_id) == ()
    assert [event.event_type.value for event in review.events(case.id)].count("closed") == 1
    assert len(review.list_human_attributions(case.id)) == 1


def test_allowed_audit_can_remain_when_a_later_review_write_rolls_back(
    tmp_path, monkeypatch
):
    import app.followup_review_sqlite as review_sqlite

    review = _review_repository(tmp_path)
    case = _create_case(review)
    audit = _audit_repository(tmp_path)
    client = _client(tmp_path, review, audit)
    _login(client)
    payload = _page_payload(client, case.id, "follow_up_coordination_planned")
    correlation_id = _correlation()

    def fail_attribution(*args, **kwargs):
        del args, kwargs
        raise sqlite3.IntegrityError("synthetic post-audit review failure")

    monkeypatch.setattr(review_sqlite, "_insert_human_attribution", fail_attribution)
    response = _post_close(client, case.id, payload, correlation_id)

    assert response.status_code == 503
    assert review.get(case.id).status is ReviewCaseStatus.OPEN
    assert [event.event_type.value for event in review.events(case.id)] == ["created"]
    assert review.list_human_attributions(case.id) == ()
    event = _human_events(audit, correlation_id)[0]
    assert (event.outcome, event.reason_code) == ("allowed", "access_granted")


def test_audit_contains_no_secrets_session_material_or_clinical_identifiers(tmp_path):
    review = _review_repository(tmp_path)
    case = _create_case(review)
    audit = _audit_repository(tmp_path)
    client = _client(tmp_path, review, audit)
    _login(client)
    raw_cookie = client.cookies.get(SESSION_COOKIE)
    assert raw_cookie
    payload = _page_payload(client, case.id, "follow_up_coordination_planned")
    correlation_id = _correlation()
    response = _post_close(client, case.id, payload, correlation_id)
    assert response.status_code == 303

    raw = b"".join(
        path.read_bytes()
        for path in tmp_path.glob("security-audit.sqlite3*")
        if path.is_file()
    )
    for forbidden in (
        DEV_SECRET,
        SERVICE_TOKEN,
        SIGNING_SECRET,
        raw_cookie,
        case.case_id,
        "synthetic-secret-encounter-001",
        "synthetic-secret-observation-001",
        "Patient",
        "Bundle",
    ):
        assert forbidden.encode() not in raw

    event = _human_events(audit, correlation_id)[0]
    with pytest.raises(SecurityAuditRejected):
        validate_security_audit_event(
            replace(event, metadata=event.metadata + (("clinical_note", "Patient/secret"),))
        )


def test_concurrent_same_version_closes_append_one_audit_and_one_transition(tmp_path):
    review = _review_repository(tmp_path)
    case = _create_case(review)
    audit = _audit_repository(tmp_path)
    service = FollowUpReviewCaseService(review)
    snapshot = DevelopmentPrincipalSnapshot(
        principal_id="lab-reviewer",
        authenticator_id=DEVELOPMENT_AUTHENTICATOR_V1,
        session_id="11111111-1111-4111-8111-111111111111",
    )
    start = threading.Barrier(2)
    correlations = (_correlation(), _correlation())

    def close(correlation_id: str):
        start.wait()

        def audit_allowed() -> None:
            audit.append(
                human_review_decision_event(
                    outcome="allowed",
                    reason_code="access_granted",
                    correlation_id=correlation_id,
                    actor_id=snapshot.principal_id,
                    review_case_id=case.id,
                    human_decision="follow_up_coordination_planned",
                    case_version=1,
                    clock=Clock(),
                )
            )

        return service.close(
            case.id,
            expected_version=1,
            outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
            attribution=snapshot,
            before_close=audit_allowed,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(close, correlations))

    assert [result.status for result in results] == [ReviewCaseStatus.CLOSED] * 2
    assert sum(len(_human_events(audit, item)) for item in correlations) == 1
    assert [event.event_type.value for event in review.events(case.id)].count("closed") == 1
    assert len(review.list_human_attributions(case.id)) == 1


def test_human_review_event_does_not_claim_workflow_execution():
    event = human_review_decision_event(
        outcome="allowed",
        reason_code="access_granted",
        correlation_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        actor_id="lab-reviewer",
        review_case_id="11111111-1111-4111-8111-111111111111",
        human_decision="review_completed_no_operational_action",
        case_version=1,
        clock=Clock(),
    )
    assert event.outcome == "allowed"
    assert event.action == "close_review_case"
    assert "workflow" not in dict(event.metadata)
    assert "completed" not in dict(event.metadata).values()

    with pytest.raises(SecurityAuditRejected):
        human_review_decision_event(
            outcome="denied",
            reason_code="human_session_missing",
            correlation_id=event.correlation_id,
            human_decision="review_completed_no_operational_action",
            case_version=1,
        )


def test_event_specific_allowlists_reject_cross_event_fields_at_persistence(tmp_path):
    audit = _audit_repository(tmp_path)
    human = human_review_decision_event(
        outcome="allowed",
        reason_code="access_granted",
        correlation_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        actor_id="lab-reviewer",
        review_case_id="11111111-1111-4111-8111-111111111111",
        human_decision="review_completed_no_operational_action",
        case_version=1,
        clock=Clock(),
    )
    login = authentication_event(
        outcome="allowed",
        actor_id="lab-reviewer",
        actor_type="development_principal",
        reason_code="credential_accepted",
        clock=Clock(),
    )
    invalid_events = (
        replace(human, reason_code="credential_accepted"),
        replace(human, action="resume_workflow"),
        replace(
            human,
            metadata=human.metadata + (("workflow_type", "post_consultation"),),
        ),
        replace(human, organization_id="synthetic-organization"),
        replace(login, reason_code="form_signature_rejected"),
    )
    for event in invalid_events:
        with pytest.raises(SecurityAuditRejected):
            audit.append(event)

    with audit._scope() as connection:
        assert connection.execute("SELECT COUNT(*) FROM security_audit_events").fetchone()[0] == 0


def test_internal_service_close_does_not_fabricate_a_human_audit_actor(tmp_path):
    review = _review_repository(tmp_path)
    case = _create_case(review)
    audit = _audit_repository(tmp_path)
    client = _client(tmp_path, review, audit)
    response = client.post(
        f"/internal/follow-up-review-cases/{case.id}/close",
        json={"expectedVersion": 1, "outcome": "review_completed_no_operational_action"},
        headers={"X-Service-Token": SERVICE_TOKEN},
    )
    assert response.status_code == 200
    with sqlite3.connect(tmp_path / "security-audit.sqlite3") as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM security_audit_events WHERE event_type = 'human_review_decision'"
        ).fetchone()[0]
    assert count == 0
    assert review.list_human_attributions(case.id) == ()
