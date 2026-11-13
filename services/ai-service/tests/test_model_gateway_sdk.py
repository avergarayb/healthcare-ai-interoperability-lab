"""SDK bridges behind the neutral gateway. HTTP stays inside the provider mock."""
import ast
import json
import logging
import socket
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import httpx2
import pytest
from google import genai
from google.genai import types
from openai import OpenAI

from app.enterprise_llm_providers.configuration import ProviderSettings
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.gemini_configuration import GeminiSettings
from app.enterprise_llm_providers.gemini_request import build_generation
from app.enterprise_llm_providers.gemini_transport import GeminiSDKTransport, dispatch_generate
from app.enterprise_llm_providers.request import build_payload
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT
from app.enterprise_llm_providers.transport import OpenAISDKTransport, dispatch_responses, live_egress_enabled
from app.enterprise_llm_providers.validation import check_observation
from app.model_gateway.adapters import lab_adapters
from app.model_gateway.agent import VacationClauseAgent
from app.model_gateway.contracts import ExecutionContext, ExecutionGrant
from app.model_gateway.gateway import NeutralModelGateway
from app.model_gateway.sdk_bridge import GeminiSdkBridge, OpenAISdkBridge


CLAUSE = FIXED_DOCUMENT
NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)
OPENAI_KEY = "sk-lab-not-a-real-key"
GEMINI_KEY = "test-gemini-marker"
PACKAGE = Path(__file__).resolve().parents[1] / "app" / "model_gateway"


def _context(organization="ORG-A", budget=1000, principal="principal-a", resource="vacation-a"):
    return ExecutionContext(organization, principal, resource, "synthetic-policy-question-answering",
                            "synthetic-internal", budget)


def _grant(provider, deployment, organization="ORG-A", principal="principal-a", resource="vacation-a",
           purpose="synthetic-policy-question-answering"):
    return ExecutionGrant(provider, deployment, organization, principal, resource, purpose,
                          "synthetic-internal", ("structured_output", "usage_report"), 1)


def _observation(**overrides):
    encoded = CLAUSE.encode("utf-8")
    body = {
        "question_id": "vacation-days-v1", "evidence_found": True, "proposed_days": 20, "proposed_months": 12,
        "source_excerpt": CLAUSE, "evidence_start": 0, "evidence_end": len(encoded),
        "refusal_or_insufficient": False,
    }
    body.update(overrides)
    return body


def _openai_settings():
    return ProviderSettings(True, "gpt-6-luna", 15, 256, 2048, 1000, 5_000_000, OPENAI_KEY)


def _gemini_settings():
    return GeminiSettings(True, "gemini-3.5-flash-lite", 15, 128, 2048, 1000, GEMINI_KEY)


class OpenAIMock:
    def __init__(self, handler):
        self.requests = []

        def wrapped(request):
            self.requests.append(request)
            return handler(request)

        self.client = OpenAI(
            api_key=OPENAI_KEY, max_retries=0, timeout=httpx2.Timeout(15.0),
            http_client=httpx2.Client(transport=httpx2.MockTransport(wrapped)))

    def send(self, payload, timeout_seconds):
        return dispatch_responses(self.client, payload, timeout_seconds)


class GeminiMock:
    def __init__(self, handler):
        self.requests = []

        def wrapped(request):
            self.requests.append(request)
            return handler(request)

        self.client = genai.Client(
            api_key=GEMINI_KEY,
            http_options=types.HttpOptions(
                timeout=15_000, retry_options=types.HttpRetryOptions(attempts=1),
                httpx_client=httpx.Client(transport=httpx.MockTransport(wrapped))))

    def send(self, generation, timeout_seconds):
        return dispatch_generate(self.client, generation)


def _http(library, status, payload):
    def handler(request):
        return library.Response(status, json=payload, request=request)
    return handler


def _openai_body(text, *, model="gpt-6-luna", status="completed", usage=True, content=None):
    if content is None:
        content = [{"type": "output_text", "text": text, "annotations": []}]
    body = {
        "id": "resp_test", "created_at": 1, "model": model, "object": "response",
        "parallel_tool_calls": False, "tool_choice": "none", "tools": [], "status": status,
        "output": [{"id": "msg_test", "type": "message", "role": "assistant", "status": status, "content": content}],
    }
    if usage:
        body["usage"] = {"input_tokens": 32, "output_tokens": 16, "total_tokens": 48}
    return body


def _gemini_body(text, *, model="gemini-3.5-flash-lite", reason="STOP", usage=True):
    body = {
        "modelVersion": model,
        "candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": reason}],
    }
    if usage:
        body["usageMetadata"] = {"promptTokenCount": 40, "candidatesTokenCount": 16, "thoughtsTokenCount": 0}
    return body


def _gateway(deployment_id, bridge):
    adapters = lab_adapters()
    adapters[deployment_id] = bridge
    return NeutralModelGateway(adapters=adapters)


def _run(gateway, provider, deployment, **context):
    return VacationClauseAgent(gateway).run(_context(**context), _grant(provider, deployment, **context))


def test_both_sdk_bridges_answer_the_same_case_for_one_agent(monkeypatch):
    seen = []

    def wrapped(source, parsed):
        seen.append(parsed["proposed_days"])
        return check_observation(source, parsed)

    monkeypatch.setattr("app.model_gateway.gateway.check_observation", wrapped)
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")))
    openai_transport = OpenAIMock(_http(httpx2, 200, _openai_body(json.dumps(_observation()))))
    gemini_transport = GeminiMock(_http(httpx, 200, _gemini_body(json.dumps(_observation()))))
    adapters = lab_adapters()
    adapters["openai-sdk-a"] = OpenAISdkBridge(_openai_settings(), openai_transport, lambda: NOW)
    adapters["gemini-sdk-a"] = GeminiSdkBridge(_gemini_settings(), gemini_transport, lambda: NOW)
    gateway = NeutralModelGateway(adapters=adapters)
    agent = VacationClauseAgent(gateway)
    first = agent.run(_context(), _grant("openai", "openai-sdk-a"))
    second = agent.run(_context(), _grant("gemini", "gemini-sdk-a"))
    assert first.accepted and second.accepted and first.deployment_id != second.deployment_id
    assert seen == [20, 20] and not hasattr(first, "days")
    assert len(openai_transport.requests) == 1 and len(gemini_transport.requests) == 1
    sent = json.loads(openai_transport.requests[0].content.decode("utf-8"))
    assert sent["store"] is False and sent["reasoning"] == {"effort": "none"} and "tools" not in sent
    gemini_sent = json.loads(gemini_transport.requests[0].content.decode("utf-8"))
    assert gemini_sent["generationConfig"]["responseMimeType"] == "application/json"
    assert "tools" not in gemini_sent


def test_default_sdk_bridges_do_not_send(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")))
    gateway = NeutralModelGateway()
    with pytest.raises(ProviderError) as openai_disabled:
        gateway.execute(_context(), _grant("openai", "openai-sdk-a"))
    fresh = NeutralModelGateway()
    with pytest.raises(ProviderError) as gemini_disabled:
        fresh.execute(_context(), _grant("gemini", "gemini-sdk-a"))
    assert openai_disabled.value.reason == gemini_disabled.value.reason == "remote_disabled"


@pytest.mark.parametrize("grant,context,reason", [
    (_grant("anthropic", "anthropic-sdk"), _context(), "model_unregistered"),
    (_grant("lab-text", "text-only-offline-a"), _context(), "capability_denied"),
    (_grant("openai", "gemini-sdk-a"), _context(), "remote_not_authorized"),
    (_grant("gemini", "openai-sdk-a"), _context(), "remote_not_authorized"),
    (_grant("openai", "openai-sdk-a", organization="ORG-B"), _context(organization="ORG-B"), "remote_not_authorized"),
    (_grant("openai", "openai-sdk-a", principal="other"), _context(), "remote_not_authorized"),
    (_grant("openai", "openai-sdk-a", purpose="other"), _context(), "remote_not_authorized"),
    (_grant("openai", "openai-sdk-a"), _context(budget=100), "budget_exceeded"),
])
def test_registry_selection_fails_closed(grant, context, reason):
    with pytest.raises(ProviderError) as caught:
        NeutralModelGateway().execute(context, grant)
    assert caught.value.reason == reason


def test_a_shared_unapproved_purpose_is_denied():
    context = ExecutionContext("ORG-A", "principal-a", "vacation-a", "other", "synthetic-internal", 1000)
    grant = _grant("openai", "openai-sdk-a", purpose="other")
    with pytest.raises(ProviderError) as caught:
        NeutralModelGateway().execute(context, grant)
    assert caught.value.reason == "remote_not_authorized"


@pytest.mark.parametrize("payload,reason", [
    (_openai_body("not-json"), "invalid_output"),
    (_openai_body("", content=[{"type": "refusal", "refusal": CLAUSE}]), "model_refusal"),
    (_openai_body(json.dumps(_observation()), usage=False), "consumption_ambiguous"),
    (_openai_body(json.dumps(_observation()), model="gpt-6-sol"), "model_denied"),
    ("timeout", "timeout"),
    ("429", "rate_limited"),
    ("500", "remote_unavailable"),
])
def test_openai_sdk_errors_send_once_and_do_not_fall_back(payload, reason, monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")))
    if payload == "timeout":
        def handler(request):
            raise httpx2.TimeoutException("slow")
        transport = OpenAIMock(handler)
    elif payload == "429":
        transport = OpenAIMock(_http(httpx2, 429, {"error": {"message": CLAUSE, "code": "rate_limit_exceeded"}}))
    elif payload == "500":
        transport = OpenAIMock(_http(httpx2, 500, {"error": {"message": CLAUSE}}))
    else:
        transport = OpenAIMock(_http(httpx2, 200, payload))
    bridge = OpenAISdkBridge(_openai_settings(), transport, lambda: NOW)
    gateway = _gateway("openai-sdk-a", bridge)
    with pytest.raises(ProviderError) as caught:
        _run(gateway, "openai", "openai-sdk-a")
    with pytest.raises(ProviderError) as replay:
        _run(gateway, "openai", "openai-sdk-a")
    assert caught.value.reason == reason and replay.value.reason == "replay_denied"
    assert bridge.calls == 1 and len(transport.requests) == 1
    assert gateway._adapters["gemini-sdk-a"].calls == 0
    assert CLAUSE not in str(caught.value) and OPENAI_KEY not in str(caught.value)


@pytest.mark.parametrize("payload,reason", [
    (_gemini_body("not-json"), "invalid_output"),
    (_gemini_body(CLAUSE, reason="SAFETY"), "model_refusal"),
    (_gemini_body(json.dumps(_observation()), usage=False), "consumption_ambiguous"),
    (_gemini_body(json.dumps(_observation()), model="gemini-3.6-flash"), "model_denied"),
    ("timeout", "timeout"),
    ("429", "rate_limited"),
    ("500", "remote_unavailable"),
])
def test_gemini_sdk_errors_send_once_and_do_not_fall_back(payload, reason, monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")))
    if payload == "timeout":
        def handler(request):
            raise httpx.ReadTimeout("slow")
        transport = GeminiMock(handler)
    elif payload == "429":
        transport = GeminiMock(_http(httpx, 429, {"error": {"message": CLAUSE, "code": 429}}))
    elif payload == "500":
        transport = GeminiMock(_http(httpx, 500, {"error": {"message": CLAUSE, "code": 500}}))
    else:
        transport = GeminiMock(_http(httpx, 200, payload))
    bridge = GeminiSdkBridge(_gemini_settings(), transport, lambda: NOW)
    gateway = _gateway("gemini-sdk-a", bridge)
    with pytest.raises(ProviderError) as caught:
        _run(gateway, "gemini", "gemini-sdk-a")
    with pytest.raises(ProviderError) as replay:
        _run(gateway, "gemini", "gemini-sdk-a")
    assert caught.value.reason == reason and replay.value.reason == "replay_denied"
    assert bridge.calls == 1 and len(transport.requests) == 1
    assert gateway._adapters["openai-sdk-a"].calls == 0
    assert CLAUSE not in str(caught.value) and GEMINI_KEY not in str(caught.value)


@pytest.mark.parametrize("provider,deployment,bridge_type,settings,library,body", [
    ("openai", "openai-sdk-a", OpenAISdkBridge, _openai_settings, httpx2, _openai_body),
    ("gemini", "gemini-sdk-a", GeminiSdkBridge, _gemini_settings, httpx, _gemini_body),
])
@pytest.mark.parametrize("observation,reason", [
    (_observation(evidence_found=False), "model_refusal"),
    (_observation(proposed_days=21), "candidate_rejected"),
    (_observation(evidence_end=1), "excerpt_mismatch"),
    (_observation(evidence_start=0, evidence_end=10_000), "invalid_offset"),
])
def test_shared_grounding_rejects_the_same_bad_observation(
        provider, deployment, bridge_type, settings, library, body, observation, reason, monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")))
    payload = body(json.dumps(observation))
    transport = OpenAIMock(_http(library, 200, payload)) if provider == "openai" else GeminiMock(_http(library, 200, payload))
    gateway = _gateway(deployment, bridge_type(settings(), transport, lambda: NOW))
    with pytest.raises(ProviderError) as caught:
        _run(gateway, provider, deployment)
    assert caught.value.reason == reason and CLAUSE not in str(caught.value)
    assert len(transport.requests) == 1


def test_utf8_boundary_and_contradiction_stay_in_the_shared_validator():
    source = (CLAUSE + " café").encode("utf-8")
    split = len(CLAUSE.encode("utf-8")) + len(" caf".encode("utf-8")) + 1
    parsed = _observation(evidence_start=split, evidence_end=len(source))
    with pytest.raises(ProviderError) as boundary:
        check_observation(source, parsed)
    assert boundary.value.reason == "invalid_offset"
    contradictory = (CLAUSE + " VACACIONES: 9 dias tras 3 meses de servicio.").encode("utf-8")
    with pytest.raises(ProviderError) as conflict:
        check_observation(contradictory, _observation())
    assert conflict.value.reason == "contradictory_source"


def test_public_surface_and_logs_omit_the_fixture_and_credentials(caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")))
    transport = OpenAIMock(_http(httpx2, 200, _openai_body(json.dumps(_observation()))))
    gateway = _gateway("openai-sdk-a", OpenAISdkBridge(_openai_settings(), transport, lambda: NOW))
    result = _run(gateway, "openai", "openai-sdk-a")
    state = gateway.public_state(result, "ORG-A")
    rendered = repr(result) + repr(state) + caplog.text + repr(gateway)
    assert CLAUSE not in rendered and OPENAI_KEY not in rendered and GEMINI_KEY not in rendered
    assert set(state) == {"phase", "reason", "organization_id", "deployment_id"}
    gateway_source = (PACKAGE / "gateway.py").read_text(encoding="utf-8")
    assert "get_answer" not in gateway_source and "get_grounding" not in gateway_source
    processing = (PACKAGE.parent / "enterprise_ai_processing" / "gateway.py").read_text(encoding="utf-8")
    assert "type(self.model) is FakeEnterpriseModel" in processing and "model_gateway" not in processing
    banned = {"openai", "google", "anthropic", "langgraph", "httpx", "socket"}
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.append(node.module.split(".")[0])
        assert banned.isdisjoint(modules)


def test_live_edges_remain_blocked(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")))
    assert live_egress_enabled() is False
    with pytest.raises(ProviderError) as openai_blocked:
        OpenAISDKTransport(OPENAI_KEY).send(build_payload(CLAUSE, _openai_settings()), 15)
    with pytest.raises(ProviderError) as gemini_blocked:
        GeminiSDKTransport(GEMINI_KEY).send(build_generation(CLAUSE, _gemini_settings()), 15)
    assert openai_blocked.value.reason == "egress_blocked"
    assert gemini_blocked.value.reason == "egress_blocked"
    assert OPENAI_KEY not in str(openai_blocked.value) and GEMINI_KEY not in str(gemini_blocked.value)


def test_credential_and_rewired_bridge_cannot_cross_the_grant(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")))
    transport = OpenAIMock(_http(httpx2, 200, _openai_body(json.dumps(_observation()))))
    bridge = OpenAISdkBridge(_openai_settings(), transport, lambda: NOW)
    adapters = lab_adapters()
    adapters["openai-sdk-a"] = bridge
    adapters["gemini-sdk-a"] = bridge
    gateway = NeutralModelGateway(adapters=adapters)
    with pytest.raises(ProviderError) as crossed:
        gateway.execute(_context(), _grant("openai", "gemini-sdk-a"))
    with pytest.raises(ProviderError) as rewired:
        gateway.execute(_context(), _grant("gemini", "gemini-sdk-a"))
    assert crossed.value.reason == "remote_not_authorized"
    assert rewired.value.reason == "invalid_input"
    assert bridge.calls == 0 and transport.requests == []
    held = gateway.execute(_context(), _grant("private-custom", "private-offline-a"))
    with pytest.raises(ProviderError) as foreign:
        gateway.public_state(held, "ORG-B")
    assert foreign.value.reason == "remote_not_authorized"
    assert not hasattr(gateway, "get_answer") and not hasattr(held, "days")
    rendered = repr(held) + str(foreign.value)
    assert CLAUSE not in rendered and OPENAI_KEY not in rendered


def test_concurrent_organizations_do_not_share_a_deployment():
    gateway = NeutralModelGateway()
    done = []

    def run(organization, deployment, provider):
        try:
            result = gateway.execute(
                _context(organization, principal=organization),
                _grant(provider, deployment, organization=organization, principal=organization, resource="vacation-a"))
            done.append(result.deployment_id)
        except ProviderError as error:
            done.append(error.reason)

    threads = [
        threading.Thread(target=run, args=("ORG-A", "private-offline-a", "private-custom")),
        threading.Thread(target=run, args=("ORG-B", "private-offline-b", "private-custom")),
        threading.Thread(target=run, args=("ORG-A", "private-offline-a", "private-custom")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(done) == ["private-offline-a", "private-offline-b", "replay_denied"]
    assert gateway._adapters["private-offline-a"].calls == 1
    assert CLAUSE not in repr(done)
