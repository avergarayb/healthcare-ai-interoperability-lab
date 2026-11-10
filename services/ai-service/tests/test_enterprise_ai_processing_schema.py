"""C02 schema preflight only: memory is a test oracle, never a durable fallback."""
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest


MIGRATION = Path(__file__).resolve().parents[1] / "app/enterprise_ai_processing/migrations/001_processing_ledger.sql"


@pytest.fixture
def db():
    with sqlite3.connect(":memory:") as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(MIGRATION.read_text(encoding="utf-8"))
        yield connection


def insert(connection, table, row):
    columns = tuple(row)
    connection.execute("INSERT INTO " + table + " (" + ",".join(columns) + ") VALUES ("
                       + ",".join("?" for _ in columns) + ")", tuple(row.values()))


def profile_row(org="ORG-A"):
    return dict(organization_id=org, profile_id="fake-enterprise-extractive-v1", version=1, enabled=1,
        provider="fake", model_id="fake-enterprise-extractive-v1", model_version="1",
        destination="in-process-offline", classification="synthetic-internal",
        processing_purpose="synthetic-policy-question-answering", retention="ephemeral-no-retention",
        tokenizer="fake-byte-v1", question_set_id="vacation-question-v1", valid_from_us=1,
        expires_at_us=100000000, review_due_at_us=100000000, max_sources=1, max_source_bytes=1024,
        max_question_bytes=256, max_input_bytes=2048, max_output_bytes=512, max_output_units=256,
        max_seconds=5, max_retries=0, max_concurrent=1)


def grant_row(org="ORG-A"):
    profile = profile_row(org)
    row = {k: v for k, v in profile.items() if k.startswith("max_") or k.endswith("_us")}
    row.update(organization_id=org, grant_id="grant-a", version=1, enabled=1, principal_id="principal-a",
        principal_type="workload", instance_id="instance-a", tenant_id="tenant-a", resource_id="vacation-a",
        recipient_id="recipient-a", read_operation="document.content.read", read_purpose="synthetic-demonstration",
        processing_operation="enterprise.document.answer", processing_purpose=profile["processing_purpose"],
        classification=profile["classification"], profile_id=profile["profile_id"], profile_version=1,
        approval="not_required", approval_ref="exemption-a")
    return row


def execution_row(org="ORG-A"):
    grant = grant_row(org)
    row = {k: grant[k] for k in ("organization_id", "grant_id", "principal_id", "principal_type", "instance_id",
        "tenant_id", "resource_id", "recipient_id", "profile_id", "profile_version", "approval_ref",
        "classification", "read_operation", "read_purpose", "processing_operation", "processing_purpose")}
    row.update(operation_id=str(uuid4()), attempt_version=1, owner_ref=str(uuid4()), process_epoch=str(uuid4()),
        lease_id=str(uuid4()), decision_ref=str(uuid4()), binding_id="binding-a", source_ref="source-a",
        read_correlation_id=str(uuid4()), registered_version=1, content_revision=1, connector_revision=1,
        processing_revision=1, grant_version=1, destination="in-process-offline", question_id="vacation-days-v1",
        source_bytes=100, question_bytes=50, input_bytes=300, reserved_output_bytes=512,
        reserved_output_units=256, max_seconds=5, authorized_at_us=1000000, expires_at_us=6000000,
        lease_state="ISSUED", run_state="INTENT", reservation_state="HELD")
    return row


def seed(db, org="ORG-A"):
    insert(db, "aip_profile", profile_row(org))
    insert(db, "aip_grant", grant_row(org))


def test_exact_five_strict_tables_and_five_explicit_indexes(db):
    tables = db.execute("SELECT name,strict FROM pragma_table_list WHERE name LIKE 'aip_%'").fetchall()
    assert len(tables) == 5 and all(strict == 1 for _, strict in tables)
    assert len(db.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL").fetchall()) == 5
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("field,value", [("provider", "openai"), ("destination", "external"), ("version", 0),
    ("enabled", 2), ("max_sources", 2), ("max_source_bytes", 1025), ("max_question_bytes", 257),
    ("max_input_bytes", 2049), ("max_output_bytes", 513), ("max_output_units", 257),
    ("max_seconds", 6), ("max_retries", 1), ("max_concurrent", 2), ("expires_at_us", 1)])
def test_profile_checks_reject_overbroad_or_incoherent_rows(db, field, value):
    row = profile_row()
    row[field] = value
    with pytest.raises(sqlite3.IntegrityError):
        insert(db, "aip_profile", row)


def test_qualified_fk_prevents_cross_org_grant(db):
    insert(db, "aip_profile", profile_row("ORG-B"))
    with pytest.raises(sqlite3.IntegrityError):
        insert(db, "aip_grant", grant_row("ORG-A"))


@pytest.mark.parametrize("change", [dict(input_bytes=149), dict(lease_state="CONSUMED"),
    dict(reservation_state="RELEASED"), dict(expires_at_us=6000001), dict(entered_at_us=1000001),
    dict(run_state="BAD"), dict(principal_type="human"), dict(grant_id="missing")])
def test_execution_checks_and_fk(db, change):
    seed(db)
    row = execution_row()
    row.update(change)
    with pytest.raises(sqlite3.IntegrityError):
        insert(db, "aip_execution", row)


def test_one_active_scope_and_unknown_remains_blocking(db):
    seed(db)
    first = execution_row()
    insert(db, "aip_execution", first)
    with pytest.raises(sqlite3.IntegrityError):
        insert(db, "aip_execution", execution_row())
    db.execute("UPDATE aip_execution SET run_state='UNKNOWN',lease_state='CLOSED',reservation_state='UNCERTAIN'")
    with pytest.raises(sqlite3.IntegrityError):
        insert(db, "aip_execution", execution_row())
    db.execute("UPDATE aip_execution SET reservation_state='CHARGED'")
    insert(db, "aip_execution", execution_row())


def test_orgs_with_identical_ids_have_distinct_slots(db):
    for org in ("ORG-A", "ORG-B"):
        seed(db, org)
        insert(db, "aip_execution", execution_row(org))
    assert db.execute("SELECT count(*) FROM aip_execution").fetchone()[0] == 2


def test_strict_storage_and_no_payload_columns(db):
    row = profile_row()
    row["version"] = "not-an-integer"
    with pytest.raises(sqlite3.IntegrityError):
        insert(db, "aip_profile", row)
    for table in ("aip_store", "aip_profile", "aip_grant", "aip_execution", "aip_audit"):
        columns = {r[1] for r in db.execute("PRAGMA table_info(" + table + ")")}
        assert not columns & {"document", "question", "prompt", "response", "candidate", "digest", "payload"}
