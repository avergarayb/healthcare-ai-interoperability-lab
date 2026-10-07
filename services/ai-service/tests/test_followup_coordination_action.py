from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.followup_coordination_action import (
    CONTROLLED_ACTION_IDENTITY_V1,
    CoordinationActionType,
    CoordinationRequestNotPersistable,
    CoordinationRequestStatus,
    FollowUpCoordinationRequest,
    build_coordination_action_identity,
)
from app.followup_review import (
    FollowUpReviewCaseService,
    ReviewCaseNotFound,
    ReviewCaseStatus,
    ReviewEventType,
    ReviewOutcome,
    ReviewStoreInitializationError,
    build_review_identity,
)
from app.followup_review_sqlite import (
    SCHEMA_VERSION,
    SQLiteFollowUpReviewCaseRepository,
    _COORDINATION_REQUEST_MIGRATION,
    _MIGRATION,
)
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)


REVIEW_CASE_ID = "10000000-0000-4000-8000-000000000001"
OTHER_REVIEW_CASE_ID = "10000000-0000-4000-8000-000000000002"
MIGRATION_001_SHA256 = "94a043adffad718fd0fcdc79794cd044d19e2471db89da664170ceb33416be80"
IDENTITY_SHA256 = "c7e9dc764682551d4987042b169382820031d2b774166be4222e009fe9c9e4f6"
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 9, 30, 13, 0, tzinfo=timezone.utc)
APPROVED_COLUMNS = {
    "id",
    "action_identity",
    "review_case_id",
    "protocol_id",
    "action_type",
    "status",
    "created_at",
}
APP = Path(__file__).resolve().parents[1] / "app"


def _protocol(
    *,
    protocol_id: str = POST_CONSULTATION_RESULT_REVIEW_V1,
    resources: tuple[str, ...] = ("Encounter/encounter-001", "Observation/observation-001"),
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


def _create(repository, *, case_id: str = "SYN-FOLLOWUP-001", protocol=None):
    created = FollowUpReviewCaseService(repository).ensure_for_protocol(
        case_id,
        protocol or _protocol(),
    )
    assert created is not None
    return created


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


def _seed_version_one(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(_MIGRATION.read_text(encoding="utf-8"))
        resources = ("Encounter/encounter-001", "Observation/observation-001")
        reasons = ("post_consultation_result_requires_review",)
        review_case_id = REVIEW_CASE_ID
        identity = build_review_identity("SYN-FOLLOWUP-001", POST_CONSULTATION_RESULT_REVIEW_V1, resources)
        created_at = "2026-09-30T12:00:00.000000Z"
        connection.execute(
            """
            INSERT INTO follow_up_review_cases (
                id, review_identity, case_id, protocol_id,
                protocol_evaluation_status, reason_codes_json,
                matched_resources_json, status, outcome, version,
                created_at, updated_at, closed_at
            ) VALUES (?, ?, ?, ?, 'matched', ?, ?, 'open', NULL, 1, ?, ?, NULL)
            """,
            (
                review_case_id,
                identity,
                "SYN-FOLLOWUP-001",
                POST_CONSULTATION_RESULT_REVIEW_V1,
                json.dumps(list(reasons), separators=(",", ":")),
                json.dumps(list(resources), separators=(",", ":")),
                created_at,
                created_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO follow_up_review_case_events (
                event_id, review_case_id, case_version, event_type,
                from_status, to_status, outcome, occurred_at
            ) VALUES (?, ?, 1, 'created', NULL, 'open', NULL, ?)
            """,
            ("10000000-0000-4000-8000-000000000010", review_case_id, created_at),
        )
        connection.commit()
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        return review_case_id
    finally:
        connection.close()


def test_action_identity_is_canonical_sha256():
    assert CONTROLLED_ACTION_IDENTITY_V1 == "CONTROLLED_ACTION_IDENTITY_V1"
    encoded = json.dumps(
        {
            "actionType": "create_follow_up_coordination_request",
            "identitySchema": "CONTROLLED_ACTION_IDENTITY_V1",
            "reviewCaseId": REVIEW_CASE_ID,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert build_coordination_action_identity(REVIEW_CASE_ID) == hashlib.sha256(encoded).hexdigest()
    assert build_coordination_action_identity(REVIEW_CASE_ID) == IDENTITY_SHA256
    assert len(IDENTITY_SHA256) == 64


def test_same_review_case_keeps_action_identity_and_another_case_changes_it():
    assert build_coordination_action_identity(REVIEW_CASE_ID) == build_coordination_action_identity(
        REVIEW_CASE_ID
    )
    assert build_coordination_action_identity(REVIEW_CASE_ID) != build_coordination_action_identity(
        OTHER_REVIEW_CASE_ID
    )


def test_fresh_database_applies_both_migrations(tmp_path):
    repository = _repository(tmp_path)
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 2
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(follow_up_coordination_requests)")
        }
    assert {
        "follow_up_review_cases",
        "follow_up_review_case_events",
        "follow_up_coordination_requests",
    } <= tables
    assert columns == APPROVED_COLUMNS


def test_version_one_database_upgrades_without_losing_review_history(tmp_path):
    path = tmp_path / "review.sqlite3"
    review_case_id = _seed_version_one(path)
    before = _snapshot(path, review_case_id)
    repository = SQLiteFollowUpReviewCaseRepository(path, clock=lambda: NOW)
    repository.initialize()
    after = _snapshot(path, review_case_id)
    assert after == before
    loaded = repository.get(review_case_id)
    assert loaded is not None
    assert loaded.status is ReviewCaseStatus.OPEN
    assert loaded.version == 1
    assert [event.event_type for event in repository.events(review_case_id)] == [
        ReviewEventType.CREATED
    ]
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
    assert _count_requests(path) == 0


def test_version_two_database_initializes_again(tmp_path):
    path = tmp_path / "review.sqlite3"
    first = SQLiteFollowUpReviewCaseRepository(path, clock=lambda: NOW)
    first.initialize()
    created = _create(first)
    second = SQLiteFollowUpReviewCaseRepository(path, clock=lambda: NOW)
    second.initialize()
    assert second.get(created.id) == created
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name = 'follow_up_coordination_requests'"
            ).fetchone()[0]
            == 1
        )


def test_future_schema_version_fails_closed_without_rebuilding(tmp_path):
    path = tmp_path / "review.sqlite3"
    repository = SQLiteFollowUpReviewCaseRepository(path, clock=lambda: NOW)
    repository.initialize()
    created = _create(repository)
    before = _snapshot(path, created.id)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=3")
    with pytest.raises(ReviewStoreInitializationError, match="schema version is unsupported"):
        SQLiteFollowUpReviewCaseRepository(path).initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
    assert _snapshot(path, created.id) == before


def test_migration_001_remains_unchanged():
    payload = _MIGRATION.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == MIGRATION_001_SHA256
    text = payload.decode("utf-8")
    assert "PRAGMA user_version = 1;" in text
    assert "follow_up_coordination_requests" not in text
    assert "follow_up_coordination_requests" in _COORDINATION_REQUEST_MIGRATION.read_text(
        encoding="utf-8"
    )


def test_failed_coordination_migration_keeps_version_one_data(tmp_path, monkeypatch):
    path = tmp_path / "review.sqlite3"
    review_case_id = _seed_version_one(path)
    before = _snapshot(path, review_case_id)
    broken = tmp_path / "broken-002.sql"
    broken.write_text(
        "BEGIN IMMEDIATE; CREATE TABLE follow_up_coordination_requests(id TEXT); INVALID SQL; COMMIT;",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.followup_review_sqlite._COORDINATION_REQUEST_MIGRATION", broken)
    with pytest.raises(ReviewStoreInitializationError):
        SQLiteFollowUpReviewCaseRepository(path).initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'follow_up_coordination_requests'"
            ).fetchone()
            is None
        )
    assert _snapshot(path, review_case_id) == before


def test_ensure_persists_one_request_and_get_reconstructs_it(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    assert repository.get_follow_up_coordination_request(created.id) is None
    stored = repository.ensure_follow_up_coordination_request(created.id)
    assert isinstance(stored, FollowUpCoordinationRequest)
    assert stored.review_case_id == created.id
    assert stored.protocol_id == created.protocol_id == POST_CONSULTATION_RESULT_REVIEW_V1
    assert stored.action_identity == build_coordination_action_identity(created.id)
    assert stored.action_type is CoordinationActionType.CREATE_FOLLOW_UP_COORDINATION_REQUEST
    assert stored.status is CoordinationRequestStatus.REQUESTED
    assert stored.created_at == "2026-09-30T12:00:00.000000Z"
    assert repository.get_follow_up_coordination_request(created.id) == stored
    assert _count_requests(repository.database_path) == 1


def test_repeated_ensure_returns_the_original_row(tmp_path):
    current = {"value": NOW}

    def clock():
        return current["value"]

    repository = _repository(tmp_path, clock=clock)
    created = _create(repository)
    first = repository.ensure_follow_up_coordination_request(created.id)
    current["value"] = LATER
    second = repository.ensure_follow_up_coordination_request(created.id)
    third = repository.ensure_follow_up_coordination_request(created.id)
    assert first == second == third
    assert first.created_at == "2026-09-30T12:00:00.000000Z"
    assert _count_requests(repository.database_path) == 1


def test_protocol_id_is_copied_from_the_durable_review_case(tmp_path):
    repository = _repository(tmp_path)
    post = _create(repository, case_id="SYN-FOLLOWUP-001")
    missed = _create(
        repository,
        case_id="SYN-FOLLOWUP-002",
        protocol=_protocol(
            protocol_id=MISSED_FOLLOW_UP_REVIEW_V1,
            resources=("Appointment/noshow-002",),
            reasons=("missed_follow_up_without_confirmed_replacement",),
        ),
    )
    post_request = repository.ensure_follow_up_coordination_request(post.id)
    missed_request = repository.ensure_follow_up_coordination_request(missed.id)
    assert post_request.protocol_id == POST_CONSULTATION_RESULT_REVIEW_V1
    assert missed_request.protocol_id == MISSED_FOLLOW_UP_REVIEW_V1
    assert post_request.action_identity != missed_request.action_identity
    assert _count_requests(repository.database_path) == 2


def test_unknown_review_case_fails_without_insert(tmp_path):
    repository = _repository(tmp_path)
    missing = "10000000-0000-4000-8000-000000000099"
    with pytest.raises(ReviewCaseNotFound):
        repository.ensure_follow_up_coordination_request(missing)
    assert repository.get_follow_up_coordination_request(missing) is None
    assert _count_requests(repository.database_path) == 0


def test_unpersistable_protocol_fails_without_insert(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository, protocol=_protocol(protocol_id="OTHER_PROTOCOL"))
    before = _snapshot(repository.database_path, created.id)
    with pytest.raises(CoordinationRequestNotPersistable):
        repository.ensure_follow_up_coordination_request(created.id)
    assert _count_requests(repository.database_path) == 0
    assert _snapshot(repository.database_path, created.id) == before


def test_coordination_record_contains_only_approved_fields(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    stored = repository.ensure_follow_up_coordination_request(created.id)
    assert set(FollowUpCoordinationRequest.__dataclass_fields__) == APPROVED_COLUMNS
    with sqlite3.connect(repository.database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(follow_up_coordination_requests)")
        }
        raw = json.dumps(
            connection.execute(
                "SELECT * FROM follow_up_coordination_requests WHERE id = ?",
                (stored.id,),
            ).fetchone()
        )
    assert columns == APPROVED_COLUMNS
    assert "version" not in columns
    for token in (
        "resourceType",
        "valueString",
        "Patient/",
        "Gemini",
        "prompt",
        "diagnosis",
        "treatment",
        "mrn",
        "birthDate",
    ):
        assert token not in raw


def test_schema_rejects_other_action_states_and_missing_review_case(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    identity = build_coordination_action_identity(created.id)
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO follow_up_coordination_requests (
                    id, action_identity, review_case_id, protocol_id,
                    action_type, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'sent', ?)
                """,
                (
                    "10000000-0000-4000-8000-000000000021",
                    identity,
                    created.id,
                    created.protocol_id,
                    CoordinationActionType.CREATE_FOLLOW_UP_COORDINATION_REQUEST.value,
                    "2026-09-30T12:00:00.000000Z",
                ),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO follow_up_coordination_requests (
                    id, action_identity, review_case_id, protocol_id,
                    action_type, status, created_at
                ) VALUES (?, ?, ?, ?, 'send_whatsapp', 'requested', ?)
                """,
                (
                    "10000000-0000-4000-8000-000000000022",
                    "a" * 64,
                    created.id,
                    created.protocol_id,
                    "2026-09-30T12:00:00.000000Z",
                ),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO follow_up_coordination_requests (
                    id, action_identity, review_case_id, protocol_id,
                    action_type, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'requested', ?)
                """,
                (
                    "10000000-0000-4000-8000-000000000023",
                    "b" * 64,
                    "10000000-0000-4000-8000-000000000099",
                    POST_CONSULTATION_RESULT_REVIEW_V1,
                    CoordinationActionType.CREATE_FOLLOW_UP_COORDINATION_REQUEST.value,
                    "2026-09-30T12:00:00.000000Z",
                ),
            )


def test_concurrent_ensure_creates_one_request(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    workers = 8
    barrier = threading.Barrier(workers)

    def create():
        barrier.wait(timeout=10)
        return repository.ensure_follow_up_coordination_request(created.id)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(lambda _index: create(), range(workers)))
    assert len({result.id for result in results}) == 1
    assert len({result.action_identity for result in results}) == 1
    assert len({result.created_at for result in results}) == 1
    assert results[0] == repository.get_follow_up_coordination_request(created.id)
    assert _count_requests(repository.database_path) == 1


def test_ensure_does_not_change_the_closed_review_case(tmp_path):
    repository = _repository(tmp_path)
    created = _create(repository)
    closed = repository.close(
        created.id,
        expected_version=1,
        outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED,
    )
    before_case = repository.get(closed.id)
    before_events = repository.events(closed.id)
    before_raw = _snapshot(repository.database_path, closed.id)
    stored = repository.ensure_follow_up_coordination_request(closed.id)
    assert stored.protocol_id == closed.protocol_id
    assert repository.get(closed.id) == before_case
    assert repository.events(closed.id) == before_events
    assert _snapshot(repository.database_path, closed.id) == before_raw
    assert before_case.status is ReviewCaseStatus.CLOSED
    assert before_case.outcome is ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED
    assert before_case.version == 2
    assert len(before_events) == 2


def test_coordination_module_does_not_call_model_or_external_systems():
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
    ):
        assert token not in source
    assert "fastapi" not in source
    assert "human_review_client" not in source
