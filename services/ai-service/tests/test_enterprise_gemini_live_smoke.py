"""Offline checks for the isolated Gemini smoke. No test contacts Google."""
import io
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from google import genai
from google.genai import types

from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.gemini_live import (
    ATTEMPT_ID, CONFIRMATION_PHRASE, LIVE_OUTPUT_TOKENS, MARKER_NAME, attempt_reservation,
    claim_attempt, cli, default_attempt_directory, dry_run, execute_once, reject_alternate,
    require_ceiling,
)
from app.enterprise_llm_providers.gemini_pricing import CALL_CEILING_MICROUSD
from app.enterprise_llm_providers.gemini_configuration import GeminiSettings
from app.enterprise_llm_providers.gemini_request import build_generation
from app.enterprise_llm_providers.gemini_transport import (
    GeminiSDKTransport, _account, open_official_client, require_official_client,
)
from app.enterprise_llm_providers.live_smoke import CONFIRMATION_PHRASE as OPENAI_PHRASE
from app.enterprise_llm_providers.smoke import FIXED_DOCUMENT
from app.enterprise_llm_providers.validation import check_observation
from app.model_gateway.sdk_bridge import gemini_reservation


CLAUSE = FIXED_DOCUMENT
NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)
MARKER = "test-gemini-marker"


def _http(status, payload):
    def handler(request):
        return httpx.Response(status, json=payload, request=request)
    return handler


def _client(handler):
    return genai.Client(
        api_key=MARKER,
        http_options=types.HttpOptions(
            timeout=15_000, retry_options=types.HttpRetryOptions(attempts=1),
            httpx_client=httpx.Client(transport=httpx.MockTransport(handler))))


def _body(text, *, model="gemini-3.5-flash-lite", reason="STOP", usage=True):
    body = {
        "modelVersion": model,
        "candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": reason}],
    }
    if usage:
        body["usageMetadata"] = {"promptTokenCount": 40, "candidatesTokenCount": 16, "thoughtsTokenCount": 0}
    return body


def _observation(**overrides):
    encoded = CLAUSE.encode("utf-8")
    body = {
        "question_id": "vacation-days-v1", "evidence_found": True, "proposed_days": 20, "proposed_months": 12,
        "source_excerpt": CLAUSE, "evidence_start": 0, "evidence_end": len(encoded),
        "refusal_or_insufficient": False,
    }
    body.update(overrides)
    return body


def _block_socket(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")))


class _TTY:
    def __init__(self, line):
        self.line = line

    def isatty(self):
        return True

    def readline(self):
        return self.line


def test_dry_run_needs_no_credential_and_sends_nothing(tmp_path, monkeypatch, caplog):
    _block_socket(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    report = cli([], io.StringIO(""), {"LOCALAPPDATA": str(tmp_path)}, lambda: NOW)
    assert report["result"] == "PASS" and report["requests_sent"] == 0 and report["grounding"] == "PASS"
    assert report["reserved_microusd"] == attempt_reservation() <= CALL_CEILING_MICROUSD
    assert report["max_output_tokens"] == LIVE_OUTPUT_TOKENS and report["attempt"] == ATTEMPT_ID
    assert report["reserved_microusd"] != gemini_reservation()
    assert "days" not in report and CLAUSE not in caplog.text and MARKER not in json.dumps(report)
    assert not list(Path(tmp_path).rglob("*attempt*"))


def test_live_once_rejects_noninteractive_input_and_a_wrong_phrase(tmp_path, monkeypatch):
    _block_socket(monkeypatch)
    monkeypatch.setattr(
        "app.enterprise_llm_providers.gemini_live.open_official_client",
        lambda credential: (_ for _ in ()).throw(AssertionError("client")))
    environ = {"LOCALAPPDATA": str(tmp_path), "GEMINI_API_KEY": MARKER}
    blocked = cli(["live-once"], io.StringIO(CONFIRMATION_PHRASE + "\n"), environ, lambda: NOW)
    wrong = cli(["live-once"], _TTY("no\n"), environ, lambda: NOW)
    assert blocked["reason"] == wrong["reason"] == "confirmation_required"
    assert blocked["requests_sent"] == wrong["requests_sent"] == 0
    assert not list(Path(tmp_path).rglob("*attempt*"))


def test_live_once_stops_for_a_missing_key_proxy_or_bad_arguments(tmp_path, monkeypatch):
    _block_socket(monkeypatch)
    missing = cli(["live-once"], _TTY(CONFIRMATION_PHRASE + "\n"), {"LOCALAPPDATA": str(tmp_path)}, lambda: NOW)
    proxied = cli(["live-once"], _TTY(CONFIRMATION_PHRASE + "\n"),
                  {"LOCALAPPDATA": str(tmp_path), "GEMINI_API_KEY": MARKER, "HTTPS_PROXY": "http://127.0.0.1:9"},
                  lambda: NOW)
    altered = cli(["live-once", "--model", "other"], io.StringIO(""), {}, lambda: NOW)
    assert missing["reason"] == "credential_absent"
    assert proxied["reason"] == "environment_redirect"
    assert altered["reason"] == "invalid_input"
    with pytest.raises(ProviderError) as model:
        reject_alternate(model="other")
    with pytest.raises(ProviderError) as document:
        reject_alternate(document="otro")
    with pytest.raises(ProviderError) as endpoint:
        reject_alternate(base_url="https://example.test")
    assert model.value.reason == "model_denied" and document.value.reason == "invalid_input"
    assert endpoint.value.reason == "not_configured"
    with pytest.raises(ProviderError) as budget:
        require_ceiling(gemini_reservation(), ceiling=gemini_reservation() - 1)
    assert budget.value.reason == "budget_exceeded"


def test_official_client_stays_closed_and_a_foreign_host_is_refused(tmp_path, monkeypatch):
    _block_socket(monkeypatch)
    client = open_official_client(MARKER)
    require_official_client(client)
    settings = GeminiSettings(True, "gemini-3.5-flash-lite", 15, 128, 2048, 1000, MARKER)
    with pytest.raises(ProviderError) as blocked:
        GeminiSDKTransport(MARKER).send(build_generation(CLAUSE, settings), 15)
    assert blocked.value.reason == "egress_blocked" and MARKER not in str(blocked.value)
    foreign = genai.Client(
        api_key=MARKER,
        http_options=types.HttpOptions(base_url="https://example.test/", timeout=15_000,
                                       retry_options=types.HttpRetryOptions(attempts=1)))
    with pytest.raises(ProviderError) as denied:
        execute_once(foreign, tmp_path, lambda: NOW)
    assert denied.value.reason == "not_configured"
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    with pytest.raises(ProviderError) as redirected:
        open_official_client(MARKER)
    assert redirected.value.reason == "environment_redirect"


def test_sdk_http_is_one_shot_and_errors_do_not_retry(tmp_path, monkeypatch):
    _block_socket(monkeypatch)
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=_body(json.dumps(_observation())), request=request)

    report = execute_once(_client(handler), tmp_path / "once", lambda: NOW)
    assert report["result"] == "PASS" and report["requests_sent"] == 1 and report["grounding"] == "PASS"
    assert len(seen) == 1 and "VACACIONES" not in json.dumps(report)
    again = execute_once(_client(handler), tmp_path / "once", lambda: NOW)
    assert again["reason"] == "replay_denied" and len(seen) == 1
    cases = [
        (_body("not-json"), "invalid_output"),
        (_body(CLAUSE, reason="SAFETY"), "model_refusal"),
        (_body("", reason="MAX_TOKENS"), "incomplete_output"),
        (_body(json.dumps(_observation()), usage=False), "consumption_ambiguous"),
        (_body(json.dumps(_observation()), model="gemini-3.6-flash"), "model_denied"),
        (_body(json.dumps(_observation(proposed_days=21))), "candidate_rejected"),
        (_body(json.dumps(_observation(evidence_end=1))), "excerpt_mismatch"),
    ]
    for index, (payload, reason) in enumerate(cases):
        calls = []

        def handler(request, calls=calls, payload=payload):
            calls.append(request)
            return httpx.Response(200, json=payload, request=request)

        failed = execute_once(_client(handler), tmp_path / str(index), lambda: NOW)
        assert failed["reason"] == reason and failed["requests_sent"] == 1 and len(calls) == 1
        assert CLAUSE not in json.dumps(failed)
    for status, reason in ((429, "rate_limited"), (500, "remote_unavailable")):
        calls = []

        def handler(request, calls=calls, status=status):
            calls.append(request)
            return httpx.Response(status, json={"error": {"message": CLAUSE, "code": status}}, request=request)

        failed = execute_once(_client(handler), tmp_path / str(status), lambda: NOW)
        assert failed["reason"] == reason and len(calls) == 1 and CLAUSE not in json.dumps(failed)

    def timeout(request):
        raise httpx.ReadTimeout("slow")

    timed = execute_once(_client(timeout), tmp_path / "timeout", lambda: NOW)
    assert timed["reason"] == "timeout" and timed["requests_sent"] == 1


def test_shared_grounding_still_rejects_utf8_and_contradictions():
    source = (CLAUSE + " café").encode("utf-8")
    split = len(CLAUSE.encode("utf-8")) + len(" caf".encode("utf-8")) + 1
    parsed = _observation(evidence_start=split, evidence_end=len(source))
    with pytest.raises(ProviderError) as boundary:
        check_observation(source, parsed)
    contradictory = (CLAUSE + " VACACIONES: 9 dias tras 3 meses de servicio.").encode("utf-8")
    with pytest.raises(ProviderError) as conflict:
        check_observation(contradictory, _observation())
    assert boundary.value.reason == "invalid_offset" and conflict.value.reason == "contradictory_source"


def test_incomplete_output_keeps_token_counts_and_drops_text(tmp_path, monkeypatch):
    _block_socket(monkeypatch)
    secret = "THOUGHT-SECRET"
    partial = '{"question_id":'
    usage = {"promptTokenCount": 40, "candidatesTokenCount": 16, "thoughtsTokenCount": 90}
    cases = {
        "stop": (_body(json.dumps(_observation())), "PASS", "STOP"),
        "max": (_body("", reason="MAX_TOKENS"), "incomplete_output", "MAX_TOKENS"),
        "partial": (_body(partial, reason="MAX_TOKENS"), "incomplete_output", "MAX_TOKENS"),
        "safety": (_body(secret, reason="SAFETY"), "model_refusal", "SAFETY"),
        "malformed": (_body("{"), "invalid_output", "STOP"),
        "grounding": (_body(json.dumps(_observation(proposed_days=21))), "candidate_rejected", "STOP"),
    }
    cases["empty-candidate"] = ({
        "modelVersion": "gemini-3.5-flash-lite", "candidates": [], "usageMetadata": usage,
    }, "incomplete_output", "absent")
    cases["no-content"] = ({
        "modelVersion": "gemini-3.5-flash-lite",
        "candidates": [{"finishReason": "STOP"}], "usageMetadata": usage,
    }, "incomplete_output", "STOP")
    cases["thought-only"] = ({
        "modelVersion": "gemini-3.5-flash-lite",
        "candidates": [{"content": {"role": "model", "parts": [{"text": secret, "thought": True}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 0, "thoughtsTokenCount": 90},
    }, "incomplete_output", "STOP")
    cases["no-usage"] = (_body("", reason="MAX_TOKENS", usage=False), "incomplete_output", "MAX_TOKENS")
    for name, (payload, reason, finish) in cases.items():
        calls = []

        def handler(request, calls=calls, payload=payload):
            calls.append(request)
            return httpx.Response(200, json=payload, request=request)

        report = execute_once(_client(handler), tmp_path / name, lambda: NOW)
        rendered = json.dumps(report)
        assert report["requests_sent"] == 1 and len(calls) == 1
        assert secret not in rendered and partial not in rendered and CLAUSE not in rendered
        if name == "stop":
            assert report["result"] == "PASS" and report["grounding"] == "PASS"
            assert "finish_reason" not in report
        else:
            assert report["reason"] == reason and report["grounding"] == "FAIL"
            assert report["finish_reason"] == finish
        if name == "no-usage":
            assert report["usage_present"] is False and report["input_tokens"] is None
        elif name != "stop":
            assert report["usage_present"] is True and report["input_tokens"] == 40
        if name in {"empty-candidate", "no-content", "thought-only"}:
            assert report["thoughts_tokens"] == 90
        if name == "no-content":
            assert report["candidate_present"] is True and report["content_present"] is False
        if name == "empty-candidate":
            assert report["candidate_present"] is False


def test_stop_without_thoughts_keeps_visible_counts(tmp_path, monkeypatch):
    _block_socket(monkeypatch)
    payload = _body(json.dumps(_observation()), usage=False)
    payload["usageMetadata"] = {"promptTokenCount": 92, "candidatesTokenCount": 107}
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload, request=request)

    report = execute_once(_client(handler), tmp_path / "visible", lambda: NOW)
    rendered = json.dumps(report)
    assert report["result"] == "PASS" and report["grounding"] == "PASS" and report["reason"] == "accepted"
    assert report["input_tokens"] == 92 and report["candidate_tokens"] == 107 and report["output_tokens"] == 107
    assert report["thoughts_tokens"] is None and report["estimated_microusd"] is None
    assert report["provider_charge"] == "unconfirmed" and len(calls) == 1
    assert CLAUSE not in rendered and "92" in rendered


def test_usage_fields_stay_distinct_and_do_not_skip_grounding(tmp_path, monkeypatch):
    _block_socket(monkeypatch)
    observation = json.dumps(_observation())
    cases = {
        "complete": ({"promptTokenCount": 40, "candidatesTokenCount": 16, "thoughtsTokenCount": 0, "totalTokenCount": 56}, "accepted", 0, True),
        "zero": ({"promptTokenCount": 40, "candidatesTokenCount": 16, "thoughtsTokenCount": 0}, "accepted", 0, True),
        "positive": ({"promptTokenCount": 40, "candidatesTokenCount": 16, "thoughtsTokenCount": 4}, "accepted", 4, True),
        "consistent": ({"promptTokenCount": 92, "candidatesTokenCount": 107, "thoughtsTokenCount": 3, "totalTokenCount": 202}, "accepted", 3, True),
        "inferred-thoughts": ({"promptTokenCount": 92, "candidatesTokenCount": 107, "toolUsePromptTokenCount": 0, "totalTokenCount": 204}, "accepted", 5, True),
        "zero-fill": ({"promptTokenCount": 40, "candidatesTokenCount": 16, "totalTokenCount": 56}, "accepted", 0, True),
        "split": ({"promptTokenCount": 92, "candidatesTokenCount": 107, "totalTokenCount": 204}, "accepted", None, False),
        "absent-total": ({"promptTokenCount": 92, "candidatesTokenCount": 107}, "accepted", None, False),
        "no-visible": ({"promptTokenCount": 92}, "consumption_ambiguous", None, False),
        "no-prompt": ({"candidatesTokenCount": 107}, "consumption_ambiguous", None, False),
        "negative": ({"promptTokenCount": 92, "candidatesTokenCount": -1}, "consumption_ambiguous", None, False),
        "bad-json": ({"promptTokenCount": 92, "candidatesTokenCount": 107}, "invalid_output", None, False),
        "max": ({"promptTokenCount": 92, "candidatesTokenCount": 107}, "incomplete_output", None, False),
        "safety": ({"promptTokenCount": 92, "candidatesTokenCount": 107}, "model_refusal", None, False),
        "inconsistent": ({"promptTokenCount": 92, "candidatesTokenCount": 107, "totalTokenCount": 10}, "consumption_ambiguous", None, False),
        "rejected": ({"promptTokenCount": 92, "candidatesTokenCount": 107}, "candidate_rejected", None, False),
    }
    for name, (metadata, reason, thoughts, exact) in cases.items():
        text = observation
        finish = "STOP"
        if name == "bad-json":
            text = "{"
        elif name == "max":
            finish = "MAX_TOKENS"
            text = ""
        elif name == "safety":
            finish = "SAFETY"
            text = "blocked"
        elif name == "rejected":
            text = json.dumps(_observation(proposed_days=21))
        payload = _body(text, reason=finish, usage=False)
        payload["usageMetadata"] = metadata
        calls = []

        def handler(request, calls=calls, payload=payload):
            calls.append(request)
            return httpx.Response(200, json=payload, request=request)

        report = execute_once(_client(handler), tmp_path / name, lambda: NOW)
        rendered = json.dumps(report)
        assert report["reason"] == reason and len(calls) == 1, name
        assert report["thoughts_tokens"] == thoughts and report["cost_exact"] is exact
        assert report["thoughts_inferred"] is (name in {"inferred-thoughts", "zero-fill"})
        assert report["tool_inferred"] is (name in {"complete", "consistent", "zero-fill"})
        assert report["prompt_inferred"] is False and report["visible_inferred"] is False
        if name == "inferred-thoughts":
            assert report["estimated_microusd"] is not None and report["provider_charge"] == "unconfirmed"
        assert CLAUSE not in rendered and "blocked" not in rendered
        if reason == "accepted":
            assert report["grounding"] == "PASS" and report["result"] == "PASS"
        else:
            assert report["grounding"] == "FAIL" and report["result"] == "FAIL"
        if name in {"split", "absent-total", "bad-json", "max", "safety", "rejected", "inconsistent"}:
            assert report["input_tokens"] == 92 and report["candidate_tokens"] == 107 and report["output_tokens"] == 107
        if name in {"no-visible", "negative", "text"}:
            assert report["candidate_tokens"] is None
        if exact is not True:
            assert report["estimated_microusd"] is None
    boolean = _account(SimpleNamespace(
        prompt_token_count=92, candidates_token_count=107, thoughts_token_count=True,
        tool_use_prompt_token_count=None, total_token_count=None))
    text_count = _account(SimpleNamespace(
        prompt_token_count="92", candidates_token_count=107, thoughts_token_count=None,
        tool_use_prompt_token_count=None, total_token_count=None))
    assert boolean["usable"] is False and text_count["usable"] is False
    assert boolean["candidate_tokens"] == 107 and boolean["thoughts_tokens"] is None


def test_windows_environ_is_accepted_and_redirects_still_block(tmp_path, monkeypatch, caplog):
    _block_socket(monkeypatch)
    redirects = (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy",
        "GEMINI_BASE_URL", "GOOGLE_GENAI_BASE_URL",
    )
    for name in redirects:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert type(os.environ).__name__ == "_Environ"
    absent = cli(["live-once"], io.StringIO(""), os.environ, lambda: NOW)
    plain = cli(["live-once"], io.StringIO(""), {"LOCALAPPDATA": str(tmp_path)}, lambda: NOW)
    invalid = cli(["live-once"], io.StringIO(""), None, lambda: NOW)
    monkeypatch.setenv("GEMINI_API_KEY", MARKER)
    held = cli(["live-once"], io.StringIO(CONFIRMATION_PHRASE + "\n"), os.environ, lambda: NOW)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    for name in redirects:
        blocked = cli(
            ["live-once"], io.StringIO(""),
            {"LOCALAPPDATA": str(tmp_path), "GEMINI_API_KEY": MARKER, name: "blocked"},
            lambda: NOW)
        assert blocked["reason"] == "environment_redirect" and blocked["requests_sent"] == 0
    monkeypatch.setenv("HTTPS_PROXY", "blocked")
    inherited = cli(
        ["live-once"], io.StringIO(""),
        {"LOCALAPPDATA": str(tmp_path), "GEMINI_API_KEY": MARKER}, lambda: NOW)
    directory = default_attempt_directory(os.environ)
    report = dry_run(lambda: NOW)
    rendered = json.dumps(absent) + json.dumps(held) + caplog.text
    assert absent["reason"] == plain["reason"] == "credential_absent"
    assert invalid["reason"] == "invalid_input"
    assert held["reason"] == "confirmation_required" and held["requests_sent"] == 0
    assert inherited["reason"] == "environment_redirect"
    assert report["result"] == "PASS" and report["requests_sent"] == 0
    assert report["model"] == "gemini-3.5-flash-lite" and report["reserved_microusd"] == attempt_reservation()
    assert report["max_output_tokens"] == 256 and report["attempt"] == "002"
    assert report["grounding"] == "PASS" and directory.name == "c04-gemini-live-smoke"
    assert MARKER not in rendered and not list(Path(tmp_path).rglob("*attempt*"))


def test_markers_directories_and_c03_stay_separate(tmp_path, monkeypatch):
    prior = tmp_path / "gemini" / "vacation-days-v1.attempt"
    prior.parent.mkdir()
    prior.write_bytes(b"provider=gemini\r\nmodel=gemini-3.5-flash-lite\r\nquestion_id=vacation-days-v1\r\n")
    digest = prior.read_bytes()
    claim_attempt(tmp_path / "gemini")
    with pytest.raises(ProviderError) as replay:
        claim_attempt(tmp_path / "gemini")
    assert replay.value.reason == "replay_denied"
    assert prior.read_bytes() == digest
    text = (tmp_path / "gemini" / MARKER_NAME).read_text(encoding="utf-8")
    assert text == "provider=gemini\nmodel=gemini-3.5-flash-lite\nquestion_id=vacation-days-v1\nattempt=002\n"
    assert CLAUSE not in text and "openai" not in text
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy",
                 "GEMINI_BASE_URL", "GOOGLE_GENAI_BASE_URL", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    old_phrase = (
        "CONFIRMO UNA SOLICITUD gemini gemini-3.5-flash-lite vacation-days-v1 MAXIMO USD 0.001\n")
    denied = cli(["live-once"], _TTY(old_phrase), {"LOCALAPPDATA": str(tmp_path), "GEMINI_API_KEY": MARKER}, lambda: NOW)
    assert denied["reason"] == "confirmation_required" and denied["requests_sent"] == 0
    report = dry_run(lambda: NOW)
    assert report["default_transport"] == "DisabledGeminiTransport" and report["live_egress"] == "closed"
    monkeypatch.setattr(
        "app.enterprise_llm_providers.gemini_live.attempt_reservation", lambda: 1001)
    with pytest.raises(ProviderError) as budget:
        execute_once(object(), tmp_path / "over", lambda: NOW)
    assert budget.value.reason == "budget_exceeded" and list((tmp_path / "over").rglob("*")) == []
    environ = {"LOCALAPPDATA": str(tmp_path)}
    assert default_attempt_directory(environ).name == "c04-gemini-live-smoke"
    openai = Path(__file__).resolve().parents[1] / "app" / "enterprise_llm_providers" / "live_smoke.py"
    source = openai.read_text(encoding="utf-8")
    assert "c04-live-smoke" in source and "c04-gemini-live-smoke" not in source
    assert "openai" in OPENAI_PHRASE and OPENAI_PHRASE != CONFIRMATION_PHRASE
    gateway = (Path(__file__).resolve().parents[1] / "app" / "enterprise_ai_processing" / "gateway.py").read_text(encoding="utf-8")
    assert "type(self.model) is FakeEnterpriseModel" in gateway
