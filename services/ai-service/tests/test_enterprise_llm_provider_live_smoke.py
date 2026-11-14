"""Offline tests for the C04 live-smoke executor. They do not call api.openai.com."""
import json
import logging
import os
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import httpx2
import pytest
from openai import OpenAI

from app.enterprise_llm_providers.adapter import OpenAIResponsesAdapter
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.pricing import estimate_microusd
from app.enterprise_llm_providers.live_smoke import (
    CONFIRMATION_PHRASE, cli, default_attempt_directory, dispatch_guarded, dry_run, ground,
    prepare_fixed, reject_alternate,
)
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT
from app.enterprise_llm_providers.transport import (
    DisabledOpenAITransport, live_egress_enabled, open_official_client,
)


KEY = "sk-lab-not-a-real-key"
CLAUSE = FIXED_DOCUMENT
NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)
REPO = Path(__file__).resolve().parents[3]
GATEWAY = REPO / "services" / "ai-service" / "app" / "enterprise_ai_processing" / "gateway.py"


def _clock():
    return NOW


def _observation(**overrides):
    encoded = CLAUSE.encode("utf-8")
    values = dict(question_id="vacation-days-v1", evidence_found=True, proposed_days=20, proposed_months=12,
                  source_excerpt=CLAUSE, evidence_start=0, evidence_end=len(encoded), refusal_or_insufficient=False)
    values.update(overrides)
    return values


def _body(observation, usage=True, status="completed", model="gpt-6-luna"):
    body = {
        "status": status, "model": model,
        "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(observation)}]}],
    }
    if usage:
        body["usage"] = {"input_tokens": 32, "output_tokens": 16}
    return body


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


def _http(status, payload):
    def handler(request):
        return httpx2.Response(status, json=payload, request=request)
    return handler


def _run(argv, stdin, environ):
    return cli(argv, stdin, environ, _clock)


def test_c04c_dry_run_does_not_open_a_socket(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("socket")
    monkeypatch.setattr(socket, "socket", blocked)
    report = dry_run(_clock)
    assert report["result"] == "PASS" and report["mode"] == "dry-run" and report["requests_sent"] == 0
    assert report["grounding"] == "encontrado" and report["observed_days"] == 20 and report["observed_months"] == 12
    assert report["project_billing"] == "unverified" and report["provider_charge"] == "unconfirmed"
    assert report["store"] is False and report["service_tier"] == "default" and report["reasoning_effort"] == "none"
    assert report["max_retries"] == 0 and report["timeout_seconds"] == 15 and report["tools"] == "absent"
    assert report["live_egress"] == "closed" and report["default_transport"] == "DisabledOpenAITransport"
    assert report["reserved_microusd"] <= 1000 and "VACACIONES" not in json.dumps(report)
    rendered = json.dumps(_run([], StringIO(), {}))
    assert "VACACIONES" not in rendered and KEY not in rendered


def test_c04c_live_stays_blocked_without_key_or_interactive_confirmation(tmp_path, monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("socket")
    monkeypatch.setattr(socket, "socket", blocked)
    environ = {"LOCALAPPDATA": str(tmp_path), "OPENAI_API_KEY": KEY}
    missing = _run(["live-once"], StringIO(), {"LOCALAPPDATA": str(tmp_path)})
    absent = _run(["live-once"], StringIO(""), environ)
    supplied = _run(["live-once"], StringIO(CONFIRMATION_PHRASE + "\n"), environ)
    assert missing["reason"] == "credential_absent"
    assert absent["reason"] == "confirmation_required" and supplied["reason"] == "confirmation_required"
    assert missing["requests_sent"] == 0 and supplied["requests_sent"] == 0
    assert list(tmp_path.rglob("*.attempt")) == []
    assert KEY not in json.dumps(supplied) and live_egress_enabled() is False
    assert type(OpenAIResponsesAdapter()._transport) is DisabledOpenAITransport


def test_c04c_rejects_alternate_fixture_model_endpoint_and_unverified_cap():
    with pytest.raises(ProviderError) as document:
        reject_alternate(document="VACACIONES: 9 dias tras 3 meses de servicio.")
    with pytest.raises(ProviderError) as model:
        reject_alternate(model="gpt-6-sol")
    with pytest.raises(ProviderError) as endpoint:
        reject_alternate(base_url="https://example.invalid/v1")
    rejected = _run(["live-once", "--base-url", "https://example.invalid/v1"], StringIO(), {})
    with pytest.raises(ProviderError) as budget:
        prepare_fixed(_clock, call_ceiling=1)
    report = dry_run(_clock)
    assert document.value.reason == "invalid_input" and model.value.reason == "model_denied"
    assert endpoint.value.reason == "not_configured" and rejected["reason"] == "invalid_input"
    assert budget.value.reason == "budget_exceeded"
    assert report["project_billing"] == "unverified" and report["provider_charge"] == "unconfirmed"
    assert "document" not in cli.__code__.co_varnames


def test_c04c_sdk_request_is_single_closed_and_not_replayed(tmp_path):
    payload, reservation = prepare_fixed(_clock)
    recorder = RecordingSDK(_http(200, _sdk_json(json.dumps(_observation()))))
    report = dispatch_guarded(recorder.client, payload, tmp_path)
    sent = json.loads(recorder.requests[0].content.decode("utf-8"))
    with pytest.raises(ProviderError) as replay:
        dispatch_guarded(recorder.client, payload, tmp_path)
    marker = (tmp_path / "vacation-days-v1.attempt").read_text(encoding="utf-8")
    assert report["result"] == "PASS" and report["requests_sent"] == 1 and reservation <= 1000
    assert report["input_tokens"] == 32 and report["output_tokens"] == 16
    assert report["estimated_microusd"] == estimate_microusd(32, 16) and report["provider_charge"] == "unconfirmed"
    assert recorder.client.max_retries == 0 and len(recorder.requests) == 1
    assert sent["store"] is False and sent["service_tier"] == "default"
    assert sent["reasoning"] == {"effort": "none"} and sent["max_output_tokens"] <= 256
    assert sent["stream"] is False and sent["background"] is False and "tools" not in sent
    assert "previous_response_id" not in sent and "base_url" not in sent
    assert replay.value.reason == "replay_denied" and "VACACIONES" not in marker and KEY not in marker
    official = open_official_client(KEY)
    assert official.max_retries == 0 and official.base_url.host == "api.openai.com"
    assert KEY not in repr(official)


def test_c04c_uncertain_responses_do_not_replay(tmp_path):
    payload, _reservation = prepare_fixed(_clock)
    cases = [
        (_http(429, {"error": {"message": CLAUSE + KEY}}), "rate_limited"),
        (_http(500, {"error": {"message": CLAUSE}}), "remote_unavailable"),
    ]
    for handler, reason in cases:
        directory = tmp_path / reason
        recorder = RecordingSDK(handler)
        with pytest.raises(ProviderError) as caught:
            dispatch_guarded(recorder.client, payload, directory)
        with pytest.raises(ProviderError) as replay:
            dispatch_guarded(recorder.client, payload, directory)
        assert caught.value.reason == reason and replay.value.reason == "replay_denied"
        assert CLAUSE not in str(caught.value) and KEY not in str(caught.value)
        assert len(recorder.requests) == 1
    directory = tmp_path / "timeout"
    def timeout(request):
        raise httpx2.TimeoutException("slow")
    recorder = RecordingSDK(timeout)
    with pytest.raises(ProviderError) as timed:
        dispatch_guarded(recorder.client, payload, directory)
    with pytest.raises(ProviderError) as again:
        dispatch_guarded(recorder.client, payload, directory)
    assert timed.value.reason == "timeout" and again.value.reason == "replay_denied"
    assert len(recorder.requests) == 1


def test_c04c_malformed_model_output_is_local_and_closed(tmp_path):
    payload, _reservation = prepare_fixed(_clock)
    cases = [
        (_sdk_json(json.dumps(_observation()), status="incomplete"), "incomplete_output"),
        (_sdk_json("", content=[{"type": "refusal", "refusal": CLAUSE}]), "model_refusal"),
        (_sdk_json(json.dumps(_observation()), usage=False), "consumption_ambiguous"),
        (_sdk_json(json.dumps(_observation()), model="gpt-6-sol"), "model_denied"),
        (_sdk_json("{"), "invalid_output"),
    ]
    for body, reason in cases:
        directory = tmp_path / reason
        recorder = RecordingSDK(_http(200, body))
        with pytest.raises(ProviderError) as caught:
            dispatch_guarded(recorder.client, payload, directory)
        with pytest.raises(ProviderError):
            dispatch_guarded(recorder.client, payload, directory)
        assert caught.value.reason == reason and CLAUSE not in str(caught.value)
        assert len(recorder.requests) == 1


def test_c04c_grounding_rejects_bad_local_observations():
    assert ground(CLAUSE.encode("utf-8"), _body(_observation())).days == 20
    with pytest.raises(ProviderError) as invented:
        ground(CLAUSE.encode("utf-8"), _body(_observation(proposed_days=21)))
    with pytest.raises(ProviderError) as offset:
        ground(CLAUSE.encode("utf-8"), _body(_observation(evidence_end=4)))
    with pytest.raises(ProviderError) as invalid:
        ground(b"\xff", _body(_observation()))
    document = ("á" + CLAUSE).encode("utf-8")
    start = document.find(CLAUSE.encode("utf-8"))
    with pytest.raises(ProviderError) as boundary:
        ground(document, _body(_observation(evidence_start=start - 1, evidence_end=start + len(CLAUSE.encode()))))
    assert invented.value.reason == "candidate_rejected" and offset.value.reason == "excerpt_mismatch"
    assert invalid.value.reason == "invalid_input" and boundary.value.reason == "invalid_offset"


def test_c04c_environment_marker_logs_and_c03_stay_closed(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    redirected = _run(["live-once"], StringIO(), {"HTTPS_PROXY": "http://127.0.0.1:9", "LOCALAPPDATA": str(tmp_path)})
    outside = default_attempt_directory({"LOCALAPPDATA": str(tmp_path)})
    with pytest.raises(ProviderError) as inside:
        default_attempt_directory({"LOCALAPPDATA": str(REPO)})
    gateway = GATEWAY.read_text(encoding="utf-8")
    script = REPO / "scripts" / "c04-openai-live-smoke" / "run_smoke.py"
    assert redirected["reason"] == "environment_redirect" and list(tmp_path.rglob("*.attempt")) == []
    assert REPO.resolve() not in outside.resolve().parents and inside.value.reason == "not_configured"
    assert "type(self.model) is FakeEnterpriseModel" in gateway and "enterprise_llm_providers" not in gateway
    source = script.read_text(encoding="utf-8")
    assert KEY not in caplog.text and CLAUSE not in caplog.text
    assert "cli(sys.argv[1:]" in source and "base_url" not in source and "document" not in source


def test_c04c_windows_environ_is_accepted_and_redirects_still_block(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")))
    redirects = (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy",
        "OPENAI_BASE_URL", "OPENAI_CUSTOM_HEADERS",
    )
    for name in redirects:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert type(os.environ).__name__ == "_Environ"
    absent = _run(["live-once"], StringIO(), os.environ)
    plain = _run(["live-once"], StringIO(), {"LOCALAPPDATA": str(tmp_path)})
    invalid = _run(["live-once"], StringIO(), None)
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    held = _run(["live-once"], StringIO(CONFIRMATION_PHRASE + "\n"), os.environ)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    for name in redirects:
        blocked = _run(["live-once"], StringIO(), {"LOCALAPPDATA": str(tmp_path), "OPENAI_API_KEY": KEY, name: "blocked"})
        assert blocked["reason"] == "environment_redirect" and blocked["requests_sent"] == 0
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    inherited = _run(["live-once"], StringIO(), {"LOCALAPPDATA": str(tmp_path), "OPENAI_API_KEY": KEY})
    directory = default_attempt_directory(os.environ)
    report = dry_run(_clock)
    rendered = json.dumps(absent) + json.dumps(held) + caplog.text
    assert absent["reason"] == plain["reason"] == "credential_absent"
    assert invalid["reason"] == "invalid_input"
    assert held["reason"] == "confirmation_required" and held["requests_sent"] == 0
    assert inherited["reason"] == "environment_redirect" and live_egress_enabled() is False
    assert report["result"] == "PASS" and report["requests_sent"] == 0
    assert report["model"] == "gpt-6-luna" and report["reserved_microusd"] == 303
    assert report["grounding"] == "encontrado" and directory.name == "c04-live-smoke"
    assert KEY not in rendered and CLAUSE not in rendered
    assert list(tmp_path.rglob("*.attempt")) == []


def test_c04c_script_dry_run_exits_without_a_prompt():
    script = REPO / "scripts" / "c04-openai-live-smoke" / "run_smoke.py"
    completed = subprocess.run(
        [sys.executable, str(script), "dry-run"], capture_output=True, text=True, check=False)
    assert completed.returncode == 0 and "VACACIONES" not in completed.stdout and KEY not in completed.stdout
    assert '"result": "PASS"' in completed.stdout and '"requests_sent": 0' in completed.stdout
    assert "CONFIRMO" not in completed.stdout and completed.stderr == ""
