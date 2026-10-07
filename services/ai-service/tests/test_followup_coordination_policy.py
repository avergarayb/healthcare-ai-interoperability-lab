from __future__ import annotations

import inspect
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.followup_coordination_action import (
    FOLLOW_UP_COORDINATION_ACTION_POLICY_V1,
    CoordinationActionDenied,
    CoordinationActionType,
    CoordinationPolicyDecision,
    CoordinationPolicyDenyReason,
    FollowUpCoordinationActionService,
    evaluate_follow_up_coordination_action_policy,
)
from app.followup_review import (
    FollowUpReviewCase,
    FollowUpReviewCaseService,
    ReviewCaseNotFound,
    ReviewCaseStatus,
    ReviewOutcome,
)
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)


ACTION = CoordinationActionType.CREATE_FOLLOW_UP_COORDINATION_REQUEST.value
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 9, 30, 13, 0, tzinfo=timezone.utc)
APP = Path(__file__).resolve().parents[1] / "app"


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


def _repository(tmp_path, *, clock=lambda: NOW) -> SQLiteFollowUpReviewCaseRepository:
    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3", clock=clock)
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


def _policy_case(
    *,
    status: ReviewCaseStatus,
    outcome: ReviewOutcome | None,
    protocol_id: str,
) -> FollowUpReviewCase:
    closed = status is ReviewCaseStatus.CLOSED
    return FollowUpReviewCase(
        id="10000000-0000-4000-8000-000000000031",
        review_identity="ab" * 32,
        case_id="SYN-FOLLOWUP-011",
        protocol_id=protocol_id,
        protocol_evaluation_status="matched",
        reason_codes=("post_consultation_result_requires_review",),
        matched_resources=("Encounter/encounter-011",),
        status=status,
        outcome=outcome,
        version=2 if closed else 1,
        created_at="2026-09-30T12:00:00.000000Z",
        updated_at="2026-09-30T12:00:00.000000Z",
        closed_at="2026-09-30T12:00:00.000000Z" if closed else None,
    )


def _evaluate(case: FollowUpReviewCase, action_type: str = ACTION):
    return evaluate_follow_up_coordination_action_policy(case, action_type=action_type)


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


class _EnsureCounter:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.ensure_calls = 0

    def get(self, review_case_id: str):
        return self.inner.get(review_case_id)

    def ensure_follow_up_coordination_request(self, review_case_id: str):
        self.ensure_calls += 1
        return self.inner.ensure_follow_up_coordination_request(review_case_id)


def test_policy_allows_both_supported_protocols():
    for protocol_id in (POST_CONSULTATION_RESULT_REVIEW_V1, MISSED_FOLLOW_UP_REVIEW_V1):
        result = _evaluate(
            _policy_case(
                status=ReviewCaseStatus.CLOSED,
                outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
                protocol_id=protocol_id,
            )
        )
        assert result.policy_id == FOLLOW_UP_COORDINATION_ACTION_POLICY_V1
        assert result.decision is CoordinationPolicyDecision.ALLOW
        assert result.reason is None


def test_policy_denies_open_case_even_when_outcome_is_supplied():
    result = _evaluate(
        _policy_case(
            status=ReviewCaseStatus.OPEN,
            outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
            protocol_id=POST_CONSULTATION_RESULT_REVIEW_V1,
        )
    )
    assert result.decision is CoordinationPolicyDecision.DENY
    assert result.reason is CoordinationPolicyDenyReason.CASE_NOT_CLOSED


def test_policy_denies_closed_case_without_operational_action():
    result = _evaluate(
        _policy_case(
            status=ReviewCaseStatus.CLOSED,
            outcome=ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION,
            protocol_id=MISSED_FOLLOW_UP_REVIEW_V1,
        )
    )
    assert result.decision is CoordinationPolicyDecision.DENY
    assert result.reason is CoordinationPolicyDenyReason.OUTCOME_NOT_AUTHORIZED


def test_policy_denies_unsupported_protocol():
    result = _evaluate(
        _policy_case(
            status=ReviewCaseStatus.CLOSED,
            outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
            protocol_id="OTHER_PROTOCOL",
        )
    )
    assert result.decision is CoordinationPolicyDecision.DENY
    assert result.reason is CoordinationPolicyDenyReason.PROTOCOL_NOT_SUPPORTED


def test_policy_denies_unsupported_action():
    result = _evaluate(
        _policy_case(
            status=ReviewCaseStatus.CLOSED,
            outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
            protocol_id=POST_CONSULTATION_RESULT_REVIEW_V1,
        ),
        action_type="send_whatsapp",
    )
    assert result.decision is CoordinationPolicyDecision.DENY
    assert result.reason is CoordinationPolicyDenyReason.ACTION_NOT_SUPPORTED


def test_service_signature_accepts_only_the_review_case_id():
    parameters = inspect.signature(
        FollowUpCoordinationActionService.ensure_follow_up_coordination_request
    ).parameters
    assert list(parameters) == ["self", "review_case_id"]


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
def test_authorized_service_creates_one_request(tmp_path, case_id, protocol):
    repository = _repository(tmp_path)
    closed = _close(repository, _create(repository, case_id=case_id, protocol=protocol))
    counter = _EnsureCounter(repository)
    service = FollowUpCoordinationActionService(counter)
    before = _snapshot(repository.database_path, closed.id)
    stored = service.ensure_follow_up_coordination_request(closed.id)
    assert counter.ensure_calls == 1
    assert stored.review_case_id == closed.id
    assert stored.protocol_id == closed.protocol_id
    assert stored.action_type is CoordinationActionType.CREATE_FOLLOW_UP_COORDINATION_REQUEST
    assert repository.get(closed.id) == closed
    assert _snapshot(repository.database_path, closed.id) == before
    assert len(repository.events(closed.id)) == 2
    assert _count_requests(repository.database_path) == 1


def test_repeated_authorized_service_call_reuses_the_request(tmp_path):
    current = {"value": NOW}

    def clock():
        return current["value"]

    repository = _repository(tmp_path, clock=clock)
    closed = _close(repository, _create(repository, case_id="SYN-FOLLOWUP-013"))
    service = FollowUpCoordinationActionService(repository)
    first = service.ensure_follow_up_coordination_request(closed.id)
    current["value"] = LATER
    second = service.ensure_follow_up_coordination_request(closed.id)
    assert first == second
    assert first.created_at == "2026-09-30T12:00:00.000000Z"
    assert _count_requests(repository.database_path) == 1


def test_unknown_review_case_fails_without_insert(tmp_path):
    repository = _repository(tmp_path)
    counter = _EnsureCounter(repository)
    service = FollowUpCoordinationActionService(counter)
    missing = "10000000-0000-4000-8000-000000000099"
    with pytest.raises(ReviewCaseNotFound):
        service.ensure_follow_up_coordination_request(missing)
    assert counter.ensure_calls == 0
    assert _count_requests(repository.database_path) == 0


def test_open_case_is_denied_without_insert(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository, case_id="SYN-FOLLOWUP-014")
    counter = _EnsureCounter(repository)
    service = FollowUpCoordinationActionService(counter)
    before = _snapshot(repository.database_path, created.id)
    events = repository.events(created.id)
    with pytest.raises(CoordinationActionDenied) as caught:
        service.ensure_follow_up_coordination_request(created.id)
    assert caught.value.result.reason is CoordinationPolicyDenyReason.CASE_NOT_CLOSED
    assert counter.ensure_calls == 0
    assert repository.get(created.id) == created
    assert repository.events(created.id) == events
    assert _snapshot(repository.database_path, created.id) == before
    assert _count_requests(repository.database_path) == 0


def test_no_operational_action_is_denied_without_insert(tmp_path):
    repository = _repository(tmp_path)
    closed = _close(
        repository,
        _create(repository, case_id="SYN-FOLLOWUP-015"),
        ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION,
    )
    counter = _EnsureCounter(repository)
    service = FollowUpCoordinationActionService(counter)
    before = _snapshot(repository.database_path, closed.id)
    events = repository.events(closed.id)
    with pytest.raises(CoordinationActionDenied) as caught:
        service.ensure_follow_up_coordination_request(closed.id)
    assert caught.value.result.reason is CoordinationPolicyDenyReason.OUTCOME_NOT_AUTHORIZED
    assert counter.ensure_calls == 0
    assert repository.get(closed.id) == closed
    assert repository.events(closed.id) == events
    assert _snapshot(repository.database_path, closed.id) == before
    assert _count_requests(repository.database_path) == 0


def test_unsupported_protocol_is_denied_before_persistence(tmp_path):
    repository = _repository(tmp_path)
    closed = _close(
        repository,
        _create(
            repository,
            case_id="SYN-FOLLOWUP-003",
            protocol=_protocol(protocol_id="OTHER_PROTOCOL"),
        ),
    )
    counter = _EnsureCounter(repository)
    service = FollowUpCoordinationActionService(counter)
    with pytest.raises(CoordinationActionDenied) as caught:
        service.ensure_follow_up_coordination_request(closed.id)
    assert caught.value.result.reason is CoordinationPolicyDenyReason.PROTOCOL_NOT_SUPPORTED
    assert counter.ensure_calls == 0
    assert _count_requests(repository.database_path) == 0


def test_repository_still_persists_an_open_case_when_called_directly(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository, case_id="SYN-FOLLOWUP-004")
    service = FollowUpCoordinationActionService(repository)
    with pytest.raises(CoordinationActionDenied):
        service.ensure_follow_up_coordination_request(created.id)
    stored = repository.ensure_follow_up_coordination_request(created.id)
    assert stored.review_case_id == created.id
    assert repository.get(created.id).status is ReviewCaseStatus.OPEN
    assert _count_requests(repository.database_path) == 1


def test_concurrent_authorized_service_calls_create_one_request(tmp_path):
    repository = _repository(tmp_path)
    closed = _close(repository, _create(repository, case_id="SYN-FOLLOWUP-005"))
    service = FollowUpCoordinationActionService(repository)
    workers = 8
    barrier = threading.Barrier(workers)

    def create():
        barrier.wait(timeout=10)
        return service.ensure_follow_up_coordination_request(closed.id)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(lambda _index: create(), range(workers)))
    assert len({result.id for result in results}) == 1
    assert len({result.action_identity for result in results}) == 1
    assert len({result.created_at for result in results}) == 1
    assert _count_requests(repository.database_path) == 1
    assert repository.get(closed.id) == closed
    assert len(repository.events(closed.id)) == 2


def test_policy_service_has_no_external_authority_or_product_surface():
    source = (APP / "followup_coordination_action.py").read_text(encoding="utf-8").lower()
    for token in (
        "gemini",
        "ai_assisted_review",
        "institutional_knowledge",
        "langgraph",
        "toolnode",
        "hapi",
        "httpx",
        "mcp",
        "execute(",
        "approved_by",
        "reviewer_id",
        "clinician_id",
        "user_id",
        "import logging",
    ):
        assert token not in source
    assert "fastapi" not in source
    assert "human_review_client" not in source
    stored = json.dumps(sorted(reason.value for reason in CoordinationPolicyDenyReason))
    assert "patient" not in stored
