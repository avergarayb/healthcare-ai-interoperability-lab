"""B2-GRD: one fake execution, one recognized observer, no delivery."""
import logging
import socket
import sqlite3
import threading
import traceback
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from asyncio import CancelledError

from app.enterprise_ai_processing.execution_types import ExecutionError, ExecutionOwner, ProcessingLease
from app.enterprise_ai_processing.fake_model import FakeEnterpriseModel
from app.enterprise_ai_processing.grounding import DeterministicVacationGrounding, GroundingRecord
from app.enterprise_ai_processing.models import ModelProcessingProfile
from app.enterprise_ai_processing.source_boundary import RuntimeExecution, TrustedEnterpriseSourceBoundary
from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
from app.enterprise_connectors.models import Gate
from app.enterprise_connectors.synthetic import SyntheticPage
from tests.enterprise_ai_processing_execution_fixture import TestAccessAuthority, execution_laboratory
from tests.enterprise_connector_fixture import HOSTILE, laboratory


CANARY = "CANARY-B2-GRD-TEXT-9f3c"
CLAUSE = "VACACIONES: 20 dias tras 12 meses de servicio. " + CANARY
OTHER = "VACACIONES: 9 dias tras 3 meses de servicio."
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
        from app.enterprise_ai_processing.models import AIProcessingGrant
        grant = AIProcessingGrant(
            "processing-grant-" + suffix, "principal-" + suffix, org, "instance-" + suffix,
            "tenant-" + suffix, "vacation-" + suffix, "recipient-" + suffix,
            start, end, end, "not_required")
        revision = ledger.change_policy(admin[org], profile, expected_revision=revision)
        revision = ledger.change_policy(admin[org], grant, expected_revision=revision, approval_ref=grant.grant_id)
    return admin, executor


def _world(tmp_path, text=CLAUSE, other=OTHER):
    tmp_path.mkdir(parents=True, exist_ok=True)
    lab = laboratory()
    lab.adapter.set_pages("vacation-a", (SyntheticPage(text),))
    lab.adapter.set_pages("vacation-b", (SyntheticPage(other),))
    access = TestAccessAuthority(lab.clock)
    ledger = SQLiteExecutionLedger(tmp_path, access, lab.clock)
    try:
        admin, executor = _seed(lab, ledger, access)
    except BaseException:
        ledger.close()
        raise
    boundary = TrustedEnterpriseSourceBoundary.compose(lab.service, ledger=ledger, executor=executor["ORG-A"])
    return SimpleNamespace(
        lab=lab, ledger=ledger, boundary=boundary, admin=admin, executor=executor, access=access)


def _rows(ledger):
    with sqlite3.connect(ledger.path) as connection:
        return connection.execute(
            "SELECT organization_id, run_state, reservation_state FROM aip_execution ORDER BY organization_id"
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


def _positive(tmp_path, text=CLAUSE):
    world = _world(tmp_path, text)
    world.boundary.read(world.lab.a, world.lab.request())
    world.boundary.admit()
    return world


def test_b2_grd_01_through_06_one_real_fake_execution_grounds_internally(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    seen = {}
    real = boundary.observe_owner

    def wrapped(owner):
        seen["source"] = owner.source_bytes
        seen["candidate"] = owner.candidate
        seen["reading"] = boundary._canonical
        seen["entries"] = owner.entries
        return real(owner)

    boundary.observe_owner = wrapped
    try:
        assert type(boundary._gateway.model) is FakeEnterpriseModel
        result = boundary.run()
        assert type(result) is RuntimeExecution
        assert result.state == "COMPLETED" and result.reason == "accepted" and result.entries == 1
        assert result.reservation == "CHARGED" and result.organization_id == "ORG-A"
        assert "days" not in RuntimeExecution.__dataclass_fields__
        assert boundary.public_reads == 1 and seen["entries"] == 1
        assert seen["reading"] is not seen["source"] and seen["reading"] is not seen["candidate"]
        assert boundary._grounding.verdict == "EVIDENCE_FOUND"
        assert boundary._grounding.days == 20 and boundary._grounding.months == 12
        assert ("ai_provider_invocation_observed", "OBSERVED") in _events(world.ledger)
        assert _rows(world.ledger) == [("ORG-A", "COMPLETED", "CHARGED")]
        assert all(event != "ai_derived_delivery_decided" for event, _outcome in _events(world.ledger))
        record = boundary._grounding
        boundary.close()
        assert boundary.state == "CLOSED" and record.days is None and boundary._grounding is None
        assert _rows(world.ledger) == [("ORG-A", "COMPLETED", "CHARGED")]
    finally:
        _release(boundary)


def test_b2_grd_07_laboratory_document_without_clause_is_insufficient(tmp_path):
    world = _world(tmp_path, "Documento ficticio vacation, organización ORG-A. Sin datos reales.")
    boundary = world.boundary
    try:
        boundary.read(world.lab.a, world.lab.request())
        boundary.admit()
        result = boundary.run()
        assert result.state == "COMPLETED" and result.entries == 1
        assert boundary._grounding.verdict == "EVIDENCE_INSUFFICIENT"
        assert boundary._grounding.days is None and boundary._grounding.months is None
    finally:
        _release(boundary)


def test_b2_grd_08_candidate_that_is_not_the_fragment_is_invalid(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    real = boundary.observe_owner

    def wrapped(owner):
        owner.candidate = b"VACACIONES: 99 dias tras 12 meses de servicio."
        return real(owner)

    boundary.observe_owner = wrapped
    try:
        result = boundary.run()
        assert result.state == "COMPLETED"
        assert boundary._grounding.verdict == "CANDIDATE_INVALID"
        assert boundary._grounding.days is None
    finally:
        _release(boundary)


def test_b2_grd_09_utf8_offset_inside_a_codepoint_is_invalid():
    watcher = DeterministicVacationGrounding()
    clause = b"VACACIONES: 20 dias tras 12 meses de servicio."
    source = b"\xc3\xa9" + clause
    evidence = SimpleNamespace(
        organization_id="ORG-A", utf8_bytes=len(source), content_revision=1, registered_version=1)
    verdict, days, _months = watcher.assess(
        source, source[1:1 + len(clause)], "CANDIDATE", b"q", source, evidence, "ORG-A", b"q")
    assert verdict == "CANDIDATE_INVALID" and days is None


def test_b2_grd_10_multibyte_document_keeps_ascii_digits(tmp_path):
    world = _positive(tmp_path, "Pol\u00edtica \u00e9 " + CLAUSE)
    boundary = world.boundary
    try:
        result = boundary.run()
        assert result.state == "COMPLETED"
        assert boundary._grounding.verdict == "EVIDENCE_FOUND"
        assert boundary._grounding.days == 20 and boundary._grounding.months == 12
    finally:
        _release(boundary)


def test_b2_grd_11_contradictory_clauses_do_not_choose_one(tmp_path):
    text = "VACACIONES: 20 dias tras 12 meses de servicio. VACACIONES: 5 dias tras 1 meses de servicio."
    world = _positive(tmp_path, text)
    boundary = world.boundary
    try:
        boundary.run()
        assert boundary._grounding.verdict == "EVIDENCE_INSUFFICIENT"
        assert boundary._grounding.days is None and boundary._grounding.months is None
    finally:
        _release(boundary)


def test_b2_grd_12_repeated_identical_clause_is_one_finding(tmp_path):
    text = "VACACIONES: 20 dias tras 12 meses de servicio. VACACIONES: 20 dias tras 12 meses de servicio."
    world = _positive(tmp_path, text)
    boundary = world.boundary
    try:
        boundary.run()
        assert boundary._grounding.verdict == "EVIDENCE_FOUND"
        assert boundary._grounding.days == 20 and boundary._grounding.months == 12
    finally:
        _release(boundary)


def test_b2_grd_13_hostile_instructions_stay_data(tmp_path):
    world = _positive(tmp_path, HOSTILE + " VACACIONES: 20 dias tras 12 meses de servicio.")
    boundary = world.boundary
    try:
        result = boundary.run()
        rendered = " ".join((repr(boundary), repr(result), repr(boundary._grounding), repr(boundary._observer)))
        assert HOSTILE not in rendered and "99" not in repr(boundary._grounding)
        assert boundary._grounding.verdict == "EVIDENCE_FOUND"
        assert boundary._grounding.days == 20 and boundary._grounding.months == 12
    finally:
        _release(boundary)


def test_b2_grd_14_swapped_reading_bytes_are_not_evidence(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    real = boundary.observe_owner

    def wrapped(owner):
        boundary._canonical = b"y" * len(boundary._canonical)
        return real(owner)

    boundary.observe_owner = wrapped
    try:
        boundary.run()
        assert boundary._grounding.verdict == "CANDIDATE_INVALID"
        assert boundary._grounding.days is None
    finally:
        _release(boundary)


def test_b2_grd_15_other_organization_keeps_its_own_reservation(tmp_path):
    world = _world(tmp_path)
    first, second = world.boundary, TrustedEnterpriseSourceBoundary.compose(
        world.lab.service, ledger=world.ledger, executor=world.executor["ORG-B"])
    try:
        first.read(world.lab.a, world.lab.request())
        second.read(world.lab.b, world.lab.request("b"))
        first.admit()
        second.admit()
        first.run()
        assert first._grounding.days == 20 and second._grounding is None
        assert set(_rows(world.ledger)) == {("ORG-A", "COMPLETED", "CHARGED"), ("ORG-B", "INTENT", "HELD")}
        second.run()
        assert second._grounding.days == 9 and second._grounding.months == 3
        assert first._grounding.days == 20
    finally:
        second.close()
        _release(first)


def test_b2_grd_16_foreign_owner_is_not_observed(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    try:
        with pytest.raises(ExecutionError) as denied:
            boundary.observe_owner(ExecutionOwner())
        assert denied.value.reason == "source_evidence_invalid"
        result = boundary.run()
        assert result.entries == 1 and boundary._grounding.verdict == "EVIDENCE_FOUND"
    finally:
        _release(boundary)


def test_b2_grd_17_other_lease_does_not_run_the_fake(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    try:
        denied = boundary._gateway.invoke_once_observed(ProcessingLease(str(uuid4())))
        assert denied.state == "DENY" and denied.entries == 0
        assert _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
        assert boundary.run().state == "COMPLETED"
    finally:
        _release(boundary)


def test_b2_grd_18_replaced_observer_cannot_watch(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    boundary._observer = DeterministicVacationGrounding()
    try:
        with pytest.raises(ExecutionError) as denied:
            boundary.run()
        assert denied.value.reason == "lease_invalid"
        assert boundary.state == "PREPARED" and _rows(world.ledger) == [("ORG-A", "INTENT", "HELD")]
        assert ("ai_provider_invocation_observed", "OBSERVED") not in _events(world.ledger)
    finally:
        _release(boundary)


def test_b2_grd_19_observer_is_single_use(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    real = boundary.observe_owner
    calls = []

    def wrapped(owner):
        calls.append(owner.entries)
        real(owner)
        with pytest.raises(ExecutionError):
            real(owner)

    boundary.observe_owner = wrapped
    try:
        boundary.run()
        assert calls == [1] and boundary._observer.used is True
        with pytest.raises(ExecutionError):
            boundary.run()
    finally:
        _release(boundary)


def test_b2_grd_20_same_lease_does_not_execute_twice(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    try:
        boundary.run()
        with pytest.raises(ExecutionError):
            boundary.run()
        assert _rows(world.ledger) == [("ORG-A", "COMPLETED", "CHARGED")]
        assert sum(event == "ai_provider_invocation_observed" for event, _outcome in _events(world.ledger)) == 1
    finally:
        _release(boundary)


def test_b2_grd_21_missing_gate_b_does_not_process(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        snapshot = world.lab.store.snapshot()
        rows = tuple(replace(row, gates=frozenset({Gate.READ})) if row.grant_id == "principal-grant-a" else row
                     for row in snapshot.principal_grants)
        world.lab.store.replace_rows("principal_grants", rows, expected_revision=snapshot.revision)
        with pytest.raises(ExecutionError):
            boundary.read(world.lab.a, world.lab.request())
        assert boundary.public_reads == 0 and _rows(world.ledger) == []
    finally:
        _release(boundary)


def test_b2_grd_22_missing_gate_c_stops_before_the_fake(tmp_path):
    lab = laboratory()
    lab.adapter.set_pages("vacation-a", (SyntheticPage(CLAUSE),))
    access = TestAccessAuthority(lab.clock)
    ledger = SQLiteExecutionLedger(tmp_path, access, lab.clock)
    admin = access.issue()
    executor = access.issue(role="executor")
    ledger.initialize(admin)
    now = lab.clock()
    start, end = now - timedelta(seconds=1), now + timedelta(hours=1)
    ledger.change_policy(admin, ModelProcessingProfile("ORG-A", start, end, end), expected_revision=1)
    boundary = TrustedEnterpriseSourceBoundary.compose(lab.service, ledger=ledger, executor=executor)
    try:
        boundary.read(lab.a, lab.request())
        with pytest.raises(ExecutionError) as denied:
            boundary.admit()
        assert denied.value.reason == "processing_not_granted"
        assert boundary.state == "DENIED" and _rows(ledger) == []
    finally:
        _release(boundary)


def test_b2_grd_23_24_revision_change_after_admission_is_revocation(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    try:
        snapshot = world.lab.store.snapshot()
        world.lab.store.replace_rows("principals", snapshot.principals, expected_revision=snapshot.revision)
        result = boundary.run()
        assert result.state == "REVOKED" and result.reason == "policy_changed" and result.entries == 0
        assert boundary._grounding.verdict == "REVOCATION_DETECTED"
        assert boundary._grounding.days is None
        assert ("ai_processing_revocation_detected", "REVOKED") in _events(world.ledger)
        assert ("ai_provider_invocation_observed", "OBSERVED") not in _events(world.ledger)
    finally:
        _release(boundary)


def test_b2_grd_26_audit_failure_on_read_creates_no_execution(tmp_path):
    world = _world(tmp_path)
    boundary = world.boundary
    try:
        def broken(_event):
            raise RuntimeError("audit down")

        world.lab.audit.append = broken
        with pytest.raises(ExecutionError):
            boundary.read(world.lab.a, world.lab.request())
        assert boundary.state == "DENIED" and _rows(world.ledger) == []
    finally:
        _release(boundary)


def test_b2_grd_27_ambiguous_finish_does_not_retry(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    real = world.ledger.finish

    def boom(*args, **kwargs):
        real(*args, **kwargs)
        raise RuntimeError("ambiguous")

    world.ledger.finish = boom
    try:
        result = boundary.run()
        assert result.state == "UNAVAILABLE" and result.entries == 1
        with pytest.raises(ExecutionError):
            boundary.run()
        assert _rows(world.ledger) == [("ORG-A", "COMPLETED", "CHARGED")]
        assert sum(event == "ai_provider_invocation_observed" for event, _outcome in _events(world.ledger)) == 1
    finally:
        world.ledger.finish = real
        _release(boundary)


def test_b2_grd_28_observer_failure_after_completed_is_not_grounded(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary

    def explode(*_args, **_kwargs):
        raise RuntimeError("observer down")

    boundary._observer.assess = explode
    try:
        result = boundary.run()
        assert result.state == "UNAVAILABLE" and result.reservation == "CHARGED"
        assert boundary._grounding.verdict == "TECHNICAL_FAILURE"
        assert boundary._grounding.days is None
        assert _rows(world.ledger) == [("ORG-A", "COMPLETED", "CHARGED")]
        with pytest.raises(ExecutionError):
            boundary.run()
    finally:
        _release(boundary)


def test_b2_grd_29_cancelled_error_during_the_model_is_uncertain(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    real = boundary._gateway.model._extract

    def interrupt(owner):
        owner.entries += 0
        raise CancelledError()

    boundary._gateway.model._extract = interrupt
    try:
        with pytest.raises(CancelledError):
            boundary.run()
        assert boundary.state == "UNCERTAIN" and boundary.outstanding_reservation == "UNCERTAIN"
        assert _rows(world.ledger) == [("ORG-A", "CANCELLED", "UNCERTAIN")]
    finally:
        boundary._gateway.model._extract = real
        _release(boundary)


def test_b2_grd_30_keyboard_interrupt_during_the_model_propagates(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary

    def interrupt(_owner):
        raise KeyboardInterrupt()

    boundary._gateway.model._extract = interrupt
    try:
        with pytest.raises(KeyboardInterrupt):
            boundary.run()
        assert boundary.state == "UNCERTAIN"
        assert boundary.outstanding_reservation == "UNCERTAIN"
    finally:
        _release(boundary)


def test_b2_grd_31_cleanup_failure_is_not_success(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    real = ExecutionOwner.clear

    def broken(self):
        raise RuntimeError("cleanup")

    ExecutionOwner.clear = broken
    try:
        result = boundary.run()
        assert result.state == "UNAVAILABLE" and result.reservation == "CHARGED"
        assert boundary._grounding.verdict == "TECHNICAL_FAILURE"
        assert _rows(world.ledger) == [("ORG-A", "COMPLETED", "CHARGED")]
        assert boundary._bound.candidate is None
    finally:
        ExecutionOwner.clear = real
        _release(boundary)


def test_b2_grd_32_canary_is_absent_from_repr_logs_and_sqlite(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    world = _positive(tmp_path)
    boundary = world.boundary
    try:
        result = boundary.run()
        rendered = " ".join((repr(boundary), repr(result), repr(boundary._grounding), repr(boundary._evidence)))
        assert CANARY not in rendered and CANARY not in caplog.text
        try:
            raise ExecutionError("source_evidence_invalid", unavailable=False)
        except ExecutionError:
            assert CANARY not in traceback.format_exc()
        for path in tmp_path.rglob("*"):
            if path.is_file() and path.name != "processing.owner":
                blob = path.read_bytes()
                assert CANARY.encode("utf-8") not in blob
                assert b"dias tras" not in blob
    finally:
        _release(boundary)


def test_b2_grd_33_public_result_has_no_candidate_channel(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    try:
        result = boundary.run()
        assert not hasattr(result, "candidate") and not hasattr(result, "days")
        assert "20" not in repr(result) and CLAUSE not in repr(result)
    finally:
        _release(boundary)


def test_b2_grd_34_unexecuted_close_still_cancels_and_executed_close_does_not(tmp_path):
    prepared = _positive(tmp_path)
    try:
        prepared.boundary.close()
        assert _rows(prepared.ledger) == [("ORG-A", "CANCELLED", "RELEASED")]
    finally:
        prepared.ledger.close()
    executed = _positive(tmp_path / "done")
    try:
        executed.boundary.run()
        executed.boundary.close()
        assert _rows(executed.ledger) == [("ORG-A", "COMPLETED", "CHARGED")]
        assert ("ai_processing_cancelled", "CANCELLED") not in _events(executed.ledger)
    finally:
        executed.ledger.close()


def test_b2_grd_35_no_derived_delivery_row(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    try:
        boundary.run()
        with sqlite3.connect(world.ledger.path) as connection:
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "aip_derived_delivery_grant" not in names
        assert all(outcome != "AUTHORIZED" or event == "ai_processing_authorized" for event, outcome in _events(world.ledger))
    finally:
        _release(boundary)


def test_b2_grd_36_positive_path_makes_no_network_attempt(tmp_path):
    before = _NETWORK["attempts"]
    world = _positive(tmp_path)
    try:
        world.boundary.run()
        assert _NETWORK["attempts"] == before
    finally:
        _release(world.boundary)


def test_b2_grd_37_historical_invoke_once_does_not_observe(tmp_path):
    lab = execution_laboratory(tmp_path)
    try:
        lease = lab.prepare()
        denied = lab.gateway.invoke_once_observed(lease)
        assert denied.state == "DENY" and denied.entries == 0
        result = lab.gateway.invoke_once(lease)
        assert result.state == "COMPLETED" and result.entries == 1
        assert not hasattr(lab.gateway.boundary, "observation") or lab.gateway.boundary.observation(ExecutionOwner()) is None
    finally:
        lab.close()


def _public(result, boundary):
    return (result.state, result.reason, result.entries, result.reservation,
            boundary.state, boundary.outstanding_reservation, boundary.public_reads)


def _sqlite_text(root):
    blob = b""
    for path in root.rglob("*"):
        if path.is_file() and path.name != "processing.owner":
            blob += path.read_bytes()
    return blob


def test_b2_grd_public_metadata_does_not_reveal_grounding(tmp_path):
    samples = (
        (CLAUSE, "EVIDENCE_FOUND", 20, 12),
        ("Documento ficticio vacation, organización ORG-A. Sin datos reales.", "EVIDENCE_INSUFFICIENT", None, None),
        ("VACACIONES: 20 dias tras 12 meses de servicio. VACACIONES: 5 dias tras 1 meses de servicio.",
         "EVIDENCE_INSUFFICIENT", None, None),
    )
    published, audits, codes = [], [], []
    forbidden = (b"EVIDENCE_FOUND", b"EVIDENCE_INSUFFICIENT", b"CANDIDATE_INVALID", b"VACACIONES", b"dias tras", CANARY.encode())
    try:
        for index, (text, verdict, days, months) in enumerate(samples):
            world = _positive(tmp_path / str(index), text)
            result = world.boundary.run()
            assert world.boundary._grounding.verdict == verdict
            assert world.boundary._grounding.days == days and world.boundary._grounding.months == months
            published.append(_public(result, world.boundary))
            audits.append(_events(world.ledger))
            with sqlite3.connect(world.ledger.path) as connection:
                codes.append(connection.execute("SELECT result_code FROM aip_execution").fetchone()[0])
            blob = _sqlite_text(tmp_path / str(index))
            rendered = " ".join((repr(result), result.state, result.reason, result.reservation, repr(world.boundary)))
            for token in ("EVIDENCE_FOUND", "EVIDENCE_INSUFFICIENT", "CANDIDATE_INVALID", "VACACIONES", "dias tras", CANARY):
                assert token not in rendered
            for token in forbidden:
                assert token not in blob
            world.boundary.close()
            world.ledger.close()
        assert published[0] == published[1] == published[2]
        assert audits[0] == audits[1] == audits[2]
        assert codes == ["CANDIDATE", "NO_EVIDENCE", "CANDIDATE"]
        assert "days" not in RuntimeExecution.__dataclass_fields__
    finally:
        pass


@pytest.mark.parametrize("window", ["before_consume", "during_fake", "before_observer", "during_grounding"])
def test_b2_grd_close_during_run_is_rejected_until_completion(tmp_path, window):
    world = _positive(tmp_path)
    boundary = world.boundary
    paused, release = threading.Event(), threading.Event()
    armed = {"done": False}

    def pause():
        if armed["done"]:
            return
        armed["done"] = True
        paused.set()
        assert release.wait(10)

    if window == "before_consume":
        real_consume = world.ledger.consume

        def consume(*args, **kwargs):
            pause()
            return real_consume(*args, **kwargs)

        world.ledger.consume = consume
    elif window == "during_fake":
        real_extract = boundary._gateway.model._extract

        def extract(owner):
            real_extract(owner)
            pause()

        boundary._gateway.model._extract = extract
    elif window == "before_observer":
        real_observe = boundary.observe_owner

        def observe(owner):
            pause()
            return real_observe(owner)

        boundary.observe_owner = observe
    else:
        real_assess = boundary._observer.assess

        def assess(*args, **kwargs):
            pause()
            return real_assess(*args, **kwargs)

        boundary._observer.assess = assess
    outcome, close_error = {}, {}

    def go():
        try:
            outcome["result"] = boundary.run()
        except Exception as error:
            outcome["error"] = error

    worker = threading.Thread(target=go)
    worker.start()
    try:
        assert paused.wait(10)
        expected = {
            "before_consume": ("INTENT", "HELD"),
            "during_fake": ("ENTERED", "HELD"),
            "before_observer": ("COMPLETED", "CHARGED"),
            "during_grounding": ("COMPLETED", "CHARGED"),
        }[window]
        assert _rows(world.ledger)[0][1:] == expected
        assert boundary._canonical is not None and boundary.state == "PREPARED"

        def do_close():
            try:
                boundary.close()
            except ExecutionError as error:
                close_error["reason"] = error.reason

        closer = threading.Thread(target=do_close)
        closer.start()
        closer.join(10)
        assert not closer.is_alive()
        assert close_error.get("reason") == "lease_invalid"
        assert boundary._canonical is not None and boundary._lease is not None
        release.set()
        worker.join(15)
        assert not worker.is_alive()
        assert outcome["result"].state == "COMPLETED" and outcome["result"].entries == 1
        assert _rows(world.ledger) == [("ORG-A", "COMPLETED", "CHARGED")]
        assert ("ai_processing_cancelled", "CANCELLED") not in _events(world.ledger)
        assert sum(event == "ai_provider_invocation_observed" for event, _outcome in _events(world.ledger)) == 1
        record = boundary._grounding
        boundary.close()
        assert record.days is None and record.months is None
        assert _rows(world.ledger) == [("ORG-A", "COMPLETED", "CHARGED")]
    finally:
        release.set()
        worker.join(15)
        _release(boundary)


def test_b2_grd_two_runs_on_one_admission_invoke_the_fake_once(tmp_path):
    world = _positive(tmp_path)
    boundary = world.boundary
    paused, release = threading.Event(), threading.Event()
    real_extract = boundary._gateway.model._extract

    def extract(owner):
        real_extract(owner)
        paused.set()
        assert release.wait(10)

    boundary._gateway.model._extract = extract
    outcome, errors = {}, []

    def first():
        try:
            outcome["result"] = boundary.run()
        except Exception as error:
            outcome["error"] = error

    def second():
        try:
            boundary.run()
        except ExecutionError as error:
            errors.append(error.reason)

    primary = threading.Thread(target=first)
    primary.start()
    try:
        assert paused.wait(10)
        rival = threading.Thread(target=second)
        rival.start()
        rival.join(10)
        assert not rival.is_alive()
        assert errors == ["lease_invalid"]
        assert len(boundary._gateway._owners) == 1
        release.set()
        primary.join(15)
        assert not primary.is_alive()
        assert outcome["result"].state == "COMPLETED" and outcome["result"].entries == 1
        assert _rows(world.ledger) == [("ORG-A", "COMPLETED", "CHARGED")]
        assert sum(event == "ai_provider_invocation_observed" for event, _outcome in _events(world.ledger)) == 1
    finally:
        release.set()
        primary.join(15)
        _release(boundary)


def test_b2_grd_concurrent_runs_do_not_cross_figures(tmp_path):
    world = _world(tmp_path)
    first = world.boundary
    second = TrustedEnterpriseSourceBoundary.compose(
        world.lab.service, ledger=world.ledger, executor=world.executor["ORG-B"])
    try:
        first.read(world.lab.a, world.lab.request())
        second.read(world.lab.b, world.lab.request("b"))
        first.admit()
        second.admit()
        barrier = threading.Barrier(2)
        errors = []

        def run(boundary):
            try:
                barrier.wait(10)
                boundary.run()
            except Exception as error:
                errors.append(error)

        threads = [threading.Thread(target=run, args=(first,)), threading.Thread(target=run, args=(second,))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(15)
            assert not thread.is_alive()
        assert errors == []
        assert first._grounding.days == 20 and first._grounding.months == 12
        assert second._grounding.days == 9 and second._grounding.months == 3
        assert set(_rows(world.ledger)) == {
            ("ORG-A", "COMPLETED", "CHARGED"),
            ("ORG-B", "COMPLETED", "CHARGED"),
        }
    finally:
        second.close()
        _release(first)
