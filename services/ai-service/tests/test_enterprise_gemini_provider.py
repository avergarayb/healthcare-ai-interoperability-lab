"""Offline Gemini provider tests. They do not call the Gemini API."""
import json
import socket
from datetime import datetime, timedelta, timezone

import pytest

from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.gemini_adapter import GeminiResponsesAdapter
from app.enterprise_llm_providers.gemini_configuration import GeminiSettings
from app.enterprise_llm_providers.gemini_permit import GeminiExecutionPermit
from app.enterprise_llm_providers.gemini_pricing import estimate_microusd
from app.enterprise_llm_providers.gemini_request import build_generation
from app.enterprise_llm_providers.gemini_smoke import dry_run_fixed_fixture, simulated_success
from app.enterprise_llm_providers.gemini_transport import (
    DisabledGeminiTransport, GeminiSDKTransport, dispatch_generate,
)
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT


KEY = "test-gemini-marker"
CLAUSE = FIXED_DOCUMENT
NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)


class Scripted:
    def __init__(self, body=None, error=None):
        self.body = body
        self.error = error
        self.calls = 0

    def send(self, generation, timeout_seconds):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.body


def _settings(**overrides):
    values = dict(enabled=True, model_id="gemini-3.5-flash-lite", timeout_seconds=15,
                  max_output_tokens=128, max_input_bytes=2048, max_call_microusd=1000, _credential=KEY)
    values.update(overrides)
    return GeminiSettings(**values)


def _read(document=CLAUSE, organization="ORG-A"):
    from app.enterprise_llm_providers.permit import SyntheticRead
    return SyntheticRead(organization, "principal-a", "instance-a", "vacation-a",
                         "synthetic-policy-question-answering", "synthetic-internal",
                         "vacation-days-v1", document.encode("utf-8"))


def _permit(organization="ORG-A"):
    return GeminiExecutionPermit(
        organization, "principal-a", "instance-a", "vacation-a",
        "synthetic-policy-question-answering", "synthetic-internal", "gemini",
        "gemini-3.5-flash-lite", "vacation-days-v1", 1,
        NOW - timedelta(minutes=1), NOW + timedelta(minutes=5), True)


def _observation(**overrides):
    encoded = CLAUSE.encode("utf-8")
    values = dict(question_id="vacation-days-v1", evidence_found=True, proposed_days=20, proposed_months=12,
                  source_excerpt=CLAUSE, evidence_start=0, evidence_end=len(encoded), refusal_or_insufficient=False)
    values.update(overrides)
    return values


def _body(observation=None, usage=True):
    if observation is None:
        observation = _observation()
    body = {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps(observation)}]}]}
    if usage:
        body["usage"] = {"input_tokens": 40, "output_tokens": 20}
    return body


def _observe(transport, reading=None, permit=None, settings=None):
    return GeminiResponsesAdapter(settings or _settings(), transport, lambda: NOW).observe(
        reading or _read(), _permit() if permit is None else permit)


def test_gemini_is_disabled_and_rejects_a_different_fixture():
    transport = Scripted(_body())
    with pytest.raises(ProviderError) as disabled:
        GeminiResponsesAdapter(clock=lambda: NOW).observe(_read(), _permit())
    assert disabled.value.reason == "remote_disabled" and isinstance(
        GeminiResponsesAdapter()._transport, DisabledGeminiTransport)
    with pytest.raises(ProviderError) as other:
        _observe(transport, _read("VACACIONES: 9 dias tras 3 meses de servicio."))
    assert other.value.reason == "invalid_input" and transport.calls == 0
    assert GeminiSettings.from_mapping({}).enabled is False


def test_gemini_dry_run_grounds_the_fixed_fixture_without_a_client():
    result = dry_run_fixed_fixture(lambda: NOW, simulated_success())
    assert result.accepted is True and result.days == 20 and result.months == 12
    assert result.reserved_microusd <= 1000 and result.estimated_microusd == estimate_microusd(40, 20)
    assert "document" not in dry_run_fixed_fixture.__code__.co_varnames
    generation = build_generation(CLAUSE, _settings())
    assert generation["model"] == "gemini-3.5-flash-lite" and generation["thinking_level"] == "MINIMAL"
    assert generation["attempts"] == 1 and generation["automatic_function_calling"] is False
    assert "tools" not in generation and generation["response_json_schema"]["additionalProperties"] is False


def test_gemini_budget_permit_replay_and_grounding_fail_closed():
    transport = Scripted(_body())
    with pytest.raises(ProviderError) as budget:
        _observe(transport, settings=_settings(max_call_microusd=1))
    assert budget.value.reason == "budget_exceeded" and transport.calls == 0
    with pytest.raises(ProviderError) as isolated:
        _observe(Scripted(_body()), permit=_permit("ORG-B"))
    assert isolated.value.reason == "remote_not_authorized"
    invented = Scripted(_body(_observation(proposed_days=21)))
    adapter = GeminiResponsesAdapter(_settings(), invented, lambda: NOW)
    with pytest.raises(ProviderError) as numbers:
        adapter.observe(_read(), _permit())
    assert numbers.value.reason == "candidate_rejected"
    with pytest.raises(ProviderError) as replay:
        adapter.observe(_read(), _permit())
    assert replay.value.reason == "replay_denied" and invented.calls == 1
    offset = Scripted(_body(_observation(evidence_end=4)))
    with pytest.raises(ProviderError) as mismatch:
        _observe(offset)
    assert mismatch.value.reason == "excerpt_mismatch"
    missing = Scripted(_body(usage=False))
    with pytest.raises(ProviderError) as ambiguous:
        _observe(missing)
    assert ambiguous.value.reason == "consumption_ambiguous"
    assert KEY not in repr(_settings()) and KEY not in repr(GeminiResponsesAdapter(_settings()))


def test_gemini_sdk_transport_does_not_send(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")))
    transport = GeminiSDKTransport(KEY)
    options = transport._client._api_client._http_options
    assert options.timeout == 15000 and options.retry_options.attempts == 1
    with pytest.raises(ProviderError) as blocked:
        transport.send(build_generation(CLAUSE, _settings()), 15)
    assert blocked.value.reason == "egress_blocked" and KEY not in str(blocked.value)
    assert KEY not in repr(transport)


class _Models:
    def __init__(self, response=None, error=None):
        self.calls = []
        self.response = response
        self.error = error

    def generate_content(self, *, model, contents, config):
        self.calls.append((model, contents, config))
        if self.error is not None:
            raise self.error
        return self.response


def _response(reason="STOP", model="gemini-3.5-flash-lite", text=None, thoughts=0, prompt=40, candidates=16):
    if text is None:
        text = json.dumps(_observation())
    finish = type("Finish", (), {"name": reason})()
    candidate = type("Candidate", (), {"finish_reason": finish})()
    usage = type("Usage", (), {
        "prompt_token_count": prompt, "candidates_token_count": candidates, "thoughts_token_count": thoughts,
    })()
    return type("Response", (), {"model": model, "text": text, "candidates": [candidate], "usage_metadata": usage})()


def test_gemini_dispatch_uses_one_closed_sdk_call():
    models = _Models(_response())
    body = dispatch_generate(type("Client", (), {"models": models})(), build_generation(CLAUSE, _settings()))
    config = models.calls[0][2]
    assert len(models.calls) == 1 and models.calls[0][0] == "gemini-3.5-flash-lite"
    assert config.max_output_tokens == 128 and config.response_mime_type == "application/json"
    assert config.thinking_config.thinking_level.name == "MINIMAL"
    assert config.automatic_function_calling.disable is True
    assert config.tools is None and body["usage"]["input_tokens"] == 40
    assert body["usage"]["output_tokens"] == 16 and body["usage"]["thoughts_tokens"] == 0
    assert body["usage"]["cost_exact"] is True and body["usage"]["thoughts_inferred"] is False
    parsed = json.loads(body["output"][0]["content"][0]["text"])
    assert parsed["proposed_days"] == 20 and parsed["proposed_months"] == 12


def test_gemini_dispatch_errors_do_not_echo_the_fixture():
    generation = build_generation(CLAUSE, _settings())
    cases = [
        (_response(reason="MAX_TOKENS"), "incomplete_output"),
        (_response(reason="SAFETY", text=CLAUSE), "model_refusal"),
        (_response(model="gemini-3.6-flash"), "model_denied"),
    ]
    visible = dispatch_generate(
        type("Client", (), {"models": _Models(_response(thoughts=None))})(), generation)
    assert visible["usage"]["input_tokens"] == 40 and visible["usage"]["output_tokens"] == 16
    assert visible["usage"]["thoughts_tokens"] is None and visible["usage"]["cost_exact"] is False
    for response, reason in cases:
        models = _Models(response)
        with pytest.raises(ProviderError) as caught:
            dispatch_generate(type("Client", (), {"models": models})(), generation)
        assert caught.value.reason == reason and CLAUSE not in str(caught.value) and len(models.calls) == 1
    class ApiError(Exception):
        code = 429
    error = ApiError()
    models = _Models(error=error)
    with pytest.raises(ProviderError) as limited:
        dispatch_generate(type("Client", (), {"models": models})(), generation)
    assert limited.value.reason == "rate_limited" and CLAUSE not in str(limited.value)


def test_gemini_stays_outside_the_c03_gateway():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    text = (root / "app" / "enterprise_ai_processing" / "gateway.py").read_text(encoding="utf-8")
    permit = (root / "app" / "enterprise_llm_providers" / "gemini_permit.py").read_text(encoding="utf-8")
    assert "type(self.model) is FakeEnterpriseModel" in text
    assert "enterprise_llm_providers" not in text and "gemini" not in text
    assert "sqlite" not in permit and "CREATE TABLE" not in permit
