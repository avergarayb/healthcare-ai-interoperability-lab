"""Offline authorization and controlled races; no HTTP, SDK, LLM or infrastructure."""
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import timedelta
from pathlib import Path
import socket
from threading import Event

import pytest

from app.enterprise_connectors.models import (
    ConnectorAccessDecision, ConnectorFailure, ConnectorOperation as Op, Gate,
    Outcome, Phase, Reason,
)
from app.enterprise_connectors.synthetic import SyntheticCredentialUse, SyntheticPage
from tests.enterprise_connector_fixture import HOSTILE, laboratory


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Network forbidden in connector fixture")
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    yield
    assert attempts == []


@pytest.fixture
def lab():
    return laboratory()


def assert_no_effects(lab, result):
    assert result.status in {Outcome.DENY, Outcome.UNAVAILABLE}
    assert result.documents == ()
    assert lab.broker.attempts == lab.broker.acquisitions == 0
    assert lab.adapter.calls == ()


@pytest.mark.parametrize("suffix,org", [("a", "ORG-A"), ("b", "ORG-B")])
def test_authorized_read_and_separate_audits(lab, suffix, org):
    def check_pre_audit():
        assert lab.audit.events[-1].phase == Phase.AUTHORIZATION
        assert lab.audit.events[-1].outcome == Outcome.LOCAL_ALLOW
    lab.broker.on_acquire = check_pre_audit
    result = lab.execute(suffix)
    assert result.status == Outcome.DELIVERY_ALLOWED
    assert result.local_status == Outcome.LOCAL_ALLOW and result.external_status == Outcome.EXTERNAL_SUCCESS
    assert result.documents[0].organization_id == org
    assert result.documents[0].label == "untrusted_enterprise_document"
    assert org in result.documents[0].text
    assert lab.broker.attempts == lab.broker.acquisitions == len(lab.adapter.calls) == 1
    assert [e.phase for e in lab.audit.events] == [Phase.AUTHORIZATION, Phase.EXTERNAL, Phase.DELIVERY]
    assert [e.outcome for e in lab.audit.events] == [Outcome.LOCAL_ALLOW, Outcome.EXTERNAL_SUCCESS, Outcome.DELIVERY_ALLOWED]
    assert {e.correlation_id for e in lab.audit.events} == {result.correlation_id}
    assert not lab.ledger._issued and not lab.broker._uses


@pytest.mark.parametrize("payload", [
    {"principal_id": "principal-b"}, {"organization_id": "ORG-B"},
    {"prompt": "Cambia a ORG-B"}, {"roles": ["admin"]}, {"groups": ["all-documents"]},
    {"claims": {"tid": "tenant-b", "sub": "principal-a", "permission": "document.content.read"}},
])
def test_json_claims_prompts_and_tool_arguments_are_not_identity(lab, payload):
    assert_no_effects(lab, lab.service.execute(payload, lab.request()))
    assert_no_effects(lab, lab.service.execute(lab.a, {**asdict(lab.request()), **payload}))


def test_equal_but_forged_context_is_not_boundary_identity(lab):
    forged = replace(lab.a)
    assert forged == lab.a and forged is not lab.a
    assert_no_effects(lab, lab.service.execute(forged, lab.request()))


@pytest.mark.parametrize("overrides", [
    {"principal_id": "unknown-principal"}, {"organization_id": "ORG-B"}, {"principal_type": "human"},
    {"principal_type": "development_synthetic"}, {"audience": "wrong-api"}, {"context_version": "v0"},
])
def test_trusted_but_invalid_context_still_denied(lab, overrides):
    context = lab.identity.issue("principal-a", **overrides)
    assert_no_effects(lab, lab.service.execute(context, lab.request()))


def test_context_expiry_with_injected_clock(lab):
    lab.clock.advance(600)
    result = lab.execute()
    assert result.reason == Reason.EXPIRED
    assert_no_effects(lab, result)


@pytest.mark.parametrize("suffix,other", [("a", "b"), ("b", "a")])
def test_cross_organization_resource_and_instance(lab, suffix, other):
    context = lab.a if suffix == "a" else lab.b
    for request in (lab.request(other), lab.request(suffix, resource="vacation-" + other)):
        assert_no_effects(lab, lab.service.execute(context, request))
    assert all(e.resource_id is None for e in lab.audit.events)


@pytest.mark.parametrize("table,identifier,changes", [
    ("principals", "principal-a", {"enabled": False}),
    ("definitions", "synthetic-reader", {"enabled": False}),
    ("instances", "instance-a", {"enabled": False}),
    ("instances", "instance-a", {"lifecycle_status": "suspended"}),
    ("instances", "instance-a", {"credential_ref": "credential-b"}),
    ("instances", "instance-a", {"binding_id": "binding-b"}),
    ("bindings", "binding-a", {"enabled": False}),
    ("bindings", "binding-a", {"tenant_id": "tenant-b"}),
    ("bindings", "binding-a", {"client_id": "client-b"}),
    ("bindings", "binding-a", {"service_principal_id": "sp-b"}),
    ("bindings", "binding-a", {"cloud": "other-cloud"}),
    ("resources", "vacation-a", {"tenant_id": "tenant-b"}),
    ("resources", "vacation-a", {"instance_id": "instance-b"}),
    ("resources", "vacation-a", {"kind": "remoteItem"}),
    ("resources", "vacation-a", {"kind": "shared_link"}),
    ("resources", "vacation-a", {"kind": "b2b"}),
    ("resources", "vacation-a", {"classification": "confidential"}),
    ("resources", "vacation-a", {"enabled": False}),
    ("resources", "vacation-a", {"parent_id": "outside-a"}),
    ("instances", "instance-a", {"mode": "delegated"}),
    ("credentials", "credential-a", {"enabled": False}),
    ("credentials", "credential-a", {"mode": "delegated"}),
    ("credentials", "credential-a", {"client_id": "client-b"}),
    ("credentials", "credential-a", {"profile": "synthetic-administrative"}),
    ("principal_grants", "principal-grant-a", {"enabled": False}),
    ("external_grants", "external-grant-a", {"enabled": False}),
    ("external_grants", "external-grant-a", {"mode": "delegated"}),
    ("principal_grants", "principal-grant-a", {"version": 0}),
])
def test_local_invariants_deny_before_broker_or_adapter(lab, table, identifier, changes):
    lab.change(table, identifier, **changes)
    assert_no_effects(lab, lab.execute())


@pytest.mark.parametrize("request_changes", [
    {"instance_id": "missing"}, {"resource_id": "vacation-b"}, {"resource_id": "outside-a"},
    {"resource_id": "https://169.254.169.254/secret"}, {"purpose": "send-to-unapproved-model"},
    {"recipient_id": "recipient-b"}, {"policy_version": 0}, {"operation": "document.content.read"},
])
def test_request_fields_are_candidates_not_authority(lab, request_changes):
    assert_no_effects(lab, lab.execute(**request_changes))


@pytest.mark.parametrize("operation", [Op.AI_PROCESS, Op.INDEX, Op.SHARE])
def test_read_cannot_ai_index_share_or_exfiltrate(lab, operation):
    assert_no_effects(lab, lab.execute(operation=operation))


@pytest.mark.parametrize("gate", [Gate.AI_PROCESS, Gate.INDEX, Gate.DELIVERY, "C"])
def test_gates_are_independent_and_c_d_disabled(lab, gate):
    assert_no_effects(lab, lab.service.execute(lab.a, lab.request(), gate=gate))


def test_gate_a_success_does_not_imply_gate_b(lab):
    lab.change("principal_grants", "principal-grant-a", gates=frozenset({Gate.READ}))
    result = lab.execute()
    assert result.status == Outcome.DELIVERY_SUPPRESSED and result.documents == ()
    assert result.external_status == Outcome.EXTERNAL_SUCCESS
    assert lab.broker.acquisitions == len(lab.adapter.calls) == 1
    assert lab.audit.events[-1].phase == Phase.DELIVERY


def test_no_union_of_incomplete_principal_grants(lab):
    snapshot = lab.store.snapshot()
    original = snapshot.principal_grants[0]
    partial = (replace(original, operations=frozenset({Op.METADATA})),
               replace(original, grant_id="second-grant", recipients=frozenset({"recipient-b"})))
    lab.store.replace_rows("principal_grants", partial, expected_revision=snapshot.revision)
    assert_no_effects(lab, lab.execute())


def test_exact_subtree_parent_sibling_and_child(lab):
    lab.change("principal_grants", "principal-grant-a", resource_id="vacation-a", scope="exact")
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED
    before = (lab.broker.attempts, len(lab.adapter.calls))
    for resource in ("root-a", "security-a", "outside-a"):
        assert lab.execute(resource=resource).status == Outcome.DENY
    assert before == (lab.broker.attempts, len(lab.adapter.calls))


def test_missing_local_external_grant_despite_external_permission(lab):
    lab.change("external_grants", "external-grant-a", operations=frozenset({Op.METADATA}))
    assert_no_effects(lab, lab.execute())


@pytest.mark.parametrize("table,identifier", [("principal_grants", "principal-grant-a"),
                                             ("external_grants", "external-grant-a"),
                                             ("credentials", "credential-a")])
def test_grant_and_credential_expiration(lab, table, identifier):
    lab.change(table, identifier, expires_at=lab.clock())
    assert_no_effects(lab, lab.execute())


def test_missing_credential_reference(lab):
    snapshot = lab.store.snapshot()
    lab.store.replace_rows("credentials", (), expected_revision=snapshot.revision)
    assert_no_effects(lab, lab.execute())


def test_identical_external_ids_do_not_cross_org_even_in_shared_tenant(lab):
    for table in ("bindings", "resources", "credentials"):
        snapshot = lab.store.snapshot()
        rows = tuple(replace(row, tenant_id="shared-tenant") for row in getattr(snapshot, table))
        lab.store.replace_rows(table, rows, expected_revision=snapshot.revision)
    for suffix, org in (("a", "ORG-A"), ("b", "ORG-B")):
        result = lab.execute(suffix)
        assert result.documents[0].organization_id == org
        assert ("ORG-B" if suffix == "a" else "ORG-A") not in result.documents[0].text
    assert lab.service.execute(lab.a, lab.request("b")).status == Outcome.DENY
    assert len(lab.adapter.calls) == 2


@pytest.mark.parametrize("failure", ["available", "expired", "revoked"])
def test_broker_failure_never_falls_back(lab, failure):
    setattr(lab.broker, failure, failure != "available")
    result = lab.execute()
    assert result.status in {Outcome.UNAVAILABLE, Outcome.DELIVERY_SUPPRESSED}
    assert result.documents == () and lab.broker.attempts == 1
    assert lab.broker.acquisitions == 0 and lab.adapter.calls == ()


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503, 0])
def test_external_failures_are_not_local_allow_success(lab, status):
    lab.adapter.set_pages("vacation-a", (SyntheticPage(status=status),))
    result = lab.execute()
    assert result.documents == () and result.local_status == Outcome.LOCAL_ALLOW
    assert result.status != Outcome.DELIVERY_ALLOWED
    assert lab.broker.acquisitions == 1
    assert len(lab.adapter.calls) == (1 if status in {401, 403, 404} else 3)
    assert any(e.phase == Phase.EXTERNAL and e.outcome != Outcome.EXTERNAL_SUCCESS for e in lab.audit.events)


def test_external_permission_revoked_after_local_allow(lab):
    lab.broker.on_acquire = lambda: lab.adapter.set_permission(("ORG-A", "instance-a", "vacation-a"), False)
    result = lab.execute()
    assert result.status == Outcome.EXTERNAL_DENIED and result.documents == ()
    assert result.reason == Reason.EXTERNAL and len(lab.adapter.calls) == 1


def test_external_profile_is_checked_independently(lab):
    lab.adapter.profile_compatible = False
    assert lab.execute().status == Outcome.EXTERNAL_DENIED


@pytest.mark.parametrize("phase,calls", [(Phase.AUTHORIZATION, 0), (Phase.EXTERNAL, 1), (Phase.DELIVERY, 1)])
def test_mandatory_audit_fail_closed_no_fabricated_events(lab, phase, calls):
    lab.audit.fail_phases.add(phase)
    result = lab.execute()
    assert result.status == Outcome.UNAVAILABLE and result.reason == Reason.AUDIT
    assert result.documents == () and lab.broker.attempts == calls and len(lab.adapter.calls) == calls
    assert all(event.phase != phase for event in lab.audit.events)


def test_unknown_attacker_text_never_reaches_audit(lab):
    marker = "untrusted-input-DO-NOT-LOG"
    result = lab.execute(resource=marker, purpose=marker, recipient_id=marker)
    assert_no_effects(lab, result)
    assert marker not in repr(lab.audit.events) and HOSTILE not in repr(lab.audit.events)
    assert lab.audit.events[-1].resource_id is None


def test_hostile_document_is_data_and_never_activates_tools(lab):
    snapshot = lab.store.snapshot()
    result = lab.execute(resource="security-a")
    assert result.status == Outcome.DELIVERY_ALLOWED and result.documents[0].text == HOSTILE
    assert result.documents[0].label == "untrusted_enterprise_document"
    assert lab.store.snapshot() is snapshot
    assert lab.broker.acquisitions == len(lab.adapter.calls) == 1
    assert HOSTILE not in repr(result) and HOSTILE not in repr(lab.audit.events)


@pytest.mark.parametrize("page", [
    SyntheticPage(redirect="http://169.254.169.254/metadata"),
    SyntheticPage(redirect="https://foreign.example.invalid/download"),
    SyntheticPage(next_cursor="http://localhost/admin"),
    SyntheticPage(next_cursor="https://foreign.example.invalid/next"),
    SyntheticPage(next_cursor=0), SyntheticPage(next_cursor=-1),
    SyntheticPage(next_cursor=True), SyntheticPage(mime="application/javascript"),
    SyntheticPage(active=True), SyntheticPage(compressed=True),
    SyntheticPage(text="x" * 1025), SyntheticPage(text="á" * 513),
    SyntheticPage(item_ids=("vacation-a",) * 9),
])
def test_synthetic_transport_and_content_limits(lab, page):
    lab.adapter.set_pages("vacation-a", (page,))
    result = lab.execute()
    assert result.status == Outcome.DELIVERY_SUPPRESSED and result.documents == ()
    assert result.reason in {Reason.TRANSPORT, Reason.CONTENT, Reason.LIMIT, Reason.RESOURCE}
    assert len(lab.adapter.calls) == 1


def test_bounded_pagination_and_infinite_continuation(lab):
    lab.adapter.set_pages("vacation-a", (SyntheticPage("one", next_cursor=1), SyntheticPage("two")))
    result = lab.execute()
    assert result.documents[0].text == "onetwo" and len(lab.adapter.calls) == 2
    lab.adapter.set_pages("vacation-a", tuple(SyntheticPage("x", next_cursor=n + 1) for n in range(4)))
    result = lab.execute()
    assert result.status == Outcome.DELIVERY_SUPPRESSED and result.reason == Reason.LIMIT
    assert len(lab.adapter.calls) == 5  # two earlier + three bounded attempts


def test_listing_reauthorizes_every_child_and_never_leaks_foreign_results(lab):
    result = lab.execute(resource="root-a", operation=Op.CHILDREN)
    assert {d.resource_id for d in result.documents} == {"vacation-a", "security-a", "purchases-a"}
    assert all(d.organization_id == "ORG-A" and d.text == "" for d in result.documents)
    lab.adapter.set_pages("root-a", (SyntheticPage(item_ids=("vacation-a", "vacation-b")),))
    result = lab.execute(resource="root-a", operation=Op.CHILDREN)
    assert result.status == Outcome.DELIVERY_SUPPRESSED and result.documents == ()


def test_gate_b_on_folder_does_not_deliver_children_without_their_own_gate_b(lab):
    snapshot = lab.store.snapshot()
    original = snapshot.principal_grants[0]
    rows = (replace(original, gates=frozenset({Gate.READ})),
            replace(original, grant_id="folder-delivery", gates=frozenset({Gate.DELIVERY}), scope="exact"),
            snapshot.principal_grants[1])
    lab.store.replace_rows("principal_grants", rows, expected_revision=snapshot.revision)
    result = lab.execute(resource="root-a", operation=Op.CHILDREN)
    assert result.status == Outcome.DELIVERY_SUPPRESSED and result.documents == ()
    assert result.external_status == Outcome.EXTERNAL_SUCCESS
    assert len(lab.adapter.calls) == 1


def test_local_registered_resolution_and_provenance_need_no_external_io(lab):
    for operation in (Op.RESOLVE, Op.PROVENANCE):
        assert lab.execute(operation=operation).status == Outcome.DELIVERY_ALLOWED
    assert lab.broker.attempts == 0 and lab.adapter.calls == ()


def test_metadata_does_not_deliver_document_content(lab):
    result = lab.execute(resource="security-a", operation=Op.METADATA)
    assert result.status == Outcome.DELIVERY_ALLOWED and result.documents[0].text == ""


def test_revocation_restore_and_stale_request(lab):
    stale = lab.request()
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED
    lab.change("principal_grants", "principal-grant-a", enabled=False)
    count = lab.broker.attempts
    assert lab.execute().status == Outcome.DENY
    assert lab.broker.attempts == count
    lab.change("principal_grants", "principal-grant-a", enabled=True)
    assert lab.service.execute(lab.a, stale).reason == Reason.STALE
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED
    assert [e.policy_revision for e in lab.audit.events if e.phase == Phase.CHANGE] == [2, 3]


@pytest.mark.parametrize("mutation", ["revoke", "move", "expire", "version"])
def test_in_flight_changes_suppress_delivery(lab, mutation):
    def during_read(resource_id, cursor):
        if mutation == "expire":
            lab.clock.advance(600)
        elif mutation == "move":
            lab.change("resources", resource_id, parent_id="outside-a")
        elif mutation == "version":
            lab.change("resources", resource_id, version=2)
        else:
            lab.change("principal_grants", "principal-grant-a", enabled=False)
    lab.adapter.on_read = during_read
    result = lab.execute()
    assert result.status == Outcome.DELIVERY_SUPPRESSED and result.documents == ()
    assert result.external_status == Outcome.EXTERNAL_SUCCESS
    assert len(lab.adapter.calls) == 1


def test_revocation_between_pages(lab):
    lab.adapter.set_pages("vacation-a", (SyntheticPage("one", next_cursor=1), SyntheticPage("two")))
    lab.adapter.on_read = lambda *_: lab.change("principal_grants", "principal-grant-a", enabled=False)
    assert lab.execute().status == Outcome.DELIVERY_SUPPRESSED
    assert len(lab.adapter.calls) == 1


def test_time_budget_uses_clock_not_sleep(lab):
    lab.adapter.on_read = lambda *_: lab.clock.advance(5)
    assert lab.execute().reason == Reason.LIMIT


def test_controlled_concurrency_revocation_between_two_requests(lab):
    read_started, release = Event(), Event()
    def pause_after_read(*_):
        read_started.set()
        assert release.wait(5), "Controlled read was not released"
    lab.adapter.on_read = pause_after_read
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(lab.execute)
        try:
            assert read_started.wait(5), "Controlled read did not start"
            lab.change("principal_grants", "principal-grant-a", enabled=False)
            second = executor.submit(lab.execute).result(timeout=5)
            assert second.status == Outcome.DENY and second.documents == ()
        finally:
            release.set()
        assert first.result(timeout=5).status == Outcome.DELIVERY_SUPPRESSED
    assert len(lab.adapter.calls) == lab.broker.acquisitions == 1


def test_cached_result_is_reauthorized_and_never_cache_allow():
    lab = laboratory(cache_size=2)
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED
    assert len(lab.adapter.calls) == 1 and lab.broker.acquisitions == 1
    lab.change("principal_grants", "principal-grant-a", gates=frozenset({Gate.READ}))
    assert lab.execute().status == Outcome.DELIVERY_SUPPRESSED
    lab.change("principal_grants", "principal-grant-a", enabled=False)
    before = len(lab.adapter.calls)
    assert lab.execute().status == Outcome.DENY and len(lab.adapter.calls) == before


def test_decision_replay_and_forgery_rejected(lab):
    seen = []
    acquire = lab.broker.acquire
    def capture(decision):
        seen.append(decision)
        return acquire(decision)
    lab.broker.acquire = capture
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED
    count = lab.broker.attempts
    for decision in (None, {}, seen[0], replace(seen[0]), replace(seen[0], request=lab.request("b"))):
        with pytest.raises(ConnectorFailure, match=Reason.REPLAY.value):
            acquire(decision)
    forged_use = SyntheticCredentialUse(seen[0])
    with pytest.raises(ConnectorFailure, match=Reason.REPLAY.value):
        lab.adapter.read(forged_use, 0)
    assert lab.broker.attempts == count and len(lab.adapter.calls) == 1


def test_policy_change_failure_is_atomic_and_snapshot_is_immutable(lab):
    snapshot = lab.store.snapshot()
    lab.audit.fail_phases.add(Phase.CHANGE)
    with pytest.raises(ConnectorFailure):
        lab.change("principal_grants", "principal-grant-a", enabled=False)
    assert lab.store.snapshot() is snapshot
    with pytest.raises(FrozenInstanceError):
        snapshot.revision = 99
    with pytest.raises(FrozenInstanceError):
        snapshot.principal_grants[0].enabled = False
    with pytest.raises(ValueError, match="invalid registered identifier"):
        lab.change("instances", "instance-a", organization_id=None)
    assert all(e.phase != Phase.CHANGE for e in lab.audit.events)


def test_cached_delivery_has_finite_expiry_and_org_partition():
    lab = laboratory(cache_size=2)
    assert lab.execute().documents[0].organization_id == "ORG-A"
    assert lab.execute("b").documents[0].organization_id == "ORG-B"
    assert lab.execute().documents[0].organization_id == "ORG-A"
    assert len(lab.adapter.calls) == 2
    lab.clock.advance(5)
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED
    assert len(lab.adapter.calls) == 3


def test_cached_result_rechecks_simulated_external_permission():
    lab = laboratory(cache_size=2)
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED
    lab.adapter.set_permission(("ORG-A", "instance-a", "vacation-a"), False)
    result = lab.execute()
    assert result.status == Outcome.EXTERNAL_DENIED and result.documents == ()
    assert lab.broker.acquisitions == len(lab.adapter.calls) == 1


def test_cache_does_not_require_an_unrelated_metadata_operation():
    lab = laboratory(cache_size=2)
    lab.change("principal_grants", "principal-grant-a", operations=frozenset({Op.READ}))
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED
    assert len(lab.adapter.calls) == 1


def test_cached_listing_rechecks_each_child_external_permission():
    lab = laboratory(cache_size=2)
    assert lab.execute(resource="root-a", operation=Op.CHILDREN).status == Outcome.DELIVERY_ALLOWED
    lab.adapter.set_permission(("ORG-A", "instance-a", "vacation-a"), False)
    result = lab.execute(resource="root-a", operation=Op.CHILDREN)
    assert result.status == Outcome.EXTERNAL_DENIED and result.documents == ()
    assert len(lab.adapter.calls) == 1


def test_c_d_disabled_even_if_configuration_attempts_to_grant_them(lab):
    lab.change("principal_grants", "principal-grant-a", gates=frozenset(Gate))
    for gate in (Gate.AI_PROCESS, Gate.INDEX):
        assert_no_effects(lab, lab.service.execute(lab.a, lab.request(), gate=gate))


@pytest.mark.parametrize("version", [True, "1", None])
def test_revision_is_a_canonical_integer(lab, version):
    assert_no_effects(lab, lab.execute(policy_version=version))


def test_read_does_not_imply_folder_content_or_document_enumeration(lab):
    assert_no_effects(lab, lab.execute(resource="root-a"))
    assert_no_effects(lab, lab.execute(operation=Op.CHILDREN))


@pytest.mark.parametrize("phase", [Phase.EXTERNAL, Phase.DELIVERY])
def test_revocation_after_external_audit_before_delivery(lab, phase):
    append = lab.audit.append
    def withdraw_after_result(event):
        append(event)
        if event.phase == phase and event.outcome in {Outcome.EXTERNAL_SUCCESS, Outcome.DELIVERY_ALLOWED}:
            lab.change("principal_grants", "principal-grant-a", enabled=False)
    lab.audit.append = withdraw_after_result
    result = lab.execute()
    assert result.status == Outcome.DELIVERY_SUPPRESSED and result.documents == ()
    assert result.external_status == Outcome.EXTERNAL_SUCCESS
    assert lab.audit.events[-1].outcome == Outcome.DELIVERY_SUPPRESSED
    if phase == Phase.EXTERNAL:
        assert not any(e.outcome == Outcome.DELIVERY_ALLOWED for e in lab.audit.events)


def test_stale_issued_decision_is_rejected_before_acquisition(lab):
    decision = ConnectorAccessDecision("decision", "correlation", lab.a, lab.request(),
                                       lab.store.snapshot().revision, lab.a.expires_at, Gate.READ)
    lab.ledger.issue(decision)
    lab.change("principal_grants", "principal-grant-a", enabled=False)
    with pytest.raises(ConnectorFailure, match=Reason.STALE.value):
        lab.broker.acquire(decision)
    assert lab.broker.attempts == lab.broker.acquisitions == 0


def test_snapshot_compare_and_swap_rejects_lost_update(lab):
    old = lab.store.snapshot()
    lab.change("principal_grants", "principal-grant-a", enabled=False)
    with pytest.raises(ConnectorFailure, match=Reason.STALE.value):
        lab.store.replace_rows("principal_grants", old.principal_grants, expected_revision=old.revision)
    assert lab.execute().status == Outcome.DENY


def test_missing_external_document_is_not_local_resource_discovery(lab):
    lab.adapter.set_pages("vacation-a", ())
    result = lab.execute()
    assert result.reason == Reason.MISSING and result.status == Outcome.EXTERNAL_DENIED
    assert lab.broker.acquisitions == len(lab.adapter.calls) == 1


def test_subtree_cycle_and_cross_org_parent_fail_closed(lab):
    lab.change("resources", "vacation-a", parent_id="vacation-a")
    assert_no_effects(lab, lab.execute())
    lab.change("resources", "vacation-a", parent_id="root-b")
    assert_no_effects(lab, lab.execute())


@pytest.mark.parametrize("parent_id", ["root-a", "root-b", "missing-parent"])
@pytest.mark.parametrize("resource_id,operation", [("vacation-a", Op.READ), ("root-a", Op.METADATA)])
def test_scope_root_does_not_hide_invalid_ancestry(lab, parent_id, resource_id, operation):
    lab.change("resources", "root-a", parent_id=parent_id)
    assert_no_effects(lab, lab.execute(resource=resource_id, operation=operation))


@pytest.mark.parametrize("point", ["before_read", "after_read", "after_delivery_audit"])
def test_fresh_delivery_rechecks_each_child_external_permission(lab, point):
    def revoke():
        lab.adapter.set_permission(("ORG-A", "instance-a", "vacation-a"), False)
    if point == "before_read":
        revoke()
    elif point == "after_read":
        lab.adapter.on_read = lambda *_: revoke()
    else:
        append = lab.audit.append
        def withdraw(event):
            append(event)
            if event.phase == Phase.DELIVERY and event.outcome == Outcome.DELIVERY_ALLOWED:
                revoke()
        lab.audit.append = withdraw
    result = lab.execute(resource="root-a", operation=Op.CHILDREN)
    assert result.status == Outcome.EXTERNAL_DENIED and result.documents == ()
    assert lab.broker.acquisitions == len(lab.adapter.calls) == 1


def test_cached_delivery_rechecks_external_permission_after_delivery_audit():
    lab = laboratory(cache_size=2)
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED
    append = lab.audit.append
    def withdraw(event):
        append(event)
        if event.phase == Phase.DELIVERY and event.outcome == Outcome.DELIVERY_ALLOWED:
            lab.adapter.set_permission(("ORG-A", "instance-a", "vacation-a"), False)
    lab.audit.append = withdraw
    result = lab.execute()
    assert result.status == Outcome.EXTERNAL_DENIED and result.documents == ()
    assert lab.broker.acquisitions == len(lab.adapter.calls) == 1


def test_duplicate_policy_resource_fails_closed(lab):
    snapshot = lab.store.snapshot()
    lab.store.replace_rows("resources", snapshot.resources + (snapshot.resources[1],), expected_revision=snapshot.revision)
    assert_no_effects(lab, lab.execute())


def test_invalid_execution_limits_fail_before_broker(lab):
    limits = replace(lab.store.snapshot().definitions[0].limits, max_pages=0)
    lab.change("definitions", "synthetic-reader", limits=limits)
    assert_no_effects(lab, lab.execute())


def test_concurrent_budget_denies_second_read_without_another_acquisition(lab):
    limits = replace(lab.store.snapshot().definitions[0].limits, max_concurrent=1)
    lab.change("definitions", "synthetic-reader", limits=limits)
    started, release = Event(), Event()
    def controlled_read(*_):
        started.set()
        assert release.wait(5)
    lab.adapter.on_read = controlled_read
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(lab.execute)
        try:
            assert started.wait(5)
            second = executor.submit(lab.execute).result(timeout=5)
            assert second.status == Outcome.DENY and second.reason == Reason.LIMIT
            assert lab.broker.attempts == len(lab.adapter.calls) == 1
        finally:
            release.set()
        assert first.result(timeout=5).status == Outcome.DELIVERY_ALLOWED
    assert lab.service._active == {}


def test_new_package_has_no_network_llm_http_routes_or_production_imports():
    package = Path(__file__).resolve().parents[1] / "app/enterprise_connectors"
    allowed = {"__future__", "dataclasses", "datetime", "enum", "typing", "threading", "uuid", "re"}
    persistence_imports = {
        "control_types.py": {"json"},
        "sqlite_store.py": {"contextlib", "contextvars", "functools", "hashlib", "pathlib", "sqlite3"},
        "control_plane.py": {"contextlib", "hashlib", "sqlite3"},
        "durable_audit.py": {"sqlite3"},
    }
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        file_allowed = allowed | persistence_imports.get(path.name, set())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] in file_allowed for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                assert node.module.split(".")[0] in file_allowed
            elif isinstance(node, ast.Call):
                assert not isinstance(node.func, ast.Name) or node.func.id not in {"open", "eval", "exec", "__import__"}
