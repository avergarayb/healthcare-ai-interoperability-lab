"""File-backed session store. One connection per operation. No HTTP."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.human_session import (
    HumanSession,
    HumanSessionStoreInitializationError,
    HumanSessionUnavailable,
    session_cleanup_cutoff,
    validate_human_session,
)


SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 5_000
_MIGRATION = Path(__file__).with_name("migrations") / "001_human_session.sql"
_TABLES = ("human_sessions",)


class SQLiteHumanSessionRepository:
    """Single-instance session repository. Stores token hashes, not raw tokens."""

    def __init__(self, database_path: str | Path) -> None:
        raw_path = str(database_path)
        if not raw_path.strip() or raw_path == ":memory:":
            raise HumanSessionStoreInitializationError("session database must be a file-backed path")
        self.database_path = Path(raw_path)

    def initialize(self) -> None:
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection_scope() as connection:
                mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                if str(mode).lower() != "wal":
                    raise HumanSessionStoreInitializationError("session database cannot enable WAL mode")
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version > SCHEMA_VERSION:
                    raise HumanSessionStoreInitializationError("session database schema version is unsupported")
                if version == 0:
                    _apply_migration(connection, _MIGRATION)
                self._validate_schema(connection)
        except HumanSessionStoreInitializationError:
            raise
        except (OSError, sqlite3.DatabaseError, UnicodeError) as exc:
            raise HumanSessionStoreInitializationError("session database initialization failed") from exc

    def insert(self, session: HumanSession, *, now: str) -> None:
        validate_human_session(session)
        if session.revoked_at is not None:
            raise HumanSessionUnavailable
        try:
            with self._connection_scope() as connection:
                connection.execute("BEGIN IMMEDIATE")
                _cleanup(connection, now)
                connection.execute(
                    """
                    INSERT INTO human_sessions (
                        session_id, token_hash, principal_id, display_name,
                        authenticator_id, issued_at, expires_at, revoked_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        session.session_id,
                        session.token_hash,
                        session.principal_id,
                        session.display_name,
                        session.authenticator_id,
                        session.issued_at,
                        session.expires_at,
                    ),
                )
                connection.commit()
        except HumanSessionUnavailable:
            raise
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise HumanSessionUnavailable from exc

    def get_by_token_hash(self, token_hash: str, *, now: str) -> HumanSession | None:
        try:
            with self._connection_scope() as connection:
                connection.execute("BEGIN IMMEDIATE")
                _cleanup(connection, now)
                row = connection.execute(
                    "SELECT * FROM human_sessions WHERE token_hash = ?",
                    (token_hash,),
                ).fetchone()
                connection.commit()
            return None if row is None else _session_from_row(row)
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise HumanSessionUnavailable from exc

    def revoke(self, token_hash: str, *, revoked_at: str, now: str) -> None:
        try:
            with self._connection_scope() as connection:
                connection.execute("BEGIN IMMEDIATE")
                _cleanup(connection, now)
                connection.execute(
                    """
                    UPDATE human_sessions
                    SET revoked_at = ?
                    WHERE token_hash = ? AND revoked_at IS NULL
                    """,
                    (revoked_at, token_hash),
                )
                connection.commit()
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            raise HumanSessionUnavailable from exc

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
            raise HumanSessionStoreInitializationError("session database schema version is unsupported")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise HumanSessionStoreInitializationError("session database integrity check failed")
        if _schema_contract(connection) != _migration_schema_contract():
            raise HumanSessionStoreInitializationError("session database schema is invalid")


def _cleanup(connection: sqlite3.Connection, now: str) -> None:
    connection.execute(
        "DELETE FROM human_sessions WHERE expires_at < ?",
        (session_cleanup_cutoff(now),),
    )


def _apply_migration(connection: sqlite3.Connection, path: Path) -> None:
    try:
        connection.executescript(path.read_text(encoding="utf-8"))
    except sqlite3.DatabaseError:
        if connection.in_transaction:
            connection.rollback()
        raise


def _session_from_row(row: sqlite3.Row) -> HumanSession:
    session = HumanSession(
        session_id=str(row["session_id"]),
        token_hash=str(row["token_hash"]),
        principal_id=str(row["principal_id"]),
        display_name=str(row["display_name"]),
        authenticator_id=str(row["authenticator_id"]),
        issued_at=str(row["issued_at"]),
        expires_at=str(row["expires_at"]),
        revoked_at=None if row["revoked_at"] is None else str(row["revoked_at"]),
    )
    return validate_human_session(session)


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
        (row[0], row[1], row[2], _normalize_schema_sql(row[3]))
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
    return objects, columns, indexes


def _index_contract(connection: sqlite3.Connection, table: str) -> tuple[tuple[object, ...], ...]:
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
        raise HumanSessionStoreInitializationError("session database schema is invalid")
    return value.strip()
