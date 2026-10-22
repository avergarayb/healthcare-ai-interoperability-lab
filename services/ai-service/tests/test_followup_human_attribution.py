from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from app.followup_coordination_action import (
    CoordinationActionDenied,
    FollowUpCoordinationActionService,
)
from app.followup_review import (
    FollowUpReviewCaseService,
    ReviewCaseStatus,
    ReviewOutcome,
    ReviewPersistenceUnavailable,
)
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.human_attribution import DEVELOPMENT_AUTHENTICATOR_V1, DevelopmentPrincipalSnapshot
from app.human_session import DEVELOPMENT_AUTHENTICATOR_V1 as SESSION_AUTHENTICATOR
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)


NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
SESSION_ID = "10000000-0000-4000-8000-0000000000c1"
OTHER_SESSION_ID = "10000000-0000-4000-8000-0000000000c2"


def _snapshot(session_id: str = SESSION_ID) -> DevelopmentPrincipalSnapshot:
    return DevelopmentPrincipalSnapshot("lab-reviewer", DEVELOPMENT_AUTHENTICATOR_V1, session_id)


def _repository(tmp_path) -> SQLiteFollowUpReviewCaseRepository:
    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3", clock=lambda: NOW)
    repository.initialize()
    return repository


def _open_case(repository, case_id: str = "SYN-FOLLOWUP-001"):
    created = FollowUpReviewCaseService(repository).ensure_for_protocol(
        case_id,
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


def _rows(path, sql: str):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return [tuple(row) for row in connection.execute(sql)]
    finally:
        connection.close()


def _reject_attribution_inserts(path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TRIGGER reject_human_attribution
            BEFORE INSERT ON follow_up_human_attributions
            BEGIN
                SELECT RAISE(ABORT, 'attribution rejected');
            END
            """
        )
        connection.commit()
    finally:
        connection.close()


def test_snapshot_is_a_synthetic_development_principal_without_secrets():
    assert DEVELOPMENT_AUTHENTICATOR_V1 == SESSION_AUTHENTICATOR
    snapshot = _snapshot()
    assert snapshot.principal_id == "lab-reviewer"
    assert snapshot.authenticator_id == DEVELOPMENT_AUTHENTICATOR_V1
    assert snapshot.session_id == SESSION_ID
    assert not hasattr(snapshot, "token")
    assert not hasattr(snapshot, "token_hash")
    assert not hasattr(snapshot, "display_name")
    with pytest.raises(ValueError):
        DevelopmentPrincipalSnapshot("Lab-Reviewer", DEVELOPMENT_AUTHENTICATOR_V1, SESSION_ID)
    with pytest.raises(ValueError):
        DevelopmentPrincipalSnapshot("lab-reviewer", "OIDC_AUTHENTICATOR_V1", SESSION_ID)
    with pytest.raises(ValueError):
        DevelopmentPrincipalSnapshot("lab-reviewer", DEVELOPMENT_AUTHENTICATOR_V1, SESSION_ID.upper())


def test_effective_close_stores_one_attribution_in_the_same_transaction(tmp_path):
    repository = _repository(tmp_path)
    created = _open_case(repository)
    closed = repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
        attribution=_snapshot(),
    )
    assert closed.status is ReviewCaseStatus.CLOSED
    assert closed.version == 2
    rows = _rows(
        repository.database_path,
        """
        SELECT operation, principal_id, authenticator_id, session_id, occurred_at, subject_version
        FROM follow_up_human_attributions
        """,
    )
    assert rows == [
        (
            "review_case_closed",
            "lab-reviewer",
            DEVELOPMENT_AUTHENTICATOR_V1,
            SESSION_ID,
            closed.closed_at,
            2,
        )
    ]
    events = _rows(
        repository.database_path,
        "SELECT event_type, occurred_at FROM follow_up_review_case_events ORDER BY case_version",
    )
    assert events == [("created", created.created_at), ("closed", closed.closed_at)]


def test_close_attribution_failure_rolls_back_the_case(tmp_path):
    repository = _repository(tmp_path)
    created = _open_case(repository)
    _reject_attribution_inserts(repository.database_path)
    with pytest.raises(ReviewPersistenceUnavailable):
        repository.close(
            created.id,
            expected_version=1,
            outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
            attribution=_snapshot(),
        )
    reopened = repository.get(created.id)
    assert reopened == created
    assert _rows(repository.database_path, "SELECT event_type FROM follow_up_review_case_events") == [
        ("created",)
    ]
    assert _rows(repository.database_path, "SELECT attribution_id FROM follow_up_human_attributions") == []


def test_repeated_close_does_not_add_or_backfill_attribution(tmp_path):
    repository = _repository(tmp_path)
    created = _open_case(repository)
    repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION,
    )
    repeated = repository.close(
        created.id,
        expected_version=2,
        outcome=ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION,
        attribution=_snapshot(),
    )
    assert repeated.status is ReviewCaseStatus.CLOSED
    assert _rows(repository.database_path, "SELECT operation FROM follow_up_human_attributions") == []
    assert (
        len(_rows(repository.database_path, "SELECT event_type FROM follow_up_review_case_events")) == 2
    )


def test_close_without_snapshot_keeps_the_internal_behavior(tmp_path):
    repository = _repository(tmp_path)
    created = _open_case(repository)
    closed = FollowUpReviewCaseService(repository).close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    assert closed.version == 2
    assert _rows(repository.database_path, "SELECT attribution_id FROM follow_up_human_attributions") == []


def test_first_coordination_request_stores_one_attribution(tmp_path):
    repository = _repository(tmp_path)
    created = _open_case(repository)
    repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    stored = FollowUpCoordinationActionService(repository).ensure_follow_up_coordination_request(
        created.id,
        attribution=_snapshot(OTHER_SESSION_ID),
    )
    assert repository.get(created.id).version == 2
    rows = _rows(
        repository.database_path,
        """
        SELECT operation, review_case_id, coordination_request_id, principal_id, session_id, occurred_at
        FROM follow_up_human_attributions
        """,
    )
    assert rows == [
        (
            "coordination_request_created",
            created.id,
            stored.id,
            "lab-reviewer",
            OTHER_SESSION_ID,
            stored.created_at,
        )
    ]


def test_coordination_attribution_failure_rolls_back_the_request(tmp_path):
    repository = _repository(tmp_path)
    created = _open_case(repository)
    repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    _reject_attribution_inserts(repository.database_path)
    with pytest.raises(ReviewPersistenceUnavailable):
        repository.ensure_follow_up_coordination_request(created.id, attribution=_snapshot())
    assert repository.get_follow_up_coordination_request(created.id) is None
    assert _rows(repository.database_path, "SELECT attribution_id FROM follow_up_human_attributions") == []


def test_repeated_coordination_does_not_duplicate_or_backfill(tmp_path):
    repository = _repository(tmp_path)
    created = _open_case(repository)
    repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    service = FollowUpCoordinationActionService(repository)
    first = service.ensure_follow_up_coordination_request(created.id)
    second = service.ensure_follow_up_coordination_request(created.id, attribution=_snapshot())
    assert second == first
    assert _rows(repository.database_path, "SELECT operation FROM follow_up_human_attributions") == []
    third = service.ensure_follow_up_coordination_request(created.id, attribution=_snapshot())
    assert third.id == first.id
    assert _rows(repository.database_path, "SELECT operation FROM follow_up_human_attributions") == []


def test_coordination_without_snapshot_stays_unattributed(tmp_path):
    repository = _repository(tmp_path)
    created = _open_case(repository)
    repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
        attribution=_snapshot(),
    )
    FollowUpCoordinationActionService(repository).ensure_follow_up_coordination_request(created.id)
    assert _rows(
        repository.database_path,
        "SELECT operation FROM follow_up_human_attributions ORDER BY operation",
    ) == [("review_case_closed",)]


def test_invalid_snapshot_writes_nothing(tmp_path):
    repository = _repository(tmp_path)
    created = _open_case(repository)
    rejected = _snapshot()
    object.__setattr__(rejected, "session_id", "not-a-canonical-uuid")
    with pytest.raises(ValueError):
        repository.close(
            created.id,
            expected_version=1,
            outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
            attribution=rejected,
        )
    assert repository.get(created.id) == created
    with pytest.raises(CoordinationActionDenied):
        FollowUpCoordinationActionService(repository).ensure_follow_up_coordination_request(
            created.id,
            attribution=_snapshot(),
        )
    assert repository.get_follow_up_coordination_request(created.id) is None
    assert _rows(repository.database_path, "SELECT attribution_id FROM follow_up_human_attributions") == []


def test_same_case_can_record_close_and_coordination_once_each(tmp_path):
    repository = _repository(tmp_path)
    created = _open_case(repository)
    repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
        attribution=_snapshot(),
    )
    repository.close(
        created.id,
        expected_version=2,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
        attribution=_snapshot(OTHER_SESSION_ID),
    )
    FollowUpCoordinationActionService(repository).ensure_follow_up_coordination_request(
        created.id,
        attribution=_snapshot(OTHER_SESSION_ID),
    )
    FollowUpCoordinationActionService(repository).ensure_follow_up_coordination_request(
        created.id,
        attribution=_snapshot(),
    )
    assert _rows(
        repository.database_path,
        "SELECT operation, session_id FROM follow_up_human_attributions ORDER BY operation",
    ) == [
        ("coordination_request_created", OTHER_SESSION_ID),
        ("review_case_closed", SESSION_ID),
    ]
