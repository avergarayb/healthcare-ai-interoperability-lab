from __future__ import annotations

import json
import re
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.followup_review import (
    REVIEW_IDENTITY_SCHEMA,
    FollowUpReviewCaseService,
    InvalidReviewTrigger,
    ReviewCaseDetail,
    ReviewCaseConflict,
    ReviewCaseStatus,
    ReviewEventType,
    ReviewOutcome,
    ReviewPersistenceUnavailable,
    ReviewStoreInitializationError,
    build_review_identity,
    canonical_matched_resources,
    trigger_from_protocol,
    utc_timestamp,
    validate_review_detail,
    validate_utc_timestamp,
)
from app.followup_review_sqlite import (
    _MIGRATION,
    SQLiteFollowUpReviewCaseRepository,
    _normalize_schema_sql,
)
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)


CASE = "SYN-FOLLOWUP-008"
RESOURCES = ("Encounter/encounter-008", "Observation/observation-008")
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def _protocol(
    *,
    status: ProtocolEvaluationStatus = ProtocolEvaluationStatus.MATCHED,
    resources: tuple[str, ...] = RESOURCES,
    reasons: tuple[str, ...] = ("post_consultation_result_requires_review",),
    protocol_id: str = POST_CONSULTATION_RESULT_REVIEW_V1,
) -> ProtocolReviewResult:
    return ProtocolReviewResult(
        id=protocol_id,
        evaluation_status=status,
        reason_codes=reasons,
        matched_resources=resources,
        human_review_status="required" if status is ProtocolEvaluationStatus.MATCHED else "not_determined",
        human_review_reason=(
            "deterministic_post_consultation_protocol_match"
            if status is ProtocolEvaluationStatus.MATCHED
            else None
        ),
        action_status="proposed" if status is ProtocolEvaluationStatus.MATCHED else "not_determined",
        action_type="review_follow_up_case" if status is ProtocolEvaluationStatus.MATCHED else None,
    )


def _repository(tmp_path, *, clock=lambda: NOW) -> SQLiteFollowUpReviewCaseRepository:
    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3", clock=clock)
    repository.initialize()
    return repository


def _create(repository, *, case_id: str = CASE, protocol=None):
    service = FollowUpReviewCaseService(repository)
    created = service.ensure_for_protocol(case_id, protocol or _protocol())
    assert created is not None
    return created


def _execute_direct(path, sql: str, parameters: tuple[object, ...] = ()) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(sql, parameters)
        connection.commit()
    finally:
        connection.close()


def _install_schema(path, sql: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(sql)
    finally:
        connection.close()


def _rename_round_trip(path) -> None:
    moved = path.with_name("renamed-review.sqlite3")
    path.rename(moved)
    moved.rename(path)


def test_identity_uses_explicit_versioned_unambiguous_serialization():
    value = build_review_identity(CASE, POST_CONSULTATION_RESULT_REVIEW_V1, RESOURCES)
    assert REVIEW_IDENTITY_SCHEMA == "FOLLOW_UP_REVIEW_EVENT_IDENTITY_V1"
    assert value == "71d58ffe8f62ba5679a7d414607d5aca9c3c7e68fb2dbca17036e29c337306ea"
    assert len(value) == 64


def test_identity_is_order_independent_and_deduplicates_resources():
    first = build_review_identity(CASE, POST_CONSULTATION_RESULT_REVIEW_V1, RESOURCES)
    second = build_review_identity(
        CASE,
        POST_CONSULTATION_RESULT_REVIEW_V1,
        (RESOURCES[1], RESOURCES[0], RESOURCES[1]),
    )
    assert first == second
    assert canonical_matched_resources((RESOURCES[1], RESOURCES[0], RESOURCES[1])) == tuple(sorted(RESOURCES))


def test_identity_changes_for_resource_case_or_protocol_changes():
    original = build_review_identity(CASE, POST_CONSULTATION_RESULT_REVIEW_V1, RESOURCES)
    assert original != build_review_identity(CASE, POST_CONSULTATION_RESULT_REVIEW_V1, (RESOURCES[0], "Observation/other"))
    assert original != build_review_identity("SYN-FOLLOWUP-009", POST_CONSULTATION_RESULT_REVIEW_V1, RESOURCES)
    assert original != build_review_identity(CASE, "POST_CONSULTATION_RESULT_REVIEW_V2", RESOURCES)


def test_reason_codes_do_not_change_identity():
    first = trigger_from_protocol(CASE, _protocol(reasons=("first_reason",)))
    second = trigger_from_protocol(CASE, _protocol(reasons=("second_reason",)))
    assert first.review_identity == second.review_identity


@pytest.mark.parametrize(
    "reference",
    ["Observation", "Observation/../x", "Observation/..", "Unknown/id", "Observation/id/path", ""],
)
def test_identity_rejects_noncanonical_resource_references(reference: str):
    with pytest.raises(InvalidReviewTrigger):
        build_review_identity(CASE, POST_CONSULTATION_RESULT_REVIEW_V1, (reference,))


def test_real_clock_serialization_requires_timezone_and_ends_in_z():
    assert utc_timestamp(lambda: NOW) == "2026-09-30T12:00:00.000000Z"
    with pytest.raises(ValueError):
        utc_timestamp(lambda: datetime(2026, 9, 30, 12, 0))


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-30Z",
        "2026-09-30T12Z",
        "2026-09-30 12:00:00.000000Z",
        "2026-09-30T12:00:00+00:00",
        "2026-09-30T12:00:00.123Z",
        "2026-09-30T12:00:00.000000Ztrailing",
    ],
)
def test_durable_timestamp_validation_rejects_noncanonical_values(value):
    with pytest.raises(ValueError, match="timestamp is invalid"):
        validate_utc_timestamp(value)


def test_every_repository_operation_closes_its_connection(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    assert repository.get(created.id) == created
    assert repository.get_detail(created.id) is not None
    assert repository.list_cases(
        status=ReviewCaseStatus.OPEN,
        case_id=None,
        limit=10,
        after=None,
    ).items == (created,)
    closed = repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    assert len(repository.events(closed.id)) == 2
    _rename_round_trip(repository.database_path)


def test_repository_closes_connection_when_read_validation_fails(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    _execute_direct(
        repository.database_path,
        "UPDATE follow_up_review_cases SET reason_codes_json = ? WHERE id = ?",
        ('{"raw":"not-an-array"}', created.id),
    )
    with pytest.raises(ReviewPersistenceUnavailable):
        repository.get(created.id)
    _rename_round_trip(repository.database_path)


def test_repository_closes_connection_when_connection_configuration_fails(
    tmp_path,
    monkeypatch,
):
    real_connect = sqlite3.connect
    closed = []

    class FailingConnection:
        def __init__(self, *args, **kwargs):
            self.inner = real_connect(*args, **kwargs)

        @property
        def row_factory(self):
            return self.inner.row_factory

        @row_factory.setter
        def row_factory(self, value):
            self.inner.row_factory = value

        def execute(self, sql, *args):
            if sql.startswith("PRAGMA busy_timeout"):
                raise sqlite3.OperationalError("configuration failed")
            return self.inner.execute(sql, *args)

        def close(self):
            self.inner.close()
            closed.append(True)

    monkeypatch.setattr(
        "app.followup_review_sqlite.sqlite3.connect",
        lambda *args, **kwargs: FailingConnection(*args, **kwargs),
    )

    with pytest.raises(ReviewStoreInitializationError):
        SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3").initialize()
    assert closed == [True]


def test_empty_database_initializes_supported_schema(tmp_path):
    path = tmp_path / "review.sqlite3"
    repository = SQLiteFollowUpReviewCaseRepository(path)
    repository.initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {
        "follow_up_review_cases",
        "follow_up_review_case_events",
        "follow_up_coordination_requests",
    } <= tables


def test_supported_schema_reopens_and_preserves_open_and_closed_state(tmp_path):
    path = tmp_path / "review.sqlite3"
    first = SQLiteFollowUpReviewCaseRepository(path, clock=lambda: NOW)
    first.initialize()
    created = _create(first)

    second = SQLiteFollowUpReviewCaseRepository(path, clock=lambda: NOW)
    second.initialize()
    reopened = second.get(created.id)
    assert reopened == created
    assert second.events(created.id)[0].event_type is ReviewEventType.CREATED

    closed = second.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    third = SQLiteFollowUpReviewCaseRepository(path, clock=lambda: NOW)
    third.initialize()
    assert third.get(created.id) == closed
    assert [event.event_type for event in third.events(created.id)] == [
        ReviewEventType.CREATED,
        ReviewEventType.CLOSED,
    ]


def test_future_schema_version_fails_safely(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=99")
    with pytest.raises(ReviewStoreInitializationError):
        SQLiteFollowUpReviewCaseRepository(path).initialize()


def test_current_version_with_invalid_schema_fails_safely(tmp_path):
    path = tmp_path / "invalid.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE follow_up_review_cases (id TEXT PRIMARY KEY)")
        connection.execute("PRAGMA user_version=1")
    with pytest.raises(ReviewStoreInitializationError):
        SQLiteFollowUpReviewCaseRepository(path).initialize()


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("event_id TEXT PRIMARY KEY", "event_id TEXT"),
        (
            "review_identity TEXT NOT NULL UNIQUE CHECK",
            "review_identity TEXT NOT NULL CHECK",
        ),
        ("case_id TEXT NOT NULL CHECK", "case_id TEXT CHECK"),
        (
            "FOREIGN KEY (review_case_id) REFERENCES follow_up_review_cases(id) ON DELETE RESTRICT,",
            "",
        ),
        (
            "CREATE INDEX follow_up_review_cases_queue_idx\n"
            "    ON follow_up_review_cases (status, created_at, id);",
            "",
        ),
    ],
    ids=[
        "missing-event-primary-key",
        "missing-review-identity-unique",
        "missing-case-id-not-null",
        "missing-event-foreign-key",
        "missing-queue-index",
    ],
)
def test_current_v1_rejects_material_schema_invariant_changes(tmp_path, old, new):
    path = tmp_path / "invalid-v1.sqlite3"
    canonical = _MIGRATION.read_text(encoding="utf-8")
    modified = canonical.replace(old, new, 1)
    assert modified != canonical
    _install_schema(path, modified)
    with pytest.raises(ReviewStoreInitializationError, match="schema is invalid"):
        SQLiteFollowUpReviewCaseRepository(path).initialize()


def test_current_v1_rejects_missing_approved_outcome_constraints(tmp_path):
    path = tmp_path / "missing-outcomes.sqlite3"
    canonical = _MIGRATION.read_text(encoding="utf-8")
    pattern = (
        r"outcome TEXT CHECK \(\s*outcome IS NULL OR outcome IN \(\s*"
        r"'follow_up_coordination_planned',\s*"
        r"'review_completed_no_operational_action'\s*\)\s*\)"
    )
    modified, count = re.subn(pattern, "outcome TEXT", canonical)
    assert count == 2
    _install_schema(path, modified)
    with pytest.raises(ReviewStoreInitializationError, match="schema is invalid"):
        SQLiteFollowUpReviewCaseRepository(path).initialize()


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            "protocol_evaluation_status = 'matched'",
            "protocol_evaluation_status = 'MATCHED'",
        ),
        ("status IN ('open', 'closed')", "status IN ('OPEN', 'closed')"),
        (
            "'follow_up_coordination_planned'",
            "'FOLLOW_UP_COORDINATION_PLANNED'",
        ),
        (
            "event_type IN ('created', 'closed')",
            "event_type IN ('CREATED', 'closed')",
        ),
    ],
    ids=[
        "protocol-evaluation-literal",
        "lifecycle-status-literal",
        "approved-outcome-literal",
        "event-type-literal",
    ],
)
def test_current_v1_rejects_case_mutated_check_literals(tmp_path, old, new):
    path = tmp_path / "case-mutated-v1.sqlite3"
    canonical = _MIGRATION.read_text(encoding="utf-8")
    modified = canonical.replace(old, new, 1)
    assert modified != canonical
    _install_schema(path, modified)

    with pytest.raises(ReviewStoreInitializationError, match="schema is invalid"):
        SQLiteFollowUpReviewCaseRepository(path).initialize()


def test_schema_sql_normalization_preserves_quoted_literal_contents():
    sql = (
        "  CHECK(value IN ('abc''Def', 'two  spaces', 'OPEN') "
        "AND other = 'matched')  "
    )

    assert _normalize_schema_sql(sql) == sql.strip()
    assert _normalize_schema_sql("CHECK(value = 'matched')") != _normalize_schema_sql(
        "CHECK(value = 'MATCHED')"
    )


def test_failed_migration_is_transactional(tmp_path, monkeypatch):
    path = tmp_path / "partial.sqlite3"
    migration = tmp_path / "broken.sql"
    migration.write_text(
        "BEGIN IMMEDIATE; CREATE TABLE should_rollback(id TEXT); INVALID SQL; COMMIT;",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.followup_review_sqlite._MIGRATION", migration)
    with pytest.raises(ReviewStoreInitializationError):
        SQLiteFollowUpReviewCaseRepository(path).initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name='should_rollback'"
        ).fetchone() is None
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0


def test_schema_enforces_event_foreign_key(tmp_path):
    repository = _repository(tmp_path)
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO follow_up_review_case_events (
                    event_id, review_case_id, case_version, event_type,
                    from_status, to_status, outcome, occurred_at
                ) VALUES (?, ?, 1, 'created', NULL, 'open', NULL, ?)
                """,
                ("event", "missing", "2026-09-30T12:00:00.000000Z"),
            )


def test_creation_has_open_state_version_one_and_one_created_event(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    assert created.status is ReviewCaseStatus.OPEN
    assert created.outcome is None
    assert created.version == 1
    assert created.created_at == created.updated_at == "2026-09-30T12:00:00.000000Z"
    assert created.closed_at is None
    events = repository.events(created.id)
    assert len(events) == 1
    assert events[0].event_type is ReviewEventType.CREATED
    assert events[0].case_version == 1
    assert events[0].from_status is None
    assert events[0].to_status is ReviewCaseStatus.OPEN


@pytest.mark.parametrize("status", list(ProtocolEvaluationStatus))
def test_only_matched_protocol_creates_a_case(tmp_path, status):
    repository = _repository(tmp_path)
    result = FollowUpReviewCaseService(repository).ensure_for_protocol(CASE, _protocol(status=status))
    page = repository.list_cases(status=ReviewCaseStatus.OPEN, case_id=None, limit=100, after=None)
    assert (result is not None) is (status is ProtocolEvaluationStatus.MATCHED)
    assert len(page.items) == (1 if status is ProtocolEvaluationStatus.MATCHED else 0)


def test_exact_identity_reuses_open_and_closed_case(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    assert _create(repository).id == created.id
    closed = repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION,
    )
    reused = _create(repository)
    assert reused == closed
    assert len(repository.events(created.id)) == 2


def test_different_matched_resource_set_creates_another_case(tmp_path):
    repository = _repository(tmp_path)
    first = _create(repository)
    second = _create(repository, protocol=_protocol(resources=(RESOURCES[0], "Observation/other")))
    assert first.id != second.id


def test_close_is_terminal_and_same_outcome_retry_is_idempotent(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    closed = repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    repeated = repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    assert closed == repeated
    assert closed.status is ReviewCaseStatus.CLOSED
    assert closed.version == 2
    assert closed.closed_at == "2026-09-30T12:00:00.000000Z"
    assert len(repository.events(created.id)) == 2
    with pytest.raises(ReviewCaseConflict):
        repository.close(
            created.id,
            expected_version=2,
            outcome=ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION,
        )


def test_open_case_rejects_stale_expected_version(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    with pytest.raises(ReviewCaseConflict):
        repository.close(
            created.id,
            expected_version=2,
            outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
        )
    assert repository.get(created.id) == created
    assert len(repository.events(created.id)) == 1


def test_closed_event_failure_rolls_back_case_state(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_closed_event
            BEFORE INSERT ON follow_up_review_case_events
            WHEN NEW.event_type = 'closed'
            BEGIN
                SELECT RAISE(ABORT, 'closed event rejected');
            END
            """
        )
    with pytest.raises(ReviewPersistenceUnavailable):
        repository.close(
            created.id,
            expected_version=1,
            outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
        )
    assert repository.get(created.id) == created
    assert len(repository.events(created.id)) == 1


def test_exhausted_sqlite_lock_maps_to_persistence_unavailable(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    trigger = trigger_from_protocol(CASE, _protocol())
    monkeypatch.setattr("app.followup_review_sqlite.BUSY_TIMEOUT_MS", 10)
    locker = sqlite3.connect(repository.database_path, isolation_level=None)
    try:
        locker.execute("PRAGMA journal_mode=WAL")
        locker.execute("BEGIN IMMEDIATE")
        with pytest.raises(ReviewPersistenceUnavailable):
            repository.ensure(trigger)
    finally:
        locker.rollback()
        locker.close()


def test_malformed_persisted_provenance_fails_closed(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "UPDATE follow_up_review_cases SET reason_codes_json = ? WHERE id = ?",
            ('{"raw":"not-an-array"}', created.id),
        )
    with pytest.raises(ReviewPersistenceUnavailable):
        repository.get(created.id)


@pytest.mark.parametrize(
    ("close_first", "assignment"),
    [
        (False, "version = 2"),
        (False, "outcome = 'follow_up_coordination_planned'"),
        (False, "closed_at = updated_at"),
        (True, "outcome = NULL"),
        (True, "closed_at = NULL"),
        (True, "version = 1"),
        (False, "protocol_evaluation_status = 'not_matched'"),
        (False, "created_at = '2026-09-30Z'"),
    ],
)
def test_repository_rejects_persisted_impossible_case_states(
    tmp_path,
    close_first,
    assignment,
):
    repository = _repository(tmp_path)
    created = _create(repository, case_id="case-impossible-state")
    if close_first:
        created = repository.close(
            created.id,
            expected_version=1,
            outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
        )

    _execute_direct(
        repository.database_path,
        f"UPDATE follow_up_review_cases SET {assignment} WHERE id = ?",
        (created.id,),
    )

    with pytest.raises(ReviewPersistenceUnavailable):
        repository.get(created.id)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        (
            "matched_resources_json",
            '["Observation/observation-008","Encounter/encounter-008"]',
        ),
        (
            "matched_resources_json",
            '["Encounter/encounter-008","Encounter/encounter-008"]',
        ),
        ("matched_resources_json", '{"resource":"Observation/observation-008"}'),
        (
            "reason_codes_json",
            '["post_consultation_result_requires_review",'
            '"post_consultation_result_requires_review"]',
        ),
        ("reason_codes_json", '["NEW_RESULT_AVAILABLE"]'),
    ],
)
def test_repository_rejects_noncanonical_persisted_provenance(tmp_path, column, value):
    repository = _repository(tmp_path)
    created = _create(repository, case_id="case-bad-provenance")
    _execute_direct(
        repository.database_path,
        f"UPDATE follow_up_review_cases SET {column} = ? WHERE id = ?",
        (value, created.id),
    )

    with pytest.raises(ReviewPersistenceUnavailable):
        repository.get(created.id)


def test_repository_rejects_open_case_without_created_event(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository, case_id="case-missing-created")
    _execute_direct(
        repository.database_path,
        "DELETE FROM follow_up_review_case_events WHERE review_case_id = ?",
        (created.id,),
    )

    with pytest.raises(ReviewPersistenceUnavailable):
        repository.get_detail(created.id)


def test_repository_rejects_closed_event_for_open_case(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository, case_id="case-open-with-close-event")
    _execute_direct(
        repository.database_path,
        """
        INSERT INTO follow_up_review_case_events (
            event_id, review_case_id, case_version, event_type,
            from_status, to_status, outcome, occurred_at
        ) VALUES (?, ?, 2, 'closed', 'open', 'closed',
                  'follow_up_coordination_planned', ?)
        """,
        (
            "10000000-0000-4000-8000-000000000001",
            created.id,
            "2026-09-30T12:00:00.000000Z",
        ),
    )

    with pytest.raises(ReviewPersistenceUnavailable):
        repository.events(created.id)


def test_repository_rejects_closed_case_without_closed_event(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository, case_id="case-missing-closed")
    closed = repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    _execute_direct(
        repository.database_path,
        """
        DELETE FROM follow_up_review_case_events
        WHERE review_case_id = ? AND event_type = 'closed'
        """,
        (closed.id,),
    )

    with pytest.raises(ReviewPersistenceUnavailable):
        repository.get_detail(closed.id)


def test_repository_rejects_history_outcome_mismatch(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository, case_id="case-history-outcome")
    closed = repository.close(
        created.id,
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

    with pytest.raises(ReviewPersistenceUnavailable):
        repository.events(closed.id)


def test_repository_rejects_noncanonical_event_timestamp(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository, case_id="case-bad-event-time")
    _execute_direct(
        repository.database_path,
        """
        UPDATE follow_up_review_case_events
        SET occurred_at = '2026-09-30Z'
        WHERE review_case_id = ? AND event_type = 'created'
        """,
        (created.id,),
    )

    with pytest.raises(ReviewPersistenceUnavailable):
        repository.get_detail(created.id)


def test_review_detail_validator_rejects_duplicate_event_identity(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository, case_id="case-duplicate-event")
    detail = repository.get_detail(created.id)

    with pytest.raises(ValueError, match="duplicate event ids"):
        validate_review_detail(
            ReviewCaseDetail(case=detail.case, events=(detail.events[0], detail.events[0]))
        )


def test_review_detail_validator_rejects_duplicate_created_event(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository, case_id="case-duplicate-created")
    detail = repository.get_detail(created.id)
    duplicate = replace(
        detail.events[0],
        event_id="10000000-0000-4000-8000-000000000002",
    )

    with pytest.raises(ValueError, match="versions"):
        validate_review_detail(
            ReviewCaseDetail(case=detail.case, events=(detail.events[0], duplicate))
        )


def test_review_detail_validator_rejects_duplicate_closed_event(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository, case_id="case-duplicate-closed")
    closed = repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    detail = repository.get_detail(closed.id)
    duplicate = replace(
        detail.events[1],
        event_id="10000000-0000-4000-8000-000000000003",
    )

    with pytest.raises(ValueError, match="versions"):
        validate_review_detail(
            ReviewCaseDetail(case=detail.case, events=detail.events + (duplicate,))
        )


def test_concurrent_identical_create_has_one_case_and_created_event(tmp_path):
    repository = _repository(tmp_path)
    trigger = trigger_from_protocol(CASE, _protocol())
    workers = 8
    barrier = threading.Barrier(workers)

    def create():
        barrier.wait(timeout=10)
        return repository.ensure(trigger)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(lambda _index: create(), range(workers)))
    assert len({result.id for result in results}) == 1
    page = repository.list_cases(status=ReviewCaseStatus.OPEN, case_id=None, limit=100, after=None)
    assert len(page.items) == 1
    assert len(repository.events(results[0].id)) == 1


def test_concurrent_same_outcome_close_has_one_closed_event(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    barrier = threading.Barrier(2)

    def close():
        barrier.wait(timeout=10)
        return repository.close(
            created.id,
            expected_version=1,
            outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: close(), range(2)))
    assert results[0] == results[1]
    assert len(repository.events(created.id)) == 2


def test_concurrent_different_outcome_close_has_one_winner(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    barrier = threading.Barrier(2)
    outcomes = list(ReviewOutcome)

    def close(outcome):
        barrier.wait(timeout=10)
        try:
            return repository.close(created.id, expected_version=1, outcome=outcome)
        except ReviewCaseConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(close, outcomes))
    winners = [result for result in results if result != "conflict"]
    assert len(winners) == 1
    assert results.count("conflict") == 1
    assert repository.get(created.id).outcome == winners[0].outcome
    assert len(repository.events(created.id)) == 2


def test_persisted_schema_and_values_are_minimized(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    with sqlite3.connect(repository.database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(follow_up_review_cases)")
        }
        stored = json.dumps(connection.execute(
            "SELECT * FROM follow_up_review_cases WHERE id = ?", (created.id,)
        ).fetchone())
    forbidden_columns = {
        "patient",
        "patient_id",
        "encounter",
        "observation",
        "appointment",
        "bundle",
        "prompt",
        "response",
        "answer",
        "note",
        "reviewer_id",
        "assigned_to",
    }
    assert columns.isdisjoint(forbidden_columns)
    for token in ("resourceType", "valueString", "Gemini", "reviewer"):
        assert token not in stored
