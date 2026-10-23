"""File-backed security audit store. One connection per operation. No HTTP.

The application API can append and read. It does not update or delete rows.
The database file itself is not tamper-proof.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.security_audit import (
    CONTRACT_VERSION,
    SecurityAuditEvent,
    SecurityAuditRejected,
    SecurityAuditStoreInitializationError,
    SecurityAuditUnavailable,
    metadata_from_json,
    metadata_json,
    validate_security_audit_event,
)


def audit_database_path(settings: object, session_repository: object | None = None) -> str:
    """Resolve the audit file without creating it.

    An explicit SECURITY_AUDIT_DB_PATH wins. Otherwise the file sits beside the
    session database that is actually open. A bare placeholder filename is not
    resolved against the process working directory.
    """
    configured = str(getattr(settings, "security_audit_db_path", "") or "").strip()
    if configured:
        if configured == ":memory:":
            raise SecurityAuditStoreInitializationError("audit database must be a file-backed path")
        return configured
    session_file = _open_session_file(session_repository)
    if session_file is not None:
        return str(session_file.resolve().parent / "security-audit.sqlite3")
    session_path = str(getattr(settings, "human_session_db_path", "") or "").strip()
    candidate = Path(session_path)
    if not session_path or session_path == ":memory:" or candidate.parent == Path("."):
        raise SecurityAuditStoreInitializationError("audit database path is not configured")
    return str(candidate.resolve().parent / "security-audit.sqlite3")


def _open_session_file(session_repository: object | None) -> Path | None:
    current = session_repository
    for _ in range(4):
        if current is None:
            return None
        values = getattr(current, "__dict__", {})
        found = values.get("database_path")
        if found:
            return Path(found)
        current = values.get("inner")
    return None


SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 5_000
_MIGRATION = Path(__file__).with_name("migrations") / "002_security_audit.sql"
_TABLE = "security_audit_events"


class SQLiteSecurityAuditRepository:
    """Single-instance append-only audit repository."""

    def __init__(self, database_path: str | Path) -> None:
        raw_path = str(database_path)
        if not raw_path.strip() or raw_path == ":memory:":
            raise SecurityAuditStoreInitializationError("audit database must be a file-backed path")
        self.database_path = Path(raw_path)

    def initialize(self) -> None:
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with self._scope() as connection:
                mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                if str(mode).lower() != "wal":
                    raise SecurityAuditStoreInitializationError("audit database cannot enable WAL mode")
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version > SCHEMA_VERSION:
                    raise SecurityAuditStoreInitializationError("audit database schema version is unsupported")
                if version == 0:
                    try:
                        connection.executescript(_MIGRATION.read_text(encoding="utf-8"))
                    except sqlite3.DatabaseError:
                        if connection.in_transaction:
                            connection.rollback()
                        raise
                self._require_table(connection)
        except SecurityAuditStoreInitializationError:
            raise
        except (OSError, sqlite3.DatabaseError, UnicodeError) as exc:
            raise SecurityAuditStoreInitializationError("audit database initialization failed") from exc

    def append(self, event: SecurityAuditEvent) -> SecurityAuditEvent:
        stored = validate_security_audit_event(event)
        try:
            with self._scope() as connection:
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        """
                        INSERT INTO security_audit_events (
                            event_id, timestamp_utc, event_type, actor_type, actor_id,
                            organization_id, source_service, resource_type, resource_reference,
                            action, outcome, reason_code, correlation_id, metadata_json,
                            contract_version
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            stored.event_id,
                            stored.timestamp_utc,
                            stored.event_type,
                            stored.actor_type,
                            stored.actor_id,
                            stored.organization_id,
                            stored.source_service,
                            stored.resource_type,
                            stored.resource_reference,
                            stored.action,
                            stored.outcome,
                            stored.reason_code,
                            stored.correlation_id,
                            metadata_json(stored.metadata),
                            stored.contract_version,
                        ),
                    )
                    connection.commit()
                except BaseException:
                    if connection.in_transaction:
                        connection.rollback()
                    raise
        except SecurityAuditRejected:
            raise
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise SecurityAuditUnavailable("audit event was not stored") from exc
        return stored

    def get(self, event_id: str) -> SecurityAuditEvent | None:
        try:
            with self._scope() as connection:
                row = connection.execute(
                    "SELECT * FROM security_audit_events WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
                return None if row is None else _event_from_row(row)
        except SecurityAuditRejected as exc:
            raise SecurityAuditUnavailable("audit event was not read") from exc
        except (sqlite3.DatabaseError, OSError) as exc:
            raise SecurityAuditUnavailable("audit event was not read") from exc

    def list_by_correlation(self, correlation_id: str) -> tuple[SecurityAuditEvent, ...]:
        try:
            with self._scope() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM security_audit_events
                    WHERE correlation_id = ?
                    ORDER BY timestamp_utc, rowid
                    """,
                    (correlation_id,),
                ).fetchall()
                return tuple(_event_from_row(row) for row in rows)
        except SecurityAuditRejected as exc:
            raise SecurityAuditUnavailable("audit events were not read") from exc
        except (sqlite3.DatabaseError, OSError) as exc:
            raise SecurityAuditUnavailable("audit events were not read") from exc

    @contextmanager
    def _scope(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            yield connection
        finally:
            connection.close()

    def _require_table(self, connection: sqlite3.Connection) -> None:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (_TABLE,),
        ).fetchone()
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if row is None or version != SCHEMA_VERSION:
            raise SecurityAuditStoreInitializationError("audit database schema is incomplete")
        if CONTRACT_VERSION != "security-audit-v1":
            raise SecurityAuditStoreInitializationError("audit contract version is unsupported")


def _event_from_row(row: sqlite3.Row) -> SecurityAuditEvent:
    organization = row["organization_id"]
    reference = row["resource_reference"]
    return validate_security_audit_event(
        SecurityAuditEvent(
            event_id=str(row["event_id"]),
            timestamp_utc=str(row["timestamp_utc"]),
            event_type=str(row["event_type"]),
            actor_type=str(row["actor_type"]),
            actor_id=str(row["actor_id"]),
            organization_id=None if organization is None else str(organization),
            source_service=str(row["source_service"]),
            resource_type=str(row["resource_type"]),
            resource_reference=None if reference is None else str(reference),
            action=str(row["action"]),
            outcome=str(row["outcome"]),
            reason_code=str(row["reason_code"]),
            correlation_id=str(row["correlation_id"]),
            metadata=metadata_from_json(str(row["metadata_json"])),
            contract_version=str(row["contract_version"]),
        )
    )
