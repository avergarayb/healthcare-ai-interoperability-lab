"""SQLite persistence adapter for operational follow-up review cases."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.followup_coordination_action import (
    CoordinationActionType,
    CoordinationRequestNotPersistable,
    CoordinationRequestStatus,
    FollowUpCoordinationRequest,
    build_coordination_action_identity,
    persistable_protocol_id,
    validate_coordination_request,
)
from app.followup_coordination_workflow import (
    CoordinationQueueItem,
    CoordinationRequestDetail,
    CoordinationRequestEvent,
    CoordinationRequestNotFound,
    CoordinationTransitionRejected,
    CoordinationTransitionResult,
    transition_is_allowed,
    validate_coordination_event,
)
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
    validate_utc_timestamp,
)
from app.human_attribution import (
    COORDINATION_REQUEST_CREATED,
    REVIEW_CASE_CLOSED,
    DevelopmentPrincipalSnapshot,
    StoredDevelopmentAttribution,
    validate_development_principal_snapshot,
)


SCHEMA_VERSION = 4
BUSY_TIMEOUT_MS = 5_000
_MIGRATION = Path(__file__).with_name("migrations") / "001_follow_up_review.sql"
_COORDINATION_REQUEST_MIGRATION = (
    Path(__file__).with_name("migrations") / "002_follow_up_coordination_request.sql"
)
_HUMAN_ATTRIBUTION_MIGRATION = (
    Path(__file__).with_name("migrations") / "003_follow_up_human_attribution.sql"
)
_COORDINATION_WORKFLOW_MIGRATION = (
    Path(__file__).with_name("migrations") / "004_follow_up_coordination_workflow.sql"
)
_TABLES = (
    "follow_up_review_cases",
    "follow_up_review_case_events",
    "follow_up_coordination_requests",
    "follow_up_human_attributions",
    "follow_up_coordination_request_events",
)


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
                    _apply_migration(connection, _MIGRATION)
                    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version == 1:
                    _apply_migration(connection, _COORDINATION_REQUEST_MIGRATION)
                    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version == 2:
                    _apply_migration(connection, _HUMAN_ATTRIBUTION_MIGRATION)
                    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version == 3:
                    _apply_migration(connection, _COORDINATION_WORKFLOW_MIGRATION)
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
        attribution: DevelopmentPrincipalSnapshot | None = None,
    ) -> FollowUpReviewCase:
        validate_review_case_id(review_case_id)
        if expected_version < 1:
            raise ValueError("expected version must be positive")
        if attribution is not None:
            validate_development_principal_snapshot(attribution)
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
                if attribution is not None:
                    _insert_human_attribution(
                        connection,
                        attribution_id=str(self._id_factory()),
                        review_case_id=review_case_id,
                        operation=REVIEW_CASE_CLOSED,
                        subject_version=next_version,
                        coordination_request_id=None,
                        snapshot=attribution,
                        occurred_at=closed_at,
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

    def ensure_follow_up_coordination_request(
        self,
        review_case_id: str,
        attribution: DevelopmentPrincipalSnapshot | None = None,
    ) -> FollowUpCoordinationRequest:
        """Insert one coordination request, or return the row already stored.

        protocol_id is copied from the review case row in this transaction.
        The review case itself is not updated. A snapshot is stored only when
        this transaction inserts the request.
        """
        validate_review_case_id(review_case_id)
        if attribution is not None:
            validate_development_principal_snapshot(attribution)
        action_identity = build_coordination_action_identity(review_case_id)
        request_id = str(self._id_factory())
        created_at = utc_timestamp(self._clock)
        try:
            with self._connection_scope() as connection:
                connection.execute("BEGIN IMMEDIATE")
                case_row = connection.execute(
                    "SELECT protocol_id FROM follow_up_review_cases WHERE id = ?",
                    (review_case_id,),
                ).fetchone()
                if case_row is None:
                    connection.rollback()
                    raise ReviewCaseNotFound
                protocol_id = persistable_protocol_id(str(case_row["protocol_id"]))
                inserted = connection.execute(
                    """
                    INSERT INTO follow_up_coordination_requests (
                        id, action_identity, review_case_id, protocol_id,
                        action_type, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(action_identity) DO NOTHING
                    """,
                    (
                        request_id,
                        action_identity,
                        review_case_id,
                        protocol_id,
                        CoordinationActionType.CREATE_FOLLOW_UP_COORDINATION_REQUEST.value,
                        CoordinationRequestStatus.REQUESTED.value,
                        created_at,
                    ),
                ).rowcount
                if inserted == 1 and attribution is not None:
                    _insert_human_attribution(
                        connection,
                        attribution_id=str(self._id_factory()),
                        review_case_id=review_case_id,
                        operation=COORDINATION_REQUEST_CREATED,
                        subject_version=None,
                        coordination_request_id=request_id,
                        snapshot=attribution,
                        occurred_at=created_at,
                    )
                stored = connection.execute(
                    """
                    SELECT * FROM follow_up_coordination_requests
                    WHERE action_identity = ?
                    """,
                    (action_identity,),
                ).fetchone()
                connection.commit()
            if stored is None:
                raise ReviewPersistenceUnavailable
            return _coordination_request_from_row(stored)
        except (
            ReviewCaseNotFound,
            CoordinationRequestNotPersistable,
            ReviewPersistenceUnavailable,
        ):
            raise
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise ReviewPersistenceUnavailable from exc

    def get_follow_up_coordination_request(
        self, review_case_id: str
    ) -> FollowUpCoordinationRequest | None:
        validate_review_case_id(review_case_id)
        try:
            with self._connection_scope() as connection:
                row = connection.execute(
                    """
                    SELECT * FROM follow_up_coordination_requests
                    WHERE review_case_id = ? AND action_type = ?
                    """,
                    (
                        review_case_id,
                        CoordinationActionType.CREATE_FOLLOW_UP_COORDINATION_REQUEST.value,
                    ),
                ).fetchone()
            return None if row is None else _coordination_request_from_row(row)
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise ReviewPersistenceUnavailable from exc

    def list_follow_up_coordination_requests(
        self,
        *,
        limit: int,
        after: tuple[str, str] | None = None,
    ) -> tuple[CoordinationQueueItem, ...]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("coordination queue limit is invalid")
        parameters: list[object] = []
        where = ""
        if after is not None:
            created_at, request_id = after
            validate_utc_timestamp(created_at)
            validate_review_case_id(request_id)
            where = "WHERE r.created_at < ? OR (r.created_at = ? AND r.id > ?)"
            parameters.extend((created_at, created_at, request_id))
        parameters.append(limit)
        try:
            with self._connection_scope() as connection:
                rows = connection.execute(
                    f"""
                    SELECT r.*, c.case_id
                    FROM follow_up_coordination_requests AS r
                    JOIN follow_up_review_cases AS c ON c.id = r.review_case_id
                    {where}
                    ORDER BY r.created_at DESC, r.id ASC
                    LIMIT ?
                    """,
                    parameters,
                ).fetchall()
            return tuple(_coordination_queue_item(row) for row in rows)
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise ReviewPersistenceUnavailable from exc

    def get_coordination_request_detail(self, request_id: str) -> CoordinationRequestDetail | None:
        validate_review_case_id(request_id)
        try:
            with self._connection_scope() as connection:
                row = connection.execute(
                    """
                    SELECT r.*, c.case_id, c.status AS review_status
                    FROM follow_up_coordination_requests AS r
                    JOIN follow_up_review_cases AS c ON c.id = r.review_case_id
                    WHERE r.id = ?
                    """,
                    (request_id,),
                ).fetchone()
                if row is None:
                    return None
                event_rows = connection.execute(
                    """
                    SELECT * FROM follow_up_coordination_request_events
                    WHERE coordination_request_id = ?
                    ORDER BY occurred_at ASC, event_id ASC
                    """,
                    (request_id,),
                ).fetchall()
            return CoordinationRequestDetail(
                request=_coordination_request_from_row(row),
                case_id=str(row["case_id"]),
                review_status=str(row["review_status"]),
                events=tuple(_coordination_event_from_row(event) for event in event_rows),
            )
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise ReviewPersistenceUnavailable from exc

    def transition_follow_up_coordination_request(
        self,
        request_id: str,
        *,
        expected_status: CoordinationRequestStatus,
        target_status: CoordinationRequestStatus,
        attribution: DevelopmentPrincipalSnapshot,
    ) -> CoordinationTransitionResult:
        """Move one stored request one allowed step, or return it unchanged.

        A repeat of the same target does not insert another event. Any other
        status is rejected and leaves the row unchanged.
        """
        validate_review_case_id(request_id)
        validate_development_principal_snapshot(attribution)
        if not transition_is_allowed(expected_status, target_status):
            raise CoordinationTransitionRejected
        occurred_at = utc_timestamp(self._clock)
        event_id = str(self._id_factory())
        try:
            with self._connection_scope() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = connection.execute(
                    """
                    SELECT * FROM follow_up_coordination_requests
                    WHERE id = ?
                    """,
                    (request_id,),
                ).fetchone()
                if current is None:
                    connection.rollback()
                    raise CoordinationRequestNotFound
                status = CoordinationRequestStatus(str(current["status"]))
                if status is target_status:
                    connection.commit()
                    return CoordinationTransitionResult(
                        request=_coordination_request_from_row(current),
                        applied=False,
                    )
                if status is not expected_status:
                    connection.rollback()
                    raise CoordinationTransitionRejected
                updated = connection.execute(
                    """
                    UPDATE follow_up_coordination_requests
                    SET status = ?
                    WHERE id = ? AND status = ?
                    """,
                    (target_status.value, request_id, expected_status.value),
                ).rowcount
                if updated != 1:
                    connection.rollback()
                    raise CoordinationTransitionRejected
                connection.execute(
                    """
                    INSERT INTO follow_up_coordination_request_events (
                        event_id, coordination_request_id, review_case_id,
                        from_status, to_status, principal_id, authenticator_id,
                        session_id, occurred_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        request_id,
                        str(current["review_case_id"]),
                        expected_status.value,
                        target_status.value,
                        attribution.principal_id,
                        attribution.authenticator_id,
                        attribution.session_id,
                        occurred_at,
                    ),
                )
                stored = connection.execute(
                    "SELECT * FROM follow_up_coordination_requests WHERE id = ?",
                    (request_id,),
                ).fetchone()
                connection.commit()
            if stored is None:
                raise ReviewPersistenceUnavailable
            return CoordinationTransitionResult(
                request=_coordination_request_from_row(stored),
                applied=True,
            )
        except (CoordinationRequestNotFound, CoordinationTransitionRejected, ReviewPersistenceUnavailable):
            raise
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise ReviewPersistenceUnavailable from exc

    def list_human_attributions(
        self, review_case_id: str
    ) -> tuple[StoredDevelopmentAttribution, ...]:
        validate_review_case_id(review_case_id)
        try:
            with self._connection_scope() as connection:
                rows = connection.execute(
                    """
                    SELECT operation, principal_id, occurred_at
                    FROM follow_up_human_attributions
                    WHERE review_case_id = ?
                    ORDER BY operation ASC
                    """,
                    (review_case_id,),
                ).fetchall()
            return tuple(
                StoredDevelopmentAttribution(
                    operation=str(row["operation"]),
                    principal_id=str(row["principal_id"]),
                    occurred_at=str(row["occurred_at"]),
                )
                for row in rows
            )
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise ReviewPersistenceUnavailable from exc

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
        connection.executescript(_COORDINATION_REQUEST_MIGRATION.read_text(encoding="utf-8"))
        connection.executescript(_HUMAN_ATTRIBUTION_MIGRATION.read_text(encoding="utf-8"))
        connection.executescript(_COORDINATION_WORKFLOW_MIGRATION.read_text(encoding="utf-8"))
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


def _apply_migration(connection: sqlite3.Connection, path: Path) -> None:
    try:
        connection.executescript(path.read_text(encoding="utf-8"))
    except sqlite3.DatabaseError:
        if connection.in_transaction:
            connection.rollback()
        raise


def _insert_human_attribution(
    connection: sqlite3.Connection,
    *,
    attribution_id: str,
    review_case_id: str,
    operation: str,
    subject_version: int | None,
    coordination_request_id: str | None,
    snapshot: DevelopmentPrincipalSnapshot,
    occurred_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO follow_up_human_attributions (
            attribution_id, review_case_id, operation, subject_version,
            coordination_request_id, principal_id, authenticator_id,
            session_id, occurred_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            attribution_id,
            review_case_id,
            operation,
            subject_version,
            coordination_request_id,
            snapshot.principal_id,
            snapshot.authenticator_id,
            snapshot.session_id,
            occurred_at,
        ),
    )


def _coordination_request_from_row(row: sqlite3.Row) -> FollowUpCoordinationRequest:
    raw_id = str(row["id"])
    raw_review_case_id = str(row["review_case_id"])
    request = FollowUpCoordinationRequest(
        id=validate_review_case_id(raw_id),
        action_identity=str(row["action_identity"]),
        review_case_id=validate_review_case_id(raw_review_case_id),
        protocol_id=str(row["protocol_id"]),
        action_type=CoordinationActionType(row["action_type"]),
        status=CoordinationRequestStatus(row["status"]),
        created_at=str(row["created_at"]),
    )
    if request.id != raw_id or request.review_case_id != raw_review_case_id:
        raise ValueError("persisted coordination request identifiers are not canonical")
    return validate_coordination_request(request)


def _coordination_queue_item(row: sqlite3.Row) -> CoordinationQueueItem:
    return CoordinationQueueItem(
        request=_coordination_request_from_row(row),
        case_id=str(row["case_id"]),
    )


def _coordination_event_from_row(row: sqlite3.Row) -> CoordinationRequestEvent:
    event = CoordinationRequestEvent(
        event_id=str(row["event_id"]),
        coordination_request_id=str(row["coordination_request_id"]),
        review_case_id=str(row["review_case_id"]),
        from_status=CoordinationRequestStatus(str(row["from_status"])),
        to_status=CoordinationRequestStatus(str(row["to_status"])),
        principal_id=str(row["principal_id"]),
        authenticator_id=str(row["authenticator_id"]),
        session_id=str(row["session_id"]),
        occurred_at=str(row["occurred_at"]),
    )
    return validate_coordination_event(event)


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
