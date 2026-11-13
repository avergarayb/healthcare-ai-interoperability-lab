"""TASK-C04 offline provider boundary. No network and no live OpenAI call."""
import ast
import importlib.metadata
import inspect
import json
import logging
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx2
import pytest
from openai import OpenAI

from app.enterprise_llm_providers.adapter import OpenAIResponsesAdapter
from app.enterprise_llm_providers.configuration import ProviderSettings
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.permit import RemoteExecutionPermit, SyntheticRead
from app.enterprise_llm_providers.pricing import estimate_microusd
from app.enterprise_llm_providers.request import build_payload
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT, dry_run_fixed_fixture
from app.enterprise_llm_providers.transport import (
    DisabledOpenAITransport, OpenAISDKTransport, dispatch_responses, live_egress_enabled,
)


KEY = "sk-lab-not-a-real-key"
CLAUSE = "VACACIONES: 20 dias tras 12 meses de servicio."
OTHER = "VACACIONES: 9 dias tras 3 meses de servicio."
NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)
PACKAGE = Path(__file__).resolve().parents[1] / "app" / "enterprise_llm_providers"


class LocalTransport:
    def __init__(self, body=None, error=None):
        self.body = body
        self.error = error
        self.payloads = []

    def send(self, payload, timeout_seconds):
        self.payloads.append((payload, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.body


def _settings(**overrides):
    values = dict(enabled=True, model_id="gpt-6-luna", timeout_seconds=15, max_output_tokens=256,
                  max_input_bytes=2048, max_call_microusd=1000, laboratory_cap_microusd=5_000_000,
                  _credential=KEY)
    values.update(overrides)
    return ProviderSettings(**values)


def _read(document=CLAUSE, organization="ORG-A"):
    return SyntheticRead(organization, "principal-a", "instance-a", "vacation-a",
                         "synthetic-policy-question-answering", "synthetic-internal",
                         "vacation-days-v1", document.encode("utf-8"))


def _permit(organization="ORG-A", **overrides):
    values = dict(organization_id=organization, principal_id="principal-a", instance_id="instance-a",
                  resource_id="vacation-a", purpose="synthetic-policy-question-answering",
                  classification="synthetic-internal", provider="openai", model_id="gpt-6-luna",
                  question_id="vacation-days-v1", authorization_revision=1,
                  valid_from=NOW - timedelta(minutes=1), expires_at=NOW + timedelta(minutes=5), enabled=True)
    values.update(overrides)
    return RemoteExecutionPermit(**values)


def _observation(document=CLAUSE, **overrides):
    encoded = document.encode("utf-8")
    start = encoded.find(CLAUSE.encode("utf-8"))
    values = dict(question_id="vacation-days-v1", evidence_found=True, proposed_days=20, proposed_months=12,
                  source_excerpt=CLAUSE, evidence_start=start, evidence_end=start + len(CLAUSE.encode("utf-8")),
                  refusal_or_insufficient=False)
    values.update(overrides)
    return values


def _body(observation, usage=(32, 16), status="completed", error=None):
    body = {"status": status, "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps(observation)}]}]}
    if error is not None:
        body["error"] = error
    if usage is not None:
        body["usage"] = {"input_tokens": usage[0], "output_tokens": usage[1]}
    return body


def _adapter(transport, settings=None):
    return OpenAIResponsesAdapter(settings or _settings(), transport, lambda: NOW)


def _observe(transport, reading=None, permit=_permit, settings=None):
    selected = _permit() if permit is _permit else permit
    return _adapter(transport, settings).observe(reading or _read(), selected)


def test_c04_adapter_is_disabled_by_default():
    transport = LocalTransport(_body(_observation()))
    with pytest.raises(ProviderError) as caught:
        OpenAIResponsesAdapter(clock=lambda: NOW).observe(_read(), _permit())
    assert caught.value.reason == "remote_disabled" and transport.payloads == []
    assert ProviderSettings.from_mapping({}).enabled is False


def test_c04_missing_configuration_and_credential_fail_closed():
    with pytest.raises(ProviderError) as caught:
        ProviderSettings.from_mapping({"OPENAI_TIMEOUT_SECONDS": "later"})
    assert caught.value.reason == "not_configured"
    transport = LocalTransport(_body(_observation()))
    with pytest.raises(ProviderError) as missing:
        _observe(transport, settings=_settings(_credential=None))
    assert missing.value.reason == "credential_absent" and transport.payloads == []


def test_c04_unknown_model_and_missing_permit_do_not_send():
    transport = LocalTransport(_body(_observation()))
    with pytest.raises(ProviderError) as model:
        _observe(transport, settings=_settings(model_id="gpt-6-sol"))
    assert model.value.reason == "model_denied"
    with pytest.raises(ProviderError) as permit:
        _observe(transport, permit=None)
    assert permit.value.reason == "remote_not_authorized" and transport.payloads == []


def test_c04_insufficient_budget_does_not_send():
    transport = LocalTransport(_body(_observation()))
    with pytest.raises(ProviderError) as caught:
        _observe(transport, settings=_settings(max_call_microusd=1, laboratory_cap_microusd=1))
    assert caught.value.reason == "budget_exceeded" and transport.payloads == []


def test_c04_valid_synthetic_response_is_checked_locally():
    transport = LocalTransport(_body(_observation()))
    result = _observe(transport)
    payload = transport.payloads[0][0]
    assert result.accepted is True and result.days == 20 and result.months == 12
    assert payload["store"] is False and payload["model"] == "gpt-6-luna"
    assert payload["reasoning"] == {"effort": "none"} and "tools" not in payload
    assert payload["service_tier"] == "default"
    assert CLAUSE in payload["input"][0]["content"] and CLAUSE not in payload["instructions"]
    assert "ORG-A" not in str(payload) and KEY not in str(payload)
    assert "Según" not in repr(result)


def test_c04_invented_numbers_wrong_excerpt_and_bad_offset_are_rejected():
    invented = LocalTransport(_body(_observation(proposed_days=99)))
    with pytest.raises(ProviderError) as first:
        _observe(invented)
    assert first.value.reason == "candidate_rejected"
    moved = LocalTransport(_body(_observation(source_excerpt="VACACIONES: 99 dias tras 12 meses de servicio.")))
    with pytest.raises(ProviderError) as second:
        _observe(moved)
    assert second.value.reason == "excerpt_mismatch"
    offset = LocalTransport(_body(_observation(evidence_start=-1)))
    with pytest.raises(ProviderError) as third:
        _observe(offset)
    assert third.value.reason == "invalid_offset"


def test_c04_utf8_boundary_and_contradiction_fail_closed():
    document = "á" + CLAUSE
    encoded = document.encode("utf-8")
    start = encoded.find(CLAUSE.encode("utf-8"))
    transport = LocalTransport(_body(_observation(
        document, evidence_start=start - 1, evidence_end=start + len(CLAUSE.encode("utf-8")))))
    with pytest.raises(ProviderError) as boundary:
        _observe(transport, _read(document))
    assert boundary.value.reason == "invalid_offset"
    mixed = CLAUSE + " " + OTHER
    contradiction = LocalTransport(_body(_observation(mixed)))
    with pytest.raises(ProviderError) as caught:
        _observe(contradiction, _read(mixed))
    assert caught.value.reason == "contradictory_source"


def test_c04_refusal_incomplete_and_invalid_json_fail_closed():
    refusal = LocalTransport(_body(_observation(
        evidence_found=False, proposed_days=None, proposed_months=None, source_excerpt="",
        evidence_start=None, evidence_end=None, refusal_or_insufficient=True)))
    with pytest.raises(ProviderError) as first:
        _observe(refusal)
    assert first.value.reason == "model_refusal"
    incomplete = LocalTransport(_body(_observation(), status="incomplete", usage=None))
    with pytest.raises(ProviderError) as second:
        _observe(incomplete)
    assert second.value.reason == "incomplete_output"
    broken = _body(_observation())
    broken["output"][0]["content"][0]["text"] = "{not-json"
    with pytest.raises(ProviderError) as third:
        _observe(LocalTransport(broken))
    assert third.value.reason == "invalid_output"


def test_c04_timeout_rate_limit_and_remote_error_hide_bodies():
    with pytest.raises(ProviderError) as timeout:
        _observe(LocalTransport(error=TimeoutError("VACACIONES body")))
    assert timeout.value.reason == "timeout" and "VACACIONES" not in str(timeout.value)
    limited = LocalTransport(_body(_observation(), error={"code": "rate_limit_exceeded", "message": CLAUSE}))
    with pytest.raises(ProviderError) as rate:
        _observe(limited)
    assert rate.value.reason == "rate_limited" and CLAUSE not in str(rate.value)
    with pytest.raises(ProviderError) as remote:
        _observe(LocalTransport(error=RuntimeError("server " + CLAUSE + " " + KEY)))
    assert remote.value.reason == "remote_unavailable"
    assert CLAUSE not in str(remote.value) and KEY not in str(remote.value)


def test_c04_a_send_cannot_be_repeated_and_ambiguous_usage_is_closed():
    transport = LocalTransport(error=TimeoutError())
    adapter = _adapter(transport)
    with pytest.raises(ProviderError):
        adapter.observe(_read(), _permit())
    with pytest.raises(ProviderError) as replay:
        adapter.observe(_read(), _permit())
    assert replay.value.reason == "replay_denied" and len(transport.payloads) == 1
    ambiguous = LocalTransport(_body(_observation(), usage=None))
    with pytest.raises(ProviderError) as caught:
        _observe(ambiguous)
    assert caught.value.reason == "consumption_ambiguous" and len(ambiguous.payloads) == 1


def test_c04_credential_is_absent_from_repr_and_logs(caplog):
    settings = _settings()
    adapter = OpenAIResponsesAdapter(settings, LocalTransport(_body(_observation())), lambda: NOW)
    with caplog.at_level(logging.DEBUG):
        adapter.observe(_read(), _permit())
    rendered = repr(settings) + repr(adapter) + repr(ProviderError("credential_absent"))
    assert KEY not in rendered and KEY not in caplog.text
    assert "sk-" not in rendered


def test_c04_organizations_do_not_share_a_remote_permit():
    transport = LocalTransport(_body(_observation()))
    with pytest.raises(ProviderError) as caught:
        _observe(transport, _read(CLAUSE, "ORG-B"), _permit())
    assert caught.value.reason == "remote_not_authorized" and transport.payloads == []


def test_c04_package_has_no_network_client_and_c03_fake_stays_bound():
    allowed = {"transport.py": {"openai", "httpx2"}}
    banned = {"socket", "httpx", "urllib", "requests"}
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [(node.module or "").split(".")[0]]
            for name in modules:
                assert name not in banned
                if name in {"openai", "httpx2"}:
                    assert path.name == "transport.py" and name in allowed["transport.py"]
                if name == "google":
                    assert path.name == "gemini_transport.py"
    gateway = (PACKAGE.parent / "enterprise_ai_processing" / "gateway.py").read_text(encoding="utf-8")
    assert "type(self.model) is FakeEnterpriseModel" in gateway
    assert "enterprise_llm_providers" not in gateway and "openai" not in gateway
    assert isinstance(DisabledOpenAITransport(), DisabledOpenAITransport)
    assert importlib.metadata.version("openai") == "3.49.0"
    assert importlib.metadata.version("google-genai") == "2.24.0"


def test_c04_published_rates_cover_the_laboratory_scenarios():
    small = estimate_microusd(500, 200)
    medium = estimate_microusd(2_000, 500)
    large = estimate_microusd(8_000, 1_000)
    assert small == 150 and medium == 450 and large == 1_300
    assert small * 100 == 15_000 and small * 1000 == 150_000
    assert estimate_microusd(500, 200, ceiling=True) > small
    assert estimate_microusd(272_001, 0) > estimate_microusd(272_000, 0)


def _sdk_json(text, *, model="gpt-6-luna", status="completed", usage=True, content=None):
    if content is None:
        content = [{"type": "output_text", "text": text, "annotations": []}]
    body = {
        "id": "resp_test", "created_at": 1, "model": model, "object": "response",
        "parallel_tool_calls": False, "tool_choice": "none", "tools": [], "status": status,
        "output": [{"id": "msg_test", "type": "message", "role": "assistant", "status": status, "content": content}],
    }
    if usage:
        body["usage"] = {
            "input_tokens": 32, "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0},
            "output_tokens": 16, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 48,
        }
    return body


class RecordingSDK:
    def __init__(self, handler):
        self.requests = []

        def wrapped(request):
            self.requests.append(request)
            return handler(request)

        self.client = OpenAI(
            api_key=KEY, max_retries=0, timeout=httpx2.Timeout(15.0),
            http_client=httpx2.Client(transport=httpx2.MockTransport(wrapped)))

    def send(self, payload, timeout_seconds):
        return dispatch_responses(self.client, payload, timeout_seconds)


def _http(status, payload):
    def handler(request):
        return httpx2.Response(status, json=payload, request=request)
    return handler


def test_c04_sdk_client_is_closed_and_official():
    transport = OpenAISDKTransport(KEY)
    assert transport._client.max_retries == 0
    assert transport._client.timeout.connect == 15.0
    assert transport._client.base_url.host == "api.openai.com"
    assert live_egress_enabled() is False
    assert KEY not in repr(transport)
    with pytest.raises(TypeError):
        OpenAISDKTransport(KEY, base_url="http://127.0.0.1:9/v1")
    with pytest.raises(ProviderError) as missing:
        OpenAISDKTransport.from_mapping({})
    assert missing.value.reason == "credential_absent"
    transport._client.base_url = "http://127.0.0.1:9/v1"
    with pytest.raises(ProviderError) as moved:
        transport.send(build_payload(CLAUSE, _settings()), 15)
    assert moved.value.reason == "not_configured"


def test_c04_sdk_send_does_not_open_a_socket(monkeypatch):
    transport = OpenAISDKTransport(KEY)
    def blocked(*args, **kwargs):
        raise AssertionError("socket")
    monkeypatch.setattr(socket, "socket", blocked)
    with pytest.raises(ProviderError) as caught:
        transport.send(build_payload(CLAUSE, _settings()), 15)
    assert caught.value.reason == "egress_blocked" and KEY not in str(caught.value)


def test_c04_sdk_positive_parse_usage_and_closed_parameters():
    text = json.dumps(_observation())
    transport = RecordingSDK(_http(200, _sdk_json(text)))
    result = _observe(transport)
    request = transport.requests[0]
    sent = json.loads(request.content.decode("utf-8"))
    assert result.accepted is True and result.days == 20 and result.months == 12
    assert result.provider_reported_input_tokens == 32 and result.provider_reported_output_tokens == 16
    assert request.url.host == "api.openai.com" and len(transport.requests) == 1
    assert sent["store"] is False and sent["service_tier"] == "default"
    assert sent["reasoning"] == {"effort": "none"} and sent["max_output_tokens"] == 256
    assert sent["stream"] is False and sent["background"] is False
    assert "tools" not in sent and "previous_response_id" not in sent and "base_url" not in sent
    assert KEY not in sent["input"][0]["content"] and "ORG-A" not in sent["input"][0]["content"]


def test_c04_sdk_rejects_wrong_model_incomplete_refusal_and_missing_usage():
    text = json.dumps(_observation())
    cases = [
        (_sdk_json(text, model="gpt-6-sol"), "model_denied"),
        (_sdk_json(text, status="incomplete"), "incomplete_output"),
        (_sdk_json("", content=[{"type": "refusal", "refusal": CLAUSE}]), "model_refusal"),
        (_sdk_json(text, usage=False), "consumption_ambiguous"),
    ]
    for payload, reason in cases:
        transport = RecordingSDK(_http(200, payload))
        with pytest.raises(ProviderError) as caught:
            _observe(transport)
        assert caught.value.reason == reason and CLAUSE not in str(caught.value)
        assert len(transport.requests) == 1


def test_c04_sdk_errors_do_not_retry_or_echo_bodies():
    failures = [
        (429, {"error": {"message": CLAUSE + KEY, "type": "rate_limit_exceeded", "code": "rate_limit_exceeded"}}, "rate_limited"),
        (500, {"error": {"message": CLAUSE, "type": "server_error"}}, "remote_unavailable"),
    ]
    for status, payload, reason in failures:
        transport = RecordingSDK(_http(status, payload))
        adapter = _adapter(transport)
        with pytest.raises(ProviderError) as caught:
            adapter.observe(_read(), _permit())
        with pytest.raises(ProviderError) as replay:
            adapter.observe(_read(), _permit())
        assert caught.value.reason == reason and replay.value.reason == "replay_denied"
        assert CLAUSE not in str(caught.value) and KEY not in str(caught.value)
        assert len(transport.requests) == 1
    def timeout(request):
        raise httpx2.TimeoutException("slow " + CLAUSE)
    transport = RecordingSDK(timeout)
    adapter = _adapter(transport)
    with pytest.raises(ProviderError) as timed:
        adapter.observe(_read(), _permit())
    with pytest.raises(ProviderError):
        adapter.observe(_read(), _permit())
    assert timed.value.reason == "timeout" and len(transport.requests) == 1
    def offline(request):
        raise httpx2.ConnectError("down " + KEY)
    transport = RecordingSDK(offline)
    with pytest.raises(ProviderError) as network:
        _observe(transport)
    assert network.value.reason == "network_unavailable" and KEY not in str(network.value)
    assert len(transport.requests) == 1


def test_c04_byte_limit_and_dry_run_stay_on_the_fixed_fixture():
    transport = LocalTransport(_body(_observation()))
    with pytest.raises(ProviderError) as caught:
        _observe(transport, _read("x" * 2049))
    assert caught.value.reason == "invalid_input" and transport.payloads == []
    result = dry_run_fixed_fixture(_settings(), _permit(), lambda: NOW, _body(_observation()))
    assert result.accepted is True and result.days == 20 and FIXED_DOCUMENT == CLAUSE
    assert "document" not in inspect.signature(dry_run_fixed_fixture).parameters
    with pytest.raises(ProviderError) as isolated:
        dry_run_fixed_fixture(_settings(), _permit("ORG-B"), lambda: NOW, _body(_observation()))
    assert isolated.value.reason == "remote_not_authorized"
    permit_source = (PACKAGE / "permit.py").read_text(encoding="utf-8")
    assert "sqlite" not in permit_source and "CREATE TABLE" not in permit_source
