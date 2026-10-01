"""SQLite persistence adapter for operational follow-up review cases."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.followup_review import (
    FollowUpReviewCase,
    FollowUpReviewCaseEvent,
    FollowUpReviewTrigger,
    ReviewCaseDetail,
    ReviewCaseConflict,
    ReviewCaseNotFound,
    ReviewCasePage,
    ReviewCaseStatus,
    ReviewEventType,
    ReviewOutcome,
    ReviewPersistenceUnavailable,
    ReviewStoreInitializationError,
    canonical_matched_resources,
    canonical_reason_codes,
    utc_now,
    utc_timestamp,
    validate_review_case,
    validate_review_detail,
    validate_review_event,
    validate_review_case_id,
    validate_trigger,
)


SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 5_000
_MIGRATION = Path(__file__).with_name("migrations") / "001_follow_up_review.sql"
_TABLES = ("follow_up_review_cases", "follow_up_review_case_events")


class SQLiteFollowUpReviewCaseRepository:
    """Single-instance V1 repository using one SQLite connection per operation."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        clock: Callable[[], datetime] = utc_now,
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        raw_path = str(database_path)
        if not raw_path.strip() or raw_path == ":memory:":
            raise ReviewStoreInitializationError("review database must be a file-backed path")
        self.database_path = Path(raw_path)
        self._clock = clock
        self._id_factory = id_factory

    def initialize(self) -> None:
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection_scope() as connection:
                mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                if str(mode).lower() != "wal":
                    raise ReviewStoreInitializationError("review database cannot enable WAL mode")
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version > SCHEMA_VERSION:
                    raise ReviewStoreInitializationError("review database schema version is unsupported")
                if version == 0:
                    migration = _MIGRATION.read_text(encoding="utf-8")
                    try:
                        connection.executescript(migration)
                    except sqlite3.DatabaseError:
                        if connection.in_transaction:
                            connection.rollback()
                        raise
                self._validate_schema(connection)
        except ReviewStoreInitializationError:
            raise
        except (OSError, sqlite3.DatabaseError, UnicodeError) as exc:
            raise ReviewStoreInitializationError("review database initialization failed") from exc

    def ensure(self, trigger: FollowUpReviewTrigger) -> FollowUpReviewCase:
        validate_trigger(trigger)
        created_at = utc_timestamp(self._clock)
        review_case_id = str(self._id_factory())
        event_id = str(self._id_factory())
        reasons_json = _json_array(trigger.reason_codes)
        resources_json = _json_array(trigger.matched_resources)
        try:
            with self._connection_scope() as connection:
                connection.execute("BEGIN IMMEDIATE")
                inserted = connection.execute(
                    """
                    INSERT INTO follow_up_review_cases (
                        id, review_identity, case_id, protocol_id,
                        protocol_evaluation_status, reason_codes_json,
                        matched_resources_json, status, outcome, version,
                        created_at, updated_at, closed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', NULL, 1, ?, ?, NULL)
                    ON CONFLICT(review_identity) DO NOTHING
                    """,
                    (
                        review_case_id,
                        trigger.review_identity,
                        trigger.case_id,
                        trigger.protocol_id,
                        trigger.protocol_evaluation_status,
                        reasons_json,
                        resources_json,
                        created_at,
                        created_at,
                    ),
                ).rowcount
                if inserted == 1:
                    connection.execute(
                        """
                        INSERT INTO follow_up_review_case_events (
                            event_id, review_case_id, case_version, event_type,
                            from_status, to_status, outcome, occurred_at
                        ) VALUES (?, ?, 1, 'created', NULL, 'open', NULL, ?)
                        """,
                        (event_id, review_case_id, created_at),
                    )
                row = connection.execute(
                    "SELECT * FROM follow_up_review_cases WHERE review_identity = ?",
                    (trigger.review_identity,),
                ).fetchone()
                event_rows = (
                    []
                    if row is None
                    else connection.execute(
                        """
                        SELECT * FROM follow_up_review_case_events
                        WHERE review_case_id = ? ORDER BY case_version ASC
                        """,
                        (row["id"],),
                    ).fetchall()
                )
                detail = None if row is None else _detail_from_rows(row, event_rows)
                connection.commit()
            if detail is None:
                raise ReviewPersistenceUnavailable
            return detail.case
        except ReviewPersistenceUnavailable:
            raise
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise ReviewPersistenceUnavailable from exc

    def get(self, review_case_id: str) -> FollowUpReviewCase | None:
        validate_review_case_id(review_case_id)
        try:
            with self._connection_scope() as connection:
                row = connection.execute(
                    "SELECT * FROM follow_up_review_cases WHERE id = ?",
                    (review_case_id,),
                ).fetchone()
            return None if row is None else _case_from_row(row)
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise ReviewPersistenceUnavailable from exc

    def get_detail(self, review_case_id: str) -> ReviewCaseDetail | None:
        validate_review_case_id(review_case_id)
        try:
            with self._connection_scope() as connection:
                connection.execute("BEGIN")
                row = connection.execute(
                    "SELECT * FROM follow_up_review_cases WHERE id = ?",
                    (review_case_id,),
                ).fetchone()
                if row is None:
                    connection.commit()
                    return None
                event_rows = connection.execute(
                    """
                    SELECT * FROM follow_up_review_case_events
                    WHERE review_case_id = ? ORDER BY case_version ASC
                    """,
                    (review_case_id,),
                ).fetchall()
                connection.commit()
            return _detail_from_rows(row, event_rows)
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise ReviewPersistenceUnavailable from exc

    def list_cases(
        self,
        *,
        status: ReviewCaseStatus,
        case_id: str | None,
        limit: int,
        after: tuple[str, str] | None,
    ) -> ReviewCasePage:
        if not 1 <= limit <= 100:
            raise ValueError("limit is outside the supported range")
        clauses = ["status = ?"]
        parameters: list[object] = [status.value]
        if case_id is not None:
            clauses.append("case_id = ?")
            parameters.append(case_id)
        if after is not None:
            clauses.append("(created_at > ? OR (created_at = ? AND id > ?))")
            parameters.extend((after[0], after[0], after[1]))
        parameters.append(limit + 1)
        query = (
            "SELECT * FROM follow_up_review_cases WHERE "
            + " AND ".join(clauses)
            + " ORDER BY created_at ASC, id ASC LIMIT ?"
        )
        try:
            with self._connection_scope() as connection:
                rows = connection.execute(query, parameters).fetchall()
            cases = tuple(_case_from_row(row) for row in rows[:limit])
            next_position = None
            if len(rows) > limit and cases:
                last = cases[-1]
                next_position = (last.created_at, last.id)
            return ReviewCasePage(items=cases, next_position=next_position)
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise ReviewPersistenceUnavailable from exc

    def close(
        self,
        review_case_id: str,
        *,
        expected_version: int,
        outcome: ReviewOutcome,
    ) -> FollowUpReviewCase:
        validate_review_case_id(review_case_id)
        if expected_version < 1:
            raise ValueError("expected version must be positive")
        closed_at = utc_timestamp(self._clock)
        event_id = str(self._id_factory())
        try:
            with self._connection_scope() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM follow_up_review_cases WHERE id = ?",
                    (review_case_id,),
                ).fetchone()
                if row is None:
                    connection.rollback()
                    raise ReviewCaseNotFound
                current_event_rows = connection.execute(
                    """
                    SELECT * FROM follow_up_review_case_events
                    WHERE review_case_id = ? ORDER BY case_version ASC
                    """,
                    (review_case_id,),
                ).fetchall()
                current = _detail_from_rows(row, current_event_rows).case
                if current.status is ReviewCaseStatus.CLOSED:
                    connection.commit()
                    if current.outcome is outcome:
                        return current
                    raise ReviewCaseConflict
                if current.version != expected_version:
                    connection.rollback()
                    raise ReviewCaseConflict
                next_version = current.version + 1
                changed = connection.execute(
                    """
                    UPDATE follow_up_review_cases
                    SET status = 'closed', outcome = ?, version = ?,
                        updated_at = ?, closed_at = ?
                    WHERE id = ? AND status = 'open' AND version = ?
                    """,
                    (
                        outcome.value,
                        next_version,
                        closed_at,
                        closed_at,
                        review_case_id,
                        expected_version,
                    ),
                ).rowcount
                if changed != 1:
                    connection.rollback()
                    raise ReviewCaseConflict
                connection.execute(
                    """
                    INSERT INTO follow_up_review_case_events (
                        event_id, review_case_id, case_version, event_type,
                        from_status, to_status, outcome, occurred_at
                    ) VALUES (?, ?, ?, 'closed', 'open', 'closed', ?, ?)
                    """,
                    (event_id, review_case_id, next_version, outcome.value, closed_at),
                )
                updated = connection.execute(
                    "SELECT * FROM follow_up_review_cases WHERE id = ?",
                    (review_case_id,),
                ).fetchone()
                updated_event_rows = connection.execute(
                    """
                    SELECT * FROM follow_up_review_case_events
                    WHERE review_case_id = ? ORDER BY case_version ASC
                    """,
                    (review_case_id,),
                ).fetchall()
                detail = (
                    None
                    if updated is None
                    else _detail_from_rows(updated, updated_event_rows)
                )
                connection.commit()
            if detail is None:
                raise ReviewPersistenceUnavailable
            return detail.case
        except (ReviewCaseConflict, ReviewPersistenceUnavailable):
            raise
        except ReviewCaseNotFound:
            raise
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise ReviewPersistenceUnavailable from exc

    def events(self, review_case_id: str) -> tuple[FollowUpReviewCaseEvent, ...]:
        detail = self.get_detail(review_case_id)
        return () if detail is None else detail.events

    @contextmanager
    def _connection_scope(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        except BaseException:
            try:
                connection.close()
            except Exception:
                pass
            raise
        else:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=BUSY_TIMEOUT_MS / 1000,
            isolation_level=None,
        )
        try:
            connection.row_factory = sqlite3.Row
            connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA foreign_keys=ON")
            if int(connection.execute("PRAGMA foreign_keys").fetchone()[0]) != 1:
                raise sqlite3.OperationalError("foreign key enforcement unavailable")
        except BaseException:
            try:
                connection.close()
            except Exception:
                pass
            raise
        return connection

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version != SCHEMA_VERSION:
            raise ReviewStoreInitializationError("review database schema version is unsupported")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ReviewStoreInitializationError("review database integrity check failed")
        if _schema_contract(connection) != _migration_schema_contract():
            raise ReviewStoreInitializationError("review database schema is invalid")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ReviewStoreInitializationError("review database foreign key check failed")


def _migration_schema_contract() -> tuple[object, ...]:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(_MIGRATION.read_text(encoding="utf-8"))
        return _schema_contract(connection)
    finally:
        connection.close()


def _schema_contract(connection: sqlite3.Connection) -> tuple[object, ...]:
    objects = tuple(
        (
            row[0],
            row[1],
            row[2],
            _normalize_schema_sql(row[3]),
        )
        for row in connection.execute(
            """
            SELECT type, name, tbl_name, sql FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        ).fetchall()
    )
    columns = tuple(
        (
            table,
            tuple(
                (row[1], str(row[2]).upper(), int(row[3]), row[4], int(row[5]))
                for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
            ),
        )
        for table in _TABLES
    )
    indexes = tuple((table, _index_contract(connection, table)) for table in _TABLES)
    foreign_keys = tuple(
        (
            table,
            tuple(
                tuple(row[index] for index in range(2, 8))
                for row in connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
            ),
        )
        for table in _TABLES
    )
    return objects, columns, indexes, foreign_keys


def _index_contract(
    connection: sqlite3.Connection, table: str
) -> tuple[tuple[object, ...], ...]:
    indexes: list[tuple[object, ...]] = []
    for row in connection.execute(f"PRAGMA index_list({table})").fetchall():
        name = str(row[1])
        columns = tuple(
            index_row[2]
            for index_row in connection.execute(
                "SELECT seqno, cid, name FROM pragma_index_info(?) ORDER BY seqno",
                (name,),
            ).fetchall()
        )
        indexes.append((name, int(row[2]), str(row[3]), int(row[4]), columns))
    return tuple(sorted(indexes, key=lambda item: str(item[0])))


def _normalize_schema_sql(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReviewStoreInitializationError("review database schema is invalid")
    return value.strip()


def _json_array(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def _load_json_array(raw: object, *, resources: bool) -> tuple[str, ...]:
    if not isinstance(raw, str):
        raise ValueError("persisted provenance is invalid")
    parsed = json.loads(raw)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("persisted provenance is invalid")
    canonical = (
        canonical_matched_resources(parsed)
        if resources
        else canonical_reason_codes(parsed)
    )
    if list(canonical) != parsed or _json_array(canonical) != raw:
        raise ValueError("persisted provenance is not canonical")
    return canonical


def _case_from_row(row: sqlite3.Row) -> FollowUpReviewCase:
    raw_review_case_id = str(row["id"])
    review_case_id = validate_review_case_id(raw_review_case_id)
    if review_case_id != raw_review_case_id:
        raise ValueError("persisted review case id is not canonical")
    outcome = None if row["outcome"] is None else ReviewOutcome(row["outcome"])
    status = ReviewCaseStatus(row["status"])
    version = int(row["version"])
    if version not in {1, 2}:
        raise ValueError("persisted version is invalid")
    reasons = _load_json_array(row["reason_codes_json"], resources=False)
    resources = _load_json_array(row["matched_resources_json"], resources=True)
    case_id = str(row["case_id"])
    protocol_id = str(row["protocol_id"])
    review_identity = str(row["review_identity"])
    case = FollowUpReviewCase(
        id=review_case_id,
        review_identity=review_identity,
        case_id=case_id,
        protocol_id=protocol_id,
        protocol_evaluation_status=str(row["protocol_evaluation_status"]),
        reason_codes=reasons,
        matched_resources=resources,
        status=status,
        outcome=outcome,
        version=version,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        closed_at=None if row["closed_at"] is None else str(row["closed_at"]),
    )
    return validate_review_case(case)


def _event_from_row(row: sqlite3.Row) -> FollowUpReviewCaseEvent:
    raw_event_id = str(row["event_id"])
    raw_review_case_id = str(row["review_case_id"])
    event = FollowUpReviewCaseEvent(
        event_id=validate_review_case_id(raw_event_id),
        review_case_id=validate_review_case_id(raw_review_case_id),
        case_version=int(row["case_version"]),
        event_type=ReviewEventType(row["event_type"]),
        from_status=None if row["from_status"] is None else ReviewCaseStatus(row["from_status"]),
        to_status=ReviewCaseStatus(row["to_status"]),
        outcome=None if row["outcome"] is None else ReviewOutcome(row["outcome"]),
        occurred_at=str(row["occurred_at"]),
    )
    if event.event_id != raw_event_id or event.review_case_id != raw_review_case_id:
        raise ValueError("persisted review event identifiers are not canonical")
    return validate_review_event(event)


def _detail_from_rows(
    case_row: sqlite3.Row,
    event_rows: list[sqlite3.Row],
) -> ReviewCaseDetail:
    return validate_review_detail(
        ReviewCaseDetail(
            case=_case_from_row(case_row),
            events=tuple(_event_from_row(event) for event in event_rows),
        )
    )
