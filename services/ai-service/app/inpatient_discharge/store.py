"""Durable discharge proposals. A consumed permit is not reopened."""
import json
import sqlite3
from pathlib import Path

from app.hospital_identity import persistent_actor


def prepare(path, authorization_id, episode_id, version, proposal_hash, body):
    with _connect(path) as connection:
        try:
            connection.execute(
                "INSERT INTO discharge_permit (authorization_id, episode_id) VALUES (?, ?)",
                (authorization_id, episode_id))
        except sqlite3.IntegrityError:
            return {"outcome": "replay_denied"}
        proposal_id = body["proposalId"]
        connection.execute(
            """
            INSERT INTO discharge_proposal (
                proposal_id, authorization_id, episode_id, episode_version, proposal_hash, body_json, status
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """,
            (proposal_id, authorization_id, episode_id, version, proposal_hash, json.dumps(body, ensure_ascii=True)))
        _audit(connection, proposal_id, "queued", "pending", "agent")
        connection.commit()
    return {"outcome": "queued", "proposalId": proposal_id}


def consume_without_draft(path, authorization_id, episode_id, reason):
    with _connect(path) as connection:
        try:
            connection.execute(
                "INSERT INTO discharge_permit (authorization_id, episode_id) VALUES (?, ?)",
                (authorization_id, episode_id))
        except sqlite3.IntegrityError:
            return {"outcome": "replay_denied"}
        _audit(connection, authorization_id, "withheld", reason, "agent")
        connection.commit()
    return {"outcome": "withheld", "reason": reason}


def decide(path, proposal_id, proposal_hash, episode_version, decision, actor_id, organization_id, idempotency_key, live_version):
    if decision not in {"approved", "rejected", "changes_requested"}:
        return {"outcome": "invalid_approval", "episodeClosed": False}
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT proposal_hash, episode_version, status FROM discharge_proposal WHERE proposal_id = ?",
            (proposal_id,)).fetchone()
        if row is None or row[0] != proposal_hash or row[1] != episode_version or episode_version != live_version:
            _audit(connection, proposal_id, "decision", "invalid_approval", actor_id)
            connection.commit()
            return {"outcome": "invalid_approval", "episodeClosed": False}
        if not persistent_actor(actor_id, organization_id):
            _audit(connection, proposal_id, "decision", "wrong_organization", actor_id)
            connection.commit()
            return {"outcome": "wrong_organization", "episodeClosed": False}
        prior = connection.execute(
            "SELECT idempotency_key, outcome FROM discharge_decision WHERE proposal_id = ?",
            (proposal_id,)).fetchone()
        if prior is not None:
            outcome = prior[1] if prior[0] == idempotency_key else "already_decided"
            return {"outcome": outcome, "episodeClosed": False}
        connection.execute(
            """
            INSERT INTO discharge_decision (
                proposal_id, idempotency_key, decision, actor_id, organization_id, outcome
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (proposal_id, idempotency_key, decision, actor_id, organization_id, decision))
        connection.execute(
            "UPDATE discharge_proposal SET status = ? WHERE proposal_id = ?",
            (decision, proposal_id))
        _audit(connection, proposal_id, "decision", decision, actor_id)
        connection.commit()
    return {"outcome": decision, "episodeClosed": False}


def authorize(path, proposal_id, proposal_hash, actor_id, organization_id, chart):
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT proposal_hash, episode_version, body_json, status FROM discharge_proposal WHERE proposal_id = ?",
            (proposal_id,)).fetchone()
        if row is None or row[0] != proposal_hash or row[3] != "approved":
            return {"outcome": "not_approved"}
        if not persistent_actor(actor_id, organization_id):
            return {"outcome": "wrong_organization"}
        existing = connection.execute(
            "SELECT body_json FROM discharge_follow_up WHERE proposal_id = ?", (proposal_id,)).fetchone()
        if existing is not None:
            return {"outcome": "already_created", "tasks": json.loads(existing[0])}
        if row[1] != chart["version"]:
            return {"outcome": "version_conflict"}
        if any(task["kind"] == "ward" and task["status"] == "open" for task in chart["tasks"]):
            return {"outcome": "pending_items"}
        tasks = json.loads(row[2]).get("draft", {}).get("proposedTasks", [])
        if not tasks:
            return {"outcome": "nothing_to_create"}
        connection.execute(
            "INSERT INTO discharge_follow_up (proposal_id, body_json) VALUES (?, ?)",
            (proposal_id, json.dumps(tasks, ensure_ascii=True)))
        _audit(connection, proposal_id, "follow_up", "authorized", actor_id)
        connection.commit()
    return {"outcome": "authorized", "tasks": tasks}


def audit(path, proposal_id):
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT action, outcome, actor_id FROM discharge_audit WHERE subject_id = ? ORDER BY audit_id",
            (proposal_id,)).fetchall()
    return [{"action": row[0], "outcome": row[1], "actorId": row[2]} for row in rows]


def _connect(path):
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS discharge_permit (
            authorization_id TEXT PRIMARY KEY,
            episode_id TEXT NOT NULL
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS discharge_proposal (
            proposal_id TEXT PRIMARY KEY,
            authorization_id TEXT NOT NULL UNIQUE,
            episode_id TEXT NOT NULL,
            episode_version INTEGER NOT NULL,
            proposal_hash TEXT NOT NULL,
            body_json TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS discharge_decision (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            decision TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            organization_id TEXT NOT NULL,
            outcome TEXT NOT NULL
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS discharge_follow_up (
            proposal_id TEXT PRIMARY KEY,
            body_json TEXT NOT NULL
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS discharge_audit (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id TEXT NOT NULL,
            action TEXT NOT NULL,
            outcome TEXT NOT NULL,
            actor_id TEXT NOT NULL
        )
        """)
    return connection


def _audit(connection, subject_id, action, outcome, actor_id):
    connection.execute(
        "INSERT INTO discharge_audit (subject_id, action, outcome, actor_id) VALUES (?, ?, ?, ?)",
        (subject_id, action, outcome, actor_id))
