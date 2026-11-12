"""TASK-C03 E2E. One real fake, one local recipient, no network and no second read."""
from asyncio import CancelledError
from dataclasses import replace
from datetime import timedelta
import logging
import socket
import sqlite3
import threading
from uuid import uuid4

import pytest

from app.enterprise_ai_processing.answer import ABSTENTION, EphemeralAnswer
from app.enterprise_ai_processing.composition import EnterpriseAnswerFlow, LocalDelivery
from app.enterprise_ai_processing.delivery_sink import RecognizedDeliverySink
from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.fake_model import FakeEnterpriseModel
from app.enterprise_ai_processing.models import AIProcessingGrant, ModelProcessingProfile
from app.enterprise_ai_processing.orchestration import NODES
from app.enterprise_ai_processing.sqlite_ledger import (
    DerivedDeliveryGrant, DerivedDeliveryQuery, SQLiteExecutionLedger,
)
from app.enterprise_connectors.models import ConnectorExecutionContext, ConnectorOperation, Gate
from app.enterprise_connectors.synthetic import SyntheticPage
from tests.enterprise_ai_processing_execution_fixture import TestAccessAuthority
from tests.enterprise_connector_fixture import HOSTILE, laboratory


CANARY = "CANARY-C03-E2E-7c1a"
CLAUSE = "VACACIONES: 20 dias tras 12 meses de servicio. " + CANARY
OTHER = "VACACIONES: 9 dias tras 3 meses de servicio."
PHRASE = "Según el documento consultado, corresponden 20 días de vacaciones tras 12 meses de servicio."
OTHER_PHRASE = "Según el documento consultado, corresponden 9 días de vacaciones tras 3 meses de servicio."
DEMO = "Documento ficticio vacation, organización ORG-A. Sin datos reales."
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


def _record(lab, org="ORG-A", **overrides):
    suffix = "a" if org == "ORG-A" else "b"
    grant = lab.ledger.policy(lab.executor[org]).grants[0]
    now = lab.clock()
    values = dict(
        organization_id=org, derived_grant_id="derived-grant-" + suffix, version=1, enabled=True,
        principal_id=grant.principal_id, instance_id=grant.instance_id, tenant_id=grant.tenant_id,
        resource_id=grant.resource_id, recipient_id=grant.recipient_id, registered_version=1,
        processing_grant_id=grant.grant_id, processing_grant_version=grant.version,
        valid_from=now - timedelta(seconds=1), expires_at=now + timedelta(minutes=5),
        review_due_at=now + timedelta(minutes=4))
    values.update(overrides)
    return DerivedDeliveryGrant(**values)


def _query(record, processing, derived, **overrides):
    values = dict(
        organization_id=record.organization_id, principal_id=record.principal_id,
        instance_id=record.instance_id, tenant_id=record.tenant_id, resource_id=record.resource_id,
        recipient_id=record.recipient_id, registered_version=record.registered_version,
        processing_grant_id=record.processing_grant_id, processing_grant_version=record.processing_grant_version,
        derived_grant_id=record.derived_grant_id, processing_revision=processing,
        derived_delivery_revision=derived)
    values.update(overrides)
    return DerivedDeliveryQuery(**values)


def _issue(lab, org="ORG-A", **overrides):
    record = _record(lab, org, **overrides)
    processing = lab.ledger.policy(lab.executor[org]).revision
    derived = _count(lab.ledger.path, "SELECT coalesce(max(revision),0) FROM aip_derived_revision WHERE organization_id=?", (org,))
    new = lab.ledger.change_derived_grant(
        lab.admin[org], record, expected_processing_revision=processing, expected_derived_revision=derived)
    return record, processing, new, _query(record, processing, new)


def _world(tmp_path, text=CLAUSE, other=OTHER, *, fault=None, grant=True):
    tmp_path.mkdir(parents=True, exist_ok=True)
    lab = laboratory()
    lab.adapter.set_pages("vacation-a", (SyntheticPage(text),))
    lab.adapter.set_pages("vacation-b", (SyntheticPage(other),))
    access = TestAccessAuthority(lab.clock)
    lab.access = access
    ledger = SQLiteExecutionLedger(tmp_path, access, lab.clock, fault=fault)
    lab.ledger = ledger
    lab.admin, lab.executor = _seed(lab, ledger, access)
    ledger.migrate_to_v2(lab.admin["ORG-A"])
    query = None
    if grant:
        _record_a, _processing, _derived, query = _issue(lab)
    flow = None
    if query is not None:
        flow = EnterpriseAnswerFlow.compose(lab.service, ledger=ledger, executor=lab.executor["ORG-A"], query=query)
    return lab, flow


def _count(path, sql, params=()):
    with sqlite3.connect(path) as connection:
        return connection.execute(sql, params).fetchone()[0]


def _decision(path):
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT state,uncertainty_recorded FROM aip_delivery_decision").fetchone()
        return None if row is None else (row["state"], row["uncertainty_recorded"])


def _execution(path):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT run_state,reservation_state,result_code FROM aip_execution").fetchall()


def _invocations(path):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT count(*) FROM aip_audit WHERE event='ai_provider_invocation_observed'").fetchone()[0]


def _blob(path):
    data = path.read_bytes()
    for suffix in ("-wal", "-shm"):
        extra = path.with_name(path.name + suffix)
        if extra.exists():
            data += extra.read_bytes()
    return data


def _run(lab, flow, suffix="a"):
    context = lab.a if suffix == "a" else lab.b
    return flow.run(context, lab.request(suffix))


def _take(lab, flow, suffix="a"):
    context = lab.a if suffix == "a" else lab.b
    return flow.receive(context, lab.request(suffix))


def _close(lab, flow=None):
    try:
        if flow is not None:
            flow.close()
    finally:
        lab.ledger.close()


def _public(view):
    return (view.phase, view.reason, view.entries, view.reservation, view.decision, view.observed)


def test_e2e_c03_01_through_09_positive_delivery_uses_the_real_fake(tmp_path, caplog):
    lab, flow = _world(tmp_path)
    caplog.set_level(logging.DEBUG)
    try:
        assert type(flow._boundary._gateway.model) is FakeEnterpriseModel
        assert flow._compiled.checkpointer is False and flow._compiled.store is None
        assert set(NODES) <= set(flow._compiled.nodes)
        view = _run(lab, flow)
        assert type(view) is LocalDelivery
        assert _public(view) == ("COMPLETED", "accepted", 1, "CHARGED", "AUTHORIZED", True)
        assert _take(lab, flow) == PHRASE
        assert _take(lab, flow, "b") is None
        assert _take(lab, flow) == PHRASE
        assert flow._boundary.public_reads == 1 and _invocations(lab.ledger.path) == 1
        assert _execution(lab.ledger.path) == [("COMPLETED", "CHARGED", "CANDIDATE")]
        assert _decision(lab.ledger.path) == ("AUTHORIZED", 0)
        blob = _blob(lab.ledger.path)
        for secret in (PHRASE, ABSTENTION, CANARY, "EVIDENCE_FOUND", "VACACIONES", CLAUSE):
            assert secret.encode("utf-8") not in blob
        assert "días" not in str(flow.projection) and CANARY not in str(flow.projection)
        assert set(flow.projection) == {"phase", "reason", "organization_id", "operation_id", "entries", "reservation", "decision"}
        assert PHRASE not in caplog.text and CANARY not in caplog.text
        assert _NETWORK["attempts"] == 0
        with pytest.raises(ExecutionError) as replay:
            _run(lab, flow)
        assert replay.value.reason == "lease_invalid"
        assert _invocations(lab.ledger.path) == 1
    finally:
        _close(lab, flow)


def test_e2e_c03_10_11_authorized_abstention_when_the_clause_is_absent(tmp_path):
    lab, flow = _world(tmp_path, DEMO)
    try:
        view = _run(lab, flow)
        assert view.phase == "INSUFFICIENT" and view.decision == "AUTHORIZED" and view.observed is True
        assert _take(lab, flow) == ABSTENTION
        assert "20" not in _take(lab, flow) and CANARY not in _take(lab, flow)
        assert _invocations(lab.ledger.path) == 1 and _execution(lab.ledger.path)[0][0] == "COMPLETED"
    finally:
        _close(lab, flow)


def test_e2e_c03_12_contradictory_clauses_do_not_pick_a_number(tmp_path):
    lab, flow = _world(tmp_path, CLAUSE + " " + OTHER)
    try:
        view = _run(lab, flow)
        assert view.phase == "INSUFFICIENT" and view.observed is True
        text = _take(lab, flow)
        assert text == ABSTENTION and "20" not in text and "9" not in text
    finally:
        _close(lab, flow)


def _revoke_gates(lab, gates):
    snapshot = lab.store.snapshot()
    rows = tuple(replace(row, gates=gates) if row.grant_id == "principal-grant-a" else row
                 for row in snapshot.principal_grants)
    lab.store.replace_rows("principal_grants", rows, expected_revision=snapshot.revision)


@pytest.mark.parametrize("case,gates", [
    ("13-gate-a", frozenset({Gate.DELIVERY})),
    ("14-gate-b", frozenset({Gate.READ})),
])
def test_e2e_c03_13_14_connector_revocation_blocks_delivery(tmp_path, case, gates):
    lab, flow = _world(tmp_path)
    flow.before_authorize = lambda: _revoke_gates(lab, gates)
    try:
        view = _run(lab, flow)
        assert case
        assert view.phase == "DENIED" and view.decision == "SUPPRESSED" and view.observed is False
        assert _take(lab, flow) is None
        assert _execution(lab.ledger.path) == [("COMPLETED", "CHARGED", "CANDIDATE")]
        assert _decision(lab.ledger.path)[0] == "SUPPRESSED"
    finally:
        _close(lab, flow)


def test_e2e_c03_15_gate_c_revocation_does_not_cancel_the_charge(tmp_path):
    lab, flow = _world(tmp_path)

    def revoke():
        policy = lab.ledger.policy(lab.executor["ORG-A"])
        profile = replace(policy.profiles[0], version=policy.profiles[0].version + 1, enabled=False)
        lab.ledger.change_policy(lab.admin["ORG-A"], profile, expected_revision=policy.revision)

    flow.before_authorize = revoke
    try:
        view = _run(lab, flow)
        assert view.phase == "DENIED" and view.observed is False and _take(lab, flow) is None
        assert _execution(lab.ledger.path)[0][0] == "COMPLETED"
        assert "CANCELLED" not in {row[0] for row in _execution(lab.ledger.path)}
    finally:
        _close(lab, flow)


def test_e2e_c03_16_derived_grant_disabled(tmp_path):
    lab, flow = _world(tmp_path)

    def revoke():
        current = lab.ledger.policy(lab.executor["ORG-A"]).revision
        derived = _count(lab.ledger.path, "SELECT revision FROM aip_derived_revision WHERE organization_id='ORG-A'")
        lab.ledger.change_derived_grant(
            lab.admin["ORG-A"], _record(lab, version=2, enabled=False),
            expected_processing_revision=current, expected_derived_revision=derived)

    flow.before_authorize = revoke
    try:
        view = _run(lab, flow)
        assert view.phase == "DENIED" and _take(lab, flow) is None
        assert _decision(lab.ledger.path)[0] == "SUPPRESSED"
    finally:
        _close(lab, flow)


def test_e2e_c03_17_missing_derived_grant_does_not_invent_an_answer(tmp_path):
    lab, _flow = _world(tmp_path, grant=False)
    policy = lab.ledger.policy(lab.executor["ORG-A"])
    grant = policy.grants[0]
    query = DerivedDeliveryQuery(
        "ORG-A", grant.principal_id, grant.instance_id, grant.tenant_id, grant.resource_id,
        grant.recipient_id, 1, grant.grant_id, grant.version, "derived-grant-missing", policy.revision, 0)
    flow = EnterpriseAnswerFlow.compose(lab.service, ledger=lab.ledger, executor=lab.executor["ORG-A"], query=query)
    try:
        view = _run(lab, flow)
        assert view.phase == "DENIED" and view.observed is False and _take(lab, flow) is None
        assert _invocations(lab.ledger.path) == 1
        assert "20" not in view.reason
    finally:
        _close(lab, flow)


def test_e2e_c03_18_expired_derived_grant(tmp_path):
    now = None
    lab, _flow = _world(tmp_path, grant=False)
    now = lab.clock()
    _issue(lab, valid_from=now - timedelta(minutes=5), expires_at=now - timedelta(seconds=1),
           review_due_at=now - timedelta(seconds=1))
    record = _record(lab, valid_from=now - timedelta(minutes=5), expires_at=now - timedelta(seconds=1),
                     review_due_at=now - timedelta(seconds=1))
    processing = lab.ledger.policy(lab.executor["ORG-A"]).revision
    derived = _count(lab.ledger.path, "SELECT revision FROM aip_derived_revision WHERE organization_id='ORG-A'")
    query = _query(record, processing, derived)
    flow = EnterpriseAnswerFlow.compose(lab.service, ledger=lab.ledger, executor=lab.executor["ORG-A"], query=query)
    try:
        view = _run(lab, flow)
        assert view.phase == "DENIED" and view.reason == "authorization_expired" and _take(lab, flow) is None
    finally:
        _close(lab, flow)


def test_e2e_c03_19_other_organization_cannot_compose(tmp_path):
    lab, flow = _world(tmp_path)
    try:
        _record_b, processing, derived, query_b = _issue(lab, "ORG-B")
        with pytest.raises(ExecutionError) as caught:
            EnterpriseAnswerFlow.compose(lab.service, ledger=lab.ledger, executor=lab.executor["ORG-A"], query=query_b)
        assert caught.value.reason == "scope_mismatch"
        view = _run(lab, flow)
        assert view.organization_id == "ORG-A" and _take(lab, flow, "b") is None
    finally:
        _close(lab, flow)


def test_e2e_c03_20_other_recipient_is_not_a_delivery_port(tmp_path):
    lab, _flow = _world(tmp_path, grant=False)
    record, processing, derived, query = _issue(lab, recipient_id="recipient-b")
    del record
    flow = EnterpriseAnswerFlow.compose(lab.service, ledger=lab.ledger, executor=lab.executor["ORG-A"], query=query)
    try:
        view = _run(lab, flow)
        assert view.phase == "DENIED" and _take(lab, flow) is None and _take(lab, flow, "b") is None
        assert processing >= 1 and derived >= 1
    finally:
        _close(lab, flow)


def test_e2e_c03_21_processing_purpose_change_blocks_delivery(tmp_path):
    lab, flow = _world(tmp_path)

    def change():
        policy = lab.ledger.policy(lab.executor["ORG-A"])
        grant = replace(policy.grants[0], version=policy.grants[0].version + 1, processing_purpose="other-purpose")
        lab.ledger.change_policy(lab.admin["ORG-A"], grant, expected_revision=policy.revision, approval_ref=grant.grant_id)

    flow.before_authorize = change
    try:
        view = _run(lab, flow)
        assert view.phase == "DENIED" and _take(lab, flow) is None
        assert _execution(lab.ledger.path)[0][0] == "COMPLETED"
    finally:
        _close(lab, flow)


def test_e2e_c03_22_processing_revision_change(tmp_path):
    lab, flow = _world(tmp_path)

    def change():
        policy = lab.ledger.policy(lab.executor["ORG-A"])
        profile = replace(policy.profiles[0], version=policy.profiles[0].version + 1)
        lab.ledger.change_policy(lab.admin["ORG-A"], profile, expected_revision=policy.revision)

    flow.before_authorize = change
    try:
        view = _run(lab, flow)
        assert view.phase == "DENIED" and view.reason == "policy_changed"
        assert _take(lab, flow) is None
    finally:
        _close(lab, flow)


def test_e2e_c03_23_derived_revision_change(tmp_path):
    lab, flow = _world(tmp_path)

    def change():
        current = lab.ledger.policy(lab.executor["ORG-A"]).revision
        derived = _count(lab.ledger.path, "SELECT revision FROM aip_derived_revision WHERE organization_id='ORG-A'")
        lab.ledger.change_derived_grant(
            lab.admin["ORG-A"], _record(lab, version=2),
            expected_processing_revision=current, expected_derived_revision=derived)

    flow.before_authorize = change
    try:
        view = _run(lab, flow)
        assert view.phase == "DENIED" and view.reason == "policy_changed" and _take(lab, flow) is None
    finally:
        _close(lab, flow)


def test_e2e_c03_24_ledger_failure_before_authorization(tmp_path):
    def fault(stage):
        if stage == "derived_authorize_before_commit":
            raise ExecutionError("audit_unavailable", unavailable=True)

    lab, flow = _world(tmp_path, fault=fault)
    try:
        view = _run(lab, flow)
        assert view.phase == "UNCERTAIN" and view.observed is False and _take(lab, flow) is None
        assert _decision(lab.ledger.path) is None
        assert _execution(lab.ledger.path)[0][0] == "COMPLETED"
    finally:
        _close(lab, flow)


def test_e2e_c03_25_ledger_failure_after_authorization_seals_uncertainty(tmp_path):
    def fault(stage):
        if stage == "derived_authorize_after_commit":
            raise ExecutionError("audit_unavailable", unavailable=True)

    lab, flow = _world(tmp_path, fault=fault)
    try:
        view = _run(lab, flow)
        assert view.phase == "UNCERTAIN" and view.observed is False and _take(lab, flow) is None
        assert _decision(lab.ledger.path) == ("RELEASE_UNCERTAIN", 1)
        with pytest.raises(ExecutionError):
            _run(lab, flow)
        assert _invocations(lab.ledger.path) == 1
    finally:
        _close(lab, flow)


def test_e2e_c03_26_sink_failure_before_handoff_is_not_success(tmp_path):
    lab, flow = _world(tmp_path)
    flow.sink_fault = "before"
    try:
        view = _run(lab, flow)
        assert view.phase == "UNCERTAIN" and view.observed is False and _take(lab, flow) is None
        assert _decision(lab.ledger.path) == ("RELEASE_UNCERTAIN", 1)
        with pytest.raises(ExecutionError) as replay:
            _run(lab, flow)
        assert replay.value.reason == "lease_invalid"
    finally:
        _close(lab, flow)


def test_e2e_c03_27_sink_failure_after_handoff_is_uncertain(tmp_path):
    lab, flow = _world(tmp_path)
    flow.sink_fault = "after"
    try:
        view = _run(lab, flow)
        assert view.phase == "UNCERTAIN" and view.observed is False and view.phase != "COMPLETED"
        assert _take(lab, flow) == PHRASE and _take(lab, flow, "b") is None
        assert _decision(lab.ledger.path) == ("RELEASE_UNCERTAIN", 1)
        with pytest.raises(ExecutionError):
            _run(lab, flow)
        assert _invocations(lab.ledger.path) == 1
    finally:
        _close(lab, flow)


def test_e2e_c03_30_two_concurrent_runs_invoke_the_fake_once(tmp_path):
    lab, flow = _world(tmp_path)
    errors, views = [], []

    def once():
        try:
            views.append(_run(lab, flow))
        except ExecutionError as error:
            errors.append(error.reason)

    first, second = threading.Thread(target=once), threading.Thread(target=once)
    first.start()
    second.start()
    first.join(15)
    second.join(15)
    try:
        assert not first.is_alive() and not second.is_alive()
        assert len(views) == 1 and views[0].phase == "COMPLETED" and errors == ["lease_invalid"]
        assert _invocations(lab.ledger.path) == 1 and _take(lab, flow) == PHRASE
    finally:
        _close(lab, flow)


def test_e2e_c03_31_close_during_execution_does_not_cancel_or_skip_delivery(tmp_path):
    lab, flow = _world(tmp_path)
    model = flow._boundary._gateway.model
    real = model.invoke
    started, release = threading.Event(), threading.Event()

    def wrapped(owner):
        real(owner)
        started.set()
        assert release.wait(10)
        return None

    model.invoke = wrapped
    box = {}

    def once():
        try:
            box["view"] = _run(lab, flow)
        except BaseException as error:
            box["error"] = error

    worker = threading.Thread(target=once)
    worker.start()
    assert started.wait(10)
    try:
        with pytest.raises(ExecutionError) as closed:
            flow.close()
        assert closed.value.reason == "lease_invalid"
        release.set()
        worker.join(15)
        assert "error" not in box and box["view"].phase == "COMPLETED"
        assert _take(lab, flow) == PHRASE
        assert _execution(lab.ledger.path)[0][0] == "COMPLETED"
    finally:
        release.set()
        worker.join(5)
        _close(lab, flow)


def test_e2e_c03_32_expiration_during_the_flow(tmp_path):
    lab, flow = _world(tmp_path)
    flow.before_authorize = lambda: lab.clock.advance(6)
    try:
        view = _run(lab, flow)
        assert view.phase == "DENIED" and view.reason == "authorization_expired"
        assert _take(lab, flow) is None
        assert _execution(lab.ledger.path)[0][0] == "COMPLETED"
    finally:
        _close(lab, flow)


def test_e2e_c03_33_observer_error_does_not_deliver(tmp_path):
    lab, flow = _world(tmp_path)

    def broken(owner):
        raise RuntimeError("observer")

    flow._boundary.observe_owner = broken
    try:
        view = _run(lab, flow)
        assert view.observed is False and _take(lab, flow) is None
        assert _execution(lab.ledger.path)[0][0] == "COMPLETED"
        assert PHRASE.encode("utf-8") not in _blob(lab.ledger.path)
    finally:
        _close(lab, flow)


def test_e2e_c03_34_grounding_error_does_not_deliver(tmp_path):
    lab, flow = _world(tmp_path)

    def broken(*_args, **_kwargs):
        raise RuntimeError("grounding")

    flow._boundary._observer.assess = broken
    try:
        view = _run(lab, flow)
        assert view.observed is False and _take(lab, flow) is None
        assert _execution(lab.ledger.path)[0][0] == "COMPLETED"
    finally:
        _close(lab, flow)


def test_e2e_c03_35_36_cancellation_and_interrupt_propagate(tmp_path):
    for signal in (CancelledError, KeyboardInterrupt):
        directory = tmp_path / signal.__name__
        lab, flow = _world(directory)
        model = flow._boundary._gateway.model
        real = model.invoke

        def wrapped(owner, raised=signal, original=real):
            original(owner)
            raise raised()

        model.invoke = wrapped
        try:
            with pytest.raises(signal):
                _run(lab, flow)
            assert _take(lab, flow) is None
            assert _decision(lab.ledger.path) != ("AUTHORIZED", 0)
        finally:
            _close(lab, flow)


def test_e2e_c03_37_hostile_instructions_do_not_become_the_answer(tmp_path):
    lab, flow = _world(tmp_path, HOSTILE + " " + CLAUSE)
    try:
        view = _run(lab, flow)
        text = _take(lab, flow)
        assert view.phase == "COMPLETED" and text == PHRASE
        assert "Ignora" not in text and "ORG-B" not in text and CANARY not in text
    finally:
        _close(lab, flow)


def test_e2e_c03_38_through_41_channels_do_not_carry_the_sentence(tmp_path):
    lab, flow = _world(tmp_path)
    try:
        view = _run(lab, flow)
        rendered = repr(view) + repr(flow) + repr(flow._sink) + str(flow.projection)
        public = {key: value for key, value in flow.projection.items() if key != "operation_id"}
        assert "LocalDelivery(in-process)" in rendered
        assert PHRASE not in rendered and "20" not in str(public) and "12" not in str(public)
        assert flow._compiled.checkpointer is False
        blob = _blob(lab.ledger.path)
        assert PHRASE.encode("utf-8") not in blob and b"EVIDENCE_FOUND" not in blob
        error = ExecutionError("internal_failure")
        assert PHRASE not in str(error) and CANARY not in str(error)
    finally:
        _close(lab, flow)


def test_e2e_c03_49_50_no_network_and_only_the_fake_model():
    assert _NETWORK["attempts"] == 0
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            __import__("pathlib").Path(__file__).resolve().parents[1] / "app" / "enterprise_ai_processing" / name
            for name in ("composition.py", "orchestration.py", "answer.py", "authorization.py", "delivery_sink.py"))
    )
    for token in ("openai", "httpx", "socket", "get_answer", "get_grounding", "get_candidate"):
        assert token not in source


def test_e2e_c03_public_denials_do_not_encode_the_figures(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    lab_a, flow_a = _world(left, CLAUSE)
    lab_b, flow_b = _world(right, CLAUSE + " " + OTHER)
    flow_a.before_authorize = lambda: _revoke_gates(lab_a, frozenset({Gate.READ}))
    flow_b.before_authorize = lambda: _revoke_gates(lab_b, frozenset({Gate.READ}))
    try:
        first, second = _run(lab_a, flow_a), _run(lab_b, flow_b)
        assert _public(first) == _public(second)
        assert "20" not in first.reason and "9" not in second.reason
        assert _take(lab_a, flow_a) is None and _take(lab_b, flow_b) is None
    finally:
        _close(lab_a, flow_a)
        _close(lab_b, flow_b)


def test_e2e_c03_organizations_do_not_share_an_answer(tmp_path):
    lab, flow = _world(tmp_path)
    _issue(lab, "ORG-B")
    other = EnterpriseAnswerFlow.compose(
        lab.service, ledger=lab.ledger, executor=lab.executor["ORG-B"],
        query=_query(_record(lab, "ORG-B"), lab.ledger.policy(lab.executor["ORG-B"]).revision,
                     _count(lab.ledger.path, "SELECT revision FROM aip_derived_revision WHERE organization_id='ORG-B'")))
    try:
        first = _run(lab, flow, "a")
        second = _run(lab, other, "b")
        assert first.phase == "COMPLETED" and second.phase == "COMPLETED"
        assert _take(lab, flow) == PHRASE and _take(lab, flow, "b") is None
        assert _take(lab, other, "b") == OTHER_PHRASE and _take(lab, other) is None
        assert _invocations(lab.ledger.path) == 2
    finally:
        _close(lab, flow)
        other.close()


def test_e2e_c03_p1a_recipient_string_is_not_authority(tmp_path):
    lab, flow = _world(tmp_path)
    try:
        assert flow.receive(lab.a, lab.request()) is None
        view = _run(lab, flow)
        assert _take(lab, flow) == PHRASE
        assert flow.receive(lab.identity.issue("principal-a"), lab.request()) == PHRASE
        assert flow.receive(lab.b, lab.request()) is None
        assert flow.receive(replace(lab.a), lab.request()) is None
        forged = ConnectorExecutionContext(
            lab.a.principal_id, lab.a.organization_id, lab.a.authenticated_at, lab.a.expires_at)
        assert flow.receive(forged, lab.request()) is None
        assert flow.receive("recipient-a", lab.request()) is None
        assert flow.receive(lab.a, "recipient-a") is None
        assert flow.receive(lab.a, lab.request(resource="security-a")) is None
        assert flow.receive(lab.a, lab.request(operation=ConnectorOperation.METADATA)) is None
        planted = RecognizedDeliverySink("recipient-a")
        planted._text = PHRASE
        assert planted.release(object()) is None
        assert planted.release(flow._sink._token) is None
        with pytest.raises(TypeError):
            EnterpriseAnswerFlow.compose(
                lab.service, ledger=lab.ledger, executor=lab.executor["ORG-A"], query=flow._query, sink=planted)
        unused = EphemeralAnswer("answer", "recipient-a", view.operation_id)
        unused._text = "forged"
        assert _take(lab, flow) == PHRASE and "forged" not in _take(lab, flow)
        lab.clock.advance(11 * 60)
        assert flow.receive(lab.a, lab.request()) is None
    finally:
        _close(lab, flow)


def test_e2e_c03_p1a_second_accept_does_not_repeat_delivery(tmp_path):
    lab, flow = _world(tmp_path)
    try:
        _run(lab, flow)
        with pytest.raises(ExecutionError) as caught:
            flow._sink.accept(
                recipient_id="recipient-a", operation_id=flow._state["operation_id"],
                decision_state="AUTHORIZED", revision=1, text=PHRASE)
        assert caught.value.reason == "revision_conflict" and PHRASE not in str(caught.value)
        assert _take(lab, flow) == PHRASE
        with pytest.raises(ExecutionError) as replay:
            _run(lab, flow)
        assert replay.value.reason == "lease_invalid" and _invocations(lab.ledger.path) == 1
    finally:
        _close(lab, flow)


def test_e2e_c03_p1b_failed_seal_does_not_claim_release_or_replay(tmp_path):
    def fault(stage):
        if stage == "derived_uncertain_before_commit":
            raise ExecutionError("audit_unavailable", unavailable=True)

    lab, flow = _world(tmp_path, fault=fault)
    flow.sink_fault = "before"
    try:
        view = _run(lab, flow)
        assert view.phase == "UNCERTAIN" and view.observed is False and view.decision == "AUTHORIZED"
        assert _decision(lab.ledger.path) == ("AUTHORIZED", 0)
        assert _take(lab, flow) is None and PHRASE not in repr(view)
        assert _execution(lab.ledger.path) == [("COMPLETED", "CHARGED", "CANDIDATE")]
        with pytest.raises(ExecutionError):
            _run(lab, flow)
        assert _invocations(lab.ledger.path) == 1 and _decision(lab.ledger.path) == ("AUTHORIZED", 0)
    finally:
        _close(lab, flow)


def test_e2e_c03_p1b_copied_phrase_stays_uncertain_when_seal_fails(tmp_path):
    def fault(stage):
        if stage == "derived_uncertain_before_commit":
            raise ExecutionError("audit_unavailable", unavailable=True)

    lab, flow = _world(tmp_path, fault=fault)
    flow.sink_fault = "after"
    try:
        view = _run(lab, flow)
        assert view.phase == "UNCERTAIN" and view.observed is False and view.decision == "AUTHORIZED"
        assert _decision(lab.ledger.path) == ("AUTHORIZED", 0)
        assert _take(lab, flow) == PHRASE and _take(lab, flow, "b") is None
        assert flow.receive("recipient-a", lab.request()) is None
        with pytest.raises(ExecutionError):
            _run(lab, flow)
        assert _invocations(lab.ledger.path) == 1
        assert _execution(lab.ledger.path)[0][0] == "COMPLETED"
    finally:
        _close(lab, flow)


def test_e2e_c03_p1b_unreadable_decision_is_not_called_released(tmp_path):
    def fault(stage):
        if stage in {"derived_authorize_after_commit", "delivery_state"}:
            raise ExecutionError("audit_unavailable", unavailable=True)

    lab, flow = _world(tmp_path, fault=fault)
    try:
        view = _run(lab, flow)
        assert view.phase == "UNCERTAIN" and view.observed is False
        assert view.decision != "RELEASE_UNCERTAIN" and view.decision != "AUTHORIZED"
        assert _take(lab, flow) is None and PHRASE not in repr(view)
        assert _decision(lab.ledger.path) == ("AUTHORIZED", 0)
        assert _execution(lab.ledger.path)[0] == ("COMPLETED", "CHARGED", "CANDIDATE")
        with pytest.raises(ExecutionError):
            _run(lab, flow)
        assert _invocations(lab.ledger.path) == 1
    finally:
        _close(lab, flow)
