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
_ORG_ID = re.compile(r"^org-[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$")
_IAM_ISSUER = re.compile(r"^https?://[A-Za-z0-9._:-]{1,200}/realms/[A-Za-z0-9_-]{1,64}$")
_IAM_SUBJECT = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_DECISIONS = frozenset({"approved", "rejected"})
_AGENT_PRINCIPALS = frozenset({"synthetic-executor", "synthetic-administrator"})
IAM_AUTHENTICATOR_V1 = "LAB_REVIEW_IAM_V1"


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


def iam_principal_id(issuer, subject):
    digest = hashlib.sha256((issuer + "\n" + subject).encode("utf-8")).hexdigest()
    return "iam-" + digest[:20]


class IamReviewer:
    """A reviewer resolved from the server IAM binding, never from a browser field."""

    def __init__(self, principal_id, issuer, subject, organization_id, role, session_id):
        if any(type(value) is not str for value in (
                principal_id, issuer, subject, organization_id, role, session_id)):
            raise ReviewError("reviewer_denied")
        if (role != "clinical-reviewer" or session_id == ""
                or _IAM_ISSUER.fullmatch(issuer) is None or _IAM_SUBJECT.fullmatch(subject) is None
                or _ORG_ID.fullmatch(organization_id) is None
                or principal_id != iam_principal_id(issuer, subject)):
            raise ReviewError("role_denied" if role != "clinical-reviewer" else "reviewer_denied")
        self.principal_id = principal_id
        self.authenticator_id = IAM_AUTHENTICATOR_V1
        self.issuer = issuer
        self.subject = subject
        self.organization_id = organization_id
        self.role = role
        self.session_id = session_id


def list_reviews(path):
    """List stored summaries. Reading does not create the decision schema."""
    connection = _read_only(path)
    try:
        if _has_decision_schema(connection):
            rows = connection.execute(
                "SELECT review.review_id, review.authorization_id, review.patient_id, review.status, "
                "decision.decision, decision.decided_at "
                "FROM lab_summary_review AS review "
                "LEFT JOIN lab_summary_decision AS decision ON decision.review_id = review.review_id "
                "ORDER BY review.rowid"
            ).fetchall()
        else:
            rows = [
                (row[0], row[1], row[2], row[3], None, None)
                for row in connection.execute(
                    "SELECT review_id, authorization_id, patient_id, status FROM lab_summary_review ORDER BY rowid"
                )
            ]
    finally:
        connection.close()
    return [
        {"review_id": row[0], "authorization_id": row[1], "patient_id": row[2],
         "status": row[3], "decision": row[4], "decided_at": row[5]}
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
        identity = None
        if _table_exists(connection, "lab_summary_decision_identity"):
            identity = connection.execute(
                "SELECT issuer, subject, organization_id, role, local_principal "
                "FROM lab_summary_decision_identity WHERE review_id=?", (review_id,)).fetchone()
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
        "identity": None if identity is None else {
            "issuer": identity[0], "subject": identity[1], "organization_id": identity[2],
            "role": identity[3], "local_principal": identity[4],
        },
    }


def decide(path, review_id, reviewer, decision, note, decided_at):
    """Record one human decision. The original summary row is not updated."""
    iam = type(reviewer) is IamReviewer
    if type(reviewer) is not Reviewer and not iam:
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
        if not _has_decision_schema(connection) or (
                iam and not _table_exists(connection, "lab_summary_decision_identity")):
            connection.execute("ROLLBACK")
            raise ReviewError("schema_unprepared")
        if iam and not _table_exists(connection, "lab_summary_organization"):
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
        if iam:
            organization = connection.execute(
                "SELECT organization_id FROM lab_summary_organization WHERE review_id=?",
                (review_id,)).fetchone()
            if organization is None or organization[0] != reviewer.organization_id:
                connection.execute("ROLLBACK")
                raise ReviewError("organization_denied")
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
        if iam:
            connection.execute(
                "INSERT INTO lab_summary_decision_identity "
                "(review_id, issuer, subject, organization_id, role, local_principal) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (review_id, reviewer.issuer, reviewer.subject, reviewer.organization_id,
                 reviewer.role, reviewer.principal_id))
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
    return _table_exists(connection, "lab_summary_decision")


def _table_exists(connection, name):
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
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
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS lab_summary_decision_identity (
            review_id TEXT PRIMARY KEY,
            issuer TEXT NOT NULL,
            subject TEXT NOT NULL,
            organization_id TEXT NOT NULL,
            role TEXT NOT NULL,
            local_principal TEXT NOT NULL,
            FOREIGN KEY (review_id) REFERENCES lab_summary_review(review_id)
        )
        """)


def prepare_organization_store(path):
    """Create the organization association table. A queue page does not call this."""
    connection = _open(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS lab_summary_organization (
                review_id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                FOREIGN KEY (review_id) REFERENCES lab_summary_review(review_id)
            )
            """)
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise ReviewError("review_unavailable") from None
    finally:
        connection.close()


def assign_review_organization(path, review_id, organization_id):
    """Bind one stored review to one organization. The summary row is not updated."""
    if _REVIEW_ID.fullmatch(review_id or "") is None or _ORG_ID.fullmatch(organization_id or "") is None:
        raise ReviewError("organization_rejected")
    connection = _open(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        if not _table_exists(connection, "lab_summary_organization"):
            connection.execute("ROLLBACK")
            raise ReviewError("schema_unprepared")
        before = connection.execute(
            "SELECT summary_json, status FROM lab_summary_review WHERE review_id=?", (review_id,)
        ).fetchone()
        if before is None:
            connection.execute("ROLLBACK")
            raise ReviewError("not_found")
        current = connection.execute(
            "SELECT organization_id FROM lab_summary_organization WHERE review_id=?", (review_id,)
        ).fetchone()
        if current is None:
            connection.execute(
                "INSERT INTO lab_summary_organization (review_id, organization_id) VALUES (?, ?)",
                (review_id, organization_id))
        elif current[0] != organization_id:
            connection.execute("ROLLBACK")
            raise ReviewError("organization_conflict")
        after = connection.execute(
            "SELECT summary_json, status FROM lab_summary_review WHERE review_id=?", (review_id,)
        ).fetchone()
        if after != before:
            connection.execute("ROLLBACK")
            raise ReviewError("review_unavailable")
        connection.execute("COMMIT")
    finally:
        connection.close()


def review_organization(path, review_id):
    if _REVIEW_ID.fullmatch(review_id or "") is None:
        return None
    connection = _read_only(path)
    try:
        if not _table_exists(connection, "lab_summary_organization"):
            return None
        row = connection.execute(
            "SELECT organization_id FROM lab_summary_organization WHERE review_id=?", (review_id,)
        ).fetchone()
    finally:
        connection.close()
    return None if row is None else row[0]


def reviews_for_organization(path, organization_id):
    if _ORG_ID.fullmatch(organization_id or "") is None:
        return set()
    connection = _read_only(path)
    try:
        if not _table_exists(connection, "lab_summary_organization"):
            return set()
        rows = connection.execute(
            "SELECT review_id FROM lab_summary_organization WHERE organization_id=?",
            (organization_id,)).fetchall()
    finally:
        connection.close()
    return {row[0] for row in rows}


def _sources(summary):
    found = []
    for statement in summary.get("statements") or []:
        for source in statement.get("sources") or []:
            if not isinstance(source, dict):
                continue
            item = {
                "text": statement.get("text") or "",
                "source": source.get("source") or "",
                "resourceType": source.get("resourceType") or "",
                "id": source.get("id") or "",
            }
            for key in ("system", "code", "unit", "value", "range_low", "range_high"):
                if key in source:
                    item[key] = source[key]
            found.append(item)
    return found


def _receipt(path, authorization_id):
    receipt_path = Path(path).with_name("receipt.json")
    if not receipt_path.is_file():
        return None
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(receipt, dict):
        return None
    operation = receipt.get("operation_id")
    if operation == "lab-result-summary-v1":
        if authorization_id != "e2e-clinical-001-gemini":
            return None
    elif operation == "external-fhir-lab-summary-v1":
        if authorization_id != "external-fhir-001" or receipt.get("phase") != "intercepted":
            return None
    else:
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
