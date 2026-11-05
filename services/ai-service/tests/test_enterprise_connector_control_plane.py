"""Offline SQLite lifecycle, atomic audit and independent-store revocation."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import os
import socket
import sqlite3
from threading import Barrier, Event

import pytest

from app.enterprise_connectors.control_plane import ControlPlane
from app.enterprise_connectors.control_types import CredentialMetadata, CredentialState as CS, InstanceState as IS
from app.enterprise_connectors.models import ConnectorFailure, Gate, Outcome, Phase, Reason
from app.enterprise_connectors.synthetic import SyntheticPage
from app.enterprise_connectors.sqlite_store import SQLitePolicyStore
from tests.enterprise_connector_control_plane_fixture import persistent_laboratory


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Network forbidden in control-plane tests")
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    yield
    assert attempts == []


@pytest.fixture
def lab(tmp_path):
    return persistent_laboratory(tmp_path)


def read(lab, *, suffix="a", reader=None, request=None):
    reader = lab.reader() if reader is None else reader
    result = reader[0].execute(lab.context(suffix), lab.request(suffix) if request is None else request)
    return result, reader


def test_onboard_active_reader_and_durable_separate_audits(lab):
    result, (_, broker, adapter, _) = read(lab)
    assert result.status == Outcome.DELIVERY_ALLOWED
    assert broker.acquisitions == len(adapter.calls) == 1
    assert [e["phase"] for e in lab.control.audit_events(lab.admin_a, "access")] == [
        "local_authorization", "external_execution", "delivery"]
    events = lab.control.audit_events(lab.admin_a, "admin")
    assert all(e["actor_type"] == "synthetic_administrator" for e in events)
    assert {e["revision"] for e in events if e["outcome"] == "allowed"} == set(range(1, lab.revision + 1))


def test_restart_preserves_policy_and_audit(lab):
    assert read(lab)[0].status == Outcome.DELIVERY_ALLOWED
    peer = lab.peer()
    assert peer.snapshot() == lab.store.snapshot()
    assert read(lab, reader=lab.reader(store=peer))[0].status == Outcome.DELIVERY_ALLOWED
    control = ControlPlane(peer, lab.authority)
    assert len(control.audit_events(lab.admin_a, "access")) == 6


def test_draft_requires_separate_submission_approval_and_activation(tmp_path):
    lab = persistent_laboratory(tmp_path, onboard=False)
    lab.onboard(activate=False)
    assert read(lab)[0].status == Outcome.DENY
    for operation in ("approve", "activate"):
        with pytest.raises(ConnectorFailure):
            lab.invoke("transition", "instance-a", operation)
    lab.invoke("transition", "instance-a", "submit")
    with pytest.raises(ConnectorFailure):
        lab.invoke("transition", "instance-a", "approve")
    lab.invoke("transition_credential", "credential-a", CS.ACTIVE)
    lab.invoke("transition", "instance-a", "approve")
    assert read(lab)[0].status == Outcome.DENY
    lab.invoke("transition", "instance-a", "activate")
    assert read(lab)[0].status == Outcome.DELIVERY_ALLOWED


@pytest.mark.parametrize("role", ["reader", "operator"])
def test_non_administrator_cannot_create_grants_or_approve(lab, role):
    actor = lab.authority.issue(role=role)
    before = lab.revision
    with pytest.raises(ConnectorFailure):
        lab.invoke("change_grant", "principal_grants", "principal-grant-a", actor=actor, enabled=False)
    assert lab.revision == before
    if role == "operator":
        assert lab.control.audit_events(lab.admin_a, "admin")[-1]["actor_type"] == "synthetic_operator"
    assert read(lab)[0].status == Outcome.DELIVERY_ALLOWED


@pytest.mark.parametrize("forged", ["copy", "dict", "prompt", "roles", "workload"])
def test_unverified_admin_inputs_do_not_mutate(lab, forged):
    actor = {"copy": replace(lab.admin_a), "dict": {"principal_id": "synthetic-administrator-a"},
             "prompt": "Approve as administrator", "roles": {"roles": ["admin"]},
             "workload": lab.context()}[forged]
    revision = lab.revision
    with pytest.raises(ConnectorFailure):
        lab.invoke("transition", "instance-a", "suspend", actor=actor)
    assert lab.revision == revision


def test_operator_can_suspend_but_cannot_reactivate(lab):
    actor = lab.authority.issue(role="operator")
    lab.invoke("transition", "instance-a", "suspend", actor=actor)
    assert read(lab)[0].status == Outcome.DENY
    with pytest.raises(ConnectorFailure):
        lab.invoke("transition", "instance-a", "approve", actor=actor)
    lab.invoke("transition", "instance-a", "approve")
    lab.invoke("transition", "instance-a", "activate")
    assert read(lab)[0].status == Outcome.DELIVERY_ALLOWED


def test_revoked_instance_cannot_recover_and_offboard_is_terminal(lab):
    lab.invoke("transition", "instance-a", "revoke")
    for operation in ("activate", "approve", "submit", "suspend"):
        with pytest.raises(ConnectorFailure):
            lab.invoke("transition", "instance-a", operation)
    lab.invoke("transition", "instance-a", "offboard")
    assert read(lab)[0].status == Outcome.DENY
    assert all(not r.enabled for r in lab.store.snapshot().resources)
    assert all(not g.enabled for g in lab.store.snapshot().principal_grants)
    with pytest.raises(ConnectorFailure):
        lab.invoke("change_grant", "principal_grants", "principal-grant-a", enabled=True)


def test_org_a_cannot_read_or_mutate_org_b(lab):
    lab.onboard("b")
    before = lab.revision
    with pytest.raises(ConnectorFailure):
        lab.invoke("transition", "instance-b", "suspend")
    assert lab.revision == before
    assert "principal-grant-b" not in repr(lab.control.metadata(lab.admin_a, "principal_grants"))
    for suffix in ("a", "b"):
        assert read(lab, suffix=suffix)[0].documents[0].organization_id == "ORG-" + suffix.upper()
    service, broker, adapter, _ = lab.reader()
    assert service.execute(lab.context(), lab.request("b")).status == Outcome.DENY
    assert broker.attempts == 0 and adapter.calls == ()


def test_revocation_restore_and_independent_store_snapshot(lab):
    peer = lab.peer()
    service = lab.reader(store=peer)
    stale = lab.request()
    lab.invoke("change_grant", "principal_grants", "principal-grant-a", enabled=False)
    assert read(lab, reader=service)[0].status == Outcome.DENY
    assert read(lab, reader=service, request=stale)[0].reason == Reason.STALE
    lab.invoke("change_grant", "principal_grants", "principal-grant-a", enabled=True)
    assert read(lab, reader=service)[0].status == Outcome.DELIVERY_ALLOWED


@pytest.mark.parametrize("stage", ["after_entity_write", "before_admin_audit", "before_commit"])
def test_admin_change_and_event_rollback_together(lab, stage):
    before = lab.store.snapshot()
    events = lab.control.audit_events(lab.admin_a, "admin")
    def fail(candidate):
        if candidate == stage:
            raise ConnectorFailure(Reason.AUDIT, unavailable=True)
    lab.store.fault = fail
    with pytest.raises(ConnectorFailure):
        lab.invoke("change_grant", "principal_grants", "principal-grant-a", enabled=False)
    lab.store.fault = lambda *_: None
    assert lab.store.snapshot() == before
    assert lab.control.audit_events(lab.admin_a, "admin") == events


@pytest.mark.parametrize("phase,attempts", [(Phase.AUTHORIZATION, 0), (Phase.EXTERNAL, 1), (Phase.DELIVERY, 1)])
def test_durable_access_audit_is_fail_closed(lab, phase, attempts):
    service, broker, adapter, audit = lab.reader()
    audit.fail_phases.add(phase)
    result, _ = read(lab, reader=(service, broker, adapter, audit))
    assert result.status == Outcome.UNAVAILABLE and result.documents == ()
    assert broker.attempts == len(adapter.calls) == attempts
    assert not any(e["phase"] == phase.value for e in lab.control.audit_events(lab.admin_a, "access"))


def test_credential_suspend_restore_revoke_and_no_automatic_recovery(lab):
    lab.invoke("transition_credential", "credential-a", CS.SUSPENDED)
    assert read(lab)[0].status == Outcome.DENY
    lab.invoke("transition_credential", "credential-a", CS.ACTIVE)
    assert read(lab)[0].status == Outcome.DELIVERY_ALLOWED
    lab.invoke("transition_credential", "credential-a", CS.REVOKED)
    assert read(lab)[0].status == Outcome.DENY
    with pytest.raises(ConnectorFailure):
        lab.invoke("transition_credential", "credential-a", CS.ACTIVE)


def test_synthetic_rotation_retires_old_reference(lab):
    old = lab.store.snapshot().credentials[0]
    new = CredentialMetadata(replace(old, reference_id="credential-new", version=1), "binding-a",
                             "synthetic-custody.new", lab.clock() + timedelta(minutes=10))
    lab.invoke("rotate", "credential-a", new)
    refs = {r.reference_id: r for r in lab.store.snapshot().credentials}
    assert not refs["credential-a"].enabled and refs["credential-new"].enabled
    assert refs["credential-new"].version > old.version
    event = lab.control.audit_events(lab.admin_a, "admin")[-1]
    assert (event["related_entity_id"], event["entity_id"]) == ("credential-a", "credential-new")
    assert read(lab)[0].status == Outcome.DELIVERY_ALLOWED
    with pytest.raises(ConnectorFailure):
        lab.invoke("transition_credential", "credential-a", CS.ACTIVE)


@pytest.mark.parametrize("field,value", [("tenant_id", "foreign"), ("client_id", "foreign"),
                                         ("organization_id", "ORG-B"), ("mode", "delegated")])
def test_rotation_cannot_change_credential_scope(lab, field, value):
    old = lab.store.snapshot().credentials[0]
    metadata = CredentialMetadata(replace(old, reference_id="replacement", **{field: value}), "binding-a",
                                   "synthetic-custody.replacement", lab.clock() + timedelta(minutes=10))
    revision = lab.revision
    with pytest.raises(ConnectorFailure):
        lab.invoke("rotate", "credential-a", metadata)
    assert lab.revision == revision and read(lab)[0].status == Outcome.DELIVERY_ALLOWED


def test_stale_admin_revision_and_two_concurrent_admins(lab):
    revision = lab.revision
    peer = ControlPlane(lab.peer(), lab.authority)
    barrier = Barrier(2)
    def mutate(control):
        barrier.wait(timeout=5)
        try:
            return control.change_grant(lab.admin_a, "principal_grants", "principal-grant-a", enabled=False, expected_revision=revision)
        except ConnectorFailure as failure:
            return failure
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(mutate, (lab.control, peer)))
    assert sum(isinstance(r, dict) for r in results) == 1
    assert lab.revision == revision + 1
    with pytest.raises(ConnectorFailure, match=Reason.STALE.value):
        lab.control.change_grant(lab.admin_a, "principal_grants", "principal-grant-a", enabled=True, expected_revision=revision)


@pytest.mark.parametrize("change", ["revoke", "suspend", "offboard", "rotate"])
def test_in_flight_change_from_independent_store_suppresses_delivery(lab, change):
    peer = ControlPlane(lab.peer(), lab.authority)
    service, broker, adapter, audit = lab.reader()
    def mutate(*_):
        revision = lab.revision
        if change == "revoke":
            peer.change_grant(lab.admin_a, "principal_grants", "principal-grant-a", enabled=False, expected_revision=revision)
        elif change == "suspend":
            peer.transition(lab.admin_a, "instance-a", "suspend", expected_revision=revision)
        elif change == "offboard":
            result = peer.transition(lab.admin_a, "instance-a", "revoke", expected_revision=revision)
            peer.transition(lab.admin_a, "instance-a", "offboard", expected_revision=result["revision"])
        else:
            old = lab.store.snapshot().credentials[0]
            metadata = CredentialMetadata(replace(old, reference_id="rotated"), "binding-a", "synthetic-custody.rotated",
                                           lab.clock() + timedelta(minutes=10))
            peer.rotate(lab.admin_a, "credential-a", metadata, expected_revision=revision)
    adapter.on_read = mutate
    result, _ = read(lab, reader=(service, broker, adapter, audit))
    assert result.status == Outcome.DELIVERY_SUPPRESSED and result.documents == ()
    assert len(adapter.calls) == 1


def test_new_reader_after_confirmed_revocation_never_acquires(lab):
    started, release = Event(), Event()
    first = lab.reader()
    def pause(*_):
        started.set()
        assert release.wait(5)
    first[2].on_read = pause
    with ThreadPoolExecutor(max_workers=1) as executor:
        running = executor.submit(read, lab, reader=first)
        try:
            assert started.wait(5)
            control = ControlPlane(lab.peer(), lab.authority)
            control.change_grant(lab.admin_a, "principal_grants", "principal-grant-a", enabled=False, expected_revision=lab.revision)
            result, second = read(lab)
            assert result.status == Outcome.DENY and second[1].attempts == 0
        finally:
            release.set()
        assert running.result(timeout=5)[0].documents == ()


def test_cache_reauthorizes_after_durable_revocation(lab):
    reader = lab.reader(cache_size=2)
    assert read(lab, reader=reader)[0].status == Outcome.DELIVERY_ALLOWED
    assert read(lab, reader=reader)[0].status == Outcome.DELIVERY_ALLOWED
    assert len(reader[2].calls) == 1
    lab.invoke("change_grant", "principal_grants", "principal-grant-a", enabled=False)
    assert read(lab, reader=reader)[0].status == Outcome.DENY
    assert len(reader[2].calls) == 1


@pytest.mark.parametrize("damage", ["schema", "version", "application", "audit_gap", "foreign_table", "missing_metadata"])
def test_incompatible_or_corrupt_store_never_falls_back(lab, damage):
    reader = lab.reader()
    commands = {"schema": "DROP TABLE eca_access_audit", "version": "PRAGMA user_version=99",
                "application": "PRAGMA application_id=0", "audit_gap": "DELETE FROM eca_admin_audit WHERE revision=1",
                "foreign_table": "CREATE TABLE other_store(id TEXT)", "missing_metadata": "DELETE FROM eca_metadata"}
    with closing(sqlite3.connect(lab.store.path)) as connection:
        connection.execute(commands[damage])
        connection.commit()
    result = reader[0].execute(lab.context(), reader_request_before_damage(reader, lab))
    assert result.status == Outcome.UNAVAILABLE and result.documents == ()
    assert reader[1].attempts == 0


def reader_request_before_damage(reader, lab):
    from app.enterprise_connectors.models import OperationRequest, ConnectorOperation
    return OperationRequest("instance-a", "vacation-a", ConnectorOperation.READ, "synthetic-demonstration", "recipient-a", reader[0]._cache_revision)


def test_missing_database_explicit_initialization_and_no_overwrite(tmp_path):
    lab = persistent_laboratory(tmp_path)
    with pytest.raises(ConnectorFailure):
        lab.control.initialize(lab.admin_a)
    missing = SQLitePolicyStore(tmp_path / "absent.sqlite3", test_owned_root=tmp_path, clock=lab.clock)
    with pytest.raises(ConnectorFailure):
        missing.snapshot()
    assert not missing.path.exists()


def test_paths_reject_relative_foreign_alias_and_sidecars(lab):
    for path in ("relative.sqlite3", lab.store.root / "other.sqlite3-wal", lab.store.root.parent / "other.sqlite3"):
        with pytest.raises(ConnectorFailure):
            SQLitePolicyStore(path, test_owned_root=lab.store.root, clock=lab.clock)
    with pytest.raises(ConnectorFailure):
        SQLitePolicyStore(lab.store.path, test_owned_root=lab.store.root, clock=lab.clock, forbidden_paths=(lab.store.path,))


def test_locked_database_fails_closed_before_acquisition(lab):
    reader = lab.reader()
    request = lab.request()
    with closing(sqlite3.connect(lab.store.path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            result = reader[0].execute(lab.context(), request)
            assert result.status == Outcome.UNAVAILABLE and reader[1].attempts == 0
        finally:
            connection.rollback()


def test_metadata_and_audit_contain_no_documents_contexts_or_secrets(lab):
    result, _ = read(lab)
    content = result.documents[0].text
    events = repr(lab.control.audit_events(lab.admin_a, "admin")) + repr(lab.control.audit_events(lab.admin_a, "access"))
    assert content not in events and "CredentialReference" not in events
    assert "external_subject" not in events and "Authorization" not in events
    assert "payload" not in events


def test_declined_admin_is_anonymous_without_attacker_text(lab):
    marker = "unverified-attacker-marker"
    with pytest.raises(ConnectorFailure):
        lab.invoke("transition", marker, "suspend", actor={"actor_id": marker, "roles": ["admin"]})
    with lab.store.connection() as connection:
        actor_type, actor_id, organization, entity_id = connection.execute(
            "SELECT actor_type,actor_id,organization_id,entity_id FROM eca_admin_audit WHERE outcome='denied' ORDER BY rowid DESC LIMIT 1").fetchone()
    assert (actor_type, actor_id, organization, entity_id) == ("anonymous", None, None, None)


def test_expired_administrator_cannot_mutate(lab):
    lab.clock.advance(3600)
    with pytest.raises(ConnectorFailure):
        lab.control.transition(lab.admin_a, "instance-a", "suspend", expected_revision=lab.revision)


@pytest.mark.parametrize("replacement", ["org", "resource", "mode", "principal", "operation", "gate"])
def test_grant_modification_cannot_substitute_scope_or_add_unapproved_capability(lab, replacement):
    from app.enterprise_connectors.models import ConnectorOperation
    original = lab.store.snapshot().principal_grants[0]
    changes = {"version": original.version + 1}
    changes.update({"org": {"organization_id": "ORG-B"}, "resource": {"resource_id": "outside-a"},
                    "mode": {"mode": "delegated"}, "principal": {"principal_id": "principal-b"},
                    "operation": {"operations": frozenset({ConnectorOperation.INDEX})},
                    "gate": {"gates": frozenset({Gate.INDEX})}}[replacement])
    before = lab.store.snapshot()
    with pytest.raises(ConnectorFailure):
        lab.invoke("change_grant", "principal_grants", original.grant_id, replacement=replace(original, **changes))
    assert lab.store.snapshot() == before


def test_grant_restriction_and_restore_are_explicit(lab):
    from app.enterprise_connectors.models import ConnectorOperation
    original = lab.store.snapshot().principal_grants[0]
    restricted = replace(original, operations=frozenset({ConnectorOperation.METADATA}), version=original.version + 1)
    lab.invoke("change_grant", "principal_grants", original.grant_id, replacement=restricted)
    assert read(lab)[0].status == Outcome.DENY
    # Expanding an existing grant is refused; a new reviewed grant is explicit onboarding.
    with pytest.raises(ConnectorFailure):
        lab.invoke("change_grant", "principal_grants", original.grant_id,
                   replacement=replace(original, version=restricted.version + 1))


def test_approval_is_invalidated_by_pre_activation_configuration_change(tmp_path):
    lab = persistent_laboratory(tmp_path, onboard=False)
    lab.onboard(activate=False)
    lab.invoke("transition_credential", "credential-a", CS.ACTIVE)
    lab.invoke("transition", "instance-a", "submit")
    lab.invoke("transition", "instance-a", "approve")
    lab.invoke("change_grant", "principal_grants", "principal-grant-a", enabled=False)
    with pytest.raises(ConnectorFailure):
        lab.invoke("transition", "instance-a", "activate")


def test_missing_binding_or_grants_cannot_be_approved(tmp_path):
    lab = persistent_laboratory(tmp_path, onboard=False)
    definition = replace(lab.source.store.snapshot().definitions[0], definition_id="minimal")
    lab.invoke("register", "definitions", definition)
    lab.invoke("create_instance", "incomplete", definition.definition_id)
    lab.invoke("transition", "incomplete", "submit")
    before = lab.revision
    with pytest.raises(ConnectorFailure):
        lab.invoke("transition", "incomplete", "approve")
    assert lab.revision == before


def test_reference_expiry_and_review_due_are_fail_closed(lab):
    old = lab.store.snapshot().credentials[0]
    metadata = CredentialMetadata(replace(old, reference_id="short-lived", expires_at=lab.clock() + timedelta(seconds=10)),
                                   "binding-a", "synthetic-custody.short", lab.clock() + timedelta(seconds=5))
    lab.invoke("rotate", "credential-a", metadata)
    lab.clock.advance(5)
    result, reader = read(lab)
    assert result.status == Outcome.DENY and reader[1].attempts == 0
    lab.invoke("transition_credential", "short-lived", CS.EXPIRED)
    with pytest.raises(ConnectorFailure):
        lab.invoke("transition_credential", "short-lived", CS.ACTIVE)


def test_rotation_during_acquisition_stops_old_reference_before_read(lab):
    peer = ControlPlane(lab.peer(), lab.authority)
    reader = lab.reader()
    old = lab.store.snapshot().credentials[0]
    metadata = CredentialMetadata(replace(old, reference_id="rotated-during-acquisition"), "binding-a",
                                   "synthetic-custody.acquire", lab.clock() + timedelta(minutes=10))
    reader[1].on_acquire = lambda: peer.rotate(lab.admin_a, old.reference_id, metadata, expected_revision=lab.revision)
    result, _ = read(lab, reader=reader)
    assert result.documents == () and result.status == Outcome.DELIVERY_SUPPRESSED
    assert reader[2].calls == ()
    assert read(lab)[0].status == Outcome.DELIVERY_ALLOWED


def test_suspension_during_pagination_stops_continuation(lab):
    reader = lab.reader()
    reader[2].set_pages("vacation-a", (SyntheticPage("one", next_cursor=1), SyntheticPage("two")))
    peer = ControlPlane(lab.peer(), lab.authority)
    reader[2].on_read = lambda *_: peer.transition(lab.admin_a, "instance-a", "suspend", expected_revision=lab.revision)
    result, _ = read(lab, reader=reader)
    assert result.documents == () and len(reader[2].calls) == 1


def test_final_delivery_transaction_orders_independent_writers(lab):
    peer = ControlPlane(lab.peer(), lab.authority)
    revision = lab.revision
    with lab.store.delivery_guard():
        with pytest.raises(ConnectorFailure) as error:
            peer.change_grant(lab.admin_a, "principal_grants", "principal-grant-a", enabled=False, expected_revision=revision)
        assert error.value.unavailable
        assert lab.store.snapshot().revision == revision
    peer.change_grant(lab.admin_a, "principal_grants", "principal-grant-a", enabled=False, expected_revision=revision)
    assert read(lab)[0].status == Outcome.DENY


def test_administration_cannot_report_commit_inside_data_plane_transaction(lab):
    revision = lab.revision
    with lab.store.delivery_guard():
        with pytest.raises(ConnectorFailure) as error:
            lab.control.change_grant(lab.admin_a, "principal_grants", "principal-grant-a", enabled=False, expected_revision=revision)
        assert error.value.unavailable
    assert lab.revision == revision


def test_migration_absent_or_checksum_incompatible_is_unavailable(lab, monkeypatch, tmp_path):
    import app.enterprise_connectors.sqlite_store as storage
    reader = lab.reader()
    request = lab.request()
    monkeypatch.setattr(storage, "MIGRATION", tmp_path / "absent-migration.sql")
    result = reader[0].execute(lab.context(), request)
    assert result.status == Outcome.UNAVAILABLE and reader[1].attempts == 0


def test_foreign_database_is_not_adopted(tmp_path):
    from tests.enterprise_connector_fixture import Clock
    path = tmp_path / "foreign.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE clinical_store(id TEXT)")
        connection.commit()
    before = path.read_bytes()
    store = SQLitePolicyStore(path, test_owned_root=tmp_path, clock=Clock())
    with pytest.raises(ConnectorFailure):
        store.snapshot()
    assert path.read_bytes() == before


def test_hard_linked_store_is_rejected(lab):
    alias = lab.store.root / "alias.sqlite3"
    os.link(lab.store.path, alias)
    with pytest.raises(ConnectorFailure):
        lab.store.snapshot()


def test_symlinked_store_is_rejected_when_supported(lab):
    alias = lab.store.root / "alias.sqlite3"
    try:
        alias.symlink_to(lab.store.path)
    except OSError:
        pytest.skip("Local OS does not permit synthetic symlink creation; no ACL changed")
    with pytest.raises(ConnectorFailure):
        SQLitePolicyStore(alias, test_owned_root=lab.store.root, clock=lab.clock)


def test_connection_budget_is_bounded(lab):
    for _ in range(4):
        assert lab.store._connections.acquire(blocking=False)
    try:
        with pytest.raises(ConnectorFailure):
            lab.store.snapshot()
    finally:
        for _ in range(4):
            lab.store._connections.release()


def test_c_d_remain_disabled_with_sqlite(lab):
    reader = lab.reader()
    for gate in (Gate.AI_PROCESS, Gate.INDEX):
        result = reader[0].execute(lab.context(), lab.request(), gate=gate)
        assert result.status == Outcome.DENY and result.documents == ()
    assert reader[1].attempts == 0 and reader[2].calls == ()


def test_sqlite_never_stores_document_content(lab):
    result, _ = read(lab)
    content = result.documents[0].text.encode("utf-8")
    assert content not in lab.store.path.read_bytes()
    wal = Path(str(lab.store.path) + "-wal")
    if wal.exists():
        assert content not in wal.read_bytes()


def test_final_transaction_commit_failure_suppresses_content_and_rolls_back_event(lab):
    reader = lab.reader()
    append = reader[3].append
    def fail_commit(stage):
        if stage == "before_commit":
            raise ConnectorFailure(Reason.AUDIT, unavailable=True)
    def arm_failure(event):
        append(event)
        if event.phase == Phase.DELIVERY:
            lab.store.fault = fail_commit
    reader[3].append = arm_failure
    result, _ = read(lab, reader=reader)
    lab.store.fault = lambda *_: None
    assert result.status == Outcome.UNAVAILABLE and result.documents == ()
    assert reader[1].acquisitions == len(reader[2].calls) == 1
    assert [e["phase"] for e in lab.control.audit_events(lab.admin_a, "access")] == ["local_authorization", "external_execution"]


def test_symlink_rejection_branch_does_not_require_os_privileges(lab, monkeypatch):
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == lab.store.path or original(path))
    with pytest.raises(ConnectorFailure):
        lab.store.snapshot()


def test_snapshot_is_consistent_and_does_not_merge_grants_across_revisions(lab):
    old = lab.store.snapshot()
    lab.invoke("change_grant", "principal_grants", "principal-grant-a", enabled=False)
    fresh = lab.peer().snapshot()
    assert old.principal_grants[0].enabled and not fresh.principal_grants[0].enabled
    assert old.revision + 1 == fresh.revision
    assert read(lab)[0].status == Outcome.DENY


def test_sql_constraints_reject_cross_org_foreign_key(lab):
    lab.onboard("b")
    with lab.store.connection(write=True) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE eca_resource SET parent_id='root-b' WHERE resource_id='vacation-a'")


def test_db_payload_scope_corruption_never_becomes_permission(lab):
    reader = lab.reader()
    request = lab.request()
    with closing(sqlite3.connect(lab.store.path)) as connection:
        connection.execute("UPDATE eca_resource SET payload=json_set(payload,'$.organization_id','ORG-B') WHERE resource_id='vacation-a'")
        connection.commit()
    result = reader[0].execute(lab.context(), request)
    assert result.status == Outcome.UNAVAILABLE and result.documents == ()
    assert reader[1].attempts == 0


def test_shared_tenant_and_identical_external_ids_do_not_merge_organizations(tmp_path):
    lab = persistent_laboratory(tmp_path, onboard=False)
    for table in ("bindings", "resources", "credentials"):
        snapshot = lab.source.store.snapshot()
        rows = tuple(replace(row, tenant_id="shared-tenant") for row in getattr(snapshot, table))
        lab.source.store.replace_rows(table, rows, expected_revision=snapshot.revision)
    lab.onboard()
    lab.onboard("b")
    for suffix in ("a", "b"):
        result, _ = read(lab, suffix=suffix)
        assert result.status == Outcome.DELIVERY_ALLOWED
        assert result.documents[0].organization_id == "ORG-" + suffix.upper()
    reader = lab.reader()
    assert reader[0].execute(lab.context(), lab.request("b")).status == Outcome.DENY
    assert reader[1].attempts == 0


def test_active_binding_cannot_be_silently_replaced(lab):
    binding = lab.store.snapshot().bindings[0]
    before = lab.store.snapshot()
    for changed in (replace(binding, tenant_id="other-tenant"), replace(binding, mode="delegated")):
        with pytest.raises(ConnectorFailure):
            lab.invoke("register", "bindings", changed)
    assert lab.store.snapshot() == before


def test_new_migration_checksum_is_stable_across_line_endings(lab, monkeypatch, tmp_path):
    import app.enterprise_connectors.sqlite_store as storage
    sql = storage.MIGRATION.read_text(encoding="utf-8")
    expected = storage.migration_checksum()
    alternate = tmp_path / "same-migration-crlf.sql"
    alternate.write_bytes(sql.replace("\n", "\r\n").encode("utf-8"))
    monkeypatch.setattr(storage, "MIGRATION", alternate)
    assert storage.migration_checksum() == expected
    assert read(lab)[0].status == Outcome.DELIVERY_ALLOWED


@pytest.mark.parametrize("operation", ["rotate", "change_grant"])
def test_administrative_payload_subclasses_cannot_persist_extra_fields(lab, operation):
    from dataclasses import make_dataclass

    before = lab.store.snapshot()
    original = before.credentials[0] if operation == "rotate" else before.principal_grants[0]
    extended_type = make_dataclass("UnexpectedMetadata", [("unexpected_payload", str)],
                                   bases=(type(original),), frozen=True, slots=True, kw_only=True)
    marker = "synthetic-rejected-extra-field"
    values = {field: getattr(original, field) for field in original.__dataclass_fields__}
    if operation == "rotate":
        values["reference_id"] = "extended-reference"
    else:
        values["version"] += 1
    extended = extended_type(**values, unexpected_payload=marker)
    with pytest.raises(ConnectorFailure):
        if operation == "rotate":
            metadata = CredentialMetadata(extended, "binding-a", "synthetic-custody.extended",
                                            lab.clock() + timedelta(minutes=10))
            lab.invoke("rotate", original.reference_id, metadata)
        else:
            lab.invoke("change_grant", "principal_grants", original.grant_id, replacement=extended)
    assert lab.store.snapshot() == before
    with lab.store.connection() as connection:
        for table in ("eca_credential", "eca_principal_grant"):
            assert all(marker not in row[0] for row in connection.execute("SELECT payload FROM " + table))
    assert marker not in repr(lab.control.audit_events(lab.admin_a, "admin"))
    assert read(lab)[0].status == Outcome.DELIVERY_ALLOWED
