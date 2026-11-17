"""One durable reservation per permit. A second gateway cannot replay it."""
from pathlib import Path
import sqlite3
import threading

import pytest

from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
from app.enterprise_llm_providers.errors import ProviderError
from app.model_gateway.gateway import NeutralModelGateway
from app.model_gateway.adapters import lab_adapters
from tests.test_model_gateway_durable_authorization import (
    BUDGET, DEPLOYMENT, RESOURCE, _Calls, _gateway, _ready, _register, _run,
)
from tests.test_model_gateway_trusted_enforcement import _ready_without_audit


def test_one_permit_survives_a_second_gateway_and_a_restart(tmp_path):
    lab = _ready(tmp_path)
    _register(lab)
    first = _gateway(lab)
    result = _run(first, lab, budget=191)
    assert result.accepted is True and result.reserved_microusd == 191 and first._adapters[DEPLOYMENT].calls == 1
    second = _gateway(lab)
    with pytest.raises(ProviderError) as replay:
        _run(second, lab)
    assert replay.value.reason == "replay_denied" and second._adapters[DEPLOYMENT].calls == 0
    root, issuer, clock = lab.ledger.root, lab.issuer, lab.clock
    lab.close()
    reopened = SQLiteExecutionLedger(root, issuer, clock)
    try:
        restarted = NeutralModelGateway(resolver=__resolver(reopened))
        with pytest.raises(ProviderError) as again:
            restarted.execute(issuer.issue("ORG-A", "executor"), "remote-ops-a", BUDGET, RESOURCE, DEPLOYMENT)
        assert again.value.reason == "replay_denied" and restarted._adapters[DEPLOYMENT].calls == 0
        with sqlite3.connect(reopened.path) as connection:
            row = connection.execute(
                "SELECT status FROM aip_remote_execution_reservation").fetchone()
            version = connection.execute("SELECT schema_version FROM aip_store").fetchone()[0]
        assert row[0] == "consumed" and version == 5
    finally:
        reopened.close()


def test_two_gateways_and_two_connections_leave_one_reservation(tmp_path):
    lab = _ready(tmp_path)
    _register(lab)
    gateways = (_gateway(lab), _gateway(lab))
    outcomes = []
    barrier = threading.Barrier(2)

    def attempt(gateway):
        barrier.wait()
        try:
            outcomes.append(_run(gateway, lab).accepted)
        except ProviderError as error:
            outcomes.append(error.reason)

    threads = [threading.Thread(target=attempt, args=(gateway,)) for gateway in gateways]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert outcomes.count(True) == 1 and outcomes.count("replay_denied") == 1
    assert gateways[0]._adapters[DEPLOYMENT].calls + gateways[1]._adapters[DEPLOYMENT].calls == 1
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute("SELECT count(*) FROM aip_remote_execution_reservation").fetchone()[0] == 1
    lab.close()


def test_a_second_sqlite_writer_cannot_insert_during_the_hold(tmp_path):
    lab = _ready(tmp_path)
    _register(lab)
    started, release = threading.Event(), threading.Event()

    def stall(stage):
        if stage == "reserve_before_insert":
            started.set()
            assert release.wait(2)

    lab.ledger._fault = stall
    worker = threading.Thread(target=lambda: _run(_gateway(lab), lab))
    worker.start()
    assert started.wait(2)
    outsider = sqlite3.connect(lab.ledger.path, timeout=0.2)
    with pytest.raises(sqlite3.OperationalError):
        outsider.execute("BEGIN IMMEDIATE")
    outsider.close()
    release.set()
    worker.join()
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute("SELECT count(*) FROM aip_remote_execution_reservation").fetchone()[0] == 1
    lab.close()


def test_revocation_expiry_and_audit_failure_do_not_leave_a_second_use(tmp_path):
    lab = _ready(tmp_path)
    _register(lab, authorization_id="remote-revoked")
    lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], "remote-revoked", "operator_revoked")
    revoked = _gateway(lab)
    with pytest.raises(ProviderError) as denied:
        _run(revoked, lab, authorization_id="remote-revoked")
    assert denied.value.reason == "revoked" and revoked._adapters[DEPLOYMENT].calls == 0
    now = lab.clock()
    from datetime import timedelta
    _register(lab, authorization_id="remote-window", deployment_id="gemini-offline-a",
              provider_id="gemini", model_id="gemini-3.5-flash-lite",
              expires_at=now + timedelta(minutes=2))

    def expire(stage):
        if stage == "reserve_before_insert":
            lab.clock.advance(120)

    lab.ledger._fault = expire
    late = _gateway(lab)
    with pytest.raises(ProviderError) as expired:
        _run(late, lab, authorization_id="remote-window", deployment_id="gemini-offline-a")
    assert expired.value.reason == "authorization_expired" and late._adapters["gemini-offline-a"].calls == 0
    _register(lab, authorization_id="remote-disk", deployment_id="openai-sdk-a")

    def fail(stage):
        if stage == "remote_evaluate_before_commit":
            raise OSError("disk")

    lab.ledger._fault = fail
    broken = _gateway(lab)
    with pytest.raises(ProviderError) as storage:
        _run(broken, lab, authorization_id="remote-disk", deployment_id="openai-sdk-a")
    assert storage.value.reason == "storage_unavailable" and broken._adapters["openai-sdk-a"].calls == 0
    lab.ledger._fault = lambda stage: None
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute("SELECT count(*) FROM aip_remote_execution_reservation").fetchone()[0] == 0
    lab.close()


def test_adapter_and_consume_failures_keep_the_held_row(tmp_path):
    lab = _ready(tmp_path)
    _register(lab)
    failing = _Calls(fail="remote_unavailable")
    adapters = lab_adapters()
    adapters[DEPLOYMENT] = failing
    gateway = _gateway(lab, adapters=adapters)
    with pytest.raises(ProviderError) as broken:
        _run(gateway, lab)
    assert broken.value.reason == "remote_unavailable" and failing.calls == 1
    retry = _gateway(lab)
    with pytest.raises(ProviderError) as replay:
        _run(retry, lab)
    assert replay.value.reason == "replay_denied" and retry._adapters[DEPLOYMENT].calls == 0
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute(
            "SELECT status FROM aip_remote_execution_reservation").fetchone()[0] == "held"
    lab.close()
    (tmp_path / "consume").mkdir()
    held = _ready(tmp_path / "consume")
    _register(held)

    def fail_consume(stage):
        if stage == "audit_remote_reservation_consumed":
            raise OSError("disk")

    held.ledger._fault = fail_consume
    uncertain = _gateway(held)
    with pytest.raises(ProviderError) as consumed:
        _run(uncertain, held)
    assert consumed.value.reason == "storage_unavailable" and uncertain._adapters[DEPLOYMENT].calls == 1
    root, issuer, clock = held.ledger.root, held.issuer, held.clock
    held.close()
    reopened = SQLiteExecutionLedger(root, issuer, clock)
    try:
        follow = NeutralModelGateway(resolver=__resolver(reopened))
        with pytest.raises(ProviderError) as still:
            follow.execute(issuer.issue("ORG-A", "executor"), "remote-ops-a", BUDGET, RESOURCE, DEPLOYMENT)
        assert still.value.reason == "replay_denied" and follow._adapters[DEPLOYMENT].calls == 0
        with sqlite3.connect(reopened.path) as connection:
            status = connection.execute("SELECT status FROM aip_remote_execution_reservation").fetchone()[0]
            audits = connection.execute(
                "SELECT count(*) FROM aip_remote_authorization_audit WHERE outcome='ALLOW'").fetchone()[0]
        assert status == "held" and audits == 1
    finally:
        reopened.close()


def test_v5_migration_preserves_audit_and_rejects_an_unaudited_store(tmp_path):
    lab = _ready_without_audit(tmp_path, audit=True, binding=True)
    before = _rows(lab.ledger.path)
    lab.ledger.migrate_to_v5(lab.admin["ORG-A"])
    assert _rows(lab.ledger.path) == before
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 5
        assert connection.execute("SELECT count(*) FROM aip_remote_execution_reservation").fetchone()[0] == 0
    with pytest.raises(ExecutionError) as repeated:
        lab.ledger.migrate_to_v5(lab.admin["ORG-A"])
    assert repeated.value.reason == "revision_conflict"
    published = Path(__file__).resolve().parents[1] / "app" / "enterprise_ai_processing" / "migrations"
    assert "replay_denied" not in (published / "004_remote_authorization_binding.sql").read_text(encoding="utf-8")
    assert "replay_denied" not in (published / "004_remote_authorization_audit_v2.sql").read_text(encoding="utf-8")
    lab.close()
    (tmp_path / "rollback").mkdir()
    rolling = _ready_without_audit(tmp_path / "rollback", audit=True, binding=True)

    def fail(stage):
        if stage == "migrate_v5_before_commit":
            raise OSError("disk")

    rolling.ledger._fault = fail
    with pytest.raises(ExecutionError):
        rolling.ledger.migrate_to_v5(rolling.admin["ORG-A"])
    with sqlite3.connect(rolling.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 4
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name='aip_remote_execution_reservation'").fetchone() is None
    plain = _gateway(rolling)
    with pytest.raises(ProviderError) as old:
        _run(plain, rolling)
    assert old.value.reason == "authority_unverifiable" and plain._adapters[DEPLOYMENT].calls == 0
    rolling.close()
    (tmp_path / "busy").mkdir()
    occupied = _ready(tmp_path / "busy")
    with pytest.raises(ExecutionError):
        SQLiteExecutionLedger(occupied.ledger.root, occupied.issuer, occupied.clock)
    occupied.close()


def test_revoke_serialized_before_commit_blocks_the_reservation(tmp_path):
    lab = _ready(tmp_path)
    _register(lab)
    started, release = threading.Event(), threading.Event()

    def stall(stage):
        if stage == "remote_revoke_before_commit":
            started.set()
            assert release.wait(2)

    lab.ledger._fault = stall
    worker = threading.Thread(
        target=lambda: lab.ledger.revoke_remote_authorization(
            lab.admin["ORG-A"], "remote-ops-a", "operator_revoked"))
    worker.start()
    assert started.wait(2)
    outcome = {}

    def reserve():
        try:
            _run(_gateway(lab), lab)
            outcome["value"] = "allowed"
        except ProviderError as error:
            outcome["value"] = error.reason

    contender = threading.Thread(target=reserve)
    contender.start()
    release.set()
    worker.join()
    contender.join()
    assert outcome["value"] == "revoked"
    with sqlite3.connect(lab.ledger.path) as connection:
        assert connection.execute("SELECT count(*) FROM aip_remote_execution_reservation").fetchone()[0] == 0
    lab.close()


def __resolver(ledger):
    from app.enterprise_ai_processing.durable_resolver import LedgerDurableAuthorization
    return LedgerDurableAuthorization(ledger)


def _rows(path):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT event_id,audit_seq,contract,timestamp_us,event,outcome,reason,organization_id,"
            "authorization_id,deployment_id,provider_id,model_id,operation_id,actor_ref "
            "FROM aip_remote_authorization_audit ORDER BY audit_seq"
        ).fetchall()
