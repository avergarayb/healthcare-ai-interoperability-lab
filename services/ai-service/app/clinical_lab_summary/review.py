"""Pending human review for one lab summary. The graph cannot record an acceptance."""
import json
import sqlite3
from pathlib import Path

from app.enterprise_llm_providers.errors import ProviderError


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
