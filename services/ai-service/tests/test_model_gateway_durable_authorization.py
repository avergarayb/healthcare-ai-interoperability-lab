"""Operational gateway authorization comes from the ledger, not a caller-built grant."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import socket
import sqlite3

import pytest

from app.enterprise_ai_processing.durable_resolver import LedgerDurableAuthorization
from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.remote_authorization import RemoteAuthorization
from app.enterprise_ai_processing.sqlite_ledger import SQLiteExecutionLedger
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.gemini_transport import GeminiSDKTransport
from app.enterprise_llm_providers.transport import OpenAISDKTransport, live_egress_enabled
from app.model_gateway.adapters import lab_adapters
from app.model_gateway.agent import VacationClauseAgent
from app.model_gateway.simulation import OfflineModelHarness
from app.model_gateway.authorization import DurableAuthorizationResolver, DurableDecision
from app.model_gateway.contracts import ExecutionGrant, ModelIdentity, ModelResponse, UsageMetadata
from app.model_gateway.gateway import NeutralModelGateway
from app.model_gateway.registry import ProviderRegistry, lab_catalog
from app.enterprise_llm_providers.gemini_request import build_generation
from app.enterprise_llm_providers.gemini_configuration import GeminiSettings
from app.enterprise_llm_providers.configuration import ProviderSettings
from app.enterprise_llm_providers.request import build_payload
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT
from tests.enterprise_ai_processing_execution_fixture import execution_laboratory


BUDGET = 1000
RESOURCE = "vacation-a"
DEPLOYMENT = "openai-offline-a"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("provider socket forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)


def _ready(tmp_path):
    lab = execution_laboratory(tmp_path)
    lab.ledger.migrate_to_v2(lab.admin["ORG-A"])
    lab.ledger.migrate_to_v3(lab.admin["ORG-A"])
    lab.ledger.migrate_to_v4(lab.admin["ORG-A"])
    lab.ledger.migrate_remote_audit_v2(lab.admin["ORG-A"])
    lab.ledger.migrate_to_v5(lab.admin["ORG-A"])
    return lab


def _record(lab, **overrides):
    now = lab.clock()
    values = dict(
        authorization_id="remote-ops-a", organization_id="ORG-A", deployment_id=DEPLOYMENT,
        provider_id="openai", model_id="gpt-6-luna", valid_from=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=5), principal_id="synthetic-executor",
        resource_id=RESOURCE, budget_ceiling_microusd=1000)
    values.update(overrides)
    return RemoteAuthorization(**values)


def _register(lab, **overrides):
    record = _record(lab, **overrides)
    lab.ledger.register_remote_authorization(lab.admin[record.organization_id], record)
    return record


def _gateway(lab, **kwargs):
    values = dict(resolver=LedgerDurableAuthorization(lab.ledger))
    values.update(kwargs)
    return NeutralModelGateway(**values)


def _run(gateway, lab, authorization_id="remote-ops-a", deployment_id=DEPLOYMENT, budget=BUDGET,
         resource=RESOURCE, access=None, operation_id="vacation-days-v1"):
    return gateway.execute(
        lab.executor["ORG-A"] if access is None else access, authorization_id, budget, resource,
        deployment_id, operation_id=operation_id)


class _Calls:
    def __init__(self, response=None, fail=None):
        self.calls = 0
        self.response = response
        self.fail = fail

    def estimate_cost(self, request, deployment):
        return deployment.reservation_microusd

    def invoke_once(self, request, deployment):
        self.calls += 1
        if self.fail is not None:
            raise ProviderError(self.fail)
        return self.response


def _observation():
    encoded = FIXED_DOCUMENT.encode("utf-8")
    return {
        "question_id": "vacation-days-v1", "evidence_found": True, "proposed_days": 20, "proposed_months": 12,
        "source_excerpt": FIXED_DOCUMENT, "evidence_start": 0, "evidence_end": len(encoded),
        "refusal_or_insufficient": False,
    }


def test_operational_gateway_accepts_a_durable_permit_and_keeps_egress_closed(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)
    gateway = _gateway(lab)
    result = VacationClauseAgent(gateway).run(
        lab.executor["ORG-A"], record.authorization_id, BUDGET, RESOURCE, DEPLOYMENT)
    assert result.accepted is True and result.reason == "accepted"
    assert result.organization_id == "ORG-A" and result.deployment_id == DEPLOYMENT
    state = gateway.public_state(result, "ORG-A")
    assert set(state) == {"phase", "reason", "organization_id", "deployment_id"}
    assert gateway._registry.get(DEPLOYMENT).egress_allowed is False
    assert live_egress_enabled() is False
    source = Path(__file__).resolve().parents[1] / "app" / "model_gateway" / "gateway.py"
    assert "OfflineModelHarness" not in source.read_text(encoding="utf-8")
    lab.close()


def test_missing_permit_does_not_call_the_bridge(tmp_path):
    lab = _ready(tmp_path)
    gateway = _gateway(lab)
    with pytest.raises(ProviderError) as denied:
        _run(gateway, lab)
    assert denied.value.reason == "not_granted"
    assert gateway._adapters[DEPLOYMENT].calls == 0
    lab.close()


def test_other_organization_cannot_use_the_permit(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)
    gateway = _gateway(lab)
    with pytest.raises(ProviderError) as denied:
        _run(gateway, lab, access=lab.executor["ORG-B"])
    assert denied.value.reason == "not_granted" and gateway._adapters[DEPLOYMENT].calls == 0
    held = _gateway(lab)
    assert held.execute(lab.executor["ORG-A"], record.authorization_id, BUDGET, RESOURCE, DEPLOYMENT).accepted
    lab.close()


def test_other_deployment_provider_and_model_are_denied(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab, authorization_id="remote-ops-sdk", deployment_id="openai-sdk-a")
    moved = _gateway(lab)
    with pytest.raises(ProviderError) as deployment:
        _run(moved, lab, authorization_id=record.authorization_id, deployment_id="openai-offline-a")
    assert deployment.value.reason == "wrong_deployment" and moved._adapters["openai-offline-a"].calls == 0
    provider = _gateway(lab)
    with pytest.raises(ProviderError) as other_provider:
        _run(provider, lab, authorization_id=record.authorization_id, deployment_id="gemini-offline-a")
    assert other_provider.value.reason == "wrong_deployment" and provider._adapters["gemini-offline-a"].calls == 0
    catalog = next(item for item in lab_catalog() if item.deployment_id == "openai-sdk-a")
    forged = replace(catalog, identity=ModelIdentity("openai", "gpt-6-sol"))
    gateway = _gateway(lab, registry=ProviderRegistry((forged,)))
    with pytest.raises(ProviderError) as model:
        gateway.execute(lab.executor["ORG-A"], record.authorization_id, BUDGET, RESOURCE, "openai-sdk-a")
    assert model.value.reason == "invalid_input"
    lab.close()


def test_other_operation_and_capability_do_not_run_the_bridge(tmp_path):
    lab = _ready(tmp_path)
    with pytest.raises(ExecutionError) as malformed:
        lab.ledger.register_remote_authorization(
            lab.admin["ORG-A"], replace(_record(lab), capability="other"))
    assert malformed.value.reason == "invalid_input"
    gateway = _gateway(lab)
    with pytest.raises(ProviderError) as operation:
        _run(gateway, lab, operation_id="other-operation")
    assert operation.value.reason == "operation_denied" and gateway._adapters[DEPLOYMENT].calls == 0
    record = _register(lab)
    catalog = next(item for item in lab_catalog() if item.deployment_id == DEPLOYMENT)
    narrow = replace(catalog, capabilities=frozenset({"text"}))
    limited = _gateway(lab, registry=ProviderRegistry((narrow,)))
    with pytest.raises(ProviderError) as capability:
        limited.execute(lab.executor["ORG-A"], record.authorization_id, BUDGET, RESOURCE, DEPLOYMENT)
    assert capability.value.reason == "capability_denied"
    assert limited._adapters[DEPLOYMENT].calls == 0
    lab.close()


def test_future_expired_and_revoked_permits_are_denied(tmp_path):
    lab = _ready(tmp_path)
    now = lab.clock()
    future = _register(
        lab, authorization_id="remote-future", valid_from=now + timedelta(minutes=5),
        expires_at=now + timedelta(minutes=10))
    early = _gateway(lab)
    with pytest.raises(ProviderError) as not_yet:
        _run(early, lab, authorization_id=future.authorization_id)
    assert not_yet.value.reason == "not_yet_effective" and early._adapters[DEPLOYMENT].calls == 0
    expired = _register(
        lab, authorization_id="remote-expired", deployment_id="openai-sdk-a",
        valid_from=now - timedelta(minutes=10), expires_at=now - timedelta(minutes=1))
    late = _gateway(lab)
    with pytest.raises(ProviderError) as ended:
        _run(late, lab, authorization_id=expired.authorization_id, deployment_id="openai-sdk-a")
    assert ended.value.reason == "authorization_expired" and late._adapters["openai-sdk-a"].calls == 0
    current = _register(lab, authorization_id="remote-live", deployment_id="gemini-offline-a",
                        provider_id="gemini", model_id="gemini-3.5-flash-lite")
    assert _gateway(lab).execute(
        lab.executor["ORG-A"], current.authorization_id, BUDGET, RESOURCE, "gemini-offline-a").accepted
    lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], current.authorization_id, "operator_revoked")
    after = _gateway(lab)
    with pytest.raises(ProviderError) as revoked:
        after.execute(lab.executor["ORG-A"], current.authorization_id, BUDGET, RESOURCE, "gemini-offline-a")
    assert revoked.value.reason == "revoked" and after._adapters["gemini-offline-a"].calls == 0
    unused = _register(
        lab, authorization_id="remote-revoked", deployment_id="gemini-sdk-a",
        provider_id="gemini", model_id="gemini-3.5-flash-lite")
    lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], unused.authorization_id, "operator_revoked")
    fresh = _gateway(lab)
    with pytest.raises(ProviderError) as before:
        fresh.execute(lab.executor["ORG-A"], unused.authorization_id, BUDGET, RESOURCE, "gemini-sdk-a")
    assert before.value.reason == "revoked" and fresh._adapters["gemini-sdk-a"].calls == 0
    lab.close()


def test_revocation_and_expiry_apply_to_the_next_evaluation(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)
    assert _run(_gateway(lab), lab).accepted is True
    lab.ledger.revoke_remote_authorization(lab.admin["ORG-A"], record.authorization_id, "operator_revoked")
    revoked = _gateway(lab)
    with pytest.raises(ProviderError) as denied:
        _run(revoked, lab)
    assert denied.value.reason == "revoked" and revoked._adapters[DEPLOYMENT].calls == 0
    lab.close()


def test_expiry_between_evaluations_is_not_cached(tmp_path):
    lab = _ready(tmp_path)
    start = lab.clock()
    record = _register(
        lab, authorization_id="remote-window", valid_from=start, expires_at=start + timedelta(minutes=2))
    assert _run(_gateway(lab), lab, authorization_id=record.authorization_id).accepted is True
    lab.clock.advance(120)
    later = _gateway(lab)
    with pytest.raises(ProviderError) as denied:
        _run(later, lab, authorization_id=record.authorization_id)
    assert denied.value.reason == "authorization_expired" and later._adapters[DEPLOYMENT].calls == 0
    lab.close()


def test_storage_failures_and_old_schemas_deny_without_migrating(tmp_path):
    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    (tmp_path / "seed").mkdir()
    lab = execution_laboratory(tmp_path / "seed")
    missing = SQLiteExecutionLedger(missing_root, lab.issuer, lab.clock)
    gateway = NeutralModelGateway(resolver=LedgerDurableAuthorization(missing))
    with pytest.raises(ProviderError) as absent:
        gateway.execute(lab.executor["ORG-A"], "remote-ops-a", BUDGET, RESOURCE, DEPLOYMENT)
    assert absent.value.reason == "storage_unavailable" and gateway._adapters[DEPLOYMENT].calls == 0
    missing.close()
    (tmp_path / "v1").mkdir()
    v1 = execution_laboratory(tmp_path / "v1")
    with sqlite3.connect(v1.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 1
    with pytest.raises(ProviderError) as incompatible:
        _run(_gateway(v1), v1)
    assert incompatible.value.reason == "authority_unverifiable"
    with sqlite3.connect(v1.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 1
    (tmp_path / "v2").mkdir()
    v2 = execution_laboratory(tmp_path / "v2")
    v2.ledger.migrate_to_v2(v2.admin["ORG-A"])
    with pytest.raises(ProviderError) as unmigrated:
        _run(_gateway(v2), v2)
    assert unmigrated.value.reason == "authority_unverifiable"
    with sqlite3.connect(v2.ledger.path) as connection:
        assert connection.execute("SELECT schema_version FROM aip_store").fetchone()[0] == 2
    (tmp_path / "ready").mkdir()
    ready = _ready(tmp_path / "ready")
    record = _register(ready)

    def fail(stage):
        if stage == "remote_evaluate_before_commit":
            raise OSError("disk")

    ready.ledger._fault = fail
    with pytest.raises(ProviderError) as read_failed:
        _run(_gateway(ready), ready)
    assert read_failed.value.reason == "storage_unavailable"
    assert _gateway(ready)._adapters[DEPLOYMENT].calls == 0
    ready.ledger._fault = lambda stage: None
    _register(ready, authorization_id="remote-audit", deployment_id="gemini-offline-a",
              provider_id="gemini", model_id="gemini-3.5-flash-lite")

    def fail_allow_audit(stage):
        if stage == "audit_remote_authorization_evaluated":
            raise OSError("disk")

    ready.ledger._fault = fail_allow_audit
    blocked = _gateway(ready)
    with pytest.raises(ProviderError) as allow_audit:
        blocked.execute(ready.executor["ORG-A"], "remote-audit", BUDGET, RESOURCE, "gemini-offline-a")
    assert allow_audit.value.reason == "storage_unavailable" and blocked._adapters["gemini-offline-a"].calls == 0
    ready.ledger._fault = lambda stage: None
    with sqlite3.connect(ready.ledger.path) as connection:
        rows = connection.execute(
            "SELECT event,outcome FROM aip_remote_authorization_audit WHERE authorization_id='remote-audit'").fetchall()
    assert ("remote_authorization_evaluated", "ALLOW") not in rows
    assert record.authorization_id == "remote-ops-a"
    v1.close()
    v2.close()
    lab.close()
    ready.close()


def test_identity_must_be_recognized_and_a_fabricated_grant_is_not_authority(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)
    gateway = _gateway(lab)
    with pytest.raises(ProviderError) as missing:
        gateway.execute(None, record.authorization_id, BUDGET, RESOURCE, DEPLOYMENT)
    forged = replace(lab.executor["ORG-A"])
    with pytest.raises(ProviderError) as untrusted:
        gateway.execute(forged, record.authorization_id, BUDGET, RESOURCE, DEPLOYMENT)
    fabricated = ExecutionGrant(
        "openai", DEPLOYMENT, "ORG-A", "principal-a", RESOURCE, "synthetic-policy-question-answering",
        "synthetic-internal", ("structured_output", "usage_report"), 1)
    with pytest.raises(ProviderError) as grant:
        gateway.execute(fabricated, record.authorization_id, BUDGET, RESOURCE, DEPLOYMENT)
    assert missing.value.reason == untrusted.value.reason == grant.value.reason == "authority_unverifiable"
    assert gateway._adapters[DEPLOYMENT].calls == 0
    bare = NeutralModelGateway()
    with pytest.raises(ProviderError) as unconfigured:
        bare.execute(lab.executor["ORG-A"], record.authorization_id, BUDGET, RESOURCE, DEPLOYMENT)
    assert unconfigured.value.reason == "remote_not_authorized" and bare._adapters[DEPLOYMENT].calls == 0

    class Permissive(DurableAuthorizationResolver):
        def __init__(self):
            self.called = False

        def resolve(self, access, authorization_id, deployment):
            self.called = True
            return DurableDecision(True, "accepted", authorization_id, deployment.deployment_id,
                                   deployment.identity.provider_id, deployment.identity.model_id, "ORG-A")

    stub = Permissive()
    with pytest.raises(ProviderError) as rejected:
        NeutralModelGateway(resolver=stub).execute(
            lab.executor["ORG-A"], record.authorization_id, BUDGET, RESOURCE, DEPLOYMENT)
    assert rejected.value.reason == "remote_not_authorized" and stub.called is False

    class ForgedKind:
        authority_kind = "enterprise-ledger-v3"

        def __init__(self):
            self.called = False

        def resolve(self, access, authorization_id, deployment):
            self.called = True
            return DurableDecision(
                True, "accepted", authorization_id, deployment.deployment_id,
                deployment.identity.provider_id, deployment.identity.model_id, "ORG-A")

    forged_kind = ForgedKind()
    with pytest.raises(ProviderError) as kind:
        NeutralModelGateway(resolver=forged_kind).execute(
            lab.executor["ORG-A"], record.authorization_id, BUDGET, RESOURCE, DEPLOYMENT)
    assert kind.value.reason == "remote_not_authorized" and forged_kind.called is False

    class Spoof(LedgerDurableAuthorization):
        def resolve(self, access, authorization_id, deployment):
            self.called = True
            return DurableDecision(
                True, "accepted", authorization_id, deployment.deployment_id,
                deployment.identity.provider_id, deployment.identity.model_id, access.organization_id)

    spoof = Spoof(lab.ledger)
    spoof.called = False
    with pytest.raises(ProviderError) as subclass:
        NeutralModelGateway(resolver=spoof).execute(
            lab.executor["ORG-A"], record.authorization_id, BUDGET, RESOURCE, DEPLOYMENT)
    assert subclass.value.reason == "remote_not_authorized" and spoof.called is False

    class FakeLedger:
        def clock(self):
            return lab.clock()

        def evaluate_remote_authorization(self, access, authorization_record):
            return None

    with pytest.raises(ProviderError) as fake_store:
        LedgerDurableAuthorization(FakeLedger())
    assert fake_store.value.reason == "remote_not_authorized"
    harness = OfflineModelHarness()
    with pytest.raises(ProviderError) as harness_entry:
        VacationClauseAgent(harness)
    assert harness_entry.value.reason == "remote_not_authorized"
    assert harness._adapters[DEPLOYMENT].calls == 0
    main = Path(__file__).resolve().parents[1] / "app" / "main.py"
    operational = Path(__file__).resolve().parents[1] / "app" / "model_gateway" / "gateway.py"
    assert "OfflineModelHarness" not in main.read_text(encoding="utf-8")
    assert "OfflineModelHarness" not in operational.read_text(encoding="utf-8")
    assert "simulation" not in operational.read_text(encoding="utf-8")
    lab.close()


def test_policy_budget_and_catalog_deny_after_or_before_a_durable_permit(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)
    generous = _gateway(lab)
    priced = _run(generous, lab, budget=1000)
    catalog_reservation = generous._registry.get(DEPLOYMENT).reservation_microusd
    assert priced.reserved_microusd == catalog_reservation and priced.reserved_microusd != 1000
    inflated = _gateway(lab)
    with pytest.raises(ProviderError) as ceiling:
        _run(inflated, lab, budget=10_000_000)
    assert ceiling.value.reason == "budget_exceeded" and inflated._adapters[DEPLOYMENT].calls == 0
    with pytest.raises(TypeError):
        generous.execute(
            lab.executor["ORG-A"], record.authorization_id, 10_000_000, RESOURCE, DEPLOYMENT,
            required_capabilities=("text", "structured_output", "usage_report", "vision"))
    assert generous._adapters[DEPLOYMENT].calls == 1
    policy = _gateway(lab)
    with pytest.raises(ProviderError) as extra:
        _run(policy, lab, resource="")
    assert extra.value.reason == "invalid_input" and policy._adapters[DEPLOYMENT].calls == 0
    poor = _gateway(lab)
    with pytest.raises(ProviderError) as budget:
        _run(poor, lab, budget=1)
    assert budget.value.reason == "budget_exceeded" and poor._adapters[DEPLOYMENT].calls == 0
    outside = _gateway(lab)
    with pytest.raises(ProviderError) as catalog:
        _run(outside, lab, deployment_id="text-only-offline-a")
    assert catalog.value.reason == "invalid_input" and outside._adapters["text-only-offline-a"].calls == 0
    _register(lab, authorization_id="remote-fail", deployment_id="gemini-offline-a",
              provider_id="gemini", model_id="gemini-3.5-flash-lite")
    failing = _Calls(fail="remote_unavailable")
    adapters = lab_adapters()
    adapters["gemini-offline-a"] = failing
    fallback = _gateway(lab, adapters=adapters)
    with pytest.raises(ProviderError) as broken:
        _run(fallback, lab, authorization_id="remote-fail", deployment_id="gemini-offline-a")
    assert broken.value.reason == "remote_unavailable"
    assert failing.calls == 1 and adapters[DEPLOYMENT].calls == 0
    _register(lab, authorization_id="remote-counted", deployment_id="openai-sdk-a")
    counted = _Calls(ModelResponse(
        "openai-sdk-a", _observation(), UsageMetadata(200, 80), 60, None, True, False, False, False, False, 20))
    adapters = lab_adapters()
    adapters["openai-sdk-a"] = counted
    priced = _gateway(lab, adapters=adapters)
    result = _run(priced, lab, authorization_id="remote-counted", deployment_id="openai-sdk-a")
    assert result.output_tokens == 80 and result.included_output_tokens == 20
    assert result.estimated_microusd == 60 and result.thoughts_tokens is None
    lab.close()


def test_public_result_audit_and_transports_stay_closed(tmp_path, caplog):
    lab = _ready(tmp_path)
    record = _register(lab)
    gateway = _gateway(lab)
    result = _run(gateway, lab)
    state = gateway.public_state(result, "ORG-A")
    rendered = repr(result) + repr(state) + caplog.text
    assert FIXED_DOCUMENT not in rendered and "sk-" not in rendered
    with sqlite3.connect(lab.ledger.path) as connection:
        rows = connection.execute("SELECT * FROM aip_remote_authorization_audit").fetchall()
        text = " ".join(str(tuple(row)) for row in rows)
    assert "VACACIONES" not in text and "sk-" not in text and "AIza" not in text
    processing = Path(__file__).resolve().parents[1] / "app" / "enterprise_ai_processing" / "gateway.py"
    assert "type(self.model) is FakeEnterpriseModel" in processing.read_text(encoding="utf-8")
    settings = ProviderSettings(True, "gpt-6-luna", 15, 256, 2048, 1000, 5_000_000, "sk-lab-not-a-real-key")
    with pytest.raises(ProviderError) as openai_blocked:
        OpenAISDKTransport("sk-lab-not-a-real-key").send(build_payload(FIXED_DOCUMENT, settings), 15)
    gemini_settings = GeminiSettings(True, "gemini-3.5-flash-lite", 15, 128, 2048, 1000, "test-gemini-marker")
    with pytest.raises(ProviderError) as gemini_blocked:
        GeminiSDKTransport("test-gemini-marker").send(build_generation(FIXED_DOCUMENT, gemini_settings), 15)
    assert openai_blocked.value.reason == gemini_blocked.value.reason == "egress_blocked"
    assert record.authorization_id == "remote-ops-a"
    lab.close()


def test_permit_survives_reopen(tmp_path):
    lab = _ready(tmp_path)
    record = _register(lab)
    root, issuer, clock = lab.ledger.root, lab.issuer, lab.clock
    lab.close()
    again = SQLiteExecutionLedger(root, issuer, clock)
    try:
        gateway = NeutralModelGateway(resolver=LedgerDurableAuthorization(again))
        result = gateway.execute(issuer.issue("ORG-A", "executor"), record.authorization_id, BUDGET, RESOURCE, DEPLOYMENT)
        assert result.accepted is True and gateway._registry.get(DEPLOYMENT).egress_allowed is False
    finally:
        again.close()
