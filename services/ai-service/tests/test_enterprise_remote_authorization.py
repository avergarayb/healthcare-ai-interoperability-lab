"""Durable remote authorization. An active row does not open a provider socket."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import socket
import sqlite3

import pytest

from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.remote_authorization import RemoteAuthorization, classify
from app.enterprise_ai_processing.sqlite_ledger import MIGRATION_V3, SQLiteExecutionLedger
from app.enterprise_llm_providers.configuration import ProviderSettings
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.request import build_payload
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT
from app.enterprise_llm_providers.transport import OpenAISDKTransport, live_egress_enabled
from app.model_gateway.contracts import ExecutionPolicy
from tests.enterprise_ai_processing_execution_fixture import execution_laboratory


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("provider socket forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)


def _ready(tmp_path):
    lab = execution_laboratory(tmp_path)
    lab.ledger.migrate_to_v2(lab.admin["ORG-A"])
    lab.ledger.migrate_to_v3(lab.admin["ORG-A"])
    return lab


def _record(lab, **overrides):
    now = lab.clock()
    values = dict(
        authorization_id="remote-auth-a", organization_id="ORG-A", deployment_id="openai-sdk-a",
        provider_id="openai", model_id="gpt-6-luna", valid_from=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=5))
    values.update(overrides)
    return RemoteAuthorization(**values)


def _register(lab, **overrides):
    record = _record(lab, **overrides)
    lab.ledger.register_remote_authorization(lab.admin[record.organization_id], record)
    return record


def test_create_and_read_back_the_same_grant(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)
    decision = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], record)
    assert decision.allowed is True and decision.reason == "accepted"
    assert decision.authorization_id == record.authorization_id
    assert decision.egress_allowed is False and decision.live_authorized is False and decision.c03_connected is False
    lab.close()


def test_grant_survives_reopen(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)
    root, issuer, clock = lab.ledger.root, lab.issuer, lab.clock
    lab.close()
    again = SQLiteExecutionLedger(root, issuer, clock)
    try:
        decision = again.evaluate_remote_authorization(issuer.issue("ORG-A", "executor"), record)
        assert decision.allowed is True and decision.egress_allowed is False
    finally:
        again.close()


def test_missing_grant_is_denied(tmp_path):
    lab = _ready(tmp_path)
    decision = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], _record(lab))
    assert decision.allowed is False and decision.reason == "not_granted"
    lab.close()


def test_other_organization_cannot_use_the_grant(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)
    foreign = _record(lab, organization_id="ORG-B")
    decision = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], foreign)
    assert decision.allowed is False and decision.reason == "scope_mismatch"
    hidden = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-B"], foreign)
    assert hidden.allowed is False and hidden.reason == "not_granted"
    still = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], record)
    assert still.allowed is True
    lab.close()


@pytest.mark.parametrize("field,reason", [
    ("deployment_id", "wrong_deployment"),
    ("provider_id", "wrong_provider"),
    ("model_id", "wrong_model"),
    ("operation_id", "operation_denied"),
])
def test_classifier_rejects_a_different_scope(field, reason):
    row = {
        "deployment_id": "openai-sdk-a", "provider_id": "openai", "model_id": "gpt-6-luna",
        "operation_id": "vacation-days-v1", "status": "active", "valid_from_us": 1, "expires_at_us": 5,
    }
    query = RemoteAuthorization(
        "remote-auth-a", "ORG-A", "openai-sdk-a", "openai", "gpt-6-luna",
        datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc))
    changed = dict(deployment_id=query.deployment_id, provider_id=query.provider_id, model_id=query.model_id,
                   operation_id=query.operation_id)
    changed[field] = "other"
    query = RemoteAuthorization(
        query.authorization_id, query.organization_id, changed["deployment_id"], changed["provider_id"],
        changed["model_id"], query.valid_from, query.expires_at, operation_id=changed["operation_id"])
    assert classify(row, 3, query) == reason


def test_ledger_denies_a_different_deployment_and_an_illegal_model(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)
    moved = _record(lab, deployment_id="openai-offline-a")
    decision = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], moved)
    assert decision.allowed is False and decision.reason == "wrong_deployment"
    illegal = lab.ledger.evaluate_remote_authorization(
        lab.executor["ORG-A"], _record(lab, model_id="gpt-6-sol"))
    assert illegal.allowed is False and illegal.reason == "invalid_input"
    assert record.deployment_id == "openai-sdk-a"
    lab.close()


def test_ledger_rejects_a_model_outside_the_closed_scope(tmp_path):
    lab = _ready(tmp_path)
    with pytest.raises(ExecutionError) as caught:
        _register(lab, model_id="gpt-6-sol")
    assert caught.value.reason == "invalid_input"
    lab.close()


def test_grant_not_yet_effective_and_expired_are_denied(tmp_path):
    lab = _ready(tmp_path)
    now = lab.clock()
    future = _register(lab, authorization_id="remote-future", valid_from=now + timedelta(minutes=5),
                       expires_at=now + timedelta(minutes=10))
    early = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], future)
    assert early.allowed is False and early.reason == "not_yet_effective"
    expired = _register(lab, authorization_id="remote-expired", deployment_id="openai-offline-a",
                        valid_from=now - timedelta(minutes=10), expires_at=now - timedelta(minutes=1))
    late = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], expired)
    assert late.allowed is False and late.reason == "authorization_expired"
    lab.close()


def test_revoked_grant_cannot_be_reactivated(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)
    lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], record.authorization_id, "operator_revoked")
    denied = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], record)
    assert denied.allowed is False and denied.reason == "revoked"
    with pytest.raises(ExecutionError) as again:
        lab.ledger.register_remote_authorization(lab.admin["ORG-A"], record)
    with pytest.raises(ExecutionError) as twice:
        lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], record.authorization_id, "operator_revoked")
    assert again.value.reason == twice.value.reason == "revision_conflict"
    assert not hasattr(lab.ledger, "reactivate_remote_authorization")
    lab.close()


def test_duplicate_identifier_and_duplicate_active_scope_conflict(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)
    with pytest.raises(ExecutionError) as same_id:
        lab.ledger.register_remote_authorization(
            lab.admin["ORG-A"], _record(lab, deployment_id="openai-offline-a"))
    with pytest.raises(ExecutionError) as same_scope:
        lab.ledger.register_remote_authorization(
            lab.admin["ORG-A"], _record(lab, authorization_id="remote-auth-b"))
    assert same_id.value.reason == same_scope.value.reason == "revision_conflict"
    assert record.authorization_id == "remote-auth-a"
    lab.close()


def test_malformed_records_and_invalid_dates_are_rejected(tmp_path):
    lab = _ready(tmp_path)
    now = lab.clock()
    with pytest.raises(ExecutionError) as bad_id:
        lab.ledger.register_remote_authorization(lab.admin["ORG-A"], _record(lab, authorization_id=""))
    with pytest.raises(ExecutionError) as backwards:
        lab.ledger.register_remote_authorization(
            lab.admin["ORG-A"], _record(lab, valid_from=now + timedelta(minutes=5), expires_at=now))
    with pytest.raises(ExecutionError) as naive:
        lab.ledger.register_remote_authorization(lab.admin["ORG-A"], _record(
            lab, valid_from=datetime(2026, 1, 1), expires_at=datetime(2026, 1, 2)))
    assert bad_id.value.reason == backwards.value.reason == naive.value.reason == "invalid_input"
    lab.close()


def test_storage_failure_denies_without_a_false_allow(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)

    def fault(stage):
        if stage == "audit_remote_authorization_evaluated":
            raise OSError("disk")

    lab.ledger._fault = fault
    decision = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], record)
    assert decision.allowed is False and decision.reason == "storage_unavailable"
    assert decision.egress_allowed is False
    lab.close()


def test_concurrent_evaluations_stay_closed(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)

    def once():
        return lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], record)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [item.result() for item in (pool.submit(once), pool.submit(once))]
    assert [item.allowed for item in results] == [True, True]
    assert {item.egress_allowed for item in results} == {False}
    lab.close()


def test_empty_migration_adds_no_grant_and_leaves_v2_intact(tmp_path):
    lab = execution_laboratory(tmp_path)
    lab.ledger.migrate_to_v2(lab.admin["ORG-A"])
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 2
    denied = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], _record(lab))
    assert denied.allowed is False and denied.reason == "authority_unverifiable"
    lab.ledger.migrate_to_v3(lab.admin["ORG-A"])
    sql = MIGRATION_V3.read_text(encoding="utf-8")
    assert "INSERT INTO aip_remote_execution_permit" not in sql
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute("SELECT schema_version,contract FROM aip_store").fetchone() == (
            3, "enterprise-ai-processing-ledger-v3")
        assert connection.execute("SELECT count(*) FROM aip_remote_execution_permit").fetchone()[0] == 0
    with pytest.raises(ExecutionError) as repeated:
        lab.ledger.migrate_to_v3(lab.admin["ORG-A"])
    assert repeated.value.reason == "revision_conflict"
    lab.close()


def test_audit_keeps_identifiers_and_drops_sensitive_text(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)
    lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], record)
    with sqlite3.connect(lab.ledger.path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM aip_remote_authorization_audit").fetchall()
        names = set(rows[0].keys())
    rendered = " ".join(str(tuple(row)) for row in rows)
    assert names.isdisjoint({"prompt", "document", "api_key", "source_excerpt", "credential"})
    assert "VACACIONES" not in rendered and "sk-" not in rendered and "AIza" not in rendered
    assert any(row["event"] == "remote_authorization_registered" for row in rows)
    lab.close()


def test_neutral_contracts_and_egress_stay_closed(tmp_path):
    with pytest.raises(ProviderError):
        ExecutionPolicy(allow_egress=True)
    gateway = Path(__file__).resolve().parents[1] / "app" / "model_gateway" / "gateway.py"
    processing = gateway.parent.parent / "enterprise_ai_processing" / "gateway.py"
    assert "evaluate_remote_authorization" not in gateway.read_text(encoding="utf-8")
    assert "type(self.model) is FakeEnterpriseModel" in processing.read_text(encoding="utf-8")
    assert live_egress_enabled() is False
    settings = ProviderSettings(True, "gpt-6-luna", 15, 256, 2048, 1000, 5_000_000, "sk-lab-not-a-real-key")
    with pytest.raises(ProviderError) as blocked:
        OpenAISDKTransport("sk-lab-not-a-real-key").send(build_payload(FIXED_DOCUMENT, settings), 15)
    assert blocked.value.reason == "egress_blocked"
    lab = _ready(tmp_path)
    decision = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], _register(lab))
    assert decision.allowed is True and decision.live_authorized is False and decision.c03_connected is False
    main = gateway.parents[1] / "main.py"
    assert "register_remote_authorization" not in main.read_text(encoding="utf-8")
    assert "revoke_remote_authorization" not in main.read_text(encoding="utf-8")
    lab.close()


def test_audit_failure_rolls_back_the_permission_change(tmp_path):
    lab = _ready(tmp_path)

    def fail(stage):
        if stage == "audit_remote_authorization_registered":
            raise OSError("disk")

    lab.ledger._fault = fail
    with pytest.raises(ExecutionError) as denied:
        _register(lab)
    assert denied.value.unavailable is True
    lab.ledger._fault = lambda stage: None
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute("SELECT count(*) FROM aip_remote_execution_permit").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM aip_remote_authorization_audit").fetchone()[0] == 0
    record = _register(lab)

    def fail_revoke(stage):
        if stage == "audit_remote_authorization_revoked":
            raise OSError("disk")

    lab.ledger._fault = fail_revoke
    with pytest.raises(ExecutionError) as still:
        lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], record.authorization_id, "operator_revoked")
    assert still.value.unavailable is True
    lab.ledger._fault = lambda stage: None
    decision = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], record)
    assert decision.allowed is True and decision.reason == "accepted" and decision.egress_allowed is False
    lab.close()


def test_failed_v3_migration_preserves_v2_rows(tmp_path):
    lab = execution_laboratory(tmp_path)
    lab.ledger.migrate_to_v2(lab.admin["ORG-A"])
    with sqlite3.connect(lab.ledger.path) as connection:
        before = (
            connection.execute("SELECT count(*) FROM aip_profile").fetchone()[0],
            connection.execute("SELECT count(*) FROM aip_grant").fetchone()[0],
            connection.execute("SELECT provider,model_id,destination FROM aip_profile").fetchall(),
        )

    def fail(stage):
        if stage == "migrate_v3_before_commit":
            raise OSError("disk")

    lab.ledger._fault = fail
    with pytest.raises(ExecutionError) as failed:
        lab.ledger.migrate_to_v3(lab.admin["ORG-A"])
    assert failed.value.unavailable is True
    lab.ledger._fault = lambda stage: None
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 2
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "aip_remote_execution_permit" not in names
        assert before == (
            connection.execute("SELECT count(*) FROM aip_profile").fetchone()[0],
            connection.execute("SELECT count(*) FROM aip_grant").fetchone()[0],
            connection.execute("SELECT provider,model_id,destination FROM aip_profile").fetchall(),
        )
    lab.ledger.migrate_to_v3(lab.admin["ORG-A"])
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 3
        assert connection.execute("SELECT count(*) FROM aip_remote_execution_permit").fetchone()[0] == 0
        assert before == (
            connection.execute("SELECT count(*) FROM aip_profile").fetchone()[0],
            connection.execute("SELECT count(*) FROM aip_grant").fetchone()[0],
            connection.execute("SELECT provider,model_id,destination FROM aip_profile").fetchall(),
        )
    lab.close()


def test_concurrent_writes_keep_one_active_row_and_a_terminal_revocation(tmp_path):
    lab = _ready(tmp_path)
    record = _record(lab, authorization_id="remote-race")

    def register(_item):
        try:
            lab.ledger.register_remote_authorization(lab.admin["ORG-A"], record)
            return "recorded"
        except ExecutionError as error:
            return error.reason

    with ThreadPoolExecutor(max_workers=2) as pool:
        registered = sorted(pool.map(register, (0, 1)))
    assert registered == ["recorded", "revision_conflict"]

    def revoke(_item):
        try:
            lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], record.authorization_id, "operator_revoked")
            return "recorded"
        except ExecutionError as error:
            return error.reason

    with ThreadPoolExecutor(max_workers=2) as pool:
        revoked = sorted(pool.map(revoke, (0, 1)))
    assert revoked == ["recorded", "revision_conflict"]
    decision = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], record)
    assert decision.allowed is False and decision.reason == "revoked"
    with pytest.raises(ExecutionError) as again:
        lab.ledger.register_remote_authorization(lab.admin["ORG-A"], record)
    assert again.value.reason == "revision_conflict"
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM aip_remote_execution_permit WHERE status='active'").fetchone()[0] == 0
    lab.close()


def test_validity_includes_the_start_and_excludes_the_expiry(tmp_path):
    lab = _ready(tmp_path)
    start = lab.clock()
    record = _register(lab, authorization_id="remote-window", valid_from=start, expires_at=start + timedelta(minutes=2))
    opened = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], record)
    assert opened.allowed is True and opened.reason == "accepted"
    lab.clock.advance(120)
    closed = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], record)
    assert closed.allowed is False and closed.reason == "authorization_expired" and closed.egress_allowed is False
    with pytest.raises(ExecutionError) as equal:
        lab.ledger.register_remote_authorization(lab.admin["ORG-A"], _record(
            lab, authorization_id="remote-equal", deployment_id="openai-offline-a",
            valid_from=start, expires_at=start))
    assert equal.value.reason == "invalid_input"
    lab.close()


def test_synthetic_executor_cannot_register_or_revoke(tmp_path):
    lab = _ready(tmp_path)
    record = _record(lab, authorization_id="remote-executor")
    with pytest.raises(ExecutionError) as register:
        lab.ledger.register_remote_authorization(lab.executor["ORG-A"], record)
    lab.ledger.register_remote_authorization(lab.admin["ORG-A"], record)
    with pytest.raises(ExecutionError) as revoke:
        lab.ledger.revoke_remote_authorization(lab.executor["ORG-A"], record.authorization_id, "operator_revoked")
    assert register.value.reason == revoke.value.reason == "scope_mismatch"
    decision = lab.ledger.evaluate_remote_authorization(lab.executor["ORG-A"], record)
    assert decision.allowed is True and decision.egress_allowed is False
    lab.close()
