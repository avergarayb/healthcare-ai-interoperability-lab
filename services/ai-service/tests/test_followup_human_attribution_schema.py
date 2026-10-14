from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.followup_coordination_action import CoordinationActionType, CoordinationRequestStatus
from app.followup_review import (
    FollowUpReviewCaseService,
    ReviewCaseStatus,
    ReviewEventType,
    ReviewOutcome,
    ReviewStoreInitializationError,
)
from app.followup_review_sqlite import SCHEMA_VERSION, SQLiteFollowUpReviewCaseRepository
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)


APP = Path(__file__).resolve().parents[1] / "app"
MIGRATION_001_SHA256 = "94a043adffad718fd0fcdc79794cd044d19e2471db89da664170ceb33416be80"
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
CASE_ID = "10000000-0000-4000-8000-0000000000a1"
OTHER_CASE_ID = "10000000-0000-4000-8000-0000000000a2"
REQUEST_ID = "10000000-0000-4000-8000-0000000000b1"
OTHER_REQUEST_ID = "10000000-0000-4000-8000-0000000000b2"
SESSION_ID = "10000000-0000-4000-8000-0000000000c1"
WHEN = "2026-09-30T12:00:00.000000Z"


def _apply(path: Path, name: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript((APP / "migrations" / name).read_text(encoding="utf-8"))
    finally:
        connection.close()


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _insert_case(connection: sqlite3.Connection, case_id: str, *, closed: bool) -> None:
    identity = "ab" * 32
    if case_id == OTHER_CASE_ID:
        identity = "cd" * 32
    status = "closed" if closed else "open"
    outcome = "follow_up_coordination_planned" if closed else None
    version = 2 if closed else 1
    closed_at = WHEN if closed else None
    connection.execute(
        """
        INSERT INTO follow_up_review_cases (
            id, review_identity, case_id, protocol_id, protocol_evaluation_status,
            reason_codes_json, matched_resources_json, status, outcome, version,
            created_at, updated_at, closed_at
        ) VALUES (?, ?, 'SYN-FOLLOWUP-001', ?, 'matched', '[]', '[]', ?, ?, ?, ?, ?, ?)
        """,
        (
            case_id,
            identity,
            POST_CONSULTATION_RESULT_REVIEW_V1,
            status,
            outcome,
            version,
            WHEN,
            WHEN,
            closed_at,
        ),
    )
    connection.execute(
        """
        INSERT INTO follow_up_review_case_events (
            event_id, review_case_id, case_version, event_type,
            from_status, to_status, outcome, occurred_at
        ) VALUES (?, ?, 1, 'created', NULL, 'open', NULL, ?)
        """,
        (case_id + "-created", case_id, WHEN),
    )
    if closed:
        connection.execute(
            """
            INSERT INTO follow_up_review_case_events (
                event_id, review_case_id, case_version, event_type,
                from_status, to_status, outcome, occurred_at
            ) VALUES (?, ?, 2, 'closed', 'open', 'closed', ?, ?)
            """,
            (case_id + "-closed", case_id, outcome, WHEN),
        )


def _insert_request(connection: sqlite3.Connection, request_id: str, case_id: str) -> None:
    connection.execute(
        """
        INSERT INTO follow_up_coordination_requests (
            id, action_identity, review_case_id, protocol_id, action_type, status, created_at
        ) VALUES (?, ?, ?, ?, 'create_follow_up_coordination_request', 'requested', ?)
        """,
        (request_id, hashlib.sha256(request_id.encode("utf-8")).hexdigest(), case_id, POST_CONSULTATION_RESULT_REVIEW_V1, WHEN),
    )


def _seed_version_two(path: Path) -> None:
    _apply(path, "001_follow_up_review.sql")
    _apply(path, "002_follow_up_coordination_request.sql")
    connection = _connect(path)
    try:
        _insert_case(connection, CASE_ID, closed=True)
        _insert_request(connection, REQUEST_ID, CASE_ID)
        connection.commit()
    finally:
        connection.close()


def _attribution(
    connection: sqlite3.Connection,
    *,
    attribution_id: str,
    case_id: str,
    operation: str,
    subject_version: int | None,
    request_id: str | None,
    principal_id: str = "lab-reviewer",
    session_id: str = SESSION_ID,
) -> None:
    connection.execute(
        """
        INSERT INTO follow_up_human_attributions (
            attribution_id, review_case_id, operation, subject_version,
            coordination_request_id, principal_id, authenticator_id, session_id, occurred_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'DEVELOPMENT_AUTHENTICATOR_V1', ?, ?)
        """,
        (attribution_id, case_id, operation, subject_version, request_id, principal_id, session_id, WHEN),
    )


def test_migrations_001_and_002_do_not_define_attribution():
    assert SCHEMA_VERSION == 4
    first = (APP / "migrations" / "001_follow_up_review.sql").read_bytes()
    second = (APP / "migrations" / "002_follow_up_coordination_request.sql").read_text(encoding="utf-8")
    third = (APP / "migrations" / "003_follow_up_human_attribution.sql").read_text(encoding="utf-8")
    assert hashlib.sha256(first).hexdigest() == MIGRATION_001_SHA256
    assert "follow_up_human_attributions" not in first.decode("utf-8")
    assert "follow_up_human_attributions" not in second
    assert "CREATE TABLE follow_up_human_attributions" in third
    assert "PRAGMA user_version = 3;" in third


def test_fresh_database_applies_001_002_and_003(tmp_path):
    path = tmp_path / "review.sqlite3"
    repository = SQLiteFollowUpReviewCaseRepository(path, clock=lambda: NOW)
    repository.initialize()
    connection = _connect(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert connection.execute("SELECT COUNT(*) FROM follow_up_human_attributions").fetchone()[0] == 0
        names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'trigger')")
        }
    finally:
        connection.close()
    assert "follow_up_human_attributions" in names
    assert "follow_up_human_attributions_coordination_case" in names


def test_version_two_upgrade_keeps_cases_and_does_not_backfill(tmp_path):
    path = tmp_path / "review.sqlite3"
    _seed_version_two(path)
    before = _connect(path)
    try:
        case_before = [tuple(row) for row in before.execute("SELECT * FROM follow_up_review_cases")]
        event_before = [tuple(row) for row in before.execute("SELECT * FROM follow_up_review_case_events")]
        request_before = [tuple(row) for row in before.execute("SELECT * FROM follow_up_coordination_requests")]
        assert before.execute("PRAGMA user_version").fetchone()[0] == 2
    finally:
        before.close()
    SQLiteFollowUpReviewCaseRepository(path, clock=lambda: NOW).initialize()
    after = _connect(path)
    try:
        assert after.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert [tuple(row) for row in after.execute("SELECT * FROM follow_up_review_cases")] == case_before
        assert [tuple(row) for row in after.execute("SELECT * FROM follow_up_review_case_events")] == event_before
        assert [tuple(row) for row in after.execute("SELECT * FROM follow_up_coordination_requests")] == request_before
        assert after.execute("SELECT COUNT(*) FROM follow_up_human_attributions").fetchone()[0] == 0
    finally:
        after.close()


def test_failed_attribution_migration_keeps_version_two_data(tmp_path, monkeypatch):
    path = tmp_path / "review.sqlite3"
    _seed_version_two(path)
    broken = tmp_path / "broken-003.sql"
    broken.write_text(
        "BEGIN IMMEDIATE; CREATE TABLE follow_up_human_attributions(attribution_id TEXT); INVALID SQL; COMMIT;",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.followup_review_sqlite._HUMAN_ATTRIBUTION_MIGRATION", broken)
    with pytest.raises(ReviewStoreInitializationError):
        SQLiteFollowUpReviewCaseRepository(path).initialize()
    connection = _connect(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM follow_up_review_cases").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM follow_up_coordination_requests").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'follow_up_human_attributions'"
            ).fetchone()
            is None
        )
    finally:
        connection.close()


def test_close_attribution_requires_the_version_two_event_and_is_unique(tmp_path):
    path = tmp_path / "review.sqlite3"
    _seed_version_two(path)
    _apply(path, "003_follow_up_human_attribution.sql")
    connection = _connect(path)
    try:
        _attribution(
            connection,
            attribution_id="10000000-0000-4000-8000-0000000000d1",
            case_id=CASE_ID,
            operation="review_case_closed",
            subject_version=2,
            request_id=None,
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            _attribution(
                connection,
                attribution_id="10000000-0000-4000-8000-0000000000d2",
                case_id=CASE_ID,
                operation="review_case_closed",
                subject_version=2,
                request_id=None,
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            _attribution(
                connection,
                attribution_id="10000000-0000-4000-8000-0000000000d3",
                case_id=CASE_ID,
                operation="review_case_closed",
                subject_version=1,
                request_id=None,
            )
        connection.rollback()
        _insert_case(connection, OTHER_CASE_ID, closed=False)
        with pytest.raises(sqlite3.IntegrityError):
            _attribution(
                connection,
                attribution_id="10000000-0000-4000-8000-0000000000d4",
                case_id=OTHER_CASE_ID,
                operation="review_case_closed",
                subject_version=2,
                request_id=None,
            )
    finally:
        connection.close()


def test_coordination_attribution_must_match_the_request_case(tmp_path):
    path = tmp_path / "review.sqlite3"
    _seed_version_two(path)
    _apply(path, "003_follow_up_human_attribution.sql")
    connection = _connect(path)
    try:
        _insert_case(connection, OTHER_CASE_ID, closed=True)
        _insert_request(connection, OTHER_REQUEST_ID, OTHER_CASE_ID)
        _attribution(
            connection,
            attribution_id="10000000-0000-4000-8000-0000000000e1",
            case_id=CASE_ID,
            operation="coordination_request_created",
            subject_version=None,
            request_id=REQUEST_ID,
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            _attribution(
                connection,
                attribution_id="10000000-0000-4000-8000-0000000000e2",
                case_id=OTHER_CASE_ID,
                operation="coordination_request_created",
                subject_version=None,
                request_id=REQUEST_ID,
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            _attribution(
                connection,
                attribution_id="10000000-0000-4000-8000-0000000000e3",
                case_id=CASE_ID,
                operation="coordination_request_created",
                subject_version=None,
                request_id=REQUEST_ID,
            )
    finally:
        connection.close()


def test_attribution_rejects_secrets_and_blocks_parent_deletes(tmp_path):
    path = tmp_path / "review.sqlite3"
    _seed_version_two(path)
    _apply(path, "003_follow_up_human_attribution.sql")
    connection = _connect(path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            _attribution(
                connection,
                attribution_id="10000000-0000-4000-8000-0000000000f1",
                case_id=CASE_ID,
                operation="review_case_closed",
                subject_version=2,
                request_id=None,
                principal_id="Lab-Reviewer",
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            _attribution(
                connection,
                attribution_id="10000000-0000-4000-8000-0000000000f2",
                case_id=CASE_ID,
                operation="review_case_closed",
                subject_version=2,
                request_id=None,
                session_id="not-a-session-token-value",
            )
        connection.rollback()
        _attribution(
            connection,
            attribution_id="10000000-0000-4000-8000-0000000000f3",
            case_id=CASE_ID,
            operation="review_case_closed",
            subject_version=2,
            request_id=None,
        )
        _attribution(
            connection,
            attribution_id="10000000-0000-4000-8000-0000000000f4",
            case_id=CASE_ID,
            operation="coordination_request_created",
            subject_version=None,
            request_id=REQUEST_ID,
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM follow_up_review_cases WHERE id = ?", (CASE_ID,))
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM follow_up_review_case_events WHERE review_case_id = ? AND case_version = 2",
                (CASE_ID,),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM follow_up_coordination_requests WHERE id = ?", (REQUEST_ID,))
    finally:
        connection.close()


def test_repository_close_and_coordination_still_write_no_attribution(tmp_path):
    path = tmp_path / "review.sqlite3"
    repository = SQLiteFollowUpReviewCaseRepository(path, clock=lambda: NOW)
    repository.initialize()
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
    closed = repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    assert closed.status is ReviewCaseStatus.CLOSED
    stored = repository.ensure_follow_up_coordination_request(created.id)
    assert stored.action_type is CoordinationActionType.CREATE_FOLLOW_UP_COORDINATION_REQUEST
    assert stored.status is CoordinationRequestStatus.REQUESTED
    connection = _connect(path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM follow_up_human_attributions").fetchone()[0] == 0
        assert [row[0] for row in connection.execute(
            "SELECT event_type FROM follow_up_review_case_events ORDER BY case_version"
        )] == [ReviewEventType.CREATED.value, ReviewEventType.CLOSED.value]
    finally:
        connection.close()
