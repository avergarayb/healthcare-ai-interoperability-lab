"""Offline proof of the provider-neutral gateway. No provider SDK and no egress."""
import ast
import logging
from pathlib import Path

import pytest

from app.enterprise_llm_providers.errors import ProviderError
from app.model_gateway.adapters import OfflineGeminiAdapter, OfflineResponsesAdapter, PrivateCustomAdapter
from app.model_gateway.agent import VacationClauseAgent
from app.model_gateway.contracts import ExecutionContext, ExecutionGrant, ExecutionPolicy
from app.model_gateway.gateway import NeutralModelGateway
from app.model_gateway.registry import ProviderRegistry, pin_resolution, reject_redirect
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT


PACKAGE = Path(__file__).resolve().parents[1] / "app" / "model_gateway"
CLAUSE = FIXED_DOCUMENT


def _context(organization="ORG-A", budget=1000):
    return ExecutionContext(organization, "principal-a", "vacation-a",
                            "synthetic-policy-question-answering", "synthetic-internal", budget)


def _grant(provider, deployment, organization="ORG-A", principal="principal-a", resource="vacation-a"):
    return ExecutionGrant(
        provider, deployment, organization, principal, resource, "synthetic-policy-question-answering",
        "synthetic-internal", ("structured_output", "usage_report"), 1)


def test_two_offline_adapters_serve_the_same_use_case_without_a_sdk(monkeypatch):
    seen = []
    from app.enterprise_llm_providers.validation import check_observation
    def wrapped(source, parsed):
        seen.append((parsed["proposed_days"], parsed["proposed_months"]))
        return check_observation(source, parsed)
    monkeypatch.setattr("app.model_gateway.gateway.check_observation", wrapped)
    gateway = NeutralModelGateway()
    agent = VacationClauseAgent(gateway)
    openai = agent.run(_context(), _grant("openai", "openai-offline-a"))
    gemini = agent.run(_context(), _grant("gemini", "gemini-offline-a"))
    private = agent.run(_context(), _grant("private-custom", "private-offline-a"))
    assert seen == [(20, 12), (20, 12), (20, 12)]
    assert not hasattr(openai, "days") and not hasattr(openai, "months")
    assert openai.deployment_id != gemini.deployment_id
    responses = gateway._adapters["openai-offline-a"]
    custom = gateway._adapters["private-offline-a"]
    assert responses.last_protocol == "offline-responses-shape"
    assert custom.last_protocol.startswith("custom-json-v1:")
    assert responses.last_protocol != custom.last_protocol
    for name in ("agent.py", "gateway.py", "contracts.py"):
        text = (PACKAGE / name).read_text(encoding="utf-8")
        assert "offline-responses-shape" not in text and "custom-json-v1" not in text
        assert "get_answer" not in text and "get_candidate" not in text and "get_grounding" not in text


def test_registry_capabilities_organizations_and_grants_fail_closed():
    gateway = NeutralModelGateway()
    with pytest.raises(ProviderError) as missing:
        gateway.execute(_context(), _grant("anthropic", "anthropic-claude"))
    assert missing.value.reason == "model_unregistered"
    with pytest.raises(ProviderError) as capability:
        gateway.execute(_context(), _grant("lab-text", "text-only-offline-a"))
    assert capability.value.reason == "capability_denied"
    with pytest.raises(ProviderError) as other_org:
        gateway.execute(_context("ORG-A"), _grant("private-custom", "private-offline-b", "ORG-A"))
    assert other_org.value.reason == "remote_not_authorized"
    with pytest.raises(ProviderError) as crossed:
        gateway.execute(_context(), _grant("openai", "gemini-offline-a"))
    assert crossed.value.reason == "remote_not_authorized"
    assert gateway._adapters["gemini-offline-a"].calls == 0
    with pytest.raises(ProviderError) as budget:
        gateway.execute(_context(budget=100), _grant("openai", "openai-offline-a"))
    assert budget.value.reason == "budget_exceeded" and gateway._adapters["openai-offline-a"].calls == 0
    with pytest.raises(ProviderError):
        ProviderRegistry().register(object())


def test_destination_budget_replay_and_grounding_have_no_fallback():
    adapters = NeutralModelGateway()._adapters
    failing = OfflineResponsesAdapter()
    failing.invoke_once = _boom(failing)
    adapters["openai-offline-a"] = failing
    gateway = NeutralModelGateway(adapters=adapters)
    with pytest.raises(ProviderError) as failed:
        gateway.execute(_context(), _grant("openai", "openai-offline-a"))
    assert failed.value.reason == "remote_unavailable"
    assert failing.calls == 1 and adapters["gemini-offline-a"].calls == 0
    with pytest.raises(ProviderError) as replay:
        gateway.execute(_context(), _grant("openai", "openai-offline-a"))
    assert replay.value.reason == "replay_denied" and failing.calls == 1
    uncertain = NeutralModelGateway(adapters={"openai-offline-a": OfflineResponsesAdapter(usage=False)})
    with pytest.raises(ProviderError) as ambiguous:
        uncertain.execute(_context(), _grant("openai", "openai-offline-a"))
    with pytest.raises(ProviderError) as again:
        uncertain.execute(_context(), _grant("openai", "openai-offline-a"))
    assert ambiguous.value.reason == "consumption_ambiguous" and again.value.reason == "replay_denied"
    bad = {"question_id": "vacation-days-v1", "evidence_found": True, "proposed_days": 21, "proposed_months": 12,
           "source_excerpt": CLAUSE, "evidence_start": 0, "evidence_end": len(CLAUSE.encode()),
           "refusal_or_insufficient": False}
    grounded = NeutralModelGateway(adapters={"openai-offline-a": OfflineResponsesAdapter(observation=bad)})
    with pytest.raises(ProviderError) as invented:
        grounded.execute(_context(), _grant("openai", "openai-offline-a"))
    assert invented.value.reason == "candidate_rejected" and CLAUSE not in str(invented.value)
    with pytest.raises(ProviderError) as url:
        NeutralModelGateway().execute(_context(), _grant("openai", "openai-offline-a"), "http://127.0.0.1/")
    assert url.value.reason == "destination_denied"
    with pytest.raises(ProviderError):
        pin_resolution("10.0.0.8", "10.0.0.9")
    with pytest.raises(ProviderError):
        reject_redirect(302)
    with pytest.raises(ProviderError):
        ExecutionPolicy(allow_fallback=True)


def test_results_logs_and_c03_do_not_carry_the_fixture(caplog):
    caplog.set_level(logging.DEBUG)
    result = VacationClauseAgent(NeutralModelGateway()).run(_context(), _grant("private-custom", "private-offline-a"))
    state = NeutralModelGateway().public_state(result, "ORG-A")
    rendered = repr(result) + repr(state) + caplog.text
    assert CLAUSE not in rendered and "20" not in repr(result)
    gateway = (PACKAGE.parent / "enterprise_ai_processing" / "gateway.py").read_text(encoding="utf-8")
    assert "type(self.model) is FakeEnterpriseModel" in gateway and "model_gateway" not in gateway
    banned = {"openai", "google", "anthropic", "langgraph", "httpx", "socket", "urllib", "requests"}
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                modules = [(node.module or "").split(".")[0] for _ in node.names]
                modules.append((node.module or "").split(".")[0])
            assert banned.isdisjoint(modules)


def _boom(adapter):
    def invoke_once(request, deployment):
        adapter.calls += 1
        raise ProviderError("remote_unavailable")
    return invoke_once
