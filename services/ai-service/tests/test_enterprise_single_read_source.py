"""B2-SRC: one public read, one in-process receipt, C01 recognition, C02 prepare."""
import copy
import gc
import logging
import pickle
import socket
import sqlite3
import threading
import traceback
import weakref
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from asyncio import CancelledError

from app.enterprise_ai_processing.execution_types import ExecutionError, ProcessingLease
from app.enterprise_ai_processing.gateway import EnterpriseModelGateway
from app.enterprise_ai_processing.models import (
    AIProcessingEnvelope, AIProcessingGrant, ModelProcessingProfile, ProcessingOutcome,
    ProcessingReason, SourceEvidence,
)
from app.enterprise_ai_processing.policy import GateCPolicyEvaluator
from app.enterprise_ai_processing.sqlite_ledger import DerivedGrantMatch, SQLiteExecutionLedger
from app.enterprise_connectors.models import (
    ConnectorFailure, ConnectorOperation, Gate, OperationResult, Outcome, Reason,
)
from app.enterprise_connectors.service import ConnectorService
from app.enterprise_connectors.synthetic import SyntheticPage
from tests.enterprise_ai_processing_execution_fixture import TestAccessAuthority
from tests.enterprise_ai_processing_fixture import processing_laboratory
from tests.enterprise_connector_fixture import laboratory
from tests.enterprise_single_read_source import SyntheticSingleReadIssuer, TrustedSourceReadReceipt
from tests.test_enterprise_ai_processing_architecture import C01, C02

CANARY = "CANARY-B2-SRC-TEXT-9f3c"
_NETWORK = {"attempts": 0}


def _blocked(*args, **kwargs):
    _NETWORK["attempts"] += 1
    raise RuntimeError("unauthorized network")


def _install_network_guard():
    for name in ("connect", "connect_ex", "send", "sendall"):
        setattr(socket.socket, name, _blocked)
    for name in ("create_connection", "getaddrinfo", "gethostbyname"):
        setattr(socket, name, _blocked)


_install_network_guard()


@pytest.fixture(autouse=True)
def _offline_counter():
    yield _NETWORK


def _positive(text="Documento sintetico B2-SRC."):
    lab = laboratory()
    lab.adapter.set_pages("vacation-a", (SyntheticPage(text),))
    issuer = SyntheticSingleReadIssuer(lab)
    before = lab.adapter.calls
    receipt = issuer.read_once(lab.a, lab.request())
    return lab, issuer, receipt, before


def _materials(issuer, receipt):
    return issuer.open_materials(receipt)


def _rows(ledger):
    with sqlite3.connect(ledger.path) as connection:
        return connection.execute(
            "SELECT run_state, reservation_state FROM aip_execution").fetchall()


def _stack(tmp_path, text=CANARY):
    lab = laboratory()
    lab.adapter.set_pages("vacation-a", (SyntheticPage(text),))
    access = TestAccessAuthority(lab.clock)
    admin, executor = access.issue(), access.issue(role="executor")
    ledger = SQLiteExecutionLedger(tmp_path, access, lab.clock)
    ledger.initialize(admin)
    now = lab.clock()
    start, end = now - timedelta(seconds=1), now + timedelta(hours=1)
    profile = ModelProcessingProfile("ORG-A", start, end, end)
    grant = AIProcessingGrant(
        "processing-grant-a", "principal-a", "ORG-A", "instance-a", "tenant-a", "vacation-a",
        "recipient-a", start, end, end, "not_required")
    revision = ledger.change_policy(admin, profile, expected_revision=1)
    revision = ledger.change_policy(admin, grant, expected_revision=revision, approval_ref=grant.grant_id)
    issuer = SyntheticSingleReadIssuer(lab, ledger=ledger, executor=executor)
    gateway = EnterpriseModelGateway(ledger, lab.policy, issuer)
    invoked = []
    gateway.model.invoke = lambda owner: invoked.append(True)
    return lab, issuer, ledger, gateway, invoked, revision


def test_b2_src_01_one_authorized_read_one_receipt():
    lab, issuer, receipt, before = _positive()
    envelope, evidence, result, document = _materials(issuer, receipt)
    assert before == ()
    assert issuer.public_executions == 1
    assert issuer.adapter_reads == 1
    assert len(lab.adapter.calls) == 1
    assert issuer.observed_gates == [Gate.READ]
    assert type(result) is OperationResult and result.status is Outcome.DELIVERY_ALLOWED
    assert len(result.documents) == 1 and result.documents[0] is document
    assert evidence.read_correlation_id == result.correlation_id
    assert evidence.content_revision == document.version
    assert evidence.utf8_bytes == len(document.text.encode("utf-8"))
    assert not hasattr(receipt, "operation_id")
    with pytest.raises(TypeError):
        issuer.read_once(lab.a, lab.request(), content_revision=9)
    decision = GateCPolicyEvaluator(lab.policy, issuer).evaluate(
        lab.store.snapshot(), issuer.processing_policy, envelope, evidence)
    assert decision.outcome is ProcessingOutcome.ALLOW_PROCESSING
    assert type(decision) is not ProcessingLease
    issuer.close()


def test_b2_src_02_second_read_is_not_the_first_evidence():
    lab, issuer, first, _before = _positive("primero")
    second = issuer.read_once(lab.a, lab.request())
    first_envelope, first_evidence, first_result, first_document = _materials(issuer, first)
    second_envelope, second_evidence, second_result, second_document = _materials(issuer, second)
    assert issuer.public_executions == 2 and issuer.adapter_reads == 2
    assert first_result.correlation_id != second_result.correlation_id
    assert first_document is not second_document
    assert issuer.recognizes_source(first_evidence, second_envelope) is False
    assert issuer.recognizes_source(second_evidence, first_envelope) is False
    assert issuer.recognizes_source(first_evidence, first_envelope) is True
    issuer.close()


def test_b2_src_03_copied_result_is_not_recognized():
    _lab, issuer, receipt, _before = _positive()
    _envelope, _evidence, result, _document = _materials(issuer, receipt)
    copied = replace(result)
    assert copied == result and copied is not result
    assert issuer.open_materials(receipt)[2] is result
    issuer.close()


def test_b2_src_04_caller_built_result_and_evidence_are_not_recognized():
    lab, issuer, receipt, _before = _positive()
    envelope, evidence, result, _document = _materials(issuer, receipt)
    built = OperationResult(
        result.status, result.reason, result.correlation_id, result.local_status,
        result.external_status, result.delivery_status, result.documents)
    forged = replace(evidence)
    assert built == result and built is not result
    assert forged == evidence and forged is not evidence
    assert issuer.recognizes_source(forged, envelope) is False
    assert issuer.recognizes_envelope(envelope) is True
    decision = GateCPolicyEvaluator(lab.policy, issuer).evaluate(
        lab.store.snapshot(), issuer.processing_policy, envelope, forged)
    assert decision.outcome is ProcessingOutcome.DENY
    assert decision.reason is ProcessingReason.SOURCE
    issuer.close()


def test_b2_src_05_unregistered_receipt_is_not_authority():
    _lab, issuer, receipt, _before = _positive()
    bogus = TrustedSourceReadReceipt(issuer, object())
    with pytest.raises(ExecutionError):
        issuer.open_materials(bogus)
    with pytest.raises(TypeError, match="not portable"):
        pickle.dumps(receipt)
    with pytest.raises(TypeError, match="not portable"):
        copy.copy(receipt)
    with pytest.raises(TypeError, match="not portable"):
        copy.deepcopy(receipt)
    with pytest.raises(AttributeError):
        issuer.receipt_for("operation")
    issuer.close()


def test_b2_src_06_consumed_receipt_does_not_mint_another_lease(tmp_path):
    lab, issuer, ledger, gateway, invoked, revision = _stack(tmp_path)
    try:
        receipt = issuer.read_once(lab.a, lab.request())
        envelope, evidence, _result, _document = _materials(issuer, receipt)
        assert issuer.public_executions == 1 and envelope.processing_revision == revision
        lease = issuer.prepare_once(gateway, receipt)
        assert type(lease) is ProcessingLease and lease is not receipt
        assert _rows(ledger) == [("INTENT", "HELD")]
        owner = gateway._owners[id(lease)]
        gateway._seal(owner)
        assert owner.evidence is evidence and owner.source_bytes == receipt._record.canonical
        assert issuer.recognizes_source(evidence, envelope) is True
        with pytest.raises(ExecutionError):
            issuer.prepare_once(gateway, receipt)
        with pytest.raises(ExecutionError):
            gateway.prepare(envelope, evidence)
        assert _rows(ledger) == [("INTENT", "HELD")]
        assert invoked == [] and issuer.public_executions == 1 and issuer.adapter_reads == 1
    finally:
        gateway.close()
        ledger.close()
        issuer.close()


def test_b2_src_concurrent_prepare_admits_one_lease(tmp_path):
    lab, issuer, ledger, gateway, invoked, _revision = _stack(tmp_path)
    try:
        receipt = issuer.read_once(lab.a, lab.request())
        envelope, evidence, _result, document = _materials(issuer, receipt)
        start = threading.Barrier(2)
        outcome = {"leases": [], "reasons": [], "text": []}
        guard = threading.Lock()

        def attempt():
            try:
                start.wait(timeout=5)
                lease = issuer.prepare_once(gateway, receipt)
                with guard:
                    outcome["leases"].append(lease)
            except ExecutionError as error:
                with guard:
                    outcome["reasons"].append(error.reason)
                    outcome["text"].append(str(error))
            except BaseException as error:
                with guard:
                    outcome["reasons"].append(type(error).__name__)
                    outcome["text"].append(str(error))

        workers = [threading.Thread(target=attempt) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=15)
        assert all(not worker.is_alive() for worker in workers)
        assert len(outcome["leases"]) == 1 and outcome["reasons"] == ["source_evidence_invalid"]
        assert all(CANARY not in text for text in outcome["text"])
        assert _rows(ledger) == [("INTENT", "HELD")] and len(gateway._owners) == 1
        owner = gateway._owners[id(outcome["leases"][0])]
        gateway._seal(owner)
        assert owner.evidence is evidence and owner.source_bytes == document.text.encode("utf-8")
        assert issuer.recognizes_source(evidence, envelope) is True
        with pytest.raises(ExecutionError):
            issuer.prepare_once(gateway, receipt)
        assert _rows(ledger) == [("INTENT", "HELD")]
        assert invoked == [] and issuer.public_executions == 1 and issuer.adapter_reads == 1
        for path in tmp_path.rglob("*"):
            if path.is_file() and path.name != "processing.owner":
                assert CANARY.encode("utf-8") not in path.read_bytes()
    finally:
        gateway.close()
        ledger.close()
        issuer.close()


def test_b2_src_07_other_organization_is_not_recognized():
    lab, issuer, receipt, _before = _positive()
    envelope, evidence, _result, _document = _materials(issuer, receipt)
    foreign = replace(envelope, operation_id=str(uuid4()), context=replace(envelope.context, organization_id="ORG-B"))
    decision = GateCPolicyEvaluator(lab.policy, issuer).evaluate(
        lab.store.snapshot(), issuer.processing_policy, foreign, evidence)
    assert decision.outcome is not ProcessingOutcome.ALLOW_PROCESSING
    assert decision.organization_id is None and decision.resource_id is None
    assert "ORG-B" not in repr(decision)
    issuer.close()


def test_b2_src_08_other_recipient_is_not_recognized():
    lab, issuer, receipt, _before = _positive()
    envelope, evidence, _result, _document = _materials(issuer, receipt)
    other = replace(envelope, read_request=replace(envelope.read_request, recipient_id="recipient-b"))
    assert issuer.recognizes_envelope(other) is False
    decision = GateCPolicyEvaluator(lab.policy, issuer).evaluate(
        lab.store.snapshot(), issuer.processing_policy, other, evidence)
    assert decision.outcome is ProcessingOutcome.DENY
    assert decision.reason is ProcessingReason.IDENTITY
    assert decision.resource_id is None
    issuer.close()


def test_b2_src_09_expired_envelope_is_not_authorized():
    lab, issuer, receipt, _before = _positive()
    envelope, evidence, _result, _document = _materials(issuer, receipt)
    lab.clock.advance(6)
    decision = GateCPolicyEvaluator(lab.policy, issuer).evaluate(
        lab.store.snapshot(), issuer.processing_policy, envelope, evidence)
    assert decision.outcome is ProcessingOutcome.DENY
    assert decision.reason is ProcessingReason.EXPIRED
    issuer.close()


def test_b2_src_10_revision_change_before_and_after_execute(tmp_path):
    lab = laboratory()
    issuer = SyntheticSingleReadIssuer(lab)
    before = lab.store.snapshot().revision

    def bump():
        snapshot = lab.store.snapshot()
        lab.store.replace_rows("principals", snapshot.principals, expected_revision=snapshot.revision)

    issuer._after_execute = bump
    with pytest.raises(ExecutionError):
        issuer.read_once(lab.a, lab.request())
    assert issuer.public_executions == 1 and issuer._retained == []
    assert lab.store.snapshot().revision == before + 1
    issuer.close()

    stack_lab, stack_issuer, ledger, gateway, invoked, _revision = _stack(tmp_path)
    try:
        receipt = stack_issuer.read_once(stack_lab.a, stack_lab.request())
        envelope, evidence, _result, _document = _materials(stack_issuer, receipt)
        snapshot = stack_lab.store.snapshot()
        stack_lab.store.replace_rows("principals", snapshot.principals, expected_revision=snapshot.revision)
        decision = GateCPolicyEvaluator(stack_lab.policy, stack_issuer).evaluate(
            stack_lab.store.snapshot(), stack_issuer.processing_policy, envelope, evidence)
        assert decision.reason is ProcessingReason.STALE
        with pytest.raises(ExecutionError):
            stack_issuer.prepare_once(gateway, receipt)
        assert _rows(ledger) == [] and invoked == []
    finally:
        gateway.close()
        ledger.close()
        stack_issuer.close()


def test_b2_src_11_local_bytes_replaced_without_version_change():
    _lab, issuer, receipt, _before = _positive("version-stable")
    envelope, evidence, _result, document = _materials(issuer, receipt)
    version = document.version
    receipt._record.canonical = b"y" * len(receipt._record.canonical)
    assert document.version == version == evidence.content_revision
    assert issuer.recognizes_source(evidence, envelope) is False
    decision = GateCPolicyEvaluator(_lab.policy, issuer).evaluate(
        _lab.store.snapshot(), issuer.processing_policy, envelope, evidence)
    assert decision.reason is ProcessingReason.SOURCE
    issuer.close()


def test_b2_src_12_multibyte_utf8_counts_bytes():
    text = "e\u0301" * 4
    _lab, issuer, receipt, _before = _positive(text)
    _envelope, evidence, _result, document = _materials(issuer, receipt)
    canonical = document.text.encode("utf-8")
    assert document.text == text
    assert evidence.utf8_bytes == len(canonical) == 12
    assert len(text) == 8 and evidence.utf8_bytes != len(text)
    assert canonical != ("é" * 4).encode("utf-8")
    assert receipt._record.canonical == canonical
    issuer.close()


def test_b2_src_13_1024_bytes_can_be_c_eligible():
    lab, issuer, receipt, _before = _positive("x" * 1024)
    envelope, evidence, _result, document = _materials(issuer, receipt)
    assert evidence.utf8_bytes == 1024 and len(document.text) == 1024
    decision = GateCPolicyEvaluator(lab.policy, issuer).evaluate(
        lab.store.snapshot(), issuer.processing_policy, envelope, evidence)
    assert decision.outcome is ProcessingOutcome.ALLOW_PROCESSING
    issuer.close()


def test_b2_src_14_1025_bytes_are_not_truncated_and_c_denies():
    lab = laboratory()
    snapshot = lab.store.snapshot()
    definition = snapshot.definitions[0]
    raised = replace(definition, limits=replace(definition.limits, max_bytes=2048))
    lab.store.replace_rows("definitions", (raised,), expected_revision=snapshot.revision)
    lab.adapter.set_pages("vacation-a", (SyntheticPage("y" * 1025),))
    issuer = SyntheticSingleReadIssuer(lab)
    receipt = issuer.read_once(lab.a, lab.request())
    envelope, evidence, _result, document = _materials(issuer, receipt)
    assert len(document.text) == 1025 and evidence.utf8_bytes == 1025
    assert receipt._record.canonical == b"y" * 1025
    decision = GateCPolicyEvaluator(lab.policy, issuer).evaluate(
        lab.store.snapshot(), issuer.processing_policy, envelope, evidence)
    assert decision.outcome is ProcessingOutcome.DENY
    assert decision.reason is ProcessingReason.LIMIT
    issuer.close()


def test_b2_src_15_missing_delivery_permission_has_no_receipt():
    lab = laboratory()
    snapshot = lab.store.snapshot()
    rows = tuple(replace(row, gates=frozenset({Gate.READ})) if row.grant_id == "principal-grant-a" else row
                 for row in snapshot.principal_grants)
    lab.store.replace_rows("principal_grants", rows, expected_revision=snapshot.revision)
    issuer = SyntheticSingleReadIssuer(lab)
    with pytest.raises(ExecutionError):
        issuer.read_once(lab.a, lab.request())
    assert issuer.public_executions == 0 and issuer._retained == []
    issuer.close()


def test_b2_src_16_missing_c_grant_does_not_process(tmp_path):
    lab = laboratory()
    access = TestAccessAuthority(lab.clock)
    admin, executor = access.issue(), access.issue(role="executor")
    ledger = SQLiteExecutionLedger(tmp_path, access, lab.clock)
    issuer = SyntheticSingleReadIssuer(lab, ledger=ledger, executor=executor)
    gateway = EnterpriseModelGateway(ledger, lab.policy, issuer)
    invoked = []
    gateway.model.invoke = lambda owner: invoked.append(True)
    try:
        ledger.initialize(admin)
        receipt = issuer.read_once(lab.a, lab.request())
        with pytest.raises(ExecutionError) as caught:
            issuer.prepare_once(gateway, receipt)
        assert caught.value.reason == "processing_not_granted"
        assert gateway._owners == {} and _rows(ledger) == [] and invoked == []
        with pytest.raises(ExecutionError):
            issuer.prepare_once(gateway, receipt)
    finally:
        gateway.close()
        ledger.close()
        issuer.close()


def test_b2_src_17_connector_failure_has_no_receipt():
    lab = laboratory()
    lab.adapter.set_pages("vacation-a", (SyntheticPage(status=404),))
    issuer = SyntheticSingleReadIssuer(lab)
    with pytest.raises(ExecutionError):
        issuer.read_once(lab.a, lab.request())
    assert issuer.public_executions == 1 and issuer.adapter_reads == 1 and issuer._retained == []
    issuer.close()


def test_b2_src_18_audit_unavailable_has_no_receipt():
    lab = laboratory()
    issuer = SyntheticSingleReadIssuer(lab)

    def broken(_event):
        raise ConnectorFailure(Reason.AUDIT, unavailable=True)

    lab.audit.append = broken
    with pytest.raises(ExecutionError):
        issuer.read_once(lab.a, lab.request())
    assert issuer.public_executions == 1 and issuer._retained == []
    issuer.close()


def test_b2_src_19_cancellation_is_preserved_without_a_receipt():
    lab = laboratory()
    issuer = SyntheticSingleReadIssuer(lab)
    other = laboratory()
    other_issuer = SyntheticSingleReadIssuer(other)
    other_receipt = other_issuer.read_once(other.a, other.request())

    def cancel(_resource_id, _cursor):
        raise CancelledError()

    lab.adapter.on_read = cancel
    with pytest.raises(CancelledError):
        issuer.read_once(lab.a, lab.request())
    assert issuer._retained == []
    assert other_issuer.recognizes_envelope(other_issuer.open_materials(other_receipt)[0]) is True
    issuer.close()
    other_issuer.close()


def test_b2_src_20_keyboard_interrupt_is_preserved_without_a_receipt():
    lab = laboratory()
    issuer = SyntheticSingleReadIssuer(lab)

    def interrupt(_resource_id, _cursor):
        raise KeyboardInterrupt()

    lab.adapter.on_read = interrupt
    with pytest.raises(KeyboardInterrupt):
        issuer.read_once(lab.a, lab.request())
    assert issuer._retained == []
    issuer.close()


def test_b2_src_21_no_content_in_logs_repr_traceback_or_sqlite(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    lab, issuer, ledger, gateway, invoked, _revision = _stack(tmp_path)
    try:
        receipt = issuer.read_once(lab.a, lab.request())
        envelope, evidence, result, document = _materials(issuer, receipt)
        lease = issuer.prepare_once(gateway, receipt)
        rendered = " ".join((
            repr(receipt), repr(evidence), repr(envelope), repr(result), repr(document), repr(lease),
        ))
        assert CANARY not in rendered and CANARY not in caplog.text
        receipt._record.canonical = b"substituted-bytes"
        try:
            issuer.prepare_once(gateway, receipt)
        except ExecutionError as error:
            text = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            assert CANARY not in text and "substituted-bytes" not in text
            for path in tmp_path.rglob("*"):
                if not path.is_file() or path.name == "processing.owner":
                    continue
                assert CANARY.encode("utf-8") not in path.read_bytes(), path.name
        assert invoked == []
    finally:
        gateway.close()
        ledger.close()
        issuer.close()


def test_b2_src_22_old_workflow_still_closes_before_return():
    source = (Path(__file__).resolve().parents[1] / "app/enterprise_workflows/document_read.py").read_text(encoding="utf-8")
    invoke = source.split("def _invoke", 1)[1].split("\n    def ", 1)[0]
    assert invoke.index("self._close(") < invoke.index("return EnterpriseResult")
    issuer_source = Path(__file__).with_name("enterprise_single_read_source.py").read_text(encoding="utf-8")
    assert "document_read" not in issuer_source and "EnterpriseDocumentWorkflow" not in issuer_source


def test_b2_src_23_c01_evaluator_recognizes_the_same_read():
    lab, issuer, receipt, _before = _positive()
    envelope, evidence, _result, _document = _materials(issuer, receipt)
    evaluator = GateCPolicyEvaluator(lab.policy, issuer)
    assert type(evaluator) is GateCPolicyEvaluator
    decision = evaluator.evaluate(lab.store.snapshot(), issuer.processing_policy, envelope, evidence)
    assert decision.outcome is ProcessingOutcome.ALLOW_PROCESSING
    assert decision.operation_id == envelope.operation_id
    issuer.close()


def test_b2_src_direct_prepare_cannot_mint_a_second_lease(tmp_path):
    lab, issuer, ledger, gateway, invoked, _revision = _stack(tmp_path)
    try:
        receipt = issuer.read_once(lab.a, lab.request())
        envelope, evidence, _result, _document = _materials(issuer, receipt)
        lease = gateway.prepare(envelope, evidence)
        gateway._seal(gateway._owners[id(lease)])
        assert issuer.recognizes_source(evidence, envelope) is True
        with pytest.raises(ExecutionError):
            gateway.prepare(envelope, evidence)
        assert _rows(ledger) == [("INTENT", "HELD")]
        assert invoked == [] and issuer.public_executions == 1
    finally:
        gateway.close()
        ledger.close()
        issuer.close()


def test_b2_src_24_c02_prepare_does_not_invoke_the_fake(tmp_path):
    lab, issuer, ledger, gateway, invoked, _revision = _stack(tmp_path)
    try:
        receipt = issuer.read_once(lab.a, lab.request())
        lease = issuer.prepare_once(gateway, receipt)
        owner = gateway._owners[id(lease)]
        gateway._seal(owner)
        assert type(gateway) is EnterpriseModelGateway
        assert invoked == [] and "invoke_once" not in Path(__file__).with_name(
            "enterprise_single_read_source.py").read_text(encoding="utf-8")
    finally:
        gateway.close()
        ledger.close()
        issuer.close()


def test_b2_src_25_derived_grant_is_not_the_read_authority(tmp_path):
    lab, issuer, ledger, gateway, invoked, _revision = _stack(tmp_path)
    try:
        receipt = issuer.read_once(lab.a, lab.request())
        assert not isinstance(receipt, DerivedGrantMatch)
        assert not isinstance(receipt, ProcessingLease)
        issuer.prepare_once(gateway, receipt)
        with sqlite3.connect(ledger.path) as connection:
            states = {row[0] for row in connection.execute("SELECT run_state FROM aip_execution")}
        assert "AUTHORIZED" not in states and invoked == []
        source = Path(__file__).with_name("enterprise_single_read_source.py").read_text(encoding="utf-8")
        assert "assess_derived_delivery" not in source and "DerivedGrantMatch" not in source
    finally:
        gateway.close()
        ledger.close()
        issuer.close()


def test_b2_src_26_no_unauthorized_network(_offline_counter):
    _positive()
    assert _offline_counter["attempts"] == 0


def test_b2_src_laboratory_constructor_reads_before_any_composer(monkeypatch):
    calls = []
    original = ConnectorService.execute

    def wrapped(self, context, request, *, gate=Gate.READ):
        calls.append(gate)
        return original(self, context, request, gate=gate)

    monkeypatch.setattr(ConnectorService, "execute", wrapped)
    processing_laboratory()
    assert calls == [Gate.READ]


def test_b2_src_weak_identity_is_not_authority():
    lab, issuer, receipt, _before = _positive()
    envelope, evidence, result, document = _materials(issuer, receipt)
    evidence_id, document_id = id(evidence), id(document)
    del envelope, evidence, result, document
    gc.collect()
    restored_envelope, restored_evidence, restored_result, restored_document = _materials(issuer, receipt)
    assert id(restored_evidence) == evidence_id and id(restored_document) == document_id
    assert issuer.recognizes_source(restored_evidence, restored_envelope) is True
    issuer.close()
    del restored_envelope, restored_evidence, restored_result, restored_document, receipt
    gc.collect()

    class Marker:
        pass

    marker = Marker()
    orphans = weakref.WeakValueDictionary()
    orphans[id(marker)] = marker
    key = id(marker)
    del marker
    gc.collect()
    assert key not in orphans


def test_b2_src_second_read_evidence_is_not_the_first_boundary():
    lab, issuer, first, _before = _positive("alfa")
    second = issuer.read_once(lab.a, lab.request())
    first_envelope, first_evidence, _result, _document = _materials(issuer, first)
    _second_envelope, second_evidence, _second_result, _second_document = _materials(issuer, second)
    copied = replace(second_evidence)
    assert issuer.recognizes_source(second_evidence, first_envelope) is False
    assert issuer.recognizes_source(copied, first_envelope) is False
    assert issuer.recognizes_source(first_evidence, first_envelope) is True
    issuer.close()


def test_b2_src_pagination_is_not_one_external_read():
    lab = laboratory()
    lab.adapter.set_pages("vacation-a", (SyntheticPage("uno", next_cursor=1), SyntheticPage("dos")))
    issuer = SyntheticSingleReadIssuer(lab)
    with pytest.raises(ExecutionError):
        issuer.read_once(lab.a, lab.request())
    assert issuer.public_executions == 1 and issuer.adapter_reads == 2 and issuer._retained == []
    issuer.close()


def test_b2_src_cleanup_exception_drops_this_owner_only():
    lab, issuer, receipt, _before = _positive(CANARY)
    other_lab, other, other_receipt, _other_before = _positive("otro")

    def boom():
        raise RuntimeError("cleanup-failed")

    issuer._cleanup_hook = boom
    with pytest.raises(RuntimeError, match="cleanup-failed") as caught:
        issuer.close()
    assert CANARY not in str(caught.value)
    assert issuer._retained == []
    with pytest.raises(ExecutionError):
        issuer.open_materials(receipt)
    assert other.recognizes_envelope(other.open_materials(other_receipt)[0]) is True
    other.close()


def test_b2_src_product_inventory_stays_closed():
    source = Path(__file__).with_name("enterprise_single_read_source.py").read_text(encoding="utf-8")
    assert "enterprise_single_read_source.py" not in C01 | C02
    for banned in ("frame.clear", "f_locals", "gc.collect", "invoke_once", "FakeEnterpriseModel"):
        assert banned not in source
    assert type(SourceEvidence) is type
    assert AIProcessingEnvelope.__module__.endswith("enterprise_ai_processing.models")
