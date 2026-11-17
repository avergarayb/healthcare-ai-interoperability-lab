"""Pending human review for one lab summary. The graph cannot record an acceptance.

A later human decision is a separate row. It never updates the original summary.
The reviewer identity comes from the server session, not from the model and not
from a role posted by the browser. This is a laboratory development control.
"""
import hashlib
import json
import re
import sqlite3
from pathlib import Path

from app.enterprise_llm_providers.errors import ProviderError
from app.human_session import DEVELOPMENT_AUTHENTICATOR_V1


def queue_summary(path, review_id, authorization_id, patient_id, summary):
    """Store one pending review. A failure leaves no accepted row."""
    if summary.get("review") != "pending_human_review":
        raise ProviderError("review_unavailable")
    database = Path(path)
    try:
        database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS lab_summary_review (
                    review_id TEXT PRIMARY KEY,
                    authorization_id TEXT NOT NULL,
                    patient_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status = 'pending'),
                    summary_json TEXT NOT NULL
                )
                """)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS lab_summary_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    outcome TEXT NOT NULL
                )
                """)
            connection.execute(
                "INSERT INTO lab_summary_review (review_id, authorization_id, patient_id, status, summary_json) "
                "VALUES (?, ?, ?, 'pending', ?)",
                (review_id, authorization_id, patient_id, json.dumps(summary, ensure_ascii=True)))
            connection.execute(
                "INSERT INTO lab_summary_audit (review_id, event, outcome) VALUES (?, 'queued', 'pending')",
                (review_id,))
            connection.commit()
    except (OSError, sqlite3.Error, TypeError, ValueError):
        raise ProviderError("review_unavailable") from None


def read_status(path, review_id):
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT status FROM lab_summary_review WHERE review_id=?", (review_id,)).fetchone()
    if row is None:
        raise ProviderError("review_unavailable")
    return row[0]


_REVIEW_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_PRINCIPAL_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
_DECISIONS = frozenset({"approved", "rejected"})
_AGENT_PRINCIPALS = frozenset({"synthetic-executor", "synthetic-administrator"})


class ReviewError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


class Reviewer:
    """One human principal copied from the server session."""

    def __init__(self, principal_id, authenticator_id, session_id):
        if (type(principal_id) is not str or type(authenticator_id) is not str
                or type(session_id) is not str):
            raise ReviewError("reviewer_denied")
        if (principal_id in _AGENT_PRINCIPALS or _PRINCIPAL_ID.fullmatch(principal_id) is None
                or authenticator_id != DEVELOPMENT_AUTHENTICATOR_V1 or session_id == ""):
            raise ReviewError("reviewer_denied")
        self.principal_id = principal_id
        self.authenticator_id = authenticator_id
        self.session_id = session_id


def list_reviews(path):
    """List stored summaries. Reading does not create the decision schema."""
    connection = _read_only(path)
    try:
        if _has_decision_schema(connection):
            rows = connection.execute(
                "SELECT review.review_id, review.authorization_id, review.patient_id, review.status, "
                "decision.decision "
                "FROM lab_summary_review AS review "
                "LEFT JOIN lab_summary_decision AS decision ON decision.review_id = review.review_id "
                "ORDER BY review.rowid"
            ).fetchall()
        else:
            rows = [
                (row[0], row[1], row[2], row[3], None)
                for row in connection.execute(
                    "SELECT review_id, authorization_id, patient_id, status FROM lab_summary_review ORDER BY rowid"
                )
            ]
    finally:
        connection.close()
    return [
        {"review_id": row[0], "authorization_id": row[1], "patient_id": row[2],
         "status": row[3], "decision": row[4]}
        for row in rows
    ]


def read_review(path, review_id):
    if _REVIEW_ID.fullmatch(review_id or "") is None:
        raise ReviewError("not_found")
    connection = _read_only(path)
    try:
        row = connection.execute(
            "SELECT review_id, authorization_id, patient_id, status, summary_json "
            "FROM lab_summary_review WHERE review_id=?", (review_id,)).fetchone()
        if row is None:
            raise ReviewError("not_found")
        decision = None
        decision_audits = []
        if _has_decision_schema(connection):
            decision = connection.execute(
                "SELECT decision, reviewer_id, reviewer_authenticator, note, decided_at, summary_sha256 "
                "FROM lab_summary_decision WHERE review_id=?", (review_id,)).fetchone()
            decision_audits = connection.execute(
                "SELECT event, outcome, actor_id, decision FROM lab_summary_decision_audit "
                "WHERE review_id=? ORDER BY audit_id", (review_id,)).fetchall()
        audits = connection.execute(
            "SELECT event, outcome FROM lab_summary_audit WHERE review_id=? ORDER BY audit_id",
            (review_id,)).fetchall()
    finally:
        connection.close()
    summary = json.loads(row[4])
    return {
        "review_id": row[0],
        "authorization_id": row[1],
        "patient_id": row[2],
        "status": row[3],
        "summary": summary,
        "sources": _sources(summary),
        "summary_sha256": hashlib.sha256(row[4].encode("utf-8")).hexdigest(),
        "receipt": _receipt(path, row[1]),
        "decision": None if decision is None else {
            "decision": decision[0],
            "reviewer_id": decision[1],
            "reviewer_authenticator": decision[2],
            "note": decision[3],
            "decided_at": decision[4],
            "summary_sha256": decision[5],
        },
        "audit": [{"event": item[0], "outcome": item[1], "actor_id": ""} for item in audits],
        "decision_audit": [
            {"event": item[0], "outcome": item[1], "actor_id": item[2], "decision": item[3]}
            for item in decision_audits
        ],
    }


def decide(path, review_id, reviewer, decision, note, decided_at):
    """Record one human decision. The original summary row is not updated."""
    if type(reviewer) is not Reviewer:
        raise ReviewError("reviewer_denied")
    if decision not in _DECISIONS or _REVIEW_ID.fullmatch(review_id or "") is None:
        raise ReviewError("invalid_decision")
    if type(note) is not str or not 1 <= len(note) <= 400 or any(ord(char) < 32 for char in note):
        raise ReviewError("invalid_note")
    if "AIza" in note or "GEMINI_API_KEY" in note:
        raise ReviewError("invalid_note")
    if type(decided_at) is not str or len(decided_at) != 27 or not decided_at.endswith("Z"):
        raise ReviewError("invalid_decision")
    connection = _open(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        if not _has_decision_schema(connection):
            connection.execute("ROLLBACK")
            raise ReviewError("schema_unprepared")
        row = connection.execute(
            "SELECT summary_json, status FROM lab_summary_review WHERE review_id=?",
            (review_id,)).fetchone()
        if row is None or row[1] != "pending":
            connection.execute("ROLLBACK")
            raise ReviewError("not_found")
        original = row[0]
        digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
        taken = connection.execute(
            "SELECT decision FROM lab_summary_decision WHERE review_id=?", (review_id,)).fetchone()
        if taken is not None:
            connection.execute("ROLLBACK")
            raise ReviewError("already_decided")
        connection.execute(
            "INSERT INTO lab_summary_decision (review_id, decision, reviewer_id, "
            "reviewer_authenticator, session_id, note, decided_at, summary_sha256) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (review_id, decision, reviewer.principal_id, reviewer.authenticator_id,
             reviewer.session_id, note, decided_at, digest))
        connection.execute(
            "INSERT INTO lab_summary_decision_audit "
            "(review_id, event, outcome, actor_id, decision) VALUES (?, 'decided', 'recorded', ?, ?)",
            (review_id, reviewer.principal_id, decision))
        current = connection.execute(
            "SELECT summary_json, status FROM lab_summary_review WHERE review_id=?",
            (review_id,)).fetchone()
        if current != (original, "pending"):
            connection.execute("ROLLBACK")
            raise ReviewError("review_unavailable")
        connection.execute("COMMIT")
    except sqlite3.IntegrityError:
        connection.execute("ROLLBACK")
        raise ReviewError("already_decided") from None
    finally:
        connection.close()
    return read_review(path, review_id)


def prepare_decision_store(path):
    """Create the decision tables. A queue page does not call this."""
    connection = _open(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        _ensure_decision_tables(connection)
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise ReviewError("review_unavailable") from None
    finally:
        connection.close()


def _read_only(path):
    connection = _open(path)
    connection.execute("PRAGMA query_only=ON")
    return connection


def _has_decision_schema(connection):
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lab_summary_decision'"
    ).fetchone()
    return row is not None


def _open(path):
    database = Path(path)
    if not database.is_file():
        raise ReviewError("review_unavailable")
    return sqlite3.connect(database, timeout=5, isolation_level=None)


def _ensure_decision_tables(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS lab_summary_decision (
            review_id TEXT PRIMARY KEY,
            decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
            reviewer_id TEXT NOT NULL,
            reviewer_authenticator TEXT NOT NULL,
            session_id TEXT NOT NULL,
            note TEXT NOT NULL,
            decided_at TEXT NOT NULL,
            summary_sha256 TEXT NOT NULL,
            FOREIGN KEY (review_id) REFERENCES lab_summary_review(review_id)
        )
        """)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS lab_summary_decision_audit (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id TEXT NOT NULL,
            event TEXT NOT NULL,
            outcome TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            decision TEXT NOT NULL
        )
        """)


def _sources(summary):
    found = []
    for statement in summary.get("statements") or []:
        for source in statement.get("sources") or []:
            found.append({
                "text": statement.get("text") or "",
                "source": source.get("source") or "",
                "resourceType": source.get("resourceType") or "",
                "id": source.get("id") or "",
            })
    return found


def _receipt(path, authorization_id):
    receipt_path = Path(path).with_name("receipt.json")
    if not receipt_path.is_file():
        return None
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(receipt, dict) or receipt.get("operation_id") != "lab-result-summary-v1":
        return None
    if authorization_id != "e2e-clinical-001-gemini":
        return None
    kept = {
        "provider": receipt.get("provider"),
        "model": receipt.get("model"),
        "phase": receipt.get("phase"),
        "requests_sent": receipt.get("requests_sent"),
        "input_tokens": receipt.get("input_tokens"),
        "output_tokens": receipt.get("output_tokens"),
        "estimated_microusd": receipt.get("estimated_microusd"),
        "provider_request_id": receipt.get("provider_request_id"),
        "recorded_at": _timestamp(receipt_path),
    }
    rendered = json.dumps(kept)
    if "AIza" in rendered or "GEMINI_API_KEY" in rendered:
        return None
    return kept


def _timestamp(path):
    from datetime import datetime, timezone
    moment = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
