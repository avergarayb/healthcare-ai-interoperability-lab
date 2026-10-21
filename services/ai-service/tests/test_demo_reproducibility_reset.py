"""Controlled reset of disposable demo review rows. Temporary SQLite only."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

from app.followup_coordination_action import CoordinationRequestStatus
from app.followup_review import FollowUpReviewTrigger, ReviewOutcome, build_review_identity
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.human_attribution import DEVELOPMENT_AUTHENTICATOR_V1, DevelopmentPrincipalSnapshot
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1, REASON_MISSED
from app.post_consultation_review import POST_CONSULTATION_RESULT_REVIEW_V1

REPO_ROOT = Path(__file__).resolve().parents[3]
RESET_PATH = REPO_ROOT / "scripts" / "demo-reproducibility" / "reset_demo_cases.py"
DEMO_IDS = ("SYN-DEMO-101", "SYN-DEMO-102")
PRESERVED_IDS = (
    "SYN-FOLLOWUP-006",
    "SYN-FOLLOWUP-008",
    "SYN-FOLLOWUP-009",
    "SYN-FOLLOWUP-012",
)


def _load_reset():
    spec = importlib.util.spec_from_file_location("reset_demo_cases", RESET_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reset = _load_reset()


def _review_db(tmp_path: Path) -> Path:
    path = tmp_path / "follow-up-review.sqlite3"
    SQLiteFollowUpReviewCaseRepository(path).initialize()
    return path


def _paths(tmp_path: Path, review: Path) -> dict[str, str]:
    session = tmp_path / "human-session.sqlite3"
    knowledge = tmp_path / "institutional-knowledge.sqlite3"
    session.write_bytes(b"")
    knowledge.write_bytes(b"")
    return {
        "review_db_path": str(review.resolve()),
        "configured_review_db_path": str(review.resolve()),
        "session_db_path": str(session.resolve()),
        "knowledge_db_path": str(knowledge.resolve()),
    }


def _reset(tmp_path: Path, review: Path, **overrides):
    values = _paths(tmp_path, review)
    values["service_accepts_connections"] = lambda: False
    values.update(overrides)
    return reset.reset_demo_review(**values)


def _rows(path: Path, sql: str, parameters: tuple = ()) -> list[sqlite3.Row]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return list(connection.execute(sql, parameters))
    finally:
        connection.close()


def _seed_case(repository: SQLiteFollowUpReviewCaseRepository, case_id: str, protocol_id: str, resource: str):
    reason = (
        "post_consultation_result_requires_review"
        if protocol_id == POST_CONSULTATION_RESULT_REVIEW_V1
        else REASON_MISSED
    )
    return repository.ensure(
        FollowUpReviewTrigger(
            case_id=case_id,
            protocol_id=protocol_id,
            protocol_evaluation_status="matched",
            reason_codes=(reason,),
            matched_resources=(resource,),
            review_identity=build_review_identity(case_id, protocol_id, (resource,)),
        )
    )


def _principal() -> DevelopmentPrincipalSnapshot:
    return DevelopmentPrincipalSnapshot(
        principal_id="lab-reviewer",
        authenticator_id=DEVELOPMENT_AUTHENTICATOR_V1,
        session_id=str(uuid.uuid4()),
    )


def _close_with_attribution(repository: SQLiteFollowUpReviewCaseRepository, review_case_id: str, outcome: ReviewOutcome):
    repository.close(review_case_id, expected_version=1, outcome=outcome, attribution=_principal())


def _seed_preserved(repository: SQLiteFollowUpReviewCaseRepository) -> str:
    _seed_case(repository, "SYN-FOLLOWUP-006", POST_CONSULTATION_RESULT_REVIEW_V1, "Encounter/historical-enc-006")
    closed = _seed_case(
        repository,
        "SYN-FOLLOWUP-008",
        POST_CONSULTATION_RESULT_REVIEW_V1,
        "Observation/historical-obs-008",
    )
    _seed_case(repository, "SYN-FOLLOWUP-009", POST_CONSULTATION_RESULT_REVIEW_V1, "Encounter/historical-enc-009")
    _seed_case(repository, "SYN-FOLLOWUP-012", MISSED_FOLLOW_UP_REVIEW_V1, "Appointment/historical-appointment-012")
    _close_with_attribution(repository, closed.id, ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED)
    repository.ensure_follow_up_coordination_request(closed.id, attribution=_principal())
    return closed.id


def _seed_demo(repository: SQLiteFollowUpReviewCaseRepository, case_id: str, protocol_id: str, resource: str, *, coordination: bool):
    case = _seed_case(repository, case_id, protocol_id, resource)
    outcome = (
        ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED
        if coordination
        else ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION
    )
    _close_with_attribution(repository, case.id, outcome)
    if coordination:
        repository.ensure_follow_up_coordination_request(case.id, attribution=_principal())
    return case


def _preserved_dump(path: Path) -> dict[str, list[tuple]]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        cases = connection.execute(
            """
            SELECT * FROM follow_up_review_cases
            WHERE case_id NOT IN (?, ?)
            ORDER BY id
            """,
            DEMO_IDS,
        ).fetchall()
        ids = tuple(row["id"] for row in cases)
        tables = (
            "follow_up_review_case_events",
            "follow_up_coordination_requests",
            "follow_up_human_attributions",
            "follow_up_coordination_request_events",
        )
        if not ids:
            children = {table: [] for table in tables}
        else:
            marker = ",".join("?" for _ in ids)
            children = {
                table: [
                    tuple(row)
                    for row in connection.execute(
                        f"SELECT * FROM {table} WHERE review_case_id IN ({marker}) ORDER BY 1",
                        ids,
                    )
                ]
                for table in tables
            }
        return {"follow_up_review_cases": [tuple(row) for row in cases], **children}
    finally:
        connection.close()


def _guard_other_databases(monkeypatch: pytest.MonkeyPatch, session: Path, knowledge: Path) -> None:
    real_connect = sqlite3.connect

    def connect(database, *args, **kwargs):
        if database != ":memory:":
            resolved = Path(database).resolve()
            if resolved in {session.resolve(), knowledge.resolve()}:
                raise AssertionError("reset opened a non-review database")
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", connect)


def test_reset_removes_both_demo_cases_and_keeps_every_other_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review = _review_db(tmp_path)
    paths = _paths(tmp_path, review)
    _guard_other_databases(monkeypatch, Path(paths["session_db_path"]), Path(paths["knowledge_db_path"]))
    repository = SQLiteFollowUpReviewCaseRepository(review)
    _seed_preserved(repository)
    _seed_demo(
        repository,
        "SYN-DEMO-101",
        POST_CONSULTATION_RESULT_REVIEW_V1,
        "Encounter/syn-demo-enc-101",
        coordination=True,
    )
    _seed_demo(
        repository,
        "SYN-DEMO-102",
        MISSED_FOLLOW_UP_REVIEW_V1,
        "Appointment/syn-demo-noshow-102",
        coordination=False,
    )
    before = _preserved_dump(review)
    first = _reset(tmp_path, review)
    assert first.removed_case_ids == DEMO_IDS
    assert first.removed_cases == 2
    assert first.removed_attributions == 3
    assert first.removed_coordination_requests == 1
    assert first.removed_events == 4
    assert _rows(review, "SELECT id FROM follow_up_review_cases WHERE case_id IN (?, ?)", DEMO_IDS) == []
    assert _preserved_dump(review) == before
    assert {row["case_id"] for row in _rows(review, "SELECT case_id FROM follow_up_review_cases")} == set(PRESERVED_IDS)
    second = _reset(tmp_path, review)
    assert second.removed_case_ids == ()
    assert second.removed_cases == second.removed_events == 0
    assert second.removed_attributions == second.removed_coordination_requests == 0
    assert _preserved_dump(review) == before


def test_reset_removes_a_single_demo_case(tmp_path: Path):
    review = _review_db(tmp_path)
    repository = SQLiteFollowUpReviewCaseRepository(review)
    _seed_preserved(repository)
    _seed_demo(
        repository,
        "SYN-DEMO-101",
        POST_CONSULTATION_RESULT_REVIEW_V1,
        "Encounter/syn-demo-enc-101",
        coordination=True,
    )
    before = _preserved_dump(review)
    report = _reset(tmp_path, review)
    assert report.removed_case_ids == ("SYN-DEMO-101",)
    assert report.removed_cases == 1
    assert _preserved_dump(review) == before
    assert _rows(review, "SELECT id FROM follow_up_review_cases WHERE case_id = 'SYN-DEMO-102'") == []


def test_reset_without_demo_cases_changes_nothing(tmp_path: Path):
    review = _review_db(tmp_path)
    repository = SQLiteFollowUpReviewCaseRepository(review)
    _seed_preserved(repository)
    before = _preserved_dump(review)
    report = _reset(tmp_path, review)
    assert report.removed_case_ids == ()
    assert report.removed_cases == 0
    assert _preserved_dump(review) == before


def test_wrong_protocol_aborts_without_deleting(tmp_path: Path):
    review = _review_db(tmp_path)
    repository = SQLiteFollowUpReviewCaseRepository(review)
    _seed_preserved(repository)
    _seed_case(repository, "SYN-DEMO-101", MISSED_FOLLOW_UP_REVIEW_V1, "Appointment/not-demo")
    _seed_demo(
        repository,
        "SYN-DEMO-102",
        MISSED_FOLLOW_UP_REVIEW_V1,
        "Appointment/syn-demo-noshow-102",
        coordination=False,
    )
    before = [tuple(row) for row in _rows(review, "SELECT * FROM follow_up_review_cases ORDER BY id")]
    with pytest.raises(reset.DemoResetAborted) as caught:
        _reset(tmp_path, review)
    assert caught.value.reason == "review_protocol_mismatch"
    after = [tuple(row) for row in _rows(review, "SELECT * FROM follow_up_review_cases ORDER BY id")]
    assert after == before


def test_duplicate_demo_case_aborts(tmp_path: Path):
    review = _review_db(tmp_path)
    repository = SQLiteFollowUpReviewCaseRepository(review)
    _seed_preserved(repository)
    _seed_case(repository, "SYN-DEMO-101", POST_CONSULTATION_RESULT_REVIEW_V1, "Encounter/syn-demo-enc-101")
    _seed_case(repository, "SYN-DEMO-101", POST_CONSULTATION_RESULT_REVIEW_V1, "Encounter/syn-demo-enc-101-b")
    before = _preserved_dump(review)
    demo_before = _rows(review, "SELECT id FROM follow_up_review_cases WHERE case_id = 'SYN-DEMO-101'")
    with pytest.raises(reset.DemoResetAborted) as caught:
        _reset(tmp_path, review)
    assert caught.value.reason == "ambiguous_relation"
    assert len(_rows(review, "SELECT id FROM follow_up_review_cases WHERE case_id = 'SYN-DEMO-101'")) == len(demo_before)
    assert _preserved_dump(review) == before


def test_ambiguous_attribution_aborts(tmp_path: Path):
    review = _review_db(tmp_path)
    repository = SQLiteFollowUpReviewCaseRepository(review)
    historical_id = _seed_preserved(repository)
    demo = _seed_demo(
        repository,
        "SYN-DEMO-101",
        POST_CONSULTATION_RESULT_REVIEW_V1,
        "Encounter/syn-demo-enc-101",
        coordination=True,
    )
    historical_request = _rows(
        review,
        "SELECT id FROM follow_up_coordination_requests WHERE review_case_id = ?",
        (historical_id,),
    )[0]["id"]
    connection = sqlite3.connect(review)
    connection.execute(
        """
        UPDATE follow_up_human_attributions
        SET coordination_request_id = ?
        WHERE review_case_id = ? AND operation = 'coordination_request_created'
        """,
        (historical_request, demo.id),
    )
    connection.commit()
    connection.close()
    before = [tuple(row) for row in _rows(review, "SELECT * FROM follow_up_human_attributions ORDER BY attribution_id")]
    with pytest.raises(reset.DemoResetAborted) as caught:
        _reset(tmp_path, review)
    assert caught.value.reason == "ambiguous_relation"
    after = [tuple(row) for row in _rows(review, "SELECT * FROM follow_up_human_attributions ORDER BY attribution_id")]
    assert after == before
    assert _rows(review, "SELECT id FROM follow_up_review_cases WHERE id = ?", (demo.id,))


def test_referential_integrity_failure_aborts(tmp_path: Path):
    review = _review_db(tmp_path)
    repository = SQLiteFollowUpReviewCaseRepository(review)
    demo = _seed_demo(
        repository,
        "SYN-DEMO-101",
        POST_CONSULTATION_RESULT_REVIEW_V1,
        "Encounter/syn-demo-enc-101",
        coordination=True,
    )
    connection = sqlite3.connect(review)
    connection.execute("PRAGMA foreign_keys=OFF")
    connection.execute(
        """
        INSERT INTO follow_up_review_case_events (
            event_id, review_case_id, case_version, event_type,
            from_status, to_status, outcome, occurred_at
        ) VALUES (?, ?, 1, 'created', NULL, 'open', NULL, ?)
        """,
        (str(uuid.uuid4()), str(uuid.uuid4()), "2026-10-08T16:00:00.000000Z"),
    )
    connection.commit()
    connection.close()
    with pytest.raises(reset.DemoResetAborted) as caught:
        _reset(tmp_path, review)
    assert caught.value.reason == "referential_integrity"
    assert _rows(review, "SELECT id FROM follow_up_review_cases WHERE id = ?", (demo.id,))


def test_schema_four_reset_keeps_historical_coordination_history(tmp_path: Path):
    review = _review_db(tmp_path)
    repository = SQLiteFollowUpReviewCaseRepository(review)
    historical_id = _seed_preserved(repository)
    historical_request = repository.get_follow_up_coordination_request(historical_id)
    assert historical_request is not None
    repository.transition_follow_up_coordination_request(
        historical_request.id,
        expected_status=CoordinationRequestStatus.REQUESTED,
        target_status=CoordinationRequestStatus.IN_PROGRESS,
        attribution=_principal(),
    )
    demo = _seed_demo(
        repository,
        "SYN-DEMO-101",
        POST_CONSULTATION_RESULT_REVIEW_V1,
        "Encounter/syn-demo-enc-101",
        coordination=True,
    )
    demo_request = repository.get_follow_up_coordination_request(demo.id)
    assert demo_request is not None
    repository.transition_follow_up_coordination_request(
        demo_request.id,
        expected_status=CoordinationRequestStatus.REQUESTED,
        target_status=CoordinationRequestStatus.IN_PROGRESS,
        attribution=_principal(),
    )
    before = _preserved_dump(review)
    assert before["follow_up_coordination_request_events"]
    with sqlite3.connect(review) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
    report = _reset(tmp_path, review)
    assert report.removed_case_ids == ("SYN-DEMO-101",)
    assert _preserved_dump(review) == before
    assert _rows(
        review,
        "SELECT event_id FROM follow_up_coordination_request_events WHERE review_case_id = ?",
        (demo.id,),
    ) == []
    with sqlite3.connect(review) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5


@pytest.mark.parametrize("version", [3, 6])
def test_incompatible_schema_is_left_unchanged(tmp_path: Path, version: int):
    review = _review_db(tmp_path)
    connection = sqlite3.connect(review)
    connection.execute(f"PRAGMA user_version = {int(version)}")
    connection.commit()
    connection.close()
    with pytest.raises(reset.DemoResetAborted) as caught:
        _reset(tmp_path, review)
    assert caught.value.reason == "schema_incompatible"
    assert sqlite3.connect(review).execute("PRAGMA user_version").fetchone()[0] == version


@pytest.mark.parametrize(
    ("path_kind", "reason"),
    [
        ("relative", "review_db_path_invalid"),
        ("missing", "review_db_missing"),
        ("session", "session_database"),
        ("knowledge", "knowledge_database"),
        ("unconfigured", "review_db_not_configured"),
    ],
)
def test_invalid_review_database_path(tmp_path: Path, path_kind: str, reason: str):
    review = _review_db(tmp_path)
    overrides: dict = {}
    if path_kind == "relative":
        overrides["review_db_path"] = "follow-up-review.sqlite3"
    elif path_kind == "missing":
        overrides["review_db_path"] = str(tmp_path / "missing.sqlite3")
    elif path_kind == "session":
        session = tmp_path / "human-session.sqlite3"
        session.write_bytes(b"")
        overrides["review_db_path"] = overrides["session_db_path"] = str(session.resolve())
    elif path_kind == "knowledge":
        knowledge = tmp_path / "institutional-knowledge.sqlite3"
        knowledge.write_bytes(b"")
        overrides["review_db_path"] = overrides["knowledge_db_path"] = str(knowledge.resolve())
    else:
        other = tmp_path / "other-review.sqlite3"
        other.write_bytes(b"")
        overrides["configured_review_db_path"] = str(other.resolve())
    with pytest.raises(reset.DemoResetAborted) as caught:
        _reset(tmp_path, review, **overrides)
    assert caught.value.reason == reason


def test_exclusive_lock_failure_aborts(tmp_path: Path):
    review = _review_db(tmp_path)
    holder = sqlite3.connect(review, timeout=0.1, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(reset.DemoResetAborted) as caught:
            _reset(tmp_path, review, busy_timeout_ms=200)
        assert caught.value.reason == "exclusive_lock_unavailable"
    finally:
        holder.rollback()
        holder.close()
    assert _rows(review, "SELECT id FROM follow_up_review_cases") == []


def test_active_service_aborts_before_opening_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review = _review_db(tmp_path)

    def connect(*_args, **_kwargs):
        raise AssertionError("sqlite opened")

    monkeypatch.setattr(sqlite3, "connect", connect)
    with pytest.raises(reset.DemoResetAborted) as caught:
        _reset(tmp_path, review, service_accepts_connections=lambda: True)
    assert caught.value.reason == "service_accepting_connections"


def test_delete_failure_rolls_back_the_whole_transaction(tmp_path: Path):
    review = _review_db(tmp_path)
    repository = SQLiteFollowUpReviewCaseRepository(review)
    _seed_preserved(repository)
    _seed_demo(
        repository,
        "SYN-DEMO-101",
        POST_CONSULTATION_RESULT_REVIEW_V1,
        "Encounter/syn-demo-enc-101",
        coordination=True,
    )
    before = [tuple(row) for row in _rows(review, "SELECT * FROM follow_up_human_attributions ORDER BY attribution_id")]
    cases_before = [tuple(row) for row in _rows(review, "SELECT * FROM follow_up_review_cases ORDER BY id")]

    def fail(step: str) -> None:
        if step == "follow_up_human_attributions":
            raise RuntimeError("injected delete failure")

    with pytest.raises(RuntimeError, match="injected delete failure"):
        _reset(tmp_path, review, after_delete_step=fail)
    attributions = [tuple(row) for row in _rows(review, "SELECT * FROM follow_up_human_attributions ORDER BY attribution_id")]
    cases = [tuple(row) for row in _rows(review, "SELECT * FROM follow_up_review_cases ORDER BY id")]
    assert attributions == before
    assert cases == cases_before


def test_reset_deletes_disposable_narratives_and_keeps_the_others(tmp_path: Path):
    review = _review_db(tmp_path)
    repository = SQLiteFollowUpReviewCaseRepository(review)
    preserved = _seed_case(
        repository,
        "SYN-FOLLOWUP-006",
        POST_CONSULTATION_RESULT_REVIEW_V1,
        "Encounter/historical-enc-006",
    )
    demo = _seed_demo(
        repository,
        "SYN-DEMO-101",
        POST_CONSULTATION_RESULT_REVIEW_V1,
        "Encounter/syn-demo-enc-101",
        coordination=False,
    )
    repository.record_narrative(preserved.id, "Preserved proposal.")
    repository.record_narrative(demo.id, "Disposable proposal.")
    before = repository.get(preserved.id)
    assert before is not None
    report = _reset(tmp_path, review)
    assert report.removed_case_ids == ("SYN-DEMO-101",)
    kept = repository.get(preserved.id)
    assert kept is not None
    assert kept.narrative_text == "Preserved proposal."
    assert kept.version == before.version
    assert kept.status is before.status
    assert repository.get(demo.id) is None
    assert _rows(
        review,
        "SELECT narrative_text FROM follow_up_review_narratives WHERE review_case_id = ?",
        (demo.id,),
    ) == []
    assert _rows(
        review,
        "SELECT origin, narrative_text FROM follow_up_review_narratives WHERE review_case_id = ?",
        (preserved.id,),
    )[0]["narrative_text"] == "Preserved proposal."


def test_reset_does_not_call_preparation_or_fhir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review = _review_db(tmp_path)
    source = RESET_PATH.read_text(encoding="utf-8")
    assert "prepare_demo_review" not in source
    assert "httpx" not in source
    assert "put_resource" not in source
    assert "unlink" not in source
    assert "os.remove" not in source
    prepare = reset._prepare_module()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("preparation was called")

    monkeypatch.setattr(prepare, "prepare_demo_review", forbidden)
    report = _reset(tmp_path, review)
    assert report.removed_cases == 0
