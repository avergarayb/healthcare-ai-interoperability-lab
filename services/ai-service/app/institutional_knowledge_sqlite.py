"""SQLite index for synthetic institutional knowledge. Not the review-case store."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 5_000
_MIGRATION = Path(__file__).with_name("migrations") / "001_institutional_knowledge.sql"
_TABLES = (
    "knowledge_index_state",
    "institutional_documents",
    "institutional_chunks",
    "institutional_vectors",
)


class InstitutionalKnowledgeStoreError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class IndexState:
    ready: bool
    embedding_model: str
    vector_dimension: int
    corpus_fingerprint: str


class SQLiteInstitutionalKnowledgeIndex:
    """One connection per operation. Embedding calls stay outside these transactions."""

    def __init__(self, database_path: str | Path) -> None:
        raw_path = str(database_path)
        if not raw_path.strip() or raw_path == ":memory:":
            raise InstitutionalKnowledgeStoreError("index_not_ready")
        self.database_path = Path(raw_path)

    def initialize(self) -> None:
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection_scope() as connection:
                mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                if str(mode).lower() != "wal":
                    raise InstitutionalKnowledgeStoreError("index_not_ready")
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version > SCHEMA_VERSION:
                    raise InstitutionalKnowledgeStoreError("index_not_ready")
                if version == 0:
                    migration = _MIGRATION.read_text(encoding="utf-8")
                    try:
                        connection.executescript(migration)
                    except sqlite3.DatabaseError:
                        if connection.in_transaction:
                            connection.rollback()
                        raise
                self._validate_schema(connection)
        except InstitutionalKnowledgeStoreError:
            raise
        except (OSError, sqlite3.DatabaseError, UnicodeError) as exc:
            raise InstitutionalKnowledgeStoreError("index_not_ready") from exc

    def read_state(self) -> IndexState:
        with self._connection_scope() as connection:
            row = connection.execute(
                """
                SELECT ready, embedding_model, vector_dimension, corpus_fingerprint
                FROM knowledge_index_state
                WHERE id = 1
                """
            ).fetchone()
            if row is None:
                raise InstitutionalKnowledgeStoreError("index_not_ready")
            return IndexState(
                ready=int(row["ready"]) == 1,
                embedding_model=str(row["embedding_model"]),
                vector_dimension=int(row["vector_dimension"]),
                corpus_fingerprint=str(row["corpus_fingerprint"]),
            )

    def mark_unavailable(self) -> None:
        with self._connection_scope() as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                "UPDATE knowledge_index_state SET ready = 0 WHERE id = 1"
            ).rowcount
            if updated != 1:
                raise InstitutionalKnowledgeStoreError("index_not_ready")

    def reusable_vectors(self, embedding_model: str) -> dict[str, tuple[str, tuple[float, ...]]]:
        with self._connection_scope() as connection:
            rows = connection.execute(
                """
                SELECT c.chunk_id, c.content_hash, v.embedding_model, v.vector_json
                FROM institutional_chunks AS c
                JOIN institutional_vectors AS v ON v.chunk_id = c.chunk_id
                WHERE v.embedding_model = ?
                """,
                (embedding_model,),
            ).fetchall()
        cached: dict[str, tuple[str, tuple[float, ...]]] = {}
        for row in rows:
            if str(row["embedding_model"]) != embedding_model:
                continue
            try:
                vector = _parse_vector(row["vector_json"])
            except InstitutionalKnowledgeStoreError:
                continue
            cached[str(row["chunk_id"])] = (str(row["content_hash"]), vector)
        return cached

    def publish(self, documents, chunks, vectors: dict[str, tuple[float, ...]], embedding_model: str, fingerprint: str) -> None:
        if not documents or not chunks or set(vectors) != {chunk.chunk_id for chunk in chunks}:
            raise InstitutionalKnowledgeStoreError("vector_integrity")
        dimension = len(next(iter(vectors.values())))
        if any(len(vector) != dimension for vector in vectors.values()):
            raise InstitutionalKnowledgeStoreError("vector_integrity")
        if not embedding_model or len(embedding_model) > 128 or not fingerprint:
            raise InstitutionalKnowledgeStoreError("model_mismatch")
        with self._connection_scope() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM institutional_vectors")
            connection.execute("DELETE FROM institutional_chunks")
            connection.execute("DELETE FROM institutional_documents")
            for document in documents:
                connection.execute(
                    """
                    INSERT INTO institutional_documents (
                        document_id, version, title, status, effective_date,
                        source_type, synthetic, language, protocol_ids_json, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        document.document_id,
                        document.version,
                        document.title,
                        document.status,
                        document.effective_date,
                        document.source_type,
                        document.language,
                        _json_array(document.protocol_ids),
                        document.content_hash,
                    ),
                )
            for chunk in chunks:
                connection.execute(
                    """
                    INSERT INTO institutional_chunks (
                        chunk_id, document_id, version, title, document_status,
                        section, ordinal, content_hash, language, synthetic, text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.version,
                        chunk.title,
                        chunk.document_status,
                        chunk.section,
                        chunk.ordinal,
                        chunk.content_hash,
                        chunk.language,
                        chunk.text,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO institutional_vectors (
                        chunk_id, embedding_model, dimension, vector_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        embedding_model,
                        dimension,
                        _vector_json(vectors[chunk.chunk_id]),
                    ),
                )
            connection.execute(
                """
                UPDATE knowledge_index_state
                SET ready = 1, embedding_model = ?, vector_dimension = ?, corpus_fingerprint = ?
                WHERE id = 1
                """,
                (embedding_model, dimension, fingerprint),
            )
            self._validate_schema(connection)

    def fetch_rows(self) -> list[dict[str, object]]:
        with self._connection_scope() as connection:
            rows = connection.execute(
                """
                SELECT
                    c.chunk_id, c.document_id, c.version, c.title, c.document_status,
                    c.section, c.ordinal, c.content_hash, c.language, c.synthetic, c.text,
                    d.status AS document_row_status, d.protocol_ids_json, d.synthetic AS document_synthetic,
                    v.embedding_model, v.dimension, v.vector_json
                FROM institutional_chunks AS c
                JOIN institutional_documents AS d
                    ON d.document_id = c.document_id AND d.version = c.version
                JOIN institutional_vectors AS v ON v.chunk_id = c.chunk_id
                ORDER BY c.document_id, c.version, c.ordinal
                """
            ).fetchall()
            return [dict(row) for row in rows]

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
        except Exception:
            connection.close()
            raise
        return connection

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version != SCHEMA_VERSION:
            raise InstitutionalKnowledgeStoreError("index_not_ready")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise InstitutionalKnowledgeStoreError("vector_integrity")
        if _schema_contract(connection) != _migration_schema_contract():
            raise InstitutionalKnowledgeStoreError("index_not_ready")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise InstitutionalKnowledgeStoreError("vector_integrity")


def _json_array(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def _vector_json(vector: tuple[float, ...]) -> str:
    return json.dumps(list(vector), separators=(",", ":"), allow_nan=False)


def _parse_vector(raw: object) -> tuple[float, ...]:
    if not isinstance(raw, str):
        raise InstitutionalKnowledgeStoreError("vector_integrity")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InstitutionalKnowledgeStoreError("vector_integrity") from exc
    if not isinstance(parsed, list) or not parsed:
        raise InstitutionalKnowledgeStoreError("vector_integrity")
    values: list[float] = []
    for item in parsed:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise InstitutionalKnowledgeStoreError("vector_integrity")
        value = float(item)
        if not math.isfinite(value):
            raise InstitutionalKnowledgeStoreError("vector_integrity")
        values.append(value)
    return tuple(values)


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
    return objects, columns


def _normalize_schema_sql(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InstitutionalKnowledgeStoreError("index_not_ready")
    return value.strip()
