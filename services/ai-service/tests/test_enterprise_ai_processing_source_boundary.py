"""B2-RUNTIME: one read, one admission, no model execution, no direct reserve."""
import logging
import pickle
import socket
import sqlite3
import threading
import traceback
from contextvars import copy_context
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from asyncio import CancelledError

from app.enterprise_ai_processing.execution_types import ExecutionError, ProcessingLease
from app.enterprise_ai_processing.gateway import EnterpriseModelGateway
from app.enterprise_ai_processing.models import (
    AIProcessingEnvelope, AIProcessingGrant, ModelProcessingProfile, SourceEvidence,
)
from app.enterprise_ai_processing.source_boundary import RuntimeAdmission, TrustedEnterpriseSourceBoundary
from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
from app.enterprise_connectors.models import ConnectorOperation, Gate, OperationRequest, Outcome
from app.enterprise_connectors.service import ConnectorService
from app.enterprise_connectors.synthetic import SyntheticPage
from tests.enterprise_ai_processing_execution_fixture import TestAccessAuthority
from tests.enterprise_connector_fixture import laboratory


CANARY = "CANARY-B2-RT-TEXT-9f3c"
_NETWORK = {"attempts": 0}


def _blocked(*_args, **_kwargs):
    _NETWORK["attempts"] += 1
    raise RuntimeError("unauthorized network")


def _install_network_guard():
    for name in ("connect", "connect_ex", "send", "sendall"):
        setattr(socket.socket, name, _blocked)
    for name in ("create_connection", "getaddrinfo", "gethostbyname"):
        setattr(socket, name, _blocked)


_install_network_guard()


def _seed(lab, ledger, access):
    admin = {org: access.issue(org) for org in ("ORG-A", "ORG-B")}
    executor = {org: access.issue(org, "executor") for org in admin}
    ledger.initialize(admin["ORG-A"])
    now = lab.clock()
    start, end = now - timedelta(seconds=1), now + timedelta(hours=1)
    revision = 1
    for suffix, org in (("a", "ORG-A"), ("b", "ORG-B")):
        profile = ModelProcessingProfile(org, start, end, end)
        grant = AIProcessingGrant(
            "processing-grant-" + suffix, "principal-" + suffix, org, "instance-" + suffix,
            "tenant-" + suffix, "vacation-" + suffix, "recipient-" + suffix,
            start, end, end, "not_required")
        revision = ledger.change_policy(admin[org], profile, expected_revision=revision)
        revision = ledger.change_policy(admin[org], grant, expected_revision=revision, approval_ref=grant.grant_id)
    return admin, executor


def _world(tmp_path, text=CANARY):
    tmp_path.mkdir(parents=True, exist_ok=True)
    lab = laboratory()
    lab.adapter.set_pages("vacation-a", (SyntheticPage(text),))
    lab.adapter.set_pages("vacation-b", (SyntheticPage(text),))
    access = TestAccessAuthority(lab.clock)
    ledger = SQLiteExecutionLedger(tmp_path, access, lab.clock)
    try:
        admin, executor = _seed(lab, ledger, access)
    except BaseException:
        ledger.close()
        raise
    boundary = TrustedEnterpriseSourceBoundary.compose(lab.service, ledger=ledger, executor=executor["ORG-A"])
    invoked = []
    boundary._gateway.model.invoke = lambda _owner: invoked.append(True)
    return SimpleNamespace(
        lab=lab, ledger=ledger, boundary=boundary, admin=admin, executor=executor, invoked=invoked, access=access)


def _rows(ledger):
    with sqlite3.connect(ledger.path) as connection:
        return connection.execute(
            "SELECT organization_id, run_state, reservation_state FROM aip_execution ORDER BY operation_id"
        ).fetchall()


def _events(ledger):
    with sqlite3.connect(ledger.path) as connection:
        return connection.execute("SELECT event, outcome FROM aip_audit ORDER BY audit_seq").fetchall()


def _release(boundary):
    ledger = boundary._ledger
    try:
        boundary.close()
    finally:
        ledger.close()


def _pause_authority(boundary):
    paused, release, holder = threading.Event(), threading.Event(), {}
    real = boundary.authority

    def wrapped(owner):
        if "id" not in holder:
            holder["id"] = threading.get_ident()
            paused.set()
            assert release.wait(10)
        return real(owner)

    boundary.authority = wrapped
    return paused, release


def test_b2_rt_01_authorized_composition_binds_the_same_gateway(tmp_path):
    world = _world(tmp_path)
    try:
        boundary = world.boundary
        assert boundary.state == "NEW"
        assert boundary._gateway.boundary is boundary
        assert boundary._gateway.ledger is world.ledger
        assert boundary._service.cache_size == 0
        assert type(boundary._service.adapter).__name__ == "SyntheticDocumentAdapter"
        assert boundary._identity.recognizes(world.lab.a) is True
        assert boundary._executor.organization_id == world.lab.a.organization_id
        assert not hasattr(boundary.read, "receipt")
        with pytest.raises(ExecutionError):
            TrustedEnterpriseSourceBoundary()
    finally:
        _release(boundary)


def test_b2_rt_02_unrecognized_composition_does_not_read(tmp_path):
    lab = laboratory()
    access = TestAccessAuthority(lab.clock)
    ledger = SQLiteExecutionLedger(tmp_path, access, lab.clock)
    ledger.initialize(access.issue())
    executor = access.issue(role="executor")
    before = lab.adapter.calls
    with pytest.raises(ExecutionError):
        TrustedEnterpriseSourceBoundary.compose(object(), ledger=ledger, executor=executor)
    cached = laboratory(cache_size=1)
    with pytest.raises(ExecutionError):
        TrustedEnterpriseSourceBoundary.compose(cached.service, ledger=ledger, executor=executor)

    class ForeignAdapter:
        def read(self, _use, _cursor):
            raise AssertionError("read")

        def authorize_delivery(self, _resources):
            raise AssertionError("delivery")

    foreign = ConnectorService(lab.store, lab.policy, lab.audit, lab.ledger, lab.broker, ForeignAdapter())
    with pytest.raises(ExecutionError):
        TrustedEnterpriseSourceBoundary.compose(foreign, ledger=ledger, executor=executor)
    assert lab.adapter.calls == before and cached.adapter.calls == ()
    ledger.close()


def test_b2_rt_03_04_one_public_read_without_processing_laboratory(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        before = world.lab.adapter.calls
        boundary.read(world.lab.a, world.lab.request())
        assert before == ()
        assert boundary.public_reads == 1
        assert len(world.lab.adapter.calls) == 1
        assert boundary.state == "SOURCE_RECOGNIZED"
        assert boundary._result.status is Outcome.DELIVERY_ALLOWED
        assert boundary._evidence.content_revision == boundary._document.version
        assert boundary._evidence.read_correlation_id == boundary._result.correlation_id
        assert boundary._evidence.utf8_bytes == len(boundary._canonical)
        with pytest.raises(TypeError):
            boundary.read(world.lab.a, world.lab.request(), content_revision=9)
    finally:
        _release(boundary)


def test_b2_rt_05_06_07_one_evidence_one_admission_and_no_model(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        admission = boundary.admit()
        assert type(admission) is RuntimeAdmission
        assert admission.state == "PREPARED" and admission.reservation == "HELD"
        assert type(admission.lease_id) is str and not isinstance(admission, ProcessingLease)
        assert boundary.outstanding_reservation == "HELD"
        assert boundary._lease is not None and boundary._lease.reference == admission.lease_id
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
        assert world.invoked == []
        owner = next(iter(boundary._gateway._owners.values()))
        assert owner.entries == 0
        events = [event for event, _outcome in _events(world.ledger)]
        assert "ai_provider_invocation_observed" not in events
        assert events.count("ai_processing_authorized") == 1
        with pytest.raises(TypeError):
            pickle.dumps(admission)
    finally:
        _release(boundary)


def _without_grant(tmp_path):
    lab = laboratory()
    lab.adapter.set_pages("vacation-a", (SyntheticPage(CANARY),))
    access = TestAccessAuthority(lab.clock)
    ledger = SQLiteExecutionLedger(tmp_path, access, lab.clock)
    admin = access.issue()
    executor = access.issue(role="executor")
    ledger.initialize(admin)
    now = lab.clock()
    start, end = now - timedelta(seconds=1), now + timedelta(hours=1)
    ledger.change_policy(admin, ModelProcessingProfile("ORG-A", start, end, end), expected_revision=1)
    boundary = TrustedEnterpriseSourceBoundary.compose(lab.service, ledger=ledger, executor=executor)
    invoked = []
    boundary._gateway.model.invoke = lambda _owner: invoked.append(True)
    return SimpleNamespace(lab=lab, ledger=ledger, boundary=boundary, invoked=invoked)


def test_b2_rt_08_prepare_deny_is_terminal(tmp_path):
    world = _without_grant(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        with pytest.raises(ExecutionError) as denied:
            boundary.admit()
        assert denied.value.reason == "processing_not_granted"
        assert boundary.state == "DENIED" and _rows(world.ledger) == []
        with pytest.raises(ExecutionError):
            boundary.admit()
        assert _rows(world.ledger) == [] and world.invoked == []
    finally:
        _release(boundary)


def test_b2_rt_09_failure_before_populate_does_not_retry(tmp_path):
    world = _without_grant(tmp_path)
    boundary = world.boundary
    populated = []
    real = boundary.populate

    def spy(owner):
        populated.append(True)
        return real(owner)

    boundary.populate = spy
    try:
        boundary.read(world.lab.a, world.lab.request())
        with pytest.raises(ExecutionError) as denied:
            boundary.admit()
        assert denied.value.reason == "processing_not_granted"
        assert populated == [] and boundary._populated is False
        assert boundary.state == "DENIED" and _rows(world.ledger) == []
        with pytest.raises(ExecutionError):
            boundary.admit()
        with pytest.raises(ExecutionError):
            boundary._gateway.prepare(boundary._envelope, boundary._evidence)
        assert _rows(world.ledger) == [] and world.invoked == []
    finally:
        _release(boundary)


def test_b2_rt_10_11_ambiguous_reserve_is_uncertain_and_not_retried(tmp_path, monkeypatch):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())

        def fail_after_reserve(_reference):
            raise RuntimeError("ambiguous")

        monkeypatch.setattr("app.enterprise_ai_processing.gateway.ProcessingLease", fail_after_reserve)
        with pytest.raises(ExecutionError) as failed:
            boundary.admit()
        assert failed.value.unavailable is True
        assert boundary.state == "UNCERTAIN"
        assert boundary.outstanding_reservation == "HELD"
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
        with pytest.raises(ExecutionError):
            boundary.admit()
        with pytest.raises(ExecutionError):
            boundary._gateway.prepare(boundary._envelope, boundary._evidence)
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
        boundary.close()
        assert boundary.state == "CLOSED" and boundary.outstanding_reservation == "HELD"
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
        assert all(event != "ai_processing_cancelled" for event, _outcome in _events(world.ledger))
        assert world.invoked == []
    finally:
        _release(boundary)


def test_b2_rt_12_two_threads_admit_one_lease(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        barrier = threading.Barrier(2)
        outcomes = []

        def run():
            try:
                barrier.wait(10)
                outcomes.append(boundary.admit())
            except ExecutionError as error:
                outcomes.append(error.reason)

        threads = [threading.Thread(target=run), threading.Thread(target=run)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(15)
            assert not thread.is_alive()
        assert sum(type(item) is RuntimeAdmission for item in outcomes) == 1
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
        assert world.invoked == []
    finally:
        _release(boundary)


def test_b2_rt_13_second_sequential_admission_fails(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        boundary.admit()
        with pytest.raises(ExecutionError):
            boundary.admit()
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
    finally:
        _release(boundary)


def test_b2_rt_14_direct_prepare_before_claim_reserves_nothing(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        envelope, evidence = boundary._envelope, boundary._evidence
        with pytest.raises(ExecutionError) as blocked:
            boundary._gateway.prepare(envelope, evidence)
        assert blocked.value.reason == "source_evidence_invalid"
        assert boundary.state == "SOURCE_RECOGNIZED" and _rows(world.ledger) == []
        admission = boundary.admit()
        assert admission.state == "PREPARED" and len(_rows(world.ledger)) == 1
    finally:
        _release(boundary)


def test_direct_prepare_during_claim_on_another_ledger_reserves_nothing(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    other_root = tmp_path / "other"
    other_root.mkdir()
    other = SQLiteExecutionLedger(other_root, world.access, world.lab.clock)
    release = threading.Event()
    try:
        _seed(world.lab, other, world.access)
        other_gateway = EnterpriseModelGateway(other, world.lab.policy, boundary)
        boundary.read(world.lab.a, world.lab.request())
        paused, release = _pause_authority(boundary)
        outcome = {}

        def admit():
            try:
                outcome["value"] = boundary.admit()
            except ExecutionError as error:
                outcome["error"] = error

        worker = threading.Thread(target=admit)
        worker.start()
        assert paused.wait(10)
        with pytest.raises(ExecutionError) as blocked:
            other_gateway.prepare(boundary._envelope, boundary._evidence)
        assert blocked.value.reason == "source_evidence_invalid"
        assert _rows(other) == []
        release.set()
        worker.join(15)
        assert not worker.is_alive()
        assert type(outcome.get("value")) is RuntimeAdmission
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
        assert _rows(other) == []
        assert world.invoked == []
    finally:
        release.set()
        _release(boundary)
        other.close()


def test_direct_prepare_waiting_on_the_same_gateway_reserves_nothing(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    release = threading.Event()
    try:
        boundary.read(world.lab.a, world.lab.request())
        paused, release = _pause_authority(boundary)
        competitor = {}

        def admit():
            boundary.admit()

        def sneak():
            try:
                boundary._gateway.prepare(boundary._envelope, boundary._evidence)
            except ExecutionError as error:
                competitor["reason"] = error.reason

        first = threading.Thread(target=admit)
        second = threading.Thread(target=sneak)
        first.start()
        assert paused.wait(10)
        second.start()
        release.set()
        first.join(15)
        second.join(15)
        assert not first.is_alive() and not second.is_alive()
        assert competitor["reason"] == "source_evidence_invalid"
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
        assert world.invoked == []
    finally:
        release.set()
        _release(boundary)


def test_direct_prepare_after_prepared_cannot_open_another_operation(tmp_path):
    prepared = _world(tmp_path)
    boundary = prepared.boundary
    try:
        boundary.read(prepared.lab.a, prepared.lab.request())
        boundary.admit()
        owner = next(iter(boundary._gateway._owners.values()))
        boundary._gateway._seal(owner)
        assert owner.entries == 0 and prepared.invoked == []
        with pytest.raises(ExecutionError):
            boundary._gateway.prepare(boundary._envelope, boundary._evidence)
        assert _rows(prepared.ledger) == [("ORG-A", "INTENT", "HELD")]
        fresh = AIProcessingEnvelope(
            str(uuid4()), boundary._envelope.context, boundary._envelope.read_request,
            boundary._envelope.binding_id, boundary._envelope.tenant_id, boundary._envelope.source_ref,
            boundary._envelope.registered_version, boundary._envelope.content_revision,
            boundary._envelope.connector_revision, boundary._envelope.processing_revision,
            boundary._envelope.profile_id, boundary._envelope.profile_version,
            boundary._envelope.issued_at, boundary._envelope.expires_at, boundary._envelope.question)
        with pytest.raises(ExecutionError):
            boundary._gateway.prepare(fresh, boundary._evidence)
        assert len(_rows(prepared.ledger)) == 1
    finally:
        _release(boundary)


def test_b2_rt_15_other_organization_is_rejected(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    other = TrustedEnterpriseSourceBoundary.compose(
        world.lab.service, ledger=world.ledger, executor=world.executor["ORG-B"])
    try:
        with pytest.raises(ExecutionError):
            boundary.read(world.lab.b, world.lab.request("b"))
        assert boundary.public_reads == 0 and boundary.state == "DENIED"
        other.read(world.lab.b, world.lab.request("b"))
        admission = other.admit()
        other._gateway.model.invoke = lambda _owner: world.invoked.append(True)
        assert admission.organization_id == "ORG-B"
        assert _rows(world.ledger) == [("ORG-B", "INTENT", "HELD")]
        assert world.invoked == []
    finally:
        if other.state == "PREPARED":
            other._gateway.close()
        other.close()
        _release(boundary)


def test_b2_rt_16_revocation_during_read_and_before_prepare(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        def bump(_resource_id, _cursor):
            snapshot = world.lab.store.snapshot()
            world.lab.store.replace_rows("principals", snapshot.principals, expected_revision=snapshot.revision)

        world.lab.adapter.on_read = bump
        with pytest.raises(ExecutionError):
            boundary.read(world.lab.a, world.lab.request())
        assert boundary.state == "DENIED" and boundary._evidence is None
        assert boundary.public_reads == 1 and _rows(world.ledger) == []
    finally:
        _release(boundary)

    world = _world(tmp_path / "between")
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        snapshot = world.lab.store.snapshot()
        world.lab.store.replace_rows("principals", snapshot.principals, expected_revision=snapshot.revision)
        with pytest.raises(ExecutionError) as changed:
            boundary.admit()
        assert changed.value.reason == "policy_changed"
        assert boundary.state == "DENIED" and _rows(world.ledger) == []
        with pytest.raises(ExecutionError):
            boundary.admit()
    finally:
        _release(boundary)


def test_b2_rt_16b_revocation_after_admission_keeps_the_single_hold(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        boundary.admit()
        snapshot = world.lab.store.snapshot()
        world.lab.store.replace_rows("principals", snapshot.principals, expected_revision=snapshot.revision)
        owner = next(iter(boundary._gateway._owners.values()))
        with pytest.raises(ExecutionError) as changed:
            boundary._gateway._seal(owner)
        assert changed.value.reason == "policy_changed"
        assert boundary.state == "PREPARED"
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
        with pytest.raises(ExecutionError):
            boundary.admit()
    finally:
        _release(boundary)


def test_b2_rt_17_expiration_denies_before_reserve(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        world.lab.clock.advance(6)
        with pytest.raises(ExecutionError) as expired:
            boundary.admit()
        assert expired.value.reason == "authorization_expired"
        assert boundary.state == "DENIED" and _rows(world.ledger) == []
    finally:
        _release(boundary)


def test_b2_rt_18_local_byte_swap_keeps_the_version(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request("a"))
        version = boundary._document.version
        boundary._canonical = b"y" * len(boundary._canonical)
        assert boundary._document.version == version == boundary._evidence.content_revision
        assert boundary.recognizes_source(boundary._evidence, boundary._envelope) is False
        with pytest.raises(ExecutionError):
            boundary.admit()
        assert boundary.state == "DENIED" and _rows(world.ledger) == []
    finally:
        _release(boundary)


def test_b2_rt_19_multibyte_utf8_counts_bytes(tmp_path):
    text = "e\u0301" * 4
    world = _world(tmp_path, text)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        assert boundary._document.text == text
        assert len(text) == 8
        assert len(boundary._canonical) == boundary._evidence.utf8_bytes == 12
        assert boundary._canonical != ("é" * 4).encode("utf-8")
    finally:
        _release(boundary)


def test_b2_rt_20_1024_bytes_can_be_admitted(tmp_path):
    world = _world(tmp_path, "x" * 1024)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        assert len(boundary._canonical) == 1024
        admission = boundary.admit()
        assert admission.state == "PREPARED"
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
        assert world.invoked == []
    finally:
        _release(boundary)


def test_b2_rt_21_1025_bytes_are_not_truncated(tmp_path):
    world = _world(tmp_path, "y" * 1025)
    boundary = world.boundary
    try:
        snapshot = world.lab.store.snapshot()
        definition = snapshot.definitions[0]
        raised = replace(definition, limits=replace(definition.limits, max_bytes=2048))
        world.lab.store.replace_rows("definitions", (raised,), expected_revision=snapshot.revision)
        world.lab.adapter.set_pages("vacation-a", (SyntheticPage("y" * 1025),))
        boundary.read(world.lab.a, world.lab.request())
        assert len(boundary._canonical) == 1025 and boundary._evidence.utf8_bytes == 1025
        with pytest.raises(ExecutionError) as limited:
            boundary.admit()
        assert limited.value.reason == "budget_exceeded"
        assert boundary.state == "DENIED"
        assert len(boundary._canonical) == 1025
        assert _rows(world.ledger) == []
    finally:
        _release(boundary)


def test_b2_rt_22_23_cancellation_and_interrupt_do_not_leave_a_reusable_read(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    other = TrustedEnterpriseSourceBoundary.compose(
        world.lab.service, ledger=world.ledger, executor=world.executor["ORG-B"])
    try:
        other.read(world.lab.b, world.lab.request("b"))

        def cancel(_resource_id, _cursor):
            raise CancelledError()

        world.lab.adapter.on_read = cancel
        with pytest.raises(CancelledError):
            boundary.read(world.lab.a, world.lab.request())
        assert boundary.state == "CLOSED" and boundary._evidence is None
        assert other.state == "SOURCE_RECOGNIZED"
    finally:
        other.close()
        _release(boundary)

    world = _world(tmp_path / "interrupt")
    boundary = world.boundary
    try:
        def interrupt(_resource_id, _cursor):
            raise KeyboardInterrupt()

        world.lab.adapter.on_read = interrupt
        with pytest.raises(KeyboardInterrupt):
            boundary.read(world.lab.a, world.lab.request())
        assert boundary.state == "CLOSED" and boundary._canonical is None
    finally:
        _release(boundary)


def test_cancel_during_claim_is_uncertain(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())

        def interrupt(_owner):
            raise KeyboardInterrupt()

        boundary.authority = interrupt
        with pytest.raises(KeyboardInterrupt):
            boundary.admit()
        assert boundary.state == "UNCERTAIN"
        with pytest.raises(ExecutionError):
            boundary.admit()
        assert world.invoked == []
    finally:
        _release(boundary)


def test_b2_rt_24_close_failure_does_not_touch_another_operation(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    other = TrustedEnterpriseSourceBoundary.compose(
        world.lab.service, ledger=world.ledger, executor=world.executor["ORG-B"])
    try:
        other.read(world.lab.b, world.lab.request("b"))
        evidence = other._evidence

        def fail():
            raise RuntimeError("close failed")

        boundary._on_close = fail
        with pytest.raises(RuntimeError):
            boundary.close()
        assert boundary.state == "CLOSED" and boundary._canonical is None
        assert other._evidence is evidence and other.state == "SOURCE_RECOGNIZED"
        other.admit()
        assert _rows(world.ledger) == [("ORG-B", "INTENT", "HELD")]
    finally:
        if other.state == "PREPARED":
            other._gateway.close()
        other.close()
        world.ledger.close()


def test_b2_rt_25_no_canary_in_repr_logs_traceback_or_sqlite(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        admission = boundary.admit()
        rendered = " ".join((repr(boundary), repr(admission), repr(boundary._evidence), repr(boundary._envelope)))
        assert CANARY not in rendered and CANARY not in caplog.text
        try:
            raise ExecutionError("source_evidence_invalid", unavailable=False)
        except ExecutionError:
            assert CANARY not in traceback.format_exc()
        for path in tmp_path.rglob("*"):
            if path.is_file() and path.name != "processing.owner":
                assert CANARY.encode("utf-8") not in path.read_bytes()
    finally:
        _release(boundary)


def test_b2_rt_27_c02_prepare_keeps_one_held_reservation(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        boundary.admit()
        assert ("ai_processing_authorized", "AUTHORIZED") in _events(world.ledger)
        assert all(event != "ai_provider_invocation_observed" for event, _outcome in _events(world.ledger))
        assert boundary.state == "PREPARED"
        assert "COMPLETED" not in {row[1] for row in _rows(world.ledger)}
    finally:
        _release(boundary)


def test_b2_rt_28_derived_grant_is_not_required(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        boundary.admit()
        with sqlite3.connect(world.ledger.path) as connection:
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "aip_derived_delivery_grant" not in names
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
    finally:
        _release(boundary)


def test_missing_delivery_permission_does_not_execute(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        snapshot = world.lab.store.snapshot()
        rows = tuple(replace(row, gates=frozenset({Gate.READ})) if row.grant_id == "principal-grant-a" else row
                     for row in snapshot.principal_grants)
        world.lab.store.replace_rows("principal_grants", rows, expected_revision=snapshot.revision)
        with pytest.raises(ExecutionError):
            boundary.read(world.lab.a, world.lab.request())
        assert boundary.public_reads == 0 and boundary.state == "DENIED" and boundary._evidence is None
    finally:
        _release(boundary)


def test_audit_failure_and_connector_failure_leave_no_evidence(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        def broken(_event):
            raise RuntimeError("audit down")

        world.lab.audit.append = broken
        with pytest.raises(ExecutionError):
            boundary.read(world.lab.a, world.lab.request())
        assert boundary.public_reads == 1 and boundary.state == "DENIED" and boundary._evidence is None
    finally:
        _release(boundary)

    world = _world(tmp_path / "missing")
    boundary = world.boundary
    try:
        world.lab.adapter.set_pages("vacation-a", (SyntheticPage(status=404),))
        with pytest.raises(ExecutionError):
            boundary.read(world.lab.a, world.lab.request())
        assert boundary.public_reads == 1 and boundary._evidence is None and _rows(world.ledger) == []
    finally:
        _release(boundary)


def test_two_adapter_reads_are_not_one_recognized_source(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        world.lab.adapter.set_pages("vacation-a", (SyntheticPage("one", next_cursor=1), SyntheticPage("two")))
        with pytest.raises(ExecutionError):
            boundary.read(world.lab.a, world.lab.request())
        assert boundary.public_reads == 1 and len(world.lab.adapter.calls) == 2
        assert boundary.state == "DENIED" and boundary._evidence is None
    finally:
        _release(boundary)


def test_caller_cannot_supply_fabricated_evidence(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        with pytest.raises(TypeError):
            boundary.read(world.lab.a, world.lab.request(), evidence=SourceEvidence(
                "vacation-a", "ORG-A", "instance-a", "tenant-a", "vacation-a", 1, 1,
                "synthetic-internal", "synthetic-documents-v1", 1, str(uuid4()), 1, world.lab.clock()))
        with pytest.raises(TypeError):
            boundary.admit(SourceEvidence(
                "vacation-a", "ORG-A", "instance-a", "tenant-a", "vacation-a", 1, 1,
                "synthetic-internal", "synthetic-documents-v1", 1, str(uuid4()), 1, world.lab.clock()))
        assert boundary.public_reads == 0 and boundary.state == "NEW"
    finally:
        _release(boundary)


def test_close_of_unexecuted_admission_releases_the_hold(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        boundary.admit()
        envelope, evidence = boundary._envelope, boundary._evidence
        owner = next(iter(boundary._gateway._owners.values()))
        boundary._gateway._seal(owner)
        assert owner.entries == 0 and world.invoked == []
        boundary.close()
        assert boundary.state == "CLOSED" and boundary._canonical is None
        assert boundary.outstanding_reservation == "RELEASED"
        assert _rows(world.ledger) == [("ORG-A", "CANCELLED", "RELEASED")]
        assert ("ai_processing_cancelled", "CANCELLED") in _events(world.ledger)
        assert all(state != "COMPLETED" for _org, state, _reservation in _rows(world.ledger))
        with pytest.raises(ExecutionError):
            boundary._gateway.prepare(envelope, evidence)
        with pytest.raises(ExecutionError):
            boundary._gateway._seal(owner)
        boundary.close()
        assert sum(event == "ai_processing_cancelled" for event, _outcome in _events(world.ledger)) == 1
        assert world.invoked == []
    finally:
        world.ledger.close()


def test_two_organizations_admit_concurrently(tmp_path):
    world = _world(tmp_path)
    first = world.boundary
    second = TrustedEnterpriseSourceBoundary.compose(
        world.lab.service, ledger=world.ledger, executor=world.executor["ORG-B"])
    second._gateway.model.invoke = lambda _owner: world.invoked.append(True)
    try:
        first.read(world.lab.a, world.lab.request())
        second.read(world.lab.b, world.lab.request("b"))
        barrier = threading.Barrier(2)
        found = []

        def run(boundary):
            barrier.wait(10)
            found.append(boundary.admit().organization_id)

        threads = [threading.Thread(target=run, args=(first,)), threading.Thread(target=run, args=(second,))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(15)
            assert not thread.is_alive()
        assert set(found) == {"ORG-A", "ORG-B"}
        assert set(_rows(world.ledger)) == {("ORG-A", "INTENT", "HELD"), ("ORG-B", "INTENT", "HELD")}
        assert world.invoked == []
    finally:
        if second.state == "PREPARED":
            second._gateway.close()
        second.close()
        _release(first)


def test_unavailable_prepare_error_is_uncertain(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        real = boundary.authority

        def fail(owner):
            real(owner)
            raise ExecutionError("audit_unavailable", unavailable=True)

        boundary.authority = fail
        with pytest.raises(ExecutionError) as failed:
            boundary.admit()
        assert failed.value.unavailable is True
        assert boundary.state == "UNCERTAIN" and _rows(world.ledger) == []
        with pytest.raises(ExecutionError):
            boundary.admit()
    finally:
        _release(boundary)


def test_b2_rt_31_positive_path_makes_no_network_attempt(tmp_path):
    before = _NETWORK["attempts"]
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        boundary.admit()
        assert _NETWORK["attempts"] == before
        assert type(world.lab.request()) is OperationRequest
        assert world.lab.request().operation is ConnectorOperation.READ
    finally:
        _release(boundary)


def test_competitor_cannot_bind_the_owner_before_legitimate_authority(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    other_root = tmp_path / "other"
    other_root.mkdir()
    other = SQLiteExecutionLedger(other_root, world.access, world.lab.clock)
    release = threading.Event()
    try:
        _seed(world.lab, other, world.access)
        other_gateway = EnterpriseModelGateway(other, world.lab.policy, boundary)
        other_gateway.model.invoke = lambda _owner: world.invoked.append(True)
        boundary.read(world.lab.a, world.lab.request())
        paused = threading.Event()
        real_prepare = boundary._gateway.prepare
        stolen = {}

        def wrapped(envelope, evidence):
            stolen["context"] = copy_context()
            paused.set()
            assert release.wait(10)
            return real_prepare(envelope, evidence)

        boundary._gateway.prepare = wrapped
        outcome = {}

        def admit():
            try:
                outcome["value"] = boundary.admit()
            except ExecutionError as error:
                outcome["error"] = error

        worker = threading.Thread(target=admit)
        worker.start()
        assert paused.wait(10)
        assert boundary.state == "PREPARE_CLAIMED" and boundary._bound is None
        envelope, evidence = boundary._envelope, boundary._evidence
        competitor = {}

        def sneak():
            try:
                stolen["context"].run(lambda: real_prepare(envelope, evidence))
            except ExecutionError as error:
                competitor["same"] = error.reason
            try:
                stolen["context"].run(lambda: other_gateway.prepare(envelope, evidence))
            except ExecutionError as error:
                competitor["other"] = error.reason
            fresh = AIProcessingEnvelope(
                str(uuid4()), envelope.context, envelope.read_request, envelope.binding_id,
                envelope.tenant_id, envelope.source_ref, envelope.registered_version,
                envelope.content_revision, envelope.connector_revision, envelope.processing_revision,
                envelope.profile_id, envelope.profile_version, envelope.issued_at, envelope.expires_at,
                envelope.question)
            try:
                other_gateway.prepare(fresh, evidence)
            except ExecutionError as error:
                competitor["fresh"] = error.reason

        thief = threading.Thread(target=sneak)
        thief.start()
        thief.join(15)
        assert not thief.is_alive()
        assert competitor == {
            "same": "source_evidence_invalid",
            "other": "source_evidence_invalid",
            "fresh": "source_evidence_invalid",
        }
        assert boundary._bound is None and boundary._gateway._owners == {} and other_gateway._owners == {}
        assert _rows(world.ledger) == [] and _rows(other) == []
        release.set()
        worker.join(15)
        assert not worker.is_alive()
        assert type(outcome.get("value")) is RuntimeAdmission
        assert len(boundary._gateway._owners) == 1
        owner = next(iter(boundary._gateway._owners.values()))
        assert boundary._bound is owner and owner.envelope is boundary._envelope
        assert other_gateway._owners == {}
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")] and _rows(other) == []
        boundary._gateway._seal(owner)
        assert owner.entries == 0 and world.invoked == []
    finally:
        release.set()
        _release(boundary)
        other.close()


def test_close_failure_keeps_the_hold_and_a_second_close_can_release_it(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        boundary.admit()
        real_close = boundary._gateway.close

        def fail():
            raise RuntimeError("close failed")

        boundary._gateway.close = fail
        with pytest.raises(RuntimeError):
            boundary.close()
        assert boundary.state == "PREPARED" and boundary.outstanding_reservation == "HELD"
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
        boundary._gateway.close = real_close
        boundary.close()
        assert boundary.outstanding_reservation == "RELEASED"
        assert _rows(world.ledger) == [("ORG-A", "CANCELLED", "RELEASED")]
        assert world.invoked == []
    finally:
        _release(boundary)


def test_interrupt_during_close_does_not_mark_the_hold_released(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        boundary.admit()

        def interrupt():
            raise KeyboardInterrupt()

        boundary._gateway.close = interrupt
        with pytest.raises(KeyboardInterrupt):
            boundary.close()
        assert boundary.state == "PREPARED" and boundary.outstanding_reservation == "HELD"
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
        assert world.invoked == []
    finally:
        real = type(boundary._gateway).close
        boundary._gateway.close = real.__get__(boundary._gateway, type(boundary._gateway))
        _release(boundary)


def test_concurrent_close_releases_one_hold_and_leaves_the_other_org(tmp_path):
    world = _world(tmp_path)
    first = world.boundary
    second = TrustedEnterpriseSourceBoundary.compose(
        world.lab.service, ledger=world.ledger, executor=world.executor["ORG-B"])
    second._gateway.model.invoke = lambda _owner: world.invoked.append(True)
    try:
        first.read(world.lab.a, world.lab.request())
        second.read(world.lab.b, world.lab.request("b"))
        first.admit()
        second.admit()
        barrier = threading.Barrier(2)
        errors = []

        def run():
            try:
                barrier.wait(10)
                first.close()
            except Exception as error:
                errors.append(error)

        threads = [threading.Thread(target=run), threading.Thread(target=run)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(15)
            assert not thread.is_alive()
        assert errors == []
        assert first.state == "CLOSED" and first.outstanding_reservation == "RELEASED"
        assert set(_rows(world.ledger)) == {
            ("ORG-A", "CANCELLED", "RELEASED"),
            ("ORG-B", "INTENT", "HELD"),
        }
        assert sum(event == "ai_processing_cancelled" for event, _outcome in _events(world.ledger)) == 1
        second.close()
        assert set(_rows(world.ledger)) == {
            ("ORG-A", "CANCELLED", "RELEASED"),
            ("ORG-B", "CANCELLED", "RELEASED"),
        }
        assert world.invoked == []
    finally:
        second.close()
        _release(first)


def test_product_module_does_not_import_tests():
    import app.enterprise_ai_processing.source_boundary as boundary_module
    from pathlib import Path
    assert boundary_module.__name__ == "app.enterprise_ai_processing.source_boundary"
    text = Path(boundary_module.__file__).read_text(encoding="utf-8")
    assert "tests." not in text and "ProcessingLaboratory" not in text
