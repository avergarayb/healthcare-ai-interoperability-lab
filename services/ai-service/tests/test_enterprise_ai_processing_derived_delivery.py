"""TASK-C03 Phase B1. Derived-delivery authority and explicit V1 to V2 migration."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import socket
import sqlite3
from uuid import uuid4

import pytest

from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.sqlite_ledger import (
    CONTRACT, CONTRACT_V2, DERIVED_KIND, DERIVED_OPERATION, DerivedDeliveryGrant, DerivedDeliveryQuery,
    DerivedGrantMatch, MIGRATION, MIGRATION_V2, SQLiteExecutionLedger, schema_ddl,
)
from tests.enterprise_ai_processing_execution_fixture import execution_laboratory


CANARY = b"VACACIONES-CANARY-B1-9f3c"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("B1 external network forbidden")

    for name in ("connect", "connect_ex", "send", "sendall", "sendto"):
        monkeypatch.setattr(socket.socket, name, forbidden)
    for name in ("create_connection", "getaddrinfo", "gethostbyname"):
        monkeypatch.setattr(socket, name, forbidden)
    yield attempts
    assert attempts == []


def _hash(path):
    return sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _connect(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _count(path, sql, params=()):
    with _connect(path) as connection:
        return connection.execute(sql, params).fetchone()[0]


def _migrate(lab):
    before = lab.ledger.policy(lab.executor["ORG-A"]).revision
    lab.ledger.migrate_to_v2(lab.admin["ORG-A"])
    assert lab.ledger.policy(lab.executor["ORG-A"]).revision == before
    return before


def _record(lab, **overrides):
    grant = lab.ledger.policy(lab.executor["ORG-A"]).grants[0]
    now = lab.clock()
    values = dict(
        organization_id="ORG-A", derived_grant_id="derived-grant-a", version=1, enabled=True,
        principal_id=grant.principal_id, instance_id=grant.instance_id, tenant_id=grant.tenant_id,
        resource_id=grant.resource_id, recipient_id=grant.recipient_id, registered_version=1,
        processing_grant_id=grant.grant_id, processing_grant_version=grant.version,
        valid_from=now, expires_at=now + timedelta(minutes=5), review_due_at=now + timedelta(minutes=4))
    values.update(overrides)
    return DerivedDeliveryGrant(**values)


def _query(record, processing_revision, derived_revision, **overrides):
    values = dict(
        organization_id=record.organization_id, principal_id=record.principal_id,
        instance_id=record.instance_id, tenant_id=record.tenant_id, resource_id=record.resource_id,
        recipient_id=record.recipient_id, registered_version=record.registered_version,
        processing_grant_id=record.processing_grant_id, processing_grant_version=record.processing_grant_version,
        derived_grant_id=record.derived_grant_id, processing_revision=processing_revision,
        derived_delivery_revision=derived_revision)
    values.update(overrides)
    return DerivedDeliveryQuery(**values)


def _issue(lab, record=None, **overrides):
    record = record or _record(lab, **overrides)
    processing = lab.ledger.policy(lab.executor["ORG-A"]).revision
    derived = _count(lab.ledger.path, "SELECT coalesce(max(revision),0) FROM aip_derived_revision WHERE organization_id='ORG-A'")
    new = lab.ledger.change_derived_grant(
        lab.admin["ORG-A"], record, expected_processing_revision=processing, expected_derived_revision=derived)
    return record, processing, new


def test_v1_open_remains_valid(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        policy = lab.ledger.policy(lab.executor["ORG-A"])
        with _connect(lab.ledger.path) as connection:
            meta = connection.execute("SELECT schema_version,contract FROM aip_store").fetchone()
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert meta["schema_version"] == 1 and meta["contract"] == CONTRACT
        assert "aip_derived_delivery_grant" not in tables
        assert policy.revision >= 1 and policy.grants[0].grant_id == "processing-grant-a"
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.change_derived_grant(
                lab.admin["ORG-A"], _record(lab), expected_processing_revision=policy.revision, expected_derived_revision=0)
        assert caught.value.unavailable is True
    finally:
        lab.close()


def test_explicit_migration_preserves_v1_metadata(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        with _connect(lab.ledger.path) as connection:
            before = dict(connection.execute("SELECT * FROM aip_store").fetchone())
            profiles = connection.execute("SELECT count(*) FROM aip_profile").fetchone()[0]
            grants = connection.execute("SELECT count(*) FROM aip_grant").fetchone()[0]
            audits = connection.execute("SELECT count(*) FROM aip_audit").fetchone()[0]
        _migrate(lab)
        with _connect(lab.ledger.path) as connection:
            after = dict(connection.execute("SELECT * FROM aip_store").fetchone())
            assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
            assert connection.execute("PRAGMA quick_check(1)").fetchone()[0] == "ok"
        assert after["schema_version"] == 2 and after["contract"] == CONTRACT_V2
        assert after["store_id"] == before["store_id"]
        assert after["revision"] == before["revision"] and after["next_audit_seq"] == before["next_audit_seq"]
        assert after["v1_checksum"] == lab.ledger._checksum and after["migration_checksum"] == lab.ledger._checksum_v2
        assert after["next_grounding_seq"] == 1
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_profile") == profiles
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_grant") == grants
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_audit") == audits
    finally:
        lab.close()


def test_migration_file_checksums_match_the_store(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        assert _hash(MIGRATION) == lab.ledger._checksum
        assert _hash(MIGRATION_V2) == lab.ledger._checksum_v2
        _migrate(lab)
        with _connect(lab.ledger.path) as connection:
            row = connection.execute("SELECT migration_checksum,v1_checksum FROM aip_store").fetchone()
        assert row["v1_checksum"] == _hash(MIGRATION) and row["migration_checksum"] == _hash(MIGRATION_V2)
        with _connect(lab.ledger.path) as connection:
            connection.execute("UPDATE aip_store SET migration_checksum=?", ("0" * 64,))
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.policy(lab.executor["ORG-A"])
        assert caught.value.unavailable is True
    finally:
        lab.close()


def test_v2_ddl_matches_the_migration_oracle(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        with _connect(lab.ledger.path) as connection:
            assert schema_ddl(connection) == lab.ledger._ddl_v2
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"aip_store", "aip_profile", "aip_grant", "aip_execution", "aip_audit", "aip_derived_revision",
                "aip_derived_delivery_grant", "aip_grounding_audit", "aip_delivery_decision"} <= names
    finally:
        lab.close()


def test_migration_rolls_back_completely(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        def fault(stage):
            if stage == "migrate_before_commit":
                raise OSError(stage)
        lab.ledger._fault = fault
        with pytest.raises(ExecutionError):
            lab.ledger.migrate_to_v2(lab.admin["ORG-A"])
        with _connect(lab.ledger.path) as connection:
            version = connection.execute("SELECT schema_version FROM aip_store").fetchone()[0]
            present = connection.execute(
                "SELECT count(*) FROM sqlite_master WHERE name='aip_derived_delivery_grant'").fetchone()[0]
        assert version == 1 and present == 0
        lab.ledger._fault = lambda stage: None
        _migrate(lab)
    finally:
        lab.close()


def test_ambiguous_commit_reopens_as_complete_v2(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        def fault(stage):
            if stage == "migrate_after_commit":
                raise OSError(stage)
        lab.ledger._fault = fault
        with pytest.raises(ExecutionError):
            lab.ledger.migrate_to_v2(lab.admin["ORG-A"])
        lab.ledger._fault = lambda stage: None
        policy = lab.ledger.policy(lab.executor["ORG-A"])
        with _connect(lab.ledger.path) as connection:
            version = connection.execute("SELECT schema_version FROM aip_store").fetchone()[0]
            assert schema_ddl(connection) == lab.ledger._ddl_v2
        assert version == 2 and policy.revision >= 1
    finally:
        lab.close()


def test_reopen_v2_without_automatic_migration(tmp_path):
    lab = execution_laboratory(tmp_path)
    root = lab.ledger.root
    try:
        _migrate(lab)
    finally:
        lab.close()
    reopened = SQLiteExecutionLedger(root, lab.issuer, lab.clock)
    try:
        assert reopened.policy(lab.executor["ORG-A"]).grants[0].grant_id == "processing-grant-a"
        with _connect(reopened.path) as connection:
            assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 2
    finally:
        reopened.close()


def test_downgrade_and_repeat_migration_are_rejected(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.migrate_to_v2(lab.admin["ORG-A"])
        assert caught.value.reason == "revision_conflict"
        with pytest.raises(sqlite3.IntegrityError):
            with _connect(lab.ledger.path) as connection:
                connection.execute("UPDATE aip_store SET schema_version=1")
        assert not hasattr(lab.ledger, "migrate_to_v1")
    finally:
        lab.close()


def test_partial_schema_is_rejected(tmp_path):
    lab = execution_laboratory(tmp_path)
    root = lab.ledger.root
    try:
        _migrate(lab)
    finally:
        lab.close()
    with _connect(root / "processing.sqlite3") as connection:
        connection.execute("CREATE TABLE aip_partial(id INTEGER)")
    reopened = SQLiteExecutionLedger(root, lab.issuer, lab.clock)
    try:
        with pytest.raises(ExecutionError) as caught:
            reopened.policy(lab.executor["ORG-A"])
        assert caught.value.unavailable is True
    finally:
        reopened.close()


def test_historical_c02_commands_work_on_v2(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        audits = len(lab.ledger.read_audit(lab.admin["ORG-A"]))
        _migrate(lab)
        assert len(lab.ledger.read_audit(lab.admin["ORG-A"])) == audits
        revised = lab.change_grant()
        lease = lab.prepare("a")
        result = lab.gateway.invoke_once(lease)
        assert result.state == "COMPLETED"
        assert lab.ledger.policy(lab.executor["ORG-A"]).revision == revised
        assert CANARY not in Path(lab.ledger.path).read_bytes()
        assert b"VACACIONES" not in Path(lab.ledger.path).read_bytes()
    finally:
        lab.close()


def test_processing_revision_is_not_moved_by_derived_administration(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        before = lab.ledger.policy(lab.executor["ORG-A"]).revision
        _issue(lab)
        assert lab.ledger.policy(lab.executor["ORG-A"]).revision == before
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_audit WHERE event='ai_processing_policy_changed'") == before
    finally:
        lab.close()


def test_derived_revision_is_independent_of_c02_policy_changes(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        record, processing, derived = _issue(lab)
        lab.ledger.assess_derived_delivery(lab.executor["ORG-A"], _query(record, processing, derived))
        moved = lab.change_grant()
        assert moved == processing + 1
        assert _count(lab.ledger.path, "SELECT revision FROM aip_derived_revision WHERE organization_id='ORG-A'") == derived
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.assess_derived_delivery(lab.executor["ORG-A"], _query(record, processing, derived))
        assert caught.value.reason == "processing_not_granted"
        assert _count(lab.ledger.path,
                      "SELECT count(*) FROM aip_grounding_audit WHERE reason='policy_changed'") == 1
        stored = _count(lab.ledger.path, "SELECT processing_revision FROM aip_derived_delivery_grant")
        assert stored == processing
    finally:
        lab.close()


def test_complete_grant_is_valid_at_its_own_new_revision(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        record, processing, derived = _issue(lab)
        assert derived == 1
        matched = lab.ledger.assess_derived_delivery(lab.executor["ORG-A"], _query(record, processing, derived))
        assert type(matched) is DerivedGrantMatch
        assert not hasattr(matched, "state") and not hasattr(matched, "documents")
        assert "AUTHORIZED" not in repr(matched) and "AUTHORIZED" not in str(matched)
        with _connect(lab.ledger.path) as connection:
            row = connection.execute("SELECT * FROM aip_derived_delivery_grant").fetchone()
        assert row["content_kind"] == DERIVED_KIND and row["delivery_operation"] == DERIVED_OPERATION
        assert row["processing_revision"] == processing and row["derived_delivery_revision"] == derived
        assert row["enabled"] == 1
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_delivery_decision") == 0
    finally:
        lab.close()


def test_revocation_blocks_future_assessment_without_rewriting_history(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        record, processing, derived = _issue(lab)
        created = _count(lab.ledger.path, "SELECT count(*) FROM aip_grounding_audit WHERE event='derived_delivery_grant_changed'")
        revoked = _record(lab, version=2, enabled=False)
        new = lab.ledger.change_derived_grant(
            lab.admin["ORG-A"], revoked, expected_processing_revision=processing, expected_derived_revision=derived)
        assert new == derived + 1
        assert lab.ledger.policy(lab.executor["ORG-A"]).revision == processing
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.assess_derived_delivery(lab.executor["ORG-A"], _query(revoked, processing, new))
        assert caught.value.reason == "processing_not_granted"
        assert _count(lab.ledger.path,
                      "SELECT count(*) FROM aip_grounding_audit WHERE event='derived_delivery_grant_changed'") == created + 1
        assert _count(lab.ledger.path, "SELECT enabled FROM aip_derived_delivery_grant") == 0
    finally:
        lab.close()


def test_stale_derived_revision_is_rejected(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        record, processing, derived = _issue(lab)
        stale = _record(lab, version=2, enabled=False)
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.change_derived_grant(
                lab.admin["ORG-A"], stale, expected_processing_revision=processing, expected_derived_revision=derived - 1)
        assert caught.value.reason == "revision_conflict"
        assert _count(lab.ledger.path, "SELECT version FROM aip_derived_delivery_grant") == record.version
    finally:
        lab.close()


def test_foreign_or_inactive_processing_grant_cannot_back_a_derived_grant(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        processing = lab.ledger.policy(lab.executor["ORG-A"]).revision
        foreign = _record(lab, processing_grant_id="processing-grant-b")
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.change_derived_grant(
                lab.admin["ORG-A"], foreign, expected_processing_revision=processing, expected_derived_revision=0)
        assert caught.value.reason == "processing_not_granted"
        lab.change_grant(enabled=False)
        processing = lab.ledger.policy(lab.executor["ORG-A"]).revision
        inactive = _record(lab)
        with pytest.raises(ExecutionError) as inactive_caught:
            lab.ledger.change_derived_grant(
                lab.admin["ORG-A"], inactive, expected_processing_revision=processing, expected_derived_revision=0)
        assert inactive_caught.value.reason == "processing_not_granted"
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_derived_delivery_grant") == 0
    finally:
        lab.close()


def test_cross_organization_query_reveals_nothing(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        record, processing, derived = _issue(lab)
        foreign = _query(record, processing, derived, organization_id="ORG-B", resource_id="vacation-b")
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.assess_derived_delivery(lab.executor["ORG-A"], foreign)
        assert caught.value.reason == "processing_not_granted"
        assert str(caught.value) == "processing_not_granted"
        rows = lab.ledger.read_derived_audit(lab.admin["ORG-B"])
        assert rows == ()
        visible = lab.ledger.read_derived_audit(lab.admin["ORG-A"])
        assert all(row["organization_id"] == "ORG-A" for row in visible)
        assert all(row["resource_id"] is None for row in visible if row["reason"] == "scope_mismatch")
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_grounding_audit WHERE resource_id='vacation-b'") == 0
    finally:
        lab.close()


def test_unrecognized_operator_gets_no_organization(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        record, processing, derived = _issue(lab)
        forged = lab.issuer.issue("ORG-Z", "executor")
        lab.issuer.issued.pop(id(forged))
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.assess_derived_delivery(forged, _query(record, processing, derived, organization_id="ORG-Z"))
        assert caught.value.reason == "authority_unverifiable"
        with _connect(lab.ledger.path) as connection:
            row = connection.execute(
                "SELECT * FROM aip_grounding_audit WHERE reason='authority_unverifiable'").fetchone()
        assert row["organization_id"] is None and row["principal_id"] is None and row["resource_id"] is None
        assert lab.ledger.read_derived_audit(lab.admin["ORG-A"])[-1]["reason"] != "authority_unverifiable"
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_grounding_audit WHERE organization_id='ORG-Z'") == 0
    finally:
        lab.close()


def test_auditor_can_read_only_its_organization(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        _issue(lab)
        auditor = lab.issuer.issue("ORG-A", "auditor")
        record = _record(lab, version=2, enabled=False)
        processing = lab.ledger.policy(lab.executor["ORG-A"]).revision
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.change_derived_grant(
                auditor, record, expected_processing_revision=processing, expected_derived_revision=1)
        assert caught.value.reason == "scope_mismatch"
        visible = lab.ledger.read_derived_audit(auditor)
        assert visible and all(row["organization_id"] == "ORG-A" for row in visible)
        assert lab.ledger.read_derived_audit(lab.issuer.issue("ORG-B", "auditor")) == ()
    finally:
        lab.close()


def test_denial_before_execution_creates_no_execution_or_decision(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        record, processing, derived = _issue(lab)
        executions = _count(lab.ledger.path, "SELECT count(*) FROM aip_execution")
        missing = _query(record, processing, derived, derived_grant_id="derived-grant-missing")
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.assess_derived_delivery(lab.executor["ORG-A"], missing)
        assert caught.value.reason == "processing_not_granted"
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_execution") == executions
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_delivery_decision") == 0
        assert _count(lab.ledger.path,
                      "SELECT count(*) FROM aip_grounding_audit WHERE event='ai_derived_delivery_denied' "
                      "AND reason='derived_delivery_not_granted'") == 1
        with pytest.raises(ExecutionError) as suppressed:
            lab.ledger.suppress_derived_delivery(lab.executor["ORG-A"], str(uuid4()))
        assert suppressed.value.reason == "lease_invalid"
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_execution") == executions
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_delivery_decision") == 0
    finally:
        lab.close()


def test_suppression_after_attempt_does_not_authorize_delivery(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        lab.prepare("a")
        operation_id = _count(lab.ledger.path, "SELECT operation_id FROM aip_execution")
        lab.ledger.suppress_derived_delivery(lab.executor["ORG-A"], operation_id)
        with _connect(lab.ledger.path) as connection:
            row = connection.execute("SELECT * FROM aip_delivery_decision").fetchone()
        assert row["state"] == "SUPPRESSED" and row["uncertainty_recorded"] == 0
        assert row["derived_grant_id"] is None and row["recipient_id"] == "recipient-a"
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_delivery_decision WHERE state!='SUPPRESSED'") == 0
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.suppress_derived_delivery(lab.executor["ORG-A"], operation_id)
        assert caught.value.reason == "revision_conflict"
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_delivery_decision") == 1
    finally:
        lab.close()


def test_audit_failure_does_not_count_as_a_persisted_denial(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        record, processing, derived = _issue(lab)

        def fault(stage):
            if stage == "audit_ai_derived_delivery_denied":
                raise OSError(stage)
        lab.ledger._fault = fault
        with pytest.raises(ExecutionError):
            lab.ledger.assess_derived_delivery(
                lab.executor["ORG-A"], _query(record, processing, derived, derived_grant_id="derived-grant-missing"))
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_grounding_audit WHERE event='ai_derived_delivery_denied'") == 0
    finally:
        lab.close()


def test_sqlite_wal_and_audit_do_not_contain_payload(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        record, processing, derived = _issue(lab)
        with pytest.raises(ExecutionError):
            lab.ledger.assess_derived_delivery(
                lab.executor["ORG-A"], _query(record, processing, derived, resource_id="vacation-missing"))
        for suffix in ("", "-wal", "-shm", "-journal"):
            candidate = Path(str(lab.ledger.path) + suffix)
            if candidate.exists():
                assert CANARY not in candidate.read_bytes()
                assert b"VACACIONES" not in candidate.read_bytes()
        with _connect(lab.ledger.path) as connection:
            blob = " ".join("" if value is None else str(value)
                            for row in connection.execute("SELECT * FROM aip_grounding_audit") for value in row)
        assert "VACACIONES" not in blob and CANARY.decode("ascii") not in blob
    finally:
        lab.close()


def test_administrative_contention_allows_one_grant(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        record = _record(lab)
        processing = lab.ledger.policy(lab.executor["ORG-A"]).revision
        outcomes = []

        def attempt():
            try:
                outcomes.append(lab.ledger.change_derived_grant(
                    lab.admin["ORG-A"], record, expected_processing_revision=processing, expected_derived_revision=0))
            except ExecutionError as error:
                outcomes.append(error.reason)

        with ThreadPoolExecutor(max_workers=2) as pool:
            tuple(pool.map(lambda _: attempt(), (0, 1)))
        assert sorted(outcomes, key=str) == [1, "revision_conflict"]
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_derived_delivery_grant") == 1
        assert _count(lab.ledger.path, "SELECT revision FROM aip_derived_revision") == 1
    finally:
        lab.close()


def test_caller_text_or_identifier_cannot_mint_a_permission(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        with pytest.raises(TypeError):
            DerivedDeliveryGrant(content_kind=DERIVED_KIND, delivery_operation=DERIVED_OPERATION)
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.change_derived_grant(
                lab.admin["ORG-A"], DERIVED_KIND, expected_processing_revision=1, expected_derived_revision=0)
        assert caught.value.reason == "invalid_input"
        with pytest.raises(sqlite3.IntegrityError):
            with _connect(lab.ledger.path) as connection:
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute(
                    "INSERT INTO aip_derived_delivery_grant(organization_id,derived_grant_id,version,enabled,"
                    "principal_id,instance_id,tenant_id,resource_id,recipient_id,content_kind,delivery_operation,"
                    "purpose,classification,registered_version,processing_grant_id,processing_grant_version,"
                    "processing_revision,derived_delivery_revision,valid_from_us,expires_at_us,review_due_at_us) "
                    "VALUES ('ORG-A','caller-grant',1,1,'principal-a','instance-a','tenant-a','vacation-a',"
                    "'recipient-a','caller-authored','enterprise.answer.deliver','synthetic-policy-question-answering',"
                    "'synthetic-internal',1,'processing-grant-a',1,1,1,1,2,2)")
        assert _count(lab.ledger.path, "SELECT count(*) FROM aip_derived_delivery_grant") == 0
    finally:
        lab.close()


def test_held_reservation_blocks_migration_without_release(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        lab.prepare("a")
        lab.ledger._live.clear()
        with pytest.raises(ExecutionError) as caught:
            lab.ledger.migrate_to_v2(lab.admin["ORG-A"])
        assert caught.value.reason == "lease_invalid"
        assert _count(lab.ledger.path, "SELECT reservation_state FROM aip_execution") == "HELD"
        assert _count(lab.ledger.path, "SELECT schema_version FROM aip_store") == 1
    finally:
        lab.close()


def test_no_egress(no_network):
    assert no_network == []


def test_predicate_misses_share_one_public_denial(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        record, processing, derived = _issue(lab)
        revoked = _record(lab, version=2, enabled=False)
        current = lab.ledger.change_derived_grant(
            lab.admin["ORG-A"], revoked, expected_processing_revision=processing, expected_derived_revision=derived)
        past = lab.clock() - timedelta(minutes=5)
        expired = _record(lab, derived_grant_id="derived-grant-expired", version=1, valid_from=past,
                          expires_at=past + timedelta(minutes=1), review_due_at=past + timedelta(seconds=30))
        final = lab.ledger.change_derived_grant(
            lab.admin["ORG-A"], expired, expected_processing_revision=processing, expected_derived_revision=current)
        probes = (
            _query(revoked, processing, final),
            _query(record, processing, derived),
            _query(record, processing, final, derived_grant_id="derived-grant-missing"),
            _query(record, processing, final, organization_id="ORG-B", resource_id="vacation-b", recipient_id="recipient-b"),
            _query(expired, processing, final),
        )
        seen = []
        for query in probes:
            with pytest.raises(ExecutionError) as caught:
                lab.ledger.assess_derived_delivery(lab.executor["ORG-A"], query)
            seen.append(str(caught.value))
        assert seen == ["processing_not_granted"] * len(probes)
        with _connect(lab.ledger.path) as connection:
            leaked = connection.execute(
                "SELECT count(*) FROM aip_grounding_audit WHERE resource_id='vacation-b' OR recipient_id='recipient-b' "
                "OR organization_id='ORG-B'").fetchone()[0]
            reasons = {row[0] for row in connection.execute(
                "SELECT reason FROM aip_grounding_audit WHERE event='ai_derived_delivery_denied'")}
        assert leaked == 0
        assert {"derived_delivery_not_granted", "policy_changed", "authorization_expired", "scope_mismatch"} <= reasons
        auditor = lab.issuer.issue("ORG-A", "auditor")
        with pytest.raises(ExecutionError) as missing_role:
            lab.ledger.assess_derived_delivery(auditor, _query(record, processing, current, derived_grant_id="derived-grant-missing"))
        with pytest.raises(ExecutionError) as present_role:
            lab.ledger.assess_derived_delivery(auditor, _query(expired, processing, final))
        assert str(missing_role.value) == str(present_role.value) == "scope_mismatch"
    finally:
        lab.close()


def test_terminal_history_keeps_its_meaning_after_migration(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        result = lab.gateway.invoke_once(lab.prepare("a"))
        assert result.state == "COMPLETED"
        with _connect(lab.ledger.path) as connection:
            before_store = connection.execute("SELECT store_id,revision,next_audit_seq FROM aip_store").fetchone()
            before_exec = [tuple(row) for row in connection.execute("SELECT * FROM aip_execution")]
            before_audit = [tuple(row) for row in connection.execute("SELECT * FROM aip_audit")]
            before_grants = [tuple(row) for row in connection.execute("SELECT * FROM aip_grant")]
        _migrate(lab)
        with _connect(lab.ledger.path) as connection:
            after_store = connection.execute("SELECT store_id,revision,next_audit_seq FROM aip_store").fetchone()
            assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
            assert schema_ddl(connection) == lab.ledger._ddl_v2
            assert [tuple(row) for row in connection.execute("SELECT * FROM aip_execution")] == before_exec
            assert [tuple(row) for row in connection.execute("SELECT * FROM aip_audit")] == before_audit
            assert [tuple(row) for row in connection.execute("SELECT * FROM aip_grant")] == before_grants
        assert tuple(after_store) == tuple(before_store)
        assert lab.ledger.policy(lab.executor["ORG-A"]).revision == before_store["revision"]
    finally:
        lab.close()


def test_fresh_initialized_store_migrates(tmp_path):
    lab = execution_laboratory(tmp_path)
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    ledger = SQLiteExecutionLedger(fresh, lab.issuer, lab.clock)
    try:
        ledger.initialize(lab.admin["ORG-A"])
        with _connect(ledger.path) as connection:
            before = connection.execute("SELECT store_id,revision,next_audit_seq FROM aip_store").fetchone()
            audits = [tuple(row) for row in connection.execute("SELECT * FROM aip_audit")]
        ledger.migrate_to_v2(lab.admin["ORG-A"])
        with _connect(ledger.path) as connection:
            after = connection.execute("SELECT store_id,revision,next_audit_seq,schema_version FROM aip_store").fetchone()
            assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
            assert [tuple(row) for row in connection.execute("SELECT * FROM aip_audit")] == audits
        assert after["store_id"] == before["store_id"] and after["revision"] == 1
        assert after["next_audit_seq"] == before["next_audit_seq"] and after["schema_version"] == 2
    finally:
        ledger.close()
        lab.close()


def test_each_organization_has_its_own_derived_revision(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        _migrate(lab)
        _, processing, derived_a = _issue(lab)
        other = lab.ledger.policy(lab.executor["ORG-B"]).grants[0]
        now = lab.clock()
        record_b = DerivedDeliveryGrant(
            "ORG-B", "derived-grant-b", 1, True, other.principal_id, other.instance_id, other.tenant_id,
            other.resource_id, other.recipient_id, 1, other.grant_id, other.version,
            now, now + timedelta(minutes=5), now + timedelta(minutes=4))
        derived_b = lab.ledger.change_derived_grant(
            lab.admin["ORG-B"], record_b, expected_processing_revision=processing, expected_derived_revision=0)
        assert derived_a == 1 and derived_b == 1
        assert _count(lab.ledger.path, "SELECT revision FROM aip_derived_revision WHERE organization_id='ORG-A'") == 1
        assert _count(lab.ledger.path, "SELECT revision FROM aip_derived_revision WHERE organization_id='ORG-B'") == 1
        assert lab.ledger.policy(lab.executor["ORG-A"]).revision == processing
    finally:
        lab.close()
