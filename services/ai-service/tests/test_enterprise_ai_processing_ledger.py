"""C02 transactional storage, fail-closed audit and recovery, isolated files only."""
from copy import copy
from dataclasses import replace
import sqlite3

import pytest

from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
from tests.enterprise_ai_processing_execution_fixture import execution_laboratory


@pytest.fixture
def lab(tmp_path):
    instance = execution_laboratory(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def rows(lab, table="aip_execution"):
    with sqlite3.connect(lab.ledger.path) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM " + table)]


@pytest.mark.parametrize("kind", ["copy", "forged", "auditor", "wrong_org", "expired"])
def test_admin_authority_is_not_structural_or_a_label(lab, kind):
    access = lab.admin["ORG-A"]
    if kind == "copy": access = copy(access)
    elif kind == "forged": access = replace(access)
    elif kind == "auditor": access = lab.issuer.issue(role="auditor")
    elif kind == "wrong_org": access = lab.admin["ORG-B"]
    else: access = lab.issuer.issue(expires_at=lab.clock())
    policy = lab.ledger.policy(lab.executor["ORG-A"])
    with pytest.raises(ExecutionError):
        lab.ledger.change_policy(access, replace(policy.grants[0], version=2), expected_revision=policy.revision,
                                 approval_ref="synthetic-exemption")
    assert lab.ledger.policy(lab.executor["ORG-A"]).revision == policy.revision


def test_revision_cas_and_admin_audit_are_one_commit(lab):
    before = lab.ledger.policy(lab.executor["ORG-A"])
    lab.ledger._fault = lambda stage: (_ for _ in ()).throw(OSError()) if stage == "change_before_commit" else None
    with pytest.raises(ExecutionError):
        lab.change_grant(enabled=False)
    lab.ledger._fault = lambda stage: None
    after = lab.ledger.policy(lab.executor["ORG-A"])
    assert after == before
    with pytest.raises(ExecutionError):
        lab.ledger.change_policy(lab.admin["ORG-A"], replace(before.grants[0], version=2),
                                 expected_revision=before.revision - 1, approval_ref="exemption")


@pytest.mark.parametrize("stage", ["T1_before_commit", "T1_after_commit", "audit_ai_processing_evaluated",
    "audit_ai_processing_profile_selected", "audit_ai_processing_budget_approved", "audit_ai_processing_authorized"])
def test_t1_audit_failures_never_create_execution_authority(lab, stage):
    def fail(current):
        if current == stage: raise OSError("synthetic storage failure")
    lab.ledger._fault = fail
    with pytest.raises(ExecutionError):
        lab.prepare()
    lab.ledger._fault = lambda stage: None
    assert not lab.gateway._owners
    executions = rows(lab)
    assert len(executions) == (1 if stage == "T1_after_commit" else 0)
    assert not any(e["event"] == "ai_provider_invocation_observed" for e in rows(lab, "aip_audit"))


@pytest.mark.parametrize("stage", ["T2_before_commit", "T2_after_commit", "T3_before_commit", "T3_after_commit",
    "audit_ai_provider_invocation_observed", "T4_before_commit", "T4_after_commit", "audit_ai_provider_result_observed"])
def test_execution_storage_failure_preserves_last_fact_no_replay(lab, stage):
    lease = lab.prepare()
    owner = lab.gateway._owners[id(lease)]
    def fail(current):
        if current == stage: raise OSError("synthetic storage failure")
    lab.ledger._fault = fail
    result = lab.gateway.invoke_once(lease)
    lab.ledger._fault = lambda stage: None
    assert result.state == "UNAVAILABLE" and owner.done and owner.candidate is None
    assert lab.gateway.invoke_once(lease).state == "DENY"
    assert rows(lab)[0]["run_state"] in {"UNKNOWN", "CONSUMED", "ENTERED", "COMPLETED"}
    if "T2" in stage:
        assert owner.started == owner.entries == 0
    elif "T3" in stage or stage == "audit_ai_provider_invocation_observed":
        assert owner.entries == 1 and owner.started == 0


def test_reopen_does_not_reconstruct_lease_and_reconcile_does_not_run_model(lab):
    lease = lab.prepare()
    op = lab.gateway._owners[id(lease)].metadata["operation_id"]
    # Simulate a terminated runtime after intent; no fake invocation.
    lab.ledger.retire_runtime(lab.gateway._owners[id(lease)].authority, lab.gateway._owners[id(lease)].metadata)
    lab.gateway._owners[id(lease)].clear()
    lab.gateway._owners.clear()
    lab.ledger.close()
    ledger = SQLiteExecutionLedger(lab.ledger.root, lab.issuer, lab.clock)
    try:
        ledger.initialize(lab.admin["ORG-A"])
        ledger.reconcile(lab.admin["ORG-A"], op)
        with sqlite3.connect(ledger.path) as connection:
            state = connection.execute("SELECT run_state,reservation_state FROM aip_execution").fetchone()
        assert state == ("UNKNOWN", "UNCERTAIN")
        ledger.reconcile(lab.admin["ORG-A"], op, release_slot=True)
        with sqlite3.connect(ledger.path) as connection:
            assert connection.execute("SELECT run_state,reservation_state FROM aip_execution").fetchone() == ("UNKNOWN", "CHARGED")
    finally:
        ledger.close()


def test_live_owner_cannot_be_reconciled_to_free_budget(lab):
    lease = lab.prepare()
    op = lab.gateway._owners[id(lease)].metadata["operation_id"]
    with pytest.raises(ExecutionError):
        lab.ledger.reconcile(lab.admin["ORG-A"], op, release_slot=True)


def test_audit_reads_are_organization_scoped_and_hide_global_sequence(lab):
    for org in ("ORG-A", "ORG-B"):
        auditor = lab.issuer.issue(org, "auditor")
        events = lab.ledger.read_audit(auditor)
        assert events and all(e["organization_id"] == org and "audit_seq" not in e for e in events)
    with pytest.raises(ExecutionError):
        lab.ledger.read_audit(lab.issuer.issue(role="executor"))


@pytest.mark.parametrize("mutation", ["extra_table", "checksum", "deleted_event"])
def test_unknown_schema_or_integrity_is_not_repaired(lab, mutation):
    with sqlite3.connect(lab.ledger.path) as connection:
        if mutation == "extra_table": connection.execute("CREATE TABLE unexpected(x INTEGER)")
        elif mutation == "checksum": connection.execute("UPDATE aip_store SET migration_checksum=?", ("0" * 64,))
        else: connection.execute("DELETE FROM aip_audit WHERE audit_seq=2")
    with pytest.raises(ExecutionError):
        lab.ledger.policy(lab.executor["ORG-A"])


def test_recognized_workload_denial_is_attributed_without_unresolved_resource(lab):
    lab.change_grant(enabled=False)
    with pytest.raises(ExecutionError):
        lab.prepare()
    denied = [e for e in lab.ledger.read_audit(lab.admin["ORG-A"]) if e["outcome"] == "DENY"]
    assert len(denied) == 1
    event = denied[0]
    assert (event["actor_kind"], event["actor_ref"], event["organization_id"]) == ("workload", "principal-a", "ORG-A")
    assert event["resource_id"] is event["grant_id"] is event["operation_id"] is None


def test_cross_org_denial_has_only_recognized_a_identity(lab):
    envelope_a, evidence_a = lab.mint()
    envelope_b, evidence_b = lab.mint("b")
    before_b = lab.ledger.read_audit(lab.admin["ORG-B"])
    crossed = lab.source.boundary.remember(replace(envelope_a, read_request=envelope_b.read_request,
        source_ref=envelope_b.source_ref, tenant_id="tenant-b", binding_id="binding-b"))
    with pytest.raises(ExecutionError):
        lab.gateway.prepare(crossed, evidence_b)
    denied = [e for e in lab.ledger.read_audit(lab.admin["ORG-A"]) if e["outcome"] == "DENY"]
    assert len(denied) == 1 and denied[0]["actor_ref"] == "principal-a"
    assert "ORG-B" not in repr(denied) and "vacation-b" not in repr(denied) and "tenant-b" not in repr(denied)
    assert lab.ledger.read_audit(lab.admin["ORG-B"]) == before_b


@pytest.mark.parametrize("kind", ["envelope_copy", "context_copy", "inactive_principal", "unknown_input"])
def test_unverifiable_identity_denial_is_anonymous_and_contains_no_refs(lab, kind):
    envelope, evidence = lab.mint()
    if kind == "envelope_copy": envelope = replace(envelope)
    elif kind == "context_copy": envelope = lab.source.boundary.remember(replace(envelope, context=replace(envelope.context)))
    elif kind == "inactive_principal": lab.connector.change("principals", "principal-a", enabled=False)
    else: envelope = {"organization_id":"ORG-B", "principal_id":"principal-b"}
    with pytest.raises(ExecutionError): lab.gateway.prepare(envelope, evidence)
    denied = [e for e in rows(lab, "aip_audit") if e["outcome"] in {"DENY", "UNAVAILABLE"}]
    assert len(denied) == 1 and denied[0]["actor_kind"] == "anonymous"
    assert all(denied[0][key] is None for key in ("actor_ref", "organization_id", "operation_id", "resource_id", "grant_id"))


def test_close_cannot_release_coordinator_while_an_owner_is_live(lab):
    lab.prepare()
    with pytest.raises(ExecutionError):
        lab.ledger.close()


@pytest.mark.parametrize("code", ["ERROR", "INVALID", "UNKNOWN", "TIMEOUT", "CANCELLED", "REVOKED", "UNREGISTERED", None])
def test_completed_cannot_mean_a_provider_error(lab, code):
    lease = lab.prepare()
    owner = lab.gateway._owners[id(lease)]
    with lab.ledger.barrier:
        owner.attempt_version = lab.ledger.consume(owner.authority, owner.metadata, 1)
        owner.attempt_version = lab.ledger.observe_entry(owner.authority, owner.metadata, 2)
        usage = dict(input_units=owner.metadata["input_bytes"], output_bytes=0, output_units=0,
                     elapsed_us=0, result_code=code)
        with pytest.raises(ExecutionError):
            lab.ledger.finish(owner.authority, owner.metadata, 3, "COMPLETED", "accepted", "CHARGED", usage)


@pytest.mark.parametrize("field", ["input_units", "output_bytes", "output_units", "elapsed_us"])
def test_usage_rejects_boolean_as_integer(lab, field):
    lease = lab.prepare()
    owner = lab.gateway._owners[id(lease)]
    usage = dict(input_units=0, output_bytes=0, output_units=0, elapsed_us=0, result_code="CANCELLED")
    usage[field] = True
    with pytest.raises(ExecutionError):
        lab.ledger.finish(owner.authority, owner.metadata, 1, "CANCELLED", "cancelled", "RELEASED", usage)


def test_denial_storage_failure_does_not_fabricate_an_attributed_event(lab):
    lab.change_grant(enabled=False)
    before = rows(lab, "aip_audit")
    def fail(stage):
        if stage == "deny_before_commit": raise OSError("synthetic sink failure")
    lab.ledger._fault = fail
    with pytest.raises(ExecutionError) as caught:
        lab.prepare()
    lab.ledger._fault = lambda stage: None
    assert caught.value.unavailable and rows(lab, "aip_audit") == before


def test_forged_audit_authority_cannot_assert_an_organization(lab):
    with pytest.raises(ExecutionError):
        lab.ledger.deny("scope_mismatch", access=copy(lab.executor["ORG-A"]), subject=("principal-a", "ORG-A"))


@pytest.mark.parametrize("field", ["attempt_version", "grant_version", "input_bytes", "expires_at_us"])
def test_numeric_metadata_cannot_use_sqlite_type_coercion(lab, field):
    lease = lab.prepare()
    owner = lab.gateway._owners[id(lease)]
    command = dict(owner.metadata, **{field:str(owner.metadata[field])})
    with pytest.raises(ExecutionError):
        lab.ledger.consume(owner.authority, command, 1)


def test_unknown_cannot_release_uncertain_budget_through_finish(lab):
    lease = lab.prepare()
    owner = lab.gateway._owners[id(lease)]
    usage = dict(input_units=0, output_bytes=0, output_units=0, elapsed_us=0, result_code="UNKNOWN")
    with pytest.raises(ExecutionError):
        lab.ledger.finish(owner.authority, owner.metadata, 1, "UNKNOWN", "execution_unknown", "RELEASED", usage)


def test_unknown_expiry_does_not_free_slot_and_cross_org_reconcile_cannot(lab):
    lease = lab.prepare()
    owner = lab.gateway._owners[id(lease)]
    usage = dict(input_units=0, output_bytes=0, output_units=0, elapsed_us=0, result_code="UNKNOWN")
    lab.ledger.finish(owner.authority, owner.metadata, 1, "UNKNOWN", "execution_unknown", "UNCERTAIN", usage)
    owner.clear()
    lab.gateway._owners.clear()
    lab.clock.advance(6)
    with pytest.raises(ExecutionError): lab.prepare()
    with pytest.raises(ExecutionError):
        lab.ledger.reconcile(lab.admin["ORG-B"], rows(lab)[0]["operation_id"], release_slot=True)
    assert rows(lab)[0]["reservation_state"] == "UNCERTAIN"


@pytest.mark.parametrize("cursor,limit", [(-1, 1), (True, 1), (0, 0), (0, 101), (0, True), ("0", 1)])
def test_audit_pagination_is_strict_and_not_sql_input(lab, cursor, limit):
    with pytest.raises(ExecutionError):
        lab.ledger.read_audit(lab.admin["ORG-A"], cursor=cursor, limit=limit)


@pytest.mark.parametrize("release", ["false", 1, None])
def test_reconciliation_release_requires_an_explicit_boolean(lab, release):
    lease = lab.prepare()
    owner = lab.gateway._owners[id(lease)]
    operation = owner.metadata["operation_id"]
    lab.ledger.retire_runtime(owner.authority, owner.metadata)
    owner.clear()
    lab.gateway._owners.clear()
    before = rows(lab)
    with pytest.raises(ExecutionError):
        lab.ledger.reconcile(lab.admin["ORG-A"], operation, release_slot=release)
    assert rows(lab) == before


def test_expired_held_reservation_is_not_automatically_freed(lab):
    lease = lab.prepare()
    lab.clock.advance(6)
    with pytest.raises(ExecutionError): lab.prepare()
    assert rows(lab)[0]["reservation_state"] == "HELD"
    result = lab.gateway.invoke_once(lease)
    assert result.state == "EXPIRED" and result.entries == 0
    assert rows(lab)[0]["reservation_state"] == "RELEASED"
