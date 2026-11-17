"""Operational V4 enforcement. Caller arguments do not widen the stored permit."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.remote_authorization import RESERVATION_MICROUSD, RemoteAuthorization
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.permit import RemoteExecutionPermit
from app.model_gateway.gateway import NeutralModelGateway
from tests.test_model_gateway_durable_authorization import (
    BUDGET, DEPLOYMENT, RESOURCE, _gateway, _ready, _register, _run,
)


def test_matching_principal_resource_and_budget_keep_the_catalog_reservation(tmp_path):
    lab = _ready(tmp_path)
    _register(lab)
    gateway = _gateway(lab)
    reservation = gateway._registry.get(DEPLOYMENT).reservation_microusd
    floor = _run(gateway, lab, budget=reservation)
    assert floor.accepted is True and floor.reserved_microusd == reservation
    within = _gateway(lab)
    covered = _run(within, lab, budget=BUDGET)
    assert covered.accepted is True and covered.reserved_microusd == reservation
    assert covered.reserved_microusd != BUDGET
    with sqlite3.connect(lab.ledger.path) as connection:
        allow = connection.execute(
            "SELECT contract,reason FROM aip_remote_authorization_audit "
            "WHERE outcome='ALLOW' ORDER BY audit_seq DESC").fetchone()
    assert allow == ("enterprise-remote-authorization-audit-v2", "accepted")
    lab.close()


def test_principal_resource_and_budget_cannot_be_widened(tmp_path):
    lab = _ready(tmp_path)
    _register(lab)
    other = lab.issuer.issue("ORG-A", "executor", principal_id="other-principal")
    moved = _gateway(lab)
    with pytest.raises(ProviderError) as principal:
        _run(moved, lab, access=other)
    assert principal.value.reason == "scope_mismatch" and moved._adapters[DEPLOYMENT].calls == 0
    alien = _gateway(lab)
    with pytest.raises(ProviderError) as resource:
        _run(alien, lab, resource="vacation-b")
    assert resource.value.reason == "scope_mismatch" and alien._adapters[DEPLOYMENT].calls == 0
    for budget in (10_000_000, 190, True):
        gateway = _gateway(lab)
        with pytest.raises(ProviderError) as denied:
            _run(gateway, lab, budget=budget)
        expected = "invalid_input" if budget is True else "budget_exceeded"
        assert denied.value.reason == expected and gateway._adapters[DEPLOYMENT].calls == 0
    with sqlite3.connect(lab.ledger.path) as connection:
        reasons = {row[0] for row in connection.execute(
            "SELECT reason FROM aip_remote_authorization_audit WHERE contract=?",
            ("enterprise-remote-authorization-audit-v2",))}
    assert "budget_exceeded" in reasons
    assert gateway._registry.get(DEPLOYMENT).reservation_microusd == 191
    lab.close()


def test_v3_and_unaudited_v4_do_not_authorize_the_gateway(tmp_path):
    (tmp_path / "v3").mkdir()
    old = _ready_without_audit(tmp_path / "v3", audit=False, binding=False)
    gateway = _gateway(old)
    with pytest.raises(ProviderError) as v3:
        _run(gateway, old)
    assert v3.value.reason == "authority_unverifiable" and gateway._adapters[DEPLOYMENT].calls == 0
    with sqlite3.connect(old.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 3
    (tmp_path / "v4").mkdir()
    stored = _ready_without_audit(tmp_path / "v4", audit=False, binding=True)
    plain = _gateway(stored)
    with pytest.raises(ProviderError) as unaudited:
        _run(plain, stored)
    assert unaudited.value.reason == "authority_unverifiable" and plain._adapters[DEPLOYMENT].calls == 0
    source = Path(__file__).resolve().parents[1] / "app" / "model_gateway" / "gateway.py"
    text = source.read_text(encoding="utf-8")
    assert "RemoteExecutionPermit" not in text and "OfflineModelHarness" not in text
    published = Path(__file__).resolve().parents[1] / "app" / "enterprise_ai_processing" / "migrations" / "004_remote_authorization_binding.sql"
    assert "budget_exceeded" not in published.read_text(encoding="utf-8")
    old.close()
    stored.close()


def test_invalid_shapes_memory_permit_and_unreadable_store_stay_closed(tmp_path):
    lab = _ready(tmp_path)
    _register(lab, budget_ceiling_microusd=5_000_000)
    gateway = _gateway(lab)
    covered = _run(gateway, lab, budget=5_000_000)
    assert covered.reserved_microusd == RESERVATION_MICROUSD[DEPLOYMENT] == 191
    over_cap = _gateway(lab)
    with pytest.raises(ProviderError) as cap:
        _run(over_cap, lab, budget=5_000_001)
    assert cap.value.reason == "budget_exceeded" and over_cap._adapters[DEPLOYMENT].calls == 0
    for budget in (190.5, "1000", False, -1):
        denied_gateway = _gateway(lab)
        with pytest.raises(ProviderError) as denied:
            _run(denied_gateway, lab, budget=budget)
        assert denied.value.reason == "invalid_input" and denied_gateway._adapters[DEPLOYMENT].calls == 0
    prefix = _gateway(lab)
    with pytest.raises(ProviderError) as shortened:
        _run(prefix, lab, resource="vacation")
    assert shortened.value.reason == "scope_mismatch" and prefix._adapters[DEPLOYMENT].calls == 0
    wildcard = _gateway(lab)
    with pytest.raises(ProviderError) as star:
        _run(wildcard, lab, resource="*")
    assert star.value.reason == "invalid_input" and wildcard._adapters[DEPLOYMENT].calls == 0
    now = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
    permit = RemoteExecutionPermit(
        "ORG-A", "synthetic-executor", "instance-a", RESOURCE, "synthetic-policy-question-answering",
        "synthetic-internal", "openai", "gpt-6-luna", "vacation-days-v1", 1,
        now - timedelta(minutes=1), now + timedelta(minutes=5), True)
    memory = _gateway(lab)
    with pytest.raises(ProviderError) as in_memory:
        memory.execute(permit, "remote-ops-a", BUDGET, RESOURCE, DEPLOYMENT)
    assert in_memory.value.reason == "authority_unverifiable" and memory._adapters[DEPLOYMENT].calls == 0
    lab.ledger.path.write_bytes(b"not a sqlite database")
    unread = _gateway(lab)
    with pytest.raises(ProviderError) as broken:
        _run(unread, lab)
    assert broken.value.reason == "storage_unavailable" and unread._adapters[DEPLOYMENT].calls == 0
    lab.close()


def test_denied_budget_audit_failure_does_not_allow(tmp_path):
    lab = _ready(tmp_path)
    _register(lab)

    def fail(stage):
        if stage == "audit_remote_authorization_denied":
            raise OSError("disk")

    lab.ledger._fault = fail
    gateway = _gateway(lab)
    with pytest.raises(ProviderError) as denied:
        _run(gateway, lab, budget=10_000_000)
    assert denied.value.reason == "storage_unavailable" and gateway._adapters[DEPLOYMENT].calls == 0
    with sqlite3.connect(lab.ledger.path) as connection:
        reasons = {row[0] for row in connection.execute("SELECT reason FROM aip_remote_authorization_audit")}
        allows = connection.execute(
            "SELECT count(*) FROM aip_remote_authorization_audit WHERE outcome='ALLOW'").fetchone()[0]
    assert "budget_exceeded" not in reasons and allows == 0
    lab.close()


def test_audit_migration_keeps_previous_rows_and_rolls_back(tmp_path):
    lab = _ready_without_audit(tmp_path, audit=False, binding=True)
    before = _audit_rows(lab.ledger.path)

    def fail(stage):
        if stage == "migrate_audit_v2_before_commit":
            raise OSError("disk")

    lab.ledger._fault = fail
    with pytest.raises(ExecutionError) as failed:
        lab.ledger.migrate_remote_audit_v2(lab.admin["ORG-A"])
    assert failed.value.unavailable is True
    assert _audit_rows(lab.ledger.path) == before
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 4
    lab.ledger._fault = lambda stage: None
    lab.ledger.migrate_remote_audit_v2(lab.admin["ORG-A"])
    assert _audit_rows(lab.ledger.path) == before
    with pytest.raises(ExecutionError) as repeated:
        lab.ledger.migrate_remote_audit_v2(lab.admin["ORG-A"])
    assert repeated.value.reason == "revision_conflict"
    lab.close()


def _ready_without_audit(tmp_path, *, audit, binding):
    from tests.enterprise_ai_processing_execution_fixture import execution_laboratory

    lab = execution_laboratory(tmp_path)
    lab.ledger.migrate_to_v2(lab.admin["ORG-A"])
    lab.ledger.migrate_to_v3(lab.admin["ORG-A"])
    now = lab.clock()
    values = dict(
        authorization_id="remote-ops-a", organization_id="ORG-A", deployment_id=DEPLOYMENT,
        provider_id="openai", model_id="gpt-6-luna", valid_from=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=5))
    if binding:
        lab.ledger.migrate_to_v4(lab.admin["ORG-A"])
        values.update(principal_id="synthetic-executor", resource_id=RESOURCE, budget_ceiling_microusd=1000)
    record = RemoteAuthorization(**values)
    lab.ledger.register_remote_authorization(lab.admin["ORG-A"], record)
    if audit:
        lab.ledger.migrate_remote_audit_v2(lab.admin["ORG-A"])
    return lab


def _audit_rows(path):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT event_id,audit_seq,contract,reason FROM aip_remote_authorization_audit ORDER BY audit_seq"
        ).fetchall()
