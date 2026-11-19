"""Durable proposals for one critical-lab case. A permit is not reused."""
import hashlib
import json
import sqlite3
from pathlib import Path
from uuid import uuid4


def _connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS critical_proposal (
            proposal_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL UNIQUE,
            proposal_hash TEXT NOT NULL,
            body_json TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS critical_decision (
            proposal_id TEXT PRIMARY KEY,
            decision TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS critical_grant (
            order_id TEXT PRIMARY KEY,
            proposal_id TEXT NOT NULL
        )
    """)
    return connection


def _hash(body):
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def find_by_order(path, order_id):
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT proposal_id, proposal_hash, body_json, status FROM critical_proposal WHERE order_id = ?",
            (order_id,)).fetchone()
    if row is None:
        return None
    body = json.loads(row["body_json"])
    body["proposalId"] = row["proposal_id"]
    body["proposalHash"] = row["proposal_hash"]
    body["phase"] = row["status"]
    return body


def save_proposal(path, order_id, body):
    existing = find_by_order(path, order_id)
    if existing is not None:
        return existing
    proposal_id = str(uuid4())
    digest = _hash(body)
    stored = dict(body)
    stored["proposalId"] = proposal_id
    stored["proposalHash"] = digest
    stored["phase"] = "PENDING_REVIEW"
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO critical_proposal (proposal_id, order_id, proposal_hash, body_json, status)
            VALUES (?, ?, ?, ?, 'PENDING_REVIEW')
            """,
            (proposal_id, order_id, digest, json.dumps(stored, sort_keys=True)))
    return stored


def decide(path, proposal_id, proposal_hash, decision, actor_id, role, organization_id, idempotency_key):
    if (decision not in {"approved", "rejected"} or not actor_id or role != "clinician"
            or organization_id != "org-mini-his"):
        return {"outcome": "invalid_approval"}
    with _connect(path) as connection:
        prior = connection.execute(
            "SELECT decision FROM critical_decision WHERE idempotency_key = ?",
            (idempotency_key,)).fetchone()
        if prior is not None:
            if prior["decision"] != decision:
                return {"outcome": "replay_denied"}
            return {"outcome": "recorded", "decision": decision}
        row = connection.execute(
            "SELECT proposal_hash, status FROM critical_proposal WHERE proposal_id = ?",
            (proposal_id,)).fetchone()
        if row is None or row["proposal_hash"] != proposal_hash:
            return {"outcome": "invalid_approval"}
        taken = connection.execute(
            "SELECT decision FROM critical_decision WHERE proposal_id = ?",
            (proposal_id,)).fetchone()
        if taken is not None:
            return {"outcome": "already_decided", "decision": taken["decision"]}
        connection.execute(
            "INSERT INTO critical_decision (proposal_id, decision, actor_id, idempotency_key) VALUES (?, ?, ?, ?)",
            (proposal_id, decision, actor_id, idempotency_key))
        connection.execute(
            "UPDATE critical_proposal SET status = ? WHERE proposal_id = ?",
            ("APPROVED" if decision == "approved" else "REJECTED", proposal_id))
    return {"outcome": "recorded", "decision": decision}


def apply_grant(path, proposal_id, proposal_hash, organization_id):
    if organization_id != "org-mini-his":
        return {"outcome": "not_approved"}
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT order_id, proposal_hash, status FROM critical_proposal WHERE proposal_id = ?",
            (proposal_id,)).fetchone()
        if row is None or row["proposal_hash"] != proposal_hash or row["status"] != "APPROVED":
            return {"outcome": "not_approved"}
        existing = connection.execute(
            "SELECT proposal_id FROM critical_grant WHERE order_id = ?",
            (row["order_id"],)).fetchone()
        if existing is not None:
            return {"outcome": "already_created", "orderId": row["order_id"]}
        connection.execute(
            "INSERT INTO critical_grant (order_id, proposal_id) VALUES (?, ?)",
            (row["order_id"], proposal_id))
    return {"outcome": "created", "orderId": row["order_id"]}
